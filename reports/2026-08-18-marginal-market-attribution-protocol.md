# Marginal-vs-dependence attribution audit — protocol (S4, DRAFT for operator freeze)

**Protocol ID:** `20260818-marginal-market-attribution-v1`
**Status:** DRAFT — operator approved the S4 direction (2026-08-18
decision a: q95/q99 descriptive until the instrument validates there);
this document is the freeze once the SHA-256 is pinned.
**Class:** outcome-aware diagnostic; no fit, no tuning, no gate.

## Question

The 210+ book tail is under-predicted while ordinary players' marginal
q90 appears too WIDE (TabPFN walk-forward exceedance 7.37% vs nominal
10%). Wide marginals + thin book tail indicts dependence by inference.
This audit pins the attribution: are the production shaped marginals'
upper tails right, per position and breakout state, judged against the
market's alt-ladder implied quantiles and realized outcomes?

## Frozen design (implemented, offline-tested)

`analysis/marginal_market_attribution.attribution_report`:

- **Population:** player-weeks on the 2023–25 corpus slates that have
  BOTH an archived player-by-world draw row and an alt-yardage ladder
  under the honest pre-lock snapshot rule (the repaired shared-lock
  filtering — post-lock lines for late games are excluded). Common
  support is a law: model and market are compared on identical rows.
- **Model quantiles:** q90/q95/q99 of the archived draw row — exactly
  the marginal the selector saw (`model_quantiles_from_draws`).
- **Market quantiles:** de-vigged implied quantiles from
  `inference/market_implied.py` (validated calibrated at q90, Addendum
  45; q95/q99 carried as DESCRIPTIVE, flagged per-block in the report).
- **Statistics per stratum** (overall, by position, by breakout state;
  strata under 25 rows suppressed): exceedance of realized actuals
  against each quantile vs nominal, pinball loss for model and market,
  and their difference.

## Interpretation rules (frozen before any number)

- If model upper tails verify (exceedance ≈ nominal, pinball ≈ market)
  while the book tail stays thin: dependence is CONFIRMED as the
  deficit; marginal work stays closed; the D-lane/S2/dependence
  scorecard order stands.
- If specific strata fail two-sided (e.g. ordinary veterans wide,
  fast-role/vacancy narrow): that licenses drafting ONE targeted,
  stratum-specific marginal protocol — never the rejected generic
  widening, and never a change adopted from this audit itself.
- Distinct from and does not reopen the CLOSED player-level market-tail
  feature gate: the market curve is the instrument here; nothing feeds a
  model, candidate, or selector.

## Execution

One run per frozen protocol version: extract prop ladders (BQ) and
archived draw rows (GCS artifacts), assemble the common-support panel,
call the pure module, write create-only JSON with its SHA-256. Light
compute; design lane; no heavy slot.
