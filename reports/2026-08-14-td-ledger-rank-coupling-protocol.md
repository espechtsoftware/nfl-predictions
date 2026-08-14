# TD-ledger rank-coupling terminal repair protocol

Frozen 2026-08-14 CDT after both invalid TD-ledger executions and the
pre-forensic exhaustion review, but before implementing or computing this
treatment. This is one final adaptive, retrospective, score-free dependence
repair. It may read player outcomes only to grade the frozen joint-distribution
scores; it must not generate, select, query or score any lineup.

## Why one repair remains licensed

TD-ledger v1 failed exact marginal preservation because a shared float32 mean
reduction was order-sensitive. The general float64 repair made v2 preserve
every sorted marginal exactly, with maximum mean drift `7.11e-15`, but changed
the incumbent control's 13 frozen G1 variograms by `2.8e-10` to `1.28e-8` and
therefore failed the registered `1e-12` control-reproduction invariant. Both
runs were invalid/inconclusive, not scientific failures. Their directional
metrics motivated this repair but are not reused as its result.

The shared production numeric path has since been restored byte-for-byte. The
repair below isolates the ledger's rank dependence from every marginal and
numeric transform. It is the terminal retry specified before output in
`reports/2026-08-13-incumbent-numeric-path-restoration.md`.

## Immutable identity

The launch manifest must pin:

- an immutable full-test image digest and full code SHA;
- active cache `tabpfn_active_label_treatment_v2`;
- finite Dirichlet usage `K=28.154043586960896`;
- evaluation panel `20260812-pitclean-e80-selected-tabpfn-active-v2` and
  historical splice `20260811-pitclean-e80-k1-role12union-a12ab31`;
- exact G0 v2 and G1 v3 report/manifest hashes;
- the accepted walk-forward 2023--2025 served-position schedule;
- 45/55 model/market blend, 10,000 worlds and seed 0; and
- paired whole-slate bootstrap of 2,000 replicates with seed 1703.

The unchanged control must reproduce every frozen G0/G1 population and score
to the original absolute tolerance `1e-12`. Otherwise the run is invalid and
may not be repaired or reinterpreted again on these outcomes.

## Sole treatment and tie rule

For each aligned player:

1. obtain the unchanged incumbent final-served control draws;
2. independently obtain a rank-source draw row from the existing simulator
   with only `TD_LEDGER=1` (`td_alloc_k=None`);
3. compute the rank-source world order with stable ascending `numpy.argsort`
   (`kind="stable"`), so ties retain original world-index order;
4. stable-sort that player's unchanged control values; and
5. place those unchanged sorted values into the rank-source world order.

No TD-ledger value enters the treatment—only its within-player world order.
Every treatment row is therefore an exact permutation of its own incumbent
row. Do not blend ranks, tune weights, jitter ties, change allocation, alter a
shared transform, change seeds or add another factor. A second independently
generated TD-ledger rank source must reproduce the treatment bit-for-bit.

## Population, scores and invariants

Use exactly the prior 7,848-row, 54-slate held-out 2023--2025 G0/G1 population:
active QB/RB/WR/TE rows with final-served mean at least 4.0. Each player's boom
threshold remains its unchanged control final-served q90. Recompute all nine G0
cells; every G1 relationship; aggregate joint-q90 Brier and p=0.5 variogram;
supported G0/G1 absolute-log-error sums; QB-WR, QB-TE, WR-WR and RB-RB broad
errors; season disclosures; and the registered paired bootstrap.

The treatment is valid only if:

1. player keys, outcomes, team, opponent and game alignment are exact;
2. the control reproduces frozen G0/G1 within `1e-12`;
3. every treatment sorted draw row is bit-exact to its control row;
4. output is finite and maximum float64 player-mean drift is at most `1e-10`;
5. the independently repeated rank source yields bit-exact treatment output;
6. at least one eligible player row and world cell changes rank; and
7. cache, schedule, usage, blend, seeds and every non-ledger setting match.

## Frozen scientific gate

Conditional on all invariants, the repair passes only if all seven original
scientific requirements hold:

1. aggregate joint-q90 Brier strictly improves;
2. aggregate variogram p=0.5 strictly improves;
3. QB-WR broad absolute-log error strictly improves;
4. supported G0 absolute-log-error sum strictly improves;
5. fixed-weight supported G1 absolute-log-error sum strictly improves;
6. WR-WR broad error does not increase by more than `1e-12`; and
7. none of QB-TE, RB-RB, G0 multiplicity `>=2`, or G0 multiplicity `>=3`
   error increases by more than `log(1.05)`.

Valid dispositions are `td-ledger-rank-coupling-gate-passes`,
`td-ledger-rank-coupling-gate-fails` and
`td-ledger-rank-coupling-invalid-or-inconclusive`. No tolerance or result may
be changed after treatment output.

## Consequences

A valid pass licenses exactly one separately frozen exact-80 control/treatment
comparison under the current finite-K incumbent. It does not authorize a
production change, K=1 transfer, blend, parameter tuning, or composition with
another dependence mechanism. Any exact-80 pass remains adaptive historical
evidence and requires a labeled prospective 2026 shadow before production use.

A valid failure closes the TD-ledger/rank-coupling mechanism on the historical
panel. An invalid result closes it as unadjudicated; there is no fourth repair
on these outcomes. In every branch, the result and the remaining Odds API/SIS
acquisition gaps must enter the terminal arm ledger and prospective opportunity
register before the final forensic freeze.
