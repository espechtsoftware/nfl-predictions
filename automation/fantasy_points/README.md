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

### Projected-ownership website session

Fantasy Points serves projected ownership from `www.fantasypoints.com`, not
the Data Suite host. The current sites require a separate ordinary web session
in the same persistent profile. Before the 2026 ownership collector can be
frozen, authenticate that surface with:

```bash
fantasy-points-ownership login --terminal-credentials
fantasy-points-ownership verify-login
fantasy-points-ownership inspect
```

`inspect` emits only relevant control labels, column headers and visible grid
counts. It does not capture player rows. That deliberate stop prevents the
project from guessing an offseason/signed-out DOM or claiming a collector is
ready before the real licensed DraftKings Classic Sunday Main table is
visible. Once authenticated data is posted, freeze and test the normal UI
context/apply/export contract before enabling any snapshot intake.

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

The frozen QB shell-fit follow-up collects the complete strictly-prior
Offense Coverage Matrix grid with:

```bash
fantasy-points-download run \
  --plan automation/fantasy_points/plans/same-season-qb-shell-fit-last-four-v1.json
```

This is a one-time historical research plan, not a weekly download. It must be
paired with the already accepted last-four Defense Coverage Matrix windows and
used only under
`reports/2026-08-13-fantasy-points-qb-shell-fit-protocol.md`.

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

## Weekly operator command

Run the combined acquisition workflow every Wednesday at **10:00am America/
Chicago**. Week 1 captures odds/matchups and automatically skips Route Share;
strict-prior Route Share begins with target Week 2:

```bash
source .venv/bin/activate
nfl-weekly-data run --week W
```

It verifies the saved Fantasy Points session and deliberately forces a fresh
SIS logout/login before starting the long work. It then continues on its own.
The run triggers the deployed `ingest-odds` Cloud Run job (whose API key stays
in Secret Manager), downloads and writes the strict-prior Route Share import,
and captures/archives the three Fantasy Points matchup reports. Beginning in
target Week 5 it also runs the frozen grouped-header
`2026-alignment-last-four-weekly-v1` export for exact Weeks W-4--W-1, plus the
five registered SIS pass-tail views. Week 5 retrieves SIS source Weeks 1--4;
Weeks 6--18 retrieve only the newly completed W-1. Both importers archive raw
bytes by SHA-256 and append only novel rows to the existing licensed tables;
any target/future week, schema drift or provenance conflict aborts. It records
a durable local manifest below ignored `weekly-data-runs/`. If completed data
has not posted by 10:00am, retry Wednesday evening; Route Share must finish
before `s-features-route` Thursday at 6:30am and Week-5+ pass-tail inputs must
finish before the isolated caches at 9:15/9:20am CT.

This on-demand Odds API snapshot supplements rather than replaces the normal
game-odds schedule (9:00am and 3:00pm CT Wednesday-Sunday). Player props keep
their Thursday 11:00am CT cloud schedule; use `--include-props` only for an
intentional extra snapshot because each provider request consumes quota.

Before Week 5 SIS is deliberately session-checked without a query. From Week
5 the default command spends exactly the five normal-UI Submit requests
licensed by the prospective pass-tail protocol, under a durable seven-request
ceiling that reserves two identical operational retries. `--sis-plan` is
still available only for a different evidence-approved declarative plan; it
does not replace or broaden the pass-tail acquisition. Never point the weekly
command at a closed historical research tranche. Emergency audit switches
`--audit-only-alignment` and `--skip-sis-pass-tail` are fail-closed diagnostic
controls, not permission to run the downstream caches with missing inputs.

## Prospective matchup snapshots

QB Coverage Matchup, WR Coverage Matchup and OL/DL Matchups have no historical
Season surface. They are captured as future research data, never substituted
for the rejected offseason samples. Before the target week's first kickoff:

```bash
fantasy-points-matchups --season 2026 --week W --archive
```

The command selects and verifies Schedule Week W, keeps the vendor's documented
All/default input window, presses Apply, records each values-response contract,
downloads the three grouped-header CSVs, and rejects the entire capture unless
every team/opponent pair exactly matches `nfl_raw.schedules` for 2026 Week W.
It also labels Weeks 1--3 as the vendor's early-season/prior-season regime and
requires active-season inputs from Week 4 onward. Passing bytes are archived
under create-only hash-addressed GCS names. These snapshots are collection-only
until a separate future scoring protocol passes.
