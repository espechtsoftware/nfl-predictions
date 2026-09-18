# Week-2 diagnostic archive transfer verified

September 18, 2026. Workstation handoff1aeecd9 supplied the September17 D6400/K90 population at
`gs://nfl-2-506823-lab/research/week2-diagnostic-population/20260917T150719330879Z-e7255e9/`.
Laptop independently downloaded and verified the FULL supplied SHA256 of candidates.parquet,
frame.parquet, both player-score arrays and receipt.json. All five matched. Object generation IDs
and schemas are retained in `reviews/evidence/2026-09-18-week2-archive-preflight.json`, with its script.

Structure:6400 candidate rows,435 frame rows, two float32(435,10000) arrays. Only schemas/headers and
allowlisted receipt metadata were decoded; no actuals, prediction values, ranks or book outputs read.
Array bytes were hashed but not interpreted as scores. This is verified access and structural support,
not completion of a performance experiment.

The operating agent reports the armed entry build has BOOK_ENTRIES=97 and ENTER_LAYOUT=sequential,
with12 disjoint contest blocks totaling97. It reports rejection of K90 by the build receipt gate and
successful synthetic97-entry publication checks. Those host-environment checks are its evidence,
not independently reproduced on this laptop. The final D12800/K97 entry build is still distinct from
this archived D6400/K90 diagnostic run.

The pending capture patch will preserve existing incumbent audit draws without changing selections.
It is not yet reviewed or deployed. The hsim audit half remains missing, explicitly acknowledged.
Current-week selection diagnostics must use raw dual_emax, explicit97-entry/block semantics, and
separately report primary utility/220 diagnostics; the old D800/WEMAX sidecar is not that baseline.
