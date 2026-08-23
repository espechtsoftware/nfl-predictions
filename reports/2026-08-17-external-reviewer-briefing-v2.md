# External reviewer briefing (v2)

**Read this first. It is written for a reviewer with no prior context on this
repository.**

Date: 2026-08-17. Supersedes
`reports/2026-08-15-external-reviewer-briefing.md`, which is now stale in
several material places (§5 dependence numbers, §6a queue, the forensic status
note). Where the two disagree, this document wins.

Purpose: orient an external model to review this codebase productively, and —
equally important — to avoid the very large amount of material describing
mechanisms that were tested and **rejected**.

---

## 1. What the system does, in one paragraph

It builds DraftKings NFL "Classic" daily-fantasy lineups. Each week it picks 9
players under a $50,000 salary cap (QB 1, RB 2, WR 3, TE 1, FLEX 1 from
RB/WR/TE, DST 1) and submits **80 distinct lineups** into large-field
tournaments — typically a ~160,000-entry contest where only the very top scores
win meaningful money. Because payouts are extremely top-heavy, **the objective
is not average accuracy — it is the single best score among the 80 entries.**
That distinction drives every design decision and is the most common thing an
outside reviewer gets wrong.

---

## 2. The single most important instruction: what NOT to read

`reports/` now holds roughly **300 documents**, and the large majority describe
**experiments that failed and mechanisms that are closed.** They are retained
deliberately — the discipline here is to record negative results rather than
delete them — but they do **not** describe how the system works.

**Do not infer current behaviour from `reports/` unless a document explicitly
says a mechanism was adopted.** Almost nothing is adopted.

Rejected or closed mechanism families that appear extensively and are **not** in
production:

- GFlowNet candidate generation; **the entire Gumbel family** (plain,
  fixed-budget, hierarchical game/team/player); Schaake shuffle; cross-entropy
  (CE) worlds; epistemic (EPI) candidates; forest-learned dependence templates;
  Chronos time-series marginals
- **Fast-role / latent role-state wholesale adoption** (11/107 vs 17/107 control)
- Ownership "fade" objectives (`OWN_MODEL=fade`, `milly_fade`)
- Fantasy Points: route share (both marginal and rank channels), advanced
  prior-season, coverage fit, same-season coverage, route shape, QB shell,
  defense PROE
- SIS: team context, QB line, RB run defense, pass-tail marginal, run-tail
  Boom/Bust, team pass-defense coverage schema, receiver copula calibration
- TD ledger (all four attempts), G2 QB-Gumbel factor, competitive-WR allocation,
  TE hub follow-up
- Selector variants: reranker, LSE, sharp-LSE, QB-concentration,
  dollars-objective, bagged/bootstrap selection
- Overtime prediction (closed — see §11.1)
- Raw candidate-budget scaling (multiple 2→4: `tail-first-not-supported`)

**Read these instead** — this is the authoritative set:

| file | what it is |
|---|---|
| `HANDOFF.md` | **The authoritative current-state record.** Read "Current state" first. It is updated continuously and is often days ahead of any report. |
| `README.md` | Full design guide (§0–§14) with a section-to-code map at the top |
| `CLAUDE.md` | Project rules, including the validation law |
| `reports/2026-08-14-final-preseason-forensic-result.md` | The forensic audit — where the score is lost |
| `reports/2026-08-15-exact-p-generator-census-result.md` | **Why** it is lost (§5.1) |
| `reports/2026-08-15-cbwu-oi-construction-diagnostic-result.md` | The first thing that moved it (§5.2) |
| `reports/2026-08-16-simulation-law-ledger.md` | Which simulation law each result was measured under (§7 — read this before comparing any two numbers) |
| `src/nfl_dfs/inference/production_policy.py` | The single frozen definition of production behaviour |
| `src/nfl_dfs/models/featureset.py` | Exactly which features the model uses |

If a document and the code disagree, **the code is authoritative**. If
`HANDOFF.md` and any report disagree, `HANDOFF.md` wins.

---

## 3. Architecture — the pipeline in order

```
nflverse / Odds API / DK salaries / SIS / Fantasy Points   (raw ingest)
        ↓  src/nfl_dfs/ingest/
BigQuery  nfl_raw.*
        ↓  sql/features/*.sql   (run by `nfl-dfs build-features`)
BigQuery  nfl_features.*   → player_week_training / player_week_inference
        ↓  src/nfl_dfs/models/
   [1] LightGBM component models  (targets, carries, yards, TDs, …)
   [2] TabPFN cached marginals    (features.tabpfn_projections)
        ↓  src/nfl_dfs/models/simulate.py + game_sim.py
   [3] Possession simulator → 30,000 correlated worlds
        ↓  src/nfl_dfs/backtest/replay.py  (apply_draw_shape)
   [4] Marginal shaping + per-position calibration + 45/55 market blend
        ↓  src/nfl_dfs/optimizer/
   [5] Candidate generation (MILP, ~250 lineups/slate, tagged by generator)
        ↓
   [6] Selection: greedy world-coverage at line 194 → exactly 80 entries
        ↓  src/nfl_dfs/app/  (FastAPI) → DKEntries CSV
```

### The four channels — essential for making useful suggestions

The most common failure of outside review here is proposing something in a
channel that is already exhausted. **Every proposal must name its channel.**

| channel | what it changes | status |
|---|---|---|
| **Marginal** | a player's own projected distribution | **exhausted** — ~12 arms, all failed |
| **Copula / dependence** | which players boom *together* | mostly closed; one live premise (§7.3) |
| **Generation** | which lineups get built from available players | **where the loss is, and the only place anything has moved** |
| **Selection** | which 80 of ~250 candidates get submitted | **saturated** — selected == pool oracle at 220+ |

**A critical mechanical fact:** TabPFN marginal coverage is **100%**, and the
shaper rank-remaps every player's simulated draws onto that player's cached
TabPFN quantiles. So for covered rows, a feature added to the **LightGBM
component models** changes only the *ranks* (the copula) — it cannot change the
served marginal. A feature added to `scripts/tabpfn_gen/features.txt` changes
the marginal. **These are different experiments on the same feature**, and
conflating them has caused real confusion here.

---

## 4. The forensic result — the frame for everything

Every slate was decomposed into four layers using hindsight-optimal solves:

- **H** — best legal lineup from the complete slate player universe
- **P** — best legal lineup from the union of players appearing in *any*
  generated candidate
- **C** — best candidate actually generated
- **S** — best entry actually selected

| gap | mean points |
|---|---:|
| H − P (player support) | **4.06** |
| **P − C (construction)** | **68.91** |
| C − S (selection) | **5.01** |

At the 210-point threshold the first failing layer is **construction on 44 of 54
slates**, player support on 1, selection on **0**.

> **These are the exact-stack corrected values**
> (`reports/2026-08-15-post-forensic-exact-stack-addendum-result.md`). The
> originally published **3.58 / 78.99** are superseded and still circulate —
> add them to the stale-constant list in §12.4.
>
> **H is not the DraftKings-legal optimum.** `_solve_oracle` in
> `src/nfl_dfs/research/final_forensic.py` applies `qb_stack_min` and
> `bring_back_min`, and the corrected run uses the full production
> **QB+2 / one-bring-back** contract. So H, P, C and S are all *inside* the
> production strategy rules, and the forensic **cannot see tail score excluded
> by the stack mandate itself.** Relaxing that contract to QB+1 / no-bring-back
> is what moved P−C from 68.91 to 78.99 — roughly **10 points of hindsight pool
> oracle sit outside the production stacking rule**, and no layer of the
> decomposition reports it.

**Interpretation, and this should govern the whole review:** the right players
are already in the candidate pool. The generator never assembles them. **The
problem is combinatorial coverage of lineup space** — not player projection, not
player selection, and not the player universe.

Two settled side findings:

- **The $49,000 minimum-salary floor costs nothing.** Removing it gave +0.53
  mean and **zero** new threshold-reaching slates from 187 through 240.
- **Late-swap (recourse) has a large hindsight ceiling** but the realized
  experiment failed: the tail-aware late-decision policy lost, and its naive
  conditional-mean comparator was nonnegative but produced **no new ≥200 week.**
  Do not quote the originally published **+42.62** recourse mean — it was
  superseded by an exact-stack correction. The remaining untested recourse idea
  is choosing the *initial* 80 for the late-game alternatives they preserve
  (§9).

---

## 5. What has been learned since the forensic — the most useful section

### 5.1 The construction gap is a search problem, not an eligibility problem

The exact-P generator census asked *why* P is never built. Across 54 slates:

| loss stage | slates |
|---|---:|
| exact P absent from the complete five-seed native union | **54** |
| exact P generated but removed by admission | **0** |
| invalid retained reconstruction | 0 |

All nine P players were present in the native union on **every** slate. Over a
native union of 500–801 candidates per slate (mean 579.80), the nearest roster
to exact P was a **median five swaps** away.

Put that beside the real-winner assembly finding — the pool's closest candidate
to a known Millionaire winner held **3.46 of nine** winning players against
**3.30 under an exposure-preserving random null.** Two independent measurements
agree: **the generator's proximity to high-scoring rosters is roughly what
undirected sampling would produce.**

**Important caveat that bounds this.** Exact P is a *hindsight* target defined by
realized scores. A perfect searcher optimising the *simulated* objective would
also miss it, because `corr(sim-rank, regret) = +0.030` at the candidate level.
So the census establishes *that the combination was never created* — not that a
pre-lock criterion could have created it. The useful question is narrower:
**does a pre-lock-identifiable region exist whose lineups contain high-actual
rosters more densely than current sampling does?**

### 5.2 CBWU-OI — the first measured construction gain

At **exactly equal candidate budget**, an order-invariant complete-union
admission rule improved the best generated candidate:

| metric | canonical | CBWU-OI |
|---|---:|---:|
| mean weekly C | 181.07 | **186.73** (+5.66) |
| ≥194 / ≥200 / ≥210 | 11 / 8 / 6 | **18 / 14 / 10** |
| ≥220 / ≥230 / ≥240 | 3 / 1 / 0 | **3 / 1 / 0** |

**The mechanism matters more than the score.** Pair reach rose 3,056 → 4,308
(+41%) and QB-stack-core reach 118.78 → 181.09 (+52%), while slates retaining
all nine P players *fell* from 54 to 44.

> **Combination breadth, not player breadth, is the lever.**

**And the caveat that governs interpretation: all gains stop at 220.** The
standing decision law reads 240 → 230 → 220 → 210 → 200 and takes the first
non-zero difference, so the first three thresholds are exact ties. This improves
the *shoulder*; the objective is the *extreme*.

### 5.3 Selection is saturated, and less reproducible on the better pool

Selected equals pool oracle at 220/230/240 — there is no selection headroom at
the tail. Separately, CBWU-OI's pool selects **less stably** under world
resampling: bootstrap pairwise exact-80 overlap `61.13 → 54.58` (−6.55),
disjoint-half `65.69 → 60.87` (−4.81). Better candidates, less reproducible
books.

### 5.4 ATLAS — strong on its own endpoint, and moving breadth the wrong way

ATLAS reranks worlds by attainable legal roster quality. Under the production
law its transfer passed decisively: mean exact attainable world quality
`271.56 → 282.49` (+10.93), improving in **all 270** seed/slate cells.

**But its endpoint is *world quality*, not candidate `C`.** Nothing yet measures
ATLAS's `C`, and `+10.93` is **not** comparable to CBWU-OI's `+5.66`. Worse for
the prior: ATLAS *reduces* combination breadth — pair reach ratio `0.9520`,
dominant-game `0.9080` — the opposite sign to the mechanism §5.2 identified. A
pair-reach floor and an explicit "expected to underperform on C" prior were
added to its gate as a result.

### 5.5 Exact-N ranking works only for small books

| N | relative primary-coverage change | disposition |
|---:|---:|---|
| 1 | +3.53% | shadow |
| 3 | **+7.23%** | shadow |
| 20 | +1.62% | shadow |
| **40** | **−0.05%** | **failed/closed** |

Monotone decay, crossing zero by 40. **Production submits 80.** Treat this as a
small-field-qualifier mechanism, not a main-book one.

---

## 6. Current production state

Frozen in `src/nfl_dfs/inference/production_policy.py` as
`ADOPTED_CLASSIC_POLICY`, policy id **`classic-k1-role12-boom40-poscal-cbwu-v4`**:

- **K=1** single model (not an ensemble), registry variant `tail_k1`
- **TabPFN marginals on**, active-only training labels
- **Possession simulator**, per-team game factors, 30,000 worlds
- **Production-multinomial** within-team usage law (see §7)
- **Per-position final-served calibration**: QB 0.970 / RB 1.005 / TE 0.940 /
  WR 1.070
- **45/55 model/market blend**, props-first with DK-PPG fallback
- **Selector**: greedy world coverage at line **194**, exactly **80** entries
- **$49,000 salary floor**, mandatory stacking (QB + 2 + bring-back)
- **CBWU** candidate/world union portfolio; generator mix role 12 / boom 40

Nothing in §5 is in production. CBWU-OI, ATLAS, exact-N and the constraint
lattice are all research or prospective-shadow only.

---

## 7. Two things that will mislead you if you don't read them

### 7.1 There are two panels, and they are not interchangeable

- **107 slates**, six seasons (2019, 2021–2025), 2020 excluded — the historical
  replay baseline. Current corrected result: **17/107 ≥194**, mean best 173.31.
  *This baseline has a known defect* (DST salary aliases unnormalized, dropping
  478 rows in 2019/2021); it is reproducible but **not** a citable
  complete-universe control.
- **54 slates**, 2023–2025 Weeks 1–18 — the forensic / CBWU-OI / ATLAS /
  lattice panel. Everything in §5 is on this panel.

Do not compare a 107-slate count to a 54-slate count.

### 7.2 There are three simulation laws, and results do not transfer between them

This is the single most common way a number gets misread here.

| law | used by |
|---|---|
| **production multinomial** | the money policy, the UI, the served exact-80 book |
| **fitted-Dirichlet research law** | the older G-series dependence diagnostics |
| **finite-K + SIS-ASOE (Phase S)** | ATLAS Phase S and several research panels |

A result measured under one law is not evidence about another. Every research
result needs an explicit transfer step, and each transfer can lose the effect.
`reports/2026-08-16-simulation-law-ledger.md` records which law each result used
— **check it before comparing any two numbers.**

### 7.3 The dependence numbers you will find are under the wrong law

The frequently cited table — QB→WR realized 3.32 vs simulated 2.42, ≥3
multiplicity 1.84 vs 2.38, ≥4 multiplicity 2.33 vs **6.18** — describes an
**under-coupled hub with over-produced high multiplicity**, a *shape* error no
single global coupling parameter fixes.

**But it was measured under the fitted-Dirichlet research law, not the
production multinomial law the money policy actually serves.** A remeasurement
under the exact production law is frozen and pending. Treat the shape claim as a
live hypothesis, not an established property of production.

---

## 8. Operational reality: most recent failures are mechanical, not scientific

A reviewer skimming recent reports will see a long run of failures and may
conclude the science is failing. It mostly isn't. The ATLAS matched-diversity
grid has now been attempted six times:

| grid | cause of loss |
|---|---|
| repair2 | CBC child `SIGKILL` at ~84% of a 4 GiB cap |
| repair3 | **all 54 cells** rejected a new output prefix — a hard-coded constant |
| repair4 | one genuine 16 GiB memory failure + 6 `Internal error running task` |
| repair5 | code defect: `ATLAS world <n> identity tiebreak is infeasible` |
| repair6 | in flight — hybrid: reuse repair5 successes, rerun only classified failures |

Only repair2 and repair5 taught anything. The structural cause was a contract
requiring **all 54 cells to succeed with zero retries**: at even a 1–2%
per-cell infrastructure failure rate, `(1-p)^54` makes a clean grid a coin flip.
Two fixes were adopted and are now standard: a **bounded platform-error-only
retry** (literal Cloud Run platform error, no object written, one replacement
execution — never for memory, timeout, solver or signal) and a **real-path
canary** (run one real grid cell on the real launch path and prefix before
releasing the other 53).

If you review the execution machinery, that is the current state of the art
here; suggestions should build on it rather than rediscover it.

---

## 9. What is in flight right now

Historical experimentation is closed. Current work is prospective or
descriptive. Roughly in queue order:

- **ATLAS repair6 + historical score v4** — completing the matched-diversity
  grid, then a frozen retrospective realized-score diagnostic. Its signal rule
  requires +2 selected weeks at 200 **and no decline at 210, 220, 230 or 240**;
  the 200 anchor is explicitly disclosed as informed by CBWU-OI on the same
  panel.
- **Constraint lattice** — a bounded sleeve of ≤8 lineups (of 80) that each
  violate exactly one incumbent strategic constraint (QB stack shape, bring-back,
  RB-vs-DST, two-RB-same-team). Five-fold held-out simulated blocks, p230-anchored
  gate, with a control support census and resource preflight now required first.
- **Coherent model/market-state generator** — when model and market disagree,
  build lineups that represent each source's *coherent team story* rather than
  the 45/55 blended mean. Fixed-budget candidate discovery only.
- **Stack-core × shell** — an independent fallback construction grid, gated on
  its own support census and on ATLAS closing.
- **Recourse-aware initial book** — choose the initial 80 for the legal
  late-game alternatives they preserve. The one untested recourse idea.
- **Same-law capacity curve** — descriptive: how fast the six-family candidate
  law saturates given genuinely independent search books.
- **Production-law dependence remeasurement** (§7.3).
- **Impact/equivalence certificate** — governance tooling: an upstream change
  forces revalidation only when it can change the exact downstream contrast.

---

## 10. Data access and validation law

Google Cloud project **`nfl-predictions-503414`**. `gcloud` and `bq` are
available and authenticated; queries are cheap and safe.

| dataset | contents |
|---|---|
| `nfl_raw` | `pbp`, `schedules`, `rosters_weekly`, `injuries`, `snap_counts`, `ngs_*`, `ftn_charting`, `prop_lines`, `contest_ownership`, `fantasy_points_*`, `sis_*` |
| `nfl_features` | `player_week_training`, `player_week_inference`, `player_week_usage`, `defense_week_allowed`, `dk_salary_week`, `tabpfn_projections`, `team_week_*` |
| `nfl_predictions` | `replay_candidates`, `replay_candidates_staging`, `slate_player_features`, shadow tables |
| `nfl_forensic_review` | Frozen forensic corpus. **`production_use=forbidden`** — read only. |

Score artifacts (candidate × world matrices) are checksummed NPZ in
`gs://nfl-predictions-503414-raw/`. **Licensed vendor data** (Fantasy Points,
SIS) lives in gitignored directories and private tables — never commit or
reproduce raw vendor rows; schemas, hashes and aggregates are fine.

**The validation law. Suggestions that violate it are not usable:**

1. **Point-in-time is sacred.** A feature for week W may use only weeks < W;
   windows end at `1 PRECEDING`. `features/leakage.py` runs on every build.
2. **Walk-forward only**, by season. Never random splits.
3. **Preregistration.** Every experiment freezes its success criterion and an
   immutable image digest *before* it runs, runs once, and records a
   disappointing result as disappointing.
4. **Verdicts do not transfer across a changed downstream stage.**
5. **No retrospective tuning** on known outcomes. Reading outcomes makes an
   analysis hypothesis-generating only.
6. **Deterministic.** Same seed and image reproduce byte-identical results.
7. **Support preflight before freezing cell-dependent gates** — if a gate needs
   minimum counts in cells, census the counts (outcome-blind) first.

**Will not be usable:** retuning a parameter on the historical panel; reopening a
closed arm without a changed downstream stage; anything using same-week data as
a predictor; anything optimising mean or average lineup score.

---

## 11. What would actually be valuable

In rough priority order:

1. **Correctness bugs** — point-in-time violations, bad joins, train/serve skew,
   silent-null paths. Prior audits found real ones (post-lock injury data,
   end-of-season position leakage, cross-season smoother contamination, a
   Dirichlet allocation-unit error, DST salary alias drops), so more may exist.
2. **Ideas that attack construction** (§4, §5.1). Specifically: **is there a
   pre-lock-identifiable region denser in high-actual rosters than current
   sampling?** That is the open question the census leaves.
3. **An independent read of the breadth mechanism** (§5.2). Combination breadth
   beat player breadth once. Is that general, or an artifact of one admission
   rule?
4. **The dependence shape error** (§7.3) — under-coupled hub, over-produced
   multiplicity, no single parameter fixing both, and now needing remeasurement
   under the production law.
5. **Recourse-aware initial construction** (§9). Entries can be edited until each
   game's kickoff, so the real problem is multi-stage with recourse. Almost
   nothing in the codebase treats it that way.
6. **What the framing excludes.** Two dozen mechanisms have been tested inside
   one framing; an outside reading of what that framing cannot see is genuinely
   valuable.

**For any proposal, please state: which channel (§3), which simulation law
(§7.2), what endpoint it moves (world quality / `C` / `S`), whether it needs new
data, and how it would be falsified.** A proposal that cannot be placed and
falsified cannot enter the queue.

---

## 12. Six traps that have caught reviewers, including me

Each has already produced a wrong conclusion here.

**12.1 Era pooling.** The panel spans rule and pace changes. Overtime analysis
produced a ~4σ claim on pooled 2015–2025 data that became noise once rule
regimes were separated (10-minute OT in 2017; both-teams-possess reaching the
regular season in 2025). **State the seasons used and check whether the rules or
the pipeline changed across them.**

**12.2 Endpoint confusion.** `attainable world quality`, `candidate C` and
`selected S` are three different quantities. ATLAS's `+10.93` and CBWU-OI's
`+5.66` are **not** comparable. Always name the endpoint.

**12.3 Simulation-law confusion.** See §7.2. Three laws; results don't transfer.

**12.4 Constants going stale.** This project corrects its own headline numbers,
and superseded values keep getting quoted downstream. Known-stale figures still
circulating: recourse **+42.62**; simulated QB→WR **≈1.05** (pre-`26e73c5`);
selector disjoint-half overlap **54.28/80** (measured at a different sample
width — the comparable current value is 65.69); source row count **72,520** (it
is 68,199). **Before relying on any number, search for a later correction.**

**12.5 Nested thresholds read as independent.** Counts at 240/230/220/210/200 are
**nested** — a slate crossing 220 necessarily crosses 210 and 200 — so a
"+2/+2/+3" delta may be three distinct slates, not seven improvements. Ask for
**distinct slates moved**.

**12.6 Simulated success ≠ transfer.** Schaake, three Gumbel variants, CE and
fast-role all satisfied simulated criteria and then failed. Held-out simulated
blocks control Monte Carlo noise but **not model misspecification** — five seeds
of one simulator share any dependence-structure error. A held-out pass certifies
"not seed-overfit," nothing more.

And the general form of §3: **the channel a feature is inserted into determines
what it can affect.** "We tested route share" is ambiguous between two different
experiments — one changing the served marginal, one changing only ranks — and
that has been confused here before.
