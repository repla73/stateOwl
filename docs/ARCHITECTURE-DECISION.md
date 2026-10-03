# stateOwl — Architecture decision and R&D package

**Date:** 3 October 2026  
**Status:** Proposed architecture decision; not ratified and not implemented  
**Baseline:** `repla73/stateOwl`, `main@213079f2ea2fa45e0c659339183130fd4c265226`  
**Companions:** [Roadmap](ROADMAP.md) · [Sources and verification record](SOURCES.md)

## Decision in brief

**Develop stateOwl as a small, transport-independent contract for reading and publishing exact project-state snapshots. Maintain several thin integrations rather than one mandatory runtime.**

The model-facing surface should be `read` and `publish`. An optional, machine-facing `observe` capability should support inexpensive change detection. GitHub and local Git are the first implementations, not definitions of the protocol. Existing project state remains in place. A project-specific resolver and validator supply meaning; stateOwl does not become a task manager, agent framework, memory database, scheduler or authority system.

There is credible prior art. GNAP already coordinates agents through Git. Lethe Memory Git already documents exact-head state, compare-and-swap, idempotency and review. Beads and durable execution frameworks solve substantial coordination/persistence problems. The opportunity is narrower than “persistent memory for agents”: a small, independently implementable contract combining **focused addressing, exact provenance, guarded publication and cross-plane continuity for existing project records**. No examined system was established to provide that complete combination under the charter's constraints. This is a bounded research finding, not a claim of universal novelty. [S5–S9]

The decisive proof is practical: one plane leaves an exact, authorized state transition; a different plane resumes from it without conversation reconstruction, broad repository reading or adopting the first plane's runtime.

## 0. Baseline verification

Both the initial and final live lookups of `main` matched the supplied baseline; no material baseline drift was observed during this review. `CHARTER.md` and the complete architecture draft were read before deriving this decision. Relevant reader, GitHub adapter, CLI, state convention, tests and benchmark files were inspected at that exact commit. The charter remains authoritative product intent; this package challenges and resolves the draft rather than treating it as accepted architecture. [R1–R11]

### Findings verified against 0.1.0

| Finding | Evidence and consequence |
|---|---|
| Focused reads are useful. | The reader projects declared fields and expands only explicitly named links. Preserve this behavior. [R3] |
| Current reads bind their dependent files to one resolved head. | Preserve this invariant and expose a separate immutable-snapshot read. [R3] |
| `expected_head` is a freshness assertion. | The reader still resolves the ref, then fails before file reads on mismatch. That is correct for this meaning; it is not an exact historical-read API. Do not silently change its meaning. [R3, R5, R6] |
| Multiple routes cannot share one public read. | Each `Reader.read()` handles one route and freshly resolves the ref. Add batch selections at one snapshot. [R3] |
| “Provider-neutral” is overstated today. | Core repository validation requires `owner/name`; identities require 40-character Git SHA-1 values. Move those assumptions into the Git binding. [R3] |
| Annotated tags need a correction. | The GitHub adapter returns `object.sha` without checking `object.type` or peeling a tag object to a commit. It can therefore label a tag-object ID as a commit. [R4, S25] |
| Python is an implementation, not a protocol specification. | The public contract is expressed largely through Python methods and a reference adapter recipe. Preserve the implementation, extract independent semantics. [R3, R10] |
| The implementation is already small in dependency terms. | Python >=3.11 is required, but no third-party runtime dependencies are declared. Do not justify a rewrite by claiming a large dependency tree that is not present. [R11] |
| The test suite is not an interoperability suite. | Ten inspected tests cover selected reader, mocked adapter and synthetic benchmark behavior. They do not qualify other languages, publication or automation. [R6–R8] |
| The benchmark establishes a limited result. | Stored focused results are three logical provider operations, 2,382 returned payload bytes and 573 model-context bytes for 0, 10, 100 and 1,000 unrelated records. The naive 1,000-record case is 1,004 operations and 332,364 model-context bytes. These are published in-memory results, not measured network traffic or tokens. [R8, R9] |
| Router growth is untested. | The benchmark holds the router constant while adding unrelated files. A router that enumerates every task can still grow with project history. [R8] |
| JSON portability needs more than duplicate-key rejection. | `strict_json` rejects duplicate keys but uses Python's default JSON constant handling without a non-finite-number rejection hook. Formal cross-language rules must close that gap. [R3] |
| Provenance and cryptographic proof must be distinguished. | Blob bytes are checked against the reported Git blob ID. The current adapter still trusts GitHub for the commit/path-to-blob association; it does not independently verify the full commit/tree chain. [R3, R4] |
| Writes and automation are not implemented. | Their guarantees must be designed and proven, not inferred from read-only tests. [R3–R5] |

**Verification boundary:** the existing tests were inspected, not run. No live publication, installation, host mutation or new benchmark was executed. There is no new architecture code in this package.

## 1. Landscape: reuse before rebuilding

| System or standard | What to reuse | Why it is not a direct substitute for the proposed scope |
|---|---|---|
| MCP, current documented revision 2026-07-28 | Tool/resource transport, discovery, version handling and authenticated integration patterns. | It transports capabilities. A stateOwl read/publication contract must still define project snapshots, projection, expected-state writes and outcome evidence. Optional task tracking must not be confused with those guarantees. [S1, S2] |
| A2A, released 1.0.0 | Agent delegation, messages, artifacts and task references. | A handoff can carry a stateOwl locator, but an A2A context or task ID is not itself the common project-state snapshot contract. [S3] |
| Agent Client Protocol | Editor-to-agent communication and session integration. | Useful at the execution boundary; not a replacement for the project's durable state store. [S4] |
| GNAP | The simple premise that agents can coordinate through repository files and Git history. | It defines agent/task/run/message entities and a Git-bound coordination convention. Its documented pull/rebase/retry policy does not establish semantic revalidation of arbitrary state transitions. [S5] |
| Lethe Memory Git | Exact heads, immutable changesets, CAS, request idempotency and explicit acceptance boundaries. | It operates on semantic memory records with its own review/merge authority. Adopting it unchanged would introduce more state and authority semantics than the charter allows. A reusable subset or adapter remains worth evaluating. [S6] |
| Beads | Mature problem framing around durable work records and coordination. | Its current Dolt-backed work model is a product/data-system choice, not a minimal adapter over every existing `.state` layout. JSONL is currently an export, not its source of truth. [S7] |
| LangGraph and Temporal | Checkpoint/replay discipline, interruption tests and effect-idempotency patterns. | They are execution/persistence systems in which stateOwl could participate. Requiring their runtime or service for every project would expand stateOwl's responsibility. [S8, S9] |
| Markdown handoff conventions | Human-readable records, small entry documents and durable cross-agent notes. | Useful project content, but a convention alone is not enforced atomic publication, exact snapshot addressing or ambiguous-write reconciliation. [S10] |

**Reuse decision:** use Git and provider CAS rather than inventing storage; use MCP where a plane needs remote tools; use A2A/ACP where the execution environment already uses them; use existing authentication. Borrow failure models and fixtures from durable systems. Do not import their entire workflow or memory model.

**What remains to prove:** the value of a small common contract over strong targeted-read alternatives, and that independent adapters preserve its guarantees. If an existing implementation can satisfy the fixtures without a new workflow schema, mandatory service or authority system, adopt or extend it instead. Novelty is not an acceptance condition.

## 2. Responsibility and terminology

| Term | Meaning in this design |
|---|---|
| Project state | Records a project deliberately publishes as its operational continuity source. Not every conversation message or working file. |
| Store | The authoritative storage location and state namespace. An adapter's local cache is not automatically that authority. |
| Snapshot | An immutable version of the records in one store namespace. Its identifier is opaque outside the provider binding. |
| Locator | A portable description of a store, current/exact version and selected record or route. It contains no credential or authority grant. |
| Route | A project-defined name resolved to exact records and a bounded view. |
| Profile | Optional, project-owned routing and validation semantics. Governance is one such integration, not the universal model. |
| Publication | One guarded transition from an expected snapshot to a new snapshot in one namespace. |
| Execution plane | The replaceable environment that reads state, performs work and requests publication. |

stateOwl owns addressing, exact snapshot consistency, bounded reads, source provenance, mechanical publication checks, stable outcome semantics and conformance.

Projects own what records mean, which task is relevant, whose decision is authoritative, which transitions are valid, which evidence is required and which external actions are permitted. Execution environments own model calls, tools, scheduling, credentials and process lifecycle. Providers own storage durability, access control and atomic update primitives.

A “resumable project” means its **published** decisions, work position, references and recovery records can be recovered. It does not mean arbitrary in-flight RAM, unsaved code, hidden reasoning, open sockets or unrecorded side effects migrate between planes.

## 3. Architecture decision

### 3.1 Three boundaries, not a universal runtime

The flow is **plane binding → stateOwl contract → provider adapter**. A trusted project resolver/validator supplies project meaning at the contract boundary.

| Component | Owns | Must not own |
|---|---|---|
| Core contract | Read/publication semantics, locators, snapshots, provenance, errors and limits. | Task lifecycle, approvals, claims policy, scheduling or identity service. |
| Provider adapter | Ref/version resolution, exact object access, batching, caching, atomic publication and reconciliation evidence. | Deciding which project work is approved. |
| Plane binding | Native tool schemas, authentication integration, permission prompts, result presentation and cancellation handling. | A divergent state format or weaker publication guarantee. |
| Project profile | Native route resolution, required context, transition validation, authority interpretation and recovery policy. | Replacing the core's atomicity or disguising an uncertain write as success. |

A profile can be ordinary trusted adapter code plus fixtures. Do not start with a plugin runtime for profiles, a general rules language or an automatic remote-code loader.

### 3.2 Public operations

**`read`** is mandatory for readers. **`publish`** is mandatory only for implementations advertising write capability. **`observe`** is optional, specified for machines and normally not exposed as another model tool. Capability descriptions and limits accompany installation/connection; they need not consume a separate model turn before each call.

Resolve refs, peel tags, fetch routers, deduplicate paths, compute hashes, call providers and reconcile receipts inside a qualified tool implementation. A skill that tells the model to make these calls remains an assisted integration, not proof that provider operations disappeared from model context.

### 3.3 Choices rejected now

Do not make a router file mandatory; require every plane to use MCP; deploy a central project-state database; standardize task/review/claim records; auto-merge stale transitions; introduce a scheduler; or build every language SDK and native binary at once. Each adds scope without being necessary to prove continuity.

## 4. Candidate protocol

This section fixes the intended behavior. Field spelling and complete JSON Schemas are the next specification deliverable, not a claim of a released wire protocol. Examples use illustrative values.

### 4.1 Locator and snapshot identity

Use a small versioned JSON locator first. Do not invent and standardize a custom URI scheme before there is a demonstrated interoperability need.

```json
{
  "protocol": "stateowl/next-draft",
  "target": {
    "kind": "git",
    "authority": "github.com",
    "resource": "acme/project",
    "namespace": "refs/heads/state"
  },
  "at": {"current": true},
  "record": {"route": "current"}
}
```

For a frozen handoff, replace `at` with `{"snapshot":"git:sha1:<full-object-id>"}`. The generic protocol treats that token as opaque and compares it only within its store scope. Another binding may use a SHA-256 Git ID or an opaque revision. A GitHub API adapter and a local Git adapter may access the same canonical Git target; their access methods are not separate project identities.

An authoritative local-only repository needs its own stable store identity. A filesystem path can be an access hint but is not a portable identity. Repository moves, namespace deletion/recreation and provider migrations require explicit mapping or a new namespace generation. Never infer object equivalence from equal-looking unscoped strings.

Separate native object IDs from a portable digest of **raw record bytes**. Use an algorithm-labeled SHA-256 content digest for portable byte checks; preserve native Git IDs as additional provenance. A digest establishes byte identity, not author identity, authorization or currentness. Git's documented hash transition reinforces why SHA-1 must not be universal. [S28]

### 4.2 `read`

A request selects one target and either its current head or an exact snapshot. It contains one or more uniquely named selections, each a direct path or route, plus optional field projection and explicit linked detail.

```json
{
  "protocol": "stateowl/next-draft",
  "target": {
    "kind": "git",
    "authority": "github.com",
    "resource": "acme/project",
    "namespace": "refs/heads/state"
  },
  "at": {"current": true},
  "records": [
    {"key": "current", "route": "current"},
    {"key": "work", "path": "state/work.json", "select": ["id", "status"]}
  ]
}
```

The contract is:

1. A current read resolves the mutable head **once**, then binds every dependent routing and record read to that snapshot. A directly addressed exact-snapshot read does **zero mutable-ref resolutions**. Object verification/fetches may still be necessary.
2. A separate optional current-head assertion preserves the meaning of 0.1.0 `expected_head`. It is not an alias for historical read mode.
3. Direct paths need no router. Repeated paths are fetched once per snapshot within a logical call. Related route lookups share the same routing reads.
4. The initial projection vocabulary remains exact top-level JSON fields. Do not add a general query language without a measured need. A result identifies its selection and missing fields; it never presents a projection as the full record.
5. Expansion is explicit and non-recursive. Cross-store or differently versioned links require their own exact snapshots and provenance. Such results are not a distributed atomic snapshot.
6. Required records are all-or-error. Optional selections may report explicit absence. A partial/truncated result must never look complete. Exceeding a declared limit produces a bounded error; the caller narrows the selection rather than accepting silently dropped content.
7. Results carry one compact shared snapshot descriptor, per-record path/native ID/raw-byte digest and selection metadata. Routing sources and resolver identity are included when they affect the view. Repeating the same long repository descriptor for every field is unnecessary.
8. A returned current snapshot was current at the provider's resolution point. It is not a promise that the branch remains unchanged after the call.

A record representation is explicit: structured JSON, UTF-8 text or base64 bytes. Field projection applies only to JSON. Do not guess a representation from the filename or alter the original bytes while calculating provenance.

Provider-returned provenance and independently verified object-chain provenance must be labeled differently. An adapter must not advertise stronger verification than it performed.

### 4.3 Routing without a new state layout

Keep `.stateowl/router.json` as an **optional legacy convention**. Retain `stateowl.router/v1` support in a compatibility adapter. It is not the mandatory entry point for every project.

For existing Governance projects, the resolver starts from native `.state/current.json` at the chosen exact snapshot and follows the project's own routing rules. Do not create a second authoritative router, copy task records into another schema or edit Governance merely to make stateOwl convenient. An actual sanitized Governance fixture must establish the mapping before compatibility is claimed.

Routing/projection/link metadata can live in a small optional manifest, trusted integration configuration or a project profile. If configuration is outside the state snapshot, identify its exact version/digest in provenance. A change in resolver semantics invalidates cached projections and observation tokens.

Do not put one entry for every historical task in a universal router. Prefer direct paths, deterministic ID-to-path resolution or the project's existing bounded index. The resolver's read set must be visible in conformance traces.

### 4.4 Errors and bounds

Use a compact machine code, a human explanation, a retry disposition and, for writes, publication-outcome certainty. Minimum categories are invalid request, unsupported version/capability, unauthenticated, forbidden, not found, snapshot unavailable, integrity mismatch, limit exceeded, validation failed, conflict, rate limited and indeterminate publication. Provider details are diagnostic fields, not unstable replacements for the common categories.

`NOT_FOUND` must not silently mean “authorized empty state.” Providers may deliberately conceal forbidden resources; bindings must preserve that uncertainty rather than infer permission.

Specify UTF-8, duplicate-key rejection, non-finite-number rejection, normalized paths, maximum record/response bytes and expansion counts. Metadata numbers must be cross-language safe. When structured projection cannot represent a source number losslessly, reject that structured view or return an explicitly raw-text representation; do not round it silently. Arbitrary source bytes are not rewritten merely to fit a canonical JSON style.

## 5. Writable-state design

### 5.1 One namespace, one expected snapshot, one transition

`publish` accepts a target, an expected snapshot, an operation ID and exact record replacements/deletions. The adapter computes the request/change digest; the model does not have to calculate hashes. The profile's authoritative validator binding is resolved independently of any untrusted request claim.

```json
{
  "protocol": "stateowl/next-draft",
  "target": {
    "kind": "git",
    "authority": "github.com",
    "resource": "acme/project",
    "namespace": "refs/heads/state"
  },
  "expected": "git:sha1:<previous-head>",
  "operation_id": "<unique-transition-id>",
  "changes": [
    {
      "path": "state/work.json",
      "put": {"encoding": "utf8", "data": "{\"id\":\"work\",\"status\":\"ready\"}\n"}
    },
    {"path": "state/obsolete-pointer.json", "delete": true}
  ]
}
```

Start with whole-record put/delete, not a new patch language. Preserve all untouched records and metadata. Reject duplicate paths, path collisions, unsupported file kinds, deleting a missing record and empty/net-no-change transitions with explicit non-publication results. New regular-file defaults and existing mode preservation belong in the Git binding.

A writer must provide **atomic visibility of all changed records and an exact expected-state comparison**. A provider lacking that primitive is read-only until an adapter can supply it honestly. Sequential file writes are not an acceptable emulation of a transaction.

Whole-namespace comparison intentionally rejects even disjoint stale writes. That is a simple, safe starting point. Introduce narrower conflict scopes only after benchmarks show that this conservatism materially harms useful work.

### 5.2 Publication sequence

The trusted adapter validates syntax, target scope and exact changes; resolves the applicable project authority/validator at the expected state; constructs and validates the complete candidate transition; then atomically admits it only if the current namespace still equals the expected snapshot. A final fresh verification checks the admitted snapshot, changed bytes and receipt binding.

Validation must see the old state and candidate together. Checking each file in isolation cannot establish a multi-record invariant. A request cannot weaken its own validator or authority rules and then use the weaker candidate rules to approve itself. Project-defined policy changes require the project's existing authority process.

The ordinary success result distinguishes **committed snapshot** from **currently observed head**. Another worker may already have published a valid successor. If this publication was admitted and verified, observing that successor is not a failure and must not trigger a duplicate write.

### 5.3 Outcomes that survive uncertainty

| Outcome | Required meaning | Permitted next step |
|---|---|---|
| `committed` | Admission is established and fresh verification succeeded. | Continue from the receipt; re-read current state when needed. |
| `not_committed` | This request is known not to have been admitted; the reason is explicit. | For conflict, re-read, reconsider and revalidate a new transition. For validation/permission failure, correct the cause. |
| `verification_pending` | Admission is established, but required fresh verification could not finish. | Verify the same publication. Do not create another transition. |
| `indeterminate` | The adapter cannot establish whether admission occurred. | Reconcile or repeat the identical request within its replay contract. Do not rebase it or invent a new operation ID. |

A timeout is not a conflict. A commit object existing in storage is not proof that the state head ever admitted it. Seeing the original head again is not, by itself, proof that an in-flight request will not complete later.

Each transport maps these outcomes without loss. For example, a network exception after dispatch must not be converted to an ordinary retryable “write failed” message.

### 5.4 Replay and reconciliation without a mandatory database

Before dispatch, the caller/binding retains the exact request envelope and operation ID. The published transition carries a receipt binding its expected state, operation ID, change digest and validation identity where applicable. The receipt is committed with the state, not written afterward into an unrelated log.

For Git, commit metadata can carry this binding; it need not become a second task ledger or require a new `.state` file. Reconciliation checks the actual parent and full relevant delta, not only a message marker. A future manifest-based provider can store the same binding in its immutable snapshot manifest.

The replay identity is scoped to the target namespace and expected snapshot. Reusing that identity with different content is rejected when reconciliation establishes the mismatch. Clients generate a new operation ID after reconsidering a conflict against a new base. No universal cross-project idempotency database is required.

An identical retry may recover the original receipt or race the original request under the same expected-state comparison. Only one transition from that base can be admitted while the namespace advances monotonically. If another transition won, the adapter establishes that fact before returning a definitive conflict.

History searches are bounded and invisible to the model. If receipt history is missing, retention has expired, the branch has been rewritten, or a search cannot establish the answer within limits, return `indeterminate`. Do not manufacture certainty. A provider advertises its reconciliation/retention guarantees; a profile must preserve unresolved effect evidence for as long as its own recovery policy requires.

The Git writer's normal operating requirement is an append-only state publication history, with no force reset or silent namespace recreation. Where existing retention or merge procedures do not preserve sufficient admission evidence, qualify an alternative provider receipt mechanism or restrict the guarantee. Do not silently rewrite Governance retention rules to fit an adapter.

### 5.5 Provider choices

**GitHub:** prefer `createCommitOnBranch` with `expectedHeadOid` for bounded ordinary-file state transitions. Its API supplies the expected-head input and multi-file change request needed for this design. Qualify permissions, limits, branch rules and lost-response behavior in the implementation stage. `clientMutationId` is not documented as a durable idempotency guarantee; stateOwl must not treat it as one. [S24]

**Do not equate REST `force:false` with compare-and-swap.** The REST ref update checks fast-forward ancestry and has no explicit expected-old-head parameter. A carefully constrained append-only algorithm may derive useful safety from it, but that is a separate proof, not the general contract. Use the stronger available primitive first. [S25]

**Authoritative local Git:** construct objects without modifying the user's product working tree and update the state ref with explicit new and old object IDs. `git update-ref` documents that exact old-value check. [S26]

**Remote Git transport:** an adapter may use an explicitly valued `--force-with-lease=<state-ref>:<expected>` check while separately enforcing that its candidate is a new commit based on that expected state. Never use bare force or an implicit tracking-branch lease. Despite the command option's name, the proposed adapter must reject history rewrites. [S27]

### 5.6 Transaction boundary

Atomicity covers one state namespace. It does not cover another repository, another branch, a deployment, an email, a payment or an external service. Record exact product/evidence versions in the state transition. Use the project's effect-intent and reconciliation rules for work outside the transaction.

Creating a new state namespace is a separately authorized setup action. Normal publication must not quietly create a missing namespace or switch to a convenient branch.

## 6. Automation and interruption

### 6.1 Three separate problems

| Problem | Mechanism | Owner and limit |
|---|---|---|
| Two workers publish incompatible state. | Exact expected-state comparison plus atomic transition. | Core/provider. Prevents lost updates, not duplicate computation. |
| Two workers do the same eligible work. | Project eligibility and an atomically published claim, with leases only where needed. | Profile/executor. A claim must be admitted before relying on it. |
| An external action repeats or has unknown outcome. | Stable effect identity, target-side idempotency, intent/outcome records and reconciliation. | Project and effect target. A Git transaction cannot supply exactly-once external execution. |

Claims, leases, renewals and fencing are **not universal core entities**. A profile that needs them can update its existing records through `publish`. A one-person interactive project need not install an unused coordination subsystem.

A lease profile must define its clock authority, acceptable skew, renewal and takeover rules. An agent-supplied timestamp is not enough to establish safe expiry. Lease expiry alone does not stop an old process. A fencing number is useful only when the effect target checks and rejects stale numbers. An integer stored in Git, or a random lease token that the target ignores, does not provide that protection. For non-idempotent targets without enforceable fencing, require reconciliation or human authorization before takeover rather than pretending automatic recovery is safe.

### 6.2 Cheap wake/check behavior

The normal loop is: provider event or existing schedule → deterministic observation/eligibility check → no model call when nothing relevant is eligible → bounded agent work → guarded publication → sleep.

`observe` standardizes a target, a selection/dependency scope, a prior comparison token and an outcome of changed, unchanged or unknown/error. It returns no broad state dump. The token is valid only for the same target, selection, resolver version and authorization scope. A provider can implement this using a head read, conditional request or a cached dependency signature verified against current state.

A root-head change may be a false positive for a particular worker. A deterministic profile check can compare the relevant record/routing dependencies before invoking the model. Webhook delivery is a hint to check authoritative state, not proof of a valid task transition. Handle duplicate/out-of-order events and periodically repair missed notifications.

**Unchanged state does not necessarily mean no work.** A lease can expire or a scheduled action become due without any record changing. The executor/profile keeps the next relevant deadline and evaluates time-based eligibility even when the head is unchanged. Policy/credential changes, retry deadlines and changed resolver versions also invalidate a simplistic “same head, sleep forever” rule.

Authentication failure, rate limiting and missing state are errors, not “unchanged.” Backoff and monitoring remain executor concerns. Do not spend a model invocation merely to explain each idle check.

GitHub documents that correctly authorized conditional GETs returning 304 do not consume the primary REST rate limit. They still incur requests and latency; do not market observation as universally free or assume the same rule for mutations. [S30]

### 6.3 OpenClaw and other existing schedulers

Use an existing scheduler or event source rather than adding a stateOwl daemon. Current upstream OpenClaw documents native tools, automation command/script payloads and scheduled heartbeat agent turns. A deterministic gate should use a verified non-model execution path. A heartbeat that asks the model whether anything changed does not meet the zero-idle-model target. The exact deployed OpenClaw version must be qualified; upstream documentation is not proof that an older installation supports every current hook. [S17, S18]

### 6.4 Restart and handoff contract

Before an external effect, publish the project's required intent and claim. Use a stable effect identity across retries and handoffs, not a new timestamp-based key per attempt. After execution, publish the observed outcome with its evidence. If interrupted between those steps, another plane sees a pending/uncertain effect and reconciles it before doing more work.

An interrupted worker reloads current durable state, checks existing claim/effect/publication receipts and verifies referenced artifacts. It does not infer completion from its old chat or automatically repeat the last command.

An ephemeral client that disappears before persisting either its request envelope or project intent cannot promise recovery of that unpublished intent. StateOwl can preserve the last published state, not information never durably written. The integration must make this boundary visible.

## 7. Integration and packaging matrix

The following are **documented integration paths and proposed stateOwl bindings**, not installations performed or end-to-end passes obtained in this session.

| Plane/environment | Proposed binding | Requirements and qualification boundary |
|---|---|---|
| ChatGPT with stock GitHub app | Focused native-connector recipe using exact reads, where exposed. | Current official documentation describes live, on-demand, read-only access. Availability and exact addressing must be checked on the actual surface. A recipe is not automatically a single executable `read` tool. [S11] |
| ChatGPT Web with stateOwl plugin | Small skill for entry/usage; remote MCP only when needed for executable aggregation or guarded writes. | Current plugins can package skills and MCP. Installing a web plugin does not deploy local scripts. Do not assume access to the stock connector's credentials or internal tool chaining. [S12] |
| ChatGPT Work / Codex runtime | Native plugin/runtime binding or CLI/Git, according to actual execution and network permissions. | Hook scripts must exist in the execution environment. A web listing is not deployment or credential provisioning. [S12, S13] |
| Claude web | Authenticated remote MCP exposing the same operations. | Remote connections originate from Anthropic infrastructure; a local-only stdio process is not reachable merely because the user has installed it. [S14] |
| Claude Desktop / Claude Code | Local extension/stdio MCP, remote MCP or CLI where supported. | Local desktop and hosted-web connectors are not interchangeable. Keep tools useful without custom UI. [S14, S15] |
| Pi | Thin TypeScript extension registering native tools; optional shared MCP binding. | Pi supports executable extensions, lifecycle events and structured tool results. Do not mistake Pi session persistence for shared project-state storage. [S16] |
| OpenClaw/headless worker | Native plugin tools plus an existing non-model observation gate. | Use operator-approved credentials and tool exposure. Scheduling stays in the host; no new stateOwl scheduler. [S17, S18] |
| Codex/local Git-capable agent | Small CLI/library, or stdio MCP when preferred. | Local access does not by itself establish remote-head freshness or remote write authorization. CLI MCP support is documented; each cloud worker's permissions remain a separate qualification. [S13] |
| Generic MCP-capable plane | Reuse one transport binding and the same semantic fixtures. | Negotiate/qualify the client's actual MCP revision. MCP compatibility alone does not prove stateOwl write conformance. [S1] |
| Ephemeral shell | Existing-runtime CLI via Python/uv or Node/npm; native binary later if justified. | Include cold install, registry access, runtime download and credential availability in the assessment. A short launch command is not zero dependency. [S32, S33] |
| Gemini CLI | MCP/extension packaging or local CLI. | Local stdio and remote transports are documented. Keep credentials and trusted-folder restrictions in the integration boundary. [S19] |
| Gemini web/mobile through Spark | Remote custom MCP for eligible accounts; explicit user confirmation for writes. | Official documentation currently limits the feature to eligible Spark users, adults in the US, personal accounts, English and Keep Activity enabled. Do not infer unattended write support. [S20] |
| Gemini Enterprise | Separately configured custom remote MCP connector. | Admin enablement, Streamable HTTP, TLS and OAuth/organization policy requirements differ from consumer Spark. [S21] |
| Antigravity | Shared local/remote MCP adapter. | Qualify the selected Antigravity surface and its tool-permission rules. [S22] |
| Grok API | Shared remote MCP adapter with a narrow tool allowlist. | API-side remote MCP is documented. This research did not establish an equivalent general Grok web integration; do not advertise one from API evidence alone. [S23] |

### Packaging decision

Maintain the existing small Python implementation as a reference and local distribution. Prototype an independent TypeScript implementation because it can fit native Pi/OpenClaw bindings and provides a meaningful cross-language test. Neither language is mandatory for the protocol.

`uvx` and `npx` are optional distribution choices. Both have a first-use and runtime footprint. An SDK is a convenience for its host language, not an interoperability requirement. A native binary is a possible later distribution if measured cold-start or runtime availability warrants maintaining builds for multiple systems. [R11, S32, S33]

A shared remote MCP service is justified only for planes whose hosted environment cannot execute the necessary aggregation directly. Reuse authorized hosting where available, but do not conceal its operating, credential-storage or authentication costs. It need not become the authoritative state store. No hosted service, tunnel or identity integration is created by this architecture session.

**Multiple native bindings are preferable. Multiple independent state systems are not.** Every qualified binding uses the same snapshot, publication, error and provenance semantics.

## 8. Storage architecture

### 8.1 Minimum primitives

A read-capable provider must resolve the current version of a namespace and read named records from an exact immutable version. It must distinguish unavailable history, absent records and access/integrity failures. A write-capable provider additionally needs atomic expected-state publication and sufficient receipt/history access to establish a known outcome or explicitly return uncertainty.

Provider capabilities declare maximum record/transaction sizes, supported source types, current-read consistency, retention and reconciliation bounds. Efficient batch reads and change observation are optimizations with defined semantics, not reasons to expose provider plumbing to the model.

The protocol does not require branch listing, repository crawling, full clone, arbitrary SQL, a queue, a global transaction coordinator or a general search index.

### 8.2 GitHub state branch

Keep the existing dedicated state branch. Read only relevant objects at the resolved commit. Use API batching where supported and useful; cache immutable objects by canonical store identity, snapshot and object identity. A qualified local Git cache can supply exact bytes, but a stale remote-tracking ref cannot assert the remote's current state.

Publish one commit per meaningful atomic transition. Do not create a state commit merely because an observer polled successfully. State history, evidence retention and cleanup remain project/provider policies. Do not mix state maintenance with unrelated product-tree edits.

GitHub REST and GraphQL are alternative access paths to this same backend. The provider adapter chooses the most efficient safe path, subject to permissions, object types, payload limits and branch rules. A future repository-native facility is not a prerequisite.

### 8.3 Local Git

A local authoritative store supports offline exact reads and guarded local publication. Remote publication is a separate outcome. Never label a locally committed change “published to GitHub” before the remote admits it.

Use object-level operations or an isolated worktree rather than switching the user's active product branch. Preserve unrelated staged/unstaged work. A local adapter must apply the same bounds, regular-file policy, hash handling and provenance rules as the API adapter.

### 8.4 Future non-Git provider

The smallest alternative is immutable records plus an immutable snapshot manifest, with one atomically compared-and-updated head pointer. The manifest maps record names to exact objects and includes the publication receipt. The mutable pointer includes an update generation where necessary to detect namespace resets or returning to an old content value.

This is a conceptual provider design, not a decision to deploy an object store or database. A non-Git, opaque-ID conformance backend should first demonstrate that protocol semantics do not secretly depend on Git commits. A production provider follows only if actual needs justify it.

### 8.5 Requirements for a future GitHub repository-state facility

A proposal to GitHub should request a **repository-attached versioned namespace**, not an agent scheduler. Essential requirements are atomic multi-record changes with exact expected-version comparison; exact-version batch reads; durable operation receipts; explicit retention and export; events/conditional observation; repository ownership linkage; and permissions appropriate to state publication without unnecessary source-code write authority.

It should expose namespace generations so delete/recreate and rollback cannot masquerade as unchanged state. It should preserve provider-native actor/audit evidence while allowing project-defined authority. It should support links to exact source commits and migration from existing state branches without requiring a new task schema.

Useful limits and service behavior must be documented: record/transaction size, conflict responses, rate treatment, event delivery, historical access and recovery after an ambiguous request. A stateOwl conformance adapter would be the acceptance proof. This is a requirements proposal only; no such GitHub product is assumed to exist.

## 9. Security and authority

Keep six questions separate: **Who authenticated? What repository access do they have? Can this transition be published atomically? Does the project authorize it? Is it semantically valid? Is the external action permitted?** An affirmative answer to one does not answer the others.

A read-only binding remains useful. Write capability must be explicit and least-privileged. Where a remote integration is justified, prefer an existing approved identity flow and narrowly scoped repository credentials. GitHub installation tokens support repository/permission scoping and short expiration, but the requested GraphQL/REST operations still need actual permission qualification. Do not create a new identity system merely to expose state reads. [S29]

A third-party stateOwl service cannot assume it inherits another connector's GitHub authorization. User authentication to that service and delegation to GitHub are distinct boundaries. Credential storage and refresh have an operational cost even when the service stores no authoritative project state.

A model-provided `validated: true`, a tool annotation, a successful Git push or post-publication CI result is not pre-publication project authority. A Governance-capable writer needs its existing authoritative validator and approval rules enforced before admission. If agents can bypass that path with unrestricted raw writes, stateOwl can report mechanically valid publication but cannot guarantee that all repository transitions respected project authority. An operator must choose the appropriate trust model or restrict admission paths; this package does not silently grant bypass rights.

Pin resolver/validator identities. Load executable profiles only through trusted installation/configuration, not because a fetched state record names a script. Treat repository text as data, not permission to run commands. Restrict cross-store targets and redirects to authorized destinations. Reject traversal paths and unsupported symlink/submodule behavior rather than following them opportunistically.

Caches must not cross user/tenant authorization boundaries. Specify permission revalidation and offline disclosure behavior. An immutable object hash is not a credential. Bound incoming bytes, parsing, expansion and outgoing context; protect both structured and model-visible outputs from secret leakage.

Proof strength must be honest: authenticated provider responses, native object-byte checks, independently verified object chains and cryptographic actor signatures are different evidence. Support existing stronger evidence where available, but do not require a new signing PKI for every stateOwl user.

## 10. Conformance and compatibility

### 10.1 Specification deliverable

Produce a short normative protocol document, machine-readable request/result/error schemas and language-neutral fixtures. Keep the legacy router schema, Git-specific identities and plane-specific transports separate from the core contract.

Use a standardized canonicalization only for the constrained transaction envelope/digest inputs. RFC 8785 is a suitable candidate with an explicitly defined JSON subset. The digest binds normalized target identity, expected state, ordered change descriptors with raw-byte digests, and applicable validation identity. It must not normalize or silently reserialize original project-file bytes. [S31]

Read-only, writable and observation capabilities should be separately testable. A read-only conforming implementation must reject unsupported publication clearly. A client must not fall back from guarded publication to unguarded writes when capability negotiation fails.

### 10.2 Required fixture groups

| Group | Required proof |
|---|---|
| Snapshot reads | Ref moves between calls; all dependent records still come from the originally resolved snapshot. Exact-snapshot mode performs no ref resolution. |
| Addressing | Direct path without router; multi-route shared reads; deterministic profile resolution; native `.state` fixture with no duplicated authoritative router. |
| Focus | Unrelated record and router growth; explicit one-level links; cross-store links bound to exact versions; no hidden broad reads. |
| Integrity/types | SHA-1, SHA-256 and opaque snapshots; annotated/lightweight/nested tags ending in commits; rejection of non-commit targets, wrong blobs and unsupported file kinds. |
| JSON/bounds | Duplicate keys, non-finite numbers, invalid UTF-8, unsafe numeric projection, missing selected fields, oversized inputs and path traversal. |
| Concurrency | Two writers use the same base: at most one is admitted. Rejected transitions leave no partial records. Disjoint stale changes are still conflicts under the initial contract. |
| Ambiguity | Lost request/response at each publication step; success followed by a successor commit; same-request retry; different content with reused replay identity; bounded reconciliation exhaustion. |
| History | Namespace deletion/recreation, rollback to an old head, missing receipts and retention expiry produce explicit uncertainty/discontinuity, not invented failure or success. |
| Authority | Candidate cannot weaken its own validation; unauthorized path/effect cannot be approved by a model assertion; raw-access trust limits are visible. |
| Observation | Zero model calls for idle checks; relevant deadlines still evaluated at an unchanged head; lost/duplicate events; unknown/error never becomes unchanged. |
| Cross-plane continuation | A different implementation reads the same published state and relevant artifact references, then safely continues after an interruption. |

A GitHub adapter and local Git adapter alone do not prove independence from Git semantics. Include a non-Git opaque-ID backend in the conformance/fault harness. It need not become a shipped production service. A semantic test backend does not establish production durability; every shipped storage provider requires its own durability and interruption qualification.

### 10.3 Independent implementations and versions

Use the existing Python implementation and a separately implemented TypeScript reader/writer for interoperability proof. A TypeScript wrapper that launches Python is not a second implementation. Compare semantic results, exact byte digests and error/outcome categories; do not require irrelevant diagnostic timestamps to be identical.

Version core protocol, profile semantics, legacy schema and distribution packages separately. Breaking meaning requires explicit version negotiation or a new protocol generation. Additive diagnostic fields may be ignored; unknown required capabilities may not. Extension fields must be namespaced and unable to change safety semantics without negotiation.

Preserve 0.1.x callers through a compatibility layer. Retain the old `expected_head` behavior, route format and projection rules there. Formalize the new contract independently instead of declaring the old Python API normative by accident.

**Stability gate:** no stable protocol claim until two independent language implementations, materially different execution planes, Git plus a non-Git semantic test backend, the negative/failure fixtures and reproducible benchmark evidence pass. Reader stability may precede write-capability stability, provided the distinction is explicit.

## 11. Benchmark plan

The benchmark must separate model-visible cost from backend work. A one-tool response may still hide many provider requests; a small final JSON object does not mean the model avoided seeing the raw inputs earlier.

### 11.1 Strong baselines

Compare the candidate with the existing 0.1.0 reader; direct known-path GitHub REST reads at a pinned commit; a compact batch GraphQL query over exact objects; local Git object/batch reads; a project-native resolver without stateOwl; and a carefully maintained compact summary/index. Include native tool, CLI and MCP bindings using equivalent data and semantics.

A summary/index baseline must include its maintenance and invalidation cost. A raw known-file read may be the best solution for a tiny project. StateOwl must justify itself by portable guarantees and useful aggregation, not only by defeating an unnecessary crawl.

### 11.2 Measurements

| Dimension | Measurement |
|---|---|
| Model cost | Actual exposed tool schemas, tool calls/results and tokenizer-measured tokens; separately report raw bytes. Name tokenizer/model configuration. |
| Provider cost | Network requests, object operations, transferred wire/payload bytes, auth refreshes, conditional hits and API rate accounting. |
| User latency | End-to-end p50/p95, cold/warm cache, cold process, first-use install and transient failure recovery. |
| Footprint | Package bytes, runtime/download requirements, peak memory, processes and persistent services. Count already-present versus newly required runtime separately. |
| Scale | Unrelated records at 0/100/10,000/100,000; fixed and growing router; 1/5/20 requested routes; large unused fields and large linked details. |
| Publication | Single writer and contending writers; overlapping/disjoint changes; conflict rate, useful completed transitions, retries and failure recovery. |
| Automation | Poll/event traffic, deterministic check cost, model invocations, due-time correctness, duplicate wakeups and outage behavior. |

Control repository contents, revisions, cache state, network location and credentials. Record cold and warm results separately. Use provider traces rather than labeling simulated store calls as measured API traffic.

### 11.3 Initial acceptance targets—not measured results

A fresh logical read resolves its root mutable ref once; an exact-snapshot read does not. One batch shares snapshot and routing work. Unrelated history does not increase a fixed selection's exposed records or model context. No benchmark hides router growth or the cost of maintaining a compact index.

In a declared 1,000-check idle scenario, model invocation count must be **zero**. A due deadline at an unchanged head must still be detected. Two stale competing publications cannot both succeed. Every forced ambiguous-write case must remain recoverable or explicitly uncertain, with no invented success and no repeated external action caused by blind retry.

Before claiming a release efficiency win, publish measurements against the best applicable targeted baseline and explain any slower path. Do not set invented millisecond or token-saving promises before measurement.

## 12. Migration from 0.1.0

| Preserve | Replace or extend | Keep compatible |
|---|---|---|
| Small standard-library Python implementation; focused fields; exact dependent reads; explicit links; byte verification; immutable cache concept. | Extract language-neutral specification; opaque/scoped snapshots; exact-read mode; batch selections; provider-aware tag peeling; portable digest/error rules; safe publication and observation. | Legacy CLI and router as a named compatibility layer; old freshness assertion; existing state files and layouts. |

Do not perform a destructive rewrite or introduce a second source of truth. First capture golden fixtures for 0.1.0 behavior. Add the new reader contract alongside it. Add a native `.state` profile only after testing against authorized fixtures, preserving original record bytes and routing authority.

Read-only integrations can ship while writable semantics remain experimental. Enable writers separately, only after their provider and profile qualifications. Update public claims to match the actual capability: a reference recipe, conforming reader, qualified writer and automation integration are different delivery states.

No backend migration is required for the first generation. A future storage migration needs an export mapping old exact snapshots to new identifiers, a guarded cutover of the canonical locator and a defined read/retention policy for old references. Do not silently declare new provider IDs interchangeable with Git commits.

## 13. Staged roadmap and release decision

The companion [roadmap](ROADMAP.md) specifies purpose, deliverable, dependency, proof and acceptance for each stage.

| Stage | Concrete result | Gate |
|---|---|---|
| R0 — Decision and reuse review | Ratified boundaries and a documented adopt/extend/build decision. | No implementation before approval; no competitor dismissed solely because it is not stateOwl. |
| R1 — Protocol and fixtures | Small normative draft, schemas, legacy fixtures and failure cases. | Independent implementer can understand required behavior without reading Python internals. |
| R2 — Read interoperability | Independent Python/TypeScript readers, native `.state` mapping and exact batch reads. | Equivalent results; no duplicate router; zero exact-read ref resolutions; strong-baseline measurements. |
| R3 — Guarded publication | Local Git and GitHub writers with exact CAS, receipts and outcome recovery. | Race/timeout/retention/authority cases pass on explicitly authorized fixtures. |
| R4 — Real plane continuity | Minimal local/native and hosted bindings; documented capability matrix. | Cross-plane resume succeeds without copying conversation or using a universal runtime. |
| R5 — Automation continuation | Deterministic observation gate and one project-specific claim/effect recovery integration. | Zero idle model calls, correct deadline handling and no unsafe repeat on interruption. |
| R6 — Stable candidate | Independent review, compatibility policy, reproducible benchmarks and release scope. | All advertised guarantees have evidence; unsupported capabilities remain explicitly unsupported. |

Some packaging can proceed in parallel after the relevant semantic gate. Do not use that flexibility to build ten integrations before proving two. The first independent-native target is Pi or OpenClaw; the first hosted target is ChatGPT or Claude through an approved executable path. Other MCP planes should reuse that transport work rather than create new cores.

### Risks that require evidence, not another speculative layer

The largest remaining risks are authenticated aggregation in hosted planes, trustworthy publication-outcome recovery without an unbounded receipt index, enforcing project authority when raw writes remain available, native Governance compatibility, and whether real context savings justify the abstraction over targeted reads. Each has a roadmap proof; none justifies adding a database, queue or new authority system preemptively.

### Final recommendation

Proceed with the protocol-and-fixture stage once this decision is accepted. Preserve the useful reader and existing state layouts. Prioritize exact batch reads and guarded publication before expanding installation options. Keep the promise narrow and testable:

**The project can change execution planes because its published state, provenance and recovery position do not belong to any one plane.**
