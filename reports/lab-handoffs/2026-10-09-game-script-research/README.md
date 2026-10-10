# Game-script research for study 97 (2026-10-09 evening)

**For:** the operator's question of 10-09 evening (HANDOFF `543f2695`): does a running back on the expected winner, or on the
winning side of a shootout, get more carries and goal-line work; do QB + WR stacks pay in shootouts and for teams expected to
trail? Aggregates of public NFL statistics only.

- **Seasons:** 2018–2022 and 2025, regular season, weeks ≤ 18. **2023–24 are left out on purpose**: they are the harness's read
  seasons, so study 97's scenario definitions were chosen without any 2023–24 outcome.
- **Rows:** 3,142 team-games. Per team-game: the pre-game QB1 (depth chart), RB1 (depth chart, then carry share over the
  previous 4 games) and WR1 (target share over the previous 4); their actual carries, targets, attempts, touchdowns and DK
  points (`nfl_features.player_week_training`'s y_ columns); goal-line carries inside the 5 from `nfl_raw.pbp`.
- **Scenario, pre-game lines only:** expected margin = 2 × the team's implied total − the game total (> 0: expected to win);
  the game-total terciles over these seasons are 44.0 and 47.5.
- `research.py` (the analysis; the BigQuery pull is in its header's description) and `research_out.txt` (its output).

**What it shows (the output's numbers):**

| | big underdog (7+) | favorite 3–7 | big favorite (7+) | favorite in a high-total game | underdog in a high-total game |
|---|---|---|---|---|---|
| RB1 carries | 12.4 | 13.7 | 13.5 | 13.4 | 12.7 |
| RB1 goal-line carries (inside the 5) | 0.57 | 0.79 | 0.84 | 0.94 | 0.79 |
| RB1 rushing TDs | 0.31 | 0.53 | 0.58 | 0.60 | 0.44 |
| RB1 P(≥ 25 DK) | 7.7% | 17.8% | 19.2% | 22.7% | 13.1% |
| QB pass attempts | 31.1 | 33.4 | 32.7 | 34.8 | 34.4 |
| QB P(≥ 25 DK) | 11.2% | 25.4% | 31.7% | 36.0% | 22.5% |
| corr(QB, WR1) DK | 0.41 | 0.33 | 0.30 | 0.28 | 0.36 |
| corr(QB, RB1) DK | 0.08 | 0.07 | −0.04 | −0.01 | 0.04 |
| P(QB + RB1 ≥ 45 DK) | — | — | — | 33.8% | 21.0% |
| P(QB + WR1 ≥ 45 DK) | — | — | — | 30.9% | 22.2% |

(The last two rows are from the scenario table: "fav in shootout" / "dog in shootout"; the big-favorite non-shootout rows read
20.9% QB + RB1 and 25.3% QB + WR1.)

- **The RB idea holds for goal-line work, not carries:** the expected winner's RB1 gets about the same carries (13–14) but
  about 50% more goal-line carries and nearly twice the rushing TDs, and 2.5× the chance of a 25-point game. The best case is
  the favorite in a high-total game.
- **But the QB and his own RB barely move together on a favorite** (correlation ≈ 0), so the stack's gain is the two players'
  separate upside, not correlation. On the favorite in a high-total game the QB + RB1 pair still reaches 45 points more often
  (33.8%) than QB + WR1 (30.9%).
- **The QB + WR idea, partly:** trailing teams in high-total games have the highest pass rate (60%; 34.4 attempts, about the
  same as the favorite's 34.8 in those games) and their QB–WR1 correlation is higher (0.36 vs 0.28), but the favorite in a high-total game still has the higher QB and stack
  ceiling (QB 25+ 36% vs 22.5%). The game total drives the QB ceiling most (25+ in 30% of high-total games, 12% of low).
- **Caveat:** these are outcomes, not value: salaries and ownership already price favorites and high totals. Whether a
  construction rule built on them wins more is study 97's question.
