# Live local query lab — experience contract needs and design

Master-selected scope read at 03:38 UTC. This extends the verified frozen review with temporary spatial questions; it does not change the 17 supplier records, geometries, cohort counts, frozen export or retained benchmark.

## First slice

A new **Local query lab** view starts from the currently selected supplied plot. A mode control chooses its exact polygon or an explicitly temporary rectangle. The rectangle has labelled West/East/South/North numeric fields (decimal degrees), populated from the selected plot's bounds only after an explicit action. It is not labelled an edited farm boundary. Keyboard entry is the primary complete route; pointer drawing can follow only if it adds value after the verified slice.

The user explicitly runs the current region. Editing mode/plot/bounds invalidates the displayed answer and cancels any active request. A later response for an old draft cannot reappear. Cancel is a real AbortController action plus request-sequence guard. Invalid input gives a specific error without sending a request. Loading, cancelled, service unavailable, rejected query, unknown support and actual zero observations remain distinct.

Results identify the exact submitted geometry, request ID, query version and dataset/store snapshot. Show original/compact outputs with actual structural comparison, selected/valid/unknown support, both supported periods and annual counts; never use an advertised equality flag alone. Local receipt download preserves the request, source identities, answer and response scope. Per-request timings are observed operation timings, not benchmark replacements.

A native-cell preview/table must state whether it is complete. If the service caps evidence, show returned versus selected cells and the explicit omission reason; never present a partial preview as the complete answer. The geometry and source cell lattice remain exact. Unknown cells must use the fixed availability semantics, not zero/no-loss truthiness.

The frozen review remains reachable even when the optional local service is absent. The app makes same-origin requests through a lead-owned Vite loopback proxy; no private data or geometry goes to an external service.

## Engine contract needs (engine lead owns final names/limits)

Please publish a shared live interface early. Consumer needs:

- A health/snapshot endpoint: schema/query version, pinned source identities and retained store identity, geographic support/grid, accepted geometry modes and interactive work/evidence limits. No fabricated current satellite freshness.
- Query request: client request ID plus exact GeoJSON geometry; no arbitrary paths. Rectangle UI converts valid numeric bounds into a closed polygon before sending. Service validates independently.
- Query response: echoed request ID and exact submitted geometry or verifiable association; identified dataset/store snapshot; source/compact results; comparison; provenance receipt; honest evidence completeness/count/limit; per-request timings with scope/units if measured.
- Structured errors for invalid/unsupported/oversized regions and unavailable inputs. Source/compact disagreement is an encoding issue, not a supplier or legal finding.

Names/port/routes above are requirements, not invented callable endpoints. Frontend transport will follow the engine-owned contract when published. Main lead owns proxy/config and App integration.

## Acceptance route

Exact P-0003 reproduces its frozen source answer; temporary rectangle changes selection as actually computed. Tiny/no-center, wholly outside, invalid numeric/order and oversized cases retain truthful states. A delayed first response after a second draft/run cannot overwrite the current answer. Cancel and unavailable service work; frozen review stays usable. Keyboard and390px layout must complete region→run→proof→receipt without pointer drawing. Hansen first; JRC stays separate and gated.

## Published transport binding

Engine contract is now `engine-live-interface-v1.md`: health `/v1/health`, query `/v1/query`, loopback service8765. Vite development and preview proxy these same-origin routes to127.0.0.1 only; an optional numeric PLOTLINE_LIVE_PORT changes the port, never the destination host. Engine has its own exact Origin/Host checks.

Health binds a canonical snapshot string and limits; queries bind exact request bytes, request ID, snapshot and geometry. The client verifies canonical strings using UTF8 SHA-256 without guessing cross-language float serialization. v1 accepts at most4096candidate/selectedcells and returns all selected native evidence; oversized work is rejected rather than silently truncated.

## Separate rule-sensitivity follow-up (not a live blocker)

Read engine-spatial-sensitivity-report.md after master relay. Its exact-cell witness could support a compact “Why selection rules matter” research explanation after Volta/Feynman acceptance. Candidate: P-0003's native2025loss cell whose center lies outside while a small footprint sliver intersects. Use actual footprint, center, polygon and angular fraction with the precise rule names; do not call angular overlap hectares or forest loss area. Keep the production center rule fixed and source/compact encoding equality distinct from query-rule sensitivity. No witness results have been copied/rendered, and no production toggle is planned before an explicit contract. This research does not resolve the supplied2021–23declarations.
