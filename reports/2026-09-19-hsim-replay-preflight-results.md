# Hsim archived-bank replay: exact match

Frozen protocol/source `b9392eb0`, executed September 19, 2026. The unchanged hsim source at lab `e7255e98bf87297452befb61fb508ad4b368b59f`, authenticated historical benchmark inputs and archived Week2 frame reproduce the archived 435 × 10,000 float32 score bank **exactly**. Differing elements: **0 of 4,350,000**; all absolute differences zero. NPY SHA-256 matches the archive: `1d5b6372c9ba4a1d86ddac7c29652f432377486966a5be4bc08f338eb01e7a06`.

Runtime after downloading inputs: **3.526 seconds**. The input benchmark contains six files across historical training, raw weekly stats and raw schedules; all byte counts and manifest CRC32C values matched, with additional SHA-256 identities recorded. The existing outcome firewall at cutoff 2026 prevents current/future realized outcomes from entering a fit. Frame reads use a fixed 18-column identity/hsim-input allowlist with no actuals. Exact source authentication covers every hsim module plus data.py.

The existing calibration expression emits divide-by-zero warnings because NumPy evaluates the unused branch of `np.where` for zero pilot means. Output scores are finite and byte-identical; no warning suppression or model change was made.

This validates mechanical replay only. It supports the planned isolated usage-input comparison; it does not establish accurate real-world tails or an improved book. No repaired-input effect has been read in this preflight. Full receipt: [evidence](reviews/evidence/2026-09-19-hsim-replay-preflight.json). The local replay NPY is reproducible from the pinned inputs and is held under `review-evidence/overnight-20260918/hsim-replay/`.
