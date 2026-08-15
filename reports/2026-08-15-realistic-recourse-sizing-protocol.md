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
- improved/tied/worsened slates, mean/median/max realized delta and season
  diagnostics;
- swap counts and locked/unlocked players changed;
- realized recovery versus the corrected perfect-information ceiling; and
- player-swap distance from corrected exact P, the corrected hindsight source
  and corrected hindsight final roster, so construction and recourse are not
  double counted.

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
