# One arm at a time: what it buys, and what it is structurally blind to

Date: 2026-08-13. On whether the sequential single-arm design is missing
something, and what to do about it. **No code was changed.**

---

## What the approach has bought

Worth stating first, because the answer below is not "the method is wrong."

Deterministic, one-arm-at-a-time testing with frozen protocols has given this
project something most modelling efforts never have: **airtight causal
attribution for every individual comparison.** When an arm moves a number, you
know exactly which lever moved it, because everything else was byte-identical.
The mechanism audits, invariant checks and same-image co-runs are not
bureaucracy — they are what makes each verdict trustworthy.

The problem is not rigour. It is **coverage of the design space.**

---

## The blind spot: one-factor-at-a-time cannot see interactions

Sequential single-arm testing measures the effect of X **holding everything else
at its current setting**. That is a *local gradient*, not an effect. If the
effect of X depends on the setting of Y, OFAT will report the effect of X at
whatever Y happens to be — and will report it as though it were the effect of X.

This is not a theoretical concern here. **You have already discovered two large
interactions, both by accident, after paying full price for the sequential runs
that hid them.**

### Interaction 1: feature × copula — **corrected 2026-08-13, see the retraction below**

Eight marginal arms failed the tail gate — route share, fast-role, fitted-K v1,
SCHED, team-QB, SIS QB line, SIS RB run defense, plus the older
`depth_rank_delta` and `team_ol_out`. Several improved MAE, CRPS or held-out
likelihood with clean intervals.

G0 measured a simulated QB→WR lift of **1.053** against a realized **3.3228** —
a near-independent copula.

> **RETRACTED as originally written.** The first version of this section claimed
> that under a near-independent copula "a better marginal cannot propagate into"
> the lineup tail, and that all eight arms were therefore blocked by the same
> hidden factor. That is wrong on the mathematics and wrong on the evidence.
> See §"Retraction and corrected diagnosis" below. The interaction is real but
> it is one of **leverage**, not impossibility, and it explains far fewer of the
> eight failures than claimed.

### Interaction 2: within a single mechanism

G2's WR channel could not activate because a shared factor forces
`corr(WR1,WR2) > 0` whenever it makes both QB→WR correlations positive, and
reality shows WR–WR near independence. The calibration correctly set θ_WR = 0.

That is an interaction *between two cells of one mechanism*, and it was
discovered only by running the arm and reading a zero.

### A third, quieter one

Route share was tested as a LightGBM component feature. TabPFN marginal coverage
is 100%, and the shaper rank-remaps every player onto TabPFN's own quantiles —
so for covered rows the feature can only alter ranks, never the served marginal.
The arm's outcome was conditional on a stage nobody was varying.

---

## Retraction and corrected diagnosis (added 2026-08-13)

Two corrections were raised against the first version of this report. Both are
right, and the second identifies an error in the proposed design that would have
reproduced exactly the ambiguity this report was written to remove.

### Correction 1 — weak dependence reduces leverage, it does not block propagation

The original claim was that under a near-independent copula a better marginal
"cannot propagate" into the lineup tail. That is false. A lineup score is a sum
`S = Σ Xᵢ`; under independence `Var(S) = Σ Var(Xᵢ)`, and fattening individual
upper tails demonstrably fattens the tail of the sum.

Two statements were conflated:

- the sum concentrates **relative to what it would be under positive
  dependence** — true;
- the marginal cannot move the sum's tail — **false**.

The correct statement is about **leverage**: weak dependence reduces the return
on a marginal improvement, because the co-boom multiplier that converts one
player's exceedance into several is absent. That still argues for repairing
dependence first, but on efficiency grounds rather than impossibility grounds.

### The corrected diagnosis is better evidenced than the original

Once the impossibility claim is dropped, the obvious question is whether the
failed arms actually improved the **served upper tail** — the thing the gate
measures. Reading the tail-specific diagnostics back out of the results:

| arm | centre | upper tail (q95 / q99) |
|---|---|---|
| Route Share components | MAE and CRPS better in every fold | exceedance `11.11/7.10/2.69 → 12.04/7.57/3.04` — **worse** |
| Team-QB quality | point MAE `3.63282 → 3.61681` | CRPS and q90/q95/q99 pinball **worse** |
| SIS RB run defense | point MAE `3.8366509 → 3.8268668` | CRPS and all three pinball losses **worse** |
| SIS QB line | Brier-20 and q90 pinball better | q95 and q99 pinball **worse** |
| FP QB shell fit | — | Brier-30, Brier-20 and MAE all **worse** |
| SCHED sync | CRPS `2.6041 → 2.6027`, MAE `3.6328 → 3.6292` | tail-specific pinball not reported |

**Wherever tail-specific pinball or exceedance was reported, it worsened.**

So most of these arms did not fail because a broken copula blocked a good
marginal. They failed for a simpler and more direct reason: **they never
improved the served upper tail in the first place.** They improved central
accuracy and left or degraded the tail, and the gate measures the tail.

This materially changes the standing of the copula-blocking hypothesis: it was
largely **never tested**. SCHED is the only arm with a clean distributional
improvement on both reported metrics, and its q95/q99 behaviour is not in the
record. An arm that improves the served upper tail and *still* fails the lineup
gate would be evidence for blocking; the program does not clearly have one.

### Correction 2 — a factorial must name the channel, not just the feature

The proposed "feature × copula" design is ambiguous, and in the specific case
proposed it is worse than ambiguous.

Route share was tested as a **LightGBM component** feature. TabPFN marginal
coverage is 100%, and the shaper rank-remaps every covered player onto TabPFN's
own quantiles. So for covered rows route share can only alter **ranks** — it is
a copula-channel intervention. Crossing it with a dependence mechanism would
vary *two things in the same channel* and confound them, which is precisely the
failure the report was written to prevent.

The channels are separable in code, so the fix is concrete:

| channel | where the feature is added | what it changes |
|---|---|---|
| **marginal** | `scripts/tabpfn_gen/features.txt` | the served per-player distribution |
| **copula** | `featureset.NUMERIC_FEATURES` | ranks only, for TabPFN-covered rows |

**A valid factorial crosses a dependence mechanism with a *marginal-channel*
feature** — one added to `features.txt` — never with a component-model feature.
Every future protocol should state which channel it varies, in one line, before
anything else.

### A cheaper diagnostic that falls out of Correction 2

`features.txt` contains **none** of the 19 `CANDIDATE_FEATURES`. So **route
share has never been tested in the marginal channel at all** — the closed
component arm tested it in the copula channel. These are different experiments
on the same feature, and the marginal one is untested.

That suggests a better first step than the 2×2: run the **same feature through
both channels** and compare.

- It isolates the channel within a single feature, so nothing else varies.
- It requires no dependence mechanism to exist yet, so it is available now.
- It directly measures how much of a feature's effect is marginal versus rank —
  the exact quantity both corrections turn on.
- It is two arms rather than four.

Route share is the natural subject: it improved composed MAE and CRPS in every
fold, it already has a licensed 2026 shadow, and its copula-channel result is
already recorded, so only the marginal-channel arm is new.

## Two second-order consequences worth naming

**The arm record is not a ranked list.** Each verdict was measured against
whatever the incumbent was at the time — and the incumbent has changed
repeatedly (K=1, CE, role union, per-position calibration, fitted-K,
active-label labels). Arm 3 and arm 12 were evaluated at different points in
configuration space. It is therefore not valid to read the ledger as "route
share < fitted-K"; those are local gradients at different locations, not
comparable magnitudes.

**The final configuration is path-dependent.** Adopting A and then testing B
measures B|A. Had B been tested first, A might not have survived. With roughly
eight adoptions, the current stack is one of many orderings, and nothing in the
record establishes it is the best one.

---

## Three fixes, in order of cost

### 1. Test the dependency graph top-down, prospectively (free)

The stages are ordered: **marginal → dependence → generation → selection →
objective.** A verdict obtained while a downstream stage is broken is
uninformative about the upstream lever.

The project already has the law — *"verdicts don't transfer across a changed
downstream stage"* — but applies it **reactively**, to invalidate old verdicts
after a stage changes. Applied **prospectively** it says something stronger and
cheaper: *do not test features while the dependence stage is known to be
mis-specified.*

Concretely: the current G-series ordering (measure dependence → repair it → then
revisit marginals) is the right order. It was arrived at after eight arms had
already been spent in the wrong one. Make the ordering an explicit standing rule
so the next program does not repeat it.

### 2. The oracle-ceiling diagnostic (cheap — and more useful after the correction, not less)

Before running a feature arm, ask: **would this feature matter if the stage
below it were perfect?**

Impose the *realized* co-exceedance structure — the G0/G1 scorecard — as an
oracle copula, then evaluate the feature under it. You cannot ship an oracle
dependence law, but as a diagnostic ceiling it sorts arms into three buckets
that OFAT currently conflates into one:

1. **did not improve the served upper tail at all** — the feature is dead on its
   own terms, and no dependence repair will rescue it;
2. **improved the served upper tail but not the lineup gate** — genuinely
   blocked; park it for revisit once the copula is repaired;
3. **improved both** — adopt.

The corrected diagnosis above says most of the eight failures are in bucket 1,
not bucket 2 — which is a far more actionable finding than the undifferentiated
pile described in the first version of this report. It also means the ceiling
diagnostic should be run **with the tail-specific metrics reported alongside**
(q95/q99 pinball and exceedance, not only CRPS and MAE), since that is what
separates bucket 1 from bucket 2 and several results omitted it.

### 3. One small factorial where an interaction is suspected (moderate)

Sequential testing needs *k* runs for *k* main effects and gives zero
interactions. A 2×2 factorial needs 4 runs and gives 2 main effects **plus their
interaction**.

The specific design worth running: once a dependence mechanism passes its
score-free gate, do not test it alone. Run

|  | marginal-channel feature off | marginal-channel feature on |
|---|---|---|
| **copula repair off** | current incumbent | main effect of the feature |
| **copula repair on** | copula effect alone | **the cell that matters** |

Four panels, and the bottom-right cell directly measures the quantity the entire
program has been implicitly assuming.

**Two constraints from Correction 2, without which this design is invalid:**

- The feature must be added through the **marginal channel** —
  `scripts/tabpfn_gen/features.txt` — so that it and the dependence mechanism
  are varying different things. A component-model (`NUMERIC_FEATURES`) feature
  is a copula-channel intervention and would confound the two factors.
- The top-right cell must be **run, not assumed**. The first version of this
  report marked it "already known: null" from the closed component arm. That
  arm varied the *other* channel, so it does not populate this cell.

Sequencing note: run the two-arm channel comparison in §"A cheaper diagnostic"
first. If route share turns out to have no marginal-channel effect either, this
factorial should use a different feature — or not run at all.

---

## What already exists that you have not mined

Fourteen candidate panels exist on common slates. Fitting

```
weekly_max ~ arm factors + slate effects
```

across all of them extracts main effects **and any interactions the existing
design happens to identify**, from sunk cost, with no new compute. It also
yields the between-arm variance — the empirical answer to "how big must an
effect be before we should believe it," which every gate has needed and none has
had.

This is §6.4 of the forensic plan and it should be promoted: it is the cheapest
interaction information available, and unlike everything else here it requires
no new runs.

Two constraints to preregister: the fourteen panels are the arms that were
*chosen* to be launched, so pooling inherits that selection; and this may not be
used to revive any rejected arm — its output is a variance estimate and an
interaction map, not a re-adjudication.

---

## Summary

The scientific process is not the problem, and it should not be loosened. What
should change is what gets varied:

1. **Name the channel in every protocol.** One line stating whether the arm
   varies the served marginal (`features.txt`) or the rank structure
   (`NUMERIC_FEATURES` / a dependence mechanism). Without it, "we tested route
   share" is ambiguous between two different experiments — which is how the
   closed component arm came to be treated as though it had settled the
   marginal question.
2. **Report tail-specific metrics on every arm.** q95/q99 pinball and exceedance
   alongside MAE and CRPS. Several results omitted them, and they are the only
   thing that distinguishes "did not improve the tail" from "improved the tail
   and was blocked."
3. **Run the two-arm channel comparison** — the same feature through both
   channels — before any 2×2. Two runs, available now, and it measures the
   quantity both corrections turn on.
4. **Order matters, on efficiency grounds.** Test the stage that gates the
   others first. Not because downstream breakage makes upstream arms
   meaningless — Correction 1 shows it does not — but because it lowers the
   return on them.
5. **Ask the ceiling question before spending a panel**, and use the three-bucket
   version: dead, blocked, or adopt.
6. **Use a 2×2 only where an interaction is the actual question**, with the
   marginal-channel constraint above.
7. **Mine the fourteen panels you already paid for**, for the between-arm
   variance and whatever interaction structure is identifiable.

And record with every verdict *which incumbent it was measured against*, so the
ledger reads as what it is — a set of local gradients — rather than as a ranking
it was never designed to produce.

---

## Amendment log

**2026-08-13 (second amendment).** Review of this report identified a further
error, accepted in full: the "eight marginal arms" list both miscounts (nine
items are named) and **conflates channels — the exact error this report argues
against.** Route Share components was primarily a rank/copula intervention
after TabPFN remapping; fitted-K is a within-team allocation/dependence law;
fast-role included a candidate-belief generation mechanism. Only the remaining
feature/cache arms varied player marginals. **No pooled "eight-arm marginal
failure" conclusion is valid.** The corrected diagnosis below — that most arms
never improved the served upper tail — survives only for the arms that
genuinely varied marginals, and may not be asserted over the whole list.

Two consequences: the claim that "only the marginal-channel arm is new" in
"A cheaper diagnostic" is **wrong** — the historical Route component result
predates the repaired allocation and active-only cache lineage and cannot
populate a current-stack copula cell, so **both** cells of that comparison must
be run. And the tail table below mixes raw exceedance (a calibration statistic)
with pinball losses (a proper score) as one evidence class; pinball should carry
the argument. Full detail:
`reports/2026-08-13-multiseed-factorial-implementation-review.md` §1.

**2026-08-13.** Section "Interaction 1" retracted as originally written and
replaced by "Retraction and corrected diagnosis." The claim that a weak copula
makes marginal improvement impossible was wrong; the effect is on leverage, not
possibility. The evidence table added there shows most failed arms never
improved the served upper tail, so the copula-blocking hypothesis was largely
untested rather than confirmed. Recommendation 3 was corrected to require a
marginal-channel feature and to stop treating its top-right cell as already
known. The ceiling diagnostic was extended from two buckets to three. Both
corrections originated in review of the first version and are adopted in full.
