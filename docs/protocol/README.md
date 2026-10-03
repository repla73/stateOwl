# Protocol and conformance — draft 2

**Protocol:** `stateowl/0.2-draft.2`  
**Stage:** R1 correction prepared for independent re-audit; not stable or independently accepted.  
**Scope:** Specification, fixtures and offline test infrastructure. R2 has not started.

## Contract

| File | Purpose |
|---|---|
| [PROTOCOL.md](PROTOCOL.md) | Provider-neutral identities, focused reads, publication outcomes, observation and deterministic errors. |
| [git-binding-v1.md](git-binding-v1.md) | Typed Git identities, tag peeling, file modes, atomic receipt representation and bounded reconciliation. |
| [router-v1.md](router-v1.md) | Self-contained optional `stateowl.router/v1` compatibility binding. |
| [schema.json](schema.json) | Closed protocol messages and compatibility shapes, JSON Schema 2020-12. |
| [HARNESS.md](HARNESS.md) | Adapter-facing provider/fault interface and fixture format. |
| [harness.schema.json](harness.schema.json) | Closed test case/world/fault containers. |
| [fixtures.json](fixtures.json) | Exact bytes, shared assets, structural/serialization/hash vectors and scenario index. |
| [Read](read-cases.json), [publish](publish-cases.json), [observe](observe-cases.json) | Fixed expected scenarios executed against finite provider worlds. |
| [legacy-v0.1.0.json](legacy-v0.1.0.json) | The unchanged six original Reader goldens. |
| [CHECKS.md](CHECKS.md) | Executed commands, results and evidence limits. |

## Correction decisions

| Finding | Draft-2 decision |
|---|---|
| F01 — binding identity | One pinned semantic identifier shared by independent implementations; no implementation-code digest. |
| F02 — Git generation | Ordinary snapshots contain only typed/scoped immutable identity. No invented incarnation counter; write continuity is an explicit trust boundary. |
| F03 — receipt discovery | Canonical identity in a commit-message receipt, sole expected parent, complete candidate verification and a bounded linear-history walk. Missing history stays uncertain. |
| F04 — legacy compatibility | A separately versioned normative binding defines supported router/link behavior without requiring Python knowledge. |
| F05 — determinism | Exact result cardinality/order, minimal outcome-specific fields, fixed error codes/retry classes and ordered validation stages. |
| N02 — replay identity | Remove `operation_id`. Hash the normalized unordered change set, target, expected state and validation pin. `reconcile` cannot dispatch. |
| N03 — retention | `reachable_history` has precise storage semantics, not a free-text or time-based guarantee; lookup is numerically bounded. |

The archived [architecture](../ARCHITECTURE-DECISION.md), [roadmap](../ROADMAP.md), Charter, product runtime, adapters and package version are unchanged. The correction assignment accepts R0 for this work; historical wording in the archived package remains intact.

## Run

Test prerequisites: Python, `jsonschema`, and Node.js for the **test-only ECMAScript/JCS oracle**. These are not new product/runtime dependencies. Install the existing test requirements in a test environment if needed:

```sh
python -m pip install -r docs/protocol/requirements-checks.txt
python docs/protocol/check_fixtures.py
python docs/protocol/check_fixtures.py --adapter python docs/protocol/harness_client.py
PYTHONPATH=src python -m unittest discover -s tests -v
```

The first command installs test dependencies; the checks themselves use no network. `harness.py` is a finite specification model, and `harness_client.py` tests the JSONL interface using that same model in another process. Neither is a production adapter or an independent implementation. `fixture_codec.py` and `ecma_oracle.js` test serialization; they expose no stateOwl service. No GitHub Actions workflow is added.

The corpus contains 90 read, 56 publication and 16 observation scenarios. The checker validates fixed expected outputs and actual simulated traces, including zero-dispatch reconciliation and complete candidate bytes/modes. Six separate tests execute the unchanged legacy Reader. See CHECKS for the exact counts of structural and serialization assertions.

## R1 boundary

The listed R1 correction gaps are covered for re-audit. Independent review still decides acceptance. Real GitHub/local-Git write qualification, independent-language agreement, real Governance fixtures, hosted-plane continuity and automation qualification remain later gates. Synthetic graph execution is not evidence of real-provider concurrency, history retention or object-chain integrity.
