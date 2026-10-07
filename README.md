<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/final/stateowl-mark-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="branding/final/stateowl-mark-light.svg">
    <img src="branding/final/stateowl-mark-light.svg" alt="stateOwl owl mark" width="156">
  </picture>
</p>
<h1 align="center">stateOwl</h1>
<p align="center"><strong>Exact project state. Minimal context.</strong></p>

stateOwl retrieves exact project records without loading unrelated repository history into an agent's context. The project has **no mandatory scheduler, database, identity service or hosted MCP server**.

## R6 source release: what is actually supported

**Python `0.2.0`** is the proposed source-version designation for a **narrow stable compatibility surface**: the existing `stateowl.Reader` / `stateowl.GitHubStore` focused GitHub reader and `stateowl` CLI, retaining the frozen 0.1.0 behavior. This is **not** a claim that every module in the distribution has a stable API.

Independent Python `stateowl.r2.R2Reader` and TypeScript `@stateowl/reader@0.2.0-draft.3` are qualified for the **exact draft protocol** `stateowl/0.2-draft.3`; the TypeScript package remains prerelease source. R3 local-Git/GitHub guarded publication is qualified only with an actual trusted project validation/authorization boundary, externally enforced single-step namespace continuity and retrievable receipts. Python R5 optional observe is implemented; TypeScript observe is not. Pi is a qualified native extension; OpenClaw was exercised through ordinary agent execution, **not** through a shipped OpenClaw plugin. ChatGPT is a connector-assisted recipe, **not** a shipped hosted MCP/plugin.

See the [capability matrix](docs/R6-CAPABILITY-MATRIX.md), [reproduction guide](docs/R6-REPRODUCTION.md), [0.1 migration guide](docs/R6-MIGRATION.md) and [manifest](docs/R6-RELEASE-MANIFEST.md). This repository contains source artifacts; **no public tag, GitHub release, PyPI/npm publication or deployment has been authorized or performed**.

## Existing Python reader and CLI

Python 3.11+, with no runtime third-party Python dependencies. After independent R6 acceptance and clean adoption, install from an **exact verified adopted commit** (not an unpinned moving branch):

```sh
python -m pip install "git+https://github.com/repla73/stateOwl.git@<adopted-main-sha>"
```

```sh
GITHUB_TOKEN=... stateowl owner/repo release --ref refs/heads/main
```

```python
from stateowl import GitHubStore, Reader
result = Reader(GitHubStore()).read("owner/repo", "release", ref="refs/heads/main")
```

Public reads can be unauthenticated, subject to GitHub rate limits. Private reads require caller-owned credentials; never commit secrets. This legacy route lookup uses `.stateowl/router.json`. The separately qualified draft-3 reader supports direct paths and native `.state` without that router.

## Qualified technical guarantees and boundaries

A current draft-3 read freshly resolves one mutable ref; an exact read uses its pinned snapshot without mutable resolution. Both independent languages return selected records with raw-byte digest/provenance, optional expansion, and explicit unsupported-version/error results. The [published-in-repository schemas/fixtures](docs/protocol/README.md) are **draft-3**, not a stable future wire contract.

R2 in-memory benchmark evidence proves fixed selected-context bytes as unrelated records grow under the specified fixture, not fixed network latency, general token savings or a security boundary. R3 receipts are not indefinitely retained by Git; arbitrary competing GitHub writers can bypass the library. R5's duplicate-effect target is **test-only** and proves no general exactly-once execution or effect-target fencing. Consult [SECURITY.md](SECURITY.md) before enabling any write.
