# Priority-first dealing: a frozen HARM SCREEN before the W2–4 fixed-book replay (2026-10-07)

**Status: FROZEN 2026-10-07 13:58 CT, before any replay number exists** (the laptop; the wording is the TD-deal screen's,
`c9028505`, which the reviewer worded). It is the test the money-path rule requires before the change is entered: a
fixed-book replay on the weeks with real fields. It is in-sample. The reviewer's study 59 is the harness test of the
same sort (below).

**Amendment 1 (2026-10-07, before any replay number exists): his contest order and the pairs.**

**His requests** (to the outside reviewer, verbatim):
- "I forgot about the midseason warm ups. Those are big prizes. Can we move that up to under the 4444 and before 555."
- Then, FINAL: "I'm sorry - I didn't even realize what the showdown Mega is. That should be under the $333. The order
  should be two mega 4444 satellites / midseason warmup / 555 / WFFC / 333 / Showdown mega / everything else."

**The vehicle: his private plan Rev5.** It replaces an intermediate Rev4, which was never installed.
- Rev5 holds Rev3's same 29 contests with byte-equal fields, re-ordered only. It is never committed; HANDOFF and the arm
  script carry its sha.
- Its per-rank entry weights equal Rev3's, so the MIX interleave and the book's rows and built order are unchanged.
- The new ranks under head:
  - the two $4,444 MEGA satellites: 1–2;
  - the Midseason Warm Ups: 3–5 (from 20–22);
  - the $555 singles: 6–11 (from 3–8). The $555 2x supersat keeps 3–4, the head block of the second 2-entry contest; it
    shares those rows with two Warm Ups and takes none from them;
  - the $490 FFWC: 12 (from 9);
  - the $333 satellites: 13–21 (from 11–19);
  - the $4,444 Showdown MEGA satellite: 22 (from 10).
- The Millionaire's 1–2, the pinned $125 FFWC at 1, and the pinned $20 supersats over 1–26 do not move.
- Every contest except the $20 supersats now reads ranks 1–22. Only the supersats read 23–26.
- **The block:** its ranks 2, 5, 9, 12, 15, 18, 22 and 25 are kept. Seven of them are inside 1–22: the second MEGA, the
  third Warm Up, a $555, the FFWC, two $333s and the Showdown each get a block row whatever the scores. Of the 18
  sorted positions, 15 are inside 1–22. The 3 lowest-scoring non-block rows go to ranks 23, 24 and 26.

**The arms** (both changes are in-sample):
- **CB:** today's deal, Rev3 in book order.
- **CB_REV5:** Rev5 in book order.
- **CB_PRI:** Rev5 with `--priority-order`.

**Each pair answers its own question under the frozen rule below** (NOT ENTERED if P(≥ 1 big) is lower in 2 or 3 of the 3
weeks, or the pooled e_big ratio is below 0.80):
- **(i) THE SORT:** CB_PRI vs CB_REV5, both on Rev5. This decides whether `--priority-order` is armed. It is the pairing
  of the reviewer's study 59, which isolates the sort.
- **(ii) THE PLAN RE-ORDER:** CB_REV5 vs CB. This decides whether Rev5 stands.
- **Descriptive only:** CB_PRI vs CB, the whole change against today.

"CB_PRI vs CB" in the rule below reads as pair (i), and the same rule applies to pair (ii).
- CB and CB_REV5 are ONE book: Rev3 and Rev5 give equal weights, which the replay asserts. They are dealt on their own
  plans.
- CB_PRI is the same build with `--priority-order`. Integrity requires the same 26 rows, the same block rows at the block
  positions, and the same spares.

## Why

The operator (10-07): "Let's try to do this one this week as it seems more promising." The proposal is the outside
reviewer's class-E change, logged at `29e6632b` on `review/outside-fill-order-20261006`, §4 of
`reports/2026-10-07-week5-options-this-week.md`. The book does not change; only which contest each row goes to.

- **The idea:** his priority contests ($4,444 / $555 / $333 / FFWC satellites) should read the rows that look most
  like what wins there. The rows that look least like it go to the $20 Millionaire supersats, which he counts as lower
  priority and not as big wins.
- **The evidence** (the outside reviewer; the W1–4 real priority fields; odds of a top-5% finish within user):
  - QB with one teammate vs two: 0.78 (by contest 0.64);
  - a bring-back: 1.51;
  - two or more sub-$4,000 players: 1.93.
- **The counter-evidence:**
  - study 48b re-dealt the whole book by study 48's winner-likeness score: NO DIFFERENCE (+0.008 [−0.030, +0.044];
    expected big seats ratio 0.899);
  - study 52's touchdown deal: NOT SUPPORTED.
- **The prior:** a re-deal moves wins between contests and does not create them, so a small or null effect is the
  likeliest reading.

## The deal (exact)

- **The score of a row** is computed pre-lock from the row itself, using the definitions in
  `scripts/priority_field_monitor.py`:
  - **+2** if the QB has 2 or more teammates: players on his team other than the QB and the DST, FLEX included;
  - **+1** for a bring-back: 1 or more non-DST players on the QB's opponent;
  - **+1** if 2 or more non-DST players have a DraftKings salary under 4,000.
- **The order: the reviewer's block rule** (TD-deal screen, "Block interaction"): "if both are ever armed together, the
  re-deal applies only to the 18 non-block rows over their own positions (the block keeps its ranks), tested in that
  form first."
  - With the cheap +2 block armed, its 8 rows keep their positions (0-based 1, 4, 8, 11, 14, 17, 21, 24).
  - The other 18 rows are sorted among their own 18 positions by score, highest first; ties keep the book's order.
  - The 15 spares are untouched.
- **What that does on Rev3 under head:**
  - The priority contests read ranks 1–19, the Midseason Warm Up satellites 20–22, and only the $20 supersats read
    23–26.
  - Of the 18 sorted positions, 13 are priority ranks. The 5 lowest-scoring non-block rows go to ranks 20, 21, 23, 24
    and 26.
- **The books:** his Week-5 construction on the W2–4 real fields with the cheap +2 block armed, as Saturday arms it.
  - `union_reselect` takes the bonus-blocks replay's live arguments: overlap 4, round-robin fill, QB cap 5, no
    ownership term, Rev3 K 26, 15 spares; W4 on FP projections.
  - Plus the block: `--term-block-rows 8 --term-block-source cheap2-wW.csv --term-block-tilt 0.20
    --term-block-cap-points 2.0`, with the file written by `scripts/cheap_block_file.py --points 2.0` from the week's
    T-70 frame.
  - **CB** (the unchanged deal): that build.
  - **CB_PRI:** the same build plus `--priority-order`, production's switch (the commit that adds it is named in
    HANDOFF with the numbers).
- **Integrity** (the week is VOID otherwise): both books hold the same 26 rows as player sets, the same rows at the 8
  block positions, and the same 15 spares in the same order.
- **Scoring:**
  - Each book goes through production's head layout on Rev3: `enter_layout write --layout head`, with
    `ENTER_SMALL_MAX_SHARED=5` and `ENTER_SMALL_OVERLAP_MAX_ENTRIES=10`, the live `week_env` values.
  - It is scored as this week's block replays: `big_seat_stats` on `~/s24-panel/plan-week5-rev3-s24.json`, each row's
    finish against the week's real Millionaire field.

## The frozen rule (CB_PRI vs CB)

**NOT ENTERED** if either holds:
1. CB_PRI's P(≥ 1 big) is below CB's (strictly) in 2 or 3 of the 3 weeks;
2. the pooled expected-big-seats ratio, Σ e_big(CB_PRI) / Σ e_big(CB) over W2–4, is below 0.80.

**This is a STOP rule only** (the reviewer, 10-07). The score's three features were all found on the W1–4 real fields,
so on W2–4 this check can show harm but not gain.

**Otherwise it passes this screen only:**
- It is entered in Week 5 only after Friday's armed rehearsal (A3) with the switch on, and on the operator's yes at
  arming.
- **The reviewer's harness study** (proposed 10-07 for Thursday morning, read by about noon) is the decision-bearing
  test if he sets the same bar as study 56. Its shape is study 52's: the LIVE deal vs the PRIORITY deal on his 26-row
  book (and in the block-kept form), the 2023–24 read and the 2022 go / no-go.
- Disclosure, in these words: *"in-sample (weeks already seen; the score's evidence comes from the same W1–4 real
  fields); no out-of-sample evidence from this check."*

**If study 56's quotas are also armed** (only on its PASS that is not contradicted, and his yes):
- The same screen runs on the cheap +2 + QB2HALF pair (CBQ vs CBQ_PRI) under the same rule.
- It must pass too before both are armed. No untested combination.

## Descriptive, beside the rule (no part of it)

- P(≥ 1 big) and e_big over the priority contests only, and over the other big contests.
- The priority entries' mean Millionaire-field percentile.
- The QB-with-one-teammate, bring-back and 2+ sub-4,000 shares of the priority entries, under each deal.
- **CB_ALL (exploratory, not armable this week under the block rule):** all 26 rows sorted by the score. This is the
  outside reviewer's original form.

## If it is entered

- **Monitoring:**
  - Every Monday, the live book is re-dealt in its unchanged order and scored beside the entered deal, on the same real
    fields: P(≥ 1 big), e_big, and the priority contests' finishes.
  - The P3 and study 38 records are kept as they are. The reviewer decides whether study 38's paper arms follow the
    switch.
- **Rollback:** `UNION_PRIORITY_ORDER=0`, today's deal.
- **The reviewer's standing line**, from the same screen: "One construction change per week." The cheap +2 trial is
  already this week's change. The operator decides whether both run.
