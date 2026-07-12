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

---

*Add new decisions below this line.*
