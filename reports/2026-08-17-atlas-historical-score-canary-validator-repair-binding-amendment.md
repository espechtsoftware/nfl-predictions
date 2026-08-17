# ATLAS historical-score v3 canary-validator repair binding amendment

Frozen: 2026-08-17, after the repair5 canary cloud execution and object
completed but before the canary shard body, any repair5 score-free treatment
effect, or any realized historical score was opened.

Applies to `20260816-atlas-historical-score-diagnostic-v3`. It adds only the
provenance needed for the local canary-validator quoting repair; all prior v3
source, attempt, canary, population and tail-gate rules remain unchanged.

The repair5 historical-score source lock must additionally bind and verify:

- unchanged original canary validator SHA-256
  `e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411`;
- repair protocol
  `reports/2026-08-17-atlas-repair5-canary-validator-quoting-repair.md`,
  SHA-256
  `3929c805db67b0d9d66500f6b4d14c6ea4011d8c3723dd2b86535ea9a4e69d94`;
- exact-argv compatibility wrapper
  `scripts/atlas_repair5_validator_bin/awk`, SHA-256
  `42e0c74654f5e7ecb70e164aa1b28bc188f6279bde1273aa45093c51e5871b7a`;
- resume launcher
  `scripts/resume_atlas_repair5_after_canary_validator_quoting.sh`, SHA-256
  `a2a00c559d74a38610736ccb93f695568993da6f65bc7ce7d82b2ecca527bb48`;
- `canary-validator-attempt0/receipt.txt`, its hash, both archived metadata
  hashes and `attempt.sha256`;
- the re-executed unchanged validator's final `canary-completion.txt`,
  `canary-execution-metadata.json`, `canary-object-metadata.json` and
  `canary.sha256`; and
- `grid-release.txt`, including exact matching values for
  `original_canary_validator_sha256`,
  `canary_validator_repair_protocol_sha256`,
  `canary_validator_awk_wrapper_sha256`,
  `canary_validator_resume_sha256`, and
  `canary_validator_attempt0_receipt_sha256`, plus
  `canary_rerun=false`, `object_content_inspected=false` and
  `effect_fields_inspected=false`.

The lock must also prove that the canary execution identity remains
`atlas-md-s2023-w1-r5-45nvf`, that the primary ledger contains that execution
exactly once, and that no second canary execution exists. Any missing or
different repair receipt, file hash, field, execution or archived-metadata
binding invalidates the v3 source lock. It may not be waived or reconstructed
after opening a shard or score.

This amendment changes no ATLAS law, seed, slate, image, command, resource,
retry rule, destination, score-free gate, realized-score gate or production
policy. It only makes the mechanical continuation auditable.
