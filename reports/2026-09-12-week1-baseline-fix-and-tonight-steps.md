# Week 1 — the baseline defect found tonight, and the specific steps to run before the morning decision

**Date:** 2026-09-12 (Saturday, ~11:45 CT) · **Lock:** 2026-09-13 17:00Z / 12:00 CT
**Author:** Claude (Fable 5.1). Everything below is outcome-blind: no realized
2026 score exists yet. Every number is a simulated, pre-lock receipt.
**Governing docs:** `reports/2026-09-12-state-audit-and-week1-agenda.md`,
`reports/2026-09-12-week1-saturday-dry-run.md`, `scripts/week1_sunday_runbook.sh`.

---

## 0. The one finding that changes tomorrow

**The lab live path (`nfl2/scripts/live_week.py`, the generator of tomorrow's
paid book) is building Week 1 on a collapsed projection level.** On today's
official 13:25Z D800 frame:

| player | lab model (`model_points_pre`) | props market | lab blended mean (what the book used) | production `proj_points` | last-season DK avg |
|---|---:|---:|---:|---:|---:|
| Jahmyr Gibbs ($8.0k) | 8.30 | 23.1 | 16.4 | 21.7 | 22.3 |
| Bijan Robinson ($7.7k) | 7.63 | 20.5 | 14.6 | 18.8 | 23.2 |
| Ja'Marr Chase ($7.8k) | 8.56 | 20.2 | 15.0 | 20.2 | 21.0 |
| Josh Allen ($7.0k) | 14.17 | 14.4 | 14.3 | 20.2 | 23.3 |
| Aidan O'Connell ($4.0k, QB3) | **14.80** | — | **14.8** | 7.7 | 4.8 |

Every RB projects ~8, every WR ~8.3, every QB ~14.5 — **a per-position
constant**: the lab component models receive all-null usage windows for Week 1
(`nfl_features.player_week_inference` 2026-W1 has `targets_l4`, `carries_l4`,
`snap_share_l4`, `xfp_l4` … = NULL for 100% of skill rows, `is_cold_start=TRUE`
— that is production's intended Week-1 law) and output the positional floor.
The 45/55 market blend rescues the 152 prop-covered players halfway; the 217
uncovered skill players (and every QB, whose props-derived mean is itself ~35%
low: top-12 QB market 12.9 vs production 20.6) ride the broken number.

Level check against history (lab panel, naive best-lineup projection
QB+3RB+3WR+TE+DST): 2023-W1 **150.7**, 2024-W1 **144.1**, season mean 159.4 —
today's official frame: **120.3**. Candidate simulated mean total 95.6 vs the
~117 the same machinery produces with sane means.

**Why the historical evidence never saw this:** the lab panel centres every
simulated marginal on production's `mean_projection`
(`NFL2_CENTER=mean`, `nfl2/pipeline.py:147`); the lab models only ever supplied
the *shape*. The live path instead takes its *level* from the lab models'
draw mean — a parity gap on every week, catastrophic in Week 1. Honouring the
warehouse `is_cold_start` flag (`nfl2/live.py:139` overwrites it with
`~has_features`) was tested first and changes nothing (Gibbs stays 8.30): the
cold-start prior fill does not rescue these models.

**The fix (built and verified tonight):** an env-gated change in
`scripts/live_week.py` — `NFL2_LIVE_CENTER=production` centres the skill draws
on production's `nfl_predictions.player_projections.proj_points` (latest
`generated_at` for the season/week; already market-blended, so no re-blend;
DST keeps the lab prior; 363/369 skill rows match by `gsis_id`, the 6 misses
are $2.5k long snappers). Default behaviour is unchanged when the variable is
unset. Local commit `3df1b0c` on lab branch
`lab/live-center-production-20260912` (not pushed, not merged; worktree
`<scratch>/nfl2-coldstart-probe`, being moved to
`/home/erich/projects/.nfl2-worktrees/live-center-production-20260912`).

### What it does to the book (same seeds, same machinery, 10,000 worlds)

| receipt (D800, K80, dual_emax) | official 13:25Z (lab level) | corrected 16:22Z (production level) |
|---|---:|---:|
| naive top-lineup projection | 120.3 | **153.9** |
| candidate mean total (incumbent bank) | 95.6 | 116.6 |
| book E[max], incumbent selection bank | 154.8 | **177.7** |
| P(book max ≥194 / ≥210 / ≥220 / ≥230), incumbent | .023 / .004 / .001 / .000 | **.190 / .050 / .018 / .006** |
| pool (800) E[max], incumbent | 166.2 | 187.6 |
| P(pool max ≥220 / ≥230), incumbent | .003 / .001 | .041 / .015 |
| book E[max], corrected-hsim law | 145.6 | 198.4 |
| P(book max ≥220), corrected-hsim | .000 | .133 |

The corrected level lands where the validated history sits (historical
simulated K20 E[max] under the incumbent law ≈174; realized K80 max ≈181).

**It is not only a level shift — it changes which lineups are chosen.** Scoring
the official book under the *corrected* incumbent bank: E[max] **171.8**,
P(≥194) .117, P(≥220) .009. The corrected book under the same bank: **177.7**,
.190, .018. Only 10/80 rosters are shared; 284/800 candidates overlap. (The
two runs differ by a 13:03Z vs 16:01Z salary pull; that accounts for little —
the 09-10→09-12 official rebuild changed 76/80 over two days of news.)

**Consequence:** the book published on 09-10 and the one the runbook would
build tomorrow are both on the broken level. The corrected build is the
baseline to enter unless the morning finds a reason not to.

---

## 1. Steps to run NOW (tonight), in order

Each step leaves an artifact the morning decision can point at. Times are
wall-clock on this workstation (one heavy process at a time).

### Step 1 — corrected D800/D400 from a clean commit (running; ~7 min)

The 16:22Z corrected pair was built from a dirty tree, which the production
adapter refuses (`identity.dirty must be False`). The same pair is being rebuilt
from the committed branch:

```
cd <worktree of lab/live-center-production-20260912>
NFL2_LIVE_CENTER=production PYTHONPATH=$PWD/src /home/erich/projects/nfl2/.venv/bin/python scripts/live_week.py \
  --season 2026 --week 1 --group 151307 --selector dual_emax --lev 160 --boom 640 \
  --sims 10000 --k 1 --seed 2026 --entries 80 --emit-a5-sidecars          # D800 paid
… --lev 80 --boom 320 (no sidecar flag)                                   # D400 shadow
```

Check the receipt: `identity.dirty=false`, `config.centering` names production,
`matched_skill=363`, `production_generated_at` = today's latest.

### Step 2 — governed publisher preflight on the corrected pair (~2 min, no `--execute`)

```
cd /home/erich/projects/.nfl-predictions-worktrees/week1-publisher-20260912   # 00c6097f, clean
PYTHONPATH=src /home/erich/projects/nfl-predictions/.venv/bin/python scripts/publish_week1_a5_books.py \
  --paid-run-dir <clean D800 dir> --shadow-run-dir <clean D400 dir> \
  --nfl2-source-root <worktree of lab/live-center-production-20260912> \
  --run-id 20260912t<hhmm>z-3df1b0c --code-sha 00c6097f6b369c7f28ff88a5b8db2c3c936e9c39
```

Pass = exit 0, four distinct book hashes, `pmix_turnover_per_side ≥ 1`. The
publisher records (does not pin) the `live_week.py` hash and source commit, so
the patched branch is admissible. Result recorded in §4.

### Step 3 — placeholder upload tonight (10 min, DK UI)

```
cd /home/erich/projects/nfl-predictions && PYTHONPATH=src .venv/bin/python scripts/emit_dk_upload_csv_v1.py \
  --source run-dir --run-dir <clean D800 dir> --ranks 1-57 --output /home/erich/week1-upload-CORRECTED-milly-1-57.csv
```
(and `1-20`, `1-3`, `1-10` for the other three contests, or the unique layout
in Step 4). Upload in the DK UI so the 90 reservations hold a sane book
overnight; Sunday's rebuild replaces it. This is P_CTRL-equivalent (DEMAX,
no participation mixture); P_MIX comes from the publisher tomorrow.

### Step 4 — decide the entry layout (operator, 5 min)

The A5 plan enters ranks 1–57 (Milly), 1–20, 1–3, 1–10 → **57 unique
lineups**. The only lever with a positive realized interval is more *unique*
entries (+13.55 K20→K80). For a weekly-max objective the alternative is 90
unique: build once with `--entries 90` (nested: ranks 1–80 identical to the K80
book) and slice Milly `1-57`, Play-Action `58-77`, FFWC-Q6 `78-80`, FFWC-Q5
`81-90`. Cost: the qualifiers/Play-Action carry lower-ranked lineups instead
of duplicating the top ranks (a payout-exposure choice, not a model change).
The emitter's `--ranks` supports either layout.

### Step 5 — dose ladder under corrected centering (~10 min, optional)

`--lev 320 --boom 1280` (D1600; the "1600 rung" the ledger calls
ladder-eligible after D800's +1.2). Report the same receipts as §0 under the
independent audit bank (seed 2126) and the corrected-hsim law. Adopt only if
both P(book ≥210) and P(book ≥220) rise without P(≥194) falling — and note the
instrument caveat: each law scores its own selections generously, so treat
the two laws as two views, never one as truth.

### Step 6 — DST concentration guard (~15 min, optional)

Both books lean on one DST (Chargers 59/80 official, 41/80 corrected) because
DST uses a salary-linear prior with no game context. A one-file post-selector
that re-runs `select_expected_max` with a per-player exposure cap (e.g. ≤ 30%
on DST, ≤ 40% on any player) is cheap and reversible. Report book E[max] and
tail probabilities with and without the cap; if the cap costs < 1 point of
E[max] under both laws it is worth the variance reduction. Untested
historically — a judgment lever; state it as such in the receipt.

### Step 7 — supply arms as shadow books (optional tonight, mandatory before Week 2)

All are preregistered in
`reports/2026-09-12-prereg-prospective-tail-supply-shadow-arms.md`; none may
enter the paid book except through the 8-slot sleeve rule there. Cheapest to
stand up on the live frame with existing code:

- **Relaxed-topology sleeve (084 `T_NOBB_TAIL`)**: 160 lev + 320 boom under
  house law, plus 160 boom under `StackRules(qb_stack_min=2, bring_back_min=0)`
  on worlds 161–320 via `generate_candidates(..., stack=LAW_NOBB,
  existing=cands, family_suffix=":nobb", world_order_override=…)`; select K80
  by DUAL_EMAX over the union. ~40 lines around `live_week.py`.
- **Direct-tail generator (PREREG-083)**: `direct_tail_world_order(frame,
  draws)` from `nfl2.prereg083_direct_tail` (branch
  `production/prereg083-r2-supply-gate-r1-20260910`) as the boom
  `world_order_override`; same union selection. Report expected exceedances
  at 200/210/220/230 vs control on the audit bank.

Freeze each as a run dir tonight; settle Monday with `scripts/settle_live.py`.

### Step 8 — do not do tonight

- Do not re-tune the blend weight, selector, or stack laws on the historical
  panel (opened outcomes; panel mining).
- Do not "fix" `book.csv` player ids in place (the adapter reads them).
- Do not publish a second create-once run under the 09-10 run id.
- Do not relax the adapter's clean-commit or exact-K gates to admit the dirty
  16:22Z pair; use the clean rebuild.

---

## 2. Sunday procedure, corrected

Production's `s-project-su` regenerates `player_projections` hourly at :00
(06:00–11:00 CT; `project-slate` takes ~4 min) with Sunday's injury cascade;
the corrected lab build reads the latest generation automatically.

| CT | action |
|---|---|
| 08:30–09:05 | confirm `s-nflverse`, `s-features-sun`, and the 09:00 `project-slate` execution succeeded (`gcloud run jobs executions list --job=project-slate`) |
| 09:10 | corrected D800 + D400 builds from the clean branch (Step 1 commands, `NFL2_LIVE_CENTER=production`); verify receipts as in Step 1 |
| 09:25 | publisher preflight (Step 2); then **once** with `--execute` under a fresh run id |
| 09:40 | emit P_MIX (paid) and P_CTRL (fallback) upload files from the published books (`--source published`); slice per the Step-4 layout |
| 10:15 | optional re-run if a late designation changes the frame (new run id); otherwise skip |
| by 11:15 | upload in the DK UI; keep the P_CTRL files as the fallback |
| 12:00 | lock |

Fallback ladder if a step fails: corrected P_MIX → corrected P_CTRL
(`emit … --source run-dir`) → tonight's placeholder already on DK →
production app export (`nfl-dfs-app`, greedy-tail-coverage 40/160).

Monday/Tuesday: `capture-dk-standings` for all four contests (validation-only,
then `--confirm-settled --confirm-full-field --apply`); settle every frozen run
dir (`settle_live.py`), then the tail-ledger row
(`scripts/run_week_tail_ledger_v1.py`).

---

## 3. What to fix in the lab live path after Week 1 (not tonight)

1. Make production centering the default for live builds (it is the panel's
   law), or retrain the lab component models with salary/depth/draft context
   so a null-usage row does not collapse.
2. `nfl2/live.py:139` — stop overwriting the warehouse `is_cold_start` flag.
3. Props-derived QB means (`market_means`) are ~35% below production's; check
   the market-mean construction for QB rushing/TD components. Add a README
   deficiency-log row.
4. Add a level-sanity gate to `live_week.py`'s receipt: refuse (or warn loudly)
   if the naive top-lineup projection is < 135 or the covered model/market
   ratio leaves [0.8, 1.25] — this defect would have been caught by either.
5. DST: replace the salary-linear prior with production's DST projection.

---

## 4. Tonight's artifacts and results ledger

| artifact | location | status |
|---|---|---|
| official D800 / D400 (lab level) | `nfl2-week1-a5-sidecars-current-20260910/results/live/2026-w01/20260912T132523949270Z-fa5d035`, `…133100344084Z-fa5d035` | built 13:25Z/13:31Z, preflight passed (dry-run report) |
| corrected D800 / D400 (dirty tree, receipts only) | `<scratch>/nfl2-coldstart-probe/results/live/2026-w01/20260912T162232432384Z-fa5d035`, `…162741499500Z-3df1b0c` | built 16:22Z/16:27Z; not adapter-admissible (`dirty: true`) |
| corrected D800 / D400 (clean commit `3df1b0c`, `dirty: false`) | `/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/results/live/2026-w01/20260912T163007999462Z-3df1b0c` (D800, sidecars) and `…/20260912T163513970937Z-3df1b0c` (D400) | **built** 16:30Z/16:35Z; receipts identical to the 16:22Z pair (same salary pull 16:01:57Z, same seeds): book E[max] 177.7 / P(≥194) .190 / P(≥220) .018 under the incumbent bank |
| publisher preflight on the clean pair (no `--execute`) | `/home/erich/week1-preflight-20260912t1637z-3df1b0c.json` (+ `.err`) | **exit 0**: four distinct book hashes (P_MIX `338798c1…`, P_CTRL `0bcec8ee…`, D400_DEMAX `be0a74cd…`, D800_WEMAX `a02c0e74…`), `pmix_turnover_per_side 5`, `designation_count 11`, `history_rows 1460`, `execute false`, nothing published |
| placeholder upload CSVs (corrected P_CTRL-equivalent, draftable ids) | `/home/erich/week1-upload-CORRECTED-20260912T1630Z-3df1b0c-milly-193028206-ranks-1-57.csv` (57 rows, sha256 `1fd349d5…`), `…-playaction-193028208-ranks-1-20.csv`, `…-ffwc-q6-194478066-ranks-1-3.csv`, `…-ffwc-q5-194478065-ranks-1-10.csv`, `…-all-80-ranks-1-80.csv` (80 rows, sha256 `463d9151…`) | **emitted**; not uploaded — the DK UI upload is the operator's step (§1 Step 3) |
| K90 unique-layout build (corrected centering, clean) | `…/live-center-production-20260912/results/live/2026-w01/20260912T163843301844Z-3df1b0c` | **built**: 90 unique rosters; ranks 1–80 identical to the K80 corrected book (nested prefix verified) — so the 90-unique layout is the same paid book plus ten more lineups |
| D1600 dose arm (corrected centering, clean; lev 320 / boom 1280) | `…/live-center-production-20260912/results/live/2026-w01/20260912T164335280473Z-3df1b0c` | **built**: vs corrected D800 under the incumbent bank — book E[max] 178.6 vs 177.7, P(≥210) .060 vs .050, P(≥220) .021 vs .018, pool P(≥220) .068 vs .041 (supply +66%); under corrected-hsim 199.0 vs 198.4, P(≥220) .141 vs .133; 48/80 rosters shared. Directionally better on every receipt, as the optimizer's curse predicts; adoption for tomorrow is governed by PREREG-090's frozen consequence 1 (needs the historical PASS) |
| governed publish of tonight's corrected pair (`--execute`) | — | **not run**: the session's permission classifier refused the create-once publish twice; the preflight passed, so the only difference is durability of tonight's books. Tomorrow's publish is the runbook's operator step 4a |
| PREREG-090 historical cohort (D1600 rung × direct-tail schedule × DUAL_EMAX, 3 banks × 72 slates on the lab Cloud Run lanes) | nfl2 worktree `live-center-production-20260912`: `PREREG-090.md`, `experiments/110_dose1600_directtail.py`, `scripts/prereg090_report.py`, `scripts/queue_110.sh`, `Dockerfile.prereg090` | frozen; smoke → image → mechanics gate → banks (see PREREG-090 for the frozen consequences for tomorrow's dose) |
| comparison script | `<scratch>/compare_books.py` (reads run dirs only) | — |
| patch commit | lab branch `lab/live-center-production-20260912` @ `3df1b0c` (local, not pushed); durable detached worktree `/home/erich/projects/.nfl2-worktrees/live-center-production-20260912` | operator decides whether to push |

Note on a stderr line in the corrected builds: `nfl2/hsim/world.py:91 RuntimeWarning: divide by zero` — numpy evaluates both branches of an `np.where` whose mask already excludes `cur <= 0.3`; benign, but a real per-player zero in the lab draws is worth a look after Week 1.
