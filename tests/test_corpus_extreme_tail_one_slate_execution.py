from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_extreme_tail_one_slate_execution as execution
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as accepted
from nfl_dfs.research import residual_world_columns as rw


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}


def _identity(name: str, ordinal: int) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/{name}",
        "generation": str(ordinal + 1),
        "sha256": f"{ordinal + 1:064x}",
        "bytes": ordinal + 1,
    }


def _accepted_reconstruction() -> accepted.AcceptedV12SlateReconstruction:
    acceptance_identity = _identity("acceptance.json", 0)
    carrier_identity = _identity("carrier.json", 1)
    membership = {
        "slate_id": SLATE["slate_id"],
        "lane_ordinal": 0,
        "lane_id": "v12a",
        "task_ordinal": 0,
        "source_task_ordinal": 0,
        "task_acceptance_identity": acceptance_identity,
        "carrier_identity": carrier_identity,
        "arms": [],
    }
    world_artifacts = {
        role: _identity(f"{block}.npz", ordinal + 10)
        for ordinal, (block, role) in enumerate(
            zip(rw.WORLD_BLOCKS, batch.TASK_WORLD_SOURCE_ROLES, strict=True)
        )
    }
    imported = SimpleNamespace(
        compatibility_receipt={
            "compatibility_import_sha256": "1" * 64,
        }
    )
    reconstructed = SimpleNamespace(
        prepared=SimpleNamespace(
            world_ids=tuple(
                SimpleNamespace(block=block, index=0)
                for block in rw.WORLD_BLOCKS
            )
        ),
        provenance={
            "slate": dict(SLATE),
            "candidate_provenance_sha256": "2" * 64,
        },
        union_scores=np.zeros((1, len(rw.WORLD_BLOCKS)), dtype=np.float64),
        reconstruction_receipt={
            "reconstruction_sha256": "3" * 64,
            "matrix_binding": {
                "matrix_binding_sha256": "4" * 64,
                "score_matrix_sha256": "5" * 64,
            },
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        },
    )
    return accepted.AcceptedV12SlateReconstruction(
        slate_id=str(SLATE["slate_id"]),
        panel_index_identity=_identity("panel.json", 20),
        panel_index_sha256="6" * 64,
        accepted_slate_membership=membership,
        task_acceptance_identity=acceptance_identity,
        carrier_identity=carrier_identity,
        later_source_freeze_identity=_identity("source.json", 21),
        world_artifact_identities=world_artifacts,
        imported=imported,
        reconstructed=reconstructed,
    )


def _support_census(*, require_authoritative: bool, worlds_per_block: int) -> dict:
    return {
        "schema_version": census.CENSUS_SCHEMA,
        "slate": dict(SLATE),
        "input_binding": {
            "reconstruction_sha256": "3" * 64,
            "candidate_provenance_sha256": "2" * 64,
            "matrix_binding_sha256": "4" * 64,
        },
        "world_basis": {"worlds_per_block": worlds_per_block},
        "require_authoritative": require_authoritative,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
        "support_census_sha256": "7" * 64,
    }


def _call(**overrides) -> dict[str, object]:
    kwargs = {
        "validated_panel_index": {"panel": "validated"},
        "panel_index_identity": _identity("panel-input.json", 30),
        "accepted_slate_membership": {"slate_id": SLATE["slate_id"]},
        "task_acceptance_identity": _identity("acceptance-input.json", 31),
        "carrier_identity": _identity("carrier-input.json", 32),
        "read_exact": lambda identity: b"unused",
    }
    kwargs.update(overrides)
    return execution.execute_one_slate_extreme_tail_census(**kwargs)


def test_authoritative_smoke_binds_reconstruction_and_replays_census(
    monkeypatch,
) -> None:
    retained = _accepted_reconstruction()
    calls: list[str] = []

    def reconstruct(**kwargs):
        calls.append("reconstruct")
        assert kwargs["require_authoritative"] is True
        return retained

    def build(**kwargs):
        calls.append("build")
        assert kwargs["provenance"] is retained.reconstructed.provenance
        assert kwargs["union_scores"] is retained.reconstructed.union_scores
        assert kwargs["reconstruction_receipt"] is (
            retained.reconstructed.reconstruction_receipt
        )
        assert kwargs["world_ids"] == [
            {"block": block, "index": 0} for block in rw.WORLD_BLOCKS
        ]
        assert kwargs["worlds_per_block"] is None
        assert kwargs["require_authoritative"] is True
        return _support_census(
            require_authoritative=True,
            worlds_per_block=rw.WORLDS_PER_BLOCK,
        )

    def validate(value, **kwargs):
        calls.append("validate")
        assert value["support_census_sha256"] == "7" * 64
        assert kwargs["union_scores"] is retained.reconstructed.union_scores
        return deepcopy(value)

    monkeypatch.setattr(
        accepted, "reconstruct_one_accepted_v12_slate", reconstruct
    )
    monkeypatch.setattr(census, "build_extreme_tail_support_census", build)
    monkeypatch.setattr(census, "validate_extreme_tail_support_census", validate)

    result = _call()

    assert calls == ["reconstruct", "build", "validate"]
    assert result["execution_mode"] == (
        "authoritative-dose-one-slate-outcome-blind-smoke"
    )
    assert result["panel_index_identity"] == retained.panel_index_identity
    assert result["accepted_slate_membership"] == (
        retained.accepted_slate_membership
    )
    assert result["world_artifact_identities"] == (
        retained.world_artifact_identities
    )
    assert result["output_hashes"] == {
        "compatibility_import_sha256": "1" * 64,
        "candidate_provenance_sha256": "2" * 64,
        "reconstruction_sha256": "3" * 64,
        "matrix_binding_sha256": "4" * 64,
        "score_matrix_sha256": "5" * 64,
        "support_census_sha256": "7" * 64,
    }
    for field in execution._FALSE_AUTHORITY_FIELDS:
        assert result[field] is False
    retained_hash = result["one_slate_execution_sha256"]
    assert retained_hash == batch.canonical_sha256({
        key: value for key, value in result.items()
        if key != "one_slate_execution_sha256"
    })


def test_fixture_dose_is_explicit_and_forwarded(monkeypatch) -> None:
    retained = _accepted_reconstruction()
    observed: list[tuple[int | None, bool]] = []

    monkeypatch.setattr(
        accepted,
        "reconstruct_one_accepted_v12_slate",
        lambda **kwargs: retained,
    )

    def build(**kwargs):
        observed.append(
            (kwargs["worlds_per_block"], kwargs["require_authoritative"])
        )
        return _support_census(
            require_authoritative=False,
            worlds_per_block=1,
        )

    monkeypatch.setattr(census, "build_extreme_tail_support_census", build)
    monkeypatch.setattr(
        census,
        "validate_extreme_tail_support_census",
        lambda value, **kwargs: deepcopy(value),
    )

    result = _call(require_authoritative=False, worlds_per_block=1)

    assert observed == [(1, False)]
    assert result["execution_mode"] == "non-authoritative-fixture-smoke"
    assert result["configuration"] == {
        "worlds_per_block": 1,
        "require_authoritative": False,
    }
    assert result["verification"][
        "canonical_authoritative_dose_verified"
    ] is False


def test_authoritative_dose_override_fails_before_reconstruction(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        accepted,
        "reconstruct_one_accepted_v12_slate",
        lambda **kwargs: calls.append("reconstruct"),
    )

    with pytest.raises(
        execution.CorpusExtremeTailOneSlateExecutionError,
        match="cannot override registered doses",
    ):
        _call(worlds_per_block=1, require_authoritative=True)

    assert calls == []


def test_census_replay_binding_drift_fails_closed(monkeypatch) -> None:
    retained = _accepted_reconstruction()
    body = _support_census(
        require_authoritative=False,
        worlds_per_block=1,
    )
    body["input_binding"]["matrix_binding_sha256"] = "f" * 64
    monkeypatch.setattr(
        accepted,
        "reconstruct_one_accepted_v12_slate",
        lambda **kwargs: retained,
    )
    monkeypatch.setattr(
        census,
        "build_extreme_tail_support_census",
        lambda **kwargs: body,
    )
    monkeypatch.setattr(
        census,
        "validate_extreme_tail_support_census",
        lambda value, **kwargs: deepcopy(value),
    )

    with pytest.raises(
        execution.CorpusExtremeTailOneSlateExecutionError,
        match="differs from accepted reconstruction",
    ):
        _call(require_authoritative=False, worlds_per_block=1)
