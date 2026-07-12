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

## SOURCE OF TRUTH — read before touching code, docs, or Notion

**Every fact has exactly one home. The other side is a labeled mirror, never a
second original.**

### The Repo owns (build layer)
- All code and versioned work: `holos_tools/`, tests, agent defs (`.claude/agents/`)
- The build task tracker: **`TASKS.md`** (repo-native, updated as work progresses)
- Decisions log: **`decisions.md`** (append-only record of engineering choices)
- The data-source registry: **`config/sources.yaml`** (dataset IDs, URLs, status, rights)
- Reference documentation: `/docs/master-brief.md`, `/docs/tech-spec.md`, `/docs/runbook.md`, `/docs/gap-register.md`, `/docs/roadmap.md`
- This constitution: `CLAUDE.md` (non-negotiable rules + Definition of Done/Ready)

### Notion owns (human/business layer only)
- Pitch & strategy (investor-facing, narrative)
- Legal drafts & formations
- Financials & cap table
- Meetings & notes
- Admin & credentials
- **NOT the build tasks** (moved to `TASKS.md`)
- **NOT the data-source tracker** (moved to `config/sources.yaml` + decisions.md)
- **NOT the decisions log** (moved to `decisions.md`)

### No mirrors, no duplication
- If a build task appears anywhere in Notion, it's historical context only. The source of truth is `TASKS.md`.
- If a decision needs recording, append it to `/decisions.md` (repo), which is automatically mirrored to Notion by humans as needed.
- If a data source status changes, update `config/sources.yaml` (repo) and note the change in decisions.md.
- **Notion updates are manual and optional** (humans pull from the repo); they never drive build work.

## DEFINITION OF DONE — a task is complete only when ALL are true

1. Tests pass.
2. Work is committed to git.
3. **TASKS.md updated:** task status set to `[x]` (Done), acceptance criteria met, any decision appended to `/decisions.md`.
4. **Notion updates are optional** (humans mirror the decision log if needed for narrative/legal tracking).

### At session start
Read these files in order (in 2 minutes, not hours):
1. **`TASKS.md`** — open tasks by phase; prioritize "This week", then Phase 1
2. **`decisions.md`** — latest 5 entries; understand the current assumptions
3. **`.claude/agents/*.md`** — current agent defs if you're calling an agent

You never work from stale assumptions because the repo is the single source of truth.

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

1. **Read the source docs for this task.** Find the task in `TASKS.md`; the "BUILD FROM:" field points to `/docs/tech-spec.md`, `/docs/runbook.md`, `/docs/gap-register.md`, or `/docs/roadmap.md`. Read that section completely.
2. **Check the inputs it depends on:** `config/sources.yaml` (data registry + status + rights), `decisions.md` (prior decisions that affect this task).
3. **Post a SCOPE before touching code:**
   - The acceptance criteria (from `TASKS.md`; if missing, derive from source docs and confirm first).
   - Inputs → outputs (what it reads, what it produces, which schema/table/CLI).
   - Which documents you are building from (cite them, specific sections).
   - Anything ambiguous or missing → ask ONE specific question, don't guess.

Only after the scope is approved do you write code. This ritual runs at the start of every task, not just every session.

## STOPPING FOR REVIEW — be decisive, not open-ended

When you stop for human review, present: (a) concretely what you did or plan to do, and (b) a specific approval question with your recommended answer.

Do NOT ask open-ended questions like "should I proceed, or is there something you want me to check?" Decide what the right next step is, state it, and ask for a yes/no. If you are unsure, name the one thing you are unsure about and propose a default.

## Commands you will use constantly
- `uv run holos --help`  ·  `uv run pytest golden/ -x`  ·  `docker compose up -d hub`
- `holos validate all --changeset <id>` before requesting any review.
- **Update `TASKS.md`** with task status as you work (repo is now the source of truth for build tasks).
- **Append to `decisions.md`** whenever a decision is made (append-only; humans mirror to Notion if needed).

## Style
Python 3.12, typed, ruff. SQL migrations in `/db/migrations`. Small PRs.
