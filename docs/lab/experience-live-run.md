# Shared live integration run

Experience lead owns server lifecycle. Parfit owns integrated browser QA on its own tab and test/report files. Do not kill shared processes.

- App: http://127.0.0.1:5173/ (lead Vite session77039). Same-origin `/v1` proxy targets127.0.0.1:8765.
- API: waiting for the canonical result/evidence string implementation required by engine-live-interface-v1.md. Lead will record the actual running session and positive health/query below after it lands. Do not bypass BINDING_UNAVAILABLE.
- Client: Carver's strict live-client.ts API is integrated. Exactbody/request/snapshot/geometry, canonicalhashes, semanticcounts, complete nativeevidence and actual source/compact equality are validated before resultstate.
- View: Query lab has exactplot/temporaryrectangle modes, explicitboundsseed, Run/Cancel, stale sequence+abort, native map/table/year, source/compact counts and boundreceipt download. Editing invalidates oldresults; referenceplot does not mutate frozenrecords. Initialselectedplot seeds component once; sidebarselection exitslab to frozenreview.

Once available, QA first positive P-0003 should compare all source/compact result fields to current frozenartifact, not just the displayed selectedcount. Then use actual temporaryrectangles and realHTTPresponses for successful/failure/race tests. A single-request timing is not the retainedbenchmark. No legalflag/JRC/ruleoverride in livev1.

Convenience command for a fresh local session: `cd app && npm run dev:local` (stop existing appserver first or set documented alternateports). Launcher was tested on5183/8766 and SIGINT closed both ownedchildren/ports. Those alternateports are now closed; shared5173 remainsup.

## READY — 04:08 UTC

Shared API started by Hooke: exec session68659,127.0.0.1:8765. Shared Vite remains session77039 on5173. Health snapshot `84219023e64fad041d5b063353a8fd0cb1543802b094c28f3b6b009dc0525e06`. Actual engine now emits required canonical result/evidence strings.

Lead real-browser positive through5173 passes: exact P-0003 renders “Original and compact answers match. Complete selected-cell evidence received.” No response augmentation/mocking was used for this positive. Empty/reversed bounds reject. Run `PLOTLINE_QA_ORIGIN=http://127.0.0.1:5173 node app/checks/experience-live-integration.mjs` to reproduce the bounded lead smoke. Parfit may now run complete integrated C5-C suite against5173. Do not restart/kill shared API without coordination; requests do not mutate frozen artifacts.

## ACCEPTED LIVE JOURNEY — 04:15 UTC

Parfit's14checks passed, and lead reran them through the finalized command `npm run qa:live --prefix app`:14passed/0failed, no blockedcase, no pageerrors. Exactrealresponses bind every canonicalresult/evidence/receipt; race/cancel/unknown/recovery/mobile pass. ResultJSON `docs/lab/browser-evidence/w3-live-service-results.json` records request/receipt/body identities and noResponseAugmentation:true. Sharedsessions remain unchanged and running. Historical missing-field/absent-service blockers above are resolved.
