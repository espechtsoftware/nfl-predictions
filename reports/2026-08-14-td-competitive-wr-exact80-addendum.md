# TD competitive-WR allocation five-seed exact-80 addendum

Frozen 2026-08-14 CDT while the replacement full-test image was nonterminal,
before Stage R or Stage T launched and before any competitive-WR lineup was
generated, selected or scored. This makes the sole conditional scoring license
in `2026-08-14-td-competitive-wr-allocation-protocol.md` executable without a
post-result choice.

## Conditional license and question

Run this experiment only if Stage R has disposition
`td-competitive-wr-reference-passes`, Stage T has disposition
`td-competitive-wr-allocation-gate-passes`, and every registered invariant,
negative control and reference-attestation check passes. Otherwise this
addendum expires without a lineup run.

The sole question is whether changing only eligible WR world order by the
frozen centered competitive TD priority improves the tail of the best realized
score among exactly 80 selected lineups per slate under the accepted finite-K
incumbent.

This is one paired experiment over five pre-existing Monte Carlo seed books,
not five adoption attempts. The 54 slates, not the 270 seed-slate observations,
remain the independent outcome units.

## Frozen common stack

Both arms use the exact finite-K incumbent represented by
`20260812-pitclean-e80-selected-tabpfn-active-v2`:

- seasons 2023--2025 and all 54 main slates;
- active-label cache `tabpfn_active_label_treatment_v2`;
- 45/55 model/market blend and the accepted served-position schedules:
  - 2023: `QB:0.965,RB:0.99,TE:0.945,WR:1.03`;
  - 2024: `QB:0.905,RB:0.97,TE:0.95,WR:1.06`;
  - 2025: `QB:0.925,RB:0.96,TE:0.94,WR:1.04`;
- possession simulation with finite Dirichlet
  `K=28.154043586960896`;
- direct role belief using exactly
  `target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump`;
- 12 role candidates, 40 boom candidates, no CE or Gumbel candidates;
- 10,000 worlds, 194-world coverage, $49,000 salary floor and exactly 80
  selected entries per slate; and
- unchanged point-in-time snapshots, solvers, candidate budgets, selector,
  tiebreakers and actual-score labels.

Do not enable SIS ASOE, any SIS marginal cache, pass-tail, Route dependence,
G2/G3, the named future TE-only mechanism, production K=1, or any other
dependence/marginal treatment in either arm.

## Fixed seeds and panels

Use the five seed pairs frozen before the incumbent seed audit:

| book | baseline/simulator seed | role-belief seed |
|---|---:|---:|
| R0 | 0 | 7,331 |
| R1 | 1,137,260,708 | 2,690,847,602 |
| R2 | 2,875,959,182 | 1,630,284,992 |
| R3 | 253,722,715 | 3,374,646,876 |
| R4 | 1,643,280,042 | 3,977,633,467 |

Panel IDs are
`20260814-td-comp-wr-control-r{0..4}-v1` and
`20260814-td-comp-wr-treatment-r{0..4}-v1`. Within each book both arms use
identical seeds. No replacement, retry seed or favorable subset is allowed.

## Sole arm difference

Control uses unchanged incumbent final-served draws. Treatment applies the
exact Stage T law after all common marginal shaping, market blending and
served-position scaling:

1. independently produce the aligned rank-source book with only
   `TD_LEDGER=1` and the same baseline seed;
2. identify outcome-blind supported `(season,week,game_id,team)` groups with
   exactly one QB and at least two WRs, using served mean at least 4.0;
3. compute stable control-QB percentiles and stable TD-source WR percentiles;
4. assign each eligible WR the exact priority
   `QB_control_percentile + (WR_TD_percentile - team_WR_mean_percentile)`; and
5. stably permute only that WR's unchanged control marginal into the priority
   world order.

Every QB, RB, TE, unsupported WR and ineligible group remains bit-exact
control. No TD value enters output. Coefficients remain exactly 1.0/1.0 and
world index is the sole exact-tie rule. An independent rank-source repeat must
reproduce treatment bit-for-bit.

The permutation applies only to the incumbent baseline draw matrix used for
boom generation, candidate scoring and coverage selection. The separately
trained role-belief draw matrix is a common alternate generator and remains
bit-identical. Extending competitive ranks to that matrix is a second,
score-free-unvalidated treatment and is prohibited.

## Mechanical gate before realized scoring

Require all of the following before comparing lineup outcomes:

1. Stage R/Stage T report, manifest, protocol and attestation hashes match;
2. all 30 arm/book/season cells have 18 slates, exactly 80 distinct rosters per
   slate, complete labels and checksummed 10,000-world artifacts;
3. control R0 reproduces the registered incumbent and R1--R4 reproduce their
   frozen seed identities;
4. within each pair, player keys, PIT inputs, market means, cache, schedules,
   seeds and all non-arm settings match exactly;
5. every treatment row retains its bit-exact control marginal, float64 mean
   drift at most `1e-10`, and only Stage-T-eligible WR rows change;
6. the independent source repeat, eligible-group hash, audit counts and output
   are bit-exact;
7. treatment reaches candidate masks or distribution-derived scores; and
8. candidate/player snapshots are equal after excluding only preregistered
   distribution-derived fields, while shared-roster actuals agree.

Any violation makes the experiment invalid. Byte-identical infrastructure
retry is allowed only after proving zero destination rows/artifacts. Release is
capped at ten nonterminal cells.

## Frozen tail-first decision

For each arm/book, take each slate's maximum realized score among its 80
selected lineups. Sum threshold counts across all five books in this exact
order: `240,230,220,210,200,194,187`. The first nonzero
treatment-minus-control count decides. Positive selects treatment; negative
retains control. If all counts tie, compare the mean of all 270 seed-slate
maxima; exact tie retains control.

Report each book, aggregate and per-season tails; mean/median; paired
better/worse/tied slates; roster/candidate overlap; and every absolute weekly
delta at least 10 points. Also report a 2,000-resample whole-slate cluster
bootstrap with seed `8,142,029`, averaging the five books within each resampled
slate. These disclose uncertainty but do not override the frozen decision.

A historical treatment win may enter the research baseline and a labeled 2026
prospective shadow. It does not silently change production, K=1, UI defaults,
the TE follow-up, or another registered experiment.
