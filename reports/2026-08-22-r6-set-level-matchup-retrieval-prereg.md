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

- Substrate amendment 2026-08-23, made before ANY batch task produced a
  score: the v6 single batch died with its task-0 producer (one correct
  ~91 s collision proof crossed the 120 s per-visit deadline; the
  all-optimal and finish-batch laws make a 54-task batch unrecoverable
  after one consumed failed launch). The substrate is now the UNION of
  the two v7 half-batches over the SAME 54 source slates —
  `20260823-corpus-parametric-production-batch-v7a` (source tasks 0–27)
  and `-v7b` (source tasks 28–53) — with the split fixed by enumerated
  lattice law before any lane score existed. Every frozen cell,
  endpoint, bar, and prohibition above is unchanged; "the accepted
  panel" means the union of both lanes' verifier-accepted tasks.
- Namespace amendment 2026-08-23 (still before ANY batch task produced
  a score): the v7 lane namespaces were burned UNUSED — their published
  foundations pin a superseded image digest after the transport's
  lane batch-mode law forced one more image respin; no launch was ever
  consumed under them. The lanes are now
  `20260823-corpus-parametric-production-batch-v8a` (source tasks 0–27)
  and `-v8b` (28–53); every frozen cell, endpoint, bar, and prohibition
  is unchanged.
- Namespace amendment 2 (2026-08-23, still zero scores read or
  published): v8a's task-0 producer completed a perfect 7,000/7,000
  generation but the finalizer's stage-tuple law refused the new
  uniqueness certificate before ANY variant result was published, so
  v8a is burned by its consumed launch and v8b unused by the image pin.
  The lanes are now `20260823-corpus-parametric-production-batch-v9a`
  and `-v9b`; every frozen cell, endpoint, bar, and prohibition is
  unchanged.
- Namespace amendment 3 (2026-08-23, still zero scores read or
  published): the Cloud Asset analyzer daily quota wall forced a
  policy-derived effective-access fallback in the transport (validator
  recomputes grants from the captured version-3 policies; analyzer
  preferred when available), which pins a new image, so the v9 lanes
  are burned unused. The lanes are now
  `20260823-corpus-parametric-production-batch-v10a` and `-v10b`; every
  frozen cell, endpoint, bar, and prohibition is unchanged.
- Namespace amendment 4 (2026-08-23, still zero scores READ; lane-A's
  v10 producer published its variant results but no score was ever read
  by any consumer — its verifier failed on the attempt-ledger
  certificate law, and lane-B's producer refused on positional
  source-row selection; both fixed with lane-safe identity-matched
  selection). The lanes are now
  `20260823-corpus-parametric-production-batch-v11a` and `-v11b`; every
  frozen cell, endpoint, bar, and prohibition is unchanged.
- Namespace amendment 5 (2026-08-23; simulated scores exist for three
  v11-accepted slates but NO realized outcome has been read anywhere,
  and no admission/evaluation choice was conditioned on any simulated
  score): the certificate exposed genuine CBC non-optimality (~2/7000
  worlds on the first slate expressing it), fixed by exact-gaps CBC
  flags requiring one more image; v11 lanes closed with three accepted
  slates retained as diagnostic evidence OUTSIDE the panel. The panel
  substrate is now `20260823-corpus-parametric-production-batch-v12a`
  and `-v12b`; every frozen cell, endpoint, bar, and prohibition is
  unchanged.
- v12a batch manifest: TO BE BOUND at publication
  (uri/generation/sha256/bytes).
- v12b batch manifest: TO BE BOUND at publication
  (uri/generation/sha256/bytes).
- Runner commit at freeze: bound to repository main at the commit that
  adds this file (see git history for the exact SHA).
