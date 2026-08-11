# 2026 Route Share operating contract

Status: frozen on 2026-08-11 before any 2026 Route Share value or outcome was
available. This is a prospective operating contract, not a reinterpretation
of the closed historical Route arms.

## Weekly collection

For target Week W, collect only Fantasy Points Weekly Route Share for the
single completed source Week W-1. The checked-in plan declares target Weeks
2--18 and the downloader's `--target-week W` selector executes exactly one
export. Week 1 uses the labeled prior-season/no-current-season fallback; it
must never pretend that a 2026 observation exists.

The browser must verify the selected season and week after Apply, the response
scope, CSV schema and rendered game count. The manifest records the target
week, source week, retrieval time, URL, bytes and SHA-256. A source week equal
to or later than the target week fails closed.

## Immutable archive and idempotent ingest

The implemented ingest step:

1. require one complete downloader manifest and one successful Route Share
   artifact for the declared season/target week;
2. re-hash the bytes and reject manifest, schema, season, source-week or value
   range drift;
3. archive the exact bytes under a hash-addressed GCS object using a
   create-only generation precondition;
4. resolve players from point-in-time 2026 roster/ID data, retaining unresolved
   rows and surfacing their count rather than guessing;
5. append new `(season, source_week, player identity)` rows idempotently; an
   identical repeat is a no-op, while a different value or hash for an
   existing logical key is a conflict and cannot overwrite history; and
6. record ingestion time, source file/hash and resolution provenance.

The existing daily backup discovery includes every base table named
`nfl_raw.fantasy_points_*`; a focused test also proves that the actual
`fantasy_points_route_share` table is selected.

## Strict prior features and fallback

Training and live inference will consume the same four registered fields:
`fp_route_share_last`, `fp_route_share_l4`, `fp_route_share_jump` and
`fp_route_cross_season`. Every target row must carry the exact source
season/week, and a mechanical assertion must prove `source < target` in
season-week order. Missing, late, unresolved or unavailable Route data yields
null Route fields plus an explicit labeled fallback; it never blocks the
incumbent projection/lineup path.

The four fields are now built symmetrically into training and inference by
`017k_fantasy_points_route.sql`, with a runtime leakage assertion over every
nonnull source season/week. The 2026 Route model and lineup books remain
shadow-only until their
prospectively frozen scoring gate is satisfied. Production cannot inherit an
`EXTRA_FEATURES` shell variable or a partial weekly download.

## Timing and operator checklist

Collection should run after Fantasy Points posts the completed week and before
the next projection/training chain. The first live weeks must record the
vendor refresh time; until that is known, Tuesday/Wednesday collection is
manual and the importer must report staleness. The in-app Weekly guide will
show the exact command, source/target week, latest successful hash, unresolved
count, backup status and fallback label once the ingest/shadow implementation
is complete.

The operator sequence for target Week W is:

```bash
fantasy-points-download run \
  --plan automation/fantasy_points/plans/2026-route-share-weekly-v1.json \
  --target-week W
nfl-dfs import-fantasy-points-route-weekly \
  --input-dir fantasy-points/automated/<completed-run> --target-week W
nfl-dfs import-fantasy-points-route-weekly \
  --input-dir fantasy-points/automated/<completed-run> --target-week W --write
```

The first import is the mandatory read-only audit. The second archives and
appends only after that audit is reviewed. UI surfacing and the independently
graded 2026 shadow execution remain the next implementation steps.
