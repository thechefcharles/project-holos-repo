# 🗺️ Build Roadmap (Civic Tools MVP)

The three civic-accountability tools: what to build, what data you need, where to get it, and how to build it in Claude Code (Cursor).

*Prepared for Charlie & Sam. Chicago-first, designed to generalize to other cities later.*

---

## The big picture (read this first)

You are **not** trying to out-build Exodigo or 4M Analytics on underground mapping — they have $100M+ and own that. Your wedge is the thing none of them do: **connecting public infrastructure spending to need and to buried reality, for taxpayers and to hold aldermen accountable.**

You build it in three tools, in order. Each one works on its own, and each makes the next more powerful:

1. **The Money Map** — where every menu-money dollar went, vs. where the need is. *Buildable now with data in hand.*
2. **The Report Cards** — turns the map into ward-vs-ward comparisons and accountability scores. *Builds on Tool 1.*
3. **The Underground Layer** — money vs. what's actually failing below the street. *Your long-term moat; needs the atlas extraction.*

**Golden rule of the architecture:** build one central database (the "hub") in one coordinate system. Every tool reads from the hub. Never let a tool hold its own private copy of the data.

- **Coordinate system:** store everything in **EPSG:4326 (lat/long)** for web maps, and keep **EPSG:3435 (Illinois State Plane East, US feet)** for any engineering/CAD math. Reproject with `pyproj`.
- **What you already have in hand:** `chicago_menu_spending_2005-2023_geocoded.csv` + `.geojson` (46,046 projects, $1.26B, geocoded), the Ward Wise repo as your answer key, and a working sheet-232 extraction with known CV thresholds.

---

## Shared foundation (build this once, before the tools)

### Recommended stack (solo/two-person friendly, mostly free)

| Layer | Choice | Why |
|-------|--------|-----|
| Language (data) | Python (pandas, geopandas, shapely, pyproj) | Standard for geo/data work |
| Database | DuckDB + spatial to start; PostGIS when you outgrow it | DuckDB is zero-setup; PostGIS is the pro answer |
| Geocoding | Chicago Street Center Lines + Census geocoder | Free, local, accurate |
| Web app | Next.js (React) + MapLibre GL JS | Free, fast, deploys to Vercel |
| Extraction (Tool 3) | OpenCV + pymupdf + Claude API + ezdxf | What we proved in the session |
| Hosting | Vercel (app) + Supabase (Postgres/PostGIS) | Free tiers, minimal ops |

### The single most important file: `CLAUDE.md`

Claude Code reads this automatically. Put in it: the mission, the coordinate-system rule, the "hub" architecture rule, where the data lives, and the current phase. This is what keeps Claude Code from wandering.

---

## TOOL 1 — The Money Map

**What it does:** An interactive public map. Pick a ward and a year range; see every menu-money project as a point/line, colored by category, with cost. Toggle on **311 complaints** (the need) and **income/demographics**. The story in one screen: *here's the money, here's the need, here's the gap.*

### Data & where to get it

| Data | Source | ID / location |
|------|--------|---------------|
| Menu spending (money) | Already built; refresh from Ward Wise | Ward Wise repo `github.com/ward-wise/data-analysis`; API `wardwisechicago.org/api/spendingitems` |
| 311 service requests (need) | Chicago Data Portal | `v6vf-nfxy` |
| Ward boundaries (2023 remap) | Chicago Data Portal | `p293-wvbd` / `cdf7-bgn3` (map) |
| Ward offices / alderman | Chicago Data Portal | `f4sz-sn2p` |
| Income / demographics | US Census ACS 5-year | `data.census.gov` / ACS API (B19013) |
| Street centerlines (geo ref) | Chicago Data Portal | `6imu-meau` |

All Chicago datasets pull as CSV/GeoJSON or via the Socrata API: `https://data.cityofchicago.org/resource/<id>.json`.

### How to build it in Claude Code

1. **Set up the hub.** Load menu spending, 311 (points), ward boundaries (polygons), ACS income into DuckDB; reproject to EPSG:4326; validate row counts.
2. **Spatial joins.** Tag every 311 request and project with its ward (point-in-polygon) and its tract income.
3. **API layer.** Next.js route serving filtered GeoJSON: `/api/spending?ward=1&from=2015&to=2023`.
4. **Map UI.** MapLibre with toggleable layers: spending, 311 heatmap, income choropleth, ward outline; filter panel.
5. **Deploy** to Vercel.

**Definition of done:** a stranger can open it, pick their ward, and see money vs. complaints vs. income without instructions.

---

## TOOL 2 — The Report Cards

**What it does:** Turns the map into judgment. Per ward: spending per resident, spending mix, an **election-year spike** check, a **spatial concentration** score, and a **need-match** score (does spending go where the 311 complaints are?). Ranks all 50 wards.

### Metrics to compute (this is the product)

- **Spend per capita** = ward spend ÷ ward population, over time.
- **Category mix** = % on streets vs. alleys vs. lighting, ward vs. citywide.
- **Election-year index** = spending in election years vs. off years.
- **Concentration score** = how clustered spending is (Gini/nearest-neighbor) — high = possible favoritism.
- **Need-match score** = correlation between where money went and where 311 complaints were. *The headline metric.*

Extra data: ward population (ACS); election dates (Chicago Board of Elections).

**Definition of done:** you can rank all 50 wards by "need-match" and click any number down to the projects behind it. Sanity anchor: Ward 1 = 1,064 projects, $25.8M.

---

## TOOL 3 — The Underground Layer (your moat)

**What it does:** Overlays water/gas/sewer mains — with size, material, age — under the spending map. The killer view: *"$150K repaving over a 100-year-old main that's due to fail."*

### The pipeline (what we proved, plus what's left)

```
PDF plate
  → rasterize @300 DPI (pymupdf)                      [DONE]
  → color-split blue mains / red fittings (OpenCV)     [DONE]
  → separate text from lines (directional morphology)  [DONE]
  → vectorize mains + detect fittings                  [DONE]
  → GEOREFERENCE with control points   ← HARD PART, DO THIS NEXT
  → build connected network + attach size/material     [next]
  → export DXF (AutoCAD) + GeoJSON + load to hub        [DONE for geometry]
```

Known CV thresholds: blue mains HSV `(95,60,40)–(135,255,255)`; red fittings two bands `(0,80,60)–(10,255,255)` + `(168,80,60)–(180,255,255)`.

### Build order

1. **Fix georeferencing first — it's the hinge.** Control-point registration: ~6–10 known intersections → affine/homography; report residual in feet. Target under ~half a block.
2. **Build topology.** Merge segments into a connected graph snapping endpoints at intersections.
3. **Attach attributes with vision.** Crop each main's neighborhood → Claude API reads size/material → structured JSON.
4. **Load to hub + overlay** on the Money Map; add a "money over old pipe" flag to the Report Cards.

**Definition of done:** extracted mains land on the real streets (verified vs. `6imu-meau`), carry size/material, open in AutoCAD, show under the spending map.

---

## Suggested phasing

- **Phase 1 (weeks 1–3):** Tool 1 MVP — hub + Money Map on data in hand. Ship fast.
- **Phase 2 (weeks 3–6):** Tool 2 — report cards + need-match. Gets journalists' attention.
- **Phase 3 (weeks 6+):** Tool 3 — georeferencing fix first, then one utility on a few plates.
- **Parallel track:** build your own menu-PDF scraper against Chicago; grade it vs. Ward Wise before pointing it at another city.

## Honest risks

- **Georeferencing accuracy** (Tool 3) is the real technical risk — everything spatial depends on it.
- **Data drift** — Ward Wise is volunteer-maintained; verify vs. source PDFs before publishing.
- **Sustainability** — this is a public good; plan for grants/journalism, not just SaaS.
- **Fairness** — a need-match score reads as an accusation; keep methodology transparent and traceable.

---

*Tool 1 needs nothing you don't already have.*
