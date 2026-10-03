# stateOwl Architecture Draft

**Status:** R&D starting point — not an accepted architecture  
**Purpose:** Turn the stateOwl Charter and current 0.1.0 experience into a concrete design space for architecture research and roadmap definition.

This document is intentionally opinionated enough to be testable but not final. The architecture session should challenge its assumptions, compare alternatives, simplify where possible, and produce an accepted design and roadmap.

## 1. Target outcome

stateOwl should let a project move between independent AI execution planes without reconstructing operational context from chat history.

A representative flow is:

1. work begins in a ChatGPT web session;
2. durable project state is read from GitHub;
3. work is handed to Codex or another coding plane;
4. that plane publishes product work and updates durable state;
5. an OpenClaw worker later wakes, reads the same state, and performs an automated step;
6. a human opens Claude, Gemini, Pi, Grok, ChatGPT, or another compatible plane and can immediately resolve the same current project state;
7. work continues without requiring the previous model session to survive.

The state store is the continuity layer. Execution planes are replaceable workers.

## 2. Current baseline

stateOwl 0.1.0 currently provides a Python reference reader with:

- a provider-neutral StateStore read boundary;
- a GitHub REST transport;
- fresh mutable-ref resolution;
- exact commit-bound file reads;
- a small router;
- top-level projection;
- explicit non-recursive detail expansion;
- repository/commit/path/blob provenance;
- bounded immutable-object caching;
- a CLI;
- initial ChatGPT adapter guidance;
- deterministic focused-read benchmarks.

This baseline proves the core focused-read idea but is not yet the intended cross-plane system.

Known limitations of the current release include:

- Python 3.11+ is the only implemented runtime;
- GitHub REST is the only implemented remote store;
- a model-facing integration may still require multiple underlying tool operations;
- exact known commits still go through ref resolution;
- multiple route reads do not yet share one resolved snapshot efficiently;
- writes and guarded state publication are not implemented;
- automation claims/leases and wake semantics are not designed;
- the current router and linked-detail format are implementation conventions rather than a complete interoperable specification;
- conformance fixtures and normative request/response schemas do not yet define independent implementations;
- Git object identity assumes SHA-1;
- tag resolution needs explicit annotated-tag semantics;
- current benchmarks prove scaling against a naive scan but not optimality against strong realistic alternatives.

## 3. Architecture hypothesis

The central hypothesis is:

> stateOwl should be a small state protocol with multiple first-class plane bindings and multiple storage adapters.

The protocol should define observable semantics. It should not define one runtime.

A conceptual architecture is:

~~~text
                 EXECUTION PLANES

 ChatGPT   Claude   Gemini   Grok   Codex   Pi   OpenClaw   other
    |         |       |       |      |      |      |         |
    +---------+-------+-------+------+------+------+---------+
                              |
                    plane-specific binding
                              |
                    stateOwl protocol contract
                              |
              +---------------+---------------+
              |                               |
       optional project/profile        generic state core
       semantic validation             addressing/provenance/
       and lifecycle rules             concurrency semantics
              |                               |
              +---------------+---------------+
                              |
                     storage-provider adapter
                              |
            +-----------------+------------------+
            |                 |                  |
        GitHub state      local Git       future provider /
          branch                           GitHub state API
~~~

This layering is a hypothesis. The R&D session should test whether any layer can be removed or combined without losing portability, correctness, or efficiency.

## 4. Protocol versus tools

stateOwl may ship many tools.

Examples:

- a ChatGPT plugin/app;
- a Claude extension;
- a Pi extension;
- an OpenClaw integration;
- a Codex/local-agent integration;
- an MCP binding;
- a CLI;
- Python, TypeScript, Rust, or other libraries;
- a remote HTTPS endpoint;
- a local Git adapter.

These are not separate state systems.

Each binding should:

- expose the smallest useful stateOwl operation surface for that plane;
- reuse native credentials when possible;
- hide transport-specific GitHub/Git details from the model;
- return the same logical result for the same state snapshot;
- share protocol schemas and conformance fixtures;
- avoid inventing plane-specific project semantics.

A native extension can be richer operationally than a generic MCP binding while still implementing the same state contract.

## 5. Candidate protocol capabilities

The final public API should be smaller than the internal implementation.

The architecture should evaluate whether two primary operations are sufficient:

~~~text
stateowl.read(...)
stateowl.publish(...)
~~~

with observation/change detection as either:

- a third protocol capability;
- a transport/provider capability used by automation;
- or an integration concern outside the core protocol.

### 5.1 Read

One logical read should be able to:

- identify the project/state namespace;
- accept either a mutable entry point or an already-known exact snapshot;
- resolve a mutable entry point exactly once;
- address one or more named routes/records;
- apply field projection;
- expand only explicitly requested linked detail;
- batch reads that share the same snapshot;
- return compact provenance;
- avoid exposing internal provider calls to model context.

Candidate conceptual request:

~~~json
{
  "project": "owner/repo",
  "state": {
    "ref": "refs/heads/state"
  },
  "routes": ["current-task"],
  "expand": ["review"]
}
~~~

If the exact state snapshot is already known:

~~~json
{
  "project": "owner/repo",
  "state": {
    "snapshot": "provider-specific-exact-id"
  },
  "routes": ["current-task"]
}
~~~

These shapes are illustrative, not normative.

### 5.2 Publish

One logical publish should be able to:

- bind to an expected prior state snapshot;
- accept a complete intended logical state transition or a profile-produced candidate;
- run required mechanical and profile validation;
- publish atomically where the provider permits;
- refuse stale writers;
- distinguish conflict, validation failure, ambiguous publication, and success;
- fresh-read enough target truth to establish the resulting state identity;
- return the new exact snapshot and compact affected-record provenance.

The architecture must decide how much generic mutation stateOwl itself should expose.

A raw arbitrary-file write API may be too weak semantically and too dangerous for governed projects. A fully semantic workflow API would violate stateOwl's project-neutrality.

A likely boundary is:

- stateOwl core owns exact snapshot identity, complete delta publication, concurrency protection, and provenance;
- a project profile owns legal semantic transitions and authorization/evidence checks;
- a plane binding supplies authenticated execution context.

This needs R&D rather than assumption.

### 5.3 Observe

Automation should be able to cheaply determine whether relevant durable state changed without invoking an LLM.

Candidate provider mechanisms include:

- compare current ref/snapshot;
- webhook/event delivery;
- provider-specific change tokens;
- local filesystem/Git observation;
- polling.

The model should not be called solely to discover that the state head is unchanged.

## 6. State locator

Cross-plane handoff would benefit from one compact canonical locator.

A locator should be able to identify:

- stateOwl protocol generation;
- storage/provider type if necessary;
- project/repository;
- state namespace or mutable ref;
- optional exact snapshot;
- route/record;
- optional profile.

Conceptual example only:

~~~text
stateowl://github/repla73/project?ref=state&route=p01t090
~~~

Requirements:

- copy/paste friendly;
- deterministic;
- compact;
- human-readable enough to diagnose;
- no embedded secrets;
- usable by web plugins/extensions and CLI tools;
- able to preserve an exact snapshot when handoff must be immutable;
- extensible without making every locator verbose.

The R&D session should determine whether a URI is the right form or whether a small JSON locator is safer.

## 7. State manifest and routing

The current .stateowl/router.json proves the usefulness of named focused routes, but the final role of a router needs review.

The design should support existing project-owned state layouts such as Governance .state without forcing those records to contain stateOwl metadata.

Candidate direction:

- stateOwl-specific metadata lives in a small manifest/router;
- the manifest maps stable route names to project-owned records and default projections;
- project records remain project-owned;
- profiles may provide additional semantic resolution;
- callers that already know an exact path may use a lower-level addressed read where appropriate;
- manifest lookup should be cacheable at an immutable snapshot;
- the manifest must not become a duplicate project index or lifecycle database.

Questions:

- Is a router required for every project?
- Can a profile generate routing deterministically from an existing project schema?
- Should routes support only exact paths, or parameterized route templates?
- Should default projection be declared by the project or by the plane integration?
- How are linked detail and cross-repository state represented without contaminating project records?

## 8. Snapshot model

Every logical state operation should have one exact source snapshot.

A snapshot abstraction should not assume:

- Git SHA-1;
- GitHub;
- a branch;
- one repository provider.

For Git backends, the exact commit remains a natural snapshot identity. Object IDs and blob identities should carry an explicit algorithm or use a provider-neutral opaque representation.

Requirements:

- mutable refs are never treated as immutable state identity;
- an exact snapshot can be supplied directly;
- all records in one read are interpreted against the same snapshot unless an explicit cross-project link carries its own exact snapshot;
- returned provenance distinguishes the mutable entry point from the exact resolved state;
- cached immutable state must never cause a mutable ref to become stale.

## 9. Storage-provider contract

A minimal provider adapter may need capabilities equivalent to:

~~~text
resolve(mutable_locator) -> exact_snapshot
read(exact_snapshot, path) -> bytes + object_identity
publish(expected_snapshot, complete_delta) -> new_snapshot | conflict | unresolved
observe(mutable_locator, previous_snapshot) -> current_snapshot/change
~~~

This is conceptual. The final interface should be derived from required semantics and benchmarked.

Useful optional capabilities may include:

- batch reads;
- server-side field/range selection;
- transaction construction;
- change events/webhooks;
- history/ancestry verification.

A provider capability must not leak into the normative protocol unless callers actually need it.

## 10. GitHub backend

The initial production-quality backend can continue to use a dedicated state branch.

Advantages:

- existing authentication and GitHub App support;
- immutable commits;
- complete history;
- atomic multi-file commits;
- human inspectability;
- distributed access;
- natural snapshot identity;
- non-force publication semantics that can protect against stale state candidates;
- no stateOwl server requirement.

The adapter should hide Git plumbing from the model.

### Current branch model

A project may have:

~~~text
product branch(es)
state branch
  .stateowl/...
  .state/...
~~~

The exact file layout is project/profile-specific except for any minimal stateOwl manifest that the final protocol requires.

### Future GitHub-native state facility

A desirable future GitHub capability would provide repository-associated state separate from ordinary source branches while preserving:

- path-addressable records;
- immutable snapshots/history;
- atomic multi-record update;
- expected-version/CAS publication;
- separate permissions;
- GitHub App and connector access;
- events/webhooks;
- efficient targeted reads;
- human inspection.

stateOwl should treat such a service as another provider adapter, not require architectural redesign.

The project may separately prepare a proposal/request for GitHub after stateOwl's provider requirements are precise.

## 11. Local Git backend

CLI-capable planes such as Codex, Pi, OpenClaw, local Claude tooling, or other host workers may already have a repository checkout and Git credentials.

For those environments, a local Git adapter could be cheaper than REST.

Potential read path:

1. identify/fetch the configured state ref as required;
2. resolve it to an exact local object;
3. read records directly from Git objects without changing the product worktree;
4. return the same stateOwl result shape.

Potential write path:

1. construct the state commit separately from the product worktree;
2. validate complete candidate state;
3. push with an expected-old/lease-style guard or equivalent;
4. fresh-resolve remote truth;
5. return the admitted snapshot.

The architecture must define remote-truth versus local-cache semantics clearly. An offline local commit is not globally durable project state until published.

## 12. Hosted web planes

Hosted web environments may not allow third-party package installation or local Git.

They should not need either.

Possible bindings include:

- native repository connector;
- first-party/third-party plugin or app;
- extension surface;
- remote MCP;
- remote function/tool endpoint;
- provider-specific authenticated integration.

The stateOwl contract should allow a web binding to expose one compact logical read/publish tool while doing all GitHub/provider operations outside model context.

The architecture must research the actual integration and authentication capabilities of target planes at design time instead of assuming symmetry between vendors.

Priority target environments for research include:

- ChatGPT Web / Work;
- Claude web/desktop extension surfaces;
- Gemini web/tool surfaces;
- Grok web/tool surfaces;
- other hosted model workspaces that can authorize repository access.

## 13. CLI and package distribution

CLI availability is useful for shell-capable execution planes but is not the universal protocol.

Distribution options to evaluate include:

- a small native binary;
- Python package / uvx / pipx;
- npm / npx package;
- language-specific SDKs;
- container image only where justified.

Selection criteria:

- cold-start time;
- installed size;
- dependency count;
- supported architectures;
- Windows/macOS/Linux portability;
- ease of ephemeral use;
- supply-chain surface;
- ability to run without modifying the target repository;
- parity with protocol conformance tests.

It may be better to ship more than one small native integration rather than force one runtime everywhere.

## 14. Project profiles

A profile maps project-specific semantics onto stateOwl without contaminating the universal core.

A profile may define:

- routing conventions;
- semantic record types;
- projection rules;
- validation;
- allowed transitions;
- authorization/evidence requirements supplied by a trusted caller;
- publication construction;
- automation eligibility/claim rules.

The Governance .state system is a primary stress test.

stateOwl itself should understand a Governance task only as addressed project state. A Governance profile/integration may understand task, review, effect, authority, readiness, and recovery.

The architecture should determine whether a "profile" is:

- a normative stateOwl extension concept;
- an adapter library concept;
- or simply project-owned code above the protocol.

Prefer the smallest layer that preserves interoperability.

## 15. Read path

Desired logical behavior:

~~~text
caller asks for state
        |
plane binding authenticates
        |
known exact snapshot? -- yes --> use it
        |
        no
        |
resolve mutable state entry point once
        |
read/cache manifest or route metadata at exact snapshot
        |
read only requested records at same snapshot
        |
apply deterministic projection/expansion
        |
verify object provenance
        |
return one compact logical result
~~~

Important properties:

- no repository scan;
- no sibling-state loading;
- no history loading unless explicitly requested;
- no repeated ref resolution inside one logical read;
- one model-facing tool call where the plane permits it;
- batching for multiple requested routes;
- compact source representation without repeatedly copying the same repository/snapshot fields.

## 16. Publication path

Desired generic behavior:

~~~text
read exact state H
        |
construct intended transition against H
        |
run project/profile validation
        |
construct complete state candidate C
        |
provider publication with expected H
        |
   +----+----+
   |         |
conflict   response ambiguous
   |         |
reread     reconcile target truth
   |         |
rederive   establish H/C/current
        |
fresh-read admitted state
        |
return exact new snapshot
~~~

The core rule is that a stale writer cannot silently overwrite newer state.

State publication and product publication remain separate unless a project explicitly provides a combined transactional system.

## 17. Concurrency, claims, and duplicate work

Three failure classes must remain distinct.

### 17.1 State write collision

Two writers start from the same snapshot and both attempt to update state.

Core solution: expected-snapshot publication / CAS semantics.

### 17.2 Duplicate work

Two automated workers observe the same eligible task and both begin expensive or non-idempotent work.

Possible solution: project/profile claim, lease, or fencing semantics.

This may require a small generic automation extension, but should not be added to the core without evidence that profiles cannot handle it cleanly.

### 17.3 Ambiguous external effect

A worker performs an external action, crashes, and cannot tell whether the action completed.

StateOwl cannot promise exactly-once external effects.

A project/profile must record enough effect identity and recovery state to reconcile target truth before retry. Governance already exercises this class of problem.

## 18. Automation architecture

Automation should be event-efficient.

Preferred pattern:

~~~text
provider event / cheap state-head observation
                 |
        relevant state changed?
          |             |
         no            yes
          |             |
        sleep       invoke worker
                         |
                    focused read
                         |
                  claim if required
                         |
                       work
                         |
                 guarded publication
                         |
                  next / yield / sleep
~~~

A scheduler should be able to store the last observed state snapshot outside model context and skip model execution if nothing relevant changed.

The architecture should compare:

- GitHub webhooks;
- polling;
- provider event streams;
- local Git observation;
- scheduled automation loops.

## 19. Authentication and trust

stateOwl should avoid becoming a centralized credential service.

Preferred order:

1. reuse an execution plane's existing repository authorization;
2. use a plane-native stateOwl plugin/extension with scoped credentials;
3. use a remote stateOwl service only when the plane cannot perform the required provider operations itself.

The protocol should keep these concepts separate:

- transport authentication;
- repository permission;
- project authority;
- semantic transition validity;
- external-effect authorization.

A successful Git write does not prove that a state transition was authorized by the project.

## 20. Security boundaries

Required properties:

- no secrets in durable state records;
- no credentials in locators;
- no broad repository collection as a side effect of state reads;
- least-privilege provider scopes;
- explicit cross-repository links;
- exact snapshots for cross-project dependencies;
- deterministic path validation;
- strict serialization parsing;
- bounded resource use;
- no remote execution of arbitrary policy code merely because a repository references it;
- no silent fallback from exact-bound rules to a newer implementation.

Project-specific secure-publication requirements belong to the project/profile.

## 21. Serialization and schemas

For interoperability, the protocol should define:

- normative request schemas;
- normative response schemas;
- state locator grammar if used;
- manifest/router schema;
- provenance representation;
- stable error codes;
- compatibility/version negotiation;
- strict JSON behavior or another deliberately chosen serialization format.

The design should avoid heavyweight query languages unless benchmarks show they materially improve context efficiency.

Top-level projection is intentionally simple today. The R&D session should test whether nested projection is needed and, if so, whether a tiny pointer mechanism is preferable to JSONPath/JMESPath dependencies.

## 22. Object identity and hashing

The protocol must not equate "exact state" with a 40-character SHA-1 string.

Provider-neutral identities should either be opaque typed identifiers or explicitly include their algorithm/provider semantics.

Git adapters must correctly handle repositories/object formats supported by their environment.

Annotated Git tags must resolve deliberately to the intended commit/snapshot or be excluded by contract rather than accidentally treated as commits.

## 23. Context efficiency

stateOwl should optimize model-visible information separately from provider transport.

A compact result should avoid repeating invariant provenance.

Conceptually:

~~~json
{
  "snapshot": {
    "project": "owner/repo",
    "ref": "refs/heads/state",
    "id": "exact-snapshot"
  },
  "records": {
    "current-task": {
      "value": {
        "status": "working",
        "next": "review"
      },
      "source": {
        "path": ".state/...",
        "object": "exact-object-id"
      }
    }
  }
}
~~~

The exact shape is open for design.

The architecture should measure actual model tokens, not only serialized byte count.

## 24. Conformance

Industry-style interoperability requires more than one implementation of the same Python code.

A future conformance suite should include fixtures for:

- mutable-ref resolution;
- exact-snapshot reads;
- multi-route reads;
- projection;
- linked detail;
- cross-repository exact links;
- malformed manifest/records;
- duplicate JSON keys or other serialization ambiguity;
- object-identity verification;
- ref advancement between reads;
- guarded publication success;
- stale writer conflict;
- ambiguous publication reconciliation;
- provider error normalization;
- cache correctness;
- hash/object-format variation.

Plane bindings should be able to test against the same logical fixtures even if their provider calls differ.

At least two materially independent implementations should pass the suite before calling the protocol stable.

## 25. Benchmark program

The current benchmark should become one case in a broader program.

Compare stateOwl against strong alternatives:

- direct targeted GitHub reads;
- current stateOwl 0.1 reader;
- exact-commit direct reads;
- local Git object reads;
- one aggregated state file;
- manifest + separate records;
- MCP/native connector implementations;
- provider batch APIs where available.

Measure:

- model-visible calls;
- model-visible tokens;
- provider calls;
- wire bytes;
- latency;
- cold start;
- memory;
- installation footprint;
- cache hit/miss behavior;
- scaling with unrelated state;
- batch-route behavior;
- publish conflict behavior;
- automation idle/wake cost.

Benchmark fixtures should include realistic Governance-like state rather than only synthetic noise.

## 26. Relationship to existing protocols and systems

The R&D session should compare stateOwl with adjacent work rather than assume novelty.

Areas to investigate include:

- Model Context Protocol;
- agent-to-agent protocols;
- durable agent/workflow frameworks;
- checkpoint/state systems;
- Git-backed coordination systems;
- GitHub Apps and repository APIs;
- provider extension/plugin systems;
- local coding-agent state/handoff mechanisms.

The research question is not "can these systems be replaced?"

It is:

> Is there already a small standard that provides durable project state, cross-plane handoff, exact snapshot provenance, context-focused reads, guarded publication, and automation-safe continuation without binding the project to one agent runtime?

If yes, stateOwl should reuse it. If only parts exist, stateOwl should compose with them.

## 27. GitHub platform opportunity

The current dedicated state branch is practical but semantically mixes project operational state with ordinary Git branch concepts.

Once stateOwl's provider requirements are precise, prepare a separate GitHub product proposal for a repository-attached state facility.

Do not make stateOwl dependent on GitHub accepting or implementing that proposal.

The proposal should be derived from demonstrated stateOwl requirements and benchmarks, not speculative platform design.

## 28. Questions the architecture R&D must answer

### Protocol

1. What is the minimum normative operation surface?
2. Are read + publish sufficient?
3. Is observe part of the protocol or automation binding?
4. Is a canonical state locator worth standardizing?
5. What must be normative versus implementation-defined?

### Representation

6. Is a manifest/router required?
7. How should existing .state layouts integrate without modification?
8. Where should optional links/projections live?
9. How should multiple records be returned compactly?
10. What serialization and strictness rules are required?

### Publication

11. What generic write primitive is powerful enough without becoming a workflow engine?
12. How are complete multi-record deltas represented?
13. Which validation belongs in core versus project profiles?
14. How are ambiguous remote writes reconciled consistently?
15. What minimum provider primitives are required for a writable backend?

### Automation

16. Does stateOwl need a generic claim/lease/fencing extension?
17. Can project profiles fully own duplicate-work prevention?
18. How should change observation avoid unnecessary LLM calls?
19. What state, if any, belongs outside the repository for scheduler bookkeeping?

### Integrations

20. Which first-class integrations should be maintained by the project?
21. Which should be reference recipes only?
22. How can a ChatGPT plugin, Claude extension, Pi extension, MCP tool, and CLI share conformance tests?
23. When should a plane use native GitHub access versus a remote stateOwl service?
24. How should authentication be reused without centralizing credentials?

### Portability

25. Is a single native binary useful enough to justify maintaining it?
26. Should npx/uvx-style ephemeral packages exist in parallel?
27. How should Windows/macOS/Linux and ARM64/x86_64 qualification be handled?
28. How should offline/local state be distinguished from published durable state?

### Standardization

29. What is required before stateowl.router/v1 or a successor can be called stable?
30. What compatibility policy is appropriate before 1.0?
31. Which independent implementation should serve as the second conformance proof?
32. What governance/process should protect the public protocol from implementation-driven drift?

## 29. R&D deliverables

The architecture session should produce, before implementation:

1. a landscape comparison identifying what stateOwl should reuse versus own;
2. a refined problem statement and terminology;
3. an accepted layered architecture;
4. a minimal protocol operation design;
5. read and publication semantics;
6. provider/storage interface requirements;
7. project-profile boundary;
8. automation/concurrency decision;
9. canonical integration strategy for major plane categories;
10. conformance and compatibility design;
11. benchmark methodology and baseline results where practical;
12. security/authentication boundary;
13. a migration plan from 0.1.0 that preserves useful existing code;
14. a staged roadmap with explicit decision gates and acceptance criteria.

The roadmap should prioritize proof of interoperability over feature count.

A strong early milestone would demonstrate the same state read from materially different planes using different bindings while producing the same logical result.

A later writable milestone should demonstrate a guarded state transition from one plane and correct continuation from another.

## 30. Constraints for the R&D session

Do not assume the current Python API is the protocol.

Do not assume MCP is the universal transport.

Do not assume every execution plane can install packages.

Do not require a hosted stateOwl service unless evidence shows it is necessary.

Do not make Governance semantics universal.

Do not redesign existing Governance state merely to suit stateOwl.

Do not add a database, vector store, queue, scheduler, daemon, or identity service without a demonstrated requirement.

Do not implement the new architecture before the major protocol, provider, publication, and integration decisions are made.

Prefer the smallest architecture that can prove:

- cross-plane continuity;
- exact state identity;
- minimum model context;
- guarded publication;
- automation-safe continuation;
- independent implementation.
