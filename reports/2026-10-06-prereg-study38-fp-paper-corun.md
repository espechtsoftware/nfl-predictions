# Preregistration: study 38, the FP paper co-run (the regulars' structure beside the yes-book, under the projections we play with) (DRAFT 2026-10-06)

**Status: DRAFT 2026-10-06** by the reviewer. It FREEZES before Week 5's lock (Sunday 10-11, 12:00 CT), after the
dress-rehearsal census on a Week-5 snapshot (§7); the laptop acks the census and re-runs every score. No week is built
before the freeze. Nothing here enters a contest: the money path, its checkout and its files are never touched.

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
- **MIXT_QA** (reference): the yes-book (the winners' mix, the 0.20 ownership term, the per-QB cap of 5 rows,
  production's player / DST caps 13 / 6), rebuilt in the lab harness like-for-like with MIXT_RS.
- **MIXT_RS** (DECISION): study 37's regulars' structure, its frozen tiers unchanged (QB: a 6-row cap, at most 1 / 1 /
  2 / 4 / 7 QBs reach 6 / 5 / 4 / 3 / 2 rows; non-QB: at most 1 / 1 / 2 / 3 / 4 / 5 / 7 / 10 / 13 / 18 / 25 / 36 players
  reach 13 … 2 rows; the loud fallback).
- **MIXT_QBB / MIXT_NQC** (exploratory): each tier set alone.
- **His ENTERED book**: a context column, scored the same way, never an arm. The lab's MIXT_QA and the production union
  will differ (the union's own solver path, pins and spares); that difference is itself reported.

## 3. Inputs and provenance (the laptop's pre-lock snapshot; the build runs after lock)
- **The snapshot** (the laptop, Sunday right after the T-70 union and before 12:00 CT): copies of the union run's
  `frame.parquet`, FP's projections `proj_fp-<TAG>.csv` and its `.json` sidecar, FP's ownership `ownership_fp-<TAG>.csv`,
  the `dk-status` file the union read, the union's arguments, the installed `contests.json`, the week's contest
  details, `plan-overrides.json` (his per-contest decisions that week; `{}` if none), and `MANIFEST.txt` (each file's
  sha256, bytes, source path and mtime, the receipt's built_utc, the snapshot time).
- **The MANIFEST is the build's only input list.** Every file the build reads must have its sha256 in it, or the build
  REFUSES. The copies of FP's projections, FP's ownership and the DK status must be byte-identical to the files the
  union's arguments name, where those originals are still on disk.
- **The build** uses production's own functions, imported from a pinned production checkout: `apply_proj_source`
  (FP's projections replace `mean_projection`; it refuses a file made for another frame), `unavailable_ids` plus the
  skill `--min-proj` filter (the exclusions), and `own_bonus` at the union's tilt (the 0.20 term). Then study 28's
  `mix_book` with study 37's builders, at the plan's K 26 head layout.
- **The union's arguments must match the lab builder** (mix, K 26, overlap 7, per-game 4, salary floor 49,000, min-proj
  1.0, caps 0.5 / 0.25, the QB cap of 5 rows, tilt 0.20, head layout), or the build refuses.
- **Disclosed: the objective differs from studies 28–37.** It is FP's `mean_projection` + the term, as the money path
  ranks, not the simulated `player_mean` of the harness.
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
- **PRIMARY:** per week, d = P(≥ 1 big seat) of MIXT_RS − MIXT_QA.
- **Guards** (pooled over the four weeks): guard 1, the mean of the weekly mean-entry-pct differences > −0.015;
  guard 2, expected big seats summed, MIXT_RS / MIXT_QA ≥ 0.80 (his tolerance; it holds when both sums are 0).
- **Verdicts:** PASS (d > 0 in ALL FOUR weeks and both guards hold) / FAIL (guard) (d > 0 in all four, a guard fails) /
  WORSE (d < 0 in all four) / NO PASS (anything else) / NOT ENOUGH VALID WEEKS. The guards gate a PASS only.
- **Said plainly: four weeks are four draws.** With one slate a week, four weeks are four independent outcomes. Under a
  coin-flip null, MIXT_RS ahead in all four happens 1 time in 16, so a PASS is a strong but not certain signal, and a
  real but modest gain will usually read NO PASS. His goal itself (one big win a week) cannot be measured in four
  weeks; the smooth P(≥ 1 big) on the real field is the closest measurable stand-in. Every weekly number is
  descriptive.

## 6. What a verdict can do
- **PASS:** licenses building production tier code (the QB and non-QB tiers with the loud fallback in
  `union_reselect`) for the following week. It is reviewed, parity-tested against the harness and rehearsed, and
  armed only on his yes.
- **FAIL, NO PASS, WORSE or NOT ENOUGH VALID WEEKS:** the yes-book stays, and the structure remains a paper option.

## 7. Smoke, census and integrity
- **The Week-4 smoke** (the laptop's frozen copies; dry run): the build exited 0, all four books built (the parity check
  named Week 4's different union arguments, as it should). The scorer exited 0 with its 2 headers and 4 book lines; no
  outcome line was read. The reader marked the dry-run week INVALID.
- **The dress-rehearsal census:** the live-mode build on a Week-5 snapshot from the laptop's A3 rehearsal (construction
  only). Results are recorded here before the freeze.
- **Code:** nfl2 `production/s38-paper-corun-20261006`; the shas are recorded at the freeze.
- **The production pin:** `union_reselect.py`, `r1c_sunday_reselect.py` and `moneygate_score.py` are checked at the
  freeze against the head armed for Week 5. If the armed head changes them, the pin follows the armed head and the change
  is disclosed.
- **Order:**
  1. this freeze;
  2. the laptop's ack;
  3. each Sunday, the snapshot before lock;
  4. the build after lock;
  5. Monday, `fetch_week` (the laptop), then the score (the reviewer);
  6. the laptop's byte-identical re-run;
  7. the weekly record;
  8. after the fourth valid week, the frozen read, the LEDGER row and an Addendum.
