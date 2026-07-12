---
description: Push the current work state to Notion — Task Board, Decisions Log, and trackers — in one consistent routine.
---

Update Notion to reflect the work just completed, using the Notion MCP tools. Search before writing so you update existing rows instead of duplicating them.

**1. Task Board** (data source `16156204-e1bb-4d13-95fc-099bebf685c0`)
- Set any task you completed this session to **Status = Done**.
- Set the task you are actively working on to **In progress** and set **Owner**.
- Add any newly discovered work as new rows (fill Phase, Component, Status = Not started, a one-line Notes).

**2. Decisions** (page `39bf6ea8-4e41-81c5-83b8-c0400317b9b6`)
- For every decision recorded in `/decisions.md` since the last sync that is not yet in Notion, append it to the Decisions Log with `insert_content` at the **end** (append-only — never edit existing entries). Use the format: `### YYYY-MM-DD — <decision>` then a one-line rationale.

**3. Trackers** (update only what changed)
- Data & Access Tracker (`e5b40003-cec0-48fe-a50e-b85b21fe34ce`): update the **Status** of any source you acquired/ingested (e.g., "To ingest" → "In hand").
- Outreach & Partnerships (`eb6346d2-5823-4651-8699-31574791732b`): update Status / Next step for any contact that changed.
- Meetings & Notes (`66b5fd89-8396-4afa-9e1f-03063b9aecd5`): if this session was a call or produced a working note, add a row.

**4. Guardrails**
- Do NOT write secrets to Notion (they live in `.env` / a password manager; Notion Admin holds references only).
- Respect source of truth: Notion owns trackers/planning; the repo owns code/config/decisions.md. You are pushing the repo's decisions *up* to the Notion mirror, not editing Notion as the original for code.

**5. Write the sync marker and report**
- Run: `git rev-parse HEAD > .claude/.notion-synced 2>/dev/null || true`
- Report a one-line summary of exactly what you changed in Notion.
