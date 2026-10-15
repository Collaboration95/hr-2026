# Plotline lab results and decisions

Final master checkpoint: 13 October 2026, 04:27 UTC. This index separates the accepted demonstration from additive research. Detailed reports contain exact inputs, code identities, raw measurements and limits. It is not a claim that pending work passed.

| Question | Observed result | Decision / status |
| --- | --- | --- |
| Can the compact Hansen representation preserve this sample? | All 17 declared plot-query dictionaries agree; full raw arrays/masks/metadata and independent scalar checks pass. | Accepted computational fidelity for the pinned inputs and declared rule. No environmental/legal accuracy claim. |
| Is compact storage always smaller? | Retained custom535,012 bytes versus necessary original585,293 bytes; symmetric review inputs604,558 → 562,571 bytes (6.95%). A separately measured standard GeoTIFF control uses532,444 bytes. | Keep original retained run immutable; disclose stronger standard control and its separate study. Do not claim universal custom superiority. |
| Does the retained format make queries faster? | Retained hot preloaded17-query medians source 1.418 ms / custom 1.446 ms. Fresh-process full load+query11.182 ms / 5.800 ms; OS cache uncontrolled. | Full-load improvement is demonstrated for this small sample; hot query improvement is not. |
| Should indexed custom reads become the default? | Current compact indexed reader is slower than source; repeated chunk decode/hash work and differing cache policies matter. | Keep full preload for the small demonstration; preserve the losing indexed result. |
| Does learned codec selection help? | Spatial holdout joint selector811,164 bytes versus fixed810,764; fixed optimized GeoTIFF806,058. The level-3 selector beats its same-family fixed control but loses to matching standard-format control. | Reject production ML integration. Keep spatial split, frozen policy, measurements and reproduction evidence. |
| Can a JRC 2020 baseline be acquired? | Official v4 full tile and native chip acquired; class 0 is valid non-forest,1 forest. Native grid differs from Hansen. | Separate companion. Initial full fidelity/17-query checks pass; timing-proof/export-lifecycle fixes are independently verified; the separate native view is mounted. No grid fusion or legal inference. |
| Can standard one-bit TIFF improve JRC storage? | Complete standard control is 19,901 B versus 21,459 B custom; custom loads faster and uses less peak memory. | Retained research; no new production adapter or universal winner. |
| Does the plot inclusion rule change observations? | Overlap adds 337 plot/cell memberships and changes five period flags; both rules retain 17/17 source/compact equality. It does not explain the five historical supplier indications. | Research complete with 29 tests and independent reproduction of all changed flags/witnesses. Default center rule remains unchanged. |
| Can a reviewer ask a fresh spatial question? | Read-only local service and temporary region editor pass 14 actual integrated browser checks; exact source/compact answers, cells and receipt bytes agree. | Accepted bounded local workflow. Frozen source records are not edited. |

## Evidence map

- Accepted engine: [engine-report.md](engine-report.md), [interface-v1.md](interface-v1.md), [validator-report.md](validator-report.md).
- Working experience: [experience-report.md](experience-report.md), [browser-qa.md](browser-qa.md), [demo-script.md](demo-script.md).
- Strong standard Hansen control: [engine-strong-baseline-report.md](engine-strong-baseline-report.md).
- Adaptive experiment: [engine-selector-report.md](engine-selector-report.md), [engine-selector-review.md](engine-selector-review.md).
- JRC: [engine-jrc-report.md](engine-jrc-report.md), [validator-jrc-report.md](validator-jrc-report.md).
- Live query contract: [engine-live-interface-v1.md](engine-live-interface-v1.md), [experience-live-plan.md](experience-live-plan.md).
- Human next step: [company-next-conversation.md](company-next-conversation.md).

Separate studies have separate timing samples, fingerprints and baseline accounting. Never splice their fastest columns into a single synthetic benchmark. A successful integrity hash does not authenticate a source or replace raw/source comparison. Unknown support stays unknown even if the observed-loss count is zero.

Final master verification: 198 engine tests, 298 frontend checks, production build, Hansen/JRC verifiers and all six original strong-control forgery reproducers pass. The historical 2023-v1.11 comparison also finished: no shared 2021–23 count/flag changes on the17plots; later years remain unavailable in historical outputs. RuleLens UI is deferred and unmounted. See [complete handover](../HANDOVER.md).
