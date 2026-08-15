# Historical realistic-recourse sizing protocol

Date frozen: 2026-08-15 07:04 CDT  
Protocol: `20260815-historical-realistic-recourse-sizing-v1`  
Scope: immutable repair4 `phase-s-cbwu-54` corpus  
Status: descriptive/prospective sizing only; not a historical adoption arm

## Question

How much of the corrected perfect-information late-swap ceiling is recovered
by the already frozen `prospective-recourse-policy-v1` when it sees only points
and game status actually knowable before the late-afternoon games, plus the
retained pre-lock simulation worlds?

This is one outcome-viewed policy-sizing analysis. It cannot promote a money
policy on 2023--2025 results. Its role is to decide whether late-swap
engineering is large enough to prioritize and to identify its operational
shape before outcome-unseen 2026 shadow evaluation.

## Frozen population and identities

- Seasons/weeks: all 54 Sunday-main slates in 2023--2025 from forensic scope
  `phase-s-cbwu-54`.
- Source candidate panels:
  `20260813-sis-asoe-treatment-r0-v1` through
  `20260813-sis-asoe-treatment-r4-v1` in
  `nfl_predictions.replay_candidates_staging`.
- Each seed/slate must have exact-80 native membership, 10,000 worlds, one
  immutable score artifact and a `player_ids`/`player_draws` payload.
- The five source artifacts must reproduce their native candidates and
  selectors, share the same player universe and reconstruct the frozen CBWU
  candidate budget, 50,000-world transport and exact-80 selected book.
- Reconstructed CBWU candidate and selected roster identities must exactly
  match the retained repair4 forensic candidate/selection corpus before a
  proposal is evaluated.
- Production legality is $50,000 maximum salary, classic positions, QB+2
  WR/TE, at least one opposing RB/WR/TE bring-back, no same-team two-RB pairing,
  no RB against its DST, and at least two games. The source generator already
  enforces the $49,000 floor; recourse does not introduce new rosters.

All artifact URIs, SHA-256 values, source code identities and reconstruction
receipts are recorded. A mismatch aborts the complete run.

## Frozen decision instant

For every retained Sunday slate, the only decision instant is **3:55 PM
America/New_York on that slate's game date**. Every retained late game starts
at either 4:05 or 4:25 PM Eastern, so the law leaves at least ten minutes for
an automated proposal, validation, human review and DraftKings upload. It is
not selected separately by week and may not move after results are seen.

Player kickoff timestamps are rebuilt from the nflverse schedule's game date,
home/away teams and kickoff clock, then cross-checked against the forensic
slate's team-pair and kickoff fields. A player is locked when kickoff is no
later than the decision instant.

## Independently derived game status

Game status is reconstructed from timestamped nflverse play-by-play, not from
the final box score or schedule result:

1. kickoff after the decision instant: `not_started`;
2. kickoff at/before the instant with no terminal PBP signal by the instant:
   `in_progress`; or
3. kickoff at/before the instant whose latest observable PBP row is terminal:
   `final`.

A terminal row must itself be timestamped no later than the decision and must
either explicitly identify end of game, or show zero game seconds in Q4 with a
non-tied score, or zero game seconds in overtime. The final-game set is frozen
from this rule before authoritative labels are supplied. Unknown timestamps,
ambiguous team/game mapping, impossible status, or a final game without an
authoritative player and DST label aborts the run.

## Points and remaining worlds

`points_information_as_of` is the only scoring adapter:

- `not_started`: zero observed points; retain initial full-game draws;
- `in_progress`: score only PBP events timestamped at/before 3:55 PM Eastern,
  then use `points_to_date + max(initial_draw - points_to_date, 0)`; and
- `final`: use the authoritative full-game player/DST label and zero remaining
  draw, but only for the independently frozen final-game set.

The 12 known nflverse multi-lateral reconciliation residuals must be checked
before execution. If a residual play is included before the decision in an
in-progress game and its player appears in the retained candidate universe,
the run aborts as non-identifiable. Completed games are safe because they use
authoritative labels; post-decision plays are excluded.

### Pre-execution data-identifiability amendment (2026-08-15 07:26 CDT)

The required residual audit was performed before any recourse proposal or
outcome query. It found two timestamped multi-lateral plays before 3:55 PM in
games that remain in progress under the frozen status law: 2024 Week 9
LAC-CLE play 2105 and 2025 Week 15 CLE-CHI play 1934. Three affected player
identities appear in retained candidates. A blind abort is unnecessary because
the contemporaneous PBP descriptions explicitly enumerate the omitted
intermediate players and their yard allocations even though the structured
lateral fields do not.

Accordingly, the abort clause is narrowed before execution: a known residual
is identifiable only when its exact game/play identity, event time,
description SHA-256 and player yard delta match the frozen eight-play/twelve-
player reconciliation table in `recourse_scoring.MULTI_LATERAL_ADJUSTMENTS`.
The scorer applies those description-derived yards only when that timestamped
play is itself at or before the decision. Any checksum drift, missing row,
additional candidate-relevant unresolved residual, or untimed scoring event
still aborts the run. The complete table is used rather than special-casing
only the three recourse-relevant identities. Its full-game output must exactly
reproduce all 54,419 authoritative 2023--2025 stat-line player-week labels,
plus all 21,293 intentionally materialized salary-zero labels, before the
historical run is launched.

This amendment repairs source-field identifiability; it does not change the
decision instant, candidate set, worlds, tail objective, policy, entries or
evaluation rule. It was frozen after inspecting timestamp/schema mechanics and
the previously documented scorer residuals, but before seeing any realistic-
recourse proposal or realized score.

The historical artifacts were computed later from strictly point-in-time
pre-lock inputs. The runner must not falsify their object creation time. It
records both the real artifact generation identity and the counterfactual
availability assumption established by the prior five-seed PIT/checksum
reconstruction. This limitation is explicit in the result.

## Frozen policy

Run `prospective-recourse-policy-v1` without changes:

- candidate alternatives are the exact fixed-budget CBWU candidate set;
- each of the 80 entries retains every kickoff-locked player;
- each entry considers at most 24 compatible alternatives, pre-ranked by its
  simulated crossings at 240/230/220/210/200/194/187, then q99, mean and
  canonical roster identity;
- entries are visited lowest-to-highest simulated 194 reach probability;
- accept only a strict lexicographic improvement in simulated book-maximum
  crossings at the same tail ladder, then q99 and mean;
- duplicate final lineups are prohibited; and
- original roster is always the fail-safe fallback.

No actual score, actual ownership, contest rank, payout, future game status or
post-decision event may enter proposal generation. Proposals and their
checksum are frozen for all 54 slates before final outcomes are joined.

### Pre-execution policy-class and overlap amendment (2026-08-15 08:21 CDT)

At amendment time the scorer reconciliation, proposal ledger and result
objects were independently verified absent. No realistic-recourse proposal or
realized result existed. External review requested three diagnostic cuts that
are decision-relevant but do not change `prospective-recourse-policy-v1`:

1. compare it with ordinary projected-points re-optimization;
2. retain the incumbent book's full point-in-time liveness profile; and
3. split residual distance from corrected exact P into already locked versus
   still-unlocked players.

The proposal ledger therefore freezes a second comparator alongside the
unchanged treatment. `naive-mean-reoptimization-v1` visits entry IDs in
canonical order, retains every kickoff-locked player, considers every
compatible retained candidate not already assigned elsewhere, and selects the
highest conditional projected mean. Ties minimize player churn and then use
canonical roster identity. It never uses reach classes, a tail ladder or a
book-level objective. Both treatment and comparator prohibit duplicate
lineups and use the same candidates, remaining worlds, observed points and
decision instant. Their complete assignments are frozen in the same
create-only ledger before the outcome query.

For each slate, the ledger also retains every entry's simulated probability
of reaching 194, its already frozen alive/marginal/effectively-dead class and
the class counts. The outcome report may describe associations between those
pre-outcome quantities and realized treatment gain or treatment-minus-naive
gain. These are descriptive associations, not a fitted first-stage policy.

The implementation review also found that the prior runner incorrectly tried
to recover exact P as the best generated candidate. That contradicts the
construction diagnosis: exact P is an oracle over generated player support,
not generally a generated roster. After and only after the proposal ledger is
created, the repaired runner reconstructs exact P from the authoritative
player corpus under the frozen $49,000 floor, $50,000 cap, QB+2 and one
bring-back rules. Its score must match the immutable exact-stack addendum to
1e-6. The result then partitions P players missing from the corrected
hindsight and realistic final rosters by kickoff lock at 3:55 PM. An unlocked
residual is only a necessary timing condition; salary, position, stack and
retained-candidate constraints can still make it unreachable.

The report must present the corrected perfect-information hindsight ceiling,
the realistic tail-aware policy and the naive projected-mean comparator on the
same weekly-max and tail grid. It must also split liveness and P-distance by
the immutable first-failed layer at 210. This amendment expands diagnostics
and repairs comparator identity; it does not change the population, worlds,
decision time, primary recourse assignments or adoption status.

### Pre-freeze serialization recovery (2026-08-15 09:04 CDT)

Execution `realistic-recourse-sizing-v1-p2n4c` failed while hashing the first
pre-outcome proposal because the BigQuery grouping identity supplied NumPy
`int64` season/week scalars to Python's strict JSON encoder. The failure was
before `freeze_proposals`, before either create-only upload and before the
outcome query. The proposal-set and result objects were independently
verified absent after terminal failure. No proposal assignment, comparator
assignment or realized result was exposed.

The licensed operational correction converts NumPy scalar values to their
identical standard JSON scalar values during canonical encoding and
normalizes the frozen ledger to standard JSON primitives. It changes no
population, data, candidates, worlds, policy, comparator, objective, decision
time, checksum ordering or outcome boundary. A regression test must prove
that integer, float and Boolean NumPy scalars produce a strict serializable
ledger. The replacement exact image must pass the full suite, then publish a
fresh create-only same-image scorer reconciliation at
`scorer-reconciliation-serialization-repair.json` before one replacement
zero-retry scientific execution is allowed. The original audit remains an
immutable record of the superseded image and is not accepted by the repaired
runner.

## Registered outputs

The create-only result is:

`gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-realistic-recourse-sizing-v1/result.json`

It must report:

- source/reconstruction/artifact checksums and PIT receipts;
- per-slate decision instant, final/in-progress/not-started game and player
  counts, proposal checksum, entries changed and alternatives considered;
- simulated objective before/after with a mandatory non-decline invariant;
- realized initial/final weekly maxima and tail counts at
  240/230/220/210/200/194/187;
- naive projected-mean re-optimization assignments, weekly maxima and tail
  counts, plus realistic-minus-naive policy-class differences;
- improved/tied/worsened slates, mean/median/max realized delta and season
  diagnostics;
- swap counts and locked/unlocked players changed;
- realized recovery versus the corrected perfect-information ceiling; and
- player-swap distance from corrected exact P, the corrected hindsight source
  and corrected hindsight final roster, so construction and recourse are not
  double counted;
- exact-P residual players split by locked/unlocked timing and immutable
  first-failed layer at 210; and
- full pre-outcome 194 liveness class counts and their descriptive association
  with realized treatment and treatment-minus-naive gains.

The run uses one task, zero retries, a full Git SHA and immutable image digest.
It reads no partial output; any failure is terminal unless a separately logged
operational-only correction leaves this protocol byte-identical.

## Interpretation

Report the historical executable-policy estimate separately from the
perfect-information upper bound. It is neither expected ROI nor promotion
evidence. A favorable result prioritizes the already scheduled UI-to-CSV
rehearsal and 2026 paired recourse shadow. An unfavorable result closes only
this fixed decision time, retained-candidate set and v1 policy; it does not
erase the feasibility ceiling or license post-hoc tuning.
