# PFR secondary report-transport repair

Status: frozen 2026-08-13 after clean execution
`tabpfn-pfr-secondary-final-served-v1-f2zrw` and a failed local harvest.

The Cloud Run task completed successfully, but the one-line structured report
exceeded Cloud Logging's 102,400-byte `textPayload` limit. The retained record
ends after exactly 102,400 bytes and is invalid JSON. The scientific task did
not fail; the output transport did. Diagnosis necessarily exposed the report's
already-computed top-level disposition and gate: no feature-drop arm was
eligible. The complete fold, position, calibration, and uncertainty report was
not recoverable from the truncated log.

The sole licensed repair is transport-only:

1. preserve the truncated payload as `truncated_raw_log.txt`;
2. serialize the unchanged report as canonical finite JSON, gzip it with a
   fixed timestamp, base64-encode it, and emit chunks of at most 48,000
   characters plus byte counts and SHA-256 identities;
3. make the harvester require every indexed chunk and verify both compressed
   and uncompressed identities before accepting the report; and
4. rebuild and repeat the deterministic score-free task once from a new
   immutable image.

No arm, cache, source row, fold, seed, fit, position-factor grid, metric, gate,
tie order, or conditional lineup consequence changes. The repeated task may
only reproduce the already-visible no-eligible-drop branch or reveal a
mechanical failure in the complete payload; it cannot license a different
scientific question.
