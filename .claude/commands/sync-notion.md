---
name: sync-notion
description: Sync repo work to Notion (Task Board, Decisions Log, trackers) — part of Definition of Done
---

# /sync-notion — Sync repo state to Notion

**Purpose:** Automate the Definition of Done by syncing git commits, decisions.md, and task status to Notion.

**When to run:** At the end of every session or after completing a task.

**Requirements:**
- NOTION_TOKEN in .env (loaded via .mcp.json)
- decisions.md up-to-date (repo owns this; Notion mirrors it)

---

## Workflow

### 1. Query the Task Board

Find all Phase 1A/1B tasks matching the current work.

**Data source:** `16156204-e1bb-4d13-95fc-099bebf685c0`

Use `notion-query-data-sources` (SQL mode):
```sql
SELECT * FROM "collection://16156204-e1bb-4d13-95fc-099bebf685c0"
WHERE (Status = 'Not started' OR Status = 'In progress')
AND (Phase LIKE '%Phase 1%' OR Title LIKE '%setup%')
LIMIT 50
```

Search for tasks like:
- "Phase 1A infrastructure" → Set to **Done**
- "Phase 1B reference data" → Set to **In progress**
- "Notion MCP setup" → Set to **Done**
- "GitHub & Vercel setup" → Set to **Done**

### 2. Update Task Board Rows

For each matching task, use `notion-update-page` (command: "update_properties"):

```json
{
  "page_id": "<task_id>",
  "properties": {
    "Status": "Done",
    "Owner": "Claude Code",
    "Last updated": "2026-07-12"
  }
}
```

**Critical:** Search first to get the actual page_id; don't guess.

### 3. Append New Decisions to Decisions Log

Read `/decisions.md` and compare against last sync marker (`.claude/.notion-synced`).

Extract all new decisions (those with dates after the synced commit).

For each new decision, use `notion-update-page` (command: "insert_content"):

```json
{
  "page_id": "39bf6ea8-4e41-81c5-83b8-c0400317b9b6",
  "command": "insert_content",
  "content": "### 2026-07-12 — Phase 1 infrastructure: agents, not scripts\nFive pipeline agents with explicit output contracts; human gates in job queue.",
  "position": {"type": "end"}
}
```

**Append-only rule:** Never edit or delete existing Notion entries; only add new ones.

### 4. Update Trackers (if applicable)

Query and update:

- **Data & Access Tracker** (`e5b40003-cec0-48fe-a50e-b85b21fe34ce`):
  - If you ingested a source, find its row and set Status = "In hand" or "Loaded"
  
- **Outreach & Partnerships** (`eb6346d2-5823-4651-8699-31574791732b`):
  - Update if you contacted any partners
  
- **Meetings & Notes** (`66b5fd89-8396-4afa-9e1f-03063b9aecd5`):
  - Add a row if this session was a call or working session

### 5. Write Sync Marker

```bash
git rev-parse HEAD > .claude/.notion-synced
git add .claude/.notion-synced
git commit -m "Sync: Notion updated ($(git rev-parse --short HEAD))"
git push origin dev
```

### 6. Report Summary

Print one-line summary:
```
✓ Notion synced: 3 tasks → Done, 4 decisions appended, chicago_centerlines → In hand
```

---

## MCP Tool Invocations

### Get Current Commit

```bash
COMMIT_HASH=$(git rev-parse HEAD)
echo "Syncing commit: $COMMIT_HASH"
```

### Get Last Synced Commit

```bash
if [ -f .claude/.notion-synced ]; then
  LAST_SYNCED=$(cat .claude/.notion-synced)
else
  LAST_SYNCED="none"
fi
echo "Last synced: $LAST_SYNCED"
```

### Query Task Board (SQL)

Use `notion-query-data-sources` with:
- mode: "sql"
- data_source_urls: ["collection://16156204-e1bb-4d13-95fc-099bebf685c0"]
- query: SELECT with Status and Phase filters

### Update Task Status

Use `notion-update-page` with:
- page_id: <task_id_from_query>
- command: "update_properties"
- properties: {Status, Owner, Last updated}

### Append to Decisions Log

Use `notion-update-page` with:
- page_id: "39bf6ea8-4e41-81c5-83b8-c0400317b9b6"
- command: "insert_content"
- content: formatted markdown
- position: {type: "end"}

---

## Guardrails

1. **Never write secrets to Notion** — credentials in .env only
2. **Search before writing** — query to find rows; no duplicate creation
3. **Append-only** — Decisions Log and trackers never edited, only added to
4. **Commit the sync marker** — prevents re-syncing same work
5. **Respect source of truth** — Notion mirrors repo; repo is original

---

## Example

**Session:** Load reference data (Phase 1B start)

**Before /sync-notion:**
- .claude/.notion-synced: c83db3e
- /decisions.md: new entries added
- git log: 3 new commits (db-, refdata commits)
- Task Board: "Phase 1B reference data" = "Not started"

**After /sync-notion:**
- Task Board: "Phase 1B reference data" = "In progress", Owner = "Claude Code"
- Decisions Log: 3 new decision entries appended
- Data & Access Tracker: chicago_centerlines, chicago_wards = "In hand"
- .claude/.notion-synced: latest commit hash
- Report: ✓ Notion synced: 1 task → In progress, 3 decisions appended, 2 sources → In hand

---

*Last updated: 2026-07-12*
