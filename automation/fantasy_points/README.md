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

## Adding or changing recurring exports

Plans are declarative JSON. `seasons` and `week_windows` form a Cartesian
product. A window can be `"1-4"`, `"1,3-5"`, or a list such as `[1, 2, 3]`.
Keep group headers enabled for Advanced and grouped coverage reports because
their repeated bare column names otherwise become ambiguous.

For recurring or bulk historical collection, replace `week_windows` with
`target_weeks` plus one `source_window` policy:

- `cumulative-prior` selects Weeks 1 through W-1.
- `last-four-prior` selects at most the four weeks immediately before W.

The generated filename includes `target-week-W`, and plan validation rejects
Week 1 or any source week that is not strictly earlier than its target. This
lets one plan safely expand all historical seasons/weeks without manually
enumerating dozens of exports.

Do not add every available report to the weekly plan. The recurring plan will
be frozen only after evidence identifies the reports worth operating. For a
target Week W, its plan may include only completed source weeks `< W`; the
downloader records the filters but does not weaken that research rule.

The automation intentionally runs sequentially with a delay between exports.
It uses only the normal authenticated UI and does not bypass access controls.
