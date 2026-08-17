# DST Phase D0 canonical event-frame implementation

Date: 2026-08-17
Status: source/schema and offline gate implemented; warehouse population and
historical support census deliberately not run while ATLAS owns the historical
outcome/heavy chain

## Result

`sql/features/024_team_defense_week.sql` now exposes one versioned team-game
DST event frame without changing the canonical `dst_dk_points` choice used by
existing consumers. The additive fields include:

- `game_id`, normalized team/opponent, opponent final score and computed PA;
- excluded offensive pick-six/fumble-six and safety points, separately and in
  aggregate, with no zero-clipping and exact reconciliation to the reciprocal
  DST's defensive-return and defensive-safety event counts. The shared
  nflfastR offensive-play predicate is exactly `pass`, `run`, `qb_kneel`, or
  `qb_spike`; a punt safety remains charged to the reciprocal DST's PA;
- sacks, interceptions, opponent fumble recoveries, safeties, blocked kicks,
  return touchdowns and defensive conversion returns;
- the PA-tier contribution and complete reconstructed DK score;
- the nullable authoritative historical score, raw/matched/rejected source-row
  counts, distinct-score count, source-conflict status, canonical chosen score,
  reconciliation delta and explicit status;
- the dated event-frame/scoring-law IDs, official-source SHA-256, canonical
  JSON event payload and its independently reproducible team-game SHA-256; and
- strictly-prior L4 and L16 means for every component and PA, with prior-game
  support counts. L4 resets by season; L16 can use prior-season run-up. Every
  SQL frame ends at `1 PRECEDING`.

The prior omission of `defensive_conversions` from the selected output schema
is corrected. Existing columns retain their exact leading order through
`dst_points_l16`. New rolling columns are prefixed `dst_event_`, avoiding
collisions with the aliases created by `research/dst_tail.py` after its
`SELECT d.*`. A composed BigQuery dry run compiled that existing consumer
against the prospective schema.

## Fail-closed consumer gate

`src/nfl_dfs/research/dst_event_frame.py` independently validates a populated
frame before any future D1 event-ledger fit. It rejects:

- null, duplicate team-game or duplicate team-week keys;
- games without exactly two reciprocal team/opponent rows;
- negative/fractional event counts, clipped/impossible PA, exclusions outside
  their 6/2-point units, or exclusions not exactly supported by the reciprocal
  DST event row;
- any divergence from the canonical executable DST scoring contract;
- malformed law/source hashes, a changed frame version, a payload that differs
  from the row, or a SHA-256 that differs from the canonical payload;
- unmatched, conflicting, or even partially rejected authoritative source
  rows, mislabeled authoritative overrides, or authoritative per-season counts
  that differ from the caller's mandatory strict coverage contract; and
- any L4/L16 value that is not exactly reconstructible from completed prior
  rows.

The strict default also rejects every authoritative-score/reconstruction
difference and refuses to run without an exact per-season authoritative-row
coverage contract. A diagnostic mode can inventory such differences and
season-level nonzero/tail support, but its receipt explicitly does not license
a fit. The support census reports, by season, raw/matched/rejected source rows,
source failures, exact-label coverage, mismatch count, nonzero support for
every event component, and canonical/reconstructed 15+/20+/25+ counts.

`src/nfl_dfs/models/dst_scoring.py` now owns the same offensive-play predicate
used by the recourse scorer, while the warehouse SQL pins its literal form.
The recourse scorer no longer clips negative PA; impossible scoreboard/event
accounting fails closed with its game/team identity.

## Validation

The rendered production BigQuery statement was submitted as a dry run and
validated successfully. Its reported processing upper bound was 66,630,074
bytes; no table was created or replaced. A second dry run composed the
prospective table query with the existing `DST_TAIL_SQL` consumer and compiled
successfully, proving the new prefixed fields do not create duplicate-alias
ambiguity.

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_dst_event_frame.py tests/test_dst_scoring_law.py \
  tests/test_feature_sql.py tests/test_recourse_scoring.py
passed (one existing skip)

.venv/bin/python -m compileall -q \
  src/nfl_dfs/research/dst_event_frame.py
passed

git diff --check
passed
```

The focused fixtures prove season-reset L4 windows, cross-season prior-only
L16 windows, exact four- and sixteen-game truncation, reciprocal opponent/event
accounting, payload/hash tamper detection, strict source-conflict and coverage
closure, strict score-mismatch closure and a diagnostic mismatch census. DST
scorer parity fixtures separately cover offensive pass/run/kneel/spike
safeties, a punt safety, and negative-PA rejection.

## Remaining D0 gates

This milestone does not populate or inspect the physical table. Once ATLAS
and the historical-outcome lease close, D0 still requires:

1. rebuild the table from an exact committed SQL version and record the query
   job/table generation/schema receipt;
2. run the strict physical support census across the configured seasons;
3. explain or repair every authoritative/reconstruction mismatch before the
   strict gate can pass;
4. record exact per-season source coverage and support; and
5. implement reusable common-lock odds/weather selectors and their
   `pulled_at <= lock` assertions before those covariates can enter D1/D2.

No generated DST world, lineup score, selector result, production policy or
ATLAS artifact was opened or changed here.
