# QB availability contract: served projections are conditional on playing — repair design (class R candidate, Week 3)

Draft for the lab's review, 2026-09-19 17:4xZ. Nothing here is implemented or armed. Evidence in lab handoff
`2026-09-19-workstation-991-read-qb-contract-policy-v2.md` §2 (read-only, Week-2 batch `2026-09-19 15:09:52Z`).

## 1. The defect

| depth_rank (features) | QBs | mean served proj | QBs with proj ≥ 8 |
|---|---:|---:|---:|
| 1 | 30 | 16.68 | 27 |
| 2 | 30 | 9.80 | 22 |
| 3 | 20 | 6.46 | 8 |

Backups at the $4,000 minimum project 9-17 points (Bagent 16.55 behind Williams 22.0; Keenum 15.55 at depth 3;
McKee 14.31; Ehlinger 14.26; Lance 13.75 …). Cause, from source: `depth_rank` is a model input
(`models/featureset.py:50` ← `003_player_week_role.sql` ← `depth_charts_snapshots.pos_rank`), but the component
models fit on `was_active` rows only (`featureset.py:146`), so for a backup the learned quantity is
**E[points | he played]**, and a backup who plays usually plays most of a game. No stage converts it to an
unconditional expectation: `cascade_adjust.find_out_players` zeroes DK O/IR and report OUT only (`OUT_STATUSES`,
Doubtful deliberately excluded); there is no P(start) in `inference/`; backups have no props, so the market blend
serves the model number; TabPFN's inactive zeros deflate it only partly. The vetter flags `depth_rank >= 3` for RB/TE
only. The lab's hsim gives team passing to the highest-`proj` QB, so the two halves disagree by ~13 points on these
players (Bagent −13.48 in the archived trace) and the morning D160 proof put non-primary QBs in 14 of 97 lineups.

Week 1's entered K90 sheet carried none of the 26 backup names; the risk is real for the full-dose Week-2 book and
every later week.

## 2. Repair (production, `src/nfl_dfs/inference/cascade_adjust.py` + `run_projections.py`)

**Contract to restore:** the served QB projection is the *unconditional* expectation for the slate. Implementation:

1. New `qb_start_factor(feats) -> pd.Series` (per QB gsis_id), computed after blending and before
   `zero_out_projections`:
   - depth-1 QB of the team present and not OUT/IR/Doubtful → backups (depth ≥ 2) get factor `p_backup_start[depth]`;
   - depth-1 QB OUT/IR → the depth-2 QB becomes primary (factor 1, and the existing `adjust_for_inactives` cascade
     already redistributes the starter's opportunity — verify it treats QB), depth-3 gets `p_backup_start[2]`;
   - depth-1 QB Doubtful → the depth-2 QB gets `p_doubtful_starter_sits` (historical rate of Doubtful QBs sitting)
     and the starter keeps `1 − p`; this is the ATL (Tua / Rush) case;
   - missing depth for a team (no snapshot) → no change, listed in the receipt as unadjusted.
2. Factors scale `proj_points`, `proj_p50`, `proj_p90` (and `p_20_plus`) — the distribution's mass at zero is the
   honest representation; `proj_std` recomputed as a mixture (or left, with the limitation stated). **Receipt** lists
   every adjusted player with before/after and the rule that fired, so the after-build sheet and the weekly evidence
   record can audit it.
3. **Status-only gate first (Week 3):** `p_backup_start = 0` for depth ≥ 2 when the starter is healthy — that is the
   contract restored exactly at the modal outcome and matches the hsim treatment. The historical start-rate version
   (walk-forward from `rosters_weekly` × `player_week_actuals`: share of weeks a depth-k QB recorded a pass attempt
   while the depth-1 was active) is a class-C refinement measured on the weekly record, not part of the repair.

## 3. Proof required before entering (track v2 §2, class R)

- The broken contract and correction proven (this document + the Week-2 table reproduced on the frozen frame).
- Unchanged leakage checks pass (`build-features` untouched; the change is inference-side only).
- Exact identities and declared tolerances: every non-QB row byte-identical; QB rows with depth 1 and a healthy
  starter byte-identical; only the listed backups change.
- Propagation quantified on the **archived Week-2 frame**: served means, candidate pool, selected K97 book,
  membership/exposure shifts, expected max / proxy / P220 under both component banks — reported, not optimized.
- Rollback: the previous pinned production commit; the factor is behind a config flag defaulting to the repair.
- Tests: unit tests for the four branches above on a synthetic slate; a golden test on the archived Week-2 frame.

## 4. Consumers to check for the same class (frozen-chain lesson 4: sweep the class)

The same conditional-vs-unconditional gap exists for depth-2 RBs/TEs/WRs, but P(plays) is far higher and the vetter
already flags RB/TE depth ≥ 3; QB is the extreme case (one starter). Sweep: the TabPFN active-only label experiment
(prepared), the DST path (separately sampled), and the K1 role model's use of `depth_rank`.

## 5. Sunday (class E — operator's decision, information only)

`/home/erich/week2-sunday/qb_flags.sh` writes the backup-QB table from the live batch; `gen_sheet.py` marks kept
lineups whose QB is on it, with the starter's status. No vetter, build or projection change before Sunday.
