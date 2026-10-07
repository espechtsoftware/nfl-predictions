# Preregistration: study 60, the rows for a big-contest ticket at the CASH line -- the book's top rows vs the plain FP and props top rows, on the real Millionaire field (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07 (17:30 CDT)** by the reviewer, before any Week-5 outcome. Week 5 locks Sunday 10-11, and its
standings load Monday 10-12.
- **The DRAFT and what came before the freeze:**
  - DRAFT `746719ca`.
  - The reader, its tests, the W2–4 identity census and the W2–4 full-path baseline (which filled §6): `29567af2`.
  - Two DRAFT changes, both before any W5 outcome and disclosed where they sit: §3's positions by P1's rule, and §5's
    short look.
  - **At the freeze, from the laptop's answers (10-07):**
    - P3 builds its arms MONDAY after settlement, from the union's pinned pre-lock inputs, at `~/moneygate/p3/wWW`. So
      the W5 identity census runs then, before the record is read (§7).
    - R0 is the union's book BEFORE Sunday's vetting, the same stage as every arm (§2).
- **Frozen:** the reader, its tests and the code it reads (§7, "At the freeze").
- **The laptop:** acks, and re-runs the W2–4 baseline.

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
  - **R0 is the union's book BEFORE Sunday's vetting**, the same stage as MEAN_MILP and PROPS_MILP.
    - Vetting replaces an OUT/IR player or moves a flagged row back. It applies to whichever rows are entered, so the
      arms are compared at one stage.
    - A player scratched after T-70 scores 0 in whichever row holds him, as P3 scores.
    - When vetting changed the lineup entered at rank 1 or 2, the Monday record says so in words (the laptop, from the
      published upload). It never changes d.
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
     `~/private/cash-line/cash-lines-wWW.csv`, checked against its `.sha256`), each row gets a position among that
     contest's real entrants by P1's rule: 1 + the entries (every real entry of ours removed) strictly above it.
     - A hit is a position at or inside the contest's line: `cash500_last_position` for the roles big and gpp,
       `seat_last_position` for sat.
     - (Changed in the DRAFT, before any W5 outcome: the first text placed rows with `moneygate_score.place` and its
       tie split. The position needs no prize ladder, and `place`'s ladder refuses a tier that mixes cash and tickets.)
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
- **Looks:** W8, W12 and W18 (the season's end), each over the valid prospective weeks up to it.
  - Fixed looks limit the inflation from looking every week. With three looks it is modest, and it is disclosed here.
  - A look with fewer than 4 valid weeks reads "too few valid weeks", and the next look comes as scheduled.
  - (Changed in the DRAFT, before any W5 outcome: the first text let a short W8 look wait for the fourth week. The
    reader was written with the simpler rule before the W2–4 baseline ran.)
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

## 6. Power (filled in from the W2–4 baseline after the DRAFT `746719ca`; §2–§5 unchanged by it)
- **What it can show was stated before any number:** only a large, steady difference reads at W8. A difference of the
  W2–4 size would need every prospective week to agree with it.
- **The W2–4 baseline** (in-sample, the P3 replay; the reader's full path; never pooled):

  | | W2 | W3 | W4 | Mean | sd |
  |---|---|---|---|---|---|
  | d1 = z(PROPS #1) − z(R0 #1) | +1.043 | +0.401 | +0.222 | +0.555 | 0.431 |
  | d2 = z(MIXED) − z(R0 PAIR) | −0.926 | +0.401 | −0.529 | −0.352 | 0.681 |

  - D1 agrees with the outside reviewer's field shares (§1).
  - D2 was negative in W2 and W4, because the book's #2 row finished well in those weeks.
- **The interval's half-width,** t(0.95, n − 1) × sd / √n:

  | sd | 4 weeks | 8 weeks | 14 weeks |
  |---|---|---|---|
  | 0.431 (d1, W2–4) | 0.508 | 0.289 | 0.204 |
  | 0.681 (d2, W2–4) | 0.802 | 0.456 | 0.322 |
  | 0.5 | 0.588 | 0.335 | 0.237 |
  | 1.0 | 1.177 | 0.670 | 0.473 |

- **What it means:**
  - Four prospective weeks with W2–4's d1 mean and sd would read at W8 "the props row is the better single ticket", by
    a hair (+0.555 − 0.508 = +0.047).
  - A smaller or noisier difference waits for W12 or W18, or never reads.
  - D2 needs a much larger difference.

## 7. Smoke, census and integrity (before the freeze)
- **The reader:** `scripts/s60_record.py`, with its tests. It runs behind the reconcile gate, as P1's reader does.
- **The W4 mechanics smoke:** the whole path on W4's P3 replay books and W4's tables. W4 is in-sample and already
  examined (§1), so its values may print. It is never counted.
- **The outcome-blind identity census:** from the books alone, how often PROPS #1 is R0 #1's lineup, MIXED is R0
  PAIR's, and FP #1 is R0 #1's.
  - It runs on the W2–4 replay now. For W5 it runs on P3's books at `~/moneygate/p3/w05`, once P3 builds them on
    Monday.
    - P3 builds them from the union's pinned pre-lock inputs, so they hold no outcome.
    - The census runs before the record is read.
  - It reads lineups only, never points.
- **At the freeze** (production `review/s60-cash-line-20261008`; the reader and tests as committed at `29567af2`):
  - **`scripts/s60_record.py` (the reader), sha256 `76fa50fe1e0a13e6d1fe7c5a410d257600f8c6d54347d258d87dc22fc24b3b14`**;
  - `tests/test_s60_record.py`, sha256 `2da8b9a06e8859f15f86e2d09ff598a92083a2385776489c9ef7f50943c1e421`;
  - `scripts/p1_record.py` (P1's frozen reader; its `latent_z`), sha256
    `ea142610e30320b03d4b4d66270abea571088950df3855d48d90ff895267bbb8`, asserted by the reader;
  - `scripts/moneygate_score.py` (the week tables and the reconcile gate), sha256
    `dd8ff1f7015ada7ebe307ffd599be39166736ecb38dd64ad67e0acb9fa741e56`. Its own receipt pins it per reconcile.
  - `scripts/p3_arms.sh` (the books), sha256 `41fb7db32a57c3823c8c9efab2f40e6d9c536374958bc3fcab3a935aa6adf3bd`. Each
    week's arms.json carries its build shas.
  - **A repair** of the reader after the freeze names its new sha in an amendment before the next record it reads.
- **Done in the DRAFT (2026-10-07 evening):**
  - **The identity census on the W2–4 replay** (outcome-blind; lineups only). PROPS #1 differs from R0 #1, and MIXED
    from R0 PAIR, in all three weeks. FP #1 is R0 #1's lineup in all three, as the outside reviewer found. D1 and D2
    have support.
  - **The full path on W2–4** (the baseline in §6) ran behind the reconcile gate and exited 0.
    - Every ladder-file contest got a position for every row, inside its size.
    - There were no hits at those weeks' deep lines.
    - It is never counted.
  - **The tests:** `tests/test_s60_record.py`, 9 pass. They cover:
    - the frozen constants and the printed level;
    - the same-lineup rule and the MIXED fallback;
    - P3's validity rules;
    - the position and p (P1's, to 1e-12);
    - the look readings;
    - the lines by role;
    - that the census reads no outcome code;
    - one scored synthetic week.

## 8. What a reading can do
- **"The props row is the better ...":** a candidate for his big-contest tickets.
  - Entering it needs a production step that builds PROPS_MILP's top rows before lock and pins them to the ticket
    contest.
  - That is a new step inside the last hour before lock. It enters only after Friday's rehearsal runs that exact step
    (study 57's §4).
- **Otherwise:** the head deal stands; the book's top rows go on the tickets.

## 9. Order
1. The DRAFT (`746719ca`). Done.
2. The power table (§6) from the W2–4 baseline. Done (`29567af2`).
3. The reader, its tests, the W2–4 smoke and the identity census. Done (`29567af2`).
4. The freeze. Done (this text).
5. The laptop's ack, and its re-run of the W2–4 baseline:
   `PYTHONPATH=src python scripts/s60_record.py --weeks 2,3,4 --arms 2=<replay>/w2,3=<replay>/w3,4=<replay>/w4`.
   Expect d1 +1.043 / +0.401 / +0.222 and d2 −0.926 / +0.401 / −0.529.
6. **Each Monday from W5:**
   - P3's arms at `~/moneygate/p3/wWW` (P3's Monday step).
   - `--census` on them.
   - The reconcile covering the week.
   - The record: `--weeks 5,…,W --arms 5=~/moneygate/p3/w05,…`, which the laptop re-runs.
7. The looks at W8, W12 and W18.
