# Production independent review — PREREG-054 / experiment 085

Date: 2026-09-03  
Lab evidence commit: `8b00020a4a7c7e026ce664a042d06624f5f6e364`  
Disposition: **independently reproduced; P_MIX is conditionally recommended for Week 1**

## Bottom line

The participation-mixture arm (`P_MIX`) is the strongest actionable selection result in the current historical program. It improves the predeclared winner-CDF proxy, increases the historical mean weekly K80 maximum by 1.399 points, and materially reduces selection of lineups containing players later recorded inactive. Production recommends using `P_MIX` on the adopted `D800_DEMAX` supply for Week 1 if, and only if, the live designation feed passes the point-in-time certification below.

`P_ELIG` also passes the registered proxy and contamination boundaries, but it is dominated by `P_MIX` on the principal efficacy summaries. It should remain a diagnostic/shadow comparator rather than replace `P_MIX`.

This is not an extreme-tail breakthrough. In the historical panel, `P_MIX` increased weeks at or above 200 from 9 to 12, but did not improve the number of weeks at or above 220 or 230. It is best understood as a meaningful selection-quality, mid-tail, and integrity improvement.

## Independent reproduction

Production ran the repaired reader directly from the lab evidence commit:

```text
.venv/bin/python scripts/prereg054_report.py \
  085b640r1-20260903T175658Z \
  085b641r1-20260903T175939Z \
  085b642r1-20260903T183705Z
```

The reader exited zero and reproduced the lab result. Reader SHA-256:
`6bfc7d34a268fcd1a76e4a4053d826e5dc9b724211c114fe641b342b8ef658a0`.

Key results:

| Measure | P_CTRL | P_MIX | P_ELIG |
|---|---:|---:|---:|
| Mean weekly K80 max | 180.550 | 181.950 | 181.291 |
| Raw delta vs control | — | +1.399 `[-0.107, +2.906]` | +0.741 `[+0.044, +1.485]` |
| Winner-CDF proxy delta | — | +0.00552 | +0.00162 |
| Family interval | — | `[+0.00022, +0.01261]` | `[+0.00020, +0.00296]` |
| Proxy verdict | — | PASS | PASS |
| Weeks >=200 | 9 | 12 | 10 |
| Weeks >=210 | 3 | 3 | 3 |
| Weeks >=220 | 1 | 0 | 0 |
| Weeks >=230 | 0 | 0 | 0 |
| Selected-roster inactive contamination | 21.53% | 16.25% | 16.24% |

For `P_MIX`, all three bank means and all four leave-one-season-out estimates are positive; the paired sign-flip p-value is 0.0092. Its raw-score interval still crosses zero, so the correct statement is that the registered proxy passed and the raw-score diagnostic is positive but not independently conclusive.

The reader found belief changes on 162 `P_MIX` slates and 182 `P_ELIG` slates out of 216, ruling out a cohort-wide dead lever. Candidate Jaccard is 1.0 across arms, confirming this was a judgment/selection test on common generated supply rather than a generation comparison.

## Co-sign on the validation repair

Production co-signs the substance of the pre-open reader repair. `sim_mean` and `sim_q99` are arm-specific beliefs altered by the treatment. Including them in the shared-candidate signature incorrectly required the treatment not to act. Removing those two fields while continuing to bind candidate index, tags, roster hash, salary, ledger, mixture, settlement, retained count, and candidate Jaccard correctly separates shared generation identity from treatment-specific judgment.

The repair was limited to the reader after its first attempt failed closed and before any result was printed. The immutable execution source, image, runner, arms, endpoints, thresholds, and artifacts were not changed. On that evidence, the repair does not invalidate the read.

Two non-blocking evidence-package repairs remain:

1. The new section is labeled `Amendment 2`, duplicating the existing Amendment 2; it should be renumbered Amendment 4.
2. The preregistration prose says beliefs must differ “exactly when” receipt cause exists, but the implementation intentionally proves only that a belief change cannot occur without receipt cause. The converse is allowed when designated players occur in zero candidates. The prose should state the implemented one-directional guarantee plus the cohort-vacuity guard.

For future/reentrant use, the module-global engagement counters should also be reset at reader entry. This has no bearing on this one-process CLI reproduction.

## Week-1 live-feed certification

Before `P_MIX` can control entered selections, production should require one candidate-only rehearsal proving all of the following:

1. The raw injury/designation snapshot has a provider timestamp and ingestion timestamp no later than the declared build cutoff.
2. Raw `injury_status` and `practice_level` values are retained with a content hash and immutable as-of receipt.
3. Player identity mapping, designation normalization, participation-map version, and source artifact SHA are recorded in the build receipt.
4. Missing, stale, ambiguous, or unmapped designations follow an explicit fail-closed/fallback policy; no later snapshot silently overwrites the bound input.
5. Replaying the frozen snapshot produces identical player probabilities, selected roster hashes, and exact K for every contest prefix.
6. The control and `P_MIX` books are generated from the same frozen D800 candidate supply, and their separate roster hashes are retained for settlement.

If that rehearsal passes, the production recommendation is:

- Enter the A5 allocation using the `P_MIX`-selected nested book.
- Emit and freeze the corresponding `P_CTRL` nested book as the primary prospective shadow comparator.
- Retain `P_ELIG` only as an optional diagnostic shadow; do not spend entered allocation on it merely because it also passed historically.
- Settle all books against identical contest outcomes and report realized maxima, thresholds, contamination, duplication/rank, and exact roster-level swaps.

If the timestamped input contract cannot be certified before the entry build, keep `P_MIX` shadow-only and use the adopted control selection for paid entries. The historical result must not justify silently using post-lock status knowledge.

## What this changes next

This result closes a concrete selection weakness: the incumbent treated questionable/doubtful participants as certain to play, and 21.5% of its selected historical rosters contained at least one player later inactive. It supports adding participation uncertainty to the judge now. It does not close the separate generation and extreme-tail gaps exposed by the knowledge graph, so the queued phenotype/admission/direct-generation work remains necessary.
