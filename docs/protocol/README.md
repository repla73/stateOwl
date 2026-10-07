# Protocol and conformance — draft 3

**Protocol:** `stateowl/0.2-draft.3`  
**Status:** The normative protocol remains **draft-3**, unchanged. R1–R5 stage evidence has been independently accepted and adopted; this file's wire ID is **not** a stable future protocol designation.  
**Scope:** Python R6 source metadata designates only the legacy-compatible reader/CLI stable surface. Qualified Python/TypeScript draft-3 readers, conditional publication, Pi execution and optional Python observe are in the [R6 matrix](../R6-CAPABILITY-MATRIX.md).

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

The protocol remains `stateowl/0.2-draft.3` and is **not** a stable wire release. Its semantics, original fixtures and legacy goldens are unchanged in R6. R2 exact reads, R3 guarded publication, R4 controlled Pi/OpenClaw execution and R5 optional Python observe have bounded accepted evidence, with the limits stated in the [R6 matrix](../R6-CAPABILITY-MATRIX.md). These files are published in source, not in a separately authorized registry artifact.
