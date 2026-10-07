# Independent TypeScript stateOwl implementation

**Package source:** `@stateowl/reader@0.2.0-draft.3` (still prerelease; **not** a published npm package). **Normative protocol:** `stateowl/0.2-draft.3`; Git receipt `stateowl.git-receipt/2`. No change to either contract is implied by Python source version 0.2.0.

## Implementation and evidence

R2 independent TypeScript `Reader`: exact/current/batched/direct reads, legacy `stateowl.router/v1`, native `.state`, strict UTF-8/JSON/JCS/base64, SHA-1/SHA-256 Git identity, annotated tags, opaque in-memory non-Git semantics and six frozen legacy goldens. In-memory, real local Git and GitHub read providers are present, without a Python subprocess.

R3 `Publisher`: guarded GitHub and local-Git publication, receipt verification and bounded reconciliation. **Trusted project validation, path authorization, single-step namespace continuity and retention are external prerequisites.** A provider does not enforce exclusivity against arbitrary GitHub writers. See [R3 integration evidence](../docs/R3-INTEGRATION.md).

R4 Pi extension is [documented separately](../bindings/pi/README.md) and qualified in one controlled environment. Python R5 optional observe is **not** a TypeScript feature. R5 pre-model gate and disposable effect target are qualification-only.

## Reproduce

From `typescript/` in a fresh exact-source checkout:

```sh
npm install
npm run build
npm test
npm run conformance
npm run benchmark
```

`npm install` provides the **development-only** TypeScript compiler (no runtime npm dependencies). Applicable local-Git tests also need Git. No mandatory Node version pin is imposed; [historical R2 tested versions](QUALIFICATION.md) are observations, not general support certification. See [R6 reproduction](../docs/R6-REPRODUCTION.md) for cross-language differential tests, identical fixture benchmarks and scope restrictions.

No stable npm package, hosted service, mandatory MCP server, durable non-Git storage, or OpenClaw plugin is shipped from this directory.
