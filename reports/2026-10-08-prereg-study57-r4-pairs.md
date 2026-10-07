# Preregistration: study 57, R4 joint coverage for his 2-entry contests, in the harness (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding (support) census (§6), before any scored
bank.
- DRAFT `c395471e`, with additions before study 56's read: the combined arms (`01961fbf`) and Rev6 (`3ca3d8c6`).
- The decision pair was fixed by his arming (`93a2d04d`). Two design fixes came out of the smoke (`328af45a` and this
  freeze), both before any scored bank.
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
  - **Every other contest keeps its head deal exactly.** R4's pairs replace only the five contests' ranks in the dealt
    layout.
  - **Changed at the smoke, before the freeze:** the first form wrote only the five pins and re-ran the head layout. That
    re-blocks six other contests: the single Wildcats move 15–17 → 11–13, and his Warm Up sats move 20–22 → 14–16, which
    overrides his Rev6 order.
    - Production's Sunday step must therefore pin all 29 contests from the head deal, replacing only the five. The
      laptop is told.
    - The census asserts that no other contest moves.

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
- **The smoke** (`~/s57-panel/smoke.sh`; bank 1406; 2024 W10 SCORED with the F dump, 2023 W5 MECHANICS ONLY; Rev6). It
  found two design defects, both fixed before the freeze:
  1. **The five pins alone re-blocked six other contests** under production's head layout. The single Wildcats moved
     15–17 → 11–13, and his Warm Up sats moved 20–22 → 14–16, against his Rev6 order. R4 now replaces only the five
     contests' ranks in the dealt layout (lab `4c5c10a`). Production's Sunday step must pin all 29 contests from the head
     deal; the laptop is told.
  2. **Independent picks repeated lineups inside the 2-entry group.** The three Wildcats took the same pair; the
     laptop's catch. His rule, encoded in enter_layout's head docstring, is that no lineup repeats inside a size group
     (2026-09-24; "All distinct", 10-05). The five pairs are now chosen SEQUENTIALLY in his Rev6 order (the $555 2x, the
     three Wildcats, the Millionaire), each from the book rows the earlier ones have not taken (lab `e7d73ad`).
  - **Production parity** (the final smoke): production's `entry_choice.joint_coverage`, given the same F and the same
    exclusions, picks the same pair as study 32's `choose` for all five contests (2024 W10, bank 1406).
  - The census and the reader exited 0; the reader printed section names only.
  - The logs: lab `results/s57/SMOKE_s57.log` (the first smoke and the final).
- **The binding (support) census** (outcome-blind; bank 1406; 36/36 slates of 2023–24; code `e7d73ad` clean;
  `results/s57/CENSUS_s57_binding.txt` `96532e4d…`, raw `cec6d951…`; lab `9e3416a`):
  - R4's pair differs from the head pair on every slate-bank, for all five contests.
  - No other contest moves (asserted). The five pairs are disjoint (asserted).
  - The pre-lock field fell back on 1 of 36 slate-banks (0.028).
  - The priority order (CB_PRI) moves 16.6 of 26 book positions.
  - R4 − the head pair, simulated in-sample (study 32 found the simulator over-sells about 3×): supersat +0.038, Wildcats
    +0.012 / +0.019 / +0.014, Millionaire +0.008.
- **Banks:** 1593–1598 and seed 20261109. The reviewer's unique-blob scan of both repositories (8,048 lab and 17,714
  production blobs up to 5 MB) found them only in study 57's own records (the DRAFTs, `s57_drive.py`, `s57_report.py`).
  No result file exists on disk.
- **Code:** nfl2 `production/s57-r4-pairs-20261007` @ `e7d73ad` (the census at `9e3416a`):
  - `experiments/s57_r4_pairs.py`, sha256 `a1c1ce66f7e2f241a4ff907cb976726b04dc7b6cffc1428b6db1357075f729e4`;
  - `scripts/s57_drive.py`, `e71c082b27655efec08bd6b3e2029e36e387f1b4b9f8b7d324fa3089a86019ea`;
  - **`scripts/s57_report.py` (the reader), sha256 `d7fedb91d73243ba52e09b2a3b36f7da0438c2e85e792ddd93512ff31561c633`**;
  - `scripts/s57_census.py`, `705f317f5604a51031ac60ff741478fde8f21ffb811aab10cd85159bb238a4cf`;
  - `tests/test_s57_r4_pairs.py`, `9a7b36e89a7319140760815502860b8307e507733d970b3018c96a80ddcd0e27` (7 tests);
  - unchanged, sha-asserted: `s32_sorting.py` `06c35b9a…`, `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py`
    `f3f9d735…`, `priority_deal.py` `fa47594d…`, and production's `enter_layout.py` `3cb051ac…`;
  - the plan: `plan-week5-rev6-s24.json` `ac10ddf6…`.

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
