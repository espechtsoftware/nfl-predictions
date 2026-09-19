# In-season adoption track (operator directive, 2026-09-19) — v2, incorporating the lab's independent review

**Authority.** Erich, 2026-09-19 ~16:50Z: *"We need to change the rules immediately so we can realize gains as
early as possible this year. Audit the rules and change any that are contrary to my objectives of winning quickly.
Then let the labs know the rules have changed."* The operator retains protocol and bankroll decisions; this document
records that decision and the rules that implement it. **v2 (17:2xZ)** replaces v1's fixed multi-week sign-count
bars and automatic two-loss rollback with the candidate-specific standard below, on the lab's independent review
(`reports/2026-09-19-in-season-rules-independent-review.md`, research branch `45e5a25c`): sign counts discard effect
size and tail utility, 3-of-4 under a fair coin is 5/16, and a four-week wait is unnecessary when transferable
evidence already exists. v2 is faster than v1 and keeps every integrity law.

**Precedence.** This document governs over any earlier sentence that (a) made the six-season historical panel a
prerequisite for using a change in-season, (b) required "72 historical books" before any entered-book change (the
requirement is *a test before entering*, in whatever form the change admits — historical books where they exist,
otherwise a fixed-book replay or a paired shadow), (c) said research should be presented "rather than implying
in-season upside", or (d) treated a method-family closure as a prohibition on a differently scoped trial.

## 1. The governing standard

> The goal is useful improvements in the current season. Evidence requirements inform the strength and scope of a
> recommendation; elapsed weeks, an old experiment's endpoint, and a method-family closure do not independently
> prohibit a reversible trial. Each candidate states its mechanism, exact change, primary utility, evidence and known
> tradeoffs, earliest usable week, operational proof, unchanged comparison, monitoring plan, and rollback. The
> operator decides adoption. Scientific verdicts retain their frozen rules and are reported separately from that
> decision. Integrity failures always stop release.

A **reversible in-season trial** may be recommended as soon as its candidate-specific evidence package is ready —
not after a fixed number of weeks. The package is one short **decision record** linked to the code, the comparison
and the release proof: cumulative paired effect with uncertainty, mechanism, the unchanged control, known costs, the
review date and the material-harm criteria (tied to the chosen utility, not to a sign count), and the restore path.
A trial is a decision under uncertainty, not a declaration of a confirmed effect; stronger evidence supports broader
adoption. No claim of a proven gain from one slate.

**Stopping.** Integrity failures (identity, legality, leakage, data contract, implementation) stop a trial at once.
Efficacy is reviewed on the candidate's preregistered review dates against its material-harm criteria; two weeks
without the rare tail we want do not by themselves invalidate a tail policy, and automatic switching on a loss count
would itself be an untested selection policy. The control is always retained for comparison and rollback.

## 2. Risk classes — what each candidate's package must contain

| class | what | package contents | rollback |
|---|---|---|---|
| **R — repair** | an input restored to what it should have been: data plumbing, stale inputs, identity or unit bugs, a contract defect traced to a mechanism | the broken contract and the intended correction, proven; the **unchanged** leakage checks passing; exact identities and **declared numerical tolerances** on values the repair does not claim to change (bitwise equality is not assumed for nondeterministic float reductions); propagation quantified through the final consumer (means, selections, entered book); no NFL-outcome wait is required for correctness. "Mechanism explained" alone does not make a model hypothesis a repair. | previous pinned commit / data snapshot recorded before adoption |
| **C — calibration / weighting** | component mixture weights, world weights, mean or spread corrections not traced to a defect | measured **at the final consumer being changed**: served-law and fixed-lineup / fixed-book diagnostics with predeclared tail scores, not player-marginal CRPS alone (marginals can improve while shared-world dependence or selected extremes worsen). CRPS for distributions; point MAE reported separately (it favours a median). A point projection alone cannot supply distribution CRPS. Plus the archived fixed-book replay on 2026 populations. | revert to the prior weights; control retained |
| **S — selection / objective / construction** | anything that changes which lineups are chosen or how candidates are generated | a **paired, prelock-frozen shadow book** each week it is ready; one primary matching the operator's utility, with the other quantities (components, prefixes, contest blocks, expected max, proxy, P220) reported as **explicit costs** under narrowly justified material-harm limits — **no universal dominance veto** (requiring every cell non-negative makes the search unable to propose a useful tradeoff); independent audit worlds; proposals from selection worlds, evaluated once on separate audit worlds; all proposed books reported, losers included. The historical panel is not required first. | revert to the incumbent selector; control retained |
| **E — entry-side** | contest mix and order, entries per contest, dose within the tested range, the late-swap / scratch protocol | the operator's authority, plus: mechanical rehearsal (legal complete books, exact identities), the affected entries named, and a restore path. Classify the underlying change by what it does — a new optimizer called "entry-side" still carries model risk. No new universal historical gate. | the restore path in the record |

## 3. The weekly evidence record — from Week 2

Run as soon as realized DK points for the Sunday-main slate are in the warehouse (normally Monday), with the
**accepted proper-score reader** (`review/2026-09-prospective-proper-score` @ `1c95dd68`; protocol
`reports/2026-09-19-prospective-proper-score-protocol.md`) unchanged as the frozen instrument, and separately frozen
extensions (delivered ordering, coverage, tail scores) that must not imply selected-bank forecasts are independent
audit banks:

- served projections vs realized — CRPS by position, mean bias and squared error for served means, median MAE
  reported separately, p10 / p50 / p90 coverage, upper-tail pinball scores;
- each simulator component vs realized (incumbent, hsim, pooled mixture) — player marginals, fixed lineup totals,
  fixed-book maxima; realized vs simulated P(lineup ≥ 200 / 220) over the delivered pool;
- the entered book — realized best, count ≥ 187 / 194 / 200 / 220, contest results from standings;
- every class-S shadow book, scored identically and paired against the live book.

**Monitoring is not inference.** Display every weekly result promptly; the weekly record is *descriptive* unless a
prespecified sequential procedure (with its assumptions checked) is declared for a candidate — fixed-sample intervals
checked every week are not valid stopping rules, and no method creates more independent NFL slates. Actuals stay
behind the settled-slate gate; never use a week's realized high scorers to select the shadow being graded.

## 4. Reads are immediate

A completed, validated result is read with its correct frozen reader under its existing outcome-access authority as
soon as that reader exists. Missing or failed tasks are never silently dropped. Reader repairs and mechanical failures
are resolved promptly, not left as holds. A deliberate unread hold needs the operator's explicit instruction and a
written reason. (Bank 991: authorized by the operator 2026-09-19 ~16:57Z, "Yes on bank 991"; the amendment-5 reader
is frozen pre-read, then the read follows.)

## 5. Multi-season gates: the frozen scientific read stays; a weekly decision record is added

The 2026 Route Share gate's final read after Week 18 — its lexicographic 240/230/220/210/200 primary, its 12-week,
2,500-row and 40-event floors — is unchanged and governs permanent adoption. Amendment 1 (v2) adds a **separately
named weekly in-season decision record** from the first complete paired week (Week 3), with its endpoint and available
support stated explicitly, the original floors never silently waived, and bounded in-season use considered under §1
with the actual uncertainty. Its original exact-80 consumer and historical generation contract must be shown to
transfer to today's lab K97 / dose before any live claim; a frozen contract is never changed in place — a **versioned
current-policy companion** states every generation / env / registry / K / selector setting (O-2).

## 6. Shadows start when they are ready, prioritized by information and gain

Any mechanically ready, supported candidate with a clear hypothesis and a frozen comparison enters the next week's
paired prelock-frozen shadow, prioritized by expected information and potential gain, with owner, compute limit and
earliest week named. A positive reused-panel score is neither necessary nor sufficient; an unsupported or vacuous arm
must not consume the build window.

## 7. Permanent adoption and closures

Validation for a permanent (next-season default) adoption is proportional to the mechanism and the available data:
six-season panels with a co-run control where six seasons exist; a licensed source with fewer seasons is evaluated on
what exists, with the shortage stated, never invented and never treated as proof of no value. The 2026-09-01
objective ladder and its L2 tail carve-out govern new studies (LOSO is *reported*, not a veto); each old experiment
keeps its own frozen rule and verdict. Every closure names four dimensions — implementation, information set,
objective, budget — and a new candidate must state which changed; repeated tuning of an unchanged failed arm is
exploration and is labelled so.

## 8. Unchanged — each of these is what makes a measured gain real, not a delay

Point-in-time data and unchanged leakage checks; legal complete books; explicit player / contest identity;
walk-forward training; evaluation rules frozen before outcomes are seen; independent audit randomness; same-build
controls when code changes; immutable artifacts and archived original verdicts; development-look counts and
independent reproduction; the identity gate on entered books (`EXPECT_SHA`); the scratch protocol (remove a player
only when confirmed OUT); single-writer lanes and protection of running jobs; the Cloud Run quota rule; never commit
in a worktree whose bank is running; host capacity limits (one heavy local process). Frozen prospective gates must be
armed on the current policy — that is what produces the weekly evidence. A calendar-wide ban on every production job
mutation is too broad: name the shared resource, the release risk and the latest safe window instead.

## 9. Immediate consequences (recorded 2026-09-19)

1. **Week-2 record** Monday 2026-09-21 on realized points, with the accepted reader; incumbent vs hsim is the first
   class-C instrument, read at the final consumer.
2. **O-2**: versioned current-policy companion (40/160/CE0 and every other setting) prepared for review; the two
   shadow jobs re-pointed and the four schedulers enabled on Monday 2026-09-21 so Week 3 is graded; the original
   12-CE / 12-role / 28-boom / exact-80 contract and its verdict preserved as documents.
3. **Bank 991**: amendment-5 reader frozen, mechanical checks run, then read once; reported as the replication row.
4. **hsim mean offsets**: the laptop's refreshed calibration trace is running on the morning D160 proof; a proven
   contract defect → class R for Week 3; otherwise a class-C candidate with its own decision record.
5. **Active labels × participation**: four-arm protocol prepared (`reports/2026-09-19-active-label-participation-experiment.md`);
   earliest shadow Week 3; the live cache stays the adopted artifact until a reviewed release.
6. **Selection**: a frozen tradeoff-frontier comparison on the finished K97 corpus replaces universal-dominance
   screens; a Week-3 S trial candidate only if it supports one.
