"""Geocoding cascade: stages 0–5 (address normalization → gazetteer match)."""

import re
import unicodedata
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

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
        """Execute query and return results as list of dicts."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params or {})
                if cur.description:
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
                return []
        except Exception as e:
            print(f"Query error: {e}\nSQL: {sql}\nParams: {params}")
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


class GeocodeNormalizer:
    """Stage 0: Normalize address text."""

    # Abbreviations to expand (suffix-only, not directions)
    ABBREVIATIONS = {
        r'\bST\b': 'STREET',
        r'\bAVE\b': 'AVENUE',
        r'\bBLVD\b': 'BOULEVARD',
        r'\bDR\b': 'DRIVE',
        r'\bRD\b': 'ROAD',
        r'\bLN\b': 'LANE',
        r'\bCT\b': 'COURT',
        r'\bPL\b': 'PLACE',
        r'\bPK\b': 'PARK',
        # Don't expand directions: they're metadata, not part of street name
    }

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize address text: strip punctuation, expand abbreviations."""
        if not text:
            return ""

        # Uppercase
        text = text.upper()

        # Remove diacritics
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")

        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)

        # Expand abbreviations
        for abbr, full in GeocodeNormalizer.ABBREVIATIONS.items():
            text = re.sub(abbr, full, text)

        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text


class GeocodeParser:
    """Parse normalized address into components."""

    @staticmethod
    def parse(text: str) -> Dict[str, str]:
        """Parse address into number, street, direction."""
        # Simple parser: "123 N MICHIGAN AVE" → {number: 123, predir: N, street: MICHIGAN, suffix: AVE}
        parts = text.split()
        result = {
            "number": None,
            "predir": None,
            "street": None,
            "suffix": None,
        }

        if not parts:
            return result

        # First part: number?
        if parts[0].isdigit():
            result["number"] = int(parts[0])
            parts = parts[1:]

        # Next part: direction? (NORTH, SOUTH, EAST, WEST, etc.)
        if parts and parts[0] in ("NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "NORTHWEST", "SOUTHEAST", "SOUTHWEST"):
            result["predir"] = parts[0]
            parts = parts[1:]

        # Remaining: street name and suffix
        if parts:
            # Last part: suffix?
            if parts[-1] in ("STREET", "AVENUE", "BOULEVARD", "DRIVE", "ROAD", "LANE", "COURT", "PLACE", "PARK"):
                result["suffix"] = parts[-1]
                result["street"] = " ".join(parts[:-1])
            else:
                result["street"] = " ".join(parts)

        return result


class GeocodeCascade:
    """Run the geocoding cascade (stages 1–5)."""

    def __init__(self, db):
        """Initialize cascade with database connection."""
        self.db = db
        self.normalizer = GeocodeNormalizer()
        self.parser = GeocodeParser()

    def query(self, sql: str, params: dict = None) -> list:
        """Execute query and return results as list of dicts."""
        return self.db.execute(sql, params or {})

    def geocode(self, location_text: str, ward: Optional[str] = None) -> GeocodeResult:
        """Run full cascade on a location."""
        # Stage 0: Normalize
        norm_text = self.normalizer.normalize(location_text)
        parsed = self.parser.parse(norm_text)

        # Try stages 1–5 in order
        for stage_func in [
            self.stage_1_address_point,
            self.stage_2_centerline,
            self.stage_3_intersection,
            self.stage_4_segment,
            self.stage_5_gazetteer,
        ]:
            result = stage_func(norm_text, parsed, location_text)
            if result and result.score > 0:
                return result

        # Try Stage 6: External geocoders (Census + Nominatim)
        result = self.stage_6_external(location_text, norm_text)
        if result and result.score > 0:
            return result

        # All stages failed
        return GeocodeResult(
            stage=8,
            method="none",
            geometry_type="POINT",
            score=0.0,
            reason="No match found; escalate to human review"
        )

    def stage_1_address_point(self, norm_text: str, parsed, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 1: Exact match on address point."""
        # Support both dict and AddressComponents objects
        number = parsed.get("number") if isinstance(parsed, dict) else getattr(parsed, "number", None)
        street = parsed.get("street") if isinstance(parsed, dict) else getattr(parsed, "street", None)

        if not number or not street:
            return None

        # Query address_points for exact match (parameterized to prevent SQL injection)
        # Real schema: add_number (text), st_name, lon, lat
        sql = """
            SELECT lon, lat
            FROM ref.address_points
            WHERE add_number::text = %(address_number)s::text
              AND UPPER(st_name) = UPPER(%(street_name)s)
            LIMIT 1
        """
        result = self.query(sql, {
            "address_number": str(number),
            "street_name": street
        })

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
        """Stage 2: Interpolate on centerline."""
        number = parsed.get("number") if isinstance(parsed, dict) else getattr(parsed, "number", None)
        street = parsed.get("street") if isinstance(parsed, dict) else getattr(parsed, "street", None)

        if not number or not street:
            return None

        # Try to convert to int for interpolation
        try:
            house_num = int(number) if isinstance(number, str) else number
        except (ValueError, TypeError):
            return None

        # Find centerline segment (parameterized to prevent SQL injection)
        sql = """
            SELECT segment_id, from_house_num_l, to_house_num_l, from_house_num_r, to_house_num_r,
                   ST_X(ST_StartPoint(geom)) as start_lon, ST_Y(ST_StartPoint(geom)) as start_lat,
                   ST_X(ST_EndPoint(geom)) as end_lon, ST_Y(ST_EndPoint(geom)) as end_lat
            FROM ref.centerlines
            WHERE UPPER(street_name) = UPPER(%(street_name)s)
            LIMIT 1
        """
        result = self.query(sql, {"street_name": street})

        if result:
            row = result[0]

            # Try left side
            if row["from_house_num_l"] and row["to_house_num_l"] and \
               row["from_house_num_l"] <= house_num <= row["to_house_num_l"]:
                denom = row["to_house_num_l"] - row["from_house_num_l"]
                if denom > 0:
                    fraction = (house_num - row["from_house_num_l"]) / denom
                    lon = row["start_lon"] + fraction * (row["end_lon"] - row["start_lon"])
                    lat = row["start_lat"] + fraction * (row["end_lat"] - row["start_lat"])
                    return GeocodeResult(
                        stage=2,
                        method="centerline_interpolation",
                        geometry_type="POINT",
                        coordinates=(lon, lat),
                        score=0.88,
                        reason=f"Interpolated on centerline: {street}"
                    )

            # Try right side
            if row["from_house_num_r"] and row["to_house_num_r"] and \
               row["from_house_num_r"] <= house_num <= row["to_house_num_r"]:
                denom = row["to_house_num_r"] - row["from_house_num_r"]
                if denom > 0:
                    fraction = (house_num - row["from_house_num_r"]) / denom
                    lon = row["start_lon"] + fraction * (row["end_lon"] - row["start_lon"])
                    lat = row["start_lat"] + fraction * (row["end_lat"] - row["start_lat"])
                    return GeocodeResult(
                        stage=2,
                        method="centerline_interpolation",
                        geometry_type="POINT",
                        coordinates=(lon, lat),
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

        # Find intersection of two centerlines (parameterized to prevent SQL injection)
        sql = """
            SELECT ST_X(ST_Intersection(c1.geom, c2.geom)) as lon,
                   ST_Y(ST_Intersection(c1.geom, c2.geom)) as lat
            FROM ref.centerlines c1
            JOIN ref.centerlines c2 ON ST_Intersects(c1.geom, c2.geom)
            WHERE (UPPER(c1.street_name) = UPPER(%(street1)s) OR UPPER(c1.street_name) LIKE UPPER(%(street1_like)s))
              AND (UPPER(c2.street_name) = UPPER(%(street2)s) OR UPPER(c2.street_name) LIKE UPPER(%(street2_like)s))
            LIMIT 1
        """
        result = self.query(sql, {
            "street1": street1,
            "street1_like": f"%{street1}%",
            "street2": street2,
            "street2_like": f"%{street2}%"
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

    def stage_4_segment(self, norm_text: str, parsed: Dict, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 4: Block/segment match (return whole segment as LINESTRING)."""
        if not parsed.get("street"):
            return None

        # Find all centerline segments for this street (parameterized to prevent SQL injection)
        sql = """
            SELECT ST_AsText(geom) as geom_wkt, segment_id
            FROM ref.centerlines
            WHERE UPPER(street_name) = UPPER(%(street_name)s)
            LIMIT 1
        """
        result = self.query(sql, {"street_name": parsed['street']})

        if result:
            row = result[0]
            return GeocodeResult(
                stage=4,
                method="segment_clipping",
                geometry_type="LINESTRING",
                geometry_wkt=row["geom_wkt"],
                score=0.92,
                reason=f"Block face: {parsed['street']}"
            )

        return None

    def stage_5_gazetteer(self, norm_text: str, parsed: Dict, raw_text: str) -> Optional[GeocodeResult]:
        """Stage 5: Named place match (gazetteer)."""
        # Try to find a gazetteer match (parameterized to prevent SQL injection)
        place_search = parsed.get('street', '')
        if not place_search:
            return None

        sql = """
            SELECT ST_X(geom) as lon, ST_Y(geom) as lat, name
            FROM ref.gazetteer
            WHERE UPPER(name) = UPPER(%(place)s) OR UPPER(name) LIKE UPPER(%(place_like)s)
            LIMIT 1
        """
        result = self.query(sql, {
            "place": place_search,
            "place_like": f"%{place_search}%"
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
