from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models.components import COMPONENT_NAMES
from nfl_dfs.research.corpus_r6_belief_evidence_v1 import (
    L1_BANK_MANIFEST_SCHEMA,
)
from nfl_dfs.research.corpus_r6_l1_conditional_shards_v1 import (
    COMPONENT_COLUMNS,
    EXPECTED_SLATE_COUNT,
    EXPECTED_WEEK_COUNTS,
    L1ConditionalShardError,
    component_surface_preflight_v1,
    materialize_l1_conditional_shards_v1,
    validate_l1_component_surface_v1,
)


def _identity() -> dict[str, object]:
    return {
        "uri": "gs://belief/l1-component-surface.parquet",
        "generation": "17",
        "sha256": "a" * 64,
        "bytes": 123456,
    }


def _component_values(position: str) -> dict[str, float]:
    values = {
        "targets": 7.0,
        "catch_rate": 0.65,
        "ypr": 11.0,
        "rec_tds": 0.35,
        "carries": 1.0,
        "ypc": 4.2,
        "rush_tds": 0.08,
        "pass_attempts": 0.0,
        "ypa": 7.2,
        "pass_tds": 0.0,
        "interceptions": 0.0,
    }
    if position == "QB":
        values.update({
            "targets": 0.0,
            "rec_tds": 0.0,
            "carries": 4.0,
            "pass_attempts": 34.0,
            "pass_tds": 1.8,
            "interceptions": 0.7,
        })
    elif position == "RB":
        values.update({"targets": 4.0, "carries": 14.0})
    elif position == "TE":
        values.update({"targets": 5.0})
    return {
        f"component_mean_{name}": values[name] for name in COMPONENT_NAMES
    }


def _surface() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for season, week_count in EXPECTED_WEEK_COUNTS.items():
        for week in range(1, week_count + 1):
            game_id = f"{season}_{week:02d}_A_B"
            for team, opponent in (("A", "B"), ("B", "A")):
                for position in ("QB", "RB", "WR", "TE"):
                    rows.append({
                        "gsis_id": f"p-{season}-{week:02d}-{team}-{position}",
                        "season": season,
                        "week": week,
                        "pos": position,
                        "team": team,
                        "opp": opponent,
                        "game_id": game_id,
                        "game_total": 48.0,
                        **_component_values(position),
                    })
    return pd.DataFrame(rows)


def test_component_surface_preflight_and_validation_cover_exact_53_slates():
    surface = _surface().sample(frac=1.0, random_state=7)
    preflight = component_surface_preflight_v1(
        surface, source_identity=_identity()
    )
    assert preflight["ready"] is True
    assert preflight["slate_count"] == EXPECTED_SLATE_COUNT
    assert preflight["complete_component_row_count"] == len(surface)
    assert preflight["uses_player_outcomes"] is False
    validated, replay = validate_l1_component_surface_v1(
        surface, source_identity=_identity()
    )
    assert replay == preflight
    assert len(validated) == len(surface)
    assert validated.iloc[0].season == 2019


def test_all_null_legacy_component_surface_fails_with_actionable_message():
    surface = _surface()
    surface.loc[:, list(COMPONENT_COLUMNS)] = np.nan
    preflight = component_surface_preflight_v1(
        surface, source_identity=_identity()
    )
    assert preflight["ready"] is False
    assert preflight["complete_component_row_count"] == 0
    assert set(preflight["nonnull_rows_by_component"].values()) == {0}
    with pytest.raises(
        L1ConditionalShardError,
        match="final player worlds and mean_projection cannot reconstruct",
    ):
        validate_l1_component_surface_v1(
            surface, source_identity=_identity()
        )


def test_component_surface_rejects_game_mapping_and_position_masks():
    surface = _surface()
    surface.loc[0, "opp"] = "C"
    with pytest.raises(L1ConditionalShardError, match="opponent mapping"):
        validate_l1_component_surface_v1(
            surface, source_identity=_identity()
        )
    surface = _surface()
    qb = surface["pos"].eq("QB")
    surface.loc[qb, "component_mean_targets"] = 1.0
    with pytest.raises(L1ConditionalShardError, match="QB receiving"):
        validate_l1_component_surface_v1(
            surface, source_identity=_identity()
        )


def test_materializer_emits_loadable_exact_shards_and_receipts(tmp_path: Path):
    output = tmp_path / "l1-shards"
    result = materialize_l1_conditional_shards_v1(
        component_surface=_surface(),
        component_surface_identity=_identity(),
        output_dir=output,
        n_sims=100,
        base_seed=41,
        usage_dirichlet_k=20.0,
    )
    assert result.manifest["schema"] == L1_BANK_MANIFEST_SCHEMA
    assert len(result.manifest["shards"]) == EXPECTED_SLATE_COUNT
    assert result.receipt["slate_count"] == EXPECTED_SLATE_COUNT
    assert result.receipt["uses_player_outcomes"] is False
    manifest = json.loads((output / "l1-bank-manifest.json").read_text())
    first = manifest["shards"][0]
    with np.load(first["path"], allow_pickle=False) as bank:
        assert bank.files == [
            "player_ids", "ordinary_draws", "shootout_draws"
        ]
        assert bank["ordinary_draws"].shape == (8, 100)
        assert bank["shootout_draws"].shape == (8, 100)
        assert not np.array_equal(
            bank["ordinary_draws"], bank["shootout_draws"]
        )
    receipt = json.loads(
        (output / "2019-w01.receipt.json").read_text()
    )
    assert receipt["npz_identity"] == first["source_identity"]
    assert receipt["component_receipt"]["calibration_labels_read"] is False
    assert len(list(output.glob("*.npz"))) == EXPECTED_SLATE_COUNT
