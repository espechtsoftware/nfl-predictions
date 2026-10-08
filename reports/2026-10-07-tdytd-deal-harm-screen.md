# Dealing the book by the lineups' season-to-date touchdowns: a frozen HARM SCREEN before the W2–4 re-deal (2026-10-07)

**Status: FROZEN 2026-10-07, before any number exists** (the laptop). No season-to-date touchdown count has been
computed for any book row. The only data seen before the freeze is an outcome-blind coverage census: 2026 rows per week
of the two source tables, and their null counts.
- The wording follows the priority-deal screen (`reports/2026-10-07-priority-deal-harm-screen.md`) and the TD-deal screen
  (`c9028505`), which the reviewer worded.
- It is the in-sample check of the operator's idea on the weeks with real fields. The decision-bearing test is the
  harness study proposed to the reviewer (below).

## Why

The operator (10-07): "Earlier, we tried an experiment of sorting based on projected touchdowns, and that didn't work out
so well. Please now try another experiment on the total touchdowns prior to this game this year for all the players in
the lineup and sort by that."

- **What was tried (both ledgers checked 10-07; study list 49):**
  - Study 52 (Addendum 160) dealt the book by the lineups' PROJECTED touchdowns (the simulator's rushing + receiving
    TDs): NOT SUPPORTED, −0.022 [−0.059, +0.014] on 2023–24.
  - The laptop's W2–4 re-deal by the market's anytime-TD prices was NOT ENTERED (below LIVE in all 3 weeks; ratio 0.101).
  - The idea was closed "unless a new TD source appears".
- **What is new:** touchdowns the players actually SCORED this season before the slate. This is a realized,
  point-in-time count, not a projection or a price. Unlike the market prices, it exists in every historical season, so
  the harness can test it out of sample.
- **The prior:**
  - A re-deal moves wins between contests and does not make them, so a small or null effect is the likeliest reading.
  - Studies 48b, 52 and 59, and this morning's priority sort, all read null or worse.
  - Season-to-date TDs are also a noisy measure of role, especially early in the season (W2 sees one week).

## The deal (exact)

- **The book:** the CB books of the priority-deal replay, `~/rehearsals/prioritydeal-20261007T193507Z/w{2,3,4}-cb`.
  - They are his Week-5 construction on the W2–4 real fields with the cheap +2 block armed: overlap 4, round-robin fill,
    QB cap 5, no ownership term, K 26, 15 spares; W4 on FP projections.
  - No new builds.
- **The key: the lineup's season-to-date touchdowns.** For a row in week W, it is the sum over its 9 players of each
  player's 2026 regular-season touchdowns in weeks 1 … W−1:
  - **QB / RB / WR / TE:** `pass_tds + rush_tds + rec_tds + special_teams_tds` from `nfl_features.player_week_actuals`,
    joined by the T-70 frame's `gsis_id`. A QB's passing TDs count: they are his "total touchdowns" in the usual sense.
  - **DST:** the team's `return_tds` from `nfl_features.team_defense_week` (defensive and special-teams touchdowns, the
    ones DraftKings credits to a DST).
  - A player with no rows (no game played, or no `gsis_id` on the frame) counts 0. Fumble-recovery TDs by offensive
    players are not in the table and are left out (rare). The count of rostered players without a `gsis_id` is printed.
  - W2's key sees Week 1 only, W3's Weeks 1–2, and W4's Weeks 1–3.
  - **Disclosed:** the warehouse holds each week's final stats, including any stat correction made after it. A
    production version would read the same table at Saturday arming, when weeks before W are final.
- **The arms**, all on his live contest plan Rev6 (`5f8352ee…`):
  - **CB_REV6 (the reference):** the book in its own order, today's live deal.
  - **CB_TDY (the decision):** the reviewer's block rule.
    - The 8 cheap-block rows keep their positions (0-based 1, 4, 8, 11, 14, 17, 21, 24).
    - The other 18 rows are sorted among their own 18 positions by the key, most first; ties keep the book's order.
    - The 15 spares are untouched.
  - **Exploratory, never decision-bearing:**
    - **CB_TDY_ALL:** all 26 rows sorted by the key, no block kept. This is the literal "sort by that".
    - **CB_TDY_SCORED:** CB_TDY with the key restricted to touchdowns the players scored themselves (no passing TDs).
      It shows whether the QBs' passing TDs carry the sort.
    - **CB_PROJ18:** CB_TDY's 18 positions sorted by the lineup's projection (`proj_sum`). This is the projection-order
      control: if CB_TDY ≈ CB_PROJ18, the TD sort is projection order.
- **Integrity** (the week is VOID otherwise):
  - each sorted arm holds CB's 26 rows (a Counter multiset of player sets), the same rows at the block positions (except
    CB_TDY_ALL), and the same 15 spares in order;
  - the written order equals the key sort recomputed from the written key file.
- **Reproduction check:** CB_REV6 is laid out again in this run. Its `ENTER-rowmap.json` must equal the priority-deal
  run's `stage-w{W}-cbrev6` byte for byte, and its scores must equal that run's CB_REV6 scores.
- **Scoring** (as the priority-deal replay):
  - production's head layout on Rev6, `enter_layout write --layout head` with `ENTER_SMALL_MAX_SHARED=5` and
    `ENTER_SMALL_OVERLAP_MAX_ENTRIES=10`, at production `7ee09fe1` (the priority-deal run's worktree);
  - `s24_qb_game_cap.big_seat_stats` (`ce2cddc1`) on `~/s24-panel/plan-week5-rev3-s24.json` (`3dd19d6c`), each row's
    finish against the week's real Millionaire field (`moneygate_score` `dd8ff1f7`).

## The frozen rule (CB_TDY vs CB_REV6)

**NOT ENTERED** if either holds:
1. CB_TDY's P(≥ 1 big) is below CB_REV6's (strictly) in 2 or 3 of the 3 weeks;
2. the pooled expected-big-seats ratio, Σ e_big(CB_TDY) / Σ e_big(CB_REV6) over W2–4, is below 0.80.

**This is a STOP rule only.** On weeks already seen it can show harm but not gain.

**Otherwise it passes this screen only.** It becomes a candidate only if the out-of-sample harness study passes:
- the shape of study 52: DEAL_TDY vs DEAL_LIVE on his 26-row book, the 2023–24 read and the 2022 go / no-go;
- season-to-date TDs from the same tables, point-in-time (weeks before the slate);
- the reviewer designs and freezes it.

Then the operator decides. Disclosure, in these words: *"in-sample (the operator's idea, tested on weeks already seen); no
out-of-sample evidence from this check; the harness study carries the decision."*

## Descriptive, beside the rule (no part of it)

- the key's range and the rows moved per week;
- the key's correlation with the projection;
- the QBs' share of the key;
- P(≥ 1 big) and e_big over the priority contests only;
- the priority entries' mean Millionaire-field percentile.

## Interaction

- **One construction change per week** (the reviewer's standing line). The cheap +2 block is Week 5's change, so a
  supported TD deal is a Week-6 candidate.
- If it is ever armed with the block, it is in CB_TDY's form (the block keeps its ranks), the form tested here.
