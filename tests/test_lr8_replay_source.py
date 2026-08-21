from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import lr8_replay_source as source
from nfl_dfs.research import lr8_training_source as training


def _receipt(name: str) -> dict[str, object]:
    uri = f"gs://lr8-replay-test/{name}"
    raw = uri.encode("utf-8")
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _players(week: int) -> tuple[dict[str, object], ...]:
    rows = (
        ("qb", "QB", "A", "B", "g1"),
        ("rb1", "RB", "A", "B", "g1"),
        ("rb2", "RB", "C", "D", "g2"),
        ("wr1", "WR", "A", "B", "g1"),
        ("wr2", "WR", "B", "A", "g1"),
        ("wr3", "WR", "C", "D", "g2"),
        ("wr4", "WR", "D", "C", "g2"),
        ("te", "TE", "B", "A", "g1"),
        ("dst", "DST", "C", "D", "g2"),
    )
    return tuple({
        "id": f"w{week}-{name}",
        "pos": position,
        "team": team,
        "opp": opponent,
        "game_id": f"w{week}-{game}",
        "salary": 5_000,
    } for name, position, team, opponent, game in rows)


def _audited_slates() -> tuple[source.AuditedReplaySlate, ...]:
    output = []
    for week in (1, 2):
        players = _players(week)
        output.append(source.AuditedReplaySlate(
            season=2019,
            week=week,
            players=tuple(reversed(players)),
            catalog_sha256=training.catalog_sha256(players),
            dst_mean_projection={f"w{week}-dst": 5.25 + week},
            replay_source_receipts=(_receipt(f"worlds/r0/2019/{week}"),),
        ))
    return tuple(output)


def _panel() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for season in training.MODEL_TRAINING_SEASONS[2019]:
        rows.append({
            "season": season,
            "week": 1,
            "gsis_id": f"prior-{season}",
            "position": "QB",
            "y_dk_points": 20.0,
            "y_targets": 0.0,
            "actual": 20.0,
            "was_active": True,
        })
    for week in (1, 2):
        for player in _players(week):
            if player["pos"] == "DST":
                continue
            rows.append({
                "season": 2019,
                "week": week,
                "gsis_id": player["id"],
                "position": player["pos"],
                "y_dk_points": np.nan,
                "y_targets": np.nan,
                "actual": np.nan,
                "was_active": np.nan,
            })
    return pd.DataFrame(rows)


def _projected(panel: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    frame = panel[panel.season == 2019][
        ["gsis_id", "season", "week", "position"]
    ].iloc[::-1].reset_index(drop=True)
    draws = np.stack([
        np.full(training.WORLDS_PER_BLOCK, index + 0.25, dtype=np.float32)
        for index in range(len(frame))
    ])
    return frame, draws


def _setup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(source, "EXPECTED_WEEKS", {2019: (1, 2)})
    panel = _panel()
    slates = _audited_slates()
    calls: list[dict[str, object]] = []

    def project(arg_panel, **kwargs):
        assert arg_panel is panel
        calls.append(kwargs)
        return _projected(arg_panel)

    def forbidden(*args, **kwargs):
        raise AssertionError("build_slates must not run")

    monkeypatch.setattr(source.replay, "replay_projections", project)
    monkeypatch.setattr(source.replay, "build_slates", forbidden)
    return panel, slates, calls


def _build(
    panel,
    slates,
    *,
    block="R0",
    provenance=None,
):
    return source.materialize_baseline_replay_block(
        panel,
        slates,
        target_season=2019,
        block=block,
        model_fit_input_sha256="1" * 64,
        model_fit_sha256="2" * 64,
        fit_source_receipts=(_receipt("fit/2019"),),
        provenance=provenance or source.ReplaySourceProvenance(),
    )


def test_materializes_aligned_skill_and_static_dst_worlds(monkeypatch):
    panel, slates, calls = _setup(monkeypatch)
    block = _build(panel, slates)
    assert len(calls) == 1
    assert calls[0] == {
        "season": 2019,
        "n_sims": 10_000,
        "num_boost_round": 400,
        "seed": 0,
        "widen": True,
        "return_draws": True,
        "include_actual": False,
    }
    assert block.target_season == 2019
    assert block.block == "R0"
    assert block.projection_seed == 0
    assert block.source_environment_role_seed_nonoperative == 7331
    assert block.replay_path_id == training.PIT_REPLAY_PATH_ID
    assert block.model_training_seasons == (2015, 2016, 2017, 2018)
    assert block.target_player_labels_read is False
    assert block.candidate_labels_read is False
    assert block.role_belief_worlds_used is False
    assert len(block.slates) == 2

    projected, raw_draws = _projected(panel)
    raw_by_id = {
        row.gsis_id: raw_draws[index]
        for index, row in enumerate(projected.itertuples(index=False))
    }
    for slate in block.slates:
        assert slate.player_ids == tuple(sorted(
            str(player["id"]) for player in _players(slate.week)
        ))
        assert slate.player_draws.shape == (9, 10_000)
        assert slate.player_draws.dtype == np.float32
        assert slate.player_draws.flags.writeable is False
        assert slate.player_ids_sha256 == training.player_ids_sha256(
            slate.player_ids
        )
        assert slate.player_draws_sha256 == training.array_sha256(
            slate.player_draws
        )
        by_id = {
            player_id: slate.player_draws[index]
            for index, player_id in enumerate(slate.player_ids)
        }
        dst = by_id[f"w{slate.week}-dst"]
        assert np.array_equal(
            dst,
            np.full(10_000, 5.25 + slate.week, dtype=np.float32),
        )
        for player_id, values in by_id.items():
            if player_id.endswith("-dst"):
                continue
            assert np.array_equal(values, raw_by_id[player_id])


def test_registered_projection_seeds_are_deterministic(monkeypatch):
    panel, slates, calls = _setup(monkeypatch)
    r0_first = _build(panel, slates, block="R0")
    r0_second = _build(panel, slates, block="R0")
    r1 = _build(panel, slates, block="R1")
    assert [call["seed"] for call in calls] == [0, 0, 1137260708]
    assert [slate.player_draws_sha256 for slate in r0_first.slates] == [
        slate.player_draws_sha256 for slate in r0_second.slates
    ]
    assert r1.projection_seed == 1137260708
    assert r1.source_environment_role_seed_nonoperative == 2690847602


@pytest.mark.parametrize("column", [
    "y_dk_points", "y_targets", "actual", "was_active",
])
def test_target_nonnull_outcome_is_poison(monkeypatch, column):
    panel, slates, calls = _setup(monkeypatch)
    target_index = panel.index[panel.season == 2019][0]
    panel.loc[target_index, column] = 1.0
    with pytest.raises(source.LR8ReplaySourceError, match="absent or null"):
        _build(panel, slates)
    assert calls == []


@pytest.mark.parametrize("field", [
    "target_player_labels_read",
    "candidate_labels_read",
    "build_slates_used",
    "dst_correlated_draws_used",
    "role_belief_worlds_used",
    "b1_inputs_used",
    "a2a_inputs_used",
    "later_period_inputs_used",
])
def test_provenance_firewalls_are_literal_false(monkeypatch, field):
    panel, slates, calls = _setup(monkeypatch)
    provenance = replace(
        source.ReplaySourceProvenance(), **{field: True}
    )
    with pytest.raises(source.LR8ReplaySourceError, match=field):
        _build(panel, slates, provenance=provenance)
    assert calls == []


def test_target_outcome_fields_read_must_be_empty(monkeypatch):
    panel, slates, calls = _setup(monkeypatch)
    provenance = replace(
        source.ReplaySourceProvenance(),
        target_outcome_fields_read=("y_dk_points",),
    )
    with pytest.raises(
        source.LR8ReplaySourceError, match="target_outcome_fields_read"
    ):
        _build(panel, slates, provenance=provenance)
    assert calls == []


@pytest.mark.parametrize("mode", ["missing", "extra", "position"])
def test_target_skill_universe_and_alignment_are_exact(monkeypatch, mode):
    panel, slates, calls = _setup(monkeypatch)
    target = panel.index[panel.season == 2019]
    if mode == "missing":
        panel.drop(index=target[0], inplace=True)
    elif mode == "extra":
        row = dict(panel.loc[target[0]])
        row["gsis_id"] = "extra-player"
        panel.loc[len(panel)] = row
    else:
        panel.loc[target[0], "position"] = "TE"
    with pytest.raises(
        source.LR8ReplaySourceError, match="skill universe/alignment"
    ):
        _build(panel, slates)
    assert calls == []


@pytest.mark.parametrize("mode", ["missing", "extra", "position"])
def test_replay_skill_universe_and_alignment_are_exact(monkeypatch, mode):
    panel, slates, calls = _setup(monkeypatch)

    def poisoned(arg_panel, **kwargs):
        calls.append(kwargs)
        frame, draws = _projected(arg_panel)
        if mode == "missing":
            return frame.iloc[1:].reset_index(drop=True), draws[1:]
        if mode == "extra":
            extra = frame.iloc[[0]].copy()
            extra["gsis_id"] = "extra-player"
            return (
                pd.concat([frame, extra], ignore_index=True),
                np.concatenate([draws, draws[[0]]], axis=0),
            )
        frame.loc[0, "position"] = "QB" if frame.loc[0, "position"] != "QB" else "TE"
        return frame, draws

    monkeypatch.setattr(source.replay, "replay_projections", poisoned)
    with pytest.raises(
        source.LR8ReplaySourceError, match="replay skill universe/alignment"
    ):
        _build(panel, slates)
    assert len(calls) == 1


def test_score_free_replay_may_not_return_actual(monkeypatch):
    panel, slates, _ = _setup(monkeypatch)

    def poisoned(arg_panel, **kwargs):
        frame, draws = _projected(arg_panel)
        frame["actual"] = 0.0
        return frame, draws

    monkeypatch.setattr(source.replay, "replay_projections", poisoned)
    with pytest.raises(source.LR8ReplaySourceError, match="returned actual"):
        _build(panel, slates)


def test_dst_static_projection_keys_and_values_are_exact(monkeypatch):
    panel, slates, calls = _setup(monkeypatch)
    missing = replace(slates[0], dst_mean_projection={})
    with pytest.raises(source.LR8ReplaySourceError, match="keys differ"):
        _build(panel, (missing, slates[1]))
    nonfinite = replace(
        slates[0], dst_mean_projection={"w1-dst": np.nan}
    )
    with pytest.raises(source.LR8ReplaySourceError, match="must be finite"):
        _build(panel, (nonfinite, slates[1]))
    string_value = replace(
        slates[0], dst_mean_projection={"w1-dst": "6.25"}
    )
    with pytest.raises(source.LR8ReplaySourceError, match="must be numeric"):
        _build(panel, (string_value, slates[1]))
    assert calls == []


def test_mixed_panel_rejects_missing_prior_or_later_season(monkeypatch):
    panel, slates, calls = _setup(monkeypatch)
    missing = panel[panel.season != 2015].copy()
    with pytest.raises(source.LR8ReplaySourceError, match="seasons differ"):
        _build(missing, slates)
    later = pd.concat([
        panel,
        pd.DataFrame([{
            "season": 2023,
            "week": 1,
            "gsis_id": "later",
            "position": "QB",
        }]),
    ], ignore_index=True)
    with pytest.raises(source.LR8ReplaySourceError, match="seasons differ"):
        _build(later, slates)
    assert calls == []
