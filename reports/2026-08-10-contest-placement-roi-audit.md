# Contest placement and ROI evidence audit

Status: current repository/warehouse inventory and one real-contest anchor,
2026-08-10. This report separates observed contest evidence from simulated
field estimates.

## What the existing 2025 files contain

- `reports/2025-milly-rosters.csv` has 153 rows: the nine players in the
  first-place lineup for each of 17 weeks. It has no entry rank, entry ID,
  second-through-fifth-place roster, payout, or field row.
- `reports/2025-milly-winners.csv` has one summary row for the same winner in
  each week. It is also first-place-only.
- The older `milly-winners-2019-2023-2024.csv` is likewise a player-level
  winner-roster source, not a leaderboard.

The warehouse confirms the gap. `nfl_raw.contest_ownership` has 103,556
player-ownership rows from 1,258 contests over 72 slates in 2022--2025, but
the prospective `contest_entries` table does not yet exist. The
`dk_contest_fills` table exists but has zero rows. No current table contains
historical opponent lineup, rank, score, duplication, or payout rows.

Therefore, second-through-fifth-place score/roster averages and historical
realized GPP ROI cannot be computed from current project data. They must not
be inferred from first-place rosters.

## First-place score distribution we can measure

The 68 known same-week Millionaire first-place lines produce:

| Season | Weeks | Mean | Median | Minimum | Maximum |
|---:|---:|---:|---:|---:|---:|
| 2019 | 17 | 255.14 | 251.64 | 221.64 | 331.86 |
| 2023 | 17 | 236.58 | 233.24 | 193.94 | 296.38 |
| 2024 | 17 | 226.88 | 232.50 | 178.32 | 281.68 |
| 2025 | 17 | 236.88 | 239.34 | 193.92 | 277.04 |
| **All known** | **68** | **238.87** | **237.29** | **178.32** | **331.86** |

Against those same 68 weeks, the corrected direct-role exact-80 research
incumbent beats first place 0 times, comes within 20 points 0 times, within 30
points 2 times, and within 40 points 8 times. Its mean/median first-place gaps
are 57.14/55.97 points. This is the honest top-prize evidence; fixed 194/200
thresholds are arm-comparison markers rather than claimed winning lines.

## One real-contest payout anchor

The operator's DFS Hero screenshot supplies contest metadata for the 2025
Week 5 Sunday main slate:

| Contest | Fee | Field | Min cash | First-place line |
|---|---:|---:|---:|---:|
| $2.75M Fantasy Football Millionaire | $20 | 161,764 | $30 at 169.34 | 246.82 |
| $40K MEGA mini-MAX | $2 | 23,781 | $4 at 171.54 | 239.14 |

The corrected direct-role book's 80 Week 5 scores have mean 135.45, median
131.84, and best 190.04. Three clear the Millionaire min-cash line and two
clear the mini-MAX line. If all 80 were entered and every cash were valued
only at the displayed minimum payout, the payout-floor calculations are:

- Millionaire: $1,600 staked, at least $90 represented by known min-cashes,
  payout-floor ROI `-94.4%`;
- mini-MAX: $160 staked, at least $8 represented by known min-cashes,
  payout-floor ROI `-95.0%`.

These are not realized ROI estimates: exact ranks, upper payout tiers,
duplicates, and tie splits are missing, so actual winnings could be higher.
They are a useful warning that a high weekly maximum and a profitable full
80-entry portfolio are different objectives.

## What the simulated ROI does and does not say

Older replays reported four-season double-up ROI of +51% to +69% against a
synthetic field. Older GPP outputs sometimes showed enormous positive ROI.
Those figures are not credible bankroll forecasts: the field uses a
salary/ownership heuristic rather than opponent rosters, the GPP payout curve
is stylized, top-tail ranks are extrapolated, and duplication/tie splitting is
absent. The extreme GPP results are especially jackpot-dominated. Keep them
as internal mechanics diagnostics only.

There is currently no defensible multi-season realized ROI number for the
80-entry GPP policy. The strongest available statement is: 0/68 known
first-place wins, a 57.14-point mean gap, and a poor payout-floor result in the
one slate where contest min-cash metadata is available.

## Prospective closure

DraftKings documents that a completed contest CSV contains final rank,
points, and complete lineups, but remains downloadable for only ten days:
https://support.draftkings.com/dk/en-us/how-do-i-download-a-csv-to-see-gamecenter-standings-for-a-contest?id=kb_article_view&sysparm_article=KB0010448

For every 2026 slate, capture at least one target GPP's full standings CSV and
the exact payout curve immediately after settlement. The implemented importer
then preserves ordered lineups, ranks, scores, ownership, and duplication in
`contest_entries`/`contest_ownership`; the daily backup already includes both.
Also retain the operator's DraftKings entry-history export (fees and actual
winnings). Those two sources enable exact 2nd--5th summaries, portfolio cash
rate, gross winnings, net profit, and realized ROI without reconstructing
ephemeral history later.
