# WR/defense coverage inventory reconciliation

Date: 2026-08-13. This reconciles the operator-supplied
`reports/2026-08-13-wr-defense-coverage-test-inventory.md` without modifying
that source review.

## Accepted findings

The three Fantasy Points WR/TE shell-fit conclusions and their numbers match
the immutable experiment records. The prior-season player gate was a tiny
pass, its licensed exact-80 union changed 33 slots but tied every weekly
maximum and threshold, and the last-four mechanism failed support while
worsening aggregate 30-point Brier. Those exact receiver-shell mechanisms are
closed. The current WR Coverage Matchup sample is schedule-stale and contains
no cornerback identities, so it remains schema-only.

The live-feature audit also checks out. `featureset.NUMERIC_FEATURES` includes
`cb_ypt_allowed_l6`, `cb_comp_rate_allowed_l6`, `db_ypt_allowed_l6`, and
`top_cb_out`; the current active-only TabPFN cache reports all four in its
feature contract. Repository experiment records contain no isolated ablation
of either the three PFR secondary-quality rates or `top_cb_out`. Leakage and
join validation prove that the fields are point-in-time safe, not that they
improve forecasts or lineups.

## Scope corrections

The Fantasy Points failures do not directly answer either adjacent question:

- PFR secondary quality and cornerback availability are opponent-strength and
  availability inputs, not receiver-skill-by-shell interactions; and
- the receiver effect-size arithmetic does not close a QB offense-by-defense
  shell-fit hypothesis. The newly frozen QB protocol therefore remains a
  distinct, lower-prior test rather than a retry of the WR feature subset.

## Queue consequence

Before the final forensic closure, freeze a current-stack feature ablation that
tests the three PFR rate fields as one block and `top_cb_out` as a separate
availability block. The protocol must predeclare the conditional combined-drop
branch before any treatment metric, retrain every affected mean/marginal model
under the terminal active-only law, require a score-free player-tail gate
before any exact-80 comparison, and disclose that the hypothesis arose after
adjacent coverage results were known. Do not simply remove the live fields from
the feature list based on this audit.

If operational constraints leave that arm unfinished, the final exhaustion
certificate must label it explicitly deferred with a prospective 2026 shadow
and falsifier; it may not disappear into a generic data census.
