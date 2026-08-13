# Review: effective-rank implementation and frames reconciliation

Date: 2026-08-12. Review of `a958da8` (portfolio effective-rank diagnostic),
`53d7895` (frames reconciliation) and the G1 result. **No code was changed.**

---

## Corrections to my proposals that I accept

Three of the reconciliation's corrections are straightforwardly right and one
of them was an actual error on my part.

- **Ownership as consensus — my framing was wrong.** Realized ownership is
  observed *after* lock, so it is not a pre-lock forecast and can never serve as
  a live input; and repeated contest rows for the same player-slate are the same
  field observed repeatedly, not independent forecasts. Collapsing to a
  field-size-weighted player-slate estimate with slate-clustered uncertainty is
  the correct construction. My "free consensus projection source" phrasing
  implied a live signal it cannot supply.
- **"Order-of-magnitude power gain" was loose.** The 107 maxima are paired
  across arms, non-identically distributed across seasons, and arise from
  correlated selected books. The safeguard list in A1 — paired resampling, a
  season/location term, LOSO fits, influential-week sensitivity, visible failure
  on boundary shape estimates — is a better specification than mine.
- **Slate winnability is weaker than I implied.** With one Sunday-main slate per
  week the lever is weekly entry *volume*, not choice among simultaneous slates.
  That is still a lever but a smaller one.

The belief-distance correction is also an improvement: routing through the
`H/P/C/S` layers first, so a *selection* failure is not mis-attributed to a
projection error, is a better design than what I proposed.

---

## Code review: `research/portfolio_effective_rank.py`

The implementation is sound. `np.cov(..., rowvar=True)` has the right
orientation, `eigh` is the correct symmetric solver, negative eigenvalues are
clamped, the participation ratio matches the specification, spectral-entropy
rank is a good second measure, and artifact handling is careful
(`allow_pickle=False`, sha256 verification, finite check, `cand_ix` identity).
80 entries from 10,000 worlds is well conditioned.

Four changes, the first of which materially affects what the number means.

### 1. The participation ratio will be crushed by the common slate factor

No deflation of the leading eigenvector is performed. Every one of the 80
entries loads positively on "this slate scored high," so λ₁ will take the large
majority of variance. If λ₁'s share is ~0.85, then
`PR = (Σλ)²/Σλ² ≈ 1/0.73 ≈ 1.4`.

Reporting "the book contains 1.4 independent bets" is arithmetically correct and
answers the wrong question. Whether the slate runs hot is not a bet the
portfolio makes — it is the environment every entry shares. The
decision-relevant quantity is: **after removing the common factor, how many
independent bets remain?**

Report the participation ratio and entropy rank on the **deflated** matrix
(project out the first eigenvector, or equivalently residualise each entry
against the cross-entry mean score per world) alongside the raw values. One
extra step, and it is the number that actually informs entries-per-slate.
`top_eigenvalue_shares[:5]` is already emitted, so λ₁'s dominance will be
visible — but the headline PR should not be the pre-deflation one.

Suggested headline: **correlation-matrix participation ratio after deflation.**

### 2. The measurement is in-sample with respect to the selector

The 80 entries were chosen to maximise distinct covered worlds *using these
exact 10,000 worlds*. Measuring their covariance on the same worlds therefore
inherits the selection: the selector deliberately made them look decorrelated,
so the participation ratio is optimistic.

A strict world holdout is not available retrospectively — selection consumed all
10,000. Two things that are:

- **Add controls.** Compute the identical spectrum for a random 80 from the same
  slate's pool, and for the top 80 by `sim_mean`. The comparison
  selected-vs-random-vs-ranked isolates how much apparent independence the
  selector created versus how much the pool supplies. Cheap, and it makes the
  headline number interpretable.
- **Split prospectively.** For any G2 book, select on half the worlds and
  measure the spectrum on the other half. That is the clean version.

### 3. State the direction of the model-implied caveat

The reconciliation correctly labels the result model-implied because G0/G1 show
the simulator misses QB–receiver tail dependence. Worth stating **which way it
biases**, because that makes it actionable.

G0 measured simulated QB→WR lift at 1.053 against a realized 3.321. Under-modelled
dependence means simulated entry scores are *less* correlated than reality, so
the covariance matrix is closer to diagonal and the participation ratio is
**overstated**. The real book therefore contains **fewer** independent bets than
this diagnostic will report.

That converts a caveat into a usable one: treat the output as an **upper
bound**. It also means the diagnostic should be re-run after any G2 adoption,
where the number should *fall* — and if it does not, the new dependence law is
not reaching the portfolio.

### 4. Emit event counts beside the tail metrics

The pair joint-exceedance and Jaccard measures at the frozen tail lines are the
right constructions, but at 220 and 240 the number of worlds where any entry
exceeds is small and pair estimates get noisy fast. Report the raw event counts
per pair-cell alongside the ratios so thin cells are visible — the same lesson
G0 applied correctly when it declared its `≥4` cell unsupported at seven
realized events.

---

## One point where I would push back

The reconciliation demotes EVT to "a mandatory risk diagnostic rather than a
replacement promotion gate," and keeps the empirical
`240/230/220/210/200/194/187` grid as the registered decision rule.

That is defensible and I am not asking to replace the gate. But the reason for
proposing EVT was precisely that the grid decides on one or two Bernoulli
events, and keeping the grid as the *sole* gate preserves that problem intact.
The fitted-usage adoption — one eval-panel week crossing 240, against −7 weeks
at 194 — is the case in point.

A middle position that respects the conservatism: **a non-contradiction
requirement.** Keep the grid as the gate. But when the grid says pass *and* the
EVT diagnostic's shape parameter or preregistered return-level interval excludes
improvement, that discordance requires an explicit operator decision rather than
automatic promotion. It cannot promote anything the grid rejects, so it adds no
new adoption pathway; it only prevents a one-event pass from being automatic
when the fitted tail disagrees.

This costs nothing when the two agree, which will be most of the time.

---

## G1

The result is clean and the sequencing is right: G2 licensed but not launched,
gated on the active-only fitted-K revalidation, with the correct conditional —
if multinomial is selected the terminal dependence law changed and G0/G1 must be
rerun before a production-eligible G2. That is the standing downstream-change
law applied correctly to their own work.

The transport handling is also right: v1 invalid before metrics (ambiguous QB
team-weeks), v2 computation complete but truncated at Cloud Logging's
102,400-byte boundary and therefore no result, v3 the sole valid record with
checksummed transport. Treating a truncated log as *no result* rather than a
partial one is the conservative call and the correct one.

---

## Summary

The implementation is good and the reconciliation improved four of my seven
frames. The one change I would make before the diagnostic is run in anger is
**deflating the common slate factor** — without it the headline number will be
near 1.4 and will answer a question nobody asked. Adding the random-80 and
ranked-80 controls costs almost nothing and makes the result interpretable.
