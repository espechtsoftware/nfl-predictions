# Preregistration: study 104, the RB version that held (FAVHI) together with study 102's pick, in one book — conditional (DRAFT 2026-10-10, committed BEFORE study 102 is read)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer, on the laptop's proposal, agreed by
the lab reviewer; committed and pushed **before study 102's READ**. The code is written only if study 103 holds; the lab
reviewer reviews it, runs the census and freezes; the laptop acks. **Information for his morning decision.**

## 1. Why
- **Study 99** (READ `9a796eb1`) confirmed RBMATE4_FAVHI on a fresh draw: the QB's own RB in 4 QB + 1 (C) lineups, only for
  the expected winner of a high-scoring game, on top of ONECATCH. Across studies 97 and 99 it was ahead of his book on all four
  opponent sets (+0.9, +3.4).
- **Study 102** may pick one ceiling construction, which **study 103** re-checks on a fresh draw. The two were read
  separately, and separately-read rules have not added up before (studies 93 + 94 → 96; study 83's combination −1.9). The
  production wiring therefore refuses to arm them together.
- **Study 104 reads them together**, so that he can choose both if both hold.
- **When it runs:** ONLY if study 102 picks an arm AND study 103 holds it; otherwise it is not run (recorded).

## 2. Arms (the code is written after study 103 holds; the design is fixed now)
Study 102's harness exactly (study 95's frozen module, sha-asserted; his live Week-5 construction: the package + te1 / low1 +
ONECATCH, 89's `own_caps`, QB cap 5, overlap 4, the cheap +2 block, A1 .30 / A2 .14 / B .28 / C .28):
- **FAVHI (the reference):** study 97 / 99's RBMATE4_FAVHI exactly. Study 96's `combo_rules` (ONECATCH and the RB mate in one
  optimize patch per solve) take the QB-own-RB floor on the first 4 C-cell book solves, with the pairs only for QBs of FAVHI
  teams: margin = 2 × implied team total − game total ≥ 3, in a game whose total is ≥ the slate's numpy quantile 2/3 over its
  games. It uses study 97's frozen `scenarios` / `rm_pairs_for` texts (`938032a8` / `fb2142c7`).
- **COMBO:** FAVHI + study 102's picked arm, in ONE build:
  - **TAIL_STACK8:** study 102's `tail_rules` entered before `combo_rules`. The full stack touches only the A1 book solves and
    the RB mate only the C slots, so each wrapper keeps its own optimize patch and its own records.
  - **CEIL_BLOCK8 / CEIL_ALL:** the same objective change as study 102 (p85 on the block / every row), with FAVHI's floor
    riding on that objective.
- **LIVE:** information only. Its line is printed, and decides nothing.
- **Mechanics checks (the census):** both arms' RB-mate slots, ruled and plain, equal on bank 1406's smoke. COMBO's pick
  binding is shown on the same lines as study 102's census (full-stack ruled / plain, or the p85 − mean size). The vacuity is
  COMBO vs FAVHI.

## 3. The read
- Study 102's reader, adapted to read **COMBO − FAVHI** (a dealt-identity field for that pair). Study 63's statistics; two
  draws and pooled; two-sided 0.95, B 20,000; the reader's own new seed.
- **THE PASS RULE (fixed now; study 103's guarded rule) on COMBO − FAVHI:**
  - **> 0 on both draws for the mean best real lineup points**, AND
  - **P(≥ 1 big seat) not worse on both draws**, AND
  - **the pooled expected big seats ratio ≥ 0.80**.
  - Pass → the morning page offers the pair ("FAVHI and the pick together held"). Fail → "pick one of the two", or neither,
    his call.
- **Information:** COMBO − LIVE and FAVHI − LIVE, with his rule printed; P(best ≥ 200) for every arm.
- **Honest limits:** the same 36 slates of 2023–24 as studies 89–103; a fresh opponent and simulation draw, not new games. The
  harness builds on simulator means; his book on Fantasy Points' projections.

## 4. Banks, integrity, production
- **Banks (the laptop's full-set check and text scan: CLEAN, banks and seed):** **3408–3419** (set A 3408–3413, set B 3414–3419; sims
  bases 3458–3469, fields 4108–4119); the reader's bootstrap seed **20261147** (new).
- The census on bank 1406 before the freeze; PYTHONHASHSEED=0; one heavy job at a time.
- **Production if it passes:** one small reviewed commit opens the wiring's pair refusal (RB_MATE_SCOPE = favhi with
  A1_FULL_STACK = 1, or the p85 switch if one is built), plus the laptop's Week-4 check of the pair. Study 38's classification of
  any new union flag comes before any merge.
