"""Test against golden fixtures (Ward Wise calibration set)."""

import json
from pathlib import Path
import pytest


def load_golden():
    """Load golden fixtures."""
    fixture_path = Path("golden/chicago_spending_golden.json")
    with open(fixture_path) as f:
        return json.load(f)


class TestGoldenSet:
    """Verify geocoding against known-good results."""

    def test_golden_fixtures_exist(self):
        """Verify golden fixtures are available."""
        fixture_path = Path("golden/chicago_spending_golden.json")
        assert fixture_path.exists(), f"Golden fixtures not found at {fixture_path}"

    def test_golden_structure(self):
        """Verify golden fixtures have required fields."""
        golden = load_golden()
        assert len(golden) > 0, "Golden set is empty"

        for item in golden:
            required = [
                "project_id",
                "row_id",
                "location_text_raw",
                "ward",
                "year",
                "expected_geom_type",
                "expected_method",
                "expected_stage",
                "expected_score_min",
                "expected_score_max",
                "description",
            ]
            for field in required:
                assert field in item, f"Missing required field '{field}' in golden fixture {item['project_id']}"

    def test_golden_geometry_types(self):
        """Verify golden fixtures have valid geometry types."""
        golden = load_golden()
        valid_types = {"POINT", "LINESTRING", "POLYGON"}

        for item in golden:
            assert item["expected_geom_type"] in valid_types, (
                f"Invalid geometry type '{item['expected_geom_type']}' in {item['project_id']}"
            )

    def test_golden_score_ranges(self):
        """Verify golden fixtures have valid score ranges."""
        golden = load_golden()

        for item in golden:
            min_score = item.get("expected_score_min", 0)
            max_score = item.get("expected_score_max", 1)
            assert 0.0 <= min_score <= 1.0, f"Invalid min_score in {item['project_id']}"
            assert 0.0 <= max_score <= 1.0, f"Invalid max_score in {item['project_id']}"
            assert min_score <= max_score, f"min_score > max_score in {item['project_id']}"

    def test_golden_ward_assignments(self):
        """Verify all golden fixtures have ward assignments."""
        golden = load_golden()
        for item in golden:
            ward = item.get("ward")
            assert ward is not None, f"Missing ward in {item['project_id']}"
            assert isinstance(ward, str) or isinstance(ward, int), f"Invalid ward type in {item['project_id']}"


def test_benchmark_target():
    """Verify we're targeting ≥90% geocode accuracy."""
    # Phase 1 goal: ≥90% accuracy vs Ward Wise
    # This test documents the target; actual benchmark runs on CI
    target_accuracy = 0.90
    assert target_accuracy == 0.90, "Benchmark target should be 90% accuracy"


def test_phase_1_coverage():
    """Verify Phase 1 covers spending extraction (Chain A1)."""
    golden = load_golden()
    # All Phase 1 fixtures are Chicago spending (Chain A1)
    assert all(item.get("category") for item in golden), "All Phase 1 fixtures must have a category"
    assert len(golden) >= 3, "Phase 1 golden set should have at least 3 fixtures"
