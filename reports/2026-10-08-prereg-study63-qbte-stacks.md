# Preregistration: study 63, QB + tight-end stacks and a tight-end bonus, in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08** by the reviewer, before any scored bank.
- Fixed here, before any code is run: the arms, the endpoint, the rule and the banks.
- Before the freeze come the code, the smoke (the full path; no decision-set outcome printed), the binding support
  census and the unique-blob bank scan.
- Then the laptop's ack and scan, the run, the confirmatory census, the frozen reader, the laptop's re-run and the
  records.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-07 night** (relayed by the outside reviewer; study list 63):
  1. "I would like to do more testing on the QB tight end stacks right away";
  2. "please engage with the production laptop to see if we can get a test running of this and perhaps consider a
     percentage of our lineups to have a QB tight end stack";
  3. "and also to include a bonus to the tight end in these types of situations."
- **The evidence so far** comes from the outside reviewer's note, `79a205f5` on `review/outside-fill-order-20261006`,
  `reports/2026-10-07-week5-options-this-week.md` §6–§7.
- **Twelve seasons** (2014–2025, point-in-time defence strength):
  - TEs do not score more against tough pass defences: TE1 +0.04 per sd (t 0.4).
  - The supported TE predictor is the opponent's record against TEs: TE1 +0.28 per sd of TE points allowed (t 3.0).
  - QB + a pass-catching TE reaches 45 points about three-quarters as often as QB + WR1.
- **The 2026 real fields:**
  - In W3–4, within-user, QB + TE beat QB + WR at the top 1% against strong pass defences (odds ratio 4.48), and the
    reverse held elsewhere. That is two weeks, likely a few games.
  - Over W2–4 the winners stacked ANY TE with the QB more often than the field (Millionaire top 1% .396 vs .303;
    priority contests' top 5% .686 vs .457). They were mostly not the established pass catchers.
- **Our book** already stacks a TE with the QB in 9–13 of its 26 rows, about 40%.
- **The W2–4 fixed-book replay** (in-sample) cannot rank the TE blocks against the cheap block: every 8-row block beat
  the weak live book.
- **The question for Week 6:**
  - Does any of the TE bonus forms beat the cheap +2 block, the Week-5 trial?
  - Does a fixed share of QB + TE stacks beat the live book's own mix?

## 2. Arms (`experiments/s63_qbte.py`)
**The book:** on each slate-bank, study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted), with LIVE = 48d's
41 rows: mix_fill rr, QB cap 5, caps 13 / 6, overlap limit 4. It is dealt on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`), as in studies 54–59.

- **LIVE_CB (the reference):** his live book with the cheap +2 block. This is study 53's CHEAP2_BLOCK8 and study 57's CB:
  8 rows on projection + min(0.20 × pred_own, 2.0), with pred_own = 2 / 0.20 for every non-DST player under $4,000.
- **TE2_B8:** the same live book, with an 8-row TE block INSTEAD of the cheap block. The block gives +2 to every TE whose
  frame `target_share_l4` is ≥ 0.15. That is production `te_block_file.py`'s rule (`196ae64e…`, its `build`), carried
  through study 53's `block_term`.
- **TETOUGH2_B8:** the TE block given only to those TEs facing the slate's toughest third of pass defences. This is the
  operator's form.
  - "Toughest" means the lowest `epa_per_dropback_allowed_l6`, AS SERVED. Production O-55 (`1004155c`) found that the
    live frame holds each defence's LATEST built row before week W, which is one game staler than training's
    exact-week row.
  - So the harness takes each defence's value from its last game week w′ < W: the median over the players facing it on
    the harness frame of week w′.
  - A defence with no earlier game that season has no value. A slate where fewer than 6 opponents have one gets no tough
    block (that arm is missing for the slate-bank, recorded), as te_block_file refuses.
- **CHEAPTE2_B8:** one block, +2 to a pass-catching TE OR any non-DST player under $4,000, with one cap. That is
  te_block_file's `--with-cheap` form.
- **QBTE_SHARE:** his percentage idea, tested rather than argued. It is LIVE_CB (the cheap block kept) with a QB + TE
  stack REQUIRED on 18 of the 26 book rows. Eighteen is the priority contests' winners' rate, .686 × 26 = 17.8.
  - **"Stack":** at least one TE from the QB's own team. It is enforced by the production optimizer's interaction
    floor: weight 1 on every (QB, TE of his team) pair, floor 1.
  - **Which rows:** book position q (0-based) carries the requirement when floor((q + 1) × 18 / 26) > floor(q × 18 / 26),
    which spreads 18 rows evenly over the 26. The spares are unconstrained.
  - **The MIX cells keep their own rules.** In cells B and C (exactly one pass catcher with the QB) the required TE is
    that one pass catcher.
  - **A row that cannot satisfy the requirement** under the cell and caps is built without it. It is counted and
    recorded, never silently dropped.
- **EXPLORATORY TEWEAKD2_B8** (history's supported form, beside his, per the test-both rule): the TE block given only to
  pass-catching TEs facing the slate's weakest third against TEs. "Weakest" means the highest `te_fp_allowed_adj_l6`,
  as served, built the same way as TETOUGH2's label.

## 3. Endpoint and rule (the reader `scripts/s63_report.py`)
- **THE READ: 2023–24** (36 slates). For each of the four decision arms, the arm − LIVE_CB on P(≥ 1 big seat), per
  slate, on the calibrated field v2.
  - The interval is two-sided 0.95, with B 20,000.
  - The seed and banks are named at the freeze, after the unique-blob scan.
- **THE GO / NO-GO: 2022** (the study-51 rule). A read whose 2022 estimate has the opposite sign, with its interval
  excluding 0, is CONTRADICTED.
- **Guards** as in studies 54–59. They gate a PASS only: the mean entry percentile and the expected-big-seats ratio.
- **Verdict per arm:** DEAD LEVER (the arm's dealt book is identical to LIVE_CB's on more than 80% of slate-banks) /
  WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **THE TRIAL RULE** (study 51's), per arm:
  - NOT ENTERED if WORSE, if CONTRADICTED, or if the expected-big-seats ratio is below 0.80;
  - MOOT on a dead lever;
  - otherwise ENTERABLE, his decision.
- **Multiplicity, disclosed:** four decision arms, each its own read for its own Week-6 choice, with no adjustment.
  Under no effect, a false PASS somewhere among the four has roughly a 10% chance.
- **EXPLORATORY:**
  - TEWEAKD2_B8 − LIVE_CB;
  - each arm on the l02 field;
  - P(≥ 2 big seats);
  - the QB + TE rows per book (any TE, and pass-catching TEs);
  - QBTE_SHARE's unsatisfied rows.

## 4. What a verdict can do
- **A TE block ENTERABLE:** his Week-6 choice is that block INSTEAD of the cheap block. There is one construction change
  per week.
  - Production writes it with `te_block_file.py`.
  - Live use needs the file written from the T-70 frame, or a `--group` form. A Saturday frame misses the T-70 joiners,
    the cheap writer's lesson.
- **QBTE_SHARE ENTERABLE:** new union code is needed: the interaction floor on the designated rows. Friday's rehearsal
  must run it before entry.
- **Otherwise:** the live book stands. Study 38's 6k paper arms keep the real-field record weekly.

## 5. Order
1. This DRAFT.
2. The code (lab `production/s63-qbte-20261008`) and the smoke.
3. The binding census: support, the arms' identity to LIVE_CB, the served-label coverage and QBTE_SHARE's satisfied
   rows. Then the bank scan.
4. The freeze.
5. The laptop's ack and scan.
6. The run.
7. The confirmatory census before the read.
8. The read.
9. The re-run.
10. The records.
