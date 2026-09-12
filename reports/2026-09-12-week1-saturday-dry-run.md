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

## Step 3 — staged upload (corrected: draftable IDs, not player IDs)

The first staged file was a copy of the D800 `book.csv`. That file is **not
importable**: the lab's `dk_csv` writes `dk_player_id` (its own docstring says
so), while DraftKings' lineup import matches on the slate-specific draftable
ID — the README data-deficiency log recorded exactly this on 2026-07-25
("pre-fix DK upload CSVs were never actually importable"). The audit's
"already DK-importable" assumption was wrong. It has been renamed
`…csv.NOT-IMPORTABLE-player-ids`.

`scripts/emit_dk_upload_csv_v1.py` (module
`nfl_dfs/inference/dk_upload_csv_v1.py`) now writes the importable file from
either a `live_week.py` run dir (player id → draftable id through the run's
own `frame.parquet`, every slot checked for position eligibility) or a
published book (`slot_dk_draftable_ids`, positions from the exact-reopened
salary catalog). Verified: the run-dir path on the 09-10 D800 run reproduces
the published 09-10 `P_CTRL` rosters 80/80 in rank order, and the published
path emits the 09-10 `P_MIX` book (80 rows) with terminal/book/catalog
identities in its receipt.

Do **not** "fix" the lab's `book.csv` in place: production's
`week1_live_pair_adapter.py` reads `book.csv` and maps every cell through
`dk_player_id` (lines 167–207), so a draftable-ID `book.csv` would break the
publisher. If the lab wants its own importable file it must be an additional
artifact (e.g. `book_upload.csv`); until then the production emitter is the
upload path.

Today's placeholder (audit §3.3 step 4, P_CTRL = D800 DEMAX of the 13:25Z run):
`/home/erich/week1-upload-P_CTRL-draftable-20260912T1325Z-fa5d035.csv`
(80 rows, sha256 `5b0e42291cf5c439d366d234e402137c8c906751b1755781ea65458e745b44e6`),
plus per-contest slices of the same book in `/home/erich/`:
`…-milly-193028206-ranks-1-57.csv`, `…-playaction-193028208-ranks-1-20.csv`,
`…-ffwc-q6-194478066-ranks-1-3.csv`, `…-ffwc-q5-194478065-ranks-1-10.csv`.

## Sunday procedure (audit §3.3)

Steps 1–2 are scripted: `scripts/week1_sunday_runbook.sh --run-id
20260913t<hhmm>z-fa5d035` builds D800 and D400 in the clone, verifies both
receipts (identity `fa5d035` clean, 80 written, canonical header, 80 unique,
lock/draft group), runs the publisher preflight WITHOUT `--execute` and
checks it (four distinct book hashes, P_MIX turnover ≥ 1), then prints the
exact `--execute`, emit and upload commands and stops. Rehearsed today in
reuse mode on the 13:25Z/13:31Z builds (`--paid-dir/--shadow-dir`): receipts
ok, preflight ok (`pmix_turnover_per_side=7`, 11 designations), exit 0.

1. ~09:30 CT: run the runbook (fresh salary pull and injury state).
2. Run the printed 4a command once (`--execute`; create-once, never two
   attempts on one run-id), then the printed 4b emit loop.
3. Emit the upload files from the published books — the paid book is P_MIX:
   `PYTHONPATH=src python scripts/emit_dk_upload_csv_v1.py --source published --terminal-uri <PUBLISH_ROOT>/<run-id>/terminal.json --book-id P_MIX --output <path>`
   (and `--book-id P_CTRL` for the fallback). Add `--ranks` per contest
   (audit §3.1): Millionaire `1-57`, Play-Action `1-20`, FFWC Q6 `1-3`,
   FFWC Q5 `1-10` — or the §3.4 unique-entry alternative if the operator
   chooses it. Then upload in the DK UI by ~11:15 CT (no scriptable upload).
   Never upload a `book.csv` directly. Lock 12:00 CT.
4. Operator decision still open (audit §3.4): unique vs duplicated entries
   across the 90 reservations.
5. Monday/Tuesday: `capture-dk-standings … --confirm-settled
   --confirm-full-field --apply`. This is load-bearing — `contest_entries` has
   never received a row and DK purges standings after ~4 days; it is the first
   chance to price placement for the entries lever (+13.55 at K80).
