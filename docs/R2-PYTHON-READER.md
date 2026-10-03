# R2 Python reader candidate

Candidate protocol: `stateowl/0.2-draft.3` / Git binding `stateowl.git-receipt/2`.

Read-only R2 modules are additive to the unchanged 0.1.0 reader:

- `stateowl.r2.R2Reader` — exact/current/batched reads, direct paths, projection, router-v1 and explicit one-level expansion.
- `stateowl.r2_memory.MemoryReadProvider` — opaque semantic test backend.
- `stateowl.r2_localgit.LocalGitReadProvider` — local Git object reads without worktree mutation.
- `stateowl.r2_github.GitHubReadProvider` — GitHub Git-data reads with uncached mutable refs and immutable-object caching.
- `stateowl.r2_legacy.R2LegacyReader` — 0.1.0 compatibility projection executed through the R2 reader.

Run the complete Python R2 tests, including the normative read and legacy corpora:

```sh
PYTHONPATH=src:tests python -m unittest discover -s tests -p 'test_r2*.py' -v
```

`tests/test_r2_conformance.py` executes the R2 runtime against `docs/protocol/read-cases.json`, `docs/protocol/fixtures.json`, and `docs/protocol/legacy-v0.1.0.json`. It does not import or execute `docs/protocol/harness.py`.

Run benchmarks:

```sh
python benchmarks/r2_read_benchmark.py --output benchmarks/results/r2-python-reader.json
```

The benchmark token count is explicitly an approximation (`ceil(UTF-8 bytes / 4)`). Simulated provider timing is not GitHub network latency.

The shared native `.state` interoperability fixture is intentionally not included in this candidate. It is pending the coordinator-owned, data-only fixture shared with both language implementations.

No publish/write API is provided by the R2 modules.
