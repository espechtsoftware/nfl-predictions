# Preregistration: study 24, an all-distinct deal and, on it, a per-game QB cap (no game in more than a quarter of the entries), on the operator's real Week-5 plan (FROZEN 2026-10-05)

**Status: FROZEN 2026-10-05** (late evening CDT), before the binding census and before any scored bank. Three things
came first:
- the one-slate smokes (§2a: three runs, the last on the final code, both paths, with the census and the reader
  exit-checked and the reader's output unread);
- the operator's tolerance (§5, GUARD 2);
- his definition of a big win (§4).

Later changes are dated deviation notes at the end. The reviewer froze it and reads first. The laptop reviewed the
draft (10-05: the plan check passed; its port-sizing point is in §6) and re-runs the frozen reader before the LEDGER
row. Study list item 24 (`reports/2026-10-04-post-week4-study-list.md`).

**The operator (10-05, verbatim):**
- "If i could win one 333, 555 or 4444 or $500 in the milly, the week is a success and i wouldnt care if i lost all the
  $20 milly tickets. Winning 4-5 $20 milly tickets is not enough to make the week successful, but 20 of them would be."
- "Id prefer to enter one in each of several $5 and $17 contests rather than multiple so there is a possibility of
  winning more than one rather than putting all my money into 2-3 contests."
- Earlier: "If there is disagreement, perhaps we can try both approaches."

## 1. What is known (descriptive; motivates, is not evidence)
- **Concentration on one game** (the smoke, §2a, shows WS can concentrate on a game OTHER than the #1 total).
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
Each arm is read against its REFERENCE.
- **WS (reference):** study 18's WS book, head layout (the four best rows in two contests each; 20 lineups for 24
  entries).
- **SEQD (DECISION, vs WS): all distinct.** WS's same book, with every one of the 24 entries holding its own lineup.
  This is the operator's choice (10-05, the laptop's question "A 'sequential' layout makes all 24 entries different
  lineups. Which do you want?"; his answer, verbatim: "All distinct (Recommended)").
  - It deals the sequential layout's ranks, then applies the small-contest overlap limit (M 5).
  - Each replacement is drawn from rows BEYOND the layout's ranks, in solve order, unused anywhere in the plan, each
    used once.
  - A contest with no fitting unused row falls back to production's limit (counted by the census).
  - Production's sequential deal cannot do this: its limit replaces within the layout's own ranks (0..23), so a row
    can repeat across contests. Adopting SEQD therefore needs a small, reviewed enter_layout change with a parity test.
- **G25S (DECISION, vs SEQD): the per-game cap on the all-distinct deal.** WS plus an entry-weighted budget on EVERY
  game's QBs: no game's QBs in more than 6 of the 24 dealt entries. It is dealt all-distinct, which is the package he
  would actually run.
  - w_k = the plan entries the sequential layout deals to rank k (one each for ranks 0–23).
  - Solve k bans a game's QBs when that game's dealt count so far + max(w_k, 1) > 6.
  - Rows the plan never deals (w_k = 0) are banned from a game once its budget is spent. The all-distinct deal's
    replacements come from those rows, so the cap holds exactly (smoke: 6 of 24).
  - Only the QB is capped. Other players from a capped game stay available as bring-backs and second-game pairs.
- **G25 (EXPLORATORY, vs WS):** the same budget on the head layout's weights, dealt by the head layout. Production's
  overlap limit runs after the budget and can move a 2-entry contest's second entry onto a row whose game is already at
  the cap (smoke: 8 of 24).
- **SEQ (EXPLORATORY, vs WS):** WS's book dealt by production's `ENTER_LAYOUT=sequential` as it stands (22 distinct
  lineups on the smoke slate). It is the no-code fallback for this week.
- **G1 (EXPLORATORY, vs WS):** the head-layout budget for the #1-total game's QBs only. The game is ranked by pre-lock
  `game_total`, using study 1's `game_ranks`. This was the first draft's decision arm; see §2a.

## 2a. Smoke observations before the freeze (mechanics only; one slate, 2023 W9, throwaway bank 1406)
Both paths ran: mechanics only, then the full outcome path. Each took about 95 s, and the rows and deals were identical
across the two. The smoke used the first draft's arm names; they are mapped here. Shares are of the 24 DEALT entries.
Outcomes were not read.

| arm (smoke name) | distinct lineups dealt | QB games | busiest QB game | #1-total game's QB entries | solves with a ban |
|---|---|---|---|---|---|
| WS | 19 | 3 | **21 of 24 (0.875)** | 0 | — |
| G25 (GA) | 20 | 5 | 7 of 24 (0.292) | 3 | 102 |
| SEQ | 21 | 3 | 20 of 24 (0.833) | 0 | — |
| G1 | identical to WS | 3 | 0.875 | 0 | 0 |

- **The first draft's decision arm was the wrong cap.** On this slate WS put 21 of 24 entries on ONE game's QBs, and
  that game was NOT the #1-total game. The #1-game cap therefore did nothing (dealt identically to WS). The operator's
  concern, and the laptop's question to him ("to keep one game from carrying half your entries"), is concentration on
  ANY one game. So the per-game cap (G25) became the decision arm and the #1-game cap moved to exploratory. This was
  decided on mechanics alone, before any outcome existed for these arms.
- **The cap leaked by one entry.** The Milly's head rows 0 and 1 shared more than 5 players, so the overlap limit
  replaced rank 1 with rank 5, whose game was already at the cap. That is disclosed in §2 and kept for production
  parity.
- **SEQ still reuses rows.** The overlap limit reused rows across contests (21 distinct lineups, not 24).
- **Build time:** about 95 s per slate-bank, so the 106 scored slate-banks take about 10 minutes on 24 workers.
- **The re-smoke on the revised plan** (Rev1, the same slate and bank, both paths) showed:
  - WS: 19 distinct lineups, busiest game 21 of 24;
  - SEQD: 24 distinct, 0 fallbacks, busiest 21 of 24;
  - SEQ: 22 distinct;
  - G25 (head): 19 distinct, busiest **8 of 24** (two overlap moves onto capped games; Rev1 has five 2-entry contests);
  - G25S: 24 distinct, busiest **6 of 24**, 5 QB games;
  - G1: identical to WS.

  The cap leaks under the head deal but holds under the all-distinct deal. So the decision structure became the
  package the operator would run: all-distinct vs head (SEQD vs WS), then the cap on top (G25S vs SEQD). G25 moved to
  exploratory. This was decided on mechanics alone, before any outcome existed for these arms.
- **Binding-census checks before the scored run** (a failure is a design question at that review, not after scoring):
  - SEQD and G25S: 24 distinct lineups dealt on every slate-bank, or the fallbacks counted and ≤ 5% of governed
    contests;
  - G25S's busiest QB game ≤ 6 of 24 on every slate-bank (≤ 7 where a fallback occurred);
  - G25S dealt identically to SEQD on ≤ 80% of slate-banks; SEQD never identical to WS;
  - no short books.

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
- **The plan is the operator's REAL, REVISED Week-5 plan.**
  - History: he withdrew the two MLB satellites (10-05, verbatim: "I didnt mean to do an mlb one.  Im withdrawing.")
    and added two entries to a $19 SUPERSatellite to the $555 ("added 2 entries into a $19 super satellite to the 555,
    which seems like a good way to go").
  - Source: built from his revised DraftKings entries export (`DKEntries-Week5-Rev1.csv`, 10-05 21:23) by production's
    own `contests_from_entries.py` and `dk_contest_details.py`, at the integration head. Only public contest details
    were fetched, and only the export's four header columns were read.
  - Study copy: `~/s24-panel/plan-week5-rev1-s24.json` (private), sha256
    `f34f3a0023a649f2270a4c7c0d592ced54ed03d73ec3458cae6d04a3d32982bc`; 19 contests, 24 entries, $256; head layout 20
    rows (rows 0–3 in two contests each), sequential 24 ranks; cap floor(0.25 × 24) = 6.
  - Production's own contests.json is rebuilt by the laptop from the same export, and the ids, order and entries are
    checked against this copy before the freeze. The Milly line differs deliberately: production uses its cash line;
    the study uses the $500+ line, the top 95 of 161,764 (p99.9413).
  - The first export's copy (`plan-week5-s24.json`, sha `ab6da496…`) was used only by the one-slate smoke (§2a), which
    reads mechanics only.
- **Contests (size, seats, his entries):**

  | contests | fee | size | seats | entries each | big |
  |---|---|---|---|---|---|
  | 1 Millionaire | $20 | 161,764 | 95 ($500+) | 2 | yes |
  | 2 $4,444 MEGA sats | $13 | 402 | 1 | 1 | yes |
  | 1 $4,444 Showdown (10-12) sat | $13 | 402 | 1 | 1 | yes |
  | 3 $555 sats | $9 | 72 | 1 | 1 | yes |
  | 3 $555 sats | $6 | 108 | 1 | 1 | yes |
  | 1 $555 SUPERSatellite [2x] | $19 | 68 | 2 | 2 | yes |
  | 1 FFWC $490 qualifier sat | $8 | 72 | 1 | 1 | yes |
  | 3 $333 Wildcat sats | $5 | 79 | 1 | 2 | yes |
  | 3 $333 Wildcat sats | $17 | 23 | 1 | 1 | yes |
  | 1 SUPERSat to the $20 Milly [25x] | $5 | 118 | 25 | 1 | **no** |

  "Big" = every prize except a $20 Millionaire ticket. His words (10-05): "any one except a $20 milly ticket count as
  big wins to me". In this plan that means every contest except the $5 SUPERSat to the $20 Milly. The Milly itself
  counts at a $500+ finish, his own threshold ("$500 in the milly").
- **Field caveat.** Every contest's opponents are modelled as draws from the Millionaire field at the slate's realized
  Millionaire ownership. Real satellite fields are smaller and sharper: the regulars are 54% of FFWC-qualifier entries,
  28% of the $4,444 Showdown satellite's and 11% of the $555 satellites' (`reports/2026-10-05-max-entry-regulars.md`).
  The absolute probabilities are therefore optimistic. The ARM − reference differences are the decision quantities.

## 5. Endpoints and decision rule (each decision arm against WS)
- **PRIMARY = P(≥ 1 big seat) per slate**, ARM − its reference (SEQD − WS; G25S − SEQD), paired. Season-clustered bootstrap (slates resampled within
  season), B 20,000, seed 20261006. **Two-sided 0.975 per decision arm** (0.95 split over SEQD and G25S).
- **GUARD 1:** mean dealt-entry finish (the share of the field each entry beats), ARM − its reference. The one-sided 0.975 lower
  bound must exceed −0.015, study 18's margin.
- **GUARD 2, the operator's tolerance:** expected big seats, the ARM / reference ratio of slate means, as a point estimate, must
  be ≥ 1 − TOL.
  - TOL is the operator's answer to "how many expected big seats would you give up for a better chance of one?"
    (asked 10-05). The reviewer recommended 0.20.
  - **TOL = 0.20.** He answered twice on 10-05, consistently:
    - typed as "Other" to the laptop's question (21:06 CDT): "judge the entry cap by chance of at least one big win
      (seats of $333+ or $500+ Milly), not average tickets, accepting up to ~20% fewer expected big seats if average
      finish holds";
    - to the reviewer: "Ill trust your opinion on accepting 20% fewer.  One big win is sufficient and any one except a
      $20 milly ticket count as big wins to me".

    The reader's `TOL` constant is 0.20. "If average finish holds" is GUARD 1.
- **Verdicts:**
  - **PASS** = primary lower bound > 0, at most one of the three season means < 0, and both guards hold;
  - **FAIL (guard)** = the primary would pass but a guard fails (each failing guard named);
  - **WORSE** = upper bound < 0;
  - **DEAD LEVER** = dealt identically to its reference on > 80% of slate-banks;
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
  - the dealt entries' shape and QB-game spread: the busiest QB game's share, QB games, #1-game share, top-4 share,
    QB + 1, bring-back, second-game pair, players in the QB's game, games used, the top player's entry share.
- **Power:** not estimable before outcomes. The per-slate P(≥ 1) is heavy-tailed, since a few slates where the book's
  best row is near the top carry most of it. With 53 slates, an effect of a few points of P(≥ 1) will likely read NO
  DIFFERENCE. That is a legitimate result, not a failure.

## 6. What a verdict can do
- **SEQD PASS:** a reason to offer the all-distinct deal.
  - The laptop builds it in production's enter_layout with a parity test against `distinct_deal`, call for call. The
    reviewer reviews it.
  - If it is not ready and reviewed by Saturday's arming, SEQ (exploratory, no code) is the nearest available deal,
    offered with its own read stated.
  - The operator decides.
- **Porting either deal needs spare rows.** Production's union builds exactly the rows the layout needs (24 for
  sequential on Rev1), so the all-distinct deal has nothing beyond the layout's ranks to draw from. A port builds
  K = rows needed + S spares. S is sized from the binding census's maximum replacement rows per slate-bank plus a
  margin. vet_replace and audit_build_levers must accept unused spare rows. For G25S the budget must also govern the
  spares (max(w, 1)); otherwise the replacements leak the cap. (The laptop's review, 10-05.)
- **G25S PASS:** a reason to offer the per-game budget ON the all-distinct deal.
  - The laptop builds the budget in production's `mix_rows` (WS portfolio) with a parity test against `capped_book`,
    call for call on a frozen frame. The reviewer reviews it before Friday.
  - It needs the all-distinct deal too: G25 under the head deal leaks the cap (§2a).
  - The operator decides. Rollback = the budget off: the WS book is byte-identical when off.
- **NO DIFFERENCE with both guards intact:** a legitimate reason to choose either as a risk preference, stated as such.
  This matters for SEQD, which is already his stated preference. It is not a PASS.
- **WORSE / FAIL (guard):** the arm is not offered, and the operator is told plainly what his preference costs.

## 7. Integrity
- **Code:** nfl2 `production/s24-qb-game-cap-20261006` @ `109ca2b` (cut from study 18's `0738a41`):
  - `experiments/s24_qb_game_cap.py`, sha256 `c72bc6f80fbf911d6f807525843f31e7b1642d9a8f22e1b7d14453a1a6a72b8f`;
  - `scripts/s24_drive.py`, `a2f515d6cc3b3784a8ad4068d45adb09b96b25f57d04baeb2699ca06ab900d46`;
  - **`scripts/s24_report.py` (the reader), sha256
    `e1a4968ae3eea7a8a382b53d98ee01392016f5c6af5ece5a00f99d591dfdd933`**;
  - `scripts/s24_census.py`, `e97f0591e5d42eabe03ab668eaf49ee8c5638593d361d36777b2e00695f85074`;
  - `tests/test_s24_qb_game_cap.py`, `d79210831baa86b06e17ba27b39ac610a155e8017cd8186350d79bcc7480e7f3`. It holds
    15 tests, green together with study 18's 12: the contest arithmetic against brute force; the budget at every solve;
    both layouts and the all-distinct deal (incl. its fallback); mechanics-only census reads; the reader's references,
    rules and printed levels against this text; and an end-to-end reader run.
- **Run with:** `PYTHONPATH=<nfl2 worktree>/src:<production worktree at the integration head>/src`, the lab venv,
  `OMP_NUM_THREADS=1`.
- **Order:**
  1. this freeze;
  2. the BINDING outcome-blind census on bank 1406: all 53 slates, mechanics only (rows, distinct dealt rows, the
     busiest QB game's entries against the cap, #1-game QB entries, QB games, banned solves, distinct-deal fallbacks,
     identical-to-reference, short books), reviewed by both parties, with §2a's checks;
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

## Census note 1 (2026-10-05, after the BINDING census, BEFORE any scored bank; sent for the joint review)
The census is recorded at nfl2 `fb4deff`, `results/s24/CENSUS_s24_binding.txt` (sha256 `c21e4363…`; raw bank 1406
`26e475a4…`): 53/53 slate-banks, 0 errors, mechanics only. **Every §2a check passes; no design change.**
- SEQD and G25S deal 24 distinct lineups on every slate-bank (minimum 24), with 0 distinct-deal fallbacks.
- G25S's busiest QB game is ≤ 6 of 24 on every slate-bank (mean 5.92, maximum 6).
- G25S is never dealt identically to SEQD (61% of entries changed); SEQD is never dealt identically to WS.
- No short books in any arm.

Descriptive (mechanics only):
- **Concentration is the rule, not the smoke's exception.** WS's busiest QB game averages 15.5 of 24 entries (maximum
  24); WS uses 3.2 QB games against G25S's 5.8. The #1-total game's share is only 0.21 (G25S 0.17): most of the
  concentration is NOT on the #1 game, which confirms §2a's redesign.
- **The exploratory head-layout cap (G25) leaks:** the busiest game reaches 9, and 33 slate-banks exceed 6. G1 is dealt
  identically to WS on 66% of slate-banks.
- **Port sizing:** replacement rows beyond the layout's ranks average 2.0 (maximum 5). The deepest spare used is 9
  (G25S) or 8 (SEQD), so a production port needs S ≥ 9 spare rows; S = 15 is suggested.
- **Not this study's lever:** the top player's entry share is about 0.98 in every arm, so one non-DST player sits in
  nearly all 24 entries. The game cap does not address it; study 1b's entry-level player cap FAILED on cost
  (Addendum 123).
