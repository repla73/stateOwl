# R2 TypeScript read qualification

**Basis:** `05278c225eb302697e8b31406d06f98022ab7d3c`  
**Protocol:** `stateowl/0.2-draft.3`  
**Git binding:** `stateowl.git-receipt/2`

## Tested environment

- Node.js `v22.16.0`
- npm `10.9.2`
- TypeScript `5.8.3`
- Git `2.47.3`
- Linux x64

These are observed qualification versions, not product version pins. The package declares no Node `engines` restriction and has no runtime package dependencies.

## Executed evidence

```sh
npm test
npm run conformance
npm run benchmark
```

Final results:

- implementation/provider/vector tests: 23/23 passed;
- normative R2 read scenarios: 90/90 passed;
- frozen legacy 0.1.0 goldens: 6/6 passed inside the test suite;
- exact reads: 0 mutable-root resolutions observed;
- current batch reads: 1 mutable-root resolution observed and repeated file work deduplicated;
- local Git test uses a real temporary repository without switching the checked-out branch;
- GitHub provider tests are mocked/read-only; no remote write API is present;
- opaque non-Git exact-read case passes;
- normative SHA-1/SHA-256 and tag cases pass;
- benchmark artifact: `benchmarks/results.json`.

The conformance runner consumes the frozen language-neutral fixture corpus and executes the TypeScript reader directly. It does not run or import the Python stateOwl implementation.

## Evidence boundary

No authenticated live GitHub network execution was available from the local qualification runtime, so GitHub transport qualification is mocked/provider-level rather than `github_real_read_only`. Local Git evidence is real. Benchmark evidence is therefore `mixed` (in-memory semantic measurements plus real local-Git measurements).

Native `.state` compatibility remains blocked by the missing normative sanitized fixture/profile described in `PROTOCOL-AMBIGUITIES.md`. No project-specific Governance behavior was inferred or imported.

No write support, publication, branch mutation API, server, tunnel, MCP binding, or integration packaging was added.
