# Studies 77 and 79 on his real book: what the production options change (W4 inputs, outcome-blind, 2026-10-09)

**Why:** studies 77 (QB alone, Addendum 175) and 79 (one pass catcher per team, Addendum 177) are tonight's two
enterable leans, and each has a production option built and reviewed, both UNMERGED and default off:
- `--mix-qb-alone-rows N` (`review/qb-alone-flag-20261008` @ `3a9327e1`);
- `--mix-one-catcher-rows N` (`review/one-catcher-flag-20261009` @ `3ecdc6db`).

The harness books are not his book (the simulator's means against Fantasy Points' projections), so this checks what each
option does to his real Week-5-style book.

**What ran:** union runs on the Week-4 inputs with the Week-5 arming (mix, rr, overlap 4, QB cap 5, FP projections, the
cheap +2 block), through the tracked `reports/2026-10-08-s71-flag/w4_union_run.sh`, from each option's branch. Script:
`flag_w4_check.sh`.
- **OFF:** must reproduce the known W4 book `a4ab2839…` byte for byte (the known-answer gate); it did every time.
- **ON:** the option.

Only the books' composition and FP projections are read: no points, ranks or contest results. Each position's dealing
under his real Rev6 plan uses production's head layout, `enter_layout.assign_ranks`. The big flags come from the
converted `plan-week5-rev6-s24.json`. Counts only: no contest names, no stakes.

**Results** (verbatim in the `OUTPUT-*.txt` files):

| Option | Rows ruled | Book rows changed | What changed | FP projection / row |
|---|---|---|---|---|
| `--mix-qb-alone-rows 3` (77) | 3 of 3 | 24 of 26 (path dependence) | QB-alone rows 0 → 3, at book positions 3 / 7 / 13 (the harness's positions). They are dealt into 3 / 2 / 2 contests, 2 / 1 / 1 of them big. None has an RB teammate | 143.70 → 143.81 |
| `--mix-one-catcher-rows 8` (79, the decision arm) | 8 of 8 | **0 of 26: byte-identical to OFF** | nothing. The book's 7 rows with a same-team WR / TE pair away from the QB sit at positions 1 (A1), 8 (C), 14 (B), 17 (C), 22 (B), 23 (C), 24 (A1). Its B / C ones come from B / C solves after the first 8, which the rule does not reach | 143.70 → 143.70 |
| `--mix-one-catcher-rows 14` (every B / C solve; study 79's exploratory ONEPC_ALL) | 14 of 14 | 8 of 26 | pair rows 7 → 1 (the one left, at position 21, is a QB + 2 row) | 143.70 → 143.73 |
| `--mix-flex-wr-rows 3` (75's dose in study 83; the flag at `09e93be1`, run 05:17) | 3 of 3 | 26 of 26 | flex WR / TE / RB 1 / 14 / 11 → 4 / 11 / 11; non-QB pair rows 7 → 6 | 143.70 → 143.39 (−0.31) |

**Reading:**
- 77's option transfers as tested: its three rows land where the harness put them, in big contests, at no projection
  cost.
- 79's decision arm (8 rows) can be a **no-op** in his real book; on W4 it was. In the harness it changed about 2.1 of
  its 8 rows on average.
- The version that binds in his book (all B / C rows) was tested only as an exploratory arm (+2.1, 2022 +0.8), which is
  not decision-bearing.
- If he chooses 79, Friday's A3 run on the Week-5 inputs must show that the 8-row rule changes his book; otherwise it
  changes nothing that week.
- One week's inputs. Descriptive only.

## Addendum (02:53 run): study 81's exploratory NOTE5K_ALL on his real book

**Why:** study 81's exploratory arm (no TE priced ≥ $5,000 on any book row; Addendum 179, +4.7 points on the read, one
of about 35 comparisons tonight) is a paper-arm candidate. What would it do to his real book?

**How:** there is no production flag for it. The 5 W4 TEs priced ≥ $5,000 (`dk_status-te5k-out-w4.csv`) were marked
OUT through the union's own `--dk-status` path, the same runner and gate as above (OFF = `a4ab2839`). This bans them on
every row. It also removes them from the spares and the T-70 replacement pool, which a snapshot paper arm would not;
that does not affect the 26 book rows. Verbatim: `OUTPUT-no-te5k-all-rows.txt`.

| | OFF | No TE ≥ $5,000 |
|---|---|---|
| Rows holding a TE ≥ $5,000 | 11 of 26 | 0 of 26 |
| Book rows changed | | 24 of 26 |
| FP projection per row | 143.70 | 142.94 (−0.76) |
| Flex WR / TE / RB | 1 / 14 / 11 | 4 / 7 / 15 |
| QB + own-TE stack rows | 12 | 10 |

**Reading:**
- In his real book the cost is more than twice the harness's (−0.76 against −0.33 per row), because his FP book leans
  harder on those TEs.
- The flex moves mostly to RBs.
- A paper arm would measure the trade on new weeks; this check sets its expected size.

## Addendum (06:02 runs): the study 83 / 84 combinations on his real book

The same runner and gate (OFF = `a4ab2839`). The code is a local test merge of integration + `review/combo-flag-20261009`
(`f6fdee34`) + `production/c0-wiring-20261009` (`c116e98d`), as `ad1d9e84`; its 29 reader modules give 507 passed,
3 skipped, rc 0. The TE ban is via `--dk-status`, as above. Verbatim: `OUTPUT-combo83-triple.txt`,
`OUTPUT-combo81-four-rules.txt`.

| | OFF | COMBO (C0 3 + one catcher 14 + flex 3) | COMBO81 (COMBO + no TE ≥ $5,000) |
|---|---|---|---|
| Rules ruled / plain | | 3 / 14 / 3 ruled, 0 plain | all ruled, 0 plain |
| QB-alone rows | 0 | 3 (positions 3 / 7 / 13; big) | 3 (3 / 7 / 13; big) |
| Rows with a non-QB same-team WR / TE pair | 7 | 2 | 1 |
| Flex WR / TE / RB | 1 / 14 / 11 | 3 / 13 / 10 | 6 / 5 / 15 |
| Rows with a TE ≥ $5,000 | 11 | (not read) | 0 |
| QB + own-TE rows | 12 | (not read) | 9 |
| FP projection per row | 143.70 | 143.60 (−0.10) | 143.17 (−0.53) |
| Book rows changed | | 26 of 26 | 26 of 26 |

The A3 combination check's logic (`w5_combo83_union_check.sh`) PASSES on the COMBO run.

## Addendum (07:06–07:11 runs): his experiment books 85 / 87 and the $7,900 cap (86), the parts a ban can emulate

The same runner and gate (OFF = `a4ab2839`); players marked OUT through `--dk-status` (files beside). The WR-count, top-WR
and flex rules of 85 / 87 cannot be emulated this way, so these are the bans' part only.

| Ban set (W4) | Players OUT | Rows changed | FP projection per row | Flex WR / TE / RB |
|---|---|---|---|---|
| 85's bans: TE > $5,000, DST > $3,000 | 4 TE + 7 DST | 24 of 26 | 142.97 (−0.73) | 3 / 6 / 17 |
| 86 CAP7900: any player > $7,900 (exact) | 4 (WR $9,100 / $8,100, RB $8,400 / $8,200) | 17 of 26 | 143.52 (−0.18) | 1 / 13 / 12 |
| 87's bans: QB outside the top-4 games + 85's bans | 16 QB + 4 TE + 7 DST | 24 of 26 | 142.11 (−1.59) | 7 / 5 / 14 |

The read-only counts on the OFF book:
- **85:** 5 of 26 rows already meet all four rules.
- **86:** 11 of 26 rows hold a player > $7,900.
- **87:** 9 of 26 rows have a QB outside the top-4 games; 4 lack the QB's own top WR; 14 have ≥ 1 WR ≤ $4,500.

87's QB restriction leaves 8 QBs for 26 rows under the cap of 5, the likely source of most of its cost.

## Addendum (08:04–08:05 runs): study 87's no-caps book on his real book

The same runner and gate (OFF = `a4ab2839`). The caps were lifted with `--main-qb-cap-rows 26 --main-cap-share 1.0
--main-dst-cap 1.0`: the QB cap of 5 rows, the player cap of 13 rows and the DST cap of 6 rows. These are the caps
the operator removed for study 87 (overlap 4 kept). The second run adds 87's bans through the same `--dk-status` file
as above. Verbatim: `OUTPUT-nocap.txt`, `OUTPUT-book87-bans-nocap.txt`. The concentration counts below come from the
books' player ids only.

| | OFF (caps on) | NOCAP (no bans) | 87's bans, caps off |
|---|---|---|---|
| Rows changed | | 12 of 26 | 24 of 26 |
| FP projection per row | 143.70 | 144.66 (+0.96) | 143.25 (−0.45; −1.41 vs NOCAP) |
| Most rows for one player | 13 | 21 | 20 |
| Most rows for one QB / distinct QBs | 5 / 9 | 6 / 12 | 8 / 6 |
| Most rows for one DST / distinct DSTs | 6 / 7 | 8 / 7 | 11 / 5 |
| Rows with a non-QB same-team pair | 7 | 2 | 7 |
| Flex WR / TE / RB | 1 / 14 / 11 | 1 / 12 / 13 | 4 / 11 / 11 |

**Reading:**
- Lifting the caps alone raises the FP projection (+0.96 per row), as removing a constraint must. One player then sits
  in 21 of 26 rows.
- With 87's bans and no caps, the cost against the capped live book falls from −1.59 to −0.45 per row. The caps were
  most of the bans' real-book cost, as the 07:11 note expected.
- Against its own no-caps baseline, the bans still cost −1.41 per row. Study 87 measures
  that part (its prereg reads each rule arm against NOCAP).

## Addendum (12:39 run): his package, the 35% cap + the ownership cap, on his real book

His 10-09 package (HANDOFF `5380e0e7`): the player cap 0.35 PLUS each skill player capped at floor(26 × (FP's projected
ownership, rescaled to 800% over skill players, + 15 points) / 100) rows. The run used the same runner and gate (OFF =
`a4ab2839`), the outside reviewer's flag at `680533c8` (union_reselect `3ff8f0d5`) and W4's real FP ownership export
(`~/week4-sunday/ownership_fp-20261004t1550z-d800-32cdb61.csv`, sha `0ec90a6b`, captured 15:50Z pre-lock). The arguments
were `--main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source <that file> --main-own-cap-fallback-share 0.5`.
Verbatim: `OUTPUT-pkg035-own15.txt`.

| | OFF (today's book) | The flat 35% (10:25) | The package |
|---|---|---|---|
| FP projection per row | 143.70 | 141.39 (−2.31) | 140.76 (−2.94) |
| Rows changed | | 17 of 26 | 17 of 26 |
| Most rows for one player | 13 | 9 | 9 |
| Players in ≥ 40% / ≥ 30% of rows | 7 / 10 | 0 / 14 | 0 / 10 |
| Distinct players | 48 | 49 | 54 |
| Skill players over their ownership cap | 10 | | 0 |
| Flex WR / TE / RB | 1 / 14 / 11 | 0 / 16 / 10 | 0 / 17 / 9 |

- **The receipt:** own_cap_source applied; factor 1.0128 (FP's skill total 789.9%); 292 of 292 skill players named;
  coverage 1.0; the smallest cap 3 rows. own_cap: 26 ruled solves, 0 re-solved without the bans, 3.0 players banned per
  solve on average (max 11).
- **Reading:** the rule binds on his real book: 10 of his players sit above their ownership cap today. It spreads the book
  more than the flat 35% does (54 distinct players against 49). It costs about 0.6 projected points per row more than the
  flat cap.

## Addendum (13:03 run): the ownership cap at +10 points (study 90's condition 5, a W6 candidate)

The same runner, gate and inputs as the package run above, with `--main-own-cap-delta 10` in place of 15 (`680533c8`;
`~/rehearsals/flagcheck-pkg035own10-20261009T180347Z`). This is a check, not an arming: W5 stays at +15.

| | OFF | The package at +15 (armed) | At +10 |
|---|---|---|---|
| FP projection per row | 143.70 | 140.76 | 139.89 (−0.87 vs +15) |
| Rows changed | | 17 of 26 vs OFF | 17 vs OFF; 16 vs +15 |
| Players in ≥ 30% of rows | 10 | 10 | 7 |
| Distinct players | 48 | 54 | 58 |
| The smallest ownership cap (rows) | | 3 | 2 |
| Players banned per solve (mean / max) | | 3.0 / 11 | 7.3 / 23 |
| Skill players over the +10 cap | | 18 | 0 |

The tighter cap binds much more than +15 (18 players in the armed book sit above it) and costs another 0.9 projected
points per row. Applied; 0 re-solves.

## Addendum (13:36 run): his test 2 on top of the package (one TE + one sub-3% player per lineup; study 91)

The same runner and gate, the package's arguments plus `--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3` (the
outside reviewer's flag `e8c63263`; `~/rehearsals/flagcheck-pkgTE1LOW1-20261009T183613Z`). This is a check, not an arming:
it goes live only if study 91 passes his "better on both draws" rule.

| | OFF | The package (armed) | Package + TE1_LOW1 |
|---|---|---|---|
| FP projection per row | 143.70 | 140.76 | 140.00 (−0.76 vs the package) |
| Rows changed | | 17 of 26 vs OFF | 21 of 26 vs the package |
| TEs per row | 1.54 | 1.65 | 1.00 |
| Skill players under 3% FP ownership per row | 0.08 | 0.12 | 0.23 |
| Flex WR / TE / RB | 1 / 14 / 11 | 0 / 17 / 9 | 7 / 0 / 19 |
| Distinct players | 48 | 54 | 57 |

The receipt: the rules applied on all 26 solves, 0 re-solved; 163 of the pool's 235 skill players count as low-owned. On
his real book the TE half is the live effect: no TE in the flex; RBs and WRs take it. The low-ownership half never binds
(the TE rule itself pulls cheap low-owned players in, to 0.23 per row, still under the limit of one).

## Addendum (18:33 run, written 18:34): study 93's ONECATCH on top of the armed version (his "Live W5 if built in time")

His 10-09 decision (HANDOFF `90e8470c`) puts ONECATCH live in W5 if every check passes: at most one WR / TE per team on
every QB + 1 (B / C) book row, including the cheap block's.
- **The code under test:** the outside reviewer's flag `--mix-one-catcher-all` (review/one-catcher-armed-20261009 @
  `c391fbd0`, union_reselect `ce55a465`) and the laptop's wiring (production/onecatch-wiring-20261009 @ `f483644c`), merged
  on integration `90e8470c` as `93d58464`.
- **The runner:** `flag_w4_check_armed.sh` (beside this file), with two known-answer gates.
  - OFF reproduces `a4ab2839`.
  - ARMED (the package + te1_low1, the flag absent) reproduces the 13:36 armed book `e1c8f9f7` byte for byte. With the
    option off, the new code therefore changes nothing.
  - Then ON = ARMED + `--mix-one-catcher-all`.
- Outcome-blind: book composition and FP projections only. Verbatim: `OUTPUT-onecatch-all-armed.txt`.

| | ARMED (package + te1_low1) | + ONECATCH |
|---|---|---|
| Rows with two WR / TE of one team away from the QB | 5 (all B / C) | 0 |
| Rows changed | | 19 of 26 (A1 5, A2 3, B 5, C 6) |
| FP projection per row | 140.00 | 139.94 (−0.06) |
| TEs per row | 1.00 | 1.00 |
| Flex WR / TE / RB | 7 / 0 / 19 | 8 / 0 / 18 |
| Distinct players | 57 | 52 |

- **The receipt:**
  - one_catcher_source applied; 24 teams.
  - The rule ran on all 14 B / C solves, live and cheap block, with 0 re-solved without it; pair_rows_bc 0.
  - pair_rows_book 12 counts the A1 / A2 rows' own QB stacks, as designed.
  - The row rules still ran on all 26 solves, 0 re-solved.
- **Reading:**
  - The rule binds on his real book: 5 rows held such a pair; none do after.
  - It reaches 19 rows through the shared caps and the overlap limit (path dependence, as in the harness, where 11.7 of
    26 rows were shared).
  - It costs almost nothing in projection, and the book uses 5 fewer distinct players.
  - The changed rows include 16 positions dealt into a big contest under his W5 plan.

## Addendum (20:09 run, written 20:12): RBMATE4 on top of ONECATCH (his "Try live W5 if built"; study 96 read it PAPER ONLY)

- **The code under test:** the outside reviewer's flag `--mix-rb-mate-c 4` (review/rb-mate-c-20261009 @ `4caff46d`) and the
  laptop's wiring (production/rbmate-wiring-20261009 @ `77bd55c5`), merged on integration `48955ffd` as `5c66f156`.
- **The runner:** `flag_w4_check_armed2.sh`. Gates: OFF == `a4ab2839`; ARMED (the package + te1_low1 + ONECATCH, the option
  absent) == the 18:33 ONECATCH book `293d9465`. Both reproduced byte for byte.
- Verbatim: `OUTPUT-rbmate-c4-on-onecatch.txt`.

| | ARMED (+ ONECATCH) | + RBMATE4 |
|---|---|---|
| Rows with the QB's own RB | 4 | 6 |
| Rows changed | | 20 of 26 |
| FP projection per row | 139.94 | 139.87 (−0.07) |
| Flex WR / TE / RB | 8 / 0 / 18 | 10 / 0 / 16 |
| Distinct players | 52 | 55 |

- **The receipt:** rb_mate_source applied; 59 (QB, own RB) pairs; slots C 2 / 6 / 10 / 14, all 4 ruled, 0 re-solved without
  the floor. ONECATCH still 14 / 14 ruled with 0 B / C pairs.
- **Status:** study 96 read ONECATCH + RBMATE4 PAPER ONLY by his rule (−0.5, negative on both draws). RB_MATE_C stays 0; this
  check only proves the flag on his book in case a game-script version (study 97) is chosen.

## Addendum (20:10 run, written 20:12): study 95's shape arms built on the armed version (his morning percentages)

His words (HANDOFF `543f2695`): "we're going to decide the percentages of each of the successful shapes first thing in the
morning".
- **Setup:** production's `--mix-cell-quotas` now takes a cell at 0 (production/cell-quotas-zero-20261009 @ `21fa9d29`,
  parser only; the reviewer approved it).
- **The runner:** `quota_w4_builds.sh`, using study 95's exact quota floats. Gates: ARMED, and the default quotas spelled
  out ("A1=0.3,A2=0.14,B=0.28,C=0.28"), both == `293d9465`.
- Verbatim: `OUTPUT-shape-arms-quotas.txt`.

| Arm | Rows A1 / A2 / B / C | FP per row | Distinct players | Rows changed | QBs |
|---|---|---|---|---|---|
| ARMED (live) | 8 / 4 / 7 / 7 | 139.94 | 52 | | 8 |
| NO_A1 | 0 / 6 / 10 / 10 | 140.25 | 53 | 24 | 9 |
| NO_A2 | 9 / 0 / 9 / 8 | 140.02 | 55 | 20 | 10 |
| NO_B | 10 / 6 / 0 / 10 | 139.95 | 53 | 24 | 10 |
| NO_C | 10 / 6 / 10 / 0 | 139.80 | 59 | 16 | 10 |
| ONLY_A1 | 26 / 0 / 0 / 0 | 139.38 | 60 | 24 | 10 |
| ONLY_A2 | 0 / 26 / 0 / 0 | 139.60 | 52 | 26 | 9 |
| ONLY_B | 0 / 0 / 26 / 0 | 140.14 | 56 | 26 | 9 |
| ONLY_C | 0 / 0 / 0 / 26 | 140.36 | 51 | 26 | 9 |

- **The cell counts** equal the reviewer's known answers from study 95's census (the same allocate / interleave functions).
- **No arm passed a row to A1.** ONECATCH ruled every B / C solve in each arm.
- **Reading:** every arm builds on his real book, and the projection moves by at most 0.5 per row. Whatever percentages he
  picks can be armed through MIX_QUOTAS once the parser merges.

## Addendum (22:47 run, written 22:48): RBMATE4_FAVHI on top of ONECATCH (study 97's one passing game-script arm)

- **The code under test:** the outside reviewer's `--mix-rb-mate-scope favhi` (review/game-script-scopes-20261010 @
  `60f6dbe9`) and the laptop's narrowed wiring (production/scope-wiring-20261009 @ `2bd5bbff`), merged on integration as
  `de1a7700`.
- **The runner:** `flag_w4_check_armed2.sh`. Gates: OFF == `a4ab2839`; ARMED + ONECATCH == `293d9465`; both reproduced.
- Verbatim lines: `OUTPUT-rbmate-favhi-on-onecatch.txt`.

| | ARMED (+ ONECATCH) | + RBMATE4_FAVHI |
|---|---|---|
| Rows with the QB's own RB | 4 | 7 |
| Rows changed | | 20 of 26 |
| FP projection per row | 139.94 | 139.83 (−0.11) |
| Distinct players | 52 | 52 |

- **The receipt:** scope favhi applied. The expected winners of upper-third-total games on W4's slate: BUF, HOU, SF (8
  QB–own-RB pairs). Slots C 2 / 6 / 10 / 14 were all ruled, 0 re-solved. ONECATCH stays 14 / 14.
- **Status:** off (RB_MATE_C=0) until his morning decision, after study 99's confirmation on a fresh draw.

## Addendum (10-10 01:55 run, written 01:59): OVERLAP3 on the armed version (study 100's pick; study 101 rechecking)

- **The run:** FRIDAY_HEAD `5faf2f05` with `--mean-max-shared 3` (today 4); the runner `flag_w4_check_armed2.sh`.
  - Gates: OFF == `a4ab2839`, ARMED + ONECATCH == `293d9465`.
  - Verbatim: `OUTPUT-overlap3-armed.txt`.

| | ARMED (+ ONECATCH, overlap 4) | Overlap 3 |
|---|---|---|
| Rows changed | | 25 of 26 |
| Distinct players | 52 | 60 |
| FP projection per row | 139.94 | 139.92 (−0.02) |
| Flex WR / TE / RB | 8 / 0 / 18 | 9 / 0 / 17 |
| Cells A1 / A2 / B / C | 8 / 4 / 7 / 7 | 8 / 4 / 7 / 7 |

- **Reading:**
  - The tighter overlap rebuilds almost the whole book (25 of 26 rows) at almost no projected cost, with 8 more distinct
    players.
  - ONECATCH and the row rules still apply on every solve.
- **To arm:** MAX_SHARED=3 in the arm (check_week_runtime accepts 3–8), plus the reviewer's study 38 6x (the paper arms are
  defined at overlap 4–7). Only on his decision after study 101.

