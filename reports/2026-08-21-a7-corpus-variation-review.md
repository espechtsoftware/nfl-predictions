# Review: A7 corpus rank-fusion variations v1

**Date:** 2026-08-21. **Role:** review only — no code changed, nothing
run, no protocol edited. **Reviewed:**
`reports/2026-08-21-a7-corpus-rank-fusion-variations-v1.md`
(run `20260821-a7-corpus-rank-fusion-variations-v1`, code parent
`b8234f9`), against the sealed A7-v2 result and this review file's
earlier addenda.

## Summary judgement

The *engineering* of this protocol is excellent and the *honesty* is
exemplary — it labels itself `retrospective-post-outcome-exploratory`,
holds every license false, forbids follow-up grids and retries, and
permits exactly one downstream use. The two-phase boundary (construct
selections under a score-free projection, commit, only then open
`candidate_actual_scores` once) is the strongest post-outcome discipline
I have seen in this repository.

My concerns are not about rigor. They are about **what this experiment
can possibly discover**, and about two specific rules that I think point
the nomination in the wrong direction. Suggestions are ordered by how
much they would change the outcome.

---

## 1. The achievable range is probably very small, and is knowable before scoring

The sealed A7 result reports **48 of 54 slates tied** at N=80 between
control and treatment, with 4 better and 2 worse. Ties in weekly maximum
that pervasive mean the two books' *top-scoring* lineups are largely the
same rosters.

Every one of the seven challengers is a deterministic fusion of those
two orders. DS25/50/75 swap `k = ceil(d/4 · j)` members; RB25/50/75
re-rank the union `U = C ∪ T`; A7-100 is `T` itself. So the entire grid
lives inside the span between two books that already agree on
seven-eighths of their weekly outcomes. If `d` is small, the exercise
explores a correspondingly small space, and no fusion can reach a lineup
that neither order surfaced.

**Suggestion:** `freeze-selections` already computes `d` per slate and
the protocol already requires reporting min/mean/max control-book swaps.
Report those **before** running `score`, and state a pre-committed
reading: if the mean swap count is small (say under ~5 of 80), the
diagnostic's own conclusion should be "the fusion space is too narrow to
distinguish these laws" rather than a nomination. That costs nothing,
uses only score-free information already computed in phase 1, and
prevents a near-null result from being read as a signal.

## 2. The tie-break actively selects the *most control-like* challenger

Nomination among eligible challengers is: smallest Holm-adjusted
`p_joint`, then **largest mean delta**, then **smallest mean swap
count**, then fixed order.

I understand the intent of the swap-count term — prefer the minimal
intervention. But for this specific purpose it is backwards. The
nominee's only permitted use is to seed a fresh unseen-2026 prospective
test. A challenger that differs from the incumbent by a handful of
lineups will, in a 6-to-12-week prospective window with this program's
observed variance, be statistically indistinguishable from the control
it was derived from. That burns a prospective slot to learn nothing.

**Suggestion:** either invert that tie-break (prefer the *larger* mean
swap count among otherwise-equivalent eligible challengers, since a
distinguishable mechanism is the point), or add a minimum-materiality
condition to eligibility — a nominee must differ from control on at
least some pre-committed number of book slots. I would not change the
statistical criteria; only the "which one do we carry forward" rule.

## 3. A7-100 is a known answer occupying a Holm slot

`A7-100` is exactly the sealed treatment `T`. Its result is already
known — null, `p_mean` 0.844, `p_signed_rank` 0.688, and it *lost* a
slate at 200, 210 and 220. Including it as one of seven Holm-adjusted
challengers inflates the correction factor for the six genuinely new
laws: at the best sorted position the multiplier is 7 rather than 6, and
every variant's adjusted `p_joint` pays for a comparison whose answer
was already in hand.

**Suggestion:** keep A7-100 in the report — it is a valuable *consistency
assertion*, and the protocol already requires reproducing the sealed A7
vectors exactly, so it doubles as a strong self-check. But treat it as a
verification row rather than a Holm-adjusted challenger, and apply Holm
across the six new fusion laws. This strictly increases power for the
things actually being discovered without weakening any guard.

## 4. Excluding N=4 forfeits the one signal A7 actually produced

The protocol excludes N=4 and N=14 because "these fused sets have no
separately frozen internal selection order." That is correct for the DS
variants, which produce a *set* by construction.

It is not correct for RB25/50/75. Those rank the union by an explicit
total-order tuple `((w_C·rC + w_T·rT), max, min, candidate_index)` and
retain the first 80 — the order is fully determined, so a `[:4]` prefix
is exactly as well-defined as A7's own was.

This matters because N=4 is what the money path actually enters, and it
was the one place A7 moved at all: **+0.66 at N=4 versus +0.050 at
N=80**, an order of magnitude larger, on the cut that decides real
entries.

**Suggestion:** for the three RB variants only, report the N=4 and N=14
prefix maxima as explicitly non-gating diagnostics, exactly as A7-v2
did. If that is considered a scope change to a frozen protocol, then
record it as a required element of the *next* protocol rather than
losing the observation entirely.

## 5. The framing question: what could this change?

Set against the completed evidence, the ceiling here is low by
construction:

- the selector algorithm is already within **0.134%** of the exact
  optimum of its own objective (A5), so ordering is not where the loss
  is;
- a *perfect* selector on this pool reaches **187.6** mean against a
  **194** target, so no selection-side change closes the gap;
- A7's ladder was null and *lost tail clears*, which this review
  attributed to its shoulder-heavy shape (68% of utility at or below
  194).

None of the seven challengers changes the objective. They fuse two
existing orders, one of which is the incumbent and the other of which is
known to underperform in the tail. The maximum achievable is therefore
bounded near the better of two known-mediocre orders per slate.

**Suggestion — the one I would act on:** run this diagnostic if it is
cheap (it is: no BigQuery, no GCS, no new outcome, pure local
recomputation over a sealed report), but pre-commit that its most likely
correct outcome is **null nominee**, and do not let a marginal
eligibility pass consume the prospective slot. The evidence points
elsewhere — the A2a dependence repair fixed four of nine cells and
manufactured two new defects, and its re-dose is *free* to evaluate on
the score-free census. That is a lane with a measured mechanism and no
outcome cost, versus this one, which is a blend of two orders that
already agree on 48 of 54 slates.

---

## Smaller notes

- **Integer micro-DK arithmetic** (`cents = round(score*100)` with an
  explicit `1e-9` guard, then `micro = cents * 10_000`) is the right
  call and eliminates the float-comparison class entirely. Worth reusing
  as the standard for future scoring paths.
- **Reconstructing and byte-matching the sealed control and A7 vectors
  before scoring any new variant** is exactly the independent-verification
  property I asked for in Addendum 12 and could not perform in Addendum
  14, because the published result carried no per-slate rows. This
  protocol builds that check in. Good — and it is an argument for making
  per-slate score vectors a standard retained field, so *any* later
  reader can do what this analyzer does.
- **Fresh RNG per challenger** (`default_rng(20_260_818)` re-seeded for
  each variant, same sign matrix used for both the mean and W+ counts)
  is deterministic and correctly specified.
- **"Individual variants may coincide on an individual slate; that fact
  is reported and never repaired"** — right, and it is the kind of clause
  that prevents a silent post-hoc fix.
- The stated reading that Holm "is descriptive and does not restore
  confirmatory status" is correct and should survive into the result
  document verbatim; a reader three months from now will otherwise see
  seven adjusted p-values and infer more than they should.
