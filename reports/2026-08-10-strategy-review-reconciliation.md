# Strategy-review reconciliation

Reviewed 2026-08-10 against the repository ledger, warehouse inventory and
the primary optimization papers cited by the outside review. This document is
the tracked disposition of those ideas; the untracked review draft is not an
authoritative statement of project state.

## Important baseline correction

The review labels `classic-k1-ce12-role12-boom28-v2` and its
`39/27/18/12/6/3/2` tail grid as corrected. They are not. Those results come
from the preserved panel invalidated for new decisions by the common-slate-
lock prop defect. The corrected K3 and K1 controls are still running, and CE
and role must follow. Therefore claims that the final corrected pool is
already saturated at 220/230/240 are premature.

This is why the already-frozen 220→210→200 selector will receive exactly one
corrected-history confirmation after the generator chain finishes. The old
oracle table neither proves nor disproves that corrected selector.

## Dispositions

| Review idea | Disposition | Repository evidence / next action |
|---|---|---|
| Opponent-field simulation and expected-payout selection | **Use, prospectively** | This is genuinely distinct from the rejected ownership-fade objective and aligns directly with winning money. The warehouse has 103,556 player ownership rows from 1,258 contests over 72 slates (2022–2025), but no opponent rosters, payout curves, field sizes, min-cash lines or duplication labels. Build only after contest metadata/standings make a field-model gate honest. |
| Slate-specific target line | **Defer pending metadata** | Sixty-eight winner scores/rosters exist, but contest size and payout context are absent and the historical panels retain masks only at fixed thresholds. First acquire `{field size, payout curve, min cash, first place}`; then evaluate a walk-forward winning/cashing-line model on those labels, never on our portfolio outcomes. |
| Widen ordinary-player upper tails | **Reject as written** | The cited ordinary-player q90/q99 exceedance is `7.37%/0.72%` versus nominal `10%/1%`. Fewer actuals exceed the predicted upper quantile, so those upper quantiles are conservative/too high, not too thin. Widening them moves in the wrong direction. Re-measure after the common-lock correction if useful, but do not launch the proposed widening arm. |
| New within-team Dirichlet allocation | **Already tested; closed** | `GAME_SIM_USAGE=dirichlet` already implements mean-preserving team allocation. K=20 was negative and K=8 later produced only 11 tails with mean 175.0. The review's claim that this mechanism class is untried is incorrect. Do not retune concentration on known outcomes. |
| Reallocate leverage budget to boom/dark/CE/role | **Possible, lower priority** | Constant-budget reallocation is narrower than deletion, but the neighborhood is not cleanly unexplored: boom dose 100, enlarged candidate pools and candidate-multiple 4 were negative, while CE/role replacement already supplied the useful candidate-budget gains. Reconsider only after the corrected chain and current preregistered unions, with one exact budget and no dose sweep. |
| Scenario-conditional world argmax | **Not novel** | The production `boom` generator is already based on per-world/scenario argmax solves. It was also used as the strong GFlowNet comparator. A renamed world-argmax panel would repeat existing machinery. |
| Contest-specific portfolio slices | **Use prospectively** | The live freezer already preserves 187/194/200, extreme 220→210→200 and multiple generator books. Once actual Week 1 contest allocation is known, freeze which book serves each contest class before outcomes and grade payouts/weekly maxima afterward. Do not retrospectively choose among books. |
| Route data and narrower contest-metadata purchase | **Use** | The no-cost pass-participation diagnostic passed in both held-out seasons, supporting the under-$200 true-route export trial. A metadata-only historical export is also materially more useful and likely cheaper than full opponent fields; request it before a full standings purchase. |
| Paired statistical evidence | **Mandatory diagnostic, not a veto** | Report paired weekly wins/ties/losses and season deltas for every arm. Do not restore a significance veto that conflicts with the operator's explicit highest-score utility; instead label a one-week extreme gain as fragile and require prospective shadow confirmation when practical. |

## Opponent-field path

The research direction is sound. Hunter, Vielma and Zaman formulate fixed-
cardinality DFS portfolios around the probability that at least one entry
wins, with a submodular portfolio objective. Haugh and Singal explicitly model
opponent choices, top-heavy payoffs and multiple entries, including a
Dirichlet-multinomial opponent process. These support building an opponent
side of the contest rather than subtracting a hand-tuned ownership penalty
from our own score.

Primary sources:

- <https://arxiv.org/abs/1604.01455>
- <https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528>
- <https://onlinelibrary.wiley.com/doi/10.1111/itor.13344>

The minimum honest gate needs data the project does not currently have:

1. field size, entry fee and complete payout curve per contest;
2. min-cash and first-place scores;
3. enough full opponent lineups to measure stack/co-ownership and duplication;
4. held-out reproduction of player ownership marginals, pairwise roster
   structure, salary use and duplication; and
5. prospective payout grading of a frozen control and treatment book.

Aggregate ownership alone can seed player marginals but cannot validate joint
lineup construction or duplicated payouts. The first 2026 full-standings CSVs
should therefore be treated as model-training data, not merely archived.

### Vendor-access follow-up

DFS Hero's own current product page says BacktestIQ uses actual historical
fields with real opponent lineups and reports realized ROI, which would be the
most direct source for this work. The operator's paid trial nevertheless
returns `Contest data not available` for the available NFL Millionaire
contests, and the public materials do not promise a CSV/API export. Before any
renewal, ask support whether 2022--2025 NFL Classic full-field lineups plus
contest/payout metadata can be exported; interactive-only access is not enough
for a reproducible model gate.

FantasyLabs publicly documents historical player ownership and detailed
contest-lineup dashboards, but likewise does not publicly confirm bulk export.
It is a secondary support inquiry, not a reason to buy another subscription.

Official product references:

- <https://dfshero.com/tools>
- <https://www.fantasylabs.com/articles/introducing-new-fantasylabs-ownership-dashboard/>

Fantasy Points remains the clearest route-data lead. Its own materials confirm
weekly route share plus route-by-route coverage/alignment data back to 2022 and
CSV/Excel export. The published 2026 list price is $200; the $160 figure was an
expired early-bird offer. Confirm that one subscription permits full 2022--2025
bulk export before treating it as within the operator's strictly-under-$200
ceiling.

- <https://newsletter.fantasypoints.com/p/fantasy-points-data-free-this-week>
- <https://newsletter.fantasypoints.com/p/week1-average-separation-score>
- <https://newsletter.fantasypoints.com/p/early-bird-discount-2026>

## Resulting priority order

1. Finish the point-in-time-corrected K3→K1→CE→role chain and its frozen
   selector/NGS/no-floor follow-ups.
2. Confirm and acquire the under-$200 true-route history if export/history
   terms are adequate.
3. Seek a metadata-only 2022–2025 main-slate export before paying for complete
   historical fields.
4. Build the opponent-field/payout gate prospectively as 2026 full standings
   accumulate.
5. Consider one constant-budget generator reallocation only after the current
   corrected candidates finish; do not reopen tail widening, Dirichlet usage,
   generic ownership fade or renamed world-argmax arms.
