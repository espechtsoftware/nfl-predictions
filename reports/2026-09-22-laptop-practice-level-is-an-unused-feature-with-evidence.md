# Practice participation is sitting unused in the training table, with evidence it matters

Following production's `efcfa371` (2025 `injury_status` missing from the training panel; "the
model's featureset carries no injury or practice feature at all").

## Verified, with one refinement

`src/nfl_dfs/models/featureset.py`: `NUMERIC_FEATURES` has **35** features. Two concern
injuries — **`team_vacated_target_share`, `team_vacated_carry_share`** — and both describe
**teammates'** absences (the injury cascade). **Nothing describes the player's own
designation or practice.** `EXTRA_FEATURES` is not set in the adopted policy, and the opt-in
`CANDIDATE_FEATURES` contain only `vacated_capture_*`.

So the precise statement: **the model knows when a teammate is out; it does not know when the
player himself is limited.**

## The unused columns already exist in `player_week_training`

`injury_status`, `practice_level`, `practice_participation_trend`. Coverage on active rows:

| seasons | `practice_level` | `practice_participation_trend` | `injury_status` |
|---|---:|---:|---:|
| 2014–2015 | 15–16% | 11–12% | 15–16% |
| 2016–2024 | **15–18%, steady** | 11–14% | 4–5% |
| **2025** | **0.0%** | **0.0%** | **0.0%** |
| 2026 (live) | 9.1% | 1.9% | 1.1% |

The 15–18% is not a quality problem: only players on the injury report carry a practice level,
so a null reliably means *not listed*, i.e. healthy, and can be encoded as such. **`practice_level`
is the usable one**: steady across a decade, unlike `injury_status`, which collapses after 2015.

## Evidence it would add signal

PREREG-100 (lab ledger, 2026-09-16) measured served-projection residuals by status and practice:
**Q_dnp −5.9 and Q_limited −2.9 points**, zero rates 47% and 25%, while none_limited / none_dnp
delivered their projection. A residual against the *served* projection is by definition signal
the model does not have. That is exactly what an own-practice feature would supply.

This is a different axis from today's availability work. The Doubtful denylist and the backup-QB
gate handle **will he play**; practice level would handle **how well, given that he plays** —
the Q_limited case, where the player dresses and under-delivers.

## Proposed experiment, and its prerequisite

1. **Prerequisite — re-run the injuries ingest for 2025** (production's open log row). Without it
   the most recent full season has no practice data, and the six-season walk-forward law would be
   evaluated on panels ending in 2024. This is the only blocker.
2. Register `practice_level` (null → "not listed") and `practice_participation_trend` as
   `CANDIDATE_FEATURES`, so they are inert until named in `EXTRA_FEATURES` — the existing
   adoption path.
3. Walk-forward by season, co-run control on the same image, with at most one negative
   leave-one-season-out, per the standing validation law. Primary endpoint: projection error on
   **listed** players (the rows the feature can change); secondary: whole-slate error, so a gain
   on 15% of rows is not diluted to invisibility or claimed as a slate-wide improvement.

I have not run it: it is a model-training change on production's adoption path, and the 2025 gap
should close first.
