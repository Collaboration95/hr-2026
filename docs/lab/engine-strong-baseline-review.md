# Lead decision: accept the additive standard-format comparison

The optimized standard GeoTIFF control is **532444bytes including its required manifest**, compared with **535012bytes for the retained custom store**. It is2568bytes/0.480%smaller on the exact same supplied Hansen chip. This storage comparison is accepted as additive evidence. Do not replace the frozen Hansen choice, benchmark, run or17plotartifact, and do not claim the custom format beats optimized standard storage.

Lead independently read the actual controlTIFFs through rasterio, without the worker's decoder, and compared every rawbandvalue, bandmask, nativegrid and reconstructionmetadata with pinned source. All2234196rawvalues/masks match. All17queries match source and the independent scalaroracle. Actual required files independently sum to532444bytes forblock256 and537920forblock512. Real masks are allvalid; the worker's separate tests cover independently different masks/rawmaskedvalues. Rasterio/GDAL is shared, not an independent implementation of TIFF decompression. Reproduction: `.venv-data/bin/python -B data/experimental/lead/review_strong_storage.py`; recorded evidence is data/experimental/lead/strong-storage-review.json. Lead also reran all19worker tests successfully.

## User-facing comparison for Hooke

| Same native Hansen AOI representation | Required bytes | Interpretation |
| --- | ---: | --- |
| Provided DEFLATE chips + acquisition provenance | 585293 | Actual source-loader input |
| Retained custom separate-band Zstd19 | 535012 | Frozen accepted comparison path |
| Optimized standard GeoTIFF Zstd19, predictor1, block256 | 532444 | Strongest reviewed standard control;0.480%smaller than custom |

Each encoded total includes its own necessary metadata/index/masks. The symmetric common-input view includes identical acquisition provenance and exactplotinputs: source604558, custom562571, standard560003bytes. Sourcealreadycontains the acquisitionprovenance, so it is not counted twice. No crop, fulltilecache or unusedmetadata padding enters these numbers.

Suggested wording: “The retained custom encoding preserves all pixels and query results and reduces storage versus the supplied DEFLATE inputs. A separately tested optimized GeoTIFF is another2568bytes smaller. Format choice depends on loading, window access and integrity policy.” Keep the strongcontrol clearly separate from the frozen accepted benchmark. This is one seenAOI, not a universal format ranking.

## Performance tradeoffs, same additive run

Median17querybatch milliseconds: fullpreloaded source1.526/custom1.476/standard1.480, so no meaningful hotquery advantage. Processcold full-load+queries source11.163/custom5.867/standard8.498: customloads faster here. Indexedhot source2.425/custom27.717/standard1.991; currentTIFFreader retainsGDALblocks, while customredecodes and verifiesselectedchunkhasheseachquery. Those differentcache/integritypolicies materially affect the indexedcomparison. No inherentformat-only speedclaim. Standardindexed processcoldmedian7.735ms butp95=15.675ms, worse than sourcep95=10.061; preserve theoutlier. Sevenreps, twowarmups forhot, nearest-rankp95=max; uncontrolledlikelywarmOScache, notdiskcold. Network/UI excluded.

Single freshencode measurements: custom210.568ms/101.6MBpeakRSS versusstandard302.488ms/163.7MBpeakRSS. PeakRSSincludesinterpreter/imports/sourcearrays, notincrementalcodec memory. Oneencoding sample andoneAOI do not establish robustthroughput orpopulationconfidence. Workerreport and archivedJSON preserve wall/CPU/rawsamples/resources/settings.

## Proof hardening remains open

The canonical storage/pixels/results above are valid independently of a verifier typebug. Lead's clean-copypositive passes, but a rehashed artifact with integer1in `proof.raw_values_equal` and `comparisons[0].equal` also passes because Python dict equality conflates1andTrue. Reproducer: data/experimental/lead/review_strong_proof.py; recordedoutputstrong-proof-review.json. No canonicaldata corruption is alleged. Requested W3fix: strictstructure/types, completecontrolsettings, finite nonnegative correctlysizedtimings, positive+rehashednegativecontrols; refresh additivecodefingerprintedrun only. ExistingacceptedHansenproof is unaffected. Do not mark this newverifier hardened until leadrecheckpasses.

Correction after independent audit: `differing_fields` comes from `engine.benchmark`, already fingerprinted. Lead confirmed its actual module; the earlier claim of a missing `engine/export.py` dependency was mistaken and is withdrawn. The six independently reproduced type/sample-count/negative-time/settings/control-set failures remain the bounded revision scope.

## Packaging

`.venv-data/bin/python -B -m engine.package_control` creates artifacts/strong-baseline-bundle-manifest.json. It includes this currentcontrolrun and bothcurrentstores, source/cohort/code and the specificretainedHansenproofdependencies (including itsmeasuredcandidatefiles); nohistoricalstores/fulltilecaches. Currentproofpositive andindependentstoragecheck must pass before inventory. Regenerate after W3hardening andfinalreport, then run clean-copyCLIverification. Packaging/inventory grants no publicationpermission for companyinputs.

Current review inventory is43files/3718216bytes before this note. A disposablecopy of exactlythemanifestfiles passes `.venv-data/bin/python -B -m engine.strong_baseline --verify artifacts/strong-baseline-v1.json`; evidence data/experimental/lead/strong-bundle-smoke.json. Noacquisitiontile/historicalstores are present. Inventorybytes maychange with report/codeupdates; use the regeneratedmanifest as authority, not this historicalsize.

## Early-stop checkpoint: bounded revised gate

Current revised artifact `exp-7daaf163af701f29eefac7f988a7b556ec9e9c84c74417af11bc9d72691e9ebc` passes actual verifier. Lead ran only RealControlTests.test_fresh_positive_and_six_validator_rehashed_controls: pass1.194s, with fresh positive and allsixself-consistentforgeries rejected. No new benchmark or broad suite was launched by lead. Independent final recheck and worker final report remain pending at this checkpoint; do not claim them complete. Current control inventory is provided for master review, preserving the unchanged accepted Hansen run.

## Final focused lead acceptance

Final worker report read. The fresh current artifact passes. Lead reran the single focused test with12rehashedcontrols, including allsixvalidatorreproductions: pass1.432s. Lead also reran its own disposable-copy reproduction: freshpositive exits0; integer-for-boolean forgery exits1 specifically at control proof reconstruction. This closes the lead's typed-proof blocker. Worker reports20tests and compilechecks passing; the lead did not rerun that broad suite during shutdown. No fresh Feynman execution is claimed.

Accepted additive revision: exp-7daaf163af701f29eefac7f988a7b556ec9e9c84c74417af11bc9d72691e9ebc, run-88872a2c4746ed0a2f0666e538712c8334f65ef8316cf952c0cb2428ad10332c. Current bytes remain532444/537920 for standard256/512 and535012 for immutablecustom. Use currentarchive for timings; historicaltimingtable above belongs to its labelledolderrun. Finalcontrolinventory regeneratedafterworkerreport. Independent finalrerun remains optionalmastergate, not completedwork. Lead stops here.
