# SIS DataHub Pro Playwright acquisition

Raw SIS files, cookies and credentials are excluded from Git. The browser uses
its own persistent profile under `~/.local/share/nfl-dfs/sis-playwright`; CSVs
and manifests will live under the root-gitignored `sis/` directory.

One-time login:

```bash
source .venv/bin/activate
pip install -e ".[browser]"
playwright install chromium
sis-download login --terminal-credentials
sis-download verify-login
```

The password is read with hidden terminal input, used only to fill the SIS
login form, and discarded. It is never logged or written to the repository.
SIS uses a session-scoped identity cookie that Chromium removes at clean
shutdown even when Remember Login is checked. The command therefore writes a
Playwright storage-state file next to (not inside) the external browser
profile. It contains the authenticated session but no plaintext password and
must be guarded like a credential. `verify-login` starts a fresh headless
browser from that state, so a successful verification proves later unattended
downloads can authenticate.

The bulk NFL exporter is being built around these fail-closed rules established
by the first trial files:

- every filter mutation must be followed by `Submit`;
- the rendered table must reflect the requested season/week/game scope before
  `Download`;
- the CSV must independently contain the expected Season/Week/Opponent/Games
  scope and differ from a prior broader query;
- `[object Object]` Rank is discarded;
- output at exactly the account limit (20 trial, documented 200 paid) is
  considered potentially truncated and must be split into narrower queries;
- raw CSVs remain local and a secret-free manifest records hashes, schemas,
  filters, row counts and retrieval times.

The first guarded single-export command is available now:

```bash
sis-download catalog
sis-download export \
  --entity players \
  --report pass-defense-value \
  --season 2025 --start-week 1 --end-week 17 \
  --team-id 1
```

The command always selects Split by Game unless `--aggregate` is explicit,
clicks Submit, verifies the exact POST scope and response rows, waits for the
rendered table to match, downloads through the visible UI, and independently
checks the CSV's season/week/opponent/game scope. Exactly 200 returned rows is
treated as truncation and rejected. Use `--team-id` to split capped queries;
team IDs are SIS's own values shown by the page filter. Incomplete downloads
use a `.partial` suffix and are never promoted to accepted artifacts.

Priority 1 covers the distinct inputs most likely to help DFS modeling:
passing/receiving/pass-defense/pass-rush/blocking value and their volume
denominators. Priority 2 covers rushing and run defense. Returning, punting
and kicking remain inventoried priority 3 sources, not omitted unknowns.

Every model feature built from these files must be point-in-time: for a target
week, aggregate only games completed before that target week's lock. A target
week's own SIS row is an outcome and may never predict that same week.

The first budgeted plan is tracked at
`automation/sis/plans/team-context-tranche-1.json`. Validate its expansion
without spending a query:

```bash
sis-download plan --file automation/sis/plans/team-context-tranche-1.json
```

It declares 108 artifacts (six replay seasons, three six-week windows, six
team-context reports) and a hard 500-API-request ceiling. An artifact can cost
several API requests because the normal UI refreshes on page, family, view and
Submit actions; do not equate artifacts with queries. The ceiling leaves half
the documented weekly allowance for retries and capped-query splitting. Bulk
execution is resumable and writes licensed data only below the ignored `sis/`
tree:

```bash
sis-download run-plan \
  --file automation/sis/plans/team-context-tranche-1.json \
  --output-dir sis/team-context-tranche-1
```

Every API request increments a durable run-state counter before it is sent;
restarts cannot reset the plan's hard ceiling. Existing artifacts are skipped
only after their manifest scope, SHA-256 and CSV scope revalidate. The runner
reserves four requests before beginning an artifact and the browser route
itself blocks any request beyond the declared ceiling. Each manifest retains
the stable SIS IDs and readable scope keys from the exact submitted response,
because the visible CSV omits the IDs.

The first paid month is NFL-only. College acquisition is deferred to the 2027
CFB go/no-go review.
