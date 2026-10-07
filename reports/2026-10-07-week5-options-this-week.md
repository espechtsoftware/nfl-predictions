# Week 5: what can still change this week (2026-10-07, afternoon)

The operator, 10-07: *"I'm very interested in finding improvements that can be made this week after several weeks of
heavy losses. Please consider ideas - prioritizing those that can be tested this week."*

Outside reviewer. Everything here was measured today on data we already hold: the Week 1–4 real Millionaire fields
(1.33M lineups), the T-70 frames, the W2–4 replay books at the Week-5 settings, and 2018–2025 history. Scripts and full
outputs are in `reports/2026-10-07-brainstorm/` (`line_depth.*`, `role_value.*`, `role_persist.*`). Aggregates only.
This is evidence for the operator's Saturday choice. It is not a passed test.

## 0. In plain words

**Already right under the Week-5 settings (nothing to do):**
- the salary is used (at most $300 left in any replay row);
- defenses are cheaper than the field's;
- about two-thirds of rows sit in the four highest-total games;
- late-game inactives are replaced at 1:55 CT by production's step.

**New today: what wins at the depths Week 5 actually enters.** Week 5's installed plan puts most entries into contests
paying the top 1–4%, with a few shallower. Within the same user's lineups, three patterns held in **all four weeks** at
those depths:

| Within the same user's lineups (users with 20+ entries) | top 1% | top 4% | top 10% | top 20% |
|---|---|---|---|---|
| **2+ players under $4,000 vs 0–1** | 1.87 | **1.81** (1.73 / 2.15 / 1.92 / 1.88) | 1.77 | 1.71 |
| **Defense under $3,000 vs $3,500+** | 2.86 | **2.29** (2.98 / 3.09 / 2.42 / 1.22) | 1.91 | 1.76 |
| **QB with 3+ teammates vs 2** | 1.32 (mixed) | **1.29** (1.35 / 1.12 / 1.29 / 1.08) | 1.28 | 1.23 |
| QB with 1 teammate vs 2 | 0.80 | 0.82 (W4 1.68) | 0.85 | 0.90 |
| Projection above the user's own median | 1.55 | 1.42 (W2, W4 below 1) | 1.38 | 1.31 |
| Chalkier (ownership sum above own median) | 0.99 | 1.00 | 1.00 | 0.99 |

The numbers are odds ratios of finishing inside the line; per-week values are in brackets. Higher projection and chalk
do not reliably help, even at shallow depths.

**Why study 53 found nothing for the cheap block.** It tested on 2022–24, the three weakest seasons since 2018 for
cheap players with real roles, on both value per dollar and the 4× rate. 2026 has the highest value per dollar of the
nine so far:

| Weeks 1–4, depth-chart starters under $4,000 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | **2026** |
|---|---|---|---|---|---|---|---|---|---|
| Points per $1,000 | 1.85 | 1.82 | 1.81 | 1.80 | 1.43 | 1.64 | 1.16 | 1.76 | **1.87** |
| Share scoring 4× salary | .103 | .124 | .110 | .139 | .074 | .099 | .051 | .112 | **.130** |

A season's early *average* cheap value carries forward: across 2018–2025, Weeks 1–4 correlate 0.68 with Weeks 5–8.
Its *boom* rate does not (0.21), and booms are what deep lines need. So this supports the cheap block for 2026, but only
partly.

**Options, ranked:**

1. **Cheap +2 in place of the matchup block, as an override of the frozen stop. The operator decides.**
   - **On history:** it is neutral, not harmful (2023–24 +0.004 [−0.031, +0.043]; 2022 −0.0016; expected big seats −6%).
   - **This season:** the evidence is consistently positive. The W2–4 replay ran ahead every week (ratio 1.46), and the
     real fields show the pattern at every depth, every week.
   - **Against it:**
     - This reasoning comes after study 53's read and uses the same four weeks that suggested the idea.
     - The boom rate is weak to persist (0.21).
     - It would be recorded as an override, not a passed test.
   - **My recommendation:** if one block goes in this week, cheap +2 rather than matchup. Both are neutral on history,
     and only cheap has this season's evidence behind it.
   - **Timing:** decide before Friday's A3 rehearsal, so the rehearsal and its 6e snapshot gate use the block that will
     be entered. Production already writes both files on Thursday.
   - *(Earlier today I told the laptop I would not argue for an override. The depth and season results above are new
     since then, and they change my view of his choice. They do not change the frozen verdict.)*
2. **Keep the matchup block.** This is the rule's choice, also neutral on history (study 51: enterable).
3. **For Week 6, with proper tests:**
   - **A shape tilt toward QB + 2 / QB + 3.** Our Week-5 replay rows are 50% QB + 1, 42% QB + 2 and 8% QB + 3+, while the
     field runs about 52 / 33 / 15. QB + 3 beat QB + 2 in all four weeks at the top 4–20%. This needs a harness test at
     the installed plan's lines; study 18's shape result stands until then.
   - **Duplicate-aware dealing** for one-seat satellites (study list 50).
   - **R4 joint coverage** for the contests with two entries (study 32 passed, +0.030; the tool is due in Week 6). The
     five-entry SUPERSat pins follow his rule ("reuse my top lineups ... hope with those is to win many"), so R4 does
     not apply there.

**Checked and not worth doing:**
- a salary floor (salary is already used);
- a ceiling objective (tested null before the season);
- late swap (closed, lab 023 / 024);
- prop-line movement (the close absorbs the news, Addendum 17).

## 1. Method notes

- **Line depth (`line_depth.py`)**
  - Population: the week's largest Millionaire, users with 20+ entries, and lineups with all nine names matched to the
    T-70 frame.
  - The finish is inside the line when rank ≤ the line × the field.
  - The Mantel–Haenszel odds ratio is stratified by user-week.
  - Projection is the frame's mean projection. Ownership is realized field ownership, used as the measure of chalk.
- **Season regime (`role_value.py`, `role_persist.py`)**
  - Population: depth-chart starters (`player_week_role`: WR ≤ 3, TE 1, RB ≤ 2) in Sunday 13:00–16:30 ET games.
  - History: 2018–2025 salaries from `dk_salaries_historical`, joined by normalized name + season + week to
    `rosters_weekly` (gsis) and to `player_week_actuals`. A starter without an actuals row scores 0.
  - 2026: the T-70 frames with the same role and actuals tables.
  - An earlier pass without the role filter is not used: the 2022–25 salary rows hold about twice as many fringe cheap
    players as other seasons.
- **Stack size:** the W2–4 replay books at the Week-5 settings (`~/rehearsals/outside-cblocks-20261007T153309Z`) vs the
  10-07 structure screen's field shares.

## 2. Update, 10-07 afternoon: the satellites themselves (`satellite_fields.py`)

The Neo4j graph holds only the Millionaire, but Week 5's entries are mostly satellites. The same test on every W1–4
satellite / qualifier contest in `nfl_raw.contest_entries` (76 contests, 42,309 lineups). Odds ratios [95%] of finishing
in the top 2% / top 10% of the lineup's own contest:

| Feature (vs reference) | top 2%, by contest | top 10%, by contest | top 10%, within user | top 10% by contest, per week |
|---|---|---|---|---|
| **2+ sub-$4k vs 0–1** | 1.55 [1.25, 1.87] | 1.44 [1.23, 1.67] | 1.59 [1.36, 1.82] | 1.65 / 2.12 / 1.35 / 1.11 |
| **DST < $3,000 vs ≥ $3,500** | 2.46 [1.78, 3.42] | 1.92 [1.58, 2.42] | 1.55 [1.28, 1.92] | 4.25 / 3.16 / 2.70 / 1.21 |
| QB + 3+ vs QB + 2 | 0.97 | 1.02 | 1.23 [1.02, 1.47] | 0.93 / 1.00 / 0.95 / 1.19 |
| **QB + 1 vs QB + 2** | 0.81 [0.63, 1.04] | 0.83 [0.74, 0.93] | 0.95 | 0.65 / 0.88 / 0.68 / 1.18 |
| Bring-back 1+ vs none | 1.91 | 1.33 | 1.08 | 1.71 / 0.93 / 1.43 / 1.31 |
| Projection above contest median | 1.71 | 1.56 | 1.06 | 1.21 / 1.94 / 2.62 / 0.79 |
| Chalkier | 0.93 | 1.13 | 0.95 | mixed |

"By contest" is stratified by contest: it controls the field and compares users. "Within user" is stratified by
user-week, for users with 3+ satellite lineups that week. Weeks: W1 had one satellite (the FFWC qualifier), W2 7, W3
44, W4 24.

**What this changes:**
- **The cheap-player and cheap-DST patterns hold in the satellites too, every week.**
- **The QB + 3 advantage does not carry to the satellites.** QB + 2 over QB + 1 does, in three weeks of four. So study
  list 56 (the shape tilt) should test **fewer QB + 1 rows in favour of QB + 2**, judged at the satellite lines, rather
  than more QB + 3. Our Week-5 replay rows are 50% QB + 1.
- The projection effect seen between users (1.56–1.71) almost disappears within a user (1.06). It is mostly who builds
  the lineup, not a lever.

## 3. Update: the operator's priority contests (`priority_fields.py`)

The operator, 10-07: *"I'd consider the $20 milly satellites a lower priority, the 4444, 555, 333, WWFC are top
priorities."*

The same test, restricted to the 14 W1–4 contests the laptop's private shark-share table types as:
- FFWC qualifier ($14M) and FFWC sat/supersat;
- $4,444 MEGA and Showdown-MEGA sat;
- $555 sat/supersat;
- $333 Wildcat.

That is 12,219 lineups: the two $14M FFWC qualifiers hold 9,992 (sharp, 150-max fields, ~56% regulars), and twelve
small satellites hold 2,227. Odds ratios [95%]:

| Feature (vs reference) | top 2%, by contest | top 5%, by contest | top 10%, by contest | top 5%, within user | top 10% by contest, per week |
|---|---|---|---|---|---|
| **2+ sub-$4k vs 0–1** | 2.25 | 2.03 [1.60, 2.55] | 1.78 | **1.93 [1.50, 2.44]** | 1.65 / 2.94 / 1.96 / 1.19 |
| DST < $3,000 vs ≥ $3,500 | 3.26 | 1.93 | 2.22 | 1.16 [0.70, 2.06] | 4.25 / 1.31 / 2.23 / 0.93 |
| **Bring-back 1+ vs none** | 2.01 | 1.73 | 1.49 | **1.51 [1.14, 2.04]** | 1.71 / 0.50 / 1.40 / 1.17 |
| QB + 1 vs QB + 2 | 0.51 | 0.64 | 0.68 | 0.78 [0.61, 1.00] | 0.65 / 1.54 / 0.64 / 1.45 |
| QB + 3+ vs QB + 2 | 1.30 | 1.12 | 1.15 | 1.03 | mixed |
| **Projection above contest median** | 1.94 | 1.74 | 1.67 | **1.39 [1.15, 1.74]** | 1.21 / 1.83 / 2.32 / 0.86 |
| Chalkier | 0.99 | 1.00 | 0.97 | 0.88 | mixed |

The FFWC qualifiers alone and the small priority satellites alone give the same signs (full output in
`priority_fields.txt`). W2 and W4 rest on small satellites only, so their per-week values are thin.

**What this adds:**
- **In his priority contests, the cheap-player pattern is the strongest and steadiest signal:** about 2× the odds, every
  week, within contest and within user. It carries the W5–W8 cheap tracking, and the 2025 regime study (list 58) should
  be judged at these contests' lines.
- **Bring-backs and higher projection help here within the same user,** unlike in the $20 Millionaire satellites. Study
  list 56 (the shape tilt) should be judged at these contests' lines: fewer QB + 1, keep bring-backs.
- **The utility definition for tests should follow his priority statement.** On 10-06 he said the $125 WFFC "doesn't"
  count as a big win; on 10-07 he names WFFC among the top priorities. Production should confirm with him which WFFC
  contests count before the next test freezes its endpoint.

## 4. Priority-first dealing: an entry-side change for Week 5 (requested by the operator, 10-07)

The operator asked for anything more that could help his priority contests this week. He has asked production to try
this one directly; it is logged here as the proposal's record.

**What:**
- His priority entries ($4,444 / $555 / $333 / FFWC satellites: 22 of 53 entries, most of the fee total) are dealt
  first, from the book's rows ranked by a simple frozen score.
- The rows left over go to the 29 $20-Millionaire-satellite entries, which he calls lower priority and which do not
  count as big wins.
- **The 26 rows are not changed.** The cheap +2 trial and its paper comparisons stay exactly as they are; only which
  row goes to which contest changes. This is class E (entry side): his authority, plus a mechanical rehearsal, the
  affected entries named, and a restore path (today's deal).

**FINAL RULE (production, the laptop, 10-07; logged in its wording):**
- **Score per row:**
  - 2 if the QB has 2+ teammates (players on his team, not QB or DST, FLEX included);
  - +1 for a bring-back (1+ non-DST player on the QB's opponent);
  - +1 for 2+ non-DST players with salary < $4,000.
  These are `priority_field_monitor.py`'s definitions.
- **With the cheap +2 block armed** (the reviewer's standing rule from the TD-deal screen, c9028505: a re-deal armed
  with a block "applies only to the 18 non-block rows over their own positions (the block keeps its ranks), tested in
  that form first"):
  - The 8 block rows keep their positions (0-based 1, 4, 8, 11, 14, 17, 21, 24).
  - The other 18 rows are sorted among their own positions by score, highest first, ties by book order.
  - 13 of those 18 positions are priority ranks, so the 5 lowest-scoring non-block rows go to ranks 20, 21, 23, 24 and
    26.
  - 6 block rows sit in the priority ranks either way.
  - The spares are untouched. Without a block, all 26 rows would sort.
- **Where it lives:** `union_reselect --priority-order` (`UNION_PRIORITY_ORDER`, default off, byte-identical when off),
  the same pattern as study 48b's WINNER_ORDER. The book.csv order is the deal, so the head layout, the row map, the
  exposure sheet and the relayout checks do not change.
- **Which ranks are priority** (Rev3 under head):
  - ranks 1–19 are his priority contests: $4,444 × 3 incl. the Showdown sat, $555 × 8 incl. the 2x supersat, $333 × 9,
    FFWC × 2;
  - ranks 20–22 are the Midseason Warm Up sats;
  - ranks 23–26 are the $20 supersats.
  The pinned $125 FFWC reuses rank 1. Its ticket is not a big win (the operator, 10-07). The Midseason Warm Up sats
  count as big under s38_plan but are not in his priority list, so they now get leftovers. The harm screen's P(≥ 1 big)
  prices that.
- **The test before entering:**
  1. The laptop commits a frozen harm screen first, in the TD-screen wording: NOT ENTERED if P(≥ 1 big) is below the
     unchanged deal in 2 or 3 of 3 weeks, or the pooled e_big ratio is < 0.80.
  2. The books: cheap2-armed W2–4 builds through the real switch (cheap2 vs cheap2 + priority order), scored by
     big_seat_stats on the Rev3 s24 plan.
  3. Descriptive beside it: the priority entries' mean percentile and their QB + 1 / bring-back / 2+ cheap shares,
     before and after.
  4. All of this is in-sample and disclosed as such. Then Friday's A3 runs with it armed, and arming on Saturday
     follows his yes after both. The restore path is UNION_PRIORITY_ORDER=0.

Real-field evidence for the score's elements in the priority contests (within user, top 5%):

| Element | Points | Evidence |
|---|---|---|
| QB with 2+ teammates | 2 | QB + 1 vs QB + 2: 0.78 [0.61, 0.97] (by contest 0.64) |
| A bring-back | 1 | 1.51 [1.15, 2.01] |
| 2+ sub-$4,000 non-DST players | 1 | 1.93 [1.52, 2.41] |

**Our rows** (W2–4 replays at the Week-5 settings, cheap +2 armed) against the priority-contest field:

| Share of rows | Ours | Field |
|---|---|---|
| QB + 1 | 49% | 41% |
| Bring-back | 58% | ~49% |
| 2+ cheap | 42% | 18% |
| All three of QB 2+, bring-back, 2+ cheap | 17% | — |

**Against:** study 48b, a whole-book re-deal by a winner-likeness score, read NO DIFFERENCE on history (+0.008
[−0.030, +0.044]). This deal is narrower: it moves rows only between his priority and lower-priority contests, so for
his utility the downside is about nil.

### 4a. The final deal order (the operator, 10-07): private plan Rev6

The operator's messages, verbatim, in order (Rev4 and Rev5 were built from the first two and never installed):
1. *"I forgot about the midseason warm ups. Those are big prizes. Can we move that up to under the 4444 and before
   555."*
2. *"I'm sorry - I didn't even realize what the showdown Mega is. That should be under the $333. The order should be:
   two mega 4444 satellites / midseason warmup / 555 / WFFC / 333 / Showdown mega / everything else."*
3. **FINAL:** *"I apologize again. I didn't understand what the prizes were in some of these contests. Let's change the
   order for the final time to: 4444 (all of them including the showdown - which seems the same as the others anyway) /
   555 / WFFC / 333 / Millionaire / Midseason warmup / Everything else including milly qualifiers."*

**How it is applied:**
- The deal follows the order of contests in his plan file. **Rev6** is Rev3's 29 contests, byte-equal, re-ordered only.
  It replaces Rev5.
- The installed form will be sha256 `5f8352eebf17860795922f8b5bca754c4ed0566c8c5ca63419e6dacd24e59470`. Nothing tracked
  holds the file itself.
- Rev6's per-rank entry weights are identical to Rev3's ([4, 3, 3, 3, 2 × 18, 1, 1, 1, 1]), so the same 26 rows are
  built in the same order. Rows needed and protected ranks stay at 26.

**Rank map under head (Rev3's ranks in brackets):**

| His order | Contests | Rev6 ranks |
|---|---|---|
| 1 | $4,444: MEGA, MEGA, Showdown MEGA | 1 [1], 2 [2], 3 [10] |
| 2 | $555 single entries × 6 | 4–9 [3–8] |
| 2 | $555 2x supersat | 1–2 [3–4] |
| 3 | the WFFC ($490 ticket) | 10 [9] |
| 4 | $333 2-entry contests × 3 | 3–4, 11–12, 13–14 [11–16] |
| 4 | $333 single entries × 3 | 15–17 [17–19] |
| 5 | the Millionaire (2 entries) | 18–19 [1–2] |
| 6 | the Midseason Warm Ups × 3 | 20–22 [20–22] |
| 7 | everything else: the $20 supersats pinned over 1–26, the $125 FFWC pinned at 1 | unchanged |

**The mechanics** (no pin tied the Millionaire to ranks 1–2):
- The head layout gives its two 2-entry head blocks (the shared top rows 1–2 and 3–4) to the first two 2-entry
  contests in file order. In Rev6 those are the $555 2x (1–2) and the first $333 2-entry contest (3–4).
- That $333 contest shares rows 3–4 with the Showdown MEGA and the first $555 single entry, and takes nothing from
  them.
- The Millionaire becomes an ordinary 2-entry contest on its own rows 18–19.
- The pins reach 26, and the all-head rule now protects through the Warm Ups' rank 22.
- **The priority span is ranks 1–22.** Only the $20 supersats read 23–26.

**The cheap block** keeps its 1-based ranks 2, 5, 9, 12, 15, 18, 22 and 25, so block rows land at:

| Block rank | Contests |
|---|---|
| 2 | MEGA #2, and the $555 2x |
| 5, 9 | $555 entries |
| 12, 15 | $333 entries |
| 18 | the Millionaire |
| 22 | a Warm Up |
| 25 | the supersats |

The priority sort fills the non-block ranks 1, 3, 4, 6, 7, 8, 10, 11, 13, 14, 16, 17, 19, 20 and 21, best first. The 3
lowest-scoring non-block rows go to ranks 23, 24 and 26.

**The harm screen's three arms**, under the same frozen rule, amended before any number was run:
- **CB:** Rev3, book order (unchanged).
- **CB_REV6:** Rev6, book order.
- **CB_PRI:** Rev6 + the priority sort.
