# Bounded spatial-rule sensitivity study — Sol worker assignment

Master may resume W2 or dispatch an available Sol high worker. This is **additive research**, not a production contract change. Own only `data/experimental/spatial-sensitivity/` (scripts/tests/JSON/witnesses) and `docs/lab/engine-spatial-sensitivity-report.md` (optional same-prefix results JSON). Do NOT edit any engine/core/app/canonicalartifact/source/other-worker files. No Git mutations, downloads/dependencies, private uploads/publication/messages/cloud spend or extra agents.

Read docs/lab/research-agenda.md, interface-v1.md, acceptedengine-report.md, and actual source/plot guidance. The supplied declarations are not groundtruth and their historical sourcevintage/company inclusionrule are unknown.

## Scientific question and frozen alternatives

On the same17unaltered supplied polygons, same pinned Hansen2025v1.13nativegrid/rawvalues/masks and periods2021–23/2024–25, compare:

1. Accepted `center_covers`: select nativecellcenters covered bypolygon (existingengine.query.select_cells/evaluate).
2. `positive_area_overlap`: select nativecellfootprints whose intersection with polygon has **strictly positive area**. Exclude point/edge-only contact explicitly. Preserve holes/multipart. No buffers, geometrysimplification, centroid approximations, resampling or thresholdtuning to matchdeclarations.

The second rule is intentionally different; differences are **rule sensitivity**, not encodingerror and not the earlier shifted-window1ULP implementationbug. Construct allfootprints from original chipaffine/grid and preserve globalrow/col. Include out-of-chip selectedcells asunknown; do not clipawayunknown support. Follow same masked-validland/histogram/tri-state reduction contract via core summarize_selected if useful; no alterations to its semantics. Counts remain selectednativecells, not hectares.

Use GEOS intersection area>0 or an equivalent interior-intersectiondimension2 predicate. Cross-check membership using a distinct predicate and exact analytic boundary fixtures; disclose shared GEOS topology/geometry implementation. Do not call two aliases of the same helper an independentoracle. An independent scalar polygon/rectangle clipping check on simplefixtures is useful if bounded, but no newlargegeometrylibrary needed.

## Required outputs

A deterministic CLI/researchscript under ownedpath loads current source/store/17plots, records inputgeometry/code/rulehashes and full queryoutputs forbothrules. For EACHrule compareoriginalvsacceptedcompact arrays/queryresults exactly; a source/compactfailure must block anypositive fidelityclaim. Productioncenteroutputs must match existingcanonicaldemo. Results include:

- perplot selectedcellcounts, selectedvalidland, mask/unknown/outside counts; fullcanopy/yearlyloss histograms including0; periodobservedlosscellcounts and tri-stateflags;
- center-only and overlap-only cellsets (center should generally be subset for valid nonzeroarea polygons; explicitly investigateanycounterexample instead of assuming);
- zero-area-touch cellcounts separately, not analyticalselectedsupport;
- any changed periodflag with concrete nativecell witness: plotID, exactoriginalpolygon, row/col, footprint, center, rawcanopy/lossyear/datamask/masks and inclusiondecisions;
- optional intersectionfraction ofnativecell in geographiccoordinates, clearly dimensionless angular-area fraction, never surveyed area/hectares or weighted loss area;
- comparisonwith the five supplier-declared indicationIDs is descriptive only: does this rulechange create anymapped2021–23signal on thoseIDs? Do not label either rule as the company'srule, treatdeclarations aslabels, or optimize foragreement.

Keep17realcohort and syntheticfixtures in separate sections/files/denominators. If noflag changes or no supplier-indication difference isexplained, reportthe negative resultplainly. No newregulatory/compliance verdict.

## Boundary and adverse fixtures

Separate exact/dyadic syntheticcases: tinyplotwithnopixelcenter butpositiveoverlap; parcel exactlyequaltoa cell; point-only contact; sharededge-onlycontact; exterior/holeboundaries; holeinterior; multipartislands; out-of-chip partialsupport withabsence→unknown and witnessedpositive→true; invalidmask/nodata/water; diagonal/sliverintersection; zeroareageometryrejection. Preserve rawmaskedvalues. Exercise currentnative-decimalgrid nearboundaries to keep intentionalrulechoice distinctfromfloating-origin shifts. Avoid anytolerance that silentlychangestherule; explainmachineprecisionlimits.

## Bounds and handoff

Use originalinputs readonly, acceptedstore immutable. No recompilation/re-encoding isnecessary. Aim firstfull17plotoutput and witnesses within20minutes, finalreviewable tests/report within30–40minutes. Useful graph/table or self-containedSVGwitness isallowed inowned researchscratch; noimagegenneeded for exactdata geometry. Include runnablecommands, source/codefingerprints, measuredcounts, allmismatches, uncertainty and adoptionrecommendation. Lead will review; no default-querychange is authorized. Completedworker mayclose afterreport.
