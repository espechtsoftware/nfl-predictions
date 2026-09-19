# Availability semantics in this weekend's forecast law

The main component models and the current TabPFN cache use different training populations. It is therefore incorrect to describe the complete served law as fully conditional on playing, or to claim that a participation mixture cannot count availability twice. This qualifies the interpretation of the participation experiment; it does not change its measured conditional comparison or authorize a new cache/model deployment.

## What the code establishes

| Path | Actual behavior | Consequence |
|---|---|---|
| Baseline and component model fitting | [`active_training_rows`](../src/nfl_dfs/models/featureset.py) excludes rows whose `was_active` flag is false when that provenance column exists. | These fits use played outcomes. This statement alone does not characterize the final transformed simulation law. |
| Current TabPFN generation | The released strict-prior generator filters position, prior season/week and non-null `y_dk_points`; it does not apply the active-row filter. | Synthetic inactive zero labels enter its eligible training context. The overnight execution receipt reports103,790source rows:78,831active and24,959inactive, before context subsampling. |
| Score-label construction | [`013_player_week_actuals.sql`](../sql/features/013_player_week_actuals.sql) fills missing stat lines for salary-listed players on played slates with zero labels. [`021_player_week_training.sql`](../sql/features/021_player_week_training.sql) joins those labels. | NULL usage shares for inactive players do **not** imply NULL DK score labels. |
| Actual lab incumbent consumer | On source `2dc116c`, `src/nfl2/pipeline.py:138–143` maps draws through the cached TabPFN quantiles and position scaling; lines160–175then recenter skill rows on the served mean. | This is a sequence of transformations, not simply a weighted mixture of two complete marginal distributions. Inactive training labels can affect shape; their count does not establish the final mean or zero-mass effect for a particular player. |
| Explicit current availability adjustment | [`cascade_adjust.py`](../src/nfl_dfs/inference/cascade_adjust.py) recognizes DK Out/IR and injury-report Out. [`run_projections.py`](../src/nfl_dfs/inference/run_projections.py) zeros those projections after blending. Own Q/D designation and practice level are absent from the default model feature list. | There is no explicit default Q/D participation probability at this step. That does not rule out availability information implicit in history, the TabPFN transformation or market forecasts. |

The released TabPFN source identity is `fb875dd3`, generator SHA256 `96eadcd3ee2d4b7aa846c0f15c519eed2ac1d852fdd80e53e0cd40757b8eca04`, image digest `fdb120dc2291b7d09538987d97e8b30d0e8fe5f7e9d9d40995b6adcc4d4692d6`. The [actual overnight cache receipt](reviews/evidence/2026-09-19-release-cache-validation.json) binds the training-population counts to the completed execution. The morning refresh uses the same image and label rule.

The cascade comment claiming depressed practice features already carry the Doubtful signal is not evidence of a current practice-to-model path. Default feature lists exclude own practice, and usage rollups use strictly earlier weeks. Earlier injuries may affect prior usage; that is a different, indirect channel.

## Existing research and the appropriate next comparison

The [repaired August12 active-label result](2026-08-12-pit-clean-active-label-exact80-result.md) selected an active-only research cache in its historical chain:220counts were equal and the first registered difference favored treatment at210. Its [usage revalidation](2026-08-12-active-label-usage-revalidation-result.md) retained the associated finite-K law. This is existing evidence, not a new discovery this morning. That selected research artifact and today's live generator are different identities; historical acceptance does not establish current-week coverage or a completed live transfer.

Trace that disposition before proposing a deployment change. If a new mechanism experiment is warranted, freeze a small2×2comparison of label law (current/active-only) and participation (off/on), with identical inputs, candidates, objective and separate audit worlds. Changing both factors together cannot identify which helped. Any new historical evaluation must respect previously used evidence and the outcome firewall.

For this weekend, retain the frozen same-cache participation comparison and its double-counting/calibration limitation. Recheck it on the completed operating corpus and refreshed forecast inputs. Fresh confirmed-out reselection and the fixed first-entry promotion remain separate recommendations; no new model or cache switch follows from this source review.

## Fresh injury data is now joined correctly

The10:03:45UTC capture contains246unique players and99Out/Q/D designations. Before the morning feature rebuild,23designated players matched the inference population but none had a designation in that input field. After `build-features-cx2px`, the full captured population has zero missing injury rows, zero status mismatches and zero capture-timestamp mismatches; all23matched designations are now present in inference.

The [before receipt](reviews/evidence/2026-09-19-morning-injury-join-before.json), [after receipt](reviews/evidence/2026-09-19-morning-injury-join-after.json) and [read-only checker](reviews/evidence/2026-09-19-morning-injury-join-check.py) preserve the evidence. This establishes input propagation, not a new score gain. Cache/projection completion and the final CLI proof were still pending when this source review was written.

The workstation's initial broad conditional-on-playing conclusion was corrected in handoffs `fdca786` and `8b77f81`; the laptop supplied deployed-source/receipt evidence in `2775987` and the exact lab-consumer qualification in `bc84774`. Both sides retain the narrower conclusion.
