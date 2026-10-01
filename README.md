<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/final/stateowl-mark-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="branding/final/stateowl-mark-light.svg">
    <img src="branding/final/stateowl-mark-light.svg" alt="stateOwl owl mark" width="156">
  </picture>
</p>

<h1 align="center">stateOwl</h1>

<p align="center"><strong>Exact project state. Minimal context.</strong></p>

<p align="center">A GitHub-backed state reader for AI agents.</p>

---

## What is stateOwl

stateOwl retrieves the exact project state an agent needs without loading unrelated repository history or records into model context.

## What it aims to solve

AI sessions often waste context and API calls rediscovering structured project state. stateOwl provides a compact, predictable path to the current record that matters.

## How it solves it

1. Resolve the configured mutable Git ref fresh.
2. Read `.stateowl/router.json` at that exact commit.
3. Read only the selected route record.
4. Return selected fields with exact repository / commit / path / blob provenance.
5. Expand named linked detail only when requested.

## Install / use

Python 3.11+ with no runtime third-party dependencies.

```bash
python -m pip install "git+https://github.com/repla73/stateOwl.git"
```

CLI:

```bash
GITHUB_TOKEN=... stateowl owner/repo release --ref refs/heads/main
```

Python:

```python
from stateowl import GitHubStore, Reader

result = Reader(GitHubStore()).read(
    "owner/repo",
    "release",
    ref="refs/heads/main",
)
```

Public repositories can be read without `GITHUB_TOKEN`, subject to GitHub's unauthenticated rate limits.

## Features

- Fresh mutable-ref resolution
- Exact commit-bound reads
- Compact router-based state selection
- Field projection for model-visible results
- On-demand named detail expansion
- Exact repository / commit / path / blob provenance
- Bounded caching of immutable reads
- Read-only GitHub REST transport
- Provider-neutral core
- Deterministic efficiency benchmarks and tests
