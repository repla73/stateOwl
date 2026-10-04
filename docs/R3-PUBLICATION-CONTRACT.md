# R3 publication implementation and qualification contract

**Status:** R3 implementation-support contract.  
**Basis:** stateOwl main at 8c0b7baefcc2ba4c48cbf4dfa1964551c1291fa4.  
**Protocol:** stateowl/0.2-draft.3 with stateowl.git-receipt/2.

This document is non-normative. It does not create a second protocol and does not weaken or extend docs/protocol/**. If this document conflicts with the protocol, Git binding, schemas, or accepted fixtures, the normative material wins and the conflict is a defect in this document.

Its purpose is to give independent Python and TypeScript R3 workers the same implementation boundary and the same reproducible qualification target.

## 1. Fixed inputs and exclusions

R3 implementations preserve the accepted R1/R2 foundation:

- stateowl/0.2-draft.3 and stateowl.git-receipt/2;
- accepted Python and TypeScript R2 read behavior;
- native .state compatibility and existing 0.1.x compatibility;
- no Governance semantics in stateOwl core;
- no scheduler, claim/lease engine, external-effect engine, hosted service, plugin/MCP layer, release bump, or infrastructure provisioning.

The normative publication behavior remains defined by docs/protocol/PROTOCOL.md, docs/protocol/git-binding-v2.md, docs/protocol/schema.json, and the accepted protocol fixtures.

## 2. Implementation responsibility boundary

### Core publisher

The provider-neutral publisher owns:

- request framing/schema/local-semantic validation and protocol error precedence;
- canonical publication-change normalization;
- PublicationIdentity construction and request_digest;
- complete old-state/candidate overlay semantics, including untouched-state preservation;
- receipt construction and parsing;
- the four protocol outcomes and their exact retry semantics;
- submit-versus-reconcile control flow after the caller has selected the request mode;
- bounded reconciliation and combination of evidence within the current call;
- post-admission verification requirements.

The core does not authenticate users, grant project authority, install validators, create credentials, or own durable caller recovery state.

### Project-validation boundary

Trusted project integration/configuration owns:

- resolving the required validation binding for the target and expected state;
- determining whether the trusted validator implementation is available;
- comparing the request validation pin with the independently resolved binding;
- supplying project and path authority from trusted configuration;
- validating old state and complete candidate state together;
- preventing candidate data from selecting, replacing, disabling, or weakening its own validator.

Repository data may be validator input, but it MUST NOT install validator code or choose an untrusted implementation. A candidate that changes validation-related records is still judged by the trusted binding resolved from the old/expected state.

The production API may split these responsibilities differently, but the R1 black-box harness projects them through access and validate. R3 workers must preserve those observable semantics rather than invent a new wire contract.

### Git publication provider

The Git provider owns provider-specific mechanics:

- exact Git object type, tree, blob, mode, parent, and raw commit-message handling;
- complete candidate-tree construction or an equivalent exact Merkle proof;
- construction of one candidate commit whose sole parent is expected;
- the exact stateowl.git-receipt/2 commit message bytes;
- atomic expected-old namespace admission;
- fresh namespace observation after admission;
- exact commit/tree/message/history inspection for verification and reconciliation;
- normalization of transport/provider failures into protocol fault codes.

Creating Git objects is not admission. The provider must not translate a stale whole-namespace comparison into a merge, rebase, force update, or sequential file write.

The finite harness method tree is a qualification primitive for complete finite fixture state. A real Git provider may use exact tree-object comparison instead of materializing every file, provided the resulting proof is equivalent.

### Caller

The caller, outside stateOwl core, owns:

- credentials and authentication material;
- durable retention of the unresolved request, validation pin, PublicationIdentity/request_digest, and prior result evidence;
- choosing submit for a fresh attempt versus reconcile after any possible earlier dispatch;
- retaining prior trusted positive admission evidence across calls;
- claims, leases, scheduling, retries of external work, and external-effect recovery.

A stateOwl publisher MUST NOT move these responsibilities into the core or silently redispatch an uncertain request.

## 3. R1 harness projection used by R3

R3 reuses the accepted stateowl.fixtures/3 provider/fault harness. The black-box adapter sees only the expanded request, capabilities, and provider returns/faults.

Relevant provider calls remain exactly those in docs/protocol/HARNESS.md:

| Harness call | R3 use |
|---|---|
| access | authentication/access result, required validation identity, validator availability, project authority, continuity |
| resolve | one fresh mutable namespace observation |
| inspect | commit parents and raw receipt-bearing commit metadata |
| tree | finite complete-state/candidate verification primitive |
| validate | trusted old-state + candidate validation |
| admit | atomic expected-old admission of complete candidate plus receipt |
| file | available where exact file evidence is needed; publication must not broaden focused read behavior |

Fault timing, dispatched evidence, ref_updates, admission_policy, counts, and trace assertions remain harness-owned. The adapter must not receive case IDs, expected answers, future fault scripts, or trace expectations.

## 4. Shared black-box publication runner

The accepted checker is the runner. R3 adds only a scenario selector; default checker behavior remains unchanged.

Run publication conformance for either implementation with:

    python docs/protocol/check_fixtures.py --scenario publish --adapter <adapter-command> [args...]

The --scenario option must appear before --adapter because adapter consumes the remaining command arguments.

The adapter transport is the existing UTF-8 JSONL contract in docs/protocol/HARNESS.md:

1. driver sends start with request_base64 and capabilities;
2. adapter issues bounded provider calls;
3. driver returns exactly one value or normalized fault per call;
4. adapter returns one protocol response.

The checker imports no Python or TypeScript publisher implementation. An implementation adapter is an executable black box. The driver owns fixture expansion, finite provider state, fault injection, expected-result comparison, provider traces, and safety bounds.

Without --scenario, check_fixtures.py continues to execute all accepted read, publish, and observe scenarios.

### Publication coverage map

After the two R3 support cases added by W1, the publication scenario is 89 addressable black-box cases. The required categories are represented as follows:

| Category | Representative case(s) |
|---|---|
| normal committed publication | atomic-commit |
| pre-dispatch rejection | failure-before-dispatch; unavailable-trusted-validator |
| stale expected-state conflict | stale-entire-namespace |
| whole-namespace conflict for disjoint stale writes | disjoint-stale-writer |
| identical concurrent transition recovery | submit-conflict-recovers-identical-publication |
| lost response after dispatch | response-lost-after-admission |
| verification_pending | admission-ack-verification-unavailable |
| indeterminate | reconcile-same-head-does-not-exclude |
| successor after publication | successor-does-not-negate-commit |
| bounded reconciliation | identical-replay-no-dispatch; single-step-history-proves-intermediate |
| reconciliation exhaustion | bounded-history-no-negative-proof |
| missing history | history-missing |
| malformed receipt | malformed-receipt; receipt-grammar-* cases |
| wrong valid receipt | wrong-valid-receipt |
| skipped-head history | fast-forward-skips-receipt-commit; skipped-history-revealed-during-walk |
| namespace reset/discontinuity | recreated-at-same-head; rollback-no-replay |
| validator unavailable | unavailable-trusted-validator |
| validation-pin mismatch | validation-pin-cannot-disable-required-validator |
| candidate validator self-downgrade | validator-self-downgrade |
| unauthorized path | unauthorized-path |
| no-change | no-change |
| delete-missing | delete-missing |
| mode preservation | existing-executable-mode-preserved |
| new file mode 100644 | new-regular-file-mode |

This table is an index, not a replacement for the complete 89-case corpus.

## 5. Independent implementation rule

W2A and W2B are independent.

Shared inputs allowed to both workers:

- the exact accepted W1 subject;
- normative docs/protocol/**;
- this contract;
- shared protocol fixtures and black-box qualification tooling;
- the accepted R2 implementation in that worker's own language.

During independent R3 implementation, each worker MUST NOT read:

- the other language's R3 publisher source;
- the other language's R3 publisher tests;
- the other language's unpublished debugging output.

Published shared W1 fixtures/tooling are not cross-language implementation material.

## 6. W4 deterministic local-Git execution matrix

W1 defines this matrix but does not execute it.

### Common setup

Create a disposable local Git repository owned by the qualification run. Keep an unrelated checked-out branch named worktree-sentinel. Create the publication namespace refs/heads/stateowl-r3-qualification at base commit A without checking it out.

The local target is fixed by trusted test configuration as:

    {"kind":"git","authority":"qualification.local","resource":"stateowl/r3","namespace":"refs/heads/stateowl-r3-qualification"}

The A tree is fixed to these exact bytes and modes:

| Path | Canonical base64 bytes | Mode |
|---|---|---|
| state/work.json | eyJ2IjoiQSJ9Cg== | 100644 |
| state/obsolete.txt | b2xkCg== | 100644 |
| state/script | IyEvYmluL3NoCmV4aXQgMAo= | 100755 |
| state/untouched.txt | a2VlcAo= | 100644 |
| state/validation.json | eyJlbmFibGVkIjp0cnVlfQo= | 100644 |

The qualification transitions use these exact mutation payloads:

- normal: put state/work.json = eyJ2IjoiQiJ9Cg== and delete state/obsolete.txt;
- divergent-P: put state/race.txt = cHl0aG9uCg==;
- divergent-T: put state/race.txt = dHlwZXNjcmlwdAo=;
- identical: put state/shared.txt = c2FtZQo=;
- successor: put state/successor.txt = bGF0ZXIK;
- executable-mode case: put state/script = IyEvYmluL3NoCmVjaG8gcjMK;
- new-file-mode case: put state/new.txt = the empty byte string.

These are request bytes, not precomputed Git object IDs. Each implementation computes its protocol identity and actual Git commit ID and returns them as evidence.

Record before every case:

- target and exact base snapshot;
- namespace ref;
- checked-out HEAD;
- index tree identity;
- worktree file digest set;
- complete target tree with modes.

Each case starts from a fresh clone/repository instance derived from the same deterministic fixture. Two-writer cases use a barrier immediately before expected-old admission so both requests are built from one base.

Single-step continuity for this local qualification is a trusted test-environment input. The harness/qualification monitor records the actual namespace transitions it owns. It is not inferred merely from Git ancestry.

### Matrix

| # | Case | Required action and result |
|---|---|---|
| 1 | normal A to B | Submit one valid transition at A. Exactly one child B is admitted and freshly verified committed. |
| 2 | divergent two-writer race | Two different requests share expected A. Exactly one child is admitted; the other returns not_committed/CONFLICT after bounded reconciliation. |
| 3 | identical two-writer race | Two identical logical requests share expected A. Exactly one child is admitted; both callers resolve to committed with the same admitted snapshot. |
| 4 | lost successful response | Admit the request, suppress/discard the caller-visible success, retain the exact request, then run reconcile. Reconcile performs zero admissions and resolves the admitted snapshot. |
| 5 | positive admission then verification failure | Let expected-old admission return a positive admitted snapshot, then inject a verification read failure. Result is verification_pending with that snapshot, never downgraded to indeterminate/not_committed. |
| 6 | later successor | After a verified publication B, admit a valid successor C. Reconcile the retained B request and return committed snapshot B with observed_head C. |
| 7 | expected-old conflict | Advance the namespace with a different valid child, then submit a stale divergent request. No new admission; result is not_committed/CONFLICT under intact continuity. |
| 8 | skipped-head violation | Deliberately perform one qualification-owned A to D ref transition where D is a descendant through intermediate C. Mark/observe that actual skipped transition in the trusted continuity monitor. Reconciliation must return NAMESPACE_DISCONTINUITY, not infer C admission from ancestry. |
| 9 | complete tree preservation | Change only named records. Verify the admitted tree equals expected overlay exactly and every untouched entry/object/mode is unchanged. |
| 10 | executable mode preservation | Put new bytes at existing state/script. Verify admitted mode remains 100755. |
| 11 | new-file mode | Put a new regular file. Verify admitted mode is exactly 100644. |
| 12 | no worktree mutation | Across the publication cases, verify checked-out HEAD, index tree, and worktree digest set are byte-for-byte unchanged from their pre-case values. |

### W4 evidence receipt

For each language and case return:

- implementation subject SHA and exact command;
- exact request digest and response;
- base/final namespace refs;
- admission count and ordered namespace-transition evidence;
- admitted commit ID where any;
- admitted commit sole-parent list;
- raw receipt message bytes or an exact base64/hex representation;
- expected and observed tree IDs plus per-path modes needed by the assertion;
- injected fault point where applicable;
- pre/post checked-out HEAD, index tree, and worktree digest set;
- PASS/FAIL against the row's expected result.

Do not replace this evidence with screenshots or prose-only claims.

## 7. W6 disposable live-provider execution contract

W1 defines this plan but performs no live writes.

### Environment supplied before W6

The execution worker is given, not asked to provision:

- one pre-existing disposable GitHub repository;
- one dedicated publication namespace already initialized at A with the exact A file bytes/modes from the W4 common fixture;
- the exact protocol Target using authority github.com, the lowercase owner/repository resource, and that fully qualified refs/heads/... namespace;
- the exact typed Git snapshot ID for A and a complete baseline tree/object/mode observation;
- one narrow credential scoped to that disposable repository and namespace use;
- the trusted validation binding and validator configuration for the fixture;
- an explicit test-environment statement/configuration establishing the single-step policy assumption for the qualification interval.

The worker records these inputs before the first write. No app, repository, credential, branch, or namespace is created by W1 or by an implementation worker.

### Maximum accepted transitions

The sequence permits at most four accepted namespace transitions. Rejected CAS attempts do not count.

1. **Transition 1 — Python A to B.** Submit one request with four changes: put state/work.json = eyJ2IjoiQiJ9Cg==; put state/script = IyEvYmluL3NoCmVjaG8gcHl0aG9uCg==; put new state/python-new.txt = cHl0aG9uCg==; delete state/obsolete.txt. Verify B committed, state/script stayed 100755, python-new.txt is 100644, and every untouched entry was preserved.
2. **Transition 2 — TypeScript B to C with discarded response.** Submit put state/lost.txt = dHlwZXNjcmlwdAo=. The qualification driver deliberately discards the successful caller-visible result while retaining the exact request, then invokes the identical transition with mode reconcile. Reconciliation must perform no admission and establish C.
3. **Transition 3 — divergent cross-language race from C.** At one start barrier, Python submits put state/race.txt = cHl0aG9uCg== and TypeScript submits put state/race.txt = dHlwZXNjcmlwdAo=, both with expected C and the same validation pin. Exactly one child D is admitted; the loser is excluded as conflict under intact continuity.
4. **Transition 4 — identical cross-language race from D.** At one start barrier, both languages submit put state/shared.txt = c2FtZQo= with expected D and the same validation pin. Exactly one E is admitted. Both implementations must resolve the same E, one directly and the other through conflict reconciliation.
5. **Later-successor verification without a fifth transition.** Reconcile the retained winning request from step 3 after E exists. E is now a later successor of D; the result must identify D as the committed snapshot and E as observed_head.

### Live observations required

For B, C, D, and E collect enough provider evidence to verify:

- returned commit identity equals the observed admitted commit identity;
- exactly one parent and that parent is the immediately previous admitted head;
- exact raw stateowl.git-receipt/2 message bytes match the retained PublicationIdentity;
- complete candidate tree preservation, not only changed paths;
- existing 100755 mode is preserved;
- any new file uses 100644;
- accepted namespace-transition count is at most four;
- the discarded-response reconcile and the identical-race recovery perform no extra admission.

Record credential/repository permission facts needed to show the adapter did not require broad administrative, workflow, or unrelated-repository access. Never publish the credential itself.

### Single-step policy evidence boundary

W6 may prove directly that every stateOwl transition it performs:

- uses the expected-old compare primitive;
- admits one commit at a time;
- creates a commit with the previous head as its sole parent;
- does not force-update, merge, or delete the namespace.

W6 cannot prove repository-wide historical single-step admission merely from:

- a linear Git DAG;
- normal fast-forward/linear-history protection;
- disabled force-push alone;
- sampled heads;
- GitHub createCommitOnBranch behavior alone.

The Git binding requires every authorized namespace-changing path to obey single-step admission throughout the relevant interval. Therefore W6 must treat exclusive/narrow write authority and enforcement against alternate mutation paths as an explicit trusted test-environment assumption/configuration unless the provider offers independently verifiable enforcement that actually satisfies G5. Administrator bypass outside that boundary remains a trust assumption and must be reported as such.

## 8. W2 implementation deliverables

Before W4/W6 execution qualification, each independent Python/TypeScript candidate must provide:

- provider-neutral publication core;
- project-validation interface/binding;
- local-Git publication provider;
- GitHub publication provider;
- executable adapter for the shared black-box runner;
- deterministic unit tests;
- provider/mock/fault tests;
- explicit mapping from implementation tests to the 89 publication fixtures;
- deterministic shared publication conformance result;
- no live-provider execution claim.

Workers do not provision credentials, repositories, apps, branches, namespaces, or hosts.

Each W2 receipt should include the exact candidate SHA, changed paths, commands/results for deterministic tests, the 89/89 publication conformance result, provider/mock coverage, and a statement that live-provider execution was not performed.

## 9. Branch and integration rules

- W1 contract/scaffolding: r3/contract
- Python implementation: r3/python-publisher
- TypeScript implementation: r3/typescript-publisher
- integration: r3/integration

Both implementation branches start from the exact accepted W1 contract subject. Neither starts from or merges the other implementation branch during independent work.

Final integration should materialize the accepted final trees cleanly. It must not import unnecessary development/debug history merely because branches exist.

## 10. Later capability split

Repository-only work:

- W1 shared contract and scaffolding;
- W2 independent implementations;
- W3 static audit;
- W5 bounded corrections, integration, and evidence;
- W7 final evidence, audit, and adoption.

Execution-required work:

- W4 local Git/concurrency/fault execution;
- W6 disposable live-provider execution.

Deterministic unit, mock, and shared black-box conformance belongs in repository work and must not be deferred to W4/W6.

## 11. Evidence and claim discipline

R3 implementation workers may claim only what they execute or what shared deterministic conformance establishes.

In particular:

- passing the finite harness does not qualify real Git CAS, permissions, history retention, or GitHub enforcement;
- local-Git execution does not qualify GitHub;
- GitHub live execution does not remove the G5 trusted single-step environment assumption;
- no W1/W2 result establishes exactly-once external effects;
- no R3 artifact grants project authority or embeds Governance semantics in stateOwl core.
