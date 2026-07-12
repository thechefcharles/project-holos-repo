#!/usr/bin/env bash
# Project Holos — SessionStart hook.
# Injects current-state reminders so the agent starts from Notion, not stale assumptions.
# stdout from a SessionStart hook is added to the session context.

cat <<'EOF'
[Project Holos — session start]
Before starting work:
1. Query the Notion Task Board (data source 16156204-e1bb-4d13-95fc-099bebf685c0)
   for tasks with Status "Not started" / "In progress"; prioritize "This week", then "Phase 1".
2. Read the latest entries in /decisions.md (and, if relevant, the Notion Decisions Log)
   so you do not act on stale assumptions.
3. Source of truth: the REPO owns code / config / CLAUDE.md / decisions.md; NOTION owns
   trackers / planning / the human-facing decisions log. Never edit a mirror as if it were
   the original. If they disagree, the owner side wins — fix the mirror and note it in /decisions.md.
EOF
