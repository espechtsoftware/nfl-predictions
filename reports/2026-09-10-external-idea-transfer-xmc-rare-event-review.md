# Review: four external ML ideas against the corpus-selection problem

Date: 2026-09-10
Status: review only. No code changed, no outcome queried, no protocol amended.
Evidence boundary: the historical figures below are development evidence.
Nothing here licenses an adoption; that requires frozen prospective shadows.

Four ideas were proposed from outside the project — XMC multi-modal anchors,
AI-boosted rare-event sampling, EDGE/Guideline-Effectiveness data selection, and
beta-separation clustering. The question asked was whether they help us select
high-scoring lineups from a corpus.

## Bottom line

| # | Idea | Verdict |
|---|---|---|
| 1 | XMC visual + structural-graph anchors | **No.** Visual half inapplicable; graph half already covered and aimed at the wrong layer |
| 2 | Rare-event sampling by clone-and-perturb | **Right layer, wrong mechanism, and currently infeasible** — see §4 |
| 3 | Guideline Effectiveness / EDGE selection | **No** as stated; its useful analogue is already the queued prop/pick'em work |
| 4 | Beta-separation "cannot-link" clustering | **No**, and it is specifically warned against in our own corpus review |

None of the four should displace anything currently queued. The most useful
thing in this review is not the verdicts but **§2 — the one-question test that
produced them**, which is reusable on the next batch of external ideas.

## 1. The test that sorts all four

> **Does the idea change the score matrix, or does it re-process a fixed score
> matrix?**

Ideas 1, 3 and 4 re-process. They are retrieval, data-selection and cluster-
separation methods that assume the hard part is *finding* the right item among
many. Idea 2 is the only one that touches how the underlying scenarios are
produced.

That distinction decides the question, because of what our own measurements say
the failure actually is.

## 2. What the measurements say

From `reports/2026-08-27-r6-corpus-selection-deep-review.md`:

**The corpus almost never contains a winner.** Across 51 slates with a governed
comparable winning score, the full R6 corpus reached or beat the recorded winner
**once**. Mean oracle-minus-winner was **-30.03** points.

**Retrieval is a real but smaller problem.** The corpus held a 200-point lineup
on 29 of 54 slates; the union of all eight 80-entry books found one on **10** of
those 29, and the best single book on 7. At 230 the corpus supplied only three
opportunities and the union converted two.

**Two empirically distinct miss modes were identified**, and the dominant one is
not a selection problem:

- **Model-support failure.** Lineups that later scored enormously looked *weak*
  in the 50,000 discovery worlds. `2023-w03 588c…` scored **239.96** with
  simulated mean rank **3,106** and exactly **one** simulated >230 event.
  `2025-w09 4531…` scored 234.34 at mean rank 1,696. The drivers are marginal
  misses of a size no reweighting reaches — De'Von Achane simulated mean
  **2.60**, realized **54.3**; Brock Bowers 11.11 → 46.3; Drake London
  14.76 → 41.8.
- **Portfolio crowding.** A visible candidate (rank 255) whose simulated success
  overlapped scenarios the book already covered, so its marginal gain fell below
  the pick-80 cutoff.

The review's own conclusion on mode 1 is the sentence that governs three of the
four ideas:

> "No selector operating only on these same worlds can consistently recover
> lineups to which the model assigns negligible or incorrectly shaped tail mass.
> Adding another algebraic transformation of the same score matrix is unlikely to
> cure this class."

And on mode 2, it is explicit that separation-style fixes are the wrong tool:

> "Do not use roster overlap, DPP diversity, or a no-good archive as a substitute
> for simulated outcome quality."

**The most recent selection result reinforces the pattern.** PREREG-076
`UNION_EMAX` selected across the union of two nearly disjoint generators and
raised mean weekly K80 maximum by **+3.7781**. It moved weeks >=194 from 6 to 10
and >=200 from 4 to 7 — and produced **no increase at 210 and no 220/230 week in
either arm.** Recombining and reselecting existing supply moves the shoulder and
leaves the extreme untouched. That is the same signature CBWU-OI showed.

## 3. Ideas 1, 3 and 4

**Idea 1 — XMC multi-modal anchors.** The visual-metadata component has no
referent here; there are no images in the lineup space. The structural-graph
component is real football structure — team, game, stack — but we already build
and measure on exactly that (pair reach, QB-stack-core reach, dominant-game
reach, archetype clustering). More importantly, XMC is a *retrieval* advance: it
helps rank a correct-but-buried label. Our winners are not buried in the ranking;
they are assigned negligible tail mass, and on 50 of 51 slates they are not in
the corpus at all.

**Idea 3 — Guideline Effectiveness.** As stated this does not transfer: there is
no agent consuming human instructions in lineup selection. The nearest honest
analogue is inverted and interesting — *identify slates where an external
information source disagrees with the model, on the theory that the model is
missing context there.* That is a reasonable idea, and it is already the queued
work: the pre-lock prop-odds coverage requirement in
`reports/2026-09-05-selection-sweep-and-prop-odds-universe-plan.md`, and the DFS
pick'em desk-ecology recommendation (N3) in the 2026-09-03 selection-gap review.
The football-native version is more specific than the generic one and is further
along.

**Idea 4 — beta-separation clustering.** This is the clearest miss. It proposes
expanding statistical contrast between overlapping records via cannot-link
constraints. Mapped here that is roster/feature-space repulsion, which our own
corpus review names and rejects as a substitute for outcome quality, and which is
already on the tested-or-queued list alongside DPP and ordinary quality-diversity.
It would act on mode 2, the smaller problem, using the specific tool that mode-2
analysis rules out.

## 4. Idea 2 deserves a longer answer

It is the only one aimed at the right layer, and it is worth being precise about
why it still does not help yet.

**4.1 It is currently infeasible on this engine, and that is already documented.**
`reports/2026-08-17-dst-shadow-and-rare-event-feasibility-audit.md` asked exactly
this question and answered it:

> "Does the current simulator expose a sufficient restart/checkpoint state?
> **No.** There is no public step/snapshot/restore API, independent per-world RNG
> or weight ledger."
>
> "Verdict: the current engine cannot support adaptive multilevel splitting,
> conditional SMC or likelihood-ratio importance sampling with a defensible
> claim that the samples target the unchanged production law."

Clone-and-perturb *is* adaptive multilevel splitting. The proposal's core
operation — take a trajectory that is heading toward an extreme, duplicate it,
perturb it, and discard the average ones — requires serializable trajectory state
that does not exist. This is a prerequisite engineering project, not a runnable
arm.

**4.2 The summary omits the step that makes it valid.** "Discards the standard,
average data paths" is only legitimate if the surviving paths carry importance
weights. Drop the weights and you have silently changed the target law, which is
precisely how CE, Gumbel and Schaake failed here. Our R6 review already states
the correct form: *"Samples must retain likelihood/proposal weights; tilted worlds
cannot be counted as ordinary equal-probability worlds."*

**4.3 The deeper point: it fixes variance, not misspecification.** This is the
part worth carrying forward regardless of feasibility.

Adaptive splitting estimates `P(X > t)` **under a given law** with far lower
variance. It does not move where that law puts its mass. If the simulator centers
De'Von Achane at **2.60** and he scores **54.3**, no amount of efficient tail
sampling from that distribution produces the world that mattered. Splitting
finds the upper tail of the model you have; our measured defect is that the
model's tail is in the wrong place — too fat in the shoulder, too thin at the
extreme, from an under-coupled hub.

**Where it would genuinely help, and this is real:** tail *rank precision*. With
seven 230-point lineups across three slates and single-digit simulated event
counts, ranking candidates by `p230` is dominated by Monte Carlo noise — a
candidate with a true 7 events versus 12 can flip on resampling alone, and the
pick-80 cutoffs in the review are exactly that size. Splitting would make those
rankings much more reliable.

That is a second-order benefit against a first-order problem. It sharpens
selection among candidates when the measured dominant failure is that the
winning candidate was never generated on 50 of 51 slates.

## 5. What is salvageable

One element, and it is already ours. The proposal's useful kernel is not
"clone trajectories" but *"identify the specific paths that lead to extreme
outcomes and generate more of those."* The football-native form of that is
already the recommended direction in the R6 review — a **mixture of calibrated
proposals tailored to distinct extremal modes** (breakout, game-environment,
role-uncertainty), with likelihood weights retained — and in the 2026-09-03
review's N1, **covariate-conditioned extremal dependence at the role/team-game
unit**.

Both are more specific than the generic method and neither needs simulator
restartability. If the goal is "put tail mass where the model currently has
none," those are the live routes.

## 6. A reusable intake filter

These four arrived as generic ML advances. Sorting them took four questions, and
the same four will sort the next batch faster:

1. **Does it change the score matrix, or re-process a fixed one?** Re-processing
   methods address our smaller problem and have repeatedly moved 194/200 while
   leaving 210+ flat.
2. **Does it assume the target is present but hard to find?** Most retrieval and
   separation advances do. Ours is usually absent — 1 of 51.
3. **If it reweights or tilts scenarios, does it retain likelihood weights?** If
   the description does not say so, it is proposing a biased estimator.
4. **Does it require simulator capabilities we have?** Restartability, per-world
   RNG and a weight ledger are all currently absent.

An idea that fails 1 and 2 is aimed at the wrong layer regardless of how strong
it is in its own field.

## 7. Recommendation

Do not queue any of the four. Nothing here should displace the prop-odds
universe work, the covariate-conditioned extremes law, or the stage-gated
population experiment the R6 review recommends — all of which target the
population problem these ideas mostly do not.

If rare-event sampling is wanted eventually, the honest sequence is: build and
prove a restartable research kernel with a weight ledger **first**, as a declared
engineering project with its own budget, and only then evaluate splitting as a
tail-precision improvement — not as a cure for model misspecification.
