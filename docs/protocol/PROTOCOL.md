# stateOwl protocol — 0.2 draft 1

**Identifier:** `stateowl/0.2-draft.1`  
**Status:** Normative working draft; R1 in progress. Not a stable release or an implementation claim.  
**Basis:** [Charter](../../CHARTER.md) and [architecture decision](../ARCHITECTURE-DECISION.md).  
**Companions:** [Schema](schema.json) · [Fixtures and remaining work](README.md).

## 1. Scope and conformance

The uppercase words MUST, MUST NOT, SHOULD and MAY use BCP 14 meanings [N1]. These requirements apply to implementations claiming this exact draft, not to the existing 0.1.0 package. Package versions, router versions, protocol versions and project rules are independent.

A reader MUST implement `read`. `publish`, `observe`, named routing and linked expansion are separately declared capabilities. An unsupported operation MUST fail explicitly; a binding MUST NOT substitute unguarded writes. No scheduler, task lifecycle, approval model, claim format, identity service or transport is required.

The schema uses JSON Schema 2020-12 [N2]. It describes message structure; it cannot prove source integrity, permission, atomicity, unique selected keys, admission or temporal facts. This document supplies those requirements. A contradiction between prose, schema and fixtures is a draft defect, not permission to choose weaker behavior.

**C1.** Before use, a binding MUST supply the `Capabilities` object through installation/configuration or discovery. Discovery need not require a model turn. The `features` list declares `routes` and/or `expand`; `resolvers` lists their installed exact bindings. A nonempty features list requires at least one resolver; without those features the resolver list is empty. Declared limits are positive maxima, not implied performance promises. Writers MUST disclose continuity assumptions, receipt retention and whether project validation is enforced. A mechanical-only writer MUST NOT represent repository access as project authority.

## 2. Identity and addressing

**I1.** A `Target` is the tuple `kind`, `authority`, `resource`, `namespace`. Its canonical spelling comes from the provider's trusted configuration. A caller MUST NOT redirect credentials merely by changing these strings. Locators contain no secrets or authority grants. Aliases require an explicit trusted mapping; matching unscoped IDs do not establish equivalence.

**I2.** A `Snapshot` contains `id` and `generation`. Both are opaque, case-sensitive strings outside their provider binding. Comparison is scoped to the complete target and generation. A generation identifies a namespace incarnation; it is not a new generation for every update. A reset, recreation or migration MUST NOT silently reuse an old incarnation's authority. The binding MUST disclose how generations and continuity are established. Git does not inherently supply a namespace-incarnation counter; a trusted append-only configuration may supply the generation only while its stated continuity assumptions hold. Suspected discontinuity requires reconciliation, not invented certainty.

**I3.** A current read uses `at: {"current": true}`. It MAY add `assert_snapshot` inside `at`, meaning the resolved current snapshot must equal that value. An exact read instead uses `at: {"snapshot": {...}}`. Combining the modes is invalid. An exact read does not assert present-day currentness or retained namespace authority.

A portable handoff is a `ReadRequest` with a frozen `at.snapshot` and the required selections. It is data, not an instruction to perform work. No custom URI scheme is defined by this draft.

**I4.** Paths are nonempty, relative POSIX paths. Reject leading/trailing slash, empty components, `.` or `..` components, backslash, ASCII control characters and DEL. Do not percent-decode or Unicode-normalize path identity. Provider escaping must preserve the logical path, including literal percent signs. Providers MAY reject unsupported names but MUST NOT silently substitute another path. Detect file/directory prefix collisions before publication. Never follow symlinks or submodules as ordinary state records.

## 3. Encoding and limits

**J1.** Wire messages are UTF-8 JSON without a BOM. Reject duplicate object keys at every depth, invalid UTF-8, unpaired surrogate values, non-finite numbers and invalid JSON grammar before dispatch. Wire objects are closed except for project JSON in `value`. Unknown protocol versions fail with `UNSUPPORTED_VERSION`; no version guessing is allowed.

**J2.** Metadata integers MUST be in the range 0 through 9007199254740991. Structured source JSON MUST preserve numerical value: integral values outside the signed safe-integer range fail with `NUMBER_UNREPRESENTABLE`. For a nonintegral value, its exact decimal value must equal the decimal value of its RFC 8785/ECMAScript binary64 round-trip spelling. Otherwise return `NUMBER_UNREPRESENTABLE`; do not round silently. Raw `text` and `base64` reads remain available by an explicit new request. Apply source JSON validity checks to the entire record before projection. These are draft interoperability restrictions, not permission to rewrite stored bytes.

**J3.** `json` means structured JSON; `text` means exact UTF-8 text; `base64` means RFC 4648 standard alphabet with required padding, zero pad bits and no whitespace [N3]. Do not infer format from an extension. UTF-8 decoding and base64 decoding MUST preserve all original bytes. Only `json` supports projection. Raw source bytes, including whitespace and final newlines, determine the SHA-256 digest.

**J4.** Enforce request-byte, record-byte, response-byte, selection, expansion, mutation and reconciliation limits. Counts and byte limits refer to decoded record bytes and UTF-8 wire bytes as applicable. Bounds MUST be checked before unbounded buffering or traversal. Exceeding any limit returns `LIMIT_EXCEEDED`, never a truncated successful result. For an already dispatched publication, preserve the outcome rules in section 6 even when a later bound is hit.

## 4. Read

A `ReadRequest` selects one target, one `at` and a nonempty ordered array of `records`. Each selection has a unique `key`, either a `path` plus explicit `format`, or a `route`. It MAY include exact top-level `select` names, `optional: true`, and named `expand` entries. Absent `optional` means required. Absent `expand` means no expansion. Empty `select` requests an empty projected object; absent `select` requests the whole direct record or the route's declared default.

**R1.** Resolve a current root exactly once, then use that immutable snapshot for every root record and routing dependency. An exact-snapshot read performs zero mutable-ref resolutions. If `assert_snapshot` fails, return `CONFLICT` before record reads. A ref movement during the read MUST NOT mix snapshots. Currentness is only asserted at the resolution point.

**R2.** Direct paths require no router. Fetch each distinct `(target, generation, snapshot, path)` at most once per logical read, apart from bounded transport retries. Routing dependencies share this cache. Unrelated state, history and directories MUST NOT be enumerated or returned by the focused read. Trace instrumentation may expose these operations to conformance tests without exposing them to the model.

**R3.** A present `select` contains unique top-level JSON property names. Project only those properties in the requested order; preserve their values. The result MUST include `select` and a `missing` array containing the absent names in that order. Do not invent nulls. Selecting fields from a non-object JSON value is `INVALID_REQUEST`. No `select` or `missing` is emitted for an unprojected value. A projection is never presented as a complete source record.

**R4.** Required records are all-or-error. An optional selection MAY return `status: "absent"` only when authorized absence at the exact snapshot is established. A provider response concealing access denial is `NOT_FOUND_OR_FORBIDDEN`, not optional absence. Unknown routes are errors, even if optional. Snapshot loss, integrity failure and denial cannot be converted to absence. Failure returns no partially successful `records` array.

**R5.** Each found record includes its selection `key`, format, value and `Source`. A source contains normalized path, `sha256:<64 lowercase hex>` raw-byte digest, and integrity level. Include the native object ID when the provider supplies one. `provider` means the adapter trusts the provider's snapshot/path association while checking returned byte identity. `object_chain` additionally requires independent verification of the full native association to the exact snapshot. Neither level proves author identity, authority or currentness.

**R6.** Named routes require a requested, installed `resolver` binding (`id` and exact digest). The request selects a trusted implementation; it cannot install or authorize code. Return the binding and all routing source provenance. All same-target routing data MUST come from the root snapshot; externally configured logic is identified by its binding digest. If authoritative configuration requires a different resolver version, reject the request. Project rules determine which context is sufficient for work; a small projection alone never authorizes execution.

**R7.** Expansion is explicit, one level, and resolved by that same trusted resolver. Expanded entries cannot themselves expand. Each requested link is required. External targets or different snapshots need exact `origin: {target, snapshot}` provenance, separate authorization and no mutable lookup. Return these sources as separately pinned reads, not a distributed atomic snapshot. Unrequested links MUST NOT be followed. An external link lacking exact binding fails with `EXACT_SNAPSHOT_REQUIRED`.

## 5. Publication input and receipt

A `PublishRequest` supplies one target, `expected` snapshot, `operation_id` and a nonempty ordered array of whole-record `changes`. A change is a `put` of exact UTF-8/base64 bytes or `delete: true`; never both. There is no patch language. An operation ID is scoped to `(target, expected generation, expected id)`.

**P1.** Check request shape, capability, target authorization, duplicate and colliding paths, supported file kinds and decoded size bounds. Reject deletion of a missing record with `NOT_FOUND`, and a byte/mode-identical total candidate with `NO_CHANGE`. Preserve every untouched record and metadata. Namespace creation, reset, migration and product publication are not implicit side effects of `publish`.

**P2.** Resolve applicable authority and validator from trusted configuration and the expected state, independently of caller assertions. Validate the complete old state and candidate together. Candidate rules cannot approve their own weakening. Caller-supplied `validated`, validator code or access tokens are not accepted wire fields. A project's stronger validation requirements cannot be bypassed by selecting mechanical-only mode.

**P3.** Compute `request_digest` as `sha256:` plus the SHA-256 of RFC 8785 canonical UTF-8 for the following object [N4]:

```json
{
  "protocol": "stateowl/0.2-draft.1",
  "target": {"kind": "...", "authority": "...", "resource": "...", "namespace": "..."},
  "expected": {"id": "...", "generation": "..."},
  "operation_id": "...",
  "changes": [{"path": "...", "put": {"digest": "sha256:...", "bytes": 1}}],
  "validation": null
}
```

Keep request change order. A deletion contributes `{path, delete: true}`. Decode each put before hashing; UTF-8 and base64 encodings of identical bytes have the same descriptor. `validation` is the exact trusted `Binding`, or null only when project validation is not required. The preimage contains only the fixed ASCII property names shown, strings, booleans, safe nonnegative integers, arrays and null. No floating-point numbers or arbitrary project objects enter it. Do not canonicalize original record bytes.

**P4.** Store the receipt binding `expected`, `operation_id`, `request_digest` and `validation` atomically with the admitted snapshot. The provider may use immutable commit metadata rather than a new project file. Snapshot identity is added to the returned receipt; it cannot be embedded in its own hash preimage. Retain the exact request and any provider candidate locator before dispatch so another session can reconcile. No mandatory external receipt database is introduced.

## 6. Admission, uncertainty and replay

**P5.** Atomically compare the entire namespace version to `expected` and admit all changes plus receipt together. A stale disjoint change is still a conflict. At most one competing transition from the same version can be admitted under the declared continuity model. Sequential file writes, automatic rebase and automatic merge are not conforming substitutes.

**P6.** Publication returns one of four mutually exclusive outcomes:

| Outcome | Evidence required | Next action |
|---|---|---|
| `committed` | Admission is established; a fresh check verified the receipt, entire intended delta and preserved remainder at the admitted snapshot. | Continue; resolve current state again when needed. |
| `not_committed` | This exact request is known not to have been admitted. | Correct input/permission, or read and revalidate a new transition after conflict. |
| `verification_pending` | Admission is established, but required verification has not completed. | Verify that same publication; do not submit new work. |
| `indeterminate` | Admission cannot be established or excluded. | Reconcile the retained request; no new operation ID or rebased retry. |

`committed` returns a receipt and `observed_head`. They MAY differ: an admitted, verified successor does not invalidate this publication. `verification_pending` returns the admitted snapshot but MUST NOT return a verified receipt. `indeterminate` MAY return a candidate snapshot; candidate existence is not admission evidence. `not_committed` MUST NOT carry admitted/candidate/receipt fields.

**P7.** A timeout after dispatch MUST initially remain `indeterminate` unless stronger evidence resolves it. A positive admission acknowledgment followed by read failure is `verification_pending`. Seeing the expected head again, seeing a candidate object, or matching a commit message alone is insufficient to infer failure or success. Cancellation does not undo an admission. Bindings that lose the entire response must tell callers to reconcile rather than synthesize a rejection.

**P8.** Replay the identical retained request under the original expected state. Recover the original receipt when proven. A matching receipt requires checking its actual parent/version relation and complete delta, not only its operation ID. Reuse of a proven replay identity with different descriptors or validation is `OPERATION_ID_REUSE`; it rejects the new payload without denying that the earlier payload may have committed. Same-key attempts racing without a receipt still rely on the expected-state guard, not a fictitious global idempotency service.

**P9.** Bound reconciliation. Missing admission history, exhausted search, retention expiry or discontinuity while an outcome remains unresolved yields `indeterminate`. A generation mismatch detected before any possible dispatch can be `not_committed`; a reset after ambiguous dispatch cannot. An adapter MUST NOT redispatch into a reset namespace using an old replay scope. Append-only continuity is a real precondition, not an inference from two equal head observations.

**P10.** Atomicity ends at the target namespace. Claims, lease clocks, deployment effects and target-side idempotency remain project/executor concerns. A successful state publication does not prove an external action ran exactly once.

## 7. Observation

An `ObserveRequest` supplies a target and optionally the same `records`/`resolver` scope as a read. Without records, observe the namespace head; with records, observe all raw record and routing dependencies, including explicitly expanded exact origins. A prior opaque `token` is optional. No record bodies are returned.

**O1.** The first authorized observation returns `status: "baseline"`, snapshot and token. A subsequent observation returns `changed` or `unchanged`. Tokens MUST bind the target, generation, selection, resolver identity, dependency set and authorization scope; they are not authority grants. A mismatched, forged or expired token is `TOKEN_INVALID`. A token format may remain binding-specific; cross-plane handoff can establish a new baseline.

**O2.** `unchanged` requires a successful current authoritative observation and a valid same-scope comparison. An outage, denied access, changed generation or unverifiable token MUST NOT become `unchanged`. Head-level `changed` can be a false positive for task eligibility; a scoped implementation may suppress unrelated changes only after checking all dependencies. A webhook is a hint, not a state proof.

**O3.** Observation itself invokes no model and performs no publication. An executor MUST separately check due times, lease expiry, retry deadlines and policy changes; unchanged bytes do not establish ineligibility. Scheduling and eligibility are not protocol operations.

## 8. Errors

Errors contain stable `code`, bounded human-readable `message` and `retry` disposition. `retry` is one of `never`, `after_correction`, `after_backoff`, `after_refresh`, `reconcile`. It is advice, not an automatic execution instruction. A publication error always retains its section 6 outcome. Unknown/unparseable operation input may use `op: "unknown"` only before dispatch. Validly identified publish requests use `PublishResult`, including validation and permission failures.

| Codes | Meaning |
|---|---|
| `INVALID_REQUEST`, `UNSUPPORTED_VERSION`, `UNSUPPORTED_CAPABILITY` | Input or negotiated feature is unusable; no weaker fallback. |
| `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND_OR_FORBIDDEN` | Authentication/access or deliberately concealed existence. |
| `NOT_FOUND`, `SNAPSHOT_UNAVAILABLE`, `EXACT_SNAPSHOT_REQUIRED` | Established absence, unavailable immutable history, or insufficient exact binding. |
| `INVALID_SOURCE`, `NUMBER_UNREPRESENTABLE`, `INTEGRITY_MISMATCH` | Malformed source encoding/JSON, unrepresentable structured number, or byte/object mismatch. |
| `LIMIT_EXCEEDED`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE` | A resource bound or transport/provider failure. |
| `VALIDATION_FAILED`, `CONFLICT`, `NO_CHANGE`, `OPERATION_ID_REUSE` | A rejected transition or freshness assertion. |
| `HISTORY_UNAVAILABLE`, `NAMESPACE_DISCONTINUITY`, `TOKEN_INVALID` | Recovery or observation scope cannot be trusted. |

If several faults apply, detect wire syntax/version/shape first, then capability, then authorization, then ordered record/transition validation. Do not leak state to unauthenticated callers merely to prioritize a more specific error. Post-dispatch outcome certainty overrides ordinary retry advice: pending/indeterminate results use `reconcile`.

## 9. Git and 0.1.0 compatibility

**G1.** Git snapshot IDs are `git:sha1:<40 lowercase hex>` or `git:sha256:<64 lowercase hex>` commit IDs. Generic code MUST accept non-Git opaque IDs as well. A native blob ID is typed the same way but identified by its `Source.object` position, never used as a snapshot merely because it has the right length.

**G2.** Fully qualified branch refs resolve to commits. Lightweight and nested annotated tags must be peeled with cycle/depth bounds to a commit; a tree/blob endpoint is `INVALID_SOURCE`. Exact snapshot input must identify a commit, not an unpeeled tag. These are object checks, not additional mutable-ref resolutions.

**G3.** Git puts preserve existing regular-file mode; new files use `100644`. No executable-mode changes, symlink/submodule writes or implicit directory replacement are defined. A writable Git binding must separately qualify admission, receipt placement, explicit old-version protection and retention. A non-force ref update alone is not a general CAS contract [N5]. No live writer is qualified by these documents.

**L1.** Keep `stateowl.router/v1` as an optional compatibility resolver. Its route default is `select`; named `links` expand explicitly and nonrecursively. Cross-repository links require exact commits. Do not add a second authoritative router to existing `.state` projects. Native Governance routing requires separately authorized real fixtures before compatibility is claimed.

**L2.** The 0.1.0 Python/CLI API and its `expected_head` freshness assertion remain unchanged. Legacy golden fixtures record its own response shape and errors. They are not rewritten to the new envelope. New source-number restrictions, typed snapshots and batch reads belong to the new draft, not a silent 0.1.0 behavior change.

## 10. References

[N1] [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174): BCP 14 terminology.  
[N2] [JSON Schema 2020-12](https://json-schema.org/draft/2020-12) and its [validation vocabulary](https://json-schema.org/draft/2020-12/json-schema-validation).  
[N3] [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259): JSON; [RFC 4648](https://www.rfc-editor.org/rfc/rfc4648): base64.  
[N4] [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html): JSON canonicalization.  
[N5] [GitHub REST refs](https://docs.github.com/en/rest/git/refs) and [git-update-ref](https://git-scm.com/docs/git-update-ref): provider-specific update semantics.
