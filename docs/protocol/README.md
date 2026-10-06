# Protocol and conformance — draft 3

**Protocol:** `stateowl/0.2-draft.3`  
**Status:** Draft; R1 protocol accepted; R2 read interoperability qualified and adopted; R3 guarded publication qualified and adopted. Not a stable release.  
**Scope:** R1 protocol/conformance accepted; R2 read interoperability adopted; R3 local-Git and GitHub guarded publication qualified and adopted. R4 hosted/native cross-plane continuity is next.

## Contract

| File | Purpose |
|---|---|
| [PROTOCOL.md](PROTOCOL.md) | Provider-neutral identities, focused reads, publication outcomes, observation and deterministic errors. |
| [git-binding-v2.md](git-binding-v2.md) | Typed Git identities, single-step admission policy, exact receipt grammar, bounded reconciliation and file modes. |
| [router-v1.md](router-v1.md) | Unchanged semantic `stateowl.router/v1` compatibility binding. |
| [schema.json](schema.json) | Closed protocol messages and compatibility shapes. |
| [HARNESS.md](HARNESS.md), [harness.schema.json](harness.schema.json) | Adapter-facing finite provider/fault interface and test containers. |
| [fixtures.json](fixtures.json) | Shared bytes, assets, structural, serialization, receipt-message and identity vectors. |
| [Read](read-cases.json), [publish](publish-cases.json), [observe](observe-cases.json) | Fixed expected results exercised against isolated provider worlds. |
| [legacy-v0.1.0.json](legacy-v0.1.0.json) | Six unchanged original Reader goldens. |
| [CHECKS.md](CHECKS.md) | Executed checks and their evidence limits. |

## Re-audit corrections

**F06 — Admission evidence.** Ancestry proves reachability, not every intermediate ref admission. Ancestry-based recovery now requires an enforced **single-step** policy for all authorized namespace update paths: each new head has the previous head as its sole parent. The harness represents actual ref transitions separately from the commit graph. Identical A–C–D graphs yield different results for A→C→D and A→D; skipped, weak or unknown admission histories cannot produce ancestry-based success or exclusion. Authenticated positive admission evidence remains stronger than later verification failure.

**F07 — Receipt grammar.** A message is exactly the receipt line, or the fixed heading `stateOwl publication` plus one blank line plus the receipt line. Both end in exactly one LF. Whole-message parsing rejects additional paragraphs, blank lines, heading whitespace, CRLF, inline markers and other nonconforming forms. Fixed positive and negative vectors exercise both parsing and reconciliation.

**N02 — Read capability.** Advertising `read` requires at least one supported format. Non-reader endpoints may still have an empty format list.

The protocol advances to draft 3, the changed Git semantic binding to `stateowl.git-receipt/2`, and the test container to `stateowl.fixtures/3`. Prior identifiers are not silently reinterpreted. Earlier F01–F05 corrections remain: semantic binding pins, snapshots without fabricated generations, canonical unordered publication identity without `operation_id`, read-only reconciliation, separate router semantics and deterministic outcomes/errors. `reachable_history` still makes no retention-duration promise.

## Run

Test prerequisites are Python, `jsonschema`, and Node.js for the **test-only ECMAScript/JCS oracle**. No product dependency is added.

```sh
python -m pip install -r docs/protocol/requirements-checks.txt
python docs/protocol/check_fixtures.py
python docs/protocol/check_fixtures.py --adapter python docs/protocol/harness_client.py
PYTHONPATH=src python -m unittest discover -s tests -v
```

Dependency installation is separate; the checks use no network. `harness_client.py` runs the **same finite Python model** through JSONL in another process, not an independent implementation. The model, codecs and Node helper are test infrastructure, not production adapters or services. No GitHub Actions workflow is added.

The corrected corpus retains the original 162 scenarios with version/identity updates, and adds 31 publication regressions: **90 read, 87 publication and 16 observation scenarios** in total. It also adds 21 direct receipt-message vectors and six structural vectors. See CHECKS for exact results.

## Boundary

The protocol remains `stateowl/0.2-draft.3` and is not a stable release. R1 protocol/conformance is accepted; R2 read interoperability is adopted; R3 local-Git and GitHub guarded publication is qualified and adopted. The Charter, package version, protocol semantics, original tests and legacy goldens remain unchanged by this status sync. R4 hosted/native cross-plane continuity is next; automation remains a later gate.
