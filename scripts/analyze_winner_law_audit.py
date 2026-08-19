#!/usr/bin/env python3
"""Run the winner-lineup law audit (protocol 20260818-winner-law-audit-v1).

Scores known Milly-winner rosters under archived production world
artifacts and writes the frozen diagnostic report, create-only. This is
outcome-aware and diagnostic-only: it licenses no gate, promotion, or
production change, and must run exactly once per frozen protocol version
after the operator freezes reports/2026-08-18-winner-law-audit-protocol.md.

Inputs:
  --winners-root  directory holding the two tracked winner CSVs
                  (milly-winners-2019-2023-2024.csv, 2025-milly-rosters.csv)
  --features      parquet/csv of immutable slate-player snapshots with
                  season, week, id, name, pos, team, salary, actual, proj,
                  mean_projection
  --manifest      JSON list of {"season", "week", "artifacts": [npz paths]}
                  — every listed slate must resolve a nine-player winner
                  and every artifact must carry player_ids/player_draws
  --output        report JSON path (created exclusively; never overwrites)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.analysis.winner_law_audit import (  # noqa: E402
    PROTOCOL_ID,
    WinnerLawAuditError,
    align_world_blocks,
    audit_roster_under_law,
    winner_law_report,
    winner_roster_world_totals,
    winner_world_assignment,
)
from nfl_dfs.analysis.atlas_world_ranking import (  # noqa: E402
    rank_worlds,
    roster_slot_upper_bound,
)
from nfl_dfs.research.real_winner_overlap import (  # noqa: E402
    load_known_winner_rows,
    match_known_winner_players,
)


def _load_features(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _load_block_full(
    path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with np.load(path) as artifact:
        keys = set(artifact.files)
        if not {"player_ids", "player_draws", "totals"} <= keys:
            raise WinnerLawAuditError(
                f"{path} lacks player worlds/totals (keys: {sorted(keys)}); "
                "only artifacts persisted with CAND_ARTIFACT_PLAYER_WORLDS "
                "carry the aligned player-by-world matrix")
        return (
            np.asarray(artifact["player_ids"], dtype=str),
            np.asarray(artifact["player_draws"], dtype=np.float64),
            np.asarray(artifact["totals"], dtype=np.float64),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--winners-root", required=True, type=Path)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text())
    if not isinstance(manifest, list) or not manifest:
        raise WinnerLawAuditError("manifest must be a non-empty JSON list")

    winners = load_known_winner_rows(args.winners_root)
    features = _load_features(args.features)
    slate_keys = {(int(m["season"]), int(m["week"])) for m in manifest}
    if len(slate_keys) != len(manifest):
        raise WinnerLawAuditError("manifest repeats a slate")
    scoped = winners[[
        (int(s), int(w)) in slate_keys
        for s, w in zip(winners.season, winners.week)
    ]]
    resolved = match_known_winner_players(scoped, features)

    entries = []
    for slate in sorted(manifest, key=lambda m: (m["season"], m["week"])):
        season, week = int(slate["season"]), int(slate["week"])
        roster = resolved[
            resolved.season.eq(season) & resolved.week.eq(week)]
        if len(roster) != 9:
            raise WinnerLawAuditError(
                f"{season} week {week}: resolved {len(roster)} winner "
                "slots, expected 9")
        blocks = []
        block_extras = []
        for p in slate["artifacts"]:
            ids, draws_block, cand_totals = _load_block_full(Path(p))
            blocks.append((ids, draws_block))
            block_extras.append((ids, draws_block, cand_totals))
        player_ids, draws = align_world_blocks(blocks)
        totals = winner_roster_world_totals(
            roster.id.tolist(), player_ids, draws)
        realized_snapshot = float(roster.snapshot_actual.sum())

        # N1b: generating-worlds census per seed block. A generating
        # world is one where the winner outscores every registered
        # candidate; ranks are positions in each block's own boom visit
        # order (descending slate total — the incumbent production
        # ordering), with the closed ATLAS ordering kept as descriptive
        # context per the frozen protocol.
        slate_pos = features[
            features.season.eq(season) & features.week.eq(week)
        ].drop_duplicates("id").set_index("id")["pos"].astype(str)
        assignment = {
            "n_generating_worlds": 0, "blocks": [],
            "best_rank_slate_total": None, "within_top40_slate_total": 0,
            "within_top200_slate_total": 0, "best_rank_atlas": None,
            "within_top40_atlas": 0, "max_margin": None,
        }
        for ids, draws_block, cand_totals in block_extras:
            winner_block = winner_roster_world_totals(
                roster.id.tolist(), ids, draws_block)
            order = np.argsort(
                np.asarray(draws_block).sum(axis=0), kind="stable")[::-1]
            positions = [slate_pos.get(str(pid), "") for pid in ids]
            atlas = rank_worlds(
                roster_slot_upper_bound(
                    np.asarray(draws_block), positions),
                np.asarray(draws_block).shape[1])
            block_result = winner_world_assignment(
                winner_block, cand_totals, order, atlas_order=atlas)
            assignment["blocks"].append(block_result)
            assignment["n_generating_worlds"] += \
                block_result["n_generating_worlds"]
            margin = block_result["max_margin"]
            if assignment["max_margin"] is None or \
                    margin > assignment["max_margin"]:
                assignment["max_margin"] = margin
            summary = block_result.get("generating_rank_summary")
            if summary:
                for field, best in (
                    ("best_rank_slate_total", "best_rank_slate_total"),
                    ("best_rank_atlas", "best_rank_atlas"),
                ):
                    value = summary.get(best)
                    if value is not None and (
                        assignment[field] is None
                        or value < assignment[field]
                    ):
                        assignment[field] = value
                assignment["within_top40_slate_total"] += summary.get(
                    "within_top40_slate_total", 0)
                assignment["within_top200_slate_total"] += summary.get(
                    "within_top200_slate_total", 0)
                assignment["within_top40_atlas"] += summary.get(
                    "within_top40_atlas", 0)

        entries.append({
            "season": season,
            "week": week,
            "roster_ids": roster.id.tolist(),
            "realized_snapshot_total": realized_snapshot,
            "realized_tracked_total": float(roster.winner_actual.sum()),
            "n_artifacts": len(blocks),
            "audit": audit_roster_under_law(realized_snapshot, totals),
            "world_assignment": assignment,
        })

    report = winner_law_report(entries)
    report["manifest_path"] = str(args.manifest)
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":")).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(
        "WINNER_LAW_AUDIT_COMPLETE",
        f"protocol={PROTOCOL_ID}",
        f"winners={report['n_winners']}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
