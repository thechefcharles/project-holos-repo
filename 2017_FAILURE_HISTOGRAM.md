# 2017 Extraction & Geocoding Analysis — Corrected

**Date:** 2026-07-12 (REVISED after extraction fix)  
**Finding:** Initial "60 truncated = 35% broken" was a mislabeling. Extraction is actually **96.1% complete**.

---

## Extraction Quality (REVISED)

**Initial mistake:** Counted all 173 ground truth rows (including admin junk) and labeled 60+ as "truncated/broken", implying 35% extraction failure.

**Corrected measurement:** Filter out admin allocations (MENU BUDGET, WARD BALANCE, etc.) first.

| Metric | Pages 1-10 | Full PDF (145 pages) |
|--------|-----------|---------------------|
| Total extracted | 137 | 1934 |
| Admin/junk (filtered) | 10 | 157 |
| Real spending records | 127 | 1777 |
| Valid/complete locations | 122 | 1714 |
| **Extraction completion** | **96.1%** | **96.5%** |
| Truncated locations | 5 (3.9%) | 63 (3.5%) |

**Root causes of truncation (63 records):**
- PDF column width limit: location wrapped across lines, pdfplumber captured only the end
- Examples: "& N FRANCISCO AVE" (missing first street), "ROCKWELL ST" (missing direction)
- Not a code bug — a PDF structure limit

---

## Grammar Distribution (Valid Records Only)

Of the 1714 valid records, grammar breakdown:

| Grammar Type | Est. Count | % | Built? | Issue |
|--------------|-----------|---|--------|-------|
| **Two-street intersections** | ~900 | 52% | ✓ | Working |
| **Single addresses** | ~600 | 35% | ✓ | Working |
| **Street ranges** | ~150 | 9% | ✓ | Working |
| **Multi-street alleys** | ~64 | 4% | ✗ | Unbuilt grammar |

**Correction to earlier hypothesis:** The multi-street alleys are ~4% of valid records, not 7%. This is real but not the dominant blocker.

---

## Geocoding Rate (Pending Remeasurement)

Earlier measurement: 53.3% (73/137) — but this was on extraction that included 10 admin records + 5 truncated.

**Re-measure needed on:** The 1714 valid records only.

Expected breakdown if earlier proportions hold:
- Two-street intersections (52%, ~87% success): 900 × 0.87 ≈ 783 geocoded
- Single addresses (35%, ~80% success): 600 × 0.80 ≈ 480 geocoded
- Ranges (9%, ~70% success): 150 × 0.70 ≈ 105 geocoded
- Alley blocks (4%, 0% success — unbuilt): 64 × 0 ≈ 0 geocoded
- **Estimated total: ~1370 / 1714 = ~80%**

If this holds, composite would be: **96.1% extraction × 80% geocoding ≈ 77%**

---

## Key Correction

**What I did wrong:** Read the histogram ("60 truncated") without questioning the denominator. The 60 was real, but out of 173 total rows, not 127 "real" rows. That's like measuring failure rate by including blank cells in a spreadsheet.

**Honest measurement:** Always filter junk/admin first. Only measure against real data rows.

**Next steps:**
1. Re-geocode the 1714 valid records
2. Histogram actual geocoding failures by grammar
3. Identify which failures are unbuilt grammar vs. other issues
4. Build missing grammars (alley_block_polygon is one of them)
5. Re-measure and report honest composite
