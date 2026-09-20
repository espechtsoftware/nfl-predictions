# SIS pass-tail 2026 prospective gate (DRAFT for lab acceptance; registry entry `sis-pass-tail-2026`)

Written 2026-09-20, before any 2026 outcome of the shadow is available, to close the finding in
`scripts/check_prospective_gates.py` ("no frozen prospective-gate document governs this pair"). Governing protocol:
`2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md` (identity `prospective-sis-pass-tail-finite-k-v1`), which
this document does not alter; it only declares the gate, window, policy contract and adjudication.

## Policy contract

* Jobs: `shadow-sis-pass-tail-paired` (Sun 06:00 CT), `tabpfn-sis-pass-tail-control` / `-treatment` caches (Thu 09:15 /
  09:20 CT). Isolated live caches `tabpfn_sis_pass_tail_live_control_v1` / `..._treatment_v1`; historical write-once
  tables never appended.
* Arms differ ONLY by the TabPFN cache and the served-position schedule (control `QB:0.85,RB:0.895,TE:0.96,WR:1.04`;
  treatment `QB:0.92,RB:0.965,TE:0.945,WR:1.04`) and the treatment's three fields `sis_pass_def_boom_rate_l4`,
  `sis_pass_def_bust_rate_l4`, `sis_pass_rush_pressure_rate_l4` (opponent-team, same-season, volume-weighted over at most
  four completed games with source week < W, at least two required; target-week spine; `available_at <= generated_at`).
* Common fixed settings: `DIRICHLET_K=28.154043586960896`, `SIS_ASOE_BETA=0.07771181538347656`, tail line 194, 80
  entries, 10,000 worlds per book, the five registered seed pairs; no CBWU union, archetype reallocation, route
  features, no-floor policy, ownership treatment, or other unregistered interaction. The money path stays boom-first
  `N_BOOM=160 / N_LEV=40` in the production selector; the shadow's own registered budget is the protocol's (12
  alternate-role + 40 boom, exact 80). `require_env` for the checker: the two cache table names above must be the
  jobs' configured `TABPFN_MARGINAL_TABLE` values (control / treatment respectively); any other divergence between the
  arms fails the gate.

## Window and adjudication

* `first_week` 5 (four completed weeks of context), `last_week` 18, `floor_weeks` 12 complete paired weeks as the
  support floor (aligned with the Route Share gate), checkpoints after Weeks 8, 13 and 18 per the protocol; checkpoints
  cannot promote; adjudication after ALL of weeks 5-18 are frozen and scored.
* Read: control vs treatment weekly maximum counts at 240/230/220/210/200/194/187, distinct improving and worsening
  slates, mean weekly maximum, exact-80 overlap, candidate overlap, source coverage, operational failures; paired
  weekly comparison with slate-cluster intervals.
* `in_season_value`: False by design (no 2026 in-season use; the value is the 2027 adoption decision and the SIS renewal
  decision). Any 2026 in-season use of the treatment would require its own class-C candidate package under the
  in-season track, never this gate.
* Material-harm guard: a snapshot with identity drift or a partial five-seed / two-arm grid is void, never imputed;
  missing-source weeks are counted, not dropped.

## What this gate needs before it is live

1. Lab acceptance (the protocol is theirs; this document only registers it) and the registry entry in
   `check_prospective_gates.py` (`doc` = this file, `first_week` 5, `last_week` 18, `floor_weeks` 12, the three
   schedulers, `require_env` as above, `in_season_value` False).
2. Operator decision to resume the three schedulers (command sheet, section 3), by the Thursday the first needed cache
   must be built; if the caches cannot be backfilled for the context window, the lab states the earliest target week.
3. If not accepted before Week 5: move the three schedulers to DORMANT in the checker with the reason "no accepted gate
   before the first target week", never park a live gate silently.
