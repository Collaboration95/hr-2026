# JRC standard-format control — completed research handoff

Master + Volta: **ready for independent review**, 2026-10-13T04:02:41.155017+00:00. No production choice changed. W1 owns production JRC fixes; existing strong-Hansen modules, source inputs, production artifacts and all other workers' files were read-only for this task.

The fixed one-bit GeoTIFF Zstd19/block1024 control is **19,901 bytes**, including its required4,196-byte manifest. It is1,558bytes (**7.26%**) smaller than the current21,459-byte custom store. Custom remains faster for measured full initialization plus17queries and has lower peak process RSS. The level3control encodes much faster but is larger (23,782bytes). Hot queries use identical native arrays/query code; small hot timing differences do not establish a format advantage. This is one seen sparse JRCchip, not a universal format result or compliance inference.

## Frozen evidence and coordination

Explicit review pointer: `data/experimental/jrc-standard/retained.json`. The runner updates only its own `latest.json`; it does not replace this retained pointer. Earlier results remain in their original experiment directories, with their earlier code fingerprints. The first two runs preceded added negative tests and final decision/guard verification; the third became stale after W1 refreshed its artifact. All three are historical, not the review choice. The fourth is the explicitly retained fresh run.

- Experiment: `exp-c11ef38c77f2bc3b77cde17183d2967dd0d99f24b07e7779897f7f29b9f2b288`.
- Run and complete canonical JSON SHA256: `run-51a4f4afa9c2ff1e525948cc194b94192ed56dac62f638909dcf55bc59e0008c` / `51a4f4afa9c2ff1e525948cc194b94192ed56dac62f638909dcf55bc59e0008c`.
- Archive: `data/experimental/jrc-standard/exp-c11ef38c77f2bc3b77cde17183d2967dd0d99f24b07e7779897f7f29b9f2b288/20261013T040145205039Z/run-51a4f4afa9c2ff1e525948cc194b94192ed56dac62f638909dcf55bc59e0008c.json`.
- Level19store: `data/experimental/jrc-standard/exp-c11ef38c77f2bc3b77cde17183d2967dd0d99f24b07e7779897f7f29b9f2b288/20261013T040145205039Z/gtiff_onebit_zstd19_b1024`.
- Compared W1 selected store: `artifacts/jrc-stores/exp-bfd3067040ae3fb83331667fba2ece195e9372893c81ac1930edbdfc68444f3a/binary_packed_zstd19-1024`.
- Canonical JRC artifact pinned SHA256: `933b3d302b8ec961444a7f252f74deb87f3f186f1b7f8d5bcb5012cb55658f71`. This is an input/store-pointer binding, not a claim that this study independently accepted W1's old timing receipt.

All engine dependencies, research scripts/tests, source/semantic inputs, exact17plot inputs, selected custom files and generated control files were pinned. Guards run before/after parent operations, in every child, and around every hot/encode sample. Imported-code fingerprints are captured before project imports. No fingerprint changed during the retained measurement. An earlier completed run was rejected during final handoff verification when W1 replaced `artifacts/jrc-baseline-v1.json`; the exact rejection and old pointer are preserved in `stale-handoff-20261013T0402.json` and `retained-before-w1-refresh.json`. This new run was explicitly selected because it binds the refreshed W1 artifact, not because its timing was favorable. Input-change and wrong-child-identity negatives fail visibly; a deliberately incorrect second measured hot sample also fails immediately. Future W1 code/artifact changes cause verification to reject this study as stale; rerun after W1 stabilizes and let Volta explicitly review a new retained choice. Production metrics were not reused.

## Actual measured results

Each value is median milliseconds; wall/CPU pairs are shown.7retained samples and2warmups for every hot, process-cold and encoded control measurement. All raw samples, warmups, answer digests, environment and store identities are in the archive.

| Representation | Required bytes | Hot17 wall/CPU ms | Process-cold load+17 wall/CPU ms | Whole-child wall ms | Max cold-child RSS bytes | Encode wall/CPU ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | 57653 | 5.126 / 5.125 | 17.241 / 17.232 | 155.086 | 98320384 | not measured |
| custom | 21459 | 5.120 / 5.113 | 10.281 / 10.237 | 143.215 | 87130112 | 218.088 / 217.560 |
| gtiff_onebit_zstd3_b1024 | 23782 | 5.285 / 5.285 | 14.659 / 14.621 | 151.712 | 99450880 | 3.842 / 3.842 |
| gtiff_onebit_zstd19_b1024 | 19901 | 5.236 / 5.233 | 14.203 / 14.191 | 151.828 | 99745792 | 211.130 / 209.679 |

Process-cold means a fresh ordinary Python process. **OS cache was not evicted; this is not disk-cold.** Fingerprint checks pre-read files. Inner cold timings include expected whole-file hashes for every necessary input/manifest/index, loader integrity checks, fullarray load, and17queries. Imports/plot loading and post-query correctness checks are excluded from inner time. Whole-child wall includes startup, imports, guards and correctness checks. Hot timing excludes loading; every answer is checked outside the timed call. RSS is whole isolated child high-water memory including imports and proof checks, not incremental query memory.

Encoding includes new required files and encoder validation, source already loaded, buffered writes without fsync. Every encode is decoded/proved and reproduces identical bytes, outside the timed encode. Encoding-child peaks: custom `127188992` bytes; level3 `136249344` bytes; level19 `212647936` bytes. These are nine-trial child lifetime peaks. Native source acquisition/recompression cost is not measured. No indexed/window timing is claimed; it is optional in this assignment. MemoryFile decoding binds checked TIFF bytes and avoids uncounted external sidecars; costs belong to this decoder implementation.

## Honest storage views

- Native DEFLATE TIFF46,238bytes + acquisition provenance4,680 + QML976 + XML5,759 = **57,653 necessary loader bytes**.
- Custom payload15,310 + index6,149 = **21,459**.
- GeoTIFF level3 payload19,587 + manifest4,195 = **23,782**.
- GeoTIFF level19 payload15,705 + manifest4,196 = **19,901**. Preliminary lead probe19,791 is superseded by this decoder's actual required manifest.
- All real masks are valid, checked across all6,684,255cells. Thus no real mask sidecar is necessary. Synthetic invalid masks require a separately accounted bounded packed-bit Zstd3sidecar, with raw1under invalid masks preserved.
- Equal external provenance/style/XML retention adds11,415bytes to custom/control only; native already includes them. Exact common CSV+GeoJSON adds19,265bytes to every representation. Symmetric totals: native **76918**, custom **52139**, level3 **54462**, level19 **50581**. The level19 advantage over custom is2.99% in this fuller shared-input view. Custom/control embeds exact loader metadata; these external retained copies are not additionally required by their decoders.
- The197,739,699-byte full acquisition tile is excluded. No tile-to-chip or plot-crop savings enter any comparison. Every representation covers the same1809×3695nativechip.
- Entire owned experimental directory is **555,080bytes** at handoff, including scripts, four preserved study runs/control pairs, identities, pointers and inventory. `inventory.json` lists hashes and bytes, excluding its own bytes from its internal sum. This total is research output, **not** a compression denominator. This report is outside that directory.

## Proof, tests and reproduction

All four representations match full raw values, independent masks, exact metadata, and all17query dictionaries. Independent JRC scalar oracle agrees. Native2020v4grid is retained; no Hansen resampling or shifted-window centers. Real cohort sums:9,511selected cells,8,957valid0 and554valid1; onlyP-0001has mapped class1. Valid0means mapped non-forest; unknown derives from support/masks/missing band, not class0. These are mapped observations, not legal findings.

Commands executed successfully:

```sh
.venv-data/bin/python -B data/experimental/jrc-standard/test_control.py
.venv-data/bin/python -B data/experimental/jrc-standard/study.py
.venv-data/bin/python -B data/experimental/jrc-standard/study.py --verify data/experimental/jrc-standard/retained.json
```

**21tests passed**. Tests include both real controls/custom roundtrip and17oracle comparisons; rawmasked1; valid0/unknown/missing/partial support; out-of-range raw values; malformed/truncated/changed TIFF; malformed/oversized/duplicate-key manifest; grid/type contradictions; unsafe paths/symlinks/unaccounted files; mask mode/padding/frame errors; bounded allocation; input/import/child fingerprint changes; wrong intermediate measured answer; and a rehashed off-plot change rejected by fullarray proof. Verifier recomputes source/control/custom/oracle proof, archive/content identities, exact required fingerprint inventory, all-sample digest claims, statistics and storage totals.

Environment: Python3.14.7, numpy2.5.4, rasterio1.5.2/GDAL3.12.2, shapely2.1.2, Python libzstd1.5.7, macOS arm64. No dependencies, Git mutations, source edits, extra agents, external uploads or publication. No implementation blockers remain. Review limitation: one seen chip, small sample count, uncontrolled host scheduling, runtime-specific deterministic encoding; hashes are integrity identities, not signatures.

**Final signal: W3 JRC-standard research complete; master relay to Volta for independent review. Production adapter/selection remains Volta's decision.**
