# SIS tranche-2 Passing Value export defect

Date: 2026-08-13. No tranche-2 table has been imported or used by a model.

## Finding

After a cooled restart, the guarded tranche advanced to 82/108 local CSV/
manifest pairs and 337/440 durably counted UI API requests. A cross-view hash
audit found 14 team Passing Totals/Value pairs with byte-identical CSVs. The
files named Passing Value contain the Totals header (`Games`, `Dropbacks`,
`Gross Yds`, etc.), not the Value header (`Points Earned`, `PE Per Play`,
`Boom%`, `Bust%`). They are invalid regardless of their scope and hash
manifests.

An authenticated no-write browser diagnosis proved a site/UI inconsistency:
the Value menu and Submit send `MetricGroupSubType=1.3`, and the API response
contains Value fields, but after a split-by-game Submit the rendered DataTable
and visible Download revert to the Totals schema. Rushing Value and Run Defense
Value do not exhibit this problem.

## Scope

- Tranche 1: 108 artifacts, 54 paired view scopes, zero duplicate cross-view
  hashes and all six importer schemas exact. The write-once table
  `nfl_raw.sis_team_context_game` and the current QB line arm are unaffected.
- Tranche 2: the 14 extant Passing Value artifacts are invalid. Other report
  families remain candidates but the tranche as a whole may not be imported.
- No result or model consumed tranche 2.

## Repair

The exporter now binds `MetricGroupSubType` explicitly to the selected menu
value; requires it in both report-view and submitted-response predicates;
requires small per-report CSV schema signatures; and waits for both the API row
count and expected DataTable columns. A real Passing Value split-by-game smoke
now fails closed on the site's Totals rendering rather than accepting mislabeled
bytes. Focused SIS acquisition tests pass.

Do not delete or overwrite the invalid licensed files automatically. Preserve
them as private evidence, list their hashes in a local quarantine manifest, and
exclude them from all import completeness checks. The durable plan counter
must remain 337/440. Freeze a reduced recovery plan before further queries; do
not retry Passing Value until a distinct normal-UI workflow proves both the
rendered and downloaded Value schema at game grain.
