# Preregistration: study 31, shape × ownership term in one co-run, on the plan he will enter (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06**, after the one-slate smokes (§2a), before the binding census and any scored bank. The
reviewer froze it and reads first. The laptop acks the census (it may object to the design there) and re-runs the
frozen reader.

## 1. Why
- **Studies 28, 29 and 30 do not compose.**
  - Study 28: MIX − C (no term) +0.061 on P(≥ 1 big seat).
  - Study 29: the term on MIX, MIXT − MIX −0.068.
  - Taken together they imply the package (MIX, no term) beats the status quo (house + term) by about 13 points.
  - Study 30 measured that comparison directly and read −0.071 [−0.188, +0.053], both seasons negative.
- **The guard-1 direction IS consistent across the three.**
  - Study 28: MIX finishes +0.013 better on average.
  - Study 29: the term adds +0.051.
  - So the status quo should finish better on average than the package; study 30 read −0.051.
  - Only the primary conflicts.
- **Two explanations remain:**
  - The term's effect differs by shape (the post-selection law: a verdict does not transfer across a changed stage).
    The INTERACTION contrast (§4) measures it.
  - Bank noise. The same construction (MIX, no term, the same 36 slates) read .362 on banks 1427/28 and .294 on
    1429/30, about 7 points apart.
- **This study puts all four constructions in ONE co-run** (identical slates, worlds and fields per bank) and averages
  SIX banks per slate.
- **The operator's plan changed on 10-06 to Rev3:** his 26 $20-ticket super-satellite entries spread over rows 1–26,
  each on its own lineup.
  - Production now lets a pin add rows: `production/pins-extend-book-20261006` @ `da399bdb`, reviewed and approved.
  - So the book is K 26 with caps 13 / 6.
  - The study is frozen on THAT plan (the K-dependence lesson).

## 2. Arms (study 29's harness)
| Arm | Shape | Objective |
|---|---|---|
| **C** | `PRODUCTION_STACK` on every row (the house shape) | the simulated mean |
| **CT** (the STATUS QUO, Week 4 as entered) | the house shape | the mean + 0.20 × TABPFN_LS predicted ownership % (skill players; the live term's stand-in) |
| **MIX** (the PACKAGE) | study 18's MIX, built as production's `mix_rows` (pin-aware weights from Rev3's pins, as production after O-35) | the simulated mean |
| **MIXT** | MIX | the mean + the same term |

Common to all arms:
- our simulated means (FP is not in history);
- production's caps for K 26: player 13, DST 6;
- the head layout with the Rev3 pins, dealt by production's `enter_layout` pinned by content;
- the small-contest overlap limit, M 5 / ceiling 10.

## 2a. Smokes (bank 1406; 2023 W1; mechanics plus the full path; the reader checked by exit code and header count only)
- **The final code on Rev3:**
  - K 26; caps 13 / 6; the pinned `enter_layout` on the row.
  - No arm identical to its reference; no short books; 26 distinct dealt rows in every arm.
  - MIX's dealt cells: A1 .302 / A2 .151 / B .283 / C .264, with 0 passes (MIXT within 2 points of the same).
  - The Rev2 re-deal changes plan positions 11–16 only: the six re-pinned supersats. The big contests' deal is
    unchanged.
  - The census exited 0; the reader exited 0 with its 2 headers.
- **Two earlier plumbing smokes:**
  - The first used a spread plan at K 22 and the integration `enter_layout`. The census and reader exited 0, and the
    reader REFUSED mechanics-only rows (exit 1).
  - The first version of the code (before Rev3) passed both paths.
- No outcome line of any smoke was read.

## 3. Panel and plan
- **Slates:** the **36** `k1` slates of 2023–24 with Millionaire ownership. The term's predictions exist only there.
- **Banks:** fresh **1431, 1432, 1433, 1434, 1435, 1436** (scanned clean 10-06). Each slate's value is the mean over
  its six banks. The census runs on 1406.
- **Plan:** the s24-format Rev3 plan, sha256 `3dd19d6cf5757cd194a9f566b6e41ee18aab1860f8a8f3ed1ee5e1e0392df06f`.
  - It is built from the laptop's `rev3-26/contests.json` (`8625de0e…`).
  - Contests, entries, pins, tracks and order were checked identical. It is Rev2 (`94cc61a8…`) with only the pins
    changed.
  - 29 contests, 53 entries, 26 of them in 21 big contests.
- **The super-satellite secondary's alternative:** the s24-format Rev2 plan, `00c660045e2917082d4e6515da7cd4388730c13e96e6d49cd42e647ae0ce7d08`.

## 4. Endpoints and decision rule (study 18b's)
- **PRIMARY:** P(≥ 1 big seat) per slate, **MIX − CT** (the package vs the status quo).
  - Bootstrap within season, B 20,000, seed 20261013; two-sided 0.95.
- **GUARD 1:** mean dealt-entry percentile, MIX − CT. The one-sided 0.95 lower bound must exceed −0.015.
- **GUARD 2:** expected big seats, MIX / CT ≥ 0.80 (his tolerance).
- **Verdicts:**
  - DEAD LEVER: identical on > 80% of slate-banks.
  - WORSE: the upper bound < 0.
  - PASS: the lower bound > 0, at most one season mean < 0, and both guards hold.
  - FAIL (guard): the PASS conditions on the primary are met but a guard fails.
  - NO DIFFERENCE: otherwise.
- **EXPLORATORY (never decision-bearing), each with its interval:**
  - CT − C: the term on the house shape;
  - MIXT − MIX: the term on MIX;
  - MIX − C: the shape without the term;
  - MIXT − CT: the shape with the term;
  - the **INTERACTION** (MIXT − MIX) − (CT − C).
- **SECONDARY, descriptive (the operator's super-satellite question).** Per arm, the 7 $20-ticket super-satellites
  under Rev3's spread (rows 1–26) and, on the SAME book, under Rev2's pins (rows 1–5). For each:
  - P(≥ 1 contest with a ticket);
  - expected tickets;
  - P(≥ 2 contests with a ticket).
- **The other secondaries:** each arm's P(≥ 1 big), expected big seats, P(≥ 2 contests) and mean entry percentile.
- **Binding-census checks:**
  - MIX's and MIXT's dealt cells within 10 points of the quotas;
  - no short books;
  - no arm identical to its reference on > 80% of slate-banks;
  - K 26, caps 13 / 6 and the pinned `enter_layout` on every row.
  - Not a stop, but reported: whether the Rev2 re-deal changes any position other than 11–16 (the overlap limit could
    move a small big contest).

## 5. What a verdict can do (frozen now)
- **PASS:** MIX is a tested gain over the status quo on his goal. It is armed Friday on his yes.
- **NO DIFFERENCE (the package not shown worse):** MIX stays his preference option, as after study 28. The
  exploratory contrasts and the interaction are reported plainly beside it.
- **WORSE:** the package is not offered. The status quo (the house shape) stays for Week 5. The term's setting on it
  follows CT − C, reported as exploratory, plus study 29's measurement.
- **FAIL (guard):** not offered as a gain. The failing guard is stated, and the status quo stays unless he chooses
  otherwise with that stated.
- **DEAD LEVER:** no verdict.
- **The term:**
  - Study 29's verdict (NO DIFFERENCE, recommended OFF on MIX) stands. This study's MIXT − MIX and CT − C are
    exploratory.
  - If both are negative they support OFF on either shape. If they differ in sign, the interaction says so, and the
    recommendation follows the shape he arms.
- **The super-satellite secondary describes; it does not decide.** He has chosen Rev3. The secondary says what the
  spread gains or costs in $20 tickets.

## 6. Disclosures (before any outcome)
1. **The secondary holds the book fixed.** Rev2's pins are dealt on the K-26 book. Production at Rev2 would have built
   K 22 at caps 11 / 5, and MIX's interleave weights would have followed Rev2's pins. The secondary isolates the deal
   only.
2. **`enter_layout` is the branch version** (`3cb051ac…`, pinned by content; it merges Friday). Studies 24–30 imported
   whatever production checkout was on `PYTHONPATH` and did not record its version (they ran on the integration
   branch before this change). Study 31 records it on every row.
3. **The term's stand-in is optimistic.** TABPFN_LS was trained on lock-time LineStar. The live term uses FP's T-70
   projection.
4. **Projections:** both shapes use our projections; the live build adds FP.
5. **Why six banks:** two banks moved the same construction's level by about 7 points. Six banks per slate are averaged
   before the bootstrap.

## 7. Integrity
- **Code:** nfl2 `production/s31-factorial-20261006` @ `71b61fa`:
  - `experiments/s31_factorial.py`, sha256 `160defc037e1fc1bf1b70e61328b6c537d20cf1d8390833c215a2ac50aaecf8b`;
  - `scripts/s31_drive.py`, `eadf2f13836d3c335d7b960ac04b9ad637fba253e0d34cf3d46764f826392160`;
  - **`scripts/s31_report.py` (the reader), sha256 `80b61bab99f0a6166c70651835f3fc8186736aa5dd5fb0d074d92c9a06e43b79`**;
  - `scripts/s31_census.py`, `6b2823cb3ee9c7826b75df5febc1e9708208b1d92e792fefb113b1944df88b52`;
  - `tests/test_s31_factorial.py`, `2d2cb758b1604b1e6d867778826dbd0d59cdce0b97f21e2aef2f4ff36d6374ec` (6 tests).
- **Production `enter_layout.py`:** sha256 `3cb051ac6a2b40a1f3577b4af43afdc516e1c338e87884fd40405bfd8c7ebc0d`
  (`da399bdb`).
- **Order:**
  1. this freeze;
  2. the binding census on 1406;
  3. the laptop's ack;
  4. the scored run on 1431–1436;
  5. the confirmatory census, committed;
  6. the read;
  7. the laptop's re-run;
  8. the LEDGER row and Addendum 136.
