# Scoring bottleneck and Week-1 ordering audit

Date: 2026-09-10

Disposition: the active scoring problem is now split into two concrete work
streams. Better ordering can materially improve a small K20 portfolio, but it
cannot by itself produce the approximately 230-point outcomes the user needs.
Candidate supply and the beliefs used to generate it are the binding ceiling.
No result in this report changes the Week-1 money policy or entry allocation.

## The graph has answered its first scoring question

PREREG-083 contains 36 slates, two frozen arms, and exactly 200 candidates per
arm and slate: 14,400 scored candidate occurrences. The immutable score JSON,
not mutable graph state, is numerical authority.

| Arm | Candidate-pool mean oracle | Current K20 mean max | K20 oracle regret | Current K80 mean max | K80 oracle regret |
|---|---:|---:|---:|---:|---:|
| control | 184.898 | 166.191 | 18.707 | 178.792 | 6.106 |
| direct-tail treatment | 185.923 | 168.508 | 17.415 | 180.922 | 5.001 |

The full corpus has no realized 230+ candidate. Its absolute best candidate is
227.20. Therefore a perfect retrospective ranker could recover some of the
17--19 point K20 regret, but no ranker over these pools could produce a 230.
The path to a championship-range score must change candidate supply or the
underlying rare-event beliefs as well as ordering.

This is not merely an inference from the missing 230s. The already-verified
72-slate miss funnel measured a 254.34 mean hindsight optimum under the house
construction rules and 251.16 when restricted to players the generator had
touched, versus only 185.20 for the best candidate it actually assembled.
Experiment 062 then decomposed that middle loss: under the house cell,
core-discovery loss was only 4.295 points while completion loss was 57.753;
under DK-only legality they were 15.403 and 58.108. Useful players and usually
useful proposed cores exist. The system is failing to build and identify the
right full nine-player completions.

The caution is equally concrete. PREREG-037's one-player completion editor
improved untouched simulated audit E[max] by 0.667 but improved realized K80
by only 0.094. The prior full-core implementation then failed its
outcome-disabled mechanics gate because fewer than 90% of targets yielded a
legal two-player completion. Therefore the next construction attempt needs a
better independent belief/critic and a mechanically feasible completion law;
simply widening the optimizer is not supported.

Selection recall confirms the smaller-book problem. Each arm supplied 12
realized 200+ candidates. Only 2/12 in each arm appeared in its K20 prefix;
the K80 books recovered 7/12 control and 8/12 treatment. The treatment supplied
two 220+ candidates in the same 2023 Week-3 slate and selected neither, while
control supplied one 220+ candidate and placed it at rank 64. No 220+ candidate
appeared in K20.

## Why a simple tail sort is not the fix

The three 220+ candidates were not consistently visible in the pre-lock
metrics. The two missed treatment candidates had:

- simulated-mean ranks 27 and 22;
- q90 ranks 70 and 56;
- q99 ranks 100 and 83; and
- simulated P(200+) ranks 108 and 108.

The control 227.20 candidate ranked 99 by simulated mean, 81 by q90, 40 by
q99, and 47 by simulated P(200+). Across all 24 realized 200+ candidates, the
median simulated-mean rank was 37.5 but the median q90/q99/P(200+) ranks were
66/76.5/89. Salary and simple team/game-count structure barely separated the
hits from the rest. The simulator has useful mean signal but weak
discrimination in the extreme tail.

As a fast chronological check, one fixed deterministic LightGBM LambdaRank
diagnostic was fit only on 2023 and evaluated on 2024. Inputs were the frozen
served/simulation mean, q90/q99, threshold probabilities, salary, simple
team/game counts, and distribution spreads. The ordinal label counted fixed
187/200/210/220/230/240 crossings. This was development diagnosis, not a
preregistered adoption test. LightGBM 4.7.0 used 120 trees, learning rate
0.03, seven leaves, depth three, minimum child size 80, feature fraction 0.8,
L2 penalty 2.0, one thread, and seed 83085; no 2024 value selected a setting.

| 2024 arm/prefix | Incumbent | Fixed learned marginal ranker | Delta |
|---|---:|---:|---:|
| control K20 | 162.199 | 159.376 | -2.823 |
| treatment K20 | 166.423 | 159.753 | -6.670 |
| control K80 | 177.532 | 172.533 | -4.999 |
| treatment K80 | 181.032 | 177.359 | -3.673 |

This rejects that fixed standalone learned score as a near-term replacement
for the current selector. Any remaining ranking challenger must be
set-aware: it must value incremental scenario coverage and redundancy against
the already selected prefix, and it must beat the incumbent chronologically at
K20 without losing K80 support. PREREG-085 is the bounded implementation path
for that test.

## Week-1 application

The four already-published Week-1 books remain unallocated. Their current K20
pre-lock diagnostics are descriptive because the selection bank is held in and
the independent audit artifact retained only candidate marginals, not the
candidate-by-world matrix.

| Book | Audit sum P(194+) | Audit mean | Selection-bank expected max | Selection-bank WEMAX proxy | Max player exposure |
|---|---:|---:|---:|---:|---:|
| P_CTRL | 0.0071 | 99.2020 | 139.7618 | 0.002467 | 65% |
| P_MIX | 0.0073 | 99.3622 | 139.5136 | 0.002375 | 60% |
| D800_WEMAX | 0.0111 | 99.0649 | 137.7271 | 0.002782 | 70% |
| D400_DEMAX | 0.0064 | 98.4449 | unavailable | unavailable | 60% |

P_MIX is doing its intended participation-risk job: it reduces designated
player exposure and concentration, but it is not a demonstrated raw-upside
gain. D800_WEMAX has the most held-in WEMAX and independent marginal P(194+)
mass, but lower held-in expected maximum and greater concentration. Without an
independent joint audit matrix it is not evidence for replacing the paid book;
at most it supports a separately bounded prospective sleeve after bankroll and
entry count are fixed.

## Immediate scoring actions

1. Stop work on the Neo4j importer unless a failed query blocks analysis. The
   current local graph is sufficient and the immutable JSON remains authority.
2. Finish only the set-aware portion of PREREG-085 and reject the standalone
   marginal LightGBM path demonstrated above.
3. Put the principal experimental effort on belief-gated multi-player
   completion: use the already-proposed cores, generate multiple legal full
   completions, and evaluate them with a genuinely independent joint
   player/game critic. The critic must first pass walk-forward joint-tail and
   calibration checks; same-model proposal and judging repeats the failure.
4. Persist the complete independent candidate-by-world audit matrix in every
   future live generation. Candidate marginal probabilities cannot evaluate a
   portfolio maximum or redundancy-aware ordering independently.
5. Keep K20 as the first operational scorecard while bankroll is reduced, but
   retain K80 and candidate-pool oracle so a ranking gain is not confused with
   a supply gain.
