# Paid-source role and coverage gate: first result

**Protocol:** `2026-09-20-paid-source-role-coverage-protocol.md`  
**Execution:** `scripts/run_role_coverage_gate.py`  
**Evidence:** `reports/reviews/evidence/2026-09-20-role-coverage-gate.json`  
**Scope:** historical held-out forecast gate only; no lineup generation or production change.

## Data support

The query returned 13,634 active WR/TE player-weeks from target Weeks 5--18 in seasons 2022--2025. The source tables were available with these row counts:

| source table | rows | seasons | notes |
|---|---:|---:|---|
| Fantasy Points alignment player L4 | 16,482 | 2022--2025 | 2,305--2,419 supported rows per season |
| Fantasy Points coverage L4 | 16,482 | 2022--2025 | 1,517--1,601 supported rows per season |
| Fantasy Points route shape L4 | 16,482 | 2022--2025 | 2,322--2,403 supported rows per season |
| SIS defender coverage history | 15,477 | 2022--2025 | 15,477 player-game rows, Wide/Slot |
| SIS defense prior context | 3,324 | 2022--2025 | all target Weeks 5--18 had supported Wide/Slot context |

The SIS arm combines SIS opponent coverage rates with the player's prior alignment share. Therefore its result is a **SIS coverage × alignment mechanism**, not a pure SIS-only attribution.

## Held-out results

Each test season was evaluated once after training on earlier seasons. Lower is better.

| arm | 2024 MAE | 2024 Brier-20 | 2024 Brier-30 | 2025 MAE | 2025 Brier-20 | 2025 Brier-30 |
|---|---:|---:|---:|---:|---:|---:|
| Control + weekly Route Share | 3.8295 | 0.051519 | 0.012813 | 3.6126 | 0.043166 | 0.010555 |
| FP role/alignment/route shape | **3.7993** | 0.051582 | 0.012806 | **3.5901** | 0.043197 | 0.010676 |
| FP coverage edges | 3.8140 | 0.051709 | 0.012837 | 3.6054 | 0.043231 | 0.010578 |
| SIS coverage × alignment | 3.8409 | 0.051694 | **0.012763** | **3.5896** | 0.043360 | **0.010535** |
| Combined FP + SIS | 3.8154 | 0.051659 | 0.012800 | 3.5790 | 0.043391 | 0.010665 |

## Reading

- The FP role arm reduced MAE in both held-out seasons by about 0.03 points, but its Brier-20 moved slightly worse in both seasons and Brier-30 moved in opposite directions. This is a useful role/mean signal, not evidence for a tail-selection change.
- The FP coverage arm did not improve any primary metric consistently. This agrees with the earlier weak/unstable coverage-fit results.
- The SIS coverage × alignment arm improved Brier-30 in both held-out seasons and improved MAE in 2025, but worsened MAE in 2024 and Brier-20 in both. The absolute Brier-30 changes are small (`-0.000050` in 2024 and `-0.000020` in 2025). This is the first positive direction for a SIS coverage interaction in this gate, but it is not large enough to authorize production or a lineup shadow.
- The combined arm did not improve Brier-30 consistently. Combining all available fields is therefore not justified; source bundles need to remain separate.

## Limitations and next step

This test used fixed ridge/logistic models and walk-forward folds, but it was still a historical player forecast gate rather than a full lineup experiment. It did not test red-zone route participation because that field is not present in the archived normalized tables. It also did not isolate a defender-to-receiver assignment; the SIS component is opponent/alignment aggregate context.

The next valid step is a separately frozen **SIS player-coverage support and assignment study** using defender identity, coverage snaps, targets, yards, and Wide/Slot shares, with a pure SIS arm and a combined alignment arm. If that survives a support and proper-score gate, run a source-aware candidate/admission shadow. Do not promote the current feature bundle from this result.
