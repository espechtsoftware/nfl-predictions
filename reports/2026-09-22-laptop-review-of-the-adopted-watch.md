# Laptop → production: the adopted watch is right; its read-only test leaks

Review of `c293c6e2`. The adoption is correct and the commit message is the clearest
statement of the problem either of us has written — "a watch that exists only in a
process is not a watch". No objection to any of it.

The review finding is in the test.

## `test_the_watch_cannot_write_start_or_destroy_anything` is a denylist, and it leaks

Measured, not argued. Each probe appended to the adopted script, the sibling test run,
script restored:

| appended line | denylist |
|---|---|
| `bq load foo bar` | **CAUGHT** |
| `rm -rf /tmp/whatever` | slips through |
| `echo pwned > /tmp/evil.txt` | slips through |
| `bq extract ds.tbl gs://bucket/x.csv` | slips through |
| `curl -X POST https://example.com` | slips through |
| `gcloud scheduler jobs run s-project-tu` | **slips through** |

The last one is the one to look at. `MUTATING` pins `jobs execute`, `jobs deploy`,
`jobs update` and `jobs delete` — but not `jobs run`, which is how a Cloud Scheduler job
is force-fired. A watch armed hourly on the build host that could fire `s-project-tu` is
precisely the capability the test exists to deny, and the test says it is fine. `bq
extract` writes to GCS; `>` writes anywhere; `rm -rf` needs no comment.

This is not a criticism of the list. It is the shape of denylists over shell: the space
of mutating verbs is open, so the list is always one verb behind.

## Offered: an allowlist companion, not a replacement

`tests/test_week3_blocker_watch_allowlist.py` pins the complementary property, which does
not leak the same way:

1. only allowlisted binaries may be invoked (`bq`, `date`, `timeout`, `echo`, `tail`,
   shell builtins);
2. every `bq` invocation must be a query;
3. no redirection into a file (`2>/dev/null` and `>&` allowed).

**Verified in both directions.** It passes on the adopted script unmodified, and catches
**all seven** probes including the six above and `gcloud run jobs execute`.

Keep both tests. The denylist states intent and names the specific verbs this project has
been burned by; the allowlist bounds capability so the next unnamed verb is caught by
default. An allowlist alone would be silent about *why*.

### Two parsing notes, because a test that misfires is worse than no test

Getting this sound against real shell took two corrections worth recording:

- **Do not split command position on `{`** — it shreds `${VAR}` into fragments that look
  like commands.
- **Backticks here quote BigQuery table names, not command substitution.** They are
  stripped as data. Nested shell quoting (`"$(q "SELECT …")"`) also defeats naive string
  stripping, which is why quoted spans, backtick spans and `${…}` expansions are all
  removed before anything is treated as a command.

Both of my first two attempts failed **on the real script**, not on a probe. I fixed the
test rather than the script each time. Flagging that because a green allowlist that is
green for parsing reasons would be worse than the leak it replaces.

## Not done

Not wired into `scripts/test_lanes.sh`. It runs in the full suite as an ordinary test
file; adding it to the money lane beside its sibling is a one-line change and yours to
make. The script itself is untouched — I appended probes and restored it each time, and
the worktree was clean before any probe.
