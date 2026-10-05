# What would let the system actually win: a ranked plan from the evidence (2026-10-05)

Written for the operator ("Keep going so the system can be improved so it actually can win"). The reviewer checks it
before any item becomes a study or a change. Every claim cites its source.

## Where we are (measured)

1. **The current system, replayed on Weeks 1–4 against the real fields and payouts, returns about 0.48× of fees.**
   Range 0.36–0.67 (`briefings/2026-week-04/2026-10-05-week5-money-gate-result.md`). None of the selection changes tested beats it.
2. **Money results can never prove an edge within a season.** A real 15% edge needs hundreds of weeks to show
   (`briefings/2026-week-04/2026-10-05-p1-contest-type-edge.md`). The satellites ran below break-even (0.12×), robustly.
3. **Our lineups score about the same as the crowd's, not better.**
   - Over W1–4 they averaged −0.15 sd against the Millionaire field (−0.55 to +0.25); break-even needs +0.12 to
     +0.22.
   - In Weeks 3–4 our picks were not more over-projected relative to the market than the field's picks were (model
     minus market +0.5 vs +0.3 per player). The losses came from **correlated busts in a concentrated book** (Week 4:
     our QBs 7.2 under projection, the field's 2.4; our WRs 7.3 under, the field's 1.2).
   - (`scratchpad curse/curse_w34.json`; W1–2 lack the projection log.)
4. **Six seasons of preregistered tests closed most modelling levers** (`reports/2026-09-14-project-briefing-for-a-new-model.md`
   §3, §7):
   - generator families;
   - selection objectives, including finish-against-the-field (PREREG-098: decisively worse);
   - paid data;
   - deeper or relaxed stacks (016, 043, 053/055);
   - player filters and late swap.

   Tail calibration (PREREG-101) was signed and then withdrawn for cause and is not to be launched. The one monotone
   lever was dose, now saturating.

**Plain reading:** the system builds lineups about as good as the average entrant's. In contests with a 15% rake and
top-heavy payouts, an average lineup loses money. Winning needs a structural edge, not a slightly better projection.

## Ranked plan

### 1. Play where the structure pays: overlays and the lowest rake (this week, no model change)
- **The only structural +EV seen in four weeks was an overlay.** The W2 FFWC 4× supersat ran 59 of 85 entries with
  tickets guaranteed: a pool ratio of 1.22. A field-average lineup broke even there at 0.82× the field's cash rate
  (P1).
- **The rake differs a lot by contest.** The 11-entry satellites keep 9%; most others keep 13–16%.
- **Proposal:** a read-only **overlay monitor**.
  - From the DK contest pulls the system already captures (`dk_contest_fills`), list every guaranteed contest on the
    slate, its entries against its maximum, and its projected fill at lock.
  - Shortly before lock, flag those projected to overlay (prize pool / (projected entries × fee) > 1).
  - The operator decides whether to enter them; nothing is entered automatically.
- **Why first:** it needs no edge in projections. An average lineup in an overlaid contest is +EV.
- **Cost:** about a day; read-only, no money-path change.

### 2. Stop concentrating the book (variance we are not paid for)
- Week 4: 61% of entries held 3+ players from one game, one triple sat in 58% of the book, the ownership sum was 152
  against the field's 110, and a third of our distinct lineups were duplicated by other entrants.
- The money-gate replay's tighter cap (30%) was **not** better on how lineups finished, so a cap alone is not the
  answer.
- **The lever with evidence is game and player diversification across contests:** the same expected points with less
  correlated risk. That is study 1 plus P4 (offset dealing), to be preregistered and tested on history before entry.

### 3. The contrarian sleeve (operator's request; study 13)
- **What history says:** the ownership study found that leaning TOWARD popular players improved finish (+0.19 sd,
  2023–24, 36 slates; `reports/2026-09-29-ownership-term-week4-arming.md`). That measures finishing position, which
  ignores prize splitting.
- **The case for a small contrarian sleeve is DUPLICATION.** When a chalky lineup hits, its prize is split with its
  copies; a contrarian lineup that hits is not.
- **So the test must score payouts with a duplication model**, or it will just repeat the old answer:
  - the 53 historical slates with real ownership and the stored 800-lineup pools (PREREG-098 archive:
    `gs://nfl-2-506823-lab/results/118_finish_objective/`);
  - a pre-lock ownership predictor only (the lag + LineStar blend from the ownership study), never the realized
    ownership;
  - the gated field sampler.
- Preregistered with the reviewer before it is run.

### 4. Projection hygiene (in progress)
- **O-22:** two features leak in training, so the live model differs from the trained one. It is being fixed; a retrain
  only after its co-run.
- **The model alone is worse than the market every week** (P2 prelim: MAE market 5.28 < served blend 5.43 < model
  5.78). The 55% market weight already absorbs most of that.
- **Expected gain:** small. This is hygiene, not the edge.

### 5. Stake sizing until an edge exists
- **Measured:** the system has no measurable edge in any contest type, and money results cannot show one this season.
  An evidence-based stake is therefore small.
- **The quickest real information** comes from paper tracking and from structure (item 1), not from more money in
  top-heavy contests.
- The stake is the operator's decision; this is the evidence for it.

## What I will do next (today, unless the operator says otherwise)
1. Build the overlay monitor (item 1), read-only, and run it on this week's Week-5 slate.
2. Draft the study-13 preregistration (item 3) for the reviewer.
3. Finish the Week-4 post-mortem when the Sunday play-by-play data lands, and import the settled standings.
