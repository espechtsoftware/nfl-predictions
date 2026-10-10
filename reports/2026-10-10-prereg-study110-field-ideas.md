# Preregistration: study 110, four lineup rules from his real Weeks 1–4 fields and a value cap, on his armed Week-5 book, in the harness (DRAFT 2026-10-10)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the lab reviewer's, on
the outside reviewer's briefing (`briefings/2026-week-05/2026-10-10-selection-ideas-from-real-fields.md`), which **the operator
queued for today**: "Read briefings/2026-week-05/2026-10-10-selection-ideas-from-real-fields.md and queue the experiments" (study
list row 93). The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and reproduces. **A pick
goes to study 111** (the fresh-draw check), whose preregistration is committed before this study's READ.
- **Banks and seed (the laptop's full-set check: CLEAN against every used or reserved bank, studies 90–109; the text scan of
  both repositories for the banks, sims bases, fields and seeds: CLEAN, 10-10):** **3580–3591** (set A 3580–3585, set B 3586–3591; sims bases 3630–3641, fields 4280–4291); the reader's bootstrap
  seed **20261153**.

## 1. Why
- The briefing tabulated 1.66 million real lineups from his Weeks 1–4 contests. Five patterns held in all four weeks; four become
  arms here (the fifth, the salary floor, rides with the QB-DST rule as one hygiene arm).
- **They describe winners after the fact.** About 33 features were screened, so a 4-for-4 pattern arises by chance about one time
  in eight. This study is the build-before-the-games test.
- **The prior: NO DIFFERENCE.** None of the four was tested before. The closest reads:
  - study 91's "at most one low-owned player" passed his rule and is live;
  - forcing stacks into the top games was worse (studies 43, 102);
  - the cheap block is a live trial (study 53 read it at about 6% fewer expected big wins);
  - deleting the salary floor read neutral (Addendum 108, August, an old build).
- **VAL4, added before the freeze.** The research page (`briefings/2026-week-05/2026-10-10-winner-patterns-and-next-tests.md`
  §3.2, merged 10-10 05:47) proposed a value cap: the solver fills lineups with the players furthest above their price, and
  his Sunday book averaged 4.5 top-value-tenth players of 8 (17 lineups with 5–7) while no winning group in his real fields
  exceeded 3.9. **The operator's answer, 10-10 morning (in the laptop's session): "Add both today (Recommended)"** — VAL4 here
  and HOT1 in study 109, both before their freezes.
  - **Its prior leans against it:** study 92's shrink toward the salary curve, the stronger form of the same idea, read
    −4.4 points pooled on P(≥ 1 big seat), worse on both draws (A −6.6, B −2.2; lab LEDGER, Addendum 190).

## 2. Arms (`experiments/s110_field_ideas.py`) — the exact definitions (production's switches will match these line for line)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with eight
listed edits, a test asserts it). **Every arm is his armed Week-5 book:**
- the package (the 35% cap with the ownership cap + 15);
- at most one TE and at most one player under 3% per lineup;
- ONECATCH;
- **the adopted FAVHI**: study 96's `combo_rules` with study 97's FAVHI pairs, computed once on the shared pool; s96 / s97 brought
  in byte for byte, `0363a84f…` / `7df6f324…`.

Each arm makes one change:
- **LIVE** — his armed book (checked equal to study 97's RBMATE4_FAVHI on bank 1406, `--ref97`).
- **LOW0** — **the live low rule at its own threshold with the count 1 → 0**: no book row holds a skill player in study 91's
  low-owned set (predicted ownership < 3%, the rescaled blend; no prediction counts as 0%). It is a member bound of 0 in the same
  row-rule tier as the live rule (91's mechanics: infeasible → the solve without the row rules, recorded).
- **QBTOP3** — **every BOOK solve's QB comes from a game among the slate's top-3 pre-lock game totals, ties included**:
  - the pool's median `game_total` per game, over the games with a QB in the pool (study 73's `game_order` grouping);
  - every game whose total is ≥ the 3rd-highest such total; a game without a total is never among them;
  - every other QB is banned on that solve;
  - infeasible (for example when those QBs reach the QB cap) → the solve without the ban, recorded. Spares never.
- **POPPUNT** — **the cheap +2 term only on the sub-$4,000 skill players with predicted ownership ≥ 5%**: study 53's
  `block_term` on that masked set, the cap 2, its coverage gate as usual. The census flags any slate where the block comes out
  empty or unapplied; production would refuse that book.
- **HYGIENE** — **on every BOOK row:**
  - no QB with his own team's DST: one (team T's QB ids + T's DST id, ≤ 1) constraint per team with both in the pool;
  - a minimum lineup salary of **$49,500** (MIN_LINEUP_SALARY for that solve; live is $49,000);
  - infeasible → the solve without them, recorded. Spares never.
- **VAL4** (added before the freeze) — **at most 4 of a book row's 8 skill players (QB / RB / WR / TE) from the top value
  tenth:**
  - value = the harness's player mean per $1,000 of salary;
  - ranked within position among the pool's players with a mean ≥ 3 (pandas `rank(pct=True)`, ties `average`);
  - top tenth = percentile ≥ 0.9. **Disclosed:** the percentile is rank ÷ n, so ≥ 0.9 takes slightly more than a tenth (the top
    2 of 10 players, the top 4 of 30). The census prints the counts by position. **It is the page's own cut** (the screen
    `reports/2026-10-10-winner-patterns/winner_patterns.py`: projection per dollar, `groupby(pos).rank(pct=True)` among skill
    players projected ≥ 3, counted at ≥ 0.9), so the harness tests the rule he approved; the lab reviewer kept it (10-10).
  - The vehicle is a row rule, (the value ids, ≤ 4), in the same tier as te1 / low1 (study 91's mechanics: infeasible → the solve
    without the row rules, recorded); the objective unchanged; spares never.
- **QBTOP3's and HYGIENE's rules sit beneath every rule tier** (entered before `combo_rules`): their constraints are ADDED to
  the tier's own. A solve that cannot be built drops them first: [row rules + rule] → [row rules] → [rule] → none.

## 3. The read (the reader `scripts/s110_report.py`)
- **Study 100's reader with study 106's edits, relabelled** (a test asserts them); study 63's statistics; two draws and pooled;
  two-sided 0.95, B 20,000.
- **Per arm − LIVE:**
  - P(≥ 1 big seat), its guards and verdict;
  - **his rule's line** (better on both draws AND the pooled expected big seats ratio ≥ 0.80);
  - the mean best real lineup points and P(best ≥ 200), printed (information).
- **THE PICK (pre-stated; study 106's tested function `floor_pick`):** among the arms passing his rule (guard 1 printed, not
  gating), the largest pooled gain. None → "keep the live book". **A pick goes to study 111.**
- **Multiplicity:** five arms on the same 36 slates as studies 89–109; about one passes by chance.

## 4. Honest limits and the census
- **The real-field patterns are measured on actual ownership** (W1–W3) **and FP's projected ownership** (W4). The harness's
  rules use its own predicted ownership (the rescaled blend), as the live low rule does.
- **QBTOP3 uses the pre-lock totals the frame carries;** production has the same column.
- **HYGIENE barely touches his real book** (the laptop's outcome-blind check, 10-10: the Week-4 armed book with FAVHI, `c605cab6`,
  FP projections): its lowest lineup is $49,700 (none under $49,500), so the salary floor is a no-op there, and the QB +
  own-DST ban touches 1 lineup of 26. A HYGIENE pass would move about one lineup live. **The $49,500 is kept** (the real-field
  pattern's own threshold, briefing idea 5); raising it until it binds would test a different rule. If the binding census
  shows the floor never binds on the 36 slates, HYGIENE reads as the QB + own-DST ban alone (the lab reviewer's call).
- **VAL4 ranks on the harness's simulated mean;** production would rank on Fantasy Points' projections (the page's definition,
  after the FP override on the T-70 frame). The two value lists differ.
- **The census, per arm:**
  - LOW0's book rows holding a low-owned player (want 0);
  - QBTOP3's book rows with the QB in a top-3 game (want 26) and the QBs it bans;
  - POPPUNT's popular cheap players given the term (an empty block is flagged);
  - HYGIENE's QB + own-DST rows (want 0) and its lowest book salary (want ≥ 49,500);
  - VAL4's top-value players per row and rows with 5+ (want 0), and the top-value players per slate by position;
  - the book rules' ruled / re-solved-plain solves (> 5% plain is flagged);
  - the RB mate's slots; ONECATCH; rows shared with LIVE; LIVE == 97's RBMATE4_FAVHI.
  - Per-slate fields stay outside the blocks the reader compares.
- **Production:** each passing rule needs a default-off switch (the laptop builds them to these definitions after this DRAFT),
  a Week-4 check and study 38's classification before any arming. LOW0 needs a small change: `--mix-max-low-own` takes only 1
  today. VAL4 needs a `val4` row rule in `row_rule_sets` and the value tenth computed in `union_reselect` after the FP override.

## 5. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census, the full path: reader exit and line count only).
- **The smoke (DONE 10-10, 06:24:21–06:26:55 CDT, in the gap the lab reviewer named after the laptop's study-109 census; bank
  1406; 2024 W10, 2023 W11, 2023 W3; PYTHONHASHSEED=0; code `083f11e2`; `results_bank1406.jsonl` `88ae979e…`):**
  - the unit tests 15 passed;
  - every arm 26 book rows within the package's caps; row rules 78 of 78 ruled, none infeasible; RB-mate slots 12 of 12 and
    ONECATCH 42 of 42, none dropped, every arm; **LIVE identical to study 97's RBMATE4_FAVHI, rows and dealing, on 3 of 3**;
  - **each rule binds** (LIVE → the arm): LOW0's rows with a low-owned player 16.33 → 0; QBTOP3's QB in a top-3 game 11.67 → 26
    of 26 (book rules ruled 78, none plain; 31.7 QBs banned per slate); POPPUNT's block applied on every slate (popular cheap
    players given the term 5.7, min 5); HYGIENE's QB + own-DST rows 1.33 → 0 (book rules 78, none plain); VAL4's rows with 5+
    top-value players 13.33 → 0 (top-value players per slate QB / RB / WR / TE 3.0 / 5.3 / 7.3 / 3.7);
  - **one half of HYGIENE did not bind on the smoke slates:** LIVE's lowest book salary was already $49,700, so the $49,500
    floor changed nothing there; the binding census on the 36 slates shows how often it binds;
  - dealt identical to LIVE: 0.000 for every arm but HYGIENE (0.333); none above 0.80. VAL4 shares no row with LIVE; its
    projection per row is within ±0.05 of LIVE's on each slate;
  - the full path: the reader exited 0 (80 lines; 106 two-draw). Only the census, the exit codes and the line counts were
    read.
- **Fixed before any run (found while adding VAL4):** the census's parity expected te1 / low1 on every arm, so LOW0's recorded
  rules would have stopped it at the first row. It now mirrors the module's rules per arm (a test asserts it). The class was
  swept: study 109 had the same defect (fixed); 106 and 112 agree.
- **Code:** nfl2 `production/s110-field-ideas-20261010` @ `083f11e2` (off study 102's frozen `969f4d3d`; VAL4 and the census fix
  at `083f11e2`):
  - `experiments/s110_field_ideas.py` `7cbbd46c…` (pins s95 `46b80611…`, s97 `7df6f324…`)
  - `scripts/s110_drive.py` `e01a9146…`
  - `scripts/s110_census.py` `d8c4bc49…`
  - **`scripts/s110_report.py` (the reader) `79fa2f2e…`** (seed 20261153)
  - `tests/test_s110_field_ideas.py` `c485859b…` (15)
