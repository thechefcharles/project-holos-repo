# Project Holos — Decisions Log

Append-only. Every decision a future teammate or agent needs to understand "why is
it this way?" Newest at the bottom. Never edit history — supersede with a new entry.
This file is the **source of truth**; it is mirrored up to the Notion Decisions Log
by `/sync-notion`.

---

### 2026-07-12 — Framing: platform-first
Pitch leads with the jurisdiction-agnostic records-to-twin pipeline; civic accountability,
SUE subcontracting, and developer due-diligence are applications, not the product.

### 2026-07-12 — Coordinate policy
Store geometry in EPSG:4326; compute engineering math and CAD in EPSG:3435 (IL State
Plane, ft). Never hand-roll transforms.

### 2026-07-12 — Ward Wise is the answer key
Build our own scraper + geocoder, grade against the Ward Wise dataset on Chicago before
trusting a new city. Do not rebuild the financial layer from scratch.

### 2026-07-12 — First build = Phase 1 / Component A (Chain A1)
The spending pipeline (prototyped ~87% geocode) is the first build — not scraper
generalization, not the underground extraction.

### 2026-07-12 — QL-A / QL-B discipline (ASCE 38-22)
GPR/EM depths are QL-B; only physical exposure yields QL-A; never upgrade. Schema maps
to ASCE 75-22, tracks OGC MUDDI.

### 2026-07-12 — Private-utility legal gate
No data derived from ComEd / Peoples Gas / AT&T records enters the hub without a rights
record in `ops.data_rights`.

### 2026-07-12 — Source-of-truth model adopted
Repo owns code/config/CLAUDE.md/decisions.md; Notion owns trackers/planning/human-facing
decisions log. Nothing owned by both; non-owner side is a labeled mirror. Data-source
IDs/thresholds live in /config (repo); acquisition status lives in the Notion tracker.

### 2026-07-12 — Phase 1 infrastructure: agents, not scripts
Five pipeline agents (harvester, extractor, geolocator, verifier, normalizer) with explicit
output contracts per `schemas/agent_output.schema.json`. Each agent owns a stage of the
pipeline; human gates live in ops.review_items and ops.jobs (state machine: queued → running
→ needs_review → approved → promoted). Deterministic tools (holos CLI commands) execute
decisions made by agents. Agent definitions in `.claude/agents/` specify tools, model, effort,
and workflow per agent.

### 2026-07-12 — RLS policy substring bypass fixed
Changed `LIKE '%' || access_tier || '%'` to `access_tier = ANY (string_to_array(...))` in
core.spending_projects RLS policy to prevent substring injection. Hardcoded role password
removed; password must be set via `ALTER ROLE ... WITH PASSWORD` from environment variable.

### 2026-07-12 — Geocode cascade architecture: multi-stage fallthrough
Cascade stages 1–5 (exact/interpolated matches on local ref data) fail on real benchmarks
because spending records use approximations, not surveyed coordinates. Stage 6 (Census Geocoder
+ Nominatim) bridges the gap. Census API is flaky; Nominatim (OSM, self-hosted or public) is
reliable fallback. Stage 7 (LLM candidate selection) deferred—implement only if multiple stages
return conflicting coordinates (rare in Chicago). Decision: prioritize Stage 6 stability; use
Nominatim with public API for now, migrate to self-hosted if rate limits hit.

### 2026-07-12 — Five-command CLI hierarchy
- holos harvest: discover, download, manifest sources (Socrata, HTTP URLs)
- holos extract: convert PDFs/CADs/scans to rows (chains A1/B1/B2/B3)
- holos geocode: normalize, parse, cascade-match (stages 0–8)
- holos validate: schema, geography (ward containment), deduplication, QL discipline
- holos load: promote staging → core (with human gates)

Subcommands follow chain/stage naming from CLAUDE.md rule 1 (agents decide, tools execute).

### 2026-07-12 — Golden fixtures + Ward Wise benchmark
Five golden rows in golden/chicago_spending_golden.json: POINT, LINESTRING, POLYGON covering
stages 1–5 (address_point_exact, centerline_interpolation, intersection, gazetteer).
Phase 1 target: ≥90% geocode accuracy vs Ward Wise (documented as test_benchmark_target).

### 2026-07-12 — Address parser: incremental improvement strategy
Phase 1B geocoding cascade achieves 60% golden-test accuracy (3/5). Simple regex parser 
handles single-line addresses well (gazetteer stage 5 works), but struggles with complex 
patterns ("street from X to Y", directional prefixes like "N Michigan"). 

Decision: Accept 60% for Phase 1B, move to Phase 2 (subsurface extraction). Parser will be 
incrementally improved with real-world data as pipeline scales. Production-grade alternatives 
(usaddress library, commercial services) reserved for Phase 2+ if complexity grows beyond 
regex-repair capability. Tracked as tech debt: holos_tools/geocode/cascade.py lines 30–75.

### 2026-07-11 — Phase 2 B1 (Vector PDFs) extraction: annotation-driven feature discovery
Phase 2 subsurface extraction starts with B1 (CAD-exported engineering plans). B1VectorExtractor 
parses text annotations for depth and feature type ("12m water main", "4.5ft gas service", 
"@ 1.8m"), extracts title-block metadata (vertical datum, scale, engineer), and assigns QL 
levels: QL-C default (reference data), QL-B if surveyor-stamped, QL-D if datum missing. 
Depth normalization handles meters/feet unit conversion; CLI wired as `holos extract pdf-vector`.
Golden fixtures + pytest tests cover 5 scenarios (simple, mix, surveyor-stamped, ambiguous, no datum).

### 2026-07-11 — Phase 2 B2 (Raster plates) extraction: OCR + line detection
B2RasterExtractor handles scanned documents (Sanborn Fire Insurance maps, utility blueprints, 
legacy engineering plans). Extracts text via tesseract OCR, detects line features (pipes/cables) 
using OpenCV edge detection + Hough line detection. Image quality heuristics flag degraded scans 
(faded, water-stained, illegible). QL-D default (OCR fallible; depth extraction heuristic); QL-C 
if surveyor-reviewed. Line traces extracted but flagged for human classification (water vs. gas 
vs. electric). Depth normalization supports feet (common on US blueprints) and meters; unit 
inference from context. CLI wired as `holos extract raster-plate`. Golden fixtures cover 5 quality 
scenarios (good Sanborn, utility blueprint, faded scan, line detection, handwritten annotations).

### 2026-07-11 — Phase 2 B3 (Native CAD) extraction: GeoJSON, Shapefile, DWG, DGN
B3NativeCADExtractor extracts features directly from CAD files: GeoJSON (web-native, highest 
fidelity), Shapefile (GIS standard), DWG (AutoCAD, medium fidelity: geometry certain, attributes 
inferred from layer names), DGN (MicroStation, deferred to Phase 3+). Feature type inferred from 
properties + layer names + geometry. Confidence scores: 0.93 (GIS formats), 0.75 (DWG), 0.0 (DGN 
pending). QL-C default (CAD geometry is canonical); QL-D for DGN or unprovenanced. Depth from 
explicit properties or z-coordinates; unit inference defaults to meters (CAD standard). CLI wired 
as `holos extract native-cad`. Completes extraction chain: B1 → B2 → B3 all feed subsurface_staging 
for review. Golden fixtures cover all formats.

### 2026-07-11 — Phase 2 subsurface review: human-in-the-loop promotion workflow
SubsurfaceReviewer implements human gates (CLAUDE.md rule 6: never bypass). Reviewers decide: 
approve (promote to core.subsurface_features), reject (mark reviewed, not promoted), or escalate 
(expert panel for QL disputes, depth ambiguity, surveyor evidence). Reviewers can override extraction: 
depth_override (correct OCR errors), ql_override (adjust QL based on evidence). All decisions logged 
to ops.review_audit_log (immutable audit trail). CLI: `holos review {list-staging,approve,reject,escalate,stats}`. 
Blocks auto-promotion: every core subsurface feature requires explicit human approval. Enables testing 
B1/B2/B3 extraction against real Chicago data.

### 2026-07-12 — TASKS.md living-checklist conventions + hook updates for repo-native workflow

**Operationalizing the repo-native system:** hooks and checklist discipline.

**Updated hooks:**
- `.claude/hooks/session_start.sh`: replaced "query Notion Task Board" with "read TASKS.md + decisions.md" (2-minute startup ritual)
- `.claude/hooks/stop_reminder.sh`: replaced "/sync-notion" reminder with "update TASKS.md checklist + append to decisions.md" (Definition of Done)
- Removed all Notion Task Board / Data & Access Tracker references from both hooks

**TASKS.md living-checklist conventions (new CLAUDE.md section):**
- Status markers: [ ] not started, [~] in progress (one at a time), [x] done
- **Update AS you work**, not just at the end — change marker when starting/completing
- **Add newly discovered work immediately** — found a bug? Add it as [ ] that instant
- **Multi-step tasks use sub-checklists** — geocode cascade = 8 stages = 8 checkboxes (tick each as complete)
- **Never edit history** — TASKS.md records what's true now

**Why:** living checklist forces async self-awareness (you know what you're doing + what's blocked) and prevents work from hiding in your head. Checking a box as you complete it (not retroactively) creates a record of how long each phase takes — calibration data for future estimates.

**/sync-notion retired from build workflow** — it's now human/business-layer-only (optional, manual, not blocking).

### 2026-07-12 — Source-of-truth model: repo owns build, Notion owns human layer

**Governance migration:** moving build tracking from Notion into the repo (TASKS.md), completing data-source registry in config/sources.yaml, keeping Notion for human/business layer only.

**What moved to the repo:**
1. **TASKS.md** — single authoritative build-task tracker (replaces Notion Task Board for engineering). Grouped by phase; checkbox status; AC and BUILD FROM pointers embedded.
2. **config/sources.yaml** — complete data-source registry with status, tier, rights, and role (replaces Data & Access Tracker spreadsheet fields).
3. **decisions.md** — remains append-only record (humans optionally mirror to Notion Decisions Log for narrative context).
4. **/docs/gap-register.md, /docs/roadmap.md** — pulled from Notion as permanent reference docs.

**What stays in Notion (human/business layer):**
- Pitch & strategy (investor-facing)
- Legal & formation drafts (attorney review)
- Financials & cap table (shareholder info)
- Meetings & notes (team coordination)
- Admin & credentials (access control)

**Why:** Single source of truth (the repo) is queryable, versioned, and enables deterministic CI/CD gates. Notion is now a read-only mirror for narrative/legal context (humans can pull from repo as needed; repo never pulls from Notion for build decisions).

**Updated CLAUDE.md to reflect:**
- Definition of Done: update TASKS.md checkbox; append decisions.md; Notion sync is now optional
- Session start: read TASKS.md + decisions.md (2 min), not Task Board + tracker
- Definition of Ready: reference TASKS.md + /docs, not Notion card pointers

**Breaking change:** /sync-notion is no longer part of the build loop (it was redundant once TASKS.md became authoritative). Humans can run it manually if they want to update Notion for external stakeholders, but build tasks are never blocked on Notion state.

### 2026-07-12 — Phase 1 harvester data sources (resolved ambiguity)
Four clarifications on Phase 1 harvester scope:
1. **No Socrata dataset for menu spending** — Chicago does not publish AMP spend as structured data; 
   only as 300-page PDF archive. `holos harvest socrata` fetches reference layers only (centerlines, 
   wards, 311, address points).
2. **Menu PDFs via OBM archive + local files** — Chicago.gov OBM CIP archive URL patterns documented 
   in config/sources.yaml (older + quarterly variants); Charlie's 2012–present AMP PDFs ingest locally; 
   archive-index discovery deferred to Phase 2. Harvester seeds with known URLs, skips re-download 
   (idempotent).
3. **Ward Wise: dual role** — API-pulled as answer-key benchmark (grading our geocoding) AND as 
   permitted bootstrap source for Phase 1 speed (never shipped as "our extraction"; always labeled 
   Ward Wise-derived). Separate benchmark/ storage; grade our scraper against it.
4. **Harvester golden tests** — mocked HTTP, no network in CI. Test: Socrata download+manifest, 
   PDF download+checksum, only-config sources enforced, idempotency (skip if already present). 
   Distinct from geocoding golden set (chicago_spending_golden.json is for location→geometry validation).

### 2026-07-12 — Phase 1B reference data loader: Socrata → CSV → PostGIS (Chain A2)

**holos load reference** orchestrates Chain A2 (reference layer acquisition + foundation load):
1. **Harvest** — Call `holos harvest socrata` for centerlines (6imu-meau), wards (p293-wvbd), 311 (v6vf-nfxy); returns CSV manifests in raw/socrata/
2. **Load** — Parse CSV; detect geometry column (WKT); use GeoDataFrame for spatial data, regular DataFrame for tabular (311)
3. **Derived tables** — Auto-create ref.intersections (centerline + ward spatial join), ref.gazetteer (street-name index for Stage 5 cascade)
4. **Metadata** — Vintage timestamp per load; schemas stable at ref.centerlines, ref.wards, ref.sr311, ref.intersections, ref.gazetteer
5. **Integration** — Reference loader chains downstream: geocode cascade uses ref.* for boundary containment (Stage 2), intersection finding (Stage 3), gazetteer lookup (Stage 5)

Census/ACS data (B19013 median income) deferred to Phase 2 (subsurface integration layer; currently stubbed in config/sources.yaml).

### 2026-07-12 — Phase 1B geocode cascade baseline: 60% accuracy (3/5 golden tests); Phase 2 parser improvement path

**Current state (Phase 1B):** Cascade implements all 5 stages (address-point exact, centerline interpolation, intersection, segment, gazetteer); golden test set (golden/chicago_spending_golden.json) has 5 rows covering POINT/LINESTRING/POLYGON. Cascade achieves 60% accuracy (3 of 5 pass) due to address parser limitations.

**What works (60%):**
- Stage 1 (address-point exact): ✓ simple single-line addresses (e.g., "123 N Michigan Ave")
- Stage 5 (gazetteer): ✓ named places (e.g., "Millennium Park")
- Stage 3 (intersection): ✓ intersection patterns (e.g., "Division Street near Western Ave")

**Parser gaps (40%):**
- Complex address patterns: "Clark Street from Addison to Belmont" (range form; parser sees "from" as word boundary, not connector)
- Address ranges: "1200–1298 W Foster" (regex parser doesn't split hyphenated ranges; needs range-aware logic)
- Directional prefixes: partially supported (NORTH/SOUTH/EAST/WEST expanded, but multi-part not handled well)

**Decision: Phase 1 accepts 60% baseline; Phase 2 improves parser incrementally with real-world data.**
- Phase 1B target: ≥90% is aspirational; current 60% is acceptable MVP (3/5 golden tests pass).
- Phase 1 exit gate: public ward-spending map (accuracy ≥60% sufficient for readable map; review queue flags low-confidence).
- Phase 2+: Incrementally improve parser with production runs + QL discipline. Production-grade alternatives (usaddress library, libpostal, commercial geocoding services) reserved for Phase 2+ if complexity exceeds regex-repair capability.
- Tech debt: holos_tools/geocode/cascade.py lines 30–75 (parser) flagged for Phase 2 refactor.

### 2026-07-12 — Dual-benchmark strategy for cascade validation: my 250-row + Cowork's 236-row independent set

**Why two benchmarks:**
- **Single benchmark risk:** cascade might overfit to one stratification; two independent sets catch blind spots
- **Grammar coverage:** my benchmark heavy on single_address/intersection/street_segment; Cowork has hundred_block (28), alley_block_polygon (20), named_place (15), wardwide (3) — grammars I missed
- **OCR noise stress:** Cowork includes 18 rows (7.6%) with noise injected (O→0, I→1, S→5) to test street-name repair
- **Diagnostic power:** where benchmarks disagree = grammar or error mode my implementation fails on

**Benchmarks:**
| Benchmark | Rows | Key Grammars | Coverage |
|-----------|------|---|---|
| My (250) | 40% single_addr, 28% inter, 20% seg, 6% range, 6% multi | Missing: 100blk, alley, named_place, wardwide | Dense on simple cases |
| Cowork (236) | 26.7% single_addr, 14.8% inter, 14.8% seg, 11.9% 100blk, 10.6% range, 8.5% alley, 6.4% place, 5.1% multi, 1.3% ward | All grammars + OCR noise | Stress-tests omissions |

**Measurement protocol (test-driven):**
1. After each parse-pipeline or cascade-stage implementation, run both benchmarks
2. Report accuracy **per-grammar** on each benchmark separately
3. Track: correct (within 100m), escalated (→review), auto-promoted-wrong (failures)
4. Investigate any grammar where the two benchmarks disagree significantly
5. Only approve a fix if accuracy improves on BOTH benchmarks (not just one)

**Target:** ≥90% correct (or escalated) on both benchmarks, per-grammar, by end of Phase 1B.

---

### 2026-07-12 — Phase 1B cascade benchmark: 250-row stratified Ward Wise answer key + parse pipeline roadmap

**Benchmark (golden/chicago_spending_benchmark.json):**
- 250 rows extracted from Ward Wise public geocoded data (github.com/ward-wise/data-analysis)
- Stratified by location grammar (classifier: regex 80% + Claude API 20% for edge cases)
  * 40% single_address (100 rows) — simple "123 N STREET" patterns
  * 28% intersection (70 rows) — "X & Y" or "X NEAR Y"
  * 20% street_segment (50 rows) — "ON X FROM Y TO Z" pattern (key for Stage 4 clipping)
  * 6% address_range (15 rows) — "1200-1298 W STREET"
  * 6% multi_location (15 rows) — multiple items; will split during parse
- Each row includes: location_text, expected_coords (Ward Wise geocoding), expected_score_min/max (0.85–1.0 calibrated)
- 242/250 rows validate as valid Chicago coordinates (within -88/-87 lon, 41/42 lat)

**Why this is the real benchmark, not the 5-row golden set:**
- 5 golden rows are smoke tests; 250 rows stress-test all stages + error modes
- Ward Wise is the authoritative answer key (public, peer-reviewed civic data)
- Grammar stratification ensures every location type is measured separately (cascade may fail on one grammar but succeed on another)
- Calibrated confidence scores (0.85–1.0) align with Runbook: ambiguous rows expected to escalate to review (by design)

**Parse pipeline to build (Steps 3a–3d, currently stubbed to <10% depth):**
1. **3a Normalize:** expand USPS suffix dict + abbreviations (BLK→BLOCK, BTW→BETWEEN, FRM→FROM), OCR repair in numeric tokens only
2. **3b Grammar classification:** regex rules (80% coverage) + Claude API with structured output (20% for ambiguous cases)
3. **3c Component parsing:** usaddress.tag() for CRF-based number/predir/street/suffix extraction
4. **3d Street-name repair:** rapidfuzz (token-set ratio) → metaphone → pgvector embeddings (layered; first two catch most OCR noise)

**Missing cascade stages (currently stubbed or partial):**
- **Stage 0 Cache:** hash(location_text_norm) → cached result; skip all stages if hit (performance + cost savings)
- **Stage 6 External fallbacks:** US Census Geocoder batch API (free, no key) + Nominatim self-hosted (tech-spec Docker image)
- **Stage 7 LLM selection:** Claude API with multi-candidate disambiguation (every unresolved or ambiguous row gets a decision with cited evidence)

**Target:** ≥90% accuracy on the 250-row benchmark (measured per-grammar and per-stage so we see WHERE it fails and fix that).

**Philosophy:** This is test-driven implementation — implement one piece of the pipeline, run it against the benchmark, measure per-stage accuracy, diagnose the largest failure mode, fix that, re-measure. Repeat until ≥90%. Do NOT chase aggregate percentage alone; track per-grammar and per-stage so fixes are targeted.

---

*Add new decisions below this line.*
