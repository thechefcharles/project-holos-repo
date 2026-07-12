-- Project Holos — Subsurface Schema Extension
-- Phase 2: Vector PDFs (B1), Raster plates (B2), Native CAD (B3)
-- Quality levels per ASCE 38-22 and OGC MUDDI

-- ============================================================================
-- SUBSURFACE SCHEMA — Underground features with depth and QL levels
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS subsurface;

-- Quality levels (ASCE 38-22)
-- QL-A: Highest confidence (physical exposure, survey)
-- QL-B: High confidence (GPR, EM depth measurement)
-- QL-C: Moderate confidence (reference data, engineering drawing)
-- QL-D: Lowest confidence (user-provided, inferred)

-- Subsurface feature: any underground utility, pipe, cable, structure
CREATE TABLE IF NOT EXISTS subsurface.features (
  feature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT,                          -- "Main water line", "Gas service line", etc.
  feature_type TEXT NOT NULL,         -- utility_water, utility_gas, utility_electric, utility_telecom, structure_foundation, cavity_void, unknown
  geom GEOMETRY(Geometry, 4326) NOT NULL,  -- POINT, LINESTRING, or POLYGON
  geom_sp GEOMETRY(Geometry, 3435) GENERATED ALWAYS AS (ST_Transform(geom, 3435)) STORED,

  -- Depth information
  depth_type TEXT,                    -- 'depth_below_surface' or 'absolute_elevation'
  depth_value NUMERIC,                -- depth in meters (if depth_type = depth_below_surface)
  depth_value_to NUMERIC,             -- for ranges (QL-B often gives range)
  vertical_datum TEXT,                -- 'NAVD88', 'CCD' (Chicago City Datum), 'MSL'
  surface_reference TEXT,             -- "ground surface", "finish floor", "top of pipe"

  -- Quality level (ASCE 38-22)
  ql_level TEXT NOT NULL,             -- QL-A, QL-B, QL-C, QL-D
  ql_rationale TEXT,                  -- why this QL (e.g., "GPR depth measurement", "physical exposure record")

  -- Confidence and provenance
  confidence NUMERIC,                 -- 0.0–1.0
  confidence_method TEXT,             -- 'survey', 'gpr', 'em', 'visual_inspection', 'engineering_drawing', 'inferred'

  -- Provenance
  source_id TEXT NOT NULL REFERENCES ops.sources(source_id),
  extraction_method TEXT,             -- 'vector_pdf', 'raster_ocr', 'cad_dwg', 'gis_shapefile'
  extraction_conf NUMERIC,            -- confidence in the extraction itself

  -- Metadata
  material TEXT,                      -- "PVC", "Cast Iron", "Copper", etc. (if known)
  diameter NUMERIC,                   -- in mm (if applicable)
  diameter_unit TEXT,                 -- 'mm', 'inches'
  service_status TEXT,                -- 'active', 'abandoned', 'unknown'
  owner TEXT,                         -- "City of Chicago", "ComEd", "AT&T", etc.

  -- Temporal
  survey_date DATE,                   -- when was this feature surveyed/observed
  valid_from TIMESTAMPTZ DEFAULT now(),
  valid_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subsurface_features_geom ON subsurface.features USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_subsurface_features_ql ON subsurface.features(ql_level);
CREATE INDEX IF NOT EXISTS idx_subsurface_features_type ON subsurface.features(feature_type);
CREATE INDEX IF NOT EXISTS idx_subsurface_features_confidence ON subsurface.features(confidence DESC);

-- Physical exposure record: evidence of QL-A (excavation, survey, inspection)
CREATE TABLE IF NOT EXISTS subsurface.physical_exposures (
  exposure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_id UUID REFERENCES subsurface.features(feature_id),

  -- Exposure details
  exposure_type TEXT NOT NULL,        -- 'excavation', 'boring', 'survey', 'visual_inspection', 'utility_locate'
  exposure_date DATE NOT NULL,
  depth_measured NUMERIC,             -- actual measured depth (meters)
  depth_precision TEXT,               -- '+/- 0.5 m', 'within 1m', etc.

  -- Surveyor information
  surveyor_name TEXT,
  surveyor_license TEXT,              -- professional license ID
  surveyor_organization TEXT,

  -- Documentation
  documentation_url TEXT,             -- link to survey report, photos, excavation logs
  notes TEXT,

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exposures_feature ON subsurface.physical_exposures(feature_id);
CREATE INDEX IF NOT EXISTS idx_exposures_date ON subsurface.physical_exposures(exposure_date);

-- GPR survey: EM/GPR depth measurements (QL-B)
CREATE TABLE IF NOT EXISTS subsurface.gpr_surveys (
  survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_id UUID REFERENCES subsurface.features(feature_id),

  -- Survey metadata
  survey_date DATE NOT NULL,
  survey_line GEOMETRY(LineString, 4326),  -- path of the GPR scan
  equipment_type TEXT,                -- "Geophysics GPR", "IDS RealTime Array", etc.
  frequency_mhz NUMERIC,              -- antenna frequency

  -- Results
  depth_measured NUMERIC,             -- measured depth (meters)
  depth_uncertainty NUMERIC,          -- +/- range (meters)
  signal_strength NUMERIC,            -- 0.0–1.0
  confidence_score NUMERIC,           -- how certain is the measurement

  -- Processing
  processed_date DATE,
  processor_notes TEXT,

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gpr_feature ON subsurface.gpr_surveys(feature_id);
CREATE INDEX IF NOT EXISTS idx_gpr_date ON subsurface.gpr_surveys(survey_date);

-- EM (electromagnetic) survey: induction-based depth (QL-B)
CREATE TABLE IF NOT EXISTS subsurface.em_surveys (
  survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_id UUID REFERENCES subsurface.features(feature_id),

  -- Survey metadata
  survey_date DATE NOT NULL,
  survey_location GEOMETRY(Point, 4326),
  equipment_type TEXT,                -- "Metrotech eMark", "Schonstedt Magnetic Locator", etc.
  method TEXT,                        -- 'induction', 'magnetic', 'pipe_locate'

  -- Results
  depth_estimated NUMERIC,            -- estimated depth (meters)
  depth_uncertainty NUMERIC,          -- +/- range (meters)
  signal_strength NUMERIC,            -- 0.0–1.0 (signal attenuation with depth)
  estimated_conductivity TEXT,        -- "high", "medium", "low" (from material)

  -- Processing
  processed_date DATE,
  processor_notes TEXT,

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_em_feature ON subsurface.em_surveys(feature_id);
CREATE INDEX IF NOT EXISTS idx_em_date ON subsurface.em_surveys(survey_date);

-- ============================================================================
-- STAGING: Extracted subsurface data (pre-promotion to core)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS subsurface_staging;

-- Raw extraction from B1/B2/B3 sources
CREATE TABLE IF NOT EXISTS subsurface_staging.extracted_features (
  extracted_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- From extraction pipeline
  source_id TEXT NOT NULL REFERENCES ops.sources(source_id),
  extraction_method TEXT,             -- 'vector_pdf', 'raster_ocr', 'cad_dwg'
  extraction_conf NUMERIC,

  -- Raw data as extracted
  name_raw TEXT,
  feature_type_raw TEXT,
  depth_raw TEXT,                     -- as found in source (may be "12m", "4-5ft", etc.)
  location_text TEXT,
  geom_raw GEOMETRY(Geometry, 4326),  -- may be imprecise or unknown

  -- Normalized
  feature_type TEXT,                  -- mapped to canonical type
  ql_level TEXT,                      -- proposed QL level
  depth_normalized NUMERIC,
  depth_to NUMERIC,
  vertical_datum TEXT,

  -- For review
  needs_review BOOLEAN DEFAULT false,
  review_reason TEXT,                 -- why needs review

  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_extracted_source ON subsurface_staging.extracted_features(source_id);
CREATE INDEX IF NOT EXISTS idx_extracted_type ON subsurface_staging.extracted_features(feature_type);

-- ============================================================================
-- OPS: Review items for subsurface QA
-- ============================================================================

-- Extend ops.review_items for subsurface-specific reviews
-- (no new table needed; use kind='subsurface_ql_dispute', 'subsurface_depth_range', etc.)

---
-- VIEWS: Subsurface analytics
---

-- Features by QL level and type
CREATE VIEW subsurface.features_by_ql AS
SELECT
  ql_level,
  feature_type,
  COUNT(*) as feature_count,
  AVG(confidence) as avg_confidence,
  MIN(depth_value) as min_depth,
  MAX(depth_value) as max_depth
FROM subsurface.features
WHERE valid_to IS NULL
GROUP BY ql_level, feature_type
ORDER BY ql_level, feature_type;

-- High-confidence features (QL-A only)
CREATE VIEW subsurface.qa_features_ql_a AS
SELECT
  feature_id, name, feature_type, ql_level,
  depth_value, vertical_datum, confidence,
  survey_date, owner
FROM subsurface.features
WHERE ql_level = 'QL-A' AND valid_to IS NULL
ORDER BY survey_date DESC;

-- Features needing review (low confidence or missing QL-A evidence)
CREATE VIEW subsurface.features_under_review AS
SELECT
  f.feature_id, f.name, f.feature_type, f.ql_level,
  f.confidence, f.confidence_method,
  COUNT(DISTINCT e.exposure_id) as exposure_count,
  f.created_at
FROM subsurface.features f
LEFT JOIN subsurface.physical_exposures e ON f.feature_id = e.feature_id
WHERE f.valid_to IS NULL
  AND (f.ql_level IN ('QL-C', 'QL-D') OR f.confidence < 0.75)
GROUP BY f.feature_id, f.name, f.feature_type, f.ql_level, f.confidence, f.confidence_method, f.created_at
ORDER BY f.confidence ASC;

---
-- GRANTS
---

GRANT USAGE ON SCHEMA subsurface, subsurface_staging TO holos;
GRANT SELECT ON ALL TABLES IN SCHEMA subsurface TO holos;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA subsurface_staging TO holos;
-- Views inherit permissions from underlying tables, no explicit GRANT needed
