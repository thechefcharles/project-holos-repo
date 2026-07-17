---
name: promote-to-core
description: Promotion workflow—validate staging, run gates, load to core schema, audit trail
---

# /promote-to-core — Safe promotion to production

Runs the controlled promotion pipeline: `staging` → `core` (read-only), with mandatory validation gates and audit logging.

## Workflow

1. **Validate staging** — run `/validate-production`
2. **Check gates** — verify all blocking human gates are resolved
3. **Snapshot staging** — create backup (if reversible)
4. **Promote data** — `holos load promote --changeset <id> --schema core`
5. **Audit trail** — log to `ops.audit_log` (changeset, timestamp, user, row counts, before/after)
6. **Publish changes** — update `config/sources.yaml` + `decisions.md`

## Usage

```bash
/promote-to-core <changeset-id> [--force-gates]
```

**Examples:**
```bash
# Standard promotion (gates enforced)
/promote-to-core 2026-07-17-chicago-2017

# Override gates (requires approval + reason)
/promote-to-core 2026-07-17-chicago-2017 --force-gates "Legal clearance obtained"
```

## When to use

- After validation passes
- When staging work is complete and ready for production
- At end of sprint (weekly promotion cycle)

## Safety guardrails

- ✓ Never write `core` schema directly (only via `holos load promote`)
- ✓ Blocking gates enforced (escalated records, missing provenance, RLS violations)
- ✓ Changeset ID logged (audit trail, reversibility)
- ✓ Before/after row counts compared (detect silent data loss)
- ✗ Force gates only with explicit approval + reason

## Output

```
✓ Promoted: 1784 spend records, 1030 geocoded (57.7%), 754 escalated
✓ Audit trail: ops.audit_log entry #4521
✓ Changes logged: decisions.md + config/sources.yaml
✓ Ready for map UI refresh
```

---

**See also:** CLAUDE.md rule #2 (never write core directly), `/docs/runbook.md` (promotion gates)
