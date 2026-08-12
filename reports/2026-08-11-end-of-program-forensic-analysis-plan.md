# End-of-program forensic analysis plan

Date: 2026-08-11. A plan for the thorough retrospective to run **once historical
experimentation stops**. Its purpose is to convert everything the system has
produced into a sized, ranked understanding of where the remaining money is —
and to hand the 2026 prospective program a charter instead of a hunch.

**No code was changed.** This is a protocol.

---

## 0. The framing that makes this legitimate

Everything below reads realized outcomes on the 107 historical slates. Under the
project's standing law that makes it **hypothesis-generating only**. This is not
a loophole to be managed; it is the entire design premise:

> **The deliverable is a prospective 2026 research charter and an opportunity
> register, not a single historical adoption.** No analysis here may promote an
> arm, retune a parameter, change a selector, or reopen a closed mechanism.

That constraint is what makes the exercise safe to run at full depth. It is also
why it belongs *after* the stopping point: once no more historical arms will be
launched, there is nothing left to contaminate.

Three disciplines make it trustworthy rather than a fishing expedition.

**0.1 Pre-register the complete analysis list before running any of it.** The
plan below contains roughly thirty distinct cuts. Run at 5%, one or two will
look striking by chance. Freeze the list, the metrics, and the direction of
interest in a tracked commit *before* the first query executes. Any analysis
added afterward is labelled `post-hoc` in the output and may not enter the
opportunity register without prospective confirmation.

**0.2 Split confirmatory from exploratory explicitly.** Confirmatory analyses
(§1, §2.1, §5.1) test claims the program already made. Exploratory analyses
(§3, §4, §6) generate new ones. Report them in separate sections with separate
evidentiary weight. Do not let an exploratory z-score be quoted later as if it
were confirmatory.

**0.3 Pin provenance.** One immutable image digest, one named analysis run id,
and an explicit list of the panel ids consumed. The pipeline is deterministic,
so the entire thing must be exactly reproducible from the manifest.

### Source inventory (verified present)

| object | rows | notes |
|---|---:|---|
| `nfl_predictions.replay_candidates` | 300,965 over 14 panels | `players`, `selected`, `tag`, `p_line`, `sim_mean/sd/q50/q90/q99`, `actual_score`, `actual_rank`, `clear_bits_{187,194,200,210,220}`, `salary` |
| `nfl_predictions.slate_player_features` | 1,948,569 over 49 panels | `proj`, `proj_p10/50/90`, `own_est`, `actual`, role/route/coverage fields |
| `nfl_raw.contest_ownership` | 103,556 over 1,258 contests | `pct_drafted`, `fpts`, per player per contest, 2022–25 |
| `nfl_predictions.missed_player_analysis` | 1,381 | prior miss audit |
| `nfl_predictions.archetype_matched_pairs` | 27,266 | matched-control pairs |
| 68 Millionaire winner rosters + winning lines | — | `reports/*.csv` |

`clear_bits_*` at five thresholds is the key asset: it permits exact
counterfactual selection at any line without re-simulating.

---

## 1. The master decomposition (confirmatory — do this first)

Everything else is detail. For each of the 107 slates, decompose the gap between
what was achievable and what the book scored into four additive layers:

| layer | definition | data |
|---|---|---|
| **L1 universe** | best legal 9-man lineup from the *full salary-listed pool* using realized scores, minus the pool oracle | `slate_player_features` + salary/legality solve |
| **L2 generation** | pool oracle minus the best 80-subset achievable from the pool | `replay_candidates.actual_score` |
| **L3 selection** | best achievable 80-subset minus our selected best | `clear_bits_*` + subset search |
| **L4 realized** | our selected best | `selected = TRUE` |

L1 is a hindsight MILP on realized points — trivially solvable and never
computed. It answers "how far short is the *candidate generator's universe*, as
opposed to the generator itself." L3 requires an upper bound on the best
weekly-max obtainable by any 80 of the ~250 candidates, which for
maximum-of-subset is exact: it is simply the top-80 by `actual_score`, so
**L3 collapses to (pool oracle − selected best)** and is already partly known.
The value is in doing all four consistently across every slate and season.

Output: a 107-row table with the four layers, aggregated by season and by
threshold band. This is the sizing instrument for every recommendation that
follows — no proposal enters the register without an L-layer attribution.

Predeclared expectation, from prior work: L2 dominates at 210+ (selection is
saturated there) and L1 is large (the winner-slot audit found 33 of 612 winning
player-slots absent from the pool entirely). If L1 turns out to dominate, the
conclusion changes materially — the problem would be *player universe
construction*, not beliefs.

## 2. Selection and candidate forensics

**2.1 Rank-skill census (confirmatory).** For every pre-lock signal in
`replay_candidates` — `p_line`, `sim_mean`, `sim_q90`, `sim_q99`,
`sim_rank_p_line`, `salary`, and `own_est` aggregated to lineup level — compute
the within-slate Spearman correlation against `actual_rank`, pooled and by
season, with slate-clustered intervals. Prior work found
`corr(oracle sim-rank, regret) = +0.030`; this generalises it to every signal
and every candidate rather than the oracle subset. **If no signal exceeds a
predeclared bar, selection is closed permanently and should be recorded as
such.**

**2.2 Counterfactual entry-count curve.** Using `clear_bits_*`, compute realized
weekly-max at N ∈ {20, 40, 80, 120, 150, 200} entries under the unchanged
selector. This sizes "more entries" as a lever directly, against the measured
`entries_curve` rather than its interpolation, and it is the one lever known to
work.

**2.3 Generator-tag yield under a fixed budget.** Extend the known finding
(`lev` = 66% of the pool, 8% of selections, 1 clear on deletion) to yield *per
thousand candidates* by tag, by season, and **conditional on slate regime** (§4).
A generator that is useless on average but strong in a specific regime is a
scheduling opportunity, not a deletion candidate.

**2.4 The near-miss frontier.** For every slate, the distribution of
`actual_score` among unselected candidates, and the roster-distance (shared
players) from the selected best to the pool oracle. Prior audits did this for
consequential misses only; do it for all 107 to get the shape rather than the
anecdotes.

## 3. Construction forensics (exploratory)

**3.1 Shape inventory.** Classify every submitted lineup and every one of the 68
winners by: number of distinct games, largest single-team block, presence of
bring-back, QB-stack size, TE-in-stack, DST-team-vs-stack relationship. Compare
the submitted distribution to the winners' distribution. This has never been
done as a distribution — only as individual roster contrasts.

**3.2 Salary utilisation.** Distribution of total salary and leftover, ours vs
winners', by season. The $49k floor is adopted; this measures whether the
binding constraint is the floor or the allocation *within* the cap.

**3.3 Positional spend.** Share of cap by position, ours vs winners. The
missed-winner audit found omitted slots averaged $4,128 and 5.88% ownership —
this asks whether the whole book is systematically mis-allocating spend rather
than missing individual players.

**3.4 Exposure-versus-value curve.** For each player-week, our exposure across
the 80 entries against realized DK points. Aggregate into a calibration-style
plot by salary band, position and archetype. The question is whether exposure is
monotone in realized value and where it inverts.

## 4. Regime and trend analysis (exploratory — highest novelty)

This is the least-explored area and the most likely source of a genuinely new
idea, because every prior analysis pooled all 107 slates.

**4.1 Regime split.** Partition slates by pre-lock observables: number of games,
sum of implied totals, maximum game total, spread dispersion, mean wind,
week-of-season, and early/late season. For each partition report the realized
tail grid, the L-layer decomposition from §1, and mean regret.

The actionable question: **does the system fail in an identifiable regime?**
If, say, all four 240-point weeks come from 13-game slates with three 50-point
totals, then slate selection and entry allocation become levers — enter more on
those slates, fewer on others. That is a strategy no belief change can provide.

**4.2 Failure autocorrelation.** Is weekly regret independent across weeks, or
does it cluster? Clustering implies a slow-moving state (a model that has gone
stale, a roster-turnover period) that a refresh cadence could fix.

**4.3 Chalk regime.** Using `contest_ownership`, classify weeks by whether the
high-owned players busted. Prior work found the system clears lines in 60% of
chalk-bust weeks vs 40% of chalk-win weeks. Re-verify on the corrected panel and
size it: if the edge is concentrated in chalk-bust weeks, the entry-allocation
implication is direct.

**4.4 Seasonal drift.** Per-season L-layer decomposition and calibration. The
panel spans 2019–2025 across major rule and pace changes; a monotone drift in
any layer is a warning about how much of the 107 is still representative.

## 5. Field, ownership and money (confirmatory + exploratory)

**5.1 Realized ownership profile of the submitted book.** Join our 80 entries to
`contest_ownership.pct_drafted` for 2022–25. Compute each entry's ownership sum
and product, and the book's distribution against the winners'. The system has
1,258 contests of actual ownership and has never scored its own submitted book
against them. This directly tests the leverage premise the construction assumes.

**5.2 Score-to-money reconstruction, as far as the data allows.** `pct_drafted`
and `fpts` are per player, not per entry, so full standings cannot be
reconstructed. What *can* be built: the realized ownership-weighted field score
distribution, and — where contest metadata exists — the relationship between
our weekly max and the known winning line. Be explicit that this is a bound, not
a payout model.

**5.3 Duplication proxy.** For each submitted entry, the product of its players'
realized ownership as a crude duplication index, and its correlation with the
entry's realized score. Tests whether our high scores are coming from
constructions the field also had.

## 6. Data census (exploratory, and overdue)

**6.1 Missingness as a predictor of error.** For every feature, the NULL rate by
season, position and week-of-season — and then the key cut: **is projection
error conditionally larger when a feature is NULL?** If so, missingness is
itself a signal the model is not using, and imputation is doing damage. This
analysis has never been run and costs one query per feature.

**6.2 Silent source degradation.** Coverage of every raw source by season. The
project has been bitten by nflverse schema drift before; a census establishes
whether any feed has quietly thinned over the panel.

**6.3 Deficiency-log reconciliation.** Walk the README data-deficiency log and
mark each entry resolved / still-open / newly-material. It is append-only by
design and has never been reconciled against current state.

**6.4 Cross-panel meta-analysis.** Fourteen candidate panels exist on common
slates. Pool them to estimate the between-arm variance of weekly max — i.e. how
much of any observed arm difference is attributable to configuration versus
slate noise. This gives an empirical answer to "how big does an effect have to
be before we should believe it," which every future gate needs and none has had.
**It may not be used to revive a rejected arm.**

---

## 7. Output: the opportunity register

One tracked table, one row per identified opportunity:

| field | meaning |
|---|---|
| `id`, `title` | — |
| `layer` | L1 universe / L2 generation / L3 selection / objective / operational |
| `evidence` | confirmatory or exploratory, with the section |
| `size_estimate` | expected weekly-max points or threshold-weeks, from §1 |
| `size_ci` | slate-clustered interval |
| `cost` | build cost and cloud cost |
| `prereq` | data or infrastructure needed |
| `disposition` | 2026 prospective / needs data / closed |

Plus two shorter documents:

- **A kill list.** Mechanisms the retrospective shows are exhausted, with the
  evidence, so no future session re-derives them. This is as valuable as the
  register and is usually skipped.
- **The 2026 prospective charter.** The ranked program the register implies,
  with gates frozen *before* Week 1 outcomes exist — which is the only way any
  of it becomes real evidence.

---

## 8. Sequencing

1. **Freeze** the analysis list, metric definitions and confirmatory/exploratory
   split; pin panels and image (§0).
2. **§1 master decomposition.** Everything else is interpreted against it, so it
   must complete first. If L1 dominates, re-order the rest around universe
   construction.
3. **§2 selection forensics** and **§6.1 missingness** — both cheap, both
   potentially decisive.
4. **§4 regime analysis** — highest novelty, and it needs §1's layers as inputs.
5. **§3 construction** and **§5 field** — richest but most confounded; do them
   once the layer sizing is known so the findings can be weighted.
6. **§6.2–6.4 census** — housekeeping with real value, no rush.
7. **§7 synthesis.**

Realistically this is one Cloud Build and a handful of executions, most of it
BigQuery. The expensive part is §1's L1 MILP across 107 slates, which is a
small solve per slate and can run in one job.

---

## 9. What this cannot answer

State these limits in the output so the register is not over-read:

- **No full contest fields.** Every payout, duplication and rank conclusion is a
  bound, not a measurement, until 2026 standings exist.
- **107 slates, 2 weeks above 240.** Anything conditioned on the extreme tail is
  descriptive. Regime cuts (§4) subdivide further and will be underpowered by
  construction — report intervals, never point estimates alone.
- **Deterministic pipeline.** There is no sampling variance to average over;
  apparent differences between arms are exact but that does not make them
  *generalisable*. §6.4 is the closest available proxy for generalisation error.
- **Survivorship.** The 14 panels are the arms that were launched, which were
  chosen by earlier evidence. Pooling them (§6.4) inherits that selection.
- **This is history.** Rule changes, pace drift and roster turnover mean 2019
  may not describe 2026. §4.4 measures the drift; it cannot remove it.
