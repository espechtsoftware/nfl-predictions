# Post-review-6 plan (2026-08-05) — for Sol's second look

Both reviews are triaged below. Sol's two CRITICAL findings are
accepted as correct and were errors in the review-6 package itself;
both are already fixed in code (commit 34432a5) or scheduled as the
first action here. Gemini's five findings are triaged against the
ledger, with two accepted as testable, one refuted by an existing
arm, one reframed, one deferred.

Everything below is written so the reader can attack the plan before
compute is spent. Nothing in "SCHEDULED" has been run yet.

---

## A. Accepted corrections (Sol) — already fixed or first in queue

**A1. The oracle numbers were not measured on the shipping baseline.
ACCEPTED — package error.** The 30-pool/22-selected decomposition
came from the instrumented build whose selected clears were 22; the
shipping baseline is 27 and the weekly CSV I shipped was the GUMBEL
arm's 26. Three artifacts, three builds, presented as one experiment.
The ledger itself flagged the rebase (Addendum 83) and I failed to
carry the caveat into the package. Consequence: "eight recoverable
weeks" is established only for the 22-clear build. On the shipping
system the residual could be ~3 weeks, a different 8, or a different
frontier entirely.
→ **ACTION 1 (running/next): one canonical HF2 run** — pure shipping
defaults, oracle instrumentation ON, candidate persistence ON, all
six seasons, one image, one run id. It produces (a) the shipping
baseline scores, (b) the shipping candidate-oracle frontier, (c) the
labeled candidate table — from the SAME run. No cross-artifact
comparisons again.

**A2. The labeled candidate training set did not exist. ACCEPTED —
package error; FIXED in 34432a5.** The persisted rows carried
salary/p_line/sim_mean/sim_q99/tag/players and no actuals; the
normalized schema declared `actual_score` but the converter left it
null; only 910 live rows over two slate-weeks existed. Fixed in the
engine's persistence block:
- `actual_score` + `actual_rank` per candidate (labels).
- `all_tags` — EVERY generator that produced the roster. Sol is right
  that `seen` dedupe made attribution first-producer-only; a
  `_note()` call now fires at all 13 generator sites.
- `sim_sd`, `sim_q50/q90/q99`, `sim_rank_p_line`.
- `clear_bits`: packed bitmask of which simulated worlds the
  candidate clears (first 2048), because scalar p_line cannot
  reconstruct the greedy coverage selector (Sol §6).
- Provenance already present: run_id, season, week, tail_line,
  n_entries, n_sims, locks/theses counts, selected + selected_rank.
Full suite green.

**A3. The +0.428 correlation is inflated. ACCEPTED — reproduced
exactly.** Selected-oracle weeks have gap ≡ 0 and better sim ranks,
which manufactures correlation. Recomputed: **+0.211 on the 56
unselected-oracle weeks**. Also confirmed Sol's counter-evidence for
the selector: it contains the exact oracle in 47.7% of weeks vs
23.8% for a random 40-of-168 draw — the selector is roughly 2x
better than chance, so the honest framing is "alternative selectors
reading the SAME simulator signal cannot beat it", not "the selector
is blind". The ledger and any future package carry +0.211 as the
signal estimate.

**A4. Generator attribution is not yet safe for mix reweighting.
ACCEPTED.** Unequal batch sizes, first-producer tags (now fixed),
winner's-curse from examining only weekly maxima, 10 post-hoc
observations, multiple comparisons. No qbvar reweighting arm will be
run. Replaced by Sol's design: **leave-one-generator-out (LOGO)
counterfactuals on the persisted pool** — remove each generator's
EXCLUSIVELY produced candidates (now computable thanks to
`all_tags`), re-run selection on the frozen pool, measure lost oracle
frontier, selected actual score, threshold clears. No regeneration,
no new sims, cheap.

## B. Gemini findings — triage

**B1. Reranker on the persisted candidates (their #1).** Same
direction as Sol's §5, weaker form. ADOPTED with Sol's design, not
Gemini's: start with a low-capacity hierarchical residual model
(target = actual − simulated location, or residual clear-probability
with `logit(p_tail)` as an OFFSET), preregistered features, split by
season, scored at PORTFOLIO level, with a within-slate shuffled
feature negative control. Explicitly NOT an unrestricted XGBRanker on
107 slates. Gated behind ACTION 1's data.

**B2. Selector quotas over generator doses (their #2).** Interesting
mechanism (boom candidates are the argmax of the same 2,000 worlds
the selector scores against — a closed loop that could crowd out
other batches), but it is exactly the reweighting Sol's A4 says is
not yet supported. DEFERRED behind the LOGO counterfactual, which
tests the same hypothesis without a hard quota and without new
compute. If LOGO shows a generator's exclusive candidates are worth
more than their selection share, the quota arm becomes justified.

**B3. Do not optimize for 237 (their #3).** Both reviewers agree, and
so does the data (one 237 week in 107). ACCEPTED as guidance. Their
proposed test — re-run selection at `tail_line=187` — is cheap and
runs as **ACTION 3**, but it is a DIAGNOSTIC, not an economic
decision: Sol is right that the real objective is contest-specific
(qualifiers: P(any entry ≥ advancement rank); Milly: expected payout
on the real curve), and that the stylized payout curve in
`backtest/payout.py` plus the missing contest_entries rank/score
tables mean the dollar question cannot be settled with current data.
Logged for September when standings accrue.

**B4. Salary floor is pre-ensemble (their #4). ACCEPTED as a real
gap — reviewers disagree here.** The $49k floor was validated
2026-07-26 (mean best 180.1 → 182.3), which is PRE-ensemble; our own
post-ensemble law says such verdicts are unreliable, and three rules
have already flipped from load-bearing to dead weight under exactly
that test. Sol says don't reopen it; the law says do. **Resolution:
run it — one arm, `MIN_LINEUP_SALARY=47500`, ACTION 4** — because
the cost is one panel and the deletion streak (25→27) came entirely
from this class of test. If Sol's second look still objects with a
reason beyond "previously validated", it comes out of the queue.

**B5. Delete the chalk fade (their #5). REFUTED — arm already
exists.** The true fade deletion (`LEV_PENALTY=0`) scored **23/107**
(Addendum 80) and the combined deletion scored **20/107** (DELETE3),
both against 27. The fade is worth ~+2 to +4, measured twice on two
builds. Gemini inferred it was untested because the package described
the trained-ownership-input deletion without stating that the fade
itself survived its own test — a packaging error being corrected.
Their mechanism story (fade sinks chalk-adjacent oracles in
high-scoring weeks) is testable as a REFINEMENT, not a deletion:
condition the fade on the slate's expected environment. Logged, not
scheduled.

## C. What runs now (in order)

1. **ACTION 1 — canonical HF2 harvest.** Pure defaults, oracle
   instrumentation + candidate persistence v2, six seasons, one
   image/run-id, writing to `predictions.replay_candidates`.
   Produces the shipping baseline, the shipping oracle frontier, and
   the ~107 × ~168 labeled candidate table in one run. Everything
   else waits on it. *(Also re-answers "how many weeks are actually
   recoverable on the shipping system" — the number that decides
   whether the reranker is worth building at all.)*
2. **ACTION 2 — LOGO counterfactual** on that persisted pool
   (offline, no new sims): per generator, drop exclusively-produced
   candidates, re-run `select_tail_entries`, report Δ oracle
   frontier, Δ selected actual, Δ clears. First real evidence on the
   `boom` crowd-out hypothesis and on `dark`'s value.
3. **ACTION 3 — tail-line sensitivity** (`tail_line` 187 vs 194 vs
   200), one panel each on the rev family. Diagnostic for the
   objective question; explicitly not an economic verdict.
4. **ACTION 4 — salary-floor post-ensemble re-test**
   (`MIN_LINEUP_SALARY=47500`), one panel, LOSO judged.
5. **ACTION 5 — reranker v0** (only if ACTION 1 shows a material
   recoverable frontier): hierarchical residual model with
   `logit(p_tail)` offset, tag effects with shrinkage, plus
   preregistered disagreement features (ensemble-member spread,
   model-vs-market divergence, conformal interval width). Evaluation:
   leave-one-season-out, portfolio-level scoring, negative control
   with within-slate shuffled features, compared against (a) the
   existing selector, (b) tag-only calibration, (c) tag+disagreement.
   Adoption needs improvement in ≥4 seasons AND improved
   oracle-capture or payout regret — never training fit.

## D. Logged for September (data-gated, not scheduled)

- **Contest-specific objectives** (Sol §7): needs real 2026 standings
  (rank/score curves) to replace the stylized payout curve; then
  qualifier P(rank ≤ seats) and Milly expected-payout objectives.
- **Slate-level entry allocation** (Sol §9): a pre-lock
  slate-opportunity score (candidate frontier breadth, independent
  clear-world clusters, market totals/uncertainty, ensemble
  disagreement, ownership concentration) predicting pool-oracle
  clearance, LOSO-evaluated; then vary entries/contest mix by slate.
  Potentially worth more than lineup-level fixes. NOTE: partially
  computable from ACTION 1's output — if the frontier features come
  free from the harvest, the predictive test runs immediately and
  only the ALLOCATION decision waits for real bankroll data.
- **Environment-conditioned fade** (B5 refinement).
- Evidence pipeline activation (live news), online-conformal live
  loop (2026 scored rows), tracking-trait shadow features (needs the
  gsis crosswalk's 51 review rows resolved), Schaake dependence arm
  (gated on the variogram instrument), inverse-optimization field
  model vs skeleton resampler (classic standings).

## E. Standing corrections to the record

- Ledger and future packages cite **+0.211**, not +0.428.
- The oracle decomposition is labeled with its build until ACTION 1
  replaces it.
- "We persist candidates with actuals" was false when written; it is
  true as of 34432a5 and will be demonstrated by ACTION 1's table.
- The review-6 package's claim that the salary floor was "tested
  load-bearing" overstated a pre-ensemble result.

**Question for Sol's second look:** does ACTION 1's single-run design
close the lineage problem completely, or does the reranker also need
a second independent harvest (different seed) to separate
simulator-noise from genuine candidate-quality signal before any
model is fit?
