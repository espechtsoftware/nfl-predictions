# Portfolio effective-rank v2 result

Date: 2026-08-13

## Disposition

The repaired composite-scope diagnostic is valid and complete. It is
descriptive only: it neither changes the accepted portfolio nor records a
scoring improvement.

The terminal 80-lineup selector produces materially broader simulator-implied
diversity and tail coverage than either same-pool top-simulated-mean selection
or deterministic random 80-entry books. It nevertheless does not behave like
80 independent bets. After removing the leading common principal component,
its correlation participation ratio averages **20.40** (median **20.37**) over
107 slates. The corresponding raw correlation participation ratio averages
**11.87**.

Because the incumbent simulator still under-models measured QB-receiver upper-
tail dependence, these are likely optimistic effective-rank descriptions, not
formal bounds or real-world independent-bet counts.

## Immutable execution

- Protocol: `reports/2026-08-13-portfolio-effective-rank-protocol.md`
- Scope repair: `reports/2026-08-13-portfolio-effective-rank-v2-scope-repair.md`
- Cloud Build: `399e8bb1-5117-43c3-ae38-af6420a1a8c4`
- Image digest:
  `sha256:450f22cbdae94e23c8322330fe3f445d256cd82dbfc96ca086593a0f80eee90e`
- Analysis code identity: `f4ccbcf`
- Cloud Run execution: `portfolio-effective-rank-v2-pbxps`
- Historical panel (2019/2021/2022):
  `20260811-pitclean-e80-k1-role12union-a12ab31`
- Evaluation panel (2023/2024/2025):
  `20260812-pitclean-e80-selected-tabpfn-active-v2`
- Source: promoted; 107 slates; 80 entries; 10,000 worlds per slate
- Realized outcomes read: no

The strict harvester accepted exactly 107 unique season-week slates, the exact
season-to-panel map, all transport checksums, all seven tail lines, nested
20/40/80 books, and both frozen same-world controls.

## Effective rank

Cross-slate summaries for the selected nested books:

| Entries | Raw correlation PR, mean | First-PC-deflated correlation PR, mean | Deflated entropy rank, mean |
|---:|---:|---:|---:|
| 20 | 9.61 | 11.94 | 14.45 |
| 40 | 12.24 | 17.19 | 23.20 |
| 80 | 11.87 | 20.40 | 31.34 |

The 80-entry raw participation ratio falling slightly below the 40-entry value
while its deflated ratio rises is evidence of a strong common slate factor.
Adding entries broadens conditional directions after that common factor is
removed, but the common component grows enough to suppress the raw ratio.

For the 80-entry books, the mean first-PC-deflated correlation participation
ratio is **20.40**, versus **13.66** for the mean of 20 deterministic random
books and **11.48** for the top-80-by-simulated-mean control. These controls are
in-sample and use the same worlds; they isolate selector structure rather than
provide an out-of-sample validation.

## Simulator-implied tail coverage

Mean fraction of worlds with at least one lineup over each score line:

| Line | Selected 20 | Selected 40 | Selected 80 | Random 80 mean | Top-mean 80 | Selected 80 minus random |
|---:|---:|---:|---:|---:|---:|---:|
| 187 | 18.76% | 24.68% | 29.37% | 19.39% | 21.56% | +9.99 pp |
| 194 | 12.51% | 16.75% | 20.25% | 12.40% | 14.27% | +7.85 pp |
| 200 | 8.28% | 11.21% | 13.67% | 8.15% | 9.68% | +5.52 pp |
| 210 | 3.93% | 5.40% | 6.68% | 3.79% | 4.71% | +2.90 pp |
| 220 | 1.74% | 2.41% | 3.05% | 1.64% | 2.11% | +1.41 pp |
| 230 | 0.75% | 1.06% | 1.38% | 0.69% | 0.91% | +0.70 pp |
| 240 | 0.33% | 0.49% | 0.67% | 0.31% | 0.39% | +0.37 pp |

The selector is therefore doing useful portfolio work within the simulator:
it improves both conditional diversity and modeled tail coverage rather than
merely selecting 80 high-mean variations of the same construction.

## Interpretation and next action

This result argues against replacing the coverage selector with simple top-
mean ranking. It also explains why 80 lineups do not yield anything close to
an 80-fold independent chance at a top result: the entries share a strong
slate factor and substantial residual dependence.

No realized score or ROI inference is permitted from this diagnostic. Continue
with mechanisms that can improve the underlying joint tail—next, the already-
queued score-free team TD-ledger evaluation—rather than further mining the
selector on known outcomes.

