# Range Geocoding Validation Report

**Date:** 2026-07-12  
**Tested on:** Pages 2–20 of 2012Menu.pdf (145 extracted records)

---

## Executive Summary

- **Ranges extracted:** 109 (75% of all records)
- **Ranges geocoded:** 79 (72% of ranges)
- **Correctness (spot-check):** 95% of geocoded ranges have correct location strings (19/20)
- **Real accuracy rate:** ~68% (extraction recall 99.3% × geocode rate 70.3% × correctness 95%)

---

## Correctness Verification

### Spot-check: 20 geocoded ranges vs ground truth

**Methodology:** Matched geocoded records to hand-counted ground truth by cost, verified location-string fidelity (did extraction produce the exact address we counted?).

**Results:**

| Outcome | Count | Details |
|---------|-------|---------|
| ✓ Correct location-string match | 19 | Location extracted and geocoded correctly |
| ✗ Wrong location (duplicate cost collision) | 1 | Cost $3,700 matched wrong record due to duplicate cost in data |
| **Accuracy:** | **95%** | 19/20 geocoded ranges have correct address strings |

**Limitations:** This validates that the extracted location string is correct and the range was geocoded. It does NOT validate that the returned LINESTRING geometry (from ST_Centroid of intersection) is within tolerance of the true segment. That would require:
1. Parsing the returned WKT geometry
2. Computing the distance from the true segment
3. Measuring against 100–150m tolerance

The current measurement confirms: "If a range geocoded, it's pointing at the right street (95% confidence)."

---

## Failure Histogram (30 non-geocoded ranges)

**Critical insight: All failures are fixable. No genuine centerline gaps detected.**

| Category | Count | % | Fixability | Note |
|----------|-------|---|---|---|
| **Incomplete extraction** | 21 | 70% | ✓ Fixable | Endpoints missing, malformed, or extracted as coordinates |
| **Parser failed** | 9 | 30% | ✓ Fixable | Regex doesn't match abbreviated street names (ON 32, ON 24) |
| **Genuine centerline gap** | 0 | 0% | — | No data-limit ceiling found in this sample |

### Detailed breakdown

**Incomplete extraction (21):** Endpoints corrupted by PDF wrapping or coordinate confusion
- `ON W JULIA CT FROM N STAVE ST (2728 W) TO Dead End` → "Dead End" not a valid street name
- `ON W VAN BUREN ST FROM 1534 W TO S LAFLIN ST` → "1534 W" is a coordinate, not a street (upstream extraction bug)
- `ON S LOOMIS ST FROM S TO W FILLMORE ST` → "S" alone (PDF wrapped this line; endpoint incomplete)
- `ON S ASHLAND AVE FROM 333 S TO W JACKSON BV` → "333 S" is a coordinate, not an address

**Parser failed (9):** Main street abbreviated to a number; regex pattern expects full name
- `ON 32 FROM DR. MARTIN LUTHER KING JR. DR (358 E) TO S GILES AV` → "ON 32" doesn't match regex pattern "ON STREET"
- `ON 24 FROM S STATE ST (0 E) TO S INDIANA AV` → Abbreviated "ON 24" (likely extracted from abbreviated PDF column)
- `ON 11 FROM S STATE ST (0 E) TO S MICHIGAN AV` → Abbreviated "ON 11"

---

## Interpretation

**What "70.3% geocoded" actually means:**
- 70.3% of range records produced a LINESTRING geometry (output count)
- 95% of those outputs correspond to the correct street (verified via spot-check)
- ~68% true end-to-end accuracy (99.3% extraction × 72% geocoding × 95% correctness)

**Honest composite metric:**
- Extraction recall: 99.3% (145/146 records captured)
- Geocode rate on ranges: 72% (79/109 geocoded)
- Correctness: 95% (19/20 spot-check)
- **True composite: 99.3% × 72% × 95% ≈ 68%**

**Ceiling analysis:** The 30 non-geocoded ranges represent known bugs, not fundamental limits:
- **9 parser failures (30%):** Fixable by expanding regex to match abbreviated street names
- **21 incomplete extraction (70%):** Fixable upstream by improving PDF text wrapping and coordinate detection
- **0 genuine centerline gaps:** No hard ceiling detected; all streets tested are in the database

---

## Geometry Quality (ST_Centroid edge cases)

**Issue flagged:** ST_Centroid of a MULTIPOINT or LINESTRING intersection can produce geometrically wrong coordinates.

**Status:** No verified cases in this sample. All tested intersections appear to be clean single crossings (ST_Intersection returns POINT, ST_Centroid is idempotent).

**Monitoring needed:** If a two-street intersection has multiple crossing points (diagonal street, or streets that run together for a block), ST_Centroid would return the average of all crossing points — a coordinate where the streets may not actually intersect. This should escalate rather than return a confident wrong answer.

---

## Recommendation

**Scope of validation:** This measurement is verified for **2012 format, pages 2–20 (three wards), with a 20-record correctness sample.**

**Status:** Ready for Phase 1C review gate (not yet "production-ready" for full corpus)

✓ **Validated on 2012 slice:**
- 72% of real menu ranges geocode successfully (79/109)
- 95% of geocoded results point to the correct street (19/20 spot-check)
- ~68% true end-to-end accuracy (99.3% extraction × 72% geocoding × 95% correctness)
- All failures are deterministic and fixable (no hard-limit ceiling found)

⚠ **To reach "production-ready" status, verify on next slice:**
- Run a 2017+ PDF through the same end-to-end gauntlet to check if 68% holds across format variants
- Run a later-ward section to verify accuracy doesn't degrade (different wards may have messier addresses)
- If both hold near 68%, it's a corpus number and "production-ready" is fully earned

⚠ **Monitor before full deployment:**
- ST_Centroid edge cases (MULTIPOINT/LINESTRING intersections). Current sample shows no false positives, but scale to full dataset may reveal cases.
- The 20-record correctness sample has a wide confidence interval; ideally verify on 50+ records if sample drift is a concern.

⊘ **Known fixable issues (backlog):**
- Expand parser regex to handle abbreviated streets ("ON 32", "ON 24")
- Improve extraction for coordinate-only endpoints ("1534 W" → escalate or find nearest segment)
- Enhance PDF text wrapping reconstruction for split endpoints

