# R3 Integration Candidate

Status: R3 final independent audit passed. Accepted R3 subject/tree were cleanly adopted on `main` by commit `4c3ed20e83f29cbd7bfec8e1376146c6a7ef5793`. R4 has not started.

## Subjects

- Governance: `claw0gang/governance@33bb80726de24531d702768498a5cad78755f589`
- Canonical R3 basis/main: `8c0b7baefcc2ba4c48cbf4dfa1964551c1291fa4`
- W1 contract: `e497bcf82ba1483fc1b3406ed8eed348f174b457`
- Accepted Python publisher: `4239e6b75a4e92fc69235c7614285545ea922511`
- Accepted TypeScript publisher: `195568d33a0b7acb36851803619bca6ce5acdb18`
- Integration branch: `r3/integration`
- Accepted R3 subject: `6d7e8fb5d46f0c7ac40d03a2c273a29e6f5dbe7e`
- Accepted R3 tree: `0351aa0b324ecae3fcf4c57448ede90476d04478`
- Clean main adoption commit: `4c3ed20e83f29cbd7bfec8e1376146c6a7ef5793`

The Python and TypeScript R3 implementation/test path sets are byte-identical to the accepted subjects. W1 shared contract/tooling remains exact. Unrelated R2 source remains unchanged.

## Deterministic evidence

Python:

- R3 deterministic: 43/43
- publication conformance: 89/89
- R2 regression: 24/24

TypeScript:

- deterministic: 72/72
- publication conformance: 89/89
- R2 read conformance: 90/90

Cross-language:

- publication semantic equivalence: PASS
- frozen live-payload receipt proof: PASS

## Independent audit

`R3_W3_ROUND2: PASS`

F01-F03 corrections were accepted with no remaining blocking or non-blocking findings.

The live-GitHub receipt-proof provider corrections were also independently audited: PASS.

Final independent acceptance audit: `R3_FINAL: PASS`.

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

Evidence boundary: W4 executed against real local Git. No local machine paths or raw execution logs are canonicalized here.

## W6 live GitHub qualification

Result: PASS.

Disposable repository: `repla73/stateowl-r3-qualification`

Namespace: `refs/heads/stateowl-r3-qualification`

Accepted chain:

- A baseline: `c965c47aa7d234cbe08c77d0c533859b65ec0895`
- B: `16a29935ee2ea2342c91faba5e37bc4c70932d94` — Python normal guarded publication
- C: `80a7dfb8d2037cb3f6cc1bd7f2df74a1186c2e40` — TypeScript caller-visible success discarded, recovered through zero-admission reconciliation
- D: `a7650e156e4bbfff6b1a6a5891845ab2d518b3b2` — divergent Python/TypeScript race from C; Python won, exactly one guarded mutation succeeded, loser returned conflict
- E: `20935945e5d85fc73adec7ca800509759c2d509d` — identical Python/TypeScript race from D; TypeScript won the guarded mutation, both implementations resolved E, exactly one admission occurred

Accepted transitions: 4/4. E is the final qualification head.

W6 verified:

- baseline freshly verified: PASS
- Python A→B: PASS
- TypeScript B→C lost-response reconciliation: PASS
- divergent cross-language race: PASS
- identical cross-language race: PASS
- later-successor reconciliation: PASS
- four accepted transitions exactly: PASS
- every admitted commit has exactly one parent: PASS
- exact expected-old guarded publication: PASS
- stale writer does not mutate: PASS
- complete tree preservation: PASS
- truncated tree not accepted: PASS
- `100755` preservation: PASS
- new files `100644`: PASS
- returned commit identities: PASS
- zero-admission reconciliation where required: PASS

Successor reconciliation after E used committed snapshot D with observed head E and performed zero admissions.

## Live receipt behavior

For all four admitted receipts, GitHub's JSON commit `message` omitted the terminal LF. The raw Git commit objects preserved the exact required receipt bytes.

Both corrected providers accept the normalized API representation only because the complete raw commit OID uniquely proves the exact receipt bytes and raw actor-timezone reconstruction.

- raw terminal LF preserved: PASS
- Python live verification: PASS
- TypeScript live verification: PASS
- malformed raw-receipt rejection rules: unchanged
- blind LF reconstruction: no
- blind timezone acceptance: no
- exact full commit OID used as proof: yes

GitHub JSON `message` is not treated as byte-exact receipt evidence.

## Governance / G5 evidence boundary

Executed W6 proof established that the four stateOwl transitions themselves:

- used exact expected-old guarded admission;
- each admitted one sole-parent commit;
- did not force, merge, reset, or overwrite stale state.

Repository-wide exclusive single-step writer confinement remained a trusted qualification-environment assumption. It was not inferred from Git history and is not claimed as a general GitHub repository guarantee.

## Status

- W6 live GitHub qualification: PASS
- R3 implementation/qualification evidence complete: yes
- final independent R3 audit: `R3_FINAL: PASS`
- accepted R3 subject: `6d7e8fb5d46f0c7ac40d03a2c273a29e6f5dbe7e`
- accepted R3 tree: `0351aa0b324ecae3fcf4c57448ede90476d04478`
- clean main adoption commit: `4c3ed20e83f29cbd7bfec8e1376146c6a7ef5793`
- R3 adopted on `main`: yes
- R4 started: no
