# Repair: parity smoke deploy comma-splits its inline command

Date: 2026-08-18
Author: Claude (Fable 5), orchestrating
Repair class: mechanical launcher defect; validation logic unchanged; no
science object existed.

## Defect

Second launch attempt of `20260816-atlas-interaction-parity-v1` (first
attempt after the census-key repair) failed closed at
`ERROR: ATLAS interaction-parity smoke container differs`.

Cause: `gcloud run jobs deploy --args=-c,"$SMOKE_COMMAND"` splits the value
on commas. `SMOKE_COMMAND` contains commas (`import base64,hashlib,pathlib`),
so the deployed container received six args and executed only
`import base64` — a vacuous success (Completed=True). The launcher's own
container-shape validation caught the mangled args exactly as designed; the
deploy syntax, not the validator, was wrong. The main-job deploy on the same
script is unaffected: its command payload is base64-wrapped and contains no
commas, and its commas are intentional argument separators.

## Evidence

`smoke-execution.json` (archived, see below): `n_args=6`,
`args[1]='import base64'`, `args[2]='hashlib'`. Verified before repair:
no `atlas-interaction-parity-v1` job existed and the cloud output prefix
matched no objects — the failure preceded any science object.

## Exact change

Line 142, gcloud alternate-delimiter syntax (verified `@` does not occur in
`SMOKE_COMMAND`):

```
- --image "$IMAGE" --command python --args=-c,"$SMOKE_COMMAND" \
+ --image "$IMAGE" --command python --args="^@^-c@$SMOKE_COMMAND" \
```

| file | before SHA-256 | after SHA-256 |
|---|---|---|
| `scripts/cloud_atlas_interaction_parity_diagnostic.sh` | `ed0ab72bf2864a227bc06b361508d26c2e2735bcb9b96f24602932e63df3fd16` | `a8d569ab026eb153c80a7ace5da98a8674f1bae86e83c4b61e758291a8e7c726` |

The before value is the after value of the census-key repair
(`reports/2026-08-18-atlas-parity-census-key-repair.md`); the finisher is
untouched by this repair.

## Partial-receipt disposition

The failed attempt wrote `manifest.txt` and `smoke-execution.json` into the
run directory before exiting; the create-only guard would otherwise block
relaunch. Both files are moved to `failed-launch-attempt-1/` inside the run
directory (nothing deleted). They contain metadata only — no roster, no
outcome, no treatment effect. `execution.txt`, `completion.txt`, the main
job and all cloud objects never existed for this attempt.
