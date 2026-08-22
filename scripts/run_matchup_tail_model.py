"""Run the walk-forward matchup tail model and the winner census.

Loads the canonical panel from `lineup_matchup_evidence` (single panel so
duplicate rosters across panels never inflate folds), runs LOSO
baseline-vs-matchup models for both targets, resolves the 68 registry
winners to GSIS ids, aggregates their lineup matchup features exactly
like 017s, and runs the same-slate winner census. Writes create-once
receipts. Exploratory tier; zero adoption authority.

Default-off: --execute plus MATCHUP_TAIL_MODEL_ENABLED=1.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ENABLE_ENV = "MATCHUP_TAIL_MODEL_ENABLED"
CANONICAL_PANEL = "20260811-pitclean-e80-k1-role12union-a12ab31"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=CANONICAL_PANEL)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute or os.environ.get(ENABLE_ENV) != "1":
        print(
            f"execution requires literal --execute and {ENABLE_ENV}=1",
            file=sys.stderr,
        )
        return 2
    outputs = {
        "model": args.output_dir / "model-run.json",
        "census": args.output_dir / "winner-census.json",
    }
    for path in outputs.values():
        if path.exists() or path.is_symlink():
            print(f"refused: output exists: {path}", file=sys.stderr)
            return 2

    import pandas as pd

    from nfl_dfs import bq
    from nfl_dfs.research.matchup_tail_model import (
        CENSUS_FEATURES,
        PRIMARY_TARGET,
        run_walk_forward,
        winner_census,
    )
    from nfl_dfs.research.real_winner_overlap import _name_matches
    from nfl_dfs.research.winner_registry import canonical_json_bytes

    features = bq.settings.features
    evidence = bq.query_df(
        f"SELECT * FROM `{features}.lineup_matchup_evidence` "
        "WHERE panel_run_id = @panel",
        {"panel": args.panel},
    )
    if evidence.empty:
        print("refused: panel has no evidence rows", file=sys.stderr)
        return 2

    receipts: dict[str, object] = {}
    for target in ("actual_ge_194", "actual_gt_200"):
        result = run_walk_forward(evidence, target=target)
        receipts[target] = result["receipt"]

    registry = json.loads(args.registry.read_text())
    pairs = sorted({
        (contest["season"], contest["week"])
        for contest in registry["contests"]
    })
    pair_predicate = " OR ".join(
        f"(season = {season} AND week = {week})" for season, week in pairs
    )
    matchup = bq.query_df(
        f"SELECT season, week, gsis_id, family, role_label, "
        f"matchup_edge_score, easy_matchup, qb_depth1 "
        f"FROM `{features}.player_matchup_week_pit` "
        f"WHERE {pair_predicate}"
    )
    names = bq.query_df(
        f"SELECT DISTINCT season, week, player_id, player_display_name "
        f"FROM `{bq.settings.raw}.weekly_stats` "
        f"WHERE position IN ('QB','RB','WR','TE') AND ({pair_predicate})"
    )
    winner_rows = []
    unresolved_total = 0
    for contest in registry["contests"]:
        season, week = contest["season"], contest["week"]
        week_names = names[
            (names["season"] == season) & (names["week"] == week)
        ]
        week_matchup = matchup[
            (matchup["season"] == season) & (matchup["week"] == week)
        ]
        resolved: list[str] = []
        for player in contest["players"]:
            if player["position"] not in ("QB", "RB", "WR", "TE"):
                continue
            matches = week_names[[
                _name_matches(player["name"], value)
                for value in week_names["player_display_name"]
            ]]
            if len(matches) == 1:
                resolved.append(str(matches.iloc[0]["player_id"]))
            else:
                unresolved_total += 1
        rows = week_matchup[week_matchup["gsis_id"].isin(resolved)]
        receiver = rows[rows["family"] == "receiver"]
        rb = rows[rows["family"] == "rb"]
        qb = rows[
            (rows["family"] == "qb")
            & (rows["qb_depth1"].fillna(True))
        ]
        record = {
            "season": season,
            "week": week,
            "resolved_skill_players": len(resolved),
            "receiver_edge_mean": receiver["matchup_edge_score"].mean(),
            "receiver_easy_count": float(
                receiver["easy_matchup"].fillna(False).sum()
            ),
            "wr1_easy_count": float((
                (receiver["role_label"] == "WR1")
                & receiver["easy_matchup"].fillna(False)
            ).sum()),
            "rb_edge_mean": rb["matchup_edge_score"].mean(),
            "rb_easy_count": float(
                rb["easy_matchup"].fillna(False).sum()
            ),
            "qb_edge": qb["matchup_edge_score"].max()
            if not qb.empty else None,
            "lineup_edge_mean": rows["matchup_edge_score"].mean(),
        }
        winner_rows.append(record)
    winner_frame = pd.DataFrame(winner_rows)
    census = winner_census(winner_frame, evidence)
    census["winner_registry_sha256"] = registry["winner_registry_sha256"]
    census["unresolved_player_total"] = unresolved_total
    census["panel_run_id"] = args.panel

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs["model"].write_bytes(canonical_json_bytes({
        "panel_run_id": args.panel,
        "targets": receipts,
    }) + b"\n")
    outputs["census"].write_bytes(canonical_json_bytes(census) + b"\n")
    print(json.dumps({
        "primary": {
            "folds": receipts[PRIMARY_TARGET]["fold_count"],
            "matchup_beats_baseline":
                receipts[PRIMARY_TARGET]["matchup_ap_beats_baseline_folds"],
        },
        "census_features": {
            name: census["per_feature"].get(name)
            for name in CENSUS_FEATURES
        },
        "winner_slates": census["winner_slates_evaluated"],
    }, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
