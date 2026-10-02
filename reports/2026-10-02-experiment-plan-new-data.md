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
- **Reads:**
  - a DESCRIPTIVE quick read every Sunday ~12:30 (`score_ownership_sources.py`, on DK's `%Drafted`; it can differ
    from Monday's, because `%Drafted` omits identical-share slot rows);
  - the official read every Monday (counted from the lineups).
  - Every read reports each source's name-match rate (the normaliser drops Jr/Sr/II/III).
- **Decision after Week 7** (Monday 10-26).

**A2. Does a better ownership source make a better book?** (paper, weekly from Week 4)
- **Design:** on each week's archived T-70 frame, re-solve the main book (PMO_X50, cap 52, DST 26, the term at the
  armed tilt) with each predictor as the term's source: LAG, BLEND_LS, FP, TabPFN.
- **Grading:** DK points against the real Millionaire field: the mean z vs the field, rates over the top 20% / 10% / 1%
  lines, and tickets at the week's satellite lines. Same frame, same caps; only the source changes.
- The reviewer's `14_entered_design_2026.py` is the template.
- **A2 is a no-harm GUARD, not the decider** (reviewer, 10-02):
  - Each week is one book-level draw. "Beats in >= 3 of 4 weeks" passes a source that is no better about 30% of the
    time. With three challengers, roughly 50–65% that one passes on noise. In the K = 105 replays, week-to-week source
    differences were 0.1–0.4 sd: the size of the effect.
  - **The ownership source is adopted on A1** (accuracy, thousands of player observations a week). A source that passes
    A1 is recommendable unless its A2 4-week mean z falls below the entered source's by more than 0.10 sd.
  - A2 adopts on its own only with a magnitude bar (a 4-week mean gain >= +0.10 sd **and** >= 3 of 4 weeks), the
    challengers named in advance, and the multiplicity disclosed.
- **Earliest read:** Monday 10-05 (one week); decision with A1 after Week 7.

**A3. Article mentions as an ownership input** (Week-5 build; graded from Week 5)
- **Feature:** per player, the count of mentions (later a positive/negative score) in the week's widely read DFS
  articles (main-slate early look, Barfield's Slate Breakdown, Heath's Advanced Matchups), from the newest pre-lock
  capture.
- **Test:** does adding it to LAG (and to FP) raise Spearman with the real ownership?
- **Rule** (freeze before Week 5): the same +0.03 / 3-of-4 rule as O1, over Weeks 5–8.
- **Frozen with the rule, before Week 5:** WHICH articles count, by category or title pattern. Otherwise the feature
  can be tuned by choosing articles after the fact.
- **Build:** a player-name matcher on article text, on the same normaliser as the ownership readers
  (`ownership_blend.norm`: Jr/Sr/II/III dropped), reviewed before it runs.

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
- **Arms** (weights FIXED, never fitted; reviewer, 10-02: two weeks cannot pin three weights):
  - ours (0.45 model / 0.55 market);
  - **the primary: 1/3 model, 1/3 market, 1/3 FP**, consistent with L04's ordering (more consensus weight did better);
  - **co-reported: 0.45 model, 0.275 market, 0.275 FP** (keeps the model's tested share).
- **Coverage rule** (frozen): when FP or the market is missing for a player, the weights renormalise over the sources
  present, and the coverage is reported per position. Otherwise missing FP silently becomes a different blend for
  backups.
- **Grading:** projection MAE **by position** (FP may help at WR and not at DST), Weeks 6–9, then a paper book (as A2)
  because of the post-ensemble law: a projection gain must survive selection.
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
- **First, an outcome-blind audit** (reviewer, 10-02), cheap:
  1. **Coverage:** the share of skill players with a non-NULL `xfp_l4` (and each candidate) in
     `player_week_inference` at the live build, 2026 W1–4, against the panel's historical rows. A live share far below
     the panel's means the gain would not transfer (the August finding).
  2. **Revisions:** re-download an old Data Suite week and compare it with its original capture. A revised history
     makes the walk-forward optimistic.
- **Then preregister.** The six-season panel is heavy and the workstation is off: on the laptop, after Monday's
  grading, one process at a time, never on a build day.
- **Earliest:** audit and preregister in Week 5; read in Week 6–7.

### Track C — The major-contest rows (the field sleeve armed 10-02)

**C1. The Millionaire row, graded weekly.**
- **Measured:** the field-sampled row's finish (percentile and z) against the projection sleeve's would-be row.
- **Reported** every Monday. **Eight weeks will probably still not decide it.** Top-0.1% events are a handful a season,
  so "no decision" is the likely outcome, and the row stays an operator choice.

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

## 3. Calendar (ESCALATED, operator 10-02: "I will want those timelines escalated")

The constraint that does not move: real weeks arrive one at a time. The levers:
- A3 and B2 grade from **Week 4** (rules frozen before the Week-4 lock: `reports/2026-10-02-PREREG-A3-B2-escalated.md`).
- **One early checkpoint after Week 5** with a doubled bar (O1 amendment 2; the same for A3/B2). A clear winner can
  start a reversible trial in Week 6.
- The outcome-blind work happens now: the B4 audit and the D1 overlap map this weekend; the B4 panel right after
  Monday's grading.
- The keep/cancel memo after Week 6.

| When | What |
|---|---|
| **Fri 10-02** | FROZEN: O1 amendment 2 (interim after W5); PREREG-A3 and PREREG-B2 (grading from W4) |
| **Sat 10-03** | FP captures 10:07 (feed A1/A3/B2); B3/E1 disagreement report; **B4 audit** (outcome-blind); **D1 overlap map** |
| **Sun 10-04** | T-70 captures 10:38; A1 descriptive quick read ~12:30 |
| **Mon 10-05** | Week-4 reads: A1 (official), A2, A3, B1, B2, B3, C1, C3. B4 preregistered; **the B4 panel starts on the laptop Monday night** (one process; never on a build day) |
| **Week 5** | A3 matcher and B2 blend code reviewed (they run Monday 10-05 on Week 4's pre-lock captures; nothing about the rules changes) |
| **Mon 10-12** (after W5) | **The early checkpoint:** A1/A3/B2 interim. A clear winner → the operator may trial it from Week 6. B4 panel read. D2 marginal value starts |
| **Mon 10-19** (after W6) | **D3 keep/cancel memo** (4 graded weeks for the ownership sources; 3 for the rest; disclosed) |
| **Mon 10-26** (after W7) | **The finals:** A1/A3/B2. A trial that fails its final is rolled back |

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

## Review

The reviewer reviewed this plan on 2026-10-02 (HANDOFF entry of that time). Their changes are folded in above:
- A2 is a guard, not the decider.
- B2 keeps fixed weights, with a co-reported alternative, the coverage rule and grading by position.
- B4 starts with an outcome-blind audit.
- C1's likely "no decision".
- A3's article set is frozen in advance, on the shared normaliser.
- The quick read is labelled descriptive, and match rates are reported.
