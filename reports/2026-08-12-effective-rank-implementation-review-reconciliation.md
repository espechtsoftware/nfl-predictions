# Effective-rank implementation review reconciliation

Date: 2026-08-12 CDT. This reconciles
`reports/2026-08-12-effective-rank-implementation-review.md` against the
outcome-blind implementation introduced at `a958da8`. The source review is
retained unchanged.

## Accepted implementation repairs

The review correctly identifies four missing disclosures. Before any panel is
analyzed, the implementation now:

1. reports raw covariance/correlation spectra and spectra after projecting out
   the covariance matrix's leading principal component;
2. compares the selected book with the same pool's top-simulated-mean book and
   twenty deterministic random books;
3. labels the current simulator's effective rank as likely optimistic while
   QB-receiver upper-tail dependence remains under-modeled; and
4. emits raw entry, world and pair-cell event counts beside every tail rate,
   lift and Jaccard value.

The first-PC-deflated correlation participation ratio is the preferred
conditional-diversity headline. Raw rank remains mandatory because the common
slate factor is a real source of unconditional portfolio variance. PCA
projection is used explicitly; subtracting the simple cross-entry mean is not
generally equivalent when entries load unequally on the common factor.

The same-world controls diagnose whether the selector appears more diversified
than its available pool and a simple ranking rule. They do not remove in-sample
selection bias. A future G2 exact-80 protocol must predeclare independent
selection/evaluation world halves (or independently seeded world books) if it
wants an out-of-world effective-rank claim. Retrospective splitting cannot
change the already-selected historical books.

## Directional caveat

G0/G1 make an optimistic bias plausible: materially understated QB-receiver
co-booms tend to make simulated lineup totals look less coupled than the real
tail. This is not a mathematical upper bound on effective rank. Lineup overlap,
opposing stacks, allocation competition and the changed within-lineup variance
can move individual covariance eigenvalues in different directions. The report
therefore says `likely optimistic ... not a formal bound`. Any selected G2 law
must rerun the diagnostic; whether effective rank falls and whether independent
world performance changes are empirical checks, not required directions by
definition.

## EVT discordance

Accept the review's middle position prospectively, with one constraint: EVT
does not silently veto the operator's tail-first utility. In the next
not-yet-frozen exact-80 protocol, predeclare that a stable, valid EVT diagnostic
which materially contradicts an empirical-grid pass triggers a mandatory
discordance disclosure and explicit operator production decision. It cannot
promote a grid failure, retune either arm or change the research result. A
prospective shadow is preferred when timing permits.

The active-label fitted-K versus multinomial comparison was frozen and launched
before either alternative-frames review. Its empirical grid remains its sole
registered selector; any EVT fit is retrospective diagnostic context only.

## Validation

Five focused effective-rank tests now cover checksum and canonical identity,
raw/deflated spectra, degenerate deflation, deterministic same-pool controls,
nested tail/event disclosure and fail-closed rank/artifact mismatches. Combined
with the active-usage and G1 suites, 17 tests pass. The analyzer reads no
realized outcome column and has not been run on a scientific panel.

