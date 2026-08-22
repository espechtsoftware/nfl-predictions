"""Winner-slate half of the receiver-matchup P3 freeze gate.

Loads the canonical winner registry, resolves one governed winner's
WR/TE receivers to GSIS ids against that week's player rows (fail-closed
on ambiguity; nothing is guessed), verifies each resolved receiver's row
in the already-published task-0 annotation object, and writes the family
FREEZE receipt binding: both smoke halves, the exact maximum-source
derivation, the provisional and frozen family-definition hashes, and the
annotation/registry identities. Outcome-blind for annotation content:
winner rosters are historical identities used to SELECT which rows to
inspect; no outcome value influences any annotation.

Default-off: requires --execute and RECEIVER_MATCHUP_ANNOTATIONS_ENABLED=1.
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
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--smoke-receipt", type=Path, required=True)
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
    from nfl_dfs.research.receiver_matchup_contract import (
        canonical_json_bytes,
        canonical_sha256,
        receiver_matchup_family_v1,
        validate_annotation_bytes,
    )
    from nfl_dfs.research.winner_registry import registry_contest

    registry = json.loads(args.registry.read_text())
    contest = registry_contest(registry, args.season, args.week)
    receivers = [
        player for player in contest["players"]
        if player["position"] in ("WR", "TE")
    ]
    if not receivers:
        print("refused: winner roster has no WR/TE", file=sys.stderr)
        return 2

    annotation_raw = args.annotation.read_bytes()
    provisional = receiver_matchup_family_v1(provisional=True)
    annotation = validate_annotation_bytes(
        annotation_raw,
        expected_family=provisional,
        require_analysis_grade=False,
    )
    if (
        annotation["slate_id"] != contest["slate_key"]
    ):
        print("refused: annotation slate differs from contest", file=sys.stderr)
        return 2
    rows_by_id = {row["player_id"]: row for row in annotation["rows"]}

    week_players = bq.query_df(
        f"SELECT DISTINCT player_id, player_display_name, team "
        f"FROM `{bq.settings.raw}.weekly_stats` "
        "WHERE season = @season AND week = @week "
        "AND position IN ('WR', 'TE')",
        {"season": args.season, "week": args.week},
    ).to_dict("records")

    resolutions = []
    unresolved = 0
    uncovered = 0
    for receiver in receivers:
        matches = [
            row for row in week_players
            if _name_matches(receiver["name"], row["player_display_name"])
        ]
        record: dict[str, object] = {
            "winner_name": receiver["name"],
            "position": receiver["position"],
        }
        if len(matches) != 1:
            record["resolution"] = (
                "unresolved" if not matches else "ambiguous"
            )
            record["match_count"] = len(matches)
            unresolved += 1
            resolutions.append(record)
            continue
        gsis_id = str(matches[0]["player_id"])
        record["resolution"] = "resolved"
        record["gsis_id"] = gsis_id
        record["team"] = str(matches[0]["team"])
        row = rows_by_id.get(gsis_id)
        if row is None:
            record["annotated"] = False
            uncovered += 1
        else:
            values = row["values"]
            record["annotated"] = True
            record["matchup_edge_score"] = values["matchup_edge_score"]
            record["matchup_component_count"] = values[
                "matchup_component_count"
            ]
            record["easy_coverage_v1"] = values["easy_coverage_v1"]
            record["role_label"] = values["role_label"]
            record["missing_reasons"] = row["missing"]
        resolutions.append(record)

    smoke_receipt = json.loads(args.smoke_receipt.read_text())
    frozen = receiver_matchup_family_v1(provisional=False)
    receipt = {
        "schema_version": "receiver-matchup-family-freeze/v1",
        "task0_half": {
            "smoke_receipt_sha256": smoke_receipt["smoke_receipt_sha256"],
            "annotation_object_sha256": smoke_receipt[
                "annotation_object_sha256"
            ],
            "row_count": smoke_receipt["row_count"],
            "rows_with_edge": smoke_receipt["rows_with_edge"],
            "easy_coverage_true_count": smoke_receipt[
                "easy_coverage_true_count"
            ],
        },
        "winner_half": {
            "winner_registry_sha256": registry["winner_registry_sha256"],
            "slate_key": contest["slate_key"],
            "governed_cohort": contest["governed_cohort"],
            "receiver_count": len(receivers),
            "resolved_count": len(receivers) - unresolved,
            "unresolved_or_ambiguous_count": unresolved,
            "annotated_count": (
                len(receivers) - unresolved - uncovered
            ),
            "resolutions": resolutions,
        },
        "maximum_source_derivation": {
            "claimed_maximum_source_time_utc": annotation[
                "maximum_source_time_utc"
            ],
            "derivation": (
                "all strictly-prior source games end before the prior "
                "week's Tuesday; week-1 sources are prior-season games "
                "ending 2023-02; the week-of depth chart and prior-window "
                "vendor files publish before the Sunday lock; the claimed "
                "bound therefore upper-bounds every consumed source"
            ),
        },
        "provisional_family_definition_sha256": (
            provisional.definition_payload()["family_definition_sha256"]
        ),
        "frozen_family_definition_sha256": (
            frozen.definition_payload()["family_definition_sha256"]
        ),
        "frozen": unresolved == 0 and uncovered == 0,
        "freeze_law": (
            "the family may be used analysis-grade "
            "(provisional=False) only while this receipt's frozen flag "
            "is true; component and easy-coverage laws are unchanged "
            "from the provisional definition"
        ),
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    receipt["freeze_receipt_sha256"] = canonical_sha256(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(receipt) + b"\n")
    print(json.dumps({
        "frozen": receipt["frozen"],
        "resolved": receipt["winner_half"]["resolved_count"],
        "annotated": receipt["winner_half"]["annotated_count"],
        "receiver_count": len(receivers),
    }, sort_keys=True))
    return 0 if receipt["frozen"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
