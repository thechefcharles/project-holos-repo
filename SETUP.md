# Project Holos — Repo + Claude Code + Notion setup

This starter wires Claude Code to build the project **and** keep Notion current. Drop
these files at the root of your new repo, then do the manual steps below.

## What's in this starter
```
CLAUDE.md                     # the constitution + source-of-truth + Notion-sync rules
decisions.md                  # append-only decisions log (repo = source of truth)
.gitignore                    # keeps secrets and large data out of git
config/sources.yaml           # machine-readable dataset registry (repo owns the IDs)
docs/                         # put master-brief.md, tech-spec.md, runbook.md here
.claude/
  settings.json               # wires the hooks
  hooks/session_start.sh      # pulls current state from Notion at session start
  hooks/stop_reminder.sh      # reminds to sync Notion before finishing (every time)
  commands/sync-notion.md     # /sync-notion — one-step Notion update
```

## Manual steps (things only you can do)

1. **Create the repo** on GitHub, clone it, open in Cursor. Copy this starter into it.
2. **Make the hook scripts executable:** `chmod +x .claude/hooks/*.sh`
3. **Add the reference docs** to `docs/`: export the Master Brief, Technical Build Spec,
   and Geolocation Runbook from Notion as `docs/master-brief.md`, `docs/tech-spec.md`,
   `docs/runbook.md` (CLAUDE.md tells the agents to read these).
4. **Connect the Notion MCP to Claude Code** (this is what lets it read/write Notion):
   - In Notion: create an internal integration and copy its token.
   - **Share the Project Holos page with that integration** (so it has access to the
     page and all sub-pages/databases).
   - Add the server to Claude Code, e.g. `claude mcp add notion` (or add it to the
     project's `.mcp.json`), with the token in the environment — **not** committed.
   - [[VERIFY exact command/config in current Claude Code docs — the MCP setup surface moves.]]
5. **Create `.env`** (git-ignored) with your secrets — Anthropic API key, Supabase
   connection string, etc. Keep the real values in a password manager; put only
   references in the Notion Admin folder.
6. **Verify the hook schema** against https://docs.claude.com/en/docs/claude-code/hooks —
   event names and output format can change. Test that `session_start.sh` fires on a new
   session and `stop_reminder.sh` fires when Claude finishes.
7. (Optional) **Enable blocking mode** in `stop_reminder.sh` once your Notion MCP wiring
   is solid, if you want Claude to *refuse to stop* until it has run `/sync-notion`.
8. **First run:** open Claude Code, let it read `CLAUDE.md` + `docs/tech-spec.md`, then
   start with the "This week" tasks on the Notion Task Board.

## The daily loop (what happens automatically once set up)
- **Session start** → hook reminds Claude to pull open tasks + recent decisions from Notion.
- **You pick a task** → Claude marks it In progress in Notion, does the work, commits.
- **Before finishing** → Stop hook reminds; Claude runs `/sync-notion` to set the task Done,
  append decisions, and update trackers.
- Repeat.
