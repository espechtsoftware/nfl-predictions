from datetime import datetime, timezone
from types import SimpleNamespace

import io
import json
import numpy as np
import pandas as pd
import pytest


def _models(features, carries_features=None):
    targets = SimpleNamespace(feature_name=lambda: list(features))
    carries = SimpleNamespace(
        feature_name=lambda: list(
            features if carries_features is None else carries_features))
    return SimpleNamespace(models={"targets": targets, "carries": carries})


def test_registry_feature_contract_is_fail_closed():
    from nfl_dfs.inference.route_share_shadow import (
        ROUTE_FEATURES, validate_component_feature_contract,
    )

    validate_component_feature_contract(
        _models((*ROUTE_FEATURES, "salary")),
        registry_variant="tail_k1_route", required=ROUTE_FEATURES,
        forbidden=("target_share_last",),
    )
    with pytest.raises(RuntimeError, match="fp_route_share_l4"):
        validate_component_feature_contract(
            _models(("fp_route_share_last",)),
            registry_variant="tail_k1_route", required=ROUTE_FEATURES,
        )
    with pytest.raises(RuntimeError, match="forbidden.*target_share_last"):
        validate_component_feature_contract(
            _models((*ROUTE_FEATURES, "target_share_last")),
            registry_variant="tail_k1_route", required=ROUTE_FEATURES,
            forbidden=("target_share_last",),
        )
    with pytest.raises(RuntimeError, match="carries"):
        validate_component_feature_contract(
            _models(ROUTE_FEATURES, carries_features=("salary",)),
            registry_variant="tail_k1_route", required=ROUTE_FEATURES,
        )


def test_live_route_policy_week1_and_exact_prior_week():
    from nfl_dfs.inference.route_share_shadow import (
        ROUTE_FEATURES, apply_live_route_policy,
    )

    week1_frame = pd.DataFrame({
        "fp_route_source_season": [2025, 2025],
        "fp_route_source_week": [18, 17],
        "fp_route_source_sha256": ["a" * 64, ""],
        "fp_route_fallback": ["ready"] * 2,
        **{column: [0.4, 0.5] for column in ROUTE_FEATURES},
    })
    week1 = apply_live_route_policy(week1_frame, 2026, 1)
    assert week1.fp_route_shadow_supported.tolist() == [True, False]
    assert week1.loc[1, list(ROUTE_FEATURES)].isna().all()
    assert week1.loc[0, "fp_route_cross_season"] == 1

    week2_frame = pd.DataFrame({
        "fp_route_source_season": [2025, 2026, 2026],
        "fp_route_source_week": [18, 1, 1],
        "fp_route_source_sha256": ["a" * 64, "b" * 64, ""],
        "fp_route_fallback": ["ready"] * 3,
        **{column: [0.4, 0.5, 0.6] for column in ROUTE_FEATURES},
    })
    week2 = apply_live_route_policy(week2_frame, 2026, 2)
    assert week2.fp_route_shadow_supported.tolist() == [False, True, False]
    assert week2.loc[0, list(ROUTE_FEATURES)].isna().all()
    assert week2.loc[1, "fp_route_cross_season"] == 0

    bad = week2_frame.copy()
    bad.loc[0, ["fp_route_source_season", "fp_route_source_week"]] = [2026, 2]
    with pytest.raises(RuntimeError, match="same/future source"):
        apply_live_route_policy(bad, 2026, 2)


def test_distribution_artifact_payload_preserves_alignment_and_draws():
    from nfl_dfs.inference.route_share_shadow import (
        DistributionArtifactSpec, distribution_artifact_payload,
    )

    slate = pd.DataFrame({
        "id": [11, 12], "gsis_id": ["g11", "g12"],
        "name": ["A", "B"], "pos": ["WR", "RB"],
        "team": ["X", "Y"], "draw_idx": [1, 0],
        "model_points_pre": [10.0, 11.0],
        "component_mean_targets": [7.0, 2.0],
        "fp_route_source_sha256": ["hash-a", "hash-b"],
        "fp_route_shadow_supported": [True, True],
    })
    belief = slate.copy()
    belief["component_mean_targets"] += 1.0
    draws = np.asarray([[1, 2, 3], [4, 5, 6]], dtype=float)
    belief_draws = draws + 10
    spec = DistributionArtifactSpec(
        bucket="bucket", panel_run_id="panel", arm="control",
        model_variant="tail_k1", belief_model_variant="tail_k1_role")
    payload = distribution_artifact_payload(
        slate, draws, belief, belief_draws, season=2026, week=1,
        model_version="base-v", belief_model_version="role-v", spec=spec,
        generated_at=datetime(2026, 9, 13, 15, tzinfo=timezone.utc),
    )
    with np.load(io.BytesIO(payload), allow_pickle=False) as artifact:
        assert artifact["dk_player_id"].tolist() == [11, 12]
        assert artifact["base_draws"].tolist() == [[4, 5, 6], [1, 2, 3]]
        assert artifact["belief_draws"].tolist() == [
            [14, 15, 16], [11, 12, 13]]
        assert artifact["component_mean_targets"].tolist() == [7.0, 2.0]
        assert artifact["belief_component_mean_targets"].tolist() == [8.0, 3.0]
        metadata = json.loads(str(artifact["metadata_json"]))
        assert metadata["arm"] == "control"
        assert metadata["n_worlds"] == 3


def test_route_registry_training_contract(monkeypatch):
    from nfl_dfs.models import train_job

    monkeypatch.setenv(
        "EXTRA_FEATURES",
        "fp_route_share_last,fp_route_share_l4,fp_route_share_jump,"
        "fp_route_cross_season")
    train_job.validate_variant_feature_contract("tail_k1_route")
    monkeypatch.setenv("EXTRA_FEATURES", "fp_route_share_last")
    with pytest.raises(RuntimeError, match="requires exact EXTRA_FEATURES"):
        train_job.validate_variant_feature_contract("tail_k1_route")


def test_distribution_artifact_upload_is_create_only(monkeypatch):
    from google.cloud import storage
    from nfl_dfs.inference.route_share_shadow import (
        DistributionArtifactSpec, persist_distribution_artifact,
    )

    slate = pd.DataFrame({
        "id": [11], "gsis_id": ["g11"], "name": ["A"], "pos": ["WR"],
        "team": ["X"], "draw_idx": [0],
    })
    uploaded = {}

    class Blob:
        def upload_from_string(self, payload, **kwargs):
            uploaded["payload"] = payload
            uploaded["kwargs"] = kwargs

    class Bucket:
        def blob(self, name):
            uploaded["name"] = name
            return Blob()

    class Client:
        def bucket(self, name):
            assert name == "bucket"
            return Bucket()

    monkeypatch.setattr(storage, "Client", Client)
    spec = DistributionArtifactSpec(
        bucket="bucket", panel_run_id="panel", arm="treatment",
        model_variant="tail_k1_route",
        belief_model_variant="tail_k1_route_role")
    uri, digest = persist_distribution_artifact(
        slate, np.asarray([[1.0, 2.0]]), slate.copy(),
        np.asarray([[3.0, 4.0]]), season=2026, week=1,
        model_version="base", belief_model_version="belief", spec=spec,
        generated_at=datetime(2026, 9, 13, 15, tzinfo=timezone.utc),
    )
    assert uri.startswith("gs://bucket/route_share_player_distributions/panel/")
    assert len(digest) == 64
    assert uploaded["kwargs"]["if_generation_match"] == 0
    assert uploaded["kwargs"]["content_type"] == "application/octet-stream"
