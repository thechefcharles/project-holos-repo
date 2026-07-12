"""Subsurface feature review and promotion workflow."""

import json
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class SubsurfaceReviewer:
    """Manage subsurface feature review and promotion to core schema."""

    def __init__(self, db):
        """Initialize reviewer with database connection."""
        self.db = db

    def get_staging_features(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Fetch features waiting for review from staging."""
        sql = """
            SELECT extracted_id, source_id, extraction_method, extraction_conf,
                   feature_type_raw, feature_type, name_raw, depth_raw, depth_normalized,
                   vertical_datum, ql_level, needs_review, review_reason, created_at
            FROM subsurface_staging.extracted_features
            WHERE needs_review = true OR ql_level IN ('QL-D', 'QL-C')
            ORDER BY extraction_conf ASC, created_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        results = self.db.execute(sql, {"limit": limit, "offset": offset})
        return results

    def get_feature_by_id(self, extracted_id: str) -> Optional[Dict]:
        """Fetch a single staging feature by ID."""
        sql = """
            SELECT extracted_id, source_id, extraction_method, extraction_conf,
                   feature_type_raw, feature_type, name_raw, depth_raw, depth_normalized,
                   vertical_datum, ql_level, needs_review, review_reason, geom_raw,
                   location_text, created_at
            FROM subsurface_staging.extracted_features
            WHERE extracted_id = %(extracted_id)s
        """
        results = self.db.execute(sql, {"extracted_id": extracted_id})
        return results[0] if results else None

    def approve_feature(
        self,
        extracted_id: str,
        reviewed_by: str,
        notes: str = None,
        depth_override: Optional[float] = None,
        ql_override: Optional[str] = None,
    ) -> Dict:
        """Approve a staging feature and promote to core.subsurface_features."""
        staging_feature = self.get_feature_by_id(extracted_id)
        if not staging_feature:
            return {"status": "error", "reason": "Feature not found in staging"}

        # Use overrides if provided, otherwise use staging values
        final_depth = depth_override if depth_override is not None else staging_feature["depth_normalized"]
        final_ql = ql_override if ql_override else staging_feature["ql_level"]

        # Validate QL level
        if final_ql not in ["QL-A", "QL-B", "QL-C", "QL-D"]:
            return {"status": "error", "reason": f"Invalid QL level: {final_ql}"}

        try:
            # Insert into core.subsurface_features
            sql = """
                INSERT INTO subsurface.features (
                    name, feature_type, geom, depth_type, depth_value, vertical_datum,
                    ql_level, ql_rationale, confidence, confidence_method,
                    source_id, extraction_method, extraction_conf, material, service_status, owner, survey_date
                ) VALUES (
                    %(name)s, %(feature_type)s, %(geom)s, %(depth_type)s, %(depth_value)s,
                    %(vertical_datum)s, %(ql_level)s, %(ql_rationale)s, %(confidence)s,
                    %(confidence_method)s, %(source_id)s, %(extraction_method)s,
                    %(extraction_conf)s, %(material)s, %(service_status)s, %(owner)s, %(survey_date)s
                )
                RETURNING feature_id
            """

            params = {
                "name": staging_feature["name_raw"],
                "feature_type": staging_feature["feature_type"],
                "geom": staging_feature.get("geom_raw") or "SRID=4326;POINT(0 0)",
                "depth_type": "depth_below_surface",
                "depth_value": final_depth,
                "vertical_datum": staging_feature["vertical_datum"],
                "ql_level": final_ql,
                "ql_rationale": f"Reviewed and approved by {reviewed_by}. {notes or ''}",
                "confidence": staging_feature["extraction_conf"],
                "confidence_method": staging_feature["extraction_method"],
                "source_id": staging_feature["source_id"],
                "extraction_method": staging_feature["extraction_method"],
                "extraction_conf": staging_feature["extraction_conf"],
                "material": None,
                "service_status": "unknown",
                "owner": None,
                "survey_date": datetime.now().date(),
            }

            result = self.db.execute(sql, params)
            feature_id = result[0]["feature_id"] if result else None

            if not feature_id:
                return {"status": "error", "reason": "Failed to insert into core.subsurface_features"}

            # Record review action
            self._record_review_action(
                extracted_id, "approved", reviewed_by, feature_id, notes, depth_override, ql_override
            )

            return {
                "status": "approved",
                "feature_id": feature_id,
                "extracted_id": extracted_id,
                "ql_level": final_ql,
                "depth_normalized": final_depth,
            }

        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def reject_feature(
        self, extracted_id: str, reviewed_by: str, reason: str
    ) -> Dict:
        """Reject a staging feature (mark for revision or discard)."""
        try:
            # Update staging record to mark as rejected
            sql = """
                UPDATE subsurface_staging.extracted_features
                SET needs_review = false
                WHERE extracted_id = %(extracted_id)s
            """
            self.db.execute(sql, {"extracted_id": extracted_id})

            # Record review action
            self._record_review_action(extracted_id, "rejected", reviewed_by, None, reason)

            return {
                "status": "rejected",
                "extracted_id": extracted_id,
                "reason": reason,
            }

        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def escalate_feature(
        self, extracted_id: str, reviewed_by: str, reason: str
    ) -> Dict:
        """Escalate a feature for expert review (QL-A evidence, legal dispute, etc.)."""
        try:
            # Insert into ops.review_items
            sql = """
                INSERT INTO ops.review_items (
                    job_id, item_kind, item_reference, status, assigned_to, reason, created_at
                ) VALUES (
                    %(job_id)s, %(item_kind)s, %(item_reference)s, %(status)s,
                    %(assigned_to)s, %(reason)s, %(created_at)s
                )
                RETURNING review_item_id
            """

            params = {
                "job_id": str(uuid4()),
                "item_kind": "subsurface_ql_dispute",
                "item_reference": extracted_id,
                "status": "open",
                "assigned_to": "TBD",
                "reason": reason,
                "created_at": datetime.now().isoformat(),
            }

            result = self.db.execute(sql, params)
            review_item_id = result[0]["review_item_id"] if result else None

            # Record review action
            self._record_review_action(
                extracted_id, "escalated", reviewed_by, None, reason
            )

            return {
                "status": "escalated",
                "extracted_id": extracted_id,
                "review_item_id": review_item_id,
                "reason": reason,
            }

        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def get_review_stats(self) -> Dict:
        """Get summary stats on review queue."""
        sql = """
            SELECT
                COUNT(*) as total_features,
                SUM(CASE WHEN needs_review THEN 1 ELSE 0 END) as needs_review_count,
                SUM(CASE WHEN ql_level = 'QL-D' THEN 1 ELSE 0 END) as ql_d_count,
                SUM(CASE WHEN ql_level = 'QL-C' THEN 1 ELSE 0 END) as ql_c_count,
                AVG(extraction_conf) as avg_extraction_conf,
                MIN(extraction_conf) as min_extraction_conf
            FROM subsurface_staging.extracted_features
        """
        results = self.db.execute(sql)
        return results[0] if results else {}

    def _record_review_action(
        self,
        extracted_id: str,
        action: str,
        reviewed_by: str,
        promoted_to_feature_id: Optional[str],
        notes: Optional[str],
        depth_override: Optional[float] = None,
        ql_override: Optional[str] = None,
    ) -> None:
        """Record a review action in audit log."""
        sql = """
            INSERT INTO ops.review_audit_log (
                extracted_id, action, reviewed_by, promoted_to_feature_id, notes, depth_override, ql_override, created_at
            ) VALUES (
                %(extracted_id)s, %(action)s, %(reviewed_by)s, %(promoted_to_feature_id)s,
                %(notes)s, %(depth_override)s, %(ql_override)s, %(created_at)s
            )
        """
        try:
            self.db.execute(
                sql,
                {
                    "extracted_id": extracted_id,
                    "action": action,
                    "reviewed_by": reviewed_by,
                    "promoted_to_feature_id": promoted_to_feature_id,
                    "notes": notes,
                    "depth_override": depth_override,
                    "ql_override": ql_override,
                    "created_at": datetime.now().isoformat(),
                },
            )
        except Exception:
            # Audit log failure should not block review
            pass
