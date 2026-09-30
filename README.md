# stateOwl

**Exact GitHub-backed project state without dragging the repository into model context.**

stateOwl is a small, provider-neutral reader for AI agents and tools that need current structured project state from GitHub. Instead of searching a repository or loading history, it follows a compact router to one exact record and expands named detail only when requested.

```text
fresh ref -> small router -> exact selected record -> optional linked detail
```

Every result carries exact repository / commit / path / blob provenance. Unrelated project history stays out of the focused read path.

## Why

Agent sessions frequently spend context and API calls rediscovering state that already has a precise location. stateOwl makes the efficient path explicit:

- resolve the mutable Git ref fresh;
- bind the read to that exact commit;
- read a small router;
- read only the selected record;
- project only model-relevant fields;
- fetch linked detail on demand;
- keep provenance in the result.

## What it is

- a platform-neutral Python core;
- a small GitHub REST transport;
- a compact router/record convention;
- provenance-preserving model-facing results;
- bounded reuse of immutable reads;
- reproducible efficiency benchmarks.

## What it is not

stateOwl is not an agent framework, workflow engine, repository indexer, database, hosted service, identity layer, MCP requirement, or generic GitHub writer.

Version 0.1.x is deliberately read-focused.

## Install from source

```bash
python -m pip install .
```

stateOwl 0.1.0 has no runtime third-party dependencies and requires Python 3.11+.

## Quick start

A repository opts in with a small router:

```json
{
  "schema": "stateowl.router/v1",
  "routes": {
    "release": {
      "path": "state/records/release.json",
      "select": ["id", "status", "summary", "next"]
    }
  }
}
```

Read it without a checkout:

```bash
GITHUB_TOKEN=... stateowl owner/repo release --ref refs/heads/main
```

Or in Python:

```python
from stateowl import GitHubStore, Reader

result = Reader(GitHubStore()).read(
    "owner/repo",
    "release",
    ref="refs/heads/main",
)
```

Public repositories can be read without `GITHUB_TOKEN`, subject to GitHub's unauthenticated rate limits.

To expand a named link only when needed:

```bash
stateowl owner/repo release --expand detail
```

See [`examples/demo-state/`](examples/demo-state/) for a minimal state layout.

## Read contract

A normal read:

1. resolves the mutable Git ref **fresh**;
2. reads `.stateowl/router.json` at that exact commit;
3. reads only the selected record at the same commit;
4. projects the route's declared fields;
5. returns exact source locators;
6. expands only explicitly requested named links.

Cross-repository links require an exact commit. Mutable refs are never cached. Verified immutable objects may be reused through a bounded cache.

See [`docs/state-format.md`](docs/state-format.md) for the public record convention.

## Benchmark

Run:

```bash
python benchmarks/benchmark.py
```

The deterministic benchmark compares a naive "load every state record" strategy with the focused locator path at 0, 10, 100, and 1,000 unrelated records. It records logical GitHub/API calls, bytes returned, and model-visible JSON bytes.

Checked-in results are in [`benchmarks/results.md`](benchmarks/results.md) and [`benchmarks/results.json`](benchmarks/results.json).

The important property is scaling: **focused read cost stays flat as unrelated records grow.**

## Provider adapters

The core is provider-neutral. Adapters should remain thin and use whatever exact GitHub access a platform already provides. A provider that cannot preserve exact ref/commit reads should not silently weaken provenance.

The first reference surface is [`adapters/chatgpt/`](adapters/chatgpt/). Other providers can wrap the same `Reader.read()` contract through their function/tool calling APIs.

## Versioning

Package versions use Semantic Versioning, beginning with `0.1.0`.

Repository release tags use the distinctive form:

```text
stateowl-v0.1.0
stateowl-v0.1.1
stateowl-v0.2.0
```

See [`CHANGELOG.md`](CHANGELOG.md).

## Security and privacy

The public repository must not contain credentials, tokens, private account identifiers, private hostnames, IP addresses, or private development-state material. See [`SECURITY.md`](SECURITY.md).

## License

MIT. See [`LICENSE`](LICENSE).
