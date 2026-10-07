# Preregistration: study 60, the rows for a big-contest ticket at the CASH line -- the book's top rows vs the plain FP and props top rows, on the real Millionaire field (DRAFT 2026-10-07)

**Status: DRAFT 2026-10-07** by the reviewer, before any Week-5 outcome.
- Week 5 locks Sunday 10-11, and its standings load Monday 10-12. This study freezes before that load.
- Before the freeze come the reader, its tests, the W4 mechanics smoke and the outcome-blind identity census (§7).
- The power table (§6) is filled in from the W2–4 in-sample baseline AFTER this DRAFT is committed. Nothing in §2–§5
  changes when it is.

**Units:** z-scores, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The source:** study list item 60. It comes from the outside reviewer's options note §5 (`6ad3f007` on
  `review/outside-fill-order-20261006`). The operator 10-07, to the laptop: "here's what the outside reviewer says, and I
  agree".
  - His reason: "if I win entries next week, I'll only have 1-2 of the large ones so I need to make them count".
- **The target is the CASH line, not a seat line.**
  - Inside a big contest his win is $500+ (his big-win rule). In a $333+ contest that is about any cash: roughly a
    top-20% line in a sharp field.
  - Studies 54–59 measured the satellites' deep seat lines instead.
- **What W2–4 showed (in-sample).** The outside reviewer scored the P3 replay books in the real fields
  (`reports/2026-10-07-brainstorm/cash_line_books.txt`; the share of the field each row beat):
  - The book's #1 row was the plain optimizer's #1 in all three weeks.
  - The props-means #1 beat more of the Millionaire field each week: .15 / .83 / .43 against .02 / .71 / .35.
  - In W3's FFWC qualifier field: .75 against .60.
  - For two entries, no construction's top rows were consistently better.
- **Why a real-field record and not the harness:**
  - The harness has no FP, props or SIS history (the six-season limit).
  - So this is a PROSPECTIVE paper record from W5, like P1 and P3. It uses P3's weekly books and P1's yardstick, and
    builds nothing new.
- **This study adopts nothing.** Which rows go on a big-contest ticket is the operator's decision. The study supplies
  the record each Monday and a frozen reading rule (§5).

## 2. Rows (outcome-blind; from P3's weekly arms, `scripts/p3_arms.sh`)
P3 builds three books each week from the ENTERED T-70 union's own recorded inputs (the frozen
`reports/2026-10-07-prereg-p3-simple-baseline.md` §2). This study reads their top rows in `book.csv` order:
- **R0 #1 and R0 #2:** the ENTERED book's rows 1 and 2.
  - These are the rows a 1–2-ticket contest takes under the head layout when it heads his contest order. His order
    (Rev6, 10-07) puts a won big-contest ticket first: 4444, 555, WFFC, 333, Millionaire, Warm Up.
  - ENTERED must be P3's byte-identical rebuild of the entered book.
- **FP #1:** MEAN_MILP's row 1. This is the plain capped optimizer on the LIVE projections, which are FP's from W5.
- **PROPS #1 and PROPS #2:** PROPS_MILP's rows 1 and 2. This is the same optimizer on props-implied DK points where a
  player has props, else on the live projection.
- **Pairs** (two tickets; all lineups distinct, his rule):
  - **R0 PAIR** = {R0 #1, R0 #2}.
  - **MIXED** = {R0 #1, PROPS #1}. When PROPS #1 is R0 #1's lineup, MIXED = {R0 #1, PROPS #2}.
  - **PROPS PAIR** = {PROPS #1, PROPS #2} (descriptive).
- **Two lineups are the same** when they hold the same nine players, in any order.

## 3. Measures
- **PRIMARY, the yardstick: P1's, unchanged** (`reports/2026-10-07-prereg-p1-contest-edge.md` §4 with amendments 1–2).
  - Each row gets a latent z in the SAME week's Millionaire field: z = Φ⁻¹(1 − p), with p = (position − 0.5) / N.
  - position = 1 + the number of the field's entries (every real entry of ours removed) strictly above the row's real
    points. N = those entries + 1.
  - The code is `p1_record.latent_z`, imported unchanged and sha-pinned at the freeze.
  - Real points come from `moneygate_score`'s week tables, as P3 scores them: canonical names, in hundredths. A name
    nobody in the field rostered scores 0 and is counted.
  - **A pair's z is the higher of its two rows' z.** A win needs one entry over the line.
- **THE TWO DECISION DIFFERENCES, per valid week w:**
  - **D1 (one ticket):** d1_w = z(PROPS #1) − z(R0 #1).
  - **D2 (two tickets):** d2_w = z(MIXED) − z(R0 PAIR). It asks whether the second ticket should take the props #1
    instead of the book's #2.
  - They answer two different decisions (a 1-ticket contest, a 2-ticket contest). So each keeps its own rule, with no
    multiplicity adjustment; disclosed here.
- **SECONDARY, descriptive (never ruling):**
  1. **Cash at the real lines.** For each contest in the week's ladder file (`scripts/cash_line_rows.py`; private,
     `~/private/cash-line/cash-lines-wWW.csv`), each row is placed among that contest's real entrants by
     `moneygate_score.place`, with ours removed and DraftKings' tie split.
     - A hit is a finish at or inside the contest's line: `cash500_last_position` for the roles big and gpp,
       `seat_last_position` for sat.
     - Counts only. The role "big" (a $333+ fee or a won ticket) is the study's real target. It first appears in a week
       he holds such a ticket; W2–5 have none.
  2. **The proxy cash line:** a finish in the Millionaire field's top 20% (p ≤ 0.20), standing in for "about any cash"
     in a $333+ contest. A sharp field's top 20% is harder than the Millionaire's, so this proxy is generous.
  3. **FP #1 against R0 #1:** the z difference, and how often they are the same lineup. In W2–4 the book's #1 was the
     plain #1 every week.
  4. **PROPS PAIR against R0 PAIR**, and each row's own-contest finish percentile in every ladder-file contest.

## 4. Weeks and validity
- **Prospective from W5.** W2–4 are printed apart as the in-sample baseline, from the P3 replay
  (`~/rehearsals/p3-replay-20261007T172856Z`). They are never pooled into a decision.
- **A week is valid for D1** when ENTERED is P3's byte-identical rebuild and PROPS_MILP built twin-identical (P3's
  determinism rule). The Millionaire field must load behind `moneygate_score`'s reconcile gate (its receipt must cover
  the week).
  - D2 needs the same. FP #1 needs MEAN_MILP valid; a void MEAN_MILP voids only FP #1's lines.
  - An invalid week is recorded with its reason and does not count.
- **The same lineup:** when PROPS #1 is R0 #1's lineup, d1_w = 0 exactly, and the week counts. Likewise d2_w = 0 when
  MIXED is R0 PAIR's lineups.
  - At a look, if D1's lineups were the same in more than 80% of its valid weeks, D1 reads DEAD LEVER (the vacuity
    check). Likewise for D2.

## 5. The rule (fixed now)
- **Looks:** W8 (with at least 4 valid weeks), W12 and W18 (the season's end).
  - Fixed looks limit the inflation from looking every week. With three looks it is modest, and it is disclosed here.
  - If W8 has fewer than 4 valid weeks, the first look waits for the fourth.
- **At each look, for each of D1 and D2:** the mean of d_w over the valid prospective weeks. Its interval is the
  two-sided 90% t interval: each side is a one-sided 95% bound, with P1's t and n − 1 degrees of freedom.
  - **Lower bound > 0:** "the props row is the better [single ticket | second ticket]".
  - **Upper bound < 0:** "the book's row is the better [single ticket | second ticket]".
  - **Otherwise:** "no difference shown". DEAD LEVER (§4) is read first.
- **A reading is advice.** The operator decides what goes on a ticket. A later look can change an earlier reading;
  each look is reported, and the season's is the last.
- **Before W8 the record is descriptive only.**
  - Each Monday's line prints every d_w plainly.
  - A W6 or W7 ticket's rows are his choice, on this record and the W2–4 replay. One week is never read as a verdict.

## 6. Power (filled in from the W2–4 baseline after this DRAFT is committed)
- The sd of d1_w and d2_w over W2–4 (in-sample, disclosed). Then the margin t(0.95, n − 1) × sd / √n at n = 4, 8 and 14
  weeks, for that sd and for 0.5 and 1.0.
- What it can show is stated now, before any number: only a large, steady difference reads at W8. A difference of the
  W2–4 size would need every prospective week to agree with it.

## 7. Smoke, census and integrity (before the freeze)
- **The reader:** `scripts/s60_record.py`, with its tests. It runs behind the reconcile gate, as P1's reader does.
- **The W4 mechanics smoke:** the whole path on W4's P3 replay books and W4's tables. W4 is in-sample and already
  examined (§1), so its values may print. It is never counted.
- **The outcome-blind identity census:** from the books alone, how often PROPS #1 is R0 #1's lineup, MIXED is R0
  PAIR's, and FP #1 is R0 #1's.
  - It runs on the W2–4 replay now, and on W5's books once P3 builds them (Sunday, before the standings load).
  - It reads lineups only, never points.
- **At the freeze:** the shas of the reader, its tests, `p1_record.py` and `moneygate_score.py`.

## 8. What a reading can do
- **"The props row is the better ...":** a candidate for his big-contest tickets.
  - Entering it needs a production step that builds PROPS_MILP's top rows before lock and pins them to the ticket
    contest.
  - That is a new step inside the last hour before lock. It enters only after Friday's rehearsal runs that exact step
    (study 57's §4).
- **Otherwise:** the head deal stands; the book's top rows go on the tickets.

## 9. Order
1. This DRAFT.
2. The power table (§6) from the W2–4 baseline.
3. The reader, its tests, the W4 smoke and the identity census.
4. The freeze, before Monday's W5 standings load.
5. The laptop's ack.
6. Each Monday, the record, which the laptop re-runs.
7. The looks at W8, W12 and W18.
