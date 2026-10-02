# Friday review: would Week 4 have done "equally bad"? The entered design against the corpus, and the code review

Reviewer, 2026-10-02 07:1x CDT. Branch `review/ownership-term-20260929`. Read: integration `aaa8051c`, every HANDOFF
entry since 2026-10-01 14:04, the corpus-win audit (`review/corpus-win-audit-20261002` @ f1579f71, draft) and its
field-sleeve panel output, the field sleeve's code, and the field-sleeve T-70 smoke that finished at 07:08.

## 0. The answer

**No.** The corpus audit's finding — the pool is below the field at every line and "the Week-4 design (union with the
T-70 pool) changes nothing at the corpus level" — is correct about the **pool**. But in Week 4 no entered row comes from
the pool:

- the **main book** (every satellite entry) is solved directly on the T-70 projections by the capped optimizer with the
  ownership term (`pmo_x50`), not selected from the pool;
- the **sleeve** (Millionaire, $555 sat, FFWC qualifier sat) now comes from the field sample (`UNION_SLEEVE_SOURCE=field`).

The pool is a fallback only. Measured the way the audit measured the pool, the entered main-book design beats the
field at the satellite lines in all three 2026 weeks.

## 1. The entered design on Weeks 1–3, next to the audit's pool

The main book rebuilt on each week's archived frame at this week's shape (K = 105, exposure cap 52, DST cap 26,
per-game 4, salary ≥ $49k), scored with DraftKings points against the real Millionaire field. "Lag 0.10" is Sunday's
likely form (LineStar has not filled Week 4, so the term falls back to Saturday's lag file at tilt 0.10; the smoke at
07:08 did exactly that). Multiples are the share of rows at or above the field's line over the field's own share.

| Week | Book | Avg points (field) | top 20% | top 10% | top 5% | top 1% | best (winner) |
|---|---|---:|---:|---:|---:|---:|---:|
| W1 | the pool (audit) | 140.2 (142.1) | 0.87× | 0.76× | 0.68× | 0.88× | 228.5 |
| W1 | **entered design, lag 0.10** | **164.7** | **2.43×** | **4.00×** | **3.81×** | **8.57×** | 245.9 (274.0) |
| W1 | entered design, no term | 166.1 | 2.57× | 3.81× | 4.19× | 2.86× | 227.6 |
| W2 | entered design, lag 0.10 | 105.4 (115.5) | 1.67× | 2.10× | 2.48× | 1.90× | 194.0 (232.4) |
| W2 | entered design, no term | 104.9 | 1.29× | 1.52× | 1.33× | 0.95× | 181.7 |
| W3 | the pool (audit) | 120.4 (128.5) | 0.62× | 0.52× | 0.45× | 0.39× | 207.1 |
| W3 | **entered design, lag 0.10** | **138.6** | **1.48×** | **1.52×** | 0.76× | **2.86×** | 193.2 (239.8) |
| W3 | entered design, no term | 133.6 | 1.38× | 1.14× | 0.57× | 0.00× | 178.7 |

What was actually entered: W1 144.9, W2 105.0, W3 120.5 average points.

- The satellites' lines sit between the top 21% and the top 1% (the $5 supersats near the top 20%, the $1 25× near
  the top 4%, the $0.25 2,378-entry near the top 1%). At those lines the entered design is above the field's rate in
  every week but one cell (W3 at the top 5%).
- W2 is the projection-defect week; even there the design clears the field at the satellite lines.
- This is hindsight on three frames, each one draw, and the rows of a week are correlated (W1's 8.57× is nine rows
  in one good week). It agrees with the panel evidence (L13: the capped optimizer 1.22× at p89 where the Weeks 1–3
  selectors were 0.82–0.95×; L20/L21/L24: the term +12–33%).

## 2. The defects found this week

Every one of them — the two-track pre-check refusing every Sunday build, `auto` never resolving the Saturday supply,
the exposure sheet's row count, `LEV_CBC_THREADS` never reaching the live build, the unlabelled long snappers in the
chalk sleeve, the field sleeve's top-up and `free`-mode limits — was **found by the smoke before Sunday** and fixed
with a test. That is the opposite of Weeks 1–3, where the defects were found on Sunday or in the post-mortem. Had the
first two not been found, Week 4 would indeed have gone badly (no build at all, or no union); they were found.

State at 07:08: the full 8-thread smoke passed (supply 2 h 35 min, T-70 577 s, audit passed); the field-sleeve T-70
smoke passed (566 s, `field_top` used, 5 rows, `audit_passed`, the term fell back loudly to the lag file at 0.10);
publish, swap and R4 on the field-sleeve run follow. At the tip the field-sleeve, union, audit, env and layout tests
pass here too.

## 3. Code review: what remains

1. **The field sleeve on the $555 and FFWC qualifier satellites (4 of the 5 sleeve rows).** Those are 72-entry,
   one-ticket contests: winning one is about the top 1.4%. The laptop's own panel (`~/corpus-audit/panel*/07_read.txt`)
   favours the projection sleeve at the top-1% line: per row 2.22× against 1.44× (blend) and 1.62× (lag) for the field
   sleeve; at least one of the five rows over the top-1% line on 11% of slates against 7–8%. The field sleeve's edge is
   at the top 0.1% (3.24× with the lag file against 0 hits), which is the Millionaire's line. Both readings rest on a
   handful of events. **Option:** the field row for the Millionaire, the projection sleeve for the four satellite rows
   (a small change in `union_reselect.py`: the sleeve is dealt Millionaire first, so `book_tail` = field pick[:1] +
   projection pick[:4], with the overlap and cap checks), smoked through publish and swap. The operator's call.
2. **The union still needs a Saturday supply although no entered row comes from it now.** If no supply exists the
   union refuses and the T-70 build's own mean book is entered, losing the capped main, the term and the field sleeve.
   Three supplies cover it (Saturday D12800, Saturday D6400, Sunday-early D12800). Low risk; a T-70-pool-only fallback
   would remove it.
3. **LineStar is still unfilled (60 of 100 players).** The term then runs on the lag file at 0.10, a weaker tilt (73 of
   105 rows shared with the no-term book) — and in the table above the strongest of the three forms. Not a worry.
4. **Latent, recorded:** O-15 (`MIN_LINEUP_SALARY` read in two places; the same value this week), O-16 (`UNION_DK_STATUS`
   unset; the T-70 frame's DK denylist covers it).

## 4. What to expect Sunday

- **Satellites (most of the money):** a real chance. On the panel and in hindsight the entered design runs at 1.2–2×
  the field's ticket rate at these lines, above the 1.1–1.2× break-even. A losing week is still common: the rows move
  together, and the winners study found even the best players profitable in a minority of weeks.
- **Millionaire / FFWC / $555:** lottery tickets in any design. The field sleeve is a reasonable shot at the shape that
  wins the Millionaire; it is not evidence of an edge.

## 5. Reproduction

`reports/lab-handoffs/2026-09-29-ownership-term/14_entered_design_2026.py 105` with `PROD_SCRIPTS` (a production
checkout's `scripts/`), `DATA_DIR` (private) and the Week-4 pinned lab clone on `PYTHONPATH`.
