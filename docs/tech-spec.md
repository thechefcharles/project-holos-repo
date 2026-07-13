# Project Holos — Technical Build Specification

Data Conversion Pathways & the Agentic Network Build Guide

Companion to the Master Brief (v2) • Prepared for CTO execution via Claude Code • July 2026

## How to read this document

Part I is the data physics: every file type that enters the system, every format it passes through, and the exact software that performs each conversion — organized as end-to-end "chains" from raw artifact to the PostGIS hub to shipped product. Part II is the software stack decision table (open-source vs. commercial, with a cost posture for a pre-seed team). Part III is the step-by-step agentic network build: how to stand up the pipeline agents and all fourteen stakeholder-lens agents in Claude Code and the Claude Agent SDK, with human checkpoints, confidence scoring, and security designed in from day one. Appendices contain copy-paste scaffolding (CLAUDE.md skeleton, subagent files, MCP config, SQL schema).

Two rules govern everything below:

1. **Agents decide; deterministic tools execute.** LLM agents never "eyeball" a coordinate transform or invent a geometry. Every conversion is a scripted, versioned, testable CLI tool. Agents choose which tool to run, interpret ambiguous inputs, route failures, and write structured judgments. This is what makes the pipeline auditable and what makes confidence scores meaningful.

2. **One hub, two coordinate frames, full provenance.** Everything lands in PostGIS. Geometry is stored in EPSG:4326 (WGS84 lat/long) for web delivery and computed in EPSG:3435 (Illinois State Plane East, US survey feet) for engineering math. Every record carries source ID, extraction method, confidence, and reviewer — no orphan geometry, ever.

---

## Chain A1 Progress Tracker

**Current Status:** Step 5 (Geocode Cascade) complete. Resuming at Step 1 (Acquire).

**Tracking Rule:** When a step is complete, change `[ ]` → `[x]` and add date `(YYYY-MM-DD)`. Commit the progress tracker update along with step completion work. Do not modify after-the-fact; append only.

- [x] **Step 1: Acquire** — OBM/DBM discovery + PDF harvesting with manifests (2026-07-12: 14 PDFs, 36 MB, 2012–2025 complete)
- [x] **Step 2: Classify PDF** — pdfplumber text/scanned detection + table extraction/OCR (2026-07-12: all 14 text-native, 100% confidence)
- [x] **Step 3: Normalize** — Year-variant adapters for 2012–2025 spending PDFs (2026-07-12: MenuAdapter2012 + MenuAdapter2017Plus; CLI ready)
- [ ] **Step 4: Parse location** — usaddress/libpostal + grammar classification
- [x] **Step 5: Geocode cascade** — exact match → census → centerline → nominatim (94.1% accuracy, 2026-07-12)
- [ ] **Step 6: Verify** — deterministic validation (point-in-ward, segment sanity, dedup)
- [ ] **Step 7: Load** — GeoPandas → GeoParquet → PostGIS core.spending_projects
- [ ] **Step 8: Serve** — MVT tiles → MapLibre dashboard (Phase 1 exit gate)

---

## PART I — FILE TYPES & THE CONVERSION PATHWAY

### 1. The format registry

Every format the system touches, and its role:

| Format | Extension(s) | Role in Holos | Produced by | Consumed by |
|--------|--------------|---------------|-------------|------------|
| Text-native PDF | .pdf | Budget reports, DBM/CIP publications | City portals | pdfplumber, PyMuPDF |
| Scanned/raster PDF | .pdf | Older menu reports, atlas plates | Archives, scanners | OCR stack (Part I §3) |
| Vector PDF (CAD-exported) | .pdf | Terra engineering plans | Engineering firms | PyMuPDF path extraction |
| TIFF / GeoTIFF | .tif | Sanborn scans, orthomosaics, DSM/DTM | Archives, photogrammetry | GDAL, rasterio, QGIS |
| Cloud-Optimized GeoTIFF | .tif (COG) | Web-servable rasters | gdal_translate | TiTiler, MapLibre, QGIS |
| PNG/JPG | .png .jpg | Cropped callouts, radargram images, drone frames | Pipeline, cameras | Vision models, ODM |
| DWG | .dwg | Native CAD from utilities/firms | AutoCAD, MicroStation exports | ODA File Converter → DXF |
| DXF | .dxf | Open CAD interchange; engineering deliverable | ezdxf, ODA, exports | ezdxf, ogr2ogr, AutoCAD, QGIS |
| DGN | .dgn | MicroStation (some utilities/IDOT) | Utilities | ODA/FME → DXF/GPKG |
| Shapefile | .shp+ | Legacy GIS exchange (city portal downloads) | Agencies | ogr2ogr → GeoPackage |
| GeoJSON | .geojson | API payloads, web layers, intermediate geometry | Pipeline | PostGIS, MapLibre, review UI |
| GeoPackage | .gpkg | Primary file-based GIS interchange | ogr2ogr, QGIS | PostGIS load, partners |
| GeoParquet / Parquet | .parquet | Analytical storage, large tabular+geo | GeoPandas, DuckDB | DuckDB, dashboards |
| CSV | .csv | Socrata exports, sensor logs, deliverables | Portals, instruments | pandas, DuckDB |
| WKT/WKB (in-DB) | (in-DB) | Geometry encoding inside PostGIS/DuckDB | PostGIS | PostGIS |
| LAS/LAZ (1.4) | .las .laz | LiDAR point clouds (drone, Hovermap) | Sensors, ODM, Emesent Aura | PDAL, CloudCompare |
| COPC | .copc.laz | Cloud-optimized point clouds for web | PDAL | Potree/Cesium viewers |
| E57 | .e57 | Terrestrial scan interchange (if partners send it) | Scanners | PDAL/CloudCompare → LAZ |
| PLY/OBJ | .ply .obj | Meshes from SLAM/photogrammetry | ODM, Aura, Blender | Blender, converters |
| glTF/GLB | .glb | Runtime 3D assets | Blender, converters | CesiumJS, Unreal |
| Cesium 3D Tiles | tileset.json + .b3dm/.glb | Streamed 3D twin | pg2b3dm, Cesium ion | CesiumJS, Cesium for Unreal |
| MVT / PMTiles | .pbf .pmtiles | 2D vector tiles for dashboards | martin / tippecanoe | MapLibre GL JS |
| SEG-Y | .sgy | GPR trace interchange | GPR export | GPRPy, custom UNet |
| DZT / DT1 / rd3 | vendor | Vendor native GPR (GSSI / Sensors&Software / MALÅ) | GPR units | Vendor software → SEG-Y/CSV |
| RINEX / NMEA | .obs .nmea | GNSS/RTK raw + streams | RTK receivers | OPUS/postprocessing, ODM |
| HDF5 / VTK | .h5 .vtk | Inversion voxel models (SimPEG) | SimPEG | ParaView, isosurface → glTF |
| JSON (schema'd) | .json | Every agent's structured output | Agents/tools | Hub loaders, review UI |
| Markdown | .md | CLAUDE.md, decisions log, run reports | Team + agents | Humans, Claude Code |

**Rule of thumb the whole team should internalize:** shapefile and DWG are things we accept, never things we keep. Internal life is GeoPackage/GeoParquet on disk and PostGIS in the hub; DXF and GeoJSON are the export dialects (engineering and web, respectively).

### 2. Coordinate & datum policy (read before writing any converter)

- **Horizontal, storage & web:** EPSG:4326 (WGS84). All hub geometry columns.
- **Horizontal, engineering math:** EPSG:3435 (NAD83 Illinois State Plane East, US survey foot). All length/area/buffer calculations, all DXF deliverables. Reproject with pyproj/PostGIS `ST_Transform` — never hand-rolled math.
- **Web tiles:** EPSG:3857 handled automatically by the tile server; never stored.
- **Vertical (the Z axis Component B exists to create):** store elevations as NAVD88 heights (EPSG:5703) in a dedicated column, with sensor-derived depths kept as depth-below-surface plus a surface elevation reference — never bake the two together silently.
- **Chicago City Datum (CCD) trap:** most Chicago water/sewer atlases and older engineering plans reference CCD, a local vertical datum (zero ≈ 579.88 ft on the old sea-level datum — the exact NAVD88 offset must be confirmed with a licensed surveyor before any Z value from a legacy plan is trusted). Action item: establish and version a single CCD→NAVD88 conversion constant as a calibration record in the hub; every legacy Z carries `vertical_datum_source = 'CCD'` until converted.

Every geometry row carries: `srid_native` (what the source was in), `datum_notes`, and transform provenance. Reprojection is lossless bookkeeping only if you record where you started.

### 3. Conversion Chain A1 — Spending PDFs → Ward Capital Planning layer

The Component A backbone. Already prototyped at ~87% geocode rate on 46k projects.

**Path:** portal → PDF → structured rows → normalized schema → parsed address → geocode cascade → geometry assignment → hub → tiles/API.

1. **Acquire.** Harvester agent hits known sources: Chicago Data Portal (Socrata API via sodapy or plain HTTPS with `$limit` paging), DBM/OBM publication pages (Playwright for JS-rendered lists, httpx for direct links). Save raw bytes to `raw/{source}/{date}/` with a manifest JSON (URL, checksum, retrieval timestamp). **Nothing downstream ever touches a file that isn't manifested.**

2. **Classify the PDF.** `pdfplumber` char-count heuristic: text-native vs. scanned. Text-native → table extraction (`pdfplumber tables`; Camelot lattice mode as fallback for ruled tables). Scanned → OCR path: render pages at 300 DPI with PyMuPDF → PaddleOCR or Tesseract for bulk; Claude vision (via API) for the gnarly pages where column structure breaks. Output is always the same: `extractions/{doc_id}.json` — an array of `{ward, year, category, location_text, cost, page, bbox, extraction_method, extraction_conf}`.

3. **Normalize.** Pandas job maps year-variant layouts into the master schema (the 2012–2026 format drift lives here as versioned per-year adapter configs, not code forks). Category strings map through a controlled vocabulary table.

4. **Parse the location.** `usaddress` (or `libpostal` if multi-city sooner) splits `location_text` into number/street/type/direction, and — critically — detects range forms ("1200–1298 W Foster") and segment forms ("Foster from Ashland to Clark"), which route to different geometry logic.

5. **Geocode cascade (the moat).** In order, cheapest-first, each step recording method + score:
   - (a) exact match against Chicago address points
   - (b) US Census Geocoder batch API (free, 10k/batch)
   - (c) street-centerline interpolation against the city centerline file (Socrata `6imu-meau`) for ranges/segments — linear referencing along the matched centerline
   - (d) Nominatim/OSM as fallback
   - (e) unresolved → human review queue
   
   Point for single addresses, line (clipped centerline) for segments, polygon (ward/park/alley footprint join) for area work.

6. **Verify.** Deterministic checks: geocoded point falls inside the stated ward polygon (2023 boundaries `p293-wvbd`, with pre-2023 remap table for historic years); segment length sanity vs. reported cost; duplicate detection. Failures → review queue with reason codes.

7. **Load.** GeoPandas → GeoParquet snapshot + `ogr2ogr` / `ST_GeomFromGeoJSON` into PostGIS `core.spending_projects` (4326) with generated-column 3435 mirror for measurement queries.

8. **Serve.** `martin` (or `pg_tileserv`) publishes MVT from PostGIS → MapLibre dashboard; FastAPI endpoint serves GeoJSON; DuckDB reads the GeoParquet for heavy analytics (need-match vs. 311 `v6vf-nfxy`, cost-per-square-foot using centerline length × curb-to-curb width).

### 4. Conversion Chain A2 — Open tabular/GIS data (Socrata, Census)

Shortest chain, but it's the reference frame everything else validates against.

**Socrata datasets** (311, centerlines, ward boundaries, address points): API → CSV/GeoJSON → `ogr2ogr -t_srs EPSG:4326` → PostGIS `ref.*` schema. Refresh on schedule; version every pull (slowly-changing-dimension style, `valid_from/valid_to`), because ward boundaries and centerlines change and historic spending must join to historic geography.

**Census/ACS:** `censusdis` or raw API → tract/block-group Parquet → DuckDB/PostGIS for demographic overlays.

### 5. Conversion Chain B1 — Vector engineering PDFs (Terra plans)

The highest-value legacy input: CAD-exported PDFs retain true vector linework.

**Path:** PDF → vector paths + text → georeferenced CAD → reviewed DXF → PostGIS.

1. **Triage.** PyMuPDF: does the page contain vector drawings (`page.get_drawings()`) or is it a raster scan wrapped in PDF? Vector → this chain; raster → Chain B2.

2. **Extract linework.** PyMuPDF pulls paths (polylines, arcs) with layer hints from PDF optional content groups when present; text extraction pulls every annotation string with its bbox and rotation. Output: `plan_extract/{doc_id}.json` (paths in PDF page coordinates) + a page-render PNG for the reviewer's eyes.

3. **Georeference.** The plan's page coordinates → EPSG:3435 via control points: the operator (or the surveyor-lens agent proposing, human confirming) clicks 3–6 known intersections/monuments visible on the plan against the city centerline/address layer. Affine transform for clean CAD exports; thin-plate spline (GDAL GCP tools) only when sheets are distorted. **Registration residuals (RMSE in feet) are stored as the sheet-level confidence input** — the "off by a block" failure mode from the gaps table dies here.

4. **Author CAD.** `ezdxf` writes a layered DXF in EPSG:3435 feet — layer names mapped to the Holos utility taxonomy (`W-MAIN`, `SS-MAIN`, `FO-CONDUIT`…), one entity per extracted feature, each entity's XDATA carrying the source doc ID + path ID for round-trip provenance. This DXF opens natively in AutoCAD/Civil 3D/QGIS.

5. **Read the callouts.** Crop each text annotation ±context window → layout-aware extraction: Claude vision (structured JSON out) for dense engineering callouts (size, material, tie distances, "4′ TO 5′ COVER" depth cues); LayoutLM/Donut fine-tunes later if volume justifies. Each attribute candidate carries its own confidence + the bbox linking it to geometry.

6. **Associate attributes to features.** Deterministic: nearest-eligible-feature within tolerance, tie-broken by leader-line detection (OpenCV) where present; ambiguous associations → review queue rendered as image overlays.

7. **HUMAN GATE (blocking).** A reviewer with engineering literacy approves geometry + attributes sheet-by-sheet in the review UI (Part III §8). **A misread pipe diameter or depth is a safety defect, not a typo.** Approval writes reviewer ID + timestamp; only then does the loader promote `staging` → `core`.

8. **Load.** `ogr2ogr` (DXF driver) or `ezdxf→GeoJSON→PostGIS` into `core.utility_segments` / `core.utility_points`, with `ql_level = 'D'` (records-derived) — **never higher from paper alone.** Depth cues from callouts land in `depth_ft_reported` with `vertical_datum_source='CCD-unverified'`.

### 6. Conversion Chain B2 — Raster plates: hand-drawn atlases & Sanborn maps

The prototype already cracked the hard part (blue-text vs. blue-line separation on a real water-atlas plate: 552 mains, 381 hydrants/valves).

**Path:** scan → georeferenced COG → segmented masks → vectorized → topology-repaired → reviewed → PostGIS.

1. **Acquire/scan.** Sanborns from Library of Congress (public-domain vintages) as high-res TIFF; city atlas plates scanned ≥400 DPI. Manifest as always.

2. **Georeference.** QGIS Georeferencer (interactive first pass; GCPs exported and versioned) or `gdal_translate -gcp … | gdalwarp -tps -t_srs EPSG:3435` for batch re-runs. Residuals stored. Output: GeoTIFF → `rio cogeo create` → COG served to the review UI via TiTiler.

3. **Segment.** OpenCV color-space separation (HSV thresholding per plate's ink palette) + morphological ops; SAM/Grounding DINO for symbol classes (hydrants, valves, manholes) where color alone fails. The text/line disambiguation: text-mask via OCR-detected boxes subtracted from the line mask before vectorization.

4. **Vectorize.** Skeletonize line masks (scikit-image) → Douglas-Peucker simplification (Shapely) → polylines; symbol centroids → points. Everything in pixel space × the georeference transform → 3435.

5. **Topology repair.** The gaps table's "disconnected segments" problem: PostGIS topology / Shapely snapping — endpoints within tolerance merge; segments crossing at plausible junctions get nodes; the result is a connected network graph (also exported to NetworkX for connectivity QC: number of components, dangling ends flagged).

6. **Attributes.** Plate marginalia + on-line labels through the same OCR→associate→review path as B1 step 5–6.

7. **HUMAN GATE, then load** with `ql_level='D'`, `source_type='atlas_plate'` or `'sanborn'`, plate ID, and per-feature confidence = f(registration RMSE, segmentation score, topology score).

### 7. Conversion Chain B3 — Native CAD from utilities/agencies (DWG/DGN)

1. DWG → DXF via ODA File Converter (free, scriptable); DGN → via ODA or FME if a partner license exists.

2. **Layer crosswalk.** Every source organization names layers differently; a versioned YAML crosswalk (`source_layer` → `holos_class`) per provider, drafted by the extractor agent, confirmed by a human once per provider, reused forever.

3. `ogr2ogr` DXF→GeoPackage with the crosswalk applied; coordinate check (some utility CAD is in local grids or modified state plane — the verifier agent tests a sample of coordinates against ref layers before bulk load).

4. Attributes from block attributes/XDATA where present; review gate; load at `ql_level='C'` if the provider certifies survey-grade horizontal, else `'D'`.

### 8. Conversion Chain B4 — Existing GIS from agencies

Shapefile/File-GDB/ArcGIS REST → `ogr2ogr` → GeoPackage → PostGIS `staging`, schema-mapped, deduplicated against what's already in `core` (conflation: match by geometry proximity + attribute similarity; conflicts become review items rather than silent overwrites — source provenance tracking is what keeps conflation defensible).

### 9. Conversion Chain C — Field sensing (the Z axis)

Component B's physical layer. Everything here outputs QL-B at best; the pipeline must say so.

**C1. Drone photogrammetry (surface truth).** RTK-tagged JPGs (+ RINEX base logs, post-processed via OPUS when needed) → OpenDroneMap/WebODM → orthomosaic GeoTIFF + DSM/DTM GeoTIFF + dense cloud LAZ → COG the rasters, `pdal translate` the cloud to COPC → hub raster/point-cloud registry. **The DTM becomes the surface-elevation reference** that converts sensor depth-below-surface to NAVD88 Z.

**C2. LiDAR / SLAM (Hovermap ST-X).** Raw scan → Emesent Aura processing → georegistered LAZ (aligned to the same RTK control as C1 — the shared-coordinate-system advantage). PDAL pipelines: ground classification (SMRF), thinning, COPC. Above-ground features (poles, hydrant heads, building faces) extracted for the twin and — importantly — as surface indicators cross-checking legacy records (a hydrant head confirms a main).

**C3. GPR.** Native DZT/DT1/rd3 → vendor software (RADAN / EKKO_Project / MALÅ Vision) for gain/migration first-pass → export SEG-Y (traces) + PNG radargrams. Interpretation: manual hyperbola picks in vendor software initially; the U-Net picker trains on those picks later. Output picks: CSV `x, y, depth_below_surface_ft, velocity_used, pick_conf` in 3435 → joined to DTM → NAVD88 Z. **Every depth row is born `ql_level='B'`.** Physical exposure records (pothole/vac results, when a firm shares them) are the only writer of `ql_level='A'`, and they also become GPR calibration points.

**C4. EM & magnetometry.** Instrument CSV/vendor logs (positions from the same RTK frame) → SimPEG inversions (EM61-style time-domain, mag gradiometry) → conductor/anomaly polylines + voxel models (HDF5/VTK). Voxels → isosurfaces (PyVista) → glTF for the twin; anomaly lines → PostGIS with method + inversion-misfit-derived confidence.

**C5. Fusion.** All C outputs + B records enter the conflation layer: proximity/attribute matching first (deterministic), factor-graph refinement (GTSAM) where multiple sensors constrain one feature. Fusion writes a **new feature version** with `derived_from[]` provenance and a fused confidence — it never destroys the input observations.

### 10. Conversion Chain D — Hub → products

- **2D dashboards:** PostGIS → `martin` (MVT) → MapLibre GL JS in Next.js. PMTiles static snapshots for zero-server public demos.

- **3D twin:** PostGIS geometry + Z → `pg2b3dm` → Cesium 3D Tiles → CesiumJS (web). Point clouds via COPC/3D Tiles. Unreal Engine consumes the same tilesets through Cesium for Unreal when a cinematic/VR view is wanted — **Cesium-first means Blender/Unreal are presentation options, not separate data paths.** Blender (with BlenderGIS) reserved for authored assets (typical vault/pipe cross-sections), exported as glTF.

- **Engineering deliverables:** PostGIS → `ezdxf` → layered DXF in 3435 feet + PDF plan sheets (QGIS layouts) stamped with QL levels and confidence — the artifact an engineering-firm partner actually opens.

- **Data exchange:** GeoPackage / GeoParquet / CSV exports per tier-appropriate access (Part III §13).

- **Reports:** DuckDB analytics → Markdown → PDF (Pandoc/Typst) for accountability and capital-planning documents.

### 11. The pathway on one line per source

| Source artifact | Chain | Terminal hub table | Export dialects |
|-----------------|-------|-------------------|-----------------|
| Menu/TIF/DBM PDF | A1 | core.spending_projects | MVT, GeoJSON, CSV |
| Socrata/Census | A2 | ref.* (reference only) | (reference only) |
| Terra vector PDF | B1 | core.utility_segments/points (QL-D) | DXF, MVT, 3D Tiles |
| Atlas plate / Sanborn | B2 | core.utility_segments/points (QL-D) | DXF, MVT, 3D Tiles |
| Utility DWG/DGN | B3 | core.utility_segments/points (QL-C/D) | DXF, MVT |
| Agency GIS | B4 | core.* via conflation per tier | per tier |
| Drone photos (RTK) | C1 | rasters + surface reference | COG, 3D Tiles |
| Hovermap LiDAR | C2 | point clouds + surface indicators | COPC, 3D Tiles |
| GPR | C3 | core.depth_observations (QL-B) | DXF w/ QL stamp |
| EM / Mag | C4 | core.anomalies + voxel registry | glTF isosurfaces |
| Physical exposure | C5 input | core.depth_observations (QL-A) | DXF w/ QL stamp |

---

## PART II — SOFTWARE STACK BY STAGE (with cost posture)

**Posture for a pre-seed team:** default to open-source, buy exactly three things — CAD seat(s), photogrammetry (only if ODM quality proves insufficient), and the GPR vendor software that ships with the rented/purchased unit. Everything else below has a production-grade open path.

| Stage | Open-source default | Commercial option (when to pay) | Notes |
|-------|---------------------|--------------------------------|-------|
| Portal scraping | Python: httpx, Playwright, Scrapy; sodapy | Bright Data et al. (only if blocked at scale) | Respect robots/ToS; FOIA is the Tier-2/3 "scraper" |
| PDF parsing | PyMuPDF, pdfplumber, Camelot | Azure Document Intelligence / AWS Textract (high-volume scanned tables) | Claude vision covers the hard 10% first |
| OCR | Tesseract, PaddleOCR | Google Document AI | Benchmark on 20 golden pages before choosing |
| Layout/attribute reading | Claude API (vision, structured output); LayoutLM/Donut (fine-tune later) | — | Structured-output JSON schema per callout type |
| Raster→vector | OpenCV, scikit-image, potrace; SAM/Grounding DINO | ArcScan (ArcGIS) | Prototype already proved the OpenCV path |
| Georeferencing | QGIS Georeferencer, GDAL GCP/TPS, rasterio | — | Store GCPs + RMSE as data |
| CAD | ezdxf (write/read DXF), ODA File Converter | **BUY: BricsCAD Pro (~$1k) or AutoCAD LT** — partner-facing sheets; Civil 3D only when a firm demands native objects | ezdxf does 90% programmatically |
| GIS desktop | QGIS | ArcGIS Pro (only if a city partner requires Esri round-trip) | QGIS is fully sufficient for build |
| Geo Python | GeoPandas, Shapely 2, pyproj, Fiona — Pin versions; geometry bugs are silent | — | — |
| Geocoding | Census batch, Nominatim (self-host), centerline interpolation (ours), usaddress/libpostal | Geocodio/Google (gap-fill only; check ToS re: storage) | The cascade + confidence is the moat — own it |
| Database hub | PostGIS 16 + pgvector (DuckDB+spatial for local analytics) | Managed Postgres (Neon/Supabase/RDS) when uptime matters | Start: one docker-compose; DuckDB reads GeoParquet lake |
| Tiles | martin or pg_tileserv; tippecanoe/PMTiles | Mapbox (only for their basemap styles) | MapLibre keeps you vendor-free |
| Photogrammetry | OpenDroneMap / WebODM | **MAYBE BUY:** Agisoft Metashape (~$3.5k) if ODM accuracy insufficient; Pix4D if a partner requires | Decide after 2 test flights, not before |
| LiDAR/point cloud | PDAL, CloudCompare, LAStools (free tier) | Emesent Aura (comes with Hovermap) | COPC everything |
| GPR processing | GPRPy, RGPR; custom U-Net (PyTorch) later | **BUY/BUNDLED:** RADAN / EKKO_Project with the unit | Manual picks are training data — log them all |
| Geophys inversion | SimPEG, PyVista | — | Already in the Holos stack |
| Fusion | Conflation; GTSAM; PyTorch Geometric (later) | — | Deterministic first, learned second |
| 3D twin | CesiumJS, pg2b3dm, Blender+BlenderGIS | Cesium ion (hosting convenience), Unreal (free) + Cesium for Unreal | One tileset, many viewers |
| Web app | Next.js, MapLibre GL JS, deck.gl | Vercel hosting | Review UI + public dashboard share components |
| Analytics | DuckDB, pandas, Evidence/Observable | — | need-match, cost/sq-ft live here |
| Orchestration | Claude Code + Claude Agent SDK, Postgres job table | Temporal/Prefect (Phase 3+, when DAGs get deep) | See Part III — don't buy an orchestrator yet |
| Data QC | pandera / Great Expectations, pytest | — | QC is code, in CI |
| Reports | Pandoc/Typst, Quarto | — | Markdown-native like everything else |

**Total commercial spend to reach the end of Phase 3:** roughly $1–5k (one CAD seat, possibly Metashape, GPR software bundled with hardware) plus Claude API usage and ~$50–100/mo hosting.

---

## PART III — BUILDING THE AGENTIC NETWORK (CTO step-by-step)

### Architecture in one paragraph

A **hub-and-spoke** system. The hub is PostGIS plus a Postgres-backed job queue and review queue. The spokes are (a) a **deterministic toolbelt** — the Python CLIs from Part I, (b) **five pipeline agents** (Harvester, Extractor, Geolocator, Verifier, Normalizer) that run the chains, (c) **fourteen lens agents** organized as a Product Review Council and a Trust Council that review change-sets before promotion, and (d) an **orchestrator** built on the Claude Agent SDK that moves jobs through states: `queued` → `running` → `needs_review` → `approved` → `promoted` (or `failed`/`escalated`). Humans sit at blocking gates; every agent writes structured JSON; every promotion writes provenance. Claude Code is the **development environment** for building all of this and the interactive harness for supervised runs; the Agent SDK is the **runtime** for unattended runs. Same agent loop, two entry points.

### Step 0 — Prerequisites (Day 1 morning)

**Accounts:** Anthropic API key (Claude API), GitHub org, hosting (Vercel + a Postgres host, or a single VPS to start).

**Install:** Claude Code (CLI + the VS Code or Cursor extension your CTO prefers — it also ships as a desktop app and runs headless for CI). Install Docker, Python 3.12 + uv, Node 20+, GDAL/PDAL (via conda-forge or OSGeo builds).

**Verify current Claude Code specifics** against the official docs before scaffolding — the surface moves fast: https://docs.claude.com/en/docs/claude-code/overview (subagents, hooks, MCP, Agent SDK pages). Treat any "Claude Code SDK" references found online as stale; the runtime library is the **Claude Agent SDK** (`claude-agent-sdk` on PyPI, `@anthropic-ai/claude-agent-sdk` on npm).

### Step 1 — Repository scaffold (Day 1)

Monorepo, because agents work best when everything they need is greppable:

```
holos/
  CLAUDE.md                    # the constitution
  decisions.md                 # append-only human decisions log
  .claude/
    agents/                    # subagent definitions
      harvester.md
      extractor.md
      geolocator.md
      verifier.md
      normalizer.md
    lens/                      # 14 lens agents
      surveyor.md
      excavation-contractor.md
      engineering-firm.md
      city-planner.md
      buildings-dept.md
      hydrologist.md
      geologist.md
      ai-specialist.md
      developer.md
      urban-planner.md
      trust-ouc.md
      trust-private-utility.md
      trust-cyber.md
      trust-emergency.md
    skills/                    # SKILL.md bundles for repeatable procedures
      georeference-plate/
      dxf-authoring/
      geocode-cascade/
    settings.json              # permissions, hooks wiring
  .mcp.json                    # MCP servers
  tools/                       # THE DETERMINISTIC TOOLBELT (installable pkg: holos-tools)
    holos_tools/
      harvest/
      extract/
      geocode/
      geometry/
      cadgis/
      sensing/
      validate/
      load/
  pipelines/                   # chain definitions (YAML)
  orchestrator/                # Agent SDK runtime (Python)
  db/                          # migrations (sqitch or plain SQL), seed refs
  webapp/                       # Next.js: review UI + dashboard
  golden/                      # golden fixtures: 20 PDFs, 3 plates, known-answer geocodes
  runs/                         # manifests + logs (gitignored, synced to object storage)
```

`git init`, first commit, then run `/init`-style setup by asking Claude Code to read the Master Brief and this spec and draft CLAUDE.md — then edit it by hand. **The constitution is human-owned.**

### Step 2 — Stand up the hub (Day 1–2)

`docker-compose.yml`: `postgis/postgis:16`, plus `martin`. One command, hub alive.

**Schemas:** `raw` (manifests), `staging` (agent-writable), `core` (promoted, human-gated), `ref` (city/Census layers), `ops` (jobs, runs, reviews, decisions, calibration), `marts` (analytics views).

Apply Appendix D SQL: provenance, confidence, QL, review, and job tables. **Row-level security roles from day one** (Step 13) even while the only user is the founding team — retrofitting trust architecture is how past civic projects died.

Load `ref.*` via Chain A2 so every later step has ground truth to validate against.

### Step 3 — Build the deterministic toolbelt first (Week 1)

**Before any agent exists, the CLIs must work by hand.** Each is a typer/click CLI with `--json` output, exit codes, and a pytest golden test:

```bash
holos harvest socrata --dataset 6imu-meau
holos harvest url --manifest …
holos extract pdf-tables --doc …
holos extract pdf-vector --doc …
holos extract plate --doc … --palette …
holos geocode cascade --in rows.json  # implements A1 §5 exactly, emits method+score per row
holos geometry segment --street … --from … --to …
holos geometry topology-repair --in …
holos cadgis georef --gcps gcps.json --rmse-max 15
holos cadgis dxf-write --class-map …
holos cadgis dwg2dxf …
holos validate ward-containment
holos validate centerline-residual
holos validate schema
holos load staging …
holos load promote --changeset … --require-approval
holos sensing odm-run …
holos sensing pdal-pipeline …
holos sensing gpr-picks-ingest …
```

**Why this order matters:** the agents' entire value is judgment about **when and how** to run these, plus handling the messy 15%. If the deterministic 85% isn't solid, agent behavior is untestable.

### Step 4 — Wire the MCP layer (Week 1–2)

**Three kinds of tool access, least privilege each:**

1. **Built-in Claude Code tools** (Bash, Read/Write, Grep) — how agents run the toolbelt CLIs during development and supervised runs. Constrain with permissions in `.claude/settings.json` (`allow Bash(holos *)`, `Bash(pytest *)`; deny raw `psql` writes to `core`).

2. **External MCP servers** in `.mcp.json` (project-scoped, committed): a Postgres MCP server pointed at a read-only hub role (agents query state, never mutate through it); Playwright MCP for portal navigation when the Harvester needs a browser; filesystem access stays within the repo + `runs/`.

3. **In-process SDK MCP tools** (runtime): in the orchestrator, wrap the toolbelt as typed tools with the Agent SDK's `@tool` decorator + `create_sdk_mcp_server` — no subprocess overhead, type-checked arguments, and the orchestrator can pre-approve exactly the tools each agent may call via `allowed_tools`.

### Step 5 — Define the five pipeline agents (Week 2)

Each is a Markdown file with YAML frontmatter in `.claude/agents/` (Appendix B shows two in full). **Shared conventions:**

**Narrow tools:** Harvester gets network+manifest tools only; Geolocator gets geocode/geometry/validate CLIs and read-only DB; nobody gets `core`-writing tools except the loader path behind the human gate.

**Model tiering:** bulk classification/extraction on the fast-cheap tier (Haiku-class), standard pipeline reasoning on Sonnet-class, and reserve the frontier tier (Opus-class) for the hard 5% — ambiguous plates, novel formats, escalations. Set per-agent via the `model` frontmatter field; revisit quarterly as pricing moves.

**Structured output contract:** every agent's final message is JSON matching `schemas/agent_output.schema.json` — `{job_id, status, artifacts[], metrics{}, flags[], needs_human: bool, reasons[]}`. The orchestrator refuses anything else (retry-with-error once, then escalate).

**Statelessness:** all state in the hub + `runs/`; an agent can die and be re-run idempotently from the job row.

**Agent charters (one line each):**

- **Harvester** — discover/download/manifest sources; never parses content; flags new formats.
- **Extractor** — routes each doc to a chain (A1/B1/B2/B3) and runs it to staging + extraction JSON; owns per-year adapter configs; proposes (never silently applies) new adapters when format drift detected.
- **Geolocator** — runs the cascade; owns geometry-type decisions (point/line/polygon) with reasons; anything below score threshold → review queue, never a guess promoted.
- **Verifier** — runs every deterministic validation; investigates failures (is it our bug, source error, or real-world weirdness?); writes reason-coded review items; maintains the golden benchmark score (vs. Ward Wise answer key) per run.
- **Normalizer** — enforces the master schema + controlled vocabularies; reconciles duplicates/conflicts across sources into conflation candidates (never auto-merges `core`).

### Step 6 — Define the fourteen lens agents (Week 2–3)

The lenses become **institutionalized code review for data.** Two councils, all defined in `.claude/agents/lens/`:

**Product Review Council** (runs on every change-set before human review; parallel subagents, each returns `{lens, verdict: pass|warn|block, findings[]}`):

| Lens agent | What it checks (rubric core) | Block power |
|------------|-----|---|
| surveyor | CRS declared on every artifact; GCP residual ≤ threshold; no mixed-datum Z; transform provenance present | Yes — georeferencing defects |
| excavation-contractor | Would this render usefully on an 811-style locate? Segment endpoints tied to real streets; ambiguity flagged not hidden | Warn |
| engineering-firm | QL level present + justified on every subsurface feature; nothing promoted above QL-B without exposure record; DXF layer/typology matches SUE deliverable norms | Yes — QL violations |
| city-planner | Ward/geo joins use period-correct boundaries; layers carry vintage metadata for comp-plan use | Warn |
| buildings-dept | Cross-referencable to permit/address keys; address normalization consistent with city address points | Warn |
| hydrologist | Depth values carry datum + surface reference; groundwater-relevant attributes not dropped in normalization | Warn |
| geologist | Sensor-derived features carry soil/velocity context used in interpretation; no depth without velocity assumption recorded | Yes — for C-chain loads |
| ai-specialist | Confidence populated + calibrated (Brier/reliability vs. golden set); no layer where model uncertainty is hidden by styling; extraction method recorded | Yes — missing/uncalibrated confidence |
| developer | Conflict-check queries (buffer utilities near parcel) return with confidence + QL surfaced; latency sane | Warn |
| urban-planner | Aggregations reproducible; need-match metrics documented with methodology | Warn |

**Trust Council** (runs before any promotion to a shared/published tier and before any new data-sharing integration):

| Lens agent | What it checks | Block power |
|---|---|---|
| trust-ouc | Data-ownership tags per feature class; tier assignment present; liability-sensitive layers not in public tier | Yes |
| trust-private-utility | No ingestion/derivation from private-utility records without a permission record in `ops.data_rights`; inference outputs labeled as inference | Yes |
| trust-cyber | RLS policies intact (tested); no secrets in repo/artifacts; export endpoints respect tier; consolidated-map exposure review | Yes |
| trust-emergency | Hydrant/critical layers meet accuracy floor before being labeled response-grade; degraded-confidence styling | Warn→Yes for "response-grade" label |

**Implementation notes:** each lens file's body is its rubric written as checks with pass criteria, referencing CLIs it may run (e.g., `surveyor` runs `holos validate centerline-residual`). Lens agents are **evaluators, not editors** — `disallowedTools` strips every write tool. The orchestrator fans out the councils with the Agent SDK's subagent support (or the Task tool in interactive Claude Code), collects verdicts, and computes the gate result: any block → change-set bounces to the responsible pipeline agent with findings attached; all-pass/warn → to the human queue with the verdict sheet as the reviewer's briefing. **The councils don't replace the human gate; they make the human's fifteen minutes count.**

### Step 7 — The orchestrator (Week 3)

A small Python service on the Agent SDK — resist buying a workflow engine until Phase 3:

**Job model:** `ops.jobs(job_id, pipeline, input_ref, state, attempt, budget_usd, created_by, …)` — states as in the architecture paragraph. A `pipelines/*.yaml` file declares each chain's stages, which agent owns each, and which gates apply.

**Loop:** poll `queued` → construct the agent session (`ClaudeSDKClient` with that agent's definition, in-process MCP toolbelt, `allowed_tools` pre-approval, `max_turns`, cost budget) → stream messages to the run log → parse the structured output → advance state or escalate. Idempotency key = `(pipeline, input_checksum)`.

**Fan-out:** council reviews run as parallel subagent sessions; results joined.

**Escalation:** two failed attempts, budget exceeded, or `needs_human` → review queue with full run log link. **Agents never retry past their budget.**

**Scheduling:** cron (or GitHub Actions scheduled workflow running the CLI headless, `claude -p`) for nightly harvests; the orchestrator daemon for everything event-driven.

### Step 8 — Human checkpoint system (Week 3–4)

`ops.review_items(item_id, job_id, kind, payload_ref, geometry, reason_codes[], council_verdicts, state, reviewer, decided_at, decision, notes)`.

**Review UI** (in `webapp/`): queue list → item view with MapLibre map (staging layer vs. ref layers vs. plate/plan COG underlay via TiTiler), the extraction crop image, council verdict sheet, and three buttons: approve / fix-and-approve (structured edit) / reject-with-reason. Every decision is a row and an append to `decisions.md` (human-readable audit trail — the pattern from the existing CLAUDE.md workstream, generalized).

**Blocking gates** (non-negotiable list, enforced by the loader, not by convention):
1. any write to `core.utility_*` attributes or geometry
2. any QL level assignment ≥ B
3. any new source-layer crosswalk
4. any new-format adapter
5. any promotion to `published`/`shared` tiers
6. any change to the CCD→NAVD88 constant or geocode-cascade thresholds

Spending-layer rows above confidence threshold may auto-promote to `core.spending_projects` after the councils pass — that's the Phase-1 throughput unlock — but a 2% random sample of auto-promotions is always routed to human QC to keep the calibration honest.

### Step 9 — Confidence & calibration (Week 4, then forever)

**Fields per Appendix D:** `extraction_conf`, `geocode_conf`, `registration_rmse_ft`, `association_conf`, `fusion_conf`, `confidence` (composite), `conf_method`, `ql_level`.

**Calibration loop:** the golden set (Ward Wise answer key for A; 3 fully-human-digitized plates for B; surveyed control points for C) is scored every run by the Verifier; the ai-specialist lens compares predicted confidence vs. observed accuracy (reliability curve) and blocks releases whose confidence is miscalibrated, not merely low. **Publish the calibration chart in the dashboard** — showing uncertainty honestly is the differentiator; wear it in public.

### Step 10 — Hooks & guardrails (Week 4)

Claude Code **hooks enforce** with code what CLAUDE.md requests with words:

- **PreToolUse on Bash:** deny-list (`psql .* core\.` writes, `DROP`, `rm -rf`, network calls outside the domain allowlist) — exit code 2 blocks the call and tells the agent why.
- **PreToolUse secret scan on Write/Edit** (no keys in repo/artifacts).
- **PostToolUse on the loader:** auto-run `holos validate schema` and refuse the turn if it fails.
- **SessionStart:** inject current run manifest + open decisions so agents never act on stale assumptions.

Same hook definitions load in the Agent SDK runtime, so interactive and unattended runs share one guardrail set. **Keep permissions default-deny; expand per agent as needed, never globally.**

### Step 11 — Evals & CI (Week 4–5)

`golden/` fixtures + pytest: every toolbelt CLI has known-answer tests; every pipeline has an end-to-end fixture run in CI (GitHub Actions).

**Agent evals:** a harness that replays 25 representative jobs per agent against the golden answers on every prompt/model change — score extraction F1, geocode accuracy@threshold, council false-block rate. **Prompts are code; they regress; test them like code.**

**Nightly headless run:** harvest → pipeline on new docs → council review → queue populated → Slack/email digest with metrics delta. Weekend of silence = something broke; the digest is the heartbeat.

### Step 12 — Observability & cost (Week 5)

Run logs (full message streams) to object storage keyed by `job_id`; metrics table (`ops.run_metrics`) feeding a small Evidence/Observable ops dashboard: docs processed, geocode rate, review queue depth, human-minutes per approval, $ per 1k records, calibration drift. **$ per 1k records is the metric that decides which model tier each agent deserves.**

### Step 13 — Security & tiered access (Week 5, designed Day 1)

Postgres RLS with four roles: `tier_public` (aggregates + spending layer), `tier_municipal` (ward tooling), `tier_engineering` (utility geometry with QL + confidence), `tier_admin`.

**Feature classes carry `access_tier`; exports and tile endpoints resolve through the same policies — one enforcement point.**

`ops.data_rights` registry: every source has a rights record (`public-record` / `licensed` / `permission-pending` / `prohibited`). **The trust-private-utility lens blocks any pipeline whose input lacks one.** No ComEd/Peoples Gas/AT&T-derived data enters the hub until a permission row exists — **the legal gate is a foreign-key constraint, not a meeting.**

Secrets in environment/secret manager only; agents' network egress limited to the allowlist (portals, Census, Anthropic API); quarterly access review logged in `decisions.md`.

### Step 14 — Phased rollout (maps to Master Brief §17)

- **Phase 1 (Weeks 1–6):** Steps 1–11 for Chain A1 end-to-end. Exit criteria: nightly automated run; ≥90% geocode@calibrated-confidence vs. Ward Wise benchmark; review queue < 1 human-hour/day; public ward-spending map live.

- **Phase 2 (Weeks 6–10):** analytics marts (need-match, cost/sq-ft) + accountability dashboard; developer-lens conflict-check API prototype.

- **Phase 3 (Weeks 8–14, overlaps):** Chains B1–B2 on Terra plans + 3 atlas plates; georeferencing skill hardened; DXF deliverable reviewed by the partner firm (their sign-off is the acceptance test). Consider Temporal/Prefect if DAG depth now hurts.

- **Phase 4 (Months 4–6):** Chain C field program — 2 test flights, 1 GPR day on a site with known utilities; C-chain agents + geologist-lens gating live; first fused features with honest QL-B labels; 3D twin slice in CesiumJS.

- **Phase 5:** policy applications on the accumulated hub.

---

## APPENDICES — copy-paste scaffolding

*(See the full PDF for Appendices A–F: CLAUDE.md skeleton, example subagent definitions, .mcp.json, hub schema SQL, orchestrator loop, and acceptance tests.)*

---

*Prepared as the execution companion to the Project Holos Master Brief v2. Verify Claude Code / Agent SDK surface details against https://docs.claude.com/en/docs/claude-code/overview at build time; verify MCP server package names against the registry; confirm the CCD→NAVD88 constant with a licensed surveyor before trusting any legacy Z value.*
