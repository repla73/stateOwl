# Security and support

## Supported line and limits

Prepared Python source `0.2.0` provides a **narrow stable read-compatibility surface** (`Reader`, `GitHubStore`, CLI); frozen 0.1.0 goldens are compatibility-tested, not a second maintained security line. Source metadata does **not** mean public tag/registry release. `stateowl/0.2-draft.3` remains an **unstable/draft wire protocol**; TypeScript is prerelease source. No security-support SLA, Git retention period, network-availability guarantee or future-protocol compatibility is promised.

## Authorization, secrets and writes

The legacy CLI reads `GITHUB_TOKEN` if provided; public GitHub reads may be unauthenticated/rate-limited. Other providers and Pi require caller-supplied scoped credentials. Never put tokens, private contents or HMAC keys in Git state, arguments, fixture logs, model-facing results or source artifacts.

Publication requires a **real** trusted project validation/authorization boundary, path allowlist and **externally enforced single-step namespace**. A provider/flag cannot enforce repository-wide exclusivity or prevent bypass GitHub writes. Pi is disabled for publication by default; `STATEOWL_PUBLISH_ENABLED=1` requires `STATEOWL_SINGLE_STEP_CONTINUITY=1` and nonempty `STATEOWL_WRITE_PATHS`, but these settings are declarations, **not** GitHub branch protection. GitHub API errors, stale/unknown admission, history loss and credential failure fail closed; unknown outcomes are reconciled or escalated, never replayed blindly.

Optional Python `Observer` HMAC tokens bind scope/dependencies, expire, and depend on a caller-owned secret; expiration, rotation, provider outage, namespace reset or deleted state requires an explicit fresh baseline.

Git receipt `reachable_history` is **not** a retention-duration promise. Preserve necessary exact commits/refs independently; parent ancestry alone cannot prove skipped intermediate admissions without the namespace single-step invariant. External effects remain project/target owned. R5 duplicate suppression was proven **only** for its idempotent local qualification target; no exactly-once effects or effect-target fencing are claimed.

## Reporting and public-repository boundary

Use the repository's private vulnerability-reporting mechanism where available. Never put credentials, private project state, account identifiers, hostnames/IPs or operational secrets in a public issue. This repository contains reusable sanitized source, fixtures, tests and documentation only. Private installation and host details belong outside.
