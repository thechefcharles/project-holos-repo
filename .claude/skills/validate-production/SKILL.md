---
name: validate-production
description: Run all validation gates before promotion—golden tests, changeset checks, geometry validation
---

# /validate-production — Full validation pipeline

Runs the complete validation suite to verify that staging work is ready for promotion to `core`.

## Steps

1. **Run golden tests** — verify all extraction, geocoding, and loading logic
   ```bash
   uv run pytest golden/ -x
   ```

2. **Run holos validate all** — check geometry integrity, missing provenance, RLS policies
   ```bash
   holos validate all --changeset <id>
   ```

3. **Run database consistency checks** — verify foreign keys, CRS consistency, QL levels
   ```bash
   psql -c "SELECT * FROM ops.validation_report WHERE status != 'pass'"
   ```

4. **Report results** — summarize pass/fail, flags for human review

## Usage

```bash
/validate-production <changeset-id>
```

**Example:**
```bash
/validate-production 2026-07-17-chicago-2017
```

## When to use

- Before committing geocoding or extraction work
- Before running `holos load promote`
- To audit staging data for data-quality issues
- As the final gate before production deployment

## Output

- ✓ All tests pass
- ⚠ Warnings (missing metadata, ambiguous geometries, escalated addresses)
- ✗ Failures (blocked until resolved)

---

**See also:** `decisions.md` (validation decisions), `/docs/runbook.md` (gate definitions)
