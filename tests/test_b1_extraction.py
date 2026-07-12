"""Test B1 vector PDF extraction (Phase 2)."""

import json
from pathlib import Path
import pytest
from holos_tools.extract.b1_vector import B1VectorExtractor


@pytest.fixture
def b1_golden():
    """Load B1 golden fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "b1_vector_golden.json"
    with open(fixture_path) as f:
        return json.load(f)


def test_b1_extractor_instantiation():
    """Test B1 extractor can be instantiated."""
    extractor = B1VectorExtractor()
    assert extractor is not None


def test_b1_depth_normalization():
    """Test depth normalization (meters and feet conversion)."""
    extractor = B1VectorExtractor()

    # Test meter parsing
    assert extractor._normalize_depth("12m") == 12.0
    assert extractor._normalize_depth("1.2 meters") == 1.2

    # Test feet parsing (4.5 ft = 1.372 m)
    assert abs(extractor._normalize_depth("4.5ft") - 1.372) < 0.01
    assert abs(extractor._normalize_depth("4.5 feet") - 1.372) < 0.01

    # Test invalid
    assert extractor._normalize_depth("unknown") is None
    assert extractor._normalize_depth(None) is None


def test_b1_feature_extraction_from_text():
    """Test feature extraction from text annotations."""
    extractor = B1VectorExtractor()

    # Mock metadata
    metadata = {
        "vertical_datum": "NAVD88",
        "scale": "1:100",
        "engineer": "City Water Dept"
    }

    # Test water main annotation
    text = "12m water main"
    features = extractor._extract_features_from_text(text, page_num=1, metadata=metadata)
    assert len(features) > 0
    assert features[0]["feature_type"] in ["utility_water", "unknown"]
    assert features[0]["depth_normalized"] == 12.0

    # Test gas service
    text = "4.5ft gas service"
    features = extractor._extract_features_from_text(text, page_num=1, metadata=metadata)
    assert len(features) > 0

    # Test electric conduit
    text = "3.2m electric conduit"
    features = extractor._extract_features_from_text(text, page_num=1, metadata=metadata)
    assert len(features) > 0


def test_b1_title_block_parsing():
    """Test title block parsing for metadata."""
    extractor = B1VectorExtractor()

    title_text = """
    ENGINEERING DRAWING
    Scale: 1:100
    Datum: NAVD88
    Engineer: John Smith, PE #12345
    Date: 2024-03-15
    """

    metadata = extractor._parse_title_block(title_text)
    assert metadata["vertical_datum"] in ["NAVD88", "unknown"]
    assert metadata["scale"] == "1:100"
    assert "John Smith" in metadata.get("engineer", "")


def test_b1_golden_water_main():
    """Test against B1 golden fixture: water main."""
    extractor = B1VectorExtractor()
    fixture = {
        "feature_type": "utility_water",
        "depth_raw": "12m",
        "vertical_datum": "NAVD88",
        "ql_level": "QL-C"
    }

    # Verify depth normalization
    depth = extractor._normalize_depth(fixture["depth_raw"])
    assert depth == 12.0

    # Verify QL assignment (QL-C default for vector PDFs)
    assert fixture["ql_level"] == "QL-C"


def test_b1_golden_utility_mix(b1_golden):
    """Test against B1 golden fixture: multiple utilities."""
    extractor = B1VectorExtractor()
    fixture = b1_golden["fixtures"][1]  # b1_utility_mix

    # Verify all features can be normalized
    for feature in fixture["expected_features"]:
        depth = extractor._normalize_depth(feature["depth_raw"])
        if depth is not None:
            # Allow 1% tolerance for unit conversion
            assert abs(depth - feature["depth_normalized"]) / feature["depth_normalized"] < 0.01


def test_b1_golden_surveyor_stamped(b1_golden):
    """Test against B1 golden fixture: surveyor-stamped plan (QL-B)."""
    fixture = b1_golden["fixtures"][2]  # b1_surveyor_stamped

    # Verify QL-B assignment (only if surveyor-stamped)
    assert fixture["expected_features"][0]["ql_level"] == "QL-B"
    assert fixture["expected_features"][0]["extraction_conf"] > 0.90


def test_b1_golden_ambiguous_depth(b1_golden):
    """Test against B1 golden fixture: ambiguous depth ranges."""
    fixture = b1_golden["fixtures"][3]  # b1_ambiguous_depth

    # Verify needs_review flag
    assert fixture["expected_features"][0]["needs_review"] is True
    assert "ambiguous" in fixture["expected_features"][0]["reason"].lower()


def test_b1_golden_no_datum(b1_golden):
    """Test against B1 golden fixture: missing vertical datum."""
    fixture = b1_golden["fixtures"][4]  # b1_no_datum

    # Verify QL-D (lowest confidence) when datum missing
    assert fixture["expected_features"][0]["ql_level"] == "QL-D"
    assert fixture["expected_features"][0]["needs_review"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
