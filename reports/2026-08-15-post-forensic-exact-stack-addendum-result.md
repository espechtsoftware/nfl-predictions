# Post-forensic exact-stack construction addendum result

Date: 2026-08-15 06:49 CDT  
Protocol: `20260815-post-forensic-exact-stack-construction-v1`  
Scope: immutable repair4 `phase-s-cbwu-54` corpus  
Disposition: **corrective/descriptive result; no historical arm promotion**

## Bottom line

Correcting the hindsight H/P and recourse solvers from QB+1/no bring-back to
the production QB+2/one-bring-back contract reduces the measured construction
gap, but does not change the diagnosis: candidate composition remains by far
the dominant failed layer.

The corrected mean gaps are:

| gap | published loose oracle | corrected exact-stack oracle |
|---|---:|---:|
| player support H-P | 3.583 | 4.057 |
| construction P-C | 78.994 | 68.914 |
| selection C-S | 5.007 | 5.007 |

At 210 points, construction is still the first failed layer on 44/54 slates,
player support on 1, selection on 0, and no layer on 9. The production
candidate and selected books never changed, so the adopted exact-80 baseline
also remains unchanged.

## Durable execution receipt

- Replacement full-suite build:
  `5c3b9d72-fd8e-4306-bd17-01a6f4a3c911`
- Build result: 1,428 passed, 2 skipped, 5 warnings in 1,126.62 seconds
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:64083d989d70e341409a211416d894245d675249395de891321e11696005dc0a`
- Analysis code: `bb7453e7213627ad446fec20ed92c6550ec0e071`
- Execution: `post-forensic-stack-addendum-v1-smrps`
- Execution result: one succeeded task, zero retries, completed
  `2026-08-15T11:48:58.072232Z` after 7m21.07s
- Manifest SHA-256:
  `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`
- Create-only GCS object generation: `1786794534795445`
- Result SHA-256:
  `1d9e6b1f8d4e6174ae4aa717acf62fe657f0f3fbfd9271289a36b4a58664e7f3`
- Result URI:
  `gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-stack-construction-v1/result.json`

The result identifies all 54 required slates, the exact repair4 manifest,
full code SHA, immutable image digest, three source tables, expected 80 entries,
and production stack contract. The run independently reproduced the published
loose-P result before computing the correction.

## Corrected H/P/C/S tail grid

| layer | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 |
|---|---:|---:|---:|---:|---:|---:|---:|
| exact H | 54 | 53 | 53 | 51 | 49 | 45 | 40 |
| exact P | 53 | 52 | 50 | 50 | 47 | 43 | 39 |
| candidate C | 22 | 11 | 8 | 6 | 3 | 1 | 0 |
| selected S | 17 | 8 | 7 | 6 | 3 | 1 | 0 |

The selected baseline remains mean weekly maximum 176.063 with
`17/8/7/6/3/1/0` at 187/194/200/210/220/230/240. This correction changes no
lineup, production policy, or historical adoption.

## What the malformed oracle overstated

The published P violated QB+2 on 49 slates, the bring-back rule on 36, and at
least one on 51. Moving through the four definition cells changes mean P from
260.064 for QB+1/no bring-back to 249.984 for QB+2/bring-back. Corrected P tail
counts are lower by `0/-1/-2/0/-3/-4/-5` versus the loose P at
187/194/200/210/220/230/240.

That correction reduces the mean P-C gap by 10.080 points. It does not make
player support or selection the binding problem: exact P still reaches 210 on
50/54 slates while the generated pool and selected book reach it on only 6.

## Candidate-composition diagnosis

Exact P is not a near miss from ordinary generated rosters. Its closest
candidate differs by a mean 5.17 player swaps (median 5): 1 slate needs one
swap, 11 need four, 19 need five, 22 need six, and 1 needs seven. Of 486
player-slots represented across the 54 P rosters, 124 use a player appearing
in fewer than five generated candidates.

Relative to each slate's candidate pool, exact P tends to:

- span more games: 5.315 versus a 4.954 candidate mean;
- use a slightly smaller largest same-team block: 3.056 versus 3.207;
- spend more at WR: $20,393 versus $19,225; and
- spend less at QB, RB, TE and DST, most notably QB ($6,083 versus $6,485).

These are outcome-viewed descriptive contrasts, not generator weights. They
support a separately frozen, fixed-realized-candidate-budget prospective
generator that targets broader game spread and more WR allocation; they do
not license fitting those amounts to historical scores.

## Salary-floor correction

Removing the $49,000 floor from exact H/P improves 19/54 slates by mean 0.856
points (median zero, maximum 10.70) and creates one new >=230 slate, with no
new crossing at any other registered threshold. This replaces the prior claim
of zero new threshold slates for the oracle.

The actual no-floor candidate arm remains independently rejected because it
created no new tail-threshold weeks. Production therefore keeps the floor.
The corrected oracle leaves a narrowly targeted low-salary construction
hypothesis open for prospective fixed-budget work; it does not justify a broad
no-floor adoption or a retrospective rerun.

## Corrected perfect-information recourse ceiling

Under the same production stack contract, the hindsight recourse ceiling
improves 53/54 slates by mean 37.807 points, median 37.23 and maximum 100.76.
The perfect-information book reaches
`45/41/35/30/23/13/9` at 187/194/200/210/220/230/240, creating
`28/33/28/24/20/12/9` new threshold slates over the incumbent.

This supersedes the published mean +42.62 and its tail counts, but preserves
the substantive conclusion: recourse has a large feasibility ceiling. It
still uses realized late outcomes and is not an executable estimate. The
separate point-in-time scorer and frozen realistic-recourse policy are needed
to size what was actually knowable.

The corrected hindsight final roster is closer to exact P than its source
entry on 41 slates and closer than the selected weekly best on 27. Its mean
distance from P is still 5.15 player swaps, so recourse and construction
partially overlap but are not interchangeable and must not be added as
independent opportunity sizes.

## Scientific disposition

1. Keep `classic-k1-role12-boom40-poscal-cbwu-v4` unchanged.
2. Keep selector sweeps deprioritized; corrected C-S is still only 5.007 and
   selection is never the first failed layer at 210+.
3. Proceed with the already licensed realistic point-in-time recourse sizing
   analysis, strictly as descriptive/prospective evidence.
4. Freeze a separate fixed-budget candidate-reallocation shadow informed by
   the structural direction, without fitting its weights to these outcomes.
5. Preserve the production salary floor and the rejection of the actual broad
   no-floor arm; do not overstate the oracle-level closure.
6. Do not use this outcome-viewed addendum to promote or relax a historical
   arm.
