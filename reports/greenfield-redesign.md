# If we started over: the greenfield design (2026-08-05)

Written at the close of the pre-season program, with 65 addenda of
evidence behind it. The question: knowing everything we now know, what
would the optimal build look like? Not a plan to rebuild — the current
system embodies most of this — but the honest reordering, for whoever
builds the next one (or the next sport).

## The single biggest inversion: build the yardstick first

We built model → sim → optimizer → backtest, in that order, and
retrofitted the evaluation machinery (six-season panels, co-run
controls, determinism, diagnostics) as incidents taught us. Every
major loss of time traced to evaluation, not modeling: the ±5
order-luck band consumed weeks of verdict ambiguity; a mid-panel
rebuild poisoned a day of arms; single-model verdicts inverted under
the ensemble; the selection ordering shipped unvalidated for weeks.

**Greenfield rule: the harness precedes the system.** Day one is the
replay panel (six seasons, parallel cloud jobs, co-run control, LOSO,
vacuity checks, the diagnostic battery) plus determinism (seeded
ensembles, deterministic training params, keyed SQL, ordered reads)
plus the ledger. Nothing else gets built until a null lever run twice
produces the same number. Total cost: about three days. It arrived on
day forty instead.

## The second inversion: zero-training models are the baseline

We spent the early program on LightGBM engineering, then discovered
TabPFN beats our tuned models zero-shot, arrives calibrated where
they under-cover (proven three independent ways), and shines
brightest exactly where boosting starves (cold starts). Greenfield:
**TabPFN-class in-context models are the day-one baseline; gradient
boosting must earn its way in**, not vice versa. Combined with the two
late unlocks that should be day-one primitives — GPU-on-Cloud-Run
(~$1/run, discovered by accident to have quota) and the cache pattern
(precompute walk-forward predictions to a table; replays join, never
train) — the adopted final stack was reachable in roughly two weeks.

## The third inversion: the field is the game

Our realized edges, ranked by evidence: (1) the ensemble (+12), (2)
draw shaping/marginal calibration (+6s), (3) leverage against the
field — validated by the chalk-regime split (we clear lines in 60% of
chalk-bust weeks vs 40% of chalk-win) and the leaderboard stratum
finding (only the WINNER is contrarian and unique; the top-1% is
chalk-shaped). Meanwhile dozens of engineered features nulled; TWO
survived panels (qb_cpoe, the schedule pair). Market data (prop
ladders — free, calibrated, professionally sharpened) and field data
(ownership archives, per-entry standings — which we possessed unused
in a reference clone for weeks) carried more strategic weight than
almost all feature engineering.

**Greenfield: the field model is a first-class citizen, co-equal with
the player model.** Collect standings and ownership from day one.
Model the field's LINEUP DISTRIBUTION (duplication, stack habits,
ownership correlation), not just marginal ownership — because the
objective is not "score X"; it is "P(our max beats the field's max)",
and the right-hand side deserves as much modeling as the left. The
prop market's implied distributions are a free calibration teacher —
blend and diff against them from week one.

## The fourth inversion: populations, never individuals

Measured: the sim ranks CONFIGURATIONS over 107 weeks superbly and
cannot rank its own entries within a week at all (entry #1 = 49th
percentile realized; ordering ~coin-flip). Winners are decided by
co-boom realizations no marginal model predicts. Greenfield
architecture respects this boundary everywhere:

- **Scenario-first construction**: sample correlated worlds
  (mechanistic correlation core × calibrated per-player marginals —
  both validated pieces we'd keep), then solve the ARGMAX LINEUP PER
  WORLD as the PRIMARY candidate generator — attribution showed these
  boom solves are 13% of candidates and 54% of weekly bests. The
  mean-objective diversity batch, which we started from, becomes the
  secondary generator.
- **Set selection, not entry ranking**: greedy max-coverage over
  worlds (what we have) is near-optimal for the set objective; the
  binding constraint is candidate assembly (84% of optimal players in
  pool, 1.87/8 in the best entry, BELOW the random-null 2.51).
  Greenfield selection optimizes the SET directly and never surfaces
  per-entry confidence — entries are co-equal shots by construction.
- **Uniqueness as a hard trait, not a tiebreak**: the leaderboard
  stratum showed winner lineups are 3-5x less duplicated than every
  other stratum. Dupe-risk against the modeled field is a first-class
  term in selection.

## What we would keep exactly as-is

Point-in-time discipline (never once bitten — because it was absolute
from day one; the one design choice that was greenfield-grade from the
start). Walk-forward validation. The possession-Markov correlation
core (fitted, cheap, beat its learned challenger's rollout gate). The
mandatory punt at ceiling valuation and the salary floor (both
independently confirmed by hindsight-optimal structure). The stack
mandate (loosening it cost a third of all tails — hindsight optimals
mislead here, because what won is not how to hunt). Tournament-only
focus. The experiment ledger with cause-of-death burials.

## Operating principles the program paid to learn

1. The harness precedes the system; a lever without an arm is a hope.
2. Zero-training calibrated models are the null hypothesis.
3. Market and field data outrank engineered features until proven
   otherwise; free calibrated distributions (prop ladders) are gold.
4. Averages over noise dimensions (ensembles) beat cleverness on top
   of noise — and invalidate all cleverness validated before them.
5. Trust populations, never individuals; optimize sets, not entries.
6. What won is not how to hunt: winner anatomy inspires hypotheses,
   panels decide them.
7. Diagnostics beside outcomes: an arm that moves the score without
   moving a mechanism is noise; a mechanism without score is a lead.
8. Check the gate before scheduling around it (GPU quota, prop data,
   standings archives — all were closer than assumed).
9. Fail loudly everywhere; graceful and silent is a trap.
10. External review earns its cost, but only with the ledger and the
    code in hand — and its findings get verified, never trusted.
