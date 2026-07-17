"""Geocoding cascade: stages 0–8 (grammar-routed address matching)."""

import os
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from .grammar import GrammarClassifier
from .normalize import normalize
from .parser import AddressParser

try:
    import psycopg
except ImportError:
    psycopg = None

try:
    from .stage6_external import CensusGeocoder, NominatimGeocoder
except ImportError:
    CensusGeocoder = None
    NominatimGeocoder = None


class PostgresDB:
    """PostgreSQL database connection wrapper."""

    def __init__(self, dbname=None, user=None, host=None, port=None, password=None):
        """Initialize connection. Defaults from environment or localhost."""
        if not psycopg:
            raise ImportError("psycopg3 required for PostgreSQL connections")

        dbname = dbname or os.getenv("POSTGRES_DB", "holos")
        user = user or os.getenv("POSTGRES_USER", "holos")
        host = host or os.getenv("POSTGRES_HOST", "127.0.0.1")
        port = port or int(os.getenv("POSTGRES_PORT", 5432))
        password = password or os.getenv("POSTGRES_PASSWORD", "holos_dev_only")

        connstr = f"dbname={dbname} user={user} host={host} port={port} password={password}"
        self.conn = psycopg.connect(connstr)

    def execute(self, sql: str, params: dict = None) -> list:
        """Execute query and return results as list of dicts.

        CRITICAL: Do NOT swallow errors. Schema bugs must surface loudly.
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, params or {})
            if cur.description:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
            return []

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()


@dataclass
class GeocodeResult:
    """Result of a geocoding attempt."""
    stage: int
    method: str
    geometry_type: str  # POINT, LINESTRING, POLYGON
    coordinates: Tuple[float, float] = None  # (lon, lat) for POINT
    geometry_wkt: str = None  # WKT for complex geometries
    score: float = 0.0
    reason: str = ""


class GeocodeCascade:
    """Run the geocoding cascade (stages 0–8, grammar-routed)."""

    def __init__(self, db):
        """Initialize cascade with database connection."""
        self.db = db

    def query(self, sql: str, params: dict = None) -> list:
        """Execute query and return results as list of dicts."""
        return self.db.execute(sql, params or {})

    def geocode(self, location_text: str, ward: Optional[str] = None) -> GeocodeResult:
        """Run full cascade on a location (grammar-routed)."""
        # Stage 0: Normalize
        norm_text = normalize(location_text)
        parsed = AddressParser.parse(norm_text)

        # Classify grammar
        grammar = GrammarClassifier.classify(location_text, ward)

        # Route by grammar type (Bug 2 fix)
        if grammar.grammar == 'single_address':
            # Try stages 1–2 for single addresses
            for stage_func in [self.stage_1_address_point, self.stage_2_centerline]:
                result = stage_func(norm_text, parsed, location_text)
                if result and result.score > 0:
                    return result

        elif grammar.grammar == 'address_range':
            # Address ranges (e.g., "1200-1298 W Foster") also use stages 1–2
            # Try stage 2 for interpolation (centerline); fall back to stage 1 if exact match exists
            for stage_func in [self.stage_2_centerline, self.stage_1_address_point]:
                result = stage_func(norm_text, parsed, location_text)
                if result and result.score > 0:
                    return result

        elif grammar.grammar == 'intersection':
            # Stage 3 for intersections
            result = self.stage_3_intersection(norm_text, parsed, location_text)
            if result and result.score > 0:
                return result

        elif grammar.grammar == 'street_segment':
            # Stage 4 for street segments
            result = self.stage_4_segment(norm_text, parsed, location_text)
            if result and result.score > 0:
                return result

        elif grammar.grammar == 'hundred_block':
            # Hundred blocks (e.g., "200 block of W Division") — stage 4 segment lookup
            result = self.stage_4_segment(norm_text, parsed, location_text)
            if result and result.score > 0:
                return result

        elif grammar.grammar == 'alley_block_polygon':
            # Alley blocks bounded by 3+ streets (e.g., "W Chicago & N Bishop & W Fry & N Greenview")
            # Stage 3b: compute centroid of corner intersections
            result = self.stage_3_alley_block_polygon(location_text)
            if result and result.score > 0:
                return result
            # Fall back to gazetteer for named alleys
            result = self.stage_5_gazetteer(norm_text, parsed, location_text)
            if result and result.score > 0:
                return result

        elif grammar.grammar == 'named_place':
            # Stage 5 for gazetteer/named places
            result = self.stage_5_gazetteer(norm_text, parsed, location_text)
            if result and result.score > 0:
                return result

        elif grammar.grammar == 'wardwide':
            # Ward-level match (entire ward polygon)
            result = self.stage_5_gazetteer(norm_text, parsed, location_text)  # Use gazetteer for ward lookup
            if result and result.score > 0:
                return result

        elif grammar.grammar == 'multi_location':
            # Multi-location: "X & Y & Z; address" or multiple locations
            # Real algorithm: split, geocode all parts, return multi-point or centroid
            # GUARD: Do NOT return partial results as if they're complete answers.
            # This is the same confidently-wrong trap as stage 4's arbitrary LIMIT 1.
            # Until we implement full multi-point handling, escalate.
            # TODO: implement proper multi-location (split, geocode each, centroid or multi-point)
            pass

        # Stage 6: External geocoders (Census + Nominatim) — fallback for any unmatched grammar
        # SKIP for now: Census API hangs; need timeout + error handling
        # result = self.stage_6_external(location_text, norm_text)
        # if result and result.score > 0:
        #     return result

        # Stage 8: All stages failed; escalate to human review
        return GeocodeResult(
            stage=8,
            method="none",
            geometry_type="POINT",
            score=0.0,
            reason=f"No match found ({grammar.grammar}); escalate to human review"
        )

    def stage_1_address_point(self, norm_text: str, parsed, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 1: Exact match on address point (Bug 3 fix: use correct schema columns)."""
        # Support both dict and AddressComponents objects
        number = parsed.get("number") if isinstance(parsed, dict) else getattr(parsed, "number", None)
        street = parsed.get("street") if isinstance(parsed, dict) else getattr(parsed, "street", None)
        predir = parsed.get("predir") if isinstance(parsed, dict) else getattr(parsed, "predir", None)

        if not number or not street:
            return None

        # Normalize predir: parser returns spelled-out (NORTH/SOUTH/EAST/WEST),
        # but database stores abbreviations (N/S/E/W)
        predir_map = {
            "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
            "N": "N", "S": "S", "E": "E", "W": "W"  # Already abbreviated
        }
        predir_normalized = predir_map.get(predir.upper()) if predir else None

        # Query address_points for exact match
        # Use numeric comparison for house numbers (3327.0 vs 3327)
        # Include predir to disambiguate when multiple entries exist for same address
        sql = """
            SELECT ST_X(geom) as lon, ST_Y(geom) as lat
            FROM ref.address_points
            WHERE address_number::numeric = %(house_num)s::numeric
              AND UPPER(st_name) = UPPER(%(street_name)s)
        """
        params = {
            "house_num": int(number) if isinstance(number, str) else number,
            "street_name": street
        }

        # If predir is present and normalized, match it; otherwise return any match
        if predir_normalized:
            sql += " AND predir = %(predir)s"
            params["predir"] = predir_normalized

        sql += " LIMIT 1"

        result = self.query(sql, params)

        if result:
            row = result[0]
            return GeocodeResult(
                stage=1,
                method="address_point_exact",
                geometry_type="POINT",
                coordinates=(row["lon"], row["lat"]),
                score=0.97,
                reason=f"Exact match: {number} {street}"
            )

        return None

    def stage_2_centerline(self, norm_text: str, parsed, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 2: Interpolate on centerline (Bug 4 fix: filter by house range IN SQL, use PostGIS interpolation)."""
        number = parsed.get("number") if isinstance(parsed, dict) else getattr(parsed, "number", None)
        street = parsed.get("street") if isinstance(parsed, dict) else getattr(parsed, "street", None)

        if not number or not street:
            return None

        # Try to convert to int for interpolation
        try:
            house_num = int(number) if isinstance(number, str) else number
        except (ValueError, TypeError):
            return None

        # Find centerline segment whose house-number range CONTAINS the address
        # FIX: centerlines.street_name has type suffix baked in (e.g., "FLETCHER ST")
        # but address_points.st_name has only base name (e.g., "FLETCHER").
        # Strip the trailing type word from centerlines.street_name when joining.
        # Also: centerlines.geom is ST_MultiLineString, but ST_LineInterpolatePoint needs a line.
        # Use ST_LineMerge to merge multilinestring into a single linestring.
        sql = """
            SELECT
              segment_id,
              ST_X(ST_LineInterpolatePoint(ST_LineMerge(geom),
                CASE
                  WHEN from_house_num_l <= %(house_num)s AND %(house_num)s <= to_house_num_l THEN
                    (%(house_num)s - from_house_num_l)::float / NULLIF(to_house_num_l - from_house_num_l, 0)
                  WHEN from_house_num_r <= %(house_num)s AND %(house_num)s <= to_house_num_r THEN
                    (%(house_num)s - from_house_num_r)::float / NULLIF(to_house_num_r - from_house_num_r, 0)
                  ELSE 0.5
                END
              )) as lon,
              ST_Y(ST_LineInterpolatePoint(ST_LineMerge(geom),
                CASE
                  WHEN from_house_num_l <= %(house_num)s AND %(house_num)s <= to_house_num_l THEN
                    (%(house_num)s - from_house_num_l)::float / NULLIF(to_house_num_l - from_house_num_l, 0)
                  WHEN from_house_num_r <= %(house_num)s AND %(house_num)s <= to_house_num_r THEN
                    (%(house_num)s - from_house_num_r)::float / NULLIF(to_house_num_r - from_house_num_r, 0)
                  ELSE 0.5
                END
              )) as lat,
              (from_house_num_l <= %(house_num)s AND %(house_num)s <= to_house_num_l) OR
              (from_house_num_r <= %(house_num)s AND %(house_num)s <= to_house_num_r) as in_range
            FROM ref.centerlines
            WHERE UPPER(REGEXP_REPLACE(street_name, '\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$', '')) = UPPER(%(street_name)s)
            ORDER BY in_range DESC
            LIMIT 1
        """
        result = self.query(sql, {
            "house_num": house_num,
            "street_name": street
        })

        if result:
            row = result[0]
            # GUARD: if the house number isn't in this segment's range (L or R),
            # don't return the midpoint at 0.88 confidence — that's the same trap
            # as stage 4's arbitrary LIMIT 1. Escalate instead.
            if not row["in_range"]:
                return None

            return GeocodeResult(
                stage=2,
                method="centerline_interpolation",
                geometry_type="POINT",
                coordinates=(row["lon"], row["lat"]),
                score=0.88,
                reason=f"Interpolated on centerline: {street}"
            )

        return None

    def stage_3_intersection(self, norm_text: str, parsed: Dict, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 3: Intersection match (e.g., 'Clark and Addison' or 'Clark & Addison')."""
        # Look for delimiter: &, "and", "near", or "at"
        # Regex: (street1) (delimiter) (street2)
        and_match = re.search(r'(\w+\s+\w*)\s+(?:AND|NEAR|AT|&)\s+(\w+\s+\w*)', norm_text)
        if not and_match:
            return None

        street1, street2 = and_match.group(1).strip(), and_match.group(2).strip()

        # Normalize extracted streets: strip leading directional, then trailing suffix
        def normalize_street(s):
            # Strip leading directional FIRST (N, S, E, W, NORTH, etc.)
            s = re.sub(r'^[NSEW](?:\s+|$)|\b(?:NORTH|SOUTH|EAST|WEST)\b\s*', '', s).strip()
            # Then strip trailing type word (AVE, ST, AVENUE, COURT, etc.)
            s = re.sub(r'\s+\w+$', '', s).strip()
            return s

        street1_norm = normalize_street(street1)
        street2_norm = normalize_street(street2)

        if not street1_norm or not street2_norm:
            return None

        # Find intersection of two centerlines
        # Use normalized names and REGEXP_REPLACE to strip suffix in database
        # GUARD: ST_Intersection can return LineString; use ST_Centroid for robustness
        sql = """
            SELECT ST_X(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lon,
                   ST_Y(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lat
            FROM ref.centerlines c1
            JOIN ref.centerlines c2 ON ST_Intersects(c1.geom, c2.geom)
            WHERE UPPER(REGEXP_REPLACE(c1.street_name, '\s+\w+$', '')) = UPPER(%(street1)s)
              AND UPPER(REGEXP_REPLACE(c2.street_name, '\s+\w+$', '')) = UPPER(%(street2)s)
            LIMIT 1
        """
        result = self.query(sql, {
            "street1": street1_norm,
            "street2": street2_norm
        })

        if result and result[0].get("lon") is not None:
            row = result[0]
            return GeocodeResult(
                stage=3,
                method="intersection",
                geometry_type="POINT",
                coordinates=(row["lon"], row["lat"]),
                score=0.95,
                reason=f"Intersection: {street1_norm} & {street2_norm}"
            )

        return None

    def stage_3_alley_block_polygon(self, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 3b: Alley block polygon (3+ bounded streets).

        Algorithm:
        1. Split location on & to get street list
        2. Normalize each street name (reuse intersection normalization)
        3. For each pair of streets, query the intersection
        4. Collect corners → ST_Centroid = representative POINT
        5. GUARD: <3 corners → escalate (don't return confidently-wrong result)
        """
        # Split on &, handling both spaced and unspaced (e.g., "AVE&ST" vs "AVE & ST")
        street_pattern = r'([A-Z\s]+(?:ST|AVE|BLVD|RD|DRIVE|ROAD|LANE|LN|CT|COURT|PLACE|PL|DR|AV|BV|PKWY))'
        streets_raw = re.split(r'\s*&\s*', raw_text.strip())

        if len(streets_raw) < 3:
            return None  # Need 3+ streets

        # Normalize streets: strip direction + suffix (reuse intersection logic)
        def normalize_street(s):
            s = s.strip()
            # Strip leading directional FIRST
            s = re.sub(r'^[NSEW](?:\s+|$)|\b(?:NORTH|SOUTH|EAST|WEST)\b\s*', '', s).strip()
            # Then strip trailing type word
            s = re.sub(r'\s+\w+$', '', s).strip()
            return s

        streets_norm = [normalize_street(s) for s in streets_raw]
        streets_norm = [s for s in streets_norm if s]  # Remove empty

        if len(streets_norm) < 3:
            return None

        # Query all pairs of streets for their intersections
        corners = []

        for i in range(len(streets_norm)):
            for j in range(i+1, len(streets_norm)):
                street_i = streets_norm[i]
                street_j = streets_norm[j]

                sql = """
                    SELECT ST_X(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lon,
                           ST_Y(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lat
                    FROM ref.centerlines c1
                    JOIN ref.centerlines c2 ON ST_Intersects(c1.geom, c2.geom)
                    WHERE UPPER(REGEXP_REPLACE(c1.street_name, '\s+\w+$', '')) = UPPER(%(street_i)s)
                      AND UPPER(REGEXP_REPLACE(c2.street_name, '\s+\w+$', '')) = UPPER(%(street_j)s)
                    LIMIT 1
                """

                result = self.query(sql, {"street_i": street_i, "street_j": street_j})
                if result and result[0].get("lon") is not None:
                    corners.append((result[0]["lon"], result[0]["lat"]))

        # GUARD: Need at least 3 corners to form a real enclosed area
        if len(corners) < 3:
            return None  # Escalate; insufficient geometry

        # Centroid of all corners
        avg_lon = sum(c[0] for c in corners) / len(corners)
        avg_lat = sum(c[1] for c in corners) / len(corners)

        return GeocodeResult(
            stage=3,
            method="alley_block_polygon",
            geometry_type="POINT",
            coordinates=(avg_lon, avg_lat),
            score=0.90,
            reason=f"Alley block: {len(corners)} corners, bounded by {len(streets_norm)} streets"
        )

    def stage_4_segment(self, norm_text: str, parsed, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 4: Block/segment match (return segment as LINESTRING).

        For bounded ranges like "ON BELDEN FROM TALMAN TO WASHTENAW":
        1. Parse the main street (BELDEN) and two bounding cross-streets (TALMAN, WASHTENAW)
        2. Find the two bounding intersections in centerlines
        3. Extract the segment between those two points
        4. Return as LINESTRING geometry

        GUARD: If either endpoint can't be resolved, escalate (don't guess).
        Confident-wrong segments are worse than honest misses.
        """
        # Try to parse range format: "ON STREET FROM X TO Y"
        # Allows numeric street names (50TH, 43RD) and special characters
        # Match: ON <main_street> FROM <from_street> TO <to_street>
        range_match = re.search(
            r'ON\s+([A-Z0-9\s\-&\(\)\.]+?)\s+FROM\s+([A-Z0-9\s\-&\(\)\.]+?)\s+TO\s+([A-Z0-9\s\-&\(\)\.]+?)(?:\s+\(|\s*$)',
            raw_text.upper()
        )

        if range_match:
            # This is a bounded range; implement real FROM/TO bounding
            main_street = range_match.group(1).strip()
            from_street = range_match.group(2).strip()
            to_street = range_match.group(3).strip()

            return self._geocode_bounded_range(main_street, from_street, to_street, raw_text)

        # Not a range format; fall back to simple street lookup
        street = parsed.get("street") if isinstance(parsed, dict) else getattr(parsed, "street", None)
        if not street:
            return None

        # Simple street (no FROM/TO)
        sql = """
            SELECT ST_AsText(geom) as geom_wkt, segment_id
            FROM ref.centerlines
            WHERE UPPER(REGEXP_REPLACE(street_name, '\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$', '')) = UPPER(%(street_name)s)
            LIMIT 1
        """
        result = self.query(sql, {"street_name": street})

        if result:
            row = result[0]
            street_name_display = street if isinstance(parsed, dict) else street
            return GeocodeResult(
                stage=4,
                method="segment_clipping",
                geometry_type="LINESTRING",
                geometry_wkt=row["geom_wkt"],
                score=0.92,
                reason=f"Block face: {street_name_display}"
            )

        return None

    def _clean_street_name(self, street: str) -> str:
        """Clean a street name for database matching.

        Removes:
        - Leading directional (N, S, E, W)
        - Coordinate suffixes ((XXXX N), (XXXX W), etc.)
        - Trailing numeric values

        Example: "N TALMAN AV (2632 W)" → "TALMAN AV"
        """
        # Remove leading directional (N, S, E, W)
        street = re.sub(r'^\s*[NSEW]\s+', '', street)

        # Remove coordinate suffixes like (2632 W) or (1234 N)
        street = re.sub(r'\s*\(\d+\s*[NSEW]\)', '', street)

        # Remove trailing numeric values
        street = re.sub(r'\s+\d+\s*$', '', street)

        return street.strip()

    def _geocode_bounded_range(self, main_street: str, from_street: str, to_street: str, raw_text: str) -> Optional[GeocodeResult]:
        """Geocode a bounded range by finding the two bounding intersections.

        Given "BELDEN FROM TALMAN TO WASHTENAW", find:
        1. Intersection of BELDEN ∩ TALMAN (using JOIN + ST_Intersects, like stage_3)
        2. Intersection of BELDEN ∩ WASHTENAW
        3. Return the segment between those two points

        GUARD: If either intersection can't be found, escalate (return None).
        Never return a confident segment we can't properly bound.

        Uses the proven stage_3_intersection pattern (JOIN with ST_Intersects),
        not single-row matching which would return NULL for unrelated segments.
        """
        # Clean street names for database matching
        main_street_clean = self._clean_street_name(main_street)
        from_street_clean = self._clean_street_name(from_street)
        to_street_clean = self._clean_street_name(to_street)

        # Strip trailing STREET-TYPE SUFFIX ONLY (e.g., "MAPLEWOOD AVENUE" -> "MAPLEWOOD")
        # Do NOT strip multi-word street names like "LE MOYNE", "NEW ENGLAND", "SOUTH SHORE"
        # Only remove known suffixes: ST, AVE, BLVD, etc.
        street_type_pattern = r'\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$'
        main_street_clean = re.sub(street_type_pattern, '', main_street_clean, flags=re.IGNORECASE)
        from_street_clean = re.sub(street_type_pattern, '', from_street_clean, flags=re.IGNORECASE)
        to_street_clean = re.sub(street_type_pattern, '', to_street_clean, flags=re.IGNORECASE)

        # Find the first intersection (MAIN_STREET ∩ FROM_STREET)
        # Reuse stage_3 pattern: JOIN on ST_Intersects across all segments
        # GUARD: ST_Intersection can return LineString; use ST_Centroid for robustness
        sql_from = """
            SELECT ST_X(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lon,
                   ST_Y(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lat
            FROM ref.centerlines c1
            JOIN ref.centerlines c2 ON ST_Intersects(c1.geom, c2.geom)
            WHERE UPPER(REGEXP_REPLACE(c1.street_name, '\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$', '')) = UPPER(%(main_street)s)
              AND UPPER(REGEXP_REPLACE(c2.street_name, '\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$', '')) = UPPER(%(from_street)s)
            LIMIT 1
        """

        result_from = self.query(sql_from, {"main_street": main_street_clean, "from_street": from_street_clean})
        if not result_from or result_from[0].get("lon") is None:
            # Couldn't resolve FROM endpoint; escalate
            return None

        # Find the second intersection (MAIN_STREET ∩ TO_STREET)
        sql_to = """
            SELECT ST_X(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lon,
                   ST_Y(ST_Centroid(ST_Intersection(c1.geom, c2.geom))) as lat
            FROM ref.centerlines c1
            JOIN ref.centerlines c2 ON ST_Intersects(c1.geom, c2.geom)
            WHERE UPPER(REGEXP_REPLACE(c1.street_name, '\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$', '')) = UPPER(%(main_street)s)
              AND UPPER(REGEXP_REPLACE(c2.street_name, '\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$', '')) = UPPER(%(to_street)s)
            LIMIT 1
        """

        result_to = self.query(sql_to, {"main_street": main_street_clean, "to_street": to_street_clean})
        if not result_to or result_to[0].get("lon") is None:
            # Couldn't resolve TO endpoint; escalate
            return None

        # Get the main street centerline segment and clip between intersections
        # Find segment closest to both intersection points (minimizes distance to both)
        # Use ST_LineSubstring to extract segment between intersections on that segment
        # Finally ST_LineInterpolatePoint to get midpoint for single point result
        sql_clipped = """
            WITH all_segments AS (
                SELECT
                    c.geom,
                    ST_Distance(c.geom, ST_Point(%(from_lon)s, %(from_lat)s, 4326)) as dist_from,
                    ST_Distance(c.geom, ST_Point(%(to_lon)s, %(to_lat)s, 4326)) as dist_to
                FROM ref.centerlines c
                WHERE UPPER(REGEXP_REPLACE(c.street_name, '\s+(ST|AVE|AVENUE|BLVD|BOULEVARD|STREET|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT|PLACE|PL|PARK|PK|SQUARE|SQ|TERRACE|TERR|TRAIL|PARKWAY|PKWY)$', '')) = UPPER(%(main_street)s)
            ),
            best_segment AS (
                SELECT geom
                FROM all_segments
                ORDER BY dist_from + dist_to
                LIMIT 1
            ),
            clipped_segment AS (
                SELECT
                    ST_LineSubstring(
                        geom,
                        LEAST(
                            ST_LineLocatePoint(geom, ST_Point(%(from_lon)s, %(from_lat)s, 4326)),
                            ST_LineLocatePoint(geom, ST_Point(%(to_lon)s, %(to_lat)s, 4326))
                        ),
                        GREATEST(
                            ST_LineLocatePoint(geom, ST_Point(%(from_lon)s, %(from_lat)s, 4326)),
                            ST_LineLocatePoint(geom, ST_Point(%(to_lon)s, %(to_lat)s, 4326))
                        )
                    ) as segment_geom
                FROM best_segment
            )
            SELECT
                ST_AsText(segment_geom) as segment_wkt,
                ST_X(ST_LineInterpolatePoint(segment_geom, 0.5)) as midpoint_lon,
                ST_Y(ST_LineInterpolatePoint(segment_geom, 0.5)) as midpoint_lat
            FROM clipped_segment
            WHERE ST_GeometryType(segment_geom) IN ('ST_LineString', 'ST_MultiLineString')
        """

        result_main = self.query(sql_clipped, {
            "main_street": main_street_clean,
            "from_lon": result_from[0]["lon"],
            "from_lat": result_from[0]["lat"],
            "to_lon": result_to[0]["lon"],
            "to_lat": result_to[0]["lat"]
        })
        if not result_main or result_main[0].get("midpoint_lon") is None:
            # Couldn't find main street or clip segment; escalate
            return None

        # Both endpoints resolved and segment clipped; return the midpoint of the bounded range
        row = result_main[0]
        return GeocodeResult(
            stage=4,
            method="range_bounding",
            geometry_type="POINT",
            coordinates=(row["midpoint_lon"], row["midpoint_lat"]),
            score=0.85,
            reason=f"Range: {main_street} from {from_street} to {to_street}"
        )

    def stage_5_gazetteer(self, norm_text: str, parsed: Dict, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 5: Named place match (gazetteer)."""
        # Try to find a gazetteer match
        place_search = parsed.get('street', '') if isinstance(parsed, dict) else getattr(parsed, 'street', '')
        if not place_search:
            return None

        # Gazetteer may also have type suffix (e.g., "MILLENNIUM PARK" stored as is, or normalized)
        # Try both exact match and match after stripping suffix
        sql = """
            SELECT ST_X(geom) as lon, ST_Y(geom) as lat, name
            FROM ref.gazetteer
            WHERE UPPER(name) = UPPER(%(place)s)
               OR UPPER(REGEXP_REPLACE(name, '\s+\w+$', '')) = UPPER(%(place)s)
            LIMIT 1
        """
        result = self.query(sql, {
            "place": place_search
        })

        if result:
            row = result[0]
            return GeocodeResult(
                stage=5,
                method="gazetteer",
                geometry_type="POLYGON",
                coordinates=(row["lon"], row["lat"]),
                score=0.90,
                reason=f"Named place: {row.get('name', place_search)}"
            )

        return None

    def stage_6_external(self, raw_text: str, norm_text: str) -> Optional[GeocodeResult]:
        """Stage 6: External geocoders (Census Geocoder + Nominatim fallback)."""
        if not raw_text:
            return None

        # Try Census Geocoder first (free, U.S. coverage)
        if CensusGeocoder:
            result = CensusGeocoder.geocode(raw_text)
            if result:
                return GeocodeResult(
                    stage=6,
                    method="census_geocoder",
                    geometry_type="POINT",
                    coordinates=(result.lon, result.lat),
                    score=result.score,
                    reason=f"Census Geocoder: {result.match_type}"
                )

        # Fallback: Nominatim (OpenStreetMap, global coverage)
        if NominatimGeocoder:
            result = NominatimGeocoder.geocode(raw_text)
            if result:
                lon, lat, score = result
                return GeocodeResult(
                    stage=6,
                    method="nominatim",
                    geometry_type="POINT",
                    coordinates=(lon, lat),
                    score=score,
                    reason="Nominatim (OSM)"
                )

        return None
