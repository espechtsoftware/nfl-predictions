# All-boom canary attempt 1 — disposition (2026-08-19)

Execution `atlas-minimal-c-s2023-w1-v1-mqpgm` (image build `174e59ff`,
tag `all-boom-8a2f83c`) died at receipt serialization: `family_counts`
held np.int64 values from `dict(pd.Series(...).value_counts())`. The
pre-launch smoke could not catch it because `json.dumps` sat inside the
non-smoke branch. No artifact was uploaded (create-only prefix empty),
so no observation exists and the rerun is legitimate.

Repairs (single commit, class-swept — the only instance repo-wide):
1. `family_counts` and `role_injected` explicitly coerced to int.
2. Receipt serialization moved OUT of the non-smoke branch: every
   path, smoke included, now exercises the full JSON contract; only
   the upload stays gated.

Relaunch: fresh clean-archive build from the repair commit; chain
re-run end to end (job reuse unchanged, rule 5).
