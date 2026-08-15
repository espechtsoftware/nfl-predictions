# Post-forensic exact-stack construction addendum protocol

Date frozen: 2026-08-15 05:20 CDT  
Protocol: `20260815-post-forensic-exact-stack-construction-v1`  
Scope: immutable repair4 `phase-s-cbwu-54` forensic corpus  
Status: corrective/descriptive analysis only; not a historical arm

## Why this addendum is required

The frozen forensic H/P oracle used QB+1 and no opponent bring-back. Production
candidates were generated with QB+2 and at least one opponent bring-back. A
read-only audit found that 51 of the 54 published P rosters violate at least
one of those production rules. The published P-C gap therefore does not isolate
candidate construction under the production contract.

This defect does **not** affect any candidate, selected lineup, S score, tail
baseline, arm comparison, or production policy. It affects only the hindsight
H/P attribution and conclusions derived from that attribution.

## Frozen inputs and output

Only the retained repair4 tables in the production-isolated
`nfl_forensic_review` dataset may be read:

- `final_forensic_20260814_player_corpus_repair4`
- `final_forensic_20260814_candidate_corpus_repair4`
- `final_forensic_20260814_oracle_rosters_repair4`

Every table must carry manifest label
`51edbe124846dc936ade71c4e5a9a07e`, corresponding to full manifest SHA-256
`51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`.

The create-only result object is frozen as:

`gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-stack-construction-v1/result.json`

Execution must use a full Git commit SHA and an immutable Artifact Registry
image digest. The original nine forensic outputs must not be overwritten.

## Computation

For each of the same 54 CBWU slates:

1. Reproduce the published loose P roster and score exactly from the union of
   candidate players. Failure to reproduce aborts the run.
2. Recompute H and P with salary $49,000–$50,000, exact DraftKings positions,
   QB+2 same-team WR/TE, one opponent RB/WR/TE bring-back, no two same-team RBs,
   no RB against the selected DST, at least two games, and all other frozen
   construction rules.
3. Reconstruct all candidate and selected scores independently, require exactly
   80 unique selected rosters, and recompute H-P, P-C, C-S, thresholds, and
   first-failed-layer counts.
4. Size the definition error with four outcome-viewed constraint cells:
   QB+1/no bring-back, QB+2/no bring-back, QB+1/bring-back, and
   QB+2/bring-back. These cells cannot promote or relax a stack rule.
5. Characterize exact P versus the generated pool using minimum player-swap
   distance, P-player candidate appearance counts, salary and position spend,
   games spanned, largest team block, QB stack size, bring-backs, and aggregate
   ownership where complete.
6. Recompute the published perfect-information late-swap ceiling with the same
   QB+2/bring-back construction contract. Report its corrected gain and tail
   counts, plus P-oracle player-swap distance from the selected weekly-best,
   the source entry chosen by the ceiling, and the final hindsight roster.
   This sizes overlap between the two opportunities without treating the
   hindsight roster as executable.

## Interpretation restrictions

- This is a correction of a descriptive diagnostic, not a new outcome-tested
  arm and not an adoption scorecard.
- The selected-lineup baseline remains unchanged.
- The original 78.994-point construction-gap and 44/54 first-failed-at-210
  claims remain provisional until this addendum completes.
- The original +42.62-point perfect-information recourse ceiling is likewise
  provisional because its final-roster solve inherited QB+1/no-bring-back.
- Any mechanism suggested by the corrected result must be frozen and evaluated
  prospectively without 2019–2025 outcomes.
- Pool admission and salary-floor conclusions may be restated only after
  checking whether their relevant corrected quantities change.

## Prospective follow-ups already licensed independently of the result

The following are outcome-unseen engineering candidates, not conclusions of
this addendum:

1. fixed-total-budget generator reallocation away from low-yield `lev`, with
   identical candidate/world/selector budgets and a compute receipt;
2. realistic late-swap shadow evaluation using only information available at
   each decision time and simulated remaining worlds;
3. construction-versus-recourse overlap measurement, only after both sides are
   defined under the same production legality contract.
