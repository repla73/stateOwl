# Migration from Python 0.1.0

## No state migration for the supported compatibility path

The prepared Python `0.2.0` source preserves `from stateowl import Reader, GitHubStore`, `Reader(GitHubStore()).read(repository, route, ref=...)`, and the `stateowl` CLI. Six frozen 0.1.0 goldens cover response/traces. Existing `.stateowl/router.json` and records remain unchanged. A current read still re-resolves its mutable ref. `0.1.0` is not a separately maintained security line.

Install from a **pinned, accepted/adopted Git SHA**, not a floating branch. No registry publication is claimed. Import and CLI package tests are required on the exact accepted candidate before any later public release.

## Optional new draft-3 behavior is a different API

`stateowl.r2.R2Reader` and the independent TypeScript `@stateowl/reader@0.2.0-draft.3` use request/result messages with exact `protocol: "stateowl/0.2-draft.3"`, provider capabilities and typed snapshot identities. They support direct paths, batches, optional `stateowl.router/v1` and native `.state` without a duplicate router. Do **not** silently replace legacy calls with these distinct signatures; unsupported versions/features fail closed.

R3 publication is **not** an added `Reader` method. It needs a trusted validator, allowed paths, expected-old admission, enforced namespace single-step continuity and later verification/reconciliation. Optional Python R5 observe requires a caller-owned HMAC secret and expiring scopes. The Pi extension is separately configured; OpenClaw and ChatGPT do not get plugins installed by importing this package. The R5 gate/effect target remain qualification code, not production workflow ownership.

See [matrix](R6-CAPABILITY-MATRIX.md), [security](../SECURITY.md), [reproduction](R6-REPRODUCTION.md) and [manifest](R6-RELEASE-MANIFEST.md).
