# Preregistration: study 24, a cap on the #1-total game's QBs and a distinct-lineup deal, on the operator's real Week-5 plan (DRAFT 2026-10-06)

**Status: DRAFT.** It is frozen, with the reader's sha256 recorded here, after three things:
- the one-slate smoke (§2a);
- the operator's answer on the expected-seat tolerance (§5, GUARD 2);
- his answer on whether the two MLB satellites and the Showdown satellite count as big seats (§4).

Both answers come before the binding census and before any scored bank. Later changes are dated deviation notes at the
end. The reviewer freezes it and reads first. The laptop reviews the design and re-runs the frozen reader before the
LEDGER row. Study list item 24 (`reports/2026-10-04-post-week4-study-list.md`).

**The operator (10-05, verbatim):**
- "If i could win one 333, 555 or 4444 or $500 in the milly, the week is a success and i wouldnt care if i lost all the
  $20 milly tickets. Winning 4-5 $20 milly tickets is not enough to make the week successful, but 20 of them would be."
- "Id prefer to enter one in each of several $5 and $17 contests rather than multiple so there is a possibility of
  winning more than one rather than putting all my money into 2-3 contests."
- Earlier: "If there is disagreement, perhaps we can try both approaches."

## 1. What is known (descriptive; motivates, is not evidence)
- **Concentration on one game.**
  - Week 4 dealt 62% of our entries to QBs from the #1-total game.
  - On the laptop's W4 replay, WS + Fantasy Points projections still put about half there (52–53%, 11 of 21 entries).
  - The 2026 W1–4 Millionaire field puts about 1 in 5 there (18–22%).
  - When that game disappoints, most of the book loses together. That costs the operator's goal, at least one big seat,
    more than it costs average tickets.
- **Study 1 (Addendum 122)** capped each game's share of rows holding ≥ 3 of its players, on the house shape. It read
  NO DIFFERENCE. The cap acted as variance shaping:
  - fewer zero-ticket slates (0.319 → 0.236);
  - a better worst decile;
  - a slightly lower ceiling (best ≥ 194: 0.292 → 0.250).

  That is the trade this study measures under the operator's utility. Study 1 used a different shape (the house shape,
  not WS), a different cap (rows, not dealt entries; all players, not the QB) and a ticket endpoint at p79–p91 lines.
- **Study 1b (Addendum 123):** an entry-level PLAYER cap FAILED, costing 2.4–4.3 points of mean finish. Exposure caps
  can cost real quality. GUARD 1 is there for that.
- **Study 18 (Addendum 129):** WS PASSED at draft A's shallow lines (p79–p91). The real Week-5 plan's lines are much
  deeper (p95.7–p99.94). WS itself is not re-tested here; the reader prints WS's absolute numbers beside the
  differences.
- **The head layout** deals the four best rows to two contests each. The operator's 24 entries therefore use 20 distinct
  lineups. The laptop flagged (10-05) that his "one in each of several … a possibility of winning more than one" reads
  either way:
  - head keeps the best rows in more contests (more expected seats from the best lineups);
  - sequential gives every entry its own lineup (less shared risk, but four weaker rows).

  So both deals are arms.

## 2. Arms (one co-run per slate-bank)
Common to every arm, study 18's WS builder unchanged:
- K = 105; the objective is each player's simulated mean over the dual-law selection worlds;
- **no ownership term in any arm**;
- ≤ 7 players shared with every earlier row; a player banned at 52 rows, a DST at 26;
- MAX_PER_GAME 4; a $49k floor; skill players with simulated mean < 1.0 dropped;
- the shape: QB + ≥ 1 WR/TE, bring-back optional, ≤ 3 players from the QB's game, and a second-game pair from any other
  game;
- the small-contest overlap limit M 5 / ceiling 10.

N = the plan's 24 mean-track entries, so the cap is floor(0.25 × 24) = **6 entries**.
- **WS (control):** study 18's WS book, head layout.
- **G1 (DECISION):** WS, plus an entry-weighted budget on the QBs of the slate's #1-total game.
  - The game is ranked by pre-lock `game_total`, using study 1's `game_ranks`.
  - w_k = the plan entries the head layout deals to rank k, before the overlap limit.
  - Solve k bans that game's QBs when the dealt count so far + max(w_k, 1) > 6.
  - Rows the plan never deals (w_k = 0) are banned once the budget is spent, so overlap replacements cannot leak it.
  - Only the QB is capped. That game's other players stay available as bring-backs and second-game pairs.
- **SEQ (DECISION):** WS's same book, dealt by `ENTER_LAYOUT=sequential`, so every entry gets its own row (24 lineups).
  It is an existing production layout; no code change.
- **GA (EXPLORATORY):** the same 6-entry budget for EVERY game's QBs.
- **G1S (EXPLORATORY):** G1's budget computed on the sequential deal's weights, dealt sequentially (the cap and the
  distinct deal together).

## 2a. Smoke observations before the freeze (mechanics only; one slate, 2023 W9, throwaway bank 1406)
(To be filled from `~/s24-panel/smoke/` before the freeze: rows, distinct dealt rows, #1-game QB entries, QB games, the
busiest QB game's share, banned solves, identical-to-WS, and wall time. Outcomes are not read.)

## 3. Why these endpoints
The operator's utility is P(≥ 1 big seat in the week), not total tickets. The primary is computed EXACTLY per
slate-bank from realized scores:
- each dealt entry's percentile F in the sampled field;
- the contest's size N and seats S;
- m = his entries in that contest.

For each contest, P(at least one of his entries in the top S) = P(Bin(N − m, 1 − F_best) ≤ S − 1). The opponents are
independent field draws given the slate's realized scores, so contests are independent given the scores. P(≥ 1 big seat)
= 1 − ∏ over big contests (1 − P_c). The correlation the cap is meant to break, entries that lose together, shows up
ACROSS slates. Ties count as losses.

## 4. Panel and plan
- **Slates and banks:**
  - the 53 `k1` slates of 2022 (17), 2023 (18) and 2024 (18) with Millionaire ownership;
  - **fresh banks 1417/1418**: no bank-label use in either repository's branch scan, 10-06; the same scan finds 1415 and
    1406;
  - the smoke and the binding census on throwaway bank 1406.
- **The plan is the operator's REAL Week-5 plan.**
  - Source: built from his DraftKings entries export (`DKEntries-Week5.csv`, 10-05 21:03) by production's own
    `contests_from_entries.py` and `dk_contest_details.py`, at the integration head. Only public contest details were
    fetched, and only the export's four header columns were read.
  - Study copy: `~/s24-panel/plan-week5-s24.json` (private), sha256
    `ab6da4963245779c154ba525c668e154c63939638eda3db91322b23f6fc3713c`; 20 contests, 24 entries, 20 head rows.
  - Production's own contests.json (the laptop, `~/week5-sunday/contests.json`, sha256 `2ffbcfe8b6ade499…`) has the same
    20 contest ids in the same order, with the same entries and tracks. Only the Milly's line differs: production uses
    the cash line (76.86); the study uses the $500+ line, the top 95 of 161,764 (p99.9413).
- **Contests (size, seats, his entries):**

  | contests | fee | size | seats | entries each | big |
  |---|---|---|---|---|---|
  | 1 Millionaire | $20 | 161,764 | 95 ($500+) | 2 | yes |
  | 2 $4,444 MEGA sats | $13 | 402 | 1 | 1 | yes |
  | 1 $4,444 Showdown (10-12) sat | $13 | 402 | 1 | 1 | yes (operator to confirm) |
  | 3 $555 sats | $9 | 72 | 1 | 1 | yes |
  | 3 $555 sats | $6 | 108 | 1 | 1 | yes |
  | 1 FFWC $490 qualifier sat | $8 | 72 | 1 | 1 | yes |
  | 3 $333 Wildcat sats | $5 | 79 | 1 | 2 | yes |
  | 3 $333 Wildcat sats | $17 | 23 | 1 | 1 | yes |
  | 2 MLB $333 Perfect Game sats | $5 / $17 | 79 / 23 | 1 | 1 | yes (operator to confirm) |
  | 1 SUPERSat to the $20 Milly [25x] | $5 | 118 | 25 | 1 | **no** |

  "Big" = a prize worth $333 or more: his list ($333, $555, $4,444, $500+ in the Milly), plus the $490 qualifier. If he
  excludes the MLB or Showdown seats, the flags change and so does the plan's sha, before the freeze.
- **Field caveat.** Every contest's opponents are modelled as draws from the Millionaire field at the slate's realized
  Millionaire ownership. Real satellite fields are smaller and sharper: the regulars are 54% of FFWC-qualifier entries,
  28% of the $4,444 Showdown satellite's and 11% of the $555 satellites' (`reports/2026-10-05-max-entry-regulars.md`).
  The absolute probabilities are therefore optimistic. The ARM − WS differences are the decision quantities.

## 5. Endpoints and decision rule (each decision arm against WS)
- **PRIMARY = P(≥ 1 big seat) per slate**, ARM − WS, paired. Season-clustered bootstrap (slates resampled within
  season), B 20,000, seed 20261006. **Two-sided 0.975 per decision arm** (0.95 split over G1 and SEQ).
- **GUARD 1:** mean dealt-entry finish (the share of the field each entry beats), ARM − WS. The one-sided 0.975 lower
  bound must exceed −0.015, study 18's margin.
- **GUARD 2, the operator's tolerance:** expected big seats, the ARM / WS ratio of slate means, as a point estimate, must
  be ≥ 1 − TOL.
  - TOL is the operator's answer to "how many expected big seats would you give up for a better chance of one?"
    (asked 10-05). The reviewer recommended 0.20.
  - **TOL = (his answer, recorded verbatim here before the freeze)**; the reader's `TOL` constant matches it.
- **Verdicts:**
  - **PASS** = primary lower bound > 0, at most one of the three season means < 0, and both guards hold;
  - **FAIL (guard)** = the primary would pass but a guard fails (each failing guard named);
  - **WORSE** = upper bound < 0;
  - **DEAD LEVER** = dealt identically to WS on > 80% of slate-banks;
  - **NO DIFFERENCE** otherwise.

  The guards are printed for every arm in every branch.
- **Secondaries:**
  - expected big seats;
  - P(≥ 2 contests with a big seat), which is his "more than one";
  - tickets at each contest's line;
  - slates with P(≥ 1 big seat) < 1%;
  - best ≥ 200;
  - the worst-decile slate's entry finish;
  - the SIMULATED P(≥ 1 big seat) over the run's own worlds (in-sample; never decision-bearing);
  - the dealt entries' shape and QB-game spread: #1-game share, top-4 share, QB games, the busiest QB game's share,
    QB + 1, bring-back, second-game pair, players in the QB's game, games used, the top player's entry share.
- **Power:** not estimable before outcomes. The per-slate P(≥ 1) is heavy-tailed, since a few slates where the book's
  best row is near the top carry most of it. With 53 slates, an effect of a few points of P(≥ 1) will likely read NO
  DIFFERENCE. That is a legitimate result, not a failure.

## 6. What a verdict can do
- **G1 PASS:** a reason to offer a reversible Week-5 trial.
  - The laptop builds the same budget in production's `mix_rows`, with a parity test against this module, call for call
    on a frozen frame. The reviewer reviews it before Friday.
  - The operator decides. Rollback = the budget off: the WS book is byte-identical when off.
- **SEQ PASS:** a reason to offer `ENTER_LAYOUT=sequential` for the week's deal (an existing layout; no code). The
  operator decides.
- **Both pass:** G1S (exploratory) informs whether to combine them. A combination is not a verdict.
- **NO DIFFERENCE with both guards intact:** a legitimate reason to choose either as a risk preference, stated as such.
  It is not a PASS.
- **WORSE / FAIL (guard):** the arm is not offered.

## 7. Integrity
- **Code:** nfl2 `production/s24-qb-game-cap-20261006` (cut from study 18's `0738a41`):
  - `experiments/s24_qb_game_cap.py`;
  - `scripts/s24_drive.py`;
  - **`scripts/s24_report.py` (the reader)**;
  - `scripts/s24_census.py`;
  - `tests/test_s24_qb_game_cap.py`. It holds 14 tests, including the contest arithmetic against brute force, the
    budget at every solve, both layouts, mechanics-only census reads, and the reader's printed levels against this
    text.

  The shas are recorded here at the freeze.
- **Order:**
  1. this freeze;
  2. the BINDING outcome-blind census on bank 1406: all 53 slates, mechanics only (rows, distinct dealt rows, #1-game QB
     entries against the cap, QB games, banned solves, identical-to-WS, short books), reviewed by both parties;
  3. the scored run on 1417/1418 (nothing changes after it starts);
  4. a confirmatory mechanics-only census from the scored rows, committed before the reader;
  5. the reviewer's read;
  6. the laptop's byte-identical re-run;
  7. the LEDGER row and an Addendum.
- **Transfer caveat:** the panel has no ownership term and no Fantasy Points projections (FP is not available for
  2022–24). The live book is WS + FP + the ownership term, so any trial is "arm + FP + term".
- **Schedule:** freeze and census Tuesday 10-06; scored run and read by Wednesday 10-07; the operator decides Friday
  10-09. No production change is made before his yes. The production checkout stays clean from Saturday's arming until
  Sunday 15:30.

---
