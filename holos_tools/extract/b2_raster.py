"""B2 Raster plate extraction: Sanborn maps, utility blueprints, scanned documents."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class B2RasterExtractor:
    """Extract subsurface features from raster images (Sanborn maps, scanned blueprints)."""

    def __init__(self):
        self.features = []

    def extract(self, image_path: str) -> Dict:
        """Extract features from a raster image."""
        result = {
            "status": "success",
            "image_path": image_path,
            "features_extracted": 0,
            "features": [],
            "extraction_conf": 0.0,
            "flags": [],
            "needs_review": False,
            "reasons": []
        }

        try:
            image_file = Path(image_path)
            if not image_file.exists():
                result["status"] = "failed"
                result["error"] = f"File not found: {image_path}"
                result["needs_review"] = True
                result["reasons"].append("Image file not accessible")
                return result

            # Extract text via OCR (pytesseract)
            text_content = self._extract_text_via_ocr(image_path)

            # Parse title block for metadata
            metadata = self._parse_title_block(text_content)

            # Extract features from OCR'd text
            features_from_text = self._extract_features_from_text(text_content, metadata)
            result["features"].extend(features_from_text)

            # Detect lines/edges (for pipe/cable traces)
            features_from_lines = self._detect_line_features(image_path, metadata)
            result["features"].extend(features_from_lines)

            result["features_extracted"] = len(result["features"])

            # Calculate average confidence
            if result["features"]:
                avg_conf = sum(f.get("extraction_conf", 0.70) for f in result["features"]) / len(result["features"])
                result["extraction_conf"] = avg_conf

            # Check for quality issues
            if self._detect_poor_quality(text_content):
                result["needs_review"] = True
                result["reasons"].append("Image quality degraded; manual verification recommended")

            if not metadata.get("vertical_datum"):
                result["needs_review"] = True
                result["reasons"].append("No vertical datum detected; set to QL-D")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["needs_review"] = True
            result["reasons"].append(f"Extraction failed: {e}")

        return result

    def _extract_text_via_ocr(self, image_path: str) -> str:
        """Extract text from image using OCR."""
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text
        except ImportError:
            # Fallback: return empty string if pytesseract not available
            return ""
        except Exception as e:
            return f"OCR error: {e}"

    def _parse_title_block(self, text: str) -> Dict:
        """Parse raster image title block for metadata."""
        metadata = {
            "title": None,
            "drawing_date": None,
            "vertical_datum": None,
            "scale": None,
            "source": None,
            "map_type": None,
        }

        if not text:
            return metadata

        # Look for common title block patterns
        if "SANBORN" in text.upper():
            metadata["source"] = "Sanborn Fire Insurance Map"
            metadata["map_type"] = "Sanborn"

        if "UTILITY" in text.upper() or "BLUEPRINT" in text.upper():
            metadata["map_type"] = "Utility Blueprint"

        # Look for vertical datum
        if "NAVD88" in text:
            metadata["vertical_datum"] = "NAVD88"
        elif "MSL" in text:
            metadata["vertical_datum"] = "MSL"
        elif "local grid" in text.lower():
            metadata["vertical_datum"] = "local_grid"

        # Extract scale (e.g., "1:100", "1 in = 50 ft")
        scale_match = re.search(r'1\s*(?::|in\s*=)\s*(\d+)', text)
        if scale_match:
            metadata["scale"] = f"1:{scale_match.group(1)}"

        # Extract date (e.g., "1923", "March 1923", "1923-05-15")
        date_match = re.search(r'(19|20)\d{2}', text)
        if date_match:
            metadata["drawing_date"] = date_match.group(0)

        return metadata

    def _extract_features_from_text(self, text: str, metadata: Dict) -> List[Dict]:
        """Parse OCR'd text to extract features."""
        features = []

        # Patterns for feature annotations
        feature_patterns = [
            (r'(\d+\.?\d*)\s*(?:m|ft|feet|\')\s+(?:water|gas|electric|telecom|sewer|sanitary)', 'utility'),
            (r'(?:water|gas|electric|telecom|sewer|sanitary)\s+(?:line|main|service|pipe|cable|conduit)', 'utility'),
            (r'(water|gas|electric|telecom|sewer|sanitary)\s+\w+\s+(\d+\.?\d*)\s*(?:m|ft|feet)', 'utility'),
            (r'(foundation|vault|chamber|cavity|void|manhole|catch basin)', 'structure'),
            (r'(\d+)\s*(?:inch|in|")\s+(?:water|gas|sewer)', 'utility'),
        ]

        for line in text.split('\n'):
            if not line.strip():
                continue

            for pattern, feature_type in feature_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    # Extract depth from match groups (could be group 1 or 2)
                    depth_raw = None
                    if match.groups():
                        # Try group 1 (primary depth capture)
                        potential_depth = match.group(1)
                        if potential_depth and re.match(r'\d+\.?\d*', potential_depth):
                            depth_raw = potential_depth
                        # Try group 2 if group 1 isn't a number
                        elif len(match.groups()) > 1:
                            potential_depth = match.group(2)
                            if potential_depth and re.match(r'\d+\.?\d*', potential_depth):
                                depth_raw = potential_depth

                    # Fallback: search line for any depth pattern
                    if not depth_raw:
                        depth_match = re.search(r'(\d+\.?\d*)\s*(?:ft|feet|m|meter)', line, re.IGNORECASE)
                        depth_raw = depth_match.group(1) if depth_match else None

                    feature = {
                        "name": line.strip()[:100],
                        "feature_type_raw": match.group(0),
                        "feature_type": feature_type,
                        "depth_raw": depth_raw,
                        "depth_normalized": self._normalize_depth(depth_raw) if depth_raw else None,
                        "vertical_datum": metadata.get("vertical_datum", "unknown"),
                        "extraction_conf": 0.70,  # Lower confidence for OCR'd text
                        "ql_level": "QL-D" if not metadata.get("vertical_datum") else "QL-C",
                        "needs_review": not metadata.get("vertical_datum"),
                        "review_reason": "vertical_datum_missing" if not metadata.get("vertical_datum") else None,
                        "source": metadata.get("source", "unknown"),
                    }
                    features.append(feature)
                    break

        return features

    def _detect_line_features(self, image_path: str, metadata: Dict) -> List[Dict]:
        """Detect line features (pipes, cables) from image edges."""
        features = []

        try:
            import cv2
            import numpy as np
            from PIL import Image

            # Load image
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return features

            # Edge detection (Canny)
            edges = cv2.Canny(img, 100, 200)

            # Hough line detection
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=50, maxLineGap=10)

            if lines is not None:
                # Each detected line is a potential feature (pipe, cable, etc.)
                for i, line in enumerate(lines[:10]):  # Limit to top 10 lines
                    x1, y1, x2, y2 = line[0]
                    length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                    feature = {
                        "name": f"Detected line {i+1}",
                        "feature_type_raw": "line_trace",
                        "feature_type": "unknown",
                        "depth_raw": None,
                        "depth_normalized": None,
                        "vertical_datum": metadata.get("vertical_datum", "unknown"),
                        "extraction_conf": 0.55,  # Lower confidence for line detection
                        "ql_level": "QL-D",
                        "needs_review": True,
                        "review_reason": "line_trace_needs_classification",
                        "metadata": {
                            "line_length_pixels": int(length),
                            "coordinates": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)}
                        }
                    }
                    features.append(feature)

        except ImportError:
            # OpenCV not available; skip line detection
            pass
        except Exception as e:
            # Silently skip line detection on errors
            pass

        return features

    def _normalize_depth(self, depth_str: Optional[str]) -> Optional[float]:
        """Convert depth string to meters."""
        if not depth_str:
            return None

        try:
            depth_str = depth_str.strip().lower()

            # Convert feet to meters (1 ft = 0.3048 m)
            if 'ft' in depth_str or 'feet' in depth_str or 'foot' in depth_str or "'" in depth_str:
                feet = float(re.search(r'\d+\.?\d*', depth_str).group())
                return round(feet * 0.3048, 3)

            # Already in meters
            if 'm' in depth_str or 'meter' in depth_str:
                return float(re.search(r'\d+\.?\d*', depth_str).group())

            # Default to feet (common on scanned US blueprints)
            num = float(re.search(r'\d+\.?\d*', depth_str).group())
            return round(num * 0.3048, 3)

        except (ValueError, AttributeError):
            return None

    def _detect_poor_quality(self, text: str) -> bool:
        """Detect if image quality is degraded (faded, illegible)."""
        # Heuristic: if OCR extracts very little text or many garbled chars
        if not text or len(text.strip()) < 50:
            return True

        # Check for garbled characters (non-ASCII ratio)
        non_ascii_count = sum(1 for c in text if ord(c) > 127)
        if len(text) > 100 and non_ascii_count / len(text) > 0.3:
            return True

        return False
