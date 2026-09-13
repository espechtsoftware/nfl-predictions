# Week-1 post-mortem and the 220 problem (2026-09-13, Sunday evening)

Operator's brief: the entered book is topping out around 180; volume will stay low until the system can routinely reach
220+; audit what has been done and find dramatic, non-obvious steps. This report is the audit. Every number below is
either from the frozen ledger or from measurements run tonight (scripts under `/home/erich/week1-sunday/audit/`,
results in `reports/2026-09-13-audit-*.md`).

## 1. What happened today, against what history predicted

| quantity | today (Week 1, 80 unique entries) | historical (72 slates, PREREG-096 bank, same construction) |
|---|---|---|
| best of the entered book | ≈180 (in progress) | K80 mean 183.0; K30 mean 175.5 |
| weeks with best ≥ 200 | 0 | K80 9–13 of 72; K30 6 of 72 |
| weeks with best ≥ 220 | 0 | K80 5 of 72; K30 4 of 72 |

Today is an ordinary draw from the historical distribution. Nothing broke; the system produced what it produces.

## 2. The ledger: every lever tried, and what it moved

Effects are on the best-of-book (points) or the winner-utility proxy; "closed" means preregistered, read, not adopted.

| lever | best measured effect | status |
|---|---|---|
| candidate dose 400→800 (PREREG-047) | +1.2 raw, replicated | adopted |
| dose 800→1600 (PREREG-090, 093, 095) | ≈0 to +0.002 proxy | null / unresolved |
| dose 800→3200 (PREREG-093, 095) | +0.009 / +0.010 proxy, both PASS; 220-supply per slate-bank 0.14→0.50 | **the one monotone lever**; Week-2 candidate |
| retrieval laws: novelty ladder, union e-max, coverage-194/220 (060, 066, 076, 094, 095) | +0.001 to +0.006, never past the family gate | closed |
| within-book orderings (24 shadows: sim mean/q99/P-lines, phenotype, market move, structure, random) | ±1.7 at K30 | none proven |
| learned lineup score, re-sort of the book (LOSO) | +0.6 [−4.5, +6.0]; 2024-only | hypothesis |
| learned lineup score as the selector over the pool (PREREG-096) | −2.8 at K30, +0.3 at K80 | **failed**; entry reverted |
| skill-salary floors, generation-time | −0.15 to −1.13 | closed |
| stack depth (QB+3, QB+4) | higher simulated tail, lower realized exceedance | closed (see §3.3) |
| tail line 187/194/200 in the objective | flat | closed |
| generator families (GFlowNet, Gumbel, hierarchical Gumbel, CE, Schaake, TD coupling, role-belief) | all ≤ control on the 107-slate panel | closed |
| dependence models (learned templates, coherent member worlds) | better average dependence, lose the joint tail | closed |
| late swap (tonight, §3.5) | +0.7 at K30, +0.2 at K80; 220-weeks unchanged | not a lever in this form |

Cumulatively: a dozen selectors and a dozen generators, each moving the best-of-book by two points or less. The
ledger's own verdict (Addendum 95) stands: selection is closed for the current simulator and feature set; the live
capture paths are more entries and genuinely new information.

## 3. New measurements tonight

### 3.1 The simulator is calibrated, including at the extreme

The realized *perfect lineup* (optimal lineup on actual points, salary cap, DK roster) averages **267.1** over the 72
slates (min 200, max 331). The simulator's own per-world perfect lineup (same optimisation on simulated draws, 120
sampled worlds per slate, six slates) averages **258** with a q95 of ~290; every realized value fell inside its slate's
simulated range. At the lineup level (57,531 real candidates): realized outcomes exceed the simulator's 99th percentile
0.70% (incumbent law) / 0.97% (corrected-hsim law) of the time; the simulator *over*-predicts P(≥200) by 3× (0.40%
predicted vs 0.13% realized). There is no hidden fat tail the model is missing; if anything it is slightly optimistic.

### 3.2 The selector works, and 220 is still a four-sigma event

Selected lineups (DEMAX K80) reach 220 at 0.10% per lineup versus 0.01% for unselected candidates from the same pool: a
10× enrichment, i.e. the selector is doing real work. But 0.10% × 80 = one 220 lineup per book every ~12 weeks, which is
exactly the historical 5–6 of 72. Realized within-slate lineup s.d. is 24.8 around a mean of 118 for selected lineups;
220 is +4.1 s.d. for a lineup fixed at lock.

### 3.3 Heavier stacks hurt

| QB-stack size | n | simulated q99 | realized ≥ own q99 | realized share ≥ 200 |
|---|---:|---:|---:|---:|
| 2 | 41,074 | 184 | 0.83% | 0.15% |
| 3 | 15,748 | 191 | 0.38% | 0.10% |
| 4 | 673 | 199 | 0.15% | 0.15% |
| 5 | 36 | 207 | 0.00% | 0.00% |

The simulator over-rewards deep stacks; reality does not pay them. The "5-man game stack" idea is closed by this table.

### 3.4 What a real 220+ lineup is made of

Perfect lineups (n = 72): mean 267; **4.2 players at 30+**, 6.6 at 25+, 8.0 at 20+; typical sorted profile
42 / 37 / 33 / 31 / 30 / 28 / 25 / 23 / 17; QB stack size **0.8** (not stacked); 6.7 distinct games, at most ~2.5
players from one game; salary used 49,283. A 220 lineup is roughly 35/30/28/26/25/22/20/18/16: five players at 25+ and
no dud, spread across games. **Who those players are is predictable; when they boom is not**: 84% of perfect-lineup
skill players are top-quartile projections within their position (97% top half), 90% of the 30-point games come from
top-quartile players, and they scored 2.4× their projection. The perfect lineup is a random subset of the top quarter
of the player pool, which is precisely the population our boom candidates already sample.

### 3.5 Late swap does not reach 220

With the early games' realized points known, re-choosing each lineup's late slots (mean 2.9 per lineup) from late-game
players to maximise P(total ≥ 220) under the pre-lock simulator: best-of-book **+0.74 at K30, +0.17 at K80**; 220-weeks
unchanged (4/72 and 5/72); chalk and ceiling late-swap policies are negative (−0.9 to −1.5). Only 13 of 80 lineups are
"alive" (≥120 early points) at 3:00 CT on an average slate. The mid-slate information exists but three late slots cannot
carry a lineup from 130 to 220.

### 3.6 Dose is the one monotone lever on 220 supply

PREREG-093/095 (six banks): candidates ≥220 per slate-bank 0.14 (800) → 0.25 (1600) → 0.50 (3200); pool oracle 195.5 →
199.5 → 203.9; K80 book weeks with a 220+: 0 → 0 → 2 of 72 (bank-averaged); roster hits ≥220 across three banks 5 → 7 →
9. Supply roughly doubles per doubling; book conversion is small but present. The novelty selector adds nothing at 3200.

## 4. The structural conclusion

A lineup fixed at lock scores 220 when five or more of its nine players have a top-decile game the same week. The
players who do that are the top quarter of the pool; which subset booms is noise the simulator reproduces faithfully.
A book of K lineups is K bets on K subsets; the count of subsets that would score 220 in the realized week is tiny
relative to the space, so P(book ≥ 220) grows roughly linearly in K and in the number of independent world-draws the
candidates cover (the dose). No selector, ordering, stack rule, learned score, floor, or dependence model in the ledger
changed that arithmetic, and tonight's measurements say the simulator is not the bottleneck either. **"Routinely 220+"
with 30 entries is not reachable by any tested or newly measured pre-lock method; it is reachable only by volume, by dose
at a much larger scale, or by changing what counts as a win.**

## 5. Dramatic options, ranked by evidence

1. **Dose at scale (6,400 → 12,800 candidates).** The only lever with a monotone effect on 220 supply. Requires
   parallelising the boom stream across Cloud Run tasks (per-world optima are independent; the lev cut-loop stays
   sequential) and a 16 GiB selection step (12.8k × 20k float32 ≈ 1 GB). Expected: 220-weeks at K80 from 2 to perhaps
   4–6 of 72 if the doubling law holds; still ≈ 5–8% of weeks. Cost: one cohort per rung; a Sunday build of 12.8k in
   ~15 min on 36 tasks. **Recommended as the next cohort (PREREG-097: 6,400 rung with the nested-prefix mechanics).**
2. **Change the win condition.** The book reaches 200 in 15–18% of weeks at K80 (8% at K30). Contests where 200
   wins (3-max and single-entry GPPs of 5–20k entries, the FFWC qualifiers) turn the existing machine's strength into
   a realistic weekly outcome; the Millionaire's 230+ bar is a 1-in-15-weeks event even at K80. This is a bankroll
   decision, not a model change, and it is the largest lever available at 30 entries.
3. **Volume.** P(≥220) scales close to linearly in entries; the ledger has always said so. Not available now.
4. **Genuinely new pre-lock information about *when* studs boom** (the only thing that would change §3.4's
   arithmetic): usage/route-participation signals from the Fantasy Points Data Suite and SIS charting are ingested but
   have never been tested as boom-week predictors (they entered as projection features, not as tail predictors). A
   frozen test: does any pre-lock feature predict a top-quartile player's 30+ game beyond the projection? If the
   answer is a clean no (likely), the pre-lock ceiling is proven and the program moves to 1–2. Cheap, informative.
5. **Late swap v2** would need to move 30+ points into three slots; §3.5 says it cannot. Keep the scratch-swap tool;
   do not build further.

Not recommended, with the evidence that closes them: deeper stacks (§3.3); learned selectors (PREREG-096); novelty and
coverage retrieval (060/066/094/095); dependence rewrites (Addenda 112, 115; §3.1 shows the simulator is calibrated).

## 6. Program for Week 2

- Tonight: preregister and launch **PREREG-097** (6,400 rung, three banks, nested D3200/D1600/D800 prefixes, frozen
  GLOBAL_WEMAX_PROXY reader, 220-supply as a descriptive secondary; boom stream parallelised if the 3-hour task timeout
  requires it). Lanes are idle; PREREG-095 is closed.
- Monday: standings capture; settle the entered 80, the paid P_MIX/K90 books, the learned/union/re-sort shadows, and the
  T-70 sheet orderings; record which candidate file was entered.
- Tuesday: the boom-week predictability test (option 4) on the 72 slates: top-quartile players' 30+ games vs every
  pre-lock feature, LOSO; one afternoon of work.
- Wednesday: decision on the win condition (option 2) with the operator, informed by the settled Week-1 shadows and the
  097 read; the Week-2 paid dose (3200 DEMAX is the candidate: two passing cohorts against 800).
- Runbook fixes already recorded (memo §4): reserved-entry export fill in the Sunday script; withdrawals not assumed;
  T-70 salary pull after the 10:30 CT inactives; scratch-swap tool live from 11:00 CT through the late window.
