# What lives outside the repo, and how to rebuild it on another machine

Operator note 2026-09-21: this workstation may be rebooted or replaced, so
nothing important may exist only on its disk. This records every non-repo
artifact this session created or depends on, and how to recover each.

## 1. Pinned Python interpreter — RESOLVED, now durable

The frozen research chains pin an exact interpreter binary
(`_PYTHON_EXECUTABLE_SHA256 = b8d8288f…`, 7,481,192 bytes). apt moved
`python3.14` from `3.14.4-1ubuntu0.1` to `0.2` on 2026-09-09 and **no longer
serves the old version**:

```
$ apt-get download python3.14-minimal=3.14.4-1ubuntu0.1 --print-uris
E: Version '3.14.4-1ubuntu0.1' for 'python3.14-minimal' was not found
```

So these two files are genuinely irreplaceable. They now live in the private
bucket:

```
gs://nfl-predictions-503414-raw/pinned-runtime/python3.14-minimal_3.14.4-1ubuntu0.1_amd64.deb
gs://nfl-predictions-503414-raw/pinned-runtime/python3.14_3.14.4-1ubuntu0.1_amd64.deb
```

Local convenience copies remain at `/home/erich/pinned-runtime/` and in
`/var/cache/apt/archives/`, but **neither is load-bearing any more**.

**Rebuild on any machine, verified by round trip today:**

```bash
gcloud storage cp gs://nfl-predictions-503414-raw/pinned-runtime/python3.14-minimal_3.14.4-1ubuntu0.1_amd64.deb .
dpkg-deb -x python3.14-minimal_3.14.4-1ubuntu0.1_amd64.deb /tmp/pinned
sha256sum /tmp/pinned/usr/bin/python3.14
# b8d8288faefdd300201f43fcf00f6f539a27218eeed3a3dff5ab10b9c4c99700  <- matches the contract
```

Downloaded fresh, the deb is byte-identical to the local copy and extraction
reproduces the contract hash and byte count exactly.

## 2. Week-3 chosen dose — RESOLVED by recording the decision here

`/home/erich/week3-sunday/chosen-dose.env` holds:

```
CHOSEN_LEV=2560
CHOSEN_BOOM=10240
```

**Operator decision 2026-09-21: hold the dose at the Week-2 level (the D12800
rung).** Reason: the dose is compute, not spend — it sets how many candidate
lineups are built, while `contests.json` sets what is actually paid for. The
Week-2 post-mortem found the winning lineup was buildable from players we had
priced and that **0 of 12,555 candidates matched it**, so narrowing candidate
coverage attacks the actual failure while saving no money. The entire Week-3
reduction in exposure is taken out of entries.

These values are **not secret** — `config/week-inputs-schema.md` already
publishes the same pair as the Week-2 example, in this public repository. Only
`contests.json` carries the stake plan. So recording the decision in git costs
nothing and makes the file reproducible anywhere: write those two lines.

The file is not yet in the private bucket because `week_inputs.py push`
deliberately takes the **pair** and pins them in one manifest, so a build can
never get one week's dose beside another week's contests. It goes up with
`contests.json` in a single push once DraftKings posts the Week-3 contests.

## 3. DK host ingest loop — local by nature, script is tracked

The loop writes `/home/erich/week1-sunday/host_ingest_dk_loop.pid` and `.log`.
A pid file is inherently host-local and should not be portable. What matters is
that the **script is tracked** (`scripts/host_ingest_dk_loop.sh`), so on a new
machine the recovery is to start it again:

```bash
PROD=<checkout of the integration branch> \
  setsid nohup ./scripts/host_ingest_dk_loop.sh >> <log> 2>&1 < /dev/null &
```

Run `--check` first. Note `PID_FILE` defaults to
`${OUT:-$HOME/week1-sunday}/host_ingest_dk_loop.pid`, and the script refuses to
start while a live pid is recorded there — that guard is what prevents two
loops double-pulling, so do not point `OUT` somewhere new to get around it.

## 4. Standing rule

Anything created outside a project directory must either be reproducible from
the repo, or be copied to the private bucket with its URI and hash recorded in
the repo. A file whose only copy is on one workstation's disk is not a stored
artifact; it is a pending loss.
