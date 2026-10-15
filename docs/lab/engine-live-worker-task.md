# Live loopback Hansen worker assignment

Master proxy: dispatch an available Sol high worker for a first usable slice in30–45minutes. Read live-lab-brief.md, engine-live-interface-v1.md, interface-v1.md, engine-report.md and relevant actual project instructions. No extra leads/agents or hidden runtimes. Requested fast mode has no exposed control; do not invent it.

## Exclusive write set

Own ONLY `engine/live_query.py`, `engine/live_server.py`, optional `engine/live_*.py`, `engine/tests/test_live*.py`, new `data/experimental/live-service/`, and `docs/lab/engine-live-report.md`. Lead owns the contract, packaging and integration; experience lead owns app. Do not edit existing core/query/codec/proof/benchmark/export/acceptedartifact/retainedstore/source files. No Git mutations, dependency changes, source downloads, cloud spend, uploads, publication or messages to people. Read-only loopback requests may not write files. Test temporary outputs only in owned scratch.

## Implementation contract

Implement exactly engine-live-interface-v1.md: immutable fully checked source/retained compact snapshot; optional read-only127.0.0.1service; health and bounded temporary geometry query; strict JSON/geographic/topology/vertex/candidate budgets before allocation; complete existing native-cell evidence; exact source/compact outputs; snapshot/request-byte/geometry/receipt bindings; single-request measured timings separate from acceptedbenchmark. No canonicalexport or remeasurement. Use stdlib HTTP server and existing env; no new web stack needed.

Recommended pure API in live_query.py: `LiveSnapshot.load(root=ROOT)` and `.query(request:dict, request_body:bytes)->dict`; strict parsing/validation helper must bind parsed request to actualbody rather than accept an unrelateddict. Keep reusable validation/error type independent from HTTP so tests do not need socket hacks. Load verifies retainedbenchmark via current proof helpers, checks currentinputs before/after load, compares fullarrays/masks/metadata, and marks arrays read-only. Descriptorhash uses canonical_bytes; no runtimeport/starttime inidentity. Startup should be fast enough from currentminimalretainedbundle and requires nofullsourcecache.

Service binds only127.0.0.1; no --host flag. ExactdefaultloopbackCORSallowlist and Hostcheck. Explicit --allow-origin accepts only http localhost/127.0.0.1 with explicitport and no credentials/path/query/fragment. Do not expose arbitrary root/store paths viaHTTP. POST requiresContent-Length bounded65536, rejectTransfer-Encoding/ambiguouslength, setshortsocketreadtimeout, closemalformedconnections. Boundparallelrequests/queries; overloadedqueries503BUSY. OPTIONSonlyallowedorigin/method/headers. Do notlogrequestgeometry/body. No credentials/authcookies. CLIerrors conciseto stderr, no HTTPtracebacks.

No global coreconstantmutation to lower limits: independently preflight4096candidate rectangle with sameacceptedfloor/ceilmargin onoriginalaffine, then call unchangedcore functions. Test boundarygrid cases so preflight cannotunderestimatecorework. Handle distantoutsidequeries cheaply and truthfully. Evidence must includeALLselectedcells andrawmaskedvalues, complete=true; rejectlargequeries rather thantruncate. Existing resultcounts/histograms/unknownstates exact.

## Required meaningful checks

- All17suppliedgeometries querysuccess and match frozenanswers; theirusage istemporary geometry only, no supplierfields injected.
- Editedrectangle changesactualselection; tiny/no-center, partialoutside positive and absent-unknown, fullyoutside, holes/multipart, invalidtopology, nonfinite/3D/booleancoordinates, outofrange, unclosedrings, excessivevertices/body/candidates.
- Freshpositive snapshot/receipt/geometry/bodybindings; alteredrequestdict vs rawbody cannot produce misleadingbinding; staleexpected snapshot409. Strict numeric/type comparisons.
- HTTPhealth/query/preflight withrealephemeral127.0.0.1port; deniedOrigin/Host, allowedloopback, duplicatekeys, invalidUTF8/JSON/Content-Type, malformedlength/chunkedrequest, forbiddenmethods/paths, boundedtimeout/busy behavior. Keep testsfast/deterministic and avoidportsownedby app.
- Snapshotload fullraw/mask/metadata mismatch/staleproof rejects; in-memorysnapshotdoesnot silentlychange when diskwrites happenafterstartup. Clearly reportexactlifetimesemantics.
- Service createsno filefromrequest and doesnotmutate loadedarrays, canonicalartifacts orsupplierinputs. Check request evidenceequalscoreevidence andselectedcounts, raw/maskunknown distinctions.

Report commands/defaultport/exactfiles/testcounts/knownlimits andfirstworkinghealth/queryexample early. Include3representative responses in owned scratch (knownplot/temporarytiny/outside) if useful. Do not put companygeometry into apublicsite. Lead reviews backend; master/experience own UIproxy/configintegration andbrowserrace tests. Coordinate any necessarycontractchange viareport before divergentfieldnames ship.

## Immediate engine/client binding addition

Read the required04:06UTCaddendum to engine-live-interface-v1.md and experience-live-client-report.md. Add actualresponsefields `source_result_canonical_json`, `compact_result_canonical_json`, `evidence_canonical_json`, eachfromcanonical_bytes(...).decode('utf-8'). Evidencecanonicalstring covers theWHOLEevidencewrapper. Hash thoseexactbytes into the correspondingreceiptpayloaddigests. Existingobject_hash gives thesamehash but strings mustbe supplied. Client currentlyfailsclosed BINDING_UNAVAILABLE; its112passingchecks augmentfixturecopies onlyand doNOT establish currentHTTPacceptance. Add backendregressions for exactstrings/object/digestalignment and runpairedclientcheck afteractualfields exist; diagnostic should reportnoaugmentation. Do noteditclient/appfiles. Contractsnapshotnames nowexplicitlymatch youractualsources/retained/query_implementation_sha256/verified_files fields.
