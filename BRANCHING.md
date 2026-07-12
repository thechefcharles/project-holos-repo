# Project Holos — Branching Strategy

## Branch Structure

```
main                    ← Go-live (disabled for now)
  └─ dev               ← Production (Vercel deploys here)
     ├─ feature/a1-reference-data-load
     ├─ feature/geocode-cascade
     ├─ feature/ui-review-panel
     └─ ...
```

## Branch Naming Convention

**Feature branches** follow this pattern:

```
feature/<component>-<short-description>
```

### Examples

| Branch | Purpose |
|--------|---------|
| `feature/a1-reference-data-load` | Load R1–R5 reference layers (Phase 1B) |
| `feature/geocode-cascade-stages` | Implement stages 1–5 (Phase 1B) |
| `feature/verifier-golden-test` | Golden set verification (Phase 1B) |
| `feature/ui-review-panel` | Review UI for geocoding mismatches (Phase 2) |
| `feature/b1-vector-extraction` | Vector PDF extraction (Phase 2) |
| `feature/subsurface-ql-discipline` | QL-A/QL-B validation (Phase 2+) |

### Component Prefixes

- `a1-` : Chain A1 (spending extraction)
- `b1-`, `b2-`, `b3-` : Chains B1–B3 (subsurface)
- `ui-` : User-facing interfaces
- `db-` : Database schema/migrations
- `cli-` : CLI tools
- `test-` : Test infrastructure
- `doc-` : Documentation
- `ops-` : Operations/CI-CD

## Workflow

### Starting a Feature

```bash
git checkout dev
git pull origin dev
git checkout -b feature/<component>-<description>
```

### Committing

- Small, atomic commits (one logical change per commit)
- Commit message: `<type>: <description>` (e.g., `feat: implement centerline interpolation`)
- Every commit must pass tests locally before pushing

### Deploying a Feature (Push to dev → Vercel production)

**When the user says "deploy":**

1. Commit all changes locally
2. Push feature branch to GitHub: `git push origin feature/...`
3. Create a pull request (feature → dev) for review
4. Merge PR once approved
5. GitHub automatically triggers Vercel deployment from dev

Or, if ready to merge dev to main:

```bash
git checkout main
git pull origin main
git merge dev
git push origin main
```

Then Vercel will switch to main deployment (one-time config change in Vercel UI).

## Protection Rules

**main:** Protected branch
- Requires PR review (Phase 2+)
- Requires CI checks to pass
- No direct pushes

**dev:** Standard branch
- PR reviews recommended (keep quality high)
- CI checks required
- Auto-deploys to Vercel on merge

**feature/\*:** Developer branches
- No protection
- Pushed to GitHub for backup
- Deleted after merge to dev

## Summary

| Action | Branch | Command |
|--------|--------|---------|
| Start work | `feature/...` | `git checkout -b feature/...` |
| Deploy (push to Vercel) | `dev` | `git push origin feature/...; gh pr create` |
| Go live | `main` | Merge dev → main (one-time) |

---

## Vercel Configuration

**Current setup:**
- Production branch: dev
- Preview deployments: All (feature branches get preview URLs)
- Main branch: Disabled

**To enable at go-live:**
1. Change production branch to main
2. Disable auto-deploys from dev
3. Keep dev for staging

---

*Last updated: 2026-07-12*
