# R2 native `.state` fixture

This fixture proves that a stateOwl reader can consume project-owned `.state` records by direct path without creating a duplicate `.stateowl/router.json`.

It covers focused JSON projection, direct task-state access, one-snapshot batching, exact text reads, exact-snapshot reads with zero mutable-ref resolution, and current batched reads with one mutable-root resolution.

The records deliberately contain project-owned lifecycle-, review-, approval-, policy-, and effect-like fields. stateOwl does not interpret them. They are ordinary JSON/text bytes; only addressing, representation, projection, snapshot consistency, integrity, and provenance are in scope.

The fixture does **not** prove Governance policy, task lifecycle, review authority, readiness, approval, effects, publication, provider durability, or either R2 reader implementation.

## Execution

Use `tests/fixtures/r2-native-state/` as the virtual project root. Execute each case in `fixture.json` as a protocol `ReadRequest` and compare the logical `ReadResponse` plus the declared trace assertions.

The primary identity is opaque and deterministic for in-memory providers. The Git overlay supplies a protocol-compliant Git target, a deterministic finite-provider snapshot identity, and exact SHA-1 blob identities for the same bytes. A real Git-backed test may materialize the tree into a real commit and substitute only the target/snapshot identity required by that provider; source byte digests must remain identical.

No case uses `resolver`, `route`, or `.stateowl/router.json`.
