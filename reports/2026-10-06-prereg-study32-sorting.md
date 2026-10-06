# Preregistration: study 32, choosing the best few lineups for a big contest (DRAFT 2026-10-06)

**Status: DRAFT 2026-10-06.** To be frozen after the one-slate smoke, before the binding census and any scored bank.
The reviewer freezes it and reads first. The laptop comments on this draft, acks the census and re-runs the frozen
reader.

## 1. Why
- **The operator (10-06):** "we NEED to have a way to sort lineups. Im trying to win entries to large contests this
  week. If successful, i will have a limited number of entries to big contests next week, so we need to figure out how
  to choose the best ones."
- **The honest prior is that we cannot rank our own lineups.** Every past attempt failed:
  - A13: the week's best row had a median rank of 15 of 40.
  - A62: our #1 pick landed at the 49th percentile of our own book; Spearman +0.086; "ranking is decorative", and
    breadth is what held.
  - A93: the reranker was falsified five ways, and ownership features made it worse.
  - A114: the oracle gap is upstream of ranking.
  - Study 18: the line-aware deal was CLOSED (+3–4% in-sample, nothing realized).
- **Two things are new:**
  - His case is small m: 1–3 entries in a field of 634 or 4,170.
  - The one family that ever validated, JOINT coverage (choosing a SET for P(at least one clears the line)), has never
    been read at small m.
- **This study asks whether any rule beats a uniformly random choice from the same book.** If none does, the answer to
  him is "co-equal shots".

## 2. Design (study 31's harness)
- **Slates:** the 36 `k1` slates of 2023–24.
- **Plan and book:** the Rev3 plan (`3dd19d6c…`), K 26, caps 13 / 6, head; `enter_layout` pinned `3cb051ac…`.
- **The two Week-5 candidate books:** CT (the house shape + 0.20 × TABPFN_LS ownership: the status quo) and MIX (the
  winners' mix, no term: the package).
- **The choice is from the book's 26 entered rows**, never the spares.
- **Targets** (this week's DraftKings lobby, 10-06; labelled as such; next week's may differ):

| Target | N | S_big (every paid place) | S_top (paying ≥ 2× the fee) |
|---|---|---|---|
| $4,444 MEGA Millionaire | 634 | 119 | 54 |
| $333 Wildcat | 4,170 | 1,000 | 270 |

- **The lines:**
  - S_big counts every paid place. All of them pay at least $500, his existing "big" threshold.
  - S_top is the operator's open question (does "big" inside a target mean more than a min-cash?). It is carried as
    exploratory.
  - The $555 Millionaire is not open this week and is left out.
- **m = 1, 2, 3.**
- **Rules** (each picks m of the 26 rows; outcome-free):
  - **R0:** book order, rows 1..m (what he does by default).
  - **R1:** the highest projected mean. FP is not in history, so this is our simulated mean.
  - **R2:** the highest simulated P(top S), one row at a time.
  - **R3:** the highest simulated ceiling (the row's 99th percentile).
  - **R4, JOINT coverage:** the m-subset that maximizes simulated P(at least one in the top S), exhaustive over C(26, m).
  - **R5, breadth first:** distinct QBs and distinct QB games, the best mean within that.
  - **RND (the CONTROL):** every m-subset equally likely, computed EXACTLY in the reader.
- **The simulation behind R2–R4:**
  - 1,000 of the run's own worlds, against a PRE-LOCK field of 20,000 lineups sampled from TABPFN_LS predicted ownership
    (skill players) with DSTs uniform.
  - Never the realized ownership.
  - At m = 1, R2 and R4 coincide by construction.

## 3. Banks
- Fresh **1437, 1438, 1439, 1440, 1441, 1442**.
  - Scanned 10-06: no hits in either repo's ledger, preregs, code or results. PREREG-092's "D1440" is a world count, not
    a bank.
  - The laptop scans independently.
- Each slate's value is the mean over its six banks.
- The census runs on 1406.

## 4. Endpoint and decision rule
- **The realized value of a chosen set A:**
  - Formula: P(the best of A is in the top S) = P(Bin(N − m, 1 − max_{r∈A} F_r) ≤ S − 1).
  - F_r is the row's realized percentile in the sampled field (the realized-ownership Millionaire field, as every
    study uses). Ties count as losses.
- **PRIMARY:** R4 − RND, the mean over the 12 cells {CT, MIX} × {MEGA, Wildcat} × {m 1, 2, 3} at S_big.
  - Slates resampled within season, B 20,000, seed 20261014; two-sided 0.95.
- **VERDICT:**
  - **OFFER R4:** the lower bound > 0 and at most one season mean < 0.
  - **R4 WORSE THAN RANDOM:** the upper bound < 0. Do not use it.
  - **CO-EQUAL SHOTS:** otherwise. No rule is shown better than random; pick for breadth (R5) or at random.
  - **NEAR-VACUOUS** is added when R4 picks exactly R0's rows in more than 80% of cells.
- **EXPLORATORY (never decision-bearing):**
  - every rule − RND and − R0, pooled, at S_big and at S_top;
  - R4 − RND per book, per target and per m;
  - each contrast's in-sample SIMULATED gain beside the realized one (how much the model believes);
  - the within-book Spearman of projected mean and realized percentile (A62's +0.086, replicated or not).
- **Binding-census checks:**
  - 26 rows per book, no short book, the pinned `enter_layout` on every row;
  - R4's in-sample value ≥ every other rule's (it is the exhaustive optimum);
  - the share of cells where R4 = R0, reported.

## 5. What a verdict can do (frozen now)
- **OFFER R4:** next week, when he holds 1–3 entries in a big contest, the entries are chosen by R4 from that week's
  book. Production adds it as a selection step: a reversible class-S trial with a paired shadow (R0 vs R4) each week.
- **CO-EQUAL SHOTS:** he is told plainly that the book's rows are co-equal shots.
  - Choose for breadth (R5, different QBs and games), or let him pick.
  - No rule is installed.
- **R4 WORSE THAN RANDOM:** the same as co-equal shots, and the joint-coverage family is not proposed again at small m
  without a new mechanism.

## 6. Disclosures (before any outcome)
1. **The fields are stand-ins.** The realized endpoint uses the sampled Millionaire field. The MEGA and Wildcat fields
   are smaller and probably sharper; no ownership history exists for them.
2. **The book rows' realized percentiles are shared across rules.** Only the choice differs. RND is exact, so the
   control adds no noise.
3. **R2–R4's worlds are in-sample.** They are the same worlds the book was built on, as production would use them. The
   endpoint is realized.
4. **Projections and ownership:** our projections (no FP in history), and the stand-in for pre-lock ownership.
5. **A 2026 descriptive check (W1–W4; already seen, never decision-bearing)** may follow on the laptop's books, labelled
   as such.

## 7. Integrity
- **Code:** nfl2 `production/s32-sorting-20261006`, cut from study 31's `71b61fa`: `experiments/s32_sorting.py`,
  `scripts/s32_drive.py`, `scripts/s32_report.py` (the reader), `scripts/s32_census.py`, `tests/test_s32_sorting.py`
  (6 tests). The commit and shas are recorded at the freeze.
- **Order:**
  1. the laptop's comments on this draft;
  2. the smoke;
  3. the freeze;
  4. the binding census on 1406;
  5. the laptop's ack;
  6. the scored run on 1437–1442 (after study 31's run; one heavy job at a time);
  7. the confirmatory census, committed;
  8. the read;
  9. the laptop's re-run;
  10. the LEDGER row and an Addendum.
