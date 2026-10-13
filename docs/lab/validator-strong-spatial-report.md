# Independent strong-control and spatial-sensitivity audit

Started 2026-10-13 04:03 UTC. Separate additive evidence; accepted Hansen artifacts/rule and prior V1–V7 resolution remain unchanged. JRC fixes are outside this assignment.

Read both completed reports, actual strong-control encoder/reader/measurement/verifier, spatial study implementation and lead's strong-control review. Lead already found strict-type/proof hardening and an omitted export.py dependency; these will be independently tested rather than reported as new discoveries.

The actual strong-control worker hashes every **measured** hot answer into a digest set, checks every cold answer in the parent, and checks source/code/store guards before/after workers. This differs from the confirmed JRC J1 failure. A transient wrong measured answer will be injected to verify that the parent gate actually rejects it.

Independent TIFF/source/mask/metadata and byte accounting, plus exact-rational clipping of real spatial witnesses, are underway. No production/research mutation or browser work is planned; owned repro outputs only.

## Concrete checkpoint — 04:10 UTC

### S1 — REVISE strong-control proof hardening (lead's existing blocker independently confirmed and extended)

Fresh original and copied-bundle positives pass. In that validator-owned bundle, **all six rehashed semantic forgeries also pass** the actual verifier:

- `proof.raw_values_equal=true` replaced by integer1 (Python equality ambiguity already found by lead).
- Hot wall timing replaced by one sample `[0.0]` and its recomputed statistics, while experiment settings still declare7repetitions.
- Process-cold wall timing similarly reduced to one zero sample, while other timing vectors/digest records retain7.
- Encoder wall time changed to **-1ms**.
- Experiment compression level changed to **3**, experiment ID/identity/archive rebound, while actual control manifests/settings remain level19.
- Block512 removed from controls and common totals while declared settings still list both256and512.

Repro: `.venv-data/bin/python -B validation/strong_proof_controls.py` exits **1** because invalid controls are accepted. It copies the provided43-file bundle into `validation/strong/bundle`; all archive/identity reconstruction is inside that owned copy. Canonical artifacts remain untouched. Outcomes/paths: `validator-strong-proof-controls.json`. These are internal consistency failures, not an authentication claim or evidence of corruption in the real control data.

Gate for closure: fresh current-code positive, then rejection of each listed control for the changed type/count/bounds/settings/configuration claim. Keep storage acceptance separate from verifier hardening.

### Actual timing path resists the J1 transient-answer class

`.venv-data/bin/python -B validation/strong_timing_checks.py` passes. The second measured hot batch receives one incorrect selected count, then later batches are correct. Parent `measure()` rejects it for **source, accepted custom, control256 and control512**, in **both full and indexed modes**. A mismatched query-code guard also rejects before operation. The probe runs actual worker loops in-process solely as a negative test; no timing-performance results or artifacts are generated. All measured hot answer hashes are collected; all cold answer hashes are checked. Unmeasured warmups are not included in that claim.

### Code-identity correction to lead note

The inspected current `differing_fields` is **engine.benchmark.differing_fields** (`__module__` confirmed), imported at strong_baseline_measure.py:16 and defined in benchmark.py. `engine/benchmark.py` is already in the guard. No `engine.export` import exists in the inspected strong-control dependency chain. The lead note's claimed missing export.py dependency is therefore **not reproduced on this revision**; no speculative dependency defect is asserted. Other guarded source/code files match their recorded hashes.

## Independent strong-storage and spatial findings

`.venv-data/bin/python -B validation/check_strong_spatial.py` passes without importing either the strong decoder or spatial study. Both control TIFFs independently match all2234196source raw values, masks,604×1233nativegrid and reconstructionmetadata. Actual complete bytes are532444(block256),537920(block512), versus535012acceptedcustom and585293original requiredinputs. The2568byte/0.480%storage advantage is valid for this sameAOI comparison. All inspected accepted/canonical/rule files remain unchanged.

Independent **Fraction** rectangle clipping of every actual ring (no GEOS intersection/membership and no research helper) reproduces all17overlap cellsets and complete results,1048center versus1385overlap memberships, and allfivechangedflags. It also reproduces all15changed-flag event witnesses and their tiny positive angular fractions. P-0003row7/col12 is center-excluded but positively overlaps, raw83/25/1 with allmasksvalid, creating2024–25false→true. Other changed pairs are P-0004/2024–25, P-0014/2021–23, P-0015/2021–23, P-0019/2024–25. Current production query.py hash matches the accepted benchmark and all17productioncenteroutputs remain canonical. No production rule change or encoding mismatch is inferred.

Detailed evidence: `validator-strong-spatial-independent.json`, including exact rational witness fractions, actual rawvalues and immutable fingerprints. Geometry coordinates are interpreted as their supplied binary floats; fractions are angular ratios, not hectares. The stronger standard-control indexed cache/integrity policy differences remain correctly disclosed; no inherent format-only speed advantage is inferred.

## Handoff / acceptance gates

Strong storage/rawmask/query and spatial sensitivity evidence pass this independent scope. Strong proof hardening remains the **known Volta/W3 revision**, not a newly discovered competing workstream. Read and compared actual `engine-review-notes.md:59+` and lead reproducer before closing this checkpoint. The six owned controls provide additional concrete settings/sample-count/bounds witnesses for the already queued fix. No further exploration is needed before W3's fresh revision is ready.

Commands: `validation/check_strong_spatial.py` and `validation/strong_timing_checks.py` under `.venv-data/bin/python -B` exit0; `validation/strong_proof_controls.py` currently exits1 because contradictory proofs pass. Acceptance requires refreshed additive codefingerprintedpositive and rejection of all six self-consistent copied-bundle controls. No change to retained Hansen choice or production center rule is authorized by these research results.

JRC priority follow-up completed separately: J1/J2 now independently resolved with a fresh positive, original J1 rejection and byte-identical no-tile46-file lifecycle. See `validator-jrc-report.md` and `validator-jrc-fix-verification.json`. Only owned validation/report paths were changed across these tasks; original Hansen artifacts remain immutable. Ready for master/Volta relay and focused fresh-W3 verification when available.

## Final master replay — 13 October 2026, 04:26 UTC

After the worker fix and refreshed bundle, the master executed the unchanged independent `validation/strong_proof_controls.py`. The fresh positive passed and all six self-consistently rehashed semantic forgeries were rejected. `validator-strong-proof-controls.json` records this run. This closes those six reproduced gates; it is not a claim that Feynman personally reran the revised code or that all possible adversarial inputs are covered. The full engine suite also passed 198 tests at this checkpoint.
