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

---

*Add new decisions below this line.*
