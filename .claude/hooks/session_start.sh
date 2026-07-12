#!/usr/bin/env bash
# Project Holos — SessionStart hook.
# Injects current-state reminders so the agent starts from repo, not stale assumptions.
# stdout from a SessionStart hook is added to the session context.

cat <<'EOF'
[Project Holos — session start]
Before starting work (read these in order — 2 minutes total):
1. **TASKS.md** — open tasks by phase (prioritize "This week", then "Phase 1").
   Status markers: [ ] not started, [~] in progress, [x] done. Update AS you work.
2. **decisions.md** — latest 5 entries. Understand the current assumptions.
3. **.claude/agents/*.md** — current agent definitions (if you're calling an agent).

Source of truth: the REPO owns build tasks (TASKS.md), decisions (decisions.md), data
registry (config/sources.yaml), and agent defs. NOTION owns human/business layer only
(pitch, legal, financials, meetings, admin). Never edit a mirror as if it were the
original — the owner side is authoritative.
EOF
