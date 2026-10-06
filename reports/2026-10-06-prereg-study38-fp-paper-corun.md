# Preregistration: study 38, the FP paper co-run (the regulars' structure beside the yes-book, under the projections we play with) (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, BEFORE any week of the decision arm (MIXT_RS0) or of the exploratory arms
QBB0 / NQC0 / QAL / RBC0 was read on any slate. Disclosed: before the freeze, the reference MIXT_QA0 was scored on
Weeks 1–4 (his rehearsal of the current process, 10-06), and MIXT_QA against MIXT_QA0 on Week 4 (the ownership-tilt
test). Those reads cannot move a prospective rule on Weeks 5–9 whose decision arm was never read. The live-mode census
on the Week-5 rehearsal snapshot is a post-freeze INTEGRITY GATE (§7), not a design step. The laptop acks and re-runs every
score. Nothing here enters a contest: the money path, its checkout and its files are never touched.

## 1. Why
- **The operator (10-06), on the proposal:** "yes, please try it, I want to exhaust all reasonable options."
- **Study 37** (Addendum 142): the regulars' structure (about 11 QB stacks and a steep player curve, their own tier
  profile at 26 lineups) did not raise P(≥ 1 big) under our projections, and breached both guards. QB breadth alone was
  neutral; the player curve carried the cost, because each spread-in player is one our model rates lower.
- **But the regulars beat the field by +6.1 points per lineup WITH their spread**, while ours runs −3.8 (the weekly
  picks-vs-field line). Their alternatives are better than our model says (study 34: their edge is pre-lock knowledge).
  Study 37's harness prices every alternative with our projections and could not credit that.
- **Since Week 5 the live book uses Fantasy Points' projections**, the closest thing we have to that knowledge. The
  fair test of the spread is therefore under FP's projections, on the 2026 slates we actually play (his ruling: test on
  2026 full-data weeks).

## 2. Arms (built each week; never entered)
- **His decision (10-06), which sets the reference:** "yes, remove the tilt as you suggested and proceed as planned". From
  Week 5 the live book runs NO ownership term. The evidence: beyond a market-quality projection, ownership carried no
  information in Weeks 1–4 (props-implied base −0.03 points per ownership point [−0.24, +0.17]; served +0.01; our old
  model +0.44, which is why the term helped before); beyond FP in Week 4 it was negative; production's own Week-4
  replay under FP gave P(≥ 1 big) 0.0094 with the 0.20 term and 0.0336 without. A verdict does not transfer across a
  changed objective, so the decision pair is on FP's mean alone, like his live book.
- **MIXT_QA0** (reference): his live yes-book (the winners' mix, the per-QB cap of 5 rows, production's player / DST
  caps 13 / 6, FP's mean, no ownership term), rebuilt in the lab harness like-for-like.
- **MIXT_RS0** (DECISION): study 37's regulars' structure on the same objective, its frozen tiers unchanged (QB: a 6-row
  cap, at most 1 / 1 / 2 / 4 / 7 QBs reach 6 / 5 / 4 / 3 / 2 rows; non-QB: at most 1 / 1 / 2 / 3 / 4 / 5 / 7 / 10 / 13 /
  18 / 25 / 36 players reach 13 … 2 rows; the loud fallback).
- **Exploratory, never decision-bearing:**
  - MIXT_QBB0 / MIXT_NQC0: each tier set alone.
  - MIXT_QA: the yes-book WITH the dropped +0.20 term (tracks his decision on the real field).
  - MIXT_QAL: the yes-book leaning AGAINST ownership, −0.10 per ownership point (his question 10-06: can ownership find
    players who project well but will be under-owned, for an edge?).
  - MIXT_RBC0: an RB-led floating core plus QB-stack breadth (the laptop's Neo4j finding 10-06: the regulars' heavy core
    is about 5 players, RB-led, carried across many QB stacks; their pass-catchers spread through the stacks). Study 37's
    QB tiers plus a WR / TE-only curve at the regulars' WR / TE medians at 26 rows, rounded half up (no WR / TE reaches 12
    rows; at most 1 / 1 / 2 / 3 / 4 / 6 / 8 / 12 / 17 / 25 reach 11 … 2 rows); RBs at production's 13-row cap; FP's mean.
  - The ownership weights are multiples of the frozen 0.20 (0, +1, −0.5); production's `own_bonus` does the matching and
    the refusals. Without an FP ownership file, only MIXT_QA and MIXT_QAL go missing (recorded), never the week.
- **His ENTERED book**: a context column, scored the same way, never an arm. The lab's MIXT_QA0 and the production union
  will differ (the union's own solver path, pins and spares); that difference is itself reported.

## 3. Inputs and provenance (the laptop's pre-lock snapshot; the build runs after lock)
- **The snapshot** (the laptop, Sunday right after the T-70 union and before 12:00 CT): copies of the union run's
  `frame.parquet`, the union's arguments, and the model inputs AS THE UNION'S OWN ARGUMENTS NAME THEM: FP's
  projections (`--proj-source`, with its `.json` sidecar; a union without one fell back from FP, and that week is not
  an FP week), the ownership file (`--main-own-source`, whatever its name), and a DK status file only when the union read
  one (`--dk-status`; production passes none while O-16 stands, so the union calls `unavailable_ids(fr, None)` and so
  does the build). Also the installed `contests.json`, the week's contest details, `plan-overrides.json` (his
  per-contest decisions that week; `{}` if none), and `MANIFEST.txt` (each file's sha256, bytes, name, source path and
  mtime; the header carries the union's built_utc and lock_utc and the snapshot time), and the union's receipt
  (`union-receipt.json`). The laptop's tool (`scripts/s38_snapshot.sh`) is create-once, never writes under a week's
  money-path directory, makes every copy fatal on failure, and marks a partial copy `SNAPSHOT-FAILED.txt` (the build
  refuses such a folder).
- **The MANIFEST is the build's only input list.** Every file the build reads must have its sha256 in it, or the build
  REFUSES. The copies of FP's projections, FP's ownership and the DK status must be byte-identical to the files the
  union's arguments name, where those originals are still on disk. **Pre-lock is proved by content:** the build refuses
  unless the MANIFEST's snapshot time is before the union receipt's `lock_utc` (and the tool refuses to snapshot at or
  after it).
- **The build** uses production's own functions, imported from a pinned production checkout: `apply_proj_source`
  (FP's projections replace `mean_projection`; it refuses a file made for another frame), `unavailable_ids` plus the
  skill `--min-proj` filter (the exclusions), and `own_bonus` at the frozen 0.20, scaled per arm. Then study 28's
  `mix_book` with study 37's builders, at the plan's K 26 head layout.
- **The union's arguments must match the lab builder's mechanics** (mix, K 26, overlap 7, per-game 4, salary floor
  49,000, min-proj 1.0, caps 0.5 / 0.25, the QB cap of 5 rows, head layout), or the build refuses. **The ownership tilt is
  each paper arm's own**, not part of that parity. With the live tilt at 0, Sunday's build captures no FP ownership
  (the capture and export run only with a non-zero tilt), so the laptop's snapshot tool runs that same capture and
  export itself: after the T-70 union, under the same FP profile lock, with the export's `--now` set to the snapshot
  time (before lock). If the vendor collect fails, the export falls back exactly as production's does (the newest
  capture within its 30-hour limit; the age is recorded in the MANIFEST). If the export refuses (stale or low coverage),
  there is no ownership file, and only MIXT_QA and MIXT_QAL go missing that week.
- **Disclosed: the objective differs from studies 28–37.** It is FP's `mean_projection` (plus the arm's ownership
  weight), as the money path ranks, not the simulated `player_mean` of the harness.
- **The plan** in the harness's form is derived inside the build from the snapshot's `contests.json`, details and
  overrides by the tracked converter (`scripts/s38_plan.py`): single-prize contests count every paid seat as big except
  a $20 ticket; multi-tier contests count the places paying $500 or more; his decisions ride in the overrides (Week 5:
  the $125 WFFC qualifier is not a big win). From the installed Rev3 (`8625de0e`) it reproduces the Week-5 harness plan
  `3dd19d6c` byte for byte.
- **No outcome is read by the build:** the frame's `actual` column is dropped on read.

## 4. Scoring (Monday, after settlement)
- Each dealt entry's real DraftKings points (the week's points table, canonical names, hundredths; a missing name
  scores 0 and is counted), and its share of the REAL Millionaire field it beats: every real entry of ours removed,
  ties counted as losses, as the harness's `contest_p`.
- Then the harness's own `big_seat_stats` per plan contest: **P(≥ 1 big seat), expected big seats, P(≥ 2)**, and the
  mean entry pct. That is studies 31–37's endpoint, with the real field in place of a sampled one.
- **Descriptive only:** realized results per contest (`moneygate_score.place` against that contest's real entrants,
  DraftKings' tie split: payouts, cashes, big seats realized), his entered book, the picks-vs-field and monkey lines.

## 5. The rule (the reader `scripts/s38_report.py`, frozen with this document)
- **The weeks:** the first FOUR VALID weeks from Week 5; Week 9 may replace an invalid one, and no later week.
- **A valid week:** its books were built LIVE (the manifest checked, union-args parity, the copies identical to the
  union's files), and every dealt entry was scored with under 1% of player names missing. A week that fails any of
  these is reported as invalid with its reason, never counted.
- **PRIMARY:** per week, d = P(≥ 1 big seat) of MIXT_RS0 − MIXT_QA0.
- **Guards** (pooled over the four weeks): guard 1, the mean of the weekly mean-entry-pct differences > −0.015;
  guard 2, expected big seats summed, MIXT_RS0 / MIXT_QA0 ≥ 0.80 (his tolerance; it holds when both sums are 0).
- **Verdicts:** PASS (d > 0 in ALL FOUR weeks and both guards hold) / FAIL (guard) (d > 0 in all four, a guard fails) /
  WORSE (d < 0 in all four) / NO PASS (anything else) / NOT ENOUGH VALID WEEKS. The guards gate a PASS only.
- **Said plainly: four weeks are four draws.** With one slate a week, four weeks are four independent outcomes. Under a
  coin-flip null, MIXT_RS0 ahead in all four happens 1 time in 16, so a PASS is a strong but not certain signal, and a
  real but modest gain will usually read NO PASS. His goal itself (one big win a week) cannot be measured in four
  weeks; the smooth P(≥ 1 big) on the real field is the closest measurable stand-in. Every weekly number is
  descriptive.

## 6. What a verdict can do
- **PASS:** licenses building production tier code (the QB and non-QB tiers with the loud fallback in
  `union_reselect`) for the following week. It is reviewed, parity-tested against the harness and rehearsed, and
  armed only on his yes.
- **FAIL, NO PASS, WORSE or NOT ENOUGH VALID WEEKS:** the yes-book stays, and the structure remains a paper option.

## 7. Smoke, census and integrity
- **Parity with the money path, confirmed:** the laptop ran production's own fixed-book replay of Week 4 (union_reselect,
  FP source, the QB cap, Rev3 head; the ownership term at 0.20 against none) and reproduced this harness's numbers to
  four decimals: P(≥ 1 big) 0.0094 against 0.0336; expected big seats 0.0094 against 0.0339; mean entry pct .4960
  against .5014. So the paper books are the books production would build. (This one week is a confirmation of the
  machinery and of the 10-06 tilt evidence, not a sample of this study.)
- **The Week-4 smoke** (the laptop's frozen copies; dry run): the build exited 0, all four books built (the parity check
  named Week 4's different union arguments, as it should). The scorer exited 0 with its 2 headers and 4 book lines; no
  outcome line was read. The reader marked the dry-run week INVALID.
- **INTEGRITY GATE (post-freeze):** before Week 5's lock, the LIVE-mode build must pass on the laptop's Week-5 rehearsal
  snapshot (`~/private/paper-corun/rehearsal-w05/`, from A3): the manifest, provenance, union-args parity and pre-lock
  checks, all arms built. If it fails, Week 5 is INVALID (the reader then takes Week 9). The same live-mode checks gate
  every week.
- **Code (frozen):** nfl2 `production/s38-paper-corun-20261006` @ `4429fd8`:
  - `experiments/s38_paper_corun.py`, sha256 `e2d593a5d4c9f161763b74c2a4b2247830717196b23372215739083855fcbcdf`;
  - `scripts/s38_build.py`, `fe51ac2e6f528b7ee9d6de27406779e3cbd4dfc4adc6eb85e6b9539587f74174`;
  - `scripts/s38_score.py`, `ca4e74d3468c0cd2f2459e80a59b97f810e0f6a04b94f41b96f5665111d331c3`;
  - **`scripts/s38_report.py` (the reader), sha256 `7865303af4b48b1c1365feb4a9098af817d9b176f5d2559bc02c92a34399da44`**;
  - `scripts/s38_plan.py`, `9af5f8053a0369cc2f787aef332ed3d5f96b506a352a518c763b8773ceb5d924`;
  - `tests/test_s38_paper_corun.py`, `d43597cc6ac0baa5b0bcbce5c509e36f44f701b435b734c6105fafd2bbdb8029` (10 tests);
  - study 37's frozen `experiments/s37_regulars_structure.py`, `29a2c2c72b86f1b5eec6072119482cafa462218272c6c90f2e9aa2c95778acbf`.
- **The production pin** (imported, never copied), identical at integration `5a1ac062` and at the pin `1478dcfb`:
  `scripts/union_reselect.py` `ffd59b721ba6236e…`, `scripts/r1c_sunday_reselect.py` `3c3b9480fc0f5516…`,
  `scripts/moneygate_score.py` `48342ae163e20738…`, `src/nfl_dfs/inference/enter_layout.py` `3cb051ac6a2b40a1…`. If
  the head armed for a week changes these files, the pin follows the armed head and the change is disclosed in that week's
  record.
- **An early look on Weeks 1–4 (after this freeze; never decision-bearing):** every arm replayed on the four completed
  weeks (W4 on FP, W1–3 on our projections), on each week's real Millionaire field. The tiers of RS0 and RBC0 were DERIVED
  from Weeks 1–4, so it is in-sample: it can warn, not confirm.
- **Order:**
  1. this freeze;
  2. the laptop's ack;
  3. each Sunday, the snapshot before lock;
  4. the build after lock;
  5. Monday, `fetch_week` (the laptop), then the score (the reviewer);
  6. the laptop's byte-identical re-run;
  7. the weekly record;
  8. after the fourth valid week, the frozen read, the LEDGER row and an Addendum.
