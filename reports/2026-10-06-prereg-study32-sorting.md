# Preregistration: study 32, choosing the best few lineups for a big contest (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06**, after the laptop's comments (all four taken) and the one-slate smoke (§2a), before the
binding census and any scored bank. The reviewer froze it and reads first. The laptop acks the census and re-runs the
frozen reader.

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

## 2a. Smoke (bank 1406, 2023 W1; mechanics plus the full path; the reader checked by exit code and header count only)
- K 26, caps 13 / 6, the pinned `enter_layout` on the row; 26 rows per book; 5 distinct QBs in each book.
- R4's in-sample value is at least every other rule's in every cell (it is the exhaustive optimum), and R4 = R2 at m 1.
- The census and reader exited 0; the reader printed its 2 headers and REFUSED mechanics-only rows (exit 1).
- The census first pooled the two targets in its "same rows" shares; it now reports each target separately (fixed
  before the freeze).
- No outcome line was read.

## 2b. Deviation note 1 (2026-10-06, at the binding census, before any scored bank)
- **What happened:** the first binding census ran 35 of 36 slates. On 2023 W11 the pre-lock selection field could not
  be sampled: 18,801 of 20,000 lineups.
  - The predicted ownership leans on expensive players. An ownership-weighted lineup averages about $51.9k, over the
    cap, so most draws are rejected.
  - The sampler's reweighting rounds always need 20,000 accepted lineups.
  - Filling unpredicted players from LAG, or widening the salary floor to $46–47k, also failed.
- **The change:** only when that sampling fails, the selection field is 10,000 lineups drawn straight from the same
  targets (`ipf_rounds` 1, no reweighting). On W11 it fills in 0.1 s.
  - Every row records `sel_field` (n, rounds, fallback, why), and the census counts the fallbacks.
  - Nothing else changed; the reader is byte-identical (`c7abb741`).
- **Why it cannot shape the result:** it was made on the mechanics bank (1406) from a sampler error alone, with no
  outcome in view. The census was re-run in full on the new code; the first attempt is kept aside, not used.
- **The re-run binding census** (36/36, code `343f446`): the fallback fired on **1 of 36** slate-banks (2023 W11).
  - The laptop's threshold: more than 10% would have meant one field rule throughout. So failure-only stays.
- **Pre-stated sensitivity (descriptive, after the read; the laptop):** R4 − RND recomputed excluding the slate-banks
  whose `sel_field.fallback` is true, from the per-row records, with no reader change.
- **Pre-stated (descriptive, after the read; the laptop's observation at the census ack):** R4 − R5 at S_big, pooled,
  with the same within-season bootstrap and seed, from the scored rows. In-sample, R4 gains largely by choosing
  different QBs deeper in the book, which R5 also does; this line shows whether the simulator adds anything beyond
  breadth.
- **The operator's "big" (10-06):**
  - This week's qualifiers: first place = the seat, as studies 24–31 used.
  - Inside next week's big contests: "a win of $500 or more". That is S_big as frozen.
  - So no §6.7 swap: S_big stays the primary and S_top stays exploratory.

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
  - **OFFER R4:** the lower bound > 0, at most one season mean < 0, AND the pooled point estimate R4 − R0 ≥ 0
    (the laptop's amendment: his default is R0, so a step that beats random but loses to the default is not
    installed).
  - **KEEP BOOK ORDER (R0):** R4 beats random by the rule above, but R4 − R0 < 0.
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
- **KEEP BOOK ORDER (R0):** no step is installed; he keeps entering rows 1..m, and the finding is reported.
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
5. **Live R0 is the VETTED order; the panel's R0 is the build order.** `vet_book` demotes flagged rows (under MIX, only
   within each cell since `030db347`), and the panel has no injury history.
6. **A 2026 descriptive check (W1–W4; ALREADY SEEN, never decision-bearing)** follows on the laptop's entered books.
   - It runs after the freeze, importing the FROZEN rule functions so it cannot shape the design.
   - Rules: R0 / R1 (ours W1–3, FP W4) / R5 / RND exact, and R2–R4 from each week's T-70 worlds where the banks exist.
7. **The primary line can still change, once and outcome-blind.** If the operator says what "big" means inside a
   target BEFORE the scored run, a deviation note may swap the primary line. After that, S_top stays exploratory and is
   reported prominently.

## 7. Integrity
- **Code:** nfl2 `production/s32-sorting-20261006` @ `343f446` (cut from study 31's `71b61fa`; deviation note 1 on
  top of the frozen `638f871`):
  - `experiments/s32_sorting.py`, sha256 `06c35b9ae2a5e3472f7c882709a5f0070a382d325162df06d0ba7d31e70730dd`
    (frozen `6350c12c…` + the fallback);
  - `scripts/s32_drive.py`, `b54f3722ef42ffcc321677aaa4a3348cf56afbb539db164a0c4a81dcdd2b65a3`;
  - **`scripts/s32_report.py` (the reader), sha256 `c7abb741e0a620a8dd2abd57e5114636e6150ab1c858f24410d042ae5eef0f27`**;
  - `scripts/s32_census.py`, `ca38841919577254151d12e98e26eb260c506986dffd3f31956c1cb0280ba00b` (counts the
    fallbacks);
  - `tests/test_s32_sorting.py`, `c4f2d322a6513a9d5380bb3325e97be21a3e07ca0230e266a1da00e6be16d820` (7 tests).
- **Production `enter_layout.py`:** `3cb051ac…` (`da399bdb`), as study 31. Runs use
  `PYTHONPATH=<nfl2 worktree>/src:<da399bdb worktree>/src`.
- **Order:**
  1. the laptop's comments on the draft (taken);
  2. the smoke;
  3. this freeze;
  4. the binding census on 1406;
  5. the laptop's ack;
  6. the scored run on 1437–1442 (after study 31's run; one heavy job at a time);
  7. the confirmatory census, committed;
  8. the read;
  9. the laptop's re-run;
  10. the LEDGER row and an Addendum.
