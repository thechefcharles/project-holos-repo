# VibeCode Project Setup Template

A blueprint for setting up ambitious software projects with Claude Code, based on **Project Holos**.

This guide covers the governance, infrastructure, and workflow patterns that made Project Holos development smooth and maintainable.

---

## Part 1: Governance & Philosophy

### 1.1 Create CLAUDE.md (The Constitution)

Every project needs non-negotiable rules. CLAUDE.md lives in the repo root and is the **source of truth** for how work gets done.

**What to include:**

```markdown
# [Project Name] — Agent Constitution

Pitch (1 paragraph): What does this project do?

## Non-negotiable rules
1. [Rule about decisions vs. execution]
2. [Rule about data integrity]
3. [Rule about legal/compliance]
4. [Rule about schema/versioning]
5. [... more rules specific to your domain]

## Source of truth model
- **Repo owns:** code, config, CLAUDE.md, decisions.md
- **[External system] owns:** planning, trackers, human decisions
- Nothing owned by both; non-owner side is a labeled mirror.

## Definition of Done
A task is complete only when ALL are true:
1. Tests pass
2. Work is committed to git
3. Notion is updated (if using Notion)

## Commands you will use constantly
[List of key CLI commands or workflows]
```

**Why this matters:** It prevents drift and keeps humans and agents aligned on what matters. See Project Holos `CLAUDE.md` for a full example.

### 1.2 Create decisions.md (Audit Trail)

Append-only log of every decision that a future teammate needs to understand "why is it this way?"

```markdown
# [Project Name] — Decisions Log

Append-only. Every decision a future teammate or agent needs. Newest at the bottom. Never edit history.

---

### [DATE] — [Decision Title]
[One-sentence summary of what was decided and why.]

### [DATE] — [Another Decision]
[Rationale.]
```

**Why this matters:** Decisions get forgotten; this becomes the system of record. Mirror to Notion if using it.

---

## Part 2: Notion Connection

### 2.1 Create .mcp.json

Wire Claude Code to Notion via MCP (Model Context Protocol).

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["@anthropic-ai/cloudflare-mcp-server@latest", "notion"],
      "env": {
        "NOTION_TOKEN": "${NOTION_TOKEN}"
      }
    }
  }
}
```

**Why this matters:** Enables Claude to read/write Notion without manual sync. See `.mcp.json` in Project Holos.

### 2.2 Create .env (Secrets)

```bash
NOTION_TOKEN=ntn_xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
[OTHER_SECRETS_HERE]
```

**Add to .gitignore:**
```
.env
.env.local
```

**Why this matters:** Secrets never commit to git. Notion MCP reads the token from .env.

### 2.3 Create /sync-notion Workflow

Document how Notion stays in sync with the repo (Definition of Done #3).

```markdown
# /sync-notion — Sync repo state to Notion

## Workflow
1. Query [Notion tracker] for tasks matching this work
2. Update Status, Owner, timestamp
3. Append new decisions to [Notion Decisions Log] (append-only)
4. Update any other trackers ([Data & Access], [Outreach], etc.)
5. Write sync marker (.claude/.notion-synced) and commit

## Tool invocations
- Use notion-query-data-sources (SQL mode) to find tasks
- Use notion-update-page to update properties and append content
- Never edit existing entries; only append
```

Save as `.claude/commands/sync-notion.md` and invoke with `/sync-notion` at end of session.

**Why this matters:** Notion stays current without manual work. Prevents duplicate effort.

---

## Part 3: GitHub & Vercel

### 3.1 Initialize Git & Push to GitHub

```bash
git init
git add -A
git commit -m "Initial commit: [project] with constitution, docs, config"
git remote add origin https://github.com/[user]/[repo].git
git branch -M main
git push -u origin main
```

### 3.2 Create dev Branch

```bash
git checkout -b dev
git push -u origin dev
```

**Why two branches?**
- `dev` = current production (Vercel deploys here during development)
- `main` = go-live branch (frozen until ready)

### 3.3 Connect to Vercel

```bash
vercel link --yes
```

Configure in Vercel UI:
- Production branch: `dev` (for now)
- Preview deployments: All
- Main: Disabled

**Why this matters:** Automatic deployments from dev; safe until go-live.

---

## Part 4: Branching Strategy

### 4.1 Create BRANCHING.md

Document how to name and use branches:

```markdown
# Branching Strategy

## Pattern
feature/<component>-<short-description>

## Examples
- feature/auth-setup
- feature/database-schema
- feature/ui-dashboard
- feature/api-endpoints

## Workflow
1. Create feature branch: git checkout -b feature/...
2. Work locally
3. Commit: git commit -m "..."
4. Push to GitHub: git push origin feature/...
5. Create PR (feature → dev)
6. Merge PR once approved
7. Vercel auto-deploys from dev
```

**Why this matters:** Consistent naming makes logs readable and makes it clear what each branch does.

### 4.2 Save Memory: What "deploy" Means

In your session memory (`/Users/admin/.claude/projects/.../memory/feedback_deploy_workflow.md`):

```markdown
---
name: deploy_means_push_to_dev
description: "deploy" command means push changes to dev branch and Vercel production
metadata:
  type: feedback
---

When the user says "deploy", it means:
1. Ensure all changes are committed locally
2. Push to dev branch (create/merge PR if on feature branch)
3. Vercel automatically deploys from dev to production

Related: BRANCHING.md for full workflow.
```

**Why this matters:** Clarifies intention; prevents accidental main-branch pushes.

---

## Part 5: Infrastructure as Code

### 5.1 docker-compose.yml (If using containers)

```yaml
version: '3.8'
services:
  [your-database]:
    image: [image:version]
    ports:
      - "5432:5432"
    volumes:
      - [volume_name]:/data
    environment:
      [VARS]: [values]
    healthcheck:
      test: ["CMD", "[health_check_command]"]
```

**Why this matters:** Reproducible local dev environment; everyone gets the same setup.

### 5.2 Schema Files (Database Migrations)

```sql
-- db/migrations/001-init-schema.sql
-- Initialize all tables, indexes, constraints

CREATE TABLE [table] (
  id UUID PRIMARY KEY,
  [columns],
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_[table]_[column] ON [table]([column]);
```

**Why this matters:** Schema is versioned in git; migrations are deterministic.

### 5.3 pyproject.toml (Python) / package.json (Node) / etc.

Lock all dependencies explicitly:

```toml
[project]
name = "my-project"
version = "0.1.0"
dependencies = [
  "requests>=2.31.0",
  "pydantic>=2.0",
  # ... more deps
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Why this matters:** Reproducible builds; no "works on my machine" surprises.

---

## Part 6: CLI & Deterministic Tools

### 6.1 Separate Agents from Tools

**Agents:** Make decisions (Claude)
- What data to extract?
- Is this geocoding result good?
- Should this be escalated to human review?

**Tools:** Execute decisions (CLI commands, durable)
- `holos harvest` — download data
- `holos extract` — parse documents
- `holos validate` — check constraints

**Why this matters:** Agents are stateless; tools are reproducible. A tool run 1 year ago should give the same result today.

### 6.2 Define Tool Contracts

Every tool has a standard output format:

```json
{
  "job_id": "uuid",
  "status": "success|failed",
  "artifacts": [{path, size, checksum}],
  "metrics": {count, rate, etc.},
  "flags": ["warning1", "warning2"],
  "needs_human": false,
  "reasons": ["explanation"]
}
```

Schema: `schemas/agent_output.schema.json`

**Why this matters:** Tools are composable; downstream agents know what to expect.

### 6.3 Create CLI Entry Point

```python
# my_tools/cli.py
import typer
from my_tools.harvest import app as harvest_app
from my_tools.extract import app as extract_app

app = typer.Typer()
app.add_typer(harvest_app, name="harvest")
app.add_typer(extract_app, name="extract")

if __name__ == "__main__":
    app()
```

**Why this matters:** Single entry point for all operations; consistent UX.

---

## Part 7: Testing & Golden Fixtures

### 7.1 Create Golden Fixtures

Known-good data for regression testing:

```json
// golden/test_fixtures.json
[
  {
    "id": "golden_001",
    "input": "...",
    "expected_output": "...",
    "expected_confidence": 0.95,
    "description": "..."
  }
]
```

**Why this matters:** Calibrates your system against a ground-truth benchmark (e.g., Ward Wise data).

### 7.2 Create Test Suite

```python
# tests/test_golden.py
def test_golden_set():
    """Verify results match golden fixtures."""
    golden = load_golden()
    for fixture in golden:
        result = my_tool(fixture['input'])
        assert result['output'] == fixture['expected_output']
        assert result['confidence'] >= fixture['expected_confidence']
```

**Why this matters:** Tests catch regressions before deployment.

---

## Part 8: Configuration & Secrets

### 8.1 config/ Directory

All non-secret configuration:

```yaml
# config/sources.yaml
sources:
  my_data_api:
    url: https://api.example.com/v1/
    frequency_days: 7
    description: "..."
    
# config/thresholds.yaml
validation:
  confidence_threshold: 0.85
  retry_count: 3
```

**Why this matters:** Config changes don't require code changes; can be updated in prod.

### 8.2 .env (Secrets)

```bash
# .env (git-ignored)
API_KEY_MY_SERVICE=secret_key_here
DATABASE_PASSWORD=secret_here
NOTION_TOKEN=secret_here
```

**.gitignore:**
```
.env
.env.local
secrets/
```

**Why this matters:** Secrets never commit; no accidental leaks.

---

## Part 9: Session Workflow

This is how a typical VibeCode session should flow:

### Start of Session
1. Pull latest from dev: `git pull origin dev`
2. Read `/decisions.md` (latest decisions)
3. Check Notion Task Board for open items

### During Session
1. Create feature branch: `git checkout -b feature/...`
2. Make changes, commit frequently
3. Run tests locally: `pytest golden/ -x`
4. Push feature branch: `git push origin feature/...`

### End of Session (Definition of Done)
1. ✓ Tests pass: `pytest golden/ -x`
2. ✓ Commit all changes: `git commit`
3. ✓ Run `/sync-notion` to update Notion
4. ✓ Merge PR (feature → dev)
5. ✓ Vercel auto-deploys
6. ✓ Report: "✓ Deployed [feature] to dev branch"

---

## Part 10: Key Files to Create Upfront

```
[project-repo]/
├── CLAUDE.md                      # Non-negotiable rules
├── decisions.md                   # Append-only decision log
├── BRANCHING.md                   # Branching strategy
├── .mcp.json                      # Notion MCP config
├── .env                           # Secrets (git-ignored)
├── .gitignore                     # Ignore secrets, temp files
├── vercel.json                    # Vercel config
├── docker-compose.yml             # Local dev environment
├── pyproject.toml                 # Python project config
├── config/
│   ├── sources.yaml               # Data sources
│   ├── thresholds.yaml            # Validation thresholds
│   └── vocabularies.yaml          # Canonical terms
├── schemas/
│   └── agent_output.schema.json   # Tool output contract
├── db/
│   └── init/
│       └── 001-init-schema.sql    # Database schema
├── .claude/
│   ├── agents/
│   │   ├── harvester.md           # Agent: discovers data
│   │   ├── extractor.md           # Agent: parses documents
│   │   ├── validator.md           # Agent: validates
│   │   └── ... more agents
│   ├── commands/
│   │   └── sync-notion.md         # /sync-notion workflow
│   └── .notion-synced             # Sync marker (git-tracked)
├── tests/
│   ├── test_setup.py              # Infrastructure tests
│   ├── test_golden.py             # Golden fixture tests
│   └── test_e2e.py                # End-to-end tests
├── golden/
│   └── fixtures.json              # Golden test data
└── [my_tools]/
    ├── __init__.py
    ├── cli.py                     # CLI entry point
    └── [submodules]/              # harvest, extract, validate, etc.
```

---

## Part 11: First Commit Message Template

```
Initial commit: [Project Name] with governance, infrastructure, and tools

- CLAUDE.md: non-negotiable rules and constitution
- decisions.md: append-only decision log
- .mcp.json: Notion MCP wired to .env
- docker-compose.yml: local dev environment
- db/init/: database schema (migrations)
- config/: sources, thresholds, vocabularies
- schemas/: tool output contracts
- .claude/agents/: 5+ agent definitions
- .claude/commands/sync-notion.md: Notion sync workflow
- CLI: [harvest, extract, validate, load] commands
- tests/: golden fixtures, infrastructure tests
- vercel.json: deployment config (dev branch only)
- BRANCHING.md: feature branch naming and workflow

Ready for: Phase 1B development.

Co-Authored-By: Claude Code <noreply@anthropic.com>
```

---

## Part 12: Quick Checklist for New Projects

Before your first commit:

- [ ] Create CLAUDE.md with non-negotiable rules
- [ ] Create decisions.md (append-only template)
- [ ] Create .env and .gitignore (no secrets in git)
- [ ] Create .mcp.json if using Notion
- [ ] Create docker-compose.yml if using containers
- [ ] Create db/migrations/ if using database
- [ ] Create config/ directory with YAML files
- [ ] Create schemas/ directory with JSON schemas
- [ ] Create .claude/agents/ with agent definitions
- [ ] Create .claude/commands/sync-notion.md
- [ ] Create CLI entry point
- [ ] Create tests/ with golden fixtures
- [ ] Create vercel.json (or equivalent deployment config)
- [ ] Create BRANCHING.md
- [ ] Create README.md (what this project does)
- [ ] `git init` and first commit
- [ ] Push to GitHub (dev branch)
- [ ] Connect to Vercel (dev branch production)

---

## Part 13: When to Use This Template

**Use this template for:**
- Data pipelines (like Project Holos)
- Multi-stage workflows (extract → transform → validate → load)
- Projects requiring audit trails (decisions.md)
- Projects with human review gates (Notion + ops.jobs)
- Projects deploying continuously (Vercel from dev)
- Projects with strong schema discipline

**Don't use this template for:**
- Simple CRUD apps (overengineered)
- Throwaway prototypes
- Single-page apps without workflow complexity

---

## Part 14: Extending This Template

Once you've set up the basics, you'll likely add:

### Observability
- Logging configuration (.claude/logging.yaml)
- Metrics collection (ops.run_metrics table, if using)
- Alerts (Slack, email) on job failures

### CI/CD
- GitHub Actions workflows (.github/workflows/)
- Pre-commit hooks (Ruff, Black, type checking)
- Automated testing on every PR

### Collaboration
- Code review guidelines (CONTRIBUTING.md)
- Incident response playbook (ops/runbook.md)
- On-call rotation (if deployed to production)

### Documentation
- User guide (docs/user-guide.md)
- API reference (docs/api.md)
- Troubleshooting (docs/troubleshooting.md)

---

## Summary

This template gives you:

1. **Governance:** CLAUDE.md + decisions.md (single source of truth)
2. **Autonomy:** Agents decide, tools execute (durable, reproducible)
3. **Sync:** Notion MCP + /sync-notion (keeps planning and code aligned)
4. **Git:** Clean commits, branching strategy, deploy from dev
5. **Testing:** Golden fixtures, regression tests, benchmark calibration
6. **Infrastructure:** Database schema, CLI tools, tool contracts

The result: A project that stays coherent as it grows, with humans and agents working together smoothly.

---

**Version:** 1.0  
**Based on:** Project Holos (Phase 1A)  
**Last updated:** 2026-07-12

Use this as a starting point for your next VibeCode project. Good luck! 🚀
