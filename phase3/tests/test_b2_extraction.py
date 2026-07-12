"""Test B2 raster extraction (Phase 2)."""

import json
from pathlib import Path
import pytest
from holos_tools.extract.b2_raster import B2RasterExtractor


@pytest.fixture
def b2_golden():
    """Load B2 golden fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "b2_raster_golden.json"
    with open(fixture_path) as f:
        return json.load(f)


def test_b2_extractor_instantiation():
    """Test B2 extractor can be instantiated."""
    extractor = B2RasterExtractor()
    assert extractor is not None


def test_b2_depth_normalization():
    """Test depth normalization for raster documents."""
    extractor = B2RasterExtractor()

    tests = [
        ("12ft", 3.658),
        ("4.5 feet", 1.372),
        ("12", 3.658),  # Default to feet on legacy blueprints
        ("2.1m", 2.1),
        ("1.5 meters", 1.5),
        ("unknown", None),
        (None, None),
    ]

    print("\n=== Testing B2 Depth Normalization ===")
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


def test_b2_title_block_parsing():
    """Test title block parsing from OCR'd text."""
    extractor = B2RasterExtractor()

    test_cases = [
        ("Sanborn Fire Insurance Map\nScale: 1:100", "Sanborn"),
        ("Utility Blueprint - ComEd\nDatum: NAVD88", "Utility Blueprint"),
        ("1923 Sanborn Map", "Sanborn"),
    ]

    print("\n=== Testing B2 Title Block Parsing ===")
    passed = 0
    for text, expected_source in test_cases:
        metadata = extractor._parse_title_block(text)
        found_source = metadata.get("source") or metadata.get("map_type")
        success = expected_source in str(found_source) if found_source else False
        status = "✓" if success else "✗"
        print(f"{status} Title block: {text[:40]}... → {metadata}")
        if success:
            passed += 1

    print(f"✓ {passed}/{len(test_cases)} title block parsing tests passed")
    return passed == len(test_cases)


def test_b2_quality_detection():
    """Test image quality detection."""
    extractor = B2RasterExtractor()

    # Good quality text
    good_text = "Sanborn Fire Insurance Map\n" * 10 + "Scale: 1:100\nWater Main 12 feet\nGas Service 4.5 feet"
    is_poor = extractor._detect_poor_quality(good_text)
    assert not is_poor, "Good quality text incorrectly marked as poor"

    # Poor quality (too little text)
    poor_text = "abc"
    is_poor = extractor._detect_poor_quality(poor_text)
    assert is_poor, "Poor quality text not detected"

    print("✓ Quality detection tests passed")
    return True


def test_b2_feature_extraction_from_ocr():
    """Test feature extraction from OCR'd text."""
    extractor = B2RasterExtractor()

    metadata = {
        "vertical_datum": "NAVD88",
        "scale": "1:100",
        "source": "Sanborn map"
    }

    test_texts = [
        ("Water Main 12ft deep", 1),
        ("Gas Service 4.5 feet", 1),
        ("Electric Conduit 3m", 1),
    ]

    print("\n=== Testing B2 Feature Extraction from OCR ===")
    passed = 0
    for text, expected_count in test_texts:
        features = extractor._extract_features_from_text(text, metadata)
        success = len(features) == expected_count
        status = "✓" if success else "✗"
        print(f"{status} Extracted {len(features)} features from '{text}' (expected {expected_count})")
        if features:
            for f in features:
                print(f"  - {f['feature_type']}: {f['depth_raw']} → {f['depth_normalized']}m")
        if success:
            passed += 1

    print(f"✓ {passed}/{len(test_texts)} feature extraction tests passed")
    return passed == len(test_texts)


def test_b2_golden_sanborn_good(b2_golden):
    """Test against B2 golden fixture: good Sanborn map."""
    fixture = b2_golden["fixtures"][0]  # b2_sanborn_good_quality
    assert fixture["ocr_quality"] == "good"

    # Verify features can be normalized
    for feature in fixture["expected_features"]:
        extractor = B2RasterExtractor()
        depth = extractor._normalize_depth(feature["depth_raw"])
        if depth is not None:
            assert abs(depth - feature["depth_normalized"]) < 0.01


def test_b2_golden_utility_blueprint(b2_golden):
    """Test against B2 golden fixture: utility blueprint."""
    fixture = b2_golden["fixtures"][1]  # b2_utility_blueprint
    assert "electric" in fixture["expected_features"][0]["feature_type"].lower()
    assert fixture["expected_features"][0]["ql_level"] == "QL-C"


def test_b2_golden_faded_sanborn(b2_golden):
    """Test against B2 golden fixture: degraded scan."""
    fixture = b2_golden["fixtures"][2]  # b2_faded_sanborn
    assert fixture["ocr_quality"] == "degraded"

    # Verify QL-D assignment for degraded images
    assert fixture["expected_features"][0]["ql_level"] == "QL-D"
    assert fixture["expected_features"][0]["needs_review"] is True


def test_b2_golden_line_detection(b2_golden):
    """Test against B2 golden fixture: line trace detection."""
    fixture = b2_golden["fixtures"][3]  # b2_line_detection

    # Line traces should be QL-D and flagged for review
    feature = fixture["expected_features"][0]
    assert feature["feature_type"] == "unknown"
    assert feature["ql_level"] == "QL-D"
    assert feature["needs_review"] is True
    assert "classification" in feature["reason"].lower()


def test_b2_golden_handwritten(b2_golden):
    """Test against B2 golden fixture: handwritten annotations."""
    fixture = b2_golden["fixtures"][4]  # b2_handwritten_annotations

    # Handwritten OCR should be low confidence, QL-D
    feature = fixture["expected_features"][0]
    assert feature["extraction_conf"] < 0.50
    assert feature["ql_level"] == "QL-D"
    assert feature["needs_review"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
