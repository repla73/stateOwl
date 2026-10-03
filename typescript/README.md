# stateOwl R2 TypeScript reader

Independent TypeScript implementation of the read semantics in `stateowl/0.2-draft.3` and the Git read rules accompanying `stateowl.git-receipt/2`.

## Scope

- exact and current reads;
- batched selections and direct paths;
- `stateowl.router/v1` compatibility and one-level expansion;
- SHA-1/SHA-256 Git identities and annotated-tag peeling;
- opaque non-Git snapshots through the in-memory semantic provider;
- read-only local Git and GitHub providers;
- strict UTF-8/JSON/base64/number handling and raw-byte SHA-256 provenance;
- the six frozen 0.1.0 legacy read goldens.

This candidate contains no publication/write path, server, daemon, MCP binding, agent SDK, database, or web framework. It does not invoke Python or depend on the Python stateOwl runtime.

## Commands

```sh
npm run build
npm test
npm run conformance
npm run benchmark
```

`npm run conformance` consumes the language-neutral normative corpus at `../docs/protocol/{fixtures,read-cases}.json`; it executes this TypeScript reader, not the Python harness implementation.

## Providers

`MemoryProvider` is an opaque-ID-capable semantic provider used for conformance and non-Git proof. `LocalGitProvider` uses Git object/ref commands and does not switch or modify the product worktree. `GitHubReadProvider` uses read-only GitHub API transport calls and exposes no write API.

## Runtime

No runtime package dependencies are required. Node.js provides JSON/UTF-8/crypto/fetch primitives. The local Git provider additionally requires the `git` executable. No `engines` restriction is imposed by this draft; the qualification run records the versions actually tested.

## Known protocol input gap

The frozen R2 basis does not contain the sanitized native `.state` fixture/profile that the architecture requires before native Governance compatibility can be claimed. The implementation therefore does not invent Governance routing semantics. See `PROTOCOL-AMBIGUITIES.md`.
