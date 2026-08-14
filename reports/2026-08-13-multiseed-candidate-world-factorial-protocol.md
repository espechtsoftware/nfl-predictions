# Multi-seed candidate/world exact-80 factorial protocol

**Frozen:** 2026-08-13 18:50 CDT, before Phase R or Phase S scoring results
were read. This is the follow-on promised in the separately frozen game-team
usage/ASOE protocol. It is not part of either Phase R or Phase S and cannot
change either decision.

**Prospective amendment:** 2026-08-13, after implementation review but still
before any Phase R/Phase S score was read and before this analyzer was
launched. In addition to the four cells, report all five native seed books as
a seed-noise envelope and q95/q99 pinball for each book's simulated weekly
maximum. The larger `CU` candidate universe is explicitly an added-pool-budget
discovery arm and cannot be adopted without the prospectively specified
fixed-budget confirmation below. The clean world-policy comparison is
`C0W0` versus `C0WU`. These additions do not change the four factorial cells,
registered seeds, tail-first ordering, or selector.

## Question

The incumbent seed audit found large search sensitivity and only 12.21/80
mean overlap between independently selected books. Test whether production
should use five independent candidate searches, five independent simulated
world sets, or both. Every evaluated portfolio contains exactly 80 final
lineups; this is not permission to buy more entries or enlarge the final book.

## Eligible inputs

Run only after the complete Phase S mechanical audit and frozen decision.
Use all five Phase S panels from the selected law:

- if Phase S selects ASOE, use the five treatment panels;
- otherwise use the five same-image control panels.

Use the registered seed pairs R0--R4, all 54 slates in 2023--2025, the Phase
S immutable image/code identity, and only the checksum-verified per-slate
artifacts written by those panels. Each artifact must contain canonical
candidate totals plus aligned unique player ids and the exact player-by-10,000
world matrix. The warehouse candidate roster and realized-score labels are the
only other inputs. No feature, roster, slate, seed, or season may be excluded.

## Mechanical reconstruction gate

For every seed and slate:

1. verify the artifact SHA-256 against the immutable candidate row;
2. require one artifact identity and one canonical candidate universe;
3. require identical player-id universes across R0--R4;
4. reconstruct every native candidate total by summing its nine player rows
   and require equality to the artifact's stored candidate total within
   `1e-4` points per cell;
5. rerun the production 194-point greedy coverage selector and require its
   exact selected roster order to match the warehouse `selected_rank`; and
6. require actual roster scores to agree whenever a roster occurs in more
   than one seed pool.

Any failure invalidates the experiment without a scoring decision. Repairing
a mechanical implementation defect requires a new image and a fully new run;
the scientific arms and decision below stay fixed.

## Four fixed books

For each slate deduplicate rosters by their exact nine-player id set. Stable
candidate ordering is R0 candidates by native `cand_ix`, followed by only
novel R1, R2, R3, then R4 candidates in each seed's native `cand_ix` order.
Stable world ordering is R0's 10,000 worlds followed by R1, R2, R3, and R4.
Use the unchanged production greedy coverage selector at line 194, including
its probability and mean-total tie breaks.

Evaluate this fixed 2×2 factorial:

| Arm | Candidate universe | Selection worlds |
|---|---|---|
| `C0W0` | R0 only | R0 only |
| `CUW0` | union R0--R4 | R0 only |
| `C0WU` | R0 only | concatenated R0--R4 (50,000, equal weight) |
| `CUWU` | union R0--R4 | concatenated R0--R4 (50,000, equal weight) |

`C0W0` must reproduce the Phase S R0 selected roster order exactly and is the
incumbent comparator. Cross-seed roster scoring always sums player draws in
the destination world block; it never reuses a candidate's native totals as
if different seeds shared worlds.

### Fixed-candidate-budget confirmation

Also construct one score-blind candidate set `CB` at exactly the R0 candidate
count for that slate. After the same exact-roster deduplication, bucket each
candidate by the first seed that supplied it. Allocate `floor(B/5)` candidates
to every seed, where `B` is the R0 candidate count, and allocate the first
`B mod 5` remainder slots to R0, R1, and so on. Within each seed take canonical
native `cand_ix` order. If a source has fewer than its quota, fill the deficit
one candidate at a time from the still-available R0--R4 buckets in that fixed
order until the set has exactly `B` candidates. No realized or simulated score
enters this allocation.

Evaluate `CBW0` in R0 worlds and `CBWU` in concatenated R0--R4 worlds. These
are a predeclared confirmatory sub-analysis, not extra factorial cells. They
remove the best-of-a-larger-pool advantage while retaining multiple candidate
searches. Run and report both regardless of which four-cell arm wins, but bind
their production verdict only if a `CU` research arm wins.

## Frozen evaluation and decision

For every arm report selected weekly-best and candidate-pool-oracle counts at
`240,230,220,210,200,194,187`, mean and median weekly best, candidate counts,
selected overlap versus `C0W0`, all weekly deltas of at least ten points,
and per-season diagnostics. Also report candidate novelty by source seed and
the score-free simulated world-coverage diagnostics for the selected books.
For each arm, treat the maximum across its 80 selected lineups in each
simulated world as the forecast distribution for that slate's selected-book
maximum; report q95 and q99 pinball against the realized selected-book maximum.
These proper scores are diagnostics and do not enter the tail-first decision.

Also report the five native books `R0`--`R4`, each selected in its own 10,000
worlds from its own candidates: the same seven-threshold grid, mean and median
weekly best, q95/q99 pinball, the min--max threshold-count envelope, and mean
pairwise selected-roster overlap across all ten seed pairs. This is the
prospective seed-noise floor for interpreting this factorial and future arms.
It cannot retroactively re-adjudicate a closed arm.

Rank the four arms lexicographically by the summed selected weekly-best counts
over all 54 slates at `240,230,220,210,200,194,187` in that exact order. If all
seven counts tie, use higher mean across the 54 weekly maxima. Exact remaining
ties use this fixed least-change order: `C0W0`, `C0WU`, `CUW0`, `CUWU`.

The four-arm winner is the multi-seed research conclusion. The separate
production-eligible comparison below controls whether world union can ship.
There is no average-score or individual-season veto, matching the operator's
stated tail-first utility. Per-season splits and a 2,000-resample slate-
clustered bootstrap (seed `8,132,027`) are diagnostics only and cannot override
either frozen ranking. No seed subset, weighting, selector threshold,
candidate cap, or alternative tie break may be tried on these realized
outcomes.

For interpretation, report the candidate main effect at each world setting,
the world main effect at each candidate setting, and the difference-in-
differences interaction. The roughly five-times-larger `CU` pool confounds its
main effect with added candidate budget. The interaction substantially cancels
that shared pool-size advantage, so it remains the headline scientific
contrast, but neither `CUW0` nor `CUWU` is immediately production-eligible.
If the research winner is a `CU` arm, it activates the prospectively frozen
fixed-candidate-budget confirmation and otherwise leaves candidate generation
unchanged. That confirmation is already specified above to avoid a post-hoc
construction choice. Independently, rank `C0W0` versus `C0WU` by the same
frozen tail-first law; that winner determines the production world setting.
At that setting, rank its `C0` book against the corresponding `CB` book by the
same law, with the `C0` book first in the exact-tie order. The `CB` verdict is
binding only when a `CU` arm won the research factorial.

## Production implication

If the clean comparison selects the `WU` setting, live selection must complete
all five registered world simulations and fail closed if any world artifact is
missing. If a `CU` research winner is followed by a winning `CB` confirmation,
live candidate generation uses the same fixed total candidate count and the
same five-seed quota/fill contract; otherwise it retains R0 candidates. Every
case still exports exactly 80 entries. This experiment does not authorize using
current-week results or any post-lock data in a live slate.
