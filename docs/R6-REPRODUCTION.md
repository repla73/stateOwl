# R6 independent conformance and focused-read benchmark reproduction

**Freeze:** run against the **immutable frozen R6 candidate commit**, not floating main. These instructions make the accepted R2–R5 evidence reproducible where a real language toolchain is available. Python >=3.11, Node/npm, Git, and test-only `jsonschema` are needed; observed historical versions are **not mandatory pins**.

## Portable local run

From repository root, without GitHub write credentials:

```sh
python -m pip install -e .
python -m pip install -r docs/protocol/requirements-checks.txt
python -m unittest discover -s tests -v
python docs/protocol/check_fixtures.py
python docs/protocol/check_fixtures.py --adapter python docs/protocol/harness_client.py
cd typescript
npm install
npm run build
npm test
npm run conformance
cd ..
node qualification/r2_differential.mjs
```

The `harness_client.py` JSONL adapter runs the **same finite Python protocol model** in another process: **not** an independent language implementation. The distinct Python R2 reader and TypeScript reader plus `qualification/r2_differential.mjs` supply language-independent interoperability evidence. Test files exercise unsupported protocol, malformed/error outcomes, native `.state`, legacy compatibility, actual local Git and guarded publication; inspect the actual run receipt before claiming PASS.

## Reproduce the deterministic focused-read comparison

Use a disposable, caller-owned output location (not committed historical results):

```sh
python benchmarks/r2_read_benchmark.py --output /tmp/stateowl-r2-read.json
python benchmarks/r2_common_benchmark.py --output /tmp/stateowl-r2-common.json
cd typescript
npm run benchmark
```

The common script invokes the TypeScript benchmark runner and compares both languages over the same in-memory fixtures. Its accepted [results](../benchmarks/results/r2-common-interoperability.json): Python and TypeScript model-visible bytes **565 exact / 565 current / 1787 batch-five**; exact read resolves **0** mutable refs; current batch resolves **1**. Fixed-router unrelated counts **0, 10, 100, 1000** retain **851 selected bytes, 5 provider operations**, while growing-router transfer bytes increase **160 → 54,940**. The direct pinned-file baseline is **20** model-visible bytes in this fixture and can outperform stateOwl on that metric.

**Evidence type:** deterministic in-memory, **not** live GitHub latency, throughput, security, tokenizer-exact tokens or a universal savings percentage. Router bytes/provider transfer/cold-start may grow even if selected-context bytes remain fixed. Do not compare [original Python](../benchmarks/results/r2-python-reader.json) and [TypeScript](../typescript/benchmarks/results.json) timing as if their environments/fixtures were identical. The `/tmp` examples are contributor scratch; governed host operations use their separate host policy.

## Accepted historic result locators and R6 gap

| Source | Prior accepted outcome | Evidence boundary |
| --- | --- | --- |
| [R1 protocol](protocol/CHECKS.md) | 90 read, 87 publish, 16 observe finite scenarios and strict errors | Finite model, not a production provider. |
| [R2 integration](R2-INTEGRATION.md) | Python/TS 90/90 read each; 6/6 legacy each; 8/8 native state each; differential 90/90 + 8/8 | Real local-Git plus modeled providers. |
| [R3 integration](R3-INTEGRATION.md) | Python/TS 89/89 publication each; local-Git 12/12 each; four real disposable GitHub transitions | R3 single-step assumed externally and positively qualified only within its disposable namespace. |
| [R4 integration](R4-INTEGRATION.md) | Pi + fresh OpenClaw agent continuation and GitHub guarded publication | Execution/qualification, not OpenClaw plugin install. |
| [R5 integration](R5-INTEGRATION.md) | Full 92/92, explicit 15/15, 1,000 idle and recovery matrix | Tokyo Python 3.12.3 / Git 2.43.0; test-only target, no live provider writes. |

The table **reuses accepted past evidence** and does not claim these suites ran again during R6 authorship. Before R6 PASS, a **separate non-authoring auditor** needs an actual checkout to verify the R6 metadata/import/wheel packaging, TypeScript fresh install/build/test/conformance, 0.1.0 compatibility and fail-closed errors. Missing runnable evidence is a blocker, not an invented PASS. Do not rerun R3 live destructive/disposable GitHub qualification or R5 OpenClaw 1,000-idle execution without a specific material regression. No GitHub Actions, new PAT or host change is required.
