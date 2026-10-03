# Git binding — stateowl.git-receipt/1

Normative companion to `stateowl/0.2-draft.2`. This describes provider behavior; it does not qualify a GitHub or local-Git implementation.

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

The commit's raw UTF-8 message contains an optional human heading followed by one blank line and this final line, terminated by exactly one LF:

```text
StateOwl-Receipt: <base64>
```

`<base64>` is canonical RFC 4648 base64 of the **RFC 8785 canonical UTF-8 `PublicationIdentity` object** from P2, without an inner final newline. A message with no heading is exactly that line and LF. There is exactly one line beginning `StateOwl-Receipt:`. No continuation, CR, trailing spaces, duplicate marker, extra paragraph or additional fields inside the identity are allowed. A marker in a human heading is forbidden. Decode and validate the payload, then require re-canonicalization to reproduce its bytes. Derive `request_digest` from those bytes; no second digest or operation ID is stored.

This representation works with raw Git commit messages and GitHub's commit-message field. Do not parse rendered HTML, platform summaries or a locally rewritten/mailmap view. Do not use Git notes, a separate receipt branch, a database or a new file in project state. The commit object, its parent/tree and receipt are constructed together; updating the namespace atomically admits them together.

## G5. Admission and continuity

A writable binding requires a trusted **linear, append-only namespace policy** for the duration of submission/recovery. It must prevent merge admissions, deletion, rollback and force replacement by participating writers; an administrator able to bypass that policy remains an explicitly outside trust assumption. Re-observing equal IDs cannot establish that policy or detect ABA. No generation counter is fabricated. Known or suspected policy violation causes `NAMESPACE_DISCONTINUITY`; it never authorizes an old request against a recreated branch.

Admission must atomically compare the ref with the exact expected commit. `git update-ref <ref> <new> <old>` is one local primitive. An explicitly expected-value remote primitive must additionally reject history rewriting. GitHub's `createCommitOnBranch(expectedHeadOid: ...)` is a candidate atomic primitive; REST `force:false` alone is only an ancestry restriction, not a universal expected-value comparison. Production adapters must qualify their actual primitive and permissions separately. [G-REFS]

## G6. Bounded discovery after a lost response

A `reconcile` request performs **no admission**, even when the head still equals expected. Its retained identity includes target, expected, normalized changes and validation pin; newer validator defaults do not replace that pin.

1. Check access and the trusted continuity assumption. Fresh-resolve the target branch once to observed head H. An inaccessible/deleted namespace, unknown continuity or reset cannot prove non-admission.
2. Walk exact commit parent links from H, reading at most `limits.reconcile_commits` distinct commit objects. This is a bounded **linear ancestry walk**, not repository search, a path-filtered log or an unbounded history scan. Metadata byte limits also apply. Each inspected commit must be a commit with a well-formed parent list. A merge, cycle or root before expected makes continuity unprovable.
3. If H equals expected, return `indeterminate` with `PROVIDER_UNAVAILABLE`: an earlier request may still finish. Do not infer rejection from an unchanged head. Otherwise locate the unique child C on this chain whose sole parent is expected. Its position on the authorized, intact chain proves namespace admission, not merely object creation.
4. Parse C's receipt. A malformed reserved marker is `indeterminate/INVALID_SOURCE`. If there is no marker or a different valid identity, return `not_committed/CONFLICT` **only under the intact append-only policy**. Another child from expected has consumed the whole-namespace admission opportunity; even a disjoint stale transition cannot pass. No matching-message search farther into history substitutes for this parent test.
5. If C has the matching identity, its chain position establishes admission of the identified publication. Freshly verify its parent, receipt canonical bytes, expected tree, full intended candidate and unchanged remainder. Failure or unavailable verification now yields `verification_pending` with snapshot C. Success yields `committed` with snapshot C and observed_head H, even if H is a later successor.

Missing commit/receipt history, retention expiry or an exhausted ancestry budget returns `indeterminate/HISTORY_UNAVAILABLE`; do not claim absence from a bounded negative search. A root/merge/cycle before expected or known reset returns `indeterminate/NAMESPACE_DISCONTINUITY`. A provider outage returns `indeterminate/PROVIDER_UNAVAILABLE`. An orphan matching candidate is not admission evidence. Direct candidate verification may avoid a repeated walk only when separately retained **trusted positive admission evidence** already establishes its admission; candidate existence is not such evidence.

A fresh `submit` that gets a CAS conflict runs this same bounded discovery to recover a concurrent identical submission. It never retries the write. A positive admission acknowledgment followed by failed verification remains `verification_pending`; this is stronger evidence than a later failed history lookup. A response lost after dispatch remains `indeterminate` until a separate reconciliation establishes more.

## G7. Retention and reset boundary

The publication capability uses exactly:

```json
{"continuity":"append_only_required","receipt_format":"stateowl.git-receipt/1","receipt_retention":"reachable_history","authority":"project_validated"}
```

`authority` may instead be `mechanical` only where the project independently permits it. `reachable_history` specifies **where** receipts are retained: the immutable commits reachable from the namespace. It promises no duration, reflog service, orphan-object availability or maximum successor distance. `reconcile_commits` is the negotiated lookup bound; it is not a retention promise. A client needing longer guaranteed recovery must obtain a stronger external project/provider policy, not reinterpret this field.

Deletion, reset or history eviction may destroy the evidence needed to resolve an earlier attempt. Exact historical reads still work when objects remain accessible, but cannot recover namespace admission by themselves. Resuming new writes after a reset requires separately authorized setup of a new canonical namespace. No automatic reset, generation file or hidden database is part of this binding.

## Sources

[G-REFS] https://git-scm.com/docs/git-update-ref ; https://git-scm.com/docs/git-push ; https://git-scm.com/docs/git-check-ref-format ; https://docs.github.com/en/graphql/reference/commits ; https://docs.github.com/en/rest/git/refs . Raw Git object semantics: https://git-scm.com/docs/git-cat-file . Checked 3 October 2026; no live write qualification is claimed.
