# TD competitive-WR repaired reference result

Date: 2026-08-14 CDT.

## Result

Stage R passed and licenses the already-frozen Stage T allocation test.

- Cloud Run execution: `td-competitive-wr-reference-v1-2trhj`
- immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:eb2902ab0d5ba07e4981875513f4c59ae5ea14055ea82160b0c9cb751b3c80c5`
- code SHA: `74df236087664208235a9cf5028abe4a86187e34`
- strict report SHA-256:
  `748822294c90f3178ca79989bac17f065662589230bf0fab24897d2c59898e2b`
- canonical control score SHA-256:
  `2584120b13fa99da99a6f916015c70eb985cb1f06396750de829593d7fd8979e`
- disposition: `td-competitive-wr-reference-passes`

Every registered reference invariant passed: frames aligned exactly, repeated
draws were bit-exact, terminal identities matched, all draws were finite, and
the newly measured repaired-control score book reproduced the pinned prior
control with no reported differences at absolute tolerance `1e-12`.

## Consequence

Stage T may run once using the mechanism and gate frozen in
`2026-08-14-td-competitive-wr-allocation-protocol.md`. The reference report,
manifest, run/code identities and canonical score SHA are all bound into the
treatment attestation. This pass does not itself license lineup scoring; the
conditional exact-80 branch still requires a strict Stage T gate pass.
