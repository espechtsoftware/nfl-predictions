# The backup-QB gate was built three days ago and never shipped

Operator asked, reasonably, whether the backup-QB problem had already been addressed.
It had been **built and validated** — and then neither merged nor deployed, which is why
the Week-2 pool measurement still found a fifth of every lineup on a quarterback who
would not play. This records the verification, the merge, and what the operator has to
run for it to reach Week 3.

## What existed, and what it actually covered

| piece | state before today | what it does |
|---|---|---|
| `scripts/qb_flags.py` → `vet_book.py`, `vet_replace_v4.py`, `gen_sheet.py` | **live in Week 2** | builds a QB availability table for **Sunday book vetting** — inspects the book after it is built |
| `production/qb-availability-gate-20260919` (`cascade_adjust.find_backup_qbs`) | **built, tested, NOT merged, NOT deployed** | zeroes backup QBs **at projection time**, upstream of generation |

The two operate at opposite ends of the chain, and the measurements match exactly: the
Sunday vetting worked — only **1 of 97** entered Week-2 rows used a cheap never-played
QB — while the pool it selected from was never protected, so **19.5% (W1) / 20.0% (W2)**
of candidates carried one.

## Verified not-deployed

- None of the four gate commits (`027d1220`, `2855cba1`, `d879beba`, `8dd7abc9`) were
  ancestors of the integration branch.
- The gate is not in `cf630a68`, the commit the live image was built from.
- The live job confirms it: `project-slate` runs
  `…/nfl-dfs:week3-market-source-cf630a68`.
- The integration tree's `cascade_adjust.py` contained no `QB_BACKUP_GATE` code.

No hold reason was recorded on the branch; it carries 13 tests, a live-frame propagation
measurement, and an env rollback. It was built the Saturday of Week 2 and missed the
merge before Sunday.

## Dry-run on the real served Week-2 frame

Applied `find_backup_qbs` to the archived Week-2 frame — the actual served columns, not
a reconstruction. **The gate fires.**

- **38 QBs zeroed**, 304.1 served projection points removed
- largest: Bagent 16.55, Keenum 15.55, McKee 14.31, Ehlinger 14.26, Lance 13.75,
  Stidham 13.50, Dalton 13.48, Mills 13.12 — all $4,000–4,200, all depth 2–3
- **3,514 of 12,555 Week-2 pool lineups (28.0%) used a QB this gate would have zeroed**

## The two repairs are complementary, not overlapping

The gate **deliberately** leaves a team alone when its primary is Doubtful — the
propagation report names the case: *"ATL (Penix Out → Tua is the shallowest non-out QB
but Doubtful → team left alone: Tua 17.47)."* Tua is exactly the player who put five
dead rows into the entered Week-2 book. Confirmed in the dry run: **Tua is not gated.**

The Doubtful exclusion closes that hole, and it is **already live** for Week 3 — the
pinned live clone `week3-live-center` sits at `EXPECT_SHA=69f98a75…`, clean, with
`DK_INACTIVE_STATUSES = {"O","OUT","IR","D"}`. Together: the gate removes backups behind
a *healthy* primary; the Doubtful rule removes the ambiguous-primary players the gate
declines to touch.

## Merged here, plus one gap closed

Merged `production/qb-availability-gate-20260919` into the integration branch. Also added
`tests/test_cascade_adjust.py` to `cloudbuild.week1-live.yaml` — **the build lane did not
test the gate**, so the image would have carried it unverified.

## What the operator must run — the harness cannot

The gate only reaches Week-3 projections through the **image**, because `project-slate`
runs on Cloud Run. `project-slate` has **not yet run for Week 3** (still behind
build-features → tabpfn-gen), so there is still time, but the order matters:

1. `gcloud builds submit --config cloudbuild.week1-live.yaml` from a checkout of this
   branch (the full `cloudbuild.yaml` times out at its 3-hour ceiling — do not use it).
2. `gcloud run jobs deploy project-slate --image <new tag> --region us-central1` — an
   **update of the existing job**, never a creation (us-central1 is at the 1000-job
   quota).
3. Then run `project-slate` for Week 3, and verify from the job log that the gate fired:
   `backup-QB gate: zeroed N QB(s) listed behind a healthy primary`.

**Rollback needs no redeploy:** `QB_BACKUP_GATE=0` as a job env var.

## What this is worth, stated honestly

The selector already avoids these rows, so this is **not** a direct scoring gain on the
delivered book — it is generation efficiency, reclaiming roughly a fifth to a quarter of
pool capacity currently spent on candidates selection will not use. Priced against the
measured logarithmic ceiling law (~7 points per e-fold), that is about **1.7 points of
pool ceiling**, not the ~35 a winning line needs. It is worth doing because it is a
correctness fix that works regardless of the simulator regime, not because it wins a
tournament.
