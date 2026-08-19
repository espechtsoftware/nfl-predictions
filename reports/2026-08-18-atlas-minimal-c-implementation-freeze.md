# Implementation freeze: minimal ATLAS world-selection C test

Date: 2026-08-18
Protocol: `20260818-atlas-minimal-world-selection-c-v1` (Part B of
`reports/2026-08-18-atlas-disposition-and-minimal-c-test-protocol.md`).
This document binds the implementation before any outcome is opened.
Operator approval to run: recorded 2026-08-18 (HANDOFF 13:20 entry).

## Sources (outcome-blind bindings)

- **Worlds and natives**: the five production-law money-worlds panels
  `20260815-atlas-money-worlds-r{0..4}-v1` — registered candidates in
  `nfl_predictions.replay_candidates_staging` (support census 2026-08-18,
  counts only: 13,633 / 13,649 / 13,642 / 13,395 / 13,632; r3 carries 53
  slates). The r3/2025-W1 cell was never registered (artifact-only recovery
  in the transfer; no snapshot, no natives), so faithful regeneration is
  impossible for that seed: the 2025-W1 slate runs BOTH arms on the same
  four seeds (r0/r1/r2/r4) — budget parity holds and the receipt discloses
  `recovery_four_seed_slate`. Artifact bindings for all cells come from the
  acquisition `source-grid.json`, SHA-256
  `9a18458c63f0155b72f3847c705fbd0bdde9b64c923a5b63cc4a1f42bfe3445b`.
- **Generation inputs**: per-panel immutable snapshots in
  `nfl_predictions.slate_player_features` (support census: 29,605 rows x 54
  slates per panel, 29,016 x 53 for r3; `proj_tourney`, `own_est`, `actual`
  fully populated).
- **Environment**: exact per-block acquisition environment from
  `nfl_dfs.research.atlas_money_transfer.acquisition_environment` with
  `SEED_PAIRS` unchanged. Persistence destinations (`CAND_LOG_TABLE`,
  `CAND_FEATURE_TABLE`, `REPLAY_LINEUPS_TABLE`, `CAND_ARTIFACT_BUCKET`)
  are blanked at generation — infrastructure destinations, outside the
  lever set — and the diagnostic persists nothing to candidate tables.

## Invocation constants (mirroring the panel replay path)

`tail_select_lineups` called directly per slate x seed x arm with:
slate reconstructed as skill rows in artifact `player_ids` order
(`draw_idx = 0..n-1`) followed by DST rows sorted by team (`draw_idx = -1`);
`pool = slate.to_dict("records")`; draws = artifact `player_draws`;
`tail_line = 194.0`; `n_entries = 40`; `objective_col = "proj_tourney"`;
`contest = payout.gpp()`; `sharp_fraction = 0.0`;
`StackRules(qb_stack_min=2, bring_back_min=1, forbid_rb_vs_dst=True)`;
`candidate_multiple`, `n_boom_solves`, `n_game_stacks` from the acquisition
env (`CAND_MULT=2`, `N_BOOM=40`, `N_GAMESTACK=4`); `cand_log_table = None`;
`candidate_capture` collects the in-memory `CandidateBatch`.

## Arms

- Control: acquisition environment exactly as recorded.
- Treatment: identical plus `ATLAS_BOOM_WORLD_RANKING=1`, the engine lever
  added 2026-08-18 (`_boom_world_order` in `backtest/engine.py`; recorded
  in the immutable lever set; absent from the production policy receipt;
  seven-case offline test `tests/test_atlas_boom_world_ranking_lever.py`).
  Default path proven byte-identical to the incumbent argsort ranking
  (lever tests + golden-hash parity `tests/test_sbi.py` 12/12).

## Validity gates (before any outcome is read, per cell)

1. Artifact/candidate/snapshot support counts match the registered census
   exactly; one artifact URI+digest per cell.
2. **Exact native reproduction**: the control arm's ordered candidate
   identities must equal the registered natives for every seed of the
   cell. A reproduction failure halts the cell before any outcome read;
   the canary halts the whole run.
3. Actual-score parity: every registered native's `actual_score`
   reproduced from nine snapshot outcomes to 1e-9.

## Endpoints (after gates, per protocol B.5)

C per arm = max realized score over the five-seed pool union; S per arm =
realized max of the exact-80 book from
`combine_cbwu_books(books, (R0..R4), expected_worlds_per_book=10000)` +
`select_tail_entries(totals, 80, 194.0, env={"SELECT_LSE": "0"})`;
diversity context = pair reach, QB-stack-core reach, dominant-game reach
(CBWU-OI definitions). Gate and predeclared negative prior: protocol B.5/B.6
unchanged. Fail or null closes the ATLAS world-ranking family permanently.

## Execution envelope

54 create-only cells (one per slate), 4 CPU / 16 GiB, zero Cloud retries,
real-path canary on the first cell (with reproduction gate) before the 53
release; at most one same-spec replacement for a literal zero-object
platform error. Queued strictly behind the coherent-market-state score-free
chain; no launch while that chain occupies the heavy lane. Runner:
`scripts/run_atlas_minimal_world_selection_c.py` (SHA-256 pinned by the
launcher at launch time, with this document's SHA-256 pinned inside the
runner).

## Amendment 1 (2026-08-18 evening): artifact schema correction

The first local outcome-blind smoke failed closed: the frozen
`_slate_frame` assumed skill-only artifact rows and reconstructed DST from
the snapshot, while the pinned money-world artifacts store the complete
generation slate (2023 W1 R0: 756 skill + 17 DST rows, DST rows being the
constant projection broadcast). Classification and full record:
`reports/2026-08-18-atlas-minimal-c-smoke-disposition.md`. Amended
contract: all artifact rows form the slate in artifact order with real
draw indices; duplicate ids, snapshot leftovers, DST-free artifacts, and
non-constant DST rows all fail closed. No lever, budget, selector, gate,
or outcome rule changes; the exact native-reproduction gate remains the
arbiter of faithfulness. This document's SHA-256 is re-pinned in the
runner as part of the same commit.

## Amendment 2 (2026-08-18 evening): arm-invariant role-native injection

The amended smoke's second failure: the acquisition environment carries
the production `role_draws` family (N_EPISTEMIC=12), whose belief
slate/draws come from the role registry pipeline and are not
reconstructible from the pinned artifacts. The role family is
arm-invariant by code — its generation never reads the boom world
ranking — so both arms now generate with the role dose at zero and
receive the SAME registered role natives spliced in verbatim at their
registered cand_ix positions (`_inject_role_natives`): player order
follows the registered roster string; injected rows carry the artifact's
own world totals (pinned inputs, exactly like the draws); collisions
with regenerated identities, budget mismatches, missing players and
missing role natives all fail closed. The acquisition-record environment
validation is unchanged and still checks the faithful environment. The
exact native-reproduction gate is unchanged and its evidential force now
rests on every REGENERATED row, which is precisely the population the
lever can move. Estimand, budgets, selector, gates and outcome rules are
unchanged. Full record:
`reports/2026-08-18-atlas-minimal-c-smoke-disposition.md`.

## Amendment 3 (2026-08-18 evening): true-80 generation basis

Smoke #3 failed closed at the splice budget: natives 255 versus
regenerated 164 + injected 12. The source money-world panels were
true-80 replays (generation basis 80 entries; 160 lev candidates at
CAND_MULT=2, exactly as the coherent support census records per cell);
the original freeze passed a 40-entry basis, silently halving the lev
family. `N_ENTRIES` is corrected to 80. No lever, dose, selector, gate
or outcome rule changes; the exact native-reproduction gate remains the
arbiter. Record: `reports/2026-08-18-atlas-minimal-c-smoke-disposition.md`.

## Amendment 4 (2026-08-19): preseeded role dedup at the source position

Attempt 1's grid fired the Amendment-2 predeclared collision gate on
2023 W5: a post-role family regenerated a roster the source run's dedup
had skipped, because the role natives occupied the dedup universe there.
Dose-zero regeneration alone therefore cannot reproduce slates where
that dedup bound. The engine gains a faithful-regeneration seam
(`preseeded_role_identities`, default None byte-identical, rejects a
nonzero role dose and malformed identities): the registered role-native
identities enter `seen` at the exact position the role family occupied,
so every later family skips them exactly as the source did. The runner
passes the registered role identities in both arms; the injection
collision check remains as a backstop that should now be unreachable.
Attempt 1 (16 per-cell jobs + 38 reused-job executions, quota event
disclosed in its manifest) is SUPERSEDED before any outcome read from
its cells; its objects and ledger are preserved. Attempt 2 runs from a
fresh image at this amendment's commit under the `attempt-2/` output
prefix. Estimand, budgets, selector, gates, prior: unchanged.

## Amendment 5 (2026-08-19): four-seed recovery slate S endpoint

Attempt 2's 2025 W1 cell failed closed at `combine_cbwu_books`' exact
five-seed contract: this freeze predeclared that the recovery slate
(r3 never registered) runs both arms on the same FOUR seeds, but the
S-endpoint path was never adapted. Amendment: for exactly four books the
runner reports C normally (the paired primary, delta C, never needed S)
and S is ABSENT BY DESIGN with a `four_seed_recovery` disclosure; any
other seed shortfall still fails closed through the CBWU contract. The
five-seed path is byte-untouched (an early-return branch reachable only
at len==4), so the 53 five-seed cells already executing under the
Amendment-4 image are unaffected; ONLY the 2025 W1 cell reruns on the
Amendment-5 image, and the run manifest records both digests with this
unreachability argument. Estimand, budgets, selector, gates, prior:
unchanged.
