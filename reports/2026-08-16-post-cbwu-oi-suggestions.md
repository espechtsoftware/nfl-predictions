# Suggestions after the CBWU-OI result and ATLAS launch

Date: 2026-08-16. **No code was changed. No outcome was queried.**

---

## 1. A recurring failure class worth abstracting, not repairing again

Recent operational failures, in order:

| item | failure |
|---|---|
| exact-P census (1) | BigQuery alias defect |
| exact-P census (2) | source-identity failure |
| ATLAS (1) | source receipt query |
| ATLAS (2) | relaunch after repair |
| TD ledger v2 / v3 | float reproduction / stale reference resolution |

Five of the last several launches failed before producing science, and **four
were the same class: the analysis could not resolve which artifact, panel,
roster or receipt it was supposed to read.** None was a scientific failure.

That is not five unlucky bugs. It is a missing abstraction.

**Suggestion:** factor a single **source-resolution preflight** that every
protocol calls before its first heavy operation — resolve the panel id, roster
source, receipt directory, image digest and code SHA, assert each exists and is
uniquely identified, and fail in seconds rather than after a Cloud Run start.
Each protocol currently re-implements this, and each re-implements it slightly
differently, which is why the same class keeps recurring.

This pairs with the narrow plumbing-only preflight already suggested for
exact-P: one shared helper plus one cheap smoke would have caught four of the
five above.

## 2. Read the CBWU-OI selector stability jointly with the C gain, not separately

Measuring selector stability on the OI pool is the right step, and the
comparison point is the canonical **54.28/80** disjoint-half overlap.

But the two numbers interact, and the protocol should say how before the result
lands:

- OI's entire measured gain sits at **194–210**;
- the selection gap `C − S = 5.007` also sits in that band, because the selector
  is saturated at 220+;
- so a pool that improves `C` by **+5.66** while selecting *less stably* could
  net out to little or nothing at `S`.

**Predeclare the joint reading.** If OI stability is materially worse than
54.28/80, a modest or absent book-level gain is the expected outcome and should
be recorded as such rather than treated as the pool gain failing to
materialise. If stability is comparable or better, the C gain has a clear path
to `S` and that strengthens the prospective case considerably.

Either way the two numbers should appear in the same table.

## 3. CBWU-OI is the first real test of the tail-first law against the paying band

This is the most consequential thing in the current state and I do not think it
has been named.

CBWU-OI improves **194 / 200 / 210** by **+7 / +6 / +4** and leaves
**220 / 230 / 240 exactly tied**. Under the standing law — first non-zero
difference from 240 downward — the first three thresholds tie and the arm is
adjudicated at 210 at best.

Now put that against what the forensic established about money:

- the one recorded contest data point has **min-cash at 169.34** and **first
  place at 246.82**;
- the book clears a representative min-cash line in roughly **seven weeks in
  ten** and wins in approximately **zero**;
- `>=240` is 0 of 54 slates even at the candidate-oracle layer.

So the band CBWU-OI improves — 194 through 210 — is **comfortably inside the
paying region**, and the band the decision law prioritises — 220 and above —
contains outcomes that, on the available evidence, still do not win the top
prize.

**This is the first arm where the tail-first law and expected dollars plausibly
disagree**, and where the disagreement is measurable rather than theoretical.

### The cheap way to settle it

Score both candidate layers against a **published DraftKings Millionaire payout
curve** — public, no new data, no acquisition — and report expected dollars
alongside the threshold grid as a **mandatory diagnostic, not a veto.**

That does not change the operator's stated objective and does not promote
anything. It makes visible what each tail-first adjudication costs, using an
arm where the trade is finally large enough to see. Right now the grid cannot
distinguish "ties at 220+ and gains 17 weeks lower down" from "no benefit," and
those are very different propositions economically.

If it turns out the law would reject something worth real money, that is the
operator's call to make knowingly — which is the whole point of reporting it.

## 4. Predeclare ATLAS's target band before its result lands

The census review established that successors should be scored on `C`, never on
reaching P, and CBWU-OI then demonstrated it empirically — **+5.66 points of C
on only 0.30 swaps toward P.**

Add one more predeclaration to the ATLAS protocol: **which band it is expected
to move.**

CBWU-OI moved the shoulder and left the extreme untouched. If ATLAS is designed
around new-combination search, the honest prior is that it does the same — broad
combination breadth improves the achievable maximum across many slates rather
than manufacturing the rare extreme construction. Saying so in advance means a
shoulder-only result reads as confirmation, and an unexpected 220+ movement
reads as genuinely surprising rather than as the thing that was hoped for.

It also protects against the failure mode where a shoulder gain gets quietly
re-described as tail progress because the tail is what the objective names.

## 5. Summary

| # | suggestion | cost |
|---|---|---|
| 1 | Factor a shared **source-resolution preflight**; four of five recent failures were the same class | low |
| 2 | **Predeclare the joint reading** of OI selector stability and the C gain; put both in one table | trivial |
| 3 | **Report expected dollars** against a published payout curve alongside the grid — CBWU-OI is the first case where the tail-first law and money plausibly diverge | low |
| 4 | **Predeclare ATLAS's expected band**, as C-scored and shoulder-weighted | trivial |
