# Fantasy Points utilization review — repository reconciliation

Reviewed 2026-08-10 CDT against the tracked intake audit, the immutable
player-tail reports, current feature SQL and the operator's tail-first law.
The outside utilization review is hypothesis-generating because its section
3 queried 2022--2025 outcomes.  This file records which conclusions are
supported and which claims must not silently change the frozen queue.

## Durable conclusions

1. Weekly Route Share is the clearest new asset in the purchase.  It is less
   redundant with snaps for tight ends than for wide receivers and is the
   only imported player-week vendor series already shown to improve held-out
   20- and 30-point calibration.  Continue the frozen Route candidate union
   exactly as preregistered.
2. The prior-season Advanced bundle failed its registered multi-position
   gate.  Coverage-fit passed only narrowly, with 62 observed 30-point events,
   a `0.0000385` aggregate Brier gain and one worsening fold.  Run the already
   frozen coverage union once, report the treated-slate paired comparison and
   describe any one-week extreme gain as fragile.
3. The route-level descriptive tables are useful mechanism evidence, but
   their thresholds, projection bands and position decompositions were chosen
   after outcomes were visible.  They cannot retune the twelve-candidate
   Route union or create a band/position/dose retry on these same slates.

## Corrections and cautions

### Route Share is not yet a demonstrated mean-projection repair

The outside review reports a roughly `+0.6` to `+1.0` realized residual among
high-route players and recommends adding the four registered Route inputs to
the production component models.  That is a reasonable distinct diagnostic,
but the closest held-out test already contains a mean result the review does
not discuss: the Route treatment's residual Ridge model worsened MAE in both
folds and aggregate.

| fold | control MAE | Route MAE |
|---|---:|---:|
| 2024 | 2.786697 | 2.804863 |
| 2025 | 2.979168 | 2.979984 |
| aggregate | 2.882990 | 2.892476 |

The same treatment improved aggregate 20/30-point Brier slightly.  Current
evidence therefore supports Route Share as a tail-calibration signal, not yet
as a mean correction.  A full component-model experiment remains open because
LightGBM component training is mechanically different from the auxiliary
Ridge model, but it starts with a lower prior than the outside review assigns.

If run, freeze exactly `fp_route_share_last`, `fp_route_share_l4`,
`fp_route_share_jump` and `fp_route_cross_season`; do not add a threshold,
position-only population, projection-band bonus, hand coefficient or feature
sweep.  Compare same-code control and treatment over the Route-available
seasons, report component metrics, composed DK-point MAE/CRPS and 20/30-point
Brier, then require prospective 2026 shadow confirmation before calling a
retrospectively motivated historical lift independent evidence.

### Defense PROE is not redundant with the current feature

`sql/features/016_team_week_context.sql` computes a team's own lagged offense
PROE and `player_week_training` joins only that offense row.  The Fantasy
Points Defense PROE exports are distinct files and represent opponent context;
the intake audit explicitly classified them as such.  Do not close Defense
PROE as redundant.  First normalize the weekly values with a strict prior-week
join and test whether they add opponent signal beyond the existing allowed,
pressure and neutral-pass features.  Offense PROE is much more directly
redundant with `proe_l4`.

### Target and Snap Share are conceptually redundant, not proven identical

The production tables already contain PBP-derived target and nflverse snap
shares.  That makes the vendor families low priority, but charting/source
differences could still improve completeness or measurement quality.  Before
closing them, run an outcome-blind agreement/missingness audit against the
existing series.  Only a near-identical, non-improving coverage result should
remove them from the weekly checklist.

### An early-season Advanced retry would still be a viewed subset

Restricting the failed prior-season Advanced experiment to Weeks 1--4 is a
football-motivated idea, but it is literally a subset of the same outcome data
after the pooled failure was read.  Do not present a historical early-week
retry as independent confirmation and do not select `XFP/RR` from the failed
bundle post hoc.  Prior-season features may be carried as a labeled
prospective early-season shadow if an exact feature set is frozen before 2026
outcomes.

### Paired evidence remains mandatory reporting, not a restored veto

Every candidate union must report treated-slate wins/ties/losses, paired
weekly deltas and season diagnostics.  The operator explicitly removed the
old season-stability/significance veto when it conflicted with the primary
240→230→220→210 objective.  A tiny treated sample changes confidence and the
need for shadow confirmation; it does not silently rewrite that policy.

## Operational consequences

- Do not modify the active Route, no-floor or coverage protocols.
- After the frozen queue, the next paid-data modeling diagnostic is one
  coefficient-free four-feature Route component-model test, unless the Route
  union itself exposes a mechanical defect.
- Audit vendor Target/Snap agreement without outcomes before finalizing the
  recurring download list.
- Preserve Defense PROE as a distinct possible opponent feature.  Do not add
  Offense PROE merely to duplicate existing `proe_l4`.
- The current hash-locked historical Route importer is not by itself a 2026
  weekly append path.  Before Week 1, implement and validate an immutable raw
  archive plus idempotent player-week upsert/append contract, strict prior-week
  feature join, schema/hash audit and labeled no-Route fallback.
- Keep the matchup exports quarantined unless their opponent pairs
  mechanically match the target schedule and the file was captured pre-lock.

This reconciliation does not claim the $200 purchase will create a large
lineup lift.  It narrows the plausible value to weekly Route Share plus one
still-untested Defense PROE question, while preventing descriptive outcome
cuts from becoming hidden tuning.
