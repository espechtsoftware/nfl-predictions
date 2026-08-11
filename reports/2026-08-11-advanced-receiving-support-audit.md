# Advanced Receiving support-window audit

Completed 2026-08-11 CDT without reading a target-week outcome, selected
lineup, score, placement or ROI field. The machine report is
`reports/fantasy-points-support-runs/20260811-advanced-receiving-support-v1/support_audit.json`.

## Source integrity

- Final run:
  `20260811T155845Z__same-season-advanced-receiving-support-windows-v1`.
- Frozen plan hash:
  `58199c502ef5c1a1d154b725fc81ce0e7229b36f86543a13527289f781783477`.
- 108/108 immutable exports passed; 52 were re-hashed and reused after the
  first browser run timed out on export 53. The clean recovery manifest has
  zero failures and records the prior run id.
- The files contain 34,227 normalized receiver-window rows: 33,432 resolved,
  795 unresolved, zero ambiguous and ten split duplicates suppressed.
- All source rows are WR or TE. This vendor surface does not contain RBs, so
  RB target rows are not counted as missing support.
- The normalized collection is durable in create-only private table
  `nfl_raw.fantasy_points_advanced_receiving_windows` with 34,227 rows. A
  repeated guarded write returned `already-identical`, and backup snapshot
  `nfl_backups.fantasy_points_advanced_receiving_windows_20260811` has the
  same row count.

## Support result

Rates below use the full eligible Sunday-main target player universe as the
denominator, not only players returned by the vendor.

| window | position | vendor match | >=20 routes | >=40 routes | >=80 routes |
|---|---|---:|---:|---:|---:|
| cumulative prior | WR | 66.57% | 53.03% | 46.70% | 38.34% |
| cumulative prior | TE | 65.58% | 48.92% | 39.48% | 27.92% |
| last four prior | WR | 58.28% | 41.89% | 34.12% | 20.54% |
| last four prior | TE | 58.72% | 35.64% | 22.93% | 10.42% |

Cumulative >=40-route coverage was stable by season at 43.3%--44.6%; last-four
coverage was 28.6%--31.1%. Cumulative support rises naturally from 30.1% at
target Week 5 to 53.0% at Week 18 at the 40-route floor. Last-four support is
nearly flat, which confirms the outside review's claim that a last-four-only
policy imposes an avoidable support ceiling.

Across 14,987 resolved cumulative/last-four player pairs, weighted window-level
Spearman agreement was 0.77 TPRR, 0.79 aDOT, 0.86 air-yard share, 0.76 YPRR,
0.93 first-read rate and 0.78 XFP per route. Last four is therefore not a
duplicate snapshot, but first-read rate changes much less than the efficiency
metrics.

## Outcome-blind redundancy result

The maximum absolute Spearman correlation with the existing strictly prior
predictor panel, pooled with season weights, was:

| metric | cumulative | last four | closest existing feature |
|---|---:|---:|---|
| TPRR | 0.586 | 0.535 | XFP l4 |
| YPRR | 0.524 | 0.452 | XFP l4 / target share l4 |
| XFP per route | 0.604 | 0.634 | XFP l4 / target share l4 |
| aDOT | 0.886 | 0.735 | aDOT l8 |
| air-yard share | 0.914 | 0.927 | air-yard share l4 |
| first-read rate | 0.928 | 0.961 | target share or WOPR l4 |

TPRR, YPRR and XFP per route are the only stable, materially nonduplicate
three-field block. aDOT, air-yard share and first-read rate are closed by this
outcome-blind screen; they may not be restored after outcomes are viewed.

## Disposition

Support is adequate for one compact WR/TE historical diagnostic, provided it
uses cumulative support and a fixed last-four shrinkage blend rather than a
last-four-only eligibility gate. This finding licenses only the separately
frozen diagnostic protocol. It does not license a lineup arm or production
change.
