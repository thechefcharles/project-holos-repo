# Sam Voice Memo Plan 1

**Status: In Progress**
**Last Updated: 2026-07-15**

## Progress Summary

### Phase 1 Completion Status
- [x] Step 1: Build Scraper (2026-07-15)
- [x] Step 2: Data Accuracy & Extraction (2026-07-15)
- [x] Step 3: Pilot Workflow in One Ward (2026-07-15)
- [ ] Step 4: Get Building Footprints
- [ ] Step 5: Alley Measurement Workflow
- [ ] Step 6: Break Infrastructure into Segments
- [ ] Step 7: Workflow Expansion Pattern
- [ ] Step 8: Data Pipeline Goal

This is a LIVING DOCUMENT. Update it as work progresses:
- Mark completed steps with `[x]`
- Update status at the top when phases change
- Add blockers or discoveries as they emerge
- Link to related commits/PRs/decisions when work ships

---

## Phase 1: Perfect Workflow for Ward 1, 2017

### 1. Build Scraper ✅ DONE (2026-07-15)
- [x] Navigate the aldermanic publications archived download (Playwright scraper built in harvester)
- [x] Download Ward 1's 2017 file (2017OBMMenu50WardDetailsRpt3Dec2018.pdf harvested)
- [x] Convert PDF to structured format for geo-location processing

**Deliverable:** `holos scraper extract-ward --year 2017 --ward 1`
- Extracts 41 Ward 1 projects from 2017 menu PDF
- Outputs: `data/ward01_2017_menu.csv`
- Total spend: $3,624,797.65 across 10 categories
- Key insight: 25 projects (67%) lack category classification ("Unknown")

### 2. Data Accuracy & Extraction ✅ DONE (2026-07-15)
- [x] Audit extracted data for quality issues (holos validator audit)
- [x] Remove summary/administrative rows (holos validator clean)
- [x] Categorize high-confidence Unknown entries via pattern matching
- [x] Log manual corrections with confidence scores

**Findings:**
- Raw extraction: 41 records from PDF
- After cleaning: 38 actual projects (removed 3 budget/total summary rows)
- Category accuracy: 16/38 (42%) properly categorized, 22 (58%) Unknown
- Manual review corrected: 8 entries based on location/cost patterns
- Remaining: 14 "Unknown" entries requiring PDF review

**Deliverables:**
- `data/ward01_2017_menu_cleaned.csv` — 38 projects, summary rows removed
- `data/ward01_2017_menu_enhanced.csv` — with corrections + confidence scores
- `data/ward01_2017_corrections.json` — manual review log (8 corrections, 14 pending PDF review)

### 3. Pilot Workflow in One Ward ✅ DONE (2026-07-15)
- [x] Extract → Geocode → Validate end-to-end on Ward 1, 2017
- [x] Measure accuracy and identify blockers
- [x] Document findings for Phase 1 Step 4+

**Results:**
- **Records:** 21/38 geocoded successfully (55.3%)
- **Spend:** $187K/$985K (19.0%) — high-cost projects failed!
- **Key finding:** Most failures are street range addresses (FROM/TO), not single locations

**Failure breakdown:**
- Street range addresses (8 records, $251K): "FROM X TO Y" pattern needs street_segment grammar
- Program allocations (3 records, $58K): "Arts Program", "Infrastructure" — not geographic
- Ambiguous addresses (2 records, $314K): "ROCKWELL ST" (no number), single street name
- Truncated locations (1 record, $3K): PDF parsing cut off text

**What this means:** The geocoding cascade works great for intersections ($600-50K projects), but fails on the infrastructure spend category (street resurfacing $19-54K each). This is a platform gap: street_segment grammar stage is present but not tuned.

**Decision:** Proceed to Step 4 (Building Footprints) with 21 successfully geocoded projects (~19% of budget). Phase 2 will fix street_segment grammar for remaining projects.

**Deliverables:**
- `holos pilot geocode-batch` — batch geocoding CLI
- `holos pilot validate` — accuracy validation & reporting
- `data/ward01_2017_menu_cleaned_geocoded.csv` (21 with coords)
- `data/ward01_2017_pilot_analysis.json` (detailed failure analysis)

### 4. Get Building Footprints
- Navigate to Chicago data portal
- Download building footprint file
- Enable building-to-alley measurements

### 5. Alley Measurement Workflow
Similar to current street centerline workflow:
- Take point within alley centerline
- Measure distance to building/garage
- Multiply by 2

This mirrors the existing process where we:
- Take point within street centerline
- Measure to curb distance
- Multiply by 2

### 6. Break Infrastructure into Segments
Key insight: Chicago data portal already segments streets by block, each segment has:
- Own dataset
- Distance measurement
- Length
- Other metadata

Goal: Replicate this segmentation for alleys
- Break alleys into segments per block
- Each segment gets its own data attributes

### 7. Workflow Expansion Pattern
Once Ward 1, 2017 is working perfectly:
1. Expand to all wards for year 2017
2. Once all wards in 2017 are accurate
3. Then expand to multi-year mapping and assessment

### 8. Data Pipeline Goal
Navigate public documents → Download → Extract → Geo-locate → Encode

Each geo-located point should carry:
- Cost
- Ward number
- Year
- Project type
- Other relevant metadata

This creates a connection between spending records, locations, and physical measurements.

---

## Phase 2: OCR of Historical Documents (Future)

Once Phase 1 pipeline is perfected and can be replicated across all wards/years:

### OCR Implementation
- Research most effective OCR tools for museum/archive quality documents
- Top-of-the-line industry tools suitable for outdated/hand-drawn documents
- Test OCR capability on outdated source materials

### Digitization Goals
- Trace and digitize hand-drawn infrastructure (water service lines, utilities, etc.)
- Convert OCR output to GIS layers
- Encode historical data the same way as Phase 1 data

### Success Criteria
- AI tools can accurately trace hand-drawn documents
- Output can be converted to GIS-compatible layers
- Data can be encoded with historical context

---

## Core Vision: Digital Twin with Measurements

The ultimate goal is to create a georeferenced digital twin that connects:
1. **Spending records** (from aldermanic PDFs and historical documents)
2. **Physical locations** (geo-coded points on the map)
3. **Real-world measurements** (street widths, alley widths, building depths)
4. **Cost analysis** (spending per unit distance, per project type, per ward)

This enables analysis like:
- How much did we spend per linear foot of street/alley?
- Cost comparison across wards and years
- Identify patterns in municipal spending on infrastructure
- Historical trends in city development

---

## Immediate Next Steps
1. Build scraper for aldermanic archive publications
2. Extract and structure Ward 1, 2017 data
3. Test geo-location accuracy
4. Implement alley measurement workflow
5. Validate pipeline with building footprints
