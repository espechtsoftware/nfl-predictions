# Refreshed hsim trace: a smaller gap, with specific remaining weaknesses

The morning simulator can be reproduced exactly, and its disagreement with the incumbent is materially smaller on this small book than on Thursday's archive. However, important role and calibration differences remain. These are concrete next experiment targets, not evidence that either model now predicts real NFL outcomes better.

The frozen V2 trace at `2fda9467` reproduced **all 4,290,000 hsim scores exactly** in 3.69 seconds before emitting any attribution. It used the actual refreshed morning D160/K97 proof, source `2dc116c`, projection batch `2026-09-19 15:09:52.915006+00:00`, the same five 400-world calibration steps and 10,000 final worlds. Every team's targets/carries were conserved, and primary-QB passing yards/TDs exactly matched its team's receiving production. No parameter, lineup, eligibility or outcome changed.

| Same morning K97 book | Incumbent | Hsim |
|---|---:|---:|
| Expected best score | 190.6612 | 195.0521 |
| Simulated probability of at least one 220+ | 8.87% | 10.20% |

The gap is **4.3909 points / 1.33 percentage points**. Thursday's separate K90 book had a 19.71-point / 23.00-percentage-point gap. These are different populations, inputs and books; the smaller gap cannot be attributed solely to a particular repair. The archived four-way experiment remains the controlled input comparison. These are selection-bank descriptions, not independent efficacy estimates or calibrated real-world probabilities. The full D6400/D12800 host books are still pending and must be measured separately.

## What remains wrong or uncertain

**Quarterback role disagreement affects actual selections in the test book.** Fourteen of 97 lineups use one of six QBs that hsim treats as nonprimary for their team. Their served means are 11.50–16.55, while hsim gives them 0–0.61. The biggest example is Tyson Bagent: served16.545 versus hsim0.253, appearing six times. Hsim assigns all passing production to the highest-projected team QB; the incumbent recenters each QB on its own served mean. This is a proved disagreement between implemented role laws, not independently verified evidence about Sunday's starters. Do not turn this finding into automatic player removal.

The next production-owned check is the **source of each team's QB expectations**: archived depth/status, individual model component means, market anchors, and the served projection join. Establish whether the high nonprimary values are conditional-on-starting projections being consumed as unconditional forecasts, stale role inputs, or a reasonable representation of actual starter uncertainty. If a contract is broken, fix it as R; if role uncertainty needs a new probability model, test it as C. Keep team passing opportunity coherent instead of simply zeroing inconvenient players.

**The calibration loop improves fit, but does not achieve its stated matching goal.** Mean absolute skill-player residual falls from2.265 in pilot1 to1.063 in pilot5, then1.025 in the final sample. For distinct selected players, mean hsim-minus-served offsets remain RB+0.835, WR+0.886 and TE+0.446. This is not a claim that those served means are truth.

There is a concrete constraint to investigate. For Atlanta, served skill means sum to64.249 but hsim totals74.180. Across the five pilots, the sum of target weights falls1.000→0.414 and carry weights1.030→0.350 while simulated skill totals stay around73–77. The allocator normalizes weights inside each team, so shrinking all weights together cannot shrink the team's opportunity budget. The QB calibration separately controls passing efficiency. The observation and code identify a limitation of the coupled calibration, not an already-proven error in the underlying football expectations. Tampa Bay goes the other direction:79.717 served versus66.623 simulated.

Do not blindly restore post-hoc mean scaling: lab ledger049b v0.5 already found that improving marginal CRPS that way damaged joint high-score events. A new upstream calibration experiment must explicitly reconcile team budgets, QB and receiver targets, then test the joint tail and final selector. More pilot iterations alone are not established as a solution.

**Four selected players still have zero opportunity support in hsim.** Three fail the activity proxy; Ian Thomas passes that proxy but has literal zero target and carry priors, which multiplicative calibration cannot turn positive. The prior zero-target experiments already studied this general issue and found only small lineup gains; this is not a newly discovered universal cure. The current named cases and all player rows are retained for comparison with the completed larger pool.

## A reproducibility defect in the first diagnostic, resolved openly

V1 refused at parity: maximum score difference36.000002, with no substantive trace result emitted. It reconstructed pass-rate priors from a JSON receipt rounded to15 decimals. The actual live helper takes full-precision priors from the frame;24prior values differed by at most4.44e-16. V2 reconstructs using that unchanged helper and requires an identical canonical receipt. The resulting bank is exact. Both original versions, the failure receipt and amendment remain tracked.

This is random-stream/replay sensitivity, not a measured football scoring defect. Preserve lossless simulation inputs/calibration objects for future audits; a rounded human-readable receipt is not by itself sufficient to reconstruct every draw. The existing frame provides the lost precision here.

## Action and scope

Risk class: diagnostic; earliest resulting reviewed repair or calibration trial Week3. First priorities are the QB role/conditional-mean contract and a team-coherent calibration design, alongside the prepared [active-label × participation comparison](2026-09-19-active-label-participation-experiment.md). Production should repeat the fixed-book gap on the actual finished builds and prepare the already accepted weekly proper-score instrument. The latter, after settlement, can begin answering which law forecasts reality better.

[Complete trace](reviews/evidence/2026-09-19-refreshed-hsim-trace-results.json), [frozen V2 executable](reviews/evidence/2026-09-19-refreshed-hsim-trace-v2.py), [pinned inputs](reviews/evidence/2026-09-19-refreshed-hsim-trace-inputs-v2.json), [protocol and mechanical amendment](2026-09-19-refreshed-hsim-trace-protocol.md). Trace SHA256`0773a7481025f7f77d503ac376ae2df232710f0939d06a5eabb89a571f38bdfc`. Independent reproduction is requested, not yet claimed.

The [portable publication receipt](reviews/evidence/2026-09-19-refreshed-hsim-trace-publication.json) pins the35,346,304-byte input/reader bundle in the lab bucket, create-once and download-verified. It includes the original frame, candidates/book, both banks, historical fit objects, frozen reader and result. Transport may remap only local paths; retain every source/payload hash. Independent numeric comparison excludes transport provenance fields.
