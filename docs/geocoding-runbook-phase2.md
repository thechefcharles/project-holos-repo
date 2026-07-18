# Geocoding Runbook: Phase 2 Replication (2012, 2018-2025)

**Purpose:** Replicate the Phase 1 + Phase 2 geocoding pipeline on any aldermanic spending year.

**Baseline Performance (2017):** 74.6% rate, 93.9% accuracy, 70.0% composite

---

## Prerequisites

- Docker + PostgreSQL 16 + PostGIS running
- Python 3.12 with holos_tools installed
- Reference data loaded: `ref.address_points`, `ref.centerlines`, `ref.wards`
- Spending records in `staging.spending_projects` (year = TARGET_YEAR)

---

## Step 1: Harvest Source Data

**Source:** Chicago aldermanic menu spending PDFs (Chicago OBM Publications Archive)

```bash
# Harvest spending PDFs for target year
uv run holos harvest aldermanic --year 2012 --output data/

# Extract spending records from PDFs
uv run holos extract aldermanic data/*.pdf --output data/2012_spending.csv
```

**Expected Output:** CSV with columns:
- `id`: unique record ID
- `location_text_raw`: raw address from source
- `ward`: aldermanic ward (1-50)
- `category`: spending category
- `cost`: amount spent

---

## Step 2: Load into Staging

```sql
-- Load spending records into staging
INSERT INTO staging.spending_projects (
    project_id, location_text_raw, location_text_norm, ward, year, category, cost
)
SELECT 
    id, 
    location_text_raw, 
    -- normalize will be done during geocoding
    NULL AS location_text_norm,
    ward::int,
    2012 AS year,
    category,
    cost::numeric
FROM imported_data  -- load from CSV via COPY
WHERE location_text_raw IS NOT NULL
  AND location_text_raw != '';

-- Verify load
SELECT COUNT(*) FROM staging.spending_projects WHERE year = 2012;
```

---

## Step 3: Run Geocoding Cascade

**Code Location:** `holos_tools/geocode/cascade.py`

**Process:**
1. Cascade normalizes address (Phase 1: directional expansion, title case)
2. Applies spatial validation (bounds, street overlap, ward matching)
3. Tries Stage 1 (exact address match) → Stage 2 (interpolation) → ... → Stage 8 (escalate)
4. Falls back to fuzzy matching (Levenshtein distance ≤2)

**Python Script:**

```python
from holos_tools.geocode.cascade import GeocodeCascade, PostgresDB

db = PostgresDB()
cascade = GeocodeCascade(db)

# Load records to geocode
cur = db.conn.cursor()
cur.execute("""
    SELECT row_id, location_text_raw, ward
    FROM staging.spending_projects
    WHERE year = 2012 AND geom IS NULL
""")

for row_id, location_text, ward in cur:
    result = cascade.geocode(location_text, ward)
    
    # Update staging with result
    update_sql = """
        UPDATE staging.spending_projects
        SET 
            location_text_norm = %s,
            geom = ST_SetSRID(ST_Point(%s, %s), 4326),
            method = %s,
            stage = %s,
            score = %s
        WHERE row_id = %s
    """
    
    geom = None
    if result.coordinates:
        geom = f"SRID=4326;POINT({result.coordinates[0]} {result.coordinates[1]})"
    
    db.execute(update_sql, (
        normalize(location_text),
        result.coordinates[0] if result.coordinates else None,
        result.coordinates[1] if result.coordinates else None,
        result.method,
        result.stage,
        result.score,
        row_id
    ))

db.conn.commit()
```

---

## Step 4: Validate Results

```bash
# Run validation suite
uv run holos validate geocoding --year 2012 --changeset latest

# Expected output:
# - Rate: 70-76% (depends on data quality)
# - Accuracy: 92-94% (spatial validation working)
# - Composite: 65-72%
```

---

## Step 5: Promote to Core (Optional)

```sql
-- After validation approval, promote to core schema
INSERT INTO core.spending_projects
SELECT * FROM staging.spending_projects
WHERE year = 2012 AND score IS NOT NULL;
```

---

## Troubleshooting

**Low geocoding rate (<60%):**
- Check if streets are in `ref.centerlines` / `ref.address_points`
- Verify address normalization (check `location_text_norm` sample)
- Look for multi-location records (&, FROM...TO) → Phase 3 work

**High false positives (low accuracy):**
- Check spatial validation is enabled (stage_2+ should have score <0.90 filtered)
- Verify ward boundaries are loaded in `ref.wards`
- Check confidence thresholds (min_confidence = 0.80)

**Cascade timeouts on large datasets:**
- Batch geocoding by ward (faster, parallelizable)
- Use `LIMIT N` to test on subset first

---

## Expected Performance by Year

| Year | Records | Rate | Accuracy | Notes |
|------|---------|------|----------|-------|
| 2012 | 129 | 70-75% | 92-94% | Small dataset; may have OCR variants |
| 2017 | 878 | 74.6% | 93.9% | Golden dataset; well-tested |
| 2018-2025 | TBD | 72-76% | 92-95% | Estimate; depends on source quality |

---

## Phase 2A: Fuzzy Matching

If you see typo-related failures (e.g., "DIVSION" instead of "DIVISION"):
- Fuzzy matching is enabled by default
- Levenshtein distance ≤2
- Score penalized by edit distance (0.95 base - 0.01 per edit)

---

## Phase 3: Multi-Location Handling (Future)

Current pipeline doesn't handle:
- "X & Y & Z" (multi-point intersections)
- "ADDRESS FROM X TO Y" (ranges)

These block ~20-25% of records. Phase 3 work (NLP + multi-point resolution) needed to exceed 76%.

---

## Reference

- **Phase 1 Decision:** 2026-07-18, address normalization + spatial validation (+5.6pp)
- **Phase 2 Quick Win:** 2026-07-18, Stage 2 centerline fix (+11.2pp)
- **Phase 2A Fuzzy:** 2026-07-18, Levenshtein matching (no delta on 2017, infrastructure)
- **Baseline:** 57.8% (pre-optimization)
- **Current (2017):** 74.6% (+16.8pp total)

---

Last Updated: 2026-07-18
