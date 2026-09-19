# In-season adoption track (operator directive, 2026-09-19)

**Authority.** Erich, 2026-09-19 ~16:50Z: *"We need to change the rules immediately so we can realize gains as
early as possible this year. Audit the rules and change any that are contrary to my objectives of winning quickly.
Then let the labs know the rules have changed."* The operator retains protocol and bankroll decisions; this document
records that decision and the rules that implement it. It supersedes every earlier sentence that made the historical
six-season panel a prerequisite for using a change in-season, and the 2026-09-18 handoff line that research be
presented "rather than implying in-season upside".

**Objective.** Realized gains in the **2026 season, as early as possible.** Every proposal, read and handoff states
(a) the earliest week it can change the entered book and (b) its risk class below. The six-season historical panel
remains the bar for **permanent** (next-season default) adoption; it is **not** a prerequisite for in-season use.
"Evidence rules must inform risk, not veto upside" (owner directive 2026-08-30) is the governing principle: agents
state the evidence and the risk plainly; adoption is the operator's decision and he may adopt any class at any time.

## 1. Risk classes and the evidence each needs before it enters the entered book

| class | what | evidence required | rollback |
|---|---|---|---|
| **R — repair** | an input restored to what it should have been: data plumbing, stale inputs, identity or unit bugs, a calibration defect traced to a mechanism | correctness verified — the unchanged leakage checks pass; parity exact on every row the repair does not claim to change; magnitude measured and reported. **No outcome evidence needed: a repair is not a bet.** | the previous pinned commit / data snapshot recorded before adoption |
| **C — calibration / weighting** | mixture weight between simulator components, world weights, mean or spread corrections not traced to a defect | the weekly scorecard (§2) — player-level proper score (CRPS, MAE) on realized DK points — favours the candidate in **2 consecutive graded weeks, or 3 of the first 4**; and a fixed-book replay on the archived 2026 populations does not contradict it | revert after 2 consecutive losing weeks |
| **S — selection / objective / construction** | anything that changes which lineups are chosen or how candidates are generated | a **paired, prelock-frozen shadow book every week**; adopt when the shadow beats the live book on the frozen objective ladder's primary in **3 of the first 4 graded weeks** with a positive pooled paired difference. The historical panel is not required first. | revert after 2 consecutive losing weeks |
| **E — entry-side** | contest mix and order, entries per contest, dose within the tested range, the late-swap / scratch protocol | none required — the operator decides at any time; agents supply the evidence and the one-line change | n/a |

The bars above are defaults chosen for speed with the weekly variance in mind; the operator may tighten or loosen
them. Player-level scores (hundreds of players a week) carry far more power than one book maximum a week, which is
why class C reads at the player level and class S needs the paired shadow.

## 2. The weekly scorecard — mandatory from Week 2

Run as soon as realized DK points for the Sunday-main slate are in the warehouse (normally Monday):

- **served projections vs realized** — MAE and CRPS by position; coverage of p10 / p50 / p90;
- **each simulator component vs realized** (incumbent, hsim) — CRPS on player marginals; realized vs simulated
  P(lineup ≥ 200 / 220) over the delivered pool; realized best-in-book vs each component's expected best;
- **the entered book** — realized best, count ≥ 187 / 194 / 200 / 220, contest results from standings;
- **every class-S shadow book**, scored identically and paired against the live book.

One tracked row per week per instrument (`reports/scorecards/2026/week-NN.md` on the production side; the lab's
`nfl2.scorecard` on its side), read as soon as it exists. Week 2 (slate 2026-09-20) is the first.

## 3. Reads are immediate

A completed bank or capture is read with its frozen reader as soon as that reader exists. A deliberate unread hold
needs the operator's explicit instruction and a written reason. Where a reader amendment is required first (PREREG-099
bank 991 needs the amendment-5 reader), the amendment is frozen pre-read and the read follows the same day where
possible.

## 4. Multi-season gates get pre-specified interim reads

A gate that by design reads only after Week 18 (the 2026 Route Share gate) is amended to add interim reads at fixed
graded-week counts with a pre-specified interim rule. An interim pass permits in-season use under class S; the final
read still governs permanent adoption. See Amendment 1 in `reports/2026-08-11-route-share-2026-shadow-gate.md`.

## 5. Shadows start immediately

A treatment with a positive development read enters the **next** week's paired, prelock-frozen shadow. The
"pre-registered prospective clock" now governs when adoption may be *recommended* (the class bars in §1), not when
shadowing may begin.

## 6. Unchanged — each of these is what makes a measured gain real, not a delay

- Point-in-time is sacred; leakage checks are never weakened.
- Walk-forward only; never random splits.
- Evaluation rules are frozen **before** outcomes are seen; no retrospective tuning on slates already read.
- Audit before verdict; vacuity checks; the post-ensemble / post-selection law.
- The identity gate on entered books (`EXPECT_SHA`); never enter an untested change on an entered book — the test is
  the shadow or the fixed-book replay, run before the build.
- Scratch protocol: remove a player only when confirmed OUT.
- Single-writer lanes; the Cloud Run quota rule; never commit in a worktree whose bank is running; one heavy local
  process at a time.
- Frozen prospective gates must be armed on the current policy — this is what produces the weekly evidence the track
  runs on.

## 7. Immediate consequences (recorded 2026-09-19)

1. **Week-2 scorecard** runs Monday 2026-09-21 on realized points; incumbent vs hsim is the first class-C instrument.
2. **O-2** (Route Share jobs to `N_BOOM=160` / `N_LEV=40`, schedulers ENABLED) on Monday, so Week 3 is graded —
   under Amendment 1's interim reads.
3. **Bank 991**: freeze the amendment-5 reader, then read — pending the operator's yes.
4. **hsim mean offsets** (RB +2.16, TE +1.12, WR +0.93, DST −0.81 on the Week-2 archive): traced to a defect →
   class R; otherwise a class-C candidate scored from Week 2 on.
5. **TabPFN active-only fit**: class-C candidate; preregistered paired shadow from Week 3 if the lab can build it.
6. The six-season historical panel program continues in the background for permanent adoption only.
