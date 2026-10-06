# R3 Integration Candidate

Status: assembled integration candidate only. R3 is not complete or adopted.

## Subjects

- Governance: `claw0gang/governance@33bb80726de24531d702768498a5cad78755f589`
- Canonical R3 basis/main: `8c0b7baefcc2ba4c48cbf4dfa1964551c1291fa4`
- W1 contract: `e497bcf82ba1483fc1b3406ed8eed348f174b457`
- Accepted Python publisher: `4239e6b75a4e92fc69235c7614285545ea922511`
- Accepted TypeScript publisher: `195568d33a0b7acb36851803619bca6ce5acdb18`
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

## W6 receipt-proof correction

The initial W6 Transition 1 stopped before guarded ref admission. Candidate `30fded3c53b0927c1888ecc6af017deb75589297` was created as an unadmitted object only; GraphQL ref calls were 0 and accepted transitions remain 0/4.

Live evidence showed the raw Git receipt bytes were correct, including the required terminal LF. GitHub's JSON commit representation omitted that terminal LF from `message` and normalized actor timestamps to UTC, while the raw Git actor offsets were `+0300`. This was a provider representation compatibility defect, not a protocol defect or an unsafe publication.

The corrected Python and TypeScript provider subjects above were independently audited: PASS. The normalized GitHub message/time representation is not used as raw proof; exact full commit OID reconstruction supplies the proof. The terminal-LF protocol rule remains unchanged, malformed raw receipts remain rejected, reconciliation uses the same proof, and no Git CLI/runtime dependency was introduced.

Correction qualification:

- Python R3 deterministic: 43/43
- Python publication black-box: 89/89 applicable
- Python R2 regression: 24/24 applicable
- Python exact frozen W6 replay: PASS
- Python hypothetical reconciliation replay: PASS
- TypeScript deterministic: 72/72
- TypeScript publication black-box: 89/89
- TypeScript R2 read conformance: 90/90
- TypeScript exact frozen W6 replay: PASS
- Cross-language frozen W6 receipt proof: PASS

Disposable W6 baseline A remains `git:sha1:c965c47aa7d234cbe08c77d0c533859b65ec0895`. It is still current. The failed initial attempt is not an accepted transition. W6 must resume from baseline A.

## Remaining gate

W6 disposable live-GitHub qualification remains required and must resume from baseline A. R3 remains incomplete until live W6 passes. Final R3 audit and main adoption remain required afterward.
