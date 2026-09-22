# Laptop → production: correction — item 1's second clause IS answered, and I was
# wrong twice in the same way

Corrects `reports/2026-09-22-laptop-item2-per-bug-consolidation.md` §diff, pushed at
`c5adec6f`. **Read this before acting on that section.**

## The correction

I reported that item 1's second clause — season-partitioned windows, training vs
serving contracts, cold-start — was "unanswered in every committed report". **It is
answered**, thoroughly, by

    reports/2026-09-21-season-window-audit-week2.md
    commit 737104bb (2026-09-20 21:02 CDT)
    branch production/in-season-rules-20260919
    sha256 7c348722ab5f76c69c686c3974ccb45159bbda4dff87e9949d7af3af5bcc5b77

Mirrored to this branch at the same path, byte-identical (hash above verified on both
sides), so the answer now travels with the work.

## It answers the clause directly, on the exact point the clause raised

The clause asked that a cross-season training-feature change not be *classified* as a
repair without comparing contracts. The audit reaches that conclusion explicitly:

> Established: the Week-2 and Week-3 rolling features are cold-start or one-to-two-game
> windows for every player; **the model was trained on the same within-season windows, so
> this is the training contract, not an ingestion gap.**

> A cross-season window with season-change shrinkage is a modelling change to be tested
> walk-forward on 2019-2025 Weeks 2-4 with a retrain, **not a repair.**

That is the classification question answered in the direction the clause pushed, and the
training/serving contract comparison performed rather than asserted. It also quantifies
cold-start (55% of Week-2 skill rows; `xfp_l4` 100% null) and — the part I would have
missed entirely — establishes that the Week-2 damage came through the market stand-in
and the selector, **not** the window weight.

## What genuinely remains, stated narrowly

One sub-part is *recommended rather than performed*: the clause says "historical
cold-start behavior", and the audit proposes the multi-season walk-forward on 2019–2025
Weeks 2–4 as research-queue work rather than running it. So the correct status is
**answered on the classification question, with the historical comparison deliberately
deferred with a stated protocol** — not "unanswered". The deferral is reasoned, not an
omission, and it is the right call for a week that should not absorb a retrain.

## My error, because the pattern matters more than the instance

This is the **second time today** I concluded "it does not exist" after searching one
place:

1. The round-1 document — I searched `nfl-predictions` only; it was in nfl2 `handoffs/`.
2. This audit — I grepped the integration branch's `reports/` only; it was on
   `production/in-season-rules-20260919`.

Both times the artifact existed and my search scope was the defect. The standing lesson
for this project, given that findings are required to travel as committed files: **"not
in the repository" is not a conclusion that can be drawn from one branch of one repo**,
and this workspace has two repositories and many live branches. I will search
`git log --all` and both repos before making that claim again.

The consolidation's other nine rows and its replay-column finding are unaffected — those
were built from commits I verified individually. It is specifically the §diff conclusion
about item 1's second clause that was wrong.

## The residual finding, which is real but smaller

The audit was invisible from the branch production works on. Item 1's own report predates
it and was never updated to point at it, and `HANDOFF.md` on the integration branch does
not carry it. A report that answers a review item, sitting on a branch the reviewer is
not reading, is functionally unanswered — which is how I came to say so. The mirror above
fixes this instance; the general version is worth a habit, not a process.
