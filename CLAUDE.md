# Project Holos — Agent Constitution

## What We're Building

You are working on **Project Holos**: converting messy civic records into a georeferenced digital twin — above and below ground. 

**Core mission:** Integrate spending data, utilities, and subsurface features into a unified, georeferenced model for city planners, engineers, subsurface coordinators, and civic transparency advocates.

**Data flow:** Harvest → normalize → geocode → validate → promote to `core` schema.

**Read first:** `/docs/master-brief.md`, `/docs/tech-spec.md`, `/docs/runbook.md` before non-trivial work.

## Technology & Architecture

- **Backend:** Python 3.12, typed (mypy), linted (ruff), tested (pytest golden)
- **CLI toolbelt:** `holos harvest`, `holos extract`, `holos geocode`, `holos load`, `holos validate`, `holos geometry`
- **Database:** PostgreSQL 16 + PostGIS (Docker), EPSG:4326 (WGS84) for storage, EPSG:3435 (IL State Plane East) for math
- **Schemas:** `core` (production, read-only), `staging` (working area, loaded via `holos load`), `ref` (reference geometry), `ops` (metadata, audit)
- **Deployment:** Flask API on Railway, map UI on Vercel
- **Testing:** Golden tests (`pytest golden/`), integration tests, E2E validation

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

## Agent Rules for This Project

**Screenshots:** When the user uploads a screenshot, **always** read it with the Read tool first before analyzing or responding. Do not assume content from previous screenshots.

**CLAUDE.md updates:** Only update this file if the user explicitly requests it or if adding a critical operational rule that affects all future work. Keep it focused and authoritative.

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
- Planning & roadmaps: `/docs/sam-voice-memo-plan-*.md` (product roadmaps, updated as work progresses)
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

## BLOCKING & SCOPE DISCIPLINE — no reclassification as escape hatch

**Getting stuck is not "done."** Hitting difficulty on a required task never makes it
out-of-scope, complete, or deferrable. This is the escape hatch you must NOT take.

**If blocked:**
1. State the **SPECIFIC technical blocker** (not vague: "API is slow" → "Census Geocoder API returns after 30s, benchmark has 250 rows = 2+ hours")
2. Either **solve it** (fix the blocker) or **escalate that exact problem** (present the blocker to the user, ask for guidance)
3. **Never reclassify the task's scope** to declare it finished ("I'll defer stages 6–7 and call stages 1–5 complete" is forbidden)

**A task is complete only when:**
- Its acceptance criteria (from TASKS.md) are **measured and met**, AND
- Work is committed, TASKS.md marked `[x]`, decisions logged

If you cannot meet acceptance criteria, do not mark done. State the blocker instead.

## Testing & Deployment

**Local development:**
```bash
docker compose up -d hub                    # Start PostgreSQL + PostGIS
uv run holos --help                         # See all CLI commands
uv run pytest golden/ -x                    # Run golden tests
```

**Test discipline:**
- Unit: `holos_tools/*/test_*.py` (covers extract, geocode, load, validate)
- Golden: `golden/` (covers end-to-end pipeline behavior)
- Integration: Geometry math, SQL correctness, RLS policies
- E2E: Production validation on real 2017 Chicago spending data

**Deploy pipeline:**
1. Commit + push to `dev` branch
2. GitHub Actions runs `pytest golden/ -x` + `ruff check` + `mypy`
3. Merge to `master` (triggers production deployment)
4. Vercel (frontend) + Railway (API) auto-deploy

**Deployment frequency:** Weekly (MVP iteration cycle)

## Open Decisions

| Decision | Status | Scope | Notes |
|----------|--------|-------|-------|
| Multi-segment street geocoding (Tier 2 Part 1) | ✓ Implemented | ST_LineSubstring + best-segment selection | See decisions.md 2026-07-16 |
| Subsurface feature escalation workflow (Tier 2 Part 3) | Planning | Manual review queue + truncation recovery | Affects 45 records, impacts confidence scoring |
| Production re-validation timing | TBD | Async or blocking on every load? | Timeout on 1784 records—needs batching or async runner |
| Address normalization for truncated records | [ ] | Recover "123 ADAMS FROM W MONROE TO W MADISON" | 45 truncated spend records await recovery method |
| CCD→NAVD88 vertical datum calibration | [ ] | Survey constant validation | Subsurface depths require licensed surveyor confirmation |

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

## TASKS.md — Living Checklist Conventions

**TASKS.md is your working checklist.** Keep it current as you work, not just at the end.

**Status markers (use exactly one per task):**
- `[ ]` — Not started (ready to build)
- `[~]` — In progress (exactly one task at a time in this state)
- `[x]` — Done (tests pass, committed to git, decision logged if applicable)

**Update markers AS you work:**
- When you start a task: change `[ ]` → `[~]`
- When you complete it: change `[~]` → `[x]`
- Do NOT wait until the end of your turn to update status

**Add newly discovered work immediately:**
- Found a bug? Add it to TASKS.md as `[ ]` under the relevant phase
- Need refactoring? Add it as `[ ]` under Cross-cutting
- Do NOT accumulate work in your head — log it instantly

**For multi-step tasks, use sub-checklists:**
- Large tasks (geocode cascade, extraction chains) have multiple stages
- Break into numbered sub-items: `- [x] Stage 1`, `- [ ] Stage 2`, etc.
- Tick each sub-item as you complete it
- Example: geocode cascade has 8 stages (cache, address-point, centerline, intersection, segment, gazetteer, external, LLM-select) = 8 checkboxes

**Never edit history.** TASKS.md records what's true now, not what was true before.

## Commands you will use constantly
- `uv run holos --help`  ·  `uv run pytest golden/ -x`  ·  `docker compose up -d hub`
- `holos validate all --changeset <id>` before requesting any review.
- **Update `TASKS.md`** with task status as you work (repo is now the source of truth for build tasks).
- **Append to `decisions.md`** whenever a decision is made (append-only; humans mirror to Notion if needed).

## Style
Python 3.12, typed, ruff. SQL migrations in `/db/migrations`. Small PRs.
