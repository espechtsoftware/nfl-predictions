# Post-window-automation program review — suggestions to improve scoring

Date: 2026-08-11. Scope: the browser-automation download layer, the full
28-report catalog audit, the exact-window semantics finding, and the five
frozen diagnostics that have run and closed since the last outside review.

**No code was changed.** Everything below is a protocol sketch or a process
recommendation.

> Discipline note: §2 and §3 re-read metrics that are already published inside
> closed run artifacts. Re-adjudicating a closed arm under a metric chosen
> after seeing it is exactly the mining this project prohibits. Nothing here
> proposes that. §4.1 asks for a gate to be frozen *prospectively*, and §4.3
> routes the affected arm through the 2026 shadow its own protocol already
> licensed.

---

## 1. What was built, and what it proved

The automation and audit work is high quality and it settled two things that
were genuinely open.

**The window contract is exact, not cumulative.** Controlled 2025 exports
established that `Week(s)=1–4` and `Week(s)=5–8` return *exactly those weeks*
(`G≤4` in both, all 259 overlapping players differing on at least one of
`G/RTE/TGT/YDS/FP`). This is a stronger and more useful contract than a
season-to-date cutoff — it permits any window, including trailing ones.

**The catalog is fully enumerated and guarded.** 28 NFL reports, 25 with
historical `Season`+`Week(s)`; only the three upcoming-matchup tools lack a
historical Season surface. The downloader now fails visibly on catalog drift,
and the tab-reset hazard (clicking an active context tab after choosing weeks
silently reverted to full-season data) was caught and repaired, with the
polluted artifacts rejected rather than quietly reused. That is the failure
mode that would have poisoned every downstream conclusion, and it was caught
by the operator's own audit.

**The outcome-blind redundancy screen was the right thing to do before
modeling.** It correctly identified that Advanced Receiving target share
(r=0.99), air-yard share (0.98), XFP/game (0.97) and Detailed Snaps share
(0.999) are duplicates of existing features, and that vendor separation is a
genuinely different construct from NGS separation (r≈−0.12). Paying the
multiple-testing cost on duplicates would have been pure waste.

### Corrections to my earlier documents

Two things I got wrong, both caught by the repository reconciliation:

- **Defense PROE is not redundant.** `016_team_week_context.sql` computes a
  team's *own* lagged offense PROE; the vendor Defense PROE files are opponent
  context. My §1b redundancy call was wrong and the reconciliation was right to
  reject it.
- **My route-share "mean repair" claim was over-confident on the evidence then
  available** — the auxiliary Ridge MAE had worsened in both folds, which I did
  not weigh. The reconciliation correctly lowered the prior. §3 below reports
  what the component test then found.

---

## 2. The central problem: the gate is deciding at noise level

Five arms ran. Five failed. But the five are not the same kind of failure, and
the primary gate — aggregate 30-point Brier — is being asked to adjudicate
differences far below its resolution.

A Brier difference is easiest to interpret in units of *events*, because the
non-event rows contribute almost nothing. For a rare event, one row moving its
predicted probability by δ changes the summed Brier by ≈2δ. So the whole verdict
of each arm can be expressed as "equivalent to one 30-point event's predicted
probability moving by X":

| arm | rows | 30-pt events | Brier Δ (rel.) | summed Brier Δ | ≡ one event moving by | fold signs |
|---|---:|---:|---:|---:|---:|---|
| **Defense PROE** | 16,110 | 162 | **+0.04%** | 0.056 | **2.8 pp** | **+ − +** |
| Route components | 13,876 | 211 | +0.19% | 0.369 | 18.4 pp | + − − |
| Same-season coverage | 2,984 | 94 | +0.51% | 0.453 | 22.6 pp | − − − |
| Route shape | 4,486 | 100 | +0.65% | 0.609 | 30.4 pp | − − − |
| Advanced Passing | 793 | 57 | +4.25% | 2.145 | 107 pp | − − − |

Read the Defense PROE row carefully. **The entire preregistered verdict that
closed that mechanism rests on a summed Brier difference of 0.056 — what you
get from a single 30-point event's probability moving 2.8 percentage points.**
It improved in 2023 and 2025 and worsened only in 2024. That is a coin flip
recorded as a refutation.

Sorting the five honestly:

- **Advanced Passing is a decisive, correct failure.** 4.25% relative, worse in
  all three folds, and its support gate genuinely failed (26–28% vs 50%
  required). Closed on merit.
- **Route shape and same-season coverage are consistent failures** (worse in
  every fold). Coverage additionally failed a real support gate at 21.8–23.4%
  against a 30% requirement — that is a "not enough data" result, not a
  mechanism refutation.
- **Route components and Defense PROE are non-results.** Neither is evidence of
  absence. Both were closed as if they were.

### Why the support gates keep failing: the window policy

The chosen window policy — last four completed weeks — maximizes recency and
minimizes support, and the support failures follow directly. Over four games
the Separation-by-Coverage medians were 10 man routes, 27 zone, 7 Cover 2,
13 Cover 3, 7 Cover 4, 5 Cover 6. A support rule scaled to that window still
qualified only 38–44% of target rows, and realized fold coverage came in at
21.8–23.4%.

Now that the exact-window contract is proven, a trailing window is a *choice*,
not a constraint. The project's own existing feature set already uses `_l4`,
`_l8` and season-level views side by side because that trade-off is well
understood. A season-to-date window at target Week 12 carries ~11 games rather
than 4 — roughly 2.75× the route support — and a shrinkage blend
(last-four → season-to-date → prior season, with an explicit support-weighted
weight) would have given the coverage family a genuine test instead of a
support failure.

---

## 3. The finding already measured, and not acted on

The route-component run trained the **actual production K=1 LightGBM component
models** and composed outcomes from **10,000 common-seed simulations**. Its
mandatory diagnostics included quantile exceedance. Those numbers are the most
important thing produced by this entire program:

| quantile | nominal | control observed | expected exceedances | observed | z |
|---|---:|---:|---:|---:|---:|
| q90 | 10.0% | 11.11% | 1,388 | 1,542 | ~4 |
| q95 | 5.0% | 7.10% | 694 | 985 | ~11 |
| **q99** | **1.0%** | **2.69%** | **139** | **373** | **≈20** |

**The production composed player distribution's upper tail is roughly 2.7×
too thin at q99, measured on 13,876 held-out Sunday-main player-weeks across
three seasons.** Actual outcomes blow past the model's 99th percentile nearly
three times as often as they should.

Compare the power: every 30-point Brier gate run so far is deciding at well
under 2σ on 57–211 events. This calibration defect is a ~20σ measurement on
every row. It has been sitting in the mandatory-diagnostics section of a report
whose headline was "fails."

This also connects directly to the standing scoring problem. The winner slots
absent from the entire candidate pool averaged 7.19 projected against 22.74
actual. A simulator whose q99 is 2.7× too low cannot assign those outcomes
enough probability to build them into lineups — which is the mechanism behind
both the 33 missing winner slots and the near-random winner-assembly result.

**One necessary caveat.** This is measured on the component-composed simulation.
The full served path additionally applies the empirical marginal shaper
(`emp_marginals.py`, which affine-matches shapes to our mean/std) and the 45/55
prop-market blend. Some of this may be corrected downstream. **The first action
is to measure the same three exceedance rates on the full production path**, on
the same held-out rows. That is a diagnostic, not an arm, and it needs no new
data.

---

## 4. Recommendations

### 4.1 Freeze a better primary gate before the next arm runs

The current primary — aggregate 30-point Brier — throws away ~99% of the data.
It uses only the ~1% of rows that are events, so its resolution is set by
n_events (57–211 here), not n_rows (793–16,110).

Preregister, **before** the next diagnostic and applying only to arms not yet
run, a primary that uses every row:

1. **Empirical CRPS** on the composed distribution — proper, uses all rows,
   and already computed in the route-component report.
2. **Pinball loss at τ ∈ {0.90, 0.95, 0.99}** — targets the upper tail
   specifically while still scoring every row.
3. **Exceedance calibration** at q90/q95/q99 against nominal.

Keep 20/30-point Brier as mandatory diagnostics. They remain the quantity
closest to the operator's utility, and they should still be reported and
sign-checked — they are simply too noisy to be the deciding metric at these
event counts.

**Add an error bar to the report schema.** The runs already hold row-level
predictions; persisting the SD of the per-row paired metric difference (and
therefore a standard error on every reported delta) costs almost nothing and
would have flagged Defense PROE as a tie at the moment it was computed. Make it
a required field.

**Preregister a minimum detectable effect.** Before launching an arm, state how
large an effect the gate can resolve at the arm's event count. If the answer is
"larger than any plausible feature effect," the arm should not run — that is a
build, an execution and a protocol saved.

### 4.2 Repair the tail dispersion — highest expected value in the program

This is the same recommendation as §3.3 of the strategy review, now confirmed
on the production simulation path at ~20σ rather than inferred.

Sequence:

1. **Measure first.** Reproduce q90/q95/q99 exceedance on the *full* served
   path (post-shaper, post-blend) on the same held-out rows. If the defect
   survives shaping, it is the largest well-powered defect in the system. If
   shaping already corrects it, that is equally valuable to know and closes the
   question cheaply.
2. **If it survives, recalibrate segment-conditionally.** Fit a walk-forward
   monotone quantile correction on segments defined by pre-lock observables —
   position × salary tercile × projection band, with route-share tercile as a
   natural fourth given §3 of the utilization review. Target nominal exceedance
   at all three levels jointly. Enforce monotonicity across levels and shrink
   thin cells toward the global correction; q99 cell counts will be sparse by
   construction.
3. **Gate it on the calibration statistic itself**, plus non-worsening CRPS and
   byte-invariant means — this is a dispersion repair, not a new point belief,
   and that invariance is what distinguishes it from every rejected "widen the
   tails" arm.
4. Only then a candidate/oracle arm, then one fixed-budget panel.

Unlike the vendor-field arms, this has a direct mechanical path to the
objective: correcting a 2.7×-too-thin q99 raises simulated 30-point probability
for exactly the cheap-to-mid-priced players whose absence explains the missing
winner slots.

### 4.3 Let the 2026 shadow adjudicate route share

The route-component protocol explicitly licensed retention of "the same exact
four-feature contract as a labeled 2026 prospective shadow." That is the clean
path and it should be activated.

The reason to bother: the arm failed its tail gate by 0.19% on 211 events while
improving the two well-powered metrics **in every fold** — composed DK-point MAE
3.7879 → 3.7315 (−1.5%) and CRPS 2.5795 → 2.5687. Component-level MAE improved
on targets, carries, rush TDs, rec TDs, pass attempts and interceptions. That is
a consistent improvement in the projection distribution, adjudicated against by
the one metric that could not resolve it.

Do not re-read the closed historical run under a new primary. Run the shadow,
grade it under §4.1's gate frozen in advance, and let 2026 outcomes be the
independent evidence the protocol already anticipated.

### 4.4 Stop spending arms on vendor field families

Five arms, five failures, and the redundancy audit shows the remaining
candidates are mostly overlapping (Advanced Rushing explosive/expected/stuff/
YBCO at 0.50–0.72 against existing YPC; Routes Run at 0.9987–0.9998 against
Separation-by-Alignment; Basic/Bell Cow/FPTS families redundant outright).

The genuinely distinct remainders — route-break groups, Separation-by-Alignment,
missed-tackles-forced — have small distinctness (max |Spearman| 0.20–0.61 against
existing inputs) and no measured mechanism. Their prior should now be lower than
it was five arms ago: this data has been tested reasonably thoroughly and has
produced one real signal (route share) and four non-results.

If one more historical family is run, **Advanced Receiving same-season windows**
remains the best candidate — it is the only untested family holding
ceiling-relevant fields (first-read rate, air-yard share, XFP/RR) — but it must
be run under §4.1's gate, with a support-aware window per §2, and after §4.2.
It should not be run at all if §4.2 is still queued.

### 4.5 Point the automation at the 2026 operating path

The downloader is now the most valuable artifact of the purchase, and its
highest-value use is prospective, not historical. Before Week 1:

- Implement the weekly Route Share append path the reconciliation already
  specifies: immutable raw archive, idempotent player-week upsert, strict
  prior-week join, schema/hash audit, labeled no-Route fallback.
- Verify the in-season refresh timing of the weekly Route Share report against
  the Sunday 1 p.m. ET lock, and confirm the automation's catalog check still
  passes once the vendor rolls to 2026.
- Capture the three matchup tools (QB/WR Coverage, OL/DL) as **pre-lock
  prospective snapshots** with the schedule-pair verification that caught the
  offseason hindsight defect. They cannot be backtested, so prospective capture
  from Week 1 is the only way they ever become testable.

### 4.6 Two things to keep doing

The tab-reset catch and the rejection of the polluted exports were the most
valuable single acts in this program — an undetected version of that bug would
have silently made every same-season arm a full-season arm. Keep the
verify-filters-after-Apply assertion.

Deriving the opponent from the project schedule rather than the vendor `OPP`
field is likewise correct and should stay a hard rule.

---

## 5. Suggested order

1. **Measure q90/q95/q99 exceedance on the full served path** (§4.2 step 1) —
   cheap, no new data, and it either promotes or closes the largest measured
   defect in the system.
2. **Freeze the §4.1 gate** — including the error-bar field and the minimum
   detectable effect requirement — before any further arm.
3. **Tail recalibration** if step 1 confirms the defect.
4. **Activate the 2026 route-share shadow** (§4.3) and the weekly append path
   (§4.5); both are prospective and run in parallel with 1–3.
5. Advanced Receiving same-season windows only after 3, and only under the new
   gate.

The one-sentence version: **this program has been rejecting real effects with an
under-powered gate while a 20σ tail-calibration defect sat unremarked in its own
diagnostics; fix the gate, then fix the tail, and let 2026 adjudicate route
share.**
