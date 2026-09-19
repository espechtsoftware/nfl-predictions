# Target priors restore support; small-pool selection gains are minimal

Both historically nominated target priors restore nonzero simulated scoring to **19 previously zero-score players** on the repaired429-player frame. They improve calibration to the served means, including among players whose initial weights were unchanged. However, **the97-entry selection effect is very small on this160-candidate pool**: both ordinary books retain95of97baseline members. The strong historical target-share error improvement does not translate into a similarly large simulated lineup gain here.

| Fixed-pool result | Baseline | One-prior-game | Past-season empirical |
|---|---:|---:|---:|
| Prior-eligible players | 27 | 27 | 27 |
| Eligible players with zero simulated scores | 19 | 0 | 0 |
| All-frame zero-score players | 141 | 122 | 122 |
| Mean absolute gap to served means, eligible | 0.7524 | 0.1693 | 0.1788 |
| Mean absolute gap to served means, all players | 1.5957 | 1.5182 | 1.4983 |

Those served means are model outputs, not realized truth. The19recovered players are3RB,13TE and3WR. The rule does not target every prior zero: it requires at least20%prior snaps, observed zero target share, a prior game and the original activity mask. Therefore it is not accurate to promise that this particular rule prevents all22newlyzeroTEcases in the older archived census. The current frame also differs from that archive.

For the ordinary EMAX books, repair-prior minus baseline97-entry changes are:

| Evaluation mixture | One-prior-game expected-max change | P220 change (pp) | Empirical expected-max change | P220 change (pp) |
|---|---:|---:|---:|---:|
| Original repaired I/H | −0.0004 | +0.015 | −0.0027 | 0.000 |
| I + one-prior-game H | +0.0179 | +0.030 | +0.0213 | +0.040 |
| I + empirical-prior H | +0.0015 | +0.015 | +0.0033 | +0.010 |

All laws, all six EMAX/WEMAXbooks, prefixes,12contestblocks and conditional paired MonteCarlointervals are in the [full result](reviews/evidence/2026-09-19-zero-target-prior-simulator.json). Both prior books change the first lineup to the same alternative, with component-law disagreement and no universal first-lineup tail improvement. Some ordering changes occur even though97-entry membership changes little. No selector, prior or contest allocation was adopted.

Baseline verification is exact: every saved baseline Hselection and independent-audit value, and both original EMAX/WEMAXbook orders, are reproduced. Only eligible initial target weights changed. Initial carry weights and other players' initial weights stayed identical; shared calibration can subsequently alter carries and team efficiencies. All three arms use the same historical laws, current game inputs, served means, candidate pool, I banks and fixed seed/calibration contract. Runtime20.20seconds. Source`afb42627`; [protocol](2026-09-19-zero-target-prior-simulator-protocol.md).

The appropriate next check is a larger declared candidate budget: selecting97out of160leaves little opportunity for membership changes and can conceal meaningful retrieval effects. The historical result supports fixing the structural-zero model assumption; this small-pool result does not establish a material220+gain or an unambiguously better entered book. Preserve both paired prelock books for settlement regardless of which system, if any, is adopted live.
