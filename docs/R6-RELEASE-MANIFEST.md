# R6 release manifest — SOURCE PREPARATION ONLY

**Owner:** [R6 #13](https://github.com/repla73/stateOwl/issues/13)  
**Accepted basis:** `main@e3f5b1224fd3def7ab4933f0f85bfc0a5aa1e192`  
**Governance:** `claw0gang/governance@72b61e2bf9ae526eb9750fa80fce2cf6db977be3`  
**Candidate:** `r6/release` (resolve and freeze an **exact head/tree**; a branch name is not review evidence)  
**Proposed Python package version / future tag:** `0.2.0` / `v0.2.0` (public tag **NOT CREATED**)  
**TypeScript source:** `@stateowl/reader@0.2.0-draft.3`, prerelease, not npm-published  
**Wire protocol:** `stateowl/0.2-draft.3` (still draft); Git receipt: `stateowl.git-receipt/2`  
**Public GitHub release / PyPI / npm / deployment:** **NOT PERFORMED**.

## Frozen normative artifact identities

These files are unchanged from accepted R5. Values are Git **SHA-1 blob OIDs**, **not** SHA-256 checksums; verify with the candidate tree or `git rev-parse <candidate>:<path>`.

| File | Git SHA-1 blob |
| --- | --- |
| `docs/protocol/PROTOCOL.md` | `10af5ed41299a55e016e18f292be3a10594e5c0f` |
| `docs/protocol/git-binding-v2.md` | `5393b26109dd3debc690242e9e6333d43e34a64f` |
| `docs/protocol/schema.json` | `69b842a2d43ce1a3c820147bb2e0864598f10143` |
| `docs/protocol/harness.schema.json` | `ebb99aba08792fc36fc39bd42691d45b3e0bbc7c` |
| `docs/protocol/fixtures.json` | `02af471f4c60454fbd60705a97a98605f743de4d` |
| `docs/protocol/read-cases.json` | `edc1ade2bc8a7a8c6653a17ffde2825377ac3198` |
| `docs/protocol/publish-cases.json` | `d58437db6978ee9b4342b53c3b0891d6d098d944` |
| `docs/protocol/observe-cases.json` | `e18ae7ec7e7689ad5b14ac196d558c5ec6091ea8` |
| `docs/protocol/legacy-v0.1.0.json` | `239017533a80bb0f68b9bcb5ff8d87e6a71c1a67` |
| `benchmarks/results/r2-common-interoperability.json` | `e27b6f39452ead4090695ca06531f705aeb57dc1` |

Runtime source and fixture bytes from R2–R5 are preserved by the R6 **metadata/docs/tests-only** delta; compare the frozen candidate to the accepted basis, do not merely trust this assertion. The repository-held schemas, test cases and reproduction instructions are the *prepared* release artifacts. No wheel/sdist/npm tarball, signature, SBOM, build attestation or registry artifact is claimed without actually producing and verifying it.

## Conditional acceptance/adoption verification

1. Complete a separate non-authoring final audit of the **exact candidate** including import/build smoke and the scoped R6 reproduction gates. PASS binds one exact head and tree, not the branch name.
2. Fresh-read main and accepted candidate; require main still at the previously verified old head. Adopt a single-parent commit whose tree is **exactly** the accepted tree using an exact-old guarded non-force ref advance.
3. Fresh-verify adopted main, sole parent and exact accepted tree; check this manifest's Git blob identities and version coherence (`VERSION`/`pyproject.toml`/`__version__ = 0.2.0`, TypeScript `0.2.0-draft.3`), protocol/receipt identities and [matrix](R6-CAPABILITY-MATRIX.md).
4. **No** public tag, GitHub release, PyPI/npm publication, installation/deployment or infrastructure write is authorized by source preparation, audit PASS or main adoption. Obtain separate explicit founder release authority for any such effect.

If later explicitly approved, the narrow supported public claim is **Python `v0.2.0` for legacy-compatible read/CLI**, with all draft/conditional/recipe exclusions visible. A raw Git tree is not by itself a tested binary distribution.
