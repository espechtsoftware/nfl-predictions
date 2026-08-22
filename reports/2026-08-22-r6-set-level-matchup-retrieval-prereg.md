# R6 preregistration — set-level matchup admission on the Foundry v6 batch

Status: FROZEN 2026-08-22, before any v6 batch task has produced a score
and before any realized outcome for this design has been read. This
document is the complete evaluation law for the next (and only licensed)
matchup-selection test. Amendments after the first v6 task score exists
are forbidden; a failed bar closes the matchup-admission direction
pending a genuinely new pre-lock signal per the standing reopening
condition.

## Why this test is licensed

The K=8 sleeve paired matchup-retrieval test on the 107-slate replay
panel FAILED its preregistered bar (mean −0.32, >200 tie 13=13, +3 at
≥194 below the +2-with-no-tail-cost requirement as specified there), and
further challenger iteration on those same 107 slates is panel mining —
forbidden. The Foundry v6 batch is a NEW measurement substrate (54
slates × 7 fill arms × 1,000 visits under one fixed exact-80/line-194
selector, freshly generated corpus, new draws), so one preregistered
set-level test on it is legitimate. This is that test.

## Data and vehicle (frozen)

- Substrate: every VERIFIER-ACCEPTED task of the v6 production batch
  (`20260822-corpus-parametric-production-batch-v6`). Batch-manifest
  identity is appended to this file's **Bindings** section at publication
  time — an identity-only edit made while still outcome-blind; no other
  edit is permitted.
- Vehicle: `src/nfl_dfs/research/corpus_batch_retrieval_runner.py` —
  `reconstruct_and_verify` (scores rebuilt from pinned draws; candidate/
  selected score SHA verification), `matchup_lineup_scores` (QB depth-1
  starter gate; pre-lock 017r point-in-time annotations only), and
  `run_retrieval_surface` (`ADMISSION_MODES = ("full-union",
  "matchup-top-200")`, `ADMISSION_M = 200`). The run must use these
  functions with semantics byte-equivalent to main at freeze time; any
  semantic change voids the run, not the preregistration.
- Admission inputs are pre-lock only: matchup annotations from the three
  frozen families (receiver/RB/QB) joined point-in-time; no simulated
  world score, no realized outcome, and no batch artifact feeds
  admission. Lineups without matchup coverage follow the frozen runner
  ordering law as coded at freeze time.

## Cells (frozen)

Per accepted slate: 7 retrieval laws (`coverage-194-v1`,
`strict-200-coverage-v1`, `tail-ladder-200-210-220-v1`, `mean-score-v1`,
`expected-max-v1`, `block-supported-tail-ladder-v1`,
`regime-robust-ladder-v1`, exact-80 budget each) × 2 admission universes
(full-union over all seven arms' unique candidates; matchup-top-200).
The paired comparison is always same-law, matchup-top-200 versus
full-union, per slate.

## Endpoints and bars (frozen)

Realized grading (the only realized read): each selected 80-lineup
book's ACTUAL DraftKings score per lineup from historical player
scoring, computed once by the realized grader after all cells above are
fixed on disk.

- PRIMARY: law `coverage-194-v1`. Endpoint: per-slate paired indicator
  of best-of-book actual ≥194. Bar: matchup admission must net **+2 or
  more slates** at ≥194 across the accepted panel AND must not reduce
  the ≥200 count AND no season may worsen by more than 1 slate.
- SECONDARY (descriptive unless primary passes): the same paired
  endpoints for the other six laws, Holm-corrected across the six; mean
  best-of-book delta; ≥187 and ≥200 ladders.
- Any missing/failed task shrinks the panel; the bar applies to the
  accepted panel as-is. No slate substitution, no reweighting.

## Prohibitions (frozen)

- No admission-parameter tuning (M stays 200), no law editing, no
  re-ranking of annotation families, and no second admission variant on
  this batch. One test, one read of actuals.
- If the PRIMARY bar fails, matchup-informed admission is CLOSED for the
  current annotation families and simulator, and may be revisited only
  on a genuinely new pre-lock signal with a fresh preregistration on
  data these cells have not consumed.
- Nothing here licenses a production default change; adoption requires
  the standing separate confirmation gate on untouched data.

## Bindings (identity-only edits permitted while outcome-blind)

- v6 batch manifest: TO BE BOUND at publication
  (uri/generation/sha256/bytes).
- Runner commit at freeze: bound to repository main at the commit that
  adds this file (see git history for the exact SHA).
