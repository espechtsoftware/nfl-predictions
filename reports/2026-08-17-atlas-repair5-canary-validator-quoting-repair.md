# ATLAS repair5 canary-validator quoting repair

Frozen: 2026-08-17, before opening the repair5 canary shard or any ATLAS
effect/score field.

Applies only to run
`20260816-atlas-matched-diversity-mvp-v1-repair5` and execution
`atlas-md-s2023-w1-r5-45nvf`.

## Observed boundary

The real-path canary itself completed successfully. Cloud Run reported one
successful task, zero failed tasks and a terminal `True` condition. It wrote
the expected create-only object at the frozen 2023 Week 1 URI. Only object
metadata was observed: generation `1786971235274440`, positive size `292741`
bytes, and the provider checksums. The object body, candidate identities,
candidate scores, score-free treatment effects and realized outcomes were not
opened.

After those facts were collected, the frozen local validator failed while
extracting `output_prefix` from `manifest.txt`. Its source contains this exact
single-quoted awk program:

```text
$1==\"output_prefix\" {print $2}
```

Because the program is already single quoted, the backslashes reach awk
literally. System awk rejects the program before the validator's Python
contract check can run. The shell then moved the two already-collected
metadata files from their pending names, but no `canary-completion.txt`,
`canary.sha256` or `grid-release.txt` was created. The ATLAS container,
scientific law, resource envelope, artifact and cloud execution did not fail.

## Frozen repair

1. Do not rerun the canary and do not edit the original validator. Its SHA-256
   remains
   `e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411`,
   as required by the original manifest, attempt resolver and finisher.
2. Preserve the two metadata files from the failed validator invocation under
   `canary-validator-attempt0/`, together with their hashes and a receipt.
3. Invoke the unchanged validator with
   `scripts/atlas_repair5_validator_bin` first on `PATH`. Its `awk` wrapper
   replaces only the exact malformed argv value above with the intended
   `$1=="output_prefix" {print $2}`. Every other argv vector is passed to
   `/usr/bin/awk` unchanged.
4. Require the unchanged validator to reproduce the exact manifest command,
   cloud execution contract, terminal success, positive object metadata and
   score-blind canary receipt. It still opens no object body.
5. Release the same frozen remaining 53 cells only after that receipt passes.
   No seed, ATLAS setting, input, image, command, resource, retry rule,
   destination, slate, gate or later scoring rule changes.
6. Record this protocol, wrapper, resume-script and failed-attempt receipt
   hashes in the grid-release evidence. The downstream historical-score v3
   source lock must bind this repair evidence before any ATLAS shard effect or
   realized score is opened.

This is a mechanical continuation of the already-frozen experiment. It
cannot issue an ATLAS scientific disposition, inspect an effect, license a
historical-score conclusion, or change production.
