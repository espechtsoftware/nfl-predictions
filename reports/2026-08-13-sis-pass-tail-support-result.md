# SIS pass-tail existing-table support result

Date: 2026-08-13. This was an outcome-free prerequisite audit. It read no
player fantasy outcome, candidate score or lineup score.

## Result

The three-field pass-tail bundle has sufficient source support and is not a
duplicate of the existing served defense context. It may proceed to the
separately frozen marginal-cache protocol; this is not evidence that the model
or lineup score improves.

- strict prior: last four completed same-season games, minimum two;
- target population: active QB/WR/TE rows on terminal panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`;
- eligible rows: `11,435`;
- supported rows: `10,018` (`87.6082%`);
- support by position: QB `1,343`, WR `5,348`, TE `3,327`;
- support by season: 2023 `3,373`, 2024 `3,310`, 2025 `3,335`;
- distinct supported opponent team-weeks: `1,046`.

Outcome-free correlations against existing context:

| Comparison | r |
|---|---:|
| SIS pass-defense Boom% vs existing pass-defense EPA | `+0.59938` |
| SIS pass-defense Bust% vs existing pass-defense EPA | `-0.56054` |
| SIS pass-rush pressure vs existing pressure | `+0.41030` |
| SIS Boom% vs SIS Bust% | `-0.11521` |

Pressure is at least as distinct as the earlier audit indicated, and
Boom%/Bust% are neither redundant with one another nor near-clones of existing
EPA. The next test must still be a marginal-channel cache comparison with
tail-specific proper scores; do not infer predictive direction from this
support/redundancy result.

Reproduction:

```bash
source .venv/bin/activate
nfl-dfs sis-pass-tail-support-audit
```
