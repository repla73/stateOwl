# Draft-2 correction verification

**Date:** 3 October 2026  
**Baseline:** `repla73/stateOwl@a3770c370a13002ca1bc0dfeae4b3af969b7976a`  
**Environment:** Python 3.13.5; jsonschema 4.26.0; Node.js v22.16.0. These are observed test versions, not product version pins.

## Executed commands

```sh
python docs/protocol/check_fixtures.py
python docs/protocol/check_fixtures.py --adapter python docs/protocol/harness_client.py
PYTHONPATH=src python -m unittest discover -s tests -v
```

Both complete protocol runs passed. The second passed the same cases through the documented JSONL provider interface in a separate process. It uses the **same finite model**, not an independent protocol implementation.

| Check | Final result |
|---|---|
| Protocol and harness JSON Schema 2020-12 metaschemas | 2 passed. |
| Valid/invalid structural vectors | 62 passed. |
| Read scenarios | 90 passed in-process and 90 through JSONL. |
| Publication scenarios | 56 passed in-process and 56 through JSONL. |
| Observation scenarios | 16 passed in-process and 16 through JSONL. |
| Strict source JSON | 24 accepted/rejected as specified, including negative zero and exact numeric limits. |
| Canonical base64 | 9 accepted/rejected as specified. |
| Publication identity | 14 assertions across 2 fixed preimage/canonical/hash vectors; change order, encoding and mode equivalence, binding/context differences. |
| General JCS serialization | 3 fixed vectors, including UTF-16 key order and ECMAScript number spelling. |
| Native Git blob identity | 2 real SHA-1/SHA-256 hash vectors. |
| Harness negative/self checks | 10 passed: fault/call validation, asset graph rejection and response/provenance mutation detection. |
| Unchanged legacy Reader | 6 golden cases passed in each complete protocol run, including actual read traces. |
| Existing runtime suite | All 10 tests passed: 6 core, 2 mocked GitHub transport, 2 deterministic benchmark-contract tests. |

The 162 scenarios contain fixed declarative expectations, **and** each was executed against the finite provider/fault model. This is stronger than draft 1's expectation-consistency checks, but it is not live-provider qualification. Early exits for malformed inputs, unsupported capabilities and denied access are deliberately part of those scenario counts.

## Provenance of actual legacy execution

The execution environment could not clone through public DNS. The connected GitHub tool supplied source; local test copies were verified against these existing repository Git blobs before execution. They were not edited or included in the correction publication.

| File | Verified original Git blob |
|---|---|
| `src/stateowl/core.py` | `eadb36a647f3940e7faab4504c028064ae0133a5` |
| `src/stateowl/github.py` | `30804a41d23f20731b1cf2e92a10e32589644bb1` |
| `src/stateowl/__init__.py` | `6539f6a1a255333707764bf38de3fc7a99a712c8` |
| `tests/test_core.py` | `7c20139ce39b8b428ac2d8887ba851e85a31f0e9` |
| `tests/test_github.py` | `b85eff0b20404e3c94e0d469425da732568d044d` |
| `tests/test_benchmark.py` | `7d1ca95fdfecccf53465877897322530c105e850` |
| `benchmarks/benchmark.py` | `f551d32066b49dc80e74eaf7991078199929eae9` |
| `docs/protocol/legacy-v0.1.0.json` | `239017533a80bb0f68b9bcb5ff8d87e6a71c1a67` |

The checker independently verifies the pinned legacy core blob on every run. The original API's generation remains 0.1.0; passing its goldens does not make it an implementation of draft 2.

## Evidence limits and next gate

**Real-provider protocol executions: zero.** No GitHub/local-Git production adapter, TypeScript implementation, plugin, MCP service, host deployment or R2 work was started. Publishing these documentation/test files is not a protocol-provider qualification run.

The conceptual commit/tag IDs are intentionally synthetic. The tests establish specified behavior under injected facts, including receipt discovery, complete candidate preservation, lost responses, reset/missing-history uncertainty and deterministic errors. They do not establish actual GitHub CAS semantics, authenticated Git object-chain proofs, platform retention, independent cross-language conformance, Governance compatibility, latency/token performance or external-effect guarantees.

Worker assessment: F01–F05 and the listed R1 conformance gaps are addressed; no known listed R1 gap remains. **Ready for independent R1 re-audit**, not independently accepted, stable, final or release-candidate.
