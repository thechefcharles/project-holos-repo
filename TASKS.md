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
  - Status: IN PROGRESS — Hub populated, cascade wired to real data, measuring accuracy
    - ✓ Dual benchmarks committed:
      * My 250-row benchmark (stratified: 40% single_addr, 28% inter, 20% seg, 6% range, 6% multi)
      * Cowork 236-row independent benchmark (all grammars: 9 types, 18 OCR-noise rows)
      * Accuracy testing harness: per-grammar measurement, 100m tolerance scoring
    - ✓ Parse pipeline (Steps 3a–3c):
      * 3a Normalize: ✓ done (Unicode NFC, uppercase, USPS suffix + abbr expansion, OCR repair in numeric tokens)
      * 3b Grammar classification: ✓ done (91.6% my bench, 91.1% Cowork; regex layer 80%, Claude fallback Phase 2)
      * 3c Component parsing: ✓ done (AddressComponents dataclass; number, predir, street, suffix)
    - ✓ Reference data loaded to hub:
      * Address points: 582,504 rows (581,982 with street names, 1,232 unique streets)
      * Centerlines: 56,338 segments (2,611 unique streets, address ranges for interpolation)
      * Wards: 50 (MultiPolygon geometries from Socrata p293-wvbd)
    - ✓ Cascade wired to PostgreSQL:
      * PostgresDB connection class
      * Stage 1 (address_point): exact match on ref.address_points
      * Stage 2 (centerline): linear interpolation on house number ranges
      * Stage 3–5: stubs (intersection, segment, gazetteer)
    - ✓ Cascade measurement completed (250-row + 236-row benchmarks):
      * Stages 1–5 return 0% hits on real benchmark data
      * Root cause: benchmark addresses do not have exact point matches in Ward Wise dataset
      * Example: "3327 N NEW ENGLAND AVE" → parser now correctly extracts (number=3327, street=NEW ENGLAND), but address doesn't exist in ref.address_points
      * This is realistic—spending records use approximations, not surveyed coordinates
    - ✓ Stage 6 (external geocoders) wired:
      * Census Geocoder (U.S., free, no key): API call hangs/slow—needs optimization
      * Nominatim (global, OSM data): ready, fallback for Census
      * Status: implemented but Census API unreliable; Nominatim is safe fallback
    - ⊘ Stage 7 LLM selection: PENDING
      * When multiple geocoders return hits (different coords), use Claude to select best
      * Implement after Stage 6 proves reliable
    - ⊘ Stage 0 Cache: deferred (low ROI for Phase 1B)
    - ⊘ Parser improvements (Phase 1B→Phase 2):
      * Fixed semicolon handling (now splits on `;` and takes first address)
      * Still needed: handle intersections (`&` delimited), street-name repair (rapidfuzz)
    - Next: Implement Stage 6 (Census+Nominatim) + Stage 7 (LLM selection); re-measure to ≥90%

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
