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

For each standalone SIS retrieval session, deliberately replace the old token
before starting the unattended download:

```bash
sis-download login --terminal-credentials --fresh
```

The combined Wednesday workflow does this forced SIS logout/login
automatically every time it runs. This avoids beginning a long acquisition on
an apparently valid but aging SIS session.

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

Each family/view is also checked against a small required-column signature and
the exact submitted `MetricGroupSubType`. This is necessary because a 2026-08-13
audit found that SIS team Passing Value can return Value fields in its API
response but render/export the Totals table after a split-by-game Submit. Those
artifacts are invalid even when their row count, season, week and opponent
scope are correct. See
`reports/2026-08-13-sis-tranche-2-subtype-defect.md`. Do not resume tranche 2
or import it until its reduced recovery plan is frozen; its durable counter is
337/440 and must not be reset.

The first paid month is NFL-only. College acquisition is deferred to the 2027
CFB go/no-go review.

## Weekly operator integration

The Wednesday 10:00am CT command `nfl-weekly-data run --week W` forces a fresh
SIS logout/login, then verifies the replacement session alongside Fantasy
Points before unattended data work starts.
It submits zero SIS queries in target Weeks 1--4. Beginning in target Week 5,
the evidence-approved prospective pass-tail shadow automatically submits the
five exact split-by-game views frozen in
`reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md`: all-view
Pass Defense Totals/Value and Pass Rush Totals, plus Wide/Slot Pass Defense
Totals. Week 5 bootstraps source Weeks 1--4 and later weeks retrieve W-1 only.
The durable ceiling is seven Submit requests, raw bytes are archived by hash,
and imports fail on scope/provenance conflicts. Other `--sis-plan` inputs
remain opt-in and must be separately evidence-approved; the historical
team-context/alignment tranches are never valid weekly plans.

The next bounded nonweekly feasibility screen is frozen separately:

```bash
sis-download team-pass-defense-schema-sample
```

It makes exactly eight scientific normal-UI Submit requests for 2025 Week 1
team pass defense: Wide/Slot crossed with broad Man/Zone, each in Totals and
Value. Its analyzer reads only scope, identity, row counts, headers and hashes;
it never reads performance values. A ten-call durable ceiling permits no more
than two identical operational retries. This is a one-time schema/cap gate,
not a recurring SIS plan and not a model feature. Its frozen protocol is
`reports/2026-08-13-sis-team-pass-defense-schema-protocol.md`.

The frozen, one-game receiver/corner alignment feasibility sample is run as:

```bash
sis-download alignment-sample
```

It uses one browser session, seven predeclared alignment slices and a durable
12-request ceiling. It reads only receiver Routes and defender Coverage Snaps
for its concentration decision; raw rows and the durable request state remain
under `sis/alignment-feasibility-v1/`. Its frozen protocol is
`reports/2026-08-13-sis-alignment-feasibility-protocol.md`.

The dormant alignment sample's immutable `7/12` counter must not be reset. A
separate one-query player-grain denominator check is frozen as:

```bash
sis-download player-pass-defense-grain-sample
```

It uses 2025 Weeks 1--18, SIS team ID 1, CB versus Wide WR, Pass Defense
Totals, Split by Game. Incidental refreshes are blocked and its own durable
three-request ceiling permits at most two identical operational retries. The
gate reads only request scope, schema, stable identities, game scope and row
counts; it never reads performance values or fantasy/lineup outcomes. Run it
only after `sis-download login --terminal-credentials --fresh`. Its protocol
is `reports/2026-08-15-sis-player-pass-defense-grain-feasibility-protocol.md`.

That schema gate passed and licenses one bounded receiver-copula history. Run
the create-only, resumable acquisition only from a freshly verified session:

```bash
sis-download receiver-copula-history
```

It retrieves exactly 144 Player Pass Defense Totals slices: 2022--2025,
Weeks 1--18 individually, Wide then Slot, CB versus WR, all teams and Split by
Game. A permanent 150-Submit ceiling allows at most six identical operational
retries. Raw rows and partial/final manifests remain gitignored under
`sis/receiver-copula-v1/`. The protocol hash, row cap, submitted filters,
schema, stable player/team identities and numeric source columns are checked
before the data can enter the separately score-free dependence treatment.
This is a one-time historical acquisition, not part of the weekly production
schedule unless the later dependence gate licenses a 2026 paired shadow. Its
frozen contract is
`reports/2026-08-15-sis-receiver-copula-protocol.md`.

After tranche 1 completes and its private table is verified, the bounded
second plan is `plans/team-context-tranche-2.json`: team Passing,
Rushing and Run Defense Totals/Value for the same six replay seasons. These
complete the most distinct QB/RB/offensive-line/opponent-front context before
spending requests on granular player/gap splits or special teams. It declares
108 artifacts and a 440-request ceiling; combined with tranche 1's observed
440 requests, it stays below the documented weekly allowance while retaining
headroom for the earlier paid-surface audit calls.

The subsequent coverage-gap audit confirmed that team Receiving was named in
the original priority-1 inventory but was never acquired. Its bounded research
plan is `plans/team-receiving-v1.json`: Receiving Totals/Value over the same
six seasons and three cap-safe week windows, 36 artifacts and a hard 160-call
ceiling. Validate it without spending a request:

```bash
sis-download plan --file automation/sis/plans/team-receiving-v1.json
```

Do not run it in an old browser session or assume remaining provider budget.
At the next acquisition window, first use
`sis-download login --terminal-credentials --fresh`, verify login and provider
budget, then run it into `sis/team-receiving-v1/`. This is historical research,
not a weekly recurring plan, until a score-free feature gate passes.
