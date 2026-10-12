# SystemEarth public data and project options

Research date: **11 October 2026**.

We can start without company data. The strongest proposed direction is a forest-risk
history prototype for one small Brazilian region, combining public layers with
plot queries and an explicit comparison between original and encoded data. Add
incremental rechecking and a visual explanation of disagreements after the core
comparison works. The Netherlands provides a convenient alternative with official
crop parcels. No final region, stack, or implementation has been selected.

## Freedom and requirements

The [spoken guidance](transcript_rules_and_constraints.txt) explicitly allows
participants to choose the use case and dataset and use existing algorithms and
encoding methods. The [printed brief](problem_statement_reference.txt) and
[kickoff guidance](sustainability_kickoff_reference.txt) require a specific use case,
multiple layers across time and space, efficient queries, and preservation of the
information needed for plot-level decisions. The screenshot also explicitly
requests a working sample-region prototype and comparison with the originals.

Forest baselines, tree-cover loss, restricted areas, degradation, and ESG risks
are examples of relevant information. They are not a fixed menu of projects, and
every example layer is not compulsory. A map can explain the result; the storage,
query, and fidelity comparison supplies the engineering evidence. Cost estimation
is a bonus. No numeric passing threshold, mandated geography, dataset, language,
or novel algorithm is specified in the recorded brief.

We can choose public inputs, define transparent screening rules, and compute
reference answers from the original layers ourselves. We cannot discover the
company's internal rules, private reference outputs, preferred workload, or judging
weights from public datasets. Those remain questions for later, not blockers for
the public-data prototype.

## Sources for forest and land history

Access descriptions distinguish publisher documentation from the small live checks
below. Public access does not imply every dataset has the same reuse terms.

| Source | Coverage and contribution | Access and practical limits |
| --- | --- | --- |
| [JRC Tropical Moist Forest](https://forobs.jrc.ec.europa.eu/TMF/data) | Tropical forest states, annual changes for 1990–2025, degradation and deforestation years. Strong baseline for a forest-history example. | Downloadable GeoTIFF tiles; attribution required. Covers tropical moist forest, not every forest ecosystem. Use analytical layers, not the RGB map service. |
| [Hansen Global Forest Change](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2025_v1_13) | Global tree cover in 2000 and loss year through 2025, approximately 30 m. Useful independent comparison layer. | CC BY 4.0; [direct tile downloads](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html) avoid Earth Engine setup. Tree-cover loss alone does not identify agricultural conversion, and subtracting loss from the 2000 cover does not fully reconstruct forest in 2020. |
| [MapBiomas Brazil](https://brasil.mapbiomas.org/downloads/mapas-para-download-geotiff/) | Annual land cover, forest, pasture and crops; the current page lists Collection 11 at 30 m for 1985–2025 and a separate 10 m collection for 2017–2025. | Direct annual GeoTIFFs; [publisher terms](https://brasil.mapbiomas.org/downloads/) state CC BY 4.0. Raster header access tested. Pin one collection; verify file layout and regional download cost before choosing the ingestion method. |
| [INPE PRODES](https://terrabrasilis.dpi.inpe.br/en/download-files/) | Brazilian annual mapped vegetation suppression, with raster and vector products and biome-specific coverage. Adds a government monitoring source. | GeoPackage, GeoTIFF, Shapefile and spatial services. Definitions and monitoring periods differ by product; preserve them instead of silently equating them with calendar-year satellite loss. Check product metadata and attribution. |
| [INPE DETER](https://terrabrasilis.dpi.inpe.br/en/download-files/) | Dated vegetation-change alerts in monitored Brazilian biomes. Useful for replaying incoming changes. | A small GeoJSON query succeeded through the [documented WFS service](https://terrabrasilis.dpi.inpe.br/faq/). Alerts are screening evidence, not final legal findings. |
| [ESA WorldCover](https://esa-worldcover.org/en/data-access) | Global 10 m land-cover maps for 2020 and 2021. Convenient independent context layer. | CC BY 4.0; public bucket route available without signing in. The two years use different algorithms, so a map difference is not necessarily a real land-cover change. |
| [Dynamic World](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1) | Global 10 m labels and probabilities for nine classes, from 2015 onward. Useful for uncertainty and temporal-compositing experiments. | CC BY 4.0. The verified catalog route uses Earth Engine registration; do not make it a first-day dependency without access. Preserve probabilities when the rule depends on uncertainty. |

## Sources for plot geometry and reference labels

| Source | What it provides | Access and interpretation |
| --- | --- | --- |
| [Global Fields of The World](https://source.coop/ftw/global-data) | Satellite-derived field polygons for 2024 and 2025, in GeoParquet, with web-map tiles. | CC BY 4.0; catalog and a documented data-file header were accessible without credentials. These are estimated field units, not legal parcels. Current geometry can define a historical query area without asserting that the farm existed with those boundaries in every past year. |
| [Fields of The World benchmark](https://source.coop/kerner-lab/fields-of-the-world) | Field annotations, imagery and evaluation splits across 24 countries. Useful for checking boundary behavior and a second geography. | Source Cooperative; licenses vary by country, including noncommercial subsets. Choose a permissive subset explicitly rather than assuming one license covers the whole benchmark. |
| [PDOK Dutch crop parcels](https://www.pdok.nl/ogc-apis/-/article/basisregistratie-gewaspercelen-brp-) | Official crop polygons, crop codes, year and status. Excellent starting geometry for an agricultural screening demo. | Public OGC API and [bulk download feed](https://www.pdok.nl/atom-downloadservices/-/article/basisregistratie-gewaspercelen-brp-). Three 2025 records retrieved; service links Public Domain Mark 1.0. Filter crop parcels deliberately: the service also returned a landscape element. These are crop records, not ownership evidence. |
| [IGN French RPG](https://www.data.gouv.fr/datasets/rpg) | Agricultural parcel geometry and crop information for France, with dated releases. | Open Licence 2.0; official catalog links downloads. Suitable alternative to Dutch parcels; join years spatially rather than assuming every identifier remains stable. |
| [Ghana cocoa reference data](https://zenodo.org/records/16579443) | Cocoa and other land-use reference geometries collected for 2024–2025. Strong material for a cocoa classification or disagreement example. | CC BY 4.0; metadata lists a roughly 31 MB archive. The authors explicitly say the polygons are portions of farms and must not be used for compliance or legal purposes. Use them for research validation, not customer eligibility decisions. |

## Sources for restrictions and environmental context

| Source | What it adds | Access and interpretation |
| --- | --- | --- |
| [ICMBio geospatial data](https://www.gov.br/icmbio/pt-br/dados-icmbio/dados_geoespaciais) | Brazilian federal conservation-area boundaries and other agency layers. | Official downloads and services; retain product metadata and terms. Federal coverage is not a complete inventory of all restrictions. An overlap is an evidence flag, not an automatic finding of illegality. |
| [FUNAI geospatial data](https://www.gov.br/funai/pt-br/atuacao/terras-indigenas/geoprocessamento-e-mapas) | Indigenous-territory boundaries and associated status information for Brazil. | Official downloadable geospatial data and GeoServer. Preserve status and dataset date; a current boundary file cannot establish its full historical legal extent. Confirm layer-specific terms before redistributing. |
| [EEA Natura 2000](https://www.eea.europa.eu/en/datahub/datahubitem-view/6fc8ad2d-195d-40f4-bdec-576e7d1268e4) | European protected-site polygons and supporting tables, with dated releases. Pairs naturally with Dutch or French crop parcels. | Direct Shapefile/GeoPackage downloads; follow EEA product metadata and reuse terms. Overlap does not itself mean farming is prohibited. |
| [JRC Global Surface Water](https://global-surface-water.appspot.com/download) | Approximately 30 m water occurrence, seasonality and histories; the current release extends to 2024. | Direct files and attribution terms. The provider documents historical recomputation, offsets between Landsat collections, and a monthly-recurrence issue. Pin the versions and distinguish observed water from a flood forecast. |
| [Global Mangrove Watch](https://zenodo.org/records/21346456) | Mangrove extent across multiple dates; useful for a coastal habitat-change example. | Current v4.1.12 metadata and CC BY 4.0 license verified through Zenodo; raster and vector archives listed. The older [v3 page](https://zenodo.org/records/6894273) directs users to v4.1.12. Parcel geometry and a defensible local screening rule still need selection. |
| [CHIRPS v3](https://www.chc.ucsb.edu/data/chirps3) | Rainfall from 1981 to near-present, 0.05° resolution, across 60°N–60°S. Supports drought context. | Publisher provides public archive links and several file formats; retain citation and product version. Resolution is much coarser than a small farm, so do not portray rainfall as measured separately for adjacent tiny plots. |
| [ISRIC SoilGrids](https://isric.org/explore/soilgrids/) | Global soil-property predictions at 250 m and multiple depths, with uncertainty information. | CC BY 4.0; access routes linked by ISRIC. Useful context for a restoration variant; does not supply an annual soil-change history. |
| [Copernicus DEM through Earth Search](https://earth-search.aws.element84.com/v1/collections/cop-dem-glo-30) | Elevation for slope and terrain context. | Public catalog verified; honor the linked Copernicus DEM license. Treat as contextual elevation data, not annual terrain measurements. |
| [Sentinel imagery through Earth Search](https://stacspec.org/en/tutorials/access-sentinel-2-data-aws/) | Dated optical imagery for visual inspection and derived features. | Public STAC metadata access tested over Mato Grosso using `sentinel-2-c1-l2a`. Follow Copernicus terms and pin the collection. A matching scene can still be cloudy; apply quality masks and consistent preprocessing. |

## Useful sources with access or reuse conditions

- [Protected Planet](https://www.protectedplanet.net/en/legal) provides broad
  protected-area coverage, but its terms restrict commercial use and redistribution.
  Do not assume this company-facing project qualifies for unrestricted use. Prefer
  national or EEA sources for the first public demo.
- [INCRA Acervo Fundiário](https://acervofundiario.incra.gov.br/acervo/login.php)
  provides Brazilian land-parcel data but now requires a gov.br login. The service's
  description of free access does not remove that account dependency.
- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/data_availability/) supplies
  fire detections; its API requires a free map key, and some archive routes require
  Earthdata authentication. It can extend a fire-history example later.

## Access evidence

The [machine-readable checks](research/systemearth-access-checks.json) record URLs,
UTC times, response status, limited response details, and response hashes. Requests
used no credentials. These are access checks, not accuracy or performance benchmarks.

| Check | Observed result | What remains |
| --- | --- | --- |
| Dutch parcel query | HTTP 200; three polygon records with attributes | Select an area, filter appropriate records, inspect geometry and historical releases. |
| INPE DETER query | HTTP 200; three alert records | Select dates and geography; validate definitions and full source metadata. |
| Sentinel scene query in Mato Grosso | HTTP 200; one dated scene with asset references | Read imagery windows, mask cloud, and check regional usefulness. |
| MapBiomas 2025 raster | HTTP 206; valid BigTIFF header bytes | Decode a region; measure whether the file layout permits efficient reads. |
| Global FTW | Catalog read succeeded; documented France file returned HTTP 206 with Parquet signature | Decode selected regional polygons; verify quality. Earlier default-client requests returned 403; subsequent requests with the research client identifier succeeded. |
| Ghana reference data and current mangrove data | HTTP 200; licenses and downloadable archive metadata | Archives were not downloaded or quality-checked. |

## Geographic bundles

| Candidate place | Public-data bundle | Why choose it | Main limitation |
| --- | --- | --- | --- |
| Northern Mato Grosso or Pará, Brazil | JRC TMF where covered, MapBiomas, INPE PRODES/DETER, ICMBio, public field estimates, optional FUNAI | Best breadth of independent forest, land-use and dated-event sources for the proposed engineering demo. | Field estimates do not replace legal farm boundaries; choose a forest-covered area and inspect sample geometry before committing. |
| Netherlands, for example a small Gelderland area | PDOK crop parcels, Natura 2000, WorldCover, water history, Sentinel imagery | Fast route to official plot-shaped inputs and a reproducible habitat/water screening example. | Needs a clearly defined screening policy; protection overlap alone is not a violation. |
| France, for example a small Nouvelle-Aquitaine area | RPG crop parcels, Natura 2000, forest/land-cover layers, water history, Sentinel imagery | Similar parcel advantage, with room to compare crop and habitat histories. | Crop release schemas and boundaries may change across years. |
| Ghana, within cocoa reference coverage | Cocoa reference annotations, TMF, Hansen loss, Sentinel imagery | Strong demonstration of source disagreement and research validation. | Published cocoa geometries are explicitly unsuitable for compliance/legal use. Keep this an experimental benchmark. |
| Coastal Indonesia or Vietnam | Global Mangrove Watch, water history, land-cover maps, Sentinel imagery and explicitly labelled study polygons | Distinctive coastal habitat-change story and visually strong time comparisons. | Selecting usable aquaculture/land parcels and a specific decision rule takes extra work; no claims of legal or carbon certification. |

For any bundle, start with a roughly 20–50 km study area, 2020–2025 where covered,
and a proposed 200–1,000 query polygons. Those numbers are an initial experiment
size, not event requirements or a performance promise. Inspect spatial coverage
first; include both representative plots and a separately reported set of difficult
boundary, missing-data, and rare-change cases. Synthetic polygons are acceptable
engineering fixtures only when clearly labelled as such.

## Ranked project directions

Scores are engineering judgments on a 1–5 scale, where 5 is highest. Difficulty is
the work and uncertainty required, not a benefit. These are not organizer scores
or claims that no similar product exists. Every direction needs the same working
compact-representation and fidelity comparison to satisfy the track.

| Rank and direction | Brief fit | Processing depth | Visual demonstration | Differentiation potential | Difficulty |
| --- | --- | --- | --- | --- | --- |
| 1. Plot history with incremental rechecking | 5 | 5 | 5 | 5 | 5 |
| 2. Encoding comparison with an interactive error inspector | 5 | 5 | 4 | 5 | 4 |
| 3. Forest-source disagreement and uncertainty analysis | 5 | 4 | 5 | 5 | 4 |
| 4. European crop-parcel habitat and water screening | 4 | 4 | 4 | 3 | 3 |
| 5. Coastal mangrove-change screening | 4 | 4 | 5 | 5 | 5 |

### Plot history with incremental rechecking

For a plot and observation year, return a forest-state summary, mapped-change
areas by year, relevant boundary overlaps, and explicit unknowns. Preserve the
source version and rule version with the answer. Replay a new layer or alert and
identify which plots require recomputation. Compare selective updates with a full
rerun and verify that every result still agrees.

The interface can show a map and time slider, a plot's evidence timeline, an
original/encoded comparison, and an explanation of what changed after an update.
An update overlay can show affected plots and saved query work. The hard problem
is tracking spatial and temporal dependencies without missing an affected plot.
This is the best stretch direction once the reference queries work.

### Encoding comparison with an interactive error inspector

Implement a few candidate representations behind one query contract: tiled
compressed categorical rasters, packed class/flag values, and temporal event or
run-length records. Keep vector boundaries exact when rasterisation would alter
the required overlap results. Compare them against reasonably configured original
files on storage, latency, memory, preprocessing, and fidelity.

Let users select an encoding and see its storage/performance tradeoff, inspect a
mismatching plot, and locate the pixels or geometry causing the disagreement.
Lossy variants are optional experiments; the default should preserve the agreed
outputs. Stored summaries must declare which queries they support. A summary
that works for one fixed threshold may fail when the threshold or plot changes.

### Forest source disagreement and uncertainty analysis

Show where JRC, Hansen, MapBiomas, or optional probabilistic land-cover outputs
disagree after their definitions and time periods have been aligned. Keep two
separate comparisons: disagreement between input sources, and disagreement
introduced by our encoding. The first is evidence uncertainty; the second can be
an engineering error. A majority vote is not ground truth.

The UI can show source-by-source results, confidence or missing-data overlays,
and an evidence panel identifying which data drives a flag. Brazil offers several
source types; Ghana offers research labels with the limitations stated above.
This direction can strengthen the first project without becoming a separate app.

### European crop parcel habitat and water screening

Use real crop polygons and dated habitat/water layers to answer a declared policy
question, such as which parcels need review after a mapped habitat or water change.
Keep thresholds configurable and labelled as prototype policy assumptions. A batch
review table, linked map, and per-parcel timeline make the system useful to inspect.
This is the most convenient alternate region if tropical data integration stalls.

### Coastal mangrove change screening

For fixed study polygons, retain mangrove extent through time, water transitions,
and chosen conservation context. Test how compact representations preserve
habitat-change screening outputs. Show an animated coastline, before/after views,
and the source evidence for each flagged polygon. Boundary quality and rule
selection are the main uncertainties, so this is a higher-risk primary choice.

## Recommended combined project

Build direction 1's plot-history core in Brazil, use direction 2 to demonstrate
the engineering result, and add a small portion of direction 3 for explanation.
Keep incremental updates as the first stretch feature. This concentrates effort
on one reusable engine and one visible workflow.

The first query contract can preserve source-defined forest classes, mapped
change area by year, overlap area/identifiers, and missing-data coverage. Use
statuses such as "flagged for review", "no flag under these rules", and
"insufficient data". They describe the prototype's screening result. Full legal
compliance is outside what these datasets establish.

If we use EUDR as motivation, map each implemented check to the applicable
definition. [Commission guidance](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A52025XC04524)
distinguishes conversion of forest to agriculture from generic tree loss and
discusses the 31 December 2020 cut-off. Keep any policy experiment separate from
claims about legal thresholds. Farm identity, tenure, commodity traceability, and
other legal evidence are not supplied by the proposed map stack.

Use a published rule table and an original-layer evaluator as the reference.
Keep ingestion effects, grid alignment, polygon/pixel inclusion, and area
calculations consistent. Where normalisation changes source data, measure that
effect separately from encoding. Report the percentage of plots for which all
agreed outputs match, relevant pixel/geometry agreement, storage including indexes,
query latency, peak memory, and preprocessing/update work. A perfect result on the
sample means preservation on that sample; it does not validate the source maps.

## Work suitable for parallel agent tasks

Start these after the input schema and query contract are written. They are
proposed work packages; no implementation agents or compute jobs were launched
as part of this research.

| Work package | Concrete output | Review gate |
| --- | --- | --- |
| Public-data acquisition | Small regional files, provenance, hashes, licenses, quality masks and documented source dates | Files open and coverage matches the chosen region. |
| Original-layer evaluator | Independent query implementation and expected outputs for the fixed benchmark | Hand-check representative and difficult examples. |
| Encoding experiments | Several representations implementing the same queries and reporting their complete storage footprint | Compare to the original evaluator; inspect every mismatch. |
| Incremental updates | Spatial dependency index and deterministic replay of dated changes | Selective update results equal a full recomputation. |
| Interactive demonstration | Linked map, timeline, plot evidence and encoding comparison | UI values come from actual query and benchmark outputs. |
| Adversarial evaluation | Small plots, holes, slivers, partial pixels, missing data, revised observations and changed rules | Distinguish source uncertainty from transformation or encoding errors. |

Long-running work is useful for downloading selected data, comparing encodings,
testing updates and expanding benchmark coverage. It does not resolve ambiguous
decision rules automatically. Write those rules first, then let independent work
proceed against them. Validate one small end-to-end slice before expanding regions
or starting expensive training.

## Immediate next steps

1. Inspect a small Brazilian tile and its candidate plot geometries. Keep the
   Netherlands bundle available as a fallback; no company reply is needed.
2. Pin source versions and write the first query contract, including unknowns and
   the distinction between observation year and publication/version date.
3. Freeze a small public benchmark and original-layer answers before discarding
   source attributes or committing to an encoding.
4. Compare the simplest implementation with two alternatives. Add the map and
   update replay once their outputs are reproducible.
5. Keep the deliverable ready on 16 October while the exact submission deadline
   remains unresolved. Company feedback can refine the inputs and rules later.
