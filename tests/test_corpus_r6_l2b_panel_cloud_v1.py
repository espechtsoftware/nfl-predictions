from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as panel
from nfl_dfs.research import corpus_r6_l2b_panel_operator_v1 as operator
from scripts import run_corpus_r6_l2b_panel_cloud_v1 as cli


PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "l2b-panel-fixture/"
)


class _Store:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}
        self.next_generation = 1

    def seed(self, uri: str, value: object) -> dict[str, object]:
        raw = value if type(value) is bytes else legal.canonical_json_bytes(value)
        identity = {
            "uri": uri,
            "generation": str(self.next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.next_generation += 1
        self.objects[uri] = (raw, identity)
        return dict(identity)

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.objects:
            previous, identity = self.objects[uri]
            if previous != raw:
                raise RuntimeError("create-once bytes differ")
            return dict(identity)
        return self.seed(uri, raw)

    def read(self, identity: dict[str, object]) -> bytes:
        raw, expected = self.objects[str(identity["uri"])]
        if identity != expected:
            raise RuntimeError("generation-pinned identity differs")
        return raw


def _catalog() -> list[dict[str, object]]:
    rows = (
        ("d0", "DST", "E"),
        ("q0", "QB", "A"),
        ("r0", "RB", "A"),
        ("r1", "RB", "B"),
        ("r2", "RB", "C"),
        ("t0", "TE", "D"),
        ("w0", "WR", "A"),
        ("w1", "WR", "B"),
        ("w2", "WR", "C"),
        ("w3", "WR", "D"),
    )
    return [
        {
            "id": player_id,
            "pos": position,
            "team": team,
            "opp": "Z",
            "game_id": f"g{index % 3}",
            "salary": 4_500,
        }
        for index, (player_id, position, team) in enumerate(rows)
    ]


def _target_frame() -> pd.DataFrame:
    skill = [row for row in _catalog() if row["pos"] in panel.SKILL_POSITIONS]
    rows = []
    for season, week in panel.EXPECTED_SLATES:
        for row in skill:
            rows.append({
                "season": season,
                "week": week,
                "gsis_id": row["id"],
                "team": row["team"],
                "position": row["pos"],
                "previous_state": "rotation",
                "injury_status": "Healthy",
            })
    return pd.DataFrame(rows)


def _identity(uri: str, raw: bytes = b"x") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _world_npz(block: str) -> bytes:
    catalog = _catalog()
    player_ids = np.asarray([row["id"] for row in catalog], dtype="<U2")
    base = np.arange(len(catalog), dtype=np.float32)[:, None]
    worlds = np.arange(panel.WORLDS_PER_BLOCK, dtype=np.float32)[None, :] / 1000
    player_draws = np.ascontiguousarray(base + worlds, dtype=np.float32)
    buffer = BytesIO()
    np.savez_compressed(
        buffer,
        cand_ix=np.asarray([0], dtype=np.int64),
        totals=np.zeros((1, panel.WORLDS_PER_BLOCK), dtype=np.float32),
        tail_line=np.asarray([194.0], dtype=np.float32),
        player_ids=player_ids,
        player_draws=player_draws,
    )
    return buffer.getvalue()


def _fixture(monkeypatch: pytest.MonkeyPatch):
    store = _Store()
    source_slates = []
    for season, week in panel.EXPECTED_SLATES:
        slate_id = f"{season}-w{week:02d}"
        receipts = []
        for block in panel.WORLD_BLOCKS:
            raw = _world_npz(block)
            identity = store.seed(
                f"gs://fixture/ordinary/{slate_id}/{block}.npz", raw
            )
            receipts.append({
                **identity,
                "block": block,
                "candidate_rows": 1,
            })
        source_slates.append({
            "slate_id": slate_id,
            "catalog": _catalog(),
            "artifact_receipts": receipts,
        })
    source = {"freeze_sha256": "f" * 64, "slates": source_slates}
    source_identity = store.seed("gs://fixture/later-source.json", source)
    monkeypatch.setattr(
        panel.later,
        "validate_source_freeze",
        lambda value, *, expected_freeze_sha256: value,
    )

    release = {
        "calibration_id": "fixed-2018-2022",
        "release_sha256": "a" * 64,
        "final_fit_seasons": [2018, 2019, 2020, 2021, 2022],
        "final_fit_scope": "prospective-2023-plus-only",
        "gate": {"passes": True},
        "prospective_challenger_bank_generation_licensed": True,
        "uses_lineup_outcomes": False,
    }
    release_identity = store.seed("gs://fixture/l2b-release.json", release)
    monkeypatch.setattr(
        panel.calibration,
        "validate_l2_base_rate_calibration_release_v1",
        lambda value: dict(value),
    )
    targets = panel.build_pit_target_panel_v1(
        target_players=_target_frame(),
        source_identities={"pit-source": _identity("gs://fixture/pit.parquet")},
    )
    target_identity = store.seed("gs://fixture/pit-targets.json", targets)
    build_receipt = {
        "build_id": "build-1",
        "finish_time": "2026-08-28T00:10:00Z",
        "image_digest": "sha256:" + "2" * 64,
        "image_tag": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "nfl-dfs/nfl-dfs:l2b-test"
        ),
        "project_id": "nfl-predictions-503414",
        "region": "us-central1",
        "source_commit": "1" * 40,
        "start_time": "2026-08-28T00:00:00Z",
        "status": "SUCCESS",
    }
    build_identity = store.seed(
        "gs://fixture/build.json",
        json.dumps(build_receipt, indent=2, sort_keys=True).encode("utf-8"),
    )
    prepared = panel.prepare_54_task_manifest_v1(
        later_source_freeze_identity=source_identity,
        calibration_release_identity=release_identity,
        pit_target_panel_identity=target_identity,
        terminal_build_receipt_identity=build_identity,
        output_prefix=PREFIX,
        source_commit_sha="1" * 40,
        immutable_image_digest="sha256:" + "2" * 64,
        reused_job_name="atlas-minimal-c-s2023-w3-v1",
        reused_job_uid="064df315-0fb5-4b86-a5f9-6c73ac1c5eb3",
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    manifest = json.loads(
        store.read(prepared["task_manifest_identity"]).decode("utf-8")
    )
    return store, prepared, manifest


def test_pit_target_panel_rejects_any_current_week_or_score_surface() -> None:
    frame = _target_frame().assign(realized_state="primary")
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="forbidden outcomes"
    ):
        panel.build_pit_target_panel_v1(
            target_players=frame,
            source_identities={"pit": _identity("gs://fixture/pit")},
        )
    frame = _target_frame().assign(actual=30.0)
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="forbidden outcomes"
    ):
        panel.build_pit_target_panel_v1(
            target_players=frame,
            source_identities={"pit": _identity("gs://fixture/pit")},
        )


def test_prepare_freezes_only_quarter_and_native_on_one_job(monkeypatch) -> None:
    store, prepared, manifest = _fixture(monkeypatch)
    assert prepared["task_count"] == 54
    assert [row["fraction_id"] for row in manifest["fraction_registry"]] == [
        "l2b-quarter-world-mixture", "l2b-native"
    ]
    assert manifest["control_reference"]["numerator"] == 0
    assert manifest["additional_fraction_grid_allowed"] is False
    assert manifest["calibration_fit_seasons"] == [2018, 2019, 2020, 2021, 2022]
    assert manifest["calibration_fit_held_fixed_across_panel"] is True
    config = prepared["cloud_run_job_configuration"]
    assert config["task_count"] == config["parallelism"] == 54
    assert config["new_job_creation_allowed"] is False
    assert config["iam_mutation_required"] is False
    assert config["reused_job_uid"] == "064df315-0fb5-4b86-a5f9-6c73ac1c5eb3"
    assert config["environment"][panel.REUSED_JOB_UID_ENV] == config[
        "reused_job_uid"
    ]
    build = json.loads(
        store.read(manifest["terminal_build_receipt_identity"]).decode("utf-8")
    )
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="successful code/image"
    ):
        panel._validated_terminal_build_receipt(
            {**build, "image_digest": "sha256:" + "9" * 64},
            source_commit_sha="1" * 40,
            immutable_image_digest="sha256:" + "2" * 64,
        )

    tampered = dict(manifest)
    tampered.pop("task_manifest_sha256")
    tampered["actual_scores"] = []
    tampered = panel._self_hash(tampered, field="task_manifest_sha256")
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="manifest policy differs"
    ):
        panel.validate_task_manifest_v1(tampered)
    wrong_job = dict(manifest)
    wrong_job.pop("task_manifest_sha256")
    wrong_job["reused_job_uid"] = "00000000-0000-4000-8000-000000000000"
    wrong_job = panel._self_hash(wrong_job, field="task_manifest_sha256")
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="manifest identity fields differ"
    ):
        panel.validate_task_manifest_v1(wrong_job)


def test_fraction_masks_are_exact_nested_and_not_an_intensity_grid() -> None:
    quarter = panel.fraction_world_mask_v1(
        slate_id="2023-w01", block="R0",
        fraction_id="l2b-quarter-world-mixture"
    )
    native = panel.fraction_world_mask_v1(
        slate_id="2023-w01", block="R0", fraction_id="l2b-native"
    )
    assert quarter.dtype == np.bool_
    assert int(quarter.sum()) == 2_500
    assert int(native.sum()) == 10_000
    assert np.all(~quarter | native)
    assert np.array_equal(
        quarter,
        panel.fraction_world_mask_v1(
            slate_id="2023-w01", block="R0",
            fraction_id="l2b-quarter-world-mixture",
        ),
    )


def test_task_emits_selector_ready_nested_banks_without_touching_qb_dst(
    monkeypatch,
) -> None:
    store, prepared, manifest = _fixture(monkeypatch)

    def fake_runtime(**kwargs):
        ordinary = np.asarray(kwargs["ordinary_draws"], dtype=np.float64)
        bank = SimpleNamespace(
            draws=ordinary + 100.0,
            receipt={"receipt_sha256": "c" * 64},
            belief_world_artifact={"artifact_sha256": "d" * 64},
        )
        return SimpleNamespace(
            application=SimpleNamespace(receipt={"receipt_sha256": "a" * 64}),
            components=SimpleNamespace(receipt={"receipt_sha256": "b" * 64}),
            bank=bank,
        )

    monkeypatch.setattr(
        panel.runtime, "build_l2_base_rate_prospective_bank_v1", fake_runtime
    )
    execution = panel.execute_manifest_task_v1(
        manifest_identity=prepared["task_manifest_identity"],
        task_index=0,
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    result = execution.task_result
    assert result["artifact_count"] == 10
    assert result["target_outcome_columns_read"] == []
    assert result["lineup_outcome_columns_read"] == []
    panel._validate_task_result_lineage_v1(
        manifest=manifest,
        retained_manifest_identity=prepared["task_manifest_identity"],
        task_index=0,
        task_result_identity=execution.task_result_identity,
        result=result,
        read_exact=store.read,
    )

    wrong_task_authority = dict(result)
    wrong_task_authority["pit_target_panel_identity"] = _identity(
        "gs://fixture/other-target-panel.json"
    )
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="task result does not align"
    ):
        panel._validate_task_result_lineage_v1(
            manifest=manifest,
            retained_manifest_identity=prepared["task_manifest_identity"],
            task_index=0,
            task_result_identity=execution.task_result_identity,
            result=wrong_task_authority,
            read_exact=store.read,
        )

    wrong_receipt_result = deepcopy(result)
    first_artifact = wrong_receipt_result["artifacts"][0]
    receipt = json.loads(
        store.read(first_artifact["world_artifact_receipt_identity"]).decode(
            "utf-8"
        )
    )
    receipt.pop("receipt_sha256")
    receipt["pit_target_panel_identity"] = _identity(
        "gs://fixture/other-target-panel.json"
    )
    receipt = panel._self_hash(receipt, field="receipt_sha256")
    wrong_receipt_identity = store.seed(
        "gs://fixture/wrong-world-receipt.json", receipt
    )
    first_artifact["world_artifact_receipt_identity"] = wrong_receipt_identity
    first_artifact["world_artifact_receipt_sha256"] = receipt["receipt_sha256"]
    wrong_receipt_result.pop("task_result_sha256")
    wrong_receipt_result = panel._validate_task_result_v1(
        panel._self_hash(wrong_receipt_result, field="task_result_sha256")
    )
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="world receipt does not align"
    ):
        panel._validate_task_result_lineage_v1(
            manifest=manifest,
            retained_manifest_identity=prepared["task_manifest_identity"],
            task_index=0,
            task_result_identity=execution.task_result_identity,
            result=wrong_receipt_result,
            read_exact=store.read,
        )

    by_cell = {
        (row["fraction_id"], row["block"]): row for row in result["artifacts"]
    }
    source_slate = json.loads(
        store.read(manifest["later_source_freeze_identity"]).decode("utf-8")
    )["slates"][0]
    ordinary_receipt = source_slate["artifact_receipts"][0]
    ordinary = panel.evaluator._load_artifact_worlds_v1(
        ordinary_receipt,
        store.read({key: ordinary_receipt[key] for key in (
            "uri", "generation", "sha256", "bytes"
        )}),
    )
    loaded = {}
    for fraction_id in ("l2b-quarter-world-mixture", "l2b-native"):
        cell = by_cell[(fraction_id, "R0")]
        receipt = json.loads(
            store.read(cell["world_artifact_receipt_identity"]).decode("utf-8")
        )
        loaded[fraction_id] = panel.load_l2b_world_artifact_v1(
            receipt, store.read(cell["world_artifact_identity"])
        )
    index = {player_id: row for row, player_id in enumerate(ordinary.player_ids)}
    for protected in ("q0", "d0"):
        row = index[protected]
        assert np.array_equal(
            loaded["l2b-native"].player_draws[row], ordinary.player_draws[row]
        )
    quarter_mask = panel.fraction_world_mask_v1(
        slate_id="2023-w01", block="R0",
        fraction_id="l2b-quarter-world-mixture"
    )
    skill_row = index["w0"]
    assert np.array_equal(
        loaded["l2b-quarter-world-mixture"].player_draws[
            skill_row, ~quarter_mask
        ],
        ordinary.player_draws[skill_row, ~quarter_mask],
    )
    assert np.array_equal(
        loaded["l2b-quarter-world-mixture"].player_draws[
            skill_row, quarter_mask
        ],
        loaded["l2b-native"].player_draws[skill_row, quarter_mask],
    )
    with pytest.raises(
        panel.CorpusR6L2BPanelCloudV1Error, match="54 unique ordered"
    ):
        panel.finalize_panel_root_v1(
            manifest_identity=prepared["task_manifest_identity"],
            task_result_identities=[execution.task_result_identity],
            read_exact=store.read,
            publish_create_once=store.publish,
        )


def test_local_controller_output_is_atomic_create_once(tmp_path, capsys) -> None:
    output = tmp_path / "result.json"
    cli._write_create_once(output, {"complete": True})
    assert output.read_bytes() == legal.canonical_json_bytes({"complete": True})
    with pytest.raises(
        cli.RunCorpusR6L2BPanelCloudV1Error, match="create-once write refused"
    ):
        cli._write_create_once(output, {"complete": True})
    capsys.readouterr()


def _provider_job(configuration: dict[str, object]) -> dict[str, object]:
    return {
        "metadata": {
            "name": panel.REUSED_JOB_NAME,
            "uid": panel.REUSED_JOB_UID,
            "generation": "7",
        },
        "spec": {"template": {"spec": {
            "taskCount": configuration["task_count"],
            "parallelism": configuration["parallelism"],
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": f"{configuration['timeout_seconds']}s",
                "containers": [{
                    "image": configuration["image_uri"],
                    "command": configuration["command"],
                    "args": configuration["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in configuration["environment"].items()
                    ],
                    "resources": {"limits": configuration["resources"]},
                    "workingDir": "",
                    "volumeMounts": [],
                }],
                "volumes": [],
            }},
        }}},
        "status": {},
    }


def _provider_execution(*, scope: str, succeeded: int = 0) -> dict[str, object]:
    count = 1 if scope == operator.TASK0_SCOPE else panel.TASK_COUNT
    name = f"{panel.REUSED_JOB_NAME}-execution-1"
    status: dict[str, object] = {
        "succeededCount": succeeded,
        "failedCount": 0,
        "cancelledCount": 0,
    }
    if succeeded == count:
        status.update({
            "completionTime": "2026-08-28T12:00:00Z",
            "conditions": [{
                "type": "Completed",
                "state": "CONDITION_SUCCEEDED",
            }],
        })
    return {
        "metadata": {
            "name": name,
            "uid": "execution-uid-1",
            "generation": "3",
            "labels": {
                "run.googleapis.com/job": panel.REUSED_JOB_NAME,
                "run.googleapis.com/jobUid": panel.REUSED_JOB_UID,
            },
        },
        "spec": {"taskCount": count},
        "status": status,
    }


def test_operator_builds_uid_pinned_task0_and_full54_job_shapes(monkeypatch) -> None:
    store, prepared, _ = _fixture(monkeypatch)
    assert operator.validate_preparation_v1(prepared) == prepared
    smoke = operator.build_job_configuration_v1(
        preparation=prepared, scope=operator.TASK0_SCOPE, read_exact=store.read
    )
    full = operator.build_job_configuration_v1(
        preparation=prepared, scope=operator.FULL54_SCOPE, read_exact=store.read
    )
    assert smoke["task_count"] == smoke["parallelism"] == 1
    assert full["task_count"] == full["parallelism"] == 54
    assert smoke["environment"][panel.EXECUTION_SCOPE_ENV] == panel.TASK0_SCOPE
    assert full["environment"][panel.EXECUTION_SCOPE_ENV] == panel.FULL54_SCOPE
    assert smoke["expected_job_uid"] == panel.REUSED_JOB_UID
    assert smoke["image_uri"].endswith("@sha256:" + "2" * 64)
    assert operator.validate_exact_job_configuration_v1(
        _provider_job(smoke), configuration=smoke
    )["scope"] == operator.TASK0_SCOPE
    assert "create" not in operator.configure_argv_v1(
        flags_path="/tmp/l2b-flags.json"
    )


def test_operator_status_and_known_name_collection_gate_on_terminal_success(
    monkeypatch,
) -> None:
    store, prepared, manifest = _fixture(monkeypatch)
    monkeypatch.setattr(panel, "_validate_task_result_v1", lambda value: value)
    monkeypatch.setattr(panel, "_validate_task_result_lineage_v1", lambda **_: None)

    def seed_results(count: int) -> None:
        for index in range(count):
            body = {
                "task_index": index,
                "slate_id": manifest["task_rows"][index]["slate_id"],
                "task_result_sha256": f"{index + 1:064x}",
            }
            store.seed(manifest["task_rows"][index]["task_result_uri"], body)

    def open_known(uri: str, maximum_bytes: int):
        raw, identity = store.objects[uri]
        assert len(raw) <= maximum_bytes
        return raw, dict(identity)

    smoke_launch = operator.build_launch_result_v1(
        execution_name=f"{panel.REUSED_JOB_NAME}-execution-1",
        scope=operator.TASK0_SCOPE,
    )
    active = operator.build_execution_status_v1(
        _provider_execution(scope=operator.TASK0_SCOPE),
        execution_name=smoke_launch["execution_name"],
        scope=operator.TASK0_SCOPE,
    )
    with pytest.raises(
        operator.CorpusR6L2BPanelOperatorV1Error,
        match="before exact execution success",
    ):
        operator.collect_task_results_v1(
            preparation=prepared,
            launch_result=smoke_launch,
            execution_status=active,
            read_exact=store.read,
            open_known=lambda *_: (_ for _ in ()).throw(
                AssertionError("result must not open")
            ),
        )
    seed_results(54)
    smoke_status = operator.build_execution_status_v1(
        _provider_execution(scope=operator.TASK0_SCOPE, succeeded=1),
        execution_name=smoke_launch["execution_name"],
        scope=operator.TASK0_SCOPE,
    )
    smoke = operator.collect_task_results_v1(
        preparation=prepared,
        launch_result=smoke_launch,
        execution_status=smoke_status,
        read_exact=store.read,
        open_known=open_known,
    )
    assert smoke["task_result_count"] == 1
    assert smoke["real_artifact_smoke_complete"] is True
    assert smoke["panel_finalization_ready"] is False

    full_launch = operator.build_launch_result_v1(
        execution_name=f"{panel.REUSED_JOB_NAME}-execution-2",
        scope=operator.FULL54_SCOPE,
    )
    full_status = operator.build_execution_status_v1(
        {
            **_provider_execution(scope=operator.FULL54_SCOPE, succeeded=54),
            "metadata": {
                **_provider_execution(scope=operator.FULL54_SCOPE)["metadata"],
                "name": full_launch["execution_name"],
            },
        },
        execution_name=full_launch["execution_name"],
        scope=operator.FULL54_SCOPE,
    )
    full = operator.collect_task_results_v1(
        preparation=prepared,
        launch_result=full_launch,
        execution_status=full_status,
        read_exact=store.read,
        open_known=open_known,
    )
    assert full["task_result_count"] == 54
    assert full["panel_finalization_ready"] is True
    assert full["bucket_listing_performed"] is False


def test_task_dispatcher_accepts_explicit_task0_scope_only_for_index_zero(
    monkeypatch,
) -> None:
    manifest_identity = _identity("gs://fixture/l2b-manifest.json")
    manifest = {
        "source_commit_sha": "1" * 40,
        "immutable_image_digest": "sha256:" + "2" * 64,
        "reused_job_uid": panel.REUSED_JOB_UID,
    }
    monkeypatch.setattr(
        panel, "_open_manifest", lambda **_: (manifest, manifest_identity)
    )
    monkeypatch.setattr(
        panel,
        "execute_manifest_task_v1",
        lambda **kwargs: SimpleNamespace(
            task_result={
                "slate_id": "2023-w01",
                "task_result_sha256": "a" * 64,
            },
            task_result_identity=_identity("gs://fixture/task0-result.json"),
        ),
    )
    environment = {
        panel.ENABLE_ENV: "1",
        panel.MANIFEST_IDENTITY_ENV: legal.canonical_json_bytes(
            manifest_identity
        ).decode("utf-8"),
        panel.REUSED_JOB_UID_ENV: panel.REUSED_JOB_UID,
        panel.EXECUTION_SCOPE_ENV: panel.TASK0_SCOPE,
        "CODE_SHA": "1" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "2" * 64,
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    dispatcher_store = SimpleNamespace(
        read_exact=lambda _: b"", publish_create_once=lambda *_: {}
    )
    result = cli._execute_task(dispatcher_store)
    assert result["task_index"] == 0
    assert result["complete"] is True

    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "1")
    with pytest.raises(
        cli.RunCorpusR6L2BPanelCloudV1Error,
        match="only task index zero",
    ):
        cli._execute_task(dispatcher_store)


def test_operator_cli_configure_and_launch_use_existing_job_without_create(
    monkeypatch,
) -> None:
    store, prepared, _ = _fixture(monkeypatch)
    configuration = operator.build_job_configuration_v1(
        preparation=prepared, scope=operator.TASK0_SCOPE, read_exact=store.read
    )
    before = _provider_job(configuration)
    after = _provider_job(configuration)

    class ConfigureRunner:
        def __init__(self):
            self.calls = []

        def __call__(self, argv):
            self.calls.append(list(argv))
            payload = after if "update" in argv else before
            return {
                "returncode": 0,
                "stdout": json.dumps(payload).encode("utf-8"),
                "stderr": b"",
            }

    configure_runner = ConfigureRunner()
    configured = cli.configure_operator_v1(
        preparation=prepared,
        scope=operator.TASK0_SCOPE,
        store=SimpleNamespace(read_exact=store.read),
        runner=configure_runner,
    )
    assert configured["job_created"] is False
    assert any("update" in call for call in configure_runner.calls)
    assert all("create" not in call for call in configure_runner.calls)

    execution_name = f"{panel.REUSED_JOB_NAME}-execution-9"

    class LaunchRunner:
        def __init__(self):
            self.calls = []

        def __call__(self, argv):
            self.calls.append(list(argv))
            if "execute" in argv:
                stdout = (execution_name + "\n").encode("utf-8")
            else:
                stdout = json.dumps(before).encode("utf-8")
            return {"returncode": 0, "stdout": stdout, "stderr": b""}

    launch_runner = LaunchRunner()
    launched = cli.launch_operator_v1(
        preparation=prepared,
        scope=operator.TASK0_SCOPE,
        store=SimpleNamespace(read_exact=store.read),
        runner=launch_runner,
    )
    assert launched["execution_name"] == execution_name
    assert launched["expected_task_count"] == 1
    assert any("execute" in call for call in launch_runner.calls)
