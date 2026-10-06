# stateOwl Pi binding

R4 native binding for Pi.

The binding exposes exactly two model-callable tools:

- `stateowl_read`
- `stateowl_publish`

Both delegate to the accepted TypeScript stateOwl implementation in-process. The binding does not implement stateOwl read/publication semantics itself and does not launch Python, Git, a daemon, an MCP server, or another execution engine.

## Qualification loading

Build the accepted TypeScript package from the same repository subject:

```sh
cd typescript
npm run build
cd ..
```

Configure one exact GitHub state target:

```sh
export STATEOWL_TARGET_REPOSITORY='owner/repository'
export STATEOWL_TARGET_NAMESPACE='refs/heads/stateowl-r4-qualification'
```

`STATEOWL_GITHUB_TOKEN` is optional for authorized public reads and required when the selected GitHub operation requires authentication.

Publication is fail-closed by default. Enable it only for an explicitly controlled single-step namespace and exact write paths:

```sh
export STATEOWL_PUBLISH_ENABLED=1
export STATEOWL_SINGLE_STEP_CONTINUITY=1
export STATEOWL_WRITE_PATHS='state/work.json'
```

Then load the extension directly from the checked-out exact subject:

```sh
pi --extension ./bindings/pi/index.ts
```

W4 records the actual Pi, Node, stateOwl subject, authentication source category, and cold-start/install observations. This binding does not impose a new runtime version pin.

## Credential boundary

The GitHub token, when present, is read from the Pi process environment and passed only to the accepted stateOwl GitHub transports. It is not placed in tool arguments, tool results, durable handoff artifacts, or repository evidence.

## Scope

The binding restricts reads and publications to the configured repository and namespace. Publication additionally requires explicit enablement, trusted single-step continuity for the disposable qualification namespace, and an allowlist of write paths.

Unsupported publication remains visible through the accepted stateOwl `UNSUPPORTED_CAPABILITY` semantics when publication is not enabled.
