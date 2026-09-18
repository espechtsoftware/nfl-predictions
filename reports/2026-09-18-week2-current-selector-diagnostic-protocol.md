# Week2 current-selector diagnostic: reproduction and modeled220 coverage

September18,2026. Freeze before score-matrix values or stored ranks are decoded. This is a mechanics
and model-objective diagnostic, not an efficacy/adoption experiment. Use the exact hash-verified
September17 D6400/K90 archive from week2-archive-preflight.json. No2026 actuals, no model changes,
no candidate solves or cloud executions. Independent review pending.

Read only frame id and candidate cand/players/salary/book_rank; book_rank is the stored MODEL selection,
not an outcome. Read both hash-verified float32 matrices. Build joint candidate totals by adding mapped
player rows in sorted-ID order with float32 summation (the persisted roster order), then concatenate
incumbent10000 andhsim10000 worlds equally. Numerical summation order can differ from the original
in-memory Lineup order; disclose that if reference reproduction fails. Do not tune a tolerance to force
roster agreement. Greedy raw expected max follows the exact archived selector's float64 evaluation.

First select97 rows on the full matrix and compare first90 candidate IDs, in order, with book_rank.
If they differ, report mismatched positions, identities/order/precision limitations, and STOP before
coverage interpretation. No claim of reproducing the entry book if baseline fails. If they agree,
the extra7 are a diagnostic extension of this older pool, not the final D12800 entry book.

Report for baseline prefixes1/10/20/30/80/90/97 and the actual97 layout blocks:
1;2-24;25;26-30;31;32-33;34-43;44-53;54-63;64-79;80-95;96-97:
mean raw maximum and model P(max>=220), including separate component probabilities, and empirical
hit counts. Also report full-pool P(any>=220), whole-book fraction of pool-hit worlds covered,
and unselected candidate with the greatest extra220 coverage conditional on the book missing.
That last value is a diagnostic for a hypothetical98th addition, NOT an achievable97-entry swap.
Report maximum standaloneP220 in pool versus the first DEMAX row, whether that candidate is selected
and its rank; equal probability ties choose earliest candidate ID. No hindsight scores involved.

This quantifies target alignment inside the model; probabilities reuse selection worlds and may be
optimistic or miscalibrated. No alternate selector is adopted, and no claims about the actual27 missed
historical220 lineups can be inferred. Baseline objective is raw dual_emax; utility is not substituted.

Checks: allfive exactinput hashes/generations,435uniqueplayerIDs/6400unique9-playerrosters,
finitearrays,90unique storedranks exactly1..90, prefixidentity,97distinct selections, monotonic
bookmaximum/coverage. Blockrows are disjoint and cover97. Singleprocess,1BLASthread,5minutecompute
cap afterdownload,2GiBworkingarray cap,10minwall. Commit script before execution. Save source/input
identities, limitedaggregate/modelcandidate-index outputs and failures; do not output player names.
