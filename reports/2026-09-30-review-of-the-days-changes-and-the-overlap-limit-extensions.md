# Review of 2026-09-30's changes, and where L25's overlap limit reaches next

Reviewer, 2026-09-30 16:29 CDT. Branch `review/ownership-term-20260929`. Asked by the operator: "review the recent
changes; L25 is successful; consider related changes for the edge tournaments."

## 0. Summary

| | |
|---|---|
| The day's changes | Sound. One defect caught and fixed before it mattered (the Week-3 ownership label in the TabPFN lags). The live risk left is LineStar's Week-4 fill (41 players Wednesday morning, 100 needed): without it there is no ownership term at all. |
| L25 on my own books | Replicates: the 2–5-entry contests cash 1.22–1.28× as often at M = 5 (L25: 1.36× on the TabPFN book). |
| Thursday's pick, M = 4 or 5 | **M = 5.** M = 4 edges it on the TabPFN book only and loses on the blend and on the no-term book, which are the fallbacks. |
| The extension worth a frozen read now | **The 10-entry contests.** The same limit at M = 5 raises their tickets by 0.28–0.48 of the field's expectation on every objective, and triples the whole-book gain of L25 (§2). One constant in `enter_layout` (`SMALL_MAX_ENTRIES` 5 → 10); the fallback already covers it. |
| Not the 20-entry supersats | Mixed at their deep line: it costs the no-term and blend books and helps only TabPFN. Leave them under the head dealing. |
| The nine single-entry satellites | An overlap limit across them cuts the weeks with no single-entry win (60% → 49% no term; 44% → 38% blend) with tickets flat to up. A Week-5 candidate; it needs a small layout change. |
| A per-contest exposure cap | Weaker than the overlap limit everywhere. Drop it. |

## 1. The day's changes

| Change | Verdict |
|---|---|
| TabPFN armed unconditionally (operator 08:01), loud fallback to the blend; the `lags` defect (Week 3 imported as `milly20`, every `own_l1` NaN) fixed and verified | Right. The lags step now refuses when last week's file is missing, which is the correct failure. |
| "No LineStar capture = no term" (laptop 08:04) | Correct reading of the chain: the blend needs the same capture. The laptop's Thursday/Friday/Saturday LineStar checks are the right watch. |
| Week-5 cloud path built; job untouched until Monday | Correct sequencing under the lane rule. |
| Q11 (production): shape emulation costs mean; cores cost top-1% at equal chalk; styles persist, players do not | Agree with every reading. The small-book result is the one that produced a lever. |
| PREREG-L25 frozen, read SUPPORTED (M = 5: 1.36×, 29–9), re-run byte-identical, merged with a never-refuse fallback, `ENTER_SMALL_MAX_SHARED=5` the Week-4 default | Sound. `_deal_small` replaces a rank with the next fitting rank in solve order, wrapping within the mean ranks; the swap path keeps the published row map; the exposure sheet shows the real rows; `check` recomputes the fallback. The one report-only inconsistency (`exposure_cap_book.py` uses plain head ranks) is disclosed. |
| The smoke moved to Thursday (props 25.6% < 30%) | The week's remaining risk is the Thursday schedule: smoke, R4 rehearsal, the M pick and the freeze in one day. Nothing else should be added after the pick. |
| Late swap paper-only; Thursday entry withdrawn; R4 rehearsal on a scratch copy | Agree. |

## 2. L25's mechanism on the other contest classes

The same books as the TabPFN check, rebuilt at this week's shape: **K = 105**, exposure cap 52, DST cap 26, fresh banks
1320 and 1321, 36 slates, three objectives (no term, the blend at 0.20, TabPFN at 0.20). The installed Rev1 plan's
head layout deals each contest its rows; each contest is scored at its own line. The dealing variants re-deal the same
rows, so nothing about the book changes:

- **L25** — the overlap limit on the 2–5-entry contests, through the tip's own `limit_small_overlap`;
- **2–10** — the same function with the size ceiling raised to 10 entries;
- **all** — the ceiling at 20 (the deep supersats too);
- **singles** — the single-entry contests take rows that pairwise share ≤ M, in rank order, instead of rows 1..n;
- **exposure cap** — a player in at most half of a contest's rows.

Multiples are tickets over the field's expectation for the same entries; "P(cashes)" is the share of contest-slates
with at least one ticket; intervals are 90%, from a slate bootstrap by season, paired against the head dealing.

### 2.1 Per contest class, tickets × field (P(cashes))

| Class | Objective | Head (armed) | L25, M = 5 | L25, M = 4 | 2–10, M = 5 | 2–10, M = 4 | All, M = 5 |
|---|---|---|---|---|---|---|---|
| 2–5 entries | no term | 1.08 (.34) | 1.18 (.43) | 1.08 (.41) | = L25 | = L25 | = L25 |
| | blend | 1.26 (.38) | 1.41 (.46) | 1.44 (.45) | | | |
| | TabPFN | 1.36 (.39) | 1.60 (.50) | 1.69 (.54) | | | |
| 10 entries | no term | 1.13 (.30) | = head | = head | **1.61 (.38)** | 1.44 (.34) | = 2–10 |
| | blend | 1.10 (.31) | | | **1.38 (.39)** | 1.61 (.42) | |
| | TabPFN | 1.65 (.40) | | | **1.98 (.46)** | 1.91 (.44) | |
| 20 entries (deep line) | no term | 1.65 (.21) | = head | = head | = head | = head | 1.46 (.20) |
| | blend | 2.03 (.26) | | | | | 1.97 (.25) |
| | TabPFN | 1.55 (.22) | | | | | 1.75 (.26) |
| whole book | no term | 1.19 (.21) | 1.24 (.23) | 1.19 (.23) | 1.37 (.25) | 1.28 (.24) | 1.34 (.24) |
| | blend | 1.32 (.23) | 1.39 (.25) | 1.40 (.25) | 1.47 (.27) | 1.55 (.27) | 1.46 (.27) |
| | TabPFN | 1.50 (.26) | 1.60 (.28) | 1.64 (.29) | 1.69 (.29) | 1.72 (.30) | 1.72 (.30) |

### 2.2 Paired against the head dealing (Δ tickets as a share of the field's expectation; slate-banks up–down)

| Variant | Class | No term | Blend | TabPFN |
|---|---|---|---|---|
| L25, M = 5 | 2–5 | +0.10 [−0.09, +0.29] 24–15 | +0.15 [−0.02, +0.32] 27–20 | +0.24 [+0.05, +0.42] 28–23 |
| L25, M = 4 | 2–5 | −0.01 [−0.25, +0.23] 26–24 | +0.18 [−0.05, +0.41] 27–23 | +0.33 [+0.07, +0.58] 32–23 |
| 2–10, M = 5 | 10 | **+0.48 [+0.13, +0.85] 21–12** | +0.28 [−0.09, +0.65] 22–18 | +0.33 [−0.09, +0.75] 22–21 |
| 2–10, M = 4 | 10 | +0.31 [−0.05, +0.68] 22–15 | +0.51 [+0.07, +0.94] 25–18 | +0.26 [−0.19, +0.72] 23–20 |
| all, M = 5 | 20 | −0.20 [−0.45, +0.05] 5–11 | −0.07 [−0.36, +0.23] 14–17 | +0.20 [−0.12, +0.51] 15–9 |
| L25, M = 5 | whole book | +0.04 [−0.04, +0.13] | +0.07 [−0.01, +0.14] | +0.10 [+0.02, +0.18] |
| 2–10, M = 5 | whole book | **+0.18 [+0.03, +0.34] 31–19** | +0.15 [−0.01, +0.30] 31–21 | **+0.20 [+0.04, +0.35] 33–23** |
| singles M = 5 + 2–10 M = 5 | whole book | +0.19 [−0.00, +0.37] 36–15 | +0.19 [+0.01, +0.36] 36–21 | +0.22 [+0.03, +0.41] 33–23 |

P(a contest cashes) moves the same way: +0.07 to +0.09 on the 10-entry contests at M = 5, +0.03 to +0.05 for the
whole book with the 2–10 limit.

### 2.3 Reading

1. **L25 replicates** on independent books and banks, in the same direction and about the same size.
2. **The 10-entry contests gain as much as the 2–5s did**, on every objective, and they carry far more of the week's
   entries. The whole-book ticket gain goes from +0.04–0.10 (L25 alone) to +0.15–0.20 of the field's expectation.
3. **The deep supersats do not gain.** At the p99 line the rows given up cost more than the decorrelation earns; two of
   three objectives lose, and the weeks with no deep ticket rise from 50–64% to 58–67%.
4. **M = 5 over M = 4.** At M = 4 the no-term book loses what it gained and the blend's P(cashes) falls; only the TabPFN
   book prefers 4. The chain falls back to the blend or to no term when LineStar or the fit fails, so the setting
   should be the one that holds on all three.
5. **The singles.** The nine single-entry satellites take rows 1–9, which share up to seven players and win or lose
   together. Dealing them on rows that pairwise share ≤ 5 leaves the expected tickets flat to up (+0.05 / +0.32 /
   +0.16 × field, none significant) and cuts the weeks with no single-entry win: 60% → 49% (no term), 44% → 38% (blend),
   46% → 38% (TabPFN); at M = 4 the blend's falls to 26%. It is the "spread" idea applied where it is cheap.
6. **The per-contest exposure cap** is never better than the overlap limit and is worse on the TabPFN book. Closed.

### 2.4 What each would take

| Change | Code | Evidence owed | Earliest |
|---|---|---|---|
| The limit on the 10-entry contests | `SMALL_MAX_ENTRIES` 5 → 10 in `enter_layout.py` (or an env for the ceiling); the fallback, the exposure sheet and the swap path already cover any size | a frozen read on the L25 harness with the ceiling at 10 (the reader's cells then include the 10-entry contests) — about two hours on the workstation | Week 4 only if the read lands and Thursday's smoke publishes through it; otherwise Week 5 |
| The singles' overlap limit | a small change in `_head_ranks` / `limit_small_overlap`: the all-head group of single-entry contests treated as one contest for the limit | the same harness | Week 5 |
| The deep supersats | none | — | not recommended |

## 3. Limits

- The same 36 slates as every L-series read; my banks are fresh but the slates are not. The paired intervals are 90%.
- The plan is Week 4's Rev1. Other plans change the cells; the mechanism (top rows that share players) does not.
- LineStar's history inside the two term objectives is not provably pre-lock (as in L20–L25); the no-term column is the
  clean floor, and it shows the same direction on the 10-entry contests.
- The dealing variants are descriptive; the frozen read belongs to production's harness.

## 4. Reproduction

`reports/lab-handoffs/2026-09-29-ownership-term/`: the books from `11_panel_term_tabpfn.py` with `KROWS=105` on banks
1320 and 1321; `13_read_dealing.py` with `PLAN_FILE` (the private plan; counts are never printed), `ENTER_LAYOUT_PY`
(a checkout at or after `188cb07b`) and `PANEL_DIR`.
