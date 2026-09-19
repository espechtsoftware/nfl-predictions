# Participation reselection now checks the actual decision clock

The latest optional research adapter is [version 3](reviews/evidence/2026-09-19-participation-reselect-v3.py). It preserves the same fixed map, masks and ordinary/full selection algorithm, while adding an explicit clean-runtime check and checking availability rules at the actual selection and output times. The ordinary DK-confirmed-out adapter already has the corresponding runtime and final freshness checks.

The preceding version2 validated source age at use but evaluated the 90-minute official-announcement boundary at the capture cutoff. A capture taken before that boundary could therefore allow a later selection after official announcements became due. Version3 checks the real clock immediately before participation selection and again before writing output. It also reopens the entire authenticated source at output, so source aging or first lock during computation causes refusal. It still refuses supplied official-confirmation files because actual official game-day acquisition/verification has not been implemented.

The adapter now accepts `--lab-checkout` and requires the exact clean source `2dc116ce95647a776ba9c36cf194f44d022d03a4`, including no untracked files and verification that the imported package came from that checkout. Failed identity reads do not count as a clean source. This makes the same reviewed code usable with the workstation's actual checkout path.

**Validation:** 38 focused selector/provider tests pass, including a capture made before the announcement window being refused when used at the boundary, dirty/wrong runtime and failed Git-status observations. A new real provider capture and complete D1600/K97 rehearsal reproduce the prior ordinary indices, full indices, probability records and exclusions exactly. Both books remain legal. [New capture](reviews/evidence/2026-09-19-participation-provider-v3-capture.json), [new rehearsal](reviews/evidence/2026-09-19-participation-provider-reselection-v3.json).

This repairs an operational guard, not a scoring model or the preceding frozen numerical experiments. Those experiments remain as-of comparisons under their original identities. Version3 emits a separate research preview only; no entry upload or delivery adoption occurs.

From the production checkout, with its environment and single-thread numerical settings:

```bash
python reports/reviews/evidence/2026-09-19-participation-provider-capture.py /new/status-capture
python -X cpu_count=1 reports/reviews/evidence/2026-09-19-participation-reselect-v3.py \
  --lab-checkout /clean/lab-checkout-at-2dc116c \
  --run /completed/ordinary-run-with-both-a5-sidecars \
  --status-dir /new/status-capture \
  --map /authenticated/participation-map.json \
  --output /new/participation-preview
```

Set `GCP_PROJECT=nfl-predictions-503414`; the map must match the fixed SHA256 in the adapter. Fresh sources and the actual completed corpus are required each time. Once any relevant Q/D player's official active/inactive announcement is due, this adapter refuses rather than carrying forward the prior. The [ordinary DK-confirmed-out reselector](2026-09-19-prelock-dk-reselection-review.md) remains a separate prelock option; it does not need to infer that Q/D players are officially active.
