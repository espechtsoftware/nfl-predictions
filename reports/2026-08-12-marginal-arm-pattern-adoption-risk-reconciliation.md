# Marginal-arm pattern and adoption-risk reconciliation

Date: 2026-08-12 CDT. This reconciles the operator-supplied review
`reports/2026-08-12-marginal-arm-pattern-and-adoption-risk-review.md` against
the terminal PIT-clean lineage through `a58cd61`. The source review is retained
unchanged.

## Bottom line

The review identifies a credible and important hypothesis: the terminal
simulator's measured QB-receiver and same-team upper-tail dependence miss can
prevent useful player-level information from reaching a nine-player lineup's
extreme tail. G0 directly establishes the dependence miss. It does **not** by
itself establish that the miss caused every earlier arm result, so that broader
claim remains a prospective hypothesis for G2 and the fixed post-G2 re-asks.

Two entries in the review's six-arm table are superseded as dispositions:

- PIT-clean fitted `K=28.154043586960896` passed its score-free likelihood gate
  and its repaired exact-80 tail-first gate. It is selected, not rejected.
- The corrected direct role-belief union subsequently passed the revised
  tail-first law and is part of the current lineage. The older fixed-budget
  rejection and its matched-control diagnostic are historical context, not the
  current fast-role disposition.

SCHED and team-passing genuinely failed their terminal final-served gates.
Route Share's independently calibrated terminal treatment was exactly equal
to control at the primary Brier-30 gate because the fully covered TabPFN
rank-remap erased the upstream marginal change; its pre-remap component gains
remain useful mechanism evidence, not a passed served arm. Older
`depth_rank_delta` and `team_ol_out` losses were measured in earlier downstream
contexts. These facts make the G0 explanation plausible, but not proven across
all arms.

## Fitted-K adoption-risk audit

The source review reproduces the valid PIT-clean exact-80 grid correctly:

| arm | >=240 | >=230 | >=220 | >=210 | >=200 | >=194 | >=187 | mean weekly best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| multinomial | 2 | 2 | 3 | 5 | 14 | 26 | 37 | 177.9486 |
| fitted K | 3 | 3 | 3 | 6 | 11 | 19 | 34 | 177.3589 |

The frozen tail-first law was applied correctly and reflected the operator's
stated preference at the time. The cost is nevertheless material and must be
visible rather than hidden behind the first-difference decision.

An after-decision diagnostic of the already-published paired-week artifact
shows that **one slate, 2023 Week 3, supplies all three new >=240, >=230 and
>=210 events**: its selected maximum changes `195.16 -> 240.44` (`+45.28`). It
also crosses 220, but a `225.30 -> 213.40` loss in 2023 Week 9 leaves the 220
count tied. At 200, two gains and five losses produce the net `-3`; at 194,
one gain and eight losses produce the net `-7`.

The recorded 2023 Week 3 Millionaire winner scored `294.38`, so the fitted-K
lineup did not win that contest. Its roster was Kirk Cousins with Justin
Jefferson and Josh Oliver, Kenneth Walker, Dameon Pierce, Keenan Allen, Adam
Thielen, Michael Thomas and Buffalo DST. It shared Walker, Allen, Thielen and
Buffalo DST with the winner (four of nine slots). The QB-WR-TE same-team
construction is directly relevant to G0's measured QB-hub miss; it is not an
unstructured lucky roster. Exact payout/rank/ROI still cannot be inferred from
the winner score alone.

This audit does not retroactively reverse the frozen decision. It does expose
a separate standing-law issue: active-only labels and their walk-forward
served schedules were selected **after** the fitted-K comparison. Under the
repository's post-selection law, the fitted-K lineup verdict does not transfer
unchanged across that downstream change. G0/G1 remain valid descriptions of
their frozen terminal book, but the final production lineage requires a new
same-image fitted-K-versus-multinomial exact-80 comparison under the selected
active-only served law. That revalidation must be frozen before either arm's
new score is generated or read.

## Expected dollars: accept the goal, reject fabricated precision

Expected payout is the right eventual objective, but a published payout ladder
alone is insufficient. Converting a lineup score to dollars also requires the
contest field's score/rank distribution and duplication/tie behavior (or a
validated opponent-field simulator). The repository currently lacks complete
historical standings for the 107-slate panel. A stylized payout number would
therefore imply ROI precision the evidence cannot support.

Until complete standings or a prospectively validated field simulator exist,
every future tail-first comparison must instead include a mandatory
decision-cost diagnostic: full threshold grid, evaluation-only grid, mean and
median, paired threshold-crossing weeks, whether multiple thresholds are the
same event, and all material weekly gains/losses. These diagnostics cannot
silently veto a frozen objective, but they must be presented before any
production handoff. Exact expected dollars, cash rate and ROI remain mandatory
once the required contest inputs exist.

## Conditional post-G2 revalidation scope frozen now

If no new G2 dependence stage is selected, this section expires unused. If G1
licenses G2 and a separately frozen G2 mechanism becomes the selected
downstream dependence law, the standing post-selection rule requires a bounded
revalidation cascade. The scope is fixed now, before any G1 or G2 result:

1. Revalidate the accepted upstream construction chain under G2: K1 versus K3,
   direct role union versus its no-role source, fitted K versus multinomial,
   and active-only versus current labels. Any served-position calibration is
   independently walk-forward within each registered arm; old realized-score
   outcomes cannot select a scale.
2. Re-ask the exact frozen marginal treatments, in order: amended team-passing
   bundle, Route Share four-component treatment, then SCHED. Each comparison
   changes only that registered treatment against the then-terminal G2 stack.
3. Do not re-open a feature, dose, window, seed or threshold choice. The older
   `depth_rank_delta` and `team_ol_out` arms are excluded because they lack the
   qualifying terminal player-tail evidence used to fix this list.

This is not a license to promote an old result. Every item needs a new
same-image control and treatment under the changed downstream law. Failure of
G2 discards the entire conditional list without execution.

## G1 review notes

Both requested reporting safeguards are already in the frozen implementation:

- each broad relationship contains separately visible 2023, 2024 and 2025
  estimates and support, and the G2 decision requires at least two supported
  underprediction folds with no supported opposite material miss; and
- broad QB-WR/QB-TE stability carries the relationship-level decision while
  the protocol separately requires only one supported material archetype edge
  for each relationship. Unsupported thin cells stay visible and cannot be
  misread as contrary evidence.

The repaired v2 G1 execution remains the next scientific result. It must not
alter its thresholds, archetypes or G2 license in response to this review.
