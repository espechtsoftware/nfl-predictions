# External reviewer briefing

**Read this first. It is written for a reviewer with no prior context on this
repository.**

Date: 2026-08-15, updated 2026-08-16. Purpose: orient an external model to
review this codebase productively, and — equally important — to avoid the large
amount of material that describes mechanisms which were tested and **rejected**.

> **Status note.** The forensic audit referenced throughout is **still in
> progress.** Its first published result has already been partially superseded
> by a correction, and one of its components hit an operational failure and is
> being repaired. Section 4 gives the numbers that are currently believed
> correct and flags which have moved. **Section 6a lists everything that has
> changed since this briefing was first written** — read it before drawing
> conclusions from any dated report.

---

## 1. What the system does, in one paragraph

It builds DraftKings NFL "Classic" daily-fantasy lineups. Each week it picks
9 players under a $50,000 salary cap (QB 1, RB 2, WR 3, TE 1, FLEX 1 from
RB/WR/TE, DST 1) and submits **80 distinct lineups** into large-field
tournaments — typically a ~160,000-entry contest where only the very top scores
win meaningful money. Because payouts are extremely top-heavy, **the objective
is not average accuracy — it is the single best score among the 80 entries.**
That distinction drives every design decision and is the most common thing an
outside reviewer gets wrong.

The historical evaluation panel is **107 Sunday-main slates across six seasons
(2019, 2021–2025)**. 2020 is deliberately excluded.

---

## 2. The single most important instruction: what NOT to read

This repository contains roughly **200 documents in `reports/`**, and the large
majority describe **experiments that failed and mechanisms that are closed.**
They are retained deliberately — the project's discipline is to record negative
results rather than delete them — but they do **not** describe how the system
works.

**Do not infer current behaviour from `reports/` unless a document explicitly
says a mechanism was adopted.**

Rejected or closed mechanism families that appear extensively in `reports/` and
are **not** in production:

- GFlowNet candidate generation, Gumbel candidate generation (all variants),
  Schaake shuffle, forest-learned dependence templates, Chronos time-series
  marginals, cross-entropy (CE) worlds, epistemic (EPI) candidates
- Ownership "fade" objectives (`OWN_MODEL=fade`, `milly_fade`)
- Fantasy Points: route share (both marginal and rank channels), advanced
  prior-season, coverage fit, same-season coverage, route shape, QB shell,
  defense PROE
- SIS: team context, QB line, RB run defense, pass-tail marginal, run-tail
  Boom/Bust, team pass-defense coverage schema
- TD ledger (all four attempts), G2 QB-Gumbel factor, competitive-WR allocation,
  TE hub follow-up
- Selector variants: reranker, LSE, sharp-LSE, QB-concentration,
  dollars-objective, bagged/bootstrap selection

**Read these instead** — this is the authoritative set:

| file | what it is |
|---|---|
| `HANDOFF.md` | **The authoritative current-state record.** Read the top section first. |
| `README.md` | Full design guide (§0–§14) with a section-to-code map at the top |
| `CLAUDE.md` | Project rules, including the validation law |
| `reports/2026-08-14-final-preseason-forensic-result.md` | **The forensic audit — where the score is actually being lost** |
| `src/nfl_dfs/inference/production_policy.py` | The single frozen definition of production behaviour |
| `src/nfl_dfs/models/featureset.py` | Exactly which features the model uses |

If a document and the code disagree, **the code is authoritative**. If
`HANDOFF.md` and an older report disagree, `HANDOFF.md` wins.

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
channel that has already been exhausted. Every proposal should name which
channel it acts in:

| channel | what it changes | status |
|---|---|---|
| **Marginal** | a player's own projected distribution | **exhausted** — ~12 arms, all failed |
| **Copula / dependence** | which players boom *together* | mostly closed; see §5 |
| **Generation** | which lineups get built from the players available | **where the loss is** (§4) |
| **Selection** | which 80 of ~250 candidates get submitted | **saturated** — no room |

**A critical mechanical fact:** TabPFN marginal coverage is **100%**, and the
shaper rank-remaps every player's simulated draws onto that player's cached
TabPFN quantiles. So for covered rows, a feature added to the **LightGBM
component models** changes only the *ranks* (the copula) — it cannot change the
served marginal. A feature added to `scripts/tabpfn_gen/features.txt` changes
the marginal. **These are different experiments on the same feature**, and
conflating them has caused real confusion here.

---

## 4. The forensic result — read this before suggesting anything

Every slate was decomposed into four layers using hindsight-optimal solves:

- **H** — best legal lineup from the complete slate player universe
- **P** — best legal lineup from the union of players appearing in *any*
  generated candidate
- **C** — best candidate actually generated
- **S** — best entry actually selected

| gap | mean points |
|---|---:|
| H − P (player support) | **3.58** |
| **P − C (construction)** | **78.99** |
| C − S (selection) | **5.01** |

At the 210-point threshold, the first failing layer is **construction on 44 of
54 slates**, player support on 3, selection on **0**.

**Interpretation, and this should govern the whole review:** the right players
are already in the candidate pool — the union supports a 240-point legal lineup
on 44 of 54 slates. The generator never assembles them. **The problem is
combinatorial coverage of lineup space, not player projection, not player
selection, and not the player universe.**

Two further settled findings:

- **The $49,000 minimum-salary floor costs nothing.** Removing it produced +0.53
  mean and **zero** new threshold-reaching slates from 187 through 240.
- **Late-swap (recourse) has large headroom.** A perfect-hindsight ceiling
  improved 53 of 54 slates. This is an *upper bound using realized outcomes* and
  must never be quoted as an achievable gain — but it is far larger than any
  marginal or selector effect measured.

> **Corrected since first publication.** The originally published recourse mean
> of **+42.62** and its tail counts were **superseded** by an exact-stack
> correction. The substantive conclusion — a large feasibility ceiling — is
> preserved; the specific numbers are not. Do not quote +42.62.
>
> A follow-up also measured whether the recourse and construction gaps are the
> same opportunity. They **partially overlap but are not interchangeable**: the
> corrected hindsight final roster is closer to exact-P than its source entry on
> 41 slates and closer than the selected weekly best on 27, but its mean distance
> from P is still **5.15 player swaps**. **They must not be summed as independent
> opportunity sizes.**

---

## 5. Current production state

Frozen in `src/nfl_dfs/inference/production_policy.py` as
`ADOPTED_CLASSIC_POLICY`, policy id **`classic-k1-role12-boom40-poscal-cbwu-v4`**:

- **K=1** single model (not an ensemble), registry variant `tail_k1`
- **TabPFN marginals on** (`TABPFN_MARGINALS=1`), active-only training labels
- **Possession simulator** with per-team game factors, 30,000 worlds
- **Fitted Dirichlet within-team allocation**, `K = 28.154043586960896`
- **Per-position final-served calibration**: QB 0.970 / RB 1.005 / TE 0.940 /
  WR 1.070
- **45/55 model/market blend**, props-first with a DK-PPG fallback
- **Selector**: greedy world coverage at line **194**, exactly **80** entries
- **$49,000 salary floor**, mandatory stacking (QB + 2 + bring-back)
- **CBWU** candidate/world union portfolio from the multi-seed factorial
- Generator mix: role 12 / boom 40

### Dependence structure — measured, and a live caveat

Realized teammate co-exceedance (a QB exceeding his own 90th percentile raising
a teammate's probability of doing the same):

| relationship | realized | simulated (current path) |
|---|---:|---:|
| QB → WR | 3.32 | 2.42 |
| multiplicity ≥3 | 1.84 | 2.38 |
| multiplicity ≥4 | 2.33 | 6.18 |

So the simulator **under-couples the QB hub** and **over-produces high
multiplicity** — a *shape* error, not a magnitude error. No single global
coupling parameter fixes both.

**Important:** a point-in-time repair (commit `26e73c5`, correcting Dirichlet
allocation from a franchise-wide season pool to the correct `(game, team)` unit)
materially changed these values. Any report dated before 2026-08-13 that cites
QB→WR ≈ 1.05 is **pre-repair and stale**.

---

## 6. What is being worked on now

Historical experimentation is **closed**. Current work is prospective (2026
season) or descriptive.

## 6a. Changes since this briefing was first written — read this

The forensic programme is **in progress, not finished**, and several things have
moved. This section is the delta; treat it as authoritative over anything older.

### Forensic corrections and repairs

- **The exact-stack correction** superseded the published recourse ceiling
  (+42.62 and its tail counts). See the box in §4. The project published a
  correction against its own headline rather than leaving it standing — that is
  normal practice here, and it means **any number you find in a report should be
  checked against a later correction before it is relied on.**
- **The construction/recourse overlap was measured** — partial overlap, 5.15
  mean swaps from P, must not be summed. §4.
- **Realistic recourse sizing** is being implemented: a point-in-time scorer that
  optimises late-game slots knowing only the *realized early results* and the
  *simulated distribution* for late games. That produces the convertible
  figure, as opposed to the hindsight ceiling. **Not yet complete.**
- **The exact-P generator constraint census** hit an operational failure
  (a BigQuery alias defect, then a repair build) and is being re-run. This is
  the analysis that asks *which production construction rule excludes the
  P-oracle* — i.e. what causes the 79-point construction gap. It is the single
  most consequential open forensic component.

### New prospective work

- **SIS player-grain pass-defense feasibility passed.** It establishes only that
  the player-grain surface can supply volume denominators and identities — it
  explicitly does **not** establish predictive value and cannot change the money
  policy. It licenses one bounded acquisition plus a score-free dependence
  protocol.
- **SIS receiver copula protocol** is frozen off that pass, with a split
  held-out gate. Note this is a **copula-channel** mechanism, not a marginal
  one — the marginal channel is closed and every prior SIS arm failed in it.
- **Latent role-state model**: protocol plus a live factory implementation.
  Prospective shadow only.
- **Overtime prediction was assessed and closed.** Worth reading as a worked
  example of the project's standards: an outside analysis produced a
  spread-versus-overtime table that looked significant, and the project rejected
  it because it **pooled across NFL overtime rule regimes** (the 10-minute change
  in 2017, both-teams-possess reaching the regular season in 2025). Recomputed on
  permitted data the relationship inverted and proved unstable. **2025 is the only
  season under the rule that governs 2026.** A formal reconciliation is recorded.

### Standing items not yet done

- Characterising the 79-point construction gap (blocked on the exact-P census)
- Odds API market expansion — alternate team totals and volume markets;
  acquisition, not an arm
- Between-arm variance across the fourteen existing panels — proposed, not built

---

## 7. Data access

Google Cloud project: **`nfl-predictions-503414`**. `gcloud` and `bq` are
available and authenticated; queries are cheap and safe to run.

```bash
bq ls nfl_features
bq show --schema --format=prettyjson nfl_features.player_week_training
bq query --nouse_legacy_sql --format=csv 'SELECT ...'
```

| dataset | contents |
|---|---|
| `nfl_raw` | Ingested sources: `pbp`, `schedules`, `rosters_weekly`, `injuries`, `snap_counts`, `ngs_*`, `ftn_charting`, `prop_lines`, `contest_ownership`, `fantasy_points_*`, `sis_*` |
| `nfl_features` | Modelling tables: `player_week_training`, `player_week_inference`, `player_week_usage`, `defense_week_allowed`, `dk_salary_week`, `tabpfn_projections`, `team_week_*` |
| `nfl_predictions` | `replay_candidates` (~301k candidate lineups over 14 panels, with `players`, `tag`, `selected`, `actual_score`, `sim_*`, `clear_bits_{187,194,200,210,220}`), `slate_player_features` (~1.9M player snapshots) |
| `nfl_forensic_review` | Frozen forensic corpus. **`production_use=forbidden`** — read only. |

Score artifacts (candidate × world matrices) are checksummed NPZ files in
`gs://nfl-predictions-503414-raw/cand_scores/`.

**Licensed vendor data** (Fantasy Points, SIS) lives in gitignored local
directories and private BigQuery tables. Do not commit or reproduce raw vendor
rows; schemas, hashes and aggregates are fine.

---

## 8. The validation law — please respect it in any suggestion

This project's discipline is unusually strict, and suggestions that violate it
are not usable. The rules:

1. **Point-in-time is sacred.** A feature for week W may only use data from
   weeks < W. Windows end at `1 PRECEDING`. `src/nfl_dfs/features/leakage.py`
   independently reconstructs feature families and runs on every build.
2. **Walk-forward only**, by season. Never random splits.
3. **Preregistration.** Every experiment freezes its success criterion and code
   (as an immutable image digest) *before* it runs. It runs once. A
   disappointing result is recorded as disappointing.
4. **Verdicts do not transfer across a changed downstream stage.** If a stage
   below a mechanism changes, prior verdicts about it are void.
5. **No retrospective tuning** on the 107 known outcomes. Reading outcomes makes
   an analysis hypothesis-generating only.
6. **Deterministic.** Same seed and image reproduce byte-identical results;
   comparisons are exact, not statistical.

**Suggestions that will not be usable:** retuning a parameter on the historical
panel; reopening a closed arm without a changed downstream stage; anything
requiring same-week data as a predictor; anything that treats the mean or
average lineup score as the objective.

---

## 9. What would actually be valuable from this review

In rough priority order:

1. **Correctness bugs** — point-in-time violations, bad joins, train/serve skew,
   silent-null paths. Prior audits found real ones (post-lock injury data,
   end-of-season position leakage, cross-season smoother contamination), so more
   may exist.
2. **Ideas that attack the construction layer** (§4). This is where 79 of the
   ~88 lost points live. Anything that makes the generator cover lineup space
   more effectively at a fixed candidate budget is the highest-value
   contribution possible.
3. **Independent reading of the dependence shape error** (§5) — under-coupled
   hub, over-produced multiplicity, and no single parameter fixing both.
4. **Recourse / late-swap design.** Entries can be edited until each game's
   kickoff, so the real decision is multi-stage with recourse, not one-shot.
   Almost nothing in the codebase treats it that way.
5. **Anything the project has systematically failed to consider.** A dozen
   mechanisms have been tested inside one framing; an outside reading of what
   that framing excludes is genuinely valuable.

**Please state, for any proposal: which channel it acts in (§3), whether it
requires new data, and how it would be falsified.** Proposals that cannot be
placed in a channel or falsified cannot enter the queue.

---

## 10. Three traps that have caught reviewers, including me

Offered concretely, because each has already produced a wrong conclusion here.

**10.1 Era pooling.** The panel spans 2019–2025 across rule and pace changes. An
analysis that pools seasons can produce a confident result that inverts under a
regime split. This is exactly what happened with the overtime table in §6a — a
~4σ claim on pooled 2015–2025 data became noise once the rule regimes were
separated. **Always state the seasons used and check whether the rule or the
pipeline changed across them.**

**10.2 Pre-repair references.** A point-in-time repair (`26e73c5`) corrected
Dirichlet allocation from a franchise-wide season pool to the correct
`(game, team)` unit, and materially changed the measured dependence structure.
**Two experiments died on stale pre-repair reference values.** Any figure from a
report dated before 2026-08-13 that describes simulated dependence is suspect —
notably any claim that the simulator's QB→WR lift is ≈1.05, which is pre-repair.

**10.3 Nested thresholds read as independent.** Results are reported as counts at
240/230/220/210/200. These are **nested** — a slate crossing 220 necessarily
crosses 210 and 200 — so a delta of "+2/+2/+3" may be as few as three distinct
slates, not seven improvements. When judging whether a result is strong, ask for
**the count of distinct slates that moved**, not the grid.

A fourth, more general: **the channel a feature is inserted into determines what
it can affect** (§3). "We tested route share" is ambiguous between two different
experiments — one changing the served marginal, one changing only ranks — and
the project has confused them before.
