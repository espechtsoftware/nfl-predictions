from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest


def test_registry_variant_keeps_canonical_labels_unchanged():
    from nfl_dfs.models import train_job

    assert train_job.registry_variant("canonical") == "canonical"
    assert train_job._component_label("targets", "canonical") == \
        "comp_targets"
    assert train_job._component_label("targets", "tail_k1") == \
        "comp_targets__tail_k1"
    assert train_job._component_version("2026-W36", "tail_k1") == \
        "pooled/components__tail_k1/2026-W36"
    with pytest.raises(ValueError, match="MODEL_REGISTRY_VARIANT"):
        train_job.registry_variant("../canonical")


def test_shadow_training_writes_only_suffixed_registry_labels(monkeypatch):
    from nfl_dfs.models import components, train_job

    panel = pd.DataFrame({"season": [2025]})
    monkeypatch.setattr(train_job, "training_panel", lambda: panel)
    monkeypatch.setattr(
        train_job.baseline, "walk_forward",
        lambda frame: SimpleNamespace(fold_reports={}),
    )
    fitted = SimpleNamespace(
        models={name: object() for name in components.COMPONENT_NAMES})
    monkeypatch.setattr(train_job.components, "train", lambda *a, **k: fitted)
    monkeypatch.setattr(train_job.registry, "model_params", lambda model: {})
    labels = []
    monkeypatch.setattr(
        train_job.registry, "save",
        lambda model, meta, root: labels.append(meta.label),
    )

    version = train_job.train_and_register(
        today=date(2026, 9, 8), variant="tail_k1")
    assert version == "pooled/components__tail_k1/2026-W37"
    assert set(labels) == {
        f"comp_{name}__tail_k1" for name in components.COMPONENT_NAMES}
    assert "comp_targets" not in labels


def test_load_shadow_models_reads_only_suffixed_labels(monkeypatch):
    from nfl_dfs.models import components, train_job

    seen = []
    monkeypatch.setattr(train_job, "_registry_root", lambda: "gs://test/models")
    monkeypatch.setattr(
        train_job.registry, "latest_iso_week",
        lambda root, scope, label: seen.append(label) or "2026-W37",
    )
    monkeypatch.setattr(
        train_job.registry, "load",
        lambda root, scope, label, week: (seen.append(label) or object(), None),
    )
    models, version = train_job.load_latest_component_models("tail_k1")
    assert version == "pooled/components__tail_k1/2026-W37"
    assert set(models.models) == set(components.COMPONENT_NAMES)
    assert seen[0] == "comp_targets__tail_k1"
    assert all(label.endswith("__tail_k1") for label in seen)


def test_registered_component_member_count_must_be_consistent():
    from nfl_dfs.models import components, train_job

    single = components.ComponentModels(models={"a": object(), "b": object()})
    assert train_job.registered_ensemble_size(single) == 1
    ensemble = lambda n: SimpleNamespace(members=[object()] * n)
    triple = components.ComponentModels(
        models={"a": ensemble(3), "b": ensemble(3)})
    assert train_job.registered_ensemble_size(triple) == 3
    mixed = components.ComponentModels(
        models={"a": ensemble(3), "b": object()})
    with pytest.raises(RuntimeError, match="mixed member counts"):
        train_job.registered_ensemble_size(mixed)


def test_sunday_main_matches_ui_largest_all_sunday_group():
    from nfl_dfs.inference.tail_shadow import sunday_main_group

    slates = pd.DataFrame([
        {"draft_group_id": 10, "game_start": "2026-09-10T00:20:00Z",
         "teams": 2, "players": 50},
        {"draft_group_id": 10, "game_start": "2026-09-13T17:00:00Z",
         "teams": 20, "players": 180},
        {"draft_group_id": 20, "game_start": "2026-09-13T17:00:00Z",
         "teams": 16, "players": 160},
        {"draft_group_id": 20, "game_start": "2026-09-13T20:25:00Z",
         "teams": 8, "players": 80},
        {"draft_group_id": 30, "game_start": "2026-09-13T20:25:00Z",
         "teams": 8, "players": 80},
    ])
    # A larger preseason Sunday must never be paired with regular Week 1.
    slates = pd.concat([slates, pd.DataFrame([{
        "draft_group_id": 40,
        "game_start": "2026-08-30T17:00:00Z",
        "teams": 30,
        "players": 300,
    }])], ignore_index=True)
    assert sunday_main_group(slates, date(2026, 9, 13)) == 20


def test_shadow_run_is_fixed_isolated_and_synchronous(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "tail_k1")
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    monkeypatch.setenv("CAND_ARTIFACT_BUCKET", "test-artifacts")
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, 1, date(2026, 9, 13)))

    class Store:
        def classic_slates(self):
            return pd.DataFrame([{
                "draft_group_id": 77,
                "game_start": "2026-09-13T17:00:00Z",
                "teams": 20,
                "players": 100,
            }])

        def classic_salaries(self, gid):
            assert gid == 77
            return pd.DataFrame({
                "dk_player_id": range(100, 200),
                "salary": [5000] * 100,
            })

    captured = {}

    def fake_build(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return [object()] * 80

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build)
    result = tail_shadow.run(
        store=Store(),
        generated_at=datetime(2026, 9, 13, 15, 30, tzinfo=timezone.utc),
    )
    assert result["panel_run_id"] == \
        "live-shadow-tail_k1-2026w01-20260913T153000Z"
    assert result["entries"] == 80 and result["tail_line"] == 194.0
    kwargs = captured["kwargs"]
    assert kwargs["n_entries"] == 80
    assert kwargs["model_variant"] == "tail_k1"
    assert kwargs["apply_notes"] is False
    assert kwargs["cand_log_async"] is False
    assert kwargs["cand_log_required"] is True
    assert kwargs["candidate_run_type"] == "live_shadow"
    assert kwargs["panel_run_id"] == result["panel_run_id"]
    assert kwargs["allowed_ids"] == set(range(100, 200))


def test_shadow_refuses_canonical_registry(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.delenv("MODEL_REGISTRY_VARIANT", raising=False)
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    with pytest.raises(RuntimeError, match="requires MODEL_REGISTRY_VARIANT=tail_k1"):
        tail_shadow.run(store=object())


def test_canonical_reference_shadow_has_distinct_identity(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "canonical")
    monkeypatch.setenv("MODEL_ENSEMBLE", "3")
    monkeypatch.setenv("CAND_ARTIFACT_BUCKET", "test-artifacts")
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, 1, date(2026, 9, 13)))

    class Store:
        def classic_slates(self):
            return pd.DataFrame([{
                "draft_group_id": 77,
                "game_start": "2026-09-13T17:00:00Z",
                "teams": 20,
                "players": 100,
            }])

        def classic_salaries(self, gid):
            return pd.DataFrame({
                "dk_player_id": range(100, 200),
                "salary": [5000] * 100,
            })

    captured = {}

    def fake_build(*args, **kwargs):
        captured.update(kwargs)
        return [object()] * 80

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build)
    result = tail_shadow.run(
        expected_variant=tail_shadow.K3_VARIANT,
        store=Store(),
        generated_at=datetime(2026, 9, 13, 15, 30, tzinfo=timezone.utc),
    )
    assert result["panel_run_id"] == \
        "live-shadow-tail_k3-2026w01-20260913T153000Z"
    assert result["model_variant"] == "canonical"
    assert result["shadow_label"] == "tail_k3"
    assert captured["model_variant"] == "canonical"
    assert captured["candidate_run_type"] == "live_shadow"
