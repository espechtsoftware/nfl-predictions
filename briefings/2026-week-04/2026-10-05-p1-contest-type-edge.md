# P1: where are we +EV? Contest-type edge, the power to detect one, and a stake rule (2026-10-04 night)

Written for the operator, with the reviewer's checks. Approved-plan item P1 (operator 10-04: "Lets plan on all of
that"), led with the power analysis as the reviewer required.

- **Sources:** read-only. The full payout ladders (contest-details, all four weeks); our entered books' settled results
  (the DK entry history, settled 10-04); and the fields (`contest_entries` W1–3, the W4 standings).
- **Units:** multiples of fees, rates and percentiles only. Dollar tables are private (`~/private/p1/`).
- **Scope:** no alternative selection was built or scored. That is the money gate's job
  (`reports/2026-10-04-week5-money-gate-design.md`).
- **Scripts and CSVs:** session scratch `p1/`.

## The answer in plain words

1. **Money results cannot prove an edge within a season, in ANY contest type.** At our entry counts, telling 1.00×
   from 1.15× (80% power) needs:

   | Contest type | Weeks needed |
   |---|---|
   | Satellites and supersats | about 170–1,200 |
   | The whole Week-4 satellite plan | about 840 |
   | Large GPPs | 10,000–25,000 |
   | The Millionaire and the FFWC qualifier | about 0.3–3 million |

   **The season has 14 weeks left.** The smallest true edge 14 weeks could confirm is about 1.6–2.4× in satellites,
   5–7× in GPPs and 24–71× in the Millionaire.
2. **Even a real edge usually shows a losing season in top-heavy contests.** If the true multiple is 1.15 over 14
   weeks, the season still comes in below 1.0× with these probabilities:

   | Contest type | Chance of a losing season |
   |---|---|
   | The Millionaire (2 entries a week) | 93% |
   | The FFWC qualifier | 99% |
   | Large GPPs | 82% |
   | Supersats and 11-entry satellites | 25–38% |
   | The Week-4 satellite plan | 42% |

   Realized money is weak evidence either way.
3. **We cannot show we beat any contest type.** No type has a lower confidence bound above 1.0×.
4. **We CAN show some 2026 books ran below break-even** (intervals clustered by week, with a common weekly slate shock):

   | Book | Multiple | 95% interval | p vs 1.0× |
   |---|---|---|---|
   | All 2026 entries | **0.26×** | 0.11–0.79 | 0.007 |
   | Satellites and supersats, W2–4 | **0.12×** | 0.03–0.70 | 0.008 |
   | The 594-entry supersats | 0× on 121 entries | 0–0.87 | 0.018 |
   | The large GPPs, W1–2 | 0.25× | 0.08–0.99 | 0.03 |

   **By week:** W1 0.35×, W2 0.11×, W3 0.08×, W4 0.42×. Week 4 alone (the new form) cannot be told apart from
   break-even.
5. **A finish-level yardstick is more efficient, but still says we are below break-even.** It measures how far our rows
   sit above the field rather than money.
   - Our entered rows over W1–4 sat at **−0.15 sd** against the same-week Millionaire field (week means +0.10, −0.41,
     −0.33, +0.03; 95% interval −0.55 to +0.25).
   - **Break-even needs about +0.12 to +0.22 sd** depending on the contest type: a gap of about 8–10 DK points per
     lineup.
   - Satellite fields are stronger than the Millionaire field, so the gap there is larger.
   - Even this yardstick needs about 100–250 weeks to separate 1.0× from 1.15×.
6. **The contests themselves:**
   - **Rake.** The pool is 84–87% of fees almost everywhere. The 11-entry satellites have the lowest rake (break-even
     1.10× the field's cash rate).
   - **One overlay.** The only structural +EV seen was the W2 FFWC 4× supersat (59 of 85 entries with tickets
     guaranteed; pool ratio 1.22).
   - **Ticket value.** Satellite tickets are only spendable in their target contest. At our realized Millionaire
     multiple (0.53×), a seat is worth about half its face to us, which pushes the satellite break-even to about 2.2×
     the field's rate.
7. **History agrees.** The operator's pre-2026 manual entries (983 NFL entries, 6 seasons; a different process)
   returned 0.16× overall; the 5k–40k field class returned 0.075× on 618 entries.

## What this means for the stake decision (evidence; the stake is the operator's)

- **A stake rule driven by a lower confidence bound puts zero on every contest type today, and realized money will not
  turn it on this season.** That follows from point 1, not from bad luck.
- **Any evidence for staking has to come from something with far more power than money results:**
  - the frozen money-gate replay;
  - a historical panel;
  - the finish-level route.
- **What the data support right now:** the system's entered books have run well below break-even across 2026, with the
  Week-4 new form not yet distinguishable either way. Nothing here shows an edge in any contest type.
- **What the data do NOT say:** that an edge is impossible. The power is simply too low to see one, or its absence, in
  money within a season.

## Tables

### Payout ladders (fee multiples; one row per structure)

| Type | Field | Paid % | Cash-line pctile | Pool ratio | First × | Min-cash × | Ticket/cash | Break-even (× field rate) |
|---|---|---|---|---|---|---|---|---|
| Millionaire (W2–4) | 162k–173k | 22.5–23.1 | 76.9–77.5 | 0.850–0.868 | 50,000 | 1.5 | cash | multi-tier |
| Millionaire (W1) | 832k | 20.8 | 79.2 | 0.841 | 200,000 | 1.6 | cash | multi-tier |
| Large GPP | 83k–159k | 22–24 | 76–78 | 0.841 | 10,000–13,333 | 1.6–1.67 | cash | multi-tier |
| FFWC qualifier | 5,000 | 5.2 | 94.8 | 0.850 | seat | 1.0 | seat + cash | multi-tier |
| Supersat 25× / 2,378 | 2,378 | 1.05 | 98.9 | 0.841 | 80 | 80 | ticket | 1.19 |
| Supersat 25× / 594 | 594 | 4.2 | 95.8 | 0.842 | 20 | 20 | ticket | 1.19 |
| Supersat 25× / 118 (W4) | 118 | 21.2 | 78.8 | 0.848 | 4 | 4 | ticket | 1.18 |
| Satellite 11-entry | 11 | 9.1 | 90.9 | 0.909 | 10 | 10 | ticket | 1.10 |
| Satellite MEGA (380–402) | ~390 | 0.25 | 99.7 | 0.85–0.90 | 342 | 342 | ticket | 1.11–1.18 |
| FFWC 4× supersat (W2 overlay) | 59 of 85 | 6.8 | 93.2 | **1.22** | 18 | 18 | ticket | **0.82** |

Full table: `ladders_2026.csv`, `ladder_structures_2026.csv`, `rank_to_tier_2026.csv` (scratch).

### Realized by type, 2026 W1–4 (535 entries, 86 contests, 25 cashes)

| Type | Entries (lineups) | Hits | Our rate / field rate (ratio) | Multiple (95% CI) | Mean finish pctile |
|---|---|---|---|---|---|
| Millionaire | 61 (61) | 16 | 26.2% / 21.0% (1.25) | 0.53 (model 0.27–4.7) | 43 |
| Large GPP (W1–2) | 43 | 6 | 14.0 / 23.1 (0.60) | 0.25 (model 0.08–0.99) | 59 |
| Supersat 25× / 2,378 | 172 (151) | 0 | 0 / 1.05 | 0 (0–1.95) | 58 |
| Supersat 25× / 594 | 121 (94) | 0 | 0 / 4.2 | 0 (model 0–0.87) | 60 |
| Supersat 25× / 118 (W4) | 6 (3) | 2 | 33 / 21 | 1.33 (0.03–7.4) | 51 |
| Satellite 11-entry | 19 | 1 | 5.3 / 9.1 (0.58) | 0.53 (0.01–2.9) | 60 |
| **All supersats** | 372 (272) | 2 | (0.19) | **0.16** (model 0.02–0.70) | 60 |
| **All 2026** | 535 (409) | 25 | 4.7 / 7.0 (0.67) | **0.26** (model 0.11–0.79) | 58 |

**Finish percentile:** 0 = first, 50 = the field average, so 58–60 is worse than the average lineup.

**Method notes:**
- Repeated lineups are deflated by a design effect (entries ÷ unique lineups).
- "Model" intervals simulate each week's exact contests, entries and lineup sharing with a common weekly slate shock.
  This is the honest unit.

### Power (weeks to separate 1.00× from 1.15×, 80% power, 5% two-sided)

| Type (current plan) | Weeks (measured week correlation) | Smallest edge 14 weeks can confirm |
|---|---|---|
| Satellite 11-entry | 224 | 1.60× |
| Supersat 594 | 276–418 | 1.67–1.82× |
| Supersat 2,378 | 640 | 2.01× |
| Week-4 satellite plan | 836 | 2.16× |
| Large GPP | 25,272 | 7.4× |
| Millionaire (2 / 57 entries) | 3.05M / 321k | 71× / 24× |

**Model behind it:**
- A row's latent score is μ + a slate shock + row noise. The total sd (0.95) and the week correlation (0.062) were
  measured from all W1–4 entered rows placed in the same-week Millionaire field.
- μ is calibrated per type so that the expected multiple is exactly 1.00 or 1.15.
- Contests, entries and lineup sharing are each week's actual plan.

**A Monte Carlo check agrees:** a 14-week test at a true 1.15× rejects only 5–8% of the time, about its false-alarm
rate.

**Caveats:**
- Tickets are valued at face (an upper bound on their worth to us).
- W1–3 used the old form, W4 the new.
- Ties and self-competition are ignored.
- The week correlation comes from 4 weeks; the conclusion holds even if weeks are independent.
- Contest 196305080's ladder was rebuilt from the entry history.

## Robustness (reviewer's request, run 2026-10-05 early)

The question: does "below break-even" survive a larger week effect or a larger variance? The realized-row p-values were
re-run for week correlations (ICC) of 0.062 (measured), 0.15 and 0.25, each with total sd ×0.8, ×1.0 and ×1.2. The
test's size was also checked by simulating seasons at a true 1.0× (4,000 each).

| Row | Observed | p at ICC 0.062 (sd ×0.8 / 1.0 / 1.2) | p at ICC 0.15 | p at ICC 0.25 | Verdict |
|---|---|---|---|---|---|
| Satellites + supersats, W2–4 | 0.12× | 0.002 / 0.007 / 0.011 | 0.014 / 0.030 / 0.047 | 0.041 / 0.076 / 0.107 | **Below break-even up to ICC 0.15; borderline at 0.25** |
| The 594-entry supersats | 0× | 0.017 / 0.017 / 0.016 | about 0.038 | about 0.073 | Below up to ICC 0.15; borderline at 0.25 |
| All 2026 | 0.26× | 0.00004 / 0.006 / 0.20 | 0.003 / 0.037 / 0.28 | 0.013 / 0.088 / 0.35 | **Not robust** (fails at sd ×1.2 and at ICC 0.25) |
| Large GPPs, W1–2 | 0.25× | 0.0007 / 0.032 / 0.28 | 0.008 / 0.081 / … | … | **Not robust** |
| W4 satellites alone | 0.18× | — | 0.22 | 0.31 | Not distinguishable from break-even |

**Size check** (rejection rate at a true 1.0×, 5% level):

| Case | Rejection rate | Reading |
|---|---|---|
| Model correctly specified | 3–5% | Correct |
| True ICC 0.25, test assumes 0.062 | 13–20% | Over-rejects |
| All-2026 row with 20% more variance | 36–48% | Badly over-rejects (Millionaire/GPP skew) |

So the all-2026 and GPP p-values are not trustworthy beyond the measured parameters.

**Ticket discount, sensitivity only** (the primary keeps tickets at face): valuing satellite tickets at our measured
Millionaire multiple (0.53×) moves the W2–4 satellite multiple from 0.12× to 0.07×, and the break-even rate from 1.17×
to 2.2× the field's.

**The three sentences for the operator** (reviewer's framing):
1. "We cannot show an edge in any contest type, and within a season we never could have: a true 15% edge would take
   hundreds of weeks to see in money."
2. "What we CAN see is that the 2026 satellite books ran below break-even (0.12×). That holds unless the week-to-week
   effect is much larger than measured. The all-2026 figure (0.26×) is not robust to a larger week effect."
3. "The finish-level measure, which is far more powerful, puts our rows about 0.15 sd below the Millionaire field, when
   break-even needs about +0.12 to +0.22. That gap, not luck, is the main story."
