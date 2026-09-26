# Week 4: make the leverage batch fast without changing it (task for the laptop agent)

**Written** 2026-09-26 by production for the laptop agent, which owns the lab code and runs Week 4.
**Operator decision (2026-09-26):** do this for Week 4 **only if the end result is unchanged**. The goal is speed, not scoring.
A version that yields a different leverage lineup sequence is not adopted. It goes back to the operator as a separate
generator change.

## Why

The Saturday D12800 build spends about 10 of its ~10.3 hours in the leverage batch:
`generate_candidates` → `optimize_many(pool, n_lineups=2560, objective_col="proj_tourney", max_overlap=7)`
(`src/nfl2/pipeline.py:463`, `src/nfl2/core/lineup.py:502`).

- Each lineup is the best lineup that shares at most 7 players with **every** earlier one. Each accepted lineup adds one
  `<= 7` cut (`lineup.py:264`), and every solve rebuilds the whole model, writes an MPS and starts a fresh single-threaded CBC.
- Solve time grows as about k^1.5, so the batch costs about n^2.5. That is 5 s per lineup early and ~30 s near lineup 2,500.
  On the 16-core workstation one core is busy and fifteen are idle.
- D6400 (1,280 lev) took 2.11 h on 2026-09-26: the first lev ledger record carries the batch time, 7,593 s.
- Week 4 runs on the laptop. Its speed on the unchanged code has not been measured.

The batch is sequential by definition (lineup k depends on lineups 1..k-1), so the fix makes each solve cheaper. It does not
parallelise the sequence.

## The change: lazy overlap cuts (default off, env `LEV_LAZY_CUTS=1`)

In `optimize_many`, do not add all k-1 cuts to solve k. Keep an **active** cut set that persists across the batch:

1. Solve with the base constraints plus the active cuts only.
2. Check the solution against **all** earlier lineups (set intersection > `max_overlap`).
3. If it violates none, accept it. Otherwise add the violated cuts to the active set and re-solve.
4. After accepting, append the lineup to `banned` as today. Whether to add its own cut to the active set eagerly is your
   call: measure both.

**Why the result is the same:** the lazy problem is a relaxation of the full one. A relaxation optimum that satisfies every
cut is therefore optimal for the full problem. Two things can still differ, and the test below exists to catch them:
- **tied optima:** CBC may return a different lineup of equal objective;
- **CBC's gap tolerance:** with `PULP_CBC_CMD(msg=0)` CBC may stop at a small nonzero gap, and the two problems may stop at
  different near-optimal lineups. If this shows up, try `gapRel=0` on **both** paths and report it. It would be a change to
  the reference path too, so it needs the operator's call.

**Fail-closed verifier (always on when the switch is on):** after the batch, check every pair of lev lineups for overlap
`<= max_overlap` (a 0/1 incidence matrix product; 2,560² is instant). Any violation stops the run. No silent fallback to the
old path mid-run.

**Out of scope for Week 4** (each changes the output, or is the operator's call):
- splitting the batch across processes;
- multi-threaded CBC (`threads>1` may be nondeterministic);
- a different solver;
- changing the lev dose.

Solver threads may be tried later as a second step, only if repeated runs are byte-identical.

## Acceptance test (fixed now, before any run)

**Reference artifacts:** production sends these on Monday through the private channel, with the run frame.
`frame.parquet` carries licensed columns and **never** goes into this public repo.
- `20260926T153523899333Z-65305f5`: the Week-3 D6400, 1,280 lev;
- `20260926T153408285093Z-65305f5`: the Week-3 D12800, 2,560 lev, finishing about 20:30 CT tonight.

Each run dir carries `frame.parquet`, `receipt.json` (the env) and `exposure_ledger.json`, which lists every attempt in visit
order with `family`, `status` and `lineup` hash.

**Code:** the lab commit goes on top of `65305f5` (the pinned GO commit), not origin/main.

1. **Harness control.** Rebuild the pool with `_pool(frame)` and the env with `{**PRODUCTION_ENV, **receipt env}` at `65305f5`.
   Run the **unchanged** path for the first 200 lev lineups of the D6400 frame. The hashes must equal the ledger's first 200
   `family == "lev"` records, in order. This proves the harness rebuilds the real inputs. If it fails, fix the harness; the
   comparison below means nothing until it passes.
2. **Exact match.** Run the lazy path for the full batch on both frames. **PASS** requires all of the following:
   - the ordered lev hash sequence equals the ledger's (1,280/1,280 and 2,560/2,560, same order);
   - every status is `new`;
   - the verifier finds no violations.
3. **Record:**
   - wall time for each frame, lazy path;
   - the laptop's `nproc`;
   - the unchanged path's time for the first 500 lev on the laptop, so a Week-4 fallback can be scheduled.

**On any mismatch:** do not adopt, and do not tune until it matches. Report to the operator:
- the first divergent index;
- both lineups' `proj_tourney` sums;
- whether each is feasible under the other path's cuts;
- whether a gap or a tie explains it.

## Wiring for Week 4 (only after PASS)

1. Lab commit with the switch and its tests:
   - a small synthetic pool with the lazy sequence equal to the full-cut sequence;
   - the verifier tripped by a planted violation, as a mutation check.
2. Set `LEV_LAZY_CUTS=1` on the live path through `week_env.sh`. Move the pin: `EXPECT_SHA`, `LIVE_PIN_SHA` in
   `tests/test_week_env_defaults.py`, and the `week_env.sh` default.
3. Run the plain `--smoke` locally (no upload) and one D6400 Saturday-shape rehearsal on the laptop, then the receipt check.
4. **Freeze by Thu 10-01 18:00 CT.** If it is not frozen by then, Week 4 runs the unchanged code. In that case, use the
   step-3 timing to decide the start time, and tell the operator by Wed 09-30 if D12800 would not finish before Sunday.

Rollback on the day: `LEV_LAZY_CUTS=0` on the arm line gives the unchanged path.
