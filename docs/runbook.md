# Project Holos — Geolocation Automation Runbook

The complete step-by-step process for turning text locations into map geometry

Deep-dive companion to the Technical Build Spec (Part I, Chain A1 §4–7) • July 2026

This document specifies the moat in executable detail: every file, every package, every stage of the cascade that converts a string like "ALLEY RESURFACING — 5400 BLK W MADISON ST" into a confidence-scored geometry in PostGIS. It also specifies exactly where AI is allowed to help, where it is forbidden, and how data is transferred between formats at every hop.

## Design invariants (repeated from the constitution because they govern everything below)

1. **AI interprets; deterministic code locates.** A language model may parse, classify, repair, and select among candidates produced by deterministic matchers. **It may never invent a coordinate.** Every X/Y in the hub traces to a reference-data match, an interpolation along reference geometry, or a human decision — nothing else.

2. **Every result carries: method, score, stage, reference-data vintage, and geometry-type reason.** An unexplained coordinate is a defect even when it happens to be correct.

3. **Below threshold → review queue, never a guess.** The system's credibility is worth more than its match rate.

---

## STEP 0 — Understand the target: three geometries, one contract

Every input row's `location_text` resolves to exactly one of:

| Geometry | When | Example input | Output |
|----------|------|---------------|--------|
| POINT | Single address, single facility, intersection | 4536 N MAGNOLIA AVE / MADISON & PULASKI | Point(4326) |
| LINESTRING | Street segment, block range, corridor work | ASHLAND FROM DIVISION TO NORTH AVE / 1200–1298 N ASHLAND | Clipped centerline |
| POLYGON | Named area, park, facility grounds, alley footprint, whole-ward work | DOUGLASS PARK / WARD 27 — TREE TRIMMING (WARDWIDE) | Reference polygon |

**The output contract per row** (this JSON is the interchange format at every stage boundary):

```json
{
  "row_id": "amp-2019-w32-0141",
  "location_text_raw": "ALLEY RESURFACING 5400 BLK W MADISON ST",
  "location_text_norm": "5400 BLOCK W MADISON ST",
  "location_grammar": "hundred_block",
  "parse": {
    "number": "5400",
    "block": true,
    "predir": "W",
    "street": "MADISON",
    "suffix": "ST"
  },
  "geometry_type": "LINESTRING",
  "geometry_reason": "hundred-block resolves to one block face of centerline",
  "geom_wkt": "LINESTRING(-87.7601 41.8807, -87.7581 41.8807)",
  "srid": 4326,
  "method": "centerline_block_clip",
  "stage": 4,
  "score": 0.94,
  "candidates_considered": 1,
  "ref_vintage": {
    "centerlines": "2026-06-30",
    "wards": "2023"
  },
  "flags": [],
  "needs_human": false
}
```

---

## STEP 1 — Acquire and prepare the reference data (the files that make geocoding possible)

Geocoding is a **join against reference data**; the reference layers are 80% of accuracy. Build this foundation before writing a single matcher. All loads go to the `ref` schema, versioned with `valid_from`/`valid_to` (boundaries and centerlines change; historic spending must join to historic geography).

### Reference file

| # | Reference file | Source | Format in → format kept | Role |
|---|---|---|---|---|
| R1 | Chicago street centerlines (with from/to address-range fields per side, street name components, class incl. alleys) | Chicago Data Portal, dataset 6imu-meau | GeoJSON/SHP → PostGIS ref.centerlines | Interpolation, segments, blocks, intersections |
| R2 | Chicago address points | Chicago Data Portal (confirm current dataset ID on the portal at build time) | CSV/GeoJSON → ref.address_points | Stage-1 exact/fuzzy match — the highest-precision anchor |
| R3 | Ward boundaries, 2023 vintage | Portal, p293-wvbd | GeoJSON → ref.wards (vintage='2023') | Containment validation, wardwide polygons |
| R4 | Ward boundaries, 2015 and 2003 vintages | Portal archive / city clerk | → ref.wards (vintage rows) | Historic rows (2005–2015, 2015–2023) join to their map |
| R5 | Community areas, parks, school locations | Portal (community areas; Park District boundaries; CPS locations) | → ref.gazetteer_polygons / _points | Named-place resolution (Stage 5) |
| R6 | Cook County parcels | Cook County GIS open data | → ref.parcels | Facility/alley-adjacent polygon resolution; developer product later |
| R7 | National Address Database (NAD) | US DOT, free download | CSV/GDB → ref.nad_points (IL slice) | Cross-check + the day-one path for any other jurisdiction |
| R8 | OpenAddresses (IL/Cook collections) | openaddresses.io | CSV → staging | Cross-check address corpus for QC |
| R9 | Census TIGER/Line (edges, faces, place) | census.gov | SHP → ref.tiger_* | What the Census geocoder matches against — keep local for debugging its answers |
| R10 | OSM extract, Illinois | Geofabrik | .pbf → Nominatim import (Step 2) + ref.osm_* via osm2pgsql | Self-hosted fallback geocoder + gazetteer enrichment |
| R11 | 311 requests | v6vf-nfxy Portal | CSV → ref.sr311 | Not a geocoding input — the need-match analytics join later |

### Transfer commands (the pattern for every layer)

```bash
# Socrata → GeoJSON (paged) → PostGIS, reprojected, vintage-stamped
holos harvest socrata --dataset 6imu-meau --out raw/centerlines/2026-06-30/
ogr2ogr -f PostgreSQL PG:"dbname=holos" raw/centerlines/2026-06-30/centerlines.geojson \
  -nln ref.centerlines_20260630 -t_srs EPSG:4326 -lco GEOMETRY_NAME=geom -progress
psql -c "CALL ref.publish_vintage('centerlines','2026-06-30');"
```

### Derived reference tables to build immediately (SQL views/materializations)

- **ref.intersections** — node points where two named centerlines meet, with both street names attached (built once via `ST_Intersection` over shared endpoints; indexed on `(street_a, street_b)` both orderings).

- **ref.blocks** — centerline split into hundred-block faces using the address-range fields (Chicago's grid: ~8 blocks/mile, addresses increment 100 per block from the State & Madison origin — this regularity is a free sanity checker: a parsed number and a matched block whose range doesn't bracket it is an automatic flag).

- **ref.gazetteer** — unified named-place table (parks, schools, community areas, facilities) with `name`, `aliases[]`, `geom`, `valid_from`/`valid_to`. **Temporal aliases matter:** Douglas Park became Douglass Park in 2020; a 2012 report says Douglas, a 2024 report says Douglass, both must resolve to the same polygon with the right vintage.

- **ref.street_names** — distinct street name dictionary with soundex/metaphone and embedding columns (Step 2) for fuzzy repair.

---

## STEP 2 — Install the software (exact manifest)

### External services (no install, free)

**US Census Geocoder batch API** — CSV in, CSV out, up to 10,000 rows per batch file, returns match type, matched address, side-of-street, and TIGER IDs. It is the **only external service in the default cascade** because its terms permit storing results.

**Commercial geocoders (Google/Geocodio/Esri) stay out of the default path** — Google's terms restrict storing/displaying results off-platform; if ever needed, Geocodio is the storage-friendly commercial choice. **Revisit only if the open cascade plateaus below target.**

### Python environment

```bash
# Core geo + data (Python 3.12 project via uv)
uv add geopandas shapely pyproj fiona rapidfuzz usaddress duckdb \
  pandas pyarrow typer pandera httpx
uv add sentence-transformers  # local embeddings for gazetteer/street fuzzy match
uv add anthropic              # Claude API for the interpretation layer

# libpostal (optional now, required for multi-city): C lib + `postal` binding
# note: ~2 GB model download; build it into the Docker image, not laptops

# System tools
# apt/brew: gdal-bin (ogr2ogr, gdal_translate), postgresql-client, tippecanoe

# Services (docker-compose additions to the hub)
# postgis/postgis:16 # already running (hub)
# pgvector # extension in-hub: CREATE EXTENSION vector;
# mediagis/nominatim:5 # self-hosted OSM geocoder, seeded with Geofabrik IL extract
# ghcr.io/degauss-org/geocoder # optional: DeGAUSS — open, containerized, offline US street-range geocoder; zero-ToS-risk batch fallback
# martin # tiles (already in stack)
```

---

## STEP 3 — Normalize and parse the location text (where AI earns its keep)

Raw `location_text` arrives filthy: OCR noise (`MAGN0LIA`, `MAD1SON`), inconsistent abbreviations, missing directionals (fatal in Chicago's grid — there is a 5400 W Madison and nothing at 5400 E, but many streets exist N and S), and a dozen phrasings for the same intent. Stage order:

### 3a. Deterministic cleanup

```bash
holos geocode normalize
```

- Unicode NFC, uppercase, collapse whitespace, strip punctuation except `–/&`.
- Expansion dictionaries (versioned YAML): USPS Publication 28 suffix table (`ST↔STREET`, `AV/AVE↔AVENUE`), directionals, city-specific tokens (`BLK→BLOCK`, `BTW/BET→BETWEEN`, `FRM→FROM`).
- OCR confusion repair **only inside numeric tokens** (`O→0`, `l/I→1`, `S→5` when flanked by digits) — **never inside street names at this stage.**

### 3b. Grammar classification

Every string is classified into one location grammar:
```
single_address | address_range | hundred_block | intersection | street_segment | named_place | wardwide | multi_location | unresolvable_text
```

- **First pass:** a versioned rule/regex table (fast, free, transparent) catches ~80%.
- **Second pass** (the remainder): **Claude API call** with a strict JSON schema — input is the normalized string plus the report's ward/year context; output is `{grammar, fields{}, repairs[], self_conf}`. Temperature 0, structured output enforced, few-shot examples drawn from reviewed rows. **Two hard rules:** the model must copy street tokens verbatim or list them under `repairs[]` with the original (no silent rewriting), and `multi_location` strings are split into child rows (`"RESURFACING: 4500 BLK N MAGNOLIA & 4600 BLK N LAKEWOOD"` → two rows sharing a parent), never averaged into one geometry.

### 3c. Component parsing

`usaddress.tag()` (a CRF model — built, fittingly, by Chicago's own DataMade civic-tech shop) tags number/predir/street/suffix on address-like grammars; `libpostal` replaces it when the pipeline goes multi-city. **Parser disagreements with the LLM's fields** → flag, prefer the CRF for components, prefer the LLM for grammar.

### 3d. Street-name repair (deterministic + embeddings, still no coordinates)

Parsed street not in `ref.street_names` →
1. `rapidfuzz` token-set ratio vs. the dictionary
2. metaphone match
3. pgvector cosine over sentence-transformer embeddings of names+aliases

Top candidate above `repair_accept` (config) with agreeing ward context → auto-repair with `flags:['street_repaired']`; between `repair_review` and `repair_accept` → carry both candidates forward into Stage 7; below → review.

### Files produced

`staging.geocode_parsed` (Parquet + table): one row per (possibly split) input with grammar, fields, repairs, parse confidence. **This table is the cache key source** — `hash(location_text_norm)` — so the same string never costs an LLM call or a match twice (`ops.geocode_cache`).

---

## STEP 4 — The matching cascade (deterministic core, cheapest-first)

Each stage attempts a match; success emits the output contract and stops; failure falls through. Base scores are starting points — Step 6 calibrates them against ground truth.

### Stage 0 — Cache

`ops.geocode_cache` hit on `hash(location_text_norm)` where reference vintages match → reuse (score inherited, `method='cache'`). Typical warm-run hit rate on menu data: high — the same alderman resurfaces the same blocks.

### Stage 1 — Address-point match (POINT, base 0.97)

Normalized join of parsed components against `ref.address_points`; if exact fails, `rapidfuzz` ≥ config threshold on the full normalized string within the same street. One candidate → done. Multiple candidates (same address, different points — rare, usually condo/campus points) → nearest to street centerline wins, `flags:['multi_addresspoint']`.

### Stage 2 — Centerline interpolation (POINT, base 0.88)

For `single_address` with no address-point hit: match street name + suffix + predir to `ref.centerlines`; find the segment whose side-appropriate range brackets the number (parity: odd/even determines side); position = `(number − from) / (to − from)` along the segment via `ST_LineInterpolatePoint`; optional 15-ft perpendicular offset to the correct side (config: off for spending data — the centerline point is the honest answer). **Grid sanity check:** interpolated point must sit within its expected hundred-block; violation → flag, demote score.

### Stage 3 — Intersection (POINT, base 0.95)

`intersection` grammar → lookup `(street_a, street_b)` in `ref.intersections` (both orderings, fuzzy street repair already applied). Multiple nodes (streets crossing twice — diagonals like Milwaukee/Lincoln do this) → ward context disambiguates; still ambiguous → both candidates to Stage 7.

### Stage 4 — Segment & block clipping (LINESTRING, base 0.92)

- **street_segment** (`X FROM A TO B`): resolve the two bounding intersections (Stage-3 logic), then clip the named street's centerline between them — merge segments (`ST_LineMerge`), measure endpoints (`ST_LineLocatePoint`), extract (`ST_LineSubstring`). Continuity check: clipped length vs. straight-line distance ratio ≤ config (catches wrong-branch merges on discontinuous streets).

- **hundred_block / address_range**: select the `ref.blocks` face(s) whose ranges intersect the parsed range → one block = one LINESTRING; multi-block ranges merge. **Cost sanity cross-check** (Verifier owns it, but the flag is set here): reported $ vs. clipped length outside plausible unit-cost band → `flags:['cost_length_outlier']`.

### Stage 5 — Named place / gazetteer (POLYGON or POINT, base 0.90)

`named_place` → exact/alias match on `ref.gazetteer` (vintage-aware) → fuzzy (`rapidfuzz`) → embedding cosine (pgvector). Polygon if the place has one (parks, community areas, school grounds via parcel join); else facility POINT with `flags:['point_for_named_place']`. 

`wardwide` → the ward polygon for the row's period-correct vintage, score 0.99, `geometry_reason='wardwide declared'`.

### Stage 6 — External fallbacks (POINT, base 0.75, capped)

Only rows still unresolved:
- (a) **Census batch geocoder** — write pending rows to `census_batch_{run}.csv` (≤10k), POST, parse returns; accept only `Match/Exact` or `Match/Non_Exact` with our street-name agreement
- (b) **self-hosted Nominatim** (OSM) same acceptance rule
- (c) **optional DeGAUSS** container for offline runs

External results are **always re-validated** against ward containment before scoring, and capped at 0.75 because the reference data isn't ours. Disagreement between two externals → both to Stage 7.

### Stage 7 — AI-assisted candidate selection (no new coordinates, base = chosen candidate's stage score − 0.05)

Everything still unresolved or multi-candidate goes to one Claude call per row, receiving: the raw + normalized text, parse, ward/year context, and **every candidate the deterministic stages produced** (each with its method, score, and a reverse-lookup description — "Stage 2 interpolation: 5432 W MADISON ST, block face 5400–5498"). The model returns `{decision: select|unresolvable, candidate_id, justification, self_conf}`. 

**Selecting a candidate requires citing which text evidence discriminates; `unresolvable` is a fully acceptable answer.** 

**The model cannot emit coordinates, cannot propose a candidate not in the list, and its justification is stored** — this is the auditable boundary between AI judgment and invented data.

### Stage 8 — Human review queue

Everything else, with candidates and justifications pre-attached so a reviewer resolves most items in under a minute on the map UI. **Human decisions write back to the cache and to the few-shot example pool** (Step 3b) and golden set (Step 6) — **every human minute makes the machine better.**

---

## STEP 5 — Geometry-type decision & validation gates

**Geometry type follows grammar** (table in Step 0) — never inferred from cost or category.

**Post-match validation** (all deterministic, all reason-coded):

1. **Ward containment** (vintage-aware): geometry must intersect the row's stated ward polygon for that year's map. Pre-2015 rows check the 2003 map; 2015–2023 the 2015 map; 2023+ the 2023 map. Near-miss ≤ 200 ft of the boundary → `flags: ['ward_boundary_adjacent']` (boundary streets are genuinely shared); farther → review.

2. **Grid consistency** (Stage 2/4 outputs): hundred-block bracket check.

3. **Duplicate geometry** across rows in the same year/ward with different costs → conflation review, not silent keep-both.

4. **Topology:** LINESTRINGs simple & single-part after merge; POLYGONs valid (`ST_MakeValid` never auto-applied to reference layers, only to staged outputs with a flag).

---

## STEP 6 — Confidence scoring & calibration (the number engineers will trust or won't)

```
score = base(stage) × ∏ modifiers , clamped [0,1]
```

**Modifiers (config-versioned):**
- `street_repaired` ×0.93
- `multi_candidate` margin <0.1 ×0.90
- `ward_boundary_adjacent` ×0.97
- `external_source` ×cap
- **LLM self_conf blended only as a tiebreak, never a boost above deterministic score**

### Calibration loop

The golden set = 500 stratified rows with human-verified geometry (seeded from the Ward Wise answer key + our own reviewed rows; stratified across grammars, years, wards). Every config or prompt change re-runs the harness: reliability curve (predicted score vs. observed correctness), match rate @0.85, geometry-type accuracy, median distance error vs. truth (points), and length-overlap IoU (lines). 

**The ai-specialist lens blocks release on miscalibration** (predicted 0.9 bucket performing at 0.7), **not on low coverage** — honest 60% beats confident-wrong 90%.

**Thresholds that gates use:**
- `auto_promote` ≥ 0.85 (councils still run; 2% random human audit)
- `review_band` 0.60–0.85
- `reject` <0.60 (candidates preserved for Stage 7/8)

---

## STEP 7 — Data transfer map (formats at every hop, and the tools that move them)

```
PDF/portal ──pdfplumber/Claude vision──▶ extractions/{doc}.json
└─(manifested raw bytes kept forever in raw/)

extractions ──pandas normalize──▶ staging.rows (Parquet, master schema)

staging.rows ──Step 3──▶ staging.geocode_parsed (Parquet + PG table)

parsed ──Step 4 cascade──▶ geocode_results.parquet ← the output-contract rows

results ──GeoPandas──▶ GeoParquet (analytic lake, DuckDB-readable)
└──ogr2ogr / COPY──▶ PostGIS staging.spending_projects

staging ──councils + gates──▶ core.spending_projects (4326 + generated 3435)

core ──martin──▶ MVT tiles ──▶ MapLibre dashboard
core ──tippecanoe──▶ PMTiles (static public snapshot, zero-server demo)
core ──FastAPI──▶ GeoJSON API
core ──DuckDB──▶ marts (need-match, cost/sqft)
core ──ogr2ogr──▶ GeoPackage/CSV exports (tier-gated)
```

**Open-source movers by hop:**
- `pdfplumber`/`PyMuPDF` (capture)
- `pandas`/`pandera` (normalize+validate)
- `usaddress`/`libpostal`/`rapidfuzz`/`sentence-transformers` (parse/repair)
- `GeoPandas`/`Shapely`/`pyproj` + PostGIS SQL (match geometry)
- `ogr2ogr` & Postgres COPY (bulk transfer — **never row-by-row inserts**)
- `GeoParquet` + DuckDB (analytics without touching prod)
- `martin`/`tippecanoe` (delivery)

**Every hop appends provenance; no hop drops columns.**

---

## STEP 8 — Automation wrapper (how it runs unattended)

### CLI

```bash
holos geocode cascade --in staging.rows --run-id … --config config/geocode.yaml --json
```

Pure, idempotent, resumable (skips cached), emits metrics JSON (rate per stage, LLM calls, $).

### Agent

The **Geolocator subagent** (tech spec Appendix B) runs the CLI, reads the metrics, investigates anomalies (stage-2 rate collapsed? → probably a centerline vintage change), files review payloads, and emits the structured contract. **It owns judgment about the run, not the matching math.**

### Schedule

Nightly headless run (orchestrator or `claude -p` in GitHub Actions) on new harvests; council fan-out; digest with metrics delta.

**Batch sizes:** LLM calls batched 20 rows/request where grammar allows; Census in 10k files; DB writes in COPY chunks.

### Cost envelope to expect

Deterministic stages ≈ $0; LLM interpretation touches only the residual (~10–20% of rows once dictionaries mature) at fractions of a cent per row on the fast tier — **track $ / 1k rows in ops metrics and tune tiering from data, not vibes.**

---

## STEP 9 — Where AI helps (and where it is banned) — the one-page summary

| Task | AI role | Tool | Banned behavior |
|------|---------|------|---|
| Grammar classification of messy text | Primary, on the residual after rules | Claude API, JSON schema, temp 0 | Rewriting street tokens silently |
| OCR/typo repair | Propose repairs with originals preserved | Claude + rapidfuzz/metaphone/embeddings | Repairing outside candidate dictionary |
| Multi-location strings | Split into child rows | Claude | Averaging into one geometry |
| New source-format adapters | Draft adapter config → human approves | Claude Code session | Auto-applying an unreviewed adapter |
| Candidate selection (Stage 7) | Choose among deterministic candidates with cited evidence | Claude API | Emitting/adjusting coordinates; inventing candidates |
| Gazetteer aliases (renames, nicknames) | Propose alias rows w/ effective dates | Claude + web verification | Writing aliases without a source |
| Run anomaly triage | Diagnose metric shifts, draft fixes | Geolocator agent in Claude Code | Editing thresholds/config without a gate |
| Review acceleration | Pre-brief each queue item | Council verdicts + Stage-7 justifications | Auto-approving its own work |

---

## STEP 10 — Worked examples through the cascade

1. **4536 N MAGNOLIA AVE** → grammar `single_address` (rules) → Stage 1 address-point hit → POINT, 0.97, done. **Cost: $0.**

2. **ON ASHLAND FROM DIVISION TO NORTH AVE** → `street_segment` → both intersections resolve (Stage 3 logic) → Stage 4 clip, continuity ok → LINESTRING 0.92; ward containment pass.

3. **5400 BLK W MAD1SON ST** → numeric-token repair fixes `1→I`? No — `MAD1SON` is a name token: `rapidfuzz` → `MADISON` (0.96, ward agrees) → `hundred_block` → Stage 4 block face → LINESTRING 0.92 × 0.93 (street_repaired) = 0.86, auto-promote band, flagged.

4. **DOUGLAS PARK** in a 2013 row → gazetteer alias (pre-2020 name, vintage-aware) → Douglass Park POLYGON 0.90; same string in a 2024 row resolves identically via alias — one polygon, two names, zero confusion.

5. **RESURFACING VARIOUS LOCATIONS WARD 27** → `wardwide` → 2023-vintage Ward 27 POLYGON 0.99, `geometry_reason='wardwide declared'` — honest area, not a fake point.

6. **IN FRONT OF THE OLD LIBRARY BY THE VIADUCT** → rules fail → LLM: `unresolvable_text`, no candidates survive validation → review queue with the LLM's reading attached; human resolves in the map UI; answer joins the cache + golden set.

---

## STEP 11 — Build order (two-week execution checklist)

- **Day 1–2:** R1–R5 loaded + vintage-published; derived tables (intersections, blocks, gazetteer, street_names).
- **Day 3–4:** normalize + rule grammar + usaddress; golden-set v0 (200 Ward Wise rows).
- **Day 5–6:** Stages 1–4 + validations; first calibration run.
- **Day 7–8:** Stage 5 gazetteer + embeddings; Stage 6 Census/Nominatim wiring.
- **Day 9:** Stage 7 LLM selection + cache; Stage 3b LLM classifier on the residual.
- **Day 10:** review-queue payloads + map UI hookup; metrics + digest.
- **Day 11–12:** full 2005–2023 backfill run; calibration to thresholds; ai-specialist lens live. **Exit test = Tech Spec Appendix F, Phase 1.**

**Everything above is Chicago-instantiated but jurisdiction-agnostic by construction:** swap R1–R6 for the next city's layers (or fall back to R7 NAD + R9 TIGER + R10 OSM where no local data exists — that is precisely the Tier-3 play), keep the grammars, the cascade, the contract, and the calibration harness unchanged. **Verify current dataset IDs on the Chicago portal and package versions at build time.**
