-- Project Holos — Review & Audit Schema
-- Phase 2: Review workflow, human gates, audit logging

-- ============================================================================
-- OPS: Review audit log (track all review decisions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ops.review_audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Reference to staging feature being reviewed
  extracted_id UUID NOT NULL,

  -- Review action
  action TEXT NOT NULL,  -- 'approved', 'rejected', 'escalated'
  reviewed_by TEXT NOT NULL,  -- reviewer name/ID

  -- Outcome
  promoted_to_feature_id UUID,  -- feature_id if approved and promoted to core
  notes TEXT,

  -- Overrides (if reviewer changed the extracted values)
  depth_override NUMERIC,  -- if reviewer overrode depth
  ql_override TEXT,  -- if reviewer changed QL level

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_audit_extracted ON ops.review_audit_log(extracted_id);
CREATE INDEX IF NOT EXISTS idx_review_audit_action ON ops.review_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_review_audit_reviewer ON ops.review_audit_log(reviewed_by);
CREATE INDEX IF NOT EXISTS idx_review_audit_date ON ops.review_audit_log(created_at DESC);

-- ============================================================================
-- VIEWS: Review analytics
-- ============================================================================

-- Features approved by QL level
CREATE VIEW ops.review_approved_by_ql AS
SELECT
  ql_override as ql_level,
  COUNT(*) as approved_count,
  COUNT(DISTINCT reviewed_by) as unique_reviewers,
  MAX(created_at) as last_approved
FROM ops.review_audit_log
WHERE action = 'approved'
GROUP BY ql_override
ORDER BY approved_count DESC;

-- Reviewer productivity
CREATE VIEW ops.review_reviewer_stats AS
SELECT
  reviewed_by,
  COUNT(*) as total_reviews,
  SUM(CASE WHEN action = 'approved' THEN 1 ELSE 0 END) as approved_count,
  SUM(CASE WHEN action = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
  SUM(CASE WHEN action = 'escalated' THEN 1 ELSE 0 END) as escalated_count
FROM ops.review_audit_log
GROUP BY reviewed_by
ORDER BY total_reviews DESC;

-- Escalation reasons (for tracking disputes)
CREATE VIEW ops.review_escalations AS
SELECT
  extracted_id,
  notes as escalation_reason,
  reviewed_by,
  created_at
FROM ops.review_audit_log
WHERE action = 'escalated'
ORDER BY created_at DESC;

---
-- GRANTS
---

GRANT USAGE ON SCHEMA ops TO holos;
GRANT SELECT ON ops.review_audit_log TO holos;
GRANT INSERT ON ops.review_audit_log TO holos;
GRANT SELECT ON ops.review_approved_by_ql TO holos;
GRANT SELECT ON ops.review_reviewer_stats TO holos;
GRANT SELECT ON ops.review_escalations TO holos;
