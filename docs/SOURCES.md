# stateOwl — Research sources and verification record

Research date: **3 October 2026**. This ledger accompanies `ARCHITECTURE-DECISION.md` and `ROADMAP.md`.

`R` references are repository evidence. `S` references are external primary sources. Statements labeled **recommendation**, **inference**, **candidate**, or **acceptance target** in the architecture are design conclusions, not claims that software already implements them.

## Repository evidence

All source inspection used **repla73/stateOwl at `213079f2ea2fa45e0c659339183130fd4c265226`**. Both initial and final live `main` lookups matched that commit. The final tree was `345bfd234777c6c3436bed67a79e37ba27cde95f`; no material drift was observed. Files were read through the connected GitHub tool, not a search index.

| ID | Evidence | What it supports |
|---|---|---|
| R1 | [CHARTER.md](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/CHARTER.md) | Durable product intent, neutrality, boundaries and success criteria. Read completely. |
| R2 | [docs/ARCHITECTURE-DRAFT.md](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/docs/ARCHITECTURE-DRAFT.md) | Existing architecture hypothesis and unresolved decisions. Read completely, including the final continuation. |
| R3 | [src/stateowl/core.py](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/src/stateowl/core.py) | Reader, snapshot assumptions, router, projections, links, provenance and JSON handling. |
| R4 | [src/stateowl/github.py](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/src/stateowl/github.py) | REST access, immutable cache, ref resolution, object verification and tag handling. |
| R5 | [src/stateowl/cli.py](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/src/stateowl/cli.py) | Actual CLI surface and explicit `--expected-head` freshness meaning. |
| R6 | [tests/test_core.py](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/tests/test_core.py) | Six reader tests: projection, expansion, freshness, mismatch, duplicate JSON keys, cross-repository binding. |
| R7 | [tests/test_github.py](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/tests/test_github.py) | Two mocked transport tests: immutable cache and blob mismatch. |
| R8 | [benchmarks/benchmark.py](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/benchmarks/benchmark.py) and [tests/test_benchmark.py](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/tests/test_benchmark.py) | In-memory benchmark design and two benchmark-contract tests. |
| R9 | [benchmarks/results.json](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/benchmarks/results.json) | Published baseline values; these are not newly measured live-network results. |
| R10 | [docs/state-format.md](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/docs/state-format.md) and [adapters/chatgpt/README.md](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/adapters/chatgpt/README.md) | Legacy router convention and the documented, read-focused ChatGPT adapter recipe. |
| R11 | [pyproject.toml](https://github.com/repla73/stateOwl/blob/213079f2ea2fa45e0c659339183130fd4c265226/pyproject.toml) | Version 0.1.0, Python >=3.11, no declared third-party runtime dependencies; setuptools build dependency. |

### Verification limits

The ten existing tests were **inspected, not executed**. The container could not obtain a repository checkout; the live connector supplied the source used for static analysis. No new protocol implementation, live write, account installation, host change, race experiment, or performance measurement was performed. No private Governance repository was inspected. The Governance integration is therefore an architectural mapping requirement, not a qualified compatibility claim.

The supplied session brief is the task authority. Its instruction is architecture/R&D without implementation. The package does not replace the charter or imply founder ratification.

## External primary sources

### Standards and nearest alternatives

| ID | Source | Relevant finding and evidence limit |
|---|---|---|
| S1 | [MCP versioning](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning) and [specification](https://modelcontextprotocol.io/specification/2026-07-28) | The current documented revision is 2026-07-28. Version handling and discovery have evolved; bindings must qualify actual client versions, not assume a 2025 handshake universally. |
| S2 | [MCP Tasks extension draft](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks) | Asynchronous task/result tracking is relevant prior art. A draft extension is not a universal requirement or proof of project-state publication semantics. |
| S3 | [A2A latest specification](https://a2a-protocol.org/latest/specification/) and [task lifecycle](https://a2a-protocol.org/dev/topics/life-of-a-task/) | Specification index identifies released 1.0.0. Tasks, messages, artifacts and contexts support delegation. The development lifecycle guide is supplementary, not the released normative authority. |
| S4 | [Agent Client Protocol introduction](https://agentclientprotocol.com/get-started/introduction) | Editor/agent communication for local and remote scenarios. Do not confuse this ACP with unrelated projects that use the same initials. |
| S5 | [GNAP](https://github.com/farol-team/gnap) | Git-native agent/task/run/message coordination. Documented conflict policy is pull, rebase and retry. Project-authored documentation was examined; implementation was not qualified. |
| S6 | [Lethe Memory Git](https://github.com/openlethe/lethe/blob/main/docs/memory-git.md) | Exact-head semantic memory, CAS, idempotency, immutable changesets and review/merge authority. Strongest conceptual overlap; the service and enforced memory/review model differ from arbitrary existing project records. Claims are the project's documentation, not this session's test results. |
| S7 | [Beads](https://github.com/gastownhall/beads) | Current documentation makes Dolt the source of truth, with embedded and server modes. JSONL is an export, not the primary database. The old steveyegge repository redirects here. |
| S8 | [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) and [checkpointer source documentation](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/checkpointers.mdx) | Thread checkpoints and cross-thread stores; durability depends on the configured persistence mode. Not a claim that all deployments persist safely by default. |
| S9 | [Temporal Activities](https://docs.temporal.io/activities) | Durable activity execution and retries; applications still need idempotent activities to avoid duplicate effects. |
| S10 | [agent-work-mem](https://github.com/daystar7777/agent-work-mem) | Markdown-based cross-agent memory and handoff conventions. Reviewed through Exa's extracted project README; no implementation/concurrency qualification. |

### Execution planes

| ID | Source | Relevant finding and evidence limit |
|---|---|---|
| S11 | [Connecting GitHub to ChatGPT](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt) | Documented stock app is live, on-demand and read-only; availability varies by surface/workspace. Do not generalize this to every separately configured enterprise or custom GitHub connection. |
| S12 | [OpenAI plugin architecture](https://developers.openai.com/plugins/concepts/plugins) | Plugins can contain skills, MCP and runtime-specific hooks. Installing a web plugin does not deploy hook scripts. Skills guide existing tools; server-backed tools supply executable behavior. |
| S13 | [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) | Official destination of the OpenAI Codex MCP documentation: local stdio and remote MCP configuration. This does not establish the networking or credentials of any particular cloud worker. |
| S14 | [Claude remote custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) and [desktop versus web connectors](https://support.claude.com/en/articles/11725091-when-to-use-desktop-and-web-connectors) | Hosted remote connections and local desktop extensions are materially different. Remote requests originate from Anthropic infrastructure. |
| S15 | [Claude Code MCP](https://code.claude.com/docs/en/mcp) | Local and remote MCP integration; actual tool permissions still require qualification. |
| S16 | [Pi extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md) | Executable TypeScript extensions, custom tools, lifecycle events, structured results and native MCP support. The original badlogic/pi-mono URL redirects here. Extensions run with host permissions. |
| S17 | [OpenClaw plugin development](https://docs.openclaw.ai/plugins/building-plugins) | Native registered tools, manifests and permission/exposure controls. Upstream documentation is not proof of compatibility with an older installed host version. |
| S18 | [OpenClaw automation payloads](https://docs.openclaw.ai/automation/cron-jobs/payloads), [automation CLI](https://docs.openclaw.ai/cli/cron), and [heartbeat](https://docs.openclaw.ai/gateway/heartbeat) | Current upstream supports scheduling and command/script paths; heartbeats are scheduled agent turns. A deterministic pre-model gate must be qualified against the deployed runtime. |
| S19 | [Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/) and [extensions](https://geminicli.com/docs/extensions/) | Local/remote MCP and installable extension packaging; not the same product capability as consumer Gemini web. |
| S20 | [Gemini Spark custom apps](https://support.google.com/gemini/answer/17209137) | Custom MCP apps in eligible Spark web/mobile sessions; documented US/adult/personal-account/English/activity prerequisites and manual confirmation for writes. Does not establish unattended write capability. |
| S21 | [Gemini Enterprise custom MCP](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server) | Separate enterprise route with admin configuration, Streamable HTTP and TLS/auth requirements. |
| S22 | [Antigravity MCP](https://antigravity.google/docs/mcp) | Supported local/remote MCP configuration and per-tool permissions across documented Antigravity surfaces. |
| S23 | [Grok API remote MCP](https://docs.x.ai/developers/tools/remote-mcp) | API-side remote tool configuration, credentials and allowlists. It is not evidence that the ordinary Grok web interface exposes the same integration. |

### Storage, integrity and distribution

| ID | Source | Relevant finding |
|---|---|---|
| S24 | [GitHub GraphQL commits](https://docs.github.com/en/graphql/reference/commits) | `createCommitOnBranch`, multiple file changes and `expectedHeadOid`; `clientMutationId` is not documented as a durable exactly-once/idempotency service. |
| S25 | [GitHub REST references](https://docs.github.com/en/rest/git/refs) | Ref object type and SHA; `force:false` checks fast-forward ancestry rather than an explicit expected old head. |
| S26 | [git-update-ref](https://git-scm.com/docs/git-update-ref) | Explicit old-object comparison and atomic individual ref update. Multi-ref transactions do not make independently resolved reads into a cross-ref snapshot. |
| S27 | [git-push](https://git-scm.com/docs/git-push) | Explicit `--force-with-lease=<ref>:<expect>` comparison; implicit tracking-branch lease hazards. The proposed adapter must separately reject history-rewriting candidates. |
| S28 | [Git hash transition](https://git-scm.com/docs/hash-function-transition) | SHA-1 cannot be the universal object-identity assumption. |
| S29 | [GitHub App installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation) | Repository/permission-scoped installation credentials, one-hour expiration and REST/GraphQL/Git access subject to endpoint permissions. |
| S30 | [GitHub REST best practices](https://docs.github.com/en/enterprise-cloud%40latest/rest/using-the-rest-api/best-practices-for-using-the-rest-api) | Authenticated conditional GET and 304 primary-rate-limit treatment. Conditional mutation support must not be assumed. |
| S31 | [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/info/rfc8785/) | Reusable canonicalization for a constrained request envelope, not a reason to rewrite arbitrary project file bytes. |
| S32 | [uv tools](https://docs.astral.sh/uv/guides/tools/) | `uvx` uses isolated tool environments; convenient invocation is not absence of a runtime or first-use download. |
| S33 | [npx](https://docs.npmjs.com/cli/v11/commands/npx/) | npm package execution/distribution; it does not eliminate Node/npm dependencies. |

## Research interpretation

This is a focused architecture review, not an exhaustive proof that no competing implementation exists. Searches deliberately covered protocols, durable execution, Git-native coordination, memory/handoff systems, plane integration contracts, and provider write mechanics. Project READMEs establish documented intent and behavior, not independent reliability. The reuse gate in the roadmap remains open to a stronger existing implementation.

Older community answers about Gemini web lacking custom MCP were superseded by the current official Spark documentation. Outdated descriptions of Beads as a JSONL-primary store were also excluded. No community troubleshooting post was used as a normative integration contract.
