"""Golden tests for Tier-1 validators (each includes pass + fail case)."""

import pytest
from holos_tools.validate.validators import (
    validate_field_completeness,
    validate_bbox_check,
    validate_budget_tieout,
)


class TestFieldCompleteness:
    """Test validator: all required fields present."""

    def test_pass_complete_record(self):
        """Golden pass: complete record with all required fields."""
        record = {
            "ward": 5,
            "year": 2012,
            "cost": 50000.0,
            "location": "N CALIFORNIA AVE & W SHAKESPEARE AVE",
        }
        result = validate_field_completeness(record)
        assert result.passed is True
        assert "All required fields present" in result.message

    def test_fail_missing_ward(self):
        """Golden fail: ward missing."""
        record = {
            "year": 2012,
            "cost": 50000.0,
            "location": "N CALIFORNIA AVE & W SHAKESPEARE AVE",
        }
        result = validate_field_completeness(record)
        assert result.passed is False
        assert "ward" in result.details["missing_fields"]

    def test_fail_missing_cost(self):
        """Golden fail: cost is None."""
        record = {
            "ward": 5,
            "year": 2012,
            "cost": None,
            "location": "N CALIFORNIA AVE & W SHAKESPEARE AVE",
        }
        result = validate_field_completeness(record)
        assert result.passed is False
        assert "cost" in result.details["missing_fields"]

    def test_fail_empty_location(self):
        """Golden fail: location is empty string."""
        record = {
            "ward": 5,
            "year": 2012,
            "cost": 50000.0,
            "location": "",
        }
        result = validate_field_completeness(record)
        assert result.passed is False
        assert "location" in result.details["missing_fields"]


class TestBboxCheck:
    """Test validator: coordinate within Chicago bounding box."""

    def test_pass_valid_chicago_coordinate(self):
        """Golden pass: coordinate inside Chicago."""
        # Downtown Chicago (verified real location)
        result = validate_bbox_check(lon=-87.6298, lat=41.8781)
        assert result.passed is True
        assert "within Chicago bbox" in result.message

    def test_fail_coordinate_too_far_west(self):
        """Golden fail: longitude too far west (would catch lon/lat swap from Indian Ocean)."""
        result = validate_bbox_check(lon=-100.0, lat=41.8781)
        assert result.passed is False
        assert "out_of_range_lon" in result.details["reason"]

    def test_fail_coordinate_too_far_north(self):
        """Golden fail: latitude too far north (would catch inverted coordinates)."""
        result = validate_bbox_check(lon=-87.6298, lat=50.0)
        assert result.passed is False
        assert "out_of_range_lat" in result.details["reason"]

    def test_fail_swapped_coordinates(self):
        """Golden fail: coordinates swapped (lat in lon place)."""
        # Swapped: putting lat (41.8781) in lon position catches it
        result = validate_bbox_check(lon=41.8781, lat=-87.6298)
        assert result.passed is False
        # The check should fail because 41.8781 > max_lon of -87.52


class TestBudgetTieout:
    """Test validator: total spend matches expected program size."""

    def test_pass_within_tolerance(self):
        """Golden pass: total spend within tolerance of expected."""
        records = [
            {"ward": 1, "year": 2012, "cost": 1_200_000},
            {"ward": 2, "year": 2012, "cost": 1_300_000},
            {"ward": 3, "year": 2012, "cost": 1_250_000},
            # ... (50 wards × ~$1.3M = ~$66M)
            # Using 3 wards for small test; total = $3.75M
            # Expected annual = $66M, so we test with a small subset
        ]
        # For a small subset, expect proportionally less
        expected_3wards = 3 * 1_300_000
        result = validate_budget_tieout(records, expected_total=expected_3wards)
        assert result.passed is True
        assert "within" in result.message.lower()

    def test_fail_way_over_budget(self):
        """Golden fail: total spend way above expected (e.g., double-counting)."""
        records = [
            {"ward": 1, "year": 2012, "cost": 2_000_000},
            {"ward": 2, "year": 2012, "cost": 2_000_000},
            {"ward": 3, "year": 2012, "cost": 2_000_000},
        ]
        # Total = $6M, expected = $3.9M (3 × $1.3M)
        # Variance = |6M - 3.9M| / 3.9M = 53% (way over 15% tolerance)
        expected_3wards = 3 * 1_300_000
        result = validate_budget_tieout(records, expected_total=expected_3wards)
        assert result.passed is False
        assert "variance" in result.details or "off expected" in result.message.lower()

    def test_fail_way_under_budget(self):
        """Golden fail: total spend way below expected (e.g., missing records)."""
        records = [
            {"ward": 1, "year": 2012, "cost": 500_000},
        ]
        # Total = $500k, expected = $1.3M
        # Variance = |500k - 1.3M| / 1.3M = 61% (way over 15% tolerance)
        result = validate_budget_tieout(records, expected_total=1_300_000)
        assert result.passed is False
        assert "off expected" in result.message.lower()

    def test_fail_empty_records(self):
        """Golden fail: no records to validate."""
        result = validate_budget_tieout([])
        assert result.passed is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
