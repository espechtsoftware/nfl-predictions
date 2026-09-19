# Direct 220 selection on the fixed repaired pool

The current ordinary objective maximizes expected book maximum. That is not identical to maximizing the chance of a 220+ book maximum, and its first row maximizes mean score rather than individual P220. Test this objective distinction directly, without changing any player forecast, prior, candidate or mixture weight.

Use only the already-frozen repaired D1600 pool, 97 entries, and its saved independent I/H selection and audit banks. Compare ordinary EMAX and its existing WEMAX shadow against exactly two additional, predetermined books:

1. **Coverage220:** greedy marginal coverage of worlds in which at least one selected lineup scores >=220. Exact tie order: greater standalone P220, then greater mean score, then smaller original candidate index. No overlap cap, swap, fitted threshold or search.
2. **Excess220:** run the existing expected-maximum selector on `max(lineup_score - 220, 0)`, maximizing expected positive excess of the portfolio maximum above 220. Preserve its existing tie behavior. This values magnitude beyond the threshold; it is not a payout model.

Reproduce the original ordinary EMAX order before reading contrasts. Preserve original roster order and float32 score sums; all source/artifact hashes are pinned to the existing full-chain result. Score all four fixed books under control-I, control-H, repaired-I and repaired-H independent audits and both equal mixtures. If a book includes a player absent from an evaluation law, report that contrast unavailable with the player identity; never impute zero.

Report the existing expected maximum, P220 and GLOBAL proxy plus P194, P240 and expected positive excess above 220, at every existing prefix and contest block. Report selection-bank versus audit values, paired finite-world uncertainty, memberships, first-roster change and disagreements across laws. No dominance gate is manufactured after looking: this is a tradeoff screen of two explicit objectives, not an adopted selector or proof of NFL efficacy. In particular, more P220 at a cost in other metrics is a tradeoff, not automatically a failure or a victory.

One serial run, one CPU, 600-second cap; no warehouse queries, fitting, current outcomes or bank991. A synthetic objective/tie fixture and actual artifact/shape preflight precede source freeze. Existing reports supply baseline results; this work adds no parameter sweep. Any promising objective still needs historical walk-forward testing before money-path consideration.
