# Addendum: the ownership term at 100 main rows, the routing, and the spread dealing

Reviewer, 2026-09-29 18:44 CDT. Branch `review/ownership-term-20260929`. Follows
`reports/2026-09-29-ownership-term-week4-arming.md` (merged on integration as `7d9712d9`).

It answers the laptop's 17:59 ask (hold the deep-line supersats on the main book) and bears on production's 18:37
entry (`ENTER_LAYOUT=spread`, integration `f0da76d5`), whose rehearsal is due tonight.

## 0. Summary

| Question | Answer |
|---|---|
| Hold the deep-line supersats on the main book (`--hold-on-main`)? | **Reviewer: yes.** Optimizer rows clear the deep line at 1.8–2.0× the field's rate; mean-selected rows were 1.02× in L13; the laptop's break-even is about 1.19×. |
| Does the ownership term hold when the main book grows to 100 rows? | **Yes.** +0.17 and +0.18 sd per lineup, 24–12 slates in both banks, both seasons. The same as at 36 rows. |
| Does the term hurt the deep-line contests? | No sign of it. Their tickets are 2.3× and 2.6× the field's with the term against 2.0× and 1.8× without. Neither interval excludes zero. |
| Enter the spread dealing as built? | **No.** It gives contests of equal size the same rows, so it enters 37 distinct lineups where the head layout enters 100, and it does not reduce empty weeks. |
| Is there a spread that works? | One offset per contest. Empty weeks fall from 25–30% to 11–21%, with the same expected tickets. It needs building and an end-to-end rehearsal first. |

**The operator's words, for the record.** On 2026-09-29 he answered "I'll go with your suggestions" to the message
recommending tilt 0.20, and "Do as you suggest" to the message recommending the routing and offering this addendum.
The plan file is his, so the laptop confirms the contest list with him when it applies `--hold-on-main`.

## 1. The term at 100 main rows

- **Shape.** The plan as filed on 09-28, with the deep-line supersats held on the main book, gives 100 main rows and
  5 sleeve rows under the head layout.
- **Harness.** The arming report's: K = 100, exposure cap 50, DST cap 25 (the tool's `int(share × K)`), banks 1240 and
  1241, 36 slates.
- **Arms.** The plain book against the lag + LineStar blend at tilt 0.20.

### 1.1 All 100 rows

| Objective | Bank | Points vs field | p80 | p89 | p95 | p99 | p99.8 | Paired gain (sd) | 90% interval | Slates up–down | 2023 | 2024 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| plain | 1240 | +2.0 | 1.16× | 1.23× | 1.34× | 1.94× | 2.22× | | | | | |
| term 0.20 | 1240 | +5.6 | 1.35× | 1.43× | 1.51× | 2.08× | 1.94× | +0.171 | [+0.051, +0.290] | 24–12 | +0.201 | +0.140 |
| plain | 1241 | +0.7 | 1.06× | 1.14× | 1.33× | 1.67× | 1.67× | | | | | |
| term 0.20 | 1241 | +4.8 | 1.29× | 1.41× | 1.60× | 2.31× | 2.92× | +0.182 | [+0.038, +0.322] | 24–12 | +0.254 | +0.111 |

The term gives up 1.5 projected points per row (127.9 → 126.4) and shares 12 of 100 rows with the plain book.

### 1.2 Under the head layout, by contest class

Each contest is scored at its own line on its own rows. Results are multiples of what the field would expect from the
same entries.

| | Bank 1240 | Bank 1241 |
|---|---|---|
| Shallow-line contests, plain | 1.03× | 1.15× |
| Shallow-line contests, with the term | 1.35× (+0.32 [−0.11, +0.75]) | 1.10× (−0.05 [−0.40, +0.28]) |
| Deep-line supersats, plain | 2.02× | 1.79× |
| Deep-line supersats, with the term | 2.31× (+0.30 [−0.40, +0.96]) | 2.58× (+0.79 [−0.03, +1.75]) |
| Slates with no deep-line ticket, plain → with the term | 64% → 50% | 67% → 50% |

### 1.3 By row block (the laptop asked L20 for this cut)

| Rate at p99 | Bank | Rows 1–4 | 5–12 | 13–36 | 37–68 | 69–100 | All |
|---|---:|---:|---:|---:|---:|---:|---:|
| plain | 1240 | 1.39× | 1.74× | 1.39× | 1.48× | 2.95× | 1.94× |
| term 0.20 | 1240 | 1.39× | 2.43× | 1.39× | 2.00× | 2.69× | 2.08× |
| plain | 1241 | 2.08× | 0.69× | 2.31× | 1.04× | 2.00× | 1.67× |
| term 0.20 | 1241 | 0.69× | 1.74× | 1.85× | 2.00× | 3.30× | 2.31× |

| Rate at p99.8 | Bank | Rows 1–36 | 37–100 | All |
|---|---:|---:|---:|---:|
| plain | 1240 | 0.39× | 3.26× | 2.22× |
| term 0.20 | 1240 | 0.39× | 2.82× | 1.94× |
| plain | 1241 | 1.16× | 1.95× | 1.67× |
| term 0.20 | 1241 | 0.39× | 4.34× | 2.92× |

These blocks are small. Rows 1–4 hold 1.4 expected hits at p99 per bank, and the whole book holds 7 at p99.8. The
blocks show no pattern that repeats across the banks.

### 1.4 The patched tool at 100 rows

Run on the two archived Week-3 run dirs with the Week-4 pinned clone (`--entries 100 --tail-sleeve 5`):

| Check | Result |
|---|---|
| Rows solved, plain and with the term | 100 and 100, all distinct; 19 shared |
| Caps | exposure 50 of 50 used; DST 25 of 25 used |
| Sleeve rows with the term against without | identical, in order |
| `book_main_control.csv` against the plain run's main | identical, in order |
| Time for the whole union step | 36 s without the term, 61 s with it |

## 2. The routing

**Reviewer's yes**, for these reasons:

1. The capped optimizer's rows clear the deep line at 1.8–2.0× the field's rate here (plain, K = 100) and 1.77× in L13
   (K = 144).
2. Mean-selected rows, which fill most of the 85-row sleeve, were 1.02× in L13. The laptop's break-even for those
   contests is about 1.19×.
3. With the routing, the term covers every main row. Nothing in the arming report's steps changes; the caps scale with
   K.

Two caveats:

- The armed sleeve is not purely mean-selected, because its first rows are optimizer rows. L19's S_NONE arm measures
  the armed sleeve over its own 85 rows. If that rate is near the main book's, the routing matters less.
- The union step takes about a minute at 100 rows with the term. Wednesday's smoke should time it at the week's real
  K.

## 3. The spread dealing as built

**Finding.** `_spread_ranks` gives every multi-entry contest of n entries the ranks `int((j + 0.5) * K / n)`. Two
contests with the same n therefore take the same rows.

| Shape | Layout | Rows spanned | Distinct rows holding an entry | Multi-entry contests whose rows equal another's |
|---|---|---:|---:|---:|
| plan as filed | head | 36 | 36 | 0 of 8 |
| plan as filed | spread, as built | 34 | 16 | 8 of 8 |
| deep-line supersats on the main book | head | 100 | 100 | 0 of 12 |
| deep-line supersats on the main book | spread, as built | 96 | 37 | 12 of 12 |
| deep-line supersats on the main book | spread, one offset per contest | 100 | 80 | 0 of 12 |

**What it costs.** The table covers all main-track entries, both banks pooled, on the same books.

| Shape | Objective | Layout | Tickets, × the field's | Slates with no ticket |
|---|---|---|---:|---:|
| as filed (K 36) | plain | head | 1.16× | 30% |
| | | spread, as built | 1.23× | 36% |
| | | spread, one offset per contest | 1.18× | 14% |
| as filed (K 36) | term 0.20 | head | 1.30× | 22% |
| | | spread, as built | 1.37× | 20% |
| | | spread, one offset per contest | 1.40× | 14% |
| routed (K 100) | plain | head | 1.21× | 29% |
| | | spread, as built | 1.44× | 25% |
| | | spread, one offset per contest | 1.31× | 21% |
| routed (K 100) | term 0.20 | head | 1.40× | 25% |
| | | spread, as built | 1.38× | 28% |
| | | spread, one offset per contest | 1.54× | 11% |

For the deep-line supersats alone (routed shape), slates with no ticket:

| Objective | Head | Spread, as built | Spread, one offset per contest |
|---|---:|---:|---:|
| plain | 66% | 76% | 62% |
| term 0.20 | 50% | 81% | 53% |

- Expected tickets differ little between the layouts, and the differences are within the noise.
- The as-built spread leaves the share of empty weeks where it was, and raises it at the deep line. Contests of equal
  size win or lose together, which is the opposite of what the dealing is for.
- With one offset per contest, the empty weeks fall at both shapes and under both objectives.

**The change.** For the g-th of G contests with n entries:

```python
out[i] = [int((j + (g + 0.5) / G) * K / n) for j in range(n)]
```

Rows may still coincide between contests of different sizes. The all-head groups (n ≤ 2) already spread as one
block and need no change.

**Recommendation for Week 4.** The head layout stands. The spread enters only if the offset version is built and
rehearsed end to end at the exact ladders by Thursday noon. The winners study's §4.2 compared one contest's top N rows
with N spread rows. It did not deal several contests at once, so it did not show this.

## 4. Limits

- The same 36 slates and the two banks the arming report used. L20 (fresh banks, K = 36) reads tonight.
- The field is the sampler's. Whether the real satellites' fields are harder is G3, still open.
- Ticket counts at the deep line are small, and no ticket interval here excludes zero.
- LineStar's recorded projections are not provably pre-lock, so the term's rows are an upper bound.

## 5. Reproduction

`reports/lab-handoffs/2026-09-29-ownership-term/`: `01_panel_term.py` now reads `KROWS` and `WORKERS`;
`06_read_k100.py` gives §1; `07_read_layouts.py` gives §3. The plan file is read from `PLAN_FILE` and is never printed.
