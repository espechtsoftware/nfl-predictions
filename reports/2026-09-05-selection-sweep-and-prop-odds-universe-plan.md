# Selection-sweep and prop-odds-universe plan

**Date:** 2026-09-05  
**Audience:** lab implementation team  
**Status:** proposed experiment plan for review  
**Scope:** improve the quality of the candidate corpus and the final selection
process before week 1, without changing the production scoring contract

## Why this is worth testing

We have enough evidence that the current problem is not just “can the optimizer
solve the book.” The harder problem is that some candidates likely should not
be in the selection pool at all, or should at least be treated as lower
confidence than the rest.

This plan tests two related ideas:

1. whether a simple pre-selection sweep can remove weak candidates before the
   selector spends entries on them; and
2. whether requiring pre-lock prop-odds coverage for the offensive players
   in a lineup improves the quality of the remaining pool.

The goal is not to shrink the corpus for its own sake. The goal is to preserve
ceiling while removing candidates that look high-volume but weak once we add
independent pre-lock information.

## Recommendation in one sentence

Start with one conservative negative screen, and keep the prop-odds-only
variant as a separate arm. Do not combine them at first, and do not turn either
one into a universal rule until it shows a clear lift on historical data.

## The two experiment families

### A. Weak-player / weak-lineup sweep

This is the “remove obvious weak stuff before selection” idea.

Use a frozen, outcome-blind screen that only looks at information available
before lock. The screen should not use realized scores, post-lock labels, or
anything learned from the target slate outcome.

Recommended first version:

- keep the current candidate generation and selector unchanged;
- apply a deterministic pre-selection filter to the candidate pool;
- remove only candidates that fail a simple, interpretable evidence rule; and
- compare the filtered pool against a matched neutral baseline of the same
  size.

What to test first:

- a player-level screen is safer than a lineup-level screen;
- if the player-level screen helps, then test a lineup-level sweep as a second
  pass;
- do not begin with a complicated dominance lattice or a grid of thresholds.

What counts as “weak” should be conservative and pre-lock only. Examples of
acceptable inputs:

- participation/availability state;
- prop-odds presence;
- matchup context;
- role / usage / depth-chart type information;
- ownership or leverage features that are already frozen pre-lock.

What should not be used:

- realized fantasy points;
- post-lock participation labels;
- winner labels from the target slate;
- any signal that only exists after the contest starts.

### B. Prop-odds-only player universe

This is the simpler variation you asked for directly.

Define a second arm where the selection universe includes only players with
valid pre-lock prop odds data.

Suggested rule:

- keep DST exempt, since there is no comparable player-prop market for it;
- require each offensive player in a candidate lineup to have at least one
  valid pre-lock prop quote;
- keep the candidate generator, judge, and selector otherwise unchanged;
- compare against a neutral matched control with the same candidate count.

This arm is valuable because it answers a clean question:

> Does requiring prop-market coverage improve the quality of the remaining
> candidate pool, or does it simply throw away ceiling?

If the prop-only arm helps, that is strong evidence that prop availability is a
useful proxy for lineups we should trust more. If it hurts, then prop coverage
is not a good universal gate and should remain only a feature.

## Proposed order of execution

1. Run a support census first.
   - Count how many candidates remain after each filter.
   - Count how many slates/banks still have enough support for a valid
     comparison.
   - If any proposed scored cell becomes too sparse, stop and report that as a
     result.

2. Run the prop-odds-only arm.
   - This is the cleanest and most objective variant.
   - It is also the easiest to explain to future reviewers.

3. Run the weak-player / weak-lineup sweep arm.
   - Start with a single simple screen.
   - If it helps, consider a second pass at the lineup level.
   - Do not expand into a threshold grid until the first version has clear
     signal.

4. Only after those results, decide whether a combined arm is worth trying.
   - If both help independently, a combined arm may be worth a later test.
   - If either one fails, keep the scope narrow and do not force a fusion.

## How to judge success

Please report both corpus quality and selection quality.

Corpus-side:

- number of candidates retained;
- number of 200+, 210+, 220+, and 230+ candidates retained;
- whether the retained set still contains the high-ceiling candidates we care
  about;
- how many lineups are lost solely because they fail the screen.

Selection-side:

- selected-book maximum;
- mean selected-book maximum across the historical panel;
- improvement or decline versus the matched neutral control;
- overlap with the current baseline selector;
- whether the screen changes the composition of the selected book in a useful
  way.

If the filter helps corpus quality but not selected-book score, that is still
useful information. It may mean the screen is a good supply-shaping rule but
not yet a full selection policy.

## Guardrails

- Keep DraftKings legality universal.
- Do not silently relax the filter after seeing results.
- Do not treat a missing prop quote as proof that a player is bad; it is only a
  reason for the prop-only arm.
- Do not merge the two experiments on the first pass.
- Do not turn this into a threshold search unless the simple version is
  promising.
- Do not regenerate the corpus just to make the arm work; if support is too low,
  report that and stop.

## My recommendation

If you want the fastest useful answer, start with the prop-odds-only universe.
It is the cleanest “reduce uncertainty before selection” test and easiest to
interpret.

If that shows no lift, the next best follow-up is the weak-player / weak-lineup
sweep, but keep it simple and conservative. The first pass should answer one
question only: do we improve by removing obvious low-signal candidates before
the selector runs?

