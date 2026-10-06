# The calibrated field (study list item 40): the harness's sampled field with the real lineups' structure (2026-10-06)

The field audit (`reports/2026-10-06-field-audit-sampled-vs-real.md`) found that the harness's sampled fields rank the
levers like the real Millionaire fields (18 of 18 contrast-weeks agree in sign), but run 3–6 DK points easier at the
very top, so the harness's absolute chances are optimistic. This note measures why, builds a sampler that fixes most of
the structure, and checks it on the top lines. Aggregates only; the private inputs and scripts stay under
`~/private/field-calib/`.

## What the real fields do that the sampler does not
The real Weeks 2–4 Millionaire lineups (about 490,000; our entries removed; 0.1–1.1% of lineups with a name the frame
could not map left out) against `l02_field_sampler.sample_field` drawn from the same week's real ownership:

| Per lineup | real W2 / W3 / W4 | l02 (sampled) |
|---|---|---|
| the QB's WR / TE teammates: 0 / 1 / 2 / 3 | .17/.56/.26/.02, .17/.52/.30/.02, .15/.52/.31/.01 | about .23 / .68 / .09 / .00 |
| a bring-back (an opponent RB / WR / TE) | .44 / .41 / .45 | .23–.25 |
| an RB from the QB's team | .19 / .17 / .17 | .11–.12 |
| players from the QB's game (QB included, DST not) | 2.83 / 2.83 / 2.89 | 2.23–2.25 |
| salary used | $49,871 / $49,885 / $49,880 | about $49,550 |

The real field stacks much harder: three times as many lineups pair the QB with two or more of his receivers, almost
twice as many run it back, and they spend about $330 more of the cap. Correlated lineups have fatter top tails, which is
why the sampled top end is easier.

## The calibrated sampler (`experiments/l02b_field_sampler.py`, lab `production/field-calib-20261006` @ `b21edaf`)
- `sample_field_v2`: l02's sampler (IPF to the target ownership, the roster shape, the $50,000 cap) plus the structure:
  it draws the number of the QB's WR / TE teammates, places them (WR slots, then TE, then FLEX), adds an opponent in
  the FLEX on 30% of stacked lineups, a QB-team RB on 7.5% of lineups, and draws the salary floor from $49,500–50,000.
- **Fitted on the structure only, never on scores.** The draw shares were set so the REALIZED rates match the real ones
  once the free slots' chance teammates are counted; the top lines below were looked at only after the shares were set.
- l02 is untouched (its sha is pinned by l09, `4863754b…`); v2 is opt-in and imports l02's draw.
- sha256: `experiments/l02b_field_sampler.py` `fadf9cfe…`; `tests/test_l02b_field_sampler.py` `1ee7a780…` (2 tests:
  valid lineups on an 8-game synthetic slate; the ownership error within 1.5× l02's; more QB + 2 stacks and bring-backs
  than l02; l02's sha unchanged).

**Its structure** (30,000 lineups per week): the teammates .16 / .52–.54 / .29–.30 / .02, bring-backs .42–.43, a QB-team
RB .18, players from the QB's game 2.83–2.84, salary $49,864–49,866. The ownership fit is as good or better than l02's
(the sum of absolute ownership errors .297 / .294 / .262 against .303 / .355 / .307).

## The validation: the top lines (DK points; the mean of three 200,000-lineup draws, seeds 11 / 12 / 13)

| Week | | mean | p99 | p99.9 | the top-95-of-150k line |
|---|---|---|---|---|---|
| W2 | real | 115.5 | 179.8 | 199.6 | 202.9 |
| | l02 | 115.1 | 175.7 | 195.4 | 198.8 (−4.1) |
| | **v2** | 115.9 | 177.0 | 196.3 | **199.5 (−3.4)** |
| W3 | real | 128.5 | 188.2 | 205.6 | 208.0 |
| | l02 | 126.9 | 182.3 | 199.5 | 202.9 (−5.1) |
| | **v2** | 128.2 | 186.1 | 202.8 | **205.2 (−2.8)** |
| W4 | real | 118.3 | 182.8 | 205.6 | 208.6 |
| | l02 | 117.6 | 180.5 | 201.8 | 205.6 (−3.0) |
| | **v2** | 118.1 | 181.5 | 202.7 | **206.4 (−2.2)** |

- The means are within 0.4 points of the real ones in every week (l02 within 1.6).
- At the top-95 line, v2 closes about a third of the gap (12.2 points over the three weeks → 8.4); at the 99th
  percentile, about half (12.3 → 6.2).

## Reading
1. **v2 is the better field model and becomes the harness's decision field from study 46**, with l02 run beside it as
   exploratory continuity with studies 24–45. It does not change any earlier verdict: the audit showed l02's fields
   order the levers as the real fields do.
2. **What is left (2–3 points at the very top)** is not the QB stack, the bring-back or the salary: those now match. The
   likely rest is that real entrants choose better combinations than ownership-weighted draws do (which players go
   together, beyond the QB's game). A "sharp share" v3, a fraction of the field built by an optimizer on public
   projections, is the obvious next step; it is not built.
3. **The harness's absolute chances stay somewhat optimistic** under v2, less so than under l02. Effect sizes are
   compared between arms on the same field, so this matters for the levels quoted to the operator, not for the
   direction of a verdict.
