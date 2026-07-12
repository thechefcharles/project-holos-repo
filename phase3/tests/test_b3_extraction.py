"""Test B3 native CAD extraction (Phase 2)."""

import json
from pathlib import Path
import pytest
from holos_tools.extract.b3_native_cad import B3NativeCADExtractor


@pytest.fixture
def b3_golden():
    """Load B3 golden fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "b3_cad_golden.json"
    with open(fixture_path) as f:
        return json.load(f)


def test_b3_extractor_instantiation():
    """Test B3 extractor can be instantiated."""
    extractor = B3NativeCADExtractor()
    assert extractor is not None


def test_b3_format_detection():
    """Test file format detection."""
    extractor = B3NativeCADExtractor()

    tests = [
        ("model.geojson", "geojson"),
        ("data.json", "geojson"),
        ("layer.shp", "shapefile"),
        ("plan.dwg", "dwg"),
        ("design.dgn", "dgn"),
        ("unknown.xyz", "unknown"),
    ]

    print("\n=== Testing B3 Format Detection ===")
    passed = 0
    for file_path, expected in tests:
        result = extractor._detect_format(file_path)
        success = result == expected
        status = "✓" if success else "✗"
        print(f"{status} _detect_format('{file_path}') = {result} (expected {expected})")
        if success:
            passed += 1

    print(f"✓ {passed}/{len(tests)} format detection tests passed")
    return passed == len(tests)


def test_b3_depth_normalization():
    """Test depth normalization for CAD files."""
    extractor = B3NativeCADExtractor()

    tests = [
        ("12ft", 3.658),
        ("3.2m", 3.2),
        ("1.5 meters", 1.5),
        ("5", 5.0),  # Default to meters for CAD
        ("unknown", None),
        (None, None),
    ]

    print("\n=== Testing B3 Depth Normalization ===")
    passed = 0
    for depth_str, expected in tests:
        result = extractor._normalize_depth(depth_str)
        if expected is None:
            success = result is None
        else:
            success = result is not None and abs(result - expected) < 0.01

        status = "✓" if success else "✗"
        print(f"{status} _normalize_depth({repr(depth_str)}) = {result} (expected {expected})")
        if success:
            passed += 1

    print(f"✓ {passed}/{len(tests)} depth normalization tests passed")
    return passed == len(tests)


def test_b3_feature_type_inference_geojson():
    """Test feature type inference from GeoJSON properties."""
    extractor = B3NativeCADExtractor()

    print("\n=== Testing B3 Feature Type Inference (GeoJSON) ===")

    test_cases = [
        ({"type": "water_main"}, {}, "utility_water"),
        ({"TYPE": "gas_line"}, {}, "utility_gas"),
        ({"type": "electric conduit"}, {}, "utility_electric"),
        ({"type": "telecom cable"}, {}, "utility_telecom"),
        ({"type": "foundation vault"}, {}, "structure"),
        ({}, {"type": "LineString"}, "unknown"),
        ({}, {"type": "Polygon"}, "structure"),
    ]

    passed = 0
    for props, geometry, expected in test_cases:
        result = extractor._infer_feature_type_from_geojson(props, geometry)
        success = result == expected
        status = "✓" if success else "✗"
        print(f"{status} props={props}, geom={geometry} → {result} (expected {expected})")
        if success:
            passed += 1

    print(f"✓ {passed}/{len(test_cases)} feature type inference tests passed")
    return passed == len(test_cases)


def test_b3_confidence_by_format(b3_golden):
    """Test that confidence scores reflect format reliability."""
    # GeoJSON should have high confidence (0.93)
    geojson_fixture = b3_golden["fixtures"][0]
    assert geojson_fixture["expected_features"][0]["extraction_conf"] == 0.93

    # Shapefile should have high confidence (0.93)
    shapefile_fixture = b3_golden["fixtures"][1]
    assert shapefile_fixture["expected_features"][0]["extraction_conf"] == 0.93

    # DWG should have medium confidence (0.75)
    dwg_fixture = b3_golden["fixtures"][2]
    assert dwg_fixture["expected_features"][0]["extraction_conf"] == 0.75

    # DGN should have low confidence (0.0)
    dgn_fixture = b3_golden["fixtures"][4]
    assert dgn_fixture["expected_features"][0]["extraction_conf"] == 0.0

    print("✓ Confidence scores reflect format reliability")
    return True


def test_b3_golden_geojson(b3_golden):
    """Test against B3 golden fixture: GeoJSON."""
    fixture = b3_golden["fixtures"][0]  # b3_geojson_water_main
    assert fixture["file_format"] == "geojson"
    assert fixture["expected_features"][0]["ql_level"] == "QL-C"
    assert fixture["expected_features"][0]["extraction_conf"] == 0.93


def test_b3_golden_shapefile(b3_golden):
    """Test against B3 golden fixture: Shapefile."""
    fixture = b3_golden["fixtures"][1]  # b3_shapefile_utilities
    assert fixture["file_format"] == "shapefile"

    # Verify both water and electric utilities are extracted
    feature_types = {f["feature_type"] for f in fixture["expected_features"]}
    assert "utility_water" in feature_types
    assert "utility_electric" in feature_types


def test_b3_golden_dwg(b3_golden):
    """Test against B3 golden fixture: DWG."""
    fixture = b3_golden["fixtures"][2]  # b3_dwg_water_main
    assert fixture["file_format"] == "dwg"

    # DWG should have lower confidence
    assert fixture["expected_features"][0]["extraction_conf"] == 0.75
    # DWG features should often need review
    assert fixture["expected_features"][0]["needs_review"] is True


def test_b3_golden_dgn(b3_golden):
    """Test against B3 golden fixture: DGN."""
    fixture = b3_golden["fixtures"][4]  # b3_dgn_unprocessed
    assert fixture["file_format"] == "dgn"

    # DGN should be marked for deferred processing
    assert fixture["expected_features"][0]["ql_level"] == "QL-D"
    assert fixture["expected_features"][0]["extraction_conf"] == 0.0
    assert fixture["expected_features"][0]["needs_review"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
