# stateOwl Charter

**Status:** Product charter  
**Scope:** Durable product identity, boundaries, and quality requirements

## Mission

stateOwl makes project state portable across AI execution planes.

A human or agent should be able to stop work in one environment, open another compatible environment, resolve the same durable project state, continue safely, publish the next state, and leave the project ready for another plane to resume.

The execution session is disposable. Project state is durable.

## Problem

AI work is increasingly spread across incompatible execution environments: hosted web sessions, coding agents, local shells, remote hosts, automation workers, plugins, extensions, and agent frameworks. Each environment has different tools, permissions, runtimes, credentials, context limits, and persistence models.

Without a shared state layer, every new session must rediscover:

- what project state is current;
- what work is active;
- which exact records and versions matter;
- what changed previously;
- what can safely happen next.

That wastes model context and tool calls, makes handoffs fragile, and makes unattended restart or loop execution unsafe.

stateOwl exists to provide one small interoperable state contract above those execution environments.

## Product identity

stateOwl is a lightweight protocol and integration ecosystem for durable, focused, provenance-preserving project state.

GitHub is the first storage environment. Python is one reference implementation. A CLI, MCP binding, ChatGPT plugin, Claude extension, Pi extension, other plane-specific integrations, and future storage adapters may all implement the same stateOwl contract.

No single runtime, programming language, provider, agent framework, transport, plugin system, or installation mechanism defines stateOwl.

## Core principles

### 1. State outlives the execution plane

Durable project state must not depend on the lifetime of a chat, VM, agent process, model, provider, or local workspace.

A compatible plane must be able to enter the project from durable state alone, subject to its authorization and the project-specific rules that govern the work.

### 2. Protocol before implementation

The normative stateOwl contract must be small enough to implement independently.

Reference software exists to make the contract convenient, not to make one package mandatory.

### 3. Plane-native integration

Each execution environment should use the cheapest reliable integration available to it.

Examples include:

- an authorized ChatGPT plugin or GitHub-backed adapter;
- a Claude or other hosted-environment extension;
- a Pi, OpenClaw, Codex, or local-agent extension;
- an MCP binding;
- a local Git adapter;
- a CLI;
- a language library;
- a remote HTTP service.

These are peers. They must project the same observable state semantics and pass the same conformance contract.

### 4. No universal installation requirement

A hosted web session should not need Python, Node.js, Git, or another third-party runtime merely to use stateOwl when its native integration can perform the required operations.

CLI installation mechanisms such as pip, uvx, pipx, npx, packaged binaries, or platform packages are adapter conveniences, not protocol requirements.

### 5. Focused state, not repository discovery

stateOwl should address the smallest state needed for the current purpose.

Unrelated tasks, history, sibling records, logs, source trees, and documents must not enter model context merely because they exist.

The amount of model-visible state for one addressed record should remain effectively independent of unrelated project-state growth.

### 6. One logical model operation

Internal storage operations should normally be hidden behind one logical model-facing read or update.

Resolving a ref, reading a manifest/router, fetching records, verifying provenance, caching immutable objects, and publishing a transaction are implementation details unless a caller explicitly needs them.

Model tool-call count and model-visible bytes are first-class efficiency metrics.

### 7. Exact snapshots and provenance

A mutable project-state reference is an entry point, not an immutable identity.

A state read must resolve to an exact snapshot before dependent records are interpreted. Results must preserve enough provenance to establish where the returned state came from.

When the caller already has an exact snapshot, stateOwl should be able to use it directly without redundant resolution.

### 8. Transactional publication

State publication must protect concurrent writers.

A writer should publish against an expected prior snapshot or equivalent compare-and-swap boundary. A stale writer must fail or reconcile rather than silently overwrite newer state.

Multi-record logical transitions should be publishable atomically when the storage provider supports it.

### 9. Automation and restart safety

stateOwl must be suitable for interactive handoff and unattended loops.

The architecture must support efficient wake, observe, work, publish, and resume patterns without requiring an LLM invocation merely to discover that nothing changed.

Concurrency, duplicate work, and ambiguous external effects are separate problems. stateOwl must provide the state/version primitives needed to handle them safely without pretending that storage atomicity creates exactly-once external execution.

### 10. Project semantics stay project-owned

stateOwl must not hard-code Governance, task, review, deployment, approval, or agent-lifecycle semantics.

A project or profile may define those meanings on top of stateOwl.

For example, the Governance .state model can be a sophisticated stateOwl consumer without turning Governance concepts into universal stateOwl concepts.

### 11. Storage is replaceable

The protocol must not require a dedicated Git branch forever.

The initial GitHub backend may use a state branch because it provides durable history, immutable commits, existing authentication, human inspection, and concurrency protection.

A future GitHub-native repository-state namespace, another Git provider, local Git, or another durable state service should be able to implement the same stateOwl storage contract without changing project semantics.

### 12. Authentication and authority remain explicit

stateOwl should reuse the execution plane's authorized credentials where possible.

The protocol must not invent authority merely because a caller can reach storage. Transport permission, project authority, semantic validation, and execution permission are distinct.

stateOwl may enforce mechanical state invariants and expected-version publication. Project-specific authorization and lifecycle rules belong to the project/profile or trusted integration boundary.

### 13. Human and agent parity

Durable state must remain inspectable and understandable by humans.

A human should be able to inspect project state, determine its exact version, and understand the next relevant state without requiring an agent runtime.

### 14. Minimal machinery

The default architecture should require no database, daemon, vector store, orchestration server, long-lived agent process, or stateOwl-specific hosted service.

Such components may be optional adapters where they solve a real deployment need.

## Normative capability direction

The stateOwl protocol should ultimately cover four small capability classes.

### Address

Identify a project state namespace, mutable entry point or exact snapshot, and requested route/record.

### Read

Return only requested state and explicitly requested detail, bound to one exact snapshot and accompanied by compact provenance.

### Publish

Apply an authorized, validated state transition against an expected prior snapshot and return the resulting snapshot or a clear conflict/failure.

### Observe

Allow cheap detection of relevant state changes so schedulers or automation can avoid unnecessary model invocation. Polling, webhooks, provider events, and local observation are bindings of this capability rather than one mandatory mechanism.

The final protocol surface may combine these capabilities into fewer operations if that produces a simpler interoperable contract.

## Integration model

stateOwl should encourage multiple first-class integrations rather than force every plane through one adapter.

Potential integrations include:

- ChatGPT plugin/app;
- Claude extension;
- Pi extension;
- OpenClaw integration;
- Codex/local coding-agent integration;
- Gemini or Grok integration where their tool surfaces permit it;
- MCP server/binding;
- CLI;
- Python reference library;
- other language SDKs;
- remote HTTP adapter;
- local Git adapter;
- GitHub API adapter.

Every integration should be thin. Plane-specific code owns authentication, tool exposure, transport, packaging, and host constraints. It must not fork stateOwl's state semantics.

## Automation model

A compatible automated worker should be able to follow a pattern equivalent to:

1. observe durable state;
2. determine whether relevant work changed or became eligible;
3. acquire any project-required claim or lease;
4. read the exact required state;
5. perform bounded work;
6. reconcile external effects where applicable;
7. publish one guarded state transition;
8. continue, yield, or sleep.

stateOwl's universal core should provide exact state identity and concurrency-safe publication. Whether claims, leases, fencing tokens, review gates, effect records, or recovery rules belong in a generic extension or a project profile is an architecture decision to be researched rather than assumed.

## State representation

stateOwl should not require application records to contain stateOwl-specific fields unless necessary.

Protocol metadata should preferably live in a small stateOwl-owned manifest/router or be supplied by an adapter/profile. Existing project state such as Governance .state records should remain usable without being redesigned around the tool.

Named routing and selective expansion are desirable because they let a model ask for semantic state without repository-wide discovery.

## Portability requirements

A conforming design should be usable in environments with different capability levels:

- native GitHub or repository connector only;
- remote tool/plugin/extension support;
- MCP support;
- local Git checkout;
- shell plus network;
- language-runtime access;
- no install permission.

A plane with neither authorized repository/network access nor an authorized remote tool cannot access private remote state; stateOwl does not claim to bypass that security boundary.

## Efficiency requirements

stateOwl must optimize the total cost of state access, not one implementation detail.

Measurements should include:

- model-visible tool calls;
- model-visible bytes/tokens;
- provider API operations;
- bytes transferred;
- latency;
- cold-start cost;
- runtime/install footprint;
- cache effectiveness;
- behavior as unrelated state grows;
- conflict/retry cost;
- automation wake cost.

Benchmarks must compare realistic alternatives, not only intentionally broad repository scans.

## Interoperability requirements

A stable stateOwl generation should have:

- a versioned normative specification;
- closed, machine-readable request and response schemas where practical;
- stable machine-readable error semantics;
- test vectors and conformance fixtures;
- cross-language/provider conformance tests;
- clear compatibility rules;
- explicit object-ID/hash handling rather than assuming one Git hash format;
- deterministic handling of malformed or ambiguous state.

Independent implementations should agree on observable results for the same fixture.

## Security requirements

Integrations should use least privilege and reuse native identity where possible.

Secrets must not be stored in project state.

State reads must not silently broaden into source/history collection.

State writes must not silently bypass project validation or publication rules.

A remote hosted adapter must not become an unnecessary credential concentrator when a plane can safely use its own repository connection.

## Non-goals

stateOwl is not intended to become:

- an AI agent framework;
- a workflow engine;
- a replacement for Git;
- a source-control system;
- a generic repository search engine;
- a transcript store;
- a vector-memory system;
- a prompt-management platform;
- an identity provider;
- a universal scheduler;
- a Governance policy engine;
- an MCP-only product;
- a GitHub-only product.

It may integrate with systems in those categories.

## Relationship to project profiles

Projects may define profiles or adapters that map their own durable semantics onto stateOwl.

The Governance .state design is an important proving environment because it exercises:

- exact version binding;
- multi-record state;
- independent review;
- recovery/effect state;
- cross-session handoff;
- concurrent publication;
- human inspection;
- long-running project continuity.

Governance remains responsible for its own rules. stateOwl provides a transport and addressing substrate, not Governance meaning.

## Success criteria

stateOwl succeeds when a project can be moved between materially different execution planes without rebuilding operational context from conversation history.

A successful mature implementation should demonstrate that:

- the same durable project state can be resolved from multiple independent planes;
- a handoff can be expressed with a compact stable locator rather than a large explanatory prompt;
- one logical read returns the exact minimum required state;
- exact-snapshot reads avoid unnecessary mutable-ref resolution;
- one guarded logical transition can be published without overwriting concurrent work;
- unrelated state growth does not materially increase focused model context;
- a plane can implement stateOwl without adopting the reference runtime;
- at least two independent implementations pass common conformance fixtures;
- automation can detect unchanged state without invoking a model;
- project-specific semantics remain outside the universal core.

## Design discipline

New stateOwl machinery must answer four questions:

1. What concrete interoperability, correctness, or efficiency problem does it solve?
2. Why can the existing protocol or storage primitive not solve that problem?
3. Does it increase the minimum dependency/runtime burden?
4. Can it remain optional or plane-specific instead of entering the universal core?

Prefer deletion and simplification over accumulating framework features.

## Charter changes

This Charter defines product intent and durable boundaries, not implementation details or a release roadmap.

Architecture may evolve freely inside these boundaries. A change that materially redefines stateOwl's mission, portability model, protocol-first identity, provider neutrality, or project-semantics boundary should update this Charter deliberately rather than drift through implementation.
