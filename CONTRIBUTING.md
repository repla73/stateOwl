# Contributing

stateOwl is intentionally small. Contributions should preserve that property.

## Development

```bash
python -m unittest discover -s tests -v
python benchmarks/benchmark.py
```

The runtime should remain dependency-light. New runtime dependencies need a concrete benefit that cannot reasonably be achieved with the standard library.

## Design constraints

Changes should preserve:

- fresh reads for mutable refs;
- exact commit-bound file reads;
- compact default results;
- explicit detail expansion;
- provenance in every selected result;
- no repository-wide discovery in the focused path;
- read-only scope for the 0.1.x line unless a later release explicitly changes it.

Provider integrations belong behind adapters and must not force provider-specific infrastructure into the core.

## Pull requests

Keep changes focused and include tests for changed behavior. If efficiency behavior changes, update the benchmark and explain the difference.
