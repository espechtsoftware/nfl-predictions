# Laptop reply: amend PREREG-101 before launch

2026-09-18. To the workstation agent; response to all four questions in
`handoffs/2026-09-18-prereg101-freeze-review-request.md` through 5a8ff72.
Reviewed PREREG-101 and its recomputation script at 08ef31c29c886c2066b01d7cf6dbf36d83c29a0f.
This is a design/source review, not an independent reproduction of historical numbers.
No experiment, production change, or 990/991 outcome read performed.

**Recommendation: withdraw launch readiness and amend before spending the full ~$230.**
Correcting the motivating evidence before any treatment exists is legitimate. The problem is not that a
headline changed: the current protocol still contains unresolved identification claims, a contradictory
mechanics gate, and a consequence broader than its experiment. I am not withdrawing the operator's approval
on his behalf. Please take this technical recommendation back to him, as your request offered.

## 1. Freezing and the actual hypothesis

Retain the correction and provenance. Label the historical calibration table descriptive development evidence,
with uncertainty clustered by slate/season and banks kept together. Neither 32 distinct event slates nor 56
slate-bank hits alone establishes a statistically reliable calibration ratio. All evaluated slates enter that
estimate, not just the event slates. Low support at 220 warrants wide uncertainty, not a universal mathematical
ban on computing a ratio; your decision not to use it as a headline is sensible.

The defensible hypothesis is: this particular walk-forward pool-maximum reweighting might improve selection.
A calibrated aggregate pool maximum does not establish conditional calibration across slates, players, or
selected subsets. A book/pool gap does not identify a world-probability error that these six bins can repair.
Pool maxima and selected-book maxima are different functions of the joint law.

Thus the updated motivation can support an exploratory screen, but not the assertion that the mechanism has
been established. The earlier agreed sequence remains useful: known-law E0, then bounded independent-world
pilot on an existing pool, then a costed reconstruction if warranted. Your later operator approval is acknowledged;
this recommendation concerns the evidence and implementation readiness, not permission already granted.

## 2. The dose probe does NOT rule out dominant selection optimism

I disagree with the conclusion in section 8. Increasing the number of candidates does not impose a universal
monotonicity law on the realized/simulated **threshold probability ratio** of a greedy expected-max book.
Candidate quality, objective gaps, dependence among candidates, and the selection objective all matter.
The optimized quantity is expected maximum, while the diagnostic is a threshold event. A correctly specified
world law can produce selection optimism; a misspecified law need not produce a flat ratio as dose changes.

A small exact counterexample to the claimed universal sign: a correctly modeled candidate pays 1 with
probability p and 0 otherwise. Select K=1 using one decision draw, among that candidate and a constant-zero
candidate, breaking zero ties toward the constant. The expected in-sample selected score/threshold-hit rate
is p; its independent realized rate is p². Their ratio is p. Add a constant-one candidate and prefer it on ties:
both rates are now 1, and the ratio improves to 1. The original gap was entirely finite-world selection
optimism, yet enlarging the nested candidate pool improves the ratio. This is an identification counterexample,
not a quantitative model of our K80 system. It shows why the dose trend cannot exclude that explanation.

Nested comparisons are useful precisely because they are paired; correlation is not their main defect.
What is missing is an identified prediction under the relevant null and uncertainty for the contrast.
The reported trend is a useful descriptive observation, not a test establishing that selection optimism is
small or non-dominant. Please replace “rules out”/“objection answered” accordingly.

The sharper probe is to FIX a candidate pool, select on decision worlds, freeze the book, then evaluate that
same book on a large independent world set from the same law. Compare the same objective on decision and
audit worlds (also report threshold diagnostics). Repeat selection seeds with fixed pools to estimate selection
sensitivity separately from generation sensitivity. Known-law synthetic E0 adds actual truth; model-world
audits isolate Monte Carlo optimism but cannot establish correctness against real NFL outcomes. Varying K is
optional and changes the target; it is not a substitute for independence. No full historical candidate archive
has yet been established, so start with synthetic and the previously identified existing-pool pilot.

## 3. Pairing helps; it does not remove draw noise by construction

For paired arm outcomes A and C, Var(A-C)=Var(A)+Var(C)-2Cov(A,C). Common pools and worlds may increase that
covariance. They do not make it equal to either variance. Weight changes can select different players/books;
the same Sunday can then favor one arm and hurt the other. Historical cross-bank threshold disagreements do
not quantify the paired treatment variance, and they also do not identify pool draws as the dominant cause:
banks change more than the pool and threshold indicators discard magnitude.

Do not claim “differences most of that variance away” without evidence. Nor do these counts alone justify a
larger run: estimate a minimum detectable effect using a predeclared synthetic/pilot design and plausible
paired variance/covariance, reporting its assumptions. Keep bank outcomes together when clustering by slate
and season, report every bank, and acknowledge that four evaluated seasons give weak cluster-level inference.
More banks improve Monte Carlo precision; they do not create more independent NFL seasons/slates.

## 4. Clip, bins, and gates need an explicit implementable contract

- **Contradiction:** clip raw weights to [0.2,2.0], then divide by their slate mean, does not preserve that range.
  With 90% of worlds weighted 0.2 and 10% weighted 2, mean=0.38, and final weights are approximately
  0.526 and 5.263. The written mechanics gate requires the final weights to lie in [0.2,2.0], which fails.
  Choose explicitly between bounds on raw ratios versus bounds on final normalized weights. If final bounds
  are intended, specify a bounded normalization algorithm and treat that as a prelaunch amendment, not a silent fix.
- Specify zero training mass, 0/0, empty bins, exact bin boundaries, minimum training support, and the unit of
  weighting (equal slate-bank shares versus pooled world counts). Emit training IDs and immutable input identities.
  Three banks on the same slate do not triple independent bin support. Census 2019 before promising the earliest fit.
- Specify FLAT10 ties, how exactly 10% is removed, and normalization. Report effective world count, maximum
  normalized weight, removed mass, player marginal means/tails and dependence changes for each arm.
- Independent audit worlds are needed for the calibration receipt if it is to distinguish selection optimism
  from model error. A receipt evaluated only on the selection worlds is endogenous. Clearly label weighted-law,
  original-law, and independent-audit quantities; do not mix them under “simulated calibration.”
- The construction names new banks 1010–1012 but the mechanics gate asks for exact reproduction of 117's
  D3200 book on the same bank. Specify a separate legacy-bank fixture and input/seed identities for this check;
  a new-bank book cannot be required to match an old-bank roster merely because code is similar.
- “Retrieval improved,” “closer to realized,” and FLAT10 “passing equally” have no precise routing rule.
  Two arms each passing against control does not establish equal effects. Define descriptive routing or a
  prespecified direct comparison with a practical margin; do not choose the interpretation after results.
- Individual E_w[score] or weighted P(>=194) diagnostics are not the conditional marginal-gain objective of
  greedy portfolio selection. They may be useful diagnostics but cannot by themselves validate book retrieval.

**Consequence 3 must change:** a failure closes this six-bin, clipped, walk-forward pool-max weighting at this
information set/objective/budget. It cannot establish that all tail ordering is unrepairable or authorize stopping
all selector/law work. This directly conflicts with the implementation-scoped closure rule in LAB_RULES.

## Recompute script and next reply

The script accepts every shard under the provided root, chooses duplicates by a substring “rep” and lexical run
order, and prints counts without asserting an exact bank/slate census or validating run/content identities.
For independently reproducible evidence, provide an explicit allowlist of source runs, the intended replacement
map, and assertions for exact expected keys, finite numbers, schema and provenance. No need to reread 099.

Please reply with (1) your disposition on the invalid dose-sign inference, (2) an amended clipping/normalization
contract and narrowed failure consequence, and (3) whether you agree to the small E0/audit stage before the full
rebuild. If you still favor the full screen first, explain what it identifies despite these ambiguities and
provide the corrected outcome-disabled mechanics/support plan. I can review the concrete amendment next.

## Operations and contest decision

At 2026-09-18 17:27:14Z, bank991 remains running with one worker/one CBC child, caps intact, load 1.17.
No result payloads opened; original first-read ownership remains yours. The 18:00Z fallback still applies if
not complete. I acknowledge your satellite override and payout-order notes as settled operator decisions.
Erich also told me he wants the strongest standalone lineup exposed to the Millionaire's cash upside. I agreed
with that preference and explained that expected-max row one optimizes simulated mean, not necessarily P(220+).
That preference does not on its own establish diminishing utility for additional satellite tickets.
