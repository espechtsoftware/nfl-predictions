# Promotion ENTER re-layout review — row check blocks all multi-contest layouts

The v1.2 consumer is independently clear, but the v2.1 runner’s new path to the entries file has a concrete defect in `relayout_enter.sh`.

The final `PYCHK` block compares each generated contest file to a contiguous slice of the promoted all-rows upload:

```python
if body != rows[pos:pos + n]: ...
pos += n
```

That assumption is false for both supported layouts:

- **Sequential:** each contest receives its keeper rows from the front and its fill rows from the remaining rows. Contest files are intentionally noncontiguous.
- **Top-per-contest:** each contest receives the upload prefix, so later contest files intentionally repeat rows already used by earlier contests.

I ran the exact shared `relayout_enter.sh` bytes (`8e08786f…`) with a synthetic five-row upload and two contests (milly 2 entries / keep 1, flea 3 / keep 1). With `ENTER_LAYOUT` unset (the script default), explicit `sequential`, and explicit `top`, all three cases exit nonzero with `staged bundle does not reproduce the upload order`; none publishes `ENTER/`. This is source-only evidence and uses no production book or outcome data.

The runner’s own stated success test used a sequential keeper/fill arrangement, which is precisely the arrangement this check rejects on a multi-contest input. Therefore the promotion runner will leave the previous ENTER bundle and publish no promoted upload until fixed.

Fix the check to reproduce the chosen layout’s expected rows, or have the layout block emit an asserted mapping manifest and validate each generated file against it. For sequential, compare each file to its computed keeper slice plus fill slice. For top, compare non-block contests to `rows[:n]` and block contests to the selected cursor slice. Keep the existing shape verifier and atomic symlink swap. Add one synthetic test for each layout with at least two contests, then rerun the real runner success/corrupt/STOP tests.

Evidence: [reproduction](reviews/evidence/2026-09-20-relayout-enter-row-check.py); its result is written beside the private fixture under `/home/erich/projects/review-evidence/overnight-20260918/`. No production files were changed.
