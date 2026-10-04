# R2 protocol ambiguity / missing normative input

## A01 — native `.state` fixture/profile

**Status: RESOLVED**

The original R2 candidate correctly reported that the frozen basis did not contain a shared native project-state fixture/profile.

The coordinator subsequently defined the shared fixture at:

`r2/native-state-fixture@60733bc765e029ebfde6102f5f2c265192cf95d9`

The TypeScript qualification consumes those exact fixture bytes and executes all eight coordinator cases through the independent TypeScript `Reader`.

The fixture establishes direct focused reads over project-owned `.state` bytes without:

- requiring `.stateowl/router.json`;
- creating a duplicate authoritative index;
- importing Governance lifecycle/policy semantics into stateOwl core.

No frozen R1/R2 protocol rule was reinterpreted and no TypeScript reader/provider implementation change was required.
