# Archived Week2 role trace: missing opportunity history changes who can score

The largest player-level model disagreements have a concrete source. In the Thursday archive, **all 435 rows have null snap, target-share and carry-share history; every one of the 405 feature-matched skill rows has games_played_prior=0**. Hsim therefore uses its depth-based activity fallback and position-level share priors. This is a finding about the archived September 17 input, not proof that the Saturday refresh has the same values.

Frozen source `36252c68`; [protocol](2026-09-19-hsim-role-trace-protocol.md), [executable](reviews/evidence/2026-09-19-hsim-role-trace.py), [full result](reviews/evidence/2026-09-19-hsim-role-trace.json). The feature-null census above is an additional descriptive inspection of the trace's recorded allowlisted fields; no outcomes were accessed.

## Direct effects visible in the selected book

Hsim permits WR target/rush opportunity when recent snap share is at least 0.2 for an experienced player, or depth rank is at most 2. With missing snap history and zero prior games here, **all WR3-and-lower rows fail that activity rule**. A weight initialized to zero stays zero through multiplicative calibration. Six selected receivers consequently score exactly zero in every saved hsim world, while incumbent means are positive:

| Archived player | Depth | Incumbent mean | Hsim mean | K97 exposure |
|---|---:|---:|---:|---:|
| Chris Moore | missing | 5.412743 | 0 | 1 |
| Kalif Raymond | 3 | 6.381041 | 0 | 1 |
| Kendrick Bourne | 3 | 11.590918 | 0 | 3 |
| Devontez Walker | 3 | 5.325592 | 0 | 1 |
| Jack Bech | 3 | 8.844431 | 0 | 1 |
| Denzel Boston | 3 | 6.494981 | 0 | 1 |

Those exposures are player appearances, not necessarily distinct lineups. Names, teams and depth are archived inputs; this report does not independently establish their current real-world roles or recommend removing them.

The selected non-primary QB is **Tyson Bagent**, present in two of 97 lineups (369/6400 pool candidates). His incumbent mean is 16.881953; hsim mean is 3.400100. The simulator assigns all team passing production to the highest-projected QB, Caleb Williams in this archive. Bagent has depth 2, receives a positive fallback rushing weight and no passing production. The other 21 selected primary QBs average only +0.516614 hsim-minus-incumbent points. Thus the -13.481853 QB outlier is explained by different role treatment, not a generic QB distribution shift.

This still does not tell us which projection is accurate. In particular, “not primary under this simulator rule” is not an injury/status exclusion and must not become an untested live player-removal rule.

## Why the positive skill-player offsets also need care

Among selected players with nonzero activity support, average hsim-minus-incumbent offsets are RB +2.161173, WR +2.003539 and TE +1.097857. The six zero-support receivers obscure that positive WR pattern when averaged together. The K97 book includes 32 TEs, compared with 31 in the earlier K90 decomposition; that explains the small TE-average difference between reports.

Hsim has a coherent finite team opportunity budget. Its calibration makes five 400-world pilot updates, multiplies both target and carry weights by a clipped target/current ratio for skill players, normalizes weights within each team at sampling time, and separately adjusts primary-QB team efficiency/rushing. These are coupled updates, not a guarantee that every served mean is attainable or reached. Removing support from some receivers while allocating all team opportunities among supported players can redistribute scoring to them. The saved score matrices establish the observed redistribution pattern; missing calibrated weights and sampled intermediates prevent attributing its exact size to each mechanism.

The code's comment that the hsim component is calibrated “to the same served means” must not be read as empirical equality: the archived distributions demonstrably differ. DST is separately sampled from the opponent path and is not included in the skill calibration loop. The optional recenter branch is not used by this live call.

## Immediate follow-up

Verify whether the current Week2 inference table and the scheduled pre-build refresh still have these missing-history fields. Trace whether this reflects expected early-season support, missing Week1 ingestion, cross-season carry-forward semantics, a join problem, or some combination. A correct data repair could matter more than another search over the same banks, but it needs a point-in-time explanation and a measured before/after influence trace. Do not fill history with target-week outcomes or change role gates merely to make means agree.

Ask the workstation agent to independently reproduce these row-level findings and report current feature support. No live data, projections, eligibility rules, build timers or entries were changed by this trace. Exact archive hashes, 435 unique identities, source-byte equality, finite score banks and nine-player roster checks passed.
