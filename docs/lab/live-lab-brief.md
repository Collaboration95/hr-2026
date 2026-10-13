# Next product milestone: live local query lab

Master-selected milestone within the user's authorized four-hour build. Preserve the accepted frozen 17-plot review and measurements. Add a bounded way to ask a new spatial question of the same pinned local Hansen inputs and retained store.

## User outcome

A user starts from a supplied plot or a temporary rectangle, changes its bounds, runs a local query, and sees original/compact results, selected support, unknown reasons, and a reproducible receipt. The temporary region is not a new supplier record, correction to a farm boundary, legal finding, or claim of current satellite monitoring. New queries run on an identified frozen dataset snapshot.

## Lead coordination

- Engine lead owns the live-query JSON contract and bounded read-only local service. Publish a worker task and contract; delegate implementation when useful. Keep existing core/query/codec and accepted measurements unchanged. A separate `engine/live_*.py` or equivalent module is appropriate.
- Experience lead owns the interaction design and a separately scoped query-lab component. Publish a worker task against the engine contract. It may offer rectangle drawing, editable bounds, or both, with an accessible non-pointer route. Lead retains App/config integration.
- Master dispatches lead-owned worker tasks, reviews milestone reports, integrates and commits. Target a first usable slice within roughly 30–45 minutes, then independent cross-layer and browser checks. Do not block JRC proof review or the standard-format control.

## Essential boundaries

- Bind the service to loopback. No publication, remote data upload, filesystem writes from requests, arbitrary file-path parameters, or external services are needed.
- Validate body size, finite geographic coordinates, geometry type/topology, vertex count and a small interactive query-work budget before allocation. Reuse the accepted computational rule. Explain oversized or unsupported queries; preserve explicit outside-loaded-sample and missing-data states.
- Preserve original-lattice selection and exact source/compact comparison. Source/compact inputs identify their hashes, versions and retained store. Treat runtime measurements for one request as observations, not a replacement benchmark.
- Keep responses tied to the actual submitted geometry/request. Cancellation or a late response must not display an old answer for a new region. Loading/error states must not become zero or agreement.
- Provide genuine health/unavailable handling when the optional service is not running. The existing frozen review must remain usable independently.
- Native-cell evidence must match the requested geometry and counts. Bound visualization honestly; never quietly omit evidence and present the preview as complete.
- Keep supplier declarations, existing real-cohort totals and CSV/GeoJSON files immutable. Any new region is explicitly temporary/user-defined. No automatic forest-conversion/compliance conclusion.
- Begin with Hansen only. JRC or other layers may follow after separate acceptance and contract review; do not silently combine unlike native-cell counts.

## Acceptance

One known plot reproduces its frozen accepted answer; an edited region changes selection as computed; tiny/outside/invalid/oversized regions are handled truthfully; original and compact outputs agree; the receipt binds the request and inputs; keyboard use and response-race behavior are checked. No dummy action or fabricated timing is acceptable.
