# Boom unique-fill arm — protocol (DRAFT for operator freeze)

**Protocol ID:** `20260818-boom-unique-fill-v1`
**Status:** DRAFT — not frozen. The operator must approve, pin this
document's SHA-256, and bind image/code/panel identities before any
treatment execution. One shot; no parameter retry after a valid verdict.
**Class:** historical paired arm (control vs treatment), score gate
deferred to the operator's frozen utility.
**Origin:** S5 (2026-08-18 boom-capability report) + N6 (Part III of
`reports/2026-08-18-high-score-challenges-assessment.md`), premise
corrected per the handoff: `unique_target` exists but is used only at the
two CE/EPI shortfall sites (dead in production config); the primary boom
pass genuinely lacks unique-fill, and both shortfall sites resume from a
cursor that is never advanced.

## Mechanism (implemented, offline-tested, default byte-identical)

Lever `BOOM_UNIQUE_FILL` in `backtest/engine.py::tail_select_lineups`,
registered in the immutable lever set so any treatment is
self-identifying in BigQuery:

- **Off (default, production):** byte-identical to the pre-lever code —
  the primary pass solves exactly the top-`N_BOOM` worlds by the boom
  world order; duplicate optima silently deliver fewer than `N_BOOM`
  unique boom candidates; the CE/EPI replacement passes resume from the
  static cursor.
- **On (treatment only):** the primary pass walks down the world order
  until exactly `N_BOOM` unique boom rosters exist (or worlds exhaust),
  and every boom pass advances the shared cursor past the worlds it
  attempted, so replacement passes never re-solve attempted worlds. The
  realized unique count and worlds attempted are logged per slate.

Vacuity/parity evidence: `tests/test_boom_unique_fill.py` proves the
default is byte-identical to the unset path (candidates and selections),
that the lever fires on an engineered duplicate-optimum slate, and that
the treatment pool is a superset of the control's boom uniques.

## Budget accounting (predeclared)

The treatment attempts MORE MILP solves than control on slates where the
top worlds share optima; it holds the unique-boom CANDIDATE quota fixed
instead of the solve count. Both counts are reported per slate. This is
the supply/budget separation the CBWU-OI record established (a fixed
admitted budget should not require a fixed native supply); the admitted
candidate budget and the selector are unchanged.

## Arms

- Control: current production configuration on the frozen image.
- Treatment: identical except `BOOM_UNIQUE_FILL=1`.
- Same image, seeds, panel corpus (the current-stack comparable slates),
  and acceptance machinery as the standing arm process.

## Gates

1. **Mechanism gate (before any outcome read):** per-slate realized
   unique boom counts strictly ≥ control everywhere with at least five
   slates increased; treatment boom pool a superset of control boom
   uniques on every slate; all shared-roster support/score values
   invariant; lever recorded in `lever_env` on every treatment row.
2. **Score gate:** deferred to the operator's frozen utility (the
   mean-vs-lexicographic decision requested in
   `reports/2026-08-18-offseason-selection-ideas-toward-194.md` §1) and
   reported with the standing co-primary block: full 240→187 grid,
   paired mean weekly-max difference with sign-flip inference, and
   McNemar discordant pairs
   (`research/paired_max_stats.paired_weekly_max_report`).
3. **Prior (stated before any result):** shoulder-class, small. The
   expected effect is a modest recovery of the slate-varying silent tax
   on effective boom supply; a null closes the lever (delete it), and no
   alternate unique-fill variant may be tuned from this result.
