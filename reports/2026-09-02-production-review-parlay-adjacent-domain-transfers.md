# Production review for lab: parlay-adjacent domain transfers

**Date:** 2026-09-02  
**Reviewed document:** `reports/2026-09-02-operator-note-parlay-adjacent-domain-transfers.md`  
**Purpose:** identify what should affect the research program, what should remain additive measurement, and
what must be corrected before the ideas become experiment inputs.

## Executive disposition

The note contains useful ideas, but it does **not** justify changing or interrupting experiment 088, the
frozen participation experiment 085, or the frozen regime-overlay experiment 090. Its best immediate
contribution is better measurement of the books we are already generating and selecting. Its most promising
new research contribution is market-implied dependence, but the current data does not yet support the
strong version claimed in the note.

Production recommends:

1. Seal and read 088 unchanged.
2. Add T3 book-correlation and exceedance diagnostics as a post-hoc sidecar, not as fields added to the
   frozen 088 reader.
3. Run a small T1/T2 data-feasibility and point-in-time audit before defining a score-bearing arm.
4. If market-implied dependence survives that audit, route it into a successor/reopening of the 089
   dependence-law program. Do not mutate the completed PREREG-058 screen and do not describe it as a 090
   regime-overlay target.
5. Route T5 and the contest-specific portion of T7 into A5/field-value work, where payout shape,
   duplication and qualification probability can be represented explicitly.
6. Keep T4 and T6 behind the current belief/dependence work. They are useful follow-ons, not reasons to
   delay the active queue.

## Effect on active and queued work

### Experiment 088 / PREREG-057

No design, runner, reader, arm, gate or interpretation change. At review time the 620 and 621 efficacy banks
were already running under the frozen contract, and the registered coordinator owned the 622 follow-on.

T3 can improve interpretation of 088 after its frozen primary read by reporting whether a retention sleeve
changed:

- the empirical correlation matrix of selected-lineup scores across simulated worlds;
- an effective-number-of-tail-shots summary;
- the entire simulated book-maximum exceedance curve;
- marginal E[max] contribution by entry or selection step; and
- simulated-versus-realized correlation after settlement, clearly labeled outcome-bearing.

These are sidecar diagnostics. They must not amend 088's family, endpoints or pass rule.

### Experiment 085 / PREREG-054

No change. Participation uncertainty remains a distinct pre-lock belief problem. Closing-line movement may
eventually become a diagnostic for whether the market learned an availability fact, but it is neither a
replacement for P(active) nor a reason to alter the frozen 085 treatment.

### Experiment 089 / PREREG-058

The note's statement that T1 feeds “089/regime-overlay targets” conflates two programs. Experiment 089 is
the ECC/minimum-KL dependence-law program. Its minimal candidates failed their instrument screen; the
optional preregistered recoupling form is the remaining declared branch. A valid market-implied dependence
series would be genuinely new evidence capable of reopening this family, but only under a new successor
protocol after its measurement contract is frozen.

It must not retroactively change PREREG-058 targets or reinterpret its completed screen.

### Experiment 090 / PREREG-059

No change. Experiment 090 tests the previously evidenced additive regime-overlay law at its frozen 004d
dose. It is not the market-implied-dependence experiment and remains sequenced after 088's sealed read.

### Neo4j/opportunity lineage

The graph may ingest the new T3 receipts and, later, decision-time/closing-market identities. That would make
book redundancy and belief disagreement queryable alongside first-loss/rescue lineage. Neo4j remains a
read-only evidence surface; it should not compute the scientific endpoint or launch an experiment.

## T1: market-implied dependence — promising, but feasibility first

This is the most important potentially new signal in the note. It addresses a real weakness: rare realized
co-exceedances give the dependence ladder few calibration targets. However, two data claims need correction.

### What production actually has

- `nfl_raw.prop_lines` contains player-prop rows, including historical alternate-yardage ladders where
  available. Existing production code can de-vig and monotonize those player-level ladders.
- `nfl_raw.odds_snapshots` currently collects DraftKings moneyline, spread and **game-total** markets. It
  does not collect team-total ladders or SGP combination quotes.
- The historical player-prop importer generally targets kickoff-minus-two-hours snapshots. Existing
  feature code further imposes a common main-slate lock where required. This is not the same thing as a
  complete closing-line history.
- The current Odds API request code contains no SGP pair-pricing route.

Therefore:

- The direct SGP route requires new provider/endpoint capability and a capture contract. It is not available
  merely by querying the existing tables.
- A spread plus one game-total line can imply a central team-total estimate, but it cannot identify a
  team-total variance ladder by itself.
- COR3M-style variance reconciliation requires the basket and components to be in compatible units.
  Passing yards, receptions, touchdowns and team points cannot be inserted directly into one covariance
  identity. They first require an explicit mapping into a shared fantasy-point or scoring-component space,
  with missing components and weights disclosed.

### Required T1 feasibility receipt

Before any experiment or law target is declared, produce one outcome-free report containing:

1. Exact table/object identities and available seasons, weeks, books, markets and snapshot times.
2. Coverage at the common DraftKings main-slate lock—not merely before each player's kickoff.
3. The number of players/teams with enough alternate points to identify a distribution rather than one
   median line.
4. The proposed common-unit mapping, including which fantasy components are missing.
5. Sensitivity of the inferred dependence constraint to the marginal-distribution and vig assumptions.
6. Direct-SGP endpoint availability, quote reproducibility, quota cost and terms, if that route is pursued.
7. A strict separation between decision-time values, closing values, and realized outcomes.

Only if the inferred target is identifiable, stable and materially different from the incumbent simulated
dependence should the lab draft a successor dependence experiment.

### Prior result that must remain visible

Production previously tested player-level alternate-ladder tail disagreement. Its frozen mechanism gate
failed and no candidate union was licensed. T1 is not automatically closed by that result because T1 is a
joint-dependence proposal rather than the rejected marginal-tail candidate feature. Nevertheless, that null
means alternate-ladder information cannot be treated as presumptively useful; the new dependence meter must
earn its own mechanism gate.

## T2: closing-line-value grading — useful post-decision instrument

The central idea is sound: compare the beliefs available at DFS decision time with a later, more informed
market. The boundary language in the source note needs tightening.

- A closing quote observed after the common DFS lock is **post-lock evaluation evidence**, never a pre-lock
  generation or selection feature.
- Store the exact decision-time snapshot and exact closing snapshot separately. Never overwrite the first
  with the second or call both “pre-lock.”
- `odds_snapshots` makes hourly game-line closes potentially derivable during live collection; it does not
  by itself establish closing player-prop-ladder coverage. That coverage must be measured and may require a
  new scheduled capture.
- Player observations within a team, game, week and bookmaker are dependent. Effective sample size and
  uncertainty must be clustered at least by slate/game; raw player-row count cannot support the claim of
  approximately 100-fold efficiency.
- CLV is a process diagnostic and calibration alarm, not an adoption or kill gate. It can miss genuine
  information the market never absorbs.

This work can proceed as a bounded measurement project after the feasibility receipt. It does not require
a score-bearing cloud panel.

## T3: book correlation and exceedance receipts — adopt as diagnostics

This is the cheapest high-value transfer and can use existing candidate/world matrices.

Recommended sidecar outputs per slate and arm:

- pairwise selected-lineup score correlation across identical worlds;
- mean, weighted mean, upper quantiles and effective rank of the correlation matrix;
- effective independent tail-event count at the program's threshold ladder;
- `P(book max >= x)` over a fixed score grid, including 187/194/200/210/220/230;
- marginal E[max] and marginal threshold-coverage contribution in selection order; and
- the same summaries by candidate family and QB/game spine.

The source note's `sqrt(1-rho)` formula is exact only under a restrictive equal-mean/equal-variance,
equicorrelated Gaussian approximation. Our lineup totals are heterogeneous and non-Gaussian. Report that
formula only as a labeled approximation alongside direct empirical calculations from the world matrix. Do
not optimize it or use it as an adoption endpoint without a separate validation.

Any “realized correlation” comparison opens outcomes and belongs in settlement, not an outcome-disabled
mechanics gate.

## T4: bagged and Thompson-style selection — defer until its prerequisite exists

Bagging world rows can measure and reduce finite-world selector instability. It does not repair a wrong
joint law, and 087 already found that changing the same-pool selector objective produced substantial book
turnover without moving the endpoint. A cheap stability screen may be worthwhile later, but it should not
displace belief correction, candidate retention, or the generation/admission/retrieval crossing.

Thompson-from-law-uncertainty is not executable responsibly until there is a walk-forward calibrated
posterior over dependence-law parameters. When that posterior exists, test one bounded dose; do not create a
new tuning grid.

## T5: spine-contrarian concentration — A5/field-value hypothesis

The useful proposition is not “more or less diversity.” It is that book concentration should reflect both
conviction and payout-space leverage:

- repeat a strong QB/game spine when its belief advantage is robust;
- vary lower-conviction completion slots;
- deviate from field concentration where doing so materially changes duplication-adjusted payout; and
- measure whether the resulting entries remain distinct in payout space, not merely by player overlap.

This cannot be adjudicated by historical weekly maximum alone. It needs contest ownership/entry capture,
duplicate/tie modeling and the exact payout curve. It sharpens the A5 and opportunity-lineage program; it
does not add an arm to 088.

The champion-slot analogy is suggestive, not proof that a DFS QB spine has the same payoff structure. Treat
it as a hypothesis.

## T6: late swap and two-stage optionality — strengthens existing work

Production already has recourse-aware initial-book and late-swap surfaces. The note contributes a helpful
formal interpretation: late players carry option value because the book can condition decisions on early
results. The next useful comparison is direct:

- frozen-lineup simulated value; versus
- two-stage simulated value under feasible DraftKings swaps and the same information schedule.

This remains prospective/operational work and should not delay the current historical score queue.

## T7: contest utility, overlay and optimism — correct before A5 adoption

### Contest utility

A qualifier is not generally winner-take-all. When multiple finishers receive the same seat, utility rises
to the qualification boundary and then largely saturates. The correct objective is qualification
probability or portfolio probability of earning at least one seat, using the actual field and payout rules.
“Maximum variance for qualifiers” is therefore not a valid universal prescription.

Milly and other top-heavy contests require payout- and duplication-aware expected utility. Different
contest shapes may warrant different books, but the objectives must be derived from the actual payout
curves rather than imported from poker terminology.

### Overlay and allocation

Contest-fill/overlay state can affect expected value immediately and belongs in A5. It does not improve raw
lineup score. Keep the contest lobby capture and lineup-quality decision separate so a good allocation
choice is not misreported as a modeling improvement.

### Optimism calibration

Do not apply a universal 26% haircut from one external bracket example. Estimate the program's own
simulation-to-realization calibration by frozen cohort, contest type and season. The external result is a
reason to maintain a haircut, not evidence for its coefficient.

## Outcome-boundary correction

Several suggested meters are described as opening no outcome while also comparing against realized
co-exceedance or realized inter-entry correlation. Those statements are incompatible.

Use three explicit stages:

1. **Pre-lock mechanics:** availability, snapshot identity, de-vigging, unit conversion, simulated
   dependence and book diagnostics. No realized fields.
2. **Post-lock market grading:** decision-time versus closing quotes. No contest result is required, but the
   close is unavailable at the decision boundary and must remain evaluation-only.
3. **Settlement grading:** realized player outcomes, lineup scores, contest ranks, duplication and payouts.

No field may move backward from stages 2 or 3 into stage 1.

## Recommended division of labor

### Lab

- Keep 088/085/090 frozen and follow their existing sequence.
- Add the T3 sidecar after 088's sealed primary read.
- Specify the T1 common-unit and identifiability test jointly with production's data audit.
- If T1 passes, create a new dependence-law successor protocol rather than amending a viewed 089 result.
- Consider one bagged-selector stability screen only after a dependence posterior or another genuinely new
  pre-lock belief source exists.

### Production

- Produce the T1/T2 source-coverage and point-in-time receipt from `prop_lines`, `odds_snapshots`, and the
  actual collector schedules.
- Determine whether direct SGP pair quotes are technically and contractually capturable, with explicit API
  quota cost; do not assume existing support.
- Preserve decision-time and closing snapshots as separate immutable records.
- Own A5 contest-utility, lobby-fill, field, duplication and payout-source integration.
- Expose T3 and later market receipts to Neo4j only as evidence after their authoritative artifacts exist.

## Priority recommendation

| Priority | Work | Disposition |
|---|---|---|
| P0 | Finish 088 and preserve active queue | Unchanged |
| P1 | T3 post-hoc book diagnostics | Implement as sidecar; no frozen-read change |
| P1 | T1/T2 data and boundary feasibility receipt | Begin bounded audit; no score arm yet |
| P2 | Market-implied dependence successor | Only if feasibility/mechanism gate passes |
| P2 | T5 plus contest-specific utility | Route into A5/field-value work |
| P3 | Bagged/Thompson selection | Wait for calibrated law uncertainty |
| P3 | Two-stage swap valuation | Continue through existing recourse program |
| Reject as stated | Fixed 26% haircut; universal max-variance qualifier policy; closing data as an input; COR3M output as an exact copula | Replace with program-specific measurements |

## Bottom line

The outside note improves our measurement roadmap and identifies a plausible new source of dependence
information. It does not overturn the current queue or establish a new scoring technique by itself. The
fastest trustworthy path is to finish 088, add direct book-level diagnostics, and determine whether our
actual market data can identify dependence under the common DFS lock. If it can, that is a legitimate new
signal for a successor dependence experiment; if it cannot, the idea remains a useful analogy rather than
an executable arm.
