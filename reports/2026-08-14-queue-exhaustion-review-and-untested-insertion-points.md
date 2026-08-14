# Queue exhaustion: agreement, a missing dimension, and ceiling design notes

Date: 2026-08-14. Response to the assessment that no historical mechanism
remains. **No code was changed. No outcome was queried.**

---

## 1. Agreement

The registered mechanism queue is exhausted **within its taxonomy**, and the
sequencing is right: the recourse ceiling belongs in the one-time forensic run
rather than as another historical arm, and any strategy that follows must be
prospective and outcome-unseen.

The construction described — retain each incumbent entry's locked early core,
permit only legal late-player replacements, optimize against realized scores
solely to measure maximum option value — is exactly the bound intended.

## 2. The qualification: the taxonomy has a missing dimension

The four categories are:

| category | what it varies |
|---|---|
| marginal channels | beliefs about a player's own distribution |
| dependence channels | beliefs about how players co-move |
| selection / portfolio | which members of a **fixed feasible set** to field |
| data acquisition | inputs to the above |

Every one is a question about **beliefs**, or about **choosing within a fixed
feasible set**. None is a question about the **shape of the decision itself**.

That is precisely why recourse was not in the queue. It was not considered and
rejected — it was *unrepresentable* in the taxonomy, and it arrived from outside
it. So "nothing further is queued" is true of the categories, and the categories
are incomplete.

**Other members of the same dimension, none tested:**

- **Per-contest portfolio slicing.** Roughly three qualifiers at fourteen
  entries plus four Millionaire seats currently receive one book, selected at
  one line. A 14-entry small-field qualifier and four seats in a 161,764-entry
  Millionaire have different optimal target lines and radically different
  uniqueness requirements. `entries_curve.p_reach(N, line)` already exists to
  price this.
- **Entry-count allocation across weeks.** Seventeen weeks are optimised as
  seventeen independent one-shots. With a season bankroll and a top-heavy payout,
  the optimal risk profile and entry volume vary with position in the season and
  with slate quality. Nothing allocates across weeks.
- **The field / payout objective.** Still unbuilt, gated on 2026 standings, and
  still the only proposal that changes what is being optimised rather than what
  is believed.

### 2.1 The members, developed

**Per-contest slicing.** The current book is 80 entries selected at line 194 and
served to every contest. But a 14-entry qualifier and four seats in a
161,764-entry Millionaire are different problems. In a small field, a 194 score
frequently wins; in the Millionaire it is a min-cash. Selecting one book at one
line for both guarantees it is wrong for at least one.

The deterministic version needs no new modelling: select the Millionaire seats
from the already-frozen 220→210→200 lexicographic extreme book, and the
qualifier entries at a lower line, using `entries_curve.p_reach(N, line)` to set
each line from that contest's actual field size. It is a policy change, testable
prospectively on 2026 outcomes, and it costs nothing to implement.

**Cross-week allocation.** Seventeen weeks are optimised as seventeen
independent one-shots with a fixed entry count. Two things are being left on the
table.

The first is *volume*: if slate quality is predictable pre-lock — game count,
implied totals, total dispersion — then entering 150 on a high-ceiling slate and
20 on a poor one dominates entering 80 on both, at equal season cost. The
regime analysis in the forensic plan produces exactly the labels this needs.

The second is subtler and I think more interesting: **the seventeen weekly
portfolios are themselves a portfolio, and they are highly correlated.** If the
model has a systematic tilt — and after this many arms it certainly has several
— then every week is the same bet re-expressed. For an objective that needs *one*
extraordinary week per season, that is the wrong construction: you want the
seventeen weeks maximally **decorrelated in style**, so that at least one aligns
with whatever regime the season actually produces.

Nobody does this, and it is a genuinely different framing: diversification
across time rather than across entries. It would show up as deliberately
varying construction between weeks — stack shape, salary distribution,
chalk exposure — rather than applying one optimal recipe seventeen times. Note
it directly opposes the instinct to find "the best configuration" and run it
every week, which is what the entire arm program has been searching for.

**Contest selection.** Which contests to enter is itself an unoptimised
decision. Field size, payout shape and entry fee determine the target line and
the uniqueness requirement, and the system has no model that maps its own
book's characteristics onto "which contest is this book best suited to win."

**Recommendation:** enumerate this dimension deliberately in the forensic
opportunity register rather than treating recourse as a one-off discovery. A
taxonomy that cannot express a category will keep reporting exhaustion.

## 3. Fantasy Points and SIS: one insertion point was tested, not two

Little came out of either source, and the marginal-channel closure is correct
and well evidenced. But it is worth being precise about *how* they were used.

**Every arm on both datasets asked the same question:** does this field improve
a player's projected distribution? Route share, route rank, R2 shrinkage,
coverage fit, same-season coverage, QB shell, advanced prior, advanced
receiving, team context, pass-tail, run-tail, TE hub — all of them insert at
the player-belief layer.

**The untested insertion point is pool admission.**

The candidate pool is currently built by the optimizer over salary and
projection. Nothing in the system uses route participation, charting volume or
any vendor field to *admit* a player who would otherwise never be built. A hard
eligibility rule — for example, any player above a frozen route-share threshold
becomes pool-eligible regardless of projection — is a **generation-layer**
mechanism, not a marginal feature.

Why this is worth distinguishing:

- Generation is the layer both the L-decomposition and the missing-winner audit
  indict. **33 of 612 winning player-slots were absent from the candidate pool
  entirely**, averaging `7.19` projected against `22.74` actual — a `+15.55`
  surprise.
- The earlier outcome-viewed measurement found cheap high-route-share players
  clear 20 points at roughly **ten times** the rate of cheap low-route-share
  players *at the same salary* (≤$3,500: 4.48% versus 0.42%).
- Those are plausibly the same population. A projection-based pool never admits
  them, because their projection is exactly what is wrong.

This is not a new dataset, a new acquisition, or a reopening of a closed arm. It
is data already held and already screened, applied at a layer it has never
touched. A closed *feature* verdict does not transfer to an *eligibility* rule,
in the same way the project's standing law holds that verdicts do not transfer
across a changed stage.

It should be preregistered as a generation-layer mechanism with its own frozen
threshold, an explicit statement that it is not a marginal retry, and — given
the current closure posture — treated as a prospective 2026 candidate rather
than a new historical arm unless the forensic L-decomposition shows the
universe layer dominating.

### 3.1 Why a closed feature verdict does not transfer here

A feature and an eligibility rule act through different mechanisms and are
judged by different quantities:

| | marginal feature | pool-admission rule |
|---|---|---|
| what it changes | a player's projected distribution | whether he can be built at all |
| how it acts | continuously, on every player | discretely, on a small admitted set |
| how it is judged | CRPS, pinball, Brier on all rows | presence of winner-class players in the pool |
| failure mode | improves centre, misses tail | admits noise, dilutes the candidate budget |

Route share as a *feature* nudges a player's mean by a fraction of a point,
which the served TabPFN marginal then largely overwrites. Route share as an
*admission rule* does something a feature cannot: it puts a player into the
feasible set who was never a candidate, at any projection.

That distinction matters because the failure the pool exhibits is **binary
absence**, not mis-ranking. Those 33 winner slots were not ranked too low — they
were not present.

### 3.2 The cheap bound that decides it — analogue of the recourse ceiling

Before building anything, run the retrospective admission check. It is one
query and it sizes the entire idea:

> For each of the 33 winning player-slots absent from the candidate pool, and
> for the broader 36 omitted slots across 28 winner weeks, compute their
> strictly-prior route share. Then ask: **what fraction would a frozen
> route-share floor have admitted?**

Three outcomes, all decisive:

- **Most would have been admitted** — the rule targets exactly the missing
  population and the idea is worth building. The measured 10× lift in 20-point
  rate among cheap high-route-share players predicts this.
- **Few would have been admitted** — the missing winners are not
  high-route-share players, the mechanism does not target them, and the idea
  closes for one query.
- **Many would have been admitted, along with hundreds of others** — the rule
  works but its selectivity is poor, and the follow-up question is what second
  condition tightens it without losing the winners.

This belongs in the forensic program: it is outcome-viewed by construction, it
needs no new data, and like the recourse ceiling it can retire a direction
cheaply rather than after a build.

### 3.3 Design constraints if it is built

- **The threshold must be frozen before the check in §3.2 is read**, or the
  bound becomes the tuning surface.
- **Admission must be budget-neutral.** Adding candidates without removing any
  is an added-budget arm, and the CE and role unions established that added
  budget must be discovery evidence only. Admit the route-share set *in place
  of* an equal count of the lowest-yield `lev` candidates — which the
  leave-one-out evidence already identified as the cheapest budget to spend.
- **It composes with the salary floor, and may conflict.** The $49,000 floor
  pushes toward expensive players; an admission rule aimed at cheap
  high-participation players pushes the other way. Whether they compose or
  fight is an empirical question that should be measured, not assumed.

## 4. Design notes on the recourse ceiling being implemented now

### 4.1 Compute two numbers, not one — this is the important one

The perfect-hindsight ceiling optimises late slots knowing the **realized** late
game scores. That is a valid upper bound, but it is optimistic in a way no
policy can approach: it assumes knowledge of the outcomes of the very games
being swapped into.

The decision-relevant quantity is **realistic recourse** — optimise the late
slots knowing the realized **early** results but only the **simulated
distribution** for the late games. That is what an actual Sunday policy could
achieve.

Report both. The gap between them is the structurally unattainable portion.

Without this, a large hindsight ceiling will read as an enormous opportunity
that is mostly unreachable, and the register will carry a number nobody can
convert.

### 4.2 The structure is multi-stage, so a two-stage bound understates it

Lock at 1 p.m., then 4:05/4:25 kickoffs, then Sunday night. A 4:25 player is
swappable until 4:25; an SNF player until roughly 8:20. That is up to **three**
decision points, not two.

A two-stage bound is therefore itself a lower bound on the true ceiling. Either
compute the full multi-stage version or state explicitly that the reported
figure is conservative.

### 4.3 Partition by actual kickoff time, not a fixed rule

The early/late split varies week to week — some slates carry many 4:25 games,
some almost none. Derive each slate's partition from `schedules` relative to
that slate's own lock, exactly as the injury `slate_lock_at` reader does, rather
than applying a fixed assumption.

### 4.4 Enforce cap legality at swap time

A swapped lineup must remain under the salary cap and positionally legal at the
moment of the swap. A bound that ignores this is not achievable and will
overstate the ceiling.

### 4.5 Report live-entry counts per stage — free, and it sizes the mechanism

For each slate and each decision point, report how many of the 80 entries are
still capable of reaching each threshold given their locked early core.

If 78 of 80 are already dead by 4 p.m., the option is worth little regardless of
what the ceiling says. If 20 remain live, the mechanism has real room. This
costs nothing beyond what the ceiling computation already loads, and it is the
diagnostic that explains *why* the ceiling is whatever it turns out to be.

### 4.6 Report against the threshold grid, not only the mean

The objective is the tail. A ceiling expressed as mean weekly-maximum
improvement will understate or overstate depending on where the option value
lands. Report the full `240/230/220/210/200/194/187` grid for both the hindsight
and realistic variants, and the count of **distinct** slates improved — the
nested-threshold caution from the pass-tail review applies here too.

---

### 4.7 What a real policy would look like, if the ceiling is material

Worth sketching now, because it determines what the ceiling should measure.

A recourse policy is not "re-run the optimizer at 4 p.m." It has three parts:

1. **A liveness rule.** At each decision point, classify each entry by the
   maximum score still reachable given its locked core. Entries that cannot
   reach the target line are dead and their remaining slots are free options.
2. **A concentration rule.** Spend the freed slots on the *live* entries —
   raising their ceilings — rather than spreading improvement evenly. This is
   the step a greedy re-optimizer misses: it treats all 80 entries as equally
   worth improving when nine in ten are already out of contention.
3. **A first-stage construction rule** that anticipates 1 and 2: polarised early
   risk, late slots reserved for optionality, and salary deliberately withheld.

The ceiling computation should therefore report **per-stage liveness** (§4.5)
not as a curiosity but because it is the input to step 1, and it determines
whether steps 2 and 3 have anything to work with.

## Summary

Agree that the mechanism queue is exhausted and that the recourse ceiling
belongs in the forensic run.

Two additions worth carrying: the taxonomy lacks a **decision-structure**
dimension, of which recourse is the first member found and per-contest slicing,
cross-week allocation and the payout objective are the others; and both paid
datasets were tested at exactly **one** insertion point, with **pool admission**
untested and pointed at the layer the evidence indicts.

For the ceiling itself, the one change that matters is reporting **realistic
recourse alongside perfect hindsight**. Everything else is bookkeeping.
