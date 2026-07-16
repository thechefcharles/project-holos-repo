# Sam Voice Memo Plan 1

## Phase 1: Perfect Workflow for Ward 1, 2017

### 1. Build Scraper
- Navigate the aldermanic publications archived download
- Download Ward 1's 2017 file
- Convert PDF to XLS format for geo-location processing

### 2. Data Accuracy & Extraction
- Ensure highest accuracy with extracted data
- Extract structured data from downloaded files

### 3. Pilot Workflow in One Ward
- Start with Ward 1, test full workflow before scaling
- This allows us to validate the entire pipeline

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
