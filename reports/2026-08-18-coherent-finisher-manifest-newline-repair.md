# Repair: coherent score-free finisher manifest newline parsing

Date: 2026-08-18. Repair class: latent consumer-side parsing defect in a
frozen script, exercised for the first time by tonight's first complete
54-shard harvest; no data artifact modified, no eligibility weakened.

## Defect

`scripts/cloud_finish_coherent_market_state_scorefree.sh` reached its
per-execution contract check for the first time (54/54 accepted primaries)
and aborted on the first row with `ABORT: coherent-state execution contract
differs`. Independent field-by-field replication showed every execution
(canary included) matches the intended contract exactly. Cause: the
finisher's python blocks at lines 85 and 151 parse the launch manifest with
`line.split("=", 1)` over a raw file iterator — values retain their
trailing newline, so `m["image"]` and `m["code_sha"]` can never equal any
real field. Line 39 of the same file parses correctly via
`.splitlines()`; the parity finisher family already used
`.rstrip("\n")`. The check as frozen could not pass for ANY execution.

## Exact change

Add `.rstrip("\n")` before `.split("=", 1)` at both defective sites
(identical to the file's own line-39 semantics). Comparison targets and
strictness are unchanged.

| file | before SHA-256 | after SHA-256 |
|---|---|---|
| `scripts/cloud_finish_coherent_market_state_scorefree.sh` | `9e89347a71d13ad73637d0a5cc38c73cf810648a3d8896013a926023292340ef` | `1cf417e0d40dece7319d438b22ee9407a79e681be3f18add8b729f0cf9a9e8e9` |

Identical patch applied to the frozen execution worktree
`/tmp/nfl-coherent-cde9c60` (deviation recorded here). The finisher is
idempotent-by-design (cleanup-on-failure pending directory; completion not
yet written); rerun follows this repair.
