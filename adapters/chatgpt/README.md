# ChatGPT reference adapter

This adapter documents the smallest ChatGPT-side behavior for a repository that uses stateOwl. It introduces no server, database, daemon, tunnel, or separate GitHub credential when an existing GitHub connection can perform the required exact reads.

## Focused read

1. Fresh-resolve the requested mutable ref to its current commit.
2. Read `.stateowl/router.json` at that exact commit.
3. Read only the selected route record at the same commit.
4. Return projected fields plus exact repository / commit / path / blob provenance.
5. Read a named linked record only when the session requires it.
6. Re-resolve the mutable ref on the next logical read.

Conceptual model-facing input:

```json
{
  "repository": "owner/repo",
  "route": "release",
  "ref": "refs/heads/main",
  "expand": ["detail"],
  "expected_head": "optional-exact-commit"
}
```

The returned shape should match the provider-neutral `Reader.read()` contract. Do not add repository history, sibling records, or broad search results to model context unless the caller explicitly asks for them.

## Adapter boundary

The adapter is read-focused. It does not define generic GitHub writes, lifecycle authority, deployments, approvals, or provider identity semantics.
