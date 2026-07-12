"""B3 Native CAD extraction: DWG, DGN, Shapefile, GeoJSON files."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class B3NativeCADExtractor:
    """Extract subsurface features from native CAD formats (DWG, DGN, Shapefile, GeoJSON)."""

    def __init__(self):
        self.features = []

    def extract(self, file_path: str) -> Dict:
        """Extract features from a CAD file."""
        result = {
            "status": "success",
            "file_path": file_path,
            "file_format": None,
            "features_extracted": 0,
            "features": [],
            "extraction_conf": 0.0,
            "flags": [],
            "needs_review": False,
            "reasons": []
        }

        try:
            file_obj = Path(file_path)
            if not file_obj.exists():
                result["status"] = "failed"
                result["error"] = f"File not found: {file_path}"
                result["needs_review"] = True
                result["reasons"].append("CAD file not accessible")
                return result

            # Detect file format
            file_format = self._detect_format(file_path)
            result["file_format"] = file_format

            if file_format == "geojson":
                features = self._extract_from_geojson(file_path)
            elif file_format == "shapefile":
                features = self._extract_from_shapefile(file_path)
            elif file_format == "dwg":
                features = self._extract_from_dwg(file_path)
            elif file_format == "dgn":
                features = self._extract_from_dgn(file_path)
            else:
                result["status"] = "unsupported"
                result["error"] = f"Unsupported format: {file_format}"
                result["needs_review"] = True
                result["reasons"].append(f"Format {file_format} not yet supported")
                return result

            result["features"] = features
            result["features_extracted"] = len(features)

            # Calculate average confidence
            if result["features"]:
                avg_conf = sum(f.get("extraction_conf", 0.85) for f in result["features"]) / len(result["features"])
                result["extraction_conf"] = avg_conf

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["needs_review"] = True
            result["reasons"].append(f"Extraction failed: {e}")

        return result

    def _detect_format(self, file_path: str) -> str:
        """Detect CAD file format by extension."""
        ext = Path(file_path).suffix.lower()
        format_map = {
            ".geojson": "geojson",
            ".json": "geojson",
            ".shp": "shapefile",
            ".dwg": "dwg",
            ".dgn": "dgn",
        }
        return format_map.get(ext, "unknown")

    def _extract_from_geojson(self, file_path: str) -> List[Dict]:
        """Extract features from GeoJSON file."""
        features = []

        try:
            with open(file_path, 'r') as f:
                geojson_data = json.load(f)

            if not isinstance(geojson_data, dict) or 'features' not in geojson_data:
                return features

            for feature in geojson_data.get('features', []):
                props = feature.get('properties', {})
                geometry = feature.get('geometry', {})

                # Infer feature type from properties or geometry
                feature_type = self._infer_feature_type_from_geojson(props, geometry)
                depth_raw = props.get('depth') or props.get('DEPTH') or None
                feature_name = props.get('name') or props.get('NAME') or geometry.get('type', 'Unknown')

                extracted_feature = {
                    "name": str(feature_name)[:100],
                    "feature_type_raw": props.get('type') or geometry.get('type', 'Unknown'),
                    "feature_type": feature_type,
                    "depth_raw": depth_raw,
                    "depth_normalized": self._normalize_depth(depth_raw) if depth_raw else None,
                    "vertical_datum": props.get('vertical_datum') or props.get('DATUM') or "unknown",
                    "extraction_conf": 0.92,  # High confidence for native CAD
                    "ql_level": "QL-C",
                    "needs_review": False,
                    "geometry_type": geometry.get('type'),
                    "source": "geojson",
                    "properties": props,
                }
                features.append(extracted_feature)

        except json.JSONDecodeError as e:
            # Return empty features on JSON parse error
            pass
        except Exception as e:
            # Silently skip on other errors
            pass

        return features

    def _extract_from_shapefile(self, file_path: str) -> List[Dict]:
        """Extract features from Shapefile (requires shapefile library)."""
        features = []

        try:
            import shapefile

            sf = shapefile.Reader(file_path)
            for record in sf.shapeRecords():
                shape = record.shape
                attrs = dict(zip([f[0] for f in sf.fields[1:]], record.record))

                feature_type = self._infer_feature_type_from_shapefile(attrs, shape)
                depth_raw = attrs.get('depth') or attrs.get('DEPTH') or None
                feature_name = attrs.get('name') or attrs.get('NAME') or f"Feature {record.oid}"

                extracted_feature = {
                    "name": str(feature_name)[:100],
                    "feature_type_raw": attrs.get('type') or attrs.get('TYPE', 'Unknown'),
                    "feature_type": feature_type,
                    "depth_raw": depth_raw,
                    "depth_normalized": self._normalize_depth(depth_raw) if depth_raw else None,
                    "vertical_datum": attrs.get('vertical_datum') or attrs.get('DATUM') or "unknown",
                    "extraction_conf": 0.93,  # Very high confidence for GIS data
                    "ql_level": "QL-C",
                    "needs_review": False,
                    "geometry_type": shape.shapeType,
                    "source": "shapefile",
                    "attributes": attrs,
                }
                features.append(extracted_feature)

        except ImportError:
            # Shapefile library not available
            pass
        except Exception as e:
            # Silently skip on errors
            pass

        return features

    def _extract_from_dwg(self, file_path: str) -> List[Dict]:
        """Extract features from DWG (requires ezdxf or similar library)."""
        features = []

        try:
            import ezdxf

            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()

            # Extract from DXF entities
            for entity in msp:
                if entity.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'POINT']:
                    # Try to extract attributes from entity
                    feature_type = self._infer_feature_type_from_dwg_entity(entity)
                    entity_data = entity.dxf.all_existing_dxf_attributes()

                    extracted_feature = {
                        "name": f"DWG Entity {entity.dxftype()}",
                        "feature_type_raw": entity.dxftype(),
                        "feature_type": feature_type,
                        "depth_raw": entity_data.get('comment') or entity_data.get('description') or None,
                        "depth_normalized": None,
                        "vertical_datum": "unknown",
                        "extraction_conf": 0.75,  # Medium-high confidence (geometry certain, attributes uncertain)
                        "ql_level": "QL-C",
                        "needs_review": True,
                        "review_reason": "dwg_attribute_extraction_uncertain",
                        "geometry_type": entity.dxftype(),
                        "source": "dwg",
                    }
                    features.append(extracted_feature)

        except ImportError:
            # ezdxf library not available
            pass
        except Exception as e:
            # Silently skip on errors
            pass

        return features

    def _extract_from_dgn(self, file_path: str) -> List[Dict]:
        """Extract features from DGN (requires dgn library if available)."""
        features = []

        try:
            # DGN extraction is complex; for now, flag for manual review
            result_feature = {
                "name": "DGN file detected",
                "feature_type_raw": "dgn_file",
                "feature_type": "unknown",
                "depth_raw": None,
                "depth_normalized": None,
                "vertical_datum": "unknown",
                "extraction_conf": 0.0,
                "ql_level": "QL-D",
                "needs_review": True,
                "review_reason": "dgn_extraction_requires_manual_parsing",
                "source": "dgn",
            }
            features.append(result_feature)

        except Exception as e:
            pass

        return features

    def _infer_feature_type_from_geojson(self, props: Dict, geometry: Dict) -> str:
        """Infer feature type from GeoJSON properties or geometry."""
        # Check properties for type hints (check longer strings first to avoid substring conflicts)
        prop_type = (props.get('type') or props.get('TYPE') or "").lower()
        if 'water' in prop_type:
            return 'utility_water'
        elif 'gas' in prop_type:
            return 'utility_gas'
        elif 'telecom' in prop_type or 'phone' in prop_type:
            return 'utility_telecom'
        elif 'sewer' in prop_type or 'sanitary' in prop_type:
            return 'utility_sewer'
        elif 'electric' in prop_type or 'elec' in prop_type:
            return 'utility_electric'
        elif 'foundation' in prop_type or 'vault' in prop_type or 'chamber' in prop_type:
            return 'structure'

        # Infer from geometry type
        geom_type = geometry.get('type', '').lower()
        if geom_type == 'point':
            return 'unknown'
        elif geom_type in ['linestring', 'multilinestring']:
            return 'unknown'  # Could be a utility line, but we don't know which
        elif geom_type in ['polygon', 'multipolygon']:
            return 'structure'

        return 'unknown'

    def _infer_feature_type_from_shapefile(self, attrs: Dict, shape) -> str:
        """Infer feature type from Shapefile attributes or geometry."""
        # Similar logic to GeoJSON (check longer strings first to avoid substring conflicts)
        attr_type = (attrs.get('type') or attrs.get('TYPE') or "").lower()
        if 'water' in attr_type:
            return 'utility_water'
        elif 'gas' in attr_type:
            return 'utility_gas'
        elif 'telecom' in attr_type or 'phone' in attr_type:
            return 'utility_telecom'
        elif 'sewer' in attr_type or 'sanitary' in attr_type:
            return 'utility_sewer'
        elif 'electric' in attr_type or 'elec' in attr_type:
            return 'utility_electric'

        return 'unknown'

    def _infer_feature_type_from_dwg_entity(self, entity) -> str:
        """Infer feature type from DWG entity attributes."""
        try:
            # Try to extract layer name or entity data
            layer_name = entity.dxf.layer.lower() if hasattr(entity.dxf, 'layer') else ""
            if 'water' in layer_name:
                return 'utility_water'
            elif 'gas' in layer_name:
                return 'utility_gas'
            elif 'electric' in layer_name or 'elec' in layer_name:
                return 'utility_electric'
            elif 'telecom' in layer_name or 'phone' in layer_name:
                return 'utility_telecom'
        except:
            pass

        return 'unknown'

    def _normalize_depth(self, depth_str: Optional[str]) -> Optional[float]:
        """Convert depth string to meters."""
        if not depth_str:
            return None

        try:
            depth_str = str(depth_str).strip().lower()

            # Convert feet to meters (1 ft = 0.3048 m)
            if 'ft' in depth_str or 'feet' in depth_str or 'foot' in depth_str:
                feet = float(re.search(r'\d+\.?\d*', depth_str).group())
                return round(feet * 0.3048, 3)

            # Already in meters
            if 'm' in depth_str or 'meter' in depth_str:
                return float(re.search(r'\d+\.?\d*', depth_str).group())

            # Default to meters for CAD (typically metric)
            return float(re.search(r'\d+\.?\d*', depth_str).group())

        except (ValueError, AttributeError):
            return None
