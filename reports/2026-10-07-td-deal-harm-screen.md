# Dealing the book by the lineups' market touchdowns: a frozen HARM SCREEN before the W2–4 re-deal (2026-10-07)

**Status: FROZEN 2026-10-07, before any re-deal number exists** (the laptop; wording as the TD block's screen, the
reviewer's). It is the in-sample check of the exact production input beside study 52, the reviewer's harness test of the
same idea (DEAL_TD vs DEAL_LIVE on simulated TDs, 2023–24 read + 2022 go / no-go; DEAL_PROJ as its control), which is the
decision-bearing test.

## Why

The operator (10-07): "if we haven't already, I'd like to try sorting our lineups by projected touchdowns for the lineup."
Not tried before (both ledgers checked); the nearest is study 48b (Addendum 153), the same book re-dealt by a score that did
predict at the row level: NO DIFFERENCE (+0.008 [−0.030, +0.044], expected big seats ratio 0.899). A re-deal moves wins
between contests and does not make them, so a small or null effect is the likeliest reading.

## The deal (exact)

- The book: the LIVE arm of the bonus-blocks replay (`~/.cache/laptop-agent/rehearsal/bonus_blocks_replay.sh`, the live
  Week-5 settings on W2–4 real fields): its first 26 rows (book.csv), the spares untouched.
- **DEAL_TD:** the 26 rows re-ordered by the lineup's market touchdowns, highest first, ties keeping the book's order;
  lineup touchdowns = the sum over its rostered players of `td_prob` from `scripts/td_value_block_file.py` (the mean implied
  `player_anytime_td` probability over books in the last snapshot strictly before each week's Saturday 10:00 CT -- the
  TD block's timing; every rostered player with a price, QB included, the DST and unpriced players 0).
- **DEAL_PROJ (exploratory control):** the same rows re-ordered by the lineup's projection (the book's proj_sum), highest
  first. If DEAL_TD ≈ DEAL_PROJ the TD idea is projection order.
- Each deal goes through production's head layout (`enter_layout write --layout head`, Rev3) and is scored as the block
  replays (big_seat_stats on the Rev3 plan).

## The frozen rule (DEAL_TD only)

**NOT ENTERED** if either holds:
1. DEAL_TD's P(≥ 1 big) is below LIVE's (strictly) in 2 or 3 of the 3 weeks;
2. the pooled expected-big-seats ratio, Σ e_big(DEAL_TD) / Σ e_big(LIVE) over W2–4, is below 0.80.

Otherwise it passes this screen only; whether it is a candidate is decided by study 52 (SUPPORTED only if PASS and not
contradicted). Disclosure, in these words: *"in-sample (the operator's idea, tested on weeks already seen); no
out-of-sample evidence from this check; study 52 carries the decision."*

## Block interaction (the reviewer's rule)

One construction change per week: if a term block is armed for W5, a supported TD deal is a W6 candidate. If both are ever
armed together, the re-deal applies only to the 18 non-block rows over their own positions (the block keeps its ranks),
tested in that form first; no untested combination.
