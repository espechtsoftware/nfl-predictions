# Reconciliation of post-CBWU-OI suggestions

Date: 2026-08-15 CDT. This reconciliation was written before the paired
CBWU-OI selector-stability result and without querying any new realized
lineup outcome.

## Disposition summary

| Suggestion | Disposition | Required action |
|---|---|---|
| Shared source-resolution preflight | Accept | Factor a common, cheap provenance resolver for future protocols after the currently frozen executions; do not mutate the running ATLAS image or protocol. |
| Joint OI construction/stability reading | Accept with comparator correction | Put the fixed-budget C result and paired, same-world canonical/OI stability result in one table. The paired 50,000-world canonical reconstruction is the primary comparator; historical R0 `54.28/80` is context only. |
| Expected dollars from a public payout curve | Do not implement as proposed | A payout curve maps rank to dollars, not score to rank. Exact expected dollars require contest-entry score/rank data, duplication, and tie splits. Report only evidence-supported economic context until those data exist. |
| ATLAS target band | Preserve the current frozen run; accept prospectively | The active ATLAS diagnostic is score-free and measures attainable simulated-world optima. Predeclare a shoulder-improvement prior before any later outcome-facing ATLAS candidate test, while retaining the full tail grid and existing law. |

## 1. Shared provenance preflight

The repeated source-resolution failures are a real infrastructure pattern, not
scientific evidence. Future immutable-artifact protocols should call one
shared preflight before allocating heavy compute. Its receipt must resolve and
uniquely verify:

- project, region, panel IDs and their exact ordered membership;
- source artifact URIs plus object generations/checksums;
- roster/report/manifest source paths and hashes;
- code commit, immutable image digest and protocol/report hash;
- exact expected slate, panel and artifact cardinalities;
- create-only output absence; and
- an explicit allowlist of query fields, with outcome fields rejected for
  score-free work.

The preflight must emit a small machine-readable receipt and fail before Cloud
Run launch when an identity is missing, duplicated, stale or inconsistent. A
protocol-specific semantic validation remains necessary after source
resolution; the shared helper must not pretend that all sources have the same
grain or scientific gates.

This is prospective infrastructure. The repaired ATLAS execution is already
running from a frozen, validated immutable image and must not be changed.

## 2. Joint CBWU-OI construction and stability interpretation

The completed construction diagnostic and the pending selector-stability
diagnostic answer different questions and must be shown together without
converting one into the other.

The required final table is:

| Evidence | Canonical | CBWU-OI | Paired delta |
|---|---:|---:|---:|
| Fixed-budget mean candidate maximum C | 181.07 | 186.73 | +5.66 |
| C weeks >=187 / 194 / 200 / 210 | 22 / 11 / 8 / 6 | 25 / 18 / 14 / 10 | +3 / +7 / +6 / +4 |
| C weeks >=220 / 230 / 240 | 3 / 1 / 0 | 3 / 1 / 0 | 0 / 0 / 0 |
| Paired full-world exact-80 selector stability | pending | pending | pending |
| Paired disjoint/bootstrap stability details | pending | pending | pending |

The historical `54.28/80` overlap came from a canonical R0 10,000-world
disjoint-half experiment. The new diagnostic reconstructs both candidate
pools from the same R0--R4 50,000-world source and applies identical stratified
indices. Its paired canonical result is therefore the valid comparator. The
old number may be printed as historical context, never used as the primary
gate.

No new post-result threshold for "materially worse" is permitted. Report all
absolute levels, paired deltas, uncertainty summaries and the already-frozen
descriptive high/intermediate/low labels. Stability measures reproducibility
of a score-free selection rule. It is an operational-risk indicator; it is
not a mathematical estimate of the conversion from hindsight candidate
maximum C to realized selected maximum S. An absent future S gain cannot be
explained away solely by observing lower stability.

## 3. Economic interpretation and the missing rank mapping

The concern is directionally important: improvements at 194--210 can have
economic value even when 220+ is tied. The proposed shortcut does not estimate
that value.

A published DraftKings payout curve provides `rank -> payout`. Candidate or
lineup score cannot be mapped to rank without the contest field's score
distribution. Expected or realized dollars additionally require lineup
duplication and tie splitting. CBWU-OI's reported C is the hindsight best
candidate in a generation layer, not a submitted exact-80 portfolio, making a
payout assignment to C especially invalid.

The authoritative data audit remains
`reports/2026-08-10-contest-placement-roi-audit.md`:

- historical files retain first place only, not full standings;
- only one 2025 Week 5 contest supplies a min-cash anchor;
- there is no defensible multi-season realized GPP ROI estimate; and
- 2026 must retain full standings, payout tiers, duplication and the
  operator's entry-history fees/winnings.

Until those data exist, economic reporting may include observed min-cash
crossings and conservative payout floors on slates where the exact contest
metadata is known. It must not label those values expected dollars or ROI.
The current CBWU-OI construction result cannot even support that diagnostic,
because its exact-80 realized scores were deliberately not queried.

## 4. ATLAS expectation without changing the running diagnostic

The active ATLAS stage is score-free. It tests whether slate-total ranking
misses attainable legal simulated-world optima and whether those optima add
structural diversity. A 194--210 realized-score band is therefore not an
observable output of this stage and cannot be appended after launch.

Before any later outcome-facing ATLAS MVP queries realized scores, freeze this
prior:

- primary expectation: broader new-combination search improves candidate C
  across the 194--210 shoulder on multiple slates;
- no assumed improvement at 220+;
- report every threshold from 240 downward plus mean C and season breakdowns;
- treat any 220+ gain as stronger-than-prior evidence, not a retroactively
  required result; and
- apply the standing tail-first decision law exactly as frozen. The prior is
  descriptive and does not redefine adoption.

## Consequence

The review improves execution reliability and interpretation, but it does not
license a production change. CBWU-OI remains a promising prospective
construction mechanism with a verified C gain concentrated at 194--210. Its
paired stability result is still required, and any S or money-path claim needs
a separately frozen outcome-facing test with the required field data.
