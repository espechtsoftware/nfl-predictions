# TD-ledger final-served dependence protocol

Frozen 2026-08-13 CDT after the valid G2 failure and the independent
mechanism reconciliation, but before the current-incumbent TD-ledger treatment
is reconstructed or any treatment metric is computed. This is one adaptive,
retrospective, score-free evaluation. It reads player outcomes only to grade
the joint distribution; it must not query, generate, select, or score a lineup.

## Immutable terminal identity

Bind the run to:

- active cache `tabpfn_active_label_treatment_v2`;
- finite Dirichlet usage `K=28.154043586960896`;
- evaluation panel `20260812-pitclean-e80-selected-tabpfn-active-v2` and
  historical splice `20260811-pitclean-e80-k1-role12union-a12ab31`;
- the exact G0 v2 and G1 v3 reports and manifests;
- 45/55 model/market blend, 10,000 worlds, seed 0, and the accepted
  walk-forward 2023--2025 served-position schedule; and
- an immutable full-test image digest and code commit.

The control must reproduce the frozen G0/G1 populations and every registered
control score to absolute tolerance `1e-12` before the treatment is valid.

## Sole treatment

The control is the final-served incumbent. The treatment changes exactly one
simulator environment value: `TD_LEDGER=1`. It uses the existing production
ledger implementation and fixed-share multinomial TD allocation
(`td_alloc_k=None`). Do not tune or change TD allocation concentration, game
factor sigma, usage K, component means, marginal shaping, market blend,
position scales, seeds, cache, support, or thresholds.

The ledger is applied inside the component simulator, before the accepted
TabPFN marginal rank map. It draws one passing-TD event total per `(game,
team)` and assigns that same total to passer and catcher sides, with existing
other buckets reconciling unmatched TD means. This is a distinct event-ledger
mechanism, not a G2 link-family or theta retune.

## Population and scores

Use exactly the held-out G0/G1 2023--2025 population: active QB/RB/WR/TE rows
with final-served mean at least 4.0, exactly 7,848 rows and 54 Sunday-main
slates if the terminal identity is unchanged. Each player's boom threshold is
its unchanged final-served q90. Recompute:

- all nine G0 cells and supported-cell absolute-log-error sum;
- every G1 relationship, its fixed-weight supported-cell absolute-log-error
  sum, joint-q90 Brier and variogram p=0.5;
- QB-WR, QB-TE, WR-WR and RB-RB broad errors; and
- paired whole-slate bootstrap intervals for the aggregate proper-score
  changes, 2,000 replicates with seed 1703.

Report the proper scores and the four named broad relationships separately by
held-out season. Season results and bootstrap intervals are disclosures, not
additional vetoes. No lineup or contest outcome is permitted.

## Invariants

The treatment must satisfy all of the following:

1. exact player key, outcome, team, opponent and game alignment with control;
2. exact sorted final-served draw multiset for every player;
3. finite output and maximum player-mean drift at most `1e-10`;
4. an exact deterministic reproduction from a second treatment replay;
5. at least one eligible row and world rank changes; and
6. terminal cache, schedule, usage, blend, seeds and all non-TD simulation
   settings are identical, with `TD_LEDGER=1` the only intervention.

## Frozen gate

Let error mean absolute `log(simulated/realized)`. The ledger passes only if:

1. all invariants and exact G0/G1 control reproduction pass;
2. aggregate joint-q90 Brier strictly improves;
3. aggregate variogram p=0.5 strictly improves;
4. QB-WR broad error strictly improves;
5. the supported G0 error sum strictly improves;
6. the fixed-weight supported G1 error sum strictly improves;
7. WR-WR broad error does not increase by more than `1e-12`; and
8. none of QB-TE broad error, RB-RB broad error, G0 multiplicity `>=2`
   error, or G0 multiplicity `>=3` error increases by more than
   `log(1.05)`.

The `log(1.05)` guard is a fixed five-percent multiplicative-error
materiality allowance selected before treatment output. It is not a target or
a tuning parameter. Unsupported or nonfinite required cells make the run
invalid/inconclusive rather than a pass.

Valid dispositions are `td-ledger-dependence-gate-passes` and
`td-ledger-dependence-gate-fails`; an invariant/support failure is
`td-ledger-invalid-or-inconclusive`.

## Consequences

A pass licenses one separately frozen, same-image, exact-80 control/treatment
comparison under the current incumbent. It does not itself change production.
Because this mechanism was chosen after reviewing G0/G1/G2 on the same
2023--2025 outcomes, any later adoption must explicitly retain the
adaptive/retrospective overfitting risk and run as a prospective 2026 shadow.

A valid failure closes this TD-ledger mechanism on the historical panel. Do
not tune `td_alloc_k`, game sigma, usage K, or silently add passing-yard or
reception ledgers. Do not compose the ledger with G2's TE factor. Any such
mechanism requires a new independent rationale and a separately frozen
protocol before its treatment output exists.
