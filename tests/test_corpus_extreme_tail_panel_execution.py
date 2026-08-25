from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_extreme_tail_panel_release as manifest_contract
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_support_switch as support
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as accepted
from nfl_dfs.research import corpus_v12_panel_index as panel


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE = {
    "uri": f"us-central1-docker.pkg.dev/example/research/t230@{DIGEST}",
    "digest": DIGEST,
}
OUTPUT_PREFIX = "gs://fixture-bucket/research/t230/run-001/"
_PANEL_FALSE_FIELDS = tuple(
    field for field in execution._FALSE_AUTHORITY_FIELDS
    if field != "r6_freeze_authority"
)


def _load_cli():
    path = ROOT / "scripts/run_corpus_extreme_tail_panel_v1.py"
    spec = importlib.util.spec_from_file_location("t230_panel_cli_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _identity(label: str, ordinal: int, *, payload: bytes | None = None) -> dict:
    raw = payload if payload is not None else f"{label}:{ordinal}".encode()
    return {
        "uri": f"gs://fixture-bucket/objects/{label}-{ordinal:04d}.json",
        "generation": str(10_000 + ordinal),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, dict[str, object]] = {}
        self.next_generation = 200_000
        self.publications: list[str] = []

    def add(
        self, body: Mapping[str, object], identity: Mapping[str, object]
    ) -> dict[str, object]:
        normalized = batch.normalize_object_identity(identity, label="fixture identity")
        raw = batch.canonical_json_bytes(body)
        assert len(raw) == normalized["bytes"]
        assert sha256(raw).hexdigest() == normalized["sha256"]
        key = (str(normalized["uri"]), str(normalized["generation"]))
        self.objects[key] = raw
        self.current[str(normalized["uri"])] = normalized
        return normalized

    def put(self, body: Mapping[str, object], *, uri: str) -> dict[str, object]:
        raw = batch.canonical_json_bytes(body)
        self.next_generation += 1
        return self.add(body, {
            "uri": uri,
            "generation": str(self.next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })

    def read(self, identity: Mapping[str, object]) -> bytes:
        normalized = batch.normalize_object_identity(identity, label="read identity")
        return self.objects[(str(normalized["uri"]), str(normalized["generation"]))]

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> Mapping[str, object]:
        self.publications.append(uri)
        if uri in self.current:
            retained_identity = self.current[uri]
            retained = self.read(retained_identity)
            if retained != raw:
                raise cli.CorpusExtremeTailPanelCLIError(
                    "create-once fixture collision differs"
                )
            return retained_identity
        body = cli._parse_json(raw, label="published fixture")
        assert batch.canonical_json_bytes(body) == raw
        return self.put(body, uri=uri)


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    retained = deepcopy(dict(body))
    retained[field] = batch.canonical_sha256(retained)
    return retained


def _build_panel() -> tuple[dict[str, object], dict[str, object]]:
    source_completion = _identity("source-completion", 0)
    members: list[dict[str, object]] = []
    object_ordinal = 100
    for source_ordinal in range(panel.V12_SOURCE_TASK_COUNT):
        lane_ordinal = 0 if source_ordinal < 28 else 1
        task_ordinal = source_ordinal if lane_ordinal == 0 else source_ordinal - 28
        arms = []
        for arm_ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER):
            arms.append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": arm_id,
                "result_identity": _identity("arm", object_ordinal),
            })
            object_ordinal += 1
        members.append({
            "slate_id": f"2023-w{source_ordinal + 1:02d}",
            "lane_ordinal": lane_ordinal,
            "lane_id": "v12a" if lane_ordinal == 0 else "v12b",
            "task_ordinal": task_ordinal,
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": sha256(
                f"source-task:{source_ordinal}".encode()
            ).hexdigest(),
            "task_acceptance_identity": _identity(
                "task-acceptance", 1_000 + source_ordinal
            ),
            "carrier_identity": _identity("carrier", 2_000 + source_ordinal),
            "arms": arms,
        })
    lanes = []
    for lane_ordinal, law in enumerate(panel.V12_LANE_LATTICE):
        lane_members = [
            row for row in members if row["lane_ordinal"] == lane_ordinal
        ]
        lanes.append({
            "lane_ordinal": lane_ordinal,
            "lane_id": law["lane_id"],
            "terminal_receipt_identity": _identity("terminal", lane_ordinal),
            "batch_completion_identity": _identity("completion", lane_ordinal),
            "batch_id": f"fixture-batch-{lane_ordinal}",
            "batch_mode": law["batch_mode"],
            "artifact_source_authority_completion": source_completion,
            "artifact_source_authority_completion_sha256": "c" * 64,
            "source_task_offset": law["source_task_offset"],
            "expected_task_count": law["task_count"],
            "accepted_task_count": law["task_count"],
            "accepted_task_ordinals": list(range(int(law["task_count"]))),
            "task_acceptance_identities_sha256": batch.canonical_sha256([
                row["task_acceptance_identity"] for row in lane_members
            ]),
            "carrier_identities_sha256": batch.canonical_sha256([
                row["carrier_identity"] for row in lane_members
            ]),
            "complete": True,
        })
    body: dict[str, object] = {
        "schema_version": panel.PANEL_INDEX_SCHEMA,
        "publication_mode": panel.PUBLICATION_MODE,
        "panel_id": "v12:" + batch.canonical_sha256([
            row["terminal_receipt_identity"] for row in lanes
        ]),
        "artifact_source_authority_completion": source_completion,
        "artifact_source_authority_completion_sha256": "c" * 64,
        "lane_count": 2,
        "lanes": lanes,
        "accepted_slate_count": panel.V12_SOURCE_TASK_COUNT,
        "accepted_slates": members,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": panel.V12_SOURCE_TASK_COUNT,
            "accepted_task_count": panel.V12_SOURCE_TASK_COUNT,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        **{field: False for field in _PANEL_FALSE_FIELDS},
    }
    body["panel_index_sha256"] = batch.canonical_sha256(body)
    identity = batch.object_identity_for_json(
        body,
        uri="gs://fixture-bucket/panels/foundry-v12-panel-index-v1.json",
        generation="99123",
    )
    return body, identity


def _panel_publication_receipt(
    panel_body: Mapping[str, object], panel_identity: Mapping[str, object]
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": execution.PANEL_PUBLICATION_RECEIPT_SCHEMA,
        "mode": "create_once",
        "panel_uri": panel_identity["uri"],
        "panel_id": panel_body["panel_id"],
        "panel_object_identity": panel_identity,
        "panel_content_sha256": panel_identity["sha256"],
        "panel_content_bytes": panel_identity["bytes"],
        "panel_index_sha256": panel_body["panel_index_sha256"],
        "lane_count": 2,
        "accepted_slate_count": 54,
        "exact_input_replay_verified": True,
        "published": True,
        **{field: False for field in _PANEL_FALSE_FIELDS},
    }
    body["publication_receipt_sha256"] = batch.canonical_sha256(body)
    return body


def _image_evidence(
    tmp_path: Path, store: MemoryStore
) -> tuple[dict[str, object], dict[str, object], Path]:
    rows = []
    files: dict[str, bytes] = {}
    for relative_path in execution._IMPLEMENTATION_PATHS:
        raw = (ROOT / relative_path).read_bytes()
        files[relative_path] = raw
        rows.append({
            "path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    callables = execution._critical_callable_rows(files)
    runtime_facts = execution._runtime_facts()
    body: dict[str, object] = {
        "schema_version": execution.IMAGE_EVIDENCE_SCHEMA,
        "source_commit_sha": COMMIT,
        "immutable_image": IMAGE,
        "implementation_files": rows,
        "implementation_files_sha256": batch.canonical_sha256(rows),
        "critical_callables": callables,
        "critical_callables_sha256": batch.canonical_sha256(callables),
        "runtime_facts": runtime_facts,
        "build_provenance": {
            "builder_id": "cloud-build-immutable-image-evidence-v1",
            "source_commit_sha": COMMIT,
            "immutable_image_digest": IMAGE["digest"],
            "implementation_files_sha256": batch.canonical_sha256(rows),
            "critical_callables_sha256": batch.canonical_sha256(callables),
            "runtime_facts_sha256": batch.canonical_sha256(runtime_facts),
        },
        "release_image_evidence": True,
        **{field: False for field in execution._FALSE_AUTHORITY_FIELDS},
    }
    body["image_evidence_sha256"] = batch.canonical_sha256(body)
    identity = store.put(
        body, uri=execution.image_evidence_uri_for_output_prefix(OUTPUT_PREFIX)
    )
    local_path = tmp_path / "image-evidence.json"
    local_path.write_bytes(batch.canonical_json_bytes(body) + b"\n")
    return body, identity, local_path


def _git_head(_root: Path) -> str:
    return COMMIT


def _git_blob(root: Path, commit: str, relative_path: str) -> bytes:
    assert commit == COMMIT
    return (root / relative_path).read_bytes()


def _git_status(_root: Path, _paths: Sequence[str]) -> bytes:
    return b""


def _process_instance(ordinal: int) -> dict[str, object]:
    body: dict[str, object] = {
        "evidence_class": "linux-proc-pid-start-boot-v1",
        "pid": 50_000 + ordinal,
        "process_start_ticks": 10_000_000 + ordinal,
        "boot_id": "fixture-boot-id",
        "pid_namespace_inode": 77_000,
    }
    body["process_instance_sha256"] = batch.canonical_sha256(body)
    return body


def _lane_envelope(
    identity: Mapping[str, object],
    completion_identity: Mapping[str, object],
    lane_ordinal: int,
) -> dict[str, object]:
    return {
        "schema_version": "corpus-parametric-batch-accepted/v1",
        "batch_mode": "lane-a-28-task" if lane_ordinal == 0 else "lane-b-26-task",
        "task_count": 28 if lane_ordinal == 0 else 26,
        "matrix_cell_count": 196 if lane_ordinal == 0 else 182,
        "batch_completion": dict(completion_identity),
        "batch_acceptance": dict(identity),
        "final_output_inventory_sha256": "d" * 64,
        "final_output_object_count": 1,
        "complete": True,
        "accepted": True,
    }


def _patch_panel_replay(monkeypatch, panel_body: Mapping[str, object]):
    derived: list[int] = []
    reopened: list[object] = []

    def derive(**kwargs):
        derived.append(kwargs["lane_ordinal"])
        return {
            "lane_ordinal": kwargs["lane_ordinal"],
            "lane_id": kwargs["lane_id"],
            "terminal_receipt_identity": kwargs["terminal_receipt_identity"],
            "tasks": [],
        }

    def reopen(**kwargs):
        reopened.append(kwargs["panel_index_identity"])
        assert [row["lane_ordinal"] for row in kwargs["lane_inputs"]] == [0, 1]
        return dict(panel_body)

    monkeypatch.setattr(panel, "derive_v12_lane_input", derive)
    monkeypatch.setattr(panel, "reopen_v12_panel_index", reopen)
    return derived, reopened


@pytest.fixture
def authority_fixture(tmp_path, monkeypatch):
    store = MemoryStore()
    panel_body, panel_identity = _build_panel()
    store.add(panel_body, panel_identity)
    publication = _panel_publication_receipt(panel_body, panel_identity)
    publication_path = tmp_path / "panel-index-live" / "published.json"
    publication_path.parent.mkdir()
    _write(publication_path, publication)
    lane_paths = (tmp_path / "lane-a.json", tmp_path / "lane-b.json")
    for lane_ordinal, lane_path in enumerate(lane_paths):
        _write(
            lane_path,
            _lane_envelope(
                panel_body["lanes"][lane_ordinal]["terminal_receipt_identity"],
                panel_body["lanes"][lane_ordinal]["batch_completion_identity"],
                lane_ordinal,
            ),
        )
    monkeypatch.setattr(execution, "FROZEN_G0_PANEL_URI", panel_identity["uri"])
    monkeypatch.setattr(
        execution, "FROZEN_G0_PUBLICATION_RECEIPT_PATH", publication_path
    )
    monkeypatch.setattr(
        execution,
        "FROZEN_G0_PUBLICATION_RECEIPT_RELATIVE_PATH",
        "reports/fixture-panel-index-live/published.json",
    )
    monkeypatch.setattr(execution, "FROZEN_G0_LANE_RECEIPT_PATHS", lane_paths)
    monkeypatch.setattr(
        execution,
        "FROZEN_G0_LANE_RECEIPT_RELATIVE_PATHS",
        ("reports/fixture-lane-a.json", "reports/fixture-lane-b.json"),
    )
    lock_path = tmp_path / "g0-authority-lock-v1.json"
    monkeypatch.setattr(execution, "FROZEN_G0_AUTHORITY_LOCK_PATH", lock_path)
    monkeypatch.setattr(
        execution,
        "FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH",
        "reports/fixture-g0-authority-lock-v1.json",
    )
    derived, reopened = _patch_panel_replay(monkeypatch, panel_body)
    authority_lock = execution.build_g0_authority_lock_v1(read_exact=store.read)
    _write(lock_path, authority_lock)
    tracked_lock_raw = lock_path.read_bytes()
    git_state = {
        "lock_tracked": True,
        "lock_dirty": False,
        "tracked_lock_raw": tracked_lock_raw,
    }

    def fixture_git_blob(root: Path, commit: str, relative_path: str) -> bytes:
        assert commit == COMMIT
        if relative_path == execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH:
            if not git_state["lock_tracked"]:
                raise FileNotFoundError(relative_path)
            return bytes(git_state["tracked_lock_raw"])
        return (root / relative_path).read_bytes()

    def fixture_git_status(_root: Path, paths: Sequence[str]) -> bytes:
        if (
            tuple(paths) == (execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH,)
            and git_state["lock_dirty"]
        ):
            return b" M reports/fixture-g0-authority-lock-v1.json\n"
        return b""

    evidence, evidence_identity, local_evidence = _image_evidence(tmp_path, store)
    monkeypatch.setattr(execution, "EXPECTED_BAKED_IMAGE_EVIDENCE_PATH", local_evidence)
    process_state = {"ordinal": 1}
    monkeypatch.setattr(
        execution,
        "_measure_process_instance",
        lambda: _process_instance(int(process_state["ordinal"])),
    )
    manifest = manifest_contract.build_t230_panel_execution_manifest_v1(
        panel_index=panel_body,
        panel_index_identity=panel_identity,
        source_commit_sha=COMMIT,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
    )
    manifest_identity = store.put(
        manifest, uri=execution.manifest_uri_for_output_prefix(OUTPUT_PREFIX)
    )
    authority = execution.build_t230_execution_authority_v1(
        manifest_identity=manifest_identity,
        image_evidence_identity=evidence_identity,
        read_exact=store.read,
        repository_root=ROOT,
        git_head=_git_head,
        git_blob=fixture_git_blob,
        git_status=fixture_git_status,
    )
    authority_identity = store.put(
        authority, uri=execution.authority_uri_for_output_prefix(OUTPUT_PREFIX)
    )
    return SimpleNamespace(
        store=store,
        panel=panel_body,
        panel_identity=panel_identity,
        publication=publication,
        publication_path=publication_path,
        lane_paths=lane_paths,
        authority_lock=authority_lock,
        lock_path=lock_path,
        tracked_lock_raw=tracked_lock_raw,
        git_state=git_state,
        git_blob=fixture_git_blob,
        git_status=fixture_git_status,
        evidence=evidence,
        evidence_identity=evidence_identity,
        local_evidence=local_evidence,
        process_state=process_state,
        manifest=manifest,
        manifest_identity=manifest_identity,
        authority=authority,
        authority_identity=authority_identity,
        derived=derived,
        reopened=reopened,
    )


class LazyWorldIDs(Sequence[object]):
    def __len__(self) -> int:
        return execution.WORLD_COUNT

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[value] for value in range(*index.indices(len(self)))]
        if type(index) is not int or index < 0 or index >= len(self):
            raise IndexError(index)
        return SimpleNamespace(
            block=execution.WORLD_BLOCKS[index // execution.WORLDS_PER_BLOCK],
            index=index % execution.WORLDS_PER_BLOCK,
        )


def _fake_reconstruction(
    panel_body: Mapping[str, object], source_ordinal: int
) -> accepted.AcceptedV12SlateReconstruction:
    member = panel_body["accepted_slates"][source_ordinal]
    world_artifacts = {
        role: _identity(f"world-{source_ordinal}-{role}", 3_000 + ordinal)
        for ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
    }
    matrix = _self_hash({
        "score_matrix_sha256": sha256(f"scores:{source_ordinal}".encode()).hexdigest(),
        "lineup_ids_sha256": sha256(f"lineups:{source_ordinal}".encode()).hexdigest(),
        "world_ids_sha256": "6" * 64,
        "shape": [1, execution.WORLD_COUNT],
    }, "matrix_binding_sha256")
    reconstruction = _self_hash({
        "matrix_binding": matrix,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }, "reconstruction_sha256")
    return accepted.AcceptedV12SlateReconstruction(
        slate_id=str(member["slate_id"]),
        panel_index_identity=batch.object_identity_for_json(
            panel_body,
            uri="gs://fixture-bucket/panels/foundry-v12-panel-index-v1.json",
            generation="99123",
        ),
        panel_index_sha256=str(panel_body["panel_index_sha256"]),
        accepted_slate_membership=member,
        task_acceptance_identity=member["task_acceptance_identity"],
        carrier_identity=member["carrier_identity"],
        later_source_freeze_identity=_identity(
            f"source-freeze-{source_ordinal}", 4_000 + source_ordinal
        ),
        world_artifact_identities=world_artifacts,
        imported=SimpleNamespace(
            compatibility_receipt={"compatibility_import_sha256": "7" * 64}
        ),
        reconstructed=SimpleNamespace(
            prepared=SimpleNamespace(world_ids=LazyWorldIDs()),
            provenance={
                "slate": {
                    "season": 2023,
                    "week": source_ordinal + 1,
                    "slate_id": member["slate_id"],
                },
                "candidate_provenance_sha256": sha256(
                    f"provenance:{source_ordinal}".encode()
                ).hexdigest(),
            },
            union_scores=np.zeros((1, execution.WORLD_COUNT), dtype=np.float64),
            reconstruction_receipt=reconstruction,
        ),
    )


def _input_binding(reconstructed) -> dict[str, object]:
    matrix = reconstructed.reconstruction_receipt["matrix_binding"]
    return {
        "reconstruction_sha256": reconstructed.reconstruction_receipt[
            "reconstruction_sha256"
        ],
        "candidate_provenance_sha256": reconstructed.provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding_sha256": matrix["matrix_binding_sha256"],
        "score_matrix_sha256": matrix["score_matrix_sha256"],
        "lineup_ids_sha256": matrix["lineup_ids_sha256"],
        "world_ids_sha256": matrix["world_ids_sha256"],
        "score_shape": matrix["shape"],
    }


def _fake_science(
    manifest: Mapping[str, object],
    reconstructed_slate,
    *,
    fold_passed: int,
    final_passed: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    reconstructed = reconstructed_slate.reconstructed
    input_binding = _input_binding(reconstructed)
    census_body = _self_hash({
        "schema_version": census.CENSUS_SCHEMA,
        "slate": reconstructed.provenance["slate"],
        "input_binding": input_binding,
        "world_basis": {"worlds_per_block": execution.WORLDS_PER_BLOCK},
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }, "support_census_sha256")
    retrieval = manifest["t230_retrieval_contract"]
    suite_body = _self_hash({
        "schema_version": suite.SUITE_SCHEMA,
        "slate": reconstructed.provenance["slate"],
        "input_binding": input_binding,
        "strategy_registry": retrieval["strategy_registry"],
        "strategy_registry_sha256": retrieval["strategy_registry_sha256"],
        "selector_implementation_contract": retrieval[
            "selector_implementation_contract"
        ],
        "entry_budgets": [4, 14, 80],
        "ranking_depth": 80,
        "fold_count": 5,
        "books_per_scope": 12,
        "cross_fit_book_count": 60,
        "final_fit_book_count": 12,
        "worlds_per_block": execution.WORLDS_PER_BLOCK,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }, "suite_sha256")
    policy_body = _self_hash({
        "schema_version": support.POLICY_SCHEMA,
        "slate": reconstructed.provenance["slate"],
        "input_binding": input_binding,
        "source_receipts": {
            "support_census_sha256": census_body["support_census_sha256"],
            "extreme_tail_suite_sha256": suite_body["suite_sha256"],
        },
        "entry_budgets": [4, 14, 80],
        "ranking_depth": 80,
        "folds": [
            {"support_gate": {"passed": ordinal < fold_passed}}
            for ordinal in range(5)
        ],
        "final_fit": {"support_gate": {"passed": bool(final_passed)}},
        "fold_gate_count": 5,
        "final_fit_gate_count": 1,
        "selected_book_count": 18,
        "worlds_per_block": execution.WORLDS_PER_BLOCK,
        "require_authoritative": True,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }, "support_switched_policy_sha256")
    return census_body, suite_body, policy_body


@pytest.fixture
def science_stubs(monkeypatch, authority_fixture):
    state = {"boundary": "all", "ordinal": 0}
    calls: list[tuple[str, int]] = []

    def counts(ordinal: int) -> tuple[int, int]:
        if state["boundary"] == "exact":
            return (5 if ordinal < 43 else (1 if ordinal == 43 else 0), int(ordinal < 44))
        if state["boundary"] == "negative":
            return (5 if ordinal < 43 else 0, int(ordinal < 43))
        return 5, 1

    def reconstruct(**kwargs):
        ordinal = int(kwargs["accepted_slate_membership"]["source_task_ordinal"])
        state["ordinal"] = ordinal
        calls.append(("reconstruct", ordinal))
        return _fake_reconstruction(authority_fixture.panel, ordinal)

    def science() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        ordinal = int(state["ordinal"])
        reconstructed = _fake_reconstruction(authority_fixture.panel, ordinal)
        fold, final = counts(ordinal)
        return _fake_science(
            authority_fixture.manifest,
            reconstructed,
            fold_passed=fold,
            final_passed=final,
        )

    monkeypatch.setattr(
        accepted, "reconstruct_one_accepted_v12_slate", reconstruct
    )
    monkeypatch.setattr(
        census,
        "build_extreme_tail_support_census",
        lambda **kwargs: (calls.append(("census", int(state["ordinal"]))) or science()[0]),
    )
    monkeypatch.setattr(
        suite,
        "run_extreme_tail_retrieval_suite_v1",
        lambda **kwargs: (calls.append(("suite", int(state["ordinal"]))) or science()[1]),
    )
    monkeypatch.setattr(
        support,
        "build_extreme_tail_support_switched_policy_v1",
        lambda **kwargs: (calls.append(("support", int(state["ordinal"]))) or science()[2]),
    )
    monkeypatch.setattr(support, "_validate_policy_structure", lambda value: value)
    monkeypatch.setattr(execution, "_world_ids", lambda value: [{"block": "R0", "index": 0}])
    return state, calls


def _runtime_kwargs(fixture) -> dict[str, object]:
    return {
        "read_exact": fixture.store.read,
        "repository_root": ROOT,
        "git_head": _git_head,
        "git_blob": fixture.git_blob,
        "git_status": fixture.git_status,
    }


def _publish_runtime(
    fixture, *, role: str, ordinal: int | None, process_ordinal: int
) -> tuple[dict[str, object], dict[str, object]]:
    fixture.process_state["ordinal"] = process_ordinal
    body = execution.measure_t230_runtime_v1(
        role=role,
        output_prefix=OUTPUT_PREFIX,
        repository_root=ROOT,
        image_evidence_identity=fixture.evidence_identity,
        read_exact=fixture.store.read,
        git_head=_git_head,
        git_blob=fixture.git_blob,
        git_status=fixture.git_status,
    )
    identity = fixture.store.put(
        body,
        uri=execution.runtime_measurement_uri_for_output_prefix(
            OUTPUT_PREFIX, role=role, source_ordinal=ordinal
        ),
    )
    return body, identity


def _worker_result(fixture, ordinal: int = 0) -> dict[str, object]:
    _worker, worker_identity = _publish_runtime(
        fixture,
        role="worker",
        ordinal=ordinal,
        process_ordinal=1_000 + ordinal * 2,
    )
    return execution.execute_t230_panel_slate_v1(
        execution_authority_identity=fixture.authority_identity,
        worker_runtime_measurement_identity=worker_identity,
        source_ordinal=ordinal,
        **_runtime_kwargs(fixture),
    )


def _publish_and_verify(fixture, ordinal: int) -> tuple[dict, dict, dict]:
    result = _worker_result(fixture, ordinal)
    result_identity = fixture.store.put(result, uri=str(result["result_uri"]))
    _verifier, verifier_identity = _publish_runtime(
        fixture,
        role="verifier",
        ordinal=ordinal,
        process_ordinal=1_001 + ordinal * 2,
    )
    acceptance = execution.verify_t230_panel_slate_v1(
        execution_authority_identity=fixture.authority_identity,
        source_ordinal=ordinal,
        result_identity=result_identity,
        verifier_runtime_measurement_identity=verifier_identity,
        **_runtime_kwargs(fixture),
    )
    acceptance_identity = fixture.store.put(
        acceptance, uri=str(acceptance["acceptance_uri"])
    )
    return result, result_identity, acceptance_identity


def _finalizer_runtime(fixture) -> dict[str, object]:
    _body, identity = _publish_runtime(
        fixture,
        role="finalizer",
        ordinal=None,
        process_ordinal=90_000,
    )
    return identity


def _rehash(body: dict[str, object], field: str) -> None:
    body.pop(field, None)
    body[field] = batch.canonical_sha256(body)


def _write(path: Path, body: Mapping[str, object]) -> None:
    path.write_bytes(batch.canonical_json_bytes(body) + b"\n")


def test_public_contract_literals_bind_transitive_code_and_false_authority(
    authority_fixture,
) -> None:
    worker = execution.frozen_t230_worker_implementation_v1()
    verifier = execution.frozen_t230_verifier_implementation_v1()
    finalizer = execution.frozen_t230_finalizer_implementation_v1()
    assert worker["implementation_sha256"] == (
        execution.EXPECTED_WORKER_IMPLEMENTATION_SHA256
    )
    assert verifier["implementation_sha256"] == (
        execution.EXPECTED_VERIFIER_IMPLEMENTATION_SHA256
    )
    assert finalizer["implementation_sha256"] == (
        execution.EXPECTED_FINALIZER_IMPLEMENTATION_SHA256
    )
    assert worker["implementation_sha256"] != verifier["implementation_sha256"]
    assert finalizer["science_recomputation"] is False
    assert len(execution._IMPLEMENTATION_PATHS) == 25
    assert "src/nfl_dfs/research/corpus_v12_import.py" in execution._IMPLEMENTATION_PATHS
    assert "src/nfl_dfs/research/corpus_retrieval_engine.py" in (
        execution._IMPLEMENTATION_PATHS
    )
    assert "src/nfl_dfs/research/residual_world_run_context.py" in (
        execution._IMPLEMENTATION_PATHS
    )
    callable_names = [name for _path, name in execution._CRITICAL_CALLABLE_SPECS]
    assert callable_names[:6] == [
        "measure_t230_runtime_v1",
        "execute_t230_panel_slate_v1",
        "verify_t230_panel_slate_v1",
        "build_t230_panel_release_v1",
        "GCSExactCreateOnceStore.read",
        "GCSExactCreateOnceStore.publish_create_once",
    ]
    assert authority_fixture.authority["panel_publication_cloud_attested"] is False
    assert authority_fixture.authority["simulated_execution_only"] is True
    assert authority_fixture.authority["uses_realized_outcomes"] is False


def test_same_id_implementation_contract_drift_fails_closed(monkeypatch) -> None:
    drifted = dict(execution._WORKER_IMPLEMENTATION_BODY)
    drifted["ranking_depth"] = 79
    monkeypatch.setattr(execution, "_WORKER_IMPLEMENTATION_BODY", drifted)
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="implementation contract drifted",
    ):
        execution.frozen_t230_worker_implementation_v1()


def test_runtime_measures_blobs_callables_versions_dirty_state_and_fixed_bake(
    authority_fixture, monkeypatch, tmp_path
) -> None:
    measured = execution.measure_t230_runtime_v1(
        role="worker",
        output_prefix=OUTPUT_PREFIX,
        repository_root=ROOT,
        image_evidence_identity=authority_fixture.evidence_identity,
        read_exact=authority_fixture.store.read,
        git_head=_git_head,
        git_blob=authority_fixture.git_blob,
        git_status=authority_fixture.git_status,
    )
    assert measured["release_runtime_verified"] is True
    assert measured["measured_files"] == authority_fixture.evidence[
        "implementation_files"
    ]
    assert measured["measured_callables"] == authority_fixture.evidence[
        "critical_callables"
    ]
    assert measured["runtime_facts"]["numpy_version"] == np.__version__
    assert measured["process_instance_sha256"] == measured["process_instance"][
        "process_instance_sha256"
    ]
    dirty = execution.measure_t230_runtime_v1(
        role="worker",
        output_prefix=OUTPUT_PREFIX,
        repository_root=ROOT,
        image_evidence_identity=authority_fixture.evidence_identity,
        read_exact=authority_fixture.store.read,
        git_head=_git_head,
        git_blob=authority_fixture.git_blob,
        git_status=lambda _root, paths: (
            b""
            if tuple(paths)
            == (execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH,)
            else b" M critical.py\n"
        ),
    )
    assert dirty["critical_paths_clean"] is False
    assert dirty["release_runtime_verified"] is False
    monkeypatch.setattr(
        execution,
        "EXPECTED_BAKED_IMAGE_EVIDENCE_PATH",
        tmp_path / "fixed-baked-evidence-is-absent.json",
    )
    mechanics = execution.measure_t230_runtime_v1(
        role="worker",
        output_prefix=OUTPUT_PREFIX,
        repository_root=ROOT,
        image_evidence_identity=authority_fixture.evidence_identity,
        read_exact=authority_fixture.store.read,
        git_head=_git_head,
        git_blob=authority_fixture.git_blob,
        git_status=authority_fixture.git_status,
    )
    assert mechanics["local_image_evidence_matches_pinned_bytes"] is False
    assert mechanics["release_runtime_verified"] is False


def test_runtime_rejects_checkout_blob_and_baked_evidence_drift(
    authority_fixture, monkeypatch
) -> None:
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="Git blob",
    ):
        execution.measure_t230_runtime_v1(
            role="worker",
            output_prefix=OUTPUT_PREFIX,
            repository_root=ROOT,
            image_evidence_identity=authority_fixture.evidence_identity,
            read_exact=authority_fixture.store.read,
            git_head=_git_head,
            git_blob=lambda root, commit, path: (
                authority_fixture.git_blob(root, commit, path)
                if path == execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH
                else b"different committed bytes"
            ),
            git_status=authority_fixture.git_status,
        )
    authority_fixture.local_evidence.write_bytes(b"{}\n")
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="baked image evidence bytes differ",
    ):
        execution.measure_t230_runtime_v1(
            role="worker",
            output_prefix=OUTPUT_PREFIX,
            repository_root=ROOT,
            image_evidence_identity=authority_fixture.evidence_identity,
            read_exact=authority_fixture.store.read,
            git_head=_git_head,
            git_blob=authority_fixture.git_blob,
            git_status=authority_fixture.git_status,
        )


def test_fixed_g0_publication_replays_receipt_lanes_and_semantic_panel_id(
    authority_fixture,
) -> None:
    binding, receipt, reopened, lanes, g0_binding = (
        execution.replay_published_v12_panel_v1(
        repository_root=ROOT,
        read_exact=authority_fixture.store.read,
        git_head=_git_head,
        git_blob=authority_fixture.git_blob,
        git_status=authority_fixture.git_status,
    ))
    terminals = [row["terminal_receipt_identity"] for row in reopened["lanes"]]
    assert reopened["panel_id"] == "v12:" + batch.canonical_sha256(terminals)
    assert binding["path"] == str(authority_fixture.publication_path)
    assert binding["publication_receipt_sha256"] == receipt[
        "publication_receipt_sha256"
    ]
    assert [row["path"] for row in lanes] == [
        str(path) for path in authority_fixture.lane_paths
    ]
    assert authority_fixture.derived[-2:] == [0, 1]
    assert g0_binding["tracked_at_head"] is True
    assert g0_binding["g0_authority_lock_sha256"] == authority_fixture.authority_lock[
        "g0_authority_lock_sha256"
    ]


def test_g0_lock_self_hash_exactly_binds_all_three_files_and_panel(
    authority_fixture,
) -> None:
    lock = execution.validate_g0_authority_lock_v1(
        authority_fixture.authority_lock,
        read_exact=authority_fixture.store.read,
    )
    assert lock["official_publication_receipt_file"]["sha256"] == sha256(
        authority_fixture.publication_path.read_bytes()
    ).hexdigest()
    assert [row["terminal_receipt_file"]["sha256"] for row in lock[
        "lane_terminal_receipts"
    ]] == [sha256(path.read_bytes()).hexdigest() for path in authority_fixture.lane_paths]
    terminals = [
        row["terminal_receipt_identity"] for row in lock["lane_terminal_receipts"]
    ]
    assert lock["panel_id"] == "v12:" + batch.canonical_sha256(terminals)
    assert lock["panel_uri"] == authority_fixture.panel_identity["uri"]
    assert lock["panel_object_identity"] == authority_fixture.panel_identity


def test_g0_lock_replays_across_checkout_roots_and_secure_modes(
    authority_fixture, monkeypatch, tmp_path
) -> None:
    cloud_root = tmp_path / "cloud-checkout"
    publication_path = cloud_root / "panel-index-live" / "published.json"
    publication_path.parent.mkdir(parents=True)
    _write(publication_path, authority_fixture.publication)
    publication_path.chmod(0o400)
    lane_paths = (cloud_root / "lane-a.json", cloud_root / "lane-b.json")
    for ordinal, lane_path in enumerate(lane_paths):
        _write(
            lane_path,
            _lane_envelope(
                authority_fixture.panel["lanes"][ordinal][
                    "terminal_receipt_identity"
                ],
                authority_fixture.panel["lanes"][ordinal][
                    "batch_completion_identity"
                ],
                ordinal,
            ),
        )
        lane_path.chmod(0o400)
    monkeypatch.setattr(
        execution, "FROZEN_G0_PUBLICATION_RECEIPT_PATH", publication_path
    )
    monkeypatch.setattr(execution, "FROZEN_G0_LANE_RECEIPT_PATHS", lane_paths)
    assert execution.build_g0_authority_lock_v1(
        read_exact=authority_fixture.store.read
    ) == authority_fixture.authority_lock
    assert execution.validate_g0_authority_lock_v1(
        authority_fixture.authority_lock,
        read_exact=authority_fixture.store.read,
    ) == authority_fixture.authority_lock


def test_g0_portable_projection_excludes_host_path_owner_and_mode() -> None:
    content = {"sha256": "a" * 64, "bytes": 17}
    local = execution._portable_g0_file_projection(
        {
            "path": "/home/operator/reviewed.json",
            **content,
            "owner_uid": 1000,
            "mode_octal": "0600",
        },
        relative_path="reports/reviewed.json",
        label="local G0 receipt",
    )
    cloud = execution._portable_g0_file_projection(
        {
            "path": "/home/erich/projects/nfl-predictions/reports/reviewed.json",
            **content,
            "owner_uid": 0,
            "mode_octal": "0400",
        },
        relative_path="reports/reviewed.json",
        label="cloud G0 receipt",
    )
    assert local == cloud == {
        "relative_path": "reports/reviewed.json",
        **content,
    }
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="relative path differs",
    ):
        execution._portable_g0_file_projection(
            local,
            relative_path="../reviewed.json",
            label="adversarial G0 receipt",
        )


@pytest.mark.parametrize("attack", ["untracked", "dirty"])
def test_prepare_rejects_untracked_or_dirty_g0_lock(
    authority_fixture, attack
) -> None:
    authority_fixture.git_state[
        "lock_tracked" if attack == "untracked" else "lock_dirty"
    ] = False if attack == "untracked" else True
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.replay_published_v12_panel_v1(
            repository_root=ROOT,
            read_exact=authority_fixture.store.read,
            git_head=_git_head,
            git_blob=authority_fixture.git_blob,
            git_status=authority_fixture.git_status,
        )


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "unsafe_mode"])
def test_g0_lock_no_follow_owner_mode_and_link_checks(
    authority_fixture, tmp_path, attack
) -> None:
    if attack == "symlink":
        target = tmp_path / "lock-target.json"
        target.write_bytes(authority_fixture.tracked_lock_raw)
        authority_fixture.lock_path.unlink()
        authority_fixture.lock_path.symlink_to(target)
    elif attack == "hardlink":
        (tmp_path / "lock-hardlink.json").hardlink_to(authority_fixture.lock_path)
    else:
        authority_fixture.lock_path.chmod(0o666)
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.replay_published_v12_panel_v1(
            repository_root=ROOT,
            read_exact=authority_fixture.store.read,
            git_head=_git_head,
            git_blob=authority_fixture.git_blob,
            git_status=authority_fixture.git_status,
        )


@pytest.mark.parametrize("attack", ["receipt_symlink", "lane_hardlink", "lane_mode"])
def test_locked_raw_g0_files_have_no_follow_mode_and_link_checks(
    authority_fixture, tmp_path, attack
) -> None:
    if attack == "receipt_symlink":
        target = tmp_path / "publication-target.json"
        target.write_bytes(authority_fixture.publication_path.read_bytes())
        authority_fixture.publication_path.unlink()
        authority_fixture.publication_path.symlink_to(target)
    elif attack == "lane_hardlink":
        (tmp_path / "lane-hardlink.json").hardlink_to(
            authority_fixture.lane_paths[0]
        )
    else:
        authority_fixture.lane_paths[0].chmod(0o666)
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.replay_published_v12_panel_v1(
            repository_root=ROOT,
            read_exact=authority_fixture.store.read,
            git_head=_git_head,
            git_blob=authority_fixture.git_blob,
            git_status=authority_fixture.git_status,
        )


def test_coherent_alternate_lane_panel_and_lock_cannot_preempt_tracked_lock(
    authority_fixture, monkeypatch
) -> None:
    alternate = deepcopy(authority_fixture.panel)
    alternate_terminal = _identity("alternate-terminal", 9_001)
    alternate["lanes"][0]["terminal_receipt_identity"] = alternate_terminal
    terminals = [row["terminal_receipt_identity"] for row in alternate["lanes"]]
    alternate["panel_id"] = "v12:" + batch.canonical_sha256(terminals)
    _rehash(alternate, "panel_index_sha256")
    alternate_identity = authority_fixture.store.put(
        alternate, uri=str(authority_fixture.panel_identity["uri"])
    )
    lane = _lane_envelope(
        alternate_terminal,
        alternate["lanes"][0]["batch_completion_identity"],
        0,
    )
    _write(authority_fixture.lane_paths[0], lane)
    publication = _panel_publication_receipt(alternate, alternate_identity)
    _write(authority_fixture.publication_path, publication)
    monkeypatch.setattr(
        panel, "reopen_v12_panel_index", lambda **_kwargs: deepcopy(alternate)
    )
    alternate_lock = execution.build_g0_authority_lock_v1(
        read_exact=authority_fixture.store.read
    )
    _write(authority_fixture.lock_path, alternate_lock)
    assert authority_fixture.lock_path.read_bytes() != authority_fixture.tracked_lock_raw
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="bytes differ from current Git HEAD",
    ):
        execution.replay_published_v12_panel_v1(
            repository_root=ROOT,
            read_exact=authority_fixture.store.read,
            git_head=_git_head,
            git_blob=authority_fixture.git_blob,
            git_status=authority_fixture.git_status,
        )


@pytest.mark.parametrize("attack", ["receipt", "lane", "panel_generation", "panel_id"])
def test_fixed_g0_replay_rejects_replacement_splice_and_drift(
    authority_fixture, attack
) -> None:
    if attack == "receipt":
        authority_fixture.publication_path.write_bytes(
            batch.canonical_json_bytes(authority_fixture.publication)
        )
    elif attack == "lane":
        lane = cli._parse_json(
            authority_fixture.lane_paths[0].read_bytes(), label="lane"
        )
        lane["batch_acceptance"] = _identity("alternate-terminal", 9_001)
        _write(authority_fixture.lane_paths[0], lane)
    elif attack == "panel_generation":
        alternate_identity = authority_fixture.store.put(
            authority_fixture.panel,
            uri=str(authority_fixture.panel_identity["uri"]),
        )
        receipt = deepcopy(authority_fixture.publication)
        receipt["panel_object_identity"] = alternate_identity
        receipt["panel_content_sha256"] = alternate_identity["sha256"]
        receipt["panel_content_bytes"] = alternate_identity["bytes"]
        _rehash(receipt, "publication_receipt_sha256")
        _write(authority_fixture.publication_path, receipt)
    else:
        receipt = deepcopy(authority_fixture.publication)
        receipt["panel_id"] = "v12:" + "f" * 64
        _rehash(receipt, "publication_receipt_sha256")
        _write(authority_fixture.publication_path, receipt)
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.reopen_t230_execution_authority_v1(
            execution_authority_identity=authority_fixture.authority_identity,
            **_runtime_kwargs(authority_fixture),
        )


def test_worker_result_is_nonterminal_and_distinct_verifier_recomputes(
    science_stubs, authority_fixture
) -> None:
    _state, calls = science_stubs
    result, _result_identity, acceptance_identity = _publish_and_verify(
        authority_fixture, 0
    )
    acceptance = cli._parse_json(
        authority_fixture.store.read(acceptance_identity), label="acceptance"
    )
    assert result["configuration"]["worlds_per_block"] == 10_000
    assert result["configuration"]["entry_budgets"] == [4, 14, 80]
    assert "t230_slate_acceptance_sha256" not in result
    assert acceptance["verification"]["full_result_byte_equality_verified"] is True
    assert acceptance["worker_runtime_binding"]["process_instance_sha256"] != (
        acceptance["verifier_runtime_binding"]["process_instance_sha256"]
    )
    assert [name for name, _ in calls].count("reconstruct") == 2


def test_shared_science_stack_uses_exact_authoritative_no_knob_calls(
    authority_fixture, monkeypatch
) -> None:
    reconstructed_slate = _fake_reconstruction(authority_fixture.panel, 0)
    world_ids = [{"block": "R0", "index": 0}]
    calls: list[tuple[str, dict[str, object]]] = []
    census_receipt = {"support_census_sha256": "1" * 64}
    suite_receipt = {"suite_sha256": "2" * 64}
    policy_receipt = {"support_switched_policy_sha256": "3" * 64}
    monkeypatch.setattr(execution, "_world_ids", lambda _value: world_ids)

    def build_census(**kwargs):
        calls.append(("census", kwargs))
        return census_receipt

    def build_suite(**kwargs):
        calls.append(("suite", kwargs))
        return suite_receipt

    def build_support(**kwargs):
        calls.append(("support", kwargs))
        return policy_receipt

    monkeypatch.setattr(census, "build_extreme_tail_support_census", build_census)
    monkeypatch.setattr(suite, "run_extreme_tail_retrieval_suite_v1", build_suite)
    monkeypatch.setattr(
        support, "build_extreme_tail_support_switched_policy_v1", build_support
    )
    monkeypatch.setattr(
        execution,
        "_support_observation",
        lambda _value: pytest.fail("shared science helper inspected support effects"),
    )

    retained = execution._execute_t230_science_stack_v1(reconstructed_slate)
    assert [name for name, _kwargs in calls] == ["census", "suite", "support"]
    assert retained.support_census is census_receipt
    assert retained.extreme_tail_suite is suite_receipt
    assert retained.support_policy is policy_receipt
    for _name, kwargs in calls:
        assert kwargs["worlds_per_block"] is None
        assert kwargs["require_authoritative"] is True
    assert calls[0][1]["world_ids"] is world_ids
    assert calls[1][1]["entry_budgets"] == execution.ENTRY_BUDGETS
    assert calls[2][1]["support_census"] is census_receipt
    assert calls[2][1]["extreme_tail_suite"] is suite_receipt


def test_production_worker_delegates_to_shared_science_stack(
    science_stubs, authority_fixture, monkeypatch
) -> None:
    original = execution._execute_t230_science_stack_v1
    delegated: list[str] = []

    def shared(reconstructed_slate):
        delegated.append(reconstructed_slate.slate_id)
        return original(reconstructed_slate)

    monkeypatch.setattr(execution, "_execute_t230_science_stack_v1", shared)
    result = _worker_result(authority_fixture, 0)
    assert result["source_ordinal"] == 0
    assert delegated == ["2023-w01"]


def test_verifier_rejects_same_process_instance(
    science_stubs, authority_fixture
) -> None:
    result = _worker_result(authority_fixture, 0)
    result_identity = authority_fixture.store.put(result, uri=str(result["result_uri"]))
    _receipt, verifier_identity = _publish_runtime(
        authority_fixture,
        role="verifier",
        ordinal=0,
        process_ordinal=1_000,
    )
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="distinct process instances",
    ):
        execution.verify_t230_panel_slate_v1(
            execution_authority_identity=authority_fixture.authority_identity,
            source_ordinal=0,
            result_identity=result_identity,
            verifier_runtime_measurement_identity=verifier_identity,
            **_runtime_kwargs(authority_fixture),
        )


@pytest.mark.parametrize("attack", ["gate", "rank"])
def test_verifier_rejects_coherently_rehashed_forged_gate_or_rank(
    science_stubs, authority_fixture, attack
) -> None:
    result = _worker_result(authority_fixture)
    forged = deepcopy(result)
    if attack == "gate":
        forged["support_switched_policy"]["folds"][0]["support_gate"]["passed"] = False
        forged["support_observation"]["fold_gate_passed"] = 4
        _rehash(forged["support_switched_policy"], "support_switched_policy_sha256")
    else:
        forged["extreme_tail_suite"]["ranking_depth"] = 79
        _rehash(forged["extreme_tail_suite"], "suite_sha256")
        forged["support_switched_policy"]["source_receipts"][
            "extreme_tail_suite_sha256"
        ] = forged["extreme_tail_suite"]["suite_sha256"]
        _rehash(forged["support_switched_policy"], "support_switched_policy_sha256")
    _rehash(forged, "t230_slate_result_sha256")
    forged_identity = authority_fixture.store.put(
        forged, uri=str(result["result_uri"])
    )
    _receipt, verifier_identity = _publish_runtime(
        authority_fixture, role="verifier", ordinal=0, process_ordinal=1_001
    )
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.verify_t230_panel_slate_v1(
            execution_authority_identity=authority_fixture.authority_identity,
            source_ordinal=0,
            result_identity=forged_identity,
            verifier_runtime_measurement_identity=verifier_identity,
            **_runtime_kwargs(authority_fixture),
        )


def test_nested_outcome_authority_synonym_fails_after_coherent_rehash(
    science_stubs, authority_fixture
) -> None:
    result = _worker_result(authority_fixture)
    forged = deepcopy(result)
    forged["support_census"]["outcome_authority"] = False
    _rehash(forged["support_census"], "support_census_sha256")
    forged["support_switched_policy"]["source_receipts"][
        "support_census_sha256"
    ] = forged["support_census"]["support_census_sha256"]
    _rehash(forged["support_switched_policy"], "support_switched_policy_sha256")
    _rehash(forged, "t230_slate_result_sha256")
    forged_identity = authority_fixture.store.put(forged, uri=str(result["result_uri"]))
    _receipt, verifier_identity = _publish_runtime(
        authority_fixture, role="verifier", ordinal=0, process_ordinal=1_001
    )
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="unregistered authority surface",
    ):
        execution.verify_t230_panel_slate_v1(
            execution_authority_identity=authority_fixture.authority_identity,
            source_ordinal=0,
            result_identity=forged_identity,
            verifier_runtime_measurement_identity=verifier_identity,
            **_runtime_kwargs(authority_fixture),
        )


def test_result_member_clone_and_content_identity_splices_fail(
    science_stubs, authority_fixture
) -> None:
    result = _worker_result(authority_fixture, 0)
    wrong_uri_identity = authority_fixture.store.put(
        result, uri=OUTPUT_PREFIX + "wrong/result.json"
    )
    _receipt, verifier_identity = _publish_runtime(
        authority_fixture, role="verifier", ordinal=0, process_ordinal=1_001
    )
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError, match="URI differs"
    ):
        execution.verify_t230_panel_slate_v1(
            execution_authority_identity=authority_fixture.authority_identity,
            source_ordinal=0,
            result_identity=wrong_uri_identity,
            verifier_runtime_measurement_identity=verifier_identity,
            **_runtime_kwargs(authority_fixture),
        )
    correct_identity = authority_fixture.store.put(result, uri=str(result["result_uri"]))
    _receipt, wrong_member_verifier = _publish_runtime(
        authority_fixture, role="verifier", ordinal=1, process_ordinal=1_003
    )
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.verify_t230_panel_slate_v1(
            execution_authority_identity=authority_fixture.authority_identity,
            source_ordinal=1,
            result_identity=correct_identity,
            verifier_runtime_measurement_identity=wrong_member_verifier,
            **_runtime_kwargs(authority_fixture),
        )


def test_acceptance_validation_reconstructs_source_and_rejects_clone(
    science_stubs, authority_fixture
) -> None:
    _result, _result_identity, acceptance_identity = _publish_and_verify(
        authority_fixture, 0
    )
    acceptance = cli._parse_json(
        authority_fixture.store.read(acceptance_identity), label="acceptance"
    )
    assert execution.validate_t230_slate_acceptance_v1(
        acceptance,
        execution_authority_identity=authority_fixture.authority_identity,
        source_ordinal=0,
        **_runtime_kwargs(authority_fixture),
    ) == acceptance
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.validate_t230_slate_acceptance_v1(
            acceptance,
            execution_authority_identity=authority_fixture.authority_identity,
            source_ordinal=1,
            **_runtime_kwargs(authority_fixture),
        )


def test_finalizer_structurally_replays_54_without_third_science_pass(
    science_stubs, authority_fixture, monkeypatch
) -> None:
    state, calls = science_stubs
    state["boundary"] = "exact"
    identities = [
        _publish_and_verify(authority_fixture, ordinal)[2]
        for ordinal in range(54)
    ]
    finalizer_identity = _finalizer_runtime(authority_fixture)
    before_finalizer = len(calls)
    release = execution.build_t230_panel_release_v1(
        execution_authority_identity=authority_fixture.authority_identity,
        finalizer_runtime_measurement_identity=finalizer_identity,
        acceptance_identities=identities,
        **_runtime_kwargs(authority_fixture),
    )
    assert release["fold_boundary"]["passed"] == 216
    assert release["fold_boundary"]["total"] == 270
    assert release["final_fit_boundary"]["passed"] == 44
    assert release["final_fit_boundary"]["total"] == 54
    assert release["joint_support_boundary_passed"] is True
    assert release["verification"]["finalizer_science_recomputation_performed"] is False
    assert len(calls) == before_finalizer
    assert execution.validate_t230_panel_release_v1(
        release,
        execution_authority_identity=authority_fixture.authority_identity,
        finalizer_runtime_measurement_identity=finalizer_identity,
        acceptance_identities=identities,
        **_runtime_kwargs(authority_fixture),
    ) == release
    assert len(calls) == before_finalizer
    authority_fixture.process_state["ordinal"] = 90_001
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="fresh local replay",
    ):
        execution.validate_t230_panel_release_v1(
            release,
            execution_authority_identity=authority_fixture.authority_identity,
            finalizer_runtime_measurement_identity=finalizer_identity,
            acceptance_identities=identities,
            **_runtime_kwargs(authority_fixture),
        )
    monkeypatch.setattr(
        execution, "_runtime_facts", lambda: {"controller": "not-image-D"}
    )
    assert execution.validate_published_t230_panel_release_v1(
        release,
        execution_authority_identity=authority_fixture.authority_identity,
        acceptance_identities=identities,
        read_exact=authority_fixture.store.read,
    ) == release
    assert len(calls) == before_finalizer


@pytest.mark.parametrize("attack", ["missing", "duplicate", "reordered"])
def test_finalizer_rejects_incomplete_duplicate_or_reordered_acceptances(
    science_stubs, authority_fixture, attack
) -> None:
    identities = [
        _publish_and_verify(authority_fixture, ordinal)[2]
        for ordinal in range(54)
    ]
    if attack == "missing":
        identities.pop()
    elif attack == "duplicate":
        identities[-1] = identities[0]
    else:
        identities[0], identities[1] = identities[1], identities[0]
    finalizer_identity = _finalizer_runtime(authority_fixture)
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution.build_t230_panel_release_v1(
            execution_authority_identity=authority_fixture.authority_identity,
            finalizer_runtime_measurement_identity=finalizer_identity,
            acceptance_identities=identities,
            **_runtime_kwargs(authority_fixture),
        )


def _patch_cli_runtime(monkeypatch, fixture) -> None:
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", ROOT)
    monkeypatch.setattr(cli, "_git_head", _git_head)
    monkeypatch.setattr(cli, "_git_blob", fixture.git_blob)
    monkeypatch.setattr(cli, "_git_status", fixture.git_status)


def test_cli_run_and_independent_verify_publish_generation_pinned_receipts(
    tmp_path, monkeypatch, science_stubs, authority_fixture
) -> None:
    _patch_cli_runtime(monkeypatch, authority_fixture)
    authority_path = tmp_path / "authority.json"
    result_path = tmp_path / "result.json"
    _write(authority_path, authority_fixture.authority_identity)
    before = len(authority_fixture.store.publications)
    authority_fixture.process_state["ordinal"] = 30_000
    worker_receipt = cli.run([
        "run-slate",
        "--execution-authority-identity", str(authority_path),
        "--source-ordinal", "0",
        "--receipt-output", str(result_path),
        "--execute",
    ], store=authority_fixture.store)
    assert worker_receipt["terminal_acceptance_published"] is False
    assert "acceptance_identity" not in worker_receipt
    assert authority_fixture.store.publications[before:] == [
        worker_receipt["worker_runtime_measurement_identity"]["uri"],
        worker_receipt["result_identity"]["uri"],
    ]
    verify_path = tmp_path / "verify.json"
    authority_fixture.process_state["ordinal"] = 30_001
    verifier_receipt = cli.run([
        "verify-slate",
        "--execution-authority-identity", str(authority_path),
        "--source-ordinal", "0",
        "--result-identity", str(result_path),
        "--receipt-output", str(verify_path),
        "--execute",
    ], store=authority_fixture.store)
    assert verifier_receipt["operation"] == "verify-slate"
    assert verifier_receipt["acceptance_identity"]["uri"].endswith(
        manifest_contract.ACCEPTANCE_FILENAME
    )
    worker_runtime = worker_receipt["worker_runtime_measurement_identity"]
    verifier_runtime = verifier_receipt["verifier_runtime_measurement_identity"]
    assert worker_runtime != verifier_runtime


def test_cli_freeze_g0_is_create_once_and_requires_reviewed_commit(
    tmp_path, monkeypatch, authority_fixture
) -> None:
    _patch_cli_runtime(monkeypatch, authority_fixture)
    receipt_path = tmp_path / "freeze-g0-receipt.json"
    receipt = cli.run([
        "freeze-g0-authority",
        "--receipt-output", str(receipt_path),
        "--execute",
    ], store=authority_fixture.store)
    assert receipt["g0_authority_lock_sha256"] == authority_fixture.authority_lock[
        "g0_authority_lock_sha256"
    ]
    assert receipt["review_and_git_commit_required_before_prepare"] is True
    assert receipt["tracked_at_head"] is False
    assert receipt["clean_at_head"] is False
    assert receipt["prepare_gate_passed"] is False
    assert receipt["production_change_licensed"] is False


def test_cli_prepare_has_no_science_or_authority_identity_knobs(
    tmp_path, monkeypatch, authority_fixture
) -> None:
    _patch_cli_runtime(monkeypatch, authority_fixture)
    evidence_path = tmp_path / "evidence-identity.json"
    receipt_path = tmp_path / "prepare-receipt.json"
    _write(evidence_path, authority_fixture.evidence_identity)
    receipt = cli.run([
        "prepare",
        "--image-evidence-identity", str(evidence_path),
        "--output-prefix", OUTPUT_PREFIX,
        "--receipt-output", str(receipt_path),
        "--execute",
    ], store=authority_fixture.store)
    assert receipt["panel_publication_receipt_binding"]["path"] == str(
        authority_fixture.publication_path
    )
    assert receipt["panel_object_identity"] == authority_fixture.panel_identity
    prepare_help = cli._parser()._subparsers._group_actions[0].choices[
        "prepare"
    ].format_help()
    for forbidden in (
        "panel-publication-receipt",
        "lane-receipt",
        "source-commit-sha",
        "immutable-image-uri",
        "runtime-image-evidence-local",
        "worker-runtime",
        "verifier-runtime",
    ):
        assert forbidden not in prepare_help


def test_cli_requires_explicit_execute_before_publication(
    tmp_path, authority_fixture
) -> None:
    authority_path = tmp_path / "authority.json"
    _write(authority_path, authority_fixture.authority_identity)
    before = list(authority_fixture.store.publications)
    with pytest.raises(SystemExit):
        cli.run([
            "run-slate",
            "--execution-authority-identity", str(authority_path),
            "--source-ordinal", "0",
        ], store=authority_fixture.store)
    assert authority_fixture.store.publications == before


class _Collision(Exception):
    pass


class _FakeBlob:
    def __init__(self, bucket, name: str, generation: int | None) -> None:
        self.bucket = bucket
        self.name = name
        self.requested_generation = generation
        self.generation = generation

    def upload_from_string(self, raw: bytes, **kwargs) -> None:
        assert kwargs["if_generation_match"] == 0
        if self.name in self.bucket.current:
            raise _Collision()
        self.bucket.next_generation += 1
        self.generation = self.bucket.next_generation
        self.bucket.versions[(self.name, self.generation)] = raw
        self.bucket.current[self.name] = self.generation

    def download_as_bytes(self, **kwargs) -> bytes:
        generation = int(kwargs["if_generation_match"])
        assert generation == self.requested_generation
        return self.bucket.versions[(self.name, generation)]

    def reload(self, **_kwargs) -> None:  # pragma: no cover - must never be called
        raise AssertionError("unversioned reload is forbidden")


class _FakeBucket:
    def __init__(self) -> None:
        self.versions: dict[tuple[str, int], bytes] = {}
        self.current: dict[str, int] = {}
        self.next_generation = 70

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(self, name, generation)


class _FakeClient:
    def __init__(self) -> None:
        self.bucket_body = _FakeBucket()

    def bucket(self, _name: str) -> _FakeBucket:
        return self.bucket_body


def test_gcs_store_exact_generation_replay_and_delete_recreate_drift() -> None:
    client = _FakeClient()
    store = cli.GCSExactCreateOnceStore(
        client, collision_exceptions=(_Collision,)
    )
    raw = b'{"a":1}'
    identity = store.publish_create_once("gs://bucket/path/value.json", raw)
    assert store.read(identity) == raw
    old_generation = int(str(identity["generation"]))
    del client.bucket_body.versions[("path/value.json", old_generation)]
    client.bucket_body.next_generation += 1
    new_generation = client.bucket_body.next_generation
    client.bucket_body.versions[("path/value.json", new_generation)] = b'{"a":2}'
    client.bucket_body.current["path/value.json"] = new_generation
    with pytest.raises(KeyError):
        store.read(identity)


def test_gcs_collision_fails_without_current_or_latest_lookup() -> None:
    client = _FakeClient()
    store = cli.GCSExactCreateOnceStore(
        client, collision_exceptions=(_Collision,)
    )
    uri = "gs://bucket/path/value.json"
    store.publish_create_once(uri, b'{"a":1}')
    with pytest.raises(
        cli.CorpusExtremeTailPanelCLIError,
        match="current/latest lookup is forbidden",
    ):
        store.publish_create_once(uri, b'{"a":1}')
