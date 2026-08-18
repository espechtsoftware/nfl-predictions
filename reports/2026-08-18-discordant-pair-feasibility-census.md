# Feasibility census: discordant-pair reanalysis of closed arms

Date: 2026-08-18. Outcome-blind: this census read panel identities, slate
counts and row counts only — no score, rank, or outcome field.

## Finding

`nfl_predictions.replay_candidates_staging` retains complete per-slate
candidate registrations for essentially the entire same-image arm/control
history: 104 panel_run_ids, including full 107-slate pairs (fast-role
`20260807-fast-role-v1-124e853` vs `20260807-universe-baseline-124e853`;
the `20260808/09/10/11` e80-k1/k3/ce12/ceunion/nofloor/role12union/lockfix/
pitclean families) and full 54-slate five-seed pairs (`20260813` sis-asoe
control/treatment, game-team-k, game-team-mult, incumbent-mcseed;
`20260814` sis-pass-tail control/treatment; `20260815` atlas-money-worlds).

Because each registered candidate row carries its roster and its
`actual_score`, **candidate-book weekly maxima per arm per slate are a
single aggregate over already-registered data** — the discordant-pair
tables (McNemar) for the C endpoint need no re-simulation, no new panel,
and no cloud compute.

## Protocol requirements before execution

1. The canonical arm/control pair list must come from the ledger's frozen
   comparisons, not from panel-name pattern matching — several superficially
   pairable panels were invalidated pre-scoring (e.g. role-belief-v1) or are
   non-citable, and pairing across images is forbidden.
2. Selected-book (S) discordance needs selection reconstruction from stored
   totals or the replay-lineups tables; scope Phase 1 to the C endpoint,
   which is fully derivable, and treat S as Phase 2 where books survive.
3. The protocol is diagnostic-only: it re-reads outcomes already read by
   the closed arms' own scoring, licenses no adoption, no closure reversal,
   no gate. Its output is the discordant-pair table per pair per threshold
   and the McNemar statistic, to calibrate how much weight the six-mechanism
   transfer record can bear (2026-08-18 briefing review §B).

## Next step

Draft `reports/…-discordant-pair-reanalysis-protocol.md` with the
ledger-verified pair table frozen before any aggregate is computed.
