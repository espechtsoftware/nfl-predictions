# Post-correction replay revalidation plan

Date recovered/reconstructed: 2026-08-08

Status: current executable historical-replay queue completed 2026-08-08.
`HANDOFF.md` carries the current execution IDs and supersedes this document on
moment-to-moment status; this file freezes the order and gates.

## Why revalidation restarted

The 27/107 book is illegal under authoritative historical repricing, and the
17/107 replacement omitted historical DST aliases. Later audits also found
all-NFL-week rather than Sunday-main slate construction, pre-opponent salary
aggregation, and an incomplete replay-local DST scorer. No score conclusion
from those universes transfers to the corrected universe.

The first corrected 0/0/0/40 baseline reached 18/107, but its same-image
replica failed exact candidate-world parity in two seasons despite identical
persisted feature values and actual scores. Aggregate score equality is not a
substitute for reproducibility. The replacement deterministic control and its
same-image replica have now passed the full exact gate; arms remain governed
by the frozen sequence and mechanism audits below.

## Frozen execution sequence

1. **Measurement integrity.** The complete candidate, immutable player
   snapshot, world-array, checksum, provenance, and atomic-promotion contracts
   must pass.
2. **Cheap determinism probes.** On one affected 2019 slate and one affected
   2024 slate, run two staging-only executions on distinct Cloud Run jobs from
   one immutable image. Compare every candidate field, player snapshot, and
   roster-aligned world array exactly. A mismatch blocks full panels.
3. **Corrected default baseline.** Run all 107 slates with possession mode,
   `MODEL_ENSEMBLE=3`, `N_CE=0`, `N_EPISTEMIC=0`, `N_GUMBEL=0`, and
   `N_BOOM=40`. Require normal acceptance, then promote it.
4. **Full same-image reproduction.** Repeat the default panel from the same
   immutable digest and code/config/seed identity. Require exact roster-aligned
   candidate-world parity, not merely equal clears or means.
5. **A01 model/market blend deletion.** Replace the adopted 45/55 model/market
   blend with model-only (`BLEND_MODEL_WEIGHT=1.0`) on the same image and fixed
   generation budget. The comparator must prove unchanged market inputs,
   unchanged post-shaping model means, the intended persisted-mean ablation,
   exact reproduction on no-market slates, and complete candidate/player
   mean joins before applying directional score gates.
6. **A02 ensemble deletion.** Run `MODEL_ENSEMBLE=1` against the accepted K=3
   baseline on the same image. The comparator must prove exact non-ensemble
   seed/input identity, the expected member specifications, observed K=3
   disagreement, K=1/K=3 member-prediction movement, and complete
   candidate/player mean joins before applying directional score gates.
   Post-shaping player means are diagnostic rather than directionally gated:
   full-coverage TabPFN marginal shaping intentionally fixes each player's
   marginal while retaining the component simulator's changed rank copula.
   This layer-contract correction changes no scoring threshold.
7. **Only then expand the arm queue.** Revalidate one production mechanism at
   a time under the laws in `post-review6-scoring-improvement-plan.md`. New
   candidate generation or selection work must meet its preregistered earlier
   mechanism/frontier gate. Retrospective tuning on these 107 slates remains
   forbidden.

## Expanded queue decision — A03 salary-floor deletion

After A01/A02, the next open preregistered corrective arm is the §12
salary-floor deletion from `post-review6-scoring-improvement-plan.md`. Its old
26/107 result used the now-invalid 27/107 replay universe and cannot transfer.
Fresh panel `20260808-a03-nofloor-c616390` changed only
`MIN_LINEUP_SALARY=0` on the deterministic generation image and fixed
`0/0/0/40`, K=3 budget.

Before score interpretation, the `salary` mechanism audit must prove the
same upstream player features and non-treatment seeds, a $49k source floor,
a zero treatment floor, and actual sub-$49k candidate generation. Candidate
and selected salary distributions plus selected-roster overlap are reported.
The existing directional gate remains the adoption law. A neutral result does
not authorize a retrospectively chosen intermediate floor; any such dose
would require a new preregistration and independent evidence.

A03 completed from the deterministic image. Acceptance execution
`accept-replay-panel-pwlzs` passed all 107 slates with 17,514 candidates and
50,098 feature snapshots. Salary comparator
`compare-adoption-panel-2k87b` passed: the treatment generated 3,729
sub-$49k candidates and selected 468, while the source generated and selected
none. It tied the source at 11 clears at 194 and 20 oracle clears, fell 26→21
at 187, and lowered mean selected best 173.06→172.43. Season-194 deltas were
`{2019:0, 2021:0, 2022:0, 2023:+1, 2024:0, 2025:-1}`. The disposition is
`unsupported-neutral`; retain $49k and do not open an intermediate dose on
these data.

## Adoption law

An arm must be complete, mechanism-valid, same-image, fixed-budget, and
directionally supported across seasons. The primary portfolio threshold is
194, with 187/200, selected-best distribution, pool oracle, regret, candidate
counts, and per-season effects reported. A headline win cannot repair an
invalid mechanism audit; a headline tie cannot establish reproducibility.

No production configuration changes until the exact default reproduction and
the relevant deletion arm are both recorded in the experiment ledger and
`HANDOFF.md`.

## Arm ledger

| Panel | Headline | Disposition |
|---|---:|---|
| `20260806-universe-baseline-5e4646e` | incomplete | Invalid: nullable rookie crash |
| `20260806-universe-baseline-81b7ff3` | 3 slates | Invalid: incomplete lever provenance |
| `20260806-universe-baseline-525ddb1` | 11 slates | Invalid: adjacent-game DST salary ambiguity |
| `20260807-universe-baseline-124e853` | 17/107 | Invalid: 478 missing historical DST alias rows |
| `20260807-role-belief-v1-7976636-*` | 12/107 control | Invalid: inherited DST omission and pool caps |
| `20260807-universe-baseline-82584d2` | cancelled | Invalid before scoring: all-week game universe |
| `20260807-trusted-b0-ef6d31c` | 16/107 | Superseded correction checkpoint, not an arm control |
| `20260807-livefaithful-b1-bcd8d8d` | 18/107 | Superseded correction checkpoint |
| `20260807-livefaithful-b2-91d596e` | 18/107 | Superseded by instrumentation/reproducibility audit |
| `20260807-a01-noprop-91d596e` | 16/107 | Complete but no current verdict; rerun after exact gate |
| `20260808-livefaithful-b3-ee6f433` | 18/107 | Corrected and promoted, but exact replica failed |
| `20260808-livefaithful-b3r-ee6f433` | 18/107 | Exact comparison failed in 2019/2024 |
| `20260808-a02-ensemble1-ee6f433` | 18/107 | Complete but no verdict; rerun after exact gate |
| `20260808-deterministic-baseline-c616390` | 11/107 | Accepted/promoted deterministic control; full exact replica passed |
| `20260808-deterministic-replica-c616390` | 11/107 | Check accepted; exact parity passed for 107/107 artifacts |
| `20260808-a01-modelonly-c616390` | 11/107 | Mechanism valid; `unsupported-neutral`, model-only not adopted |
| `20260808-a02-ensemble1-c616390` | 16/107 | Mechanism valid; `unsupported-neutral`, K=1 not adopted |
| `20260808-a03-nofloor-c616390` | 11/107 | Mechanism valid; `unsupported-neutral`, salary-floor deletion not adopted |

## Validated repair and arm record

Commit `4f4a633` canonicalizes component means at the shared live/replay
simulator boundary, fingerprints raw and effective inputs, deduplicates the
display-only `player_ids` join that had duplicated 31 old training rows, and
orders DST inputs. Commit `6102845` adds the immutable one-slate probe runner.
The first 2019 probe pair on fully tested image `e61c59c` proved equal raw and
canonical component hashes and identical per-player feature summaries, but
failed exact joint-world parity because equal simulator outcomes were ranked
with an unstable sort inside marginal shaping. Commit `1ab4d32` replaces both
TabPFN and empirical ordinal ranks with a stable world-index tie-break. The
fresh pair (`20260808-det2019-c-c616390` / `...-d-...`) passed exact equality
in comparator execution `compare-exact-replay-zznbf`, including the complete
164x10,000 candidate-world artifact. The independent 2024 pair
(`20260808-det2024-a-c616390` / `...-b-...`) also passed in execution
`compare-exact-replay-mrdnx`, including all 700 player snapshots, 161
candidates and its 161x10,000 artifact. Both cheap gates are closed. None of
these repairs constitutes a scoring adoption. The fresh 107-slate baseline
then passed acceptance and was promoted by `accept-replay-panel-mlbxt` with
11/107 selected and 20/107 pool-oracle clears at 194. Full same-image replica
`20260808-deterministic-replica-c616390` passed check-only acceptance in
`accept-replay-panel-2qfbr` and the exact comparison in
`compare-exact-replay-4j5hz`: 50,098 feature keys and 17,432 candidate keys
had zero mismatch counts, candidate summaries had zero delta, ordering never
moved, and all 107 score-matrix artifacts were bit-identical. The exact gate
is closed. A01 then completed and its `blend` mechanism audit passed in
`compare-adoption-panel-bc4qd`. Model-only tied at 11/107 but reduced mean
selected best by 0.92 and pool oracle by one; neither directional gate passed,
so its disposition is `unsupported-neutral` and it is not adopted. The
generic baseline acceptance job's blend-parity assertion failed by design
because that assertion encodes the deleted 45/55 mean; its other completeness
and candidate-mean checks passed. A02 then passed ordinary acceptance at
16/107. Its first mechanism audit exposed a layer-contract error:
full-coverage TabPFN shaping fixes player marginals while K changes the
joint-world copula, so a changed post-shaping mean is not required. The
corrected audit was fully tested in Cloud Build
`a8ed72ec-d909-447f-881e-3eeaca6b2e7f` and passed in
`compare-adoption-panel-6kf7z` without changing the frozen score gates. K=1
improved aggregate clears, mean and oracle, but was positive in only three
seasons and negative in two. Its disposition is therefore
`unsupported-neutral`, and it is not adopted.

A03 then passed ordinary acceptance and its salary mechanism audit. The
deletion materially widened the salary support (3,729 sub-$49k candidates;
468 selected) but did not improve the primary portfolio result and degraded
the 187 count and mean score. Comparator `compare-adoption-panel-2k87b`
assigned `unsupported-neutral`; the $49k default remains. This closes the
currently executable corrected-universe historical arm queue. Reopening a
closed family requires independent data or a materially different,
preregistered mechanism.
