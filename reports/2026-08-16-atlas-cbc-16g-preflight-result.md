# ATLAS CBC 16 GiB preflight result

Date: 2026-08-16

Protocol ID: `20260816-atlas-cbc-16g-preflight-v1`

Execution: `atlas-cbc-16g-preflight-2024-w15-v1-ckjlj`

## Result

The exact old-binary 2024 Week 15 R0 calculation completed successfully in
the prospectively frozen 4-CPU / 16-GiB resource envelope. Cloud Run reports
terminal success at `2026-08-16T18:19:07.149622Z` after 2h13m37.08s.

The strict summary records:

- disposition and status `r0-complete`;
- CBC child return code `0` and no terminating signal;
- zero observed OOM-kill-counter delta;
- true cgroup peak `3,524,108,288` bytes, or `0.20513010025024414` of the
  16-GiB limit; and
- `uses_realized_outcomes=false`, `persists_lineups=false`, and
  `production_change_licensed=false`.

This passes the mandatory preflight in
`reports/2026-08-16-atlas-mvp-resource-only-repair3.md` and licenses the
complete 54-cell resource-only repair3 launch. It does not establish an ATLAS
effect, produce a historical score, or license production.

## Durable evidence

- Frozen protocol SHA-256:
  `4c09ba4065e5ac32af3873f149ca42c0dd922cadc21524fd277f404d7fdc45a7`.
- Launch manifest SHA-256:
  `059cf942a06de76815151e34db1ba363535c17c2069e1ce7bd19486804a8334f`.
- Execution ledger SHA-256:
  `00a50351f571a606e8efb47ae8eea0134c911998e64fe85e9836cf0677dd5ae3`.
- Strict summary SHA-256:
  `54e659421cd4ebe59f0d0219e1dd9a9db6774e6161c681f24f39b667e964228f`.
- Strict completion SHA-256:
  `07157e8e1589eaeb903ae5d7d124b677904061c11cdcc8567fab6649a1d317a9`.
- Execution-metadata SHA-256:
  `5be634c054a34f29c7772a04633d63eeb4cf497f84a4a99b694d38b24b147c43`.
- Artifact-ledger SHA-256:
  `3aea352b2d727e3f61a8e6cce5be980b19825f05c34a3c32e9842d975fcaa531`.
