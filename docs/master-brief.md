# 📘 01 · Master Brief & Pitch Package (v2.1)

*A jurisdiction-agnostic pipeline that turns any government's messy public records into a living, georeferenced digital twin — above and below ground. Prepared for engineering-firm partners & investors. Founders: Charlie Foreman & Sam Brandstrader. Chicago-first • built to generalize • July 2026.*

## 1. Executive Summary

**Public infrastructure is governed by data that is trapped.** The records that decide how cities spend, dig, and build sit in non-standardized, non-digital formats — budget PDFs, hand-drawn utility maps, CAD files, Sanborn maps, scanned engineering plans. Because that knowledge is unreadable to machines and disconnected across agencies, cities dig blind, spend without knowing where the need is, and cannot see what is buried beneath their own streets.

**Project Holos converts those records into clean, geolocated, analyzable civic data, then fuses that historical record with new physical sensing to produce a living, self-updating 3D digital twin of a city — above and below ground.** Chicago is our first use case, not the product. The product is a transferable pipeline that can be pointed at any jurisdiction.

**The intellectual property is not "we understand Chicago's menu-fund program." It is a system that ingests any government's messy public disclosures and outputs clean, geolocated, analyzable civic data — with confidence scoring and professional-grade rigor built in.** We have already validated the riskiest technical assumptions on real Chicago data (see §7).

## 2. The Problem We Solve

Infrastructure knowledge is real but locked, and three failures follow:

- **Cities dig blind and waste capital.** New pavement is laid over century-old mains that then fail, forcing crews to tear the new street back up; excavation crews strike utilities nobody knew were there.
- **Spending is disconnected from need and from expertise.** Aldermen each direct \~\$1.5M/year of capital, but that spending lives in 300-page PDFs, is never compared to where need is greatest, and is managed by elected officials who are not trained planners or engineers. Some wards (44th) publish visualization tools; others (16th, 17th) offer nothing.
- **Critical facts are simply unknown.** There is no public atlas of where lead service lines are or have been replaced; the depth of buried utilities cannot be known from paper records alone.

**The cost is concrete.** A Loop real-estate project was killed because the team believed there was no room for a new fiber conduit — then, after excavating, found it would have fit between two existing pipes. The project died for lack of subsurface spacing data. Multiply that across every dig in every city, and that is the market.

## 3. The Product: A Transferable Four-Stage Pipeline

The pipeline is abstracted from any one city's bureaucracy, so it re-points to a new jurisdiction as configuration, not a rebuild:

1. **Discovery & Acquisition.** Agents pointed at any public-records portal or archive locate and download relevant documents regardless of local naming conventions.
2. **Extraction & Normalization.** OCR + AI synthesis that is schema-agnostic on ingest and schema-consistent on output — handling format drift even within one jurisdiction (Chicago's records change layout across 2012–2026).
3. **Geospatial Resolution.** Geocoding agents plus accuracy-verification agents. Genuinely city-agnostic — an address is an address.
4. **Analysis & Visualization.** Configurable per use case: ward capital-planning in Chicago; school-infrastructure funding or public-housing repairs elsewhere.

## 4. The Two Components

### 4.1 Component A — Civic Records Extraction & Geolocation

The "muni-scraper" agent stack: a Scraper agent (navigates portals, downloads documents), an OCR/transcription agent (extracts ward, category, address, cost), a Geolocator agent (attaches X/Y), a Verification agent (validates geocoding), and a Normalization agent (reconciles inconsistent yearly formats into one master schema). Output feeds a Ward Capital Planning Intelligence layer.

**Chicago instantiation:** Aldermanic Menu Fund reports (\~\$1.5M/ward/year), TIF fund records, and DBM publications. Because each ward has a finite asset inventory (alleys, streets, lights, trees, parks, schools), annual spend can be measured against total asset stock — enabling capital-improvement gap analysis and "set-to-expire" end-of-life flagging.

### 4.2 Component B — Subsurface Conditions Layer (OUC + Sensor Fusion)

Chicago's Office of Underground Coordination (OUC) federates the agencies and utilities that own subterranean assets — water mains, sewer, water service lines, conduit (fire-alarm / hydrant / streetlight circuits), fiber. Record states vary: some already GIS, some CAD-only, some hand-drawn. The digitization funnel is the same OCR + AI + human-review pipeline as Component A, but outputs geospatial formats into a spatial database.

- **Seed data — Terra.** An engineering firm, Terra, has lent real plans from a prior job site (water, sewer, fiber, water-service, some conduit, plus site and topographic surveys, as PDFs) — a live firm relationship and genuine Component B input in hand today.
- **Conversion path.** Linework extraction → CAD/Civil 3D + georeference → GIS-native into PostGIS → layout-aware OCR (LayoutLM/Donut) for annotations → mandatory human engineering review (a misread pipe diameter or depth is a safety issue).
- **Physical sensing.** Drone multi-sensor surveys — LiDAR, GPR, EM, magnetometry — calibrated across depths to estimate pipe separation/sizing, bedrock depth, groundwater, fused with the aerial/legacy view.
- **Free surface reference.** Public airborne LiDAR (USGS 3DEP / Cook County) and soils (NRCS SSURGO) give a surface-elevation reference and sensor-feasibility maps before a single flight — cutting early capex.
- **Professional standard.** GPR depths qualify as ASCE 38-22 QL-B, not QL-A — only physical exposure yields QL-A. Preserved end to end. This rigor positions Holos as a trusted partner to engineering firms, not a competitor.
- **Profile sheets — free depth.** Sewer/water plan sets contain profile views with invert elevations at every manhole — dense Z data already in the Terra PDFs at zero sensing cost.

### 4.3 The Unifying Engine — Maintenance Forecasting

Component A tells you where and when work happened; Component B tells you what is down there and how old it is. Together they form a maintenance-forecasting engine: a water line last touched in 1985 under a street not resurfaced since becomes a proactive-replacement candidate. The forecasting is survival analysis (break-probability models keyed to material, diameter, install era, soil), not a heuristic — which is why obtaining water-main break/leak history via FOIA is a first-week priority (its lead time is months).

## 5. The Core Innovation (Our Moat)

Dashboards that group spending by ward already exist — they are not the innovation. **The innovation is automated geolocation — converting a text location into real X/Y coordinates and the correct geometry (point, line, or polygon) — done accurately, at scale, across messy formats, with a confidence score on every layer.** Past civic efforts stalled because doing this by hand is impossibly slow.

Two reinforcing edges: (1) jurisdiction-agnostic — an address is an address; (2) confidence scoring and QL-A/QL-B built in, so output is trustworthy enough for engineers to act on. Ward Wise performs the conversion internally but never projects it as map geometry; our prototype already does. **A third edge is honesty as a product:** a coverage map of "known unknowns" — which blocks have any subsurface data at all — is both our credibility differentiator and our sensing sales tool.

## 6. How the System Works

A multi-agent chain — scraper → OCR → geocode → verify → normalize — writes into one central spatial database (the "hub"), in one coordinate frame, that every product reads from. Human checkpoints sit at safety-critical steps. A confidence score propagates through every layer.

**Coordinate rule:** lat/long (EPSG:4326) for web maps and Illinois State Plane feet (EPSG:3435) for engineering math.

- **Confidence, decomposed.** Three numbers — existence, attribute correctness, and positional accuracy in feet — aligned to ASCE 38 quality levels, shown, never hidden.
- **Physics as free QC.** Gravity sewers flow downhill, mains come in standard diameters, hydrants sit near mains — encoded as deterministic validators that catch extraction errors at zero ML cost.

## 7. What We Have Already Proven

On real Chicago data, we have validated the pipeline end-to-end with honest measurement and correctness verification:

### Component A — Menu-Fund Spending Extraction & Range Geocoding (Validated)

- **Extraction recall: 99.3%** — 145 of 146 records hand-counted from 2012Menu.pdf pages 2–20 captured correctly (ward, category, location, cost).
- **Range geocoding: 72%** — 79 of 109 address ranges ("ON STREET FROM X TO Y" format) geocoded successfully, validated to produce street-level geometries.
- **Correctness verified: 95%** — Spot-check of 20 geocoded ranges against ground truth shows 95% land on correct streets; no false-positive centroids detected.
- **True end-to-end accuracy: 68%** — Composite of extraction (99.3%) × range geocoding (72%) × correctness (95%).
- **Failure analysis**: All non-geocoded cases are deterministic and fixable — no hard data-ceiling:
  - 21 incomplete extraction (PDF wrapping, coordinates); 9 parser gaps (abbreviated street names); 0 genuine centerline gaps.
- **Technology proven:** ST_Intersects on MultiLineString centerline segments + ST_Centroid for robust intersection detection, handling Chicago's real-world messy street geometry.

### Component B — Digitization & Attribute Reading (Validated)

- **Subsurface extraction, working.** From a real water-atlas plate, 552 mains and 381 hydrants/valves extracted automatically with computer vision; blue-text-from-blue-lines separation solved.
- **Attribute reading, working.** A vision model read dense engineering callouts and surfaced depth cues ("4′ TO 5′ COVER") hiding in the text.
- **CAD + QC, working.** Extracted geometry exported to a valid layered AutoCAD DXF in State Plane feet, validated against the city's real street centerlines.

**Translation:** The menu-spending pipeline is production-ready for Phase 1C review (range geocoding is the engine; 68% is honest and measured). Component B digitization is prototyped and ready to scale. The riskiest assumptions — address-range geocoding at scale and format-variant handling — are de-risked.

## 8. Applications (Configurable on One Pipeline)

- **Ward capital-planning intelligence** — one view of what's buried, how old, and what's been spent.
- **Civic accountability & cost analysis** — menu-money transparency; need-match score; cost-per-square-foot analysis testing whether contractors charge different rates by neighborhood.
- **SUE subcontracting for engineering firms** — plug into existing workflows; valve-isolation tracing is a directly sellable water-department feature.
- **Real-estate developer due diligence** — instant utility-conflict checks before land acquisition (the Loop problem, solved pre-dig).
- **Emergency response & public safety** — exact hydrant/gas-line locations affect response time and life safety.
- **Green infrastructure & policy (vision)** — siting permeable pavement, bioswales, tree canopy; urban-heat mitigation.

## 9. The Market: A Three-Tier Model

- **Tier 1 — Advanced & public (Chicago).** Full open-data portal; our sandbox and QC benchmark.
- **Tier 2 — Advanced but gated (Oak Park).** A real portal exists but access is by request/relationship.
- **Tier 3 — The long tail (Blue Island, Calumet City, West Chicago, Elgin).** No portal, records never digitized — the largest, most underserved market, ignored by the funded players.

**The engineering-firm partnership is the key that unlocks Tier 2/3 access and field-data collection — as important as the technology.**

## 10. Organization & Stakeholder Lenses

Seven departments carry the build; eleven stakeholder lenses keep each grounded in a real end user — doubling as the go-to-market and governance map.

| Department | Focus | Stakeholder lenses |
|---|---|---|
| 1 — Data Acquisition | Scraper agents + drone flight ops | Surveyor (ground control points); Excavation contractor (811-ticket caller; dig requests are data) |
| 2 — Digitization & Extraction | OCR/AI of PDF, CAD, Sanborn | Engineering-firm owner (plug into SUE; preserve QL-A/B; subcontractor not competitor) |
| 3 — Geospatial Engineering | GIS, CAD-to-shapefile, PostGIS | City planner (zoning/comp plan); Buildings dept (permits/inspections) |
| 4 — Sensor Fusion & Geophysics | GPR, EM, magnetometry, LiDAR | Hydrologist (groundwater → corrosion); Geologist (soil/bedrock → sensor accuracy) |
| 5 — Visualization & Digital Twin | 3D (Unreal / Blender / CesiumJS) | AI specialist (confidence on every layer; never hide uncertainty) |
| 6 — Analysis & Policy | Capital plans, green infra, heat | Real-estate developer (due-diligence = paid); Urban planner (comp-plan) |
| 7 — Quality Control & Trust | Human review + agent QC + access | OUC agencies (ownership/liability, tiered access); Private utilities (legal gate); Cybersecurity; Emergency responder (life safety) |

## 11. Competitive Landscape

| Company | What they do | Where we differ |
|---|---|---|
| Exodigo | Field sensors (GPR) + AI subsurface; \$96M Series B | We fuse legacy records + public money; partner with firms rather than replace fieldwork |
| 4M Analytics | AI conversion of legacy records → CAD; conflation | We add public-spending fusion, cost accountability, small-municipality long tail |
| Mach9 | AI-native CAD; LiDAR surface extraction (YC) | Surface-focused; we own subsurface + money + civic |

**Our lane:** a jurisdiction-agnostic records-to-twin pipeline fusing subsurface + public money + accountability, positioned as a trusted engineering-firm partner, reaching municipalities the funded players won't serve.

## 12. Governance, Trust & Legal

- **Tiered access, not one public layer.** OUC agencies carry data-ownership and liability concerns — access tiered by role.
- **Private-utility legal gate.** ComEd, Peoples Gas, AT&T own much of what's buried — mapping needs permission. A legal gate, not just technical.
- **Cybersecurity.** Consolidated critical-infrastructure maps are high-value targets; access control designed in from day one.
- **Confidence & human review.** Every layer carries a confidence score; safety-critical attributes pass human review; QL-A vs QL-B preserved.
- **Standards & interoperability.** Schema mapped to ASCE/UESI 75-22 and tracking OGC MUDDI conformance, so exports are legible to any firm or national program.

## 13. Data We Need

| Data | Source & ID | Years | Status |
|---|---|---|---|
| Menu (AMP) spending | Ward Wise; OBM/DBM CIP PDFs | 2005–2023 (+2024 partial) | In hand / geocoded |
| AMP PDFs (recent) | Founders' files | 2012–present | In hand — fills 2024–26 |
| TIF fund records | Chicago DBM / portal | Historic–present | To ingest |
| 311 service requests | Chicago portal — v6vf-nfxy | Dec 2018–present | Available |
| Ward boundaries (2023 + prior) | Chicago portal — p293-wvbd (+prior) | 2003–present | 2023 available; prior to confirm |
| Street center lines | Chicago portal — 6imu-meau | Current | Available (QC + geocode) |
| Income / demographics | US Census ACS 5-year | \~2009–present | Available |
| OUC utility records | Office of Underground Coordination | Historic–present | To obtain |
| Terra engineering plans | Partner firm (seed data) | Prior job site | In hand (PDF) |
| Sanborn / legacy maps | Archives / library | Historic | To source |
| Private-utility records | ComEd, Peoples Gas, AT&T | Current | Legal gate |
| Water-main break/leak history | Chicago DWM (FOIA) | Historic–present | FOIA now — forecasting labels |
| Airborne LiDAR | USGS 3DEP / Cook County | Recent | Free — surface reference |
| Soils | NRCS SSURGO/gNATSGO | Current | Free — sensor-feasibility |
| Interceptor sewers | MWRD (separate agency) | Historic–present | To obtain |

## 14. Tools & Technology

| Layer | Tools | Role |
|---|---|---|
| Agents / ETL | Python, agent orchestration, pandas/geopandas/pyproj | Scrape, extract, normalize, geocode |
| Extraction | OpenCV, PyMuPDF, raster-to-vector, LayoutLM/Donut, Claude vision | Records → geometry + attributes |
| CAD / GIS | AutoCAD / Civil 3D, QGIS, GeoPackage/shapefile | Engineering-native + GIS export |
| Database (hub) | PostGIS (DuckDB to start) | Single spatial source of truth |
| Web & 3D twin | Next.js + MapLibre; CesiumJS; Unreal/Blender (eval) | Dashboards + 3D |
| Field sensing | Drone LiDAR, GPR, EM, magnetometry, RTK GPS | Depth / Z-axis (QL-B) |
| Build environment | Claude Code in Cursor | AI-assisted development |

## 15. The Gaps — and How We Close Them

| Gap | Why | How we close it |
|---|---|---|
| Georeferencing accuracy | Hand-drawn plates distorted; naive corner-mapping off by \~a block | Control-point registration; validate residual vs. centerlines; carry confidence |
| Network topology | Extraction yields disconnected segments | Snap/merge into a connected graph at intersections |
| Attribute association | Reading a callout ≠ attaching it to the right feature at scale | Layout-aware OCR + per-feature vision + human review |
| Scraper generalization | Every jurisdiction differs (Tiers 1–3) | Modular per-source harvest; benchmark vs. Ward Wise before trusting new cities |
| Data access & rights | Gated portals, undigitized paper, private ownership | Firm partnership, FOIA, negotiated permissions |
| Depth (Z-axis) | Not in paper records; QL-B only from sensing | Drone GPR/EM/LiDAR; preserve QL-A vs QL-B |
| Sustainability | Public-good tools hard to monetize alone | Multi-buyer: firms, municipalities, developers, grants |

*(Full 18-item engineering backlog lives in the Build Backlog & Gap Register.)*

## 16. Chicago Proof-of-Concept Sequence

1. Use Terra's legacy plans as subsurface seed data.
2. Cross-reference against OUC records to fill gaps.
3. Run the muni-scraper stack against menu-fund / TIF / DBM publications (2012–2026) for the surface spending layer.
4. Deploy drone sensor passes over target wards — prioritizing wards with no existing tools (16th, 17th).
5. Deliver a tool where an alderman's office sees what's buried, how old, and what's been spent.

## 17. Roadmap

- **Phase 1 (now).** Component A Chicago MVP — automated workflow end to end, benchmarked vs. Ward Wise; ships the ward-spending map.
- **Phase 2.** Capital-planning intelligence + cost/accountability analytics.
- **Phase 3.** Component B digitization at scale — georeferencing fixed first, then Terra + OUC into PostGIS.
- **Phase 4.** Field program — drone GPR/LiDAR; the fused 3D subsurface twin.
- **Phase 5 (vision).** Policy applications — lead-line prioritization, green-infra siting.

## 18. Business Model & Sustainability

- **Engineering firms & municipalities.** SUE subcontracting, records digitization, subsurface data — the primary commercial engine.
- **Real-estate & private sector.** Utility-conflict due-diligence as a fast paid product.
- **Civic & grants.** Accountability analytics for watchdogs/journalists/campaigns; grants fund the public-good layer.

## 19. Open Design Questions (CTO Build Agenda)

- Artifact-to-format decision matrix (photo / PDF / Sanborn / CAD → canonical target).
- Agent-orchestration architecture (scraper → OCR → geocode → verify → normalize; where human checkpoints sit).
- Confidence-scoring schema propagated through every layer.
- Visualization-engine selection (Unreal vs Blender vs CesiumJS).
- Tiered-access / data-rights architecture from the start.
- Master schema for the normalized civic-records dataset, jurisdiction-agnostic.

## 20. The Ask & Next Steps

From an engineering-firm partner: Tier 2/3 access, records, field-data collaboration, and an SUE subcontracting relationship. From investors: capital to turn the validated Chicago prototype into a repeatable multi-city product and stand up the field program. Immediate build: the Phase 1 Component A workflow.

## 21. Cautions & Ethics

- **Variation is not automatically corruption.** Asphalt pricing varies legitimately; cost tools surface questions with traceable methodology, not accusations.
- **Lead-line inference is probabilistic.** A prioritization aid, never a published claim about a specific address.
- **QL-A vs QL-B is a liability line.** GPR depths are estimates (QL-B); only physical exposure is QL-A.
- **Verify volunteer & third-party data.** Ward Wise and Terra plans must be validated before any public/engineering claim.
- **Licensing discipline.** Only public-domain references stored as authoritative geometry; OSM cross-check only (ODbL). Output license chosen deliberately.
- **Professional liability.** SUE deliverables carry a licensed PE/PLS in responsible charge; E&O exposure named and insured.
- **FOIA reality.** Expect partial denials on consolidated utility maps under security exemptions — the partner-firm route is the workaround.

## 22. Glossary

| Term | Meaning |
|---|---|
| Digital twin | A live, data-rich virtual model of a real place — here, the city above and below ground. |
| Geolocate / georeference | Assign real-world coordinates to a record so it maps correctly. |
| Point / line / polygon | Geometry types: a spot, a segment, an area. |
| OUC | Office of Underground Coordination — federates Chicago's subterranean asset owners. |
| SUE | Subsurface Utility Engineering — the discipline of locating buried utilities. |
| QL-A / QL-B (ASCE 38-22) | Utility data quality: QL-B = estimated (GPR); QL-A = verified by physical exposure. |
| TIF | Tax Increment Financing — a Chicago funding source alongside menu funds. |
| Menu money (AMP) | The \~\$1.5M/year each alderman directs to local capital projects. |
| GPR / EM / magnetometry | Subsurface sensing methods that detect buried objects and estimate depth. |
| LiDAR | Laser scanning for precise surface/structure geometry. |
| Sanborn map | Historical fire-insurance maps — a legacy record source. |
| PostGIS | A spatial database — the project's central hub. |
| Confidence score | A machine estimate of how certain a layer is — shown, never hidden. |
| 811 ticket | A pre-dig utility-locate request — both an end user and a data source. |

---

*Master Brief v2.1 — the pitch layer of a three-document set: read alongside the Technical Build Specification and the Geolocation Automation Runbook, with the Build Backlog & Gap Register tracking open engineering items. Standards status (ASCE 75-22, OGC MUDDI) per public sources as of July 2026; verify at build time.*
