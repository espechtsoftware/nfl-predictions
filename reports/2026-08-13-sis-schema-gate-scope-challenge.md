# SIS team pass-defense schema gate: correct closure, over-broad consequence

Date: 2026-08-13. Review of the frozen SIS team pass-defense schema screen.
**No code was changed.** No performance value or lineup score is referenced.

---

## The closure itself is right

The frozen rule required both coverage snaps and targets. The team Pass Defense
Totals export carries `Att` and neither of the required fields. Substituting
`Att` *after observing the schema* would change the preregistered estimand, and
refusing to do that is exactly the discipline that has protected this project
from a dozen post-hoc rescues.

**That decision should stand.** This exact team-grain, Totals-view,
Wide/Slot × Man/Zone path is closed and should not be retried, relaxed, or
mined at narrower shells.

The execution was also clean: eight artifacts hashed to manifest, all 32 team
IDs covered in union, every slice under the cap, 9 of 10 requests used, and
outcome-blindness preserved throughout.

## But the queue consequence overreaches

The result concludes:

> "Future receiver joint-allocation work needs a distinct source/grain with
> auditable point-in-time opportunities—such as a vendor matchup export captured
> prospectively, a separately justified player-level route/coverage source, or a
> new non-SIS mechanism—under its own frozen protocol."

Two problems with that scope.

### 1. The result document itself says the denominator exists in SIS

> "Those fields are available at **player/defender grain**, not in this filtered
> team export."

And the subscription inventory, written *before* this screen, recorded it
independently:

> "Pass defense: totals, rates and value. Distinct fields include **coverage
> snaps** … **yards/coverage snap** … Filters cover coverage shell, **defender
> and receiver alignment/position**, route, direction, rushers, pressure, play
> action and motion."

So the missing denominator is not missing from SIS. It is missing from **one
grain of one sub-view**. A screen of the team Totals export cannot license a
conclusion about the player-grain export, and "a separately justified
player-level route/coverage source" reads as though SIS is not one — when the
inventory says it is.

The honest cost is **budget, not availability**: ~200 qualifying defenders per
week against a 200-row cap forces splits by team ID. But that cost is
manageable if the query is filtered rather than broad. **Filtering to a single
alignment returns only the defenders who played that alignment**, a far smaller
set than all defenders, and team-by-alignment coverage snaps are an aggregate —
you never need every defender individually, only the sum.

### 2. The allocation mechanism arguably never needed a rate

This is the more important point, and it is a structural argument rather than a
schema one.

The frozen protocol required coverage snaps because "a receiver allocation law
must distinguish opportunity volume from conditional outcomes." That is the
right requirement **for a per-snap efficiency estimand**. But the quantity a
conditional-allocation mechanism actually consumes is a **composition**, and
compositions are self-normalising.

What the mechanism needs to know is: *does this defense shift targets toward or
away from a given alignment, relative to what you would expect?* That is:

```
ASOE(defense, alignment) =
      observed share of attempts faced at that alignment      ← SIS `Att`, present
    − schedule-expected share given the offenses faced        ← free, Fantasy Points
```

The second term is computable at zero SIS cost from the already-downloaded
Fantasy Points *Separation by Alignment* exports, which give every offense's own
wide / slot / inline route composition. Weight by the opponents actually faced,
strictly prior.

That construction is denominator-controlled — the denominator is total attempts
faced, and the expectation term controls for schedule — and it needs **no
coverage snaps at all**. It is directly analogous to PROE: an observed rate
minus a schedule-adjusted expectation.

**This is not the forbidden substitution.** Swapping `Att` into the frozen
protocol after seeing its schema would be estimand-switching and is correctly
prohibited. ASOE is a *different estimand* with a *different motivation* — that
the model's target is allocation rather than per-snap efficiency — and it
requires its own preregistration. The result explicitly preserves
outcome-blindness ("no performance value, correlation, dependence score or
lineup score was read"), so a fresh protocol starts clean.

### A note on my own earlier finding, so this does not look contradictory

I previously measured receiver alignment concentration and concluded that
individual-defender crossing is too diffuse to support a CB-matchup construct
(WR modal alignment share median 0.673 on a coarse partition; TE 0.542).

That finding was about **individual defender identity**. ASOE is a **team-level**
signal — which alignment the defense as a unit yields to — and requires no
crossing inference at all. The diffuseness result does not bite here.

---

## What is actually lost, and what is not

**Lost:** the cheap team-Totals route to a per-coverage-snap defensive rate.
That is real, and it was the cheapest possible version of the input.

**Not lost:**

- the player-grain SIS route to the same denominator, at higher request cost;
- the ASOE construction, which needs only the `Att` field that *is* present plus
  free Fantasy Points data;
- **the conditional-allocation mechanism itself, which has never been tested.**

That last point deserves emphasis, because three SIS closures in a row invite
the wrong conclusion. What has been tested and failed is: a QB offensive-line
marginal bundle, an RB opponent run-defense marginal column, and now an
*acquisition route to one input*. None of those is the mechanism. **Conditional
allocation — modulating the Dirichlet split by defensive alignment profile,
gated on the G0/G1 dependence scorecard — remains untested.**

Given that G0 measured a QB→WR lift of 3.3228 against a simulated 1.053, and G2
demonstrated that a context-free shared factor mathematically cannot close that
gap, conditional allocation is still the best-motivated open mechanism in the
program. It should not be closed by a schema screen on one export view.

---

## Recommendation

1. **Keep the closure, narrow the language.** Amend the queue consequence to
   scope the closure to the team-grain Totals path, and remove the implication
   that SIS cannot supply a player-level route/coverage source — the inventory
   and the result document both say it can.
2. **Preregister ASOE as a distinct mechanism.** It uses a present field and
   free data, needs no further SIS acquisition, and is denominator-controlled
   by construction. Gate it score-free on the G0/G1 cells, with WR–WR
   must-not-worsen, exactly as proposed for the ledger arm.
3. **Cost the player-grain filtered pull before dismissing it.** One filtered
   query for a single team-season-alignment establishes the real row count and
   therefore the true budget, replacing an assumption with a number. If it is
   affordable, the original denominator-controlled estimand is back on the
   table under a new protocol.
4. **Record in the kill list what was actually killed** — an export route, not a
   mechanism. Otherwise a future session reading three consecutive SIS closures
   will reasonably conclude the whole direction is dead when the central
   hypothesis has never been put to a test.
