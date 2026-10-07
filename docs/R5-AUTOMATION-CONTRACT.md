# R5 automation and recovery contract

**Status:** R5 implementation-support contract. This document is non-normative and does not change `stateowl/0.2-draft.3`.

## Separation

stateOwl core owns exact state identity, read, optional observe, deterministic errors and guarded state publication.

The R5 qualification profile owns deadlines, eligibility, one claim/lease and operator escalation. It lives under `qualification/`; it is not a universal stateOwl entity or workflow engine.

The disposable effect target owns effect identity/status and target-side idempotency. R5 does not claim exactly-once execution or target fencing.

No scheduler, daemon, database or always-on stateOwl service is introduced.

## Production observe

`stateowl.observe.Observer` implements the already accepted `observe` operation over an existing read provider.

Properties:

- no model invocation;
- no publication;
- first call returns `baseline`;
- a valid prior token returns `changed` or `unchanged`;
- tokens bind target, normalized selectors/resolver and trusted authorization scope;
- scoped observation fingerprints every raw dependency actually read, including modes, proven absence and exact external origins;
- unrelated head changes may therefore remain `unchanged` when the relevant dependency fingerprint is identical;
- authentication, provider outage, deleted namespace, invalid/expired token and known continuity reset remain errors;
- `unchanged` does not imply that an executor-owned deadline cannot become due.

`HMACTokenService` is a binding helper. Its secret is trusted local execution configuration, never project state. Secret rotation or token expiry produces `TOKEN_INVALID`; callers explicitly establish a new baseline rather than silently treating that error as unchanged.

## Qualification profile

The fixture record is deliberately project-specific:

```json
{
  "schema": "stateowl.r5-qualification-job/1",
  "due_at": 200,
  "blocked": false,
  "claim": null,
  "effect": {
    "id": "effect-001",
    "status": "none"
  }
}
```

A claim, when present, is:

```json
{"owner":"worker-a","expires_at":240}
```

The qualification uses the host clock as the sole clock authority and assumes one-host clock consistency. Expiry only makes another claimant eligible to attempt a guarded claim publication. It is **not effect-target fencing**.

The deterministic pre-model decision is:

`event/scheduled check → observe → machine-only eligibility/deadline read when required → idle | eligible | blocked/error | operator_required`

`eligible` is permission to continue the project-specific claim step. When no live claim is already owned by the claimant, `model_allowed` remains false. Two claimants that become eligible from the same state race through guarded state publication; only the admitted claimant rechecks the profile, receives `claim-owned` with `model_allowed:true`, and may invoke model work. A stale or expired claimant must re-read ownership before any external effect.

## External effect fixture

W3 uses a disposable local target keyed by the durable `effect.id`. The target must provide atomic create-if-absent and query-by-ID so a lost response can be reconciled. Repeating the same effect ID must return the already-created effect rather than perform a second effect.

If target status cannot be established, the durable project outcome remains unknown and the gate returns `operator_required`. Automatic retry is forbidden until reconciliation proves it safe.

This demonstrates three separate problems:

1. state publication retry — R3 publication reconciliation;
2. duplicate computation — project claim/eligibility plus guarded claim publication;
3. duplicate/uncertain external effect — stable effect identity plus target reconciliation/idempotency.

## Required qualification

W3 must execute the complete R5 matrix, including 1,000 unchanged/not-due checks with zero model calls/publications/effects, same-head deadline eligibility, duplicate/missing/out-of-order wake events, competing claimants, expiry/takeover, revoked credentials, provider outage, invalid/expired token, lost publication response, restart boundaries and effect-outcome recovery/operator escalation.

Metrics must report actual counts and elapsed/runtime facts. No token-saving percentage is inferred.
