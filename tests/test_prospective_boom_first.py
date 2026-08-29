import itertools
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference import prospective_boom_first as prospective
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries


ROOT = Path(__file__).resolve().parents[1]


def _native_receipts(leverage, boom):
    return {
        f"R{index}": {
            "leverage_requested": leverage,
            "leverage_unique": leverage,
            "leverage_solve_attempts": leverage,
            "leverage_solver_errors": 0,
            "leverage_infeasible": 0,
            "leverage_successful": leverage,
            "boom_requested": boom,
            "boom_attempted": boom,
            "boom_successful": boom,
            "boom_solver_errors": 0,
            "boom_infeasible": 0,
            "boom_duplicates": index,
            "boom_failures": 0,
            "boom_unique_added": boom - index,
            "boom_unique_fill": False,
            "core_requested": leverage + boom,
            "ce_requested": 0,
            "role_or_epistemic_requested": 12,
            "gumbel_requested": 0,
            "total_requested_with_replacement_families": leverage + boom + 12,
            "unique_candidates_after_all_families": leverage + boom + 12,
            "model_version": "tail-k1-test-version",
            "role_model_version": "tail-k1-role-test-version",
            "candidate_input_receipt": {
                "sha256": "d" * 64,
                "rows": 22,
                "columns": ["id", "proj"],
            },
            "role_candidate_input_receipt": {
                "sha256": "e" * 64,
                "rows": 22,
                "columns": ["id", "proj"],
            },
            "timing_seconds": {
                "leverage": 1.0 + index,
                "primary_boom": 2.0 + index,
            },
        }
        for index in range(5)
    }


def _batch(*, treatment=False, receipts=True):
    players = tuple({
        "id": index,
        "gsis_id": f"g{index}",
        "pos": "WR",
        "team": f"T{index % 4}",
        "opp": f"T{(index + 1) % 4}",
        "salary": 5_000,
        "proj": 10.0,
    } for index in range(22))
    combinations = list(itertools.islice(
        itertools.combinations(range(22), 9), 120
    ))
    rosters = combinations[30:113] if treatment else combinations[:82]
    lineups = tuple(
        Lineup([players[index] for index in roster], tag="boom" if treatment else "lev")
        for roster in rosters
    )
    row_draws = np.add.outer(
        np.arange(22, dtype=np.float32) * 2.5,
        np.arange(50_000, dtype=np.float32) * 0.00075,
    )
    totals = np.stack([
        row_draws[list(lineup.ids)].sum(axis=0) for lineup in lineups
    ]).astype(np.float32)
    leverage, boom = ((40, 160) if treatment else (160, 40))
    metadata = {
        "portfolio": "CBWU",
        "world_blocks": 5,
        "worlds_per_block": [10_000] * 5,
    }
    if receipts:
        metadata["native_generation_receipts"] = _native_receipts(
            leverage, boom
        )
    return CandidateBatch(
        candidates=lineups,
        candidate_totals=totals,
        player_ids=tuple(range(22)),
        player_rows=players,
        row_draws=row_draws,
        all_tags={lineup.ids: (lineup.tag,) for lineup in lineups},
        metadata=metadata,
    )


def _environment(*, treatment=False):
    return {
        "MODEL_ENSEMBLE": "1",
        "MODEL_REGISTRY_VARIANT": "tail_k1",
        "MULTISEED_PORTFOLIO": "CBWU",
        "MULTISEED_WORLDS_PER_BLOCK": "10000",
        "MULTISEED_CANDIDATE_ENTRY_BASIS": "80",
        "SELECT_OBJ": "",
        "SELECT_LSE": "0",
        "SELECT_LADDER": "",
        "M4_QBLOCK": "0",
        "MAX_QBS": "0",
        "CAND_MULT": "2",
        "N_CE": "0",
        "N_GUMBEL": "0",
        "N_LEV": "40" if treatment else "160",
        "N_BOOM": "160" if treatment else "40",
        "GEN_TOTAL_BUDGET": "172" if treatment else "52",
        "N_EPISTEMIC": "12",
        "EPISTEMIC_FAMILY": "role_draws",
        "N_QB_VARIANTS": "4",
        "N_GAMESTACK": "4",
        "N_DARKGAME": "10",
        "MIN_LINEUP_SALARY": "49000",
        "PUNT_MIN": "0",
        "PUNT_MAX": "4000",
        "PUNT_STRICT": "",
        "MAX_PER_GAME": "0",
        "BOOM_UNIQUE_FILL": "0",
        "PROSPECTIVE_SHADOW_ID": "treatment" if treatment else "control",
    }


class _Policy:
    policy_id = "test-production-policy"
    model_variant = "tail_k1"
    role_model_variant = "tail_k1_role"
    model_ensemble = 1

    def boom_first_control_environment(self, base):
        return _environment(treatment=False)

    def boom_first_shadow_environment(self, base):
        return _environment(treatment=True)


class _Store:
    def classic_salaries(self, draft_group_id):
        return pd.DataFrame({
            "dk_player_id": range(22),
            "dk_draftable_id": np.arange(22) + 1000,
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


def test_native_receipts_are_optional_but_exact_when_present():
    absent = prospective.validate_native_generation_receipts(
        _batch(receipts=False), prospective.CONTROL_ALLOCATION
    )
    assert absent["available"] is False

    valid = prospective.validate_native_generation_receipts(
        _batch(treatment=True), prospective.TREATMENT_ALLOCATION
    )
    assert valid["available"] is True
    assert valid["receipts"]["R4"]["boom_requested"] == 160
    assert valid["receipts"]["R4"][
        "total_requested_with_replacement_families"
    ] == 212

    malformed = _batch(treatment=True)
    malformed.metadata["native_generation_receipts"]["R2"][
        "boom_requested"
    ] = 159
    with pytest.raises(ValueError, match="requested solve allocation differs"):
        prospective.validate_native_generation_receipts(
            malformed, prospective.TREATMENT_ALLOCATION
        )

    short = _batch(treatment=True)
    short.metadata["native_generation_receipts"]["R1"][
        "boom_solver_errors"
    ] = 1
    with pytest.raises(ValueError, match="boom solver work is incomplete"):
        prospective.validate_native_generation_receipts(
            short, prospective.TREATMENT_ALLOCATION
        )


def test_pair_accepts_unequal_candidates_but_rejects_world_drift():
    control = _batch()
    treatment = _batch(treatment=True)
    control_env = _environment()
    treatment_env = _environment(treatment=True)
    control_lineups = [
        control.candidates[index]
        for index in select_tail_entries(
            control.candidate_totals, 80, 194.0, env=control_env
        )
    ]
    treatment_lineups = [
        treatment.candidates[index]
        for index in select_tail_entries(
            treatment.candidate_totals, 80, 194.0, env=treatment_env
        )
    ]
    receipt = prospective.paired_boom_first_receipt(
        control,
        treatment,
        control_lineups,
        treatment_lineups,
        {index: index + 1000 for index in range(22)},
        control_selector_env=control_env,
        treatment_selector_env=treatment_env,
    )
    assert receipt["candidate_counts"] == {"control": 82, "treatment": 83}
    assert receipt["candidate_budget_identical"] is False
    assert receipt["player_worlds_identical"] is True
    assert [len(receipt["memberships"][str(size)]["control"])
            for size in (20, 40, 80)] == [20, 40, 80]

    treatment.row_draws[0, 0] += 1
    with pytest.raises(ValueError, match="player worlds differ"):
        prospective.paired_boom_first_receipt(
            control,
            treatment,
            control_lineups,
            treatment_lineups,
            {index: index + 1000 for index in range(22)},
            control_selector_env=control_env,
            treatment_selector_env=treatment_env,
        )


def test_runner_freezes_independent_exact80_books_and_artifacts(monkeypatch):
    control = _batch()
    treatment = _batch(treatment=True)
    calls = []

    def fake_build(**kwargs):
        is_treatment = kwargs["policy_env"]["N_LEV"] == "40"
        batch = treatment if is_treatment else control
        calls.append({
            "arm": "treatment" if is_treatment else "control",
            "panel_run_id": kwargs["panel_run_id"],
            "candidate_run_type": kwargs["candidate_run_type"],
            "expected_model_k": kwargs["expected_model_k"],
            "n_entries": kwargs["n_entries"],
            "tail_line": kwargs["tail_line"],
            "worlds": batch.row_draws.copy(),
        })
        kwargs["_candidate_capture"](batch)
        picked = select_tail_entries(
            batch.candidate_totals,
            kwargs["n_entries"],
            kwargs["tail_line"],
            env=kwargs["policy_env"],
        )
        lineups = [batch.candidates[index] for index in picked]
        for lineup in lineups:
            lineup.model_version = "tail-k1-test-version"
            lineup.role_model_version = "tail-k1-role-test-version"
        return lineups

    monkeypatch.setattr(prospective, "ADOPTED_CLASSIC_POLICY", _Policy())
    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build
    )
    monkeypatch.setenv("CODE_SHA", "b" * 40)
    monkeypatch.setenv("IMAGE_SOURCE_COMMIT_SHA", "b" * 40)
    monkeypatch.setenv(
        "IMAGE_URI",
        "us-central1-docker.pkg.dev/project/nfl-dfs/nfl-dfs@sha256:"
        + "c" * 64,
    )
    monkeypatch.setenv("CLOUD_RUN_JOB", "atlas-minimal-c-smoke")
    monkeypatch.setenv(
        "CLOUD_RUN_EXECUTION", "atlas-minimal-c-smoke-test01"
    )
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "0")
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

    assert [call["arm"] for call in calls] == ["control", "treatment"]
    assert calls[0]["panel_run_id"].endswith("-control")
    assert calls[1]["panel_run_id"].endswith("-treatment")
    assert calls[0]["candidate_run_type"] == "prospective_boom_first_control"
    assert calls[1]["candidate_run_type"] == "prospective_boom_first_treatment"
    assert all(call["expected_model_k"] == 1 for call in calls)
    assert all(call["n_entries"] == 80 for call in calls)
    assert all(call["tail_line"] == 194.0 for call in calls)
    np.testing.assert_array_equal(calls[0]["worlds"], calls[1]["worlds"])
    assert result["candidate_counts"] == {"control": 82, "treatment": 83}
    assert result["image_uri"].endswith("@sha256:" + "c" * 64)
    assert result["image_source_commit_sha"] == "b" * 40
    assert result["candidate_budget_identical"] is False
    assert result["native_generation_receipts"]["control"]["available"]
    assert result["native_generation_receipts"]["treatment"]["available"]
    assert len(result["player_identity_bridge"]) == 22
    assert result["player_identity_bridge"][0]["gsis_id"] == "g0"
    assert result["environment_contract"]["candidate_entry_basis"] == 80
    assert result["environment_contract"][
        "requested_family_slots_per_five_book_arm"
    ] == 1060
    assert result["environment_contract"][
        "nominal_all_requested_per_five_book_arm"
    ] == 1330
    assert result["constraint_contract"]["stack_rules"][
        "forbid_two_rb_same_team"
    ] is True
    assert result["model_receipt"] == {
        "model_version": "tail-k1-test-version",
        "role_model_version": "tail-k1-role-test-version",
    }
    assert result["native_provenance_receipt"][
        "all_native_books_identical_inputs"
    ] is True
    assert result["native_provenance_receipt"]["native_book_count"] == 10
    assert result["strategy_ids"] == {
        "control": "control",
        "treatment": "treatment",
    }
    assert result["environment_contract"]["portfolio"] == "CBWU"
    assert result["counts"]["control_selected"] == 80
    assert all(value >= 0 for value in result["timings_seconds"].values())
    assert result["manifest_create_only"] is True
    assert result["terminal_create_only"] is True
    assert result["complete"] is True

    prefix = (
        "boom_first_shadow/2026/week-01/"
        "prospective-boom-first-2026w01-atlas-minimal-c-smoke-test01"
    )
    blobs = storage.buckets["bucket"].blobs
    assert set(blobs) == {
        f"{prefix}/control.npz",
        f"{prefix}/treatment.npz",
        f"{prefix}/manifest.json",
        f"{prefix}/terminal.json",
    }
    assert all(
        blob.calls[0][1]["if_generation_match"] == 0
        for blob in blobs.values()
    )
    manifest = json.loads(blobs[f"{prefix}/manifest.json"].calls[0][0])
    assert manifest["candidate_counts"] == {
        "control": 82, "treatment": 83
    }
    assert len(manifest["memberships"]["80"]["control"]) == 80
    assert len(manifest["memberships"]["80"]["treatment"]) == 80
    assert manifest["control_artifact"]["create_only"] is True
    assert manifest["treatment_artifact"]["create_only"] is True
    terminal = json.loads(blobs[f"{prefix}/terminal.json"].calls[0][0])
    assert terminal["complete"] is True
    assert terminal["cloud_run_execution"] == "atlas-minimal-c-smoke-test01"
    assert terminal["manifest"]["sha256"] == result["manifest_sha256"]
    control_payload = blobs[f"{prefix}/control.npz"].calls[0][0]
    with np.load(io.BytesIO(control_payload), allow_pickle=False) as archive:
        artifact_metadata = json.loads(str(archive["metadata"].item()))
    native = artifact_metadata["candidate_batch_metadata"][
        "native_generation_receipts"
    ]
    assert all("timing_seconds" not in receipt for receipt in native.values())


def test_runner_rejects_image_source_commit_mismatch(monkeypatch):
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setenv("IMAGE_SOURCE_COMMIT_SHA", "b" * 40)
    with pytest.raises(ValueError, match="image source commit"):
        prospective.run(
            store=_Store(), season=2026, week=1, draft_group_id=123,
        )


def test_boom_first_cli_and_quota_safe_manual_launch_are_registered():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    deploy = (ROOT / "deploy/deploy_jobs.sh").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    focused_cloudbuild = (
        ROOT / "cloudbuild.boom-first-shadow.yaml"
    ).read_text(encoding="utf-8")
    launch = (
        ROOT / "scripts/cloud_boom_first_paired_shadow.sh"
    ).read_text(encoding="utf-8")
    resume = (
        ROOT / "scripts/resume_2026_production_schedulers.py"
    ).read_text(encoding="utf-8")
    assert '"shadow-boom-first-paired"' in cli
    assert "prospective_boom_first.main()" in cli
    assert "job shadow-boom-first-paired shadow-boom-first-paired" not in deploy
    assert 'REUSED_JOB="atlas-minimal-c-smoke"' in launch
    assert "--args shadow-boom-first-paired" in launch
    assert "--task-timeout 21600s" in launch
    assert "--max-retries 0" in launch
    assert "gcloud run jobs replace" in launch
    assert "operator-locks" in launch
    assert "operator-recovery" in launch
    assert "SOURCE_COMMIT_SHA" in dockerfile
    assert "IMAGE_SOURCE_COMMIT_SHA" in dockerfile
    assert "SOURCE_COMMIT_SHA=${_CODE_SHA}" in cloudbuild
    assert '"$IMG"' not in cloudbuild
    assert '"$$IMG"' in cloudbuild
    assert "focused-boom-first-shadow-tests" in focused_cloudbuild
    assert "tests/test_prospective_boom_first.py" in focused_cloudbuild
    assert "tests/test_cloud_boom_first_paired_shadow.py" in focused_cloudbuild
    assert "tests/test_week1_source_readiness.py" in focused_cloudbuild
    assert "--network none" in focused_cloudbuild
    assert "SOURCE_COMMIT_SHA=${_CODE_SHA}" in focused_cloudbuild
    assert "PYTHONPATH=src pytest" in focused_cloudbuild
    assert "PYTHONPATH=src pytest\n" not in focused_cloudbuild
    assert "s-shadow-boom-first" not in deploy
    assert "shadow-boom-first" not in resume
