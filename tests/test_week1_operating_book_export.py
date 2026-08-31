from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.inference import prospective_generation_shadow_evaluation as shadow
from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference import week1_operating_book_export as export


LOCK_AT = "2026-09-13T17:00:00+00:00"


def _fixture() -> tuple[dict[str, object], list[dict[str, object]]]:
    positions = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST")
    selected = []
    bridge = []
    salaries = []
    source_ids = (
        ["boom-first-40-160"] * 64
        + ["ceiling-all-boom-0-200"] * 12
        + ["cross-law-40-100-60"] * 4
    )
    for entry_rank, source_id in enumerate(source_ids, start=1):
        roster = []
        for player_ordinal, position in enumerate(positions):
            dk_id = str(100_000 + entry_rank * 10 + player_ordinal)
            team = "AAA" if player_ordinal % 2 == 0 else "BBB"
            salary = 5_000
            roster.append(dk_id)
            bridge.append({
                "internal_player_id": f"internal-{dk_id}",
                "dk_draftable_id": dk_id,
                "gsis_id": None if position == "DST" else f"gsis-{dk_id}",
                "position": position,
                "team": team,
                "dst_team": team if position == "DST" else None,
                "salary": salary,
            })
            salaries.append({
                "draft_group_id": 151307,
                "dk_player_id": 200_000 + entry_rank * 10 + player_ordinal,
                "dk_draftable_id": int(dk_id),
                "display_name": f"Player {dk_id}",
                "position": position,
                "team_abbr": team,
                "salary": salary,
            })
        roster.sort()
        roster_sha = canonical_sha256(roster)
        selected.append({
            "entry_rank": entry_rank,
            "lineup_id": f"lineup-v1-{roster_sha}",
            "source_id": source_id,
            "source_role": "core" if entry_rank <= 64 else "tier2",
            "source_rank": entry_rank,
            "player_ids": roster,
            "roster_sha256": roster_sha,
        })
    materialization = {
        "authority_mode": "terminal-prelock-envelope",
        "k": 80,
        "slate_context": {
            "season": 2026,
            "week": 1,
            "draft_group_id": "151307",
            "run_id": "week1-test",
            "code_sha": "a" * 40,
            "slate_lock_at": LOCK_AT,
        },
        "player_identity_bridge": bridge,
        "selected_lineups": selected,
        "selected_lineup_ids_sha256": canonical_sha256([
            lineup["lineup_id"] for lineup in selected
        ]),
    }
    materialization["materialization_sha256"] = canonical_sha256(
        materialization
    )
    raw = shadow.canonical_json_bytes_v1(materialization)
    exact = {
        "identity": {
            "uri": "gs://test/prelock/week1-operating-book.json",
            "generation": "1",
            "sha256": shadow.canonical_sha256_v1(materialization),
            "bytes": len(raw),
        },
        "storage_created_at": "2026-09-11T17:00:00+00:00",
        "materialization": materialization,
    }
    return exact, salaries


def _patch_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        export,
        "validate_week1_operating_roster_materialization_v1",
        lambda value: value,
    )


def test_exact_book_projects_to_fixed_tier_counts_and_dk_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_validator(monkeypatch)
    exact, salaries = _fixture()
    result = export.build_week1_operating_book_export_v1(
        exact_book=exact, salary_rows=salaries
    )

    assert result["complete"] is True
    assert result["k"] == 80
    assert result["source_counts"] == {
        "boom-first-40-160": 64,
        "ceiling-all-boom-0-200": 12,
        "cross-law-40-100-60": 4,
    }
    assert len(result["lineups"]) == 80
    assert result["dk_csv"].splitlines()[0] == "QB,RB,RB,WR,WR,WR,TE,FLEX,DST"
    assert len(result["dk_csv"].splitlines()) == 81
    assert result["cap4_used"] is False
    assert result["tier3_used"] is False
    assert result["uses_realized_outcomes"] is False
    assert result["tuning_controls_accepted"] == []
    first = result["lineups"][0]
    assert [player["position"] for player in first["players"]] == [
        "QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST"
    ]


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "salary", "team"))
def test_salary_resolution_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    _patch_validator(monkeypatch)
    exact, salaries = _fixture()
    if mutation == "missing":
        salaries.pop()
    elif mutation == "duplicate":
        salaries.append(deepcopy(salaries[0]))
    elif mutation == "salary":
        salaries[0]["salary"] = 4_900
    else:
        salaries[0]["team_abbr"] = "CCC"
    with pytest.raises(export.Week1OperatingBookExportError):
        export.build_week1_operating_book_export_v1(
            exact_book=exact, salary_rows=salaries
        )


def test_exact_materialization_object_identity_is_recomputed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_validator(monkeypatch)
    exact, salaries = _fixture()
    exact["identity"]["sha256"] = "f" * 64
    with pytest.raises(
        export.Week1OperatingBookExportError, match="bind exact bytes"
    ):
        export.build_week1_operating_book_export_v1(
            exact_book=exact, salary_rows=salaries
        )
