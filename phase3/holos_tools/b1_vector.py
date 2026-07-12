"""B1 Vector PDF extraction: CAD-exported engineering plans."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class B1VectorExtractor:
    """Extract subsurface features from CAD-exported vector PDFs."""

    def __init__(self):
        self.features = []

    def extract(self, pdf_path: str) -> Dict:
        """Extract features from a vector PDF."""
        import pdfplumber

        result = {
            "status": "success",
            "pdf_path": pdf_path,
            "features_extracted": 0,
            "features": [],
            "extraction_conf": 0.0,
            "flags": [],
            "needs_review": False,
            "reasons": []
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                result["page_count"] = len(pdf.pages)

                # Extract text and shapes from each page
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text (for annotations, labels, title block)
                    text = page.extract_text()
                    if not text:
                        continue

                    # Extract lines/shapes (for geometry)
                    lines = page.lines
                    rects = page.rects
                    curves = page.curves

                    # Parse title block for metadata
                    metadata = self._parse_title_block(text)

                    # Extract features from text annotations
                    features_on_page = self._extract_features_from_text(
                        text, page_num, metadata
                    )

                    result["features"].extend(features_on_page)
                    result["features_extracted"] += len(features_on_page)

                # Calculate average confidence
                if result["features"]:
                    avg_conf = sum(f.get("extraction_conf", 0.85) for f in result["features"]) / len(result["features"])
                    result["extraction_conf"] = avg_conf

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["needs_review"] = True
            result["reasons"].append(f"PDF extraction failed: {e}")

        return result

    def _parse_title_block(self, text: str) -> Dict:
        """Parse drawing title block for metadata."""
        metadata = {
            "title": None,
            "drawing_date": None,
            "vertical_datum": None,
            "scale": None,
            "engineer": None,
        }

        # Look for common title block patterns
        if "NAVD88" in text:
            metadata["vertical_datum"] = "NAVD88"
        elif "MSL" in text:
            metadata["vertical_datum"] = "MSL"
        elif "local grid" in text.lower():
            metadata["vertical_datum"] = "local_grid"

        # Extract scale (e.g., "1:100", "1 in = 50 ft")
        scale_match = re.search(r'1\s*:\s*(\d+)', text)
        if scale_match:
            metadata["scale"] = f"1:{scale_match.group(1)}"

        return metadata

    def _extract_features_from_text(self, text: str, page_num: int, metadata: Dict) -> List[Dict]:
        """Parse text annotations to extract features."""
        features = []

        # Pattern: "12m water main", "4.5ft gas service", "water line @ 1.8m"
        feature_patterns = [
            (r'(\d+\.?\d*)\s*m(?:eters?)?\s+(water|gas|electric|telecom|utility|sewer)', 'utility'),
            (r'(\d+\.?\d*)\s*ft(?:eet|)?\b\s+(water|gas|sewer|electric)', 'utility'),
            (r'(water|gas|electric|telecom|sewer)\s+(?:line|main|service|pipe)\s+@\s*(\d+\.?\d*)\s*m(?:eters?)?', 'utility'),
            (r'(foundation|vault|chamber|cavity|void)\s+@?\s*(\d+\.?\d*)\s*m(?:eters?)?', 'structure'),
        ]

        for line in text.split('\n'):
            for pattern, feature_type in feature_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    # Extract depth — could be in group 1 or 2 depending on pattern
                    depth_raw = None
                    if match.groups():
                        # Try group 1, fall back to group 2 if present
                        depth_raw = match.group(1)
                        if not depth_raw or not re.match(r'\d+\.?\d*', depth_raw):
                            # Group 1 is not a number; try group 2
                            if len(match.groups()) > 1:
                                depth_raw = match.group(2)

                    feature = {
                        "name": line.strip()[:100],
                        "feature_type_raw": match.group(0),
                        "feature_type": feature_type,
                        "depth_raw": depth_raw,
                        "depth_normalized": self._normalize_depth(depth_raw),
                        "vertical_datum": metadata.get("vertical_datum", "unknown"),
                        "page": page_num,
                        "extraction_conf": 0.85,
                        "ql_level": "QL-C" if metadata.get("vertical_datum") else "QL-D",
                        "needs_review": not metadata.get("vertical_datum"),
                        "review_reason": "vertical_datum_missing" if not metadata.get("vertical_datum") else None,
                    }
                    features.append(feature)
                    break

        return features

    def _normalize_depth(self, depth_str: Optional[str]) -> Optional[float]:
        """Convert depth string to meters."""
        if not depth_str:
            return None

        try:
            # Remove whitespace and standardize
            depth_str = depth_str.strip().lower()

            # Convert feet to meters (1 ft = 0.3048 m)
            if 'ft' in depth_str or 'feet' in depth_str or 'foot' in depth_str:
                feet = float(re.search(r'\d+\.?\d*', depth_str).group())
                return round(feet * 0.3048, 3)

            # Already in meters (m, meter, meters)
            if 'm' in depth_str or 'meter' in depth_str:
                return float(re.search(r'\d+\.?\d*', depth_str).group())

            # Default to assuming meters
            return float(re.search(r'\d+\.?\d*', depth_str).group())
        except (ValueError, AttributeError):
            return None
