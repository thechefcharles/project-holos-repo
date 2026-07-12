#!/usr/bin/env bash
# Project Holos — Stop hook.
# Fires when Claude Code tries to end its turn. NON-BLOCKING reminder by default:
# it prints the Definition-of-Done checklist every time so Notion updates are never forgotten.
#
# OPTIONAL BLOCKING MODE (stronger): uncomment the block below to refuse stopping when work
# was committed since the last /sync-notion. /sync-notion writes .claude/.notion-synced.
# Blocking mode can loop if the agent cannot sync — enable only once your MCP wiring is solid.

# --- Non-blocking reminder (default) ---
cat <<'EOF'
[Project Holos — before you finish]
Definition of Done includes Notion. If you completed or advanced any task:
- Task Board: set finished tasks to "Done"; the active one to "In progress" (with Owner).
- Decisions: append new decisions to /decisions.md AND mirror them to the Notion Decisions Log.
- Trackers: update any affected row (Data & Access, Outreach, Meetings).
Run  /sync-notion  to do all of this in one step.
EOF

# --- Optional blocking mode (uncomment to enable) ---
# HEAD_NOW="$(git rev-parse HEAD 2>/dev/null || echo none)"
# HEAD_SYNCED="$(cat .claude/.notion-synced 2>/dev/null || echo none)"
# if [ "$HEAD_NOW" != "$HEAD_SYNCED" ] && [ "$HEAD_NOW" != "none" ]; then
#   echo '{"decision":"block","reason":"Work was committed since the last Notion sync. Run /sync-notion (updates the Task Board, Decisions Log, and trackers) before finishing."}'
# fi
