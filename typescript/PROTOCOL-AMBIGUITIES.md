# R2 protocol ambiguity / missing normative input

## A01 — native `.state` fixture/profile is absent from the frozen basis

The R2 assignment requires an agreed bounded existing-project-state fixture/profile. The frozen basis does not provide one.

`docs/ARCHITECTURE-DECISION.md` states that a native resolver would begin at `.state/current.json`, but also requires an actual sanitized Governance fixture before compatibility is claimed. `docs/protocol/PROTOCOL.md` R6 explicitly states that native Governance compatibility is not claimed by the synthetic corpus.

There is therefore no normative mapping that independently determines which native `.state` files, routes, projections, or profile identity must be used for this R2 fixture. Guessing those semantics from Governance or from another implementation would violate the independence rule.

Impact: core reads, router-v1, GitHub/local Git, opaque non-Git, legacy goldens, conformance, and benchmarks are unblocked. Only `native_state_fixture` remains blocked pending a normative fixture/profile addition.
