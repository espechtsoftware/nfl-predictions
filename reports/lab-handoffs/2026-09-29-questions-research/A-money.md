# Theme A (A1–A5), F4, H2 — money, contest classes, payouts (2026-09-29)

Analyst: research subagent, read-only. Scripts and intermediate CSVs: `scratchpad/q/A/` (`roi_private.py`, `analyze.py`,
`analyze2.py`, `ladders_2026_w1w3.json`, `field_lines.csv`, `lines_at_ranks.csv`, `book_ranks.csv`, `entry_buckets.csv`,
`ticket_buckets.csv`, `milly_pct.csv`, `analysis_out2.md`, `analysis_out3.md`). No dollar figures below; contest classes are
named by field size and ticket multiple. The operator's own figures appear only as ROI %, counts and multiples.

**Read first: `reports/2026-09-29-winners-study-and-consistency.md` (branch `origin/review/winners-study-20260929`).** It
answers A1/A2 at scale (36 historical slates, real 2026 ladders, per-contest field-strength offsets). This note verifies
its ladder/field figures from `contest_entries`, fills what it leaves open (A3, A4, F4/A5 per class, the operator's own
ROI by class), and marks agreement/disagreement.

## Information time of every input

| input | time | used for |
|---|---|---|
| `nfl_raw.contest_entries` (60 contests, 1,485,591 rows, W1–3) | realized (post-settlement standings) | field lines, entry-count lifts, placing our rows |
| DK public contest API payout ladders (fetched today for all 60 contest ids; `A/ladders_2026_w1w3.json`) | contest metadata, fixed pre-lock | payouts per rank, break-even rates |
| Our entered books' scores: W1/W2 from the operator's entry-history export (Points), W3 from `~/week3-sunday/postmortem/lineup_by_lineup.csv` | realized | where our books sat |
| W3 top-mean counterfactual: top 144 of `cands_scored.pkl` by `sel_mean` (reproduces the post-mortem: mean 151.2, best 202.4) | selection pre-lock, scores realized | the mean-track form placed in every W3 contest |
| Panel ratios (laptop 16:54 HANDOFF; winners study §3.2, §4.1) | historical panel, sampled field | Week-4 form transfer (an assumption, flagged) |
| Operator entry history (2020-09 → 2026-09-20; 1,164 entries) + W3 from the ladders | realized | lifetime / 2026 ROI by class (percent only) |

---

## A4 first, because everything else rests on it: why `payout` is NULL and how to fill it

**Cause (verified in code and data).** `src/nfl_dfs/ingest/ownership_import.py:205-217` fills `payout` from a `Winnings` or
`Prize` column of the DK standings CSV and `payout_raw` from the same column as text. DraftKings' full-standings export
carries no such column (the W2 post-mortem §1 notes "the standings exports carry no payout column"), so `payout_raw` is
the empty string on all 1,485,591 rows (never NULL; `payout` is NULL on all of them). This is a wrong assumption in the
importer, not missing data in a subset — a Data-deficiency-log row is warranted.

**Fill (light, exact, already done once outside the repo).** DK's public contest endpoint
(`https://api.draftkings.com/contests/v1/contests/<id>?format=json`, the one `scripts/dk_contest_details.py` on the
week3-readiness worktree calls) still serves the complete `payoutSummary` for *completed* contests: I fetched all 60
2026 contest ids today with zero failures, and in every one the tier sum equals `totalPayouts` exactly (ratio 1.000).
Payout per row = the tier holding `rank`, with DK's tie rule (tied entries split the sum of the prizes of the positions
they occupy). The winners study did precisely this (`reports/lab-handoffs/2026-09-29-winners-study/02_fetch_ladders.py`,
`03_payouts.py`; "the computed payouts match DraftKings' stated prize pool in every contest"), but the result lives in a
private data directory, not the warehouse. What is missing is durable: (1) a `nfl_raw.contest_payout_ladders` table
(contest_id, min_position, max_position, value, entry_fee, total_payouts, maximum_entries, fetched_at) written at
capture time by `dk_contest_details.py`; (2) a view `contest_entry_payouts` joining `contest_entries.rank` to the ladder
with tie-splitting; (3) the importer's `payout`/`payout_raw` left NULL/empty honestly (or removed). Then ROI per contest
is computable for every user in the field, every week, and Q9 stops being guesswork. How long DK keeps serving
completed contests' ladders is unknown (W1's still served 16 days after settlement) — fetch on capture day.

**Verification of lines against the ladders (three corrections to the reports).** Cash line = lowest score inside the
ladder's paid places: W1 Millionaire 165.46 at place 173,275 (matches the settlement report); W2 Millionaire **135.5**
at place 38,825 (the W2 post-mortem says 138); W3 Millionaire **146.4** at place 37,425 (the W3 post-mortem's 149.5 is
the score at place ~32,000). Our W3 entered book had 18 of 144 rows above the true cash line (12.5%), not 15 (10.4%).
These are small and do not change any verdict.

---

## H2. Which payout tables exist and what is missing

| source | contests | status |
|---|---|---|
| `~/week3-sunday/postmortem/contest-details-smoke.json` | all 45 W3 contests (full ladders, Completed) | exists, local only |
| `~/week4-sunday/contest-details-main-20260928.json` | 18 W4 main-slate contests (Upcoming; ladders fixed) | exists, local only |
| `~/week4-sunday/contest-details-thu-mon-196186394.json` | 1 W4 Thu–Mon single-entry (17 tiers, 21% paid) | exists |
| `A/ladders_2026_w1w3.json` (fetched today) | all 60 W1–W3 contests incl. the 3 W1 and 12 W2 ones that had no file | exists in scratch (nondurable) |
| warehouse table / view | none | **missing** — the durable gap |
| pre-2026 contests | none (R13) | missing; DK serves completed contests' ladders but the historical contest ids are not in the warehouse (`contest_ownership` has 1,258 contests 2022–25 — their ids could be tried) |

Ladder shapes that matter (multiples of the entry fee): Millionaire — 23–34 tiers, 20.8–23.1% paid, min-cash 1.5×,
place 1,000 → 5×, place 100 → 20×, place 10 → 250×, first 50,000×; **36.4% of the pool is first place, 44.5% the top 10,
only 31.5% goes to places 10,001–37,425**. FFWC 5,000-qualifier — 9 tiers, 5.2% paid, first 3,889×, places 71–260 get 1×
(fee back). Supersats — one tier: 25 tickets of 80× (2,378 fields), 25 of 20× (594 fields), 2 of 80× (190 fields).
Single-ticket satellites — 402/1 at 342×, 148/1 at 125×, 79/1 at 66.6×, 72/1 at 61.7×, 11/1 at 10× (pool ratio 0.909;
all others 0.841–0.859).

---

## A1. Per class: the field mean, the lines as multiples of it, where our books sat, and the Week-4 form

Realized fields, W1–3. "x" = multiple of that contest's field mean. Our book placed = every row of the entered book
hypothetically entered in every contest of the class that week (ties split per DK). Source tables: `A/analysis_out2.md`
T1–T3, `A/analysis_out3.md` T4b.

### A1a. The lines

| class (2026 contests) | weeks | field mean (W1/W2/W3) | field vs same-week Millionaire | cash line ×mean | ticket/win line ×mean | % paid |
|---|---|---|---|---|---|---|
| 1 Millionaire 162k–832k (150-max) | 1,2,3 | 142.1 / 115.5 / 128.5 | 1.00 | 1.16 / 1.17 / 1.14 | top-1000 1.61/1.60/1.50; top-100 1.72/1.76/1.62; winner 1.93/2.01/1.87 | 20.9–23.1 |
| 2 Large GPP 83k–159k (20/150-max) | 1,2 | 142.2 / 118.5 | 1.00–1.03 | 1.15 / 1.16 | winner 1.86 / 1.99 | 22.0–24.1 |
| 3 Mid GPP single/5-max 9.5k–24k | 2 | 113.8–119.6 | 0.99–1.04 | 1.17 | winner 1.82–1.96 | 21.0–25.2 |
| 4 FFWC qualifier 5,000 (260 paid, 1 ticket) | 1,3 | 147.2 / 135.0 | 1.04 / 1.05 | 1.31 (place 260) | first 1.77 / 1.66 | 5.2 (ticket 0.02) |
| 5 Supersat 2,378 / 25 tickets (20-max) | 2,3 | 114.9 / 130.9 | 0.99 / 1.02 | = ticket | 1.55 / 1.48 | 1.05 |
| 6 Supersat 594 / 25 tickets (17-max) | 2,3 | 118.8 / 133.1 | 1.03 / 1.04 | = ticket | 1.39 / 1.31 | 4.21 |
| 7 Supersat 190 / 2 tickets (5-max) | 3 | 134.1 | 1.04 | = ticket | 1.42 | 1.05 |
| 8 Satellite 402 / 1 ticket (12-max) | 3 | 138.9 | 1.08 | = ticket | 1.46 | 0.25 |
| 9 Satellites 59–148 / 1–4 tickets (2–4-max; wildcats, FFWC sats, 68/2) | 2,3 | 123.2 / 135.7 | 1.06–1.07 | = ticket | 1.39 / 1.46 | 0.7–4.9 |
| 10 Satellite 11 / 1 ticket (single) | 3 | 134.1 (19 contests) | 1.04 | = ticket | 1.27 (range 1.13–1.44) | 9.09 |

Field strength agrees with the winners study §6: satellite and qualifier fields score 4–11 points above the same-week
Millionaire at the mean (402-entry satellites +10.4, 11-entry +5.6, 190-entry +5.7, 594-entry +4.7, FFWC +5.3–6.6);
the 2,378 supersats and the single-entry GPPs are Millionaire-strength or weaker. **Every satellite ticket sits at
1.27–1.55× the field mean; every GPP cash line at 1.14–1.17×.**

### A1b. Where our books sat

| class | book (week) | book mean ×field | share of rows over cash line vs field rate | share over ticket line vs field rate | mean payout multiple per entry (ROI) |
|---|---|---|---|---|---|
| 1 Millionaire | entered W1 / W2 / W3 | **1.02 / 0.91 / 0.94** | 22.5% (1.05×) / 8.3% (0.37×) / 12.5% (0.54×) | 0 / 0 / 0 at top-1000 | 0.37 / 0.13 / 0.22 (−63% / −87% / −78%) |
| 1 Millionaire | W3 top-mean-144 counterfactual | **1.18** | 56.3% (2.43×) | top-1000 2.1% (3.4×) | 1.28 (+28%) |
| 2 Large GPP | entered W1 (Play-Action) / W2 (Flea) | 1.02 / 0.89 | 21% / 7.2% (0.30×) | – | −60% / −88% |
| 3 Mid GPP | entered W2 | 0.90 | 10.7% (0.45×) | – | −81% |
| 4 FFWC 5,000 | entered W1 / W3; top-mean W3 | 0.98 / 0.89; 1.12 | 1.3% (0.24×) / 0.7% (0.13×); 16.0% (3.1×) | 0 / 0; 0 | −99% / −99%; −82% (the cash is fee-back; the ticket is first place) |
| 5 Supersat 2,378/25 | entered W2 / W3; top-mean W3 | 0.91 / 0.92; **1.16** | – | 0 / 0 (field 1.05%); **2.31% (2.2×)** | −100% / −100%; **+85%** |
| 6 Supersat 594/25 | entered W2 / W3; top-mean W3 | 0.88 / 0.91; 1.14 | – | 0 / 1.39% (0.33×); **18.3% (4.3×)** | −100% / −72%; **+266%** |
| 7 Supersat 190/2 | entered W3; top-mean W3 | 0.90; 1.13 | – | 0.06% (0.05×); **4.86% (4.6×)** | −95%; **+289%** |
| 8 Satellite 402/1 | entered W3; top-mean W3 | 0.87; 1.09 | – | 0; 0.93% (3.7×) | −100%; +217% |
| 9 Satellites 59–148 | entered W2 / W3; top-mean W3 | 0.85 / 0.89; 1.11 | – | 0 / 0; 3.94% (3.1×) | −100% / −100%; +162% |
| 10 Satellite 11/1 | entered W3 (actual: 1 of 19 won); top-mean W3 | 0.90; 1.13 | – | 3.95% placed (0.43×) [actual 5.3%]; 25.7% (2.8×) [post-mortem: 17 of 19 won] | −61% placed [actual −47%]; +157% |

Reading: the entered books sat at **0.85–0.94× the field mean in every class in W2–W3** (W1 1.02×), cleared no ticket
line at the field's rate anywhere, and returned −72% to −100% in every satellite class. The same W3 pool selected by
projected mean sits at **1.09–1.18×** and clears every ticket line at 2.2–4.6× the field's rate. This is the same
finding as the post-mortem's §6.1 and the winners study §3.1 (−0.46/−0.47 sd), now per class and in money terms.

### A1c. Break-even as a multiple of the field mean (our spread kept)

Adding a uniform shift to every row of the book until the mean payout equals the fee (`A/analysis_out2.md` T3):

| class | book mean needed ×field mean (W2 book / W3 book) | points to add to the W3 entered book |
|---|---|---|
| Millionaire | 1.16 / 1.12 | +23 |
| Large / mid GPP | 1.14 / – | (+27–30 on the W2 book) |
| FFWC 5,000 | – / 1.20 (1.28 on W1's) | +42 |
| Supersat 2,378/25 | 1.17 / 1.05 | +17 |
| Supersat 594/25 | 1.03 / **1.00** | +13 |
| Supersat 190/2 | – / 1.01 | +14 |
| Satellite 402/1 | – / 1.04 | +24 |
| Satellites 59–148 | 1.06 / 1.07 | +25 |
| Satellite 11/1 | – / 1.04 | +19 |

So the "1.10–1.19×" in the 09-22 report is the break-even in the **rate** at the line (1 / pool ratio: 1.19× the
field's base rate at pool ratio 0.841–0.85, 1.10× at 0.909 for the 11-entry sats — verified from the ladders). In
**mean-score** terms, with a book whose spread is the field's (sd 24–28), the GPP cash lines need ~1.12–1.16× the field
mean, but the satellites need only **1.00–1.07×** because their tickets pay at deep lines where spread helps. The W3
top-mean book was already above break-even in every satellite class by 6–15 points.

### A1d. The Week-4 form (PMO_X50 main + mean sleeve), if the panel transfers

Two transfers (`A/analysis_out3.md` T4b): the ratio curve from the winners study §3.2 (1.07× at p50, 1.12× at the
cash line, 1.20× p89, 1.33× p95, 1.78× p99) joined to the laptop's 2.22× at p99.8, applied at each contest's line
placed in the same-week Millionaire field (so the satellite fields' extra strength is priced in), versus the winners
study §5.1 (per-contest field-strength offsets, real ladders, 36 slates):

| class | field rate | break-even rate | this note: as armed → P(ticket), ROI | winners study §5.1 as armed | agree? |
|---|---|---|---|---|---|
| Supersat 2,378/25 | 1.05% | 1.25% | 1.50%, **+20%** | 1.68%, **+34%** | yes (sign and order) |
| Supersat 190/2 | 1.05% | 1.25% | 1.66%, **+33%** | 1.70%, **+36%** | yes |
| Supersat 594/25 | 4.21% | 5.0% | 5.72%, +14% | 5.1%, +1% | yes (marginal) |
| Satellite 11/1 | 9.09% | 10.0% | 8.53%, −15% | 7.5%, −25% | yes (below) |
| Satellite 402/1 | 0.25% | 0.29% | 0.54%, +84% | 0.21%, −29% | **no** — p99.75 line in a field +10 points stronger; both reads rest on the panel's far tail (a handful of big weeks) and 3 contests; sign unknown |
| Satellites 59–148 (wildcats etc.) | 0.7–4.9% | 0.8–2.6% | 2.29%, −16% (5 heterogeneous contests pooled) | wildcat 1.94%, +29% | **no** on the wildcats — theirs is per-contest and better; treat as unknown sign |
| FFWC 5,000 | 5.2% (ticket 0.02%) | – | P(cash) 5.3%; ROI ex-first-place −94% | 4.4% cash; "a lottery in a professional field" | yes |
| Millionaire, cash | 22.2% | – | P(cash) 25.0%; ROI ex-top-10 **−32%** | 25.9% | yes |
| Large / mid GPP, cash | 23.1–23.6% | – | 24.2–25.5%; ROI ex-top-10 −24 to −26% | 22.9–29.0% | yes |

With the blended-ownership term (winners study §4.1, λ 0.20, not yet live) every class moves up ~0.2–0.4 in ratio:
2,378 supersats 1.74% (+39%), 190 supersats 1.92% (+54%), 594s 6.7% (+34%), 11-entry sats 10.2% (≈0%). MEAN and EMAX
(the W1–3 forms) sit below break-even everywhere: 0.87–0.99% in the 1.05% supersats (−21 to −31%), 5.9–6.5% in the
11-entry sats (−35 to −41%).

---

## A2. Which classes clear the rake at our measured quality, and the weekly expectation

**At the Weeks 1–3 quality (EMAX form): none.** Realized: −72% to −100% in every satellite class in W2–W3, −63/−87/−78%
in the Millionaire; the panel agrees (0.82× at p89, 1.02× at p99 → −14 to −31% per entry).

**At the armed Week-4 form (PMO_X50), if the panel transfers — two independent transfers agree on:**

| class | entries per contest (max) | P(ticket) per entry | ticket multiple | EV per entry | weekly expectation |
|---|---|---|---|---|---|
| Supersat 2,378 / 25 tickets | 20 | 1.5–1.7% | 80× | **+20% to +34%** | at 20 rows/contest: 0.30–0.34 tickets per contest; P(no ticket in a contest) ≈ 70–75% if rows were independent, higher because they are not |
| Supersat 190 / 2 tickets | 5 | 1.66–1.70% | 80× | **+33% to +36%** | at 5 rows: 0.085 tickets per contest; 12 contests → ~1 ticket per week, P(zero) ≈ 40–55% |
| Supersat 594 / 25 tickets | 17 | 5.1–5.7% | 20× | **+1% to +14%** (marginal) | at 17 rows: 0.9–1.0 tickets per contest |
| Millionaire (one seat) | 1 | cash 25–26% | 1.5× at the floor | −32% ex-top-10; jackpot-dependent | see A3 |
| everything else (11-entry sats, 402 sats, FFWC 5,000, wildcats) | – | below or unknown | – | −15% to −94%, or sign unknown | do not fund on evidence |

The winners study §5.2 simulated the whole week: the W3 mix with the armed book wins **18% of weeks**, median week −87%;
dropping the FFWC qualifier, the 11-entry and the 402 satellites (mix A2) raises it to 24% of weeks, median −75%, good
week +288%. That is the honest "weekly expectation": positive EV per entry in two or three classes, delivered as roughly
one winning week in four to five, because the book's rows move together (its weekly mean swings ±13 points).

**What is not known:** the panel's field is sampled from Millionaire ownership, not the real satellites' lineups; the
deep-line ratios (p99+) come from a few big weeks in 36 slates; field-strength offsets are from 1–3 contests each; the
live PMO_X50 form has zero settled weeks. The first live read is Monday 10-05.

---

## A3. What one Millionaire seat is worth

One row drawn at random from each book, placed in that week's Millionaire (realized field, DK tie rule;
`A/analysis_out3.md` T5b):

| book | P(cash) | P(top 10,000) | P(top 1,000) | P(top 100) | P(top 10) | E[payout] ×fee | median finish (pct of field) | best finish |
|---|---|---|---|---|---|---|---|---|
| entered W1 (80 rows) | 22.5% | 0 | 0 | 0 | 0 | 0.37 | 44th pct | place 25,426 |
| entered W2 (97) | 8.3% | 0 | 0 | 0 | 0 | 0.13 | 65th | 12,378 |
| entered W3 (144) | 12.5% | 4.2% | 0 | 0 | 0 | 0.22 | 62nd | 4,131 |
| **pooled entered W1–3 (321)** | **13.7%** | **1.9%** | **0** | **0** | **0** | **0.23 (ROI −77%)** | | |
| W3 top-mean-144 | 56.3% | 26.4% | 2.1% | 0 | 0 | 1.28 (+28%) | 20th | 271 |
| Week-4 form, panel transfer (as armed) | 25.9% | 8.1% | 1.2% | 0.14% | 0.014% | 1.44 total, **0.60 excluding the top 10** | | |
| Week-4 form + blended ownership | 32.6% | 9.4% | 1.4% | 0.14% | 0.014% | 1.56 total, 0.72 ex-top-10 | | |

Reading. From the books actually entered, a seat was worth **0.23× its fee** with no row in any week inside the top
10,000 except in W3 (4%), and none ever inside the top 1,000 (field rate 0.6%). With the Week-4 form, if the panel
holds, the seat's value from places 11 and below is **0.6–0.7× the fee** (P(cash) 26–33%, min-cash 1.5×, place 1,000 at
5×), and its total value is carried by a **1-in-7,300 shot at the top 10** (44.5% of the pool), which the panel prices
at 1.8–2.2× the field's rate and which is measured on a handful of weeks. **It is a lottery ticket.** Size: one seat;
its expected loss ex-jackpot is 30–40% of the fee, and it buys the only exposure to the 36%-of-pool first prize and to
the top-100 line (1.6–1.8× the field mean) that no pool we have built has reached (0 of 68 historical, 0 of 3 live).
The W3 top-mean book would have paid 1.28× per seat on that slate — one week, hindsight selection form.

---

## A5 and F4. Per-entry rate by entry count, per class (2026, all 60 contests)

Lift = the bucket's cash/ticket rate ÷ the class's rate (1.0 = flat). Ticket = first place in single-ticket
satellites and the FFWC qualifier, all paid places in multi-ticket supersats, cash in the GPPs (`A/analysis_out3.md`
T7b; per-contest detail `A/entry_buckets.csv`).

| class | 1 entry | 2–3 | 4–20 | 21–149 | 150 | verdict |
|---|---|---|---|---|---|---|
| Millionaire (cash lift; top-1% lift) | 0.80; 0.64 | 0.84; 0.69 | 0.98; 1.01 | 1.08; 1.15 | **1.19; 1.36** (W1 1.27, W2 1.88, W3 1.40) | volume users win per entry |
| Large GPP (Play-Action W1, Flea W2) | 0.74; 0.47 | 0.81; 0.45 | 1.04; 0.71 | 1.13; 0.97 | **1.28; 1.39** | volume |
| Mid GPP single / 5-max Nickel | 1.02 | 0.79 | 0.91 | – | – | **flat** (5-max: 4–20 bucket 1.03 at top-1%) |
| FFWC qualifier 5,000 (cash lift) | 0.76 | 1.04 | 1.00 | 1.08 | 1.01 | **flat** (150-entry users are 57% of the field; both tickets went to a 128/150 user and a 4–20 user) |
| Supersat 2,378 / 25 (ticket lift) | **0.23** | 0.51 | **1.16** | – | – | volume: 116 of 125 tickets to 4–20-entry users |
| Supersat 594 / 25 | **0.39** | 1.07 | 1.10 | – | – | volume users ahead; 2–3 flat |
| Supersat 190 / 2 | **2.01** (9 of 24 tickets from 18.6% of the field) | 0.39 | 0.90 | – | – | singles ahead — n = 24 tickets, noisy |
| Satellite 402 / 1 | 0 | 8.5 (3 of 3 tickets) | 0 | – | – | n = 3; uninformative |
| Satellites 59–148 | 1.01 | 1.35 | 0 | – | – | n = 9; roughly flat |
| Satellite 11 / 1 | single by rule | | | | | process only |

Answer to A5: the per-entry rate is **flat or favours small counts** in the 5-max Nickel, the FFWC qualifier, the
190-entry 5-max supersats, the 402 and 59–148 satellites (small n), and the 11-entry satellites (by rule). Volume
clearly wins per entry in the Millionaire, the large GPPs and the **20-max and 17-max supersats** — there the
single-entry users are weak (mean 119 vs 126 for 4–20-entry users; ticket rate 0.24% vs 1.22%), so the W2 post-mortem's
"flat in the 20-max supersats" holds only *within* the 4–20 bucket, not against singles. **The refinement that matters:
in every class the entry count only multiplies the user's own rate.** The flat classes are flat because their entrants
are homogeneous (the 402 and 11-entry fields are the strongest we face, +6–10 points), not because they reward process
more. What decides funding is our rate against the class's break-even (A1d/A2), not whether the class is "flat".

---

## The operator's own record (percent, counts, multiples only; from the entry-history exports, W3 from the ladders)

| | entries | cash rate | ROI |
|---|---|---|---|
| lifetime 2020–2026 W2 | 1,164 | 8.9% | **−83.5%** |
| 2026 W1 / W2 / W3 | 80 / 97 / 204 | 22.5% / 3.1% / 0.5% | −64.9% / −89.4% / −91.6% |
| 2026 to date | 381 | | **−78.9%** (stake share by week 45% / 28% / 27%) |

By class (lifetime): Millionaire-size −64% (265 entries, cash 20%, best multiple 5×); 1k–100k GPPs −65% (96); 5k–40k
FFWC-style qualifiers **−96% over 623 entries — more than half of lifetime volume**; sub-1,000 satellites −100% (16);
supersats −100% (69, 66 of them in 2026); 11-entry satellites −47% (19, W3 only). By field size: 200k+ −49%; 40k–200k
−69%; 5k–40k −92%; 1k–5k −97%; 101–1k −49% (one 25× ticket in 2021); 12–100 −100%. By payout shape: >25% paid −34%;
10–25% −64%; 2–10% −96%; <2% −100%. These reproduce the 09-22 report's figures (−48.7% at 200k+, −34.7% at >25% paid,
−100% at <2%). Every class is negative lifetime and in 2026; the loss is smallest where the payout is flattest and the
field largest.

---

## Where this note agrees and disagrees with the winners study (2026-09-29)

Agree, verified independently from `contest_entries` and the ladders: every field rate in its §5.1 (1.05%, 4.2%, 1.27%,
0.25%, 9.1%, 5.2%, 22–25%); every break-even rate (1/80, 1/20, 1/66.6, 1/341.8, 1/10); the field-strength ordering in
§6 (satellites +5–11 points above the Millionaire, 2,378 supersats and single-entry GPPs at or below it); its §3.1
placement of our books (mine: W1 +0.10 sd, W2 −0.40 sd vs the Millionaire and −0.51 vs the Flea, W3 −0.33 vs the
Millionaire and −0.47 vs the satellites entered); its sign for the 2,378 and 190 supersats (above break-even), the 594s
(about even) and the 11-entry sats and FFWC qualifier (below).
Disagree or unresolved: the 402-entry satellites (mine +84%, theirs −29%) and the wildcats (mine −16% pooled with four
other small contests, theirs +29%) — both estimates sit on the panel's far tail and 1–3 contests; I would fund neither
on evidence. I also add three things it does not contain: the finish distribution of a Millionaire seat (A3), the
per-entry lifts by class (F4/A5), and the operator's own ROI by class.

---

## Immediate actions (this week, no new model)

1. **Fund only the 2,378- and 190-entry supersats (and, if wanted, the 594s) with the armed book; drop the 11-entry
   satellites, the 402 satellites and the FFWC 5,000-qualifier.** Evidence: both transfers put the 2,378/190 classes at
   +20–36% per entry and the others at −15% to −94% or unknown sign; lifetime the qualifier class is −96% over 623
   entries. Confidence: moderate on the sign for 2,378/190 (two transfers, but one underlying 36-slate panel with a
   sampled field, zero live weeks); high that the 11-entry sats and the qualifier are below break-even.
2. **One Millionaire seat, treated as a lottery ticket** (A3: 0.6–0.7× the fee ex-jackpot even under the favourable
   transfer; 0.23× realized from the W1–3 books). Confidence high.
3. **Enter the mean-track / PMO_X50 form, not EMAX.** The W3 pool selected by mean sat at 1.09–1.18× every field and
   cleared every ticket line at 2.2–4.6× the field's rate while the entered EMAX book cleared none (W1 +23, W3 +31 per
   row; panel 0.82× vs 1.22× at p89). Confidence high on direction, magnitude unmeasured live.
4. **Make payouts computable in the warehouse:** run `dk_contest_details.py` on capture day for every entered contest,
   load the ladders to a `contest_payout_ladders` table, add the rank→tier view with tie-splitting, and log the
   importer's `Winnings`/`Prize` assumption in the Data-deficiency log. The winners study's `02_fetch_ladders.py` /
   `03_payouts.py` are the working reference. Confidence high (mechanical; all 60 ladders fetch today and sum to the
   stated pools).
5. **Correct the recorded cash lines** in the W2/W3 post-mortems (135.5 and 146.4, from the ladders' paid places; W3
   book 18/144 above cash, not 15). Confidence high; no verdict changes.
6. **Deal each contest's rows spread across the optimizer sequence** (winners study §4.2: fewer empty weeks at every
   line in all three seasons, expected hits unchanged; layout only). Confidence moderate (historical, sampled field).
7. **Monday scoreboard: report per-class ROI from the ladder join** and the book's share over each class's line vs the
   field rate (the stable quantity), so Week 4 becomes the first live read of A2. Confidence high.

Unknowns that bound everything above: the real satellite fields' lineups (never sampled in the panel), the deep-line
ratios beyond p99, this week's field strengths, correlation of our rows within a week (the panel says the whole book
sits below the field's mean in half of weeks as armed, 28% with the ownership term), and whether DK keeps serving
ladders for completed contests beyond a few weeks.
