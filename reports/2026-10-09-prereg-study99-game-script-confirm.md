# Preregistration: study 99, the confirmation of study 97's picks — study 97's frozen code on a fresh draw of the same slates (DRAFT 2026-10-09, committed BEFORE study 97 is read)

**Status: DRAFT 2026-10-09 (21:45 CDT)** by the outside reviewer, committed and pushed **before study 97's READ** (the lab
reviewer's condition, 10-09 evening). The lab reviewer freezes it (banks and seed) after study 97's READ; the laptop acks.
**Information for his morning decision.**

## 1. Why
- Study 97 (frozen `88738a69`) makes eleven comparisons on the 36 slates of 2023–24; under no true effect about three pass his
  rule by chance. Its §3 situation rule picks **at most one RB version and at most one QB + 2 version** for the morning page.
- Study 81 → 84 showed the same rule on the same slates moving from +4.7 to −1.2 across bank sets (the bank-set variance
  finding). **A pick is suggested more credibly if it holds on a fresh draw.** Fresh banks re-use the SAME 36 slates' real
  outcomes: this is a check of robustness to the opponent and simulation draw, **not new outcomes, not out-of-sample**; a pass is
  still weak support (the picks were chosen on these slates).

## 2. The design (no new code)
- **Code: study 97's frozen module, census, driver and reader, byte for byte** (nfl2 `production/s97-game-script-20261009`,
  module `7df6f324…`, reader `e5827c73…`, census `346b403f…`, driver `5dff66b7…`; the reader's bootstrap seed 20261142 kept, as the
  frozen reader prints it). Nothing is edited; study 99 is the same run on new banks.
- **Banks (proposed; the laptop scans):** **3148–3159** (set A 3148–3153, set B 3154–3159; sims bases 3198–3209, fields
  3848–3859).
- **Which lines decide:** ONLY the comparisons of the arms study 97's §3 rule picks, by the same §3 rule:
  - a picked RB-with-his-QB version (RBMATE4_FAV / RBMATE4_FAVHI) is CONFIRMED iff it again beats BOTH LIVE and RBMATE4 by his
    rule;
  - a picked FAVRB_NAKED4 / FAVRB_OPPQB4 / QB2_SHOOT / QB2_DOGHI is CONFIRMED iff it again beats LIVE by his rule.
  - Every other line is printed by the frozen reader and is information only.
- **If study 97's §3 rule picks nothing, study 99 is not run** (recorded).
- **The morning page:** a pick is suggested as "held on a fresh draw" only if CONFIRMED; a pick that fails here is reported as
  "did not hold on a fresh draw" and is not suggested; if study 99 cannot be read before the morning, the page says so.

## 3. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's binding census (the frozen census on bank
  1406 = study 97's own census, so its numbers equal 97's binding census by construction; it is re-run as the mechanics check);
  PYTHONHASHSEED=0; one heavy job at a time.
