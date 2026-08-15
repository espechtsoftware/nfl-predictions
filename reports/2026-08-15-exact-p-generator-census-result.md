# Corrected exact-P generator census result

Date: 2026-08-15  
Protocol: `20260815-exact-p-generator-constraint-census-v1`  
Evidence class: score-free identity/structure diagnosis; no production change

## Immutable execution

- Cloud Run execution:
  `exact-p-generator-constraint-census-v1-pgtfb`
- Analysis code:
  `3ee4231b72c4b9ad6920972c9560885470a01bfd`
- Analysis image:
  `sha256:b0ba7c4479883a31b89bb69720e9494cf5c18e1086c78f3d0fbd0895c9347027`
- Corrected exact-P source generation:
  `1786831245271593`
- Corrected exact-P source SHA-256:
  `ff456093841266cba1b0293dd56b0e2d5089588a61518568706900617eff6ad1`
- Strict report SHA-256:
  `579be07b8ebdf223446430d5dfe626362ecf27e5e7f12f24c20bc07f4c8826ec`

The mandated 2023 preflight passed before the full execution. The full report
contains no candidate or lineup score and cannot authorize a historical arm or
production change.

## Result

The frozen disposition is **`native-generation-search-dominant`**.

| loss stage | slates |
|---|---:|
| exact P absent from the complete five-seed native union | 54 |
| exact P generated but removed by fixed-budget CBWU admission | 0 |
| invalid retained reconstruction | 0 |

This is unusually clear: canonical CBWU admission is not what removes the
corrected P roster. The exact nine-player combination was never created in any
of R0--R4 on any of the 54 slates.

At the same time, all nine exact-P players appear somewhere in the native
candidate union on every slate. There are zero wholly absent P player slots.
Only 24 of 486 P slots are thin (fewer than five native appearances), spanning
20 slates. The dominant failure is therefore **combination assembly/search**,
not broad player eligibility.

The complete native union contains 500--801 distinct candidates per slate
(mean 579.80), while canonical retained CBWU contains 241--265 (mean 253.81).
Even across that larger union, the closest native roster remains a median five
player swaps from exact P:

| minimum swaps to P | slates |
|---:|---:|
| 1 | 1 |
| 3 | 2 |
| 4 | 14 |
| 5 | 28 |
| 6 | 9 |

Mean minimum distance is 4.76 swaps. The only one-swap slate is 2025 Week 6,
where the nearest roster appears in the leverage family in R0, R3 and R4.

The frozen family-materiality rule identifies no single structurally excluded
family. Leverage, boom and EPI are statically eligible on all 54 slates; QB
variance is eligible on 28; game and dark are each eligible on five. Their
primary budget shares are 63.07%, 15.77%, 4.73%, 9.93%, 3.94% and 2.56%,
respectively.

## Consequences

1. Prioritize mechanisms that construct genuinely new player combinations.
   This directly supports ATLAS and later stack-core/search work over another
   canonical admission-only variation.
2. CBWU-OI remains worth the separately frozen construction diagnostic: it may
   improve the best retained native candidate, but it cannot literally recover
   exact P because P is absent from its complete native discovery union.
3. Do not conclude that every breadth mechanism is irrelevant. This census
   diagnoses the current six-family, five-seed generator only.
4. Do not change production from this score-free result. Production remains
   `classic-k1-role12-boom40-poscal-cbwu-v4`.

