# Frozen historical scorer: coherent model/market-state construction

Date: 2026-08-17
Version: `coherent-market-state-historical-score-v1`

This protocol is frozen before the coherent-state score-free build has
completed, before any coherent-state job or treatment object exists, and
before any coherent-state treatment coverage or realized score has been read.
It resolves the historical-book ambiguity prospectively and prevents choosing
the most favorable of the five cross-validation books after results exist.

## Purpose and license

The score-free protocol already requires this diagnostic after every
mechanically valid complete 54-slate harvest, regardless of whether its
score-free gate passes. This prevents effect-selected outcome disclosure. A
score-free failure still closes the exact construction family; a favorable
historical diagnostic cannot rescue it. A score-free pass plus a favorable
historical diagnostic can support only the already-declared, distinctly
labeled 2026 pre-lock shadow. Neither result changes production or the UI.

## Bound upstream population

- Upstream run:
  `20260816-coherent-market-state-scorefree-v1`
- Upstream prefix:
  `gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/20260816-coherent-market-state-scorefree-v1`
- Exactly 54 accepted terminal-successful shards: 2023--2025, Weeks 1--18
- Exactly 270 mechanically valid folds and the strict aggregate report
- Exact upstream manifest, accepted/primary/replacement ledgers, attempt
  resolution, completion, execution/object/shard hash ledgers, aggregate
  report and report-upload receipt

The launcher must create and upload a create-only upstream receipt that binds
all of those local strict-harvest files and every source object's URI,
generation, byte count and SHA-256. The scorer must independently download and
revalidate all 54 shards, reproduce the upstream aggregate byte-for-byte in
meaning, and prove the accepted execution population before querying an
outcome. A partial, failed, terminal-invalid or merely score-free-passing run
does not license this scorer.

## One canonical historical book per slate

Each score-free slate contains five train-four/test-one books. Historical
scoring uses **only the canonical `heldout_block=R0` fold**, the first block in
the already-frozen `R0`--`R4` order. That fold's construction and selection
were trained on `R1`--`R4` and expose exactly one control and one treatment
candidate book plus one exact-80 control and one exact-80 treatment book.

This rule is fixed before any treatment result. The scorer may not choose a
fold from its score-free effect, realized score, season, slate or lineup. It
may not take the maximum or union across five folds, because that would score
up to five opportunities while representing them as one exact-80 entry set.
It may not construct a new consensus or all-five-block book, because neither
was part of the score-free treatment. Canonical R0 therefore yields exactly 54
paired, causal, exact-80 weekly comparisons.

## Point-in-time and outcome source

Construction remains exactly as recorded upstream; no player feature, market
field, projection, candidate, selector or simulation value is recomputed.
Realized DraftKings points come only from
`nfl-predictions-503414.nfl_predictions.slate_player_features` for the exact
R0 source panel, joined by `(season, week, player_id)` after every roster is
frozen. Before scoring either book, reconstruct every registered native
candidate's `actual_score` from its nine player outcomes across the exact five
source panels plus the frozen R3/2025 Week 1 repair. Require:

- 68,199 registered candidate rows;
- exactly nine unique player IDs per roster;
- zero missing or duplicate player outcomes;
- all 54 slate keys present; and
- maximum absolute reconstructed-versus-registered error at most `1e-9`
  with zero relative tolerance.

Any parity failure invalidates the entire diagnostic. No ownership, rank,
payout, contest result or winner identity is queried.

## Per-slate scoring

For the canonical R0 fold, independently validate that control and treatment
candidate counts equal the recorded fixed budget, all rosters contain nine
unique in-slate players, and both selected books contain exactly 80 unique
rosters that are members of their respective candidate books. Score a roster
as the sum of its nine realized player points. Record, for candidate and
selected scopes and control/treatment books:

- weekly maximum and its canonical roster identity;
- counts of rosters at or above 187/194/200/210/220/230/240;
- mean and median roster score; and
- paired treatment-minus-control maximum.

Record whether each of the 12 coherent additions entered the selected book
and the realized score of every added and removed roster. These are diagnostic
attribution fields only and cannot alter the fixed gate.

## Complete aggregate and fixed signal

Aggregate once over all 54 slates and report threshold counts of **weekly
maxima**, overall and by season, at 187/194/200/210/220/230/240. Also report
mean/median weekly maxima, paired win/tie/loss counts, the complete ordered
slate table and leave-one-slate-out influence on the six gate quantities.

The previously frozen historical tail signal is positive only if all of these
hold:

1. treatment selected weekly maxima at or above 200 exceed control by at
   least two slates;
2. treatment selected weekly maxima at or above 210 do not decline;
3. treatment selected weekly maxima at or above 220 do not decline;
4. treatment selected weekly maxima at or above 230 do not decline;
5. treatment selected weekly maxima at or above 240 do not decline; and
6. treatment candidate-pool weekly maxima at or above 200 do not decline.

All other thresholds, means, seasons, addition/removal scores and influence
values are context only. No condition may be weakened and no alternative fold,
scope, threshold or season may replace this gate after any outcome is visible.

## Cloud and disclosure boundary

Use one immutable image digest and exact 40-character scorer commit, one Cloud
Run job/task, 4 CPU, 16 GiB, a two-hour timeout and task `maxRetries=0`.
Inputs and outputs are create-only. Monitoring may inspect status and object
metadata only. The strict finisher downloads and discloses the result only
after terminal success, exact execution-contract validation and positive
object metadata. The report must state `uses_realized_outcomes=true` and
`production_change_licensed=false`.
