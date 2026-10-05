# R3 Integration Candidate

Status: assembled integration candidate only. R3 is not complete or adopted.

## Subjects

- Canonical R3 basis/main: `8c0b7baefcc2ba4c48cbf4dfa1964551c1291fa4`
- W1 contract: `e497bcf82ba1483fc1b3406ed8eed348f174b457`
- Accepted Python publisher: `86fcf99111348056280f8fe63cbd414010d6867b`
- Accepted TypeScript publisher: `7db03191aa4d4d70a98aba64f4ce4afe82897059`
- Integration branch: `r3/integration`

The Python and TypeScript R3 implementation/test path sets were materialized from the accepted subjects without rewriting accepted implementation bytes. W1 shared contract/tooling remains based on the exact contract subject. R2 behavior is preserved except for changes already present in the accepted R3 candidate diffs.

## Deterministic evidence

Python:

- R3 deterministic tests: 30/30
- publication conformance: 89/89
- R2 regression: 24/24

TypeScript:

- deterministic tests: 62/62
- publication conformance: 89/89
- R2 read conformance: 90/90

Cross-language publication semantic equivalence: PASS.

## Independent audit

`R3_W3_ROUND2: PASS`

F01-F03 corrections were accepted with no remaining blocking or non-blocking findings.

## W4 real local-Git evidence

- Python: 12/12
- TypeScript: 12/12
- all four real races single-admission: PASS
- reconcile zero-admission: PASS
- positive admission evidence preservation: PASS
- skipped-head non-inference: PASS
- expected-old CAS: PASS
- complete-tree preservation: PASS
- mode preservation: PASS
- ordinary worktree isolation: PASS

Evidence boundary: W4 executed against real local Git. It is not live GitHub qualification. No local machine paths or raw execution logs are canonicalized here.

## Remaining gate

W6 disposable live-GitHub qualification remains required. GitHub receipt-byte behavior, live CAS/races, credential scope, and live provider behavior are not yet accepted.

R3 is not yet complete or adopted. Final R3 audit and main adoption remain required after the live-GitHub gate.
