# Geocode Cascade Benchmark — v1 (independent answer key)

**236 rows** built from the Ward Wise open dataset as an *independent* benchmark for the
Phase 1 geocode cascade. Use it to validate Claude Code's cascade against a source it did
not build. Target: **≥90% correct at calibrated confidence.**

## Files
- `geocode_benchmark_wardwise_v1.csv` — the benchmark.

## Columns
| column | meaning |
|---|---|
| `row_id` | stable id |
| `location_text` | the raw string to geocode (the input) |
| `expected_grammar` | the grammar the parser should detect |
| `expected_geom` | point / line / polygon / multi_point |
| `expected_lat`, `expected_lon` | **the answer key** (representative point) |
| `expected_lat2`, `expected_lon2` | second point for `multi_location` rows |
| `ocr_noise` | `injected` = text was mangled to test street-name repair |
| `source` | provenance (see below) |

## Composition
- single_address 45 + 18 OCR-noise · address_range 25 · hundred_block 28 · intersection 35
- street_segment 35 · alley_block_polygon 20 · named_place 15 · multi_location 12 · wardwide 3

## Provenance (be honest about it)
- **`ward_wise` (178 rows)** — real Ward Wise location text + their geocoded coordinates.
- **`ward_wise+ocr` (18)** — real single addresses with OCR noise injected (O→0, I→1, S→5,
  B→8, dropped directionals); the **answer coordinates are unchanged**, so these test whether
  street-name repair recovers the right place. Example: `3417 B05WORTH AVE` must still resolve
  to the real N Bosworth point.
- **`derived_from_range` (28)** — `hundred_block` cases reworded from real address-range rows
  (`1200-1298 W FOSTER` → `1200 BLK W FOSTER`), keeping the real coordinate. Ward Wise
  normalizes hundred-blocks away, so these had to be reconstructed to test that grammar.
- **`derived_pair` (12)** — `multi_location` built by joining two real single addresses
  (`ADDR A & ADDR B`); the cascade must **split** into two points (`expected_lat/lon` and
  `expected_lat2/lon2`).

## How to score
- **Point grammars:** correct if the cascade's point is within ~**100 m** of `expected_lat/lon`
  (geocoders differ slightly; don't require exact).
- **Line/segment/polygon:** correct if the representative point is within tolerance and the
  geometry type matches.
- **multi_location:** both expected points must be produced.
- **Calibration:** a row the cascade is unsure about should **escalate to review**, not be
  auto-promoted wrong. Escalations on genuinely ambiguous rows are NOT failures — wrong
  auto-promotions are. Report accuracy **per grammar** so you see which stage is weak.

## Caveats
- `wardwide` is only 3 rows — Ward Wise has almost none; wardwide handling is a trivial ward-
  polygon lookup, so low test priority. Add more if you want.
- Ward Wise's own geocoding isn't perfect ground truth (~87% coverage, volunteer-built); a
  handful of answer coordinates may be off. Treat persistent single-row mismatches as
  "verify against the source," not automatic cascade failures.
- This is an **independent** check — build your own benchmark too and compare; where the two
  disagree is exactly where to look.
