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
