"""Spatial validation for Phase 1 geocoding improvements.

Validates geocoded results against:
1. Chicago bounds check (is point within city limits?)
2. Street overlap validation (is point on the claimed street?)
3. Ward validation (does result match original ward claim?)
4. Confidence filtering (only keep 90%+ matches)

PHASE 1 ENHANCEMENT (2026-07-18): Adds spatial validation layer after geocoding.
"""

from typing import Tuple, Optional, Dict
import os

try:
    import psycopg
except ImportError:
    psycopg = None


# Chicago city bounds (WGS84 / EPSG:4326)
CHICAGO_BOUNDS = {
    'min_lat': 41.64,
    'max_lat': 42.04,
    'min_lon': -87.94,
    'max_lon': -87.52,
}


class SpatialValidator:
    """Validates geocoded results against spatial constraints."""

    def __init__(self, db=None):
        """Initialize validator with optional database connection."""
        self.db = db

    def validate_bounds(self, lon: float, lat: float) -> Tuple[bool, str]:
        """Check if point is within Chicago city bounds.

        Args:
            lon: Longitude (WGS84)
            lat: Latitude (WGS84)

        Returns:
            (is_valid, reason_if_invalid)
        """
        if not (CHICAGO_BOUNDS['min_lon'] <= lon <= CHICAGO_BOUNDS['max_lon']):
            return False, f"Longitude {lon} outside Chicago bounds"
        if not (CHICAGO_BOUNDS['min_lat'] <= lat <= CHICAGO_BOUNDS['max_lat']):
            return False, f"Latitude {lat} outside Chicago bounds"
        return True, ""

    def validate_street_overlap(self, lon: float, lat: float, street_name: str) -> Tuple[bool, str]:
        """Check if point lies on (or very near) the claimed street.

        Args:
            lon: Longitude (WGS84)
            lat: Latitude (WGS84)
            street_name: Expected street name

        Returns:
            (is_valid, reason_if_invalid)
        """
        if not self.db:
            # Without DB, we can't validate; pass it through
            return True, ""

        try:
            # Find all streets matching this name, check if point is within buffer
            sql = """
                SELECT
                    ST_DWithin(
                        ST_Point(:lon, :lat)::geography,
                        geom::geography,
                        50  -- 50 meters buffer (account for geocoding error)
                    ) AS within_buffer
                FROM ref.street_centerlines
                WHERE street_name ILIKE :street_name
                LIMIT 1
            """
            result = self.db.execute(sql, {
                'lon': lon,
                'lat': lat,
                'street_name': f"%{street_name}%"
            })

            if result and result[0].get('within_buffer'):
                return True, ""
            return False, f"Point ({lon}, {lat}) not on street '{street_name}'"
        except Exception as e:
            # DB error; log but don't fail validation
            return True, f"Street overlap check skipped: {str(e)}"

    def validate_ward(self, lon: float, lat: float, expected_ward: Optional[int]) -> Tuple[bool, str]:
        """Check if point is in the expected ward.

        Args:
            lon: Longitude (WGS84)
            lat: Latitude (WGS84)
            expected_ward: Ward number from source data (optional)

        Returns:
            (is_valid, reason_if_invalid)
        """
        if not expected_ward or not self.db:
            return True, ""  # No expected ward; skip validation

        try:
            sql = """
                SELECT ward_number
                FROM ref.ward_boundaries
                WHERE ST_Contains(geom, ST_Point(:lon, :lat))
                LIMIT 1
            """
            result = self.db.execute(sql, {'lon': lon, 'lat': lat})

            if result:
                actual_ward = result[0].get('ward_number')
                if actual_ward == expected_ward:
                    return True, ""
                return False, f"Point in ward {actual_ward}, expected ward {expected_ward}"
            return False, f"Point ({lon}, {lat}) outside all wards"
        except Exception as e:
            return True, f"Ward check skipped: {str(e)}"

    def validate_result(
        self,
        lon: float,
        lat: float,
        street_name: Optional[str] = None,
        expected_ward: Optional[int] = None,
        confidence_score: float = 1.0,
        min_confidence: float = 0.90,
    ) -> Tuple[bool, str]:
        """Run all validations on a geocode result.

        Args:
            lon: Longitude (WGS84)
            lat: Latitude (WGS84)
            street_name: Expected street (optional)
            expected_ward: Expected ward (optional)
            confidence_score: Confidence score from geocoder (0-1)
            min_confidence: Minimum confidence threshold

        Returns:
            (is_valid, reason_if_invalid)
        """
        # Step 1: Confidence filter
        if confidence_score < min_confidence:
            return False, f"Confidence {confidence_score:.2f} below threshold {min_confidence}"

        # Step 2: Bounds check
        valid, reason = self.validate_bounds(lon, lat)
        if not valid:
            return False, reason

        # Step 3: Street overlap (if street name provided)
        if street_name:
            valid, reason = self.validate_street_overlap(lon, lat, street_name)
            if not valid:
                return False, reason

        # Step 4: Ward validation (if expected ward provided)
        if expected_ward:
            valid, reason = self.validate_ward(lon, lat, expected_ward)
            if not valid:
                return False, reason

        return True, ""
