# The TD-value block: a frozen HARM SCREEN before the W2–4 replay (2026-10-07)

**Status: FROZEN 2026-10-07, before any replay number exists** (the laptop; rule wording by the reviewer). The commit
that adds this file also adds the writer it names; the replay runs only after it is pushed.

## Why

The operator (10-07): "I would like to test the under $7000 player idea before this week - not as paper." The idea is
the outside reviewer's field pattern (review/outside-fill-order-20261006 @ 70437915, section 5 of
`reports/2026-10-07-why-we-missed-the-winners-players.md`): on the W1–4 Millionaire fields, lineups carrying more
sub-$7,000 RB / WR / TE whose anytime-TD odds beat what their salary implies reached the top 1% more often in three of
four weeks. No harness test is possible (no TD prices before 2026), so the money-path test is a fixed-book replay on the
2026 weeks, and those are the weeks the rule was found on. **An in-sample pass is weak evidence; an in-sample failure is
strong evidence against.** The screen below can therefore stop the block; it can never support it.

## The options (exact formulas)

The live term-block vehicle: 8 of the 26 rows built on projection + min(0.20 × pred_own, 2.0); pred_own = bonus / 0.20.

- **TDBLOCK8:** bonus = b_td from `scripts/td_value_block_file.py`:
  - td_prob = the mean implied probability over books of the player's `player_anytime_td` price in the LAST props
    snapshot strictly before the as-of time, joined to the frame by display_name;
  - td_res = td_prob minus a linear fit of td_prob on salary within position (RB / WR / TE; priced players; a position
    with 5 or fewer priced players gets none);
  - z = td_res standardized within position (pandas' std); b_td = clip(z, 0, 2) for RB / WR / TE under $7,000, else 0.
  - The writer reproduces the outside reviewer's own W4 file exactly when given their snapshot (2026-10-04 09:32:59Z,
    before the 13:30Z London kickoff): 112 players with a bonus, max |diff| 0.0.
- **MTDBLOCK8:** bonus = b_matchup + b_td (b_matchup from `scripts/matchup_block_file.py`, approved), at the same 2.0 cap.
  **The cap binds above 2: the two bonuses are not additive there.**
- **MBLOCK8** (the matchup block) is reported beside them every week but is ruled by study 51, not by this screen.

## Timing (fidelity: test what will be entered)

The live file is pinned (TERM_SHA) at Saturday's arming, so its TD prices are the last snapshot before Saturday's arming.
The replay uses the same timing: **as-of = each week's Saturday 10:00 CT** (W2 2026-09-19 15:00Z, W3 09-26 15:00Z, W4 10-03
15:00Z; each week's last snapshot before it is that Saturday's ~09:33 CT pull). The outside reviewer's whole-book replay
used the last snapshot before Sunday's lock instead (W4: Sunday 04:32 CT): a different input, noted beside its numbers. The
**W5 live file: `--as-of 2026-10-10T15:00:00Z` (Saturday 10:00 CT), written after that morning's ~09:33 CT props pull lands; TERM_SHA is pinned after it** (the arm runs after the 09:47 refresh; everything else in the arming is unchanged). Amended 10-07 before any replay number existed (the reviewer's timing condition: one timing for W5 and the replay). The writer refuses a snapshot more than 3 h before --as-of (a missed Saturday pull cannot hand Friday's prices to the live file) and an --as-of without a time zone.

## The replay

`~/.cache/laptop-agent/rehearsal/bonus_blocks_replay.sh` (the prior-top / matchup block harness): W2–4 real fields, the
live Week-5 book (overlap 4, round-robin, QB cap 5 at K 26, no ownership term, Rev3 K 26) as LIVE, and each option as the
same build with the 8-row block; big_seat_stats on the Rev3 plan. Inputs: the W2–4 T-70 frames
(`~/moneygate/weeks.json`), the writers above at this commit.

## The frozen rule (per option, TDBLOCK8 and MTDBLOCK8)

**NOT ENTERED** if either holds:
1. the block's P(≥ 1 big) is below LIVE's (strictly) in 2 or 3 of the 3 weeks;
2. the pooled expected-big-seats ratio, Σ e_big(block) / Σ e_big(LIVE) over W2–4, is below 0.80 (his tolerance).

**Otherwise ENTERABLE, and it is his call**, disclosed in these words: *"in-sample (the rule was found on these weeks'
winners); no out-of-sample evidence; the week he enters is its first out-of-sample week."*

**Choosing among options:** all options are reported side by side every week, beside MBLOCK8 and LIVE. Picking the best
of three on three in-sample weeks is selection, and its edge is overstated twice (the rule's discovery and the choice);
the decision sheet says so.

## After

Study 38 needs no amendment: 6e treats any live source generically (QA0 carries the armed block; "QA0 − NOTERM (the live
block: <file>)" is the weekly record from W5). Friday's rehearsal runs the chosen file; Saturday he chooses matchup / TD /
combined / none.
