# Prospective latent-role-state shadow protocol

**Frozen before any 2026 NFL outcome. Historical fantasy-score and lineup-
score outcomes were not queried while defining this protocol.** Historical
usage and availability data may fit and calibrate the role-transition model;
they may not adjudicate the lineup treatment.

## Question and boundary

The registered `latent-role-state-generator` asks whether candidate generation
improves when it first models the job a player will occupy in Week W, samples
that unobserved role, and only then generates points conditional on that role.
This differs from the existing direct-role candidates:

- the incumbent `tail_k1_role` model conditions on one already observed set of
  prior-role features;
- the latent treatment predicts a distribution over the not-yet-observed Week
  W role, samples a coherent role state, changes the conditional role inputs,
  and then invokes the same conditional point model;
- every resulting roster is still scored and selected with the unchanged K=1
  baseline worlds and CBWU selector.

This is a separately labeled 2026 shadow. It cannot alter the money policy,
reuse the historical 2019--2025 lineup outcomes for promotion, or be bundled
with the archetype, route, SIS, projected-ownership, payout, no-floor or
recourse treatments.

## Point-in-time prerequisites

For target Week W the state model may read only:

1. usage, snap and roster observations from weeks `< W`;
2. a same-week injury/practice observation with either source modification
   time or collector `pulled_at` at/before the common Sunday-main lock;
3. salary and slate membership captured before that same lock; and
4. an explicit missingness indicator for every unavailable input.

Completed 2025 nflverse injury rows have no source modification timestamp and
remain unavailable. They must never be stamped with a later retrieval time.
The append-only active-season `nfl_raw.injury_snapshots` collector is therefore
a hard prerequisite for the 2026 availability-conditioned branch. A missing,
late or stale snapshot removes the availability covariate; it never invokes a
post-lock or final-file fallback. If the treatment cannot reproduce its source
timestamps and hashes, it produces no shadow book.

Historical depth-chart rows are not required by v1. This avoids treating an
untimestamped legacy weekly rank as a known pre-lock promotion. A later exact-
week depth input would require its own collector timestamp and protocol
revision.

## Frozen role states

V1 covers `RB`, `WR` and `TE`; `QB` and `DST` remain on the incumbent path.
For a completed player-week, define `opportunity_share` as:

- `WR`/`TE`: target share;
- `RB`: `max(target_share, carry_share)`.

The realized state is the first matching row below:

| State | Exact rule |
|---|---|
| `inactive` | no offensive snap or the player is inactive |
| `dormant` | snap share `< 0.25` and opportunity share `< 0.08` |
| `rotation` | snap share `< 0.60` or opportunity share `< 0.15` |
| `secondary` | opportunity share `< 0.25` |
| `primary` | opportunity share `>= 0.25` |

These cut points are football-semantic constants, not a sweep. They may not be
changed after a 2026 score is seen. State ordering is
`inactive < dormant < rotation < secondary < primary`.

## Transition model

One position-specific multinomial logistic model predicts the target-week
state. Its fixed inputs are:

- previous realized state, one-hot encoded;
- strictly-prior `target_share_last/l4`, `carry_share_last/l4`,
  `snap_share_last/l4` and their registered jump fields;
- `games_played_prior`;
- own pre-lock injury designation and practice level;
- pre-lock team vacated target and carry share; and
- missingness indicators for injury status, practice level, vacated target
  share and vacated carry share.

The fit uses regular seasons 2018--2025, with every target row reconstructed
from exact historical usage while every predictor is limited to information
available before that target week. Rows whose availability timestamp is not
PIT-valid keep that branch missing. The algorithm is scikit-learn multinomial
logistic regression with an intercept, L2 penalty, `C=1.0`, no class weights,
maximum 1,000 iterations and deterministic seed `6419`. No hyperparameter or
state-boundary sweep is licensed.

Before deployment, report expanding-season 2023, 2024 and 2025 role-state log
loss, multiclass Brier score, calibration by predicted-state decile, confusion
matrix and transition counts. This score-free audit may kill the mechanism if
it is nonconvergent, degenerate, worse than the empirical
`position x previous_state` transition matrix on both log loss and Brier, or
cannot emit all five state probabilities. It cannot promote the lineup arm.

For live Week W, refit once on all PIT-valid completed rows through W-1. Store
the training maximum season/week, feature contract, state law, coefficients,
class order, source hashes and code SHA. A rerun with the same inputs must be
byte-identical.

## Conditional point generation

For each position/state, compute the training-only median target, carry and
snap shares using the same expanding fit boundary. A sampled target-week state
replaces the six direct-role fields with the state median and the implied
state-versus-prior jump. It does not alter salary, matchup, market mean,
ownership, injury status, player pool, calibration scale or any unrelated
feature.

The already-isolated `tail_k1_role` conditional model produces points and
draws from that modified row. All conditional model versions and simulated
draw hashes must be recorded. The final latent roster is always cross-scored
under the unchanged incumbent K=1 draw matrix; alternate-state draws generate
candidates only.

## Joint state worlds and candidate budget

The treatment replaces exactly the incumbent's 12 direct-role candidates:

- four deterministic promotion scenarios, one each for the four highest-
  entropy eligible skill players, using that player's most likely state above
  the modal state while every other player stays modal; and
- sampled joint state worlds from seed `6419` until eight distinct optimized
  rosters have been produced.

Within each team and sampled world, reject and redraw if the state medians
imply total target share or total carry share above `1.15`. State worlds that
optimize to a duplicate treatment roster do not count. Stop after 50 total
sample/rejection/optimization attempts; failure to obtain all eight distinct
sampled rosters produces no treatment book. Players listed `Out` are fixed to
`inactive`. No state may be sampled for a player outside the exact incumbent
DK player pool.

Everything downstream remains frozen:

- 12 treatment role candidates plus the same 40 boom candidates;
- exact five R0--R4 native seed books and equal candidate allocation;
- the same 10,000-world blocks, baseline scoring matrix and CBWU law;
- exact 80 final entries; and
- identical salary floor, stacking, player-pool and exposure constraints.

The paired receipt must prove equal source-seed quotas, candidate count,
selection-world count and entry count. Candidate hashes should differ; a
byte-identical treatment is an inert failure, not a tie.

## Prospective falsifiers and score gate

Role calibration is evaluated after each completed 2026 week without fantasy
points: state log loss/Brier, primary-state reliability, team share-cap rejects
and the frequency with which a sampled promotion actually occurred. A failure
of source identity, PIT timestamps, calibration contract, budget parity,
conditional model identity or exact-80 construction invalidates that week.

No production promotion is allowed before nine valid 2026 Sunday-main slates.
At that checkpoint, promotion requires all of:

1. the role model beats the empirical previous-state transition baseline on
   both cumulative multiclass log loss and Brier score;
2. treatment has at least two distinct treatment-only `>=210` weekly maxima;
3. the lexicographic tail grid `240/230/220/210/200/194/187` favors treatment;
4. treatment loses no `>=230` week and its paired mean weekly-maximum delta is
   positive; and
5. at least three of five registered seed-pair comparisons are nonnegative at
   `>=210`.

If the checkpoint does not pass, the shadow continues unchanged through the
season unless a mechanical or PIT falsifier kills it. The full-season decision
uses the same rules; no threshold, seed, state law, candidate allocation or
fallback may be revised after observing scores. Contest ROI and duplication
remain separate projected-ownership/field-model questions.

## Implementation order

1. Complete and cloud-validate the append-only injury snapshot repair.
2. Implement an outcome-column-denying role-state fit/artifact with the
   expanding score-free audit.
3. Implement pure conditional-frame and joint-state-world functions with unit
   tests for state boundaries, PIT rejection, share caps and determinism.
4. Add a separately named paired shadow runner and create-only manifest; do not
   add it to the season-start resume list until a score-free live-slate smoke
   proves candidate/world parity.
5. Add state-calibration and final-score grading as separate post-settlement
   steps so role labels cannot leak into pre-lock generation.

This protocol is the sole v1 definition of `latent-role-state-generator`.
Changes require a new version and must be made before the first affected 2026
outcome is viewed.
