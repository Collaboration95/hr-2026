# Source-only spatial codec selector — bounded study for Volta review

**Decision: retain this as experimental evidence; do not integrate the selector.**
Within the existing engine's level3 candidates, the frozen selector saves
**10,417 bytes / 1.17%** on the complete heldout package. A fixed optimized
GeoTIFF at the same level is nevertheless **10,217 bytes smaller** than the
selector. Allowing existing levels 3/9/19, selection instead loses
**400 bytes** to strong fixed level 19. A separate optimized-GeoTIFF audit also
beats the currently retained AOI store by **3,059 bytes / 0.57%**. The latter is a
baseline challenge for the lead, not a changed canonical result.

## Early pilot checkpoint — preserved

At **02:45:52 UTC**, 12 training patches from six spatial regions had been
measured. Native patch size was 512×512; land fractions ranged from 0 to 0.99968.
All **312** candidate/control full roundtrips and sampled windows were exact.
Fixed optimized GeoTIFF level19/predictor1/chunk256 totaled **311,705 bytes**,
smallest on this pilot. That early total excluded global index and model costs;
no deployment win was claimed. Final holdout pixels/features/outcomes had not
been requested at that checkpoint. `pilot-results.json` preserves it.

## Hypothesis and method

Hypothesis: a cheap, interpretable rule learned from measured exact-compression
costs can choose codec/chunk size better than one fixed configuration, without
losing any raw band or validity-mask value. Compression outcomes are the labels.
No supplier declarations, the 17 plots, compliance predictions or LLM training
are involved.

Read the charter/interface, W1/W3 reports, codec implementation, project source
guidance and original acquisition provenance. Writes are confined to
`data/experimental/selector/` and this report. Existing code was imported
read-only, with `-B` to avoid bytecode writes. No dependencies, source files,
canonical stores/artifacts, Git state, app or production engine were changed.

The manifest was registered **02:45:40 UTC**, before any patch outcomes.
Seed **20261013** selects six geometrically stratified, nonoverlapping,
native-grid-aligned 512-cell patches in each of 12 macroregions of the existing
Hansen GFC2025/v1.13 `10N_090E` tile's eastern belt. Adjacent macroregions have
at least 1,000 native cells of separation. Patches intersecting the already-used
supplier bounding chip were excluded by geometry, before inspecting content.
Three source-file SHA-256 hashes match `data/public/provenance.json`; all exact
coordinates, bounds, grid, source identities and settings are in the manifest.
Sampling did not screen for easy water, land or codec performance.

Six entire regions train the rule (**36 patches**), three validate model depth
(**18**), and three form the sealed final holdout (**18**). The frozen policy
was written **02:46:43 UTC**; first holdout measurement was **02:46:49 UTC**.
No holdout feature, cost or pixel window was used to fit or choose a policy.
Source hashing reads compressed bytes, and GDAL may internally decode complete
strips; only requested development windows were exposed to the fitting process.

Eight features use a fixed stride16 sample (32×32 cells), including canopy/loss
entropy, land/water fractions and neighbor-change fractions. A cost-sensitive
tree chooses each leaf's minimum aggregate **complete patch-store bytes**.
Depths 0/1/2 are fit on training data; validation selects depth including
serialized inference-model bytes. Fixed comparators choose minimum total bytes
on all training+validation data. They were also the posthoc best fixed choices
on holdout, so the comparison does not depend on a weak fixed baseline.

Bounded candidates: all six existing codecs × chunks128/256/512 (**18**).
Separate primary and secondary analyses keep compression level matched:
level3 codec/chunk selection and level19 chunk selection. The exploratory joint
analysis allows levels3/9/19 and reports its CPU tradeoff explicitly.
Eight GeoTIFF controls use levels3/19, predictors1/2, and blocks256/512;
one fixed control is selected on development data. Settings follow
[official GDAL documentation](https://gdal.org/en/stable/drivers/raster/gtiff.html):
Zstandard compression, band interleaving, horizontal differencing when requested,
and one compression thread. All-valid masks are implicit only after verification;
the wrapper otherwise preserves three independent mask arrays. Every retained
TIFF carries the identical source metadata JSON used by the codec store.

## Final heldout measurements

Bytes below include every actual query-package file: patch payloads, native grid,
per-stream indices/checksums, global patch index/schema, original 8,294-byte
acquisition provenance, and the inference model when present. No trained
dictionary is used. Per-patch choices are already represented in the codec
indices and global index; their actual serialized bytes are included. Runtime
code/libraries are excluded equally; script bytes are separately disclosed.

| Frozen policy/control | Fixed engine package | Selected/control package | Selected minus fixed engine | Store-only regret to offline oracle |
| --- | ---: | ---: | ---: | ---: |
| Level3 codec + chunk | 894,134 | 883,717 | **−10,417 / −1.17%** | 2,124 |
| Level19 chunk | 810,764 | 811,038 | +274 / +0.034% | 0 |
| All existing levels | 810,764 | 811,164 | **+400 / +0.049%** | 4,580 |
| Fixed optimized GeoTIFF19/p1/256 | — | **806,058** | — | outside engine-candidate oracle |
| Fixed optimized GeoTIFF3/p1/256 | — | **873,500** | — | outside engine-candidate oracle |

The level3 stump is: sampled canopy entropy **≤0.846373 bits → uint16/512**;
otherwise **separate bands/256**. Fixed level3 is separate bands/512. It wins on
15 patches and loses on three, saving 10,753 patch-store bytes before model/global
cost differences. The 362-byte model plus global-index differences reduce the
net saving to 10,417 bytes. Water gains 4,477 bytes, land gains 6,743, and mixed
patches lose 467. The result is not solely an easy-water demonstration.

The additional matching-level GeoTIFF3 control is chosen solely by development
costs from four settings already registered/measured in the original experiment.
This comparison was added after challenge, without changing any model or using
holdout costs to choose the control. Its complete 873,500-byte package is
10,217 bytes / 1.17% smaller than the learned level3 package. Thus selection
improves the engine family but does **not** establish a win over the stronger
matching-level GeoTIFF control. Its additional 18 source-reread full roundtrips
and 270 window reads passed; evidence is `matching-level-control.json`.

Level19 chose depth0, separate bands/512 everywhere, which is also the actual
per-patch oracle winner within its three chunk choices. Carrying a constant
selector costs an unnecessary 274 bytes; retain the ordinary fixed store.
The joint stump uses uint16/512 below the same threshold and separate19/512
above it. Its water gain of 4,388 bytes is erased by **4,500 bytes lost on mixed
patches**. Its largest error, `R3C0-B00`, is 3,298 bytes worse than fixed19.
An offline oracle sees actual encode outcomes; its bytes are an upper-bound
comparison within the named family, never deployment performance.

Coverage composition matters: train has 22 water-dominated, six mixed and eight
land-dominated patches; validation has ten water and eight land, **zero mixed**;
holdout has ten water, five mixed and three land. Strata use ≤1%/≥99% land,
descriptively. Validation's missing coastal regime helps explain why its chosen
joint policy loses in the heldout coastal challenge. No rule was retuned afterward.

Region totals for level3 selected-minus-fixed patch bytes are −3,774, −3,684 and
−3,295. A three-region resampling interval is [−11,322, −9,885] bytes before
model/global differences. Joint selection's corresponding interval is
[−6,774, +7,926]. These are descriptive small-cluster intervals, not robust
population confidence bounds. One source tile, spatial autocorrelation and only
three test regions sharply limit generalization; millions of cells are not
millions of independent examples.

## Costs, exactness and failures

Heldout features cost **1.837 ms wall total**; tree walks cost **0.013 ms** for
level3. Encode totals are **20.935 ms wall / 20.801 ms CPU** selected versus
**19.992/19.908** fixed3, excluding shared source loading. Adding features makes
the selected ingestion cost about 2.79 ms higher. Joint encoding is
396.190 ms wall versus fixed19's 440.949 ms, plus features: a measured size/CPU
tradeoff, not a storage win. Training-only reproduction of all three depths costs
about 1.2 ms for level3 and 1.3 ms joint; it exactly matches the frozen trees.
Generating development outcomes cost **17.094 s wall /16.938 s CPU** of encoding,
plus 0.949 s source-window reads. That research/label cost is separate from deployment.

Actual package reads include global-index parsing and lookup. Over 18 patches,
five 32×32 windows and three repetitions, level3 selected/fixed medians are
**0.707/0.723 ms**; joint **0.744/0.710 ms**. Small uncontrolled differences do
not establish a reliable speedup. Chunk512 can decode 256 times the requested
spatial support; chunk256 needs 64 times for an interior 32×32 window and up to
256 times at a four-chunk crossing. Choices and per-window amplification are
recorded. Selection runs at ingestion; query readers use persisted choices.
Writes are buffered/no fsync; OS cache is uncontrolled and warm. GeoTIFF timed
reads lack the engine's selected-stream SHA validation; file hashes are checked
outside their timers. No disk-cold, polygon-query, application or RSS claim.

All **1,872 candidate/control stores** passed full three-band/mask/metadata
roundtrip plus their window checks. Retained packages were independently checked
again against reread source windows: **180 full roundtrips and 900 window checks**,
all exact. The 18 unique holdout patches contain 4,718,592 spatial cells. All source
validity masks happen to be true; this cohort does not test general invalid-mask
diversity. Native datamask categories remain raw values, not mask validity or
legal compliance. Sparse packages cover only listed patches; gaps are unavailable.

## Existing AOI baseline challenge

A separate, explicitly **seen-AOI** audit reconstructs the original 604×1233
window from the same raw public tiles and verifies equality to the retained
engine store. It uses identical retained metadata and implicit true masks after
full verification. All 12 GeoTIFF controls plus six matching separate-band controls
roundtrip; no supplier geometry or declarations are queried.

| Level19 representation | Chunk | Required bytes | Encode wall ms |
| --- | ---: | ---: | ---: |
| Separate bands | 256 | 543,221 | 312.8 |
| GeoTIFF, band interleaved, predictor1 | 256 | **531,953** | 303.5 |
| Separate bands | 512 | 538,122 | 303.0 |
| GeoTIFF, predictor1 | 512 | 537,429 | 240.9 |
| Retained separate bands | 1024 | 535,012 | 256.4 |
| GeoTIFF, predictor1 | 1024 | 538,715 | 207.2 |

The best optimized control is 3,059 bytes / 0.57% smaller than the retained store.
Counting acquisition provenance symmetrically gives 540,247 versus 543,306 bytes.
Horizontal differencing **loses** on this categorical/multiband AOI; its 256 control
is 604,557 bytes. Thus a nominal optimization should not be assumed beneficial.
Audit minima are measured on the seen AOI, not a new heldout selector result.
All code, sources and retained-choice/store hashes remained unchanged during audit.

## Recommendation and handoff

Keep the current production choice until Volta reviews these controls. The
modest level3 rule is useful research about the existing engine codec family,
but loses to fixed optimized GeoTIFF3 and does not beat fixed19 on overall storage.
Reject the joint selector for
storage optimization and remove the redundant constant selector in any deployment.
Investigate optimized GeoTIFF through the lead's independent proof and fair-query
protocol before reconsidering retention. Any improved coastal rule needs new
development coverage and a **fresh** spatial holdout; these 18 test patches are spent.

Reproduction CLI, query example and file roles are in
[`data/experimental/selector/README.md`](../../data/experimental/selector/README.md).
Primary evidence: `dataset-manifest.json`, `policy.json`, `results.json`,
`verification.json`; descriptive follow-up: `analysis.json` and
`heldout-per-patch.csv`; matching-level control: `matching-level-control.json`;
seen-AOI baseline challenge: `aoi-control-results.json`.
Scripts require only the existing `.venv-data` NumPy/rasterio/standard library.
Research scratch is approximately 250 MB, including all losers and source patch
caches; none of those research files is counted as deployment payload.

A fresh-directory CLI replay completed in **57.3 seconds**, reproducing the same
72 coordinates, frozen trees, fixed baselines, all complete package byte totals
and optimized-GeoTIFF choice. Its additional 180 full and 900 window checks
passed. `reproduction-proof.json` retains the check; redundant replay scratch
was deleted. This repeats the same cohort and adds no independent generalization.

**Master relay signal: selector study and optimized-AOI baseline challenge are
ready for Volta's scientific review. No production integration requested or performed.**
