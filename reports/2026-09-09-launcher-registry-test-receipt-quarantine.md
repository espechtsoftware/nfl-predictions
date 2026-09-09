# Launcher-registry false test receipt quarantine

Date: 2026-09-09

The former PREREG-076 entrypoint regression invoked the production launcher
with no arguments. After the checked-in release became bound, test runs could
acquire the real shared launcher registry and emit a terminal completion even
though they stopped before any provider execution. Production repaired the
test at nfl2 commit `e3f91a1` so it now passes an intentionally invalid
argument and refuses before registry acquisition.

Seven such test-only completion records remained in the live
`launcher-completions` directory and were newer than the genuine PREREG-076
R2 completion. Each had exit status 1, completed in zero or one second, had no
live launcher receipt, and originated in a temporary review/test worktree.
They were moved intact—not deleted—to:

`/home/erich/.local/state/nfl-dfs/lab-launcher-registry/quarantine/false-test-invocations-20260909/`

Exact record keys:

- `01cf32032c5d4b6cfd2ea53cfc4fbee972b252c7aec7a80170fbe2f3f0629164`
- `2dafe28c0c0e39a875ce6da583058fa17b03775976ebf0cb9ec6d500968ab3aa`
- `306f14ff85184eb740fe287f1ea326426830c11f491b86a605c09145b759c53b`
- `553513c466c637907fef0f8220f87b66bd23284424cd3e1a3bccd7161b27e23b`
- `896e05fb3d6c62d62f000248d62c50f183a5a3ee88802afa3944afe076c52189`
- `b3e0a1ac82885e2923ae6fa3c37760fc58b80bc76220e9f05307dcc6ffd021ea`
- `bcc3a231da9adbd894c64407ed14ff65d0c78d2b1a8543569c8334c1bd4fa76d`

No Cloud Run execution, build, GCS object, experiment result, score, outcome,
or DraftKings state was created, changed, or removed by this quarantine. The
records remain fully recoverable from the directory above.

The first required cold restart exposed a separate bootstrap defect: it
replayed all older immutable failures as new once and selected the newest old
success prefix as current queue work. The monitor is now covered by explicit
stale/recent terminal tests, including the next poll after bootstrap, and
applies a 900-second cold-start lookback. Older records remain visible and
integrity-checked but are baselined rather than replayed or selected as current
work. Deployment and two-poll steady-state evidence are recorded in
`HANDOFF.md` after activation.
