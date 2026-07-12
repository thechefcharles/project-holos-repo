-- Project Holos — Hub Schema Initialization
-- Raw, staging, core, reference, operations, and analytics schemas

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgvector;

-- ============================================================================
-- SCHEMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS raw;       -- manifested raw bytes, source metadata
CREATE SCHEMA IF NOT EXISTS staging;   -- agent-writable, pre-promotion
CREATE SCHEMA IF NOT EXISTS core;      -- promoted, human-gated, published
CREATE SCHEMA IF NOT EXISTS ref;       -- reference layers (census, city data, gazetteer)
CREATE SCHEMA IF NOT EXISTS ops;       -- jobs, runs, reviews, decisions, calibration
CREATE SCHEMA IF NOT EXISTS marts;     -- analytics views (need-match, cost/sqft)

-- ============================================================================
-- OPS SCHEMA — Job tracking, runs, reviews, calibration
-- ============================================================================

-- Data source registry: every source has a rights record
CREATE TABLE IF NOT EXISTS ops.sources (
  source_id TEXT PRIMARY KEY,
  kind TEXT,                          -- 'socrata', 'pdf', 'shapefile', 'cad', etc.
  url TEXT,
  rights TEXT NOT NULL,
  CHECK (rights IN ('public_record', 'licensed', 'permission_pending', 'prohibited')),
  retrieved_at TIMESTAMPTZ,
  checksum TEXT,                      -- SHA256 of raw bytes
  manifest JSONB,                     -- URL, retrieval_timestamp, etc.
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Job queue: harvest, extract, geocode, verify, normalize, promote
CREATE TABLE IF NOT EXISTS ops.jobs (
  job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline TEXT NOT NULL,             -- 'a1_spending', 'b1_vector_pdf', etc.
  input_ref JSONB,                    -- pointer to source(s), input_checksum, etc.
  input_checksum TEXT,
  state TEXT NOT NULL DEFAULT 'queued',
  CHECK (state IN ('queued', 'running', 'needs_review', 'approved', 'promoted', 'failed', 'escalated')),
  attempt INT DEFAULT 0,
  budget_usd NUMERIC,
  spent_usd NUMERIC DEFAULT 0,
  agent TEXT,                         -- which agent owns this stage
  run_log_url TEXT,                   -- S3 or local path to full message stream
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (pipeline, input_checksum)
);

-- Human review items: geocoding mismatches, QL disputes, new adapters, etc.
CREATE TABLE IF NOT EXISTS ops.review_items (
  item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES ops.jobs(job_id),
  kind TEXT NOT NULL,                 -- 'geocode_below_threshold', 'ql_violation', 'new_adapter', etc.
  payload_ref JSONB,                  -- {row_id, candidates, reason_codes, etc.}
  geom GEOMETRY(Geometry, 4326),      -- for map-based review
  reason_codes TEXT[],                -- structured failure reasons
  council_verdicts JSONB,             -- {surveyor: {verdict, findings}, ...}
  state TEXT DEFAULT 'open',
  CHECK (state IN ('open', 'approved', 'rejected', 'fixed')),
  reviewer TEXT,
  decided_at TIMESTAMPTZ,
  decision TEXT,                      -- 'approved', 'rejected_reason', etc.
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Data rights registry: legal gate for private-utility records
CREATE TABLE IF NOT EXISTS ops.data_rights (
  source_id TEXT PRIMARY KEY REFERENCES ops.sources(source_id),
  rights_basis TEXT,                  -- 'FOIA', 'public_domain', 'partnership', 'license', etc.
  granted_by TEXT,
  granted_at TIMESTAMPTZ,
  scope JSONB,                        -- {feature_classes: [...], tier: 'public|municipal|engineering', ...}
  expires TIMESTAMPTZ
);

-- Run metrics: geocode rate, review queue depth, human-minutes, $ per 1k records
CREATE TABLE IF NOT EXISTS ops.run_metrics (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID REFERENCES ops.jobs(job_id),
  metric_name TEXT NOT NULL,
  value NUMERIC,
  labels JSONB,                       -- {stage: 'geocode', method: 'centerline', ...}
  recorded_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================================
-- REF SCHEMA — Reference layers (never modified after load)
-- ============================================================================

-- Centerlines with address ranges for interpolation
CREATE TABLE IF NOT EXISTS ref.centerlines (
  segment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  street_name TEXT NOT NULL,
  predir CHAR(1),                     -- N, S, E, W
  suffix TEXT,                        -- ST, AVE, BLVD, etc.
  from_house_num_l INT, to_house_num_l INT,  -- left side ranges
  from_house_num_r INT, to_house_num_r INT,  -- right side ranges
  geom GEOMETRY(LineString, 4326) NOT NULL,
  valid_from TIMESTAMPTZ DEFAULT now(),
  valid_to TIMESTAMPTZ,
  source_id TEXT REFERENCES ops.sources(source_id),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_centerlines_street ON ref.centerlines(street_name);
CREATE INDEX IF NOT EXISTS idx_centerlines_geom ON ref.centerlines USING GIST(geom);

-- Address points for Stage 1 exact match
CREATE TABLE IF NOT EXISTS ref.address_points (
  point_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  address_number INT,
  street_name TEXT,
  city TEXT,
  state CHAR(2),
  zip TEXT,
  geom GEOMETRY(Point, 4326) NOT NULL,
  valid_from TIMESTAMPTZ DEFAULT now(),
  valid_to TIMESTAMPTZ,
  source_id TEXT REFERENCES ops.sources(source_id),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_address_points_address ON ref.address_points(address_number, street_name);
CREATE INDEX IF NOT EXISTS idx_address_points_geom ON ref.address_points USING GIST(geom);

-- Ward boundaries (versioned: 2003, 2015, 2023)
CREATE TABLE IF NOT EXISTS ref.wards (
  ward_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ward_number INT NOT NULL,
  geom GEOMETRY(Polygon, 4326) NOT NULL,
  vintage DATE NOT NULL,              -- e.g., 2023, 2015, 2003
  valid_from TIMESTAMPTZ DEFAULT now(),
  valid_to TIMESTAMPTZ,
  source_id TEXT REFERENCES ops.sources(source_id),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (ward_number, vintage)
);
CREATE INDEX IF NOT EXISTS idx_wards_geom ON ref.wards USING GIST(geom);

-- Named places: parks, schools, community areas (temporal aliases matter)
CREATE TABLE IF NOT EXISTS ref.gazetteer (
  place_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  aliases TEXT[],                     -- Douglas Park became Douglass Park in 2020
  place_type TEXT,                    -- 'park', 'school', 'community_area', 'facility'
  geom GEOMETRY(Geometry, 4326),      -- POLYGON for areas, POINT for facilities
  valid_from TIMESTAMPTZ DEFAULT now(),
  valid_to TIMESTAMPTZ,
  source_id TEXT REFERENCES ops.sources(source_id),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gazetteer_name ON ref.gazetteer(name);
CREATE INDEX IF NOT EXISTS idx_gazetteer_geom ON ref.gazetteer USING GIST(geom);

-- Street name dictionary with phonetic encoding for fuzzy repair
CREATE TABLE IF NOT EXISTS ref.street_names (
  street_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  soundex TEXT,
  metaphone TEXT,
  embedding VECTOR(384),              -- sentence-transformer embedding
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_street_names_soundex ON ref.street_names(soundex);
CREATE INDEX IF NOT EXISTS idx_street_names_embedding ON ref.street_names USING IVFFLAT(embedding vector_cosine_ops);

-- 311 service requests (reference for need-match analytics)
CREATE TABLE IF NOT EXISTS ref.sr311 (
  sr_id UUID PRIMARY KEY,
  creation_date TIMESTAMPTZ,
  status TEXT,
  service_name TEXT,
  address TEXT,
  geom GEOMETRY(Point, 4326),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Derived: intersections (node points where two streets meet)
CREATE OR REPLACE VIEW ref.intersections AS
SELECT DISTINCT
  ST_Intersection(a.geom, b.geom)::GEOMETRY(Point, 4326) AS geom,
  a.street_name AS street_a,
  b.street_name AS street_b
FROM ref.centerlines a
JOIN ref.centerlines b ON ST_Intersects(a.geom, b.geom) AND a.street_name < b.street_name;

-- ============================================================================
-- STAGING SCHEMA — Agent-writable, pre-promotion
-- ============================================================================

-- Raw parsed extractions from PDFs before normalization
CREATE TABLE IF NOT EXISTS staging.extractions (
  extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id TEXT NOT NULL,
  page_num INT,
  location_text_raw TEXT NOT NULL,
  ward TEXT,
  category TEXT,
  cost NUMERIC,
  year INT,
  bbox JSONB,                         -- {x0, y0, x1, y1} on page
  extraction_method TEXT,             -- 'pdfplumber_table', 'ocr', 'claude_vision'
  extraction_conf REAL,
  source_id TEXT REFERENCES ops.sources(source_id),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Parsed, normalized, ready to geocode
CREATE TABLE IF NOT EXISTS staging.geocode_parsed (
  row_id TEXT UNIQUE NOT NULL,
  location_text_raw TEXT,
  location_text_norm TEXT NOT NULL,
  location_grammar TEXT,              -- single_address, hundred_block, segment, etc.
  parse JSONB,                        -- {number, street, predir, suffix, ...}
  repairs TEXT[],                     -- suggestions for OCR errors
  parse_confidence REAL,
  ward TEXT,
  year INT,
  source_id TEXT REFERENCES ops.sources(source_id),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_geocode_parsed_ward_year ON staging.geocode_parsed(ward, year);

-- Geocoded results before promotion to core
CREATE TABLE IF NOT EXISTS staging.spending_projects (
  project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  row_id TEXT UNIQUE,
  location_text_raw TEXT,
  location_text_norm TEXT,
  location_grammar TEXT,
  ward TEXT NOT NULL,
  year INT NOT NULL,
  category TEXT,
  cost NUMERIC,
  geom GEOMETRY(Geometry, 4326),      -- POINT, LINESTRING, or POLYGON
  geom_sp GEOMETRY(Geometry, 3435) GENERATED ALWAYS AS (ST_Transform(geom, 3435)) STORED,
  geometry_type TEXT,                 -- 'POINT', 'LINESTRING', 'POLYGON'
  geometry_reason TEXT,               -- why this type was chosen
  method TEXT,                        -- 'address_point', 'centerline_interpolation', 'gazetteer', etc.
  stage INT,                          -- which matching stage succeeded
  score REAL,
  candidates_considered INT,
  ref_vintage JSONB,                  -- {centerlines: '2026-06-30', wards: '2023'}
  flags TEXT[],                       -- {'street_repaired', 'multi_candidate', ...}
  source_id TEXT REFERENCES ops.sources(source_id),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_spending_stage_geom ON staging.spending_projects USING GIST(geom);

-- ============================================================================
-- CORE SCHEMA — Promoted, human-gated, the source of truth
-- ============================================================================

CREATE TABLE IF NOT EXISTS core.spending_projects (
  project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  row_id TEXT UNIQUE,
  location_text_raw TEXT,
  location_text_norm TEXT,
  ward TEXT NOT NULL,
  year INT NOT NULL,
  category TEXT,
  cost NUMERIC,
  geom GEOMETRY(Geometry, 4326) NOT NULL,
  geom_sp GEOMETRY(Geometry, 3435) GENERATED ALWAYS AS (ST_Transform(geom, 3435)) STORED,
  geometry_type TEXT,
  geometry_reason TEXT,
  method TEXT,
  stage INT,
  score REAL NOT NULL,
  candidates_considered INT,
  extraction_method TEXT,
  extraction_conf REAL,
  parse_confidence REAL,
  method_chain TEXT[],                -- ['normalize', 'parse', 'stage_2_interpolation']
  confidence REAL,                    -- composite confidence
  conf_method TEXT,                   -- 'base_score_times_modifiers'
  ref_vintage JSONB,
  flags TEXT[],
  needs_human BOOLEAN DEFAULT false,
  access_tier TEXT NOT NULL DEFAULT 'tier_public',
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  source_id TEXT REFERENCES ops.sources(source_id),
  job_id UUID REFERENCES ops.jobs(job_id),
  valid_from TIMESTAMPTZ DEFAULT now(),
  valid_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_core_spending_ward_year ON core.spending_projects(ward, year);
CREATE INDEX IF NOT EXISTS idx_core_spending_geom ON core.spending_projects USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_core_spending_score ON core.spending_projects(score DESC);

-- ============================================================================
-- ROW-LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE core.spending_projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY tier_read ON core.spending_projects FOR SELECT
  USING (access_tier = 'tier_public' OR current_setting('holos.tiers', true) LIKE '%' || access_tier || '%');

-- ============================================================================
-- MART SCHEMA — Analytics views
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS marts.spending_by_ward AS
SELECT
  year,
  ward,
  COUNT(*) AS project_count,
  SUM(cost) AS total_cost,
  AVG(cost) AS avg_cost,
  AVG(score) AS avg_confidence
FROM core.spending_projects
WHERE needs_human = false
GROUP BY year, ward
ORDER BY year DESC, total_cost DESC;

-- ============================================================================
-- PRIVILEGES (default: holos role reads everything, app roles are restricted)
-- ============================================================================

GRANT USAGE ON SCHEMA raw, staging, core, ref, ops, marts TO holos;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, ref TO holos;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA staging, ops TO holos;
GRANT SELECT ON ALL TABLES IN SCHEMA core TO holos;

-- Create read-only role for MCP/agents
CREATE ROLE holos_readonly LOGIN PASSWORD 'readonly';
GRANT USAGE ON SCHEMA core, ref, ops TO holos_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA core, ref, ops TO holos_readonly;
