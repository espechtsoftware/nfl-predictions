# Handover state and proposed direction — for second-opinion review

Date: 2026-08-18
Author: Claude (Opus 5), acting as operator-directed orchestrator since
2026-08-18 ~11:50 CDT
Audience: an external reviewer asked to second-guess the direction below

**Read this as an argument, not a report.** It states what was inherited, what I
changed, where I propose to go, and — in §7.2 — the four places I think I am most
likely to be wrong. The operator wants that fourth section pressure-tested.

---

## 1. Provenance: who did what

Until today, implementation was driven by a different model (Codex/Sol) with me
acting only as an external reviewer producing documents in `reports/`. That model
hit a usage limit. The operator asked me to take over orchestration and "work
autonomously toward increasing the scores."

Everything before commit `ef36db5` is the other model's work. Commits `eed48f8`,
`46cc871`, `0ac819d` are mine.

I want to be explicit that **the inherited work is of high quality.** The
governance discipline is real, it has caught genuine defects, and on the two
occasions the other model contradicted my analysis it was correct both times
(§6). My disagreements below are about *allocation of effort*, not rigor.

---

## 2. Before you open `reports/` — what to ignore

**This matters more than anything else in this document.** `reports/` holds
**397 markdown files**. Roughly **200 are governance** (84 protocols, 49 repairs,
43 reconciliations, 24 amendments, 3 invalidations) and the large majority of the
rest describe **experiments that failed and mechanisms that are closed.** They are
retained deliberately — the discipline here is to record negative results rather
than delete them — but they do **not** describe how the system works.

> **Do not infer current behaviour from `reports/` unless a document explicitly
> says a mechanism was adopted. Almost nothing is adopted.**

### 2.1 Closed — present in `reports/`, not in production

- **Candidate generation:** GFlowNet; the **entire Gumbel family** (plain,
  fixed-budget, hierarchical); Schaake shuffle; cross-entropy (CE) worlds;
  epistemic (EPI) candidates; forest-learned dependence templates; Chronos
  marginals; raw candidate-budget scaling (multiple 2->4)
- **ATLAS matched-diversity MVP** — closed permanently today (§5.1)
- **Marginal channel (~12 arms, all failed):** Fantasy Points route share (both
  marginal and rank variants), advanced prior-season, coverage fit, same-season
  coverage, route shape, QB shell, defense PROE
- **SIS:** team context, QB line, RB run defense, pass-tail marginal, run-tail
  Boom/Bust, team pass-defense coverage schema, receiver copula calibration
- **Dependence:** TD ledger (all four attempts), G2 QB-Gumbel factor,
  competitive-WR allocation, TE hub follow-up
- **Selection:** reranker, LSE, sharp-LSE, QB-concentration, dollars-objective,
  bagged/bootstrap selection
- **Other:** fast-role / latent role state, overtime prediction, the realized
  late-swap recourse policy

### 2.2 Authoritative sources

| file | what it is |
|---|---|
| `HANDOFF.md` | **The current-state record.** Often days ahead of any report. |
| `README.md` | Design guide with a section-to-code map, plus the data deficiency log |
| `CLAUDE.md` | Project rules and the validation law |
| `src/nfl_dfs/inference/production_policy.py` | The single frozen definition of production behaviour |
| `reports/2026-08-17-external-reviewer-briefing-v2.md` | Fuller orientation than this section |

**If a document and the code disagree, the code wins. If `HANDOFF.md` and a
report disagree, `HANDOFF.md` wins.**

### 2.3 Four traps that have produced wrong conclusions here

1. **Stale constants.** This project corrects its own headline numbers and
   superseded values keep circulating. Known-stale: forensic gaps **3.58/78.99**
   (superseded by 4.06/68.91); recourse **+42.62**; simulated QB->WR **~1.05**
   (pre-`26e73c5`); selector overlap **54.28/80** (different sample width; current
   comparable value 65.69); source row count **72,520** (actual 68,199); and
   **`corr = +0.030`** (a superseded-panel omitted-oracle statistic, not a
   candidate correlation — actual ~0.22). **Search for a later correction before
   relying on any number.**
2. **Endpoint confusion.** *attainable world quality*, *candidate `C`* and
   *selected `S`* are three different quantities. ATLAS's `+10.93` and CBWU-OI's
   `+5.66` are **not** comparable — that confusion is exactly what §5.1 unwinds.
3. **Simulation-law confusion.** Three laws exist — production multinomial (the
   money path), fitted-Dirichlet (older G-series diagnostics), and finite-K +
   SIS-ASOE (Phase S). Results do not transfer between them. See
   `reports/2026-08-16-simulation-law-ledger.md`.
4. **Nested thresholds read as independent.** Counts at 240/230/220/210/200 are
   nested — a slate crossing 220 necessarily crosses 210 and 200 — so "+2/+2/+3"
   may be three distinct slates, not seven improvements. Ask for **distinct slates
   moved**.

### 2.4 A note on recent failures

A reviewer skimming the last two weeks will see a long run of failures and may
conclude the science is collapsing. Mostly it isn't: of the six ATLAS grid
attempts, four were lost to a hard-coded string constant, infrastructure noise
against a zero-retry contract, and build defects. **Distinguish mechanical
failures from scientific ones** — they are recorded with equal ceremony here, and
that is itself part of the process diagnosis in §4.5.

## 3. What the system is, in one paragraph

A DraftKings NFL Classic DFS system. Each week it picks 9 players under a
$50,000 cap and submits **80 lineups** into large-field tournaments. Payouts are
extremely top-heavy, so **the objective is the single best score among the 80** —
not average accuracy. Historical panels: 107 slates (2019, 2021-2025) and a
54-slate sub-panel (2023-2025 Weeks 1-18). Production policy is frozen as
`classic-k1-role12-boom40-poscal-cbwu-v4`.

---

## 4. Inherited state

### 4.1 The forensic frame

Each slate is decomposed by hindsight-optimal solves: **H** (best legal lineup
from the whole player universe), **P** (best from the union of players appearing
in any generated candidate), **C** (best candidate actually generated), **S**
(best entry actually selected).

| gap | mean points |
|---|---:|
| H - P (player support) | 4.06 |
| **P - C (construction)** | **68.91** |
| C - S (selection) | 5.01 |

Construction dominates. Selection is saturated — selected equals pool oracle at
220/230/240.

Two caveats the raw table hides, both established later and both important:

- **H is not the DraftKings-legal optimum.** `_solve_oracle` applies
  `qb_stack_min`/`bring_back_min`, and the corrected run uses the full production
  QB+2/one-bring-back contract. Relaxing to QB+1/no-bring-back is exactly what
  moved P-C from 68.91 to 78.99 — so roughly **10 points of hindsight pool oracle
  sit outside the production stacking rule and no layer of the decomposition
  reports it.**
- **P is a hindsight target.** The exact-P census found P absent from the
  complete five-seed native union on **54 of 54 slates**, with **zero** admission
  losses and a median five swaps to the nearest generated roster. But a perfect
  searcher optimising the *simulated* objective would also miss P.

### 4.2 The one construction mechanism that has ever worked

**CBWU-OI**, at exactly equal candidate budget: mean C `181.07 -> 186.73`
(+5.66), with `>=194/200/210` going `11/8/6 -> 18/14/10` and `>=220/230/240`
**exactly tied at 3/1/0**.

Mechanism: player-pair reach `3,056 -> 4,308` (+41%) and QB-stack-core reach
`118.78 -> 181.09` (+52%), achieved with **worse** player coverage (44 vs 54
slates retaining all nine P players). **Combination breadth, not player breadth.**
It is not in production; promotion requires prospective evidence.

### 4.3 The transfer record

| mechanism | simulated criteria | realized outcome |
|---|---|---|
| Schaake shuffle | passed | rejected |
| Gumbel (plain / fixed-budget / hierarchical) | passed | 26, 20, 23 vs 27/107 |
| Cross-entropy worlds | promising | 26 vs 27/107 |
| Fast-role / latent role | passed | 11 vs 17/107 |

Six mechanisms cleared simulated gates and failed the real one.

### 4.4 Surrogate quality (measured 2026-08-17)

Candidate-level Spearman vs realized score: **0.216** (`p_line`), **0.237**
(simulated mean), **0.223** (q99); within-slate 0.156/0.195/0.166 with bootstrap
intervals above zero; held-out ROC AUC **0.6255**. Weak but real.

The selected-book tail calibration audit found the shape error that matters:

| threshold | realized | expected | |
|---|---:|---:|---|
| 194 | 8 | 10.26 | over-predicted |
| **210** | **6** | **2.76** | **under-predicted 2.2x** |

Independently, the dependence diagnostic found an **under-coupled QB hub** with
over-produced high multiplicity — which produces exactly that shape. Two methods,
same error.

### 4.5 Process condition

`reports/` holds 389 documents: 202 governance (protocols, amendments, repairs,
reconciliations, invalidations) against 56 results — a **3.6:1 ratio**, sustained
at ~50 documents/day. Since the forensic completed on 2026-08-14: **489 commits,
zero production adoptions.**

The ATLAS matched-diversity grid was attempted **six times** (repair2-repair6) and
produced **zero scoreable population**: a CBC SIGKILL at 4 GiB, a hard-coded
output-prefix constant that failed all 54 cells, a 16 GiB memory failure plus six
platform errors, an identity-tiebreak defect, and a failed dual canary. Only two
of six taught anything about the model.

---

## 5. What I did on taking over

### 5.1 Closed and dispositioned ATLAS (`eed48f8`)

ATLAS repair6 reached `repair6-closed-no-scoreable-population` at 07:20Z. I then
found something that had not been stated: **ATLAS's two completed "passes" are
near-tautological.**

It ranks worlds by `roster_slot_upper_bound` — documented in its own source as
relaxing "salary, team, minimum-games, stack, rb-anticorrelation." Both completed
experiments then measured **exact attainable legal optimum**. The ranking key is a
relaxation of the evaluation metric; the transfer's own report records a
proxy/exact rank correlation of **0.6064** with 27.06 points of slack.

Sorting by a 0.61-correlated proxy of X and then measuring X passes under nearly
any implementation. The `+12.88` and `+10.93` establish that the sort key sorts.
**ATLAS has never measured C, S, or a realized score.** I retired both results as
adoption evidence and closed the MVP permanently.

I proposed one replacement test: swap **only** the boom-family world ranking at
`engine.py:1067` from `rd.sum(axis=0)` (raw total slate points, ignoring roster
structure) to the roster-shaped bound; `N_BOOM=40` both arms so budget parity is
exact by construction; reuse the 270 already-validated world artifacts; measure
C. Ordinary lineup MILPs, no interaction variables — a fraction of the compute
the MVP needed. **Prior predeclared negative** (ATLAS pair reach 0.9520 and
dominant-game 0.9080 move opposite to CBWU-OI's +41%/+52%); a null closes the
family permanently.

### 5.2 Rebuilt the DST D0 frame (`eed48f8`)

The handoff had gated this on the heavy chain being free; ATLAS closing released
it. Rebuilt `team_defense_week` from clean SQL: **13 -> 55 columns**, 6,302 rows,
3,151 games, 2014-2025. Gates 1, 2, 4 pass with receipts. Independent live PIT
check: zero L4/L16 window overruns, zero negative support across all rows.
`test_leakage.py` + `test_feature_sql.py`: 101 passed, 1 skipped.

**Gate 3 blocked.** Two problems: 2022/2023/2024 carry **zero** authoritative DST
rows (1,630 team-games), and where the source exists it disagrees with the
reconstruction on a stable **~2.3% of panel rows**. I tested the two obvious
causes and both fail — tier boundaries refuted (mean distance to a DK tier edge
1.62 mismatched vs 1.66 matched), excluded non-DST points explain only 3 of 41.
Logged to the README deficiency table.

### 5.3 Deployed the contest-fills collector (`46cc871`)

`dk_contest_fills` had a CLI subcommand and a job function but **no Cloud Run job
and no scheduler**. Entries, fill rate, prize pool and overlay are live-only; once
a contest settles the pre-lock trajectory is gone. Created the job plus two
schedulers, verified end-to-end through a forced scheduler run.

### 5.4 Found gate 5 is the wrong gate (`0ac819d`)

Before writing the odds/weather common-lock selectors I checked what they would
select from. `nfl_raw.weather` holds **0 rows and can never be backfilled** — its
collector is a 4-day-forward forecast job. `odds_snapshots` begins **2026-07-31**
with no season/week keys. Both historical panels predate all available data, so
these covariates **cannot enter any historical DST fit**.

---

## 6. My error record, for calibration

The reviewer should weight my judgment accordingly. In the last four days I have
been wrong, in public, five times:

1. **Quoted a stale forensic figure.** Used 3.58/78.99 in a briefing handed to an
   external reviewer; the exact-stack addendum had superseded them with
   4.06/68.91 three days earlier. The external reviewer caught it.
2. **Overstated the surrogate claim.** Built a "the simulator is an invalid
   instrument" argument on `corr = +0.030`, which was a 54-observation
   *omitted-oracle* statistic from a **superseded** panel, not a candidate-level
   correlation. The other model corrected me; true value is ~0.22. Retracted.
3. **Filed a false defect.** Claimed a bootstrap/disjoint-half ordering flip was
   an implementation bug; it was a designed sample-width difference (5,000-world
   halves vs 25,000-world halves). Caught it myself before shipping.
4. **Refuted my own power objection.** Claimed a p230 gate was underpowered on
   per-slate counts; the folds actually pool ~540k world-observations. The other
   model was right.
5. **Shipped a broken job spec today.** Created the contest-fills Cloud Run job
   without `command: ['nfl-dfs']`; the container failed to exec. Found by diffing
   against `ingest-odds`.

Pattern: **I generalise from a single statistic too fast.** Every error above is
that. The direction in §7 should be read with that in mind.

---

## 7. Proposed direction — and where to attack it

### 7.1 The reasoning chain

1. The forensic says construction holds 68.91 points.
2. But P is a hindsight target, candidate-level simulated/realized correlation is
   ~0.22, and six mechanisms have passed simulated gates and failed real ones.
3. Therefore **"improve construction, measured in simulated coverage" is
   optimising a weakly-correlated proxy** — and that is precisely the loop that
   has produced 489 commits and zero adoptions.
4. So I would prioritise work whose value **does not depend on trusting the
   surrogate.**

Two categories qualify:

**(a) Structural corrections — wrong regardless of simulator quality.**

- **DST has zero variance across all 30,000 worlds.** `live_lineups.py:334` sets
  `draw_idx = -1`, production ships `DST_CORR_DRAWS=""`, `engine.py:636` confirms
  those rows "get their static projection in every sim." One of nine roster slots
  contributes no variance to any lineup's tail. This is a fact about the code, not
  a claim about the model.
- **`H` hides strategy-constraint loss**, and the ~10-point shift from relaxing
  QB+2/BB1 to QB+1/BB0 suggests the hidden quantity is large.

**(b) Fixing the instrument rather than using it.** The tail is miscalibrated in
a specific, measured, mechanistically-explained way: 194 over, 210 under by 2.2x,
matching an under-coupled QB hub found independently. Repairing that improves
every future measurement, including all the arms that have already failed.

**Deprioritised:** further construction sweeps, ATLAS variants, another selector
arm. Selection is saturated; construction mechanisms keep passing simulated gates
and failing real ones.

**Independently and on a hard deadline:** Week 1 operational readiness. Data not
collected during the season is permanently lost, and it is the only source of
prospective evidence — which is the *only* thing that can promote CBWU-OI.

### 7.2 The four places I am most likely to be wrong

**(1) DST may not be worth what I think.** It is the cheapest roster slot, real
DST scores are genuinely low-variance, and DK DST scoring is dominated by
points-allowed bands. A booming DST is largely a world where the *opposing
offense collapsed* — so adding DST dependence will **suppress** tail coverage for
lineups stacking that offense while creating new DST-driven states. The net
effect on a max-of-80 objective is genuinely ambiguous, and I have asserted it is
positive without measuring it. **This is my weakest link and the one I most want
challenged.**

**(2) I may be over-indexing on the transfer record.** Six failures is
suggestive, but they are six *different* mechanisms, and "the surrogate is weak"
is not the only explanation — they may simply have been six bad ideas. If so,
construction work is still the right lane and I am steering away from the
largest measured gap for a bad reason.

**(3) Retiring the ATLAS evidence may be too harsh.** A 0.6064 rank correlation
is not 1.0. The proxy relaxes real constraints, and 27 points of slack is
substantial. A defender could argue the transfer measured something non-trivial.
I think the circularity is disqualifying for *adoption* evidence; I am less sure
it is disqualifying for *prioritisation*.

**(4) My gate-3 recommendation may be motivated reasoning.** I recommend
accepting a bounded ~2.3% mismatch and fitting on components, which conveniently
unblocks the lane I want to work on. The stricter reading — that an unexplained
2.3% disagreement plus three seasons of zero coverage means the reconstruction is
not trustworthy — is defensible and I may be discounting it because it is
inconvenient.

### 7.3 Open decisions the operator has not yet made

1. **D0 gate 3** — bounded-mismatch acceptance vs per-row forensics that still
   cannot cover 2022-2024.
2. **Coherent-market-state** — releasing it unblocks a watcher parked 29 hours in
   a zero-cost printf/sleep loop; its historical-score stage reads outcomes and is
   lease-gated.
3. **The minimal ATLAS C test** — worth one cheap run, or close the family now on
   the six-grid record?

---

## 8. What would be most useful from a second opinion

In priority order:

1. **Attack §7.2(1).** Is a correlated DST event model actually worth building
   for a max-of-80 objective, given that DST booms anti-correlate with the
   offensive stacks that drive big lineups?
2. **Adjudicate §7.2(2).** Weak surrogate, or six bad ideas? These imply opposite
   research programmes.
3. **Is the tail-calibration lane real work or a detour?** Fixing 194-over /
   210-under is appealing because it is upstream — but nobody has shown that a
   better-calibrated tail produces a better *book*.
4. **Is the process diagnosis right?** 3.6:1 governance-to-results with zero
   adoptions in 489 commits looks pathological to me. It may instead be the
   normal cost of a discipline that has demonstrably prevented false adoptions.
