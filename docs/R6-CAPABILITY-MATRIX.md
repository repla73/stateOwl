# R6 exact capability, assurance and distribution matrix

**Accepted R5 base:** `main@e3f5b1224fd3def7ab4933f0f85bfc0a5aa1e192`. **Task Governance:** `claw0gang/governance@72b61e2bf9ae526eb9750fa80fce2cf6db977be3`. The presence of source, prior qualification and public distribution are **different statements**.

| Feature / environment | Present in source | Accepted evidence | R6 support boundary |
| --- | --- | --- | --- |
| Python `Reader` / `GitHubStore` / CLI | Yes | Legacy 0.1.0 six golden reads and R2–R5 regression suites | **Stable Python 0.2.0 compatibility** for this original API only. |
| Python `R2Reader`, GitHub/local Git/memory read | Yes | R2 90/90 normative reads, 6/6 legacy, 8/8 native `.state`, non-Git semantics, actual local Git | **Qualified `stateowl/0.2-draft.3`**, not stable future wire protocol. |
| Independent TypeScript read providers | Yes | R2 90/90 read, 6/6 legacy, 8/8 native, 90/90 cross-language + native 8/8 | **`0.2.0-draft.3` source only**; no stable/published npm API claim. |
| Python + TypeScript Git publication | Yes | R3 89/89 each, actual local Git 12/12 each, disposable live GitHub races/recovery, final R3 PASS | **Conditional:** externally enforced single-step Git namespace, trusted validator/authorization and retrievable receipt; not generic writable GitHub authority. |
| Python optional observe/HMAC | Yes | R5 full 92/92, explicit R5 15/15 and real 1,000-idle local qualification | Production Python observe implementation; caller owns secret/continuity; **no TS observe**. |
| Pi native tools | Yes (`bindings/pi`) | Accepted R4 Pi execution/cross-plane continuity | Controlled native extension; no hosted registry integration; publication opt-in and target-bound. |
| OpenClaw | **No plugin** | R4 fresh OpenClaw agent execution; R5 OpenClaw as executor environment | Execution evidence only; no OpenClaw integration installed or shipped. |
| ChatGPT | Instructions/recipe only | Existing connector-assisted exact read recipe | No executable hosted MCP/plugin/server. |
| Non-Git storage | In-memory test provider | R2 opaque-ID semantic qualification | **Not** a durable production non-Git adapter. |
| Gate, scheduler and effect handling | R5 `qualification/` fixtures | Headless eligibility, deadline, conflict, local idempotent effect simulation, failures | **Test/recipe only**. No scheduler, daemon, workflow engine, general idempotency or effect-target fencing. |

### Exact historical accepted evidence

- [R2](R2-INTEGRATION.md): independently implemented focused read, 90/90 per language, native `.state`, legacy, differential; [deterministic common benchmark](../benchmarks/results/r2-common-interoperability.json).
- [R3](R3-INTEGRATION.md): 89/89 publication conformance in both languages; real local Git, disposable GitHub qualified transitions A–E, receipt final-LF normalization and single-admission races. Repository-wide single-step writer confinement was an **assumption** of the qualification namespace, not an inferred GitHub guarantee.
- [R4](R4-INTEGRATION.md): Pi execution and actual OpenClaw fresh-agent continuation; no production OpenClaw plugin adoption.
- [R5](R5-INTEGRATION.md): 1,000 idle checks, **0 model calls**, **0 publications**, **0 effects**, deadline/concurrency/credential/continuity/restart matrix. The external-effect target was a disposable local fixture.

**Explicit non-claims:** no hosted API deployment, published npm package or Python registry artifact, general non-Git durability, constant network latency, validated blanket percentage of token savings, one-host automation scheduler, infinite Git history retention, general exactly-once external effects, or automatic authority enforcement. [Security and retention](../SECURITY.md) and [migration](R6-MIGRATION.md) apply.

The auditor of the frozen R6 candidate must independently verify source identity and run applicable package/import, regression and conformance smoke before acceptance; prior execution receipts are **reused, not re-executed**.
