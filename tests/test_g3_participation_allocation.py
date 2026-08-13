from pathlib import Path

import numpy as np
import pandas as pd

from nfl_dfs.analysis import g3_participation_allocation as g3
from nfl_dfs.analysis import usage_dirichlet_calibration as usage


def _group(index: int, kind: str = "targets") -> usage.UsageGroup:
    return usage.UsageGroup(
        season=2021,
        week=index,
        team=f"T{index}",
        kind=kind,
        players=("a", "b", "c"),
        probabilities=np.asarray([0.6, 0.3, 0.1]),
        observed=np.asarray([18, 9, 3]),
    )


def test_cooccurrence_adds_actor_context_bonus():
    players = ";".join(f"00-{index:07d}" for index in range(11))
    participation = pd.DataFrame({
        "nflverse_game_id": ["2020_01_A_B"],
        "play_id": [1],
        "offense_players": [players],
        "n_offense": [11],
    })
    pbp = pd.DataFrame({
        "game_id": ["2020_01_A_B"],
        "play_id": [1.0],
        "passer_player_id": ["00-0000000"],
        "receiver_player_id": ["00-0000001"],
        "rusher_player_id": [None],
    })
    edges, audit = g3.build_season_cooccurrence(participation, pbp)
    assert edges[("00-0000000", "00-0000001")] == 7.0
    assert edges[("00-0000000", "00-0000002")] == 4.0
    assert edges[("00-0000002", "00-0000003")] == 1.0
    assert audit["undirected_edges"] == 55


def test_group_geometry_falls_back_below_mass_floor():
    group = _group(1)
    embeddings = {
        "a": np.asarray([1.0, 0.0]),
        "c": np.asarray([0.0, 1.0]),
    }
    geometry = g3.group_geometry(group, embeddings)
    assert not geometry.valid
    assert geometry.known_players == 2
    assert np.isclose(geometry.known_probability_mass, 0.7)
    assert g3.group_k(9.0, 1.0, geometry.valid) == g3.GLOBAL_K


def test_group_geometry_is_weighted_dispersion():
    group = _group(1)
    embeddings = {
        "a": np.asarray([1.0, 0.0]),
        "b": np.asarray([0.0, 1.0]),
        "c": np.asarray([-1.0, 0.0]),
    }
    geometry = g3.group_geometry(group, embeddings)
    assert geometry.valid
    assert geometry.dispersion > 0
    assert np.isclose(geometry.known_probability_mass, 1.0)


def test_beta_fit_uses_calibration_likelihood_and_regularization():
    rng = np.random.default_rng(20260813)
    records = []
    for index in range(500):
        z = -1.0 if index % 2 == 0 else 1.0
        probabilities = np.asarray([0.55, 0.30, 0.15])
        true_k = g3.group_k(z, 0.8)
        share = rng.dirichlet(true_k * probabilities)
        group = usage.UsageGroup(
            season=2021,
            week=index,
            team=f"T{index}",
            kind="targets",
            players=("a", "b", "c"),
            probabilities=probabilities,
            observed=rng.multinomial(35, share),
        )
        records.append({"z": z, "geometry_valid": True, "group": group})
    fitted = g3.fit_beta(pd.DataFrame(records))
    assert fitted["optimizer_success"]
    assert 0.3 < fitted["beta"] < 1.3


def test_cli_and_immutable_runners_are_packaged():
    root = Path(__file__).resolve().parents[1]
    cli = (root / "src/nfl_dfs/cli.py").read_text()
    assert "g3-participation-allocation" in cli
    for name in (
        "cloud_g3_participation_allocation.sh",
        "cloud_harvest_g3_participation_allocation.sh",
    ):
        assert (root / "scripts" / name).is_file()

