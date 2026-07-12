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
            # Alley blocks (e.g., "alley between X and Y") — stage 4 or stage 5 gazetteer
            result = self.stage_4_segment(norm_text, parsed, location_text)
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
            # Split multi-location and geocode each part
            # For now, treat as fallback to external geocoders
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
            WHERE add_number::numeric = %(house_num)s::numeric
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
            WHERE UPPER(REGEXP_REPLACE(street_name, '\s+\w+$', '')) = UPPER(%(street_name)s)
            ORDER BY in_range DESC
            LIMIT 1
        """
        result = self.query(sql, {
            "house_num": house_num,
            "street_name": street
        })

        if result:
            row = result[0]
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
        """Stage 3: Intersection match (e.g., 'Clark and Addison')."""
        # Look for "and" or "near" pattern: "street1 near/and street2"
        and_match = re.search(r'(\w+\s+\w*)\s+(?:AND|NEAR|AT)\s+(\w+\s+\w*)', norm_text)
        if not and_match:
            return None

        street1, street2 = and_match.group(1).strip(), and_match.group(2).strip()

        # Find intersection of two centerlines
        # FIX: centerlines.street_name has type suffix baked in; strip it when matching
        sql = """
            SELECT ST_X(ST_Intersection(c1.geom, c2.geom)) as lon,
                   ST_Y(ST_Intersection(c1.geom, c2.geom)) as lat
            FROM ref.centerlines c1
            JOIN ref.centerlines c2 ON ST_Intersects(c1.geom, c2.geom)
            WHERE UPPER(REGEXP_REPLACE(c1.street_name, '\s+\w+$', '')) = UPPER(%(street1)s)
              AND UPPER(REGEXP_REPLACE(c2.street_name, '\s+\w+$', '')) = UPPER(%(street2)s)
            LIMIT 1
        """
        result = self.query(sql, {
            "street1": street1,
            "street2": street2
        })

        if result and result[0].get("lon") is not None:
            row = result[0]
            return GeocodeResult(
                stage=3,
                method="intersection",
                geometry_type="POINT",
                coordinates=(row["lon"], row["lat"]),
                score=0.95,
                reason=f"Intersection: {street1} & {street2}"
            )

        return None

    def stage_4_segment(self, norm_text: str, parsed, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 4: Block/segment match (return whole segment as LINESTRING)."""
        street = parsed.get("street") if isinstance(parsed, dict) else getattr(parsed, "street", None)
        if not street:
            return None

        # Find all centerline segments for this street
        # FIX: centerlines.street_name has type suffix baked in; strip it when matching
        sql = """
            SELECT ST_AsText(geom) as geom_wkt, segment_id
            FROM ref.centerlines
            WHERE UPPER(REGEXP_REPLACE(street_name, '\s+\w+$', '')) = UPPER(%(street_name)s)
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

    def stage_5_gazetteer(self, norm_text: str, parsed: Dict, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 5: Named place match (gazetteer)."""
        # Try to find a gazetteer match
        place_search = parsed.get('street', '')
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
