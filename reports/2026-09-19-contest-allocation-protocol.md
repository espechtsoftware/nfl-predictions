# Same-book contest allocation: bounded model-Pareto pair exchanges

Frozen September19 before allocation comparisons. Operator priority is better weekend selection
and appropriate placement of high-scoring chances in contests. This test does NOT retrieve new
lineups into the book; it tests placement of the already selected97. No actual outcomes, payout
claims, live entries or dose/model changes. Independent review pending.

Input: exact Week2D6400 archive hashes plus the previously frozen/reproduced diagnostic97 index
list. Preserve ALL97rosters, uniqueness andMillyrow1; never swap that row. The diagnostic extension
beyond90 is not the finalD12800/K97entrybook. Read only frame.id, candidate.players and both score
arrays; use originalfloat32lineup summation and float64reductions.

Blocks, immutable sizes/order:1;2-24;25;26-30;31;32-33;34-43;44-53;54-63;64-79;80-95;96-97.
Compute for each block, separately in incumbent andhsim: expected best score, expected fixed
GLOBAL_WEMAX_PROXY utility of best score, andP(best>=220). The historical48-value utility constants
are read as in prior diagnostics; no current outcome information. These six per-block quantities
are model estimates and may be optimistic/miscalibrated.

Enumerate every two-row exchange between different blocks, excludingMilly. A swap is eligible only
if EACH of the six metrics is nondecreasing within1e-12 for EACH affectedblock. Among eligible swaps,
choose greatest sum of equal-mixture expected-maximum gains over the two blocks; require>1e-6points.
Tie within1e-12: smallest first row then smallest second row. Accept at mostFIVE swaps; recompute
eligibility after each. This objective is an engineering score, not expected payout; no contest
payout weights are invented. Report all accepted steps and all finalblock/component differences.

Do not reorder withinblocks. Wholebookmembership andfirstrow must remain identical; wholebookmodel
max/coverage are exactly invariant. In addition, report the familiar1/10/20/30/80/90/97prefix changes
as diagnostics: they are not interchangeable with disjointcontest objectives and can change when
blockassignment improves. No claim that every prefix or realcontest return improves is permitted.

Checks: allinputhashes,stored97indicesdistinct, all97rosterssame,blockpartitioninvariant,Millyfixed,
computedfastsingleexchange matches direct full reevaluation on a deterministic fixture AND each
acceptedrealpair. Final six-metric no-harm checks against originalblocks must pass. Retain ties and
boundary precision explicitly; same numerical convention as the reproduced baseline.

Singleprocess/1BLASthread,compute120seccap afterdownload,512MiBworkingarrays,wall5min. Do not tune
constraints/weights/budget after results. On noeligiblepairs report zero and do not widen search.
Positive result nominates only a current-final-book and independent-evaluation check; this Thursday
population cannot be substituted for Sunday's actual enteredbook. Commit executable before read.
