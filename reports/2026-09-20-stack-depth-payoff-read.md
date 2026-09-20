# Stack depth and payoff: how often do QB + 3 pass-catcher stacks pay?

Operator question (2026-09-20, 11:25 CT): "how often is it successful to have deep stacks of 3 or more players ...
I'm guessing that those rarely pay off and that one or two WRs get most of the points." Read-only reads of the
warehouse, no outcomes of the current week opened (Week 2 games had not started). Definitions: stack depth = number
of WR/TE on the QB's team in the lineup; "team-week" = one team's regular-season game.

## A. Receiving-point concentration, 2019-2025 (nfl_features.player_week_actuals x dk_salary_week, 3,718 team-weeks)

| QB game | team-weeks | #1 WR/TE avg | #2 avg | #3 avg | #1 share of top-5 | #1+#2 share | P(#2 >= 15) | P(#3 >= 15) | P(#3 >= 12) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| QB 30+ | 332 | 29.4 | 17.7 | 11.2 | 0.43 | 0.68 | 0.65 | 0.18 | 0.44 |
| QB 25-30 | 403 | 25.0 | 15.2 | 9.9 | 0.42 | 0.68 | 0.49 | 0.09 | 0.30 |
| QB 18-25 | 984 | 21.7 | 12.9 | 8.2 | 0.43 | 0.69 | 0.27 | 0.02 | 0.12 |
| QB < 18 | 1,999 | 15.9 | 9.5 | 6.1 | 0.43 | 0.69 | 0.08 | 0.00 | 0.02 |

How many WR/TE on the team score 15+ in the same game:

| QB game | team-weeks | none | one | two | three+ | two+ at 20+ | three+ at 20+ |
|---|---:|---:|---:|---:|---:|---:|---:|
| QB 25+ | 735 | 0.07 | 0.37 | 0.43 | 0.13 | 0.23 | 0.011 |
| QB < 25 | 2,983 | 0.40 | 0.46 | 0.13 | 0.009 | 0.034 | 0.0003 |

Unconditional: three WR/TE at 15+ in 3.4% of team-weeks; two at 15+ in 22.6%. These use the team's ex-post best
receivers, so they are upper bounds for a stack chosen before the game.

## B. Our scored candidates: realized results by stack depth (panel 20260811-pitclean-e80-k1-role12union-a12ab31, 107 slates 2019-2025, 27,051 candidates)

| depth | n | pool share | mean actual | within-slate percentile | P(>=187) | P(>=194) | P(>=200) | slate winners | top-10-of-slate rate | selected by the selector |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 26,444 | 0.978 | 116.6 | 0.500 | 0.008 | 0.003 | 0.002 | 106 | 0.039 | 0.31 |
| 3 | 598 | 0.022 | 113.6 | 0.478 | 0.003 | 0.003 | 0.000 | 1 | 0.054 | 0.53 |
| 4 | 9 | 0.000 | 121.5 | 0.541 | 0.111 | 0.111 | 0.000 | 0 | 0.111 | 0.67 |

Depth 3 is 3 points worse on the mean, equal at 194+, and under its pool share on slate wins (1 vs 2.3 expected);
n = 598 leaves the tail comparison inconclusive. The selector nevertheless picks depth-3 lineups at 53% versus 31%
for depth 2: the simulator rewards correlated booms more than realized outcomes do (consistent with the simulated-
tail miscalibration, book P(220+) about 2.8x realized).

## C. One real field: 2026 Week 1 Millionaire, all 831,028 entries (nfl_raw.contest_entries, names mapped through dk_salary_week)

| depth | entries | field share | mean points | P(200+) | top-1% rate | lift vs field | top-0.1% lift | top-20 entries | winner |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 159,272 | 0.19 | 140.0 | 0.013 | 0.005 | 0.52 | 0.36 | 2 | 0 |
| 1 | 440,745 | 0.53 | 141.2 | 0.019 | 0.009 | 0.85 | 0.91 | 11 | 1 |
| 2 | 217,199 | 0.26 | 144.7 | 0.033 | 0.015 | 1.47 | 1.48 | 7 | 0 |
| 3 | 13,497 | 0.016 | 151.5 | 0.080 | 0.041 | 4.14 | 3.67 | 1 | 0 |
| 4+ | 315 | 0.000 | 128 | 0.006 | 0.000 | 0.00 | 0.00 | 0 | 0 |

A single slate: that week's booms happened to spread across three receivers on a few teams, which is the rare draw
section A quantifies. It shows the payout when a deep stack hits, not how often it hits.

## Entered Week-2 book (K97, regenerated 15:49Z)

87 rows at depth 2, 8 at depth 3, 2 at depth 4 (rows 3 and 16: Jordan Love with four Packers pass-catchers plus the
RB; Jalen Hurts with four Eagles plus Barkley). Four deep rows sit in the first 30 (3, 9, 10, 16). Every row has a
bring-back. No change today (class E would be needed and the lock had passed for most rows).

## Reading and next step

The operator's concentration claim holds in every QB bucket. Deep stacks are lottery tickets: a full three-receiver
payoff happens in about 3% of team-weeks (13% when the QB booms), and in our own 107-slate pool depth 3 bought no
tail advantage while costing mean and being over-selected. Week-3 candidate experiment (class C, paired shadow next to
the labs' exposure-policy shadow): a construction cap of at most three same-team pass-catchers (forbid depth 4) and a
shadow at most two, scored on mean, P220/P230, max-of-K and contest-prefix costs on the frozen pool; realized
max-of-K and 200+/210+ clears as the primary read. Not an adoption.
