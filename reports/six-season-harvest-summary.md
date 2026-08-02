# Six-season replay harvest — shipping baseline of record (2026-08-02, PUNT_BOOM=2)

Definitive baseline: canonical feature ordering (alphabetical `build_X`),
possession-sim game engine, archetype punt tilt (PUNT_BOOM=2, adopted
Addendum 37 — the only lever to improve every metric at once),
tail-coverage selection of 40 GPP entries per week, tournament
constraints on (bring-back, sub-$4k punt, RB-vs-DST ban, chalk fade).
Deterministic — these numbers reproduce exactly on re-run (verified:
harvest matched the Addendum 37 panel to the decimal, running on the
code default with no env override).

Companion spreadsheet: `six-season-replay-lineups.csv` — every player of
every entered lineup (4,040 lineups, 36,360 rows): season, week,
score_rank within the week, lineup total, player, position, team, salary,
projection, actual DK points.

## Per-year summary

| Season | Weeks | Mean best | Highest score | Weeks ≥194 | Weeks ≥237 | Median finish | ROI |
|---|---|---|---|---|---|---|---|
| 2019 | 16 | 185.1 | **271.1** (wk 5) | 2 | 1 | 10.7% | +73,226% |
| 2021 | 17 | 179.5 | **238.9** (wk 5) | 3 | 1 | 15.1% | +39,137% |
| 2022 | 17 | 175.5 | **206.3** (wk 2) | 3 | 0 | 16.0% | +38,804% |
| 2023 | 17 | 175.0 | **200.6** (wk 3) | 2 | 0 | 14.2% | +50,701% |
| 2024 | 17 | 177.2 | **194.8** (wk 5) | 2 | 0 | 16.0% | +18,150% |
| 2025 | 17 | 185.6 | **230.9** (wk 12) | 4 | 0 | 14.2% | +36,110% |
| **Total** | **101** | **179.6** | 271.1 | **16** | **2** | **14.4% avg** | **+256,128% sum** |

Reference lines are 2025 Milly Maker anchors: 194 = minimum winning line,
237 = average. Median finish percentile is the season-portable metric
(lower is better; the field is re-simulated per week). ROI assumes Milly
payout curve at $20/entry.

## Highest-scoring lineup per season

### 2019 week 5 — 271.1 pts ($49,700)
| Pos | Player | Team | Salary | Proj | Actual |
|---|---|---|---|---|---|
| QB | Dak Prescott | DAL | $6,000 | 19.1 | 29.2 |
| RB | Christian McCaffrey | CAR | $8,700 | 27.5 | 50.7 |
| RB | Aaron Jones | GB | $5,900 | 13.9 | 52.2 |
| WR | Amari Cooper | DAL | $6,800 | 19.7 | 42.6 |
| WR | Michael Thomas | NO | $6,600 | 20.0 | 44.2 |
| WR | Michael Gallup | DAL | $5,000 | 15.0 | 27.3 |
| TE | Greg Olsen | CAR | $4,000 | 22.1 | 0.0 |
| TE | Jason Witten | DAL | $3,800 | 21.8 | 5.9 |
| DST | SFO | SFO | $2,900 | 13.2 | 19.0 |

### 2021 week 5 — 238.9 pts ($49,900)
| Pos | Player | Team | Salary | Proj | Actual |
|---|---|---|---|---|---|
| QB | Lamar Jackson | BAL | $7,600 | 24.4 | 45.9 |
| RB | Jonathan Taylor | IND | $6,300 | 12.4 | 34.9 |
| RB | Devonta Freeman | BAL | $4,000 | 10.3 | 6.5 |
| WR | Cooper Kupp | LA | $7,900 | 22.9 | 16.2 |
| WR | Marquise Brown | BAL | $5,800 | 13.4 | 36.5 |
| WR | Mecole Hardman | KC | $4,000 | 25.9 | 16.6 |
| WR | Kadarius Toney | NYG | $4,000 | 25.5 | 32.6 |
| TE | Mark Andrews | BAL | $5,400 | 11.9 | 44.7 |
| DST | NWE | NWE | $4,900 | 9.4 | 5.0 |

### 2022 week 2 — 206.3 pts ($49,800)
| Pos | Player | Team | Salary | Proj | Actual |
|---|---|---|---|---|---|
| QB | Lamar Jackson | BAL | $7,400 | 20.3 | 48.6 |
| RB | Nick Chubb | CLE | $7,100 | 19.2 | 32.3 |
| RB | Rashaad Penny | SEA | $5,400 | 12.4 | 1.5 |
| WR | Jaylen Waddle | MIA | $6,400 | 12.1 | 43.1 |
| WR | Tyler Lockett | SEA | $5,600 | 15.1 | 22.7 |
| WR | Rashod Bateman | BAL | $5,500 | 11.8 | 23.8 |
| WR | Dee Eskridge | SEA | $3,800 | 10.8 | 1.6 |
| TE | Mark Andrews | BAL | $6,400 | 15.9 | 28.7 |
| DST | CIN | CIN | $2,200 | 8.9 | 4.0 |

### 2023 week 3 — 200.6 pts ($50,000)
| Pos | Player | Team | Salary | Proj | Actual |
|---|---|---|---|---|---|
| QB | Jimmy Garoppolo | LV | $5,200 | 19.0 | 23.7 |
| RB | Tony Pollard | DAL | $8,000 | 17.2 | 18.1 |
| RB | Raheem Mostert | MIA | $6,000 | 15.4 | 45.2 |
| RB | Jaylen Warren | PIT | $5,000 | 8.9 | 8.2 |
| WR | CeeDee Lamb | DAL | $7,700 | 16.3 | 10.2 |
| WR | Davante Adams | LV | $7,500 | 17.8 | 45.2 |
| WR | Jakobi Meyers | LV | $4,800 | 13.2 | 15.5 |
| TE | Durham Smythe | MIA | $2,900 | 19.4 | 2.5 |
| DST | BUF | BUF | $2,900 | 8.9 | 32.0 |

### 2024 week 5 — 194.8 pts ($50,000)
| Pos | Player | Team | Salary | Proj | Actual |
|---|---|---|---|---|---|
| QB | Joe Burrow | CIN | $6,400 | 20.9 | 37.8 |
| RB | Zack Moss | CIN | $6,000 | 12.2 | 8.2 |
| RB | Rhamondre Stevenson | NE | $6,000 | 11.2 | 19.2 |
| WR | Ja'Marr Chase | CIN | $8,000 | 16.5 | 44.3 |
| WR | Garrett Wilson | NYJ | $6,700 | 14.6 | 32.1 |
| WR | Wan'Dale Robinson | NYG | $5,600 | 13.0 | 16.0 |
| WR | Andrei Iosivas | CIN | $4,000 | 18.5 | 4.9 |
| TE | Isaiah Likely | BAL | $4,400 | 7.0 | 16.3 |
| DST | DEN | DEN | $2,900 | 9.9 | 16.0 |

### 2025 week 12 — 230.9 pts ($50,000)
| Pos | Player | Team | Salary | Proj | Actual |
|---|---|---|---|---|---|
| QB | Jameis Winston | NYG | $4,600 | 15.0 | 36.2 |
| RB | Christian McCaffrey | SF | $9,500 | 26.4 | 27.2 |
| RB | Jahmyr Gibbs | DET | $8,300 | 22.4 | 58.4 |
| WR | Amon-Ra St. Brown | DET | $8,000 | 21.0 | 32.9 |
| WR | Wan'Dale Robinson | NYG | $5,500 | 12.7 | 33.6 |
| WR | Isaiah Hodgins | NYG | $3,300 | 16.1 | 12.2 |
| TE | Dalton Schultz | HOU | $4,000 | 18.9 | 1.8 |
| TE | Juwan Johnson | NO | $4,000 | 19.2 | 10.6 |
| DST | LA | LA | $2,800 | 7.2 | 18.0 |

## Reading the winners

The season-best lineups all share the validated construction DNA: a game
stack with bring-backs (2019: four Cowboys vs a Carolina bring-back;
2021: four Ravens; 2024: four Bengals), a sub-$4k punt that hit
(Toney 32.6, Hodgins 12.2 on a 3-stack week, Eskridge the miss the stack
survived), and cheap DSTs. Note how many winners carry one dead spot
(Olsen 0.0, Penny 1.5, Smythe 2.5, Iosivas 4.9, Schultz 1.8) — a
271-point week doesn't need nine hits, it needs five booms, which is why
the selection objective chases tail coverage instead of mean.

Every season's highest-scoring lineup is IDENTICAL to the pre-punt-boom
baseline — the tilt reshaped ~21k of 36k lineup slots across the
portfolio (better punts in the breadth entries, +1 tail week in 2022,
ROI +17%) without touching the peaks. That's the adoption thesis in
one line: a tiebreak among near-equal punts, never a mandate.

Provenance: Addendum 37 (PUNT_BOOM adoption, this baseline), 36
(attribution sweep), 35 (selection-objective panel), 34 (canonical
ordering) in `2026-07-25-system-study.md`.
