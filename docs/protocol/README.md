# Protocol and conformance — working draft

**Draft:** `stateowl/0.2-draft.1`  
**Stage:** R1 started; not accepted as complete or stable.  
**Scope:** Specification, declarative fixtures and offline checks. No new runtime, provider, plugin or deployment.

## Contents

| File | Purpose |
|---|---|
| [PROTOCOL.md](PROTOCOL.md) | Normative draft for exact/current reads, guarded publication, uncertain outcomes, observation, identity, provenance and legacy compatibility. |
| [schema.json](schema.json) | Closed JSON Schema 2020-12 message definitions; no remote schema dependencies. |
| [fixtures.json](fixtures.json) | Shared exact bytes, 36 structural vectors, 11 strict JSON vectors, one receipt-digest vector and scenario file index. |
| [Read](read-cases.json), [publish](publish-cases.json), [observe](observe-cases.json) cases | 39 concrete behavioral scenarios grouped by operation. |
| [legacy-v0.1.0.json](legacy-v0.1.0.json) | Six golden cases preserving the existing reader's own output and error shapes. |
| [check_fixtures.py](check_fixtures.py) | Offline corpus consistency checks and executable legacy-reader checks. |
| [CHECKS.md](CHECKS.md) | What was executed, its baseline and the limits of the results. |

The [architecture decision](../ARCHITECTURE-DECISION.md), [roadmap](../ROADMAP.md) and [research record](../SOURCES.md) are preserved as the original architecture package. Their historical status text is unchanged. The subsequent instruction to save that package and start the protocol authorizes this draft work; it does not itself establish independent review, a stable protocol or completed roadmap gates.

## Run the checks

From a repository checkout, in a test environment:

```sh
python -m pip install -r docs/protocol/requirements-checks.txt
python docs/protocol/check_fixtures.py
```

`jsonschema` is a test-only dependency. The existing stateOwl runtime and package requirements are unchanged. No network is used by the checker; dependency installation is a separate setup step. No GitHub Actions workflow is added.

## Fixture contract

`fixtures.json` embeds exact base64 source bytes and SHA-256 digests. Each scenario has a concrete `request`, expected `response`, named normative `rules`, declarative provider facts in `given`, and optional expected instrumentation in `trace`. Repeated requests deliberately describe different provider outcomes. Origin overrides in a returned source identify separate, explicitly pinned stores; the supplied fixture bytes for those paths are the same in this initial corpus.

The checker validates both messages, source digests, selected values, missing fields, receipt preimages and outcome consistency with the declared facts. Trace entries are expectations for a future instrumented adapter, **not observed provider traces**. Facts such as admission, changed heads, retained history and authority come from `given`; this checker does not establish them against a real provider.

The strict JSON vectors test parsing before projection, including duplicate keys, invalid UTF-8, surrogates, non-finite and unrepresentable numbers. The receipt vector binds exact decoded bytes, expected state, ordered changes and validator identity. It additionally checks UTF-8/base64 equivalence and change-order sensitivity. Canonicalization in the checker is restricted to the draft's fixed-ASCII-key, integer-only receipt envelope; it is not a general RFC 8785 implementation.

`legacy-v0.1.0.json` is separate. Its cases actually invoke the repository's existing `Reader` with an instrumented in-memory store, comparing full golden outputs/errors and read traces. These are legacy regression cases, not evidence that 0.1.0 implements the new draft.

## Remaining R1 work

The draft still needs independent contract review and an implementation-facing provider/fault-harness interface. The current scenarios do not execute new read, publish or observe implementations. Extend the corpus for tag-object graphs, hash-format variants, malformed routing, namespace retention/reset proofs, file-mode preservation and the full error/limit surface before calling it a complete conformance suite.

Native Governance compatibility needs separately authorized real fixtures; none is claimed here. Cross-language agreement, actual concurrent publication, interrupted provider requests, cross-plane continuation and zero-idle-model automation belong to later implementation/qualification gates.

Snapshot generations, numerical restrictions and the receipt envelope are explicit draft design choices derived from the architecture—not features retroactively added to 0.1.0. Review them before stabilizing the wire contract. The source package version remains 0.1.0.
