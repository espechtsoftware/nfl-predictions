# Low-scoring selected players — what the model believed at lock (opened PREREG-094 D800 books; descriptive)

Selected lineup-player rows: 155,520 (138,240 skill) across 216 slate-banks; low scorer = < 8 pts and < 40% of projection.

## 1. Prevalence
- low-scoring skill players: 25,556 of 138,240 (18.5%); zero-point: 7,852 (5.7%)
- lineups with ≥1 low scorer: 80.5%; with ≥1 zero-point player: 36.8%

## 2. Categories of low scorers (share of low-scoring skill players)

| category | n | share | mean projection | mean salary | mean own_est |
|---|---:|---:|---:|---:|---:|
| other bust | 8304 | 32.5% | 12.6 | 5296 | 0.019 |
| thin role (depth>=2) | 6602 | 25.8% | 11.9 | 5450 | 0.010 |
| inactive/DNP (0 pts) | 4481 | 17.5% | 10.9 | 4714 | 0.127 |
| active but 0 pts | 3371 | 13.2% | 8.9 | 4172 | 0.043 |
| star bust (salary>=7k) | 2378 | 9.3% | 18.2 | 7745 | 0.013 |
| volatile boom bet (std/mean>0.9) | 420 | 1.6% | 9.3 | 4573 | 0.019 |

## 3. What the model believed: low scorers vs the rest of the selected players (skill)

| metric | low scorers | other selected | selected 20+ pts |
|---|---|---|---|
| n | 25556.0 | 112684.0 | 32447.0 |
| projection | 12.096 | 14.278 | 16.424 |
| p90 | 23.655 | 27.823 | 31.651 |
| std/mean | 0.735 | 0.711 | 0.688 |
| salary | 5301.659 | 5968.366 | 6613.813 |
| depth>=2 | 0.371 | 0.315 | 0.256 |
| snap_l4 | 0.717 | 0.766 | 0.798 |
| dk_l4 | 13.206 | 15.05 | 17.354 |
| cold_start | 0.073 | 0.061 | 0.054 |
| own_est | 0.038 | 0.019 | 0.02 |
| practice<full | 0.069 | 0.029 | 0.023 |
| lev_family | 0.025 | 0.025 | 0.028 |

## 4. By position and by salary tier (low-scorer rate among selected skill players)

| position | selected | low rate | zero rate |
|---|---:|---:|---:|
| QB | 17280 | 5.5% | 0.2% |
| RB | 38355 | 17.1% | 4.9% |
| TE | 19917 | 23.9% | 8.0% |
| WR | 62688 | 21.2% | 6.9% |

| salary tier | selected | low rate | zero rate | mean actual |
|---|---:|---:|---:|---:|
| <4k | 15274 | 34.0% | 17.3% | 6.8 |
| 4-5.5k | 37785 | 21.7% | 7.4% | 10.9 |
| 5.5-7k | 53647 | 14.6% | 2.9% | 15.0 |
| >=7k | 31534 | 13.7% | 2.6% | 18.2 |

## 5. Cost to the lineup and to the weekly max

- lineups by number of low scorers: {0: 3370, 1: 6186, 2: 4762, 3: 2158, 4: 659, 5: 134, 6: 11}; mean lineup score with 0 / 1 / 2+ low scorers: 136.5 / 124.3 / 103.9
- the slate-bank's BEST lineup carried a low scorer 42.6% of the time (zero-point player 19.9%); books' best lineups average 181.4
- lineups with a zero-point player: 6358 of 17280 (36.8%); their mean score 109.8 vs 122.1

## 6. The most frequently selected low scorers (player-weeks appearing in many lineups)

| season | week | player | pos | team | lineups (of 240) | projection | salary | actual | category |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 2022 | 13 | Melvin Gordon | RB | KC | 136 | 11.3 | 200 | 0.0 | inactive/DNP (0 pts) |
| 2022 | 16 | Aaron Jones | RB | GB | 127 | 16.1 | 6900 | 5.4 | other bust |
| 2022 | 6 | Tony Jones | RB | SEA | 80 | 6.3 | 200 | 0.0 | active but 0 pts |
| 2024 | 2 | Cooper Kupp | WR | LA | 66 | 20.8 | 7600 | 7.7 | star bust (salary>=7k) |
| 2021 | 16 | Rob Gronkowski | TE | TB | 59 | 14.7 | 6200 | 3.3 | thin role (depth>=2) |
| 2024 | 17 | Chuba Hubbard | RB | CAR | 54 | 16.5 | 7000 | 0.0 | inactive/DNP (0 pts) |
| 2022 | 8 | Josh Jacobs | RB | LV | 54 | 19.4 | 7500 | 7.4 | star bust (salary>=7k) |
| 2023 | 16 | D.J. Moore | WR | CHI | 53 | 16.3 | 6900 | 4.8 | thin role (depth>=2) |
| 2021 | 16 | Tyreek Hill | WR | KC | 51 | 19.4 | 8400 | 3.9 | star bust (salary>=7k) |
| 2024 | 14 | Cole Kmet | TE | CHI | 50 | 10.9 | 3700 | 0.0 | active but 0 pts |
| 2024 | 3 | George Kittle | TE | SF | 50 | 13.1 | 5700 | 0.0 | inactive/DNP (0 pts) |
| 2021 | 15 | Brandon Aiyuk | WR | SF | 49 | 16.2 | 6300 | 4.6 | thin role (depth>=2) |
| 2021 | 11 | D'Ernest Johnson | RB | CLE | 48 | 14.7 | 5600 | 2.6 | other bust |
| 2024 | 5 | Devin Singletary | RB | NYG | 48 | 13.9 | 6300 | 0.0 | inactive/DNP (0 pts) |
| 2022 | 11 | Saquon Barkley | RB | NYG | 48 | 21.5 | 8900 | 5.5 | star bust (salary>=7k) |

## 7. Follow-up: how much of this is fixable (89 k1 frames, 2019–2024)

- **Placeholder salaries.** Only two skill player-weeks in the whole panel carry a placeholder $200 salary with a
  real projection (Melvin Gordon KC 2022 W13, proj 11.3; Tony Jones SEA 2022 W6, proj 6.3) — but on those two
  slates the optimizer treated them as free roster spots (136/240 and 80/240 selected lineups) and both scored 0.
  Paired designs are unaffected (control and treatment share the pool); the absolute level on those slates is
  depressed. Fix for Week 2+: drop skill players with salary < 2,500 from the historical frames (a preregistration
  amendment — every reader then shifts by the same slates). Deficiency-log row added.
- **Inactives.** 362 of 9,849 player-weeks projected ≥ 8 points (3.7%) were inactive at kickoff. At lock, 174 carried a
  designation (112 Questionable, 62 Doubtful), 188 carried none; counting limited practice too, **only 50.6% had any
  lock-time flag**. So roughly half of the dead slots are catchable pre-lock by an availability judge (the live
  path's P_MIX does exactly that for designated players; the historical panel has no judge), and the other half only
  by information that arrives after the book is built: the 90-minute inactives (today's T-70 rebuild covers the 1 PM
  games) and late swap for the 4:25 PM games (a Week-2 workstream — production's 3:55 PM recourse experiment 023
  already showed the mechanism is valid).

## 8. What this says about "learning to select better"

The largest single, repeatable loss in the selected books is not a mis-ranked star but a **dead slot**: 36.8% of
lineups carry a zero-point player, and the slate's best lineup does so 20% of the time. Every ordering experiment
this morning moved the top-30 maximum by ±1–2 points; removing dead slots from the best lineup is worth about +2
points on average by itself, and it is purely an availability/information problem: designations at lock (judge),
inactives at T-90 (rebuild), late-game scratches (late swap). The "thin role" and "star bust" categories are ordinary
variance the model already prices (their projections and tails were lower than the 20+ scorers' on average); no
pre-lock feature in the panel separates them further.
