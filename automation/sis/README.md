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

The first paid month is NFL-only. College acquisition is deferred to the 2027
CFB go/no-go review.
