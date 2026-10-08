# Preregistration: study 63, QB + tight-end stacks and a tight-end bonus, in the harness (FROZEN 2026-10-08)

**Status: FROZEN 2026-10-08 (00:26 CDT)** by the reviewer, after the smoke, the binding census (§6) and the bank scan,
before any scored bank.
- The DRAFT was `2cc4681b`.
- **Two definitions changed at the smoke, before any scored bank** (§2 now reads as changed):
  1. **A block that cannot be built** on a slate-bank (no qualifying player, or fewer than 6 opponents with a served
     label) FALLS BACK to LIVE_CB's book there, recorded, so its difference on that slate-bank is 0. The DRAFT said
     "missing". A per-arm set of slates would have broken the paired bootstrap.
  2. **QBTE_SHARE's 18 rows are chosen by BUILD ORDER j**, not book position. Term_book builds a cell's rows first and
     assigns their positions afterwards, so a position is not known when a row is solved. The round-robin over the
     cells still spreads them over the book.
- **Next:** the laptop's ack and bank scan, the run, the confirmatory census before the read, the frozen reader, the
  laptop's re-run and the records.

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
    block, as te_block_file refuses: the arm falls back to LIVE_CB's book there, recorded, so its difference there is 0
    (changed at the smoke; the census found a label on 0.887 of slate-banks).
- **CHEAPTE2_B8:** one block, +2 to a pass-catching TE OR any non-DST player under $4,000, with one cap. That is
  te_block_file's `--with-cheap` form.
- **QBTE_SHARE:** his percentage idea, tested rather than argued. It is LIVE_CB (the cheap block kept) with a QB + TE
  stack REQUIRED on 18 of the 26 book rows. Eighteen is the priority contests' winners' rate, .686 × 26 = 17.8.
  - **"Stack":** at least one TE from the QB's own team. It is enforced by the production optimizer's interaction
    floor: weight 1 on every (QB, TE of his team) pair, floor 1.
  - **Which rows:** book row j, in BUILD ORDER (the rows committed before it, as study 37's tier builder counts), carries
    the requirement when floor((j + 1) × 18 / 26) > floor(j × 18 / 26), which spreads 18 of the 26 book rows evenly over
    the build. The spares are unconstrained. (Changed at the smoke from book position: term_book builds a cell's rows
    first and deals their positions afterwards.)
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
  - **Banks 1599–1604**, seed **20261110**. Each slate's value is the mean over its six banks.
- **THE GO / NO-GO: 2022** (study 51's frozen rule, as study 53's reader implements it): the point estimate of
  P(≥ 1 big) ARM − LIVE_CB on 2022, with its two-sided 0.95 interval. CONTRADICTED if the point estimate is < 0.
  - Corrected at the freeze: the DRAFT's sentence said "the opposite sign, with its interval excluding 0", which is not
    the frozen rule. The reader always implemented the point-estimate rule; the text now matches it.
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
1. The DRAFT (`2cc4681b`). Done.
2. The code (lab `production/s63-qbte-20261008` @ `f3caa1f`) and the smoke. Done (§6).
3. The binding census, then the bank scan. Done (§6).
4. The freeze. Done (this text).
5. The laptop's ack and scan.
6. The run.
7. The confirmatory census before the read.
8. The read.
9. The re-run.
10. The records.

## 6. Smoke, census and integrity (before the freeze)
- **The smoke** (bank 1406, never a decision bank; Rev6; `~/s63-panel/smoke/`):
  - **Mechanics on 7 slates** (2023 W5 / W10 / W15, 2024 W4 / W8 / W10 / W14):
    - every arm is 41 rows within production's constraints, with 8 term rows;
    - the 126 required QB + TE rows were all satisfied;
    - LIVE_CB stacks a TE with the QB on 9–18 of 26 rows, QBTE_SHARE on 20–23.
  - **That finding shaped §2's reading of QBTE_SHARE.** The harness's live book already stacks more TEs (mean 13.7 of
    26 there) than his real W2–4 books (9–13 of 26). QBTE_SHARE is therefore "about 7 more QB + TE rows", not "from 40%
    to 69%".
  - **Scored on 2 slates** (2024 W10, 2022 W6) with the reader: it exited 0, and only its section labels were read.
    - Disclosed: on those two smoke slate-banks its TRIAL SUMMARY line printed verdict words. Bank 1406 and two slates
      carry no information on the decision banks.
- **The binding (support) census** (outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code `f3caa1f` clean;
  lab `results/s63/CENSUS_s63_binding.txt` `c053b84a…`, the raw mechanics rows `8abeb490…`, committed at `9ef4e4e`):
  - every arm is 41 rows within production's caps, QB cap and overlap limit, with 8 term rows (asserted);
  - the served labels: a tough third on 0.887 of slate-banks and a weak-against-TE third on 0.830. The early weeks lack
    them, and there those blocks fall back to LIVE_CB.
  - TE2_B8 and CHEAPTE2_B8 apply on 1.000;
  - QBTE_SHARE: 0 of 954 required rows were infeasible;
  - QB + TE rows of 26 (pass-catching): LIVE_CB 12.23 (8.87), TE2_B8 12.53 (10.72), TETOUGH2_B8 11.89 (9.68),
    CHEAPTE2_B8 13.28 (10.92), QBTE_SHARE 20.21 (13.75), TEWEAKD2_B8 12.21 (9.85);
  - rows shared with LIVE_CB: 18.1 / 18.9 / 18.6 / 3.0 / 19.4. Dealt identical on 0.000 / 0.113 / 0.019 / 0.000 / 0.170,
    so no arm is near the 0.80 dead-lever line. QBTE_SHARE's build path differs almost everywhere.
  - Build time: about 60 s per slate-bank.
- **The bank scan** (the reviewer's unique-blob scan, `bank_scan.py`) covered 17,886 production blobs and 8,076 lab
  blobs, up to 5 MB each.
  - It found no bank context for 1599–1604 in either repository, and no `results_bank1599`–`1604` file on disk.
  - Seed 20261110 appears only in this study's reader.
- **Code:** nfl2 `production/s63-qbte-20261008` @ `f3caa1f` (the census at `9ef4e4e`):
  - `experiments/s63_qbte.py`, sha256 `5fc6d50caa1998c2b3cfbf56cb75c1aa728c999a0b74080b9399bd0797e11bb1`;
  - `scripts/s63_drive.py`, `936c35cdf0d3bd8ab3a0651e0b840cc7ad9ea1055ddefd8018817d10045aa216`;
  - **`scripts/s63_report.py` (the reader), sha256 `5c24b8b9f329e68b3df1b20b986c6fea7264ca0dfdf1a862b961b7e1d1138848`**;
  - `scripts/s63_census.py`, `ff69f42dc9e4e40b73b9bd1865029d0bec1f97da1b6d6cb4fc4030a8a6f2b6e9`;
  - `tests/test_s63_qbte.py`, `b506a5daa0529bfb5106a20bf44c7d22d6a1da8be7cb195a049e44100e8af1d3` (8 tests);
  - unchanged and sha-asserted: `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`, `term_book.py`
    `62c2306e…`, and production's `enter_layout.py` `3cb051ac…`;
  - the plan: `plan-week5-rev6-s24.json` `ac10ddf6…`.
  - Disclosed: the raw census rows (mechanics only, no outcome field) are committed whole, not as a sha file as studies
    54–59 did.

