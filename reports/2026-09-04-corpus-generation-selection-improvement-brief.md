# Corpus generation and selection improvement brief

Date: 2026-09-04 UTC

Purpose: provide a self-contained description of the specific problem we are
trying to solve: generate more genuinely high-scoring DFS lineups, recognize
the best of those lineups before lock, and convert a stronger candidate corpus
into a stronger selected entry book.

This brief deliberately excludes deployment architecture, the broader model
stack, user-interface work, and unrelated data projects.

## Executive summary

The system currently has two distinct opportunities:

1. **Generation:** put more lineups with real 200-, 210-, 220-, and 230-point
   potential into the candidate corpus.
2. **Selection:** identify those lineups using only information available before
   lock and retain them in a small final book.

Recent work shows that generation can be improved. Participation-aware
opportunity redistribution produced materially more high-scoring candidates,
especially lineups built around teammates who benefit when a questionable or
doubtful player does not play. The problem is that the incumbent selector kept
only a small fraction of those new high scorers.

The current canonical historical K80 baseline remains **181.456 mean weekly
maximum**. A separate fresh-bank experiment measured a control mean of 180.747
and a redistribution mean of 181.314; those values are specific to that cohort
and do not replace the canonical baseline. There is no new baseline of record
yet.

The immediate experiment, 095, crosses the control and redistributed candidate
pools with the incumbent selector and a conditional-novelty selector. It asks
the right next question: can a different retrieval law convert the new supply,
or is a more targeted beneficiary-aware selector required?

## The narrow system under discussion

For this problem, the system can be understood as four stages:

```text
pre-lock beliefs -> candidate generation -> fixed candidate corpus -> K-lineup selection
                                                                    |
historical evaluation <- post-lock settlement ----------------------+
```

- **Pre-lock beliefs** describe possible player and game outcomes without using
  the eventual contest result.
- **Candidate generation** solves many simulated worlds and emits legal lineup
  candidates.
- **The corpus** is the fixed set of candidates available to the selector.
- **Selection/retrieval** chooses an exact K-lineup portfolio from that corpus.
- **Historical settlement** attaches realized fantasy scores only after all
  generation and selection decisions are frozen.

This separation matters. A generation method cannot receive credit for a
lineup that the selector never retains, and a selector cannot recover a lineup
that generation never created.

## What “ceiling” means here

Several different quantities have been called ceiling and must remain distinct:

- **Individual candidate score:** a corpus can contain individual lineups above
  220 or 230.
- **Weekly corpus oracle:** the highest realized candidate score available in
  each slate-bank corpus.
- **Mean corpus oracle:** the average of those weekly best candidates. The
  latest redistribution cohort reached 194.507.
- **Selected weekly maximum:** the best realized score in the K selected
  lineups. This is the operational historical metric and remains near 181–182.

The 194.507 mean oracle is not a hard system limit and is not an attainable
forecast. It uses hindsight to choose the best candidate separately in every
week and across repeated stochastic banks. It is evidence of available
headroom, not a promise that 13 points can be recovered.

## Current baseline and strongest selection result

The stable apples-to-apples baseline of record is:

| Measure | Current record |
|---|---:|
| Historical exact-K80 mean weekly maximum | **181.456** |

Experiment 085 tested participation uncertainty as a judgment/selection change
on common candidate supply. Its strongest arm, `P_MIX`, produced:

| Measure | Control | P_MIX | Change |
|---|---:|---:|---:|
| Mean weekly K80 maximum in that fresh cohort | 180.550 | 181.950 | +1.399 |
| Weeks >=200 | 9 | 12 | +3 |
| Weeks >=210 | 3 | 3 | 0 |
| Weeks >=220 | 1 | 0 | -1 |
| Weeks >=230 | 0 | 0 | 0 |
| Selected-roster inactive contamination | 21.53% | 16.25% | -5.28 pp |

The registered winner-CDF proxy passed, all three bank point estimates and all
four leave-one-season-out estimates were positive, but the raw-score interval
was `[-0.107,+2.906]`. Therefore P_MIX is a meaningful selection and integrity
improvement, conditionally recommended for prospective use after its live
point-in-time participation feed is certified. It is not yet a new historical
baseline or an extreme-tail breakthrough.

## What experiments 093 and 094 tested

Experiment 093 changed candidate generation by sampling whether designated
questionable/doubtful players participate. Experiment 094 repeated that arm and
added a redistribution mechanism: when a designated player was sampled out,
the model transferred opportunity to eligible same-team position-group
beneficiaries using pre-lock share information.

All arms used the same P_MIX judge. This isolated whether changing generation
created a better corpus and whether the existing selection process could use
it.

### Corpus supply

| Metric | Control | Availability-aware | Redistribution |
|---|---:|---:|---:|
| Mean weekly corpus oracle | 193.949 | 194.288 | **194.507** |
| Candidate instances >=200 | 251 | 263 | **314** |
| Candidate instances >=210 | 80 | 83 | **108** |
| Candidate instances >=220 | 26 | 27 | **35** |
| Candidate instances >=230 | 7 | 7 | **8** |

### Selected K80 result

| Metric | Control | Availability-aware | Redistribution |
|---|---:|---:|---:|
| Mean weekly selected maximum | 180.747 | 180.778 | **181.314** |
| Weeks >=200 | 6 | 7 | **9** |
| Weeks >=210 | 2 | 2 | **4** |
| Weeks >=220 | 1 | 1 | 1 |
| Weeks >=230 | 1 | 1 | 1 |
| Inactive contamination | 16.57% | 15.91% | **15.73%** |

The registered 094 contrasts were positive but did not clear their family-level
intervals. The initial 093 pass consequently failed formal replication and is
shadow-only. The exact redistribution law is closed against further dose,
weight, or transfer-rule tuning on these viewed outcomes.

The scientific lesson is still useful: participation-aware generation creates
additional mid- and high-tail supply, but the current selection method does not
reliably turn that supply into a stronger extreme-tail book.

## Exact identity of the newly generated lineups

The candidate populations can be compared without ambiguity. Within each
`(season, week, bank)` cell, canonical roster hashes define:

- `REDIST_ONLY`: generated by redistribution but absent from control;
- `CTRL_ONLY`: present in control but displaced by redistribution;
- `SHARED`: present in both pools.

A read-only reconstruction of the 54 frozen experiment-094 shards produced:

| Cohort | Candidate instances | Selected by its DEMAX book | Beneficiary-only |
|---|---:|---:|---:|
| REDIST_ONLY | 38,349 | 3,671 | 25,574 |
| CTRL_ONLY | 38,355 | 3,970 | 13,585 |
| Shared | 134,281 | 13,310 | 48,482 |

The often-cited `+63` at 200 is a **net** result. Redistribution added 131
lineups scoring at least 200 and displaced 68 such lineups.

| Threshold | Added | Added selected | Added beneficiary-only | Displaced | Net supply |
|---:|---:|---:|---:|---:|---:|
| >=200 | 131 | 18 | 103 | 68 | +63 |
| >=210 | 59 | 11 | 48 | 31 | +28 |
| >=220 | 21 | 4 | 18 | 12 | +9 |
| >=230 | 6 | 2 | 6 | 5 | +1 |

This is the clearest current localization of the selection problem:

- 103/131 (78.6%) of the added >=200 lineups were beneficiary-only.
- DEMAX selected only 18/131 (13.7%) of the added >=200 lineups.
- The control book had selected 17/68 (25.0%) of the high scorers that the new
  generation displaced.
- All six newly generated >=230 lineups were beneficiary-only, but only two
  were selected.

The new pool is not uniformly better. It contains many ordinary candidates,
adds valuable candidates, and removes some valuable control candidates. A
successful policy must improve **net fixed-budget retention**, not merely count
new high scorers.

## Where selection is going wrong

The incumbent selector chooses a diversified book designed to maximize expected
portfolio maximum under simulated worlds. That is sensible, but the recent
evidence exposes four weaknesses.

### 1. Simulation rank and realized tail rank are misaligned

Many realized high scorers are not sufficiently attractive under the simulated
decision matrix. Earlier diagnostics also found that simulated upper tails can
be too optimistic, particularly for leverage-heavy candidates. A selector can
therefore spend slots on lineups with impressive but inflated co-boom worlds.

### 2. Added opportunity is concentrated in a recognizable phenotype

Redistribution's useful additions are not random. They concentrate in lineups
containing teammates positioned to benefit from uncertain participation. The
current selector sees simulated scores but does not explicitly treat this
beneficiary mechanism as a candidate-level source of uncertainty or upside.

### 3. Generic diversity can trade away quality

A novelty or coverage selector may find candidates the incumbent misses, but a
global novelty mandate can also replace strong lineups merely because they are
similar. The desired behavior is conditional: rescue credible tail candidates
that add marginal coverage, not diversity for its own sake.

### 4. Evaluation previously summarized the pool more readily than the loss
point

Pool oracle and final-book maximum show that value was lost, but not where. The
new roster-hash lineage distinguishes generation additions, admissions,
selector ranks, and settlement. This makes it possible to measure the first
stage at which each high scorer disappeared.

## Experiment 095: the immediate test

Experiment 095 is a fixed 2 x 2 crossing:

| | Incumbent DEMAX | Conditional-novelty retrieval |
|---|---|---|
| Control generation | CTRL_DEMAX | CTRL_NOV |
| Redistribution generation | REDIST_DEMAX | REDIST_NOV |

Everything else is held fixed: D800 budget, K80, P_MIX judgment, historical
panel, resource envelope, and fresh banks 690–692. Selection uses a common
construction matrix, while a separately seeded held-out dual matrix supplies an
outcome-blind co-report.

The primary question is whether novelty beats DEMAX on the redistributed pool.
The key secondary question is whether that retrieval effect is specifically
larger on redistributed supply than on control supply.

Most importantly, 095 records each `redist_only` candidate, beneficiary status,
pre-lock tail values, exact selected rank, and realized settlement. It will
therefore report how many newly generated beneficiary candidates each selector
rescues or loses—not only the final average score.

At this writing, the corrected clean-source mechanics smoke has completed with
both stages engaged. Redistribution moved 56,539.469 simulated points and
changed the candidate pool; novelty changed approximately 38% of the control
book and 42% of the redistribution book. The durable freeze, immutable image,
cloud mechanics gate, and fresh-bank efficacy cohort remain the next execution
steps. Experiment 091 remains held and is unrelated to this crossing.

## Decision path after 095

### If conditional novelty succeeds

- Preserve the tested `REDIST_NOV` combination as a prospective shadow.
- Confirm that the gain is not purchased with worse inactive contamination or
  destruction of high-value control-only candidates.
- Compare exact live-size prefixes K3, K10, K20, and K57 as nested views, while
  retaining K80 as the historical primary.
- Do not infer that novelty works on every candidate pool unless the registered
  interaction and descriptive control comparison support that conclusion.

### If conditional novelty fails

Do not tune its thresholds, weights, or K on the same outcomes. The next bounded
test should be a **beneficiary-conditioned rescue policy** because 094 has
localized the useful additions there.

A simple first version should:

1. Start with the incumbent DEMAX book.
2. Form an eligible rescue set containing redist-only beneficiary candidates
   that clear frozen pre-lock tail-quality requirements.
3. Admit only candidates that add held-out 200/210 coverage or reduce marginal
   redundancy.
4. Replace a small, fixed number of the incumbent book's weakest marginal
   contributors.
5. Report both rescued high scorers and valuable incumbents displaced.

The rule must be specified before another result is opened. Realized 094 scores
may identify the retrospective target but may not enter live features or
selection.

## Features most likely to distinguish useful additions

The first model or rule should stay compact. Candidate inputs should be
available before lock and should describe a mechanism already observed:

- beneficiary-only and designation-exposure flags;
- the number and projected opportunity share of affected teammates;
- held-out probability of the lineup exceeding 194, 200, and 210;
- held-out mean and upper quantiles;
- marginal expected-max contribution to the incumbent book;
- marginal overlap or redundancy with already selected candidates;
- salary, ownership/leverage, stack phenotype, team/game concentration, and
  correlation summaries;
- source freshness and participation-probability confidence.

Start with an interpretable frozen rule or regularized model. A more complex
model is justified only if walk-forward validation shows that it improves
candidate recall and final-book scoring beyond the simple rule.

## Required diagnostics

Every subsequent selection comparison should report:

1. **Generation recall:** how many realized >=200/210/220/230 candidates were
   present in each fixed-budget pool.
2. **Selection recall:** how many of those candidates reached the final K book.
3. **First loss:** generation, admission, ranking, diversity conflict, or final
   contest allocation.
4. **Added-versus-displaced accounting:** high scorers rescued and high scorers
   sacrificed.
5. **Calibration by phenotype:** predicted tail probability versus realized
   tail rate for beneficiary, designated, leverage-heavy, and ordinary
   candidates.
6. **Portfolio result:** registered winner-CDF proxy, raw weekly maximum,
   threshold weeks and roster hits, oracle regret, and exact K.
7. **Robustness:** fresh stochastic banks, leave-one-season-out direction,
   bank vetoes, and contamination safety.

This is where the knowledge graph is most useful: it should answer lineage and
cohort questions over immutable evidence. It should not choose arms, change
scores, or promote results.

## What we know and what remains unknown

### Supported now

- Participation-aware judgment improves the selected book and reduces inactive
  contamination.
- Participation-aware redistribution produces more >=200–230 candidates.
- The added high-scoring supply is strongly concentrated in beneficiary-only
  lineups.
- The incumbent selector retains a low fraction of those additions.
- Exact roster-hash lineage can identify every added, displaced, selected, and
  settled candidate.

### Not yet established

- Whether conditional novelty converts the added supply on fresh banks.
- Whether beneficiary status remains predictive after controlling for existing
  simulated tail values and ownership.
- Whether a targeted rescue policy improves extreme-tail weeks rather than only
  the 200–219 range.
- Whether the historical gains survive prospective Week-1 selection and actual
  contest settlement.
- How much of the mean oracle gap is recoverable without hindsight.

## Immediate action plan

1. Freeze and launch 095 after the completed smoke and full validation bind the
   exact source, reader, gate, image, and seeds.
2. Read 095 once after all three fresh banks terminate cleanly; independently
   reproduce the frozen report.
3. Publish redist-only beneficiary capture, added-versus-displaced retention,
   and first-loss results alongside the registered score verdict.
4. If 095 passes, package REDIST_NOV as a prospective shadow. If it fails,
   preregister one compact beneficiary-conditioned rescue policy rather than a
   parameter sweep.
5. Preserve the canonical 181.456 baseline until an accepted, directly
   comparable historical policy replaces it.
6. Settle the control, P_MIX, and any licensed shadow books prospectively using
   identical Week-1 contest outcomes.

## Bottom line

The project is no longer searching blindly for whether better lineups exist.
They do. The immediate problem is recognizing a small, mechanism-defined subset
of the newly generated lineups without hindsight. Experiment 095 is the right
generic retrieval test. The exact 094 lineage supplies a clear fallback if it
fails: target beneficiary-driven additions with a compact pre-lock rescue rule,
and judge success by net retained high scorers and final-book performance—not
by corpus size alone.
