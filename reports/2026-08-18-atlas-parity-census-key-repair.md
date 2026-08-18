# Repair: parity launcher/finisher census completion key name

Date: 2026-08-18
Author: Claude (Fable 5), orchestrating
Repair class: mechanical consumer-side key-name defect; no eligibility rule
weakened, no data artifact modified.

## Defect

The first launch attempt of the ATLAS continuous-interaction parity diagnostic
(`20260816-atlas-interaction-parity-v1`, launched 2026-08-18 ~12:50Z after its
queue guard was satisfied by the repair5 terminal failure census) failed
closed with `ERROR: ATLAS repair5 census completion differs`.

Cause: two frozen artifacts disagree on one key name.

- The frozen repair5 census harvester
  (`scripts/cloud_harvest_atlas_repair5_terminal_census.sh`, line 450,
  protocol `reports/2026-08-16-atlas-repair5-terminal-census-protocol.md`
  SHA-256 `94a792d8...`) writes `all_declared_attempts_terminal=true`
  to `terminal-census-completion.txt`.
- The parity launcher expected-key table (line 86) and the finisher parity
  check (line 93) expected `all_terminal=true`.

The produced census artifacts are checksum-verified
(`terminal-census.sha256`, `terminal-census-completion.sha256`: OK) and are
NOT modified by this repair. The harvester ran first and its output format is
the recorded authority; the consumers carried a stale draft key name.

## Semantic equivalence

Both keys assert the identical proposition: every declared repair5 attempt
(54 primary executions, 0 retries) reached a terminal state. The JSON-side
strict checks (version, executions=54, terminal_failed>=1,
scientific_result_valid=false, effect_fields_inspected=false,
historical_scoring_licensed=false, continuous_parity_capacity_released=true)
are unchanged. The completion-side compare still requires the same five
assertions with unchanged values; exactly one expected key is renamed to the
name the frozen harvester actually emits. Nothing is weakened.

## Exact change

One-line rename in each consumer, `all_terminal` ->
`all_declared_attempts_terminal`:

| file | before SHA-256 | after SHA-256 |
|---|---|---|
| `scripts/cloud_atlas_interaction_parity_diagnostic.sh` | `183e29ea4387fcb3a60ea9277a01f1fa514522df50b06dc64b22cf2a3e6c246c` | `ed0ab72bf2864a227bc06b361508d26c2e2735bcb9b96f24602932e63df3fd16` |
| `scripts/cloud_finish_atlas_interaction_parity_diagnostic.sh` | `0b350fe6874c8ada762a7a9175edf9099fe3f8aa732ea2462b08de81b00987b1` | `c5d527e41030a23a71c8d31ce049adb189ce2c25ae6cb9c56cc558ff9beda2a5` |

Both pre-repair values match their HANDOFF-recorded bindings byte-for-byte
(verified with sha256sum immediately before the patch).

## Execution context

The launcher runs from detached worktree `/tmp/nfl-parity-fa90ff7` at commit
`fa90ff7cd4f62483f3dd21a7ec7dcb35c83f7246` (the latest commit where all seven
launcher-pinned frozen sources match; `src/nfl_dfs/optimizer/lineup.py`
drifted at `7c74f2a` for unrelated constraint-lattice work). The worktree
deviates from `fa90ff7` in exactly these two repaired scripts, which this
document records. Live run directories (`atlas-interaction-parity-runs`,
`atlas-cbc-32g-full-cell-preflight-runs`, repair5) are symlinked to the main
checkout. The identical patch is committed to `main`.

No treatment effect, roster, or outcome was visible at repair time: the
launch had not created the manifest, any job, or any cloud object
(fail-closed exit preceded manifest write).
