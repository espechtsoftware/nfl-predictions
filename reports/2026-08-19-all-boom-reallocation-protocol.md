# All-boom reallocation arm — protocol (operator-directed 2026-08-19)

**Protocol ID:** `20260819-all-boom-reallocation-c-v1`
**Status:** operator directed "let's try it either way" (independent of the
ATLAS C verdict); frozen at implementation completion, SHA pinned in the
runner. Queued strictly behind the ATLAS C finisher (one active
historical-score experiment at a time).
**Class:** fixed-budget generation-composition arm, C-endpoint-first (the
CBWU-OI pattern); one dose, one shot, no retry after a valid verdict.

## Estimand

On the 54-slate 2023–25 corpus, at the incumbent per-seed candidate
budget: does replacing the ENTIRE lev batch with boom-family depth
(`CAND_MULT=0`, `N_BOOM=200`, `BOOM_UNIQUE_FILL=1`; all registered
levers; every other family and the incumbent slate-total world ordering
unchanged) improve the realized candidate ceiling C? Motivation, recorded
before this arm: the 2026-08-19 family scorecard (boom owns 35/54 slate
bests from 15.8% of the pool; lev is 63.3% with zero 210+ candidates
ever), the lev-deletion precedent (≈−1 clear, old universe, budget not
reallocated), and the CAND_MULT=4 closure (raw lev scaling hurt 210+).
Predeclared prior: GENUINELY UNCERTAIN — deep worlds are weaker under the
incumbent ranking and lev's breadth may carry unmeasured pool support;
the arm is run to measure, not to confirm.

## Arms

- **Control:** the registered native pools themselves (five seed panels ×
  54 slates; 67,951 rows with actual scores) — no regeneration, no
  reproduction gate needed: the natives are the pinned truth.
- **Treatment:** per seed panel, regenerate from the SAME pinned
  money-world artifacts and snapshots with exactly three lever changes
  (`CAND_MULT=0`, `N_BOOM=200`, `BOOM_UNIQUE_FILL=1`); role natives
  injected verbatim at their registered positions (arm-invariant, the
  Amendment-2/4 mechanism); all-controls-first process ordering is moot
  (single arm per process). Acquisition-record env validation applies to
  every key EXCEPT the three predeclared treatment levers, whose exact
  treatment values are separately asserted.

## Budget parity

Target = the native count per seed. Adaptive families (qbvar/game/dark)
may deliver slightly different unique counts against the changed pool:
the treatment pool is truncated to the native count in REVERSE generation
order (deterministic); a shortfall greater than 5 per seed fails closed;
realized per-family counts are recorded per seed.

## Endpoints and gates

1. **Mechanism gate (outcome-blind, `--smoke`):** exact treatment budget
   after truncation; boom uniques = 200 per seed (or disclosed shortfall
   with worlds exhausted); role injection count parity; lever receipt
   shows exactly the three changed keys.
2. **Primary (one outcome read per slate):** paired realized C
   (treatment pool best vs native pool best, pooled across seeds),
   reported with the full 240→187 grid, discordant slates, and the
   paired weekly-max co-primary block
   (`research/paired_max_stats.paired_weekly_max_report`).
3. **No selection endpoint in this arm.** S requires its own frozen
   follow-up only if C improves; a C null closes the reallocation at
   this dose permanently (no 120/80 retry).
4. Interpretation is joint with the N1b winner world-assignment census
   (where winners' generating worlds rank) and the ATLAS C verdict
   (whether a better ordering would change the depth economics); neither
   can amend this arm after its outcome is read.

## Infrastructure

`scripts/run_all_boom_reallocation_c.py` (per-slate cell, `--smoke`
outcome-blind mode, create-only GCS receipts under the run prefix),
reusing the reality-tested ATLAS C machinery (slate reconstruction,
artifact download, role injection, env construction). 54 cells, 4 CPU /
16 GiB, zero retries, single reused Cloud Run job with per-execution
`--args` overrides (JobsPerProject quota), real-path canary first.
