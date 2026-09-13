# Preregistration 096 — today's entry rule at the paid dose: does the learned pool selection beat expected-max on real 800-candidate pools? (experiment 116)

**Frozen 2026-09-13 ~14:00Z (Sunday, 09:00 CT), before the bank launches; no 2026 outcome exists.** Author: the agent
operating both lab and production since 2026-09-12 (operator instruction, autonomous). This cohort is a pre-lock
decision aid for the Week-1 entry, not a Week-2 adoption test: one bank, read once, consequence limited to today.

## Why now

The operator adopted (13:10Z) a learned pool selection for today's 30 entries: every candidate of the live pool receives a
ridge score fitted on realized lineup scores (216 opened D800 books, PREREG-094 banks 940–942, 2021–2024; features are
within-pool-standardised sums/min/max of projection, p10/p90/std, market points, usage, game total, spread, implied total,
depth, cold start, salary, plus stack structure), and the book is built greedily by that score with pairwise overlap ≤ 5
and single-player exposure ≤ 40%. Its evidence so far is out of season but on the Neo4j PREREG-083 corpus only:
200-candidate pools (40 lev / 160 boom), two seasons (2023–2024), 72 slate-arms — K30 +6.07 / K80 +3.17 vs the
expected-max book. The live pool is 800 (paid P_MIX) or 3200 (K90) candidates with the same 20% lev share. The operator
asked whether the current algorithm can be run through a historic test before kickoff; this is the version that fits.

## Construction (frozen)

Per slate (72 development slates 2021–2024): one D800 pool (`generate_candidates(n_lev=160, n_boom=640)`, generation bank
`slate_seed(960, s, w)`), scored once on the dual decision matrix (incumbent selection bank ⊕ corrected-hsim selection
bank, `slate_seed(1010, s, w)`, float32), `NFL2_ENSEMBLE=1`, `NFL2_CENTER=mean` — PREREG-047/090/093/094/095's cell.
The learned score uses the coefficient set fitted **without the slate's season** (LOSO; four sets frozen in
`results/prereg096_learned_loso_v1.json`, sha256 in every shard). The rule choice (overlap 5, exposure 40%) was made after
seeing 2023–2024 outcomes on the 200-pool corpus; **2021–2022 are therefore the seasons untouched by rule selection** and
are reported separately.

## Arms (bank 960, one bank)

| arm | construction | role |
|---|---|---|
| `DEMAX_K80` | `select_expected_max(M, 80)`; its first 30 in greedy order are the K30 control | **control** (the adopted policy) |
| `LEARNED_DIV5_EXP40_K30` | greedy by learned score, overlap ≤ 5, exposure ≤ 40% (12 of 30) | **treatment (today's rule)** |
| `LEARNED_DIV5_EXP40_K80` | the same rule at K80 | secondary |
| `LEARNED_POOL_K30` | top-30 by learned score, no caps | reference |

The full per-candidate table (players, tag, learned score, simulated q99 under both laws, P≥200, realized score, DEMAX
rank) is written into every shard so the reader can evaluate other rules descriptively without re-solving.

## Primary endpoint and decision rule (frozen)

Primary: paired weekly **raw K30 realized maximum**, `LEARNED_DIV5_EXP40_K30 − DEMAX_K80[:30]`, over the slates whose
shard is complete at read time (target 72; the read is time-boxed to 16:15Z at the latest and states its completeness).
Secondary: the same at K80; the 2021–2022 subset; season-clustered bootstrap 90% interval (20,000 draws, seed 47);
wins/losses; threshold events 194/200/220 per arm; pool oracle and supply; concentration receipts.

**Consequence for today (the only consequence):** the learned today-30 stays the entered book **iff** the primary mean
delta is > 0 **and** at least three of the four season means are ≥ 0. Otherwise the entry reverts to the vetted paid
top-30 (`TODAY-30-LATEST.md` is rewritten to point at the vetted paid book). Nothing here adopts anything for Week 2:
that requires the standard three-bank cohort with the frozen GLOBAL_WEMAX_PROXY reader after the coefficients are
re-fitted outside the test panel.

## Mechanics

A local `--smoke --mechanics-only` (0.1 scale, 2023 W1) and a local full-path `--smoke` preceded the launch. No cloud
mechanics gate: the single bank is itself the read, and it is not an adoption test. The bank runs on a dedicated job
(`lab-run-fast`, image `Dockerfile.prereg09v`, 72 tasks, parallelism 36, `maxRetries 3`, task timeout 3600 s) so the
running PREREG-093/095 lanes are untouched.

## Identity

Runner `experiments/116_learned_pool.py`, coefficients `results/prereg096_learned_loso_v1.json`, reader
`scripts/prereg096_report.py`, image `Dockerfile.prereg09v` / `cloudbuild.prereg09v.yaml`, branch
`lab/prereg096-learned-pool-20260913` off 3c7e714c (the PREREG-095 commit).
