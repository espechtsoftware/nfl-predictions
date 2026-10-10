# Preregistration: study 116c, the receptions floor with a vacated exception — keep a backup running back when the team's pass-catching back is ruled Out (DRAFT 2026-10-10, committed BEFORE study 116 is read; conditional)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer, on the lab reviewer's design (10-10,
about 10:45), committed and pushed **before study 116's READ**. **Conditional: it runs only if study 116 picks a dose**; its
code is written only then. The lab reviewer reviews, runs the census, freezes, runs and reads; the laptop acks. **Information
for his decision.**

## 1. Why
- **The operator, 10-10, in the laptop's session (verbatim):** "Do we also need to consider that if an, another running back is
  out, like the lead running back that gets receptions, that those receptions would go to the backup?"
- **The project's prior (context, not an answer):** the 2026-08-03 event study (Addendum 44, as summarized in production's
  feature 021) found that when a high-target player is out, his targets flow mostly to the other receivers (running backs
  about 0), while a high-carry player's carries flow to the other backs (the RB2 +15.8 share points). Its absences were mostly
  receivers, so it does not isolate a pass-catching back's absence.
- **Support (an outcome-blind count, 10-10):** across the 36 weeks of 2023–24, a running back averaging 2+ receptions was ruled
  Out on **44 team-weeks**, which would keep about **114 backups** (about 3 a week) that the floor removes, against about 33
  backs removed per slate. Few of them are likely to be in the book, so **this exception may change little** (§3's vacuity
  line decides before any run).
- **In-sample, as study 116:** the floor's idea came from these same slates' outcomes (study 116 §1); this follow-up inherits
  that limit.

## 2. The design (fixed now)
- **Code: study 116's frozen module** with one added arm, `PICK_VAC`; `run()` = 116's `run()` with listed edits (a test asserts
  it). **Arms: PICK** (study 116's picked dose, its frozen threshold X) **and PICK_VAC.**
- **PICK_VAC = PICK, except** a running back below X is **kept** when a teammate running back (same team, that week) whose
  receptions per game (study 116's measure: this season's last up-to-4 regular-season games before the week) is **≥ X** is
  ruled **'Out'** on the pre-lock injury report. **'Out' only** (not Doubtful or Questionable), as production's vacated
  features use.
- **Where the Out teammate is read:** Out players are not in the k1 pools (study 116 §5), so his status, team and receptions
  come from `player_week_training` (`injury_status`, pre-lock) and the weekly stats, never from the slate frame. `was_active`
  is an outcome and is never read.
- **Banks (the laptop's reservation; the full-set check of 749 used or reserved banks: CLEAN; the text scans: to follow):**
  **4328–4339** (set A 4328–4333, set B 4334–4339; sims bases 4378–4389, fields 5028–5039). **Seed:** study 116's reader seed
  (20261161).
- **Production, if it passes:** DK OUT players leave production's T-70 pool too (`unavailable_ids`), so a production version
  reads the Out teammate from DK status plus the official inactives, not from the frame (the laptop, 10-10).

## 3. The read
- **Vacuity first (read in the smoke and the binding census, before any scored bank):** the rows where PICK and PICK_VAC
  differ, and PICK_VAC's dealt identity to PICK. **Dealt identical on more than 80% of slate-banks = a dead lever: study 116c
  is not run** (recorded), and the answer to his question is "it would change almost nothing in the harness".
- **THE PASS RULE (fixed now):** PICK_VAC − PICK on P(≥ 1 big seat) **better on both draws AND the pooled expected big seats
  ratio ≥ 0.80** (his rule; guard 1 printed).
  - **Pass** → the vacated exception rides with the floor if the floor goes in (his 116 decision: a 116 pick that 116b
    confirms goes into his Week-5 entries); the laptop's switch adds the exception to the same measure.
  - **Fail** → the floor as picked, without the exception.
- **If study 116 picks nothing, study 116c is not run** (recorded).

## 4. Integrity
- The laptop's full-set bank check and text scan before the freeze; the lab reviewer's census on bank 1406; PYTHONHASHSEED=0;
  one heavy job at a time.
