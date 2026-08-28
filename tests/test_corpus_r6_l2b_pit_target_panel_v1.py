from __future__ import annotations

from argparse import Namespace
from hashlib import sha256
import json

import pandas as pd
import pytest

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as cloud
from nfl_dfs.research import corpus_r6_l2b_pit_target_panel_v1 as target
from scripts import materialize_corpus_r6_l2b_pit_target_panel_v1 as cli


def _identity(name: str) -> dict[str, object]:
    raw = name.encode("utf-8")
    return {
        "uri": f"gs://fixture/{name}",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _catalog() -> list[dict[str, object]]:
    return [
        {"id": "d0", "pos": "DST", "team": "D", "salary": 2_500},
        {"id": "q0", "pos": "QB", "team": "A", "salary": 6_000},
        {"id": "r0", "pos": "RB", "team": "A", "salary": 5_500},
        {"id": "t0", "pos": "TE", "team": "C", "salary": 4_000},
        {"id": "w0", "pos": "WR", "team": "B", "salary": 5_000},
    ]


def _later_source() -> dict[str, object]:
    return {
        "freeze_sha256": "f" * 64,
        "slates": [
            {
                "slate_id": f"{season}-w{week:02d}",
                "catalog": _catalog(),
            }
            for season, week in cloud.EXPECTED_SLATES
        ],
    }


def _frame() -> pd.DataFrame:
    rows = []
    for season, week in reversed(cloud.EXPECTED_SLATES):
        rows.extend((
            {
                "season": season,
                "week": week,
                "gsis_id": "w0",
                "team": "B",
                "position": "WR",
                "previous_state": "rotation",
                "injury_status": "Healthy",
            },
            {
                "season": season,
                "week": week,
                "gsis_id": "r0",
                "team": "A",
                "position": "RB",
                "previous_state": "primary",
                "injury_status": None,
            },
            {
                "season": season,
                "week": week,
                "gsis_id": "t0",
                "team": "C",
                "position": "TE",
                "previous_state": "unknown",
                "injury_status": "Questionable",
            },
        ))
    return pd.DataFrame(rows)


@pytest.fixture
def source_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cloud.later,
        "validate_source_freeze",
        lambda value, *, expected_freeze_sha256: dict(value),
    )


def _materialize(frame: pd.DataFrame) -> dict[str, object]:
    return target.materialize_catalog_spined_pit_target_panel_v1(
        later_source_freeze=_later_source(),
        later_source_freeze_identity=_identity("later-source.json"),
        score_free_source=frame,
        score_free_source_identity=_identity("pit-targets.parquet"),
    )


def test_materializer_uses_catalog_as_exact_ordered_spine(source_validator) -> None:
    result = _materialize(_frame().sample(frac=1, random_state=7))
    assert result["slate_count"] == 54
    assert result["source_identities"] == {
        "later-source-freeze": _identity("later-source.json"),
        "score-free-target-source": _identity("pit-targets.parquet"),
    }
    first = result["slates"][0]
    assert first["slate_id"] == "2023-w01"
    assert [row["gsis_id"] for row in first["players"]] == ["r0", "t0", "w0"]
    assert all(row["position"] not in {"QB", "DST"} for row in first["players"])


@pytest.mark.parametrize("field", ["actual_points", "target_share", "currentRole"])
def test_materializer_rejects_outcome_and_current_week_role_fields(
    source_validator, field: str,
) -> None:
    with pytest.raises(
        target.CorpusR6L2BPITTargetPanelV1Error,
        match="current-week role or outcome",
    ):
        _materialize(_frame().assign(**{field: 1}))


@pytest.mark.parametrize("mutation", ["missing", "extra", "team", "position"])
def test_materializer_rejects_every_catalog_misalignment(
    source_validator, mutation: str,
) -> None:
    frame = _frame()
    if mutation == "missing":
        frame = frame.drop(frame.index[0])
    elif mutation == "extra":
        extra = frame.iloc[[0]].assign(gsis_id="not-in-catalog")
        frame = pd.concat([frame, extra], ignore_index=True)
    elif mutation == "team":
        frame.loc[0, "team"] = "Z"
    else:
        frame.loc[0, "position"] = "RB"
    with pytest.raises(
        target.CorpusR6L2BPITTargetPanelV1Error,
        match="catalog spine",
    ):
        _materialize(frame)


def test_cli_exact_opens_inputs_and_writes_canonical_create_once(
    source_validator, tmp_path,
) -> None:
    source_path = tmp_path / "later-source.json"
    frame_path = tmp_path / "pit-targets.parquet"
    source_raw = json.dumps(_later_source(), sort_keys=True).encode("utf-8")
    source_path.write_bytes(source_raw)
    _frame().to_parquet(frame_path, index=False)
    frame_raw = frame_path.read_bytes()

    def write_identity(path, *, uri: str, raw: bytes):
        identity = {
            "uri": uri,
            "generation": "7",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        path.write_bytes(legal.canonical_json_bytes(identity))

    source_identity_path = tmp_path / "later-source.identity.json"
    frame_identity_path = tmp_path / "pit-targets.identity.json"
    write_identity(
        source_identity_path, uri="gs://fixture/later-source.json", raw=source_raw
    )
    write_identity(
        frame_identity_path, uri="gs://fixture/pit-targets.parquet", raw=frame_raw
    )
    output = tmp_path / "target-panel.json"
    args = Namespace(
        later_source=source_path,
        later_source_identity=source_identity_path,
        source_frame=frame_path,
        source_frame_identity=frame_identity_path,
        output=output,
    )
    result = cli.materialize(args)
    output_raw = output.read_bytes()
    assert output_raw == legal.canonical_json_bytes(json.loads(output_raw))
    assert result["slate_count"] == 54
    assert result["cloud_mutation_performed"] is False
    with pytest.raises(
        cli.MaterializeCorpusR6L2BPITTargetPanelV1Error,
        match="create-once publication refused",
    ):
        cli.materialize(args)
