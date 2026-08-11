# Fantasy Points Playwright downloader

This project automates licensed Fantasy Points Data Suite CSV exports without
putting credentials, cookies, or licensed data in Git. It uses a dedicated
persistent Chromium profile under `~/.local/share/nfl-dfs/` and stores exports
and manifests below the ignored `fantasy-points/automated/` directory.

## One-time setup

```bash
source .venv/bin/activate
pip install -e ".[browser]"
playwright install chromium
sudo .venv/bin/playwright install-deps chromium
fantasy-points-download login
```

The final command opens a separate browser. Sign in normally, wait for the
Data Suite dashboard, return to the terminal and press Enter. The profile can
be deleted to revoke the local session. The normal path never handles the
password, and neither path writes credentials to the repository.

If the launched browser cannot accept keyboard input (some remote/WSL display
setups do this), cancel it with `Ctrl+C` and use the terminal fallback:

```bash
fantasy-points-download login --terminal-credentials
```

The password prompt is hidden. The value is used only to fill the browser
form, is never logged or written to disk, and is discarded immediately after
submission. The resulting authenticated browser profile is still stored
locally so later downloads do not need the password.

## Historical window-semantics check

First validate the tracked plan and current vendor report catalog:

```bash
fantasy-points-download check \
  --plan automation/fantasy_points/plans/advanced-receiving-window-check.json
```

Then run the two exports:

```bash
fantasy-points-download run \
  --plan automation/fantasy_points/plans/advanced-receiving-window-check.json \
  --headed
```

The files are deliberately named with report, season and source-week window.
Each timestamped run directory contains `manifest.json` with the retrieval
time, vendor URL and filename, filters, byte count, CSV shape and SHA-256.
Failures preserve a screenshot and stop the run rather than silently
continuing with unknown filters.

If a reboot or browser failure interrupts a long plan, start a new immutable
run while reusing only the old run's mechanically revalidated successful
prefix:

```bash
fantasy-points-download run --plan <same-plan.json> \
  --reuse-from fantasy-points/automated/<interrupted-run-id>
```

The plan hash, ordered filters, artifact hash/shape and downloaded Season/G
scope are all checked again before a file is copied. A failed or mismatched
artifact is never silently resumed in place.

The paired Defense Coverage Matrix semantics plan uses the same two exact
windows:

```bash
fantasy-points-download run \
  --plan automation/fantasy_points/plans/coverage-matrix-window-check.json
```

Coverage Matrix is tested separately because same-season, strictly prior-week
defensive scheme usage is potentially distinct from the prior-season coverage
aggregates already evaluated. It remains subject to minimum-sample and
early-season shrinkage rules before any replay or live feature use.

The broader catalog audit plan samples the other highest-priority distinct
families plus the Offense Coverage Matrix view:

```bash
fantasy-points-download run \
  --plan automation/fantasy_points/plans/high-priority-window-check.json
```

The downloader establishes report context before selecting Season/Week(s),
presses `Apply`, and reopens Week(s) to verify the exact selection. Do not
remove that order: the vendor's active context link can reset filters.
It also waits for the exact report-values response, checks the request's
season/week payload, waits for the rendered game counts, and validates Season
and `G` in the downloaded CSV. Controls can update before the table, so none
of these gates is interchangeable with a fixed sleep.

The full-menu guard covers all 28 current NFL reports. Twenty-five have
historical Season + Week(s) surfaces supported by the downloader; the three
upcoming-matchup tools are catalog-guarded but intentionally excluded from
historical plans. The nine remaining historical families are exercised by:

```bash
fantasy-points-download run \
  --plan automation/fantasy_points/plans/remaining-catalog-window-check.json
```

This is an audit plan, not a recurring download list. Its basic, Bell Cow,
Routes Run and fantasy-points outputs are redundant operational evidence;
the sparse route-break/individual-route outputs require a separate frozen
protocol before any outcome use.

After the outcome-blind catalog/redundancy audit, the first historical
modeling collection is frozen to three reports and exact last-four-completed
week windows:

```bash
fantasy-points-download check \
  --plan automation/fantasy_points/plans/same-season-coverage-last-four-v1.json
fantasy-points-download run \
  --plan automation/fantasy_points/plans/same-season-coverage-last-four-v1.json
```

This is a sequential 168-export historical collection. Its tracked protocol
is `reports/2026-08-11-fantasy-points-same-season-coverage-protocol.md`.
Do not add other catalog fields to that run or inspect outcomes before the
protocol's importer and tests are complete.

The next sequential family is frozen in
`plans/same-season-advanced-passing-last-four-v1.json`: 56 grouped-header
Player exports covering the same four seasons and target weeks for Advanced
Passing only. Do not run it concurrently with the coverage plan or change its
80-dropback/model protocol after outcomes. Its importer command is
`nfl-dfs import-fantasy-points-same-season-passing --input-dir <completed-run>`.

The broad route-composition follow-up is frozen separately in
`plans/same-season-route-shape-last-four-v1.json`: 56 grouped-header Player
exports of Receiving Separation by Route Breaks. Its importer consumes only
the five count buckets after proving they partition Overall routes; it never
uses the report's outcome-like efficiency or separation fields:

```bash
fantasy-points-download run \
  --plan automation/fantasy_points/plans/same-season-route-shape-last-four-v1.json
nfl-dfs import-fantasy-points-same-season-route-shape \
  --input-dir fantasy-points/automated/<completed-run>
```

## Adding or changing recurring exports

Plans are declarative JSON. `seasons` and `week_windows` form a Cartesian
product. A window can be `"1-4"`, `"1,3-5"`, or a list such as `[1, 2, 3]`.
Keep group headers enabled for Advanced and grouped coverage reports because
their repeated bare column names otherwise become ambiguous.

For recurring or bulk historical collection, replace `week_windows` with
`target_weeks` plus one `source_window` policy:

- `cumulative-prior` selects Weeks 1 through W-1.
- `last-four-prior` selects at most the four weeks immediately before W.
- `previous-week` selects only Week W-1. This is the recurring Route Share
  contract; use `--target-week W` so a weekly run downloads one completed
  source week rather than every future declaration in the season plan.

The generated filename includes `target-week-W`, and plan validation rejects
Week 1 or any source week that is not strictly earlier than its target. This
lets one plan safely expand all historical seasons/weeks without manually
enumerating dozens of exports.

Do not add every available report to the weekly plan. The recurring plan will
be frozen only after evidence identifies the reports worth operating. For a
target Week W, its plan may include only completed source weeks `< W`; the
downloader records the filters but does not weaken that research rule.

The prospective 2026 Route Share plan is
`plans/2026-route-share-weekly-v1.json`. Beginning before target Week 2, run:

```bash
fantasy-points-download check \
  --plan automation/fantasy_points/plans/2026-route-share-weekly-v1.json \
  --target-week W
fantasy-points-download run \
  --plan automation/fantasy_points/plans/2026-route-share-weekly-v1.json \
  --target-week W
nfl-dfs import-fantasy-points-route-weekly \
  --input-dir fantasy-points/automated/<completed-run> \
  --target-week W
```

Run the import first without `--write`: it re-hashes the one artifact, proves
the manifest is the frozen plan and source Week W-1, checks the single-week CSV
scope, resolves players against point-in-time 2026 rosters and reports every
unresolved identity. After reviewing that audit, repeat it with `--write` to
create the immutable hash-addressed GCS archive and append only novel rows.
An identical repeat is a no-op; any stored value/hash conflict aborts. The
shadow feature step remains separately fail-closed, so a completed download or
import never authorizes same-week data in a target-week projection.

The automation intentionally runs sequentially with a delay between exports.
It uses only the normal authenticated UI and does not bypass access controls.
