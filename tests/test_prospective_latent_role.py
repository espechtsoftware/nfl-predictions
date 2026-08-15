import itertools

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference import prospective_latent_role as prospective
from nfl_dfs.optimizer.lineup import Lineup


def _seed_receipts():
    output = {}
    for label in ("R0", "R1", "R2", "R3", "R4"):
        optimization = []
        for index in range(12):
            optimization.append({
                "scenario": f"s{index}",
                "kind": "promotion" if index < 4 else "sampled",
                "disposition": "accepted",
                "roster_sha256": f"{index + 1:064x}",
                "error_type": None,
            })
        output[label] = {
            "latent_scenario_receipt": {
                "uses_realized_outcomes": False,
                "uses_fantasy_or_lineup_outcomes": False,
                "source_label": label,
                "promotion_scenarios": 4,
                "sampled_cap_valid_scenarios": 8,
            },
            "latent_optimization_receipt": optimization,
        }
    return output


def _batch(*, treatment=False):
    players = tuple({
        "id": index,
        "gsis_id": f"g{index}",
        "pos": "WR",
        "team": f"T{index % 4}",
        "opp": f"T{(index + 1) % 4}",
        "salary": 5_000,
        "proj": 10.0,
    } for index in range(20))
    combinations = list(itertools.islice(
        itertools.combinations(range(20), 9),
        80 if not treatment else 160,
    ))
    if treatment:
        combinations = combinations[80:160]
    lineups = tuple(Lineup([players[index] for index in roster], tag="lev") for roster in combinations)
    row_draws = np.add.outer(
        np.arange(20, dtype=np.float32), np.arange(4, dtype=np.float32),
    )
    totals = np.stack([
        row_draws[list(lineup.ids)].sum(axis=0) for lineup in lineups
    ]).astype(np.float32)
    metadata = {"portfolio": "CBWU"}
    if treatment:
        metadata = {
            "portfolio": "CBWU_LATENT_ROLE_SHADOW",
            "uses_realized_outcomes": False,
            "latent_seed_receipts": _seed_receipts(),
        }
    return CandidateBatch(
        candidates=lineups,
        candidate_totals=totals,
        player_ids=tuple(range(20)),
        player_rows=players,
        row_draws=row_draws,
        all_tags={lineup.ids: ("lev",) for lineup in lineups},
        metadata=metadata,
    )


class _Store:
    def classic_salaries(self, draft_group_id):
        return pd.DataFrame({
            "dk_player_id": range(20),
            "dk_draftable_id": np.arange(20) + 1000,
            "salary": 5_000,
        })


class _Blob:
    def __init__(self):
        self.calls = []

    def upload_from_string(self, payload, **kwargs):
        self.calls.append((payload, kwargs))


class _Bucket:
    def __init__(self):
        self.blobs = {}

    def blob(self, name):
        return self.blobs.setdefault(name, _Blob())


class _Storage:
    def __init__(self):
        self.buckets = {}

    def bucket(self, name):
        return self.buckets.setdefault(name, _Bucket())


def test_latent_seed_receipts_require_exact_five_by_four_plus_eight():
    batch = _batch(treatment=True)
    validated = prospective.validate_latent_seed_receipts(batch)
    assert set(validated) == {"R0", "R1", "R2", "R3", "R4"}
    assert validated["R2"]["accepted_sampled"] == 8

    batch.metadata["latent_seed_receipts"]["R3"][
        "latent_optimization_receipt"
    ][0]["disposition"] = "duplicate"
    with pytest.raises(ValueError, match=r"not exact 4\+8"):
        prospective.validate_latent_seed_receipts(batch)


def test_paired_runner_freezes_control_treatment_and_transition(monkeypatch):
    class _Factory:
        artifact_receipt = {
            "sha256": "a" * 64,
            "uri": "gs://bucket/transition.json",
            "create_only": True,
        }
        receipts = [{"source_label": f"R{index}"} for index in range(5)]

    factory = _Factory()
    monkeypatch.setattr(
        prospective,
        "create_live_latent_role_scenario_factory",
        lambda **kwargs: factory,
    )
    calls = []

    def fake_build(**kwargs):
        treatment = kwargs["policy_env"].get("MULTISEED_PORTFOLIO") == (
            "CBWU_LATENT_ROLE_SHADOW"
        )
        calls.append((treatment, kwargs["panel_run_id"]))
        batch = _batch(treatment=treatment)
        kwargs["_candidate_capture"](batch)
        return list(batch.candidates)

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build,
    )
    monkeypatch.setenv("CODE_SHA", "b" * 40)
    storage = _Storage()
    result = prospective.run(
        store=_Store(),
        season=2026,
        week=1,
        draft_group_id=123,
        generated_at=pd.Timestamp("2026-09-01T12:00:00Z").to_pydatetime(),
        storage_client=storage,
        bucket_name="bucket",
    )
    assert calls == [
        (False, "prospective-latent-role-2026w01-20260901T120000Z-control"),
        (True, "prospective-latent-role-2026w01-20260901T120000Z-treatment"),
    ]
    assert result["shadow_version"] == prospective.VERSION
    assert result["entries"] == 80
    assert result["player_worlds_identical"]
    assert result["uses_post_lock_outcomes"] is False
    assert result["uses_fantasy_or_lineup_outcomes"] is False
    assert result["manifest_create_only"]
    manifest_blob = storage.buckets["bucket"].blobs[
        "latent_role_shadow/2026/week-01/"
        "prospective-latent-role-2026w01-20260901T120000Z/manifest.json"
    ]
    assert manifest_blob.calls[0][1]["if_generation_match"] == 0
