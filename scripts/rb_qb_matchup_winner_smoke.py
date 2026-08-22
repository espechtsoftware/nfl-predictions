"""Winner-slate halves of the RB and QB family freeze gates.

Resolves the governed winner's RB and QB players against that week's
rows, verifies their annotation rows in the published task-0 RB/QB
objects, checks the QB starter gate (017r `qb_depth1`) for the winner's
QB, and writes the combined freeze receipt. The QB family freezes WITH a
codified condition: analysis-grade use must apply the depth-QB1 starter
gate, since components are team-level.

Default-off: --execute plus RECEIVER_MATCHUP_ANNOTATIONS_ENABLED=1.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ENABLE_ENV = "RECEIVER_MATCHUP_ANNOTATIONS_ENABLED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--smoke-dir", type=Path, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute or os.environ.get(ENABLE_ENV) != "1":
        print(
            f"execution requires literal --execute and {ENABLE_ENV}=1",
            file=sys.stderr,
        )
        return 2
    if args.output.exists() or args.output.is_symlink():
        print(f"refused: output exists: {args.output}", file=sys.stderr)
        return 2

    from nfl_dfs import bq
    from nfl_dfs.research.real_winner_overlap import _name_matches
    from nfl_dfs.research.rb_qb_matchup_annotations import (
        qb_matchup_family_v1,
        rb_matchup_family_v1,
    )
    from nfl_dfs.research.receiver_matchup_contract import (
        canonical_json_bytes,
        canonical_sha256,
        validate_annotation_bytes,
    )
    from nfl_dfs.research.winner_registry import registry_contest

    registry = json.loads(args.registry.read_text())
    contest = registry_contest(registry, args.season, args.week)
    smoke_receipt = json.loads(
        (args.smoke_dir / "rb-qb-smoke-receipt.json").read_text()
    )

    week_players = bq.query_df(
        f"SELECT DISTINCT player_id, player_display_name, position "
        f"FROM `{bq.settings.raw}.weekly_stats` "
        "WHERE season = @season AND week = @week "
        "AND position IN ('QB', 'RB')",
        {"season": args.season, "week": args.week},
    ).to_dict("records")

    families = {
        "rb": {
            "family": rb_matchup_family_v1(provisional=True),
            "frozen": rb_matchup_family_v1(provisional=False),
            "annotation": args.smoke_dir / "rb-annotation.json",
            "positions": ("RB",),
        },
        "qb": {
            "family": qb_matchup_family_v1(provisional=True),
            "frozen": qb_matchup_family_v1(provisional=False),
            "annotation": args.smoke_dir / "qb-annotation.json",
            "positions": ("QB",),
        },
    }
    results: dict[str, object] = {}
    all_frozen = True
    starter_gate: dict[str, object] = {}
    for name, spec in families.items():
        annotation = validate_annotation_bytes(
            spec["annotation"].read_bytes(),
            expected_family=spec["family"],
            require_analysis_grade=False,
        )
        rows_by_id = {
            row["player_id"]: row for row in annotation["rows"]
        }
        winners = [
            player for player in contest["players"]
            if player["position"] in spec["positions"]
        ]
        resolutions = []
        unresolved = 0
        uncovered = 0
        for player in winners:
            matches = [
                row for row in week_players
                if row["position"] in spec["positions"]
                and _name_matches(player["name"], row["player_display_name"])
            ]
            record: dict[str, object] = {"winner_name": player["name"]}
            if len(matches) != 1:
                record["resolution"] = (
                    "unresolved" if not matches else "ambiguous"
                )
                unresolved += 1
                resolutions.append(record)
                continue
            gsis_id = str(matches[0]["player_id"])
            record["resolution"] = "resolved"
            record["gsis_id"] = gsis_id
            row = rows_by_id.get(gsis_id)
            if row is None:
                record["annotated"] = False
                uncovered += 1
            else:
                record["annotated"] = True
                record["values"] = {
                    key: row["values"][key]
                    for key in ("matchup_edge_score",
                                "matchup_component_count")
                }
            resolutions.append(record)
            if name == "qb":
                depth = bq.query_df(
                    f"SELECT qb_depth1 FROM "
                    f"`{bq.settings.features}.player_matchup_week_pit` "
                    "WHERE season = @season AND week = @week "
                    "AND family = 'qb' AND gsis_id = @gsis",
                    {"season": args.season, "week": args.week,
                     "gsis": gsis_id},
                ).to_dict("records")
                starter_gate = {
                    "winner_qb_gsis_id": gsis_id,
                    "qb_depth1": (
                        bool(depth[0]["qb_depth1"]) if depth else None
                    ),
                }
        frozen = unresolved == 0 and uncovered == 0
        all_frozen = all_frozen and frozen
        results[name] = {
            "winner_player_count": len(winners),
            "resolved_count": len(winners) - unresolved,
            "annotated_count": len(winners) - unresolved - uncovered,
            "resolutions": resolutions,
            "provisional_family_definition_sha256": spec[
                "family"
            ].definition_payload()["family_definition_sha256"],
            "frozen_family_definition_sha256": spec[
                "frozen"
            ].definition_payload()["family_definition_sha256"],
            "frozen": frozen,
        }
    receipt = {
        "schema_version": "rb-qb-matchup-family-freeze/v1",
        "slate_key": contest["slate_key"],
        "winner_registry_sha256": registry["winner_registry_sha256"],
        "task0_smoke_receipt_sha256": smoke_receipt[
            "smoke_receipt_sha256"
        ],
        "families": results,
        "qb_starter_gate": {
            **starter_gate,
            "codified_condition": (
                "qb-matchup analysis-grade use MUST apply the 017r "
                "qb_depth1 starter gate; team-level components give "
                "backup QBs the starter's edge otherwise"
            ),
        },
        "frozen": all_frozen,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    receipt["freeze_receipt_sha256"] = canonical_sha256(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(receipt) + b"\n")
    print(json.dumps({
        "frozen": receipt["frozen"],
        "rb": results["rb"]["annotated_count"],
        "qb": results["qb"]["annotated_count"],
        "qb_depth1": starter_gate.get("qb_depth1"),
    }, sort_keys=True))
    return 0 if receipt["frozen"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
