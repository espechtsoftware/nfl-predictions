# The "column-order luck" in the feature study is ordinary seed noise, and the floor was under-measured

Following `8a681096`: *"reordering the identical feature set moves mean MAE by up to 0.0052, three
times the seed floor, and a third of pure reorderings would read as harmful."* Four verdicts were
withdrawn on that basis, correctly. This explains the mechanism and what it means for the next
feature test.

## Mechanism

Both the study (`colsample_bytree=0.8`, fixed `random_state`) and the production component models
(`models/components.py`: `feature_fraction=0.8`, `feature_fraction_seed = 9100 + k`) pick 80% of
features per tree **by column index** from a fixed seed. Permuting the columns — or dropping one
feature, which shifts every later index — changes which features every tree sees. That is a
reseed of feature sampling, not a property of the order itself.

## Measured

`player_week_training`, active rows, train 2019–2022 (26,502), test 2023 (7,043), 36 features,
the study's own hyperparameters, 10 draws each:

| design | MAE range | MAE sd |
|---|---:|---:|
| **A** vary seed, fixed order, colsample 0.8 | 0.0191 | **0.0057** |
| **B** fixed seed, permute order, colsample 0.8 | 0.0215 | **0.0066** |
| **C** fixed seed, permute order, **colsample 1.0** | 0.0075 | **0.0030** |

**B ≈ A.** Reordering produces the same spread as changing the seed; there is no separate
column-order effect. **C halves it**, confirming feature subsampling as the main channel; the
remaining 0.003 is row bagging (`subsample=0.8`) and split tie-breaking.

## Why it read as "three times the floor"

The floor came from **3 seeds**. For a normal spread, the expected range of 3 draws is about
1.7 sd, while a maximum over many drop and reorder runs reaches 3 sd and beyond. Comparing a maximum
over many runs to a range over three will reliably come out around "3×". A floor measured with
10+ seeds would have contained the reorder spread.

## What this means for the next feature test

For the proposed `practice_level` experiment (`c137ed0b`), and any single-feature adoption test:

1. **Measure the floor with ≥10 seeds**, varying `feature_fraction_seed` / `random_state`, and
   compare *means over seeds*, not single fits.
2. **Or run ablations with `colsample_bytree` / `feature_fraction` = 1.0**, which halves the
   noise at the cost of matching production less exactly.
3. In production the fixed `feature_fraction_seed` per ensemble member means **adding any
   feature reshuffles every member's sampling.** The ensemble averages across members, which is
   the protection; a test on a single member would not have it.

**The study's positive findings stand.** `qb_cpoe_l6` at +0.042 in seven seasons of seven is
several times this noise and does not need re-examining; the withdrawn "harmful" verdicts were
correctly withdrawn, and this is why.
