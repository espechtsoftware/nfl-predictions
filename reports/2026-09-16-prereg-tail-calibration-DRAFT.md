# DRAFT preregistration — tail calibration of the world model by walk-forward world reweighting (for operator sign-off)

**Status: DRAFT, not frozen. Nothing in it has been run. It becomes PREREG-101 in the lab when the operator signs off;
the numbers in §2 are then recomputed from all three 097 banks and frozen with the file.** Author: the agent operating
both teams. Date 2026-09-16.

## 1. Why this, and why it is allowed

The synthesis of the week (`reports/2026-09-16-findings-since-week1-synthesis.md` §2.3) found that every objective
reaching further into the simulator's tail than expected-max does worse on realized outcomes, that admission, vendor
data and learned scores reshuffle the same uninformative ordering, and that the simulator's extreme tail is
over-predicted — mildly at the pool level and strongly at the book level. From the PREREG-097 bank-970 shards
(D3200_DEMAX, 65 slates):

| level | simulated share ≥ 194 | realized share ≥ 194 | simulated share ≥ 220 | realized share ≥ 220 | realized / simulated at 220 |
|---|---:|---:|---:|---:|---:|
| pool maximum (best candidate of 3,200) | 0.743 | 0.692 | 0.269 | 0.169 | 0.63 |
| book maximum (best of the selected 80) | 0.395 | 0.292 | 0.087 | 0.031 | 0.36 |

The selector's own book is 2.8× too optimistic about 220 while the pool it chose from is 1.6× too optimistic: selection
amplifies the miscalibration, which is what a selector does when the worlds it leans on are the least informative
ones. The lever is therefore not another selector but the *weight* the selector gives to each simulated world.

Addendum 95 closed selection "for the current simulator and static feature set" and allows a revisit only on an
adopted new dependence model or genuinely new information with evaluation frozen before outcomes are seen. A
walk-forward world reweighting is a change to the simulator's law (how much probability mass its extreme worlds
carry), fitted on seasons strictly before the evaluated one, with the reader frozen here. Lineup-level realized
outcomes of the training seasons are used in the fit; LAB_RULES count those as looks on the training seasons only.

## 2. Construction (to be frozen)

**Pools and worlds.** Experiment 117's construction at the Week-2 dose: one 3,200-solve stream per slate (lev 640 /
boom 2,560) on the generation bank, dual decision matrix (incumbent ⊕ corrected-hsim selection bank, 20,000 worlds,
float32). Identical pools and worlds across arms; only the world weights differ.

**World feature.** For each world j, z_j = the pool maximum in that world (max over the 3,200 candidates of their
simulated score) — the quantity whose realized analogue (the pool oracle) exists once per slate.

**Weights (walk-forward).** For evaluated season s, training slate-banks are every development slate-bank with
season < s from the *same* cohort (2019 and 2021… as available; 2019 must be added to the panel for 2021 to have
training data, so the cohort runs 2019–2024 with 2019 as training-only). Bins on z: (< 187, 187–194, 194–200,
200–210, 210–220, ≥ 220). Weight of bin b = (share of training slate-banks whose realized pool oracle falls in b) /
(share of training worlds whose z falls in b), clipped to [0.2, 2.0], then normalized to mean 1 over the worlds of
each evaluated slate. The clip and the bins are frozen here; nothing is tuned on the evaluated season.

**Arms** (banks 1010 / 1011 / 1012, exact K80):

| arm | selection | role |
|---|---|---|
| `DEMAX` | `select_expected_max` on the unweighted matrix | control (the money path) |
| `DEMAX_WCAL` | greedy E_w[max] under the walk-forward weights (`select_expected_max_weighted` with a single law and per-world weights, or an equivalent weighted-column matrix) | treatment |
| `DEMAX_FLAT10` | the same with the top 10 % of worlds by z removed (weights 0/1) | reference: is any gain just "less tail"? |

**Endpoints.** Primary: paired GLOBAL_WEMAX_PROXY of the weekly K80 maximum, `DEMAX_WCAL − DEMAX`, season-clustered
bootstrap (20,000 draws, seed 47), 2021–2024 (2019 is training-only), family level 1 − 0.05/2 with the reference
contrast; PASS iff the lower bound > 0, every bank ≥ 0, ≤ 1 LOSO negative (PREREG-047 semantics). Secondary and
diagnostic: raw K80 and K20/K40 deltas; threshold events; **retrieval informativeness** — within each slate-bank, the
Spearman correlation and the AUC of the arm's per-candidate objective value (E_w[score] and the weighted P(≥ 194))
against realized candidate points and against realized ≥ 194, control vs treatment; the calibration receipt of the
selected book (simulated vs realized share ≥ 194 / ≥ 220) per arm; the fitted weight table per season.

**Mechanics gate (outcome-blind).** One slate: weights sum to the world count, lie in the clip range, come only from
seasons < s (the training key list is emitted and checked), the control arm reproduces 117's D3200 book roster for
roster on the same bank, exact K80 in every arm, no book rows.

## 3. Consequences (to be frozen)

1. PASS with the retrieval diagnostic improved and the book calibration receipt closer to realized → nominate the
   reweighting for a Week-3 *shadow* book (never the entered book in the same week) and a prospective settlement.
2. PASS with `DEMAX_FLAT10` passing equally → the gain is "less tail", not calibration; adopt the simpler rule as a
   candidate, same shadow path.
3. Not passing → the world model's tail ordering is not repairable by reweighting; the points program's remaining
   levers are dose (supply) and contest choice; record and stop selector/law work on this simulator.

## 4. Cost

Three banks × 72 evaluated slates (plus 2019 training slates: ~17 more per bank) at the 3,200 dose ≈ 3 × 89 × 3.5 h ×
$0.25 ≈ $230, ≈ 8 h on the two lanes after PREREG-099 finishes. Reader and runner are one day of work from the 117
files. Nothing touches Week 2.

## 5. What the operator is asked to decide

- Sign off (or amend) the bins, the clip range and the primary endpoint before any code runs.
- Whether 2019 may be added as training-only data (it is a development season in LAB_RULES; nothing evaluates on it).
- Whether to run after PREREG-099 (lanes are busy until Thursday) or to pre-empt it.
