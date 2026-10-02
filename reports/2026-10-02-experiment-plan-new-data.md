# Experiment plan for the new data (Fantasy Points DFS tier, articles, and the sources we already pay for)

**Written 2026-10-02 by the laptop, at the operator's request:** "put together a robust plan of experiments we can do as
soon as makes sense with all of this data". **Readers:** the operator (who adopts or cancels), the reviewer (who reviews
code and readers) and production.

## 0. What this plan is for

The operator upgraded Fantasy Points (FP) on 10-02 and wants two answers as early as the evidence allows:
1. **Which of the new data improves our entries?**
2. **Is FP a better source than one we already pay for**, so that one can be cancelled?

Every experiment below states its question, its data, its measure, the rule that decides it, and the earliest week it
can be read.

**Five rules hold throughout:**
- **Paper first.** Nothing enters a book until its paper result is read and the operator adopts it (adoption track v2,
  `reports/2026-09-19-in-season-adoption-track.md`).
- **The decision rule is frozen before the outcome exists.** For a prospective test that means before the first week it
  grades.
- **Pre-lock inputs only.** A capture made after lock never feeds a prediction (lesson: the Week-3 tilt's 156.8 used
  realized ownership).
- **Read the newest capture.** Every FP table is appended per capture, so a reader takes the newest `retrieved_at`.
  This is enforced in code (reviewer, 10-02).
- **One result is not a verdict.** Weekly reads are reported but decide nothing until the frozen week count is reached.

## 1. What we have, and how far back it goes

| Data | Source | Captured since | History for back-tests? |
|---|---|---|---|
| FP DFS ownership projections | `fantasy-points-ownership` | 2026 W4 (10-02) | **No**: the page serves the current week only |
| FP DFS projections (every slate, points, points/$, ownership) | `fantasy_points_projections dfs` | 2026 W4 | **No** |
| FP weekly projections (all scoring), expert rankings | `… weekly`, `rankings-*` | 2026 W4 | **No** |
| FP articles (15 full per week; betting ones are add-on only) | `fantasy_points_articles` | 2026 W4 | **No** |
| FP Data Suite, 28 reports (XFP, separation, routes, coverage, Bell Cow, PROE …) | `fantasy-points-download`, `-matchups` | 2026 weekly; **multi-season history** | **Yes**: the only FP data a walk-forward back-test can use |
| LineStar projected ownership | `linestar_ownership_capture.py` | 2026 (fills late in the week) | Historical field exists, but not provably pre-lock (09-29) |
| Our lag model / TabPFN ownership | `ownership_sets.py`, `ownership_tabpfn.py` | 2026 | Yes (L20/L23 panels) |
| Odds API props and lines | `ingest-props`/`odds` | multi-season | Yes (the 45/55 blend, Addendum 14/15, PREREG-007) |
| SIS charting | SIS DataHub | multi-season | Yes |
| Real field ownership and lineups | `contest_entries`, `contest_ownership` | 2026 W1–W3 (+ each Monday) | The grading target |

So **everything new from FP must be graded prospectively**, one week at a time from Week 4. The FP Data Suite is the
exception: it can be back-tested now.

## 2. The experiments

### Track A — Ownership (the lab's identified bottleneck: L05 cell C; the 09-29 study measured the term at lag +0.06 sd, LineStar blend +0.19, realized +0.19–0.33)

**A1. Which pre-lock ownership predictor is most accurate?**
- **Status:** PREREG-O1, FROZEN 09-28; amendment 1 adds LINESTAR, BLEND_LS and BLEND_FP.
- **Arms:** FP, LAG (the baseline), LINESTAR, BLEND_LS, BLEND_FP. TabPFN is co-reported (descriptive; not in the frozen
  rule).
- **Target:** realized Millionaire ownership from `contest_entries`.
- **Primary measure:** Spearman. MAE and top-15 overlap are co-reported.
- **Rule** (frozen): an arm replaces LAG only if its mean Spearman gain over Weeks 4–7 is >= 0.03 **and** it is better in
  >= 3 of 4 weeks.
- **Reads:** a descriptive quick read every Sunday ~12:30 (`score_ownership_sources.py`, on DK's `%Drafted`); the
  official read every Monday (from the lineups). **Decision after Week 7** (Monday 10-26).

**A2. Does a better ownership source make a better book?** (paper, weekly from Week 4)
- **Design:** on each week's archived T-70 frame, re-solve the main book (PMO_X50, cap 52, DST 26, the term at the
  armed tilt) with each predictor as the term's source: LAG, BLEND_LS, FP, TabPFN.
- **Grading:** DK points against the real Millionaire field: the mean z vs the field, rates over the top 20% / 10% / 1%
  lines, and tickets at the week's satellite lines. Same frame, same caps; only the source changes.
- The reviewer's `14_entered_design_2026.py` is the template.
- **Rule** (to freeze before Week 5's lock): a source is recommendable for the term when its book's mean z beats the
  entered source's in >= 3 of 4 weeks and on the 4-week mean. Otherwise it stays paper.
- **Earliest read:** Monday 10-05 (one week); decision with A1 after Week 7.

**A3. Article mentions as an ownership input** (Week-5 build; graded from Week 5)
- **Feature:** per player, the count of mentions (later a positive/negative score) in the week's widely read DFS
  articles (main-slate early look, Barfield's Slate Breakdown, Heath's Advanced Matchups), from the newest pre-lock
  capture.
- **Test:** does adding it to LAG (and to FP) raise Spearman with the real ownership?
- **Rule** (freeze before Week 5): the same +0.03 / 3-of-4 rule as O1, over Weeks 5–8.
- **Build:** a player-name matcher on article text, reviewed before it runs.

**A4. A calibrated combination** (after A1 has 3 weeks)
- If two sources are close, a fixed weighted blend (weights fitted on Weeks 4–6 only, frozen, then graded on Weeks 7–9)
  can beat both.
- Preregistered only if A1 shows complementary errors (correlation of the residuals < 0.8).

### Track B — Projections

**B1. Who projects DraftKings points best: FP, ours, or the market?** (weekly from Week 4; pure measurement)
- **Per player:** FP's DK projection (slate 154078 and each later main slate), our served projection (45/55
  model/market), the market-only mean where props exist.
- **Measure:** MAE and bias against actual DK points, by position, plus the correlation. Pre-lock captures only (the
  newest before lock).
- **Earliest read:** Monday 10-05. Reported weekly; no adoption by itself.

**B2. Does blending FP into our projection help?** (preregistered after 2 weeks of B1)
- **Arms:** ours (45/55 model/market) vs ours + FP at a fixed weight. The weight is set by a frozen rule (e.g. 1/3 each
  of model, market and FP), never fitted on graded weeks.
- **Grading:** projection MAE, Weeks 6–9, then a paper book (as A2) because of the post-ensemble law: a projection gain
  must survive selection.
- **Prior:** the market blend (Addendum 14/15) is the precedent; a third opinion is the same mechanism.
- **Earliest decision:** after Week 9.

**B3. When FP and we disagree, who is right?** (weekly from Week 4)
- **Cases:** every main-slate player with |FP − ours| >= 4 points, or one side 0 and the other >= 8 (the Bears-QB kind).
- **Recorded:** the cause from the news (articles and web), and who was right after the game.
- **Use:** an operational check before every Saturday and Sunday build (manual this week). If FP is right in most
  role-change cases, a rule (e.g. "a player FP projects >= 8 whom we project at 0 is flagged for review") goes to the
  operator.

**B4. FP Data Suite features in the player model** (the only FP back-test; lab panel)
- **Candidates:** XFP and weighted opportunity, separation, route participation and route share, Bell Cow backfield
  share, PROE.
- **Prior:** XFP was a candidate in the August panel ("positive alone; stays candidate", system study ~line 1546), and
  `xfp_l4` was structurally NULL at live inference then (line 1509). Read both before re-proposing.
- **Design:** walk-forward by season, six-season panel, co-run control on the same image, leave-one-season-out with at
  most one negative (the standing laws). The local panel follows the no-heavy-Cloud-Run rule.
- **Point-in-time:** every feature for week W from weeks < W only; leakage checks must pass.
- **Earliest:** preregister in Week 5; read in Week 6–7.

### Track C — The major-contest rows (the field sleeve armed 10-02)

**C1. The Millionaire row, graded weekly.**
- **Measured:** the field-sampled row's finish (percentile and z) against the projection sleeve's would-be row.
- **Reported** every Monday. It rests on rare events; no decision before 8 weeks.

**C2. Field-sleeve targets: FP vs LAG** (paper)
- Today the sleeve samples from the lag/TabPFN estimate. Re-draw it on the archived frame with FP's ownership as the
  targets, and grade it as C1.
- Recommendable only together with A1/A2 (it uses the same predictor).

**C3. The field model's payout lines.**
- The lab's field sampler predicts each contest's lines (the satellites' p91–p99.8).
- **Compare** the predicted with the realized lines each week, with LAG vs FP targets.
- **Use:** if FP targets predict the lines better, the cash/satellite decisions get a better line estimate.
- Weekly from Week 4.

### Track D — Which source to keep (the operator's cancel decision)

**D1. Overlap map** (Week 5; descriptive)
- For each paid source (FP Data Suite + DFS, SIS, LineStar, the Odds API), list the fields the system uses and the FP
  field that could replace each one.
- For overlapping metrics (e.g. SIS vs FP route participation, coverage and separation), the weekly correlation over
  2026 games.

**D2. Marginal value** (Week 6–8)
- **Design:** for each source in a decision path, rerun that decision with the source removed (or swapped for its FP
  equivalent) and measure the loss: projection MAE (B-track tools), ownership Spearman (A-track tools), book z (A2
  tools).
- SIS today feeds research shadows (the pass-tail gate), not the money path. Its marginal value to entries is likely
  small, and D2 measures it.

**D3. Decision memo** (after Week 8)
- Per source: what it feeds, what it adds over FP (D2), and what it would cost to replace.
- The operator decides. No source is cancelled on fewer than 4 graded weeks unless it feeds nothing.

### Track E — Articles

**E1. News cross-check** (from Saturday 10-03; operational)
- B3's disagreement list is checked against the week's articles (Injury Tracker, Game Hub, Everything Report) and the
  web before each build.
- Anything that changes a role goes to the operator before the build.

**E2. = A3** (mention counts as an ownership input).

## 3. Calendar

| When | What |
|---|---|
| **Sat 10-03** 10:07 | FP captures (ownership, projections, rankings, articles); B3/E1 disagreement report |
| **Sun 10-04** 10:38 | T-70 FP captures; B3 quick check |
| **Sun 10-04** ~12:30 | A1 quick read (descriptive) once the operator's post-lock export is imported |
| **Mon 10-05** | A1 official (O1) Week 4; A2 paper books; B1 accuracy; B3 who was right; C1 grade; C3 lines |
| **Week 5** (by Sat 10-10) | Freeze: A2 rule, A3 rule + matcher (reviewed), B2 weight rule. Preregister B4. D1 overlap map |
| **Weeks 5–7** | Weekly A1/A2/B1/B3/C1/C3 reads in HANDOFF (no action) |
| **Mon 10-26** (after W7) | **A1/A2 decisions** (ownership source for the term and the sets) |
| **Week 6–7** | B4 lab panel read |
| **After W8** | **D3 memo** (keep/cancel); A3 read |
| **After W9** | B2 decision (FP in the projection blend) |

## 4. Governance

- **Who runs it:** the laptop runs every reader. The reviewer reviews each new reader and collector before its numbers
  count. The operator adopts.
- **Where it is recorded:** every weekly read goes in `HANDOFF.md`; every frozen test's final read becomes a ledger row
  (`LEDGER.md` in the lab, or `reports/2026-07-25-system-study.md`). A test's rule is frozen in a dated file before its
  first graded week.
- **Multiplicity:** several arms against one baseline (A1 has five). A pass is flagged, never auto-adopted.
- **Small samples:** 4 weeks is a first decision, not a law. The validity laws (six-season panel, LOSO) still govern
  permanent adoption; in-season trials follow adoption track v2, with a rollback named.
- **Integrity:** no capture after lock feeds a prediction; FP's methodology may change mid-season (a break in B1 is
  investigated before it is believed); name matching is reported with its match rate.

## 5. Risks and what would stop an experiment

- **FP stops serving a table, or locks it.** The collectors fail loudly; the track pauses and the operator is told.
- **LineStar keeps filling late.** A1/A2 grade it on the weeks it filled, disclosed.
- **Too few weeks to separate the arms.** The decision becomes "not shown", and the incumbent stays.
- **Any experiment that would touch an entered book before its paper read.** Not done (money-path rule; the operator's
  10-02 waiver was for the major-contest rows only).
