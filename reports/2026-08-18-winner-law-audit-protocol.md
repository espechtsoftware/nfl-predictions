# Winner-lineup law audit — protocol (DRAFT for operator freeze)

**Protocol ID:** `20260818-winner-law-audit-v1`
**Status:** DRAFT — not frozen. The operator must approve this document,
pin its SHA-256, and bind the exact artifact manifest before the runner
executes. Execution is exactly once per frozen protocol version.
**Class:** outcome-aware diagnostic. `uses_realized_outcomes=true`;
no fit, no tuning, no gate, no promotion, no closure, no production change.
**Origin:** idea N1 in
`reports/2026-08-18-high-score-challenges-assessment.md` (Part III).

## Question

For each known Millionaire Maker winning roster on a slate with archived
production world artifacts, where does its realized winning score sit
within its own simulated total distribution under the archived production
law? Systematic mass at and beyond the 99.9th percentile of the roster's
own distribution is a direct, dollars-weighted measurement of missing
co-boom mass — on exactly the lineups the program is trying to build, and
independent of our generator and selector.

## Population

- Winner rosters: the two tracked sources loaded by
  `research/real_winner_overlap.load_known_winner_rows` (2019–2024 CSV and
  2025 rosters CSV), resolved to immutable snapshot IDs by the existing
  `match_known_winner_players` (nine unique IDs required per slate;
  resolution failure fails the run, it does not drop the slate).
- Slates: exactly those listed in the frozen artifact manifest — the
  intersection of known-winner weeks with slates whose archived artifacts
  carry `player_ids`/`player_draws` (the 2023–2025 corpus artifacts
  persisted with `CAND_ARTIFACT_PLAYER_WORLDS=1`). The manifest (paths +
  SHA-256 per artifact object) is bound at freeze time and is part of the
  frozen identity.

## Measurement (implemented, offline-tested)

`analysis/winner_law_audit.py` + `scripts/analyze_winner_law_audit.py`:

1. Per slate, load all listed world blocks, fail closed on universe
   mismatch, and concatenate on the canonical player order
   (`align_world_blocks`).
2. Sum the nine resolved winner rows per world
   (`winner_roster_world_totals`) — DST rows participate with whatever
   variance the archived law gave them (currently none; that constancy is
   part of the law being measured, not a defect of the audit).
3. Primary realized score: the sum of the nine `snapshot_actual` values
   (authoritative-scorer parity). The tracked winner-points sum is
   recorded as a descriptive cross-check only.
4. Report per winner: mid-rank percentile of the realized score within
   the simulated totals, `Pr_sim(total ≥ realized)`, simulated mean/sd
   and q50/q90/q95/q99/q999 (`audit_roster_under_law`).
5. Aggregate (`winner_law_report`): counts at/beyond the 95th/99th/99.9th
   percentiles, mean/median percentile, per-season split, full per-winner
   list. The report is written create-only with its SHA-256 printed.

## Interpretation rules (frozen with the protocol)

- Winners are field maxima over ~150k entries, so a correct law is
  EXPECTED to place them high in their own distributions; the
  single-roster tail anchors in the report are scale context, not a null.
- The decision-relevant readings, stated before any number exists:
  (a) winners repeatedly at percentile 1.0 with `Pr_sim ≥ realized` = 0
  (realized score above every archived world) is unambiguous missing
  joint mass; (b) concentration in [0.95, 0.999] without pile-up at 1.0
  is consistent with a thin-but-present tail; (c) season asymmetry
  localizes law drift.
- This audit CANNOT: rank repair mechanisms, adopt or reject any arm,
  reopen any closed family, or serve as an acceptance gate by itself. Its
  sanctioned use is as a second acceptance instrument alongside the
  194/210 book-tail calibration shape for the D-lane/S2 law repairs — a
  repair that improves both is stronger evidence than either alone.

## Fail-closed conditions

Any of: manifest slate without a nine-ID winner resolution; artifact
without player worlds; player-universe mismatch across blocks; fewer than
100 combined worlds; duplicate slates; output path already exists.

## Cost and lane

Hours, design lane, no heavy slot, no cloud simulation. Reads only
tracked CSVs, immutable snapshots, and archived artifacts.
