from __future__ import annotations

from itertools import islice, product

import pandas as pd
import pytest

from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.inference import week1_a5_book_materializer as materializer
from nfl_dfs.inference.generation_exposure import canonical_sha256


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, list[list[str]]]:
    groups = (
        ("q", "QB", "AAA"),
        ("a", "RB", "AAA"),
        ("b", "RB", "BBB"),
        ("c", "WR", "AAA"),
        ("d", "WR", "BBB"),
        ("e", "WR", "CCC"),
        ("f", "TE", "AAA"),
        ("g", "RB", "AAA"),
        ("h", "DST", "CCC"),
    )
    rows: list[dict[str, object]] = []
    choices: list[list[str]] = []
    for group_index, (prefix, position, team) in enumerate(groups):
        group_choices = []
        for choice in range(4):
            player_id = f"{prefix}{choice}"
            group_choices.append(player_id)
            paid_id = 1_000 + group_index * 10 + choice
            rows.append(
                {
                    "pulled_at": "2026-09-10T12:01:43.749785+00:00",
                    "id": player_id,
                    "dk_player_id": paid_id,
                    "dk_draftable_id": 100_000 + paid_id,
                    "display_name": f"Player {paid_id}",
                    "team": team,
                    "pos": position,
                    "salary": 5_000,
                    "status": None,
                    "roster_status": pd.NA if position == "DST" else "ACT",
                }
            )
        choices.append(group_choices)
    rosters = [list(roster) for roster in islice(product(*choices), 100)]
    candidates = pd.DataFrame(
        {
            "players": [",".join(sorted(roster)) for roster in rosters],
            "book_rank": [rank if rank <= 80 else pd.NA for rank in range(1, 101)],
        }
    )
    by_id = {row["id"]: row for row in rows}
    csv_rows = [
        [str(by_id[player_id]["dk_player_id"]) for player_id in roster]
        for roster in rosters[:80]
    ]
    return pd.DataFrame(rows), candidates, csv_rows


def _ref(semantic_sha256: str, label: str) -> dict[str, object]:
    return {
        "artifact_identity": {
            "uri": (
                "gs://nfl-predictions-503414-raw/week1/prelock/"
                f"2026-w01/fixture/{label}.json"
            ),
            "generation": "1",
            "sha256": canonical_sha256(label),
            "bytes": 1,
        },
        "semantic_sha256": semantic_sha256,
    }


def _catalog_and_bridge(
    frame: pd.DataFrame,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    catalog = materializer.build_week1_paid_salary_catalog_v1(frame)
    catalog_ref = _ref(str(catalog["semantic_sha256"]), "catalog")
    bridge = materializer.build_week1_player_bridge_v1(
        frame,
        salary_catalog=catalog,
        salary_catalog_ref=catalog_ref,
    )
    bridge_ref = _ref(str(bridge["semantic_sha256"]), "bridge")
    return catalog, bridge, bridge_ref


def test_materializes_live_ranked_book_and_allows_five_player_stack() -> None:
    frame, candidates, csv_rows = _inputs()
    catalog, bridge, bridge_ref = _catalog_and_bridge(frame)
    lineups = materializer.lineups_from_ranked_csv_v1(
        frame=frame,
        candidates=candidates,
        csv_rows=csv_rows,
        rank_column="book_rank",
    )
    book = materializer.build_week1_book_materialization_v2(
        policy="P_CTRL",
        lineups=lineups,
        bridge=bridge,
        player_bridge_ref=bridge_ref,
    )

    assert capture.MAX_FROM_TEAM == 8
    assert len(catalog["players"]) == len(frame)
    assert len(bridge["players"]) == len(frame)
    assert len(book["entries"]) == 80
    assert book["entries"][0]["slot_dk_draftable_ids"] == [
        101_000,
        101_010,
        101_020,
        101_030,
        101_040,
        101_050,
        101_060,
        101_070,
        101_080,
    ]


def test_materializes_an_ordered_candidate_id_book() -> None:
    frame, candidates, _csv_rows = _inputs()
    _catalog, bridge, bridge_ref = _catalog_and_bridge(frame)
    lineup_ids = [
        f"lineup-v1-{canonical_sha256(row.split(','))}"
        for row in candidates.players.tolist()[:80]
    ]
    lineups = materializer.lineups_from_ordered_candidate_ids_v1(
        frame=frame,
        candidates=candidates,
        ordered_lineup_ids=list(reversed(lineup_ids)),
    )
    book = materializer.build_week1_book_materialization_v2(
        policy="P_MIX",
        lineups=lineups,
        bridge=bridge,
        player_bridge_ref=bridge_ref,
    )

    assert [row["lineup_id"] for row in book["entries"]] == list(
        reversed(lineup_ids)
    )


def test_inactive_salary_row_is_excluded_and_cannot_enter_a_book() -> None:
    frame, candidates, csv_rows = _inputs()
    frame.loc[frame.id == "q0", "status"] = "OUT"
    catalog = materializer.build_week1_paid_salary_catalog_v1(frame)

    assert 1_000 not in {row["player_id"] for row in catalog["players"]}
    with pytest.raises(
        materializer.Week1A5BookMaterializerError,
        match="leaves the exact player bridge",
    ):
        materializer.lineups_from_ranked_csv_v1(
            frame=frame,
            candidates=candidates,
            csv_rows=csv_rows,
            rank_column="book_rank",
        )
