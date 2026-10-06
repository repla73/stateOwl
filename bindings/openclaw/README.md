# stateOwl OpenClaw binding

R4 native OpenClaw tool plugin.

It exposes exactly two agent tools:

- `stateowl_read`
- `stateowl_publish`

The binding delegates read and publication semantics directly to the accepted TypeScript stateOwl implementation in `typescript/`. It does not launch Python, Git, MCP, a daemon, a remote service, a scheduler, a database, or another execution engine.

## OpenClaw SDK surface

The implementation uses the current native plugin contract:

- `definePluginEntry` from `openclaw/plugin-sdk/plugin-entry`;
- `api.registerTool(...)` for agent-visible tools;
- `api.pluginConfig` for entry-scoped resolved runtime configuration;
- `openclaw.plugin.json` `contracts.tools` for cold capability discovery.

Qualification must fresh-record the exact OpenClaw runtime and Node versions rather than treating this repository as a runtime-version authority.

## Configuration

Configure the plugin under trusted OpenClaw runtime configuration:

```json5
{
  plugins: {
    entries: {
      stateowl: {
        config: {
          repository: "owner/repository",
          namespace: "refs/heads/stateowl-r4-qualification",
          githubToken: { source: "env", id: "STATEOWL_GITHUB_TOKEN" },
          publishEnabled: true,
          singleStepContinuity: true,
          writePaths: ["state/work.json"]
        }
      }
    }
  }
}
```

`githubToken` is declared as a manifest secret input. OpenClaw resolves it before the plugin receives runtime config. The binding never writes the credential into stateOwl requests, handoff artifacts, model-facing tool content, or qualification evidence.

Publication is disabled unless `publishEnabled` is true. Enabling it additionally requires trusted `singleStepContinuity` and at least one configured write path. The accepted stateOwl Publisher remains responsible for R3 validation, four-outcome semantics, exact receipt/OID proof, guarded admission, and read-only reconciliation.

## Tool inputs

`stateowl_read` accepts one bounded `handoffJson` string containing the exact `stateowl.r4-handoff/1` artifact. The binding verifies the frozen R4 profile identity and exact configured target, maps it to one direct-path stateOwl read, and passes the request to the accepted Reader.

`stateowl_publish` accepts one bounded `requestJson` string. It is passed unchanged to the accepted stateOwl Publisher. The binding does not parse/rewrite publication mode or outcome semantics; lightweight parsing is used only to count requested paths for qualification evidence.

## Qualification evidence

Model-facing content is only the JSON stateOwl semantic result. OpenClaw `details.evidence` records:

- declared/discoverable tool names;
- exact model-visible request/result byte counts;
- GitHub REST/GraphQL provider-operation count;
- requested state paths;
- provider-observed state paths outside the requested set.

Runtime capability discovery is independently checked during qualification with:

```sh
openclaw plugins inspect stateowl --runtime --json
```

The implementation task performs no live GitHub state writes.
