# Project Holos — Verifier Spec (the rulebook)

**Purpose:** the automated checks that replace the manual verification loop. Each rule
below is a failure mode we found *by hand* — encode it so the system catches it by itself
and we never re-discover it manually. This is a **living document**: every time a new
failure mode is found, add a rule here in the same session, before it's lost to context.

**Source of truth:** this file lives in the repo. It is the `BUILD FROM` for the Verifier
(tech-spec Step 6). Rules discovered in chat or a Claude Code session are not "kept" until
they land here.

Each rule: what it checks · what failure it catches · how · when to build (cheap-now vs
at-scale).

---

## Tier 1 — Self-consistency checks (NO external answer key needed)
*The automatable majority. Run on every record. These need no Ward Wise and work in any city.*

1. **Field completeness** — every real record has ward, year, cost, location. Missing field = extraction failure. *(cheap, now)*
2. **Admin/junk filtering** — exclude administrative rows (MENU BUDGET, empty-location allocations) from the denominator; count them separately, never as failures. *(cheap, now)* [learned: 2017]
3. **Truncation detection** — flag locations ending in a bare directional/single letter ("...TO N"), or that look cut off. *(cheap heuristic, now)* [2012 + 2017]
4. **Metadata-bleed / over-merge detection** — flag records with metadata in a field ("Menu (2017)", "Menu Detail by Ward", two addresses merged into one). *(cheap heuristic, now)*
5. **Aggregate / budget tie-out** — does total spend per ward/year match the known program size (~$1.3M/ward, ~$66M/year)? Catches wholesale over/under-extraction with no per-record truth. *(cheap, now)* [the $66M check]
6. **Ward containment (point-in-polygon)** — does the geocoded point/line fall INSIDE the ward it's assigned to? Strongest no-answer-key geocode check. *(cheap PostGIS, now)*
7. **Bounding-box / lon-lat-swap check** — is the coordinate within Chicago's bbox (≈ −87.95..−87.52 lon, 41.64..42.02 lat)? Catches coordinate-order swaps and wild misses. *(cheap, now)*
8. **Count sanity** — extracted record count roughly matches page/structure expectation. *(cheap, now)*
9. **Dedup** — detect duplicate spending records and duplicate reference points. *(moderate)* [the 1919 HARDING two-entry case]
10. **Confidence threshold** — low cascade score → escalate to review, never auto-promote. *(already in cascade; formalize)*

## Tier 2 — Independent cross-reference (commodity external sources, exist nationwide)

11. **Cross-geocoder agreement** — geocode via two independent methods (our cascade vs US Census geocoder). Agree → high confidence. Disagree → route to review. Where they disagree is exactly where to look. *(at-scale)*

## Tier 3 — Calibration against ground truth (small, cheap, per-source)

12. **Recall vs hand-counted slice** — hand-count one small slice per new source (hours, not months); did we catch every real record? *(per new format/city)*
13. **Location fidelity vs ground truth** — is the extracted location string COMPLETE, not just present? **Recall ≠ fidelity — measure both.** *(per new format/city)* [the recurring lesson]
14. **Correctness spot-check** — sample geocoded records, confirm they land within tolerance of the hand-counted true location. **"Produced a coordinate" ≠ "correct coordinate."** *(per new format/city)*

## In-code guards (confidently-wrong prevention — belong in the geocoder, enforced by Verifier)

15. **Escalate, don't guess** — if a stage can't fully resolve, return an honest miss, not a plausible wrong answer. Applies to: range with only one endpoint; alley with <3 corners; stage-2 house number not in segment range (no midpoint fallback); intersection returning MULTIPOINT/LINESTRING (streets cross twice / run together → centroid is a wrong point — flag & monitor).
16. **Grammar-mix awareness** — track the grammar distribution per source. A low geocode rate on a new source may be an UNBUILT-GRAMMAR coverage gap (2017 skewed to alleys), not "messier data." Bucket failures by grammar before concluding anything.

---

## Process / discipline rules (the meta-lessons — the reason this project isn't at a fake 94%)

- **Escalation is not a pass.** Score on correct-only. A grammar that escalates everything is *deferred*, not solved.
- **Spot-checks must be representative.** Sample across the hard/messy cases, not the clean ones. (A 20-row "100% fidelity" check missed a 38% truncation problem twice.)
- **Aggregate-correct can hide compensating errors.** A right total can mask missed records offset by double-counts. Reconcile per-record, not just totals.
- **"It's the data / not fixable" is the reflex to distrust.** Every time it came up this project, it was actually a wiring/coverage bug. Verify against the source before declaring a hard limit.
- **Trace one real example before believing an aggregate.** A single traced record beats any summary percentage. A returned coordinate can't lie the way a percentage can.
- **Verify the loaded state, not just the code.** Code matching the schema ≠ data matching the schema. (The float house-numbers and wrong column names both passed code review and failed reality.)

---

## Failure-mode ledger (append one line every time the system gets fooled)
- 2026-07: geocoder reported 94% on benchmark strings, 6.2% on real extracted strings — benchmark distribution ≠ production distribution. → Rule 13/14.
- 2026-07: house numbers stored as "3327.0", queried as "3327" — string-vs-numeric join. → Rule "verify loaded state."
- 2026-07: intersection ST_Intersection returned LineString; single-segment matching returned NULL for crossing streets. → Rule 15.
- 2026-07-13: 2025 Menu Q4 shows 74% of records in "unknown" geometry class (grammar unbuilt), not extraction failure. Grammar-mix awareness crucial; histogram failures by grammar before concluding data quality. → Rule 16.
- 2026-07-13: Agent classified 282 records as "genuinely truncated PDF source data" (79% of failures) without spot-checking raw PDF. Actually: "E OAK ST" is complete; "W LE MOYNE" is complete. The cascade fails due to matching/cleaning bugs, not incomplete source. Mislabeling complete data as "unfixable data quality" downgraded priority on fixable bugs. → Rule 53 ("It's the data / not fixable" reflex): always spot-check 5-10 raw records in the specific category before accepting a "can't fix" verdict.
- *(add the next one here the moment you find it)*
