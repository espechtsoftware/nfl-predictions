# Studies the agent proposes (2026-10-04)

**For:** the operator (priorities and decisions) and the reviewer (designs).
**Asked:** "I would like you to do some research and some deep thinking and come up with your own set of questions of
things that we should do studies on."
**Revised 10-04 after the reviewer's review** (the ⚠ notes below are binding: closures the first draft missed).

**Basis:** two read-only research passes on 10-04:
- what has been tested: system study Addenda 91–121, the whole lab LEDGER (000–097), the week-3 post-mortem, the
  09-16 synthesis, the 09-29 reviews;
- known weaknesses and unused data: OPEN-DEFECTS, the deficiency log, the post-mortems, `where-the-points-and-money-go`,
  the B4/D1 map, plus small aggregate BigQuery checks.

Nothing here repeats the operator's nine studies (`reports/2026-10-04-post-week4-study-list.md`) or reopens a closed
verdict without a reopening condition. Numbers marked "prelim" are single descriptive queries (2026 W1–3) to be
re-derived inside each study, not results.

## The headline

The record points one way: **selection and contest choice decide the money, and the projection foundation is weaker
than the blend suggests.**
- Lifetime ROI is −83.5% over 1,164 entries. The 5k–40k qualifier class is more than half the volume and returns −96%.
- Satellites need a ticket rate 1.10–1.19× the field's to break even. MEAN runs about 0.9×. Only the Week-4 main form
  clears it (1.22×), on a 32–31 paired record (`reports/2026-09-29-where-the-points-and-money-go.md`).
- Every winning-lineup player in W1–3 was in our pool (81/81). **The loss is in what we pick, not what we generate.**

The top three proposals follow from that.

## Priority 1: they decide money, and the data is ready

### P1. Where are we +EV at all? Contest-type edge and stake vs measured edge
- **Question:** for each contest type (satellites by line percentile, supersats, 5k–40k qualifiers, the Millionaire,
  FFWC, $555), what ticket/cash rate do our books achieve against the break-even rate, with honest uncertainty? Which
  types are we structurally unable to beat at our entry counts?
- **Why:** the qualifier class is more than half the volume at −96%. "Entry count is the largest quantified lever"
  (LEDGER 001; Add. 10, 53). No study has tied stake to measured edge per contest type.
- **Already known:** cash games are closed. Contest choice and stake are operator decisions (R6/R7). This study only
  supplies the evidence.
- **Method:**
  1. Build the payout-ladder table from `dk_contest_fills.payout_metadata_json` (never built), plus a rank-to-tier view.
  2. Per contest type, compute realized and paper ticket rates against break-even, with confidence intervals from W1–4
     and the historical books.
  3. Run a power analysis: how many weeks to tell 1.0× from 1.15×?
  4. Output a stake rule candidate, e.g. stake proportional to the lower confidence bound of the edge.
- **Cost:** about 1–2 days. **It informs:** the weekly contest plan.
- ⚠ **Reviewer:** this is Add. 95's item (5), "entry-volume analysis with REAL payout curves (blocked: payout.py stylized)". Lead with the power analysis. If separating 1.0× from 1.15× takes more weeks than a season has, say so, and make the stake rule a lower-confidence-bound rule.

### P2. Is the market better than our model, and should the blend lean further toward it?
- **Prelim fact** (`div_shadow` × actuals, W1–3, n=600 prop-priced players who played): MAE market 5.28 < served
  blend 5.43 < model 5.78, in every week.
  - The model sits ≥2 points above the market 7× as often as below.
  - When above, the realized residual is −0.95.
  - corr(model−market, residual) = −0.13.
- **Already known:** L04 found 0.45 beat model-only and a 0.70 market weight on lineup outcomes (tickets). A weight
  below 0.45 needs its own preregistration. B2 only adds FP to the blend.
- **Question:** does a CONDITIONAL blend beat the fixed 0.45/0.55 on both MAE and lineup outcomes? Candidates:
  - shrink the model toward the market more when the model is above it;
  - position-specific weights.
- **Second question:** can pick'em lines (`prop_lines_us_dfs`, about 200 players a week, unused) cover the 266/487
  `model_only_no_line` players?
- **Method:** a walk-forward panel on both targets, MAE and the L04 lineup harness, with the decision rule frozen
  first. Pick'em coverage and calibration come first, as a descriptive step.
- **Cost:** about 2 days. **It informs:** the projection blend (props are 55% of every projection).
- ⚠ **Reviewer: THREE priors constrain this.**
  - L04, on lineup outcomes.
  - The 2025 blend audit (system study ~line 575: MAE flat over w 0.30–0.50, "difference is noise").
  - The 09-29 review §3, which CLOSED "a heavier market weight": at the TOP of the slate, the players a book is made
    of, served vs market MAE is 6.29 vs 6.32.

  So a uniform heavier weight is **not** re-proposed. The conditional form is really a BIAS correction, partly O-22's
  measured QB starter bias. **Order:** the O-22 retrain first, then re-run the prelim on the retrained model. Only if
  the asymmetry survives, preregister the conditional blend, scored on the top of the slate and on lineup tickets, not
  all-player MAE. The pick'em coverage step is unaffected.

### P3. A standing "simple baseline" benchmark: does each layer earn its place?
- **Prelim fact:** a plain props-only optimizer beat the entered book in 4 of 4 frames (+12.5 to +32.1 per row).
  Going from the top-K-by-mean book to the entered book cost −29 (W1) and −31 (W3) points per row (`where-the-points…`).
- **Question:** every week, as PAPER arms scored in Monday's unchanged comparison:
  - (a) a props-only MILP;
  - (b) a mean-only MILP with no term and no sleeves;
  - (c) the entered book.

  Which layers (ownership term, field sleeve, class sleeve, head layout, caps) add value, measured cumulatively?
- **Method:** reuse `union_paper_rebuild.sh` (deterministic, byte-identical) with layer toggles. A season-long ledger
  of per-layer deltas, with a preregistered review point (e.g. after Week 8).
- **Cost:** about 1 day to wire, then minutes each Monday. **It informs:** keeping or removing layers. This is the
  in-season evidence adoption track v2 asks for.
- ⚠ **Reviewer:** score the benchmarks on the book's objective: tickets and line hits by contest class at each
  contest's own line (the 10-02 Friday review's method). Not points per row. The "+12.5 to +32.1 per row" fact is a
  mean-points statement, the entered book does not maximise mean points per row, and read that way it misleads.

### P4. Spread dealing, corrected: ONLY the one-offset-per-contest variant (built in 44f5aae4, 09-29; default-off)
- ⚠ **Correction:** the first draft repeated the winners study's claim ("cut empty weeks at no expected cost"). The
  reviewer's 09-29 addendum CORRECTED it (`reports/2026-09-29-ownership-term-addendum-routing-and-dealing.md` §3;
  `07_read_layouts.py`). That claim was for ONE contest's rows and never dealt several contests at once.
  - `ENTER_LAYOUT=spread` AS BUILT (f0da76d5) gives equal-size contests identical rows: 37 distinct rows of 100. Deep-line
    empty weeks ROSE from 66% to 76%.
  - Only a variant with **one offset per contest** cut empty weeks: from 25–30% to 11–21%.
- So study 1's dealing arm is the **offset** version, citing these numbers. **Correction 2026-10-05:** it is BUILT, in 44f5aae4 (09-29), as production `_spread_ranks` (ENTER_LAYOUT=spread; default-off), and tested. The earlier "not built" was wrong (reviewer). It is **not** adopted; study 1 (prereg e7f5a36a) tests it.
- **Prelim facts** (W1–3, players who played; share above p90, nominal 10%):

  | Position | Above p90 |
  |---|---|
  | TE | 17.5% (W3 28.6%) |
  | WR | 8.5% |
  | RB | 3.5% |
  | QB | 1.1% |

  - $7k+ WRs are under-projected by +4.4.
  - **QB ranking skill near zero:** the served QB correlation with actuals was 0.50, 0.22 and 0.06 over W1–3.
- **Why:** punt valuation, the boom supply and the tail rows all read p90/variance. Mis-scaled tails by position
  distort every one of them. O-22 already shows QB over-projection.
- **Question:** are our quantiles calibrated by position and salary tier across the panel, and does a per-position
  quantile recalibration improve lineup outcomes? The recalibration would be isotonic or a conformal width per
  position, building on the existing `models/conformal.py` and `calibration.py`.
- **Already known:** a direct ceiling classifier failed (0/8); the breakout classifier is calibrated (AUC 0.85). This
  is calibration of the served distribution, not a new classifier.
- **Cost:** about 2 days. **It informs:** projection tails, punt valuation, supply.
- ⚠ **Reviewer:** fine. The QB correlations (.50/.22/.06) come from 3 slates; the panel number decides.

### P6. Simulator correlation repair: CLOSED as proposed (reviewer's ruling)
- ⚠ **Ruling: Add. 95's reopening condition is NOT met.** The coupling repair has been tried in three forms:
  - the analog copula (LEDGER 010–012: null);
  - the similarity-conditioned Schaake shuffle (Add. 99: NEGATIVE on both preregistered held-out measures);
  - the hierarchical simulator with explicit game- and team-level coupling (PREREG-021/022/027; 049b/c gates; 050 "no
    arm passes"; 057).
- `GAME_SIM_PACE=vegas` is a closed null (the system study's simulator table: 185.6 / 5-17, "gate stays off").
- An empirical copula on 2016–2025 falls inside the first two families.
- To reopen, a proposal must name what is materially different from all three (e.g. a coupling estimated with
  point-in-time inputs those laws lacked), state 057's verdict and why it does not cover the new idea, and freeze the
  evaluation first.
- The facts below are recorded as ALREADY MEASURED, not as new leads. Note LEDGER 003's recalibration: WR1–WR2
  realized +.041 under salary roles.

The original text, kept for the record:
- **Facts:**
  - Within-team coupling is overstated: WR1–WR2 +0.27 in the bank vs +0.016 realized.
  - Cross-team coupling is about 0 simulated vs +0.21 realized.
  - The incumbent bank's DST has zero variance.
  - `GAME_SIM_PACE=vegas` is unset.
  (`where-the-points…:63-69`; post-mortem Q10; O-8)
- **Why:** the pool cannot reach the Millionaire. W3's best pool row was 207 against a top-10 line of 220, and every
  200+ row was a stack we didn't enter. Wrong coupling mis-ranks exactly those stacks.
- **Question:** fit the coupling to realized data (an empirical copula on 2016–2025, point in time) and turn on
  pace=vegas. Does supply then reach the 220+ tail more often, and does the tail sleeve improve?
- **Already known:** many generator variants are closed, but all used the current simulator. This changes the
  simulator. Add. 95's reopening condition ("a new pre-lock signal") is arguably met by corrected coupling; the
  reviewer to rule.
- **Cost:** about 3–4 days, heavy local compute. **It informs:** supply and the tail rows.

### P7. Late information at T-70: Q players and backups
- **Facts:**
  - Questionable players: the market priced 101.8, we served 84.9, they scored 102.6 (week-3 review §0.5).
  - Backups of an out starter beat our projection by +1.0 historically.
- **Proposal:** fold into study 3 as its market-anchored arm. For active-Q players at T-70, use the market (which
  already prices the Q risk) instead of our haircut. The Flowers case is consistent but n=1.
- **Cost:** inside study 3.
- ⚠ **Reviewer:** fine. The market number comes from one week; the calibration-first rule applies.

## Priority 3: larger builds, worth scoping

### P8. Field-aware, duplication-aware EV for large-field contests
- **Asset:** 1.49M field lineups (`contest_entries`, W1–3), unused on the money path.
- **Question:** using the field's actual construction frequencies, estimate each candidate's duplication and its
  payout-weighted EV in the Millionaire / FFWC / $555 (with P1's ladder). Does selecting the tail rows by that EV beat
  the field sleeve?
- **Already known:** the ownership term and the field sleeve use ownership marginals only. Duplication and payout
  shape have never been modelled. The deep tail (≥220) cannot be powered by the panel (057), so it is prospective
  grading only.
- **Cost:** about 4–5 days.
- ⚠ **Reviewer:** scope later. Price the duplication model on the 1.49M field rows outcome-blind first.

### P9. E0: how much of the gap to the oracle is recoverable?
- Named in the record as "the next lab study" (09-16/17), never run.
- **Question:** of the oracle-minus-book gap, how much is decision regret (fixable by selection) vs irreducible luck?
- **Why:** it prioritises everything else. If recoverable regret is small, stop tuning selection and work on contest
  choice (P1) and inputs (P2/P5).
- **Cost:** about 2 days.

## Operational audits (cheap, they protect a Sunday; not research)

- **A1. Daylight-saving change on Sun 11-01 (Week 8).** Run O-5's UTC-bound and week-literal checks before then.
  Rehearse a Week-8-dated dry run.
- **A2. OPEN-DEFECTS review.** The register says "last reviewed 09-18". O-2/O-9/O-11/O-13/O-14 are past their deadlines
  and still listed as live. Close or re-date each with evidence.
- **A3. Weekly ownership grading is not stored** (`own_shadow` holds only W1). Persist each week's predictor-vs-realized
  row, so O1 and the dashboard have history.
- **A4. Deadlines in Week 5:** the SIS pass-tail checker (O-3) fails at Week 5 with PAUSED schedulers; the O-22 retrain
  is due before Week 5's Saturday.

## Suggested order
1. **This week:** P1 (contest edge, power analysis first), P3 (baseline benchmark, scored on tickets and line hits)
   and audits A2 and A4 first, then A1 and A3.
2. **Next:** the O-22 retrain, then P2's prelim re-run (the conditional bias correction only if the asymmetry
   survives); study 1 with P4's offset-dealing arm (build it first).
3. **Then:** P5 (calibration), study 3 + P7 (injury/Q), P9 (E0).
4. **Scope later:** P8.
5. **Closed:** P6 (recorded as measured facts).

Each item is preregistered before any outcome is read and goes to the reviewer first. Nothing changes the money path
without a test and the operator's adoption.
