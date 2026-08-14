# Something fundamentally different: recourse-aware portfolio construction

Date: 2026-08-14. A proposal for a direction no visible competitor takes.
**No code was changed.**

---

## 1. Why the envelope is where it is

Every serious NFL DFS operation — this project included — runs the same stack:
project players → simulate correlated worlds → optimize lineups → model
ownership → simulate the contest. The differences between operations are
quality differences within a shared frame.

This project has now pushed that frame close to its limit and has the evidence
to prove it:

- **selection is saturated** — selected counts equal the pool oracle at 220,
  230 and 240;
- **the marginal channel is closed** — a dozen arms, including the best-screened
  tail-shaped input available;
- **the dependence deficit was largely an artifact** of the `(game, team)`
  allocation-unit bug repaired in `26e73c5`;
- and the pool oracle itself sits **~57 points short** of the winning line, with
  33 of 612 winning player-slots absent from the candidate universe entirely.

The last point is the one that matters. **The feasible set is the constraint.**
No selector improvement helps when the best available lineup is 57 points short,
and no marginal improvement has moved it.

So the question is not "how do we optimize better." It is "how do we make the
feasible set larger."

## 2. The idea: treat the slate as a two-stage stochastic program with recourse

**A DraftKings Classic entry is not a fixed roster. It is a policy.**

You submit at the 1 p.m. lock, but every player in a 4:05, 4:25 or Sunday-night
game can still be swapped. So the actual decision is:

- **Stage 1 (1 p.m.):** choose 80 partial rosters, with early-game slots
  committed and late-game slots provisional.
- **Information arrives:** the 1 p.m. games play out. You now know which of your
  80 entries are alive and which are dead.
- **Stage 2 (4 p.m., then 8 p.m.):** re-choose the late-game slots on every
  entry, conditional on what happened.

That is a textbook two-stage stochastic program with recourse. The first-stage
decision should be chosen to maximize the **expected value of the optimal
second-stage decision** — not to be optimal on its own.

**Nobody does this.** Late swap is universally available as a tool — SaberSim,
Stokastic and FTN all ship one — and it is universally framed as
*re-optimization after the fact*: "pre-lock builds establish exposures… late
swap builds on that foundation." That is sequential-greedy. **The first stage is
never chosen with the second stage's option value in the objective.**

That gap is the opening.

## 3. Why this specifically attacks this project's bottleneck

**Recourse expands the feasible set, which is exactly the layer that binds.**

With 80 fixed rosters you can field 80 outcomes. With 80 *policies*, each
holding four late slots that can be re-chosen across, say, a dozen materially
different early-game branches, the set of reachable final rosters is an order of
magnitude larger — at the same entry count, the same salary cap, and no new
data.

This is not a selection improvement. Selection is saturated and this does not
touch it. It is a **generation-layer** expansion, and generation is the layer
the L2 decomposition and the missing-winner audit both point at.

There is a second, sharper effect. At 4 p.m. roughly nine in ten entries are
already dead — their early players busted and no late-slot choice reaches 240.
Their late slots are **free options**. The live entries are precisely those
whose early portion boomed, which is the conditional world where a 240 is
actually reachable. So recourse lets you **concentrate your remaining degrees of
freedom on the branch where the tail exists**, which a one-shot build cannot do
at any level of sophistication.

That is a structural answer to "we need one lineup to be extraordinary."

## 4. Three implications that contradict current practice

If this is right, recourse-aware construction should look *wrong* by one-shot
standards. Each of these is a testable prediction, and I would preregister them:

**4.1 Deliberately concentrated early risk.** One-shot optimization balances a
roster. Recourse wants entries that are decisively alive or decisively dead by
4 p.m. — high-variance early portions — because a "medium" entry wastes its
late-slot option. Expect optimal Stage-1 builds to look more polarized than the
incumbent's.

**4.2 Reserved late-game flexibility.** Stage-1 late slots should be chosen for
*optionality*, not projected points — cheap, positionally flexible placeholders
in games that lock last. The incumbent optimizer treats every slot identically.

**4.3 Deliberate salary underspend at Stage 1.** Unspent salary is a call option
on an expensive late-game player, exercisable once you know you need a ceiling.
**This directly contradicts the adopted $49,000 salary floor**, which is a
production rule justified by one-shot evidence. If the recourse framing is
right, that rule is optimal for the wrong problem. That tension is worth
surfacing explicitly rather than discovering it mid-experiment.

## 5. It is backtestable on the existing panel with zero new data

This is the part that makes it worth doing rather than admiring.

Everything required is already in the warehouse:

- schedule kickoff times, to partition each slate into early / late / SNF;
- realized player scores, to resolve Stage-1 outcomes exactly;
- the existing candidate generator and selector, to run both stages;
- the same 107 slates, actuals and tail-first decision law.

The historical experiment is exact and honest: build at Stage 1 using only
pre-lock information, reveal the *realized* early-game scores, re-optimize the
late slots under the unchanged selector, and score the final book. No new data,
no vendor, no acquisition. The only thing that changes is the shape of the
decision.

A cheap precursor that sizes the whole idea before any optimizer work:
**compute the recourse ceiling.** For each historical slate, take the incumbent
80 entries, freeze their early-game players, and hindsight-optimize the late
slots against realized scores. That is an upper bound on what perfect recourse
would have delivered. If the ceiling is a point or two, the idea dies for the
cost of one query. If it is ten or twenty points on the weekly maximum, it is
the largest single opportunity the project has found.

**Run that bound first.** It is one hindsight MILP per slate over roughly four
slots, and it decides everything downstream.

## 6. Honest risks

- **Operational.** Recourse requires being present and executing swaps at 4 p.m.
  and again at 8 p.m. every Sunday. A strategy that is only optimal when
  executed reliably is worth less than its backtest.
- **The ceiling may be small.** If most slates concentrate their scoring in
  early games, there is little to re-optimize. The §5 bound answers this cheaply
  and it should be run before anything is built.
- **Two-stage optimization is genuinely harder.** The second stage is small
  (four slots), but the first stage's objective becomes an expectation over
  branches, which is a real modelling and compute cost.
- **The field also late-swaps**, so some of the edge is competed away. But the
  field swaps *greedily*; the claim here is about first-stage construction,
  which is where the asymmetry sits.
- **It does not fix the missing-winner problem.** 33 winning player-slots were
  absent from the pool entirely; recourse enlarges the reachable set from the
  pool, not the pool itself.

## 7. A second idea, briefly: generative role states rather than point forecasts

If recourse does not pan out, the other genuinely different framing is to model
**what job a player has**, not how many points he scores.

Everyone models points. A +15.55-point surprise on a $4,128 player is almost
never a distributional tail on his current role — it is a **role change**: he
became the alpha because someone left in the first quarter, or the offense
shifted. Modelling role occupancy as a discrete latent state with transition
probabilities, and points *conditional* on state, puts explicit probability mass
on "this cheap player becomes the primary option" in a way a points model
smooths away.

This is distinct from the role *features* and role-belief candidates already
tested: those condition on an observed role, whereas this generates the role
distribution itself. It targets the missing-winner-slot finding directly.

I would rank it second. Recourse is more novel, more clearly matched to the
measured bottleneck, and — decisively — comes with a cheap upper bound that can
kill it in one query.

---

## Recommendation

Run the §5 recourse ceiling as a hindsight bound on the existing panel. One
MILP per slate over the late-game slots, no new data, no acquisition, and it is
outcome-viewed so it belongs naturally inside the forensic program rather than
as an arm.

If the bound is material, this is the direction — and unlike anything else
remaining, it changes the shape of the decision rather than the quality of an
estimate.

---

## Sources

- [NFL DFS Late Swap Strategy — Stokastic](https://www.stokastic.com/nfl/nfl-dfs-late-swap-strategy-with-stokastics-nfl-dfs-sims-ac11/)
- [How to Leverage NFL DFS News & Late Swap — Stokastic](https://www.stokastic.com/news/how-to-use-nfl-dfs-news-late-swap-to-create-roi-lineups-ac11)
- [Using Late Swap — SaberSim](https://support.sabersim.com/en/articles/12079563-using-late-swap)
- [Multi-objective stochastic linear programming with recourse](https://arxiv.org/pdf/2407.04602)
