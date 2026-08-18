# DST Phase D0 rebuild, support census and gate-3 blocker

Date: 2026-08-18. **No lineup, candidate or realized DFS score was opened. No
production change is licensed.**

Run ID: `20260818-dst-d0-rebuild-v1`
Receipts: `reports/dst-d0-runs/20260818-dst-d0-rebuild-v1/`

## Why this ran now

`reports/2026-08-17-dst-d0-event-frame-implementation.md` deliberately deferred
warehouse population "while ATLAS owns the historical outcome/heavy chain."
ATLAS repair6 closed `repair6-closed-no-scoreable-population` at
2026-08-18T07:20:19Z and its terminal receipt was harvested, so the D0 gates
were released.

The motivation is structural, not incremental: DST is currently **constant
across all 30,000 simulated worlds** (`live_lineups.py:334` sets
`draw_idx = -1`, production ships `DST_CORR_DRAWS=""`, and `engine.py:636`
confirms those rows "get their static projection in every sim"). One of nine
roster slots contributes **zero variance** to every lineup's tail. D0 is the
prerequisite for fixing that.

## Gate results

| gate | status |
|---|---|
| 1. rebuild from exact committed SQL + record job/generation/schema receipt | **PASS** |
| 2. strict physical support census across configured seasons | **PASS** |
| 3. explain or repair every authoritative/reconstruction mismatch | **BLOCKED** |
| 4. record exact per-season source coverage and support | **PASS** |
| 5. common-lock odds/weather selectors (D1/D2 prerequisite) | not attempted |

### Gates 1, 2, 4 — passed

Rebuilt from clean `sql/features/024_team_defense_week.sql` at code
`ef36db5ed9303c9c3a287ee6a60f56104e8bd754`, SQL SHA-256
`2f197df10cb9805f6a76309fe8ba751316cea9e3dde848ae5f41570eb4a411ad`.

- Query job `9556eae9-12af-4611-aa17-ffd122c4142f` (US), 66,630,074 bytes.
- Table went **13 -> 55 columns**; 6,302 rows across 3,151 games, 2014-2025.
- Schema SHA-256 `d31f67c1b23d86b2a4d0aff718d1f4f4bb390e8b72b4155b53c7bdf947534be0`.
- `census_dst_event_support` passed with `prior_windows_validated: true`,
  `authoritative_source_failures: 0`, scoring law
  `draftkings-nfl-classic-dst-2026-08-17-v1`. Census SHA-256
  `3e63ca8fa06b162c7b98fed210444deb8fc20af81c43bb930e5ed101d278193e`.

### Gate 3 — blocked, two distinct problems

**(a) Three of six panel seasons have no authoritative coverage at all.**

| season | authoritative rows | mismatches | rate |
|---:|---:|---:|---:|
| 2019 | 512 | 11 | 2.15% |
| 2021 | 544 | 12 | 2.21% |
| **2022** | **0** | — | — |
| **2023** | **0** | — | — |
| **2024** | **0** | — | — |
| 2025 | 528 | 14 | 2.65% |

2022-2024 contribute 1,630 team-game rows with **zero** authoritative scores.
The reconstruction is unverifiable there, and no amount of mismatch explanation
changes that.

**(b) The residual disagreement has no identified single cause.**

162 mismatches / 4,656 authoritative rows overall (3.5%); **37 / 1,584 =
2.3% in panel seasons**. The rate is remarkably stable — 2.15% to 2.65% in
every season except 2014, which is an outlier at 11.72%.

Two candidate explanations were tested and both fail:

| hypothesis | test | verdict |
|---|---|---|
| points-allowed tier boundaries | mean distance to a DK tier edge: **1.62** mismatched vs **1.66** matched; within-1-of-edge 53.1% vs 50.5% | **refuted** — no separation |
| excluded non-DST points (offensive pick-six / fumble-six / safety) | 2x enriched in mismatches (25.3% vs 13.0%), but `abs(delta)` equals the excluded value on only **3 of 41** such rows | **correlated, not explanatory** |

Delta distribution is 97% small integers: `+1` (53), `+2` (39), `-1` (24),
`-2` (21), `+3` (20); only five rows exceed `abs(4)` across twelve seasons.

## What gate 3 actually needs

It is written as "explain or repair **every**" mismatch. That standard cannot be
met by analysis alone here, and the correct response is a protocol decision
rather than more diagnosis. Two coherent options:

1. **Accept a bounded mismatch rate with a named canonical source.** Declare the
   authoritative source canonical where present, the reconstruction canonical
   where absent, freeze a maximum tolerated disagreement (the observed panel
   rate is 2.3%, max `abs` delta 8), and require the D1/D2 event model to be fit
   on components rather than on the reconstructed total. This is defensible
   because the event *components* — sacks, interceptions, fumbles, return TDs —
   are what the world model needs, and they are not implicated in the delta.
2. **Per-row play-by-play forensics** on 162 rows. Expensive, and it cannot fix
   2022-2024, which have nothing to compare against.

**Recommendation: option 1.** The blocker for the actual objective is not score
reconciliation — it is that DST has no world distribution at all. A 2.3%
disagreement on the reconstructed *total* does not impair a component-level
event model, and holding D0 hostage to a standard that three panel seasons make
unreachable would stall the one verified structural omission in the system.

That decision belongs to the operator and is recorded here rather than taken.

## Recorded elsewhere

A row was appended to the Data deficiency log in `README.md` per the standing
rule in `CLAUDE.md`.
