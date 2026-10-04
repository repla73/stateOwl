# R2 integration evidence

## Frozen subjects

- Frozen R2 basis: `05278c225eb302697e8b31406d06f98022ab7d3c`
- Accepted Python subject: `5bc2ab4834bcb17c8dee352737752e887835da4a`
- Accepted TypeScript subject: `d61c17e946e631723e8fd8407e0707e14002864f`
- Shared native `.state` fixture subject: `60733bc765e029ebfde6102f5f2c265192cf95d9`
- W2/W3 execution subject: `3fa403f4a0067174f8d11272d1ea9577427c19bd`
- Integration branch: `r2/integration`

## W2 — language qualification

Python executed qualification:

- normative reads: `90/90`
- legacy: `6/6`
- Git identity/tag: `13/13`
- non-Git: PASS
- native `.state`: `8/8`
- complete R2 tests: `24/24`
- audit corrections: PASS
- exact mutable-ref resolutions: `0`
- current batch mutable-ref resolutions: `1`
- hidden repository crawl: `no`

TypeScript executed qualification:

- normative reads: `90/90`
- legacy: `6/6`
- Git identity/tag: `20/20`
- non-Git: PASS
- native `.state`: `8/8`
- complete tests: `38/38`
- strict serialization vectors: PASS
- audit corrections: PASS
- exact mutable-ref resolutions: `0`
- current batch mutable-ref resolutions: `1`
- hidden repository crawl: `no`

The repository was unmodified by W2 execution.

## W3 — differential

At execution subject `3fa403f4a0067174f8d11272d1ea9577427c19bd`:

- normative equivalence: `90/90`
- native-state equivalence: `8/8`
- mismatches: none

The differential was not rerun after qualification-only changes. Its evidence remains valid because no Python runtime source, TypeScript runtime source, shared fixture, protocol corpus, or `qualification/r2_differential.mjs` changed after the execution subject. Post-execution changes are limited to common-benchmark qualification/evidence files and this integration evidence document.

## Corrected common benchmark

Artifact: `benchmarks/results/r2-common-interoperability.json`

- SHA-256: `6657bf3945ab3bde7c096408e021336e7f01e7e8cc7addd82cd3b71cbaacef70`
- qualification pass: `true`
- successful focused reads: PASS
- fixed-router scaling: PASS
- growing-router selected context remains constant: PASS
- cross-language comparable: PASS
- benchmark `record_bytes`: `1048576`
- benchmark `response_bytes`: `1048576`

For both implementations, exact/current/batch-5 selected-context model bytes are `565` / `565` / `1787`. Fixed-router scales `0,10,100,1000` remain constant at `851` model-visible bytes with `1` mutable-ref resolution, `5` provider operations, `2` file reads, and `160` provider-returned bytes. Growing-router scales keep the same selected context and operation counts while provider-returned bytes grow `160`, `670`, `5440`, `54940`.

Evidence boundary: `deterministic in-memory qualification; not live GitHub performance`.

## Final audit and adoption

- Final integration audit: `R2_FINAL: PASS`
- Accepted integration subject: `f46bd672704ad0978578845e00f943605f087a74`
- Accepted tree: `6306981baa653ad5f38270d743333a6e4694c2f1`
- Clean adoption commit on `main`: `7e312068264513a0e66bdd1f0c728c7d5e79667c`
- R2 status: adopted
- R3 status: not started

## Integrity and status

Accepted Python runtime source, accepted TypeScript runtime source, and the shared native fixture remain byte-identical to their accepted subjects. No new Python runtime dependency or TypeScript runtime package dependency was introduced.

R2 remains read-only. No publication/write implementation, Git ref mutation/push support, scheduler, claims/leases, plugin/MCP infrastructure, or Governance semantics are present in stateOwl core.

R2 is adopted on `main`. R3 has not started.
