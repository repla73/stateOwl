# Contributing

Keep stateOwl small, portable and contract-driven. The [R6 capability matrix](docs/R6-CAPABILITY-MATRIX.md) distinguishes a narrow supported Python reader/CLI from qualified draft/conditional APIs.

## Reproduce

```sh
python -m pip install -e .
python -m pip install -r docs/protocol/requirements-checks.txt
python -m unittest discover -s tests -v
python docs/protocol/check_fixtures.py
python docs/protocol/check_fixtures.py --adapter python docs/protocol/harness_client.py
cd typescript
npm install
npm test
npm run conformance
cd ..
node qualification/r2_differential.mjs
```

Benchmarks, accepted evidence and their provider/network boundaries: [R6 reproduction](docs/R6-REPRODUCTION.md). **Do not** replay R3 live-GitHub writes against real project state, provision tokens/hosts or modify OpenClaw merely to refresh historical tests. New runtime dependencies must justify their benefit; observed tested tool versions are not required contributor pins.

## Preserve invariants

Mutable refs resolve freshly, exact results carry commit/path/blob provenance, direct native `.state` access needs no duplicate router, selected state remains compact, expansion is explicit, guarded publication requires a real trusted validation boundary, and ambiguous publication remains unresolved rather than automatically repeated. Legacy 0.1.0 goldens stay valid. Project-level eligibility, scheduling, effects and infrastructure do not belong in stateOwl core.

Changes to runtime behavior require focused regression tests and contract parity where applicable. Benchmark claims must separate provider work, model-visible bytes and cold-start costs from simulated/live measurements.
