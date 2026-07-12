# Project Holos — Agent Constitution

You are working on Project Holos: converting messy civic records into a
georeferenced digital twin — above and below ground. Read `/docs/master-brief.md`,
`/docs/tech-spec.md`, and `/docs/runbook.md` before non-trivial work.

## Non-negotiable rules
1. Agents decide; deterministic tools execute. Never hand-compute a coordinate,
   transform, or geometry — run the `holos` CLI for it.
2. Never write to the `core` schema. Loads go to `staging`; promotion happens
   only through `holos load promote`, which enforces gates.
3. Every subsurface feature carries a QL level. GPR/EM depths are QL-B.
   QL-A requires a physical-exposure record. Never upgrade a QL level.
4. Every artifact carries provenance: source id, method, confidence, CRS.
   If you cannot populate these, stop and flag `needs_human`.
5. Elevation is meaningless without a vertical datum. Legacy Chicago plans are
   CCD until converted; never mix CCD and NAVD88 silently.
6. Blocking human gates are never bypassed, simulated, or pre-approved.
7. No data derived from private-utility records without a row in `ops.data_rights`.
   This is a legal constraint.
8. Final message of every pipeline job = JSON per `schemas/agent_output.schema.json`.
9. New/ambiguous source format → propose an adapter in `/pipelines/adapters/proposed/`,
   flag for review. Do not improvise parsing.
10. Log every decision a future teammate would need in `/decisions.md`
    (append-only; never edit history).

## Coordinate & datum policy
- Storage & web: **EPSG:4326** (WGS84) on all hub geometry columns.
- Engineering math & DXF: **EPSG:3435** (IL State Plane East, US ft). Reproject
  with pyproj / PostGIS `ST_Transform` — never hand-rolled math.
- Vertical: NAVD88 heights; sensor depths stored as depth-below-surface + a
  surface reference. Confirm the CCD→NAVD88 constant with a licensed surveyor.

---

## SOURCE OF TRUTH — read before touching Notion or docs

**Every fact has exactly one home. The other side is a labeled mirror, never a
second original.**

- **The repo owns anything that runs or is versioned:** code, schema, tests,
  agent configs, `CLAUDE.md`, `/decisions.md`, and the machine-readable config
  in `/config/*.yaml` (dataset IDs, URLs, thresholds the pipeline reads).
- **Notion owns anything humans plan, track, or read:** the Task Board, the
  Data / Outreach / Meetings trackers, the Decisions Log (human-facing mirror),
  Financials, Legal, and the narrative docs.
- **Nothing is owned by both.** Where a thing exists on both sides, the non-owner
  copy carries a banner: *"Mirror of [X] — do not edit here."*

Split-ownership rule for data sources: the **dataset ID/URL the code loads** lives
in `/config/sources.yaml` (repo owns it); the **acquisition status/FOIA/notes**
live in the Notion Data & Access Tracker (Notion owns those). Same source,
different fields — never fight over who is right.

If the repo and Notion disagree, the **owner side wins**; fix the mirror, and note
the reconciliation in `/decisions.md`.

## NOTION SYNC — Decisions Log + Data Rights only

Notion mirrors key decisions and tracks data rights (legal gate). Not a task-tracking system.

**Definition of Done — a task is complete only when ALL are true:**
1. Tests pass.
2. Work is committed to git.
3. **Notion is updated (if applicable):**
   - Any decision appended to `/decisions.md` ALSO appended to the Notion Decisions Log
   - Any new data source flagged in the Data & Access Tracker (if `ops.data_rights` row needed)

**What we DON'T sync to Notion:**
- Task Board (use git commits + GitHub issues instead)
- Outreach / Meetings trackers (not in scope for code-driven work)

**At session start:** read the latest `/decisions.md` entries so you don't work from stale assumptions.

### Notion IDs (targets for the MCP)
- Project Holos page: `38bf6ea8-4e41-803f-8858-f20effe04b85`
- Task Board (data source): `16156204-e1bb-4d13-95fc-099bebf685c0`
- Data & Access Tracker (data source): `e5b40003-cec0-48fe-a50e-b85b21fe34ce`
- Outreach & Partnerships (data source): `eb6346d2-5823-4651-8699-31574791732b`
- Meetings & Notes (data source): `66b5fd89-8396-4afa-9e1f-03063b9aecd5`
- Decisions Log (page): `39bf6ea8-4e41-81c5-83b8-c0400317b9b6`

**Never sync secrets to Notion.** Credentials live in `.env` (git-ignored) and a
password manager; the Notion Admin folder holds references only.

## Commands you will use constantly
- `uv run holos --help`  ·  `uv run pytest golden/ -x`  ·  `docker compose up -d hub`
- `holos validate all --changeset <id>` before requesting any review.
- `/sync-notion` at the end of every task.

## Style
Python 3.12, typed, ruff. SQL migrations in `/db/migrations`. Small PRs.
