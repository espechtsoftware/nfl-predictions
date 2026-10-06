# Frozen note: a Route Share tilt on 2026 Weeks 2–4 (the money-gate harness) — 3 weeks; mechanics + anecdote; no verdict

**Frozen 2026-10-06, before any book of this note is built or scored.** The operator (10-06, verbatim): "I would rather
see around the clock efforts to try different strategies of selecting boom players, sorting, testing usage of route
share data etc with the intent to use the best system available this week". The reviewer agreed to this replay as a
LABELLED ANECDOTE; Route Share's graded evidence remains the Week-5 prospective pair (companion-v1, gate document
`reports/2026-08-11-route-share-2026-shadow-gate.md`, which allows no interim scientific read).

**3 weeks; mechanics + anecdote; no verdict.** Nothing here can adopt or reject anything.

## The signal (fixed)
- `signal = fp_route_share_last − fp_route_share_l4` from `nfl_features.player_week_fp_route` for the target
  (2026, W): the player's most recent prior Route Share minus the mean of his last four prior observations (2025 history
  fills the l4 early in 2026). The table is as-of by construction: only source weeks strictly before W.
- Every 2026 capture it uses predates the lock it feeds: W1 captured 09-17 (W2 locks 09-20), W2 09-23 (W3 locks 09-27),
  W3 09-30 (W4 locks 10-04). Joined to the T-70 frame by gsis_id; a missing value is 0.
- Applied to RB / WR / TE only (QB and DST carry none).

## The objective (fixed; one κ, no sweep)
- **κ = 12 DK points per unit of Route Share** (a +0.10 rise adds +1.2 points to the player's objective).
- Arm **R**: the optimizer's per-player objective = the T-70 frame's `mean_projection` + κ·signal.
- Arm **H** (reference): `mean_projection` alone.

## Everything else (identical for both arms)
- The house shape (QB + 2 pass catchers + ≥ 1 bring-back), production's main caps for K: a player at int(0.5 K)
  rows, a DST at int(0.25 K); MAX_PER_GAME 4; the $49k floor; ≤ 7 players shared with every earlier row; skill players
  projected < 1.0 and the players production's `unavailable_ids` (r1c_sunday_reselect) marks from the frame's statuses excluded; no ownership term; no sleeve.
- Main-only books solved by production's `union_reselect.pmo_rows` on the week's pre-lock T-70 frame
  (money-gate `weeks.json`), with the money-gate's pinned lab clone (32cdb61).
- The week's REAL contest plan (money-gate `books/wN/contests.json`) with every contest set to the main track; K = the
  head layout's rows needed; dealt by production's `enter_layout` (head, the small-contest overlap limit M 5 / 10).

## Scoring
- The real W2–W4 contests through the money-gate scorer (the reconciled known-answer path): per week and pooled, for H
  and R, the return multiple (cash + tickets at face over fees), the cashes and the mean entry finish percentile.
- **Dead lever:** if R's book differs from H's in fewer than 2 of every 20 rows in a week, that week is reported as a
  dead lever.
- Dollar amounts stay private; the report carries multiples, cashes and percentiles only. FP's licensed values never
  leave the private scripts.
