# Review notes on the graph/dependence research queue

Date: 2026-08-11. Review of `reports/2026-08-11-graph-dependence-research-queue.md`.
**No code was changed.** Six issues, ordered by how much damage they do if
missed, plus two corrections to my own earlier numbers.

---

## Accepted corrections

Two catches in the queue are correct and I had missed both:

- **`player_archetypes` is unsafe as a historical label.** Its normal job fits a
  trailing window ending at the latest completed season, so using it for a 2023
  target leaks. Refitting per target season from strictly prior seasons is
  right, and it is the kind of leak that would have quietly invalidated the
  whole diagnostic.
- **Ordinary PBP does not identify all eleven on-field players.** My §4
  co-occurrence embedding proposal assumed it did. The participation feed is
  required, and it is season-delayed — which constrains G3 more than I implied.

The scope correction is also fair: joint dependence is the largest open channel,
not the only one. The fitted-K decision and the TabPFN marginal sequence are
independent open questions and should not be displaced.

---

## Issue 1 — G1's thresholds move underneath it (sequencing hazard)

G1 step 2 defines exceedance against "that player's point-in-time final-served
q90." That threshold is produced by the served path, which the in-flight
marginal queue is actively changing: active-label correction, SCHED feature
sync, and team-QB-quality are all TabPFN cache regenerations, and each one moves
every player's served quantiles.

The queue says G1 "may run while later marginal cache stages execute." That
creates a stale-baseline risk: G1 measures realized-vs-simulated topology under
cache version A, G2 is then gated on G1's grid, but production by then runs
cache version C.

**Fix:** pin G1 to a named immutable cache identity and image digest in its
manifest, and state the invalidation rule explicitly — if the served marginal
cache changes before G2 launches, G1's grid must be recomputed. G1 is cheap
enough that re-running it is not a burden; silently comparing G2 against a stale
grid would be.

Cleanest alternative: run G1 after the marginal queue drains. The queue's own
execution order already puts the marginal work first, so the "may run
concurrently" allowance is the only thing creating the hazard.

## Issue 2 — the independence baseline must be Poisson-binomial, not pooled

G1 step 5 compares realized and simulated `≥2/≥3/≥4` exceedance multiplicity.
The baseline matters and the obvious implementation is wrong.

My own earlier measurement used a **pooled** rate (p = 0.0853 for every player)
and a binomial baseline. That is not the right null when per-player exceedance
probabilities differ — and they do, materially, since the per-position
calibration deliberately made them differ (QB 0.970 / RB 1.005 / TE 0.940 /
WR 1.070 factors, and residual per-position gaps remain).

For independent Bernoulli(p_i) with Σp_i fixed, Var = Σp_i(1−p_i) ≤ n·p̄(1−p̄),
with equality only when all p_i are equal. **Heterogeneity shrinks the variance
and thins the upper tail of the count**, so the correct independence baseline
for `≥4` is *lower* than the pooled binomial. My reported 2.17× excess is
therefore conservative — the true excess is larger, not smaller.

**Fix:** compute the null as a Poisson-binomial over each team-week's actual
per-player exceedance probabilities (exact via DFT/recursion for n ≤ ~15, which
covers every team-week). Report the pooled-binomial value too, so the two are
comparable against my earlier figure, but gate on the Poisson-binomial.

## Issue 3 — add a one-execution kill test before G1's full build

G1 as specified is a substantial build: walk-forward archetype refits, edge
aggregation with shrinkage, spectral/Leiden clustering, topology comparison.
All of it is wasted if the simulator already reproduces the dependence
structure.

There is a much cheaper precursor that answers the premise directly — no
archetypes, no clustering, no communities. On simulated draws for the same
team-weeks, compute exactly six numbers and compare to realized:

1. `≥2` / `≥3` / `≥4` multiplicity ratio against the Poisson-binomial null;
2. QB→WR / QB→TE / QB→RB conditional exceedance lift;
3. WR–WR / RB–RB / TE–TE same-position lift.

Falsifiable prediction to record before running: the simulator shows WR–WR
materially above 1.0 (realized ≈0.99), QB→WR below 2.34, and `≥4` multiplicity
below the realized excess.

If the simulator reproduces all six, **G1 and G2 are both unnecessary** and the
channel closes for one execution instead of two workstreams. If it fails them,
G1 proceeds with a confirmed premise and a much stronger prior. Either way this
is the highest information-per-dollar step in the queue.

## Issue 4 — state G2's fit/evaluate split explicitly

G2's gate requires "reduced error in the G1 co-exceedance/multiplicity grid,"
and G2's parameters are fit to reproduce dependence. Unless the split is
written down, this grades a model on the statistic it was fitted to.

The queue does say "fit all link/load parameters on earlier seasons without
lineup scores," which implies the right thing, but it does not say the grid is
evaluated on held-out seasons. **Make it explicit:** fit on 2019–2022, evaluate
the G1 grid and the variogram/joint-q90 metrics on 2023–2025 only. Otherwise a
pass is uninterpretable.

## Issue 5 — a slate factor's real use is the winning line, not lineup construction

G1 correctly reports cross-game same-slate cells separately and refuses to
assume a slate factor. Worth adding one interpretive note so a null there is not
over-read, and a positive is not under-used:

Cross-game dependence does not help *construct* a lineup — you cannot stack
across games in any meaningful sense. What it governs is the **distribution of
the winning score**: if all games run hot together, every entrant's ceiling
rises and the line that wins moves up. So a confirmed slate factor feeds the
per-slate target-line model, not the copula's stacking value.

That also means G1's cross-game cells should be retained even if they do not
license a slate factor in G2 — they are an input to a different, already-proposed
piece of work.

## Issue 6 — G3's target is undefined if fitted-K is rejected

G3's first gate is "conditional target/carry allocation likelihood versus the
accepted global-K law." If the pending fitted-K exact-80 comparison rejects and
production stays at the independent-Poisson default (the K→∞ limit), then there
is no accepted finite global K for G3 to shrink around.

**Fix:** state G3's branch now, before the fitted-K result is known — e.g. the
comparison target is whatever allocation law is production at G3 launch, and if
that is K→∞ then G3's first question becomes whether *any* finite per-team
concentration beats it on held-out allocation likelihood. Deciding this after
seeing the fitted-K outcome is the kind of small post-hoc choice the project
otherwise forbids.

---

## Corrections to my own earlier numbers

Both affect figures the queue may cite; G1 should recompute rather than inherit
them.

1. **My §7 exceedance flags used `slate_player_features.proj_p90`**, which comes
   from the *widened summary* (`apply_widen`), not the served draws. That is why
   the marginal rate came out at 8.53% rather than ~10%. The conditional *lifts*
   are ratios against a common within-position threshold and are robust to this,
   but the absolute exceedance level is not the served one. G1's use of the
   point-in-time final-served q90 is the correct construction.
2. **The 2.17× `≥4` excess used a pooled binomial null** — see Issue 2. Direction
   of the error is conservative, but the number should be recomputed properly.

Neither changes the qualitative finding (QB hub strong, same-position teammates
flat, excess multiplicity at the top), which is what G1 is designed to test
properly.

---

## Summary

The queue is well constructed: the exclusions are right, the archetype-pair
aggregation correctly avoids player-pair edges, the Gumbel copula/generator
distinction is named, and the Neo4j revisit condition is sensible.

The one change I would make before starting is **Issue 3** — insert the
six-statistic kill test ahead of G1's full build, with its prediction recorded
in advance. It is one execution, it can retire two workstreams, and it converts
G1 from a speculative build into a confirmed follow-on.

Then **Issue 1** (pin the cache identity) and **Issue 2** (Poisson-binomial
null) are both small and both change what the numbers mean.
