# Review: how the candidate corpus is populated, and whether it serves the high-score goal

**Date:** 2026-08-21. **Role:** review only — no code changed, nothing
run beyond read-only warehouse queries. **Question from the operator:**
is the corpus-population process aligned with the goal of producing high
scores?

**Short answer: no, and the misalignment is measurable — but the fix is
not the obvious one, because it has already been tested and failed.**

## 1. How the corpus is actually populated

Per seed book, `tail_select_lineups` fills a fixed budget from six
generators:

| Family | How it is produced | Nominal size |
|---|---|---|
| `lev` | `optimize_many(n_lineups = CAND_MULT × 80)` — the top distinct lineups by projected points with leverage shaping | 160 |
| `boom` | one MILP solve per simulated world, walking the boom world order | 40 |
| `epi` (role) | alternate-role belief variants | 12 |
| `dark` | concentrated stacks from games ranked 5th+ by projected total | 10 |
| `game` | game-stack solves on the top games | 4 |
| `qbvar` | QB-variant solves | 4 |

Roughly 230 generated per seed, deduped to ~252 registered candidates
across the five seeds' union.

The essential distinction: **`lev` optimizes projected points; `boom`
optimizes a sampled world.** One is a mean-objective generator, the
other is a tail-objective generator.

## 2. What each family actually contributes (54-slate corpus, 67,951 candidates)

Queried from `replay_candidates_staging` over the five registered
money-worlds panels:

| Family | Share of corpus | Share of ≥200 | Share of ≥210 | Tail efficiency @210 |
|---|---|---|---|---|
| **lev** | **63.3%** | 22.2% | **0.0%** | **0.00×** |
| **boom** | 15.8% | 40.7% | **69.2%** | **4.37×** |
| qbvar | 9.7% | 14.8% | 23.1% | 2.37× |
| epi | 4.8% | 13.0% | 7.7% | 1.62× |
| game | 3.8% | 7.4% | 0.0% | 0.00× |
| dark | 2.5% | 1.9% | 0.0% | 0.00× |

Whole-corpus totals: 54 candidates at ≥200, 13 at ≥210, 4 at ≥220.

**The finding stated plainly:** `lev` is 63% of everything we generate
and has produced **zero of the 13 candidates at 210+**, and zero of the
4 at 220+, across three seasons. Its best-ever candidate is 205.6.
Meanwhile `boom` is 16% of the corpus and produces 69% of the 210+
candidates — a 4.4× tail efficiency. `dark` and `game` (6.3% combined)
have also never produced a 210+ candidate.

By the program's own stated objective — the weekly *maximum* — roughly
**70% of generation spend goes to families that have never once produced
a top-tail lineup.**

## 3. Why this is real misalignment, not a measurement artifact

The obvious objection is that `lev` might be producing the *book's*
scores even if not the pool's extremes. It is not: the money book's mean
weekly best is 176.06 and it clears 210 on 6 of 54 slates. Those clears
have to come from candidates at 210+, and 69% of those are `boom`, 23%
`qbvar`, 8% `epi`. `lev`'s contribution to the tail is exactly zero by
construction of the measurement.

The second objection is that mean-objective lineups provide a floor. That
is true and is precisely the problem: a floor is not the estimand. The
program optimizes the weekly maximum of an 80-entry book, and against
that estimand a lineup that reliably scores 130 is worth nothing.

## 4. But the obvious fix has already been tested — and failed

This is the part that matters, and it is why I would not act on §2
directly.

The **all-boom reallocation arm** did exactly what the table above
suggests: it replaced the entire `lev` batch with boom depth at
identical budget.

- Pool ceiling: **187.58 → 196.64 (+9.06)**, 43 of 54 slates better,
  p ≈ 0. Exactly as the efficiency table predicts.
- Selected book: **178.57 → 179.91 (+1.34), p = 0.49** — null. And the
  boom-deep book scored *worse* on winner-overlap-versus-chance
  (+0.11 vs +0.24).

So removing the 63% that contributes nothing to the tail **raised the
ceiling by nine points and did not move the book.**

## 5. The reconciliation, and where the real defect sits

The corpus is populated for a **coverage** objective, and it is
internally consistent with that objective. The selector's job is to
cover as many simulated worlds as possible at line 194; `lev`'s
high-mean, low-variance lineups are efficient *coverage* instruments even
though they are useless *tail* instruments. That is why deleting them
raises the ceiling but does not improve a book chosen by coverage.

Two completed results pin this down:

- **A5** proved the selector is within **0.134%** of the exact optimum of
  its own objective. It is not failing to optimize; it is optimizing
  faithfully.
- **A7** changed the objective to a multi-threshold ladder and came back
  null — and *lost* clears at 200, 210 and 220, because 68% of that
  ladder's utility still sat at or below 194.

So the chain is: generation is tuned to coverage → selection optimizes
coverage nearly perfectly → coverage is not the weekly maximum. The
corpus composition is a *symptom* of the objective, not an independent
defect, which is why attacking it directly (all-boom) produced a
ceiling with no book.

## 6. What I would suggest, in order

1. **Do not re-run an all-boom-style reallocation.** It is closed at
   this dose by a frozen null, and §4 explains why a repeat would fail
   the same way. The composition cannot be fixed while the selector's
   objective rewards coverage.

2. **The composition question and the objective question must be tested
   together, once.** Every arm so far has moved one and held the other:
   all-boom changed the pool with the coverage selector fixed; A7 changed
   the objective with the incumbent pool fixed. Both were null at the
   book. A single frozen arm that pairs a tail-weighted objective with a
   tail-weighted pool is the untested cell, and it is the only cell the
   evidence still supports. It must be one preregistered arm, not a
   grid.

3. **If a ladder is used, weight it where the corpus actually has mass.**
   The whole corpus contains 13 candidates at 210+ and 4 at 220+ across
   54 slates. A7's ladder spent 68% of its utility at or below 194 and
   lost tail clears. A tail-weighted ladder should concentrate above 200,
   with the caveat from my A7 review that 230/240 have ~1 and ~0 events
   and should stay report-only.

4. **Reconsider `dark` and `game` explicitly (6.3% of spend, zero 210+
   candidates).** Unlike `lev`, these are small and have no coverage
   rationale I can find — `dark` was justified by a winner study
   ("29% of matched 2025 Milly winners stacked a game ranked 8th–14th"),
   but on this corpus it has produced one candidate at 200+ in 1,725
   attempts. That is a cheap, self-contained deletion test.

5. **Keep `qbvar` in view as an underrated family.** At 9.7% of spend it
   delivers 23% of the 210+ candidates (2.37× efficiency) — second only
   to `boom` and never separately studied. If any family deserves a
   *increase* rather than a deletion test, the table points here.

## 7. What this does not say

It does not say `lev` is useless: it says `lev` is useless *for the
stated estimand*, and that the book currently depends on it because the
selector's objective values it. Until the objective changes, deleting it
demonstrably does not help. The honest summary is that corpus
composition, selector objective, and the 194 target are three views of
one unresolved question, and the evidence now points at testing them
jointly rather than one at a time.
