# Fixed-book screen of one-setting construction levers, Weeks 2–4 (2026-10-06)

Run 2026-10-06 15:24–15:32 CT by the outside reviewing agent at the operator's request ("yes, please do the replay"),
as item 2 of `reports/2026-10-06-outside-review-suggestions-for-high-scoring-lineups.md` §8. It is the money-path
rule's test ("a fixed-book replay before entering a rule"), not a frozen study: three weeks, no preregistration,
seven levers screened at once, so a lever that reads ahead here is a candidate for the operator's "preference with
no measured cost" class and for a paper column beside study 38, never a verdict. Aggregates only; no private data.

## Method (the tilt replay's harness, one union per arm)

Exactly `~/.cache/laptop-agent/rehearsal/b_w4_term_replay.sh` (the replay that decided the Week-5 tilt), with the
extra arguments varied per arm. Each arm: production `scripts/union_reselect.py` at integration `5533c1c2` in a
detached worktree, the pinned lab clone `f69598b` on `PYTHONPATH`, the ARMED Week-5 settings at K 26 (`--main mix`,
portfolio `mix`, Rev3 plan `8625de0e…` with the head layout, `--main-qb-cap-rows 5 --main-qb-cap-k 26`, tilt 0,
`--main-cap-share 0.5`, `--main-dst-cap 0.25`, `--max-per-game 4`, `--min-salary 49000`, `--mean-max-shared 7`),
built on each week's REAL T−70 inputs; then `enter_layout write … --layout head` (Rev3); then each dealt row's share
of that week's REAL Millionaire field beaten (ties lose) → the study harness's `big_seat_stats` per Rev3 contest
(P(≥ 1 big seat), expected big seats; "big" = the Millionaire's top 95 and first place in the one-seat satellites
of 23–402 entries) and the mean entry percentile (guard 1's quantity).

- Week 4: FP's projections (`proj_fp-w4.csv`, sha `8bba650e…`), the W4 T−70 run `20261004T155026918221Z-32cdb61`.
  The `base` arm reproduces the tilt replay's no-term book to four decimals (0.0336 / 0.5014), which validates the
  harness.
- Weeks 2–3: OUR served projections (FP exists only from Week 4), the settlement copies under
  `~/moneygate/inputs/runs` (T−70 `20260920T155005557498Z-2dc116c`, `20260927T155027472554Z-65305f5`).
- Week 1 could not be replayed: its Saturday supply copies predate the dose sidecars the union resolves by.

Arms (each one argument changed from the armed settings): `ms6` / `ms5` = `--mean-max-shared 6` / `5` (every row may
share at most 6 / 5 of 9 players with every earlier row; the live value is 7); `qb4` / `qb3` = `--main-qb-cap-rows
4` / `3`; `cap35` = `--main-cap-share 0.35` (a player in at most 9 of 26 rows; study 36's lever); `ms5qb4` = both;
`blend` (Week 4 only) = `--proj-source` 0.5 FP + 0.5 props-implied (the frame's `market_points` where it is a real
prop number, 184 of 316 players); `mpg3` = `--max-per-game 3` is INFEASIBLE under the production stack (QB+2 plus a
bring-back is four from one game) and built nothing in any week.

## Results

P(≥ 1 big seat) / mean entry percentile / best row (DK points) / QBs / games / distinct players in the 26 rows.
Max exposure stayed at the 13-row cap in every arm except `cap35` (9).

| Arm | W2 (ours) | W3 (ours) | W4 (FP) | Ahead of base on P(≥1) |
|---|---|---|---|---|
| base (armed) | .931 / .439 / 179.5 / 8 / 12 / 44 | .009 / .509 / 170.0 / 6 / 11 / 39 | .034 / .501 / 164.0 / 8 / 10 / 41 | — |
| **ms5** | .908 / .400 / 185.2 / 8 / 13 / 50 | **.310** / .526 / 170.0 / 10 / 13 / 50 | **.343** / .565 / 176.1 / 10 / 11 / 46 | 2 of 3 |
| ms6 | .817 / .425 / 174.3 / 8 / 13 / 48 | .291 / .512 / 170.0 / 8 / 12 / 46 | .132 / .537 / 175.5 / 9 / 11 / 42 | 2 of 3 |
| qb4 | .903 / .453 / 179.5 / 9 / 12 / 47 | .010 / .509 / 162.7 / 8 / 11 / 40 | .041 / .460 / 165.0 / 10 / 11 / 43 | 2 of 3 (tiny) |
| qb3 | .897 / .489 / 179.5 / 10 / 13 / 49 | .026 / .508 / 162.7 / 11 / 12 / 49 | .059 / .529 / 165.0 / 10 / 11 / 45 | 2 of 3 (small) |
| cap35 | .0002 / .505 / 157.1 / 7 / 13 / 46 | .009 / .447 / 170.0 / 8 / 12 / 45 | .001 / .610 / 158.6 / 8 / 12 / 44 | 0 of 3 |
| ms5qb4 | .070 / .450 / 165.5 / 9 / 13 / 49 | .488 / .526 / 170.0 / 12 / 13 / 53 | .305 / .576 / 177.0 / 10 / 11 / 47 | 2 of 3 |
| blend | — | — | .0001 / .442 / 148.6 / 9 / 11 / 45 | 0 of 1 |

Study 38's guards applied to `ms5` over the three weeks (descriptive; the frozen rule needs four live weeks):
guard 1, the mean of the weekly mean-entry-pct differences = (−.039 + .017 + .064) / 3 = **+.014** (> −.015 holds);
guard 2, expected big seats summed, 1.657 + .318 + .374 = 2.35 vs base 1.843 + .009 + .034 = 1.89, ratio **1.24**
(≥ .80 holds). Where the base was already near-certain (Week 2, a 179-point row), `ms5` stayed near-certain (.908)
with a better best row (185.2, the only row in any arm inside the real top 1%) and a lower mean row.

Week-4 rows behind the numbers (rank in the 161,762-entry field): base 164.0 (~7,227th), 163.5, 151.4; `ms5`
176.1 (~2,930th), 175.5 (~3,070th), 151.4, 151.1. No arm reached the real top 1% (182.8) in Week 4; the big-seat
probability there comes from ~176-point rows placed in the one-seat satellites.

## Reading

1. **The pairwise shared-player limit is the lever that spreads without paying.** At 5 shared, the rows must differ
   by four or more players, so the book covers more games (13 / 13 / 11 vs 12 / 11 / 10) and more QBs (8 / 10 / 10 vs
   8 / 6 / 8) while the best players stay in half the book (max exposure 13 in every arm). The exposure cap (`cap35`)
   does the opposite: it removes the best players from the top rows, and P(≥ 1 big) collapses in all three weeks
   even where the mean percentile improves. That is study 36's measured cost, reproduced on real fields, and it says
   the lever studied so far was the wrong one: cap the overlap between rows, not the exposure of players.
2. **`ms6` is the conservative form** (ahead in the same two weeks, a smaller Week-2 cost); `ms5qb4` adds variance
   (Week 2 collapses to .070) and is not a cleaner package than `ms5` alone. The QB caps move little.
3. **The props blend is not a Week-5 candidate**: on the one FP week it was far worse on every endpoint. This agrees
   with `reports/2026-10-06-props-and-winners.md` (props add nothing beyond FP) and goes further for the book.
4. **What this is not.** Three weeks, two under projections we no longer play, seven arms screened together: the
   chance that some arm reads ahead in two of three weeks by luck is high. What makes `ms5` more than that is the
   size of the Week-3 and Week-4 gaps (30× and 10×, driven by rows 6–12 points better than the base's best), the
   held guards, and the mechanism, which is the published one for top-heavy portfolios (an upper bound on overlap
   with earlier entries; Hunter, Vielma and Zaman 2016).

## What it would take for Week 5 (the operator's decision; the reviewer's code)

`--mean-max-shared 7` is hard-coded in `scripts/sunday_build_host.sh` (line 283), so this is a one-line code change
(an env value, default 7) plus the arm script's env and Friday's rehearsal, not a setting. The adoption-track package:
class S; mechanism and change as above; primary utility P(≥ 1 big seat); evidence this file; earliest usable week 5
if merged and rehearsed Friday, else 6; unchanged comparison = the armed book, which study 38 already builds and
scores every week; monitoring = a `ms5` paper column beside study 38 from Week 5 whatever is entered; rollback =
the env value. If it is not entered, the paper column still accrues the weeks.

## Reproduction

Scripts and the two score files are copied to `reports/2026-10-06-lever-screen-scripts/` (`screen_w4_levers.sh`,
`screen_w23_levers.sh`, `rerun_blend.sh`, `score-w4.json`, `score-w2-w3.json`). Scratch runs with every union
log, book and layout: `~/rehearsals/screen-20261006T202423Z` (W4) and `~/rehearsals/screen123-20261006T202951Z`
(W2–3); a first W1–3 attempt (`screen123-20261006T202625Z`) was killed after the Week-1 dose refusal hung at
interpreter exit. The detached worktrees were removed after this record.
