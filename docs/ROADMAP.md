# stateOwl — Staged roadmap

**Date:** 3 October 2026  
**Status:** R0 complete · R1 complete · R2 complete and adopted · R3 next · R4–R6 pending  
**Design:** [Architecture decision](ARCHITECTURE-DECISION.md)  
**Evidence:** [Sources and verification record](SOURCES.md)

R0–R2 are complete, with R2 adopted on `main`. R3 is the next stage and has not started; R4–R6 remain pending. These stage labels are roadmap labels, not reserved Governance task IDs. Future implementation assignments must bind to the actual project rules and authorized targets then in force.

## R0 — Accept the decision and close the reuse choice

**Purpose.** Agree on the smallest product boundary before writing another runtime.

**Deliverable.** An accepted decision for a transport-independent read/publish contract, optional machine observation, project-owned semantics and Git-first storage. Record whether to adopt, extend or build after comparing the strongest alternatives, especially Lethe Memory Git and GNAP, against the required guarantees.

**Dependency.** This architecture package and the charter at a freshly verified repository revision.

**Proof.** Walk through an interactive handoff, two competing publications and an interrupted external effect. Identify which layer owns each step. Explain why adopting an existing system unchanged would or would not satisfy the charter.

**Acceptance.** Core/profile/provider/plane responsibilities are unambiguous. No mandatory database, scheduler, identity service, MCP server or workflow schema has entered the core. The decision is approved. Do not repeat the entire research exercise unless material evidence changes.

## R1 — Write the protocol and conformance fixtures

**Purpose.** Make independent implementation possible without treating Python source as the specification.

**Deliverable.** A short normative draft; request/result/error schemas; capability/limit declarations; Git identity rules; legacy router compatibility; read, publication and observation fixtures. Preserve 0.1.0 golden behavior before modifying it.

**Dependency.** R0.

**Proof.** An independent reviewer can derive expected outputs for exact reads, batched routes, absent optional fields, stale publication, lost response and unsupported capabilities solely from the specification. Fixtures cover malformed paths, non-finite JSON, annotated tags, opaque IDs, namespace resets and missing history.

**Acceptance.** No safety rule exists only in an implementation comment. Snapshot versus freshness semantics are explicit. The same request cannot legitimately receive contradictory publication-outcome meanings from two conforming adapters.

**Boundary.** Specification and tests first; no account integration or production deployment.

## R2 — Prove focused-read interoperability

**Purpose.** Establish portable state addressing and real context efficiency.

**Deliverable.** Independent Python and TypeScript readers; GitHub/local Git access; a non-Git opaque-ID semantic test backend; legacy-router compatibility; one authorized native `.state` fixture/profile. Publish benchmark inputs, traces and results.

**Dependency.** R1 read semantics and fixtures.

**Proof.** Both implementations return equivalent selected values and raw-byte digests. Exact reads perform zero mutable-ref resolutions; current batch reads perform one root resolution and share routing work. Direct paths work without a router. Test fixed/growing routers and increasing unrelated history. Compare with direct pinned-file reads and a compact batch baseline.

**Acceptance.** No duplicate authoritative `.stateowl` router is required. Existing project records remain unchanged. No hidden crawl or Python subprocess sits behind the purported independent TypeScript reader. Efficiency claims distinguish model-visible tokens, provider work and cold-start cost.

**Boundary.** Read-only. A mock non-Git backend proves semantics, not production storage durability.

## R3 — Qualify guarded publication

**Purpose.** Add writes without lost updates, false success or blind repetition.

**Deliverable.** Qualified local Git and GitHub publication adapters; exact expected-state checks; atomic record transitions; durable receipt binding; bounded reconciliation; explicit committed/not-committed/verification-pending/indeterminate outcomes. Include trusted project validation and its enforcement limits.

**Dependency.** R1 write contract and R2 exact-read/integrity support.

**Proof.** Race two writers from one base. Inject interruption before dispatch, after dispatch, after admission and before verification. Test success followed by a successor commit; identical retry; conflicting retry; reused replay identity with different data; retention expiry; namespace reset; unauthorized paths and candidate validator downgrade.

**Acceptance.** At most one competing transition is admitted; no partial record group is visible. Every claimed success is freshly verified. Unknown outcomes remain unknown until evidence resolves them. Replaying a request does not create another accepted transition. The adapter does not advertise project-authority enforcement where unrestricted bypass writes remain possible.

**Boundary.** Live writes only in an explicitly authorized disposable fixture repository/namespace. Do not use production state, create apps or provision hosts merely because the roadmap mentions qualification.

## R4 — Demonstrate real cross-plane continuity

**Purpose.** Show that the contract survives materially different execution environments.

**Deliverable.** One native/local binding and one hosted binding, with installation/authentication/capability receipts. Prefer Pi or OpenClaw for the independent native TypeScript path, and ChatGPT or Claude for the hosted path. Preserve an assisted native-repository recipe as a separate, accurately labeled option.

**Dependency.** R2 for reader qualification; R3 before any binding claims writes.

**Proof.** A worker reads a bounded task and leaves an exact publication. A different plane resumes from the locator and required records without the original conversation. Verify source identities, profile version, relevant work and an interrupted-operation receipt. Measure the actual model-visible tool chain.

**Acceptance.** No session transcript is the operational authority. A skill-only recipe is not mislabeled a single executable tool. A hosted tool does not assume access to another connector's token. Native and hosted bindings preserve identical outcome semantics.

**Boundary.** A remote MCP adapter is permitted only after its need, hosting, authentication and exact authorized scope are decided. A web plugin installation is not permission to deploy scripts, tunnels or services. Additional Claude/Gemini/Antigravity/Grok API paths reuse the qualified transport where possible.

## R5 — Prove automation and recovery

**Purpose.** Make unattended continuation inexpensive and safe under interruption.

**Deliverable.** Optional observation capability, a deterministic pre-model gate in an existing executor, and one project-specific eligibility/claim/effect integration. Include restart and operator-escalation behavior.

**Dependency.** R3 write recovery and a qualified R4 headless binding. The deployed scheduler/plugin version must be checked, not assumed from current upstream documentation.

**Proof.** Run 1,000 unchanged, not-due checks with zero model invocations. Advance a deadline without changing the state head and verify detection. Inject duplicate/missing/out-of-order events, two claimants, an expired lease, revoked credentials, an outage, a lost publication response and an effect that completed before its outcome was recorded.

**Acceptance.** State conflicts, duplicate work and duplicate effects are handled as different problems. No unknown response becomes an automatic repeat. A stale worker is fenced only where the target actually enforces fencing. Other non-idempotent cases reconcile or stop for authorization. No new stateOwl scheduler or task engine is introduced.

## R6 — Release a stable, evidence-backed capability set

**Purpose.** Stabilize demonstrated behavior, not the largest feature list.

**Deliverable.** Independent interoperability review; version/compatibility policy; published schemas and fixtures; reproducible benchmark report; supported-plane/provider matrix; security/retention assumptions; migration guidance from 0.1.0. Prepare the optional GitHub repository-state proposal separately.

**Dependency.** All gates relevant to the advertised capability set. Read-only stability may precede writable stability, with explicit labeling.

**Proof.** An independent developer implements an adapter from the specification. Run cross-language and cross-plane fixtures, production-provider fault tests, non-Git semantic tests and best-baseline benchmarks. Confirm legacy compatibility and fail-closed unsupported-version behavior.

**Acceptance.** No advertised guarantee depends on private implementation knowledge, one Python package, one vendor or an unqualified host feature. Unsupported planes and uncertain guarantees are listed honestly. No fixed latency, token-saving percentage or exactly-once external-effect claim appears without corresponding evidence.

## Sequencing and stop rules

The critical path is **decision → specification → exact reads → guarded writes → real handoff → automation → stability**. Packaging may overlap after its semantic dependencies are settled. It must not expand into ten implementations before two work end-to-end.

Stop a dependent path when the provider cannot deliver exact guarded publication, the platform lacks an executable/authenticated tool path, or an effect cannot be safely reconciled. Preserve completed evidence and report the precise missing capability. Do not silently replace the backend, weaken authority, reauthenticate in a loop or create infrastructure to bypass the boundary.

No production host is mandatory for protocol/specification work. Local development and disposable qualification environments should be sufficient until an explicitly scoped deployed-runtime integration test is authorized.
