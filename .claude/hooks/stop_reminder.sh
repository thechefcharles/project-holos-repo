#!/usr/bin/env bash
# Project Holos — Stop hook.
# Fires when Claude Code tries to end its turn. Reminds about Definition of Done.
# Non-blocking: prints the checklist as a reminder, does not force you to complete it.

# --- Definition of Done reminder (default) ---
cat <<'EOF'
[Project Holos — before you finish]
Definition of Done checklist:
1. [ ] Tests pass (if applicable).
2. [ ] Work is committed to git.
3. [ ] TASKS.md updated:
   - Check off completed tasks with [x]
   - Mark active task with [~] (exactly one)
   - Add newly discovered work as [ ]
   - Update sub-task progress for multi-step tasks
4. [ ] Any decision appended to /decisions.md (append-only; never edit history).
5. (Optional) Notion updates: humans can pull from repo if needed for narrative/legal context.

TASKS.md and decisions.md are the source of truth for build work. Update them as you go,
not just at the end.
EOF
