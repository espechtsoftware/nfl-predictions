# Preregistration: study 57, R4 joint coverage for his 2-entry contests, in the harness (DRAFT 2026-10-07)

**Status: DRAFT 2026-10-07.** It was written while study 56 ran, and it does not depend on 56's lever.
- The code, the smoke, the binding census, the bank scan and the freeze follow.
- The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The source:** study list item 57, approved for testing as a Week-6 candidate (the operator 10-07 ~12:00: "if they pass
  the necessary tests"). He later named it his second priority after 56 this week: "1 is my priority to test, but 1 and 2
  would be great".
- **Study 32** (Addendum 137) offered R4: joint coverage, the m-subset of a finished book most likely to put at least one
  entry in a contest's top S, chosen against a PRE-LOCK field.
  - On 36 slates of 2023–24, R4 − RND +0.030 [+0.001, +0.060]; R4 − R0 (book order) +0.043.
  - By m: m = 2 +0.026, m = 3 +0.069.
  - Production's tool is `scripts/choose_entries.py`.
- **His Week-5 plan (Rev6, his final order of 10-07)** holds five UNPINNED big contests with 2 entries each: the $555 2x
  supersat (ranks 1–2), three $333 Wildcats (3–4, 11–12, 13–14) and the Millionaire (18–19). The head layout deals them
  consecutive ranks. The DRAFT first named Rev5; it moved to Rev6 before study 56's read.
- **Disclosed:** study 32 chose R4 among six rules on these same 36 slates. This read is therefore partly in-sample for
  the rule (not for these contests or this plan).
  - No 2022 go / no-go is possible: the pre-lock field needs predicted ownership (TABPFN_LS), which exists for 2023–24
    only.
- **The prior:** study 32's m = 2 cells gave +0.026 against RND, and the live contests differ from its targets. A small
  positive or NO DIFFERENCE is the likeliest reading.

## 2. Arms (`experiments/s57_r4_pairs.py`)
- **The book:** on each slate-bank, study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted), his live book with
  Week 5's live cheap +2 block (LIVE_CB, study 53's CHEAP2_BLOCK8), dealt on Rev6 (`plan-week5-rev6-s24.json`
  `ac10ddf6…`).
- **CB** (reference): the head deal.
- **CB_R4** (THE DECISION): the same deal, except that each of the five unpinned 2-entry big contests takes R4's pair.
  - The pair is chosen from the book's 26 rows by study 32's `choose` (m = 2; the contest's N and its big seats S),
    against study 32's pre-lock field (TABPFN_LS predicted ownership, DSTs uniform; study 32's fallback) on W_SIM of the
    slate-bank's own worlds.
  - The pairs are written as pins, so the small-contest overlap limit does not re-deal them, as production's pins.
  - Every other contest keeps its head deal.

- **Added to the DRAFT before study 56's read (the laptop's design note, 10-07):** if priority-first dealing (study 59)
  is armed too, the entered deal is "the priority sort, then R4 on top". That is a combination neither arm above covers.
  Two more arms make it tested:
  - **CB_PRI:** the same book in production's priority order (`priority_deal.py`, the block kept), head deal;
  - **CB_PRI_R4:** CB_PRI with the five contests pinned to R4's pairs. R4 picks book ROWS, not ranks, so the pins name
    the positions those rows hold in the priority order.
  - **Which pair decides is fixed by his arming, not by any outcome:** CB_PRI_R4 − CB_PRI if the operator arms the
    priority order for Week 5 (after study 59), else CB_R4 − CB. The reader prints both, with the same rule each.
  - **Resolved before any study 57 outcome (10-07 ~14:40):** the laptop's frozen W2–4 harm screen for the priority order
    (`27a1957b`, amendment 1 `7ee09fe1`) said NOT ENTERED: lower in 2 of 3 weeks, seats ratio 0.587. The priority order is
    not armed for Week 5, so **the decision pair is CB_R4 − CB**. CB_PRI_R4 − CB_PRI is printed as descriptive.

## 3. Endpoint and rule (the reader `scripts/s57_report.py`)
- **THE READ: 2023–24** (36 slates).
  - CB_R4 − CB, P(≥ 1 big seat) per slate on the calibrated field v2.
  - Two-sided 0.95. B 20,000, seed 20261109.
  - Banks 1593–1598. The unique-blob scan precedes the freeze.
- **Guards** as in studies 54–59, gating a PASS only.
- **Verdict:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **No go / no-go** (no pre-lock field for 2022). Disclosed with the in-sample caveat above.
- **THE TRIAL RULE** (study 51's), without the 2022 clause: NOT ENTERED if WORSE or the expected big seats ratio < 0.80;
  MOOT on a dead lever; otherwise ENTERABLE, his decision.
- **THE WEEK-5 LINE:** by default the operator's study-56 bar applies (live only on a PASS), unless he sets another.
- **EXPLORATORY:**
  - the five contests' own P(≥ 1 big seat);
  - R4's simulated (in-sample) gain against its realized gain;
  - the l02 field.

## 4. What a verdict can do
- **PASS or ENTERABLE:** production's Sunday step. After the T-70 build, `choose_entries.py` (m = 2) runs per unpinned
  2-entry big contest, and its pairs are written as plan pins before the upload.
  - That is a new step inside the last hour before lock, so it enters only after Friday's rehearsal runs that exact step
    (the laptop, 10-07).
- **Otherwise:** the head deal stands.

## 5. Production parity
- The pair rule is study 32's `choose` (the R4 branch), which production's `entry_choice` / `choose_entries.py` port. The
  smoke checks both pick the same pair from the same inputs.

## 6. Smoke and integrity
(Added at the freeze.)

## 7. Order
1. This DRAFT.
2. The code, the smoke (including production parity), then the binding census.
3. The freeze.
4. The laptop's ack and bank scan.
5. The run.
6. The confirmatory census before the read.
7. The read.
8. The re-run.
9. The records.
