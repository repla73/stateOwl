# R5 integration evidence

## Completion authority

R5 completion work is bound to:

`claw0gang/governance@72b61e2bf9ae526eb9750fa80fce2cf6db977be3`

Historical R0–R4 bindings remain closed and unchanged.

## Accepted basis and implementation

- canonical pre-R5 main: `d2ffde3653dc3341c9315b04a5d6304870f02578`
- R5 implementation subject: `299debe53567d3558a17f8b32f965e60fc678c87`
- W1 independent audit: GitHub issue #10 — PASS, findings none, next `READY_FOR_R5_W3`
- W3 execution qualification: GitHub issue #11 — PASS, next `READY_FOR_R5_INTEGRATION`

No R0–R4 implementation or protocol semantics are reopened by this integration.

## Adopted R5 capability set

The completion candidate contains:

- production implementation of the already-specified optional `stateowl/0.2-draft.3` observe operation;
- opaque restart-stable HMAC observation-token binding support;
- a qualification-only deterministic pre-model gate/profile kept outside stateOwl core;
- a qualification-only disposable local effect target demonstrating stable identity, query/reconciliation and target-side duplicate suppression;
- focused deterministic tests and the R5 automation/recovery contract.

stateOwl still does not own project deadlines, eligibility, claims, leases, retry timing, scheduler behavior or external-effect policy.

No stateOwl scheduler, daemon, database, generic workflow engine or mandatory always-on infrastructure was added.

## Real W3 qualification

Execution environment:

- host: `[redacted private execution host]`
- Python: `3.12.3` using the project virtual environment
- Git: `2.43.0`
- OpenClaw: `2026.9.8`, used only as the headless execution environment

Test evidence:

- complete repository suite: 92/92 PASS
- explicit R5 tests: 15/15 PASS
- production observe: PASS
- deterministic gate: PASS
- disposable effect target: PASS

### 1,000-idle proof

For 1,000 unchanged/not-due checks:

- idle decisions: 1,000
- model invocations: 0
- state publications: 0
- external effects: 0
- observation operations: 1,000 plus one baseline
- provider operations: 5,000
- provider process calls: 8,000
- state reads: 1,001 inside the loop, plus one baseline file read
- transferred bytes: 778,000 inside the loop, plus 783 baseline bytes
- elapsed: 13.573 seconds
- observed wall throughput: 73.678 checks/second
- qualification wake shape: serial executor-supplied one-second simulated ticks; no scheduler/daemon

No token-savings percentage is inferred from these measurements.

### Deadline, concurrency and failure evidence

PASS was established for:

- same state head with time advancing from not-due `idle` to due `eligible`;
- model permission remaining blocked until the claimant actually owns an admitted live claim;
- duplicate, out-of-order and missing wake events;
- two competing claimants with exactly one guarded claim admission and loser re-read;
- host-clock expiry/takeover without claiming effect-target fencing;
- controlled `UNAUTHENTICATED`, `PROVIDER_UNAVAILABLE`, `TOKEN_INVALID` and `NAMESPACE_DISCONTINUITY` failures;
- lost publication response followed by exact-request R3 reconciliation with zero additional durable ref updates;
- restart before an effect;
- restart after effect completion but before durable outcome;
- duplicate effect suppression under stable effect identity;
- operator escalation for unknown/corrupt effect status;
- no automatic repeat of an unknown external-effect outcome.

## Separation proved

R5 preserves three different recovery domains:

1. **State publication retry:** R3 publication reconciliation; one admitted ref transition and no repeat admission during reconciliation.
2. **Duplicate computation:** project-owned eligibility/claim state plus guarded claim publication; losing claimant conflicts and re-reads.
3. **Duplicate or uncertain external effect:** stable effect identity plus target query/idempotency; unknown status stops for operator action rather than automatic replay.

The qualification target supplies idempotency/query behavior only. R5 makes no exactly-once or effect-target fencing claim.

## Scope confirmation

- product source modified during W3: no
- canonical main modified during W3: no
- OpenClaw configuration/plugins/schedules modified: no
- remote qualification repository used: no
- PAT created or required: no
- R6 started: no

## Final boundary

This document records the R5 completion candidate evidence. Final project status becomes:

**R5 complete/adopted · R6 next**

only after the exact independently accepted completion tree is cleanly adopted onto `main`.
