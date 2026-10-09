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
