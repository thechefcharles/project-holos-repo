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

---

*Add new decisions below this line.*
