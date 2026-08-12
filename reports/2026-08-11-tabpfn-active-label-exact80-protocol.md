# TabPFN active-label exact-80 lineup protocol

Frozen on 2026-08-11 CDT after the preregistered final-served gate passed and
before generating, querying or inspecting any active-label candidate or lineup
score.

## Licensed question

Does removing synthetic inactive zero labels from the TabPFN training context
improve the extreme weekly maximum of the exact-80 portfolio after each cache
is independently calibrated using strictly earlier seasons?

Authorization comes only from immutable final-served report
`reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v1/report.json`
(SHA-256
`36982de7412ddd1d77ae92cf7951d42b6a5ea550fe568d2bb279672012c4d2c6`).
The launcher must recheck its passing disposition, gate, cache tables, common
production-multinomial usage law, 52,307 cache rows, exact schedules and
maximum mean drift before any deployment.

## Books and universe

- Unchanged 2019/2021/2022 splice:
  `20260810-lockfix-e80-k1-role12union-8677d21` (`code_sha=8677d21`).
- Current-label control:
  `20260811-lockfix-e80-k1-tabpfn-current-label-v1`.
- Active-only treatment:
  `20260811-lockfix-e80-k1-tabpfn-active-label-v1`.
- Generate both arms only for the 54 canonical Sunday-main slates in
  2023--2025. Splice the exact same 53 source slates into both for the frozen
  107-slate decision.
- Both arms use one immutable post-protocol image and code SHA. Each arm must
  pass a one-week 2024 preflight before its three full-season executions are
  released.

The control is the same current-label generator law as production, but reads
the validated research control cache so the two arms have identical target
keys and cache-generation timing. This is a direct correction A/B, not a
requirement that the recalibrated control reproduce the currently deployed
fixed-factor candidate pool.

## Sole causal differences

Both arms share every input snapshot, model, simulation seed, market blend,
usage law, candidate generator, selector and portfolio size. They differ only
in the validated cache and the walk-forward factor schedule fitted for that
cache in the already-completed score-free final-served gate.

Control cache:
`TABPFN_MARGINAL_TABLE=tabpfn_active_label_control_v1`

Treatment cache:
`TABPFN_MARGINAL_TABLE=tabpfn_active_label_treatment_v1`

Frozen position schedules:

| season | control | treatment |
|---|---|---|
| 2023 | `QB:0.990,RB:0.995,TE:0.940,WR:1.020` | `QB:0.955,RB:0.985,TE:0.975,WR:1.005` |
| 2024 | `QB:0.910,RB:0.990,TE:0.950,WR:1.085` | `QB:0.895,RB:0.980,TE:0.975,WR:1.040` |
| 2025 | `QB:0.935,RB:0.975,TE:0.945,WR:1.090` | `QB:0.920,RB:0.955,TE:0.955,WR:1.030` |

The launcher must take these exact numbers from the hashed report and fail on
any difference. It may not refit them.

## Identical configuration

Both arms use exactly:

- production multinomial within-team usage: blank `GAME_SIM_USAGE` and blank
  `DIRICHLET_K`;
- K=1 component ensemble, 400-round walk-forward models, possession game
  simulation, team factors, 10,000 worlds and the existing fixed seeds;
- CE 0, direct role-belief 12, boom 40, Gumbel 0, replacement slots 12;
- `EPISTEMIC_FAMILY=role_draws`, role seed 7331, and the six exact role fields
  `target_share_last,carry_share_last,snap_share_last,` plus
  `target_share_jump,carry_share_jump,snap_share_jump`;
- shape mix 1.0, model blend 0.45, TabPFN marginals, fitted simulation
  widening and empirical fallback;
- exact 80 distinct legal lineups, default candidate multiple 2, identical
  salary/stack/chalk rules and the accepted line-194 selector.

Production remains on the canonical cache during this experiment. Research
table selection must be persisted in candidate provenance and explicitly
licensed; no cache is overwritten.

## Mechanical gates

1. Revalidate both prerequisite report hashes and the final-served pass before
   launch. Confirm the exact cache tables, schedules, production-multinomial
   law, common seeds/settings and 100% TabPFN coverage.
2. Require three complete season executions per arm, exactly 80 distinct legal
   selected lineups on every slate, complete authoritative labels, one shared
   immutable image/code SHA and check-only candidate acceptance.
3. Control/treatment player snapshots must have exact key, actual, salary,
   point-in-time input, market/model point and pre-simulation ensemble parity.
   The following downstream served-distribution fields may differ:
   `proj`, `proj_tourney`, `own_est`, `proj_p10`, `proj_p50`, `proj_p90`, and
   `proj_std`. The comparator must register exactly this exclusion set.
4. Persisted levers may differ only in `TABPFN_MARGINAL_TABLE` and the exact
   season-specific `SERVED_POSITION_SCALES` above. Both usage fields must be
   absent/default. Every slate must use its season's registered schedule.
5. Shared roster actual scores must match exactly. At least one served player
   distribution and either candidate membership, common-candidate simulated
   mean or selected roster must change, proving the mechanism reached lineup
   construction. Report common/arm-only candidates, selected changes, pool
   oracles, position contributions and every changed week.

A pre-score packaging/mechanical failure licenses only a repair that leaves
the caches, schedules, books, seasons, seeds, generators, selector and decision
law unchanged. Invalid output is not a score result.

## Frozen tail-first decision

For the two full 107-slate books, count selected weekly maxima clearing 240,
230, 220, 210 and 200 in that order. The first nonzero treatment-minus-control
count decides:

- positive: pass; promote the active-only label correction after a separate
  code-reviewed canonical-cache regeneration and production validation;
- negative: reject; retain current-label TabPFN and close this correction;
- all five tied: neutral; retain current-label TabPFN and close this
  correction.

Also report 187/194, mean/median weekly best, pool-oracle thresholds, season
splits, changed weeks and selection overlap. They cannot veto or rescue the
tail-first verdict. No alternative activity definition, seed, context cap,
factor refit, cache blend, factor pooling, selector line, candidate budget,
season exclusion or second historical retry may follow the result.

The subsequent SCHED feature-sync arm inherits active-only labels only if this
exact-80 treatment passes. Otherwise it uses current labels in both arms.
