# stateOwl protocol — 0.2 draft 3

**Identifier:** `stateowl/0.2-draft.3`  
**Status:** Normative working draft for independent R1 re-audit; not stable.  
**Basis:** [Charter](../../CHARTER.md), accepted architecture and the R1 correction assignment. The archived architecture's historical status text is unchanged.

The normative set is this document, [Git binding](git-binding-v2.md), [legacy router binding](router-v1.md), and [schema](schema.json). [HARNESS.md](HARNESS.md) specifies the test interface, not a production adapter. A contradiction among these or the expected fixtures is a defect; implementations MUST NOT choose the weaker interpretation. MUST, MUST NOT, SHOULD and MAY have BCP 14 meanings [N1].

## 1. Capabilities and trust

**C1.** A reader implements `read`. Publication, observation, routing and expansion are separately advertised. A capability document describes an endpoint; an endpoint without `read` is not a conforming reader, but MUST return `UNSUPPORTED_CAPABILITY` for a read. Supply capabilities through trusted installation/configuration or discovery, not necessarily another model call. There is no automatic fallback to a weaker operation.

`Capabilities.operations`, `formats`, `features` and `resolvers` are closed declarations. Advertising `read` requires at least one supported format; an endpoint without `read` may have an empty formats array. `features` contains `routes` and/or `expand`; a nonempty features list requires installed resolver identities. A publication declaration is present exactly when `publish` is advertised. It identifies authority enforcement, continuity and receipt storage. `receipt_retention: "reachable_history"` means receipts reside in the immutable reachable history, with **no wall-clock availability promise**. Reconciliation is bounded by `limits.reconcile_commits`; unavailable objects or expiry of an operator's retention policy never justify a negative admission claim. The Git binding further narrows this guarantee. This draft standardizes one writable receipt binding, for Git; other providers may implement reads/observation, but cannot invent a publication guarantee under that binding identifier.

**C2.** Repository permission, project authority, semantic validity and external-effect permission are distinct. Trusted installation maps semantic bindings to local implementations. Requests and repository content cannot install code, grant permission, select an unapproved validator, or weaken the configured authority policy. Claims, leases, schedules and external-effect recovery remain project/executor responsibilities. This draft creates no task engine or hosted service.

## 2. Identity

**I1.** `Target` is the case-sensitive tuple `(kind, authority, resource, namespace)`. Trusted configuration supplies its canonical spelling and any explicit alias mapping **before** forming a request. An adapter MUST reject an unrecognized or unauthorized target rather than redirect credentials. Access transport is not identity: local Git and GitHub API access to the same configured repository use the same target. A move or provider migration needs an explicit mapping; equal unscoped strings prove nothing.

**I2.** `Snapshot` is exactly `{ "id": <nonempty string> }`. Equality is scoped to the complete target. The provider binding defines the identifier's type; Git uses algorithm-tagged commit IDs. Non-Git bindings may use opaque immutable IDs. No universal namespace generation exists. An exact snapshot establishes immutable content/version identity, **not** continued namespace existence, authority or absence of intervening resets.

Ordinary Git cannot detect delete/recreate or A→B→A from equal sampled heads. Writable Git therefore requires an explicitly trusted single-step, linear append-only admission policy (G5), not an invented generation or a conclusion drawn from two equal reads. Known or suspected discontinuity blocks new publication. Unresolved dispatched work stays unresolved after reset. Recovery after a reset requires project-authorized reconciliation and, for a new write domain, a new canonical namespace; this protocol does not perform that setup. Exact reads may still succeed after deletion/reset when the requested objects remain authorized and available.

**I3.** A `Binding` is one opaque, immutable, publisher-assigned ASCII semantic identifier, at most 256 characters. Examples are `urn:stateowl:binding:router-v1:1` and `urn:example:validation:3`. Its specification fixes all behavior-affecting configuration, including routing conventions and validation rules. Different implementations of those semantics use the **same identifier**. A behavior/configuration change requires a new identifier. Identifiers MUST NOT mean hashes of implementation code, packages, executables or filesystem paths. No lookup or remote code loading is implied. A trusted map must not bind the same identifier to different semantics; common fixtures test that obligation.

A read's `resolver` pins those semantics. A publish request's required `validation` is a **pin assertion**, not an authorization choice: the adapter independently resolves the required binding from trusted configuration and the expected state, then requires equality. `null` is legal only when that independent resolution says the project permits mechanical-only publication. Retain this assertion for recovery even if newer local defaults change.

**I4.** Paths are nonempty relative POSIX paths: no leading/trailing slash, empty, `.` or `..` component, backslash, ASCII control or DEL. Do not percent-decode or Unicode-normalize them. Literal `%2F` is not `/`. File/directory prefix collisions are invalid. Do not follow symlinks or submodules as ordinary records. Provider-specific unsupported names are rejected, never substituted.

## 3. Serialization and bounds

**J1.** Wire objects are UTF-8 JSON without BOM; keys are unique at every depth. Reject invalid UTF-8, unpaired surrogates (including in keys), NaN/Infinity, invalid grammar and negative zero spellings (`-0`, `-0.0`, `-0e3`). Object member order and whitespace do not affect semantic equality. Arrays preserve order except the explicitly normalized publication change set. JSON Schema 2020-12 describes structure; the rules here also apply when messages originate as native objects.

**J2.** Metadata integers are safe nonnegative integers, at most 9007199254740991. For a structured source JSON number, parse its mathematical decimal value before rounding. An integral value must lie in the signed safe-integer range. A nonintegral value is accepted only if its decimal value equals the decimal value of the RFC 8785 / ECMAScript binary64 round-trip serialization of that number. Otherwise return `NUMBER_UNREPRESENTABLE`. Thus `0.1` is supported, but `0.10000000000000001` is not; `1.0` is the number 1. Reject negative zero before conversion. These checks cover the **entire source before projection**. Explicit text/base64 reads preserve data outside this structured domain. Never rewrite stored records to satisfy it.

**J3.** `json`, `text` and `base64` are explicit representations. Text decodes exact UTF-8 and may preserve a source BOM as a character; source JSON forbids BOM. Base64 is RFC 4648 standard alphabet, required padding where needed, zero pad bits and no whitespace. Re-encoding decoded bytes must reproduce the input. Only JSON objects support field projection. SHA-256 content digests cover exact original bytes, including whitespace and final newline.

**J4.** Limits are positive maxima. `request_bytes` bounds actual UTF-8 request bytes (a native request is measured using RFC 8785); `record_bytes` bounds each decoded source, individual put, or provider metadata object; `mutation_bytes` bounds the sum of decoded puts; `records`, `expansions` (total requested links), `changes`, `tag_hops`, `reconcile_commits`, and `json_depth` bound their named work. A root JSON object/array has depth 1. `response_bytes` measures RFC 8785 UTF-8 bytes of the semantic response, excluding transport framing, and is at least 1024 so an error fits. Physical transport overhead is a separate binding limit, not a hidden success truncation.

Check byte/depth bounds before unbounded buffering or traversal. On source reads, a size violation precedes integrity/parse checks. An oversized successful response becomes `LIMIT_EXCEEDED`, never a partial success. After dispatch, bounds preserve publication certainty: admitted-but-unverified is still `verification_pending`.

**J5.** Receipt identities use **RFC 8785 itself, restricted to the closed `PublicationIdentity` schema**, not a JCS-like serializer. Its property names are fixed ASCII; values are Unicode scalar strings, safe nonnegative integers, booleans, arrays or null. There are no source JSON objects or floating-point numbers in this envelope. Recursively sort property names by UTF-16 code units, use RFC 8785 string escapes and integer spelling, and emit UTF-8 without whitespace/BOM/final newline. Source bytes are hashed separately, not canonicalized. General RFC 8785 serialization is also the deterministic response-size metric. [N2–N4]

## 4. Read

**R1.** `at` is either `{current:true, assert_snapshot?:Snapshot}` or `{snapshot:Snapshot}`. A current logical read resolves the root mutable ref **once**, then pins every root dependency to that snapshot. An exact read performs **zero** mutable-ref resolutions, including for expanded exact origins. An assertion mismatch returns `CONFLICT` before reading records. Currentness refers to the resolution point, not the end of the call.

**R2.** The nonempty `records` array has unique selection keys. Each item names a direct `path` plus `format`, or a `route`. Omitted `optional` means false; omitted/empty `expand` means none. Direct paths need no router. Require `resolver` exactly when a route or nonempty expansion is requested; an unused resolver field is invalid. Fetch each distinct `(target, snapshot, path)` once per logical read, apart from bounded transport retries. Share routing reads and do not enumerate unrelated records/history.

**R3.** A successful response has **exactly one record per requested selection, in request order**, with the same key. An authorized missing optional path produces one `absent` result; no other error becomes absence. Unknown routes, unavailable snapshots, hidden denials and missing required links remain errors. The operation is all-or-error: errors have no partial records.

A `select` array contains unique exact top-level property names; an empty array selects `{}`. For direct JSON, omission selects the whole value; a route supplies its documented default. A projected result includes its effective `select` and `missing` names in selection order. Omit absent properties; do not synthesize null. An unprojected result omits both fields. Projection of a non-object is `INVALID_REQUEST`. JSON object insertion order is not an interoperability requirement.

**R4.** Process selections in request order, each parent before its expansions, and expansions in requested order. For each found parent return exactly one found child per requested expansion; an optional absent parent has no expansions; omit `expanded` when none was requested. Expansion is one level only. Malformed unrequested links are not interpreted, though whole-source JSON validity still applies. Different stores or snapshots require exact `origin:{target,snapshot}`, separate authorization and no mutable lookup. Omit `origin` only when both target and snapshot equal the response root. Cross-store results are not a distributed atomic snapshot.

**R5.** Found records contain format, value and `Source`. Sources carry path, SHA-256 of raw bytes and actual integrity level. Return a typed native object ID when supplied. `provider` means verified byte identity with provider-trusted snapshot/path association; `object_chain` additionally requires independent native-chain verification. Neither proves actor identity or project authority. A routing result is present exactly when the request contains a resolver, identifies that binding, and lists distinct routing sources in first-use order. These are actual routing dependencies, not a dump of selected records.

**R6.** The [router-v1 binding](router-v1.md) is the supported compatibility convention, not a mandatory universal layout. Other profiles must define and pin their own resolver semantics and fixtures. Do not create duplicate `.stateowl` metadata for existing project-owned `.state` layouts. No native Governance compatibility is claimed by this synthetic corpus.

## 5. Publication identity and dispatch

**P1.** `PublishRequest` contains target, expected snapshot, required `validation` pin, `mode` (`submit` or `reconcile`), and nonempty whole-record puts/deletes. There is no operation ID. `submit` means a new attempt with no unresolved earlier dispatch by this caller; after uncertainty, use `reconcile` with the retained identical transition. `reconcile` NEVER dispatches admission. Changing mode is not changing the logical transition.

A put supplies exact UTF-8 or canonical base64 bytes. Reject duplicate paths and any prefix collision even when one item deletes a parent. Preserve untouched records and metadata. Existing regular-file mode is preserved; new Git files use `100644`. No mode-change field, symlink/submodule mutation, implicit namespace creation or directory replacement is supported. Deleting a missing record is `NOT_FOUND`. A total byte/mode-identical candidate is `NO_CHANGE`; a redundant unchanged put inside a nonempty effective transition is allowed.

**P2.** Normalize the changes as a set sorted by the UTF-8 bytes of path (unsigned lexicographic order). A put becomes `{path,put:{digest:<raw SHA-256>,bytes:<decoded length>}}`; a deletion becomes `{path,delete:true}`. Form exactly:

```json
{"protocol":"stateowl/0.2-draft.3","target":{},"expected":{"id":"..."},"changes":[],"validation":null}
```

Here `target`, `changes` and `validation` contain their actual schema-defined values. `request_digest` is `sha256:` plus the SHA-256 of J5 canonical bytes. `mode`, transport, source encoding choice, timestamps and implementation artifacts are excluded. Reordering distinct simultaneous changes or representing equal bytes as UTF-8/base64 preserves identity. Changing target, expected state, path, bytes or semantic validation pin changes identity. It is a replay identity, not a grant of authority or an external-effect idempotency key.

**P3.** Before dispatch retain the exact transition, validation pin and computed identity outside disposable process memory as required by the caller's recovery policy. Independently resolve authority/validation at the expected state, construct the complete old and candidate states, and validate them together. Candidate rules cannot approve their own weakening. A pin mismatch is `VALIDATION_FAILED`; unavailable trusted code is `UNSUPPORTED_CAPABILITY`; missing expected state is `SNAPSHOT_UNAVAILABLE`.

**P4.** Atomically compare the entire namespace to `expected` and admit all changes **and the receipt** together. Disjoint stale writers conflict too. Do not rebase, merge, force-reset, or emulate atomic publication with sequential file writes. Providers lacking this primitive cannot advertise publication. The [Git binding](git-binding-v2.md) defines its portable receipt and bounded recovery procedure. Creating an object is not admitting it to the namespace.

## 6. Outcomes and recovery

**P5.** Once request stages 0–1 succeed, every publication result contains `request_digest` exactly once. They do not echo target, expected, validation, changes, mode or an operation ID; retain the request alongside the result. This pair is the portable receipt/continuation record. The committed snapshot is scoped by that retained target and digest. Malformed wire requests instead use the generic error envelope described below.

| `outcome` | Required additional fields | Exact meaning |
|---|---|---|
| `committed` | `snapshot`, `observed_head` | Admission established and a fresh check verified receipt, intended candidate and preserved remainder. |
| `not_committed` | `error` | This fresh submission was excluded, or reconciliation proved another child of the expected state won under intact continuity. |
| `verification_pending` | `snapshot`, `error` | Admission of this identified publication is established, but verification is incomplete or failed. |
| `indeterminate` | `error` | Admission has not been established or excluded. |

No other fields are legal for these variants. A later valid successor can be `observed_head` without invalidating an earlier verified `snapshot`. Pending/indeterminate always use retry `reconcile`.

**P6.** A pre-dispatch failure on a fresh submit can be `not_committed`; it does **not** negate an earlier unreported attempt. A caller with any possible earlier dispatch MUST use `reconcile`. A lost response after dispatch is `indeterminate`, not conflict. A positive admission acknowledgment followed by any verification failure is `verification_pending`, even for corruption, retention, permission or limit failures. An expected head reappearing, an orphan candidate or a matching message alone proves neither success nor failure. Within a call, never discard stronger admission evidence because a later read failed. Across calls, the caller MUST retain and combine prior trusted results: a new binding unable to authenticate an earlier acknowledgment may return `indeterminate` for its new probe, but that does not downgrade the caller's previously established admission evidence. This draft does not turn a caller-supplied snapshot into a portable authenticated admission proof.

A submit that reaches an expected-state conflict MUST run bounded reconciliation before claiming logical conflict, so a concurrent identical transition can return its verified receipt. No response-loss path automatically retries admission. Recovery failures before evidence on a `reconcile` call remain `indeterminate`, including capability, authorization and unavailable validator/history failures. Reconciliation checks the **retained** validation identity, not a new local default, and does not rerun changed business rules to deny historical admission.

**P7.** Reconciliation is read-only. Git ancestry proves reachability, not that every intermediate commit was ever the namespace head. Ancestry-based admission or exclusion requires the trusted **single-step admission history** in G5: every authorized ref transition advances to one commit whose sole parent is the previous head. Under that intact policy, the matching direct child's chain position can establish admission; then verify its canonical receipt identity, complete candidate tree and unchanged remainder. A different direct child excludes the retained transition only under that same policy. A generic fast-forward, equal sampled heads or a policy name alone is not evidence that the requirement is enforced.

A jump A→D through receipt-bearing C does not establish C's admission. Missing/violated single-step policy, exhausted lookup, missing history or a reset leaves ancestry-based recovery uncertain. Separately retained trusted evidence of **the specific snapshot's admission**, such as an authenticated positive provider acknowledgment, remains stronger evidence under P6; object existence or a receipt is not its substitute. This draft adds no caller-supplied proof field. Seeing the expected head alone does not exclude an in-flight request. Do not redispatch an old transition into a recreated namespace.

**P8.** This transaction covers one namespace. It cannot atomically include product branches, other repositories or external effects. No exactly-once external execution guarantee is made.

## 7. Optional observation

**O1.** Observe head-only or the same records/resolver scope as read, with an optional prior opaque token. First observation returns `baseline`; later ones return `changed` or `unchanged`. Tokens bind target, normalized selectors, semantic resolver, raw record/routing dependencies (including regular-file modes and proven absence), exact external origins and trusted authorization scope. Normalize only omitted `optional` to false and omitted `expand` to an empty array; preserve all other selector fields and their order. Omit an unused resolver from token scope. Foreign, forged, expired or scope-mismatched tokens produce `TOKEN_INVALID`, not an implicit new baseline. Token encoding is binding-specific: different token bytes are explicitly outside cross-binding equality; establish a new baseline when changing token services.

**O2.** Authorization and current authoritative observation are mandatory. A scoped observation compares all raw dependencies, not only projected values. It may suppress unrelated head changes after checking that dependency set. `unchanged` means equality at successful observations, **not no intervening updates/ABA**. Known discontinuity produces `NAMESPACE_DISCONTINUITY`; outages, hidden denial and missing namespace produce errors. Observation cannot establish single-step admission history or publication authority from its token. Exact dependency identities remain scoped to their targets.

**O3.** Observe returns no record bodies, invokes no model and performs no publication. Due dates, lease expiry, retry deadlines, credential changes and eligibility remain executor concerns even at an unchanged head. Events are hints to re-observe, not admission evidence.

## 8. Determinism and errors

**E1.** Evaluate the following stages in order; do not probe later stages just to find a preferred error. Within record work use R4 order; within publication changes use P2 path order. This orders observable **logical** checks, not network batching. A batched implementation must select the same first logical failure and avoid unauthorized disclosure.

| Stage | Precedence within the stage |
|---|---|
| 0. Framing | request-byte bound → UTF-8/BOM/depth guard → JSON grammar/duplicate keys/surrogates/numeric safety. |
| 1. Request | missing/non-string protocol → unsupported protocol → schema and local semantics (keys, paths, canonical put bytes, collisions) → count/decoded-put bounds. |
| 2. Capability | operation → representation → routing/expansion → installed requested resolver. |
| 3. Access | authentication → target/path authorization. No source reads for denied targets. |
| 4. Version/context | publication continuity → exact expected-state availability → trusted validation pin and expected-state project authority (submit only); for reads current/exact object resolution → assertion. For observe token scope follows access, before resolution. |
| 5. Content | size → native/byte integrity → complete parse → binding shape → projection → ordered expansion; publication existing kinds/deletions → no-change → old+candidate project validation. |
| 6. Effect | atomic admission → acknowledgment/uncertainty → fresh observation and verification. Post-dispatch certainty overrides ordinary retry advice. |

For recovery, stage 4 is continuity → bounded receipt discovery, then stage 5 is historical receipt/candidate verification; no candidate authorization or new admission runs. At the same provider call, use its single normalized reported fault; test providers specify that report rather than inventing a precedence among inaccessible server causes.

**E2.** Error objects contain only `code` and the following deterministic `retry`. Human diagnostics stay outside the interoperable envelope. For any pending/indeterminate outcome override retry to `reconcile`.

| Retry | Codes |
|---|---|
| `after_correction` | `INVALID_REQUEST`, `NOT_FOUND`, `EXACT_SNAPSHOT_REQUIRED`, `INVALID_SOURCE`, `NUMBER_UNREPRESENTABLE`, `LIMIT_EXCEEDED`, `VALIDATION_FAILED` |
| `after_refresh` | `UNAUTHENTICATED`, `CONFLICT`, `NAMESPACE_DISCONTINUITY`, `TOKEN_INVALID` |
| `after_backoff` | `RATE_LIMITED`, `PROVIDER_UNAVAILABLE` |
| `never` | `UNSUPPORTED_VERSION`, `UNSUPPORTED_CAPABILITY`, `FORBIDDEN`, `NOT_FOUND_OR_FORBIDDEN`, `SNAPSHOT_UNAVAILABLE`, `INTEGRITY_MISMATCH`, `NO_CHANGE`, `HISTORY_UNAVAILABLE` |

Stage 0/1 failures use `{protocol:<this draft>,op:"unknown",status:"error",error:...}`: no partially parsed request is treated as an executed publication. Once a request is well formed, read/observe failures use their operation name; publication uses P5, including capability/access failures. An invalid `reconcile` message supplies no outcome evidence about the earlier request: its caller MUST keep that earlier outcome unresolved. No response silently fabricates identity fields from invalid input.

**E3.** Conformance compares complete semantic JSON results: object order/whitespace and the documented opaque token bytes are excluded, but array cardinality/order, keys, values, absence, provenance, typed IDs, publication fields, error codes and retry classes are not. Native object IDs/integrity levels reflect the declared provider evidence, not an implementation preference. The harness supplies deterministic token and proof services to compare exact test results. The shipped 0.1.0 API remains unchanged and uses its separate golden envelope.

## References

[N1] RFC 2119 and RFC 8174 (BCP 14).  
[N2] JSON Schema 2020-12: https://json-schema.org/draft/2020-12/  
[N3] RFC 8259 JSON and RFC 4648 base64: https://www.rfc-editor.org/rfc/rfc8259 and https://www.rfc-editor.org/rfc/rfc4648  
[N4] RFC 8785: https://www.rfc-editor.org/rfc/rfc8785.html ; negative-zero erratum 7920: https://www.rfc-editor.org/errata/rfc8785 . The draft explicitly rejects negative zero. Standards were checked on 3 October 2026; the conformance code uses a test-only ECMAScript oracle for number serialization rather than claiming Python `repr` is JCS.