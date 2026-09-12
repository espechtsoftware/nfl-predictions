# Week 1 (2026-w01) Saturday dry run — money path rehearsal

**Date:** 2026-09-12 · **Governing document:**
`reports/2026-09-12-state-audit-and-week1-agenda.md` §3.3 · **Status:** complete,
nothing published, nothing uploaded, no outcome opened.

## What was rehearsed

The audit found that the previous session had worked only the research chains
and never touched the Week-1 money path. This dry run executes the audit's §3.3
Saturday procedure end to end, stopping exactly where §3.3 says to stop
(publisher without `--execute`; upload is a manual DK-UI step on Sunday).

Lock: 2026-09-13T17:00Z (12:00 CT). Draft group 151307. 90 DK reservations.

## Step 1 — live-pair rebuild (nfl2 clone at `fa5d035`, clean)

Clone: `/home/erich/projects/nfl2-week1-a5-sidecars-current-20260910`
(identity `fa5d035ba99928f71736cbb77222515e9cdd94a8`, `dirty: false`).
Salary pull for both runs: `2026-09-12 13:03:26Z`.

| arm | run dir (under `results/live/2026-w01/`) | lev/boom | candidates | written | unique | seconds |
|---|---|---|---|---|---|---|
| D800 (paid, `--emit-a5-sidecars`) | `20260912T132523949270Z-fa5d035` | 160/640 | 800 | 80 | 80 | 233.4 |
| D400 (shadow) | `20260912T133100344084Z-fa5d035` | 80/320 | 400 | 80 | 80 | 112.9 |

Command (D800; D400 differs only in `--lev 80 --boom 320` and no sidecar flag):

```
PYTHONPATH=<clone>/src /home/erich/projects/nfl2/.venv/bin/python scripts/live_week.py \
  --season 2026 --week 1 --group 151307 --selector dual_emax --lev 160 --boom 640 \
  --sims 10000 --k 1 --seed 2026 --entries 80 --emit-a5-sidecars
```

Both receipts: `selector dual_emax`, `operational_k 80`, `hsim_worlds 10000`,
`book_k80_is_nested_prefix: true`, DK Classic header
`QB,RB,RB,WR,WR,WR,TE,FLEX,DST`, 80 distinct lineups, zero DK violations.
Out-designated players are excluded upstream (warehouse deduped 5 Out / 3 Q;
none reached the frame). 76/80 D800 lineups changed relative to the 09-10 book,
as expected after two days of injury/news movement.

D800 sidecars present: `book_wemax.csv/json`, `incumbent_player_scores.npy`,
`corrected_hsim_player_scores.npy`. The publisher reads the sidecars from the
paid dir only; the shadow dir needs `book.csv`, `frame.parquet`,
`candidates.parquet`, `exposure_ledger.json`, `receipt.json` — all present.

## Step 2 — publisher preflight (NO `--execute`)

Worktree `/home/erich/projects/.nfl-predictions-worktrees/week1-publisher-20260912`
at `00c6097f6b369c7f28ff88a5b8db2c3c936e9c39` (tip of
`origin/production/nflverse-current-snap-absence-20260910`, clean).

```
PYTHONPATH=<worktree>/src python scripts/publish_week1_a5_books.py \
  --paid-run-dir   <clone>/results/live/2026-w01/20260912T132523949270Z-fa5d035 \
  --shadow-run-dir <clone>/results/live/2026-w01/20260912T133100344084Z-fa5d035 \
  --nfl2-source-root <clone> \
  --run-id 20260912t1331z-fa5d035 \
  --code-sha 00c6097f6b369c7f28ff88a5b8db2c3c936e9c39
```

Exit 0. Emitted preflight record (`week1-a5-four-book-preflight/v1`):

```
book_semantic_sha256:
  D400_DEMAX 442adeaddd5e1f74fc0870e81bec01a94ed94ebe7442d46a5b89f2530b28db05
  D800_WEMAX 59e29b265687531bbc120a7f9652a02191c2c20a1faefcc8aa82d43c1b710155
  P_CTRL     4b933452eeeda6c8a130f9e3da6760adf27b4fb7b91cca5a54bdb5e183847e67
  P_MIX      9ada53a319776c46e3ef3aac0003ad38048e4015dc40873c0a3b8a70c4b8df04
pmix_turnover_per_side: 7        designation_count: 11
history_rows: 1460 (seasons 2022-2025)
participation_map_sha256: 6f8603105dd83fe995c7c595b956eccfe216e4d6d18be2e97db6bf404dc667a6
execute: false   contest_entries_submitted: false   entry_allocation_published: false
```

The §3.3 check — *P_MIX turns over members relative to P_CTRL* — passes: seven
members per side differ and the four book hashes are pairwise distinct. The
pinned generation-shadow safety receipt (generation `1789079337043256`,
6,183,059 bytes) exists at the pinned identity. Nothing was written to
`gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/a5-books/` by this run
(create-once publish is gated behind `--execute`).

## Step 3 — staged upload

`/home/erich/week1-upload-P_CTRL-D800_DEMAX-20260912T1325Z-fa5d035.csv`
(81 lines) is byte-identical to the D800 `book.csv`. It is the Saturday
rehearsal artifact only; Sunday's upload must come from Sunday's rebuild.

## Sunday procedure (audit §3.3, unchanged)

1. ~09:30 CT: rerun both `live_week.py` commands above (fresh salary pull and
   injury state), verify receipts exactly as in Step 1.
2. Rerun the publisher with a new `--run-id` (`20260913t<hhmm>z-fa5d035`),
   first WITHOUT `--execute`; if the preflight record is sane, rerun WITH
   `--execute`. The publish is create-once; never two attempts on one run-id.
3. Upload the P_CTRL/P_MIX CSVs in the DK UI by ~11:15 CT (no scriptable
   upload). Lock 12:00 CT.
4. Operator decision still open (audit §3.4): unique vs duplicated entries
   across the 90 reservations.
5. Monday/Tuesday: `capture-dk-standings … --confirm-settled
   --confirm-full-field --apply`. This is load-bearing — `contest_entries` has
   never received a row and DK purges standings after ~4 days; it is the first
   chance to price placement for the entries lever (+13.55 at K80).
