# Backup-QB availability gate: propagation on the live Week-2 frame (before any deploy)

Branch `production/qb-availability-gate-20260919`; code in `src/nfl_dfs/inference/cascade_adjust.py`
(`find_backup_qbs`) applied in `run_projections.project()` through the existing `zero_out_projections` path;
`tests/test_cascade_adjust.py` (11 pass: 7 existing + 4 new). Design: `reports/2026-09-19-qb-availability-contract-repair-design.md`.

**Input:** the served batch `2026-09-19 15:09:52.915006Z` QB rows joined to `player_week_inference` (`depth_rank`,
`injury_status`) and the latest DK feed status for draft group 153428
(`reports/reviews/evidence/2026-09-19-qb-gate-live-frame-input.csv`). **Output:**
`…-gated.csv` / `…-propagation.json`.

**Result:** of 83 QBs with a depth rank on file, the gate zeroes **48** (364.3 served points removed in total; the
largest: Bagent 16.55, McCarthy 15.91 — behind Wentz once Murray is Out — Keenum 15.55, McKee 14.31, Ehlinger 14.26,
Lance 13.75, Stidham 13.50, Dalton 13.48, Mills 13.12, Howell 12.68 …). **Untouched, by rule:** ATL (Penix Out →
Tua is the shallowest non-out QB but Doubtful → team left alone: Tua 17.47, Rush 14.44, Strand), MIN Wentz 15.95
(primary after Murray Out), SEA Lock 15.29 (primary after Darnold Out). No non-QB row changes; no depth-1 healthy
starter changes. Rollback: `QB_BACKUP_GATE=0` on the job (no redeploy) or the previous image digest.

Not measured here: the candidate pool and selected book under the gated projections — that needs a build
(the D160 CLI rehearsal after the running Saturday build, or Sunday's own chain).
