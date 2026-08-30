from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
import subprocess
from typing import Any

import pytest

from scripts import (
    build_corpus_r6_v2_runtime_authority_v1 as build_runtime,
)
from scripts import (
    run_corpus_r6_v2_matchup_candidate_analysis_release_v2 as cli,
)
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_release_v2 as release,
)
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_neo4j_transport import ObjectIdentity
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


SOURCE_COMMIT = "a" * 40
IMAGE = f"fixture/r6@sha256:{'b' * 64}"
OUTPUT_PREFIX = "gs://fixture/r6-v2-candidate-release/"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _MemoryStore:
    def __init__(self) -> None:
        self.current: dict[str, tuple[ObjectIdentity, bytes]] = {}
        self.by_key: dict[tuple[str, str, str, int], bytes] = {}
        self.generation = 0

    @staticmethod
    def _key(value: object) -> tuple[str, str, str, int]:
        if isinstance(value, ObjectIdentity):
            row = value.as_dict()
        else:
            row = batch.normalize_object_identity(value, label="memory identity")
        return (
            str(row["uri"]), str(row["generation"]), str(row["sha256"]),
            int(row["bytes"]),
        )

    def add(self, uri: str, value: object) -> dict[str, object]:
        return self.publish_create_once(uri, batch.canonical_json_bytes(value)).as_dict()

    def read_exact(self, identity: ObjectIdentity) -> bytes:
        try:
            return self.by_key[self._key(identity)]
        except KeyError as exc:
            raise RuntimeError("memory exact-read miss") from exc

    def resolve_optional(self, uri: str):
        return self.current.get(uri)

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        retained = self.current.get(uri)
        if retained is not None:
            if retained[1] != raw:
                raise RuntimeError("create-once collision differs")
            return retained[0]
        self.generation += 1
        identity = ObjectIdentity(
            uri=uri,
            generation=str(self.generation),
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        self.current[uri] = (identity, bytes(raw))
        self.by_key[self._key(identity)] = bytes(raw)
        return identity


def _dummy_identity(tag: str) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "uri": f"gs://fixture/{tag}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _with_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = deepcopy(value)
    result[field] = batch.canonical_sha256(result)
    return result


def _panel(terminals: list[dict[str, object]]) -> dict[str, Any]:
    members = []
    for ordinal in range(54):
        lane = 0 if ordinal < 28 else 1
        task = ordinal if lane == 0 else ordinal - 28
        members.append({
            "source_task_ordinal": ordinal,
            "task_ordinal": task,
            "lane_ordinal": lane,
            "slate_id": f"slate-{ordinal:02d}",
            "task_acceptance_identity": _dummy_identity(f"acceptance-{ordinal}"),
            "carrier_identity": _dummy_identity(f"carrier-{ordinal}"),
        })
    lanes = [
        {
            "lane_ordinal": ordinal,
            "lane_id": panel_index.V12_LANE_LATTICE[ordinal]["lane_id"],
            "terminal_receipt_identity": terminals[ordinal],
            "expected_task_count": count,
            "accepted_task_count": count,
            "accepted_task_ordinals": list(range(count)),
            "source_task_offset": 0 if ordinal == 0 else 28,
            "complete": True,
        }
        for ordinal, count in enumerate((28, 26))
    ]
    return _with_hash({
        "schema_version": panel_index.PANEL_INDEX_SCHEMA,
        "publication_mode": panel_index.PUBLICATION_MODE,
        "lanes": lanes,
        "accepted_slate_count": 54,
        "accepted_slates": members,
        "coverage": {
            "expected_task_count": 54,
            "accepted_task_count": 54,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "uses_realized_outcomes": False,
    }, "panel_index_sha256")


def _source_root() -> dict[str, Any]:
    entries = []
    for ordinal in range(54):
        entries.append({
            "source_task_ordinal": ordinal,
            "task_id": f"slate-2023-w{ordinal + 1}",
            "slate": {
                "season": 2023,
                "week": ordinal + 1,
                "slate_id": f"slate-{ordinal:02d}",
            },
            "candidate_artifact_identity": _dummy_identity(
                f"candidate-artifact-{ordinal}"
            ),
            "candidate_artifact_sha256": sha256(
                f"candidate-artifact-{ordinal}".encode()
            ).hexdigest(),
            "candidate_count": 320,
            "ordered_candidate_ids_sha256": sha256(
                f"candidate-order-{ordinal}".encode()
            ).hexdigest(),
            "matchup_source_member_candidate_authority_sha256": sha256(
                f"source-member-{ordinal}".encode()
            ).hexdigest(),
        })
    return {
        "schema_version": "fixture-candidate-source-root/v2",
        "namespace": "gs://fixture/source-root/",
        "task_count": 54,
        "entries": entries,
        "matchup_source_release_candidate_authority_sha256": sha256(
            b"source-root-internal"
        ).hexdigest(),
    }


def _embedded_runtime_authority(
    *, repository_root: Path = REPOSITORY_ROOT,
    source_commit_sha: str = SOURCE_COMMIT,
) -> dict[str, object]:
    return release.build_embedded_runtime_authority_v1(
        repository_root=repository_root,
        source_commit_sha=source_commit_sha,
        git_head=lambda _: source_commit_sha,
        git_blob=lambda root, _commit, relative_path: (
            root / relative_path
        ).read_bytes(),
        git_status=lambda _root, _paths: b"",
    )


def _provider_runtime_image_authority(
    embedded: Mapping[str, object],
) -> dict[str, object]:
    return release.build_provider_runtime_image_authority_v1(
        provider_observation={
            "schema_version": release.PROVIDER_IMAGE_OBSERVATION_SCHEMA,
            "provider": "google-cloud-run-v2",
            "observation_kind": "cloud-run-job",
            "resource_name": (
                "projects/fixture/locations/us-central1/jobs/r6-worker"
            ),
            "build_id": "fixture-build-001",
            "job_name": "r6-worker",
            "job_uid": "fixture-job-uid-001",
            "execution_id": None,
            "source_commit_sha": embedded["source_commit_sha"],
            "immutable_image": IMAGE,
            "provider_observed": True,
        },
        embedded_runtime_authority=embedded,
    )


def _runtime_manifest(receipt: Mapping[str, object]) -> dict[str, object]:
    return {
        "source_commit_sha": receipt["source_commit_sha"],
        "embedded_runtime_authority_sha256": receipt[
            "runtime_authority_sha256"
        ],
        "critical_runtime_paths_sha256": receipt[
            "critical_runtime_paths_sha256"
        ],
        "critical_runtime_files_sha256": receipt[
            "critical_runtime_files_sha256"
        ],
    }


def _runtime_tree(tmp_path: Path) -> Path:
    root = tmp_path / "runtime-tree"
    root.mkdir()
    for relative_path in release.CRITICAL_RUNTIME_PATHS:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPOSITORY_ROOT / relative_path).read_bytes())
    return root


def _prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    _MemoryStore, dict[str, object], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    store = _MemoryStore()
    terminals = [_dummy_identity("lane-a-terminal"), _dummy_identity("lane-b-terminal")]
    panel = _panel(terminals)
    panel_identity = store.add("gs://fixture/panel.json", panel)
    source = _source_root()
    source_identity = store.add(
        "gs://fixture/source-root/"
        + release.source_release_v2.ROOT_FILENAME,
        source,
    )
    embedded = _embedded_runtime_authority()
    monkeypatch.setattr(
        release,
        "load_image_embedded_runtime_authority_v1",
        lambda: deepcopy(embedded),
    )
    image_authority = _provider_runtime_image_authority(embedded)
    image_authority_identity = store.add(
        "gs://fixture/runtime-authority/provider-image-authority.json",
        image_authority,
    )
    monkeypatch.setattr(
        release.panel_index,
        "derive_v12_lane_input",
        lambda **kwargs: {"lane_ordinal": kwargs["lane_ordinal"]},
    )
    monkeypatch.setattr(
        release.panel_index,
        "reopen_v12_panel_index",
        lambda **kwargs: deepcopy(panel),
    )
    monkeypatch.setattr(
        release.source_release_v2,
        "validate_matchup_source_release_candidate_authority_v2",
        lambda value: deepcopy(dict(value)),
    )
    receipt = release.prepare_release_v2(
        storage=store,
        panel_index_identity=panel_identity,
        lane_terminal_identities=terminals,
        matchup_source_release_identity=source_identity,
        runtime_image_authority_identity=image_authority_identity,
        output_prefix=OUTPUT_PREFIX,
    )
    _, manifest, reopened_panel, reopened_source = release.reopen_manifest_v2(
        storage=store, manifest_identity=receipt["manifest_identity"]
    )
    return store, receipt["manifest_identity"], manifest, reopened_panel, reopened_source


def _surface(*, ordinal: int) -> dict[str, Any]:
    slate = {"season": 2023, "week": ordinal + 1, "slate_id": f"slate-{ordinal:02d}"}
    rosters = [
        sorted(f"p-{lineup:03d}-{slot}" for slot in range(9))
        for lineup in range(80)
    ]
    lineup_ids = [canonical_lineup_id(slate, roster) for roster in rosters]

    def scope(scope_ordinal: int) -> dict[str, Any]:
        fit_scope_id = release.FIT_SCOPE_IDS[scope_ordinal]
        heldout = rw.WORLD_BLOCKS[scope_ordinal] if scope_ordinal < 5 else None
        books = []
        for book_ordinal in range(release.BOOKS_PER_SCOPE):
            books.append(_with_hash({
                "schema_version": runner.BOOK_SCHEMA,
                "book_id": f"{fit_scope_id}:admission-{book_ordinal}:law-{book_ordinal}",
                "fit_scope_id": fit_scope_id,
                "admission_id": f"admission-{book_ordinal}",
                "strategy_id": f"law-{book_ordinal}",
                "entry_count": 80,
                "selected_lineup_ids": lineup_ids,
                "selected_rosters": rosters,
                "uses_realized_outcomes": False,
                "promotion_authority": False,
            }, "book_sha256"))
        return _with_hash({
            "schema_version": runner.SCOPE_SCHEMA,
            "fit_scope_id": fit_scope_id,
            "heldout_block": heldout,
            "book_count": len(books),
            "books": books,
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        }, "fit_scope_sha256")

    folds = [scope(index) for index in range(5)]
    return _with_hash({
        "schema_version": runner.RUNNER_SCHEMA,
        "slate": slate,
        "folds": folds,
        "final_fit": scope(5),
        "fold_count": 5,
        "books_per_scope": 46,
        "cross_fit_book_count": 230,
        "final_fit_book_count": 46,
        "neutral_replicate_count": 32,
        "worlds_per_block": 10_000,
        "admission_cap": 200,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "require_authoritative": True,
        "final_fit_is_distinct_all-block-refit": True,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }, "retrieval_surface_sha256")


def _task_result(
    *, ordinal: int, panel_identity: Mapping[str, object],
    source_identity: Mapping[str, object],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": release.consumer.RESULT_SCHEMA,
        "source_task_ordinal": ordinal,
        "slate_id": f"slate-{ordinal:02d}",
        "panel_index_identity": dict(panel_identity),
        "matchup_source_projection": {
            "source_release_identity": dict(source_identity),
        },
        "configuration": {
            "minimum_supported_players": 2,
            "minimum_completeness": 0.5,
            "admission_m": 200,
            "neutral_replicates": 32,
            "neutral_seed_root": "r6-v2-neutral-v1",
            "worlds_per_block": 10_000,
            "require_authoritative": True,
        },
        "verification": {
            "candidate_rooted_source_release_exact_reopened": True,
            "candidate_root_full_predecessor_replay_verified": True,
            "selected_candidate_artifact_exact_reopened": True,
            "authorized_candidate_order_matches_scored_matrix_verified": True,
            "full_seven_law_fold_final_surface_canonical_replay_verified": True,
            "canonical_authoritative_dose_verified": True,
        },
        "retrieval_surface": _surface(ordinal=ordinal),
        "outcome_columns_read": [],
        **{field: False for field in release._FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, "task_result_sha256")


def _identity_file(
    tmp_path: Path, *, name: str = "manifest",
    field: str = "manifest_identity",
) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_bytes(
        batch.canonical_json_bytes({field: _dummy_identity(name)}) + b"\n"
    )
    return path


def _worker_cli_args(
    command: str, *, manifest_path: Path,
) -> list[str]:
    return [
        command,
        "--manifest-identity", str(manifest_path),
        "--repository-root", str(REPOSITORY_ROOT),
        "--execute",
    ]


def test_prepare_cross_binds_both_exact_54_member_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, manifest, panel, source = _prepared(monkeypatch)

    assert manifest["source_member_count"] == 54
    assert [row["source_ordinal"] for row in manifest["source_members"]] == list(
        range(54)
    )
    assert [row["slate_id"] for row in manifest["source_members"]] == [
        row["slate_id"] for row in panel["accepted_slates"]
    ]
    assert manifest["matchup_source_release_sha256"] == source[
        "matchup_source_release_candidate_authority_sha256"
    ]
    assert manifest["execution_lattice"] == {
        "fit_scope_ids": list(release.FIT_SCOPE_IDS),
        "scope_count": 6,
        "books_per_scope": 46,
        "books_per_slate": 276,
        "entry_budget": 80,
        "prefix_sizes": [4, 14, 80],
        "prefixes_per_slate": 828,
        "admission_cap": 200,
        "neutral_replicates": 32,
        "neutral_seed_root": "r6-v2-neutral-v1",
        "worlds_per_block": 10_000,
        "worker_requires_distinct_verifier_process": True,
    }
    for field in release._FALSE_AUTHORITY_FIELDS:
        assert manifest[field] is False


def test_worker_retains_276_books_and_prefixes_then_distinct_verifier_accepts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, manifest_identity, manifest, _, _ = _prepared(monkeypatch)
    task = _task_result(
        ordinal=0,
        panel_identity=manifest["panel_index_identity"],
        source_identity=manifest["matchup_source_release_identity"],
    )
    execute_calls: list[dict[str, object]] = []

    def execute(**kwargs: object) -> dict[str, object]:
        execute_calls.append(dict(kwargs))
        return deepcopy(task)

    receipt = release.run_worker_v2(
        storage=store,
        manifest_identity=manifest_identity,
        source_ordinal=0,
        repository_root=REPOSITORY_ROOT,
        execute=execute,
    )
    assert len(execute_calls) == 1
    assert execute_calls[0]["admission_m"] == 200
    assert execute_calls[0]["neutral_replicates"] == 32
    assert execute_calls[0]["worlds_per_block"] is None
    assert receipt["rank_80_book_count"] == 276
    assert receipt["prefix_count"] == 828
    worker_raw = store.read_exact(ObjectIdentity(**receipt["worker_result_identity"]))
    worker = batch.parse_canonical_json_bytes(worker_raw, label="worker")
    catalog = worker["book_catalog"]
    assert catalog["book_count"] == 276
    assert catalog["prefix_count"] == 828
    assert [row["entry_count"] for row in catalog["books"][0]["prefixes"]] == [
        4, 14, 80
    ]

    recovered = release.run_worker_v2(
        storage=store,
        manifest_identity=manifest_identity,
        source_ordinal=0,
        repository_root=REPOSITORY_ROOT,
        execute=execute,
    )
    assert recovered["recovered_without_reexecution"] is True
    assert len(execute_calls) == 1

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="distinct process",
    ):
        release.verify_worker_v2(
            storage=store,
            manifest_identity=manifest_identity,
            source_ordinal=0,
            repository_root=REPOSITORY_ROOT,
            validate=lambda value, **kwargs: deepcopy(value),
        )

    original_runtime = release._current_process_runtime_v2

    def distinct_runtime(*, role: str) -> dict[str, object]:
        value = original_runtime(role=role)
        if role == "independent-verifier":
            value = dict(value)
            value.pop("process_runtime_sha256")
            value["pid"] = int(value["pid"]) + 100_000
            value["process_runtime_sha256"] = batch.canonical_sha256(value)
        return value

    monkeypatch.setattr(release, "_current_process_runtime_v2", distinct_runtime)
    validate_calls: list[dict[str, object]] = []

    def validate(value: Mapping[str, object], **kwargs: object) -> dict[str, object]:
        validate_calls.append(dict(kwargs))
        return deepcopy(dict(value))

    verified = release.verify_worker_v2(
        storage=store,
        manifest_identity=manifest_identity,
        source_ordinal=0,
        repository_root=REPOSITORY_ROOT,
        validate=validate,
    )
    assert len(validate_calls) == 1
    assert verified["accepted"] is True
    assert verified["rank_80_book_count"] == 276
    assert verified["prefix_count"] == 828
    for field in release._FALSE_AUTHORITY_FIELDS:
        assert verified[field] is False


def test_worker_fails_closed_if_one_scope_does_not_have_46_books(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, manifest, _, _ = _prepared(monkeypatch)
    task = _task_result(
        ordinal=0,
        panel_identity=manifest["panel_index_identity"],
        source_identity=manifest["matchup_source_release_identity"],
    )
    task["retrieval_surface"]["folds"][0]["books"].pop()
    task["retrieval_surface"]["folds"][0]["fit_scope_sha256"] = batch.canonical_sha256({
        key: value
        for key, value in task["retrieval_surface"]["folds"][0].items()
        if key != "fit_scope_sha256"
    })
    task["retrieval_surface"]["retrieval_surface_sha256"] = batch.canonical_sha256({
        key: value
        for key, value in task["retrieval_surface"].items()
        if key != "retrieval_surface_sha256"
    })
    task["task_result_sha256"] = batch.canonical_sha256({
        key: value for key, value in task.items() if key != "task_result_sha256"
    })

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="lattice differs",
    ):
        release._book_catalog(task)


def test_finish_requires_all_54_then_builds_exact_14904_book_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, manifest_identity, manifest, _, _ = _prepared(monkeypatch)
    members = manifest["source_members"]
    acceptance_identity_by_ordinal: dict[int, dict[str, object]] = {}
    for ordinal, member in enumerate(members[:53]):
        acceptance_identity_by_ordinal[ordinal] = store.add(
            member["acceptance_uri"], {"ordinal": ordinal}
        )

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match=r"missing acceptances \[53\]",
    ):
        release.finish_release_v2(storage=store, manifest_identity=manifest_identity)

    acceptance_identity_by_ordinal[53] = store.add(
        members[53]["acceptance_uri"], {"ordinal": 53}
    )

    def reopen_acceptance(**kwargs: object):
        ordinal = int(kwargs["source_ordinal"])
        identity = batch.normalize_object_identity(
            kwargs["identity"], label="fixture acceptance"
        )
        member = members[ordinal]
        worker_raw = f"worker-{ordinal}".encode()
        worker_identity = {
            "uri": f"gs://fixture/workers/{ordinal}.json",
            "generation": "1",
            "sha256": sha256(worker_raw).hexdigest(),
            "bytes": len(worker_raw),
        }
        worker = {
            "worker_result_sha256": sha256(
                f"worker-result-{ordinal}".encode()
            ).hexdigest(),
            "task_result_sha256": sha256(f"task-{ordinal}".encode()).hexdigest(),
            "book_catalog_sha256": sha256(
                f"catalog-{ordinal}".encode()
            ).hexdigest(),
        }
        acceptance = {
            "slate_id": member["slate_id"],
            "panel_member_sha256": member["panel_member_sha256"],
            "matchup_source_member_sha256": member[
                "matchup_source_member_sha256"
            ],
            "slate_acceptance_sha256": sha256(
                f"acceptance-{ordinal}".encode()
            ).hexdigest(),
        }
        return identity, acceptance, worker_identity, worker

    monkeypatch.setattr(release, "_reopen_acceptance", reopen_acceptance)
    finished = release.finish_release_v2(
        storage=store, manifest_identity=manifest_identity
    )
    assert finished["accepted"] is True
    assert finished["complete"] is True
    assert finished["rank_80_book_count"] == 14_904
    assert finished["prefix_count"] == 44_712
    root_raw = store.read_exact(ObjectIdentity(**finished["terminal_root_identity"]))
    root = batch.parse_canonical_json_bytes(root_raw, label="accepted root")
    assert root["accepted_slate_count"] == 54
    assert root["verified_worker_count"] == 54
    assert root["rank_80_book_count"] == 14_904
    assert root["prefix_roster_occurrence_counts"] == {
        "4": 59_616,
        "14": 208_656,
        "80": 1_192_320,
    }
    for field in release._FALSE_AUTHORITY_FIELDS:
        assert root[field] is False


def test_cli_prepare_requires_two_lanes_and_unwraps_identity_carriers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _MemoryStore()
    identities = {
        "panel": _dummy_identity("cli-panel"),
        "lane-a": _dummy_identity("cli-lane-a"),
        "lane-b": _dummy_identity("cli-lane-b"),
        "source": _dummy_identity("cli-source"),
        "runtime-authority": _dummy_identity("cli-runtime-authority"),
    }

    def write(name: str, field: str, value: Mapping[str, object]) -> Path:
        path = tmp_path / f"{name}.json"
        path.write_bytes(batch.canonical_json_bytes({field: dict(value)}) + b"\n")
        return path

    paths = {
        "panel": write("panel", "panel_object_identity", identities["panel"]),
        "lane-a": write(
            "lane-a", "terminal_receipt_identity", identities["lane-a"]
        ),
        "lane-b": write(
            "lane-b", "terminal_receipt_identity", identities["lane-b"]
        ),
        "source": write("source", "release_identity", identities["source"]),
        "runtime-authority": write(
            "runtime-authority",
            "runtime_image_authority_identity",
            identities["runtime-authority"],
        ),
    }
    captured: dict[str, object] = {}

    def prepare(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli.release, "prepare_release_v2", prepare)
    result = cli.run([
        "prepare",
        "--panel-index-identity", str(paths["panel"]),
        "--lane-terminal-identity", str(paths["lane-a"]),
        "--lane-terminal-identity", str(paths["lane-b"]),
        "--matchup-source-release-identity", str(paths["source"]),
        "--runtime-image-authority-identity", str(paths["runtime-authority"]),
        "--output-prefix", OUTPUT_PREFIX,
        "--execute",
    ], storage=store)

    assert result == {"ok": True}
    assert captured["panel_index_identity"] == identities["panel"]
    assert captured["lane_terminal_identities"] == [
        identities["lane-a"], identities["lane-b"]
    ]
    assert captured["matchup_source_release_identity"] == identities["source"]
    assert captured["runtime_image_authority_identity"] == identities[
        "runtime-authority"
    ]


def test_cloud_run_task_index_exactly_maps_all_54_ordinals() -> None:
    mapped = [
        cli._source_ordinal(
            None, environment={cli.CLOUD_RUN_TASK_INDEX: str(ordinal)}
        )
        for ordinal in range(release.AUTHORITATIVE_SLATE_COUNT)
    ]

    assert mapped == list(range(54))
    assert len(set(mapped)) == 54


@pytest.mark.parametrize(
    ("command", "release_function"),
    [
        ("run-worker", "run_worker_v2"),
        ("verify-worker", "verify_worker_v2"),
    ],
)
def test_cli_worker_roles_use_cloud_run_task_index(
    command: str, release_function: str, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _identity_file(tmp_path)
    captured: dict[str, object] = {}

    def execute(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli.release, release_function, execute)
    monkeypatch.setattr(
        cli.release,
        "load_image_embedded_runtime_authority_v1",
        _embedded_runtime_authority,
    )
    result = cli.run(
        _worker_cli_args(command, manifest_path=manifest_path),
        storage=_MemoryStore(),
        environment={cli.CLOUD_RUN_TASK_INDEX: "37"},
    )

    assert result == {"ok": True}
    assert captured["source_ordinal"] == 37


def test_cli_rejects_explicit_ordinal_conflicting_with_cloud_task_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _identity_file(tmp_path)
    called = False

    def execute(**_: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(cli.release, "run_worker_v2", execute)
    monkeypatch.setattr(
        cli.release,
        "load_image_embedded_runtime_authority_v1",
        _embedded_runtime_authority,
    )
    argv = _worker_cli_args(
        "run-worker",
        manifest_path=manifest_path,
    )
    argv.extend(("--source-ordinal", "17"))

    with pytest.raises(
        cli.CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError,
        match="conflicts with CLOUD_RUN_TASK_INDEX",
    ):
        cli.run(
            argv,
            storage=_MemoryStore(),
            environment={cli.CLOUD_RUN_TASK_INDEX: "18"},
        )

    assert called is False


@pytest.mark.parametrize(
    "raw_task_index", ["", "00", "01", "+1", "-1", "54", " 1", "1 "]
)
def test_cloud_run_task_index_rejects_noncanonical_or_out_of_range_values(
    raw_task_index: str,
) -> None:
    with pytest.raises(
        cli.CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError,
        match="canonical decimal integer in 0..53",
    ):
        cli._source_ordinal(
            None, environment={cli.CLOUD_RUN_TASK_INDEX: raw_task_index}
        )


def test_cloud_run_task_index_allows_equal_explicit_ordinal_only() -> None:
    assert cli._source_ordinal(
        17, environment={cli.CLOUD_RUN_TASK_INDEX: "17"}
    ) == 17
    assert cli._source_ordinal(17, environment={}) == 17


def test_cli_worker_requires_an_explicit_or_cloud_task_ordinal() -> None:
    with pytest.raises(
        cli.CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError,
        match="requires --source-ordinal or CLOUD_RUN_TASK_INDEX",
    ):
        cli._source_ordinal(None, environment={})


@pytest.mark.parametrize(
    "argv",
    [
        [
            "prepare",
            "--panel-index-identity", "/nonexistent/panel.json",
            "--lane-terminal-identity", "/nonexistent/lane-a.json",
            "--lane-terminal-identity", "/nonexistent/lane-b.json",
            "--matchup-source-release-identity", "/nonexistent/source.json",
            "--runtime-image-authority-identity",
            "/nonexistent/runtime-image-authority.json",
            "--output-prefix", OUTPUT_PREFIX,
        ],
        [
            "run-worker",
            "--manifest-identity", "/nonexistent/manifest.json",
            "--source-ordinal", "0",
            "--repository-root", str(REPOSITORY_ROOT),
        ],
        [
            "verify-worker",
            "--manifest-identity", "/nonexistent/manifest.json",
            "--source-ordinal", "0",
            "--repository-root", str(REPOSITORY_ROOT),
        ],
        ["finish", "--manifest-identity", "/nonexistent/manifest.json"],
    ],
)
def test_cli_main_requires_execute_before_constructing_cloud_storage(
    argv: list[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_constructions = 0

    def construct(**_: object) -> object:
        nonlocal storage_constructions
        storage_constructions += 1
        raise AssertionError("cloud storage must not be constructed")

    monkeypatch.setattr(cli, "GoogleCloudObjectStore", construct)
    with pytest.raises(
        cli.CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError,
        match="requires explicit --execute",
    ):
        cli.main(argv)

    assert storage_constructions == 0


def test_cli_main_validates_local_identity_before_cloud_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_constructions = 0

    def construct(**_: object) -> object:
        nonlocal storage_constructions
        storage_constructions += 1
        raise AssertionError("cloud storage must not be constructed")

    monkeypatch.setattr(cli, "GoogleCloudObjectStore", construct)
    with pytest.raises(
        cli.CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError,
        match="path must be absolute",
    ):
        cli.main([
            "finish",
            "--manifest-identity", "relative-manifest.json",
            "--execute",
        ])

    assert storage_constructions == 0


def test_cli_main_validates_local_arguments_before_cloud_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _identity_file(tmp_path)
    storage_constructions = 0
    monkeypatch.delenv(cli.CLOUD_RUN_TASK_INDEX, raising=False)

    def construct(**_: object) -> object:
        nonlocal storage_constructions
        storage_constructions += 1
        raise AssertionError("cloud storage must not be constructed")

    monkeypatch.setattr(cli, "GoogleCloudObjectStore", construct)

    def invalid_runtime_authority() -> dict[str, object]:
        raise release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "image runtime authority receipt is absent"
        )

    monkeypatch.setattr(
        cli.release,
        "load_image_embedded_runtime_authority_v1",
        invalid_runtime_authority,
    )
    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="image runtime authority receipt is absent",
    ):
        cli.main([
            "run-worker",
            "--manifest-identity", str(manifest_path),
            "--source-ordinal", "0",
            "--repository-root", str(REPOSITORY_ROOT),
            "--execute",
        ])

    assert storage_constructions == 0


@pytest.mark.parametrize(
    "field", ["Actual_Points", "REALIZED_SCORE", " Winner "]
)
def test_outcome_carrier_rejection_is_case_insensitive(field: str) -> None:
    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="forbidden outcome field",
    ):
        release._reject_outcome_carriers(
            {"safe": [{field: 1}]}, label="adversarial fixture"
        )


def test_critical_runtime_paths_include_direct_score_relevant_closure() -> None:
    required = {
        "src/nfl_dfs/research/corpus_legal_feasibility.py",
        "src/nfl_dfs/research/corpus_parametric_snapshot.py",
        "src/nfl_dfs/research/corpus_r6_matchup_source_v1.py",
        "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py",
        "src/nfl_dfs/research/corpus_r6_v2_one_slate_execution_v2.py",
        "src/nfl_dfs/optimizer/lineup.py",
        "src/nfl_dfs/research/corpus_artifact_source_authority.py",
        "src/nfl_dfs/research/corpus_extreme_tail_panel_execution.py",
        "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py",
        "src/nfl_dfs/research/"
        "corpus_r6_v2_matchup_candidate_analysis_controller_v1.py",
        "scripts/run_corpus_r6_v2_matchup_candidate_analysis_controller_v1.py",
    }

    assert required <= set(release.CRITICAL_RUNTIME_PATHS)
    assert all((REPOSITORY_ROOT / path).is_file() for path in required)
    all_project_python = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in (REPOSITORY_ROOT / "src" / "nfl_dfs").rglob("*.py")
    }
    assert all_project_python <= set(release.CRITICAL_RUNTIME_PATHS)


def test_build_receipt_requires_full_clean_head_and_exact_commit_blobs() -> None:
    status_paths: list[list[str]] = []

    def status(_: Path, paths: list[str]) -> bytes:
        status_paths.append(list(paths))
        return b""

    receipt = release.build_embedded_runtime_authority_v1(
        repository_root=REPOSITORY_ROOT,
        source_commit_sha=SOURCE_COMMIT,
        git_head=lambda _: SOURCE_COMMIT,
        git_blob=lambda root, _commit, path: (root / path).read_bytes(),
        git_status=status,
    )

    assert status_paths == [["."]]
    assert receipt["source_commit_sha"] == SOURCE_COMMIT
    assert receipt["file_count"] == len(release.CRITICAL_RUNTIME_PATHS)
    assert [row["relative_path"] for row in receipt["file_measurements"]] == list(
        release.CRITICAL_RUNTIME_PATHS
    )

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="not the exact clean commit",
    ):
        release.build_embedded_runtime_authority_v1(
            repository_root=REPOSITORY_ROOT,
            source_commit_sha=SOURCE_COMMIT,
            git_head=lambda _: SOURCE_COMMIT,
            git_blob=lambda root, _commit, path: (root / path).read_bytes(),
            git_status=lambda _root, _paths: b" M unrelated-file\n",
        )


def test_embedded_runtime_authority_rejects_omitted_critical_path() -> None:
    receipt = deepcopy(_embedded_runtime_authority())
    receipt.pop("runtime_authority_sha256")
    receipt["critical_runtime_paths"].pop()
    receipt["file_measurements"].pop()
    receipt["file_count"] = int(receipt["file_count"]) - 1
    receipt["critical_runtime_paths_sha256"] = batch.canonical_sha256(
        receipt["critical_runtime_paths"]
    )
    receipt["critical_runtime_files_sha256"] = batch.canonical_sha256(
        receipt["file_measurements"]
    )
    receipt["runtime_authority_sha256"] = batch.canonical_sha256(receipt)

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="closure differs",
    ):
        release.validate_embedded_runtime_authority_v1(receipt)


def test_runtime_authority_rejects_on_disk_byte_drift(tmp_path: Path) -> None:
    root = _runtime_tree(tmp_path)
    receipt = _embedded_runtime_authority(repository_root=root)
    drifted = root / release.CRITICAL_RUNTIME_PATHS[0]
    drifted.write_bytes(drifted.read_bytes() + b"\n# drift\n")

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="runtime critical file drifted",
    ):
        release.validate_runtime_files_v1(
            repository_root=root,
            embedded_runtime_authority=receipt,
        )


def test_provider_authority_rejects_wrong_commit_and_digest() -> None:
    receipt = _embedded_runtime_authority()
    authority = _provider_runtime_image_authority(receipt)

    wrong_commit = deepcopy(authority)
    wrong_commit.pop("provider_runtime_image_authority_sha256")
    wrong_commit["source_commit_sha"] = "c" * 40
    wrong_commit["provider_observation"]["source_commit_sha"] = "c" * 40
    wrong_commit["provider_observation_sha256"] = batch.canonical_sha256(
        wrong_commit["provider_observation"]
    )
    wrong_commit["provider_runtime_image_authority_sha256"] = (
        batch.canonical_sha256(wrong_commit)
    )
    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="provider runtime image authority differs",
    ):
        release.validate_provider_runtime_image_authority_v1(wrong_commit)

    wrong_digest = deepcopy(authority)
    wrong_digest.pop("provider_runtime_image_authority_sha256")
    wrong_digest["image_digest"] = f"sha256:{'d' * 64}"
    wrong_digest["provider_runtime_image_authority_sha256"] = (
        batch.canonical_sha256(wrong_digest)
    )
    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="provider runtime image authority differs",
    ):
        release.validate_provider_runtime_image_authority_v1(wrong_digest)

    caller_claim = deepcopy(authority)
    caller_claim.pop("provider_runtime_image_authority_sha256")
    caller_claim["provider_observation"]["provider_observed"] = False
    caller_claim["provider_observation_sha256"] = batch.canonical_sha256(
        caller_claim["provider_observation"]
    )
    caller_claim["provider_runtime_image_authority_sha256"] = (
        batch.canonical_sha256(caller_claim)
    )
    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="provider image observation differs",
    ):
        release.validate_provider_runtime_image_authority_v1(caller_claim)


def test_runtime_rejects_rehashed_caller_self_attestation_substitution() -> None:
    receipt = _embedded_runtime_authority()
    manifest = _runtime_manifest(receipt)
    substituted = deepcopy(receipt)
    substituted.pop("runtime_authority_sha256")
    substituted["source_commit_sha"] = "c" * 40
    substituted["runtime_authority_sha256"] = batch.canonical_sha256(
        substituted
    )
    release.validate_embedded_runtime_authority_v1(substituted)

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="differs from provider-bound manifest",
    ):
        release._validate_runtime_binding(
            manifest=manifest,
            repository_root=REPOSITORY_ROOT,
            embedded_runtime_authority=substituted,
        )

    prepare_parameters = inspect.signature(release.prepare_release_v2).parameters
    worker_parameters = inspect.signature(release.run_worker_v2).parameters
    verifier_parameters = inspect.signature(release.verify_worker_v2).parameters
    assert "source_commit_sha" not in prepare_parameters
    assert "immutable_image" not in prepare_parameters
    assert "runtime_image_authority_identity" in prepare_parameters
    assert "embedded_runtime_authority" not in worker_parameters
    assert "embedded_runtime_authority" not in verifier_parameters


def test_runtime_rejects_imported_module_origin_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    receipt = _embedded_runtime_authority()
    origins = release._runtime_module_origins_v1()
    first_path = next(iter(origins))
    origins[first_path] = tmp_path / "substituted-module.py"
    monkeypatch.setattr(release, "_runtime_module_origins_v1", lambda: origins)

    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="module origin differs",
    ):
        release._validate_runtime_binding(
            manifest=_runtime_manifest(receipt),
            repository_root=REPOSITORY_ROOT,
            embedded_runtime_authority=receipt,
        )


def test_runtime_validation_and_callbacks_never_invoke_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _embedded_runtime_authority()

    def forbidden_subprocess(*_: object, **__: object) -> object:
        raise AssertionError("runtime validation must never invoke subprocess/Git")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)
    git_head, git_blob, git_status = release._validate_runtime_binding(
        manifest=_runtime_manifest(receipt),
        repository_root=REPOSITORY_ROOT,
        embedded_runtime_authority=receipt,
    )
    assert git_head(REPOSITORY_ROOT) == SOURCE_COMMIT
    assert git_blob(
        REPOSITORY_ROOT, SOURCE_COMMIT, release.CRITICAL_RUNTIME_PATHS[0]
    ) == (REPOSITORY_ROOT / release.CRITICAL_RUNTIME_PATHS[0]).read_bytes()
    assert git_status(
        REPOSITORY_ROOT, [release.CRITICAL_RUNTIME_PATHS[0]]
    ) == b""
    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="historical tracked blob is absent",
    ):
        git_blob(
            REPOSITORY_ROOT,
            "d" * 40,
            release.CRITICAL_RUNTIME_PATHS[0],
        )

    receipt_path = tmp_path / "runtime-authority.json"
    receipt_path.write_bytes(batch.canonical_json_bytes(receipt))
    validated = build_runtime.run([
        "validate",
        "--repository-root", str(REPOSITORY_ROOT),
        "--source-commit", SOURCE_COMMIT,
        "--receipt", str(receipt_path),
    ])
    assert validated["runtime_authority_sha256"] == receipt[
        "runtime_authority_sha256"
    ]
    assert not hasattr(cli, "subprocess")


def test_worker_loads_only_fixed_canonical_image_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _embedded_runtime_authority()
    receipt_path = tmp_path / "fixed-runtime-authority.json"
    receipt_path.write_bytes(batch.canonical_json_bytes(receipt))
    monkeypatch.setattr(
        release, "IMAGE_RUNTIME_AUTHORITY_RECEIPT_PATH", receipt_path
    )

    assert release.load_image_embedded_runtime_authority_v1() == receipt

    receipt_path.write_bytes(batch.canonical_json_bytes(receipt) + b"\n")
    with pytest.raises(
        release.CorpusR6V2MatchupCandidateAnalysisReleaseV2Error,
        match="canonical",
    ):
        release.load_image_embedded_runtime_authority_v1()


def test_build_receipt_freeze_requires_explicit_execute(tmp_path: Path) -> None:
    with pytest.raises(
        build_runtime.BuildCorpusR6V2RuntimeAuthorityV1Error,
        match="requires explicit --execute",
    ):
        build_runtime.run([
            "freeze",
            "--repository-root", str(REPOSITORY_ROOT),
            "--source-commit", SOURCE_COMMIT,
            "--output", str(tmp_path / "receipt.json"),
        ])


def test_dockerfile_packages_canonical_release_cli_without_git_metadata() -> None:
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
    copy_line = (
        "COPY scripts/run_corpus_r6_v2_matchup_candidate_analysis_release_v2.py "
        "./scripts/run_corpus_r6_v2_matchup_candidate_analysis_release_v2.py"
    )

    assert dockerfile.splitlines().count(copy_line) == 1
    assert "COPY .git" not in dockerfile

    overlay = (
        REPOSITORY_ROOT / "Dockerfile.corpus-r6-v2-runtime-authority"
    ).read_text(encoding="utf-8")
    assert "COPY runtime-authority.json" in overlay
    assert "run_corpus_r6_v2_matchup_candidate_analysis_controller_v1.py" in overlay
    assert "@sha256:[0-9a-f]{64}" in overlay
    assert "build_corpus_r6_v2_runtime_authority_v1.py validate" in overlay
    assert "COPY .git" not in overlay
    assert "install git" not in overlay
    assert "test ! -e /app/.git" in overlay
    assert "! command -v git" in overlay
