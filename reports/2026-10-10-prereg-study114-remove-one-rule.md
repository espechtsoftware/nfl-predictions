# Preregistration: study 114, each live rule removed one at a time from his full armed Week-5 book, in the harness (DRAFT 2026-10-10; FROZEN 2026-10-10)

**Status: FROZEN 2026-10-10 (10:27 CDT)** by the lab reviewer, after the outside reviewer's DRAFT and code, the smoke and the
binding census, before any scored bank. The text changed at the freeze in this status block and §6 (the binding census) only.
The laptop acks. **A suggested removal goes to study 114b** (its preregistration committed before this READ).
- **Banks 3860–3871** (set A 3860–3865, set B 3866–3871; sims bases 3910–3921, fields 4560–4571), the reader's bootstrap seed
  **20261157**. The laptop's full-set check (677 used or reserved banks, every {b, b+50, b+700}) was CLEAN; the text scans of both repositories
  (banks, sims bases, fields, seed) were CLEAN, 10-10.
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run, recorded in `RUN_ENV_s114.txt` committed with the
  confirmatory census. The run starts from lab `eb981cbb` on production/s114-remove-one-20261010 (results/s114/).

## 1. Why
- **The operator, 10-10 morning, in the laptop's session (verbatim; study list row 91):** "Did we try what you had planned of
  removing one rule at a time to see if it was really helpful?  That in my opinion should be the last thing we do after we’ve
  tried the other experiments". It runs last today, after studies 106–113 and 109b.
- **The shapes were removed already** (study 95: no removal helped; study 98 kept 30 / 14 / 28 / 28). **The rules never were.**
  Each was tested only on top of the rules before it. Their reads, from the lab LEDGER:
  - **the package** (the 0.35 cap with the ownership cap + 15; study 89): +1.2 points against the book before it (A +0.5, B
    +1.9; guard 1 fails; seats 0.951), "no gain shown". He armed it by his decision.
  - **te1 / low1** (study 91): +4.1 on top of the package (A +3.2, B +5.0; seats 1.080). Low1 alone +2.8 passed; TE1 alone +0.9
    (A −0.9).
  - **the cheap +2 block** (study 53): CHEAP2_BLOCK8 +0.4 (seats 0.936), contradicted on 2022, "NOT ENTERED". He made it a
    reversible Week-5 trial (10-07). Study 100 removed it from the pre-FAVHI book: +1.2 pooled (A −1.0, B +3.5; seats 1.053).
  - **ONECATCH** (study 93): +2.0 (A +3.6, B +0.5; seats 1.107).
  - **FAVHI** (studies 97 / 99): +0.9, then +3.4 on a fresh draw; adopted 10-10.
- **The prior: NO DIFFERENCE for most removals.** The package and the cheap block never passed his rule in the harness, so
  their removals are the most open questions.

## 2. Arms (`experiments/s114_remove_one.py`)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with nine
listed edits, a test asserts it). s96 / s97 are brought in byte for byte (`0363a84f…` / `7df6f324…`).
- **LIVE** — his full armed Week-5 book:
  - the package (the 0.35 player cap with production's DST cap; the ownership cap + 15 on the harness's predicted ownership);
  - te1 / low1 (at most one TE and at most one player predicted under 3% per book row);
  - the cheap +2 block on 8 rows;
  - ONECATCH and the adopted FAVHI (study 96's `combo_rules` with study 97's FAVHI pairs, computed once on the shared pool).
  - Checked equal to study 97's RBMATE4_FAVHI, rows and dealing, on bank 1406 (`--ref97`).
- **Each other arm removes ONE rule, decoupled.** Production's arm script couples some of these rules (§5); the harness asks
  his question, one rule at a time.
  - **NO_PACKAGE** — the 0.35 cap AND the ownership cap + 15 removed together. They were adopted together, and the flat 35%
    never runs alone. Production's caps instead (0.5 × 26 = 13 players, its DST cap 6; study 89's LIVE_CB), and no
    ownership-cap bans.
  - **NO_TE1** — the row rules are low1 only.
  - **NO_LOW1** — the row rules are te1 only.
  - **NO_CHEAP** — no cheap +2 block: study 42's live fill over all 26 rows (`mix_fill.mix_book_fill`, "rr"), exactly study
    100's NOCHEAP (a test compares the call).
  - **NO_ONECATCH** — FAVHI kept, ONECATCH off. Study 96's `combo_rules` is entered with its ONECATCH cells (B / C) empty, so no
    solve takes the per-team WR / TE ≤ 1 constraint. The C cell's RB-mate floor and the row rules stay: [row rules + floor] →
    [row rules] → none. The cells are restored on exit (a test).
  - **NO_FAVHI** — no RB mate: study 93's `lead_rules(0, True, 0, …)` with ONECATCH on. This is exactly study 97's LIVE, checked
    on bank 1406 (`--ref97`).
- Everything else is LIVE's in every arm: the shape mix, the QB cap 5, the overlap 4, the pool.

## 3. The read (the reader `scripts/s114_report.py`)
- **Study 100's reader with study 106's edits, relabelled** (a test asserts them); study 63's statistics; two draws (the same
  past slates, two random opponent sets) and pooled; two-sided 0.95, B 20,000.
- **Per arm − LIVE:**
  - P(≥ 1 big seat), its guards and verdict;
  - **his rule's line** (better on both draws AND the pooled expected big seats ratio ≥ 0.80);
  - the mean best real lineup points and P(best ≥ 200), printed (information).
- **THE DECISION RULE (fixed now; the lab reviewer accepted it):**
  - **"Removal suggested"** iff NO_x − LIVE passes his rule (guard 1 printed, not gating). If two or more pass, only the
    largest pooled gain is suggested today; a second removal would need its own test with the first applied.
  - **"Still helping"** iff NO_x − LIVE is worse on both draws.
  - **Otherwise "keep"** (no clear evidence either way; the live book is the default).
- **Multiplicity:** six removals on the same 36 slates as studies 89–113. Under no true effect, each passes his rule about one
  time in four to one in three (the reader's own line), so **one or two false passes are expected**. That is why a suggested
  removal goes to study 114b before it is put to him.

## 4. Honest limits and the census
- **The harness builds on its own simulated means and predicted ownership;** his book uses Fantasy Points' projections and
  ownership. A rule's value can differ between the two.
- **The census, per arm (outcome-blind, bank 1406):**
  - **the removal is real** (the REMOVED? line, beside LIVE's): rows with 2+ TEs (NO_TE1), rows with 2+ low-owned (NO_LOW1),
    term rows (NO_CHEAP: 0), the most-used player against its cap and the players over the ownership cap (NO_PACKAGE), B / C
    rows with two catchers of one team (NO_ONECATCH), rows with a FAVHI pair and the RB-mate slots (NO_FAVHI: 0). A removal that
    does not rise above LIVE is flagged before the freeze;
  - the row-rule and ownership-cap fallbacks; ONECATCH's dropped solves; the RB mate's slots (4 per book; NO_FAVHI 0);
  - rows shared with LIVE and dealt identity (> 0.80 = a dead lever);
  - LIVE == study 97's RBMATE4_FAVHI and NO_FAVHI == study 97's LIVE (`--ref97`). **Both must hold on every slate-bank:** study
    97's LIVE is 93's `lead_rules` with ONECATCH, the package (the 0.35 cap and the ownership cap + 15), te1 / low1 and the cheap
    block, under the same pool, simulations and caps, so FAVHI is the only difference (checked in the code, 10-10). 97 builds on
    the default shape quotas and this study on `quotas(LIVE_Q)`; they are the same mix (studies 109, 110 and 115's LIVE equal
    97's RBMATE4_FAVHI on 36 of 36). A difference would be a defect, not an expected change.
  - Per-slate fields stay outside the blocks the reader compares.

## 5. Production (if a removal holds on the fresh draw)
- **Armable as they stand:**
  - NO_CHEAP: `TERM_ROWS=0` (the arm script takes 0 "by a recorded decision");
  - NO_FAVHI: `RB_MATE_C=0`, `RB_MATE_SCOPE=all`.
- **Not armable as they stand** (`scripts/arm_week5_saturday.sh`, checked):
  - l.108: `ROW_RULES=te1_low1` requires the package (`OWN_CAP_DELTA=15`);
  - l.109–111: ONECATCH requires te1_low1 and the package (with `SHAPE=mixt`, `MIX_FILL=rr`, …);
  - l.112: `RB_MATE_C=4` requires ONECATCH.
  - So removing the package (NO_PACKAGE) forces the row rules, ONECATCH and FAVHI off with it. NO_TE1 / NO_LOW1 need a
    `ROW_RULES` value with one rule and ONECATCH accepting it. NO_ONECATCH needs FAVHI decoupled from it.
  - Each needs the decoupled wiring, tests, the Week-4 check and study 38's classification first: **Week 6** unless trivial.

## 6. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke and the census (the unit tests, the mechanics smoke 2023 W3
  / 2023 W11 / 2024 W10, the census with `--ref97`, the full path: reader exit and line count only). It runs in a gap the lab
  reviewer names, after studies 110 and 112 are frozen.
- **The smoke (DONE 10-10, 10:18:43–10:21:36 CDT, in the gap the lab reviewer named after the laptop's study-112 reproduction;
  bank 1406; 2024 W10, 2023 W11, 2023 W3; PYTHONHASHSEED=0; code `cf798c56`; `results_bank1406.jsonl` `f6e6ef81…`):**
  - the unit tests: 12 passed, **1 failed — a test defect, fixed before the freeze:** the test asserted the text
    `lead_rules(0, True` never appears in `run()`, but it appears in the recorded NO_FAVHI description; it now asserts no
    direct `rr = lead_rules(` call. Test-only; at `1aef50c4`, 13 passed;
  - every arm 41 rows within its caps; row rules 78 of 78 ruled, none infeasible; ownership cap 78 of 78; RB-mate slots 12 of
    12 (NO_FAVHI 0); ONECATCH 42 of 42, none dropped (NO_ONECATCH off); **LIVE identical to study 97's RBMATE4_FAVHI and
    NO_FAVHI identical to study 97's LIVE, rows and dealing, on 3 of 3**;
  - **every removal is real** (the REMOVED? line, LIVE → the arm): NO_TE1 rows with 2+ TEs 0 → 17.7; NO_LOW1 rows with 2+
    low-owned 0 → 8.0; NO_CHEAP term rows 8 → 0; NO_PACKAGE most-used player 9 → 13 and players over the ownership cap 0 →
    12.3; NO_ONECATCH B / C rows with two catchers of one team 0 → 5.0; NO_FAVHI rows with a FAVHI pair 4 → 0. Dealt identical
    to LIVE 0.000 for every arm but NO_ONECATCH (0.333); none above 0.80;
  - the full path: the reader exited 0 (93 lines; 124 two-draw, with one decision-rule block). Only the census, the exit
    codes and the line counts were read.
- **The binding census (DONE 10-10, 10:22:42–10:26:50 CDT; the lab reviewer's; outcome-blind; bank 1406, 36 slate-banks of
  2023–24; PYTHONHASHSEED=0; code `1aef50c4`; lab `eb981cbb`: `CENSUS_s114_binding.txt` `a1615a74…`,
  `census_mechanics_bank1406.jsonl` `a68bc84c…`):**
  - the unit tests 13 passed; every arm 26 book rows within its caps; **0 row-rule and 0 ownership-cap fallbacks** in all 7
    arms (936 of 936 ruled); ONECATCH 504 of 504 (NO_ONECATCH off by design); RB-mate slots 144 of 144 (NO_FAVHI 0);
  - **LIVE identical to study 97's RBMATE4_FAVHI and NO_FAVHI identical to study 97's LIVE, rows and dealing, each on 36 of 36**;
  - **every removal is real** (the REMOVED? line, LIVE → the arm): NO_TE1 rows with 2+ TEs 0 → 14.89; NO_LOW1 rows with 2+
    low-owned 0 → 7.39; NO_CHEAP term rows 8 → 0; NO_PACKAGE the most-used player 9 → 13 rows with 11.7 players over the
    ownership cap; NO_ONECATCH B / C rows with two catchers of one team 0 → 2.69; NO_FAVHI rows with a FAVHI pair 4.25 → 1.19
    and RB-mate slots 0;
  - rows shared with LIVE 4.42 (NO_TE1) to 15.50 (NO_CHEAP) of 26; dealt identical ≤ 0.194 (NO_ONECATCH); projection per row vs
    LIVE +2.52 (NO_PACKAGE), the others within ±0.45.
- **Code:** nfl2 `production/s114-remove-one-20261010` @ `1aef50c4` (the test fix; `cf798c56` before it) (off study 102's frozen `969f4d3d`; s96 / s97 byte for byte):
  - `experiments/s114_remove_one.py` `a7496843…` (pins s95 `46b80611…`, s97 `7df6f324…`)
  - `scripts/s114_drive.py` `49da9b8e…`
  - `scripts/s114_census.py` `c6577180…`
  - **`scripts/s114_report.py` (the reader) `04262d65…`** (seed 20261157)
  - `tests/test_s114_remove_one.py` `a91737a4…` (13; `0e36cffd…` before the fix)
