# Neo4j selection-gap pipeline status and next experiment

**Date:** 2026-09-03  
**Audience:** operator, production team, and lab team  
**Decision:** the program has completed two narrow selection tests, but it does
not currently have a frozen, launch-ready experiment that addresses the broad
Neo4j finding that valuable corpus candidates are not reaching the final book.
The next such experiment should be an identical-pool, held-out KG-5 reranker.

## Why this note exists

The E0/Neo4j read established a large historical conversion gap:

- 29 of 54 slates contained at least one eligible 200+ lineup;
- only 10 of those 29 opportunity slates had a 200+ lineup captured by any
  observed final-fit strategy;
- only 38 of 279 distinct eligible 200+ lineups appeared in any observed
  final-fit book; and
- 241 of 279 were absent from every observed final-fit book.

The eight historical strategies selected weekly maxima of approximately
176.0--178.4 while their shared, outcome-known eligible-corpus maximum averaged
202.662. That difference is a hindsight diagnostic, not a promised recoverable
gain.

E0 records final-book membership but does not contain every causal transition.
It therefore establishes `FIRST_OBSERVED_ABSENCE_AT_FINAL_BOOK`, not that the
selector was necessarily the first stage to reject all 241 candidates. Some may
have been lost during eligibility, admission, pool capping, or post-selection
replacement. Complete candidate lineage is needed to distinguish those cases.

The separate D800 evidence points in the same direction: the adopted
D800_DEMAX K80 baseline was 181.456 mean weekly maximum while the corresponding
outcome-known D800 pool maximum was 194.505, a 13.048-point observed
pool-to-book gap. Again, this measures opportunity, not forecastable gain.

## What has already tested selection

### Experiment 087: DEMAX versus WEMAX on the same D800 pool

This was a clean, direct selector comparison. It changed approximately 34% of
book membership but was flat on the registered endpoint:

- proxy delta: `+0.00022`, interval `[-0.00307, +0.00507]`;
- raw weekly-maximum delta: approximately `+0.251`;
- 25 tied slates; and
- sign-flip `p = 0.91`.

It rules out the exact WEMAX replacement under that candidate pool, information
set, objective and budget. It does not establish that retrieval is solved or
that a selector using new point-in-time information cannot help.

### Experiment 088: calibration and eight-slot retention sleeves

This was the first decision-bearing treatment explicitly motivated by the
Neo4j/E0 findings. Its leverage-calibration arm and leverage sleeve were null;
the structural sleeve failed. The subsequent T3 sidecar explains that the
sleeves mostly exchanged existing entries for similarly correlated entries,
with the leverage sleeve slightly increasing redundancy.

This closes the exact near-identity calibration and eight-slot sleeve forms at
their frozen doses. It does not close a full-pool learned reranker, a different
information set, fixed-budget admission, or a generator/retriever crossing.

### Experiment 090: coherent joint-law overlay

090 changed the simulated joint law rather than directly learning which
existing corpus lineups to retain. Its accepted result was negative and the
exact frozen arm is not adopted. It does not resolve the general corpus
selection gap.

## What remains in the pipeline

| Item | Current status | Relationship to the Neo4j gap |
|---|---|---|
| 085 participation mixture | Frozen and requested as the next launch | Adjacent and valuable: it changes same-pool selection by modeling participation risk, but it tests one specific inactive-player defect rather than the broad corpus miss |
| KG-3A fixed-budget admission/retention | Planned; not frozen or launch-ready | Determines whether valuable candidates are removed before the selector at a fixed admitted count |
| KG-5 same-pool phenotype/matchup reranker | Planned; not frozen or launch-ready | **Most direct remaining test:** whether portable pre-lock traits can identify better lineups already present in the identical corpus |
| Direct phenotype generator | Planned behind the same-pool read | Tests corpus filling rather than pure selection and should not be conflated with KG-5's retrieval effect |
| KG-6 generation x admission x retrieval crossing | Dependency-gated | Final interaction test after component winners exist |
| Production E4 broad admission | Operational failure; no sealed score | Related to admission, but it performed no final K80 selection and currently supplies no accepted result |
| Coverage-194 versus ladder/mixed-book E0 comparisons | Descriptive only | Useful interpretation on already-open historical data; not adoption authority |

The lab's current action note accurately says that 085 is the only remaining
frozen historical experiment. Thus the roadmap contains direct answers, but
the executable queue after 085 does not yet contain them.

## T3 book-diagnostic consequence

The T3 result should refine the next selector test, but it should not become a
hard correlation gate as currently worded.

The report's approximately 31 "independent shots" is the entropy effective
rank of the 80-by-80 score-correlation matrix. The sidecar's separately
calculated independent-equivalent tail-shot count at 194 is approximately 42.9
for the three-bank control. Those are different quantities and must retain
different names.

Across all three recoverable banks, approximate control/treatment summaries are:

| Arm | Effective rank | Independent-equivalent shots at 194 | Simulated P(book max >= 194) |
|---|---:|---:|---:|
| Control | 30.90 | 42.93 | 0.35285 |
| Leverage sleeve | 29.82 | 42.54 | 0.34762 |
| Placebo sleeve | 30.90 | 42.86 | 0.35191 |
| Structural sleeve | 31.08 | 43.27 | 0.35184 |

The structural sleeve raises the threshold-shot estimate while slightly
lowering book exceedance probability. That demonstrates why independence is
neither a sufficient outcome nor a universal necessary condition: lineup
quality and complementary scenario coverage must be evaluated together.

Two evidence repairs should precede use of T3 as a standing experiment gate:

1. The currently referenced JSON contains only banks 621 and 622 (576 records),
   although the report describes all three banks. Bank 620 remains recoverable
   from the earlier Git object. Publish one 864-record cohort artifact or bind
   the separate immutable artifacts explicitly.
2. The sidecar evaluates the books on the regenerated selection worlds used to
   construct them. That is appropriate for diagnosing 088, but any new selector
   explicitly optimized for diversity must be evaluated on an independent
   world bank to prevent mechanical in-sample improvement.

Neither repair invalidates 088. They matter for designing the successor.

## Immediate execution sequence

### 1. Run 085 without delay

Do not reorder or expand 085. It tests a distinct, concrete selection-belief
defect and is already frozen. No KG work should delay its mechanics gate or
efficacy cohort.

### 2. Complete the minimum candidate-lineage package

Do not wait for a Neo4j UI, dedicated graph deployment, or registry v2. Freeze
the complete outcome-free transitions needed to classify each candidate as:

1. generated;
2. legal or rejected with reason;
3. unique or duplicate;
4. admitted or rejected with reason;
5. selector-eligible or ineligible;
6. selected or eligible-but-unselected, including dynamic marginal/rank; and
7. retained through post-selector replacement and final-book output.

The graph may index bounded summaries and evidence identities; dense candidate
and world matrices remain in immutable columnar/object artifacts. A separate
reader joins outcomes after the trace is frozen.

### 3. Run one cheap outcome-blind quality-diversity frontier screen

Use the identical D800 candidate pools and exact K80. Construct every treatment
book on a declared search bank and evaluate it on a separate held-out world
bank. Compare only:

1. exact D800_DEMAX control; and
2. one conditional-novelty treatment that maximizes marginal book value over a
   frozen 194/200/210/220 ladder while retaining candidate quality.

This should reuse existing selector primitives rather than introduce a broad
parameter search. Report held-out:

- `GLOBAL_WEMAX_PROXY`;
- P(book max >= 194/200/210/220/230);
- threshold-event overlap and independent-equivalent shots;
- effective rank as a diagnostic only;
- player, QB/game-spine and generator-family concentration; and
- exact K10/K20/K30/K40/K80 prefix behavior.

Do not promote a treatment merely because effective rank rises. It must improve
held-out book utility or relevant exceedance probabilities without a material
upper-tail loss. If it does not, stop the branch before a score-bearing cloud
cohort.

### 4. Route the first formal post-085 experiment from the screen and lineage

- If high-quality, complementary candidates reach the selectable D800 pool but
  are omitted, promote **KG-5 same-pool reranking**.
- If they are removed at admission, promote **KG-3A fixed-budget admission**.
- If the D800 pool contains no credible complementary candidates, route to the
  direct generator or KG-2 supply mixture rather than retuning retrieval.

This routing answers the causal stage before spending another historical read.

## KG-5 minimum experiment contract

KG-5 should use the identical frozen candidate pool, admission count, K, search
and audit banks, and resource envelope for control and treatment. It should be
a walk-forward model using only prior folds and portable pre-lock features,
grouped into a small number of prespecified families:

1. structure and salary allocation;
2. simulation beliefs, market, ownership/leverage and duplication;
3. boom, participation, player-pair/correlation and matchup/coverage traits.

Player identity should not be a primary feature. Missingness and source/as-of
identities must be explicit. Compare exact D800_DEMAX with one same-pool hybrid
reranker that combines the existing book-marginal value with the frozen
walk-forward phenotype estimate. Avoid dozens of feature-level arms; use a
small nested family or an instrument screen before the registered cohort.

Primary evaluation remains the current registered utility on exact K80, with
raw weekly maximum and 200/210/220/230 landmarks co-reported. Historical
results are development evidence because the panel has already been viewed;
prospective 2026 settlement remains adoption authority.

## Final direction

The program should not describe the Neo4j selection finding as already handled.
087 and 088 fairly rejected two narrow remedies. They did not test whether a
model using the full portable pre-lock feature set can rank the same corpus
better.

Accordingly:

> Finish 085, finish only the lineage needed to locate the loss, run the cheap
> independent-bank frontier screen, and make KG-5 same-pool reranking the next
> score-bearing experiment if the missed candidates demonstrably reach the
> selector. If they do not, run KG-3A or a supply treatment at the stage where
> the evidence shows the loss.

Registry v2 is not a blocker for this candidate-level corpus intelligence. UI
and generic graph expansion are not on its critical path.

## Source documents

- `reports/2026-09-02-e0-first-loss-rescue-summary.md`
- `reports/2026-09-02-production-to-lab-neo4j-score-priority-note.md`
- lab `reports/2026-09-01-knowledge-graph-takeaways.md`
- lab `reports/2026-09-02-sleeve-ownership-plan.md`
- lab `reports/2026-09-03-t3-book-diagnostics-findings.md`
- lab `PREREG-054.md`
- lab `PREREG-057.md`
