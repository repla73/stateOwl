# R2 integration

- Frozen basis: `05278c225eb302697e8b31406d06f98022ab7d3c`
- Python subject: `5bc2ab4834bcb17c8dee352737752e887835da4a`
- TypeScript subject: `d61c17e946e631723e8fd8407e0707e14002864f`
- Native fixture subject: `60733bc765e029ebfde6102f5f2c265192cf95d9`
- Integrated candidate: branch `r2/integration`; the exact published commit is recorded in the integration receipt.

## Qualification

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
npm --prefix typescript test
npm --prefix typescript run conformance
npm --prefix typescript run build
PYTHONPATH=src python benchmarks/r2_common_benchmark.py --output benchmarks/results/r2-common-interoperability.json
```

The common benchmark harness is `benchmarks/r2_common_benchmark.py` with the TypeScript runner `typescript/benchmarks/r2-common-runner.ts`. The committed result file initially records the previous independent common-benchmark evidence and identifies whether an integrated rerun has replaced it.

Evidence is deterministic/local unless explicitly stated otherwise. It does not claim live GitHub performance.

R2 remains read-only. No state publication API, ref mutation, scheduler, claims/leases, MCP/plugin infrastructure, or Governance semantics are introduced in core.

R3 has not started. R2 is not merged or complete until independent final integration audit passes.
