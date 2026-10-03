# Git binding — stateowl.git-receipt/2

Normative companion to `stateowl/0.2-draft.3`. This describes provider behavior; it does not qualify a GitHub or local-Git implementation.

## G1. Targets and object identity

A Git target has `kind: "git"`. For GitHub.com use authority `github.com`, resource `owner/repository` in lowercase without `.git`, and the exact fully qualified ref as namespace. An explicitly configured local adapter accessing that same remote uses the **same target**, not `localhost` or a checkout path. Other Git servers need an agreed canonical authority/resource supplied by trusted configuration; no universal clone-origin inference is defined. Renames, aliases and migration require explicit trusted mapping before forming a locator. They do not silently change an existing request's identity.

Snapshot IDs are `git:sha1:` followed by exactly 40 lowercase hex digits, or `git:sha256:` followed by exactly 64. They identify **commit objects**. Object IDs use the same typed syntax, but the object's verified type determines whether it is a commit, tag, tree or blob. An exact read of a tag object is `INVALID_SOURCE`, not implicit peeling. A binding must reject unsupported object formats rather than truncate or convert IDs. The universal core also supports non-Git opaque IDs.

Namespace syntax follows `git check-ref-format` for a fully qualified `refs/heads/...` or `refs/tags/...` name. Branch reads require a commit. Tag reads allow a lightweight commit target or annotated tag objects. Publication accepts only `refs/heads/...`.

## G2. Tag resolution

Read the mutable ref exactly once. Inspect the resulting object. At each step: missing object → `SNAPSHOT_UNAVAILABLE`; inconsistent advertised ID/type → `INTEGRITY_MISMATCH`; repeated object ID → `INVALID_SOURCE`; commit → finish; non-tag/non-commit → `INVALID_SOURCE`; a tag when `tag_hops` dereferences have already occurred → `LIMIT_EXCEEDED`; otherwise follow its exact target and increment the count. A tag with malformed target/type is `INVALID_SOURCE`. A self-cycle therefore fails on repeat before the depth test. All object access is exact; following tags is not another mutable-ref resolution.

Conceptual cyclic graphs in the fault suite test termination. They are deliberately not claimed to be constructible, hash-valid Git objects. SHA-1/SHA-256 blob vectors separately test real object hashing.

## G3. Files and candidate construction

Read only regular blobs with modes `100644` or `100755`. A put over an existing regular file preserves its mode; a new file uses `100644`. Deletion requires an existing regular file. No mode field, executable-mode change, symlink (`120000`), submodule (`160000`), directory replacement or file/directory prefix collision is accepted. Unsupported kinds are `INVALID_SOURCE`; request collisions/mode fields are `INVALID_REQUEST`. Empty files are valid. Every untouched tree entry and its metadata must be preserved.

The publication candidate is one commit with **exactly one parent**, the expected commit. Its tree equals the result of applying the whole change set to the expected tree under these rules. Checking only touched files is insufficient: verification must also prove the remainder is unchanged, for example by constructing and comparing the complete expected candidate tree ID. Record bytes are never normalized.

## G4. Receipt representation

The semantic receipt format is `stateowl.git-receipt/2`. For this draft, the raw UTF-8 commit message MUST be exactly one of these two forms, where each displayed line break is one byte LF (`0A`) and the receipt line ends with exactly one LF:

```text
StateOwl-Receipt: <base64>
```

or:

```text
stateOwl publication

StateOwl-Receipt: <base64>
```

The optional heading is the **fixed, case-sensitive ASCII text** `stateOwl publication`, followed by exactly two LF bytes. It is not free-form human text. The marker is the exact ASCII text `StateOwl-Receipt:` followed by exactly one ASCII space. No other prefix, heading, paragraph, blank line, whitespace, CR, Unicode line separator, continuation, suffix or trailing space is allowed. Do not trim, split on generic Unicode line boundaries, or normalize before parsing. The complete byte grammar is `["stateOwl publication" LF LF] "StateOwl-Receipt: " BASE64 LF`.

`<base64>` is nonempty canonical RFC 4648 base64 of the **RFC 8785 canonical UTF-8 `PublicationIdentity` object** from P2, without an inner final newline. Decode and validate the payload, then require re-canonicalization to reproduce its bytes. Derive `request_digest` from those bytes; no second digest or operation ID is stored. Source request descriptors remain unordered-normalized as P2 specifies.

A message containing no occurrence of the case-sensitive reserved marker `StateOwl-Receipt:` has no stateOwl receipt. If that marker occurs **anywhere**, the whole message MUST match one of the two forms above; otherwise it is `INVALID_SOURCE`, including indented/inline/duplicate markers. Other ordinary commit messages may occur in admission history but cannot supply a receipt. Format `/1` is not silently reinterpreted as `/2`; its draft-2 definition remains at the previous immutable repository commit.

Use raw Git commit-message bytes, not rendered HTML, summaries or rewritten views. No Git notes, separate receipt branch, database or new project-state file is required. Parent, tree and receipt are constructed in the same commit; the namespace ref update is the distinct admission event.

## G5. Admission and continuity

An ancestry-reconciling writable binding requires an enforced, trusted **single-step, linear append-only namespace policy** throughout the submission/recovery interval. For **every authorized namespace-changing ref transition** from head A to head B, B MUST be one commit whose **sole parent is A**. This applies to all authorized writers and mutation paths, including manual Git pushes and non-stateOwl integrations, not just this adapter's own writes. A fast-forward A→D through one or more intermediate commits is forbidden even when the entire object graph is linear. Merge admissions, deletion, rollback and force replacement are also forbidden.

The trusted integration/operator must establish that these restrictions apply to the namespace before advertising publication. Merely declaring a capability, forbidding force-push, observing a linear DAG or sampling equal heads does not establish enforcement. An administrator able to bypass the restrictions remains outside the stated trust assumption. Known or suspected violations make continuity unprovable and cause `NAMESPACE_DISCONTINUITY`; neither polling nor an invented generation counter can repair that evidence. New submission is rejected before dispatch; unresolved work stays uncertain unless independently established admission evidence is already held.

Admission must also atomically compare the ref with the exact expected commit. `git update-ref <ref> <new> <old>` supplies an expected-old comparison locally, but requires separate enforcement of the sole-parent rule and protection of **all** other namespace update paths. Generic Git fast-forward/push/ref-update mechanisms do not establish single-step history by themselves: fast-forward permits any descendant. GitHub's `createCommitOnBranch` creates one commit on a branch and accepts `expectedHeadOid`, so it is compatible with the single-step primitive, provided other write paths cannot bypass the policy. The API feature is not proof of repository-wide enforcement. Production permissions, modes, atomicity and enforcement remain later qualification. [G-REFS]

## G6. Bounded discovery after a lost response

A `reconcile` request performs **no admission**, even when the head still equals expected. Its retained identity includes target, expected, normalized changes and validation pin; newer validator defaults do not replace that pin.

1. Check access and the enforced single-step continuity requirement in G5. Fresh-resolve the target branch once to observed head H. An inaccessible/deleted namespace, unknown continuity or reset cannot prove non-admission.
2. Walk exact commit parent links from H, reading at most `limits.reconcile_commits` distinct commit objects. This is a bounded **linear ancestry walk**, not repository search, a path-filtered log or an unbounded history scan. Metadata byte limits also apply. Each inspected commit must be a commit with a well-formed parent list. A merge, cycle or root before expected makes continuity unprovable.
3. If H equals expected, return `indeterminate` with `PROVIDER_UNAVAILABLE`: an earlier request may still finish. Do not infer rejection from an unchanged head. Otherwise locate the unique child C on this chain whose sole parent is expected. Only the intact **single-step ref-transition policy**, together with this position, establishes that C was admitted. Ancestry alone establishes only reachability; if the ref jumped directly from expected to H through C, do not report C as admitted.
4. Parse C's receipt. A malformed reserved marker is `indeterminate/INVALID_SOURCE`. If there is no marker or a different valid identity, return `not_committed/CONFLICT` **only under the intact single-step policy**. Another child from expected has consumed the whole-namespace admission opportunity; even a disjoint stale transition cannot pass. No matching-message search farther into history substitutes for this parent test.
5. If C has the matching identity and G5 remains established for the observed interval, its position under that single-step history establishes admission of the identified publication. Freshly verify its parent, receipt canonical bytes, expected tree, full intended candidate and unchanged remainder. Failure or unavailable verification now yields `verification_pending` with snapshot C. Success yields `committed` with snapshot C and observed_head H, even if H is a later successor.

Missing commit/receipt history, retention expiry or an exhausted ancestry budget returns `indeterminate/HISTORY_UNAVAILABLE`; do not claim absence from a bounded negative search. A root/merge/cycle before expected or known reset returns `indeterminate/NAMESPACE_DISCONTINUITY`. A provider outage returns `indeterminate/PROVIDER_UNAVAILABLE`. An orphan or skipped intermediate matching candidate is not admission evidence. Unknown single-step policy or a detected skipped-head transition returns `indeterminate/NAMESPACE_DISCONTINUITY`, not `committed`, `verification_pending` or a negative logical-conflict proof derived from that ancestry. Direct candidate verification may avoid a repeated walk only when separately retained **trusted positive admission evidence** already establishes its admission; candidate existence is not such evidence.

If a ref race exposes a policy violation during discovery, reject the ancestry inference rather than relying on an earlier access check. A fresh `submit` that gets a CAS conflict runs this same bounded discovery to recover a concurrent identical submission. It never retries the write. A positive admission acknowledgment followed by failed verification remains `verification_pending`; this is stronger evidence than a later failed history lookup. A response lost after dispatch remains `indeterminate` until a separate reconciliation establishes more.

## G7. Retention and reset boundary

The publication capability uses exactly:

```json
{"continuity":"single_step_required","receipt_format":"stateowl.git-receipt/2","receipt_retention":"reachable_history","authority":"project_validated"}
```

`authority` may instead be `mechanical` only where the project independently permits it. `reachable_history` specifies **where** receipts are retained: the immutable commits reachable from the namespace. It promises no duration, reflog service, orphan-object availability or maximum successor distance. `reconcile_commits` is the negotiated lookup bound; it is not a retention promise. A client needing longer guaranteed recovery must obtain a stronger external project/provider policy, not reinterpret this field.

Skipped-head updates, deletion, reset or history eviction may destroy the evidence needed to resolve an earlier attempt. Exact historical reads still work when objects remain accessible, but cannot recover namespace admission by themselves. Resuming new writes after a reset requires separately authorized setup of a new canonical namespace. No automatic reset, generation file or hidden database is part of this binding.

## Sources

[G-REFS] https://git-scm.com/docs/git-update-ref ; https://git-scm.com/docs/git-push ; https://git-scm.com/docs/git-check-ref-format ; https://docs.github.com/en/graphql/reference/commits ; https://docs.github.com/en/rest/git/refs . Raw Git object semantics: https://git-scm.com/docs/git-cat-file . Checked 3 October 2026; no live write qualification is claimed.
