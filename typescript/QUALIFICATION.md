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

## R2 read evidence

- normative R2 read scenarios: 90/90 passed on candidate `80a9c16a74359794e235e95b9bcd826d22edd12f`;
- frozen legacy 0.1.0 goldens: 6/6 passed;
- exact reads: 0 mutable-root resolutions;
- current batch reads: 1 mutable-root resolution;
- local Git provider uses a real temporary repository without changing the checked-out branch;
- GitHub provider is read-only; no remote write API is present;
- opaque non-Git exact read passes;
- SHA-1/SHA-256 and tag cases pass;
- benchmark regression passes.

The TypeScript reader/provider source blobs were rechecked byte-identically against `80a9c16a74359794e235e95b9bcd826d22edd12f` during the native-fixture continuation. No implementation change was required.

## Shared native `.state` qualification

Fixture source:

`r2/native-state-fixture@60733bc765e029ebfde6102f5f2c265192cf95d9`

The coordinator-owned fixture files are copied into this branch by their exact Git blob identities, without byte modification.

Executed through the real TypeScript `Reader`:

- 8/8 shared native-state cases PASS;
- current project pointer PASS;
- task state PASS;
- same-snapshot batch PASS;
- text detail PASS;
- projection PASS;
- direct project-owned `.state` addressing PASS;
- exact read PASS with 0 mutable-ref resolutions;
- current batched read PASS with 1 mutable-ref resolution;
- hidden repository crawl: none;
- `.stateowl/router.json` required/read: no.

The fixture's byte length, SHA-256 digest, and Git SHA-1 blob identity assertions are checked by `test/native-fixture.test.ts`.

A01 is resolved solely because the coordinator-owned fixture now supplies the previously missing normative test input. No Governance semantics are interpreted by core stateOwl.

## Evidence boundary

No authenticated live GitHub network execution was available from the local qualification runtime, so GitHub transport qualification remains mocked/provider-level rather than `github_real_read_only`. Local Git evidence is real. Benchmark evidence remains `mixed`.

No write support, publication, branch mutation API, server, tunnel, MCP binding, or integration packaging was added.
