# R4 binding and handoff contract

**Status:** R4 W1 shared implementation-support contract.  
**Basis:** `repla73/stateOwl@6e59c4b88800fa1d3f22116486661baeea1d3df9`.  
**Governance:** `claw0gang/governance@33bb80726de24531d702768498a5cad78755f589`.  
**Protocol:** `stateowl/0.2-draft.3` with `stateowl.git-receipt/2`.

This document is non-normative. It defines R4 binding, handoff, and qualification fixtures only. It MUST NOT weaken or extend `docs/protocol/**`, R2 read semantics, or R3 publication semantics.

## 1. R4 boundary

R4 proves continuity between execution planes. The execution conversation is disposable; durable state and the exact locator are authoritative.

Bindings expose only two model-facing stateOwl operations:

- `read`
- `publish`

Provider mechanics such as ref, commit, tree, blob, receipt, and reconciliation calls stay inside the binding.

R4 introduces no scheduler, claim/lease engine, external-effect engine, database, identity provider, universal project-state schema, hosted state store, or mandatory stateOwl service.

## 2. Handoff artifact

The machine-readable artifact is `stateowl.r4-handoff/1`, validated by `docs/protocol/r4-handoff.schema.json`.

Required normal handoff material is only:

- protocol identity;
- exact project profile identity;
- target;
- current or exact state locator;
- requested records.

The normal cross-plane handoff MUST use an exact snapshot. `current` is permitted only as an entry locator before work is pinned to an exact snapshot.

The artifact contains no credential or authority grant. A receiving plane must authenticate independently.

`continuation` is normally `null`. It is populated only when durable recovery material must cross a plane boundary.

## 3. Profile identity

The R4 deterministic profile is `stateowl.r4-continuity/1`.

Its exact identity is the SHA-256 digest of the raw bytes of:

`tests/fixtures/r4-continuity/profile.json`

including its final LF:

`sha256:9558ad87b903f8c86da55320af7798eadc48ba794cef020f0b587c679937c75c`

The identity receipt is stored in `tests/fixtures/r4-continuity/profile.identity.json`.

Changing any profile byte changes the profile identity and invalidates qualification evidence bound to the earlier identity.

## 4. Deterministic continuity fixture

The fixture contains exactly two operational records:

- `state/task.json`
- `state/work.json`

`state/task.json` defines the complete deterministic state sequence. The initial `state/work.json` is step `0`.

Plane A reads both records and replaces `state/work.json` with the task-defined bytes for step `1`.

Plane B starts independently, reads the same two records from Plane A's exact published snapshot, proves step `1` is present, and replaces the work record with the task-defined bytes for step `2`.

No README, transcript, branch history scan, repository discovery, or unrelated state is required for this decision.

## 5. Interrupted publication continuation

The interrupted fixture is:

`tests/fixtures/r4-continuity/interrupted-handoff.json`

It retains exactly:

- the normal handoff fields;
- the exact R3 publish request;
- the R3 `request_digest`;
- the strongest prior publication result known to the caller.

Its fixture request digest is:

`sha256:4874c28faa0a1bef11a6bcaa3edf48a112fdd4571ef72931b92e4d5c4d935565`

The retained request uses `mode: "reconcile"`. A receiving plane MUST NOT convert an unresolved prior dispatch into a fresh `submit`.

This is R3 caller recovery material carried by R4. It is not a new publication semantic, operation ID, or external-effect mechanism.

## 6. Qualification receipt

`docs/protocol/r4-qualification-receipt.schema.json` defines the common evidence envelope.

Every executed plane qualification records at minimum:

- exact basis and binding subject;
- exact stateOwl subject;
- installation/start mechanism;
- authentication source category and credential boundary, never the credential value;
- discovered read/publish capability;
- model-facing tool-call count;
- model-visible request/result bytes;
- provider operation count;
- requested paths;
- unrelated paths;
- cold install/start observations;
- authentication steps;
- exact operation result.

Provider traces may add detail outside this compact receipt, but the compact receipt must be sufficient to determine whether unrelated state was read and whether the binding actually exercised the accepted implementation.

## 7. Binding rules

A conforming R4 binding:

1. delegates semantic read/publish behavior to an accepted stateOwl implementation;
2. does not reproduce R2/R3 protocol logic in plane-specific code;
3. does not expose raw Git/provider primitives as the normal model interface;
4. keeps plane credentials outside project state and handoff artifacts;
5. returns stateOwl semantic results without translating uncertain publication into success;
6. reports unsupported capabilities explicitly rather than falling back to unsafe behavior.

## 8. Acceptance boundary

W1 acceptance freezes this contract, schemas, fixture bytes, and profile identity.

W1 performs no live publication and installs no plane integration.

Hosted binding/runtime work may be deferred without changing these shared artifacts. The native and hosted bindings must eventually consume the same contract and profile identity.
