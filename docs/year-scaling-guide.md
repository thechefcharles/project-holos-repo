# Year Scaling Guide: Adding New Aldermanic Spending Years

**Goal:** Replicate the 2017 workflow to new years (2012, 2018-2025, etc.)

**Current Status:** 2017 is the reference implementation. 2012 and 2025 data already exists but needs proper integration.

---

## Quick Start (For Next Year)

If you have a PDF or data file for a new year:

```bash
# 1. Extract data from PDF/document
uv run holos harvest extract --year 2026 --source aldermanic-menu-2026.pdf

# 2. Normalize addresses
uv run holos extract normalize --input extracted_2026.csv --output normalized_2026.csv

# 3. Geocode
uv run holos geocode cascade --input normalized_2026.csv --output geocoded_2026.geojson

# 4. Export to web
cp geocoded_2026.geojson web/2026_aldermanic_verified.geojson

# 5. Register in map (see "Register New Year" below)
```

---

## The Full Pipeline (Reference: 2017)

### Step 1: Extract Data from PDF

**Tool:** `holos harvest extract`

**Input:** PDF from aldermanic archive (e.g., `2017OBMMenu50WardDetailsRpt3Dec2018.pdf`)

**Output:** CSV with raw extracted data

**Example:**
```bash
uv run holos harvest extract \
  --source 2017OBMMenu50WardDetailsRpt3Dec2018.pdf \
  --year 2017 \
  --output data/2017_raw.csv
```

**2017 Result:** 1,784 records extracted with ~100% completeness

---

### Step 2: Normalize & Clean Addresses

**Tool:** `holos extract normalize`

**Input:** Raw CSV from Step 1

**Output:** Normalized CSV with clean addresses, categories

**Example:**
```bash
uv run holos extract normalize \
  --input data/2017_raw.csv \
  --output data/2017_normalized.csv
```

**2017 Result:** 1,784 → 1,030 usable records (57.6% have complete addresses)

---

### Step 3: Geocode (Match to Coordinates)

**Tool:** `holos geocode cascade`

**Input:** Normalized CSV

**Output:** GeoJSON with coordinates + confidence scores

**Example:**
```bash
uv run holos geocode cascade \
  --input data/2017_normalized.csv \
  --output data/2017_geocoded.geojson \
  --db-url postgres://localhost/holos
```

**Cascade stages (in order):**
1. **Address Points** — Exact single address match (~15% hit rate)
2. **Centerlines** — Street address interpolation (~20% hit rate)
3. **Intersections** — Corner addresses (~10% hit rate)
4. **Segments** — Street range (FROM X TO Y) (~8% hit rate)
5. **Gazetteer** — Named places (parks, facilities) (~2% hit rate)
6. **Fuzzy** — Typo-tolerant matching (~2% hit rate)

**2017 Result:** 1,030 records → 878 geocoded (57.6% → 85% of addressable records)

---

### Step 4: Validate Quality

**Tool:** `holos validate`

**Input:** Geocoded GeoJSON

**Output:** Quality report + flagged records

**Example:**
```bash
uv run holos validate all \
  --input data/2017_geocoded.geojson \
  --output data/2017_validated.geojson
```

**2017 Result:** 99.3% extraction × 57.6% geocoding × 95% validation = **54.7% composite accuracy**

---

### Step 5: Export to Web GeoJSON

**Goal:** Create the file the map will load

**Example:**
```bash
cp data/2017_validated.geojson web/2017_aldermanic_verified.geojson
```

---

## Register New Year in Map

Once you have the GeoJSON file, register it in **web/app.html**:

```javascript
// In web/app.html, update the yearData object (~line 686):
const yearData = {
    '2012': { file: '2012_pages_2_20_verified.geojson', name: '2012 Aldermanic Menu' },
    '2017': { file: '2017_aldermanic_verified.geojson', name: '2017 Aldermanic Menu' },
    '2025': { file: '2025_menu_classified.geojson', name: '2025 Aldermanic Menu' },
    '2026': { file: '2026_aldermanic_verified.geojson', name: '2026 Aldermanic Menu' },  // ← ADD THIS
};
```

That's it! The year selector will now include 2026.

---

## Expected Results (By Year)

| Year | Projects | Geocoded | Accuracy | File Size |
|------|----------|----------|----------|-----------|
| 2012 | 2,009    | 16.2%    | 69.9%    | 65KB      |
| 2017 | 1,784    | 57.6%    | 54.7%    | 200KB     |
| 2025 | ~2,000   | TBD      | TBD      | 200KB     |
