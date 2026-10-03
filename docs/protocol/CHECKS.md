# Draft corpus verification

**Date:** 3 October 2026  
**Environment:** Python 3.13.5; jsonschema 4.26.0.  
**Command:** `python docs/protocol/check_fixtures.py`

| Check | Result |
|---|---|
| JSON Schema 2020-12 metaschema validation | Passed. |
| 36 valid/invalid structural vectors | Passed. |
| 39 scenario request/response pairs | Passed structural and declared-expectation consistency checks. |
| 11 strict JSON vectors | Passed expected acceptance/rejection. |
| One exact receipt vector | Passed preimage, canonical bytes and SHA-256 checks. Equivalent byte encodings preserve identity; reordered changes do not. |
| Three noncanonical base64 cases | Rejected. |
| Six legacy reader cases | Passed golden output/error comparisons and instrumented read traces. |

The legacy source used for this run was `src/stateowl/core.py` from `repla73/stateOwl@213079f2ea2fa45e0c659339183130fd4c265226`. Its 11,770 bytes were verified against Git blob `eadb36a647f3940e7faab4504c028064ae0133a5` before execution. Tests ran on local copies; a full repository checkout was not available.

**Not executed:** the complete existing test suite, a new protocol implementation, independent-language adapters, real-provider publication races or interruption tests, hosted integrations, Governance-profile qualification, latency/token benchmarks or automation runs.

The 39 scenarios are expected behavior, not 39 successful provider executions. Passing these checks establishes corpus consistency and the tested legacy behavior only. It does not establish R1 acceptance, production readiness, independent conformance or a stable release.
