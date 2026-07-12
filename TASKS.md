# 📋 Project Holos — Build Tasks

**Repo-native build task tracker.** Grouped by phase and status. Source of truth for all build work.

Last updated: 2026-07-12

---

## This week (Priority: Ship Phase 1 MVP)

- [x] **Stand up the hub** (Component: Hub)
  - Owner: Claude Code
  - BUILD FROM: tech-spec Part III Step 2
  - AC: PostgreSQL+PostGIS running, `001-init-schema.sql` loaded (core, ref, staging, ops only), RLS policies active, reference tables initialized
  - Status: **DONE** (2026-07-11)

---

## Phase 1 (Component A: Civic Records)

### Phase 1A — Data acquisition infrastructure

- [ ] **Build the deterministic toolbelt (holos CLIs)** (Component: Hub)
  - Owner: TBD
  - BUILD FROM: tech-spec Part III Step 3
  - AC: each CLI is a typer command with --json output, exit codes, pytest golden tests. Covers extract (pdf-tables/pdf-vector), geocode cascade, geometry, validate, load. Rule: agents never hand-compute
  - Blocked by: none
  - Next: Phase 1B

- [x] **Build the Harvester (menu PDFs + Socrata) — holos harvest** (Component: A - Civic)
  - Owner: Claude Code
  - BUILD FROM: tech-spec Chain A1 §1 + config/sources.yaml + Data & Access Tracker
  - AC: (1) holos harvest socrata downloads reference layers with manifest; (2) holos harvest url handles menu PDFs; (3) only config/sources.yaml sources allowed; (4) golden test + idempotency verified; (5) zero parsing
  - Status: **GOLDEN TESTS PASSED** (2026-07-12)
    - ✓ CLI built: `holos harvest socrata` + `holos harvest url` (idempotent, manifested)
    - ✓ CLI golden tests: test_harvest.py (Socrata, URL, checksum, idempotency)
    - ✓ Agent built: holos_tools/harvest/agent.py (discovers + orchestrates + outputs JSON)
    - ✓ Agent golden tests: test_harvester_agent.py (full orchestration with mocked CLI)
    - ✓ Golden test verification: 1 ref layer discovered, 1 menu PDF pattern discovered, manifests validated
    - Ready for review (2026-07-12)

### Phase 1B — Reference data + geocoding

- [x] **Load reference layers** (Component: Hub)
  - Owner: Claude Code
  - BUILD FROM: tech-spec Chain A2
  - AC: centerlines, ward boundaries (2023 + prior), address points, 311, Census loaded to `ref` schema with vintage metadata
  - Status: **DONE** (2026-07-12)
    - ✓ CLI built: `holos load reference` (EPSG:4326, CSV→PostGIS, GeoDataFrame handling)
    - ✓ Golden tests: test_load_reference.py (CSV with/without geometry, derived tables)
    - ✓ Integration: harvest + load pipeline (Socrata → CSV → ref.* schema)
    - ✓ Derived tables: ref.intersections, ref.gazetteer auto-created
    - ✓ Vintage metadata: timestamp captured per load

- [~] **Geocode cascade end-to-end vs Ward Wise benchmark** (Component: A - Civic)
  - Owner: Claude Code
  - BUILD FROM: tech-spec Chain A1 (Steps 3–8: parse pipeline + matching cascade)
  - AC: ≥90% accuracy on 250-row + 236-row dual benchmarks (per-grammar); all 8 cascade stages live (no stubs)
  - Status: IN PROGRESS — 5 cascade bugs fixed, Stage 1 at 76% accuracy; BLOCKING: reference data mismatch
    - ✓ Fixed 5 wiring bugs (Bug 1–5 from CoWork audit):
      * Bug 1: Removed inline GeocodeNormalizer/GeocodeParser; imported AddressParser + GrammarClassifier
      * Bug 2: Implemented grammar-based routing (no longer runs all stages in order)
      * Bug 3: Fixed Stage 1 SQL schema mismatch; numeric comparison for float-typed house numbers (3327.0 vs 3327)
      * Bug 4: Stage 2 now uses PostGIS ST_LineInterpolatePoint + filters by house range in SQL (not Python)
      * Bug 5: Removed error swallowing in execute(); exceptions now surface loudly
    - ✓ Per-grammar measurement (stages 1–5, 250 + 236 rows):
      * **single_address: 76% accuracy** (76/100 correct, 20 escalated, 4 wrong) ← WORKING
      * address_range: 0% (0/15 correct, 15 escalated) ← Stage 2 returns None
      * intersection: 0% (0/70 correct, 70 escalated) ← Stage 3 returns None
      * street_segment: 0% (0/50 correct, 50 escalated) ← Stage 4 returns None
      * multi_location: 0% (0/15 correct, 15 escalated) ← Fallback escalation
      * **Overall: 30.4% (76/250)**
    - ⊘ BLOCKING: Reference data mismatch (CRITICAL)
      * address_points: 582k rows, 1,232 unique street names (from Ward Wise CSV)
      * centerlines: 56k segments, 2,076 unique street names (from different source; mostly numbered streets)
      * **Overlap: only 22 matching streets** — 98% of geocoding fails because street names don't match
      * Example: "FLETCHER" is in address_points but NOT in centerlines → Stage 2 always returns None
      * Root cause: loaded reference layers from mismatched data sources (Ward Wise vs. USGS/TIGER or other)
    - ✓ Cascade architecture working correctly:
      * Grammar classification & routing: 91%+ accuracy on benchmarks
      * Parse pipeline: extracting number/street correctly
      * SQL parameterization: secure, no injection
      * PostGIS integration: ST_LineInterpolatePoint correctly implemented
    - ✓ Stage 1 (address_points) is production-ready at 76%; 4 wrong hits need investigation
    - ⊘ Stages 2–5 cannot proceed until centerlines match address_points street names
    - ⊘ Stage 6 Census API hangs; disabled pending timeout + error handling
    - Next: MUST resolve reference data mismatch before re-measuring; either:
      * (A) Reload centerlines from Ward Wise or matching source, OR
      * (B) Reload address_points from a centerlines-compatible source, OR
      * (C) Build a street-name mapping/repair layer (rapidfuzz fuzzy match)

### Phase 1C — Review & promotion

- [ ] **Injection fixtures in CI (agent hardening)** (Component: Ops)
  - Owner: TBD
  - BUILD FROM: CLAUDE.md rule 11 + tech-spec Gap 11
  - AC: prompt-injection tests in golden/ fixtures; CI blocks if injections succeed; documented in decisions.md

### Phase 1 Exit Criteria

- [ ] **Ship public ward-spending map** (Component: A - Civic)
  - Owner: TBD
  - BUILD FROM: Master Brief §7–8 + roadmap Tool 1
  - AC: **PHASE 1 EXIT GATE** — public MapLibre map of geocoded menu spending by ward + year; a stranger can open, pick ward, see spending vs. need. Deployed (Vercel)

---

## Phase 2 (Component A+: Analytics + Component B prep)

- [ ] **Build the Normalizer (master schema enforcement)** (Component: A - Civic)
  - Owner: TBD
  - BUILD FROM: tech-spec Part III Step 5
  - AC: enforces controlled vocabularies; reconciles duplicates into conflation candidates

- [ ] **Ship report cards (Tool 2)** (Component: A - Civic)
  - Owner: TBD
  - BUILD FROM: roadmap Tool 2
  - AC: all 50 wards ranked by need-match score; cost/sq-ft + concentration metrics

- [ ] **Event-to-asset linkage (spend → buried assets)** (Component: A+B)
  - Owner: TBD
  - BUILD FROM: gap-register Gap 3
  - AC: holos link events CLI; many-to-many spend→utility links with reasons

- [ ] **Build the Verifier (validation + golden benchmark)** (Component: Hub)
  - Owner: TBD
  - BUILD FROM: tech-spec Part III Step 5
  - AC: deterministic validators for schema, geography, deduplication, QL discipline; golden benchmark maintained; failure reason-coded

---

## Phase 3 (Component B: Subsurface Extraction + Review)

### ⚠️  FROZEN — Built ahead of schedule during Phase 1

The following work was completed (2026-07-11) and is preserved in `phase3/` folder. **Reactivate only after Phase 1 completes.**

Frozen commits:
- 2026-07-11 — Phase 2 B1 (Vector PDFs) extraction
- 2026-07-11 — Phase 2 B2 (Raster plates) extraction
- 2026-07-11 — Phase 2 B3 (Native CAD) extraction
- 2026-07-11 — Phase 2 subsurface review (human-in-the-loop)

**Reactivation steps (post-Phase 1):**
1. Move B1/B2/B3 extraction back to main `holos_tools/extract/`
2. Move subsurface schemas to `db/init/`
3. Re-wire to CLI + harvester agent
4. Re-integrate subsurface review agent
5. Test against real Chicago data

**Why frozen:** Phase 1 (civic spending map) is the foundation. No tested ecosystem exists yet to feed subsurface data into, and confidence scoring is uncalibrated.

### Phase 3 Tasks (Resume after Phase 1 complete)

- [ ] **B1 Vector PDFs extraction** (Component: B - Subsurface)
  - Status: **FROZEN** in phase3/holos_tools/b1_vector.py
  - BUILD FROM: tech-spec Chain B1 + decisions.md (2026-07-11)
  - AC: ezdxf DXF authoring, CLI `holos extract pdf-vector`, depth callout parsing, golden tests (5 scenarios)

- [ ] **B2 Raster plates extraction** (Component: B - Subsurface)
  - Status: **FROZEN** in phase3/holos_tools/b2_raster.py
  - BUILD FROM: tech-spec Chain B2 + decisions.md (2026-07-11)
  - AC: OpenCV segmentation + OCR, Hough line detection, golden tests (5 quality scenarios), CLI `holos extract raster-plate`

- [ ] **B3 Native CAD extraction** (Component: B - Subsurface)
  - Status: **FROZEN** in phase3/holos_tools/b3_native_cad.py
  - BUILD FROM: tech-spec Chain B3 + decisions.md (2026-07-11)
  - AC: GeoJSON/Shapefile/DWG/DGN support, confidence scoring (GIS=0.93, DWG=0.75, DGN=0.0), CLI `holos extract native-cad`

- [ ] **Subsurface review (human-in-the-loop)** (Component: B - Subsurface)
  - Status: **FROZEN** in phase3/holos_tools/review/
  - BUILD FROM: tech-spec Part III Step 8 + decisions.md (2026-07-11)
  - AC: approve/reject/escalate workflow, audit trail, manual override (depth_override, ql_override), CLI `holos review`

- [ ] **Georeferencing automation** (Component: B - Subsurface)
  - Owner: TBD
  - BUILD FROM: tech-spec Gap 8 + roadmap Tool 3
  - AC: mapKurator + RANSAC control-point proposal; residual reporting; human confirmation required

- [ ] **Ship underground layer (Tool 3)** (Component: B - Subsurface)
  - Owner: TBD
  - BUILD FROM: roadmap Tool 3
  - AC: water/gas/sewer mains overlay on spending map; size/material attributes; DXF export for partners

---

## Phase 4 (Component C: Field Sensing + Fusion)

- [ ] **Drone LiDAR program** (Component: Field)
  - Owner: TBD
  - BUILD FROM: tech-spec Chain C1
  - AC: 2 test flights, RTK-tagged, OpenDroneMap processing, orthomosaic + DSM/DTM to hub

- [ ] **GPR survey + U-Net picking** (Component: Field)
  - Owner: TBD
  - BUILD FROM: tech-spec Chain C3 + gap-register Gap 6
  - AC: 1 test day on site with known utilities; manual picks + U-Net training; CSV depth rows → NAVD88 Z

- [ ] **Sensor fusion (C5)** (Component: Field)
  - Owner: TBD
  - BUILD FROM: tech-spec Chain C5
  - AC: proximity matching + GTSAM factor-graph refinement; fused confidence; `derived_from[]` provenance

---

## Phase 5 (Policy Applications + Long-term)

- [ ] **Lead-line prioritization** (Component: Analysis)
- [ ] **Green-infrastructure siting** (Component: Analysis)
- [ ] **Maintenance forecasting (survival model)** (Component: Analysis)

---

## Cross-cutting

- [ ] **Backups + PITR** (Component: Ops)
  - BUILD FROM: gap-register Gap 18
- [ ] **Jurisdiction-pack-as-code** (Component: Ops)
  - BUILD FROM: gap-register Gap 18
- [ ] **ODbL posture + output licensing** (Component: Legal)
  - BUILD FROM: gap-register Gap 17
- [ ] **PE/PLS relationship + E&O insurance** (Component: Legal)
  - BUILD FROM: gap-register Gap 17

---

## Glossary

| Status | Meaning |
|--------|---------|
| [x] | **DONE** — committed to dev, synced to repo, marked in decisions.md |
| [ ] | **NOT STARTED** — ready to build |
| ⚠️  | **FROZEN** — built ahead; preserved; reactivate post-prerequisite |
| `BLOCKED` | Waiting on another task |

| Component | Focus |
|-----------|-------|
| Hub | Database, schema, jobs, review queue |
| A - Civic | Spending pipeline (harvester, extractor, geolocator, verifier, normalizer) |
| A+B | Analytics + analytics + event-to-asset links |
| B - Subsurface | Extraction chains (B1/B2/B3), georeferencing, topology |
| Field | Drones, GPR, LiDAR, sensors |
| Analysis | Forecasting, dashboards, reports |
| Ops | CI, backups, monitoring, automation |
| Legal | Licensing, FOIA, liability |
