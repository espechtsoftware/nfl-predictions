# Winner anatomy protocol — FROZEN 2026-08-19

**Protocol id:** `20260819-winner-anatomy-v1`. Operator direction
2026-08-19: "I would like to do all of that… begin implementing
everything you can and performing necessary research." One-shot,
descriptive, outcome-aware; licenses nothing. Its single downstream use
is to sharpen the stack-relaxation freeze and the depth-lane reading.

## Components (all implemented and unit-tested before this freeze)

1. **Roster distance.** `evaluate_known_winner_overlap` (existing,
   null-calibrated, seed 8163, null_reps frozen at 500) over the
   registered money-worlds pool (`replay_candidates_staging`, the five
   `20260815-atlas-money-worlds` panels: pool = all registered
   candidates per slate, selected = the five books). Aggregated with a
   split by the 8 production-constructible winners versus the 43
   rule-violating ones. Reading key: if even constructible winners top
   out at low overlap, stack relaxation is not their binding
   constraint.
2. **Ownership profile.** Actual Millionaire-contest ownership
   (`nfl_raw.contest_ownership`, contest_name LIKE '%Millionaire%',
   2023–2025). Frozen matching rule: DST by nickname→code through the
   existing `_TEAM_NICKNAMES` with code-alias equivalence; skill by
   exact case-insensitive name (winner spelling then snapshot
   spelling), else a UNIQUE fuzzy token match; ambiguity = unmatched
   (never guessed). Per-winner profile: matched count, cumulative
   ownership, min/max, sub-5%/sub-10% counts, log10 ownership product
   (duplication proxy).
3. **World-optimum realism.** For each winner's solved best generating
   world (N1c identities), compare each player's simulated score in
   that world against the player's maximum realized score anywhere in
   the 54-slate corpus — for the N1c DK-legal optimum roster and, as
   the control, the winner's own roster. Reading key: optima routinely
   carried by beyond-realized-max draws mean depth-harvested rosters
   are mirages and the marginal upper tail is a law target; this is
   the mechanistic prior for the all-boom read.

## Governance

Uses realized outcomes descriptively (candidate actual scores, real
ownership, realized maxima). No fit, no tuning, no gate, no production
change; `gate_decision: null` pinned in the report. Runs locally,
sequential (BQ reads + numpy + no solver). Any rule change suggested by
this report still enters only through frozen fixed-budget arms or
prospective collection — descriptive statistics never tune production.

## Reality smoke (rule-1, outcome-blind, run BEFORE this freeze)

`--smoke 2023:1`: 1,242 pool candidates / 400 selected loaded for the
slate; winner resolved 9/9 and matched the frozen N1c roster exactly;
227 Millionaire ownership rows found with 9/9 winner slots matched;
773 world scores loaded from the recorded N1c block; realized-max map
covers 1,381 players. No overlap, ownership, or realism values were
computed or printed.

## Pins (sha256 prefixes)

- Module `src/nfl_dfs/analysis/winner_anatomy.py`: `df6d1f2e364378c9`
- Runner `scripts/analyze_winner_anatomy.py`: `e8d81c14d07e7b1e`
- N1c report (rosters, legality, world identities, optima):
  `50ea349c…`
- Snapshot features parquet: `20c48b58c8475e75`
- Local artifact manifest: `915d4a06a586eb52`
- Warehouse inputs: `nfl_predictions.replay_candidates_staging`
  (five money-worlds panels), `nfl_raw.contest_ownership`
  (Millionaire rows, 2023–2025)
- Output: `reports/winner-law-audit-runs/20260819-winner-anatomy-v1-report.json`
