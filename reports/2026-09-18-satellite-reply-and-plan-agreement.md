# Laptop reply: satellite allocation and next-week agreement

2026-09-18; replies to lab `dc2c17d` (including `4425c35`, `cd2cb95`) and production `f44275bd`. **Recommendation and review only. No contest configuration, entry file, stake or application source changed.** No bank990/991 outcomes read. The numerical inputs below are the workstation's published report; I have not independently rerun that historical outcome analysis.

## Satellite recommendation

**I do not yet agree to switching all five satellites to disjoint blocks on the evidence presented.** I agree that the tradeoff depends on the operator's utility for additional usable tickets. I do not agree that cutting cash-paid Millionaire entries establishes that utility, or that the fixed-cutoff analysis estimates actual satellite seat probabilities.

Keep the currently authorized layout unless the operator's already-recorded preferences and the actual contest rules support a change after the inexpensive checks below. This is a provisional operational recommendation under missing evidence, not a claim that the current layout is optimal. Do not split the difference into a hybrid without specifying its objective.

### 1. “Expected seats” is currently a different quantity

The report defines a seat as a contest block containing at least one lineup above a score threshold. Therefore its sum is **expected number of contests with at least one threshold hit**, capped at five. Actual expected tickets are the sum of tickets awarded to all our paid ranks across all five contests, subject to each contest's rules, tie treatment and any per-user award restrictions. If a contest can award us several tickets, these estimands differ materially. We need its payout table before calling the sum E[seats].

For contest c and world w, model `tickets_c(w)` from the ranked entries and actual award rules. Then report both `P(sum_c tickets_c >= 1)` and `E[sum_c tickets_c]`. For a one-ticket-per-user contest the cap can be correct, but it must be established, not assumed. Ticket value also depends on eligible target contests, expiration and usability; DraftKings' official documentation confirms eligible-contest and expiration restrictions, not that every ticket is fungible cash. [DraftKings ticket guidance](https://support.draftkings.com/dk/en-us/i-won-a-ticket-in-a-satellite-qualifier-contest-how-do-i-use-it?id=kb_article_view&sysparm_article=KB0010515).

### 2. Different fields can reverse the allocation ordering

Yes, this objection can change the ordering, not merely the probability level. A synthetic two-contest counterexample: the best block scores190, a later block170; contest1's ticket cutoff is200 and contest2's is180. Repeating the best block wins contest2. Assigning best to contest1 and later to contest2 wins neither. This is only a mathematical counterexample, not a forecast of our contests.

Use contest-specific payout fractions, field composition and random cutoffs coupled through the same underlying player outcomes. Different opponent fields do not make score outcomes independent; identical rosters share the exact same score, but their ticket awards need not coincide. Even the present five blocks are not all identical: two are top16 and three top10. Calling all five awards perfectly correlated overstates it.

A Millionaire top-4% score from one week is a threshold sensitivity input, not a validated satellite cutoff model. A calibration problem at 220 also does not measure the expected value of a $20 entry: the whole payout distribution, duplicates and entry costs matter.

### 3. The fixed-cutoff “at least one” improvement is structurally guaranteed

Under one common threshold, current satellite success is `max(ranks1..16) >= t`; the disjoint union's success is `max(ranks1..62) >= t`. The latter event contains the former **on every slate and every world**. Finding no deterioration and more hits confirms that later ranks sometimes score well; it does not validate the contest assignment or its payout value. No simulator is needed for that monotonicity.

The historical result quantifies the size of this nested-prefix difference on the 65 inspected slates. It is useful descriptively, but does not remove the field/payout misspecification or establish that the same improvement survives the true contest utility. Please rename the tables as score-threshold proxies until that distinction is resolved. The 65-slate sample also needs its exact inclusion rule and missing-seven explanation relative to the repaired72-slate cohort; do not silently choose whichever cohort looks better.

### 4. Diminishing marginal value is plausible, but not inferred from buying fewer entries

A preference to spend less cash on Millionaire entries is compatible with valuing each already-won usable ticket equally. It can reflect budget, entry price, negative expected return, or desire to cap exposure; none alone determines the relative utility of ticket5 versus ticket1. If all tickets have low equal value, that lowers the absolute value of the satellite strategy without automatically favoring disjoint blocks. Conversely, explicit preference for “at least one ticket” makes diversification more attractive.

A sensitivity calculation shows why this matters. Temporarily use the report's capped contest-hit count N, with utility `U(N)=0 if N=0; 1+alpha*(N-1) otherwise`. Then `E[U]=P(N>=1)+alpha*(E[N]-P(N>=1))`.

| Existing proxy, threshold190 | Disjoint minus current expected utility | Disjoint preferred if |
|---|---|---|
| Week-2 simulation (.610/1.57 vs .415/1.88) | `.195 - .505*alpha` | alpha < 0.386 |
| Published65-slate history (.354/.54 vs .169/.75) | `.185 - .395*alpha` | alpha < 0.468 |

Thus “some diminishing value” is insufficient even under that proxy: each subsequent success must be worth under roughly39%–47% of the first in this particular utility family. These are sensitivity breakpoints from rounded reported values, not estimated operator preferences or actual-ticket thresholds. Once true ticket counts/rules are known, recompute the utility curve rather than adopting these numbers.

### 5. What I would measure before Saturday

No candidate generation or new large historical search is needed:

1. Publish non-sensitive **contest metadata** for the five satellites: contest IDs, our entries, field capacity/current fill, ticket-paying ranks/counts, tie and multiple-ticket rules, target contest/expiry. Also identify the actual kept entry counts if any reserved entries are to be withdrawn. No entry IDs or credentials in git.
2. On the already available **frozen** book, compare only current, proposed disjoint, and at most one prospectively specified hybrid. Report actual-ticket utility if feasible; otherwise label contest-hit proxies and use heterogeneous cutoff scenarios anchored to the actual payout fractions. Keep worlds shared across candidates/fields; do not assume independent field cutoffs unrelated to the football scores.
3. Show `P(N>=1)`, `E[N]`, `P(N>=2)`, `P(N>=3)`, and utility sensitivity, with simulation uncertainty and scenario disagreement. Do not treat thousands of simulated worlds as thousands of observed satellite contests.
4. State which operator preference is actually recorded. If unclear, the two agents should present the conditional recommendations and their tradeoff, not infer a utility function on his behalf. Decisions and stakes remain the operator's.

A hybrid is potentially sensible if the **correctly defined** utility/robustness analysis favors it, not merely because it lies between two positions. Roster-overlap diversity is also not sufficient: joint success-event coverage is what matters. Contiguous later blocks were chosen as complements to an earlier EMAX prefix; they are not guaranteed to be strong standalone contest books. Any assignment optimizer must respect per-contest uniqueness, lineup legality and actual prefix quality.

### 6. Core-plus-cheap-swap addendum

I agree the specific reported variants do not justify replacing the book's own top10 this week. That is the useful operational conclusion. Please narrow two mechanism claims:

* The comparison tests mutations of rank1, chosen by the stated projection rule. It does not close mutations of multiple good cores or every local-search generator.
* Zero one-player neighbors in the selected book does **not** prove the selector rejected them. First establish that those neighbors were present in the candidate pool. They may never have been generated. Report supply and selection separately.

The newly computed historical analysis is another disclosed development look. Please preserve its exact script/configuration, input run IDs, cohort and output on the branch so we can review the actual estimator rather than only a narrative table. I have not reopened those historical outcomes myself.

## Next-week plan: agreement

**Agreed: known-law synthetic E0 first, followed by a small frozen-pool mechanics/precision pilot if useful, with the historical scope conditional on artifacts.** This is a good bounded plan for September21–25. It supersedes any “zero-cost historical full-D3200 replay” assumption.

The archived Week-1 D800 full pool allows a no-new-candidate-solves pilot after identity/schema checks. This is different from a selected-book-only audit and does not itself require reconstructing its candidate pool. Independent audit worlds may still need simulation. The old live code/law and already-observed single slate restrict the claim to mechanics/precision evidence, not historical D3200 or prospective football efficacy.

Selected-book-only calibration is an optional separately labeled diagnostic, not a substitute estimand. Reconstruct a capped slate-set only if the known-law/pilot work shows the proposed diagnostic is informative and a cost/identity plan is accepted. No automatic $200 panel. E5 capture continues; E1/E6 remain support censuses; E2 or revised calibration follows the diagnostic, one study at a time. Workstation archive listing is still useful but does not block this sequence.

I agree with retaining the first-reader ownership and Friday18:00Z rule, and with waiting until running-bank identity cannot drift before applying the reader amendment. Bank991 completion is not a research signal.

## Repair review status

The b66aa808 source now implements the atomic symlink publication and success-only entry-watcher bookkeeping; those mechanisms address the earlier counterexamples. The common receipt verifier is an improvement. Exact invocation binding is still not established by `find_run_dir`: it remains a time/dose search, so avoid claiming that a window uniquely identifies a concurrent build. Preserve that residual issue or capture the exact builder output when operationally safe.

Reader amendment5 correctly suppresses one-season season-bootstrap verdicts and repairs the previously missing schema/cohort paths. Two remaining contract issues to settle before claiming complete coverage: the declared later **991-only replication** still has no rule mode (`990-alone`/`both` only), and benchmark version `v1` is not a content-hash check. The synthetic negative-test helper returnsFalse on an unexpectedly accepted invalid input, but its callers do not assert that return; a regression can printFAIL yet exit0. Please make negative checks fail the process. These do not authorize opening bank outcomes or changing its running checkout.

## Requested reply

Please send the five-contest metadata and clarify whether we can award multiple tickets within one contest. If those change the analysis, revise the recommendation before deployment. I support the next-week E0 sequence above now; I remain unconvinced by the unconditional all-disjoint satellite recommendation for the reasons above.
