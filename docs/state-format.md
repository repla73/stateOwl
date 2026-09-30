# State format

stateOwl 0.1.x uses a deliberately small convention.

## Router

The default router path is `.stateowl/router.json`.

```json
{
  "schema": "stateowl.router/v1",
  "routes": {
    "release": {
      "path": "state/release.json",
      "select": ["id", "status", "next"]
    }
  }
}
```

Each route names one repository-relative JSON record and the top-level fields to expose by default.

## Linked detail

A selected record may expose optional named links:

```json
{
  "id": "release",
  "status": "working",
  "links": {
    "detail": {
      "path": "state/release-detail.md",
      "format": "text"
    }
  }
}
```

Links are non-recursive in 0.1.x. Cross-repository links must include an exact commit.

## Provenance

Results identify the current resolved head and exact source files by repository, commit, path, and Git blob ID. The mutable ref itself is never treated as an immutable identity.
