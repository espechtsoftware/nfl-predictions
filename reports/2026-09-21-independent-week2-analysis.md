# Independent Week-2 analysis: where the existing post-mortem is right and where it needs sharper controls

I independently joined the released 12,555-candidate realized table to the archived D12800 candidate frame and recomputed both simulator components. I also inspected the released player-signal and game tables. This is a review of the evidence, not a production adoption decision.

## The most important correction

The headline pool correlation of -0.49 is the incumbent component, and it reproduces (-0.48794). It is not the combined decision score. The corrected-HSIM component correlates -0.08739, while an equal-mass combination correlates -0.33201. The incumbent component is therefore the dominant source of the dramatic inversion, but both components are poor on this one slate. The stored `sel_mean` is effectively the incumbent score, with maximum difference 10.87 points from the independently recomputed equal-mass mean.

This changes the next diagnostic: do not tune selector weights from the aggregate -0.49. First attribute the failure to the two projection laws, then test any mixture or market correction on walk-forward seasons.

## Market disagreement is a monotone warning signal

Using the released player signals, players whose served projection exceeded market points by 0–2 averaged 1.64 points below projection; the 2–5 group averaged 3.03 below projection; Jefferson was the extreme case at 16.79 below projection. Players at or below market averaged slightly above projection. The overall projection and market correlations were 0.616 and 0.591 respectively, while projection-minus-market versus projection residual was -0.256.

This supports a **soft market-agreement pull** as a selection shadow and a hard review gate for large positive divergence. It does not justify replacing projections with market points, because the market is not uniformly superior and the sample is one slate.

## Game selection was more revealing than total ranking

Our largest game overweight versus the Millionaire top 100 was MIN–CHI (1.15 player slots per row versus 0.66), a 48.5-total game that produced only 104.2 skill points. We also overweighted LV–LAC and CAR–ATL relative to the top 100. The largest underweights were WAS–DAL (0.98 versus 2.15; 203.84 skill points), SEA–ARI (0.20 versus 0.97), CIN–HOU, and NO–BAL.

The failure is not simply that totals were ignored. The system followed high totals but did not discount the windy MIN–CHI environment enough and did not identify the player-level concentration in WAS–DAL and SEA–ARI. The next game prior should combine total, wind, and player-level market agreement; a blunt game-total concentration rule would be too coarse.

## Exposure interpretation

The released exposure table supports the post-mortem’s central concentration finding: Jefferson, Bijan, 49ers DST, Javonte, McConkey, and London were all heavy and all underperformed. But a player-level cap must be evaluated against the same selector objective and eligible pool. The existing mean-sort counterfactual is not a clean estimate of a cap’s causal effect because it changes the selection law as well as the constraint.

The proper Week-3 comparison is a factorial on one fixed pool: current selector/no cap, current selector/soft cap, market-pull/no cap, market-pull/soft cap, with the injured/no-prop cap as a separate risk arm. Record feasibility, selected-player exposure, simulated utility, and then realized K20/K40/K80 outcomes.

## What I would prioritize

1. Confirm the serving-commit pre-blend calculation for Jefferson and the exact season-window inputs; classify as a repair only with a reproducer and regression test.
2. Run the fixed-pool market-pull and exposure-cap shadows together, not as separate retrospective adjustments.
3. Keep D12800 versus D6400 as a supply result, not a scoring result: the larger pool supplied more 200+ candidates historically but did not solve retrieval.
4. Keep the paired `dual_emax` versus `cap_prefix_then_fill` realized shadow as the primary selector test.
5. Repair ownership capture and preserve typed rejection evidence before using contest ownership as a training or fade input.

Evidence scripts and independent component result are in `/home/erich/projects/review-evidence/week2-independent/`; no production main or live book was changed.

