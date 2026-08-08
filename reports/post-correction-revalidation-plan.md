# Post-correction replay revalidation plan

Date recovered/reconstructed: 2026-08-08

Status: active protocol. `HANDOFF.md` carries the current execution IDs and
supersedes this document on moment-to-moment status; this file freezes the
order and gates.

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
   disagreement, K=1/K=3 model-mean movement, and complete candidate/player
   mean joins before applying directional score gates.
7. **Only then expand the arm queue.** Revalidate one production mechanism at
   a time under the laws in `post-review6-scoring-improvement-plan.md`. New
   candidate generation or selection work must meet its preregistered earlier
   mechanism/frontier gate. Retrospective tuning on these 107 slates remains
   forbidden.

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

## Current repair under validation

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
is closed and A01 is the next allowed arm.
