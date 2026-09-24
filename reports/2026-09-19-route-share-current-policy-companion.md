# Route Share gate: versioned current-policy companion (draft for lab review, 2026-09-19)

Prepared for O-2 under the in-season adoption track v2 §5: the frozen 2026 Route Share gate contract is **never
changed in place**; the paired weeks from Week 3 are produced under the current money-path policy, which this
document states in full so the two consumers can be told apart. Read-only inventory 2026-09-19 16:5xZ; nothing
below has been executed.

## 1. The two consumers

| setting | frozen gate contract (2026-08-11; `production_policy.py` shadow env, lines 343-349) | current money path (`ClassicProductionPolicy`, `policy_id = classic-k1-role12-lev40-boom160-poscal-cbwu-v5`) |
|---|---|---|
| `N_LEV` | 160 (`incumbent_n_leverage`) | **40** (`n_leverage`) |
| `N_BOOM` | 28 | **160** (`n_boom`) |
| `N_CE` | 12 | **0** (`n_ce`) |
| `N_GUMBEL` | 0 | 0 |
| role solves | 12 (`n_role`) | 12 (`n_role`) |
| `ROLE_BELIEF_FEATURES` | "" (off) | "" on the money path; role model `tail_k1_role` with `role_features` for the role solves |
| `N_QB_VARIANTS` | 4 | 4 |
| selector | `greedy-tail-coverage` | `greedy-tail-coverage` |
| book size K | exact 80 (`default_entries`) | 80 default; the entered Week-2 book is the lab K97 at dose 2560/10240 |
| tail line | 194 | 194 |
| model ensemble / blend | 1 / 0.45 | 1 / 0.45 |
| served position scales | `QB:0.970,RB:1.005,TE:0.940,WR:1.070` | same |
| min lineup salary / candidate multiple | 49,000 / 2 | same |

Live job env today (`gcloud run jobs describe`, both `shadow-k1-roleunion` and `shadow-k1-route-roleunion`):
`N_CE=12, N_GUMBEL=0, N_BOOM=28`, no `N_LEV` (the job image default applies — confirm the default before Monday).
Schedulers `s-shadow-k1-roleunion-{early,late}`, `s-shadow-k1-route-roleunion-{early,late}`: PAUSED, cron
`20 10 * * 7` and `10 11 * * 7`.

## 2. What the companion pair is

The same two jobs, run under the current money-path environment (`N_BOOM=160`, `N_LEV=40`, `N_CE=0`, role 12,
selector `greedy-tail-coverage`, K 80), on the same schedulers, producing the paired control/treatment books the gate
document specifies, from Week 3. It is **companion v1** to the frozen contract: its rows are recorded under a
distinct registry key (`fp-route-share-2026-companion-v1`) in `scripts/check_prospective_gates.py`, with
`require_env = {N_BOOM: 160, N_LEV: 40, N_CE: 0}`, the gate document cited as the design, this file cited as the
policy, `adjudicates` = "final scientific read after Week 18 per the gate document; weekly in-season decision record
per Amendment 1 v2", `in_season_value = True`. The original key keeps its original contract and verdict text.

Open question for the reviewer: whether the gate's exact-80 consumer transfers to the lab K97 / dose used for the
entered book, or whether the companion's paired books are evidence about the production K80 policy only. The gate's
own guards decide the scientific read; the weekly decision record must state which consumer it describes.

## 3. Monday 2026-09-21 sequence (for approval; the operator or the laptop executes — production job mutations are
   classifier-denied for the workstation agent)

1. Record the before-env of both jobs (`gcloud run jobs describe … --format=yaml` to `reports/reviews/evidence/`).
2. `gcloud run jobs update shadow-k1-roleunion --project nfl-predictions-503414 --region us-central1 --update-env-vars N_BOOM=160,N_LEV=40,N_CE=0`
   and the same for `shadow-k1-route-roleunion` (update, never create — the project is at the job quota).
3. Record the after-env; one outcome-blind dry execution per job with `--wait`; verify the receipt's env.
4. `gcloud scheduler jobs resume <each of the four>`; confirm `state: ENABLED`.
5. `python scripts/check_prospective_gates.py --week 3` must pass with the companion key registered (O-13 test).
6. Confirm the role budget and selector defaults actually in the image (`nfl-dfs` CLI `--help` / the job's
   `production_policy` manifest) match §1 before the first graded Sunday.
