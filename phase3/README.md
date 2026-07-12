# Phase 3: Subsurface Extraction (Frozen)

This folder contains **Phase 3 work built ahead of schedule during Phase 1**.

## Status
- **Built:** B1, B2, B3 extraction chains + subsurface review infrastructure
- **Frozen:** Until Phase 1 (civic spending map) is complete
- **Location:** `/phase3/` (isolated from Phase 1 tree)

## What's here

### Extraction chains
- `holos_tools/b1_vector.py` — CAD-exported vector PDF extraction
- `holos_tools/b2_raster.py` — Raster plate (Sanborn maps, utility blueprints) extraction
- `holos_tools/b3_native_cad.py` — Native CAD (GeoJSON, Shapefile, DWG, DGN) extraction

### Review infrastructure
- `holos_tools/review/` — Human-in-the-loop promotion workflow (approve/reject/escalate)

### Database schemas
- `db/init/002-subsurface-schema.sql` — Subsurface features, GPR/EM surveys, QL discipline
- `db/init/003-review-schema.sql` — Review audit log and analytics views

### Agent definitions
- `.claude/agents/b1-vector-extractor.md`
- `.claude/agents/b2-raster-extractor.md`
- `.claude/agents/b3-native-cad-extractor.md`
- `.claude/agents/subsurface-reviewer.md`

### Tests
- `tests/` — Golden fixtures and pytest suites for B1/B2/B3

## Why frozen

Phase 1 (civic spending map pipeline) is the foundation. Until it's complete:
1. There's no tested ecosystem to feed Phase 3 data into
2. Confidence scoring is uncalibrated (no Phase 1 data to validate against)
3. Building Phase 3 before Phase 1 ships is inverting priorities

## Reactivation

When Phase 1 is complete (spending map shipped, Ward Wise ≥90% benchmark hit):
1. Move B1/B2/B3 extraction back to main `holos_tools/extract/`
2. Move subsurface schemas to `db/init/`
3. Re-wire to CLI
4. Re-integrate review agent
5. Test against real Chicago data (Sanborn maps, water dept CAD, utility records)

## Decisions recorded

- 2026-07-11 — Phase 2 B1 (Vector PDFs) extraction
- 2026-07-11 — Phase 2 B2 (Raster plates) extraction
- 2026-07-11 — Phase 2 B3 (Native CAD) extraction
- 2026-07-11 — Phase 2 subsurface review (human-in-the-loop)

These decisions are in decisions.md and mirrored to Notion.
