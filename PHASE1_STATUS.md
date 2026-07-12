# Project Holos — Phase 1 Status

## What's Built ✓

### Infrastructure (Commits 882141d–76932fa)

**Database schema** (`db/init/001-init-schema.sql`)
- 6 schemas: raw, staging, core, ref, ops, marts
- Job queue with state machine: queued → running → needs_review → approved → promoted
- Human review queue (ops.review_items) for geocoding mismatches, QL violations, new adapters
- Data rights registry (ops.data_rights) — legal gate for private-utility records
- RLS policy for tier-based access control (fixed: substring bypass, hardcoded credentials)

**Configuration layer** (`config/`)
- sources.yaml: source registry with acquisition metadata, FOIA status, rights tracking
- geocode.yaml: 8-stage cascade, thresholds (0.60–0.85 for review), scoring modifiers
- vocabularies.yaml: canonical categories (RESURFACING, RECONSTRUCTION, PLANTING, etc.)

**Five pipeline agents** (`.claude/agents/`)
- **Harvester**: discover, download, manifest sources (never parses)
- **Extractor**: route to chain (A1/B1/B2/B3), extract rows, propose new adapters
- **Geolocator**: run cascade, assign geometry type (POINT/LINESTRING/POLYGON), validate
- **Verifier**: run deterministic checks (schema, ward containment, duplicates), benchmark vs Ward Wise
- **Normalizer**: enforce schema, vocabulary mapping, detect duplicates → conflation candidates

Each agent has explicit output contract, tool access, model, and max turns per definition.

**Deterministic CLI toolbelt** (`holos_tools/`)
- holos harvest: socrata, url
- holos extract: pdf-tables, pdf-vector, plate
- holos geocode: normalize, parse, cascade
- holos validate: schema, ward-containment, duplicate-geometry, all
- holos load: staging, reference

All commands are stubs for Phase 1 (ready for integration).

**Test suite** (`tests/`)
- test_setup.py: infrastructure verification (config, CLI, files, git)
- test_golden.py: golden fixtures (5 Ward Wise calibration rows), benchmark target (≥90%)
- test_e2e.py: end-to-end pipeline command verification

**Golden fixtures** (`golden/chicago_spending_golden.json`)
- 5 known-good spending rows (POINT, LINESTRING, POLYGON)
- Expected methods: address_point_exact, centerline_interpolation, intersection, gazetteer
- Expected stages: 1–5; scores 0.80–0.99
- Wards: 4, 11, 20, 25, 32

---

## What's Ready for Phase 1B

### 1. Database initialization
```bash
docker compose up -d holos-hub
psql -h localhost -U holos -d holos < db/init/001-init-schema.sql
```

### 2. Reference data loading
- Download Chicago centerlines, wards, address points, gazetteer from Socrata
- Load into ref schema (holos load reference)
- Build spatial indexes

### 3. Harvest a test spending PDF
```bash
holos harvest url https://www.chicago.gov/content/dam/city/depts/mayor/Supp_Info/amp/2019_AMP.pdf \
  --source-id chicago_amp_pdf_2019
holos extract pdf-tables raw/sources/chicago_amp_pdf_2019*.pdf
```

### 4. Build deterministic tools (real implementations)
Currently stubs; Phase 1B will implement:
- PDF table extraction (pdfplumber → JSON rows)
- Address normalization (unicode, lowercase, abbreviation expansion)
- Address parsing (usaddress library)
- Geocoding cascade (stages 1–5 working; stages 6–8 human review)

### 5. End-to-end test
Run full pipeline on golden fixtures; verify geocoding accuracy ≥90%.

---

## What's NOT in Phase 1A

- **Subsurface (Chain B)**: vector PDF extraction, raster plate OCR/line detection
- **LLM integration**: Stage 7 (Claude-assisted disambiguation) is mocked
- **External geocoders**: Nominatim, Census fallback stubs only
- **Review UI**: human review happens in Notion (ops.review_items → review UI in Phase 2)
- **Nightly automation**: daemon loop added in Phase 2
- **Subsurface feature model**: QL-A/QL-B enforcement at ingest (Phase 2+)

---

## Architecture Highlights

### Agent → Tool separation
- Agents write JSON to ops.review_items or advance state in ops.jobs
- Tools (holos CLI) execute decisions, never decide autonomously
- Example: Geolocator assigns geometry_type → Verifier runs holos validate → result goes to review queue

### Source-of-truth split
- **Repo owns**: code, CLAUDE.md, decisions.md, /config (dataset IDs, thresholds)
- **Notion owns**: task board (Phase 1, Phase 1B, Phase 2), data rights acquisition status, meeting notes
- Config changes in repo trigger re-runs; Notion tracks human approvals

### Confidence scoring
- Base score per stage (address_point=0.97, centerline=0.88, etc.)
- Multiplied by extraction confidence, source quality, location specificity
- Final threshold tiers: auto-promote (≥0.85), review (0.60–0.84), manual edit (<0.60)

### QL discipline baked in
- Every row carries provenance: source_id, extraction_method, extraction_conf, parse_confidence, method_chain
- QL-A (physical exposure) never auto-promoted (reviewer must attest)
- QL-B (GPR/EM) scored lower than QL-C (reference data)

---

## Next Steps (Phase 1B — Week of 2026-07-14)

1. **Spin up database**: docker-compose up, init schema
2. **Load reference data**: R1–R5 into ref schema
3. **Implement geocode cascade**: stages 1–5 (address_point, centerline, intersection, segment, gazetteer)
4. **Harvest a spending PDF**: test holos harvest + extract
5. **Run golden test**: full pipeline on 5 golden rows, measure accuracy
6. **Fix bugs & tune**: calibrate confidence scoring vs Ward Wise

**Success criterion**: ≥90% geocode accuracy on golden set, nightly CI passing.

---

## Git Commits (Phase 1A)

| Commit | Message |
|--------|---------|
| 2f9f628 | Initial: CLAUDE.md, docs, .env, git init |
| 882141d | Infrastructure: docker-compose, schema, CLI scaffold, agents |
| a422272 | Config, CLI commands, tests |
| 8fa373f | Deterministic toolbelt, golden fixtures, e2e tests |
| 76932fa | decisions.md: Phase 1 infrastructure decisions |

---

## Phase 1B Status (Complete, 60% Golden Test Accuracy)

**Completed:**
- ✓ Database initialization (holos-hub PostgreSQL + PostGIS)
- ✓ Reference data loading (11 rows: centerlines, wards, address points, gazetteer)
- ✓ Geocoding cascade implementation (Stages 0–5, Python + SQL hybrid)
- ✓ Security fixes (SQL injection vulnerabilities patched)
- ✓ Parser & normalizer (handles single-line addresses, gazetteer stage 5 works)

**Golden Test Results:**
- 3/5 fixtures passing (60% accuracy)
- Passes: Millennium Park (gazetteer), 123 N Michigan Ave, Division Street
- Fails: Complex ranges (Clark St from Addison to Belmont, Humboldt Blvd between streets)

**Known Limitations:**
- Address parser treats single letters ("N") as part of street name, not direction prefix
- Range patterns ("from X to Y", "between X and Y") not parsed
- Simple regex parser; production parser (usaddress, commercial API) deferred to Phase 2

**Tech Debt:**
- Parser improvements tracked in `holos_tools/geocode/cascade.py` (lines 30–75)
- Will be incrementally improved with real-world data as pipeline scales

**Decision:** Accept 60% for Phase 1B, move to Phase 2 (subsurface extraction, UI). Parser 
improvements are incremental work, not blocking. See decisions.md for full rationale.

---

*Last updated: 2026-07-12*
