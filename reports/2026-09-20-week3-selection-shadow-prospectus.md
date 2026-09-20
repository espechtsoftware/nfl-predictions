# Week-3 selection-only shadow: prospectus and freeze contract (production-owned)

Assignment: lab handoff `2026-09-20-laptop-week3-wiring-and-parallel-assignment.md` (operator direction 2026-09-20).
Code: `scripts/week3_shadow_runner.py`, `scripts/week3_shadow_reader.py`, tests `tests/test_week3_shadow_runner.py`,
branch `production/week3-shadow-runner-20260920`. Nothing here adopts a rule; the in-season v2 candidate-specific trial
route is preserved (one read per arm when outcomes are released; no mandatory multiweek wait).

## Inputs (one immutable set, frozen before lock)

The approved fresh Week-3 build's run directory: `frame.parquet`, `candidates.parquet`, `receipt.json`, `book.json`,
`incumbent_player_scores.npy`, `corrected_hsim_player_scores.npy`; the week's `contests.json`. The runner hashes all of
them into `manifest.json`, reads K = sum of contest entries and asserts it equals the receipt's `operational_k`, and
rebuilds the delivered selector input exactly: per bank, float32 sequential sums of bank rows in ascending frame-row
order; equal-mass concatenation [incumbent | corrected-hsim]. Control parity (membership, order, book.json names) must
pass before any treatment is reported; on failure the runner writes PARITY-FAILED and exits 3.

## Arms (each intervention separate; same pool; same K; ordered books; infeasible arms recorded, never relaxed)

| arm | definition |
|---|---|
| control | delivered `nfl2.selectors.select_expected_max` (dual_emax) from the pinned lab release |
| ladder016 | PREREG-016 `cap_prefix_then_fill`: inclusive rungs 194/200/210/220 on pooled worlds, weights 1/2/6/12, gamma 4, pooled-mean tie-break; prefix count recorded |
| floor8 | row filter: lowest served non-DST projection >= 8, then the control selector |
| nodepth4 | row filter: at most 3 same-team WR/TE with the QB, then the control selector |

The 220/230/240 ladder is a separately named variant and is NOT in this runner until its weights and cap are frozen
by name. Floor 10 / floor 12 and depth-2 are falsifier diagnostics available by constant change, not registered arms.

## Estimands (reader; outcomes read only after release)

Primary: each arm's realized max-of-K and the count of rows clearing 200/210/220/230/240 (194 secondary), paired
against control on the same slate. Secondary: the global winner-score proxy of the realized max (`winner_utility`, the
smoothed CDF of 2023-2025 Millionaire winning scores), contest-prefix blocks (max per contests.json block), pool
oracle (best realized candidate in the run pool) and regret. Simulated diagnostics (pooled and per-bank max
distribution, overlap with control) are recorded at freeze time and reported beside the realized read, together with
the simulated-to-realized 220 ratio. One slate cannot decide; each week's read is appended to the evidence record.

## Freeze and blindness contract

1. Runner outputs (`manifest.json`, `books.json`, `diagnostics.json`) are produced from the prelock run directory and
   committed with their hashes before the first kickoff; the label is `live` only when produced from the Week-3
   delivered run; every archived-run execution is labelled `rehearsal` and writes a REHEARSAL marker.
2. The reader takes an outcomes CSV (`id`, `actual_points`) built from `nfl_features.player_week_actuals` after the
   operator's settlement step; until then no reader run touches a score table (`--synthetic-world` draws from the
   incumbent bank and is labelled REHEARSAL).
3. Any roster id missing from the outcomes file fails the read (READER-FAILED, exit 3); nothing is imputed.

## Rehearsal on the archived D12800 run (2026-09-20, outcome-blind)

Control reproduced the delivered K97 book exactly (membership, order, names). Simulated diagnostics (pooled 20,000
worlds): control max-mean 203.451, P220 22.255%, P230 12.125%, P240 6.280%; ladder016 202.559 / 21.675% / 11.215% /
5.500% (prefix 97, overlap 48/97), which reproduces the lab's independent archived screen (research `43b04c72`) to the
digit; floor8 (pool 3,201 of 12,555) 202.233 / 20.585% / 10.865% / 5.475%, overlap 49/97; nodepth4 (pool 12,551)
203.387 / 22.160% / 11.990% / 6.215%, overlap 88/97. Runtime 565 s on the workstation. The reader rehearsal used
incumbent-bank world 2026 as a synthetic outcome (`reports/week3-shadow-rehearsal-20260920/`).

## Source eligibility for the paid-source shadow (for the lab's item 3; not run by this runner)

* Fantasy Points Route Share: 2022-25 hash-locked history plus a 2026 weekly append the operator lands on Wednesday
  (`nfl-weekly-data`); the feature table rebuilds on `s-features-route` Thursday 06:30. Eligibility week = the first
  Week-3 build after that Wednesday landing, provided the Week-3 rows are point-in-time bound (pulled before lock).
* Fantasy Points alignment weekly: same Wednesday run, separate append; no production consumer; research input only.
* Fantasy Points live matchup tools: GCS archive only (2026 contract forbids consumption); ineligible.
* SIS pass-tail (team pass defense / pass rush / blocking): operator Wednesday acquisition + warehouse append
  (`sis_pass_tail_weekly`); the isolated TabPFN caches (`tabpfn_sis_pass_tail_live_control_v1` / `_treatment_v1`) are
  built by the paused `shadow-sis-pass-tail-paired` job; eligibility requires that job to run for Week 3.
* SIS run context, receiver copula: closed; ineligible.
* Odds API props/game odds: scheduled (`s-props` Thu 11:00, `s-odds` Wed-Sun); eligible every week; the shadow markets
  table is collection-only.
* ETR: no file has ever been landed (`nfl_features.external_projections` does not exist); ineligible until captured.
* Correction to inherited repo text: `nfl_raw.contest_entries` holds 994,328 Week-1 rows (landed 2026-09-13); the
  ownership booster and field calibration have not yet been rerun on it.

## Not yet done (before Week-3 Saturday)

Lab review of runner, reader, tests and the rehearsal artifacts; the Week-3 K and contests.json; the outcomes-CSV
builder (`player_week_actuals` join to frame ids including DST ids) as a tracked script; wiring the runner into the
Saturday flow after the approved build (laptop-owned entrypoints), so its outputs are committed before lock.
