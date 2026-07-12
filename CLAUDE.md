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

## NOTION SYNC — part of every task, not an afterthought

Notion is reachable through the Notion MCP. Keeping it current is a step in the
Definition of Done, not optional.

**Definition of Done — a task is complete only when ALL are true:**
1. Tests pass.
2. Work is committed to git.
3. **Notion is updated:** Task Board status set (Done / In progress), any decision
   appended to `/decisions.md` AND mirrored to the Notion Decisions Log, and any
   affected tracker updated (Data & Access, Outreach, Meetings).

**Do it the easy way:** run `/sync-notion` at the end of a task — it performs all
of the above in one consistent routine and writes the sync marker.

**At session start:** pull open tasks from the Notion Task Board (prioritize
`This week`, then Phase 1, Status `Not started` / `In progress`) and read the
latest `/decisions.md` entries so you never work from stale assumptions.

**Critical rule:** Do NOT modify CLAUDE.md's non-negotiable rules or Definition of Done
without explicit user approval. Propose changes and wait.

### Notion IDs (targets for the MCP)
- Project Holos page: `38bf6ea8-4e41-803f-8858-f20effe04b85`
- Task Board (data source): `16156204-e1bb-4d13-95fc-099bebf685c0`
- Data & Access Tracker (data source): `e5b40003-cec0-48fe-a50e-b85b21fe34ce`
- Outreach & Partnerships (data source): `eb6346d2-5823-4651-8699-31574791732b`
- Meetings & Notes (data source): `66b5fd89-8396-4afa-9e1f-03063b9aecd5`
- Decisions Log (page): `39bf6ea8-4e41-81c5-83b8-c0400317b9b6`

**Never sync secrets to Notion.** Credentials live in `.env` (git-ignored) and a
password manager; the Notion Admin folder holds references only.

## DEFINITION OF READY — before writing code for ANY task

A task is not ready to build until you have done ALL of the following and posted the result for approval. Never build from a task title alone.

1. **Read the source docs for this task.** Every Phase 1 task's Notion card names a "BUILD FROM:" pointer — read that section of `/docs/tech-spec.md` and/or `/docs/runbook.md`, plus the Master Brief section if named.
2. **Check the inputs it depends on:** `config/*.yaml` (source/threshold registry), the Notion Data & Access Tracker (rights + acquisition status), and `decisions.md`.
3. **Post a SCOPE before touching code:**
   - The acceptance criteria (copy from the task's AC on the board; if missing, derive from tech-spec/runbook and confirm first).
   - Inputs → outputs (what it reads, what it produces, which schema/table/CLI).
   - Which documents you are building from (cite them).
   - Anything ambiguous or missing → ask ONE specific question, don't guess.

Only after the scope is approved do you write code. This ritual runs at the start of every task, not just every session.

## STOPPING FOR REVIEW — be decisive, not open-ended

When you stop for human review, present: (a) concretely what you did or plan to do, and (b) a specific approval question with your recommended answer.

Do NOT ask open-ended questions like "should I proceed, or is there something you want me to check?" Decide what the right next step is, state it, and ask for a yes/no. If you are unsure, name the one thing you are unsure about and propose a default.

## Commands you will use constantly
- `uv run holos --help`  ·  `uv run pytest golden/ -x`  ·  `docker compose up -d hub`
- `holos validate all --changeset <id>` before requesting any review.
- `/sync-notion` at the end of every task.

## Style
Python 3.12, typed, ruff. SQL migrations in `/db/migrations`. Small PRs.
