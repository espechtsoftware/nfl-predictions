# G1 walk-forward archetype topology result

The sole valid frozen G1 result is **`stable-qb-hub-confirmed`** and licenses
G2 for the finite-K terminal book. Execution
`g1-archetype-topology-v3-gq47v` completed cleanly from source `64e0428` and
immutable image digest
`sha256:72002d1b1c49783e9eda5d0b60314c3a84cfde7ea749968eae520d5eeb205a5e`.
Every terminal identity, exact G0 reproduction, cache-coverage and
mean-preservation invariant passed.

## Stable QB hub

The broad held-out relationship evidence is strong and consistent:

| relationship | pairs | source booms | realized lift | simulated lift | log(sim/real) | slate-bootstrap 95% interval |
|---|---:|---:|---:|---:|---:|---:|
| QB -> WR | 2,982 | 339 | 3.323 | 1.064 | -1.138 | [-1.357, -0.939] |
| QB -> TE | 1,129 | 127 | 2.371 | 1.079 | -0.787 | [-1.107, -0.400] |

QB-WR is a material underprediction in every held-out season:

| season | realized | simulated | log(sim/real) | classification |
|---:|---:|---:|---:|---|
| 2023 | 3.419 | 1.092 | -1.142 | material miss |
| 2024 | 3.027 | 1.084 | -1.027 | material miss |
| 2025 | 3.640 | 1.087 | -1.208 | material miss |

QB-TE points in the same direction in all three seasons. It is material in
2023 (`2.153` realized vs `1.146` simulated) and 2025 (`3.190` vs `1.132`),
and inconclusive but still underpredicted in 2024 (`1.948` vs `1.136`).

The archetype-edge requirement also passes. Seven supported QB-WR cells are
material underpredictions, spanning history-short and stable QB/WR types. The
supported `QB-tier2-stable -> TE-tier1-stable` cell is also material:
`7.647` realized lift versus `1.282` simulated, with log-gap interval
`[-3.048, -0.499]`. Thin unsupported cells remain visible but do not count.

## What G1 does not support

- QB-RB, WR-WR, RB-RB and the broad opponent relationships are inconclusive;
  TE-TE is unsupported.
- All three preregistered cross-game controls are inconclusive. G1 therefore
  does **not** license a slate-wide latent factor; any eventual cross-game use
  remains routed to a winning-line model rather than stack dependence.
- The positive-lift graph is descriptively different: realized-versus-simulated
  relative Frobenius distance is `0.8838`, normalized-Laplacian eigenvalue L1
  distance is `0.0920`, and four-cluster adjusted Rand agreement is `0.4949`.
  These confirm structural mismatch but do not enter the G2 gate.

## Population and point-in-time validity

G1 used the exact G0 population of 7,848 supported rows across 54 held-out
2023--2025 slates and 34,038 registered directed pairs. Walk-forward labels
used only strictly prior active games. The immutable label artifact contains
1,072 target-season player labels; history-short fallbacks decline from 724
rows in 2023 to 556 in 2024 and 512 in 2025 as prior evidence accumulates.
The full machine report and checksummed label artifact are under
`reports/g1-topology-runs/20260812-g1-archetype-topology-v3/`.

## Consequence and sequencing

The frozen G2 upper-tail QB bi-factor mechanism is scientifically licensed for
this finite-K terminal identity. G2 must not yet launch. The subsequently
identified active-only fitted-K standing-law revalidation is currently running:

- if finite K remains selected, G2 may be frozen and developed directly from
  this valid G1 target scorecard;
- if multinomial is selected, the terminal dependence law has changed and G0
  and G1 must be rerun under multinomial before any production-eligible G2.

The v1 execution remains invalid before G1 metrics because of ambiguous QB
team-weeks. V2 completed computation but its single log entry was truncated at
Cloud Logging's 102,400-byte boundary, leaving no complete result or license.
V3 changed only checksummed report transport and is the sole valid result.
