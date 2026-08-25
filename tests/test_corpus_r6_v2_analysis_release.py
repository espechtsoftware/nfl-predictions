from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
import fcntl
from hashlib import sha256
import multiprocessing
import os
from pathlib import Path
from typing import Any

import pytest

from scripts import run_corpus_r6_v2_analysis_release as cli
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_analysis_release as release
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_neo4j_transport import ObjectIdentity
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


def _with_hash(body: dict[str, Any], field: str) -> dict[str, Any]:
    retained = deepcopy(body)
    retained[field] = batch.canonical_sha256(retained)
    return retained


def _rehash(body: dict[str, Any], field: str) -> None:
    body.pop(field, None)
    body[field] = batch.canonical_sha256(body)


def _dummy_identity(tag: str) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "uri": f"gs://fixture/{tag}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _runtime_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    worker = release._process_runtime_identity_v1(role="run-slate-worker")
    verifier = release._process_runtime_identity_v1(role="verify-slate-verifier")
    worker["pid"] = int(worker["pid"]) + 200_000
    worker["process_start_ticks"] = int(worker["process_start_ticks"]) + 2
    _rehash(worker, "process_runtime_sha256")
    verifier["pid"] = int(verifier["pid"]) + 100_000
    verifier["process_start_ticks"] = int(verifier["process_start_ticks"]) + 1
    _rehash(verifier, "process_runtime_sha256")
    return worker, verifier


class _MemoryStore:
    def __init__(self) -> None:
        self._by_identity: dict[tuple[str, str, str, int], bytes] = {}
        self._current: dict[str, tuple[ObjectIdentity, bytes]] = {}
        self._generation = 0

    @staticmethod
    def _key(identity: object) -> tuple[str, str, str, int]:
        if isinstance(identity, ObjectIdentity):
            row = identity.as_dict()
        else:
            row = batch.normalize_object_identity(identity, label="memory identity")
        return (
            str(row["uri"]), str(row["generation"]), str(row["sha256"]),
            int(row["bytes"]),
        )

    def add(self, uri: str, value: dict[str, Any]) -> dict[str, object]:
        raw = batch.canonical_json_bytes(value)
        return self.publish_create_once(uri, raw).as_dict()

    def read_exact(self, identity: ObjectIdentity) -> bytes:
        try:
            return self._by_identity[self._key(identity)]
        except KeyError as exc:
            raise RuntimeError("memory exact-read miss") from exc

    def resolve_optional(self, uri: str):
        return self._current.get(uri)

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        current = self._current.get(uri)
        if current is not None:
            if current[1] != raw:
                raise RuntimeError("create-once collision differs")
            return current[0]
        self._generation += 1
        identity = ObjectIdentity(
            uri=uri,
            generation=str(self._generation),
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        self._by_identity[self._key(identity)] = bytes(raw)
        self._current[uri] = (identity, bytes(raw))
        return identity


class _FilesystemStore:
    """No-socket exact store shared by the worker and a real forked verifier."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _paths(self, uri: str) -> tuple[Path, Path]:
        stem = sha256(uri.encode("utf-8")).hexdigest()
        return self.root / f"{stem}.object", self.root / f"{stem}.lock"

    @staticmethod
    def _identity(uri: str, raw: bytes) -> ObjectIdentity:
        return ObjectIdentity(
            uri=uri,
            generation="1",
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )

    def add(self, uri: str, value: dict[str, Any]) -> dict[str, object]:
        raw = batch.canonical_json_bytes(value)
        return self.publish_create_once(uri, raw).as_dict()

    def read_exact(self, identity: ObjectIdentity) -> bytes:
        row = (
            identity.as_dict()
            if isinstance(identity, ObjectIdentity)
            else batch.normalize_object_identity(
                identity, label="filesystem identity"
            )
        )
        data_path, lock_path = self._paths(str(row["uri"]))
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_SH)
            raw = data_path.read_bytes()
        except OSError as exc:
            raise RuntimeError("filesystem exact-read miss") from exc
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        current = self._identity(str(row["uri"]), raw).as_dict()
        if current != row:
            raise RuntimeError("filesystem generation/content identity differs")
        return raw

    def resolve_optional(self, uri: str):
        data_path, lock_path = self._paths(uri)
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_SH)
            if not data_path.exists():
                return None
            raw = data_path.read_bytes()
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        identity = self._identity(uri, raw)
        return identity, raw

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        data_path, lock_path = self._paths(uri)
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            if data_path.exists():
                retained = data_path.read_bytes()
                if retained != raw:
                    raise RuntimeError("create-once collision differs")
                return self._identity(uri, retained)
            data_fd = os.open(
                data_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            try:
                with os.fdopen(data_fd, "wb", closefd=True) as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                if data_path.exists():
                    data_path.unlink()
                raise
            return self._identity(uri, raw)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


def _panel() -> tuple[dict[str, Any], list[dict[str, object]]]:
    terminals = [_dummy_identity("lane-a-terminal"), _dummy_identity("lane-b-terminal")]
    members = []
    for source_ordinal in range(54):
        lane_ordinal = 0 if source_ordinal < 28 else 1
        task_ordinal = source_ordinal if lane_ordinal == 0 else source_ordinal - 28
        members.append({
            "slate_id": f"slate-{source_ordinal:02d}",
            "lane_ordinal": lane_ordinal,
            "lane_id": panel_index.V12_LANE_LATTICE[lane_ordinal]["lane_id"],
            "task_ordinal": task_ordinal,
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": sha256(
                f"source-{source_ordinal}".encode()
            ).hexdigest(),
            "task_acceptance_identity": _dummy_identity(
                f"task-{source_ordinal}-acceptance"
            ),
            "carrier_identity": _dummy_identity(f"task-{source_ordinal}-carrier"),
            "arms": [
                {
                    "arm_ordinal": arm_ordinal,
                    "parameter_set_id": parameter_set_id,
                    "result_identity": _dummy_identity(
                        f"task-{source_ordinal}-arm-{arm_ordinal}"
                    ),
                }
                for arm_ordinal, parameter_set_id in enumerate(
                    batch.PARAMETER_SET_ORDER
                )
            ],
        })
    lanes = []
    for lane_ordinal, task_count in enumerate((28, 26)):
        lane_members = [
            row for row in members if row["lane_ordinal"] == lane_ordinal
        ]
        lanes.append({
            "lane_ordinal": lane_ordinal,
            "lane_id": panel_index.V12_LANE_LATTICE[lane_ordinal]["lane_id"],
            "terminal_receipt_identity": terminals[lane_ordinal],
            "batch_completion_identity": _dummy_identity(
                f"lane-{lane_ordinal}-completion"
            ),
            "batch_id": f"fixture-v12-{lane_ordinal}",
            "batch_mode": panel_index.V12_LANE_LATTICE[lane_ordinal]["batch_mode"],
            "artifact_source_authority_completion": _dummy_identity(
                "source-completion"
            ),
            "artifact_source_authority_completion_sha256": sha256(
                b"source-completion-internal"
            ).hexdigest(),
            "source_task_offset": 0 if lane_ordinal == 0 else 28,
            "expected_task_count": task_count,
            "accepted_task_count": task_count,
            "accepted_task_ordinals": list(range(task_count)),
            "task_acceptance_identities_sha256": batch.canonical_sha256([
                row["task_acceptance_identity"] for row in lane_members
            ]),
            "carrier_identities_sha256": batch.canonical_sha256([
                row["carrier_identity"] for row in lane_members
            ]),
            "complete": True,
        })
    body = {
        "schema_version": panel_index.PANEL_INDEX_SCHEMA,
        "publication_mode": panel_index.PUBLICATION_MODE,
        "panel_id": "v12:" + batch.canonical_sha256(terminals),
        "artifact_source_authority_completion": _dummy_identity(
            "source-completion"
        ),
        "artifact_source_authority_completion_sha256": sha256(
            b"source-completion-internal"
        ).hexdigest(),
        "lane_count": 2,
        "lanes": lanes,
        "accepted_slate_count": 54,
        "accepted_slates": members,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": 54,
            "accepted_task_count": 54,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
        "analytical_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    return _with_hash(body, "panel_index_sha256"), terminals


def _prepare_on_store(store: Any, monkeypatch: pytest.MonkeyPatch):
    panel, terminals = _panel()
    panel_identity = store.add("gs://fixture/panel.json", panel)
    monkeypatch.setattr(
        release.panel_index,
        "derive_v12_lane_input",
        lambda **kwargs: {
            "lane_ordinal": kwargs["lane_ordinal"],
            "lane_id": kwargs["lane_id"],
            "terminal_receipt_identity": kwargs["terminal_receipt_identity"],
            "tasks": [],
        },
    )
    monkeypatch.setattr(
        release.panel_index,
        "reopen_v12_panel_index",
        lambda **kwargs: deepcopy(panel),
    )
    receipt = release.prepare_r6_v2_analysis_release_v1(
        storage=store,
        panel_index_identity=panel_identity,
        lane_terminal_identities=terminals,
        source_commit_sha="a" * 40,
        immutable_image=f"fixture/r6@sha256:{'b' * 64}",
        output_prefix="gs://fixture/r6-v2-release/",
    )
    manifest_identity, manifest, reopened_panel = (
        release.reopen_r6_v2_analysis_manifest_v1(
            storage=store, manifest_identity=receipt["manifest_identity"]
        )
    )
    return store, manifest_identity, manifest, reopened_panel


@pytest.fixture
def prepared(monkeypatch: pytest.MonkeyPatch):
    return _prepare_on_store(_MemoryStore(), monkeypatch)


def _verify_in_subprocess(
    store: Any,
    manifest_identity: dict[str, object],
    mechanics_identity: dict[str, object],
    result_path: str,
) -> None:
    try:
        receipt = release.verify_r6_v2_analysis_slate_v1(
            storage=store,
            manifest_identity=manifest_identity,
            mechanics_result_identity=mechanics_identity,
        )
    except BaseException as exc:  # noqa: BLE001 - subprocess evidence carrier
        result = {
            "ok": False,
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }
    else:
        result = {"ok": True, "receipt": receipt}
    raw = batch.canonical_json_bytes(result)
    result_fd = os.open(result_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(result_fd, "wb", closefd=True) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _run_verifier_subprocess(
    context: Any,
    *,
    store: Any,
    manifest_identity: dict[str, object],
    mechanics_identity: dict[str, object],
    result_name: str,
) -> dict[str, Any]:
    result_path = store.root / f"subprocess-{result_name}.json"
    assert not result_path.exists()
    process = context.Process(
        target=_verify_in_subprocess,
        args=(
            store,
            manifest_identity,
            mechanics_identity,
            str(result_path),
        ),
    )
    process.start()
    process.join(timeout=60)
    assert not process.is_alive(), "verifier subprocess did not terminate"
    assert process.exitcode == 0
    parsed = batch.parse_canonical_json_bytes(
        result_path.read_bytes(), label="verifier subprocess result"
    )
    assert isinstance(parsed, dict)
    return parsed


def _snapshot(
    store: Any, *, slate: dict[str, object]
) -> tuple[dict[str, object], dict[str, Any]]:
    body = runner.build_matchup_source_snapshot(
        slate=slate,
        lock_time_utc="2023-09-10T17:00:00Z",
        maximum_source_time_utc="2023-09-10T16:59:00Z",
        eligible_players=[{
            "gsis_id": "qb-1",
            "family": "qb",
            "position": "QB",
            "qb_depth1": True,
        }],
        annotation_rows=[{
            "gsis_id": "qb-1",
            "family": "qb",
            "matchup_edge_score": 0.5,
        }],
        player_catalog_identity=_dummy_identity("player-catalog"),
        annotation_query_receipt_identity=_dummy_identity("annotation-query"),
    )
    identity = store.add(
        f"gs://fixture/matchup-{slate['slate_id']}.json", body
    )
    return identity, body


def _rank_inputs(slate: dict[str, object]):
    pairs: list[tuple[str, list[str]]] = []
    for ordinal in range(205):
        roster = sorted([f"p{ordinal:03d}-{slot}" for slot in range(9)])
        pairs.append((canonical_lineup_id(slate, roster), roster))
    pairs.sort(key=lambda row: row[0])
    lineup_ids = [row[0] for row in pairs]
    rosters = [row[1] for row in pairs]
    trace = [
        {
            "selection_rank": ordinal,
            "lineup_id": lineup_ids[ordinal],
            "admitted_lineup_index": ordinal,
            "global_lineup_index": ordinal,
        }
        for ordinal in range(205)
    ]
    return lineup_ids, rosters, trace


def _admissions(fit_scope_id: str, lineup_ids: list[str]):
    selection_sha = sha256(f"selection-{fit_scope_id}".encode()).hexdigest()
    full = _with_hash({
        "schema_version": runner.ADMISSION_SCHEMA,
        "admission_id": runner.FULL_UNION_ADMISSION_ID,
        "fit_scope_id": fit_scope_id,
        "selection_provenance_sha256": selection_sha,
        "admitted_lineup_ids": lineup_ids,
        "admitted_count": len(lineup_ids),
        "excluded_eligible_candidates": [],
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "uses_simulated_scores": False,
        "uses_matchup_values": False,
        "uses_realized_outcomes": False,
    }, "admission_sha256")
    matchup_ids = lineup_ids[:200]
    matchup_excluded = [
        {"lineup_id": lineup_id, "reason_code": "matchup-below-cap-cutoff"}
        for lineup_id in lineup_ids[200:]
    ]
    matchup = _with_hash({
        "schema_version": runner.ADMISSION_SCHEMA,
        "admission_id": runner.MATCHUP_ADMISSION_ID,
        "fit_scope_id": fit_scope_id,
        "selection_provenance_sha256": selection_sha,
        "admitted_lineup_ids": matchup_ids,
        "admitted_count": 200,
        "excluded_eligible_candidates": matchup_excluded,
        "admission_cap": 200,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "uses_simulated_scores": False,
        "uses_matchup_values": True,
        "uses_realized_outcomes": False,
    }, "admission_sha256")
    neutrals = []
    for replicate in range(32):
        omitted = set(lineup_ids[replicate % 5 : replicate % 5 + 5])
        admitted = sorted(set(lineup_ids) - omitted)
        excluded = [
            {"lineup_id": lineup_id, "reason_code": "neutral-not-sampled"}
            for lineup_id in sorted(omitted)
        ]
        neutrals.append(_with_hash({
            "schema_version": runner.ADMISSION_SCHEMA,
            "admission_id": (
                f"neutral-{replicate:02d}-{runner.NEUTRAL_LAW_ID}"
            ),
            "neutral_law_id": runner.NEUTRAL_LAW_ID,
            "replicate_index": replicate,
            "fit_scope_id": fit_scope_id,
            "selection_provenance_sha256": selection_sha,
            "admitted_lineup_ids": admitted,
            "admitted_count": 200,
            "excluded_eligible_candidates": excluded,
            "target_admission_sha256": matchup["admission_sha256"],
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "uses_simulated_scores": False,
            "uses_matchup_values": False,
            "uses_realized_outcomes": False,
        }, "admission_sha256"))
    return [full, matchup, *neutrals]


def _book(
    *,
    slate: dict[str, object],
    fit_scope_id: str,
    training_blocks: list[str],
    heldout_block: str | None,
    admission: dict[str, Any],
    strategy: dict[str, Any],
    lineup_ids: list[str],
    rosters: list[list[str]],
    rank_offset: int,
    reconstruction_sha256: str,
) -> dict[str, Any]:
    admitted_ids = list(admission["admitted_lineup_ids"])
    admitted_index = {lineup_id: index for index, lineup_id in enumerate(admitted_ids)}
    global_index = {lineup_id: index for index, lineup_id in enumerate(lineup_ids)}
    roster_by_id = dict(zip(lineup_ids, rosters, strict=True))
    rotated = admitted_ids[rank_offset % len(admitted_ids):] + admitted_ids[:rank_offset % len(admitted_ids)]
    selected_ids = rotated[:80]
    selected_local = [admitted_index[lineup_id] for lineup_id in selected_ids]
    selected_global = [global_index[lineup_id] for lineup_id in selected_ids]
    selected_rosters = [roster_by_id[lineup_id] for lineup_id in selected_ids]
    trace = [
        {
            "selection_rank": ordinal,
            "lineup_id": lineup_id,
            "admitted_lineup_index": selected_local[ordinal],
            "global_lineup_index": selected_global[ordinal],
        }
        for ordinal, lineup_id in enumerate(selected_ids)
    ]
    body = {
        "schema_version": runner.BOOK_SCHEMA,
        "book_id": (
            f"{fit_scope_id}:{admission['admission_id']}:"
            f"{strategy['strategy_id']}"
        ),
        "fit_scope_id": fit_scope_id,
        "reconstruction_sha256": reconstruction_sha256,
        "training_blocks": training_blocks,
        "heldout_block": heldout_block,
        "admission_id": admission["admission_id"],
        "admission_sha256": admission["admission_sha256"],
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "strategy_application_scope": (
            "explicit-rotated-training-blocks"
            if heldout_block is not None
            else "explicit-all-five-block-final-fit"
        ),
        "input_lineup_ids_sha256": batch.canonical_sha256(admitted_ids),
        "training_score_matrix_sha256": "d" * 64,
        "training_score_shape": [len(admitted_ids), len(training_blocks) * 10_000],
        "worlds_per_block": 10_000,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "selected_local_indices": selected_local,
        "selected_global_indices": selected_global,
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
        "entry_count": 80,
        "marginal_trace": trace,
        "training_metrics": {},
        "redundancy_diagnostics": {},
        "heldout_metrics_descriptive": None,
        "threshold_semantics": [],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    return _with_hash(body, "book_sha256")


def _scope(
    *,
    scope_ordinal: int,
    slate: dict[str, object],
    registry: list[dict[str, Any]],
    lineup_ids: list[str],
    rosters: list[list[str]],
    reconstruction_sha256: str,
    matchup_summary_sha256: str,
    matchup_source_snapshot_sha256: str,
) -> dict[str, Any]:
    fit_scope_id = release.FIT_SCOPE_IDS[scope_ordinal]
    heldout = rw.WORLD_BLOCKS[scope_ordinal] if scope_ordinal < 5 else None
    training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
    admissions = _admissions(fit_scope_id, lineup_ids)
    cells = [
        *[(admissions[0], strategy) for strategy in registry],
        *[(admissions[1], strategy) for strategy in registry],
        *[(admissions[2 + replicate], registry[0]) for replicate in range(32)],
    ]
    books = [
        _book(
            slate=slate,
            fit_scope_id=fit_scope_id,
            training_blocks=training_blocks,
            heldout_block=heldout,
            admission=admission,
            strategy=strategy,
            lineup_ids=lineup_ids,
            rosters=rosters,
            rank_offset=scope_ordinal * 47 + book_ordinal,
            reconstruction_sha256=reconstruction_sha256,
        )
        for book_ordinal, (admission, strategy) in enumerate(cells)
    ]
    candidate_view = _with_hash({
        "schema_version": "corpus-fold-candidate-view/v2",
        "slate": slate,
        "fit_scope_id": fit_scope_id,
        "training_blocks": training_blocks,
        "heldout_block": heldout,
        "eligible_candidates": [
            {"lineup_id": lineup_id} for lineup_id in lineup_ids
        ],
        "excluded_candidates_audit": [],
        "eligible_count": len(lineup_ids),
        "excluded_count": 0,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "selection_inputs_exclude_heldout_occurrences": True,
        "uses_realized_outcomes": False,
        "selection_provenance_sha256": sha256(
            f"selection-{fit_scope_id}".encode()
        ).hexdigest(),
    }, "fit_candidate_view_sha256")
    body = {
        "schema_version": runner.SCOPE_SCHEMA,
        "fit_scope_id": fit_scope_id,
        "reconstruction_sha256": reconstruction_sha256,
        "training_blocks": training_blocks,
        "heldout_block": heldout,
        "worlds_per_block": 10_000,
        "admission_cap": 200,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "require_authoritative": True,
        "candidate_view": candidate_view,
        "matchup_summary_sha256": matchup_summary_sha256,
        "matchup_source_snapshot_sha256": matchup_source_snapshot_sha256,
        "admissions": admissions,
        "neutral_control_diagnostics": {},
        "strategy_registry": registry,
        "neutral_controls_apply_to_strategy_id": release.STRATEGY_IDS[0],
        "book_count": 46,
        "books": books,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    return _with_hash(body, "fit_scope_sha256")


def _upstream_result(
    *,
    manifest: dict[str, Any],
    panel: dict[str, Any],
    source_ordinal: int,
    matchup_identity: dict[str, object],
    matchup: dict[str, Any],
) -> dict[str, Any]:
    member = panel["accepted_slates"][source_ordinal]
    slate = {
        "season": 2023,
        "week": source_ordinal + 1,
        "slate_id": member["slate_id"],
    }
    registry, _ = release._strategy_registry()
    lineup_ids, rosters, _ = _rank_inputs(slate)
    compatibility_sha = "0" * 64
    candidate_sha = "1" * 64
    matrix = _with_hash({
        "schema_version": runner.MATRIX_BINDING_SCHEMA,
        "slate": slate,
        "candidate_provenance_sha256": candidate_sha,
        "lineup_ids_sha256": batch.canonical_sha256(lineup_ids),
        "world_ids_sha256": "2" * 64,
        "shape": [len(lineup_ids), 50_000],
        "score_matrix_sha256": "3" * 64,
        "uses_realized_outcomes": False,
    }, "matrix_binding_sha256")
    reconstruction = _with_hash({
        "schema_version": runner.RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": compatibility_sha,
        "candidate_provenance_sha256": candidate_sha,
        "matrix_binding": matrix,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": parameter_set_id,
                "candidate_score_sha256": sha256(
                    f"candidate-arm-{ordinal}".encode()
                ).hexdigest(),
                "selected_score_sha256": sha256(
                    f"selected-arm-{ordinal}".encode()
                ).hexdigest(),
                "unique_count": len(lineup_ids),
                "selected_count": 80,
                "verified": True,
            }
            for ordinal, parameter_set_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }, "reconstruction_sha256")
    matchup_summary = _with_hash({
        "schema_version": runner.MATCHUP_SUMMARY_SCHEMA,
        "slate": slate,
        "matchup_source_snapshot_sha256": matchup[
            "matchup_source_snapshot_sha256"
        ],
        "player_catalog_identity": matchup["player_catalog_identity"],
        "annotation_query_receipt_identity": matchup[
            "annotation_query_receipt_identity"
        ],
        "eligible_families": list(runner.ELIGIBLE_MATCHUP_FAMILIES),
        "qb_gate": "exclude-only-when-qb_depth1-is-literal-false",
        "minimum_supported_players": 2,
        "minimum_completeness": 0.5,
        "lineups": [
            {
                "lineup_id": lineup_id,
                "matchup_edge_mean": float(len(lineup_ids) - ordinal),
                "eligible_player_count": 2,
                "supported_player_count": 2,
                "supported_families": ["qb", "wr"],
                "annotation_completeness": 1.0,
                "qualifies_for_matchup_admission": True,
                "missing_semantics": "missing-not-zero",
            }
            for ordinal, lineup_id in enumerate(lineup_ids)
        ],
        "uses_realized_outcomes": False,
    }, "matchup_summary_sha256")
    scopes = [
        _scope(
            scope_ordinal=ordinal,
            slate=slate,
            registry=registry,
            lineup_ids=lineup_ids,
            rosters=rosters,
            reconstruction_sha256=reconstruction["reconstruction_sha256"],
            matchup_summary_sha256=matchup_summary["matchup_summary_sha256"],
            matchup_source_snapshot_sha256=matchup[
                "matchup_source_snapshot_sha256"
            ],
        )
        for ordinal in range(6)
    ]
    surface = _with_hash({
        "schema_version": runner.RUNNER_SCHEMA,
        "slate": slate,
        "candidate_provenance_sha256": candidate_sha,
        "reconstruction_sha256": reconstruction["reconstruction_sha256"],
        "matchup_summary_sha256": matchup_summary["matchup_summary_sha256"],
        "matchup_source_snapshot_sha256": matchup[
            "matchup_source_snapshot_sha256"
        ],
        "folds": scopes[:5],
        "final_fit": scopes[5],
        "fold_count": 5,
        "books_per_scope": 46,
        "cross_fit_book_count": 230,
        "final_fit_book_count": 46,
        "neutral_replicate_count": 32,
        "worlds_per_block": 10_000,
        "admission_cap": 200,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "require_authoritative": True,
        "neutral_replicate_freeze_requires_outcome_blind_runtime_benchmark": True,
        "final_fit_is_distinct_all-block-refit": True,
        "uses_realized_outcomes": False,
        "evidence_tier": "outcome-blind-simulated-analysis",
        "promotion_authority": False,
    }, "retrieval_surface_sha256")
    false_fields = {
        field: False for field in release._UPSTREAM_FALSE_AUTHORITY_FIELDS
    }
    body = {
        "schema_version": execution.RESULT_SCHEMA,
        "execution_mode": "authoritative-dose-one-slate-mechanics-smoke",
        "slate_id": member["slate_id"],
        "panel_index_identity": manifest["panel_index_identity"],
        "panel_index_sha256": panel["panel_index_sha256"],
        "accepted_slate_membership": member,
        "accepted_slate_membership_sha256": batch.canonical_sha256(member),
        "task_acceptance_identity": member["task_acceptance_identity"],
        "carrier_identity": member["carrier_identity"],
        "later_source_freeze_identity": _dummy_identity("later-source-freeze"),
        "world_artifact_identities": {
            role: _dummy_identity(f"{member['slate_id']}-{role}")
            for role in batch.TASK_WORLD_SOURCE_ROLES
        },
        "world_artifact_identity_set_sha256": batch.canonical_sha256({
            role: _dummy_identity(f"{member['slate_id']}-{role}")
            for role in batch.TASK_WORLD_SOURCE_ROLES
        }),
        "matchup_source_snapshot_identity": matchup_identity,
        "matchup_source_snapshot_sha256": matchup[
            "matchup_source_snapshot_sha256"
        ],
        "matchup_evidence_class": release.CURRENT_SOURCE_EVIDENCE_CLASS,
        "matchup_mechanics_only": True,
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
            "panel_content_identity_verified": True,
            "panel_membership_binding_verified": True,
            "task_acceptance_content_identity_verified": True,
            "task_acceptance_carrier_binding_verified": True,
            "carrier_source_receipts_verified": True,
            "matchup_snapshot_content_identity_verified": True,
            "canonical_authoritative_dose_verified": True,
        },
        "output_hashes": {
            "compatibility_import_sha256": compatibility_sha,
            "candidate_provenance_sha256": candidate_sha,
            "reconstruction_sha256": reconstruction["reconstruction_sha256"],
            "matchup_summary_sha256": matchup_summary["matchup_summary_sha256"],
            "retrieval_surface_sha256": surface["retrieval_surface_sha256"]
        },
        "reconstruction_receipt": reconstruction,
        "matchup_summary": matchup_summary,
        "retrieval_surface": surface,
        **false_fields,
    }
    return _with_hash(body, "task_result_sha256")


def _coherent_first_book_rank_swap(value: dict[str, Any]) -> dict[str, Any]:
    retained = deepcopy(value)
    scope = retained["retrieval_surface"]["folds"][0]
    book = scope["books"][0]
    for field in (
        "selected_local_indices",
        "selected_global_indices",
        "selected_lineup_ids",
        "selected_rosters",
        "marginal_trace",
    ):
        book[field][0], book[field][1] = book[field][1], book[field][0]
    for rank in (0, 1):
        book["marginal_trace"][rank]["selection_rank"] = rank
    _rehash(book, "book_sha256")
    _rehash(scope, "fit_scope_sha256")
    _rehash(retained["retrieval_surface"], "retrieval_surface_sha256")
    retained["output_hashes"]["retrieval_surface_sha256"] = retained[
        "retrieval_surface"
    ]["retrieval_surface_sha256"]
    _rehash(retained, "task_result_sha256")
    return retained


def _coherent_admission_neutral_training_forgery(
    value: dict[str, Any]
) -> dict[str, Any]:
    retained = deepcopy(value)
    scope = retained["retrieval_surface"]["folds"][0]

    def change_membership(admission_index: int, book_indices: list[int]) -> None:
        admission = scope["admissions"][admission_index]
        books = [scope["books"][index] for index in book_indices]
        selected = {
            lineup_id for book in books for lineup_id in book["selected_lineup_ids"]
        }
        removed = next(
            lineup_id
            for lineup_id in reversed(admission["admitted_lineup_ids"])
            if lineup_id not in selected
        )
        added = admission["excluded_eligible_candidates"][0]["lineup_id"]
        admitted = sorted(
            (set(admission["admitted_lineup_ids"]) - {removed}) | {added}
        )
        excluded_ids = sorted(
            (
                {
                    row["lineup_id"]
                    for row in admission["excluded_eligible_candidates"]
                }
                - {added}
            )
            | {removed}
        )
        reason = (
            "matchup-below-cap-cutoff"
            if admission_index == 1
            else "neutral-not-sampled"
        )
        admission["admitted_lineup_ids"] = admitted
        admission["excluded_eligible_candidates"] = [
            {"lineup_id": lineup_id, "reason_code": reason}
            for lineup_id in excluded_ids
        ]
        _rehash(admission, "admission_sha256")
        local_by_id = {lineup_id: index for index, lineup_id in enumerate(admitted)}
        for book in books:
            book["admission_sha256"] = admission["admission_sha256"]
            book["input_lineup_ids_sha256"] = batch.canonical_sha256(admitted)
            book["selected_local_indices"] = [
                local_by_id[lineup_id] for lineup_id in book["selected_lineup_ids"]
            ]
            for rank, row in enumerate(book["marginal_trace"]):
                row["admitted_lineup_index"] = book["selected_local_indices"][rank]
            _rehash(book, "book_sha256")

    change_membership(1, list(range(7, 14)))
    matchup_sha = scope["admissions"][1]["admission_sha256"]
    for replicate in range(32):
        admission = scope["admissions"][2 + replicate]
        admission["target_admission_sha256"] = matchup_sha
        _rehash(admission, "admission_sha256")
        book = scope["books"][14 + replicate]
        book["admission_sha256"] = admission["admission_sha256"]
        _rehash(book, "book_sha256")
    change_membership(2, [14])

    training_book = scope["books"][0]
    unused_global = next(
        index
        for index in range(205)
        if index not in training_book["selected_global_indices"]
    )
    training_book["selected_global_indices"][0] = unused_global
    training_book["marginal_trace"][0]["global_lineup_index"] = unused_global
    training_book["training_score_matrix_sha256"] = sha256(
        b"coherently-spliced-training-matrix"
    ).hexdigest()
    _rehash(training_book, "book_sha256")
    _rehash(scope, "fit_scope_sha256")
    _rehash(retained["retrieval_surface"], "retrieval_surface_sha256")
    retained["output_hashes"]["retrieval_surface_sha256"] = retained[
        "retrieval_surface"
    ]["retrieval_surface_sha256"]
    _rehash(retained, "task_result_sha256")
    return retained


def test_prepare_exact_binds_54_and_rejects_matchup_free_drift(
    prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, manifest, panel = prepared
    assert manifest["source_member_count"] == 54
    assert manifest["execution_lattice"]["books_per_slate"] == 276
    assert manifest["source_boundary"]["matchup_free_lane_authorized"] is False
    assert manifest["release_implementation_sha256"] == (
        "6b301b2e9c4814a83493246e6e7eda73fc1e0a6d9d49d03fc17d9f93178f7d62"
    )

    drifted = deepcopy(manifest)
    drifted["execution_lattice"]["primary_admission_ids"] = [
        runner.FULL_UNION_ADMISSION_ID
    ]
    drifted["source_boundary"]["matchup_free_lane_authorized"] = True
    _rehash(drifted, "execution_manifest_sha256")
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="canonical replay differs",
    ):
        release.validate_r6_v2_analysis_manifest_v1(
            drifted, exact_panel_index=panel
        )
    with monkeypatch.context() as drift:
        drift.setattr(release, "EXPECTED_RELEASE_CLI_SHA256", "0" * 64)
        with pytest.raises(
            release.CorpusR6V2AnalysisReleaseError,
            match="literal identity drifted",
        ):
            release.release_implementation_contract_v1()
    with monkeypatch.context() as drift:
        expected_modules = dict(release.EXPECTED_DEPENDENCY_MODULE_SHA256)
        expected_modules["batch_runner"] = "0" * 64
        drift.setattr(
            release, "EXPECTED_DEPENDENCY_MODULE_SHA256", expected_modules
        )
        with pytest.raises(
            release.CorpusR6V2AnalysisReleaseError,
            match="transitive dependency literal identity drifted",
        ):
            release.release_implementation_contract_v1()
    with monkeypatch.context() as drift:
        drift.setattr(release.rw, "WORLD_BLOCKS", ("R0", "R1", "R2", "R3"))
        with pytest.raises(
            release.CorpusR6V2AnalysisReleaseError,
            match="transitive dependency literal identity drifted",
        ):
            release.release_implementation_contract_v1()


def test_complete_276_lattice_and_prefixes_fail_closed_on_partial_scope_and_neutral(
    prepared,
) -> None:
    store, manifest_identity, manifest, panel = prepared
    slate = {"season": 2023, "week": 1, "slate_id": "slate-00"}
    matchup_identity, matchup = _snapshot(store, slate=slate)
    upstream = _upstream_result(
        manifest=manifest,
        panel=panel,
        source_ordinal=0,
        matchup_identity=matchup_identity,
        matchup=matchup,
    )
    worker_runtime, _ = _runtime_pair()
    mechanics = release.build_r6_v2_mechanics_result_v1(
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=panel,
        source_ordinal=0,
        matchup_source_snapshot_identity=matchup_identity,
        upstream_task_result=upstream,
        worker_process_runtime=worker_runtime,
    )
    validated = release.validate_r6_v2_mechanics_result_v1(
        mechanics,
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=panel,
    )
    assert validated["book_count"] == 276
    assert len(validated["book_catalog"]["books"]) == 276
    assert [
        row["entry_count"]
        for row in validated["book_catalog"]["books"][0]["prefixes"]
    ] == [4, 14, 80]

    partial = deepcopy(upstream)
    partial["retrieval_surface"]["final_fit"] = None
    _rehash(partial["retrieval_surface"], "retrieval_surface_sha256")
    partial["output_hashes"]["retrieval_surface_sha256"] = partial[
        "retrieval_surface"
    ]["retrieval_surface_sha256"]
    _rehash(partial, "task_result_sha256")
    with pytest.raises(release.CorpusR6V2AnalysisReleaseError):
        release.derive_r6_v2_book_catalog_v1(partial)

    missing_neutral = deepcopy(upstream)
    first_scope = missing_neutral["retrieval_surface"]["folds"][0]
    first_scope["admissions"].pop()
    first_scope["books"].pop()
    _rehash(first_scope, "fit_scope_sha256")
    _rehash(missing_neutral["retrieval_surface"], "retrieval_surface_sha256")
    missing_neutral["output_hashes"]["retrieval_surface_sha256"] = (
        missing_neutral["retrieval_surface"]["retrieval_surface_sha256"]
    )
    _rehash(missing_neutral, "task_result_sha256")
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="32-neutral",
    ):
        release.derive_r6_v2_book_catalog_v1(missing_neutral)

    empty_evidence = deepcopy(upstream)
    empty_evidence["verification"] = {}
    _rehash(empty_evidence, "task_result_sha256")
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="task verification fields differ",
    ):
        release.derive_r6_v2_book_catalog_v1(empty_evidence)


def test_caller_upgrade_and_member_splice_cannot_create_mechanics(prepared) -> None:
    store, manifest_identity, manifest, panel = prepared
    matchup_identity, matchup = _snapshot(
        store,
        slate={"season": 2023, "week": 1, "slate_id": "slate-00"},
    )
    upstream = _upstream_result(
        manifest=manifest,
        panel=panel,
        source_ordinal=0,
        matchup_identity=matchup_identity,
        matchup=matchup,
    )
    upgraded = deepcopy(upstream)
    worker_runtime, _ = _runtime_pair()
    upgraded["matchup_evidence_class"] = execution.MATCHUP_EVIDENCE_PIT
    upgraded["matchup_mechanics_only"] = False
    _rehash(upgraded, "task_result_sha256")
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="lineage differs|registered retrospective",
    ):
        release.build_r6_v2_mechanics_result_v1(
            manifest_identity=manifest_identity,
            manifest=manifest,
            exact_panel_index=panel,
            source_ordinal=0,
            matchup_source_snapshot_identity=matchup_identity,
            upstream_task_result=upgraded,
            worker_process_runtime=worker_runtime,
        )

    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="lineage differs",
    ):
        release.build_r6_v2_mechanics_result_v1(
            manifest_identity=manifest_identity,
            manifest=manifest,
            exact_panel_index=panel,
            source_ordinal=1,
            matchup_source_snapshot_identity=matchup_identity,
            upstream_task_result=upstream,
            worker_process_runtime=worker_runtime,
        )


def test_run_worker_cannot_accept_and_distinct_verifier_exact_replays(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fabricated_runtime = release._process_runtime_identity_v1(
        role="verify-slate-verifier"
    )
    fabricated_runtime["pid"] = int(fabricated_runtime["pid"]) + 100_000
    fabricated_runtime["process_start_ticks"] = int(
        fabricated_runtime["process_start_ticks"]
    ) + 1
    _rehash(fabricated_runtime, "process_runtime_sha256")
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="claimed process tuple differs from /proc/current runtime",
    ):
        release._validate_current_process_runtime_identity_v1(
            fabricated_runtime, role="verify-slate-verifier"
        )

    context = multiprocessing.get_context("fork")
    with nullcontext(_FilesystemStore(tmp_path)) as store:
        store, manifest_identity, manifest, panel = _prepare_on_store(
            store, monkeypatch
        )
        matchup_identity, matchup = _snapshot(
            store,
            slate={"season": 2023, "week": 1, "slate_id": "slate-00"},
        )
        upstream = _upstream_result(
            manifest=manifest,
            panel=panel,
            source_ordinal=0,
            matchup_identity=matchup_identity,
            matchup=matchup,
        )
        monkeypatch.setattr(
            release,
            "_execute_scientific_replay_v1",
            lambda **kwargs: deepcopy(upstream),
        )
        receipt = release.run_r6_v2_analysis_slate_v1(
            storage=store,
            manifest_identity=manifest_identity,
            source_ordinal=0,
            matchup_source_snapshot_identity=matchup_identity,
        )
        assert receipt["status"] == release.WORKER_STATUS
        assert receipt["accepted"] is False
        assert "slate_acceptance_identity" not in receipt
        assert store.resolve_optional(
            manifest["source_members"][0]["acceptance_uri"]
        ) is None
        with pytest.raises(
            release.CorpusR6V2AnalysisReleaseError,
            match="distinct process",
        ):
            release.verify_r6_v2_analysis_slate_v1(
                storage=store,
                manifest_identity=manifest_identity,
                mechanics_result_identity=receipt["mechanics_result_identity"],
            )

        _, mechanics = release._read_json(
            store,
            receipt["mechanics_result_identity"],
            label="test mechanics",
        )
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            release.build_r6_v2_verifier_result_v1(
                storage=store,
                manifest_identity=manifest_identity,
                manifest=manifest,
                exact_panel_index=panel,
                mechanics_result_identity=receipt["mechanics_result_identity"],
                mechanics_result=mechanics,
                matchup_source_snapshot_identity=matchup_identity,
                matchup_source_snapshot=matchup,
                verifier_process_runtime=_runtime_pair()[1],
                independently_replayed_upstream_task_result=upstream,
            )

        forged_replay = _coherent_first_book_rank_swap(upstream)
        monkeypatch.setattr(
            release,
            "_execute_scientific_replay_v1",
            lambda **kwargs: deepcopy(forged_replay),
        )
        forged_outcome = _run_verifier_subprocess(
            context,
            store=store,
            manifest_identity=manifest_identity,
            mechanics_identity=receipt["mechanics_result_identity"],
            result_name="rank-forgery",
        )
        assert forged_outcome["ok"] is False
        assert "independent scientific executor replay differs" in forged_outcome[
            "message"
        ]
        assert store.resolve_optional(
            manifest["source_members"][0]["acceptance_uri"]
        ) is None

        controls_forgery = _coherent_admission_neutral_training_forgery(upstream)
        assert release.derive_r6_v2_book_catalog_v1(controls_forgery)[
            "book_count"
        ] == 276
        monkeypatch.setattr(
            release,
            "_execute_scientific_replay_v1",
            lambda **kwargs: deepcopy(controls_forgery),
        )
        controls_outcome = _run_verifier_subprocess(
            context,
            store=store,
            manifest_identity=manifest_identity,
            mechanics_identity=receipt["mechanics_result_identity"],
            result_name="controls-forgery",
        )
        assert controls_outcome["ok"] is False
        assert "independent scientific executor replay differs" in controls_outcome[
            "message"
        ]
        assert store.resolve_optional(
            manifest["source_members"][0]["verifier_result_uri"]
        ) is None

        monkeypatch.setattr(
            release,
            "_execute_scientific_replay_v1",
            lambda **kwargs: deepcopy(upstream),
        )
        success = _run_verifier_subprocess(
            context,
            store=store,
            manifest_identity=manifest_identity,
            mechanics_identity=receipt["mechanics_result_identity"],
            result_name="valid-replay",
        )
        assert success["ok"] is True, success
        verified = success["receipt"]
        assert verified["status"] == "complete-source-blocked"
        assert verified["accepted"] is False
        assert verified["verifier_result_identity"]["uri"] == manifest[
            "source_members"
        ][0]["verifier_result_uri"]
        _, acceptance = release._read_json(
            store,
            verified["slate_acceptance_identity"],
            label="test acceptance",
        )
        assert acceptance["complete_276_book_lattice_verified"] is True
        assert acceptance["prefix_4_14_80_replay_verified"] is True
        assert acceptance["corrected_source_contract_present"] is False
        assert acceptance["scientific_executor_replayed"] is True
        assert acceptance["all_seven_rank80_books_recomputed"] is True
        assert all(
            acceptance[field] is False for field in release._FALSE_AUTHORITY_FIELDS
        )
        _, dependency_replay = release._acceptance_dependencies(
            storage=store,
            manifest_identity=manifest_identity,
            manifest=manifest,
            panel=panel,
            acceptance_identity=verified["slate_acceptance_identity"],
        )
        assert dependency_replay == acceptance


def test_acceptance_cannot_be_coherently_rehashed_to_accepted(
    prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, manifest_identity, manifest, panel = prepared
    matchup_identity, matchup = _snapshot(
        store,
        slate={"season": 2023, "week": 1, "slate_id": "slate-00"},
    )
    upstream = _upstream_result(
        manifest=manifest,
        panel=panel,
        source_ordinal=0,
        matchup_identity=matchup_identity,
        matchup=matchup,
    )
    worker_runtime, _ = _runtime_pair()
    mechanics = release.build_r6_v2_mechanics_result_v1(
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=panel,
        source_ordinal=0,
        matchup_source_snapshot_identity=matchup_identity,
        upstream_task_result=upstream,
        worker_process_runtime=worker_runtime,
    )
    mechanics_identity = store.add(
        manifest["source_members"][0]["mechanics_result_uri"], mechanics
    )
    monkeypatch.setattr(
        release,
        "_execute_scientific_replay_v1",
        lambda **kwargs: deepcopy(upstream),
    )
    verifier_result = release.build_r6_v2_verifier_result_v1(
        storage=store,
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=panel,
        mechanics_result_identity=mechanics_identity,
        mechanics_result=mechanics,
        matchup_source_snapshot_identity=matchup_identity,
        matchup_source_snapshot=matchup,
    )
    verifier_result_identity = store.add(
        manifest["source_members"][0]["verifier_result_uri"], verifier_result
    )
    acceptance = release.build_source_blocked_slate_acceptance_v1(
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=panel,
        mechanics_result_identity=mechanics_identity,
        mechanics_result=mechanics,
        verifier_result_identity=verifier_result_identity,
        verifier_result=verifier_result,
        matchup_source_snapshot_identity=matchup_identity,
        matchup_source_snapshot=matchup,
    )
    drifted = deepcopy(acceptance)
    drifted["status"] = "accepted"
    drifted["accepted"] = True
    drifted["r6_freeze_authority"] = True
    drifted["source_blocker_codes"] = []
    drifted["source_blocker_codes_sha256"] = batch.canonical_sha256([])
    _rehash(drifted, "slate_acceptance_sha256")
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="status/source boundary",
    ):
        release.validate_source_blocked_slate_acceptance_v1(
            drifted,
            manifest_identity=manifest_identity,
            manifest=manifest,
            exact_panel_index=panel,
            mechanics_result_identity=mechanics_identity,
            mechanics_result=mechanics,
            verifier_result_identity=verifier_result_identity,
            verifier_result=verifier_result,
            matchup_source_snapshot_identity=matchup_identity,
            matchup_source_snapshot=matchup,
        )


def _identity_at(uri: str, tag: str) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _full_acceptance_shell(
    *,
    ordinal: int,
    manifest_identity: dict[str, object],
    manifest: dict[str, Any],
    worker_runtime: dict[str, Any],
    verifier_runtime: dict[str, Any],
) -> dict[str, Any]:
    source_member = manifest["source_members"][ordinal]
    mechanics_identity = _identity_at(
        source_member["mechanics_result_uri"], f"mechanics-{ordinal}"
    )
    verifier_result_identity = _identity_at(
        source_member["verifier_result_uri"], f"verifier-result-{ordinal}"
    )
    verifier_result_sha256 = sha256(
        f"verifier-result-self-{ordinal}".encode()
    ).hexdigest()
    matchup_identity = _dummy_identity(f"matchup-shell-{ordinal}")
    worlds = {
        role: _dummy_identity(f"shell-{ordinal}-{role}")
        for role in batch.TASK_WORLD_SOURCE_ROLES
    }
    task_sha = sha256(f"task-result-{ordinal}".encode()).hexdigest()
    replay = _with_hash({
        "schema_version": release.VERIFICATION_REPLAY_SCHEMA,
        "manifest_identity": manifest_identity,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_ordinal": ordinal,
        "slate_id": source_member["slate_id"],
        "panel_member_sha256": source_member["panel_member_sha256"],
        "mechanics_result_identity": mechanics_identity,
        "mechanics_result_sha256": sha256(
            f"mechanics-self-{ordinal}".encode()
        ).hexdigest(),
        "verifier_result_identity": verifier_result_identity,
        "verifier_result_sha256": verifier_result_sha256,
        "worker_process_runtime_sha256": worker_runtime[
            "process_runtime_sha256"
        ],
        "verifier_process_runtime_sha256": verifier_runtime[
            "process_runtime_sha256"
        ],
        "task_acceptance_identity": source_member["task_acceptance_identity"],
        "carrier_identity": source_member["carrier_identity"],
        "later_source_freeze_identity": _dummy_identity(
            f"later-source-shell-{ordinal}"
        ),
        "world_artifact_identities": worlds,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(worlds),
        "matchup_source_snapshot_identity": matchup_identity,
        "matchup_source_snapshot_sha256": sha256(
            f"matchup-self-{ordinal}".encode()
        ).hexdigest(),
        "verification_sha256": sha256(f"verify-{ordinal}".encode()).hexdigest(),
        "reconstruction_sha256": sha256(
            f"reconstruction-{ordinal}".encode()
        ).hexdigest(),
        "matrix_binding_sha256": sha256(f"matrix-{ordinal}".encode()).hexdigest(),
        "matchup_summary_sha256": sha256(f"summary-{ordinal}".encode()).hexdigest(),
        "retrieval_surface_sha256": sha256(f"surface-{ordinal}".encode()).hexdigest(),
        "book_catalog_sha256": sha256(f"catalog-{ordinal}".encode()).hexdigest(),
        "upstream_task_result_sha256": task_sha,
        "independent_reexecution_task_result_sha256": task_sha,
        "exact_upstream_result_replay_verified": True,
        "verification_replayed": True,
        "reconstruction_replayed": True,
        "matchup_replayed": True,
        "admissions_recomputed": True,
        "neutral_controls_recomputed": True,
        "training_matrices_recomputed": True,
        "all_seven_rank80_books_recomputed": True,
        "uses_realized_outcomes": False,
        "r6_freeze_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, "verification_replay_sha256")
    body = {
        "schema_version": release.SLATE_ACCEPTANCE_SCHEMA,
        "publication_mode": release.PUBLICATION_MODE,
        "status": release.SLATE_STATUS,
        "accepted": False,
        "manifest_identity": manifest_identity,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_ordinal": ordinal,
        "slate_id": source_member["slate_id"],
        "panel_member_sha256": source_member["panel_member_sha256"],
        "mechanics_result_identity": mechanics_identity,
        "mechanics_result_sha256": replay["mechanics_result_sha256"],
        "verifier_result_identity": verifier_result_identity,
        "verifier_result_sha256": verifier_result_sha256,
        "worker_process_runtime": worker_runtime,
        "worker_process_runtime_sha256": worker_runtime[
            "process_runtime_sha256"
        ],
        "verifier_process_runtime": verifier_runtime,
        "verifier_process_runtime_sha256": verifier_runtime[
            "process_runtime_sha256"
        ],
        "independent_verification_replay": replay,
        "independent_verification_replay_sha256": replay[
            "verification_replay_sha256"
        ],
        "matchup_source_snapshot_identity": matchup_identity,
        "matchup_source_snapshot_sha256": replay[
            "matchup_source_snapshot_sha256"
        ],
        "matchup_source_schema": runner.MATCHUP_SOURCE_SCHEMA,
        "matchup_source_content_replay_verified": True,
        "mechanics_content_replay_verified": True,
        "scientific_executor_replayed": True,
        "carrier_source_world_reopened": True,
        "verification_replayed": True,
        "reconstruction_replayed": True,
        "matchup_replayed": True,
        "admissions_recomputed": True,
        "neutral_controls_recomputed": True,
        "training_matrices_recomputed": True,
        "all_seven_rank80_books_recomputed": True,
        "complete_276_book_lattice_verified": True,
        "prefix_4_14_80_replay_verified": True,
        "source_blocker_codes": list(release.SOURCE_BLOCKER_CODES),
        "source_blocker_codes_sha256": batch.canonical_sha256(
            list(release.SOURCE_BLOCKER_CODES)
        ),
        "corrected_source_contract_present": False,
        "matchup_free_lane_authorized": False,
        "mechanics_complete": True,
        **{field: False for field in release._FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, "slate_acceptance_sha256")


def test_panel_completion_rejects_minimal_unrelated_and_clone_splice(
    prepared,
) -> None:
    store, manifest_identity, manifest, _ = prepared
    minimal = [
        _with_hash({
            "source_ordinal": ordinal,
            "slate_id": source_member["slate_id"],
            "accepted": False,
        }, "slate_acceptance_sha256")
        for ordinal, source_member in enumerate(manifest["source_members"])
    ]
    minimal_ids = [
        store.add(source_member["acceptance_uri"], minimal[ordinal])
        for ordinal, source_member in enumerate(manifest["source_members"])
    ]
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="slate acceptance fields differ|generation/content-pinned",
    ):
        release.build_source_blocked_panel_completion_v1(
            storage=store,
            manifest_identity=manifest_identity,
            ordered_acceptance_identities=minimal_ids,
        )

    worker_runtime, verifier_runtime = _runtime_pair()
    acceptances = [
        _full_acceptance_shell(
            ordinal=ordinal,
            manifest_identity=manifest_identity,
            manifest=manifest,
            worker_runtime=worker_runtime,
            verifier_runtime=verifier_runtime,
        )
        for ordinal in range(54)
    ]
    identities = [
        _identity_at(
            manifest["source_members"][ordinal]["acceptance_uri"],
            f"full-acceptance-{ordinal}",
        )
        for ordinal in range(54)
    ]
    # The private pure assembler still exact-binds every identity/body pair;
    # the exported builder additionally exact-reads all mechanics dependencies.
    bound_identities = []
    for ordinal, acceptance in enumerate(acceptances):
        raw = batch.canonical_json_bytes(acceptance)
        bound_identities.append({
            **identities[ordinal],
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    completion = release._build_source_blocked_panel_completion_body_v1(
        manifest_identity=manifest_identity,
        manifest=manifest,
        ordered_acceptance_identities=bound_identities,
        ordered_acceptances=acceptances,
    )
    assert completion["ordered_acceptance_count"] == 54
    cloned = deepcopy(bound_identities)
    cloned[1] = cloned[0]
    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="URI differs|clone/splice|identity differs",
    ):
        release._build_source_blocked_panel_completion_body_v1(
            manifest_identity=manifest_identity,
            manifest=manifest,
            ordered_acceptance_identities=cloned,
            ordered_acceptances=acceptances,
        )


def test_finish_panel_publishes_only_complete_source_blocked_terminal(
    prepared, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, manifest_identity, manifest, _ = prepared
    worker_runtime, verifier_runtime = _runtime_pair()
    bodies_by_uri: dict[str, dict[str, Any]] = {}
    dependency_calls: dict[str, int] = {}
    identities = []
    for ordinal, source_member in enumerate(manifest["source_members"]):
        body = _full_acceptance_shell(
            ordinal=ordinal,
            manifest_identity=manifest_identity,
            manifest=manifest,
            worker_runtime=worker_runtime,
            verifier_runtime=verifier_runtime,
        )
        identity = store.add(source_member["acceptance_uri"], body)
        bodies_by_uri[str(identity["uri"])] = body
        identities.append(identity)

    def accepted_dependency(**kwargs):
        identity = batch.normalize_object_identity(
            kwargs["acceptance_identity"], label="fixture acceptance"
        )
        uri = str(identity["uri"])
        dependency_calls[uri] = dependency_calls.get(uri, 0) + 1
        return identity, deepcopy(bodies_by_uri[uri])

    monkeypatch.setattr(release, "_acceptance_dependencies", accepted_dependency)
    receipt = release.finish_r6_v2_analysis_panel_v1(
        storage=store,
        manifest_identity=manifest_identity,
        ordered_acceptance_identities=identities,
    )
    assert receipt["status"] == "complete-source-blocked"
    assert receipt["accepted_release_count"] == 0
    assert receipt["accepted"] is False
    _, terminal = release._read_json(
        store,
        receipt["panel_completion_identity"],
        label="test panel completion",
    )
    assert terminal["ordered_acceptance_count"] == 54
    assert terminal["all_sources_blocked"] is True
    assert all(terminal[field] is False for field in release._FALSE_AUTHORITY_FIELDS)
    replayed = release.validate_source_blocked_panel_completion_v1(
        storage=store,
        manifest_identity=manifest_identity,
        panel_completion_identity=receipt["panel_completion_identity"],
    )
    assert replayed == terminal
    assert set(dependency_calls) == set(bodies_by_uri)
    assert set(dependency_calls.values()) == {3}

    with pytest.raises(
        release.CorpusR6V2AnalysisReleaseError,
        match="exactly 54",
    ):
        release.finish_r6_v2_analysis_panel_v1(
            storage=store,
            manifest_identity=manifest_identity,
            ordered_acceptance_identities=identities[:-1],
        )


def test_cli_exposes_prepare_worker_verifier_finish_and_no_evidence_upgrade() -> None:
    parser = cli._parser()
    assert all(command in parser.format_help() for command in cli.COMMANDS)
    parsed = parser.parse_args([
        "run-slate",
        "--manifest-identity", "/tmp/manifest.json",
        "--source-ordinal", "0",
        "--matchup-source-snapshot-identity", "/tmp/matchup.json",
    ])
    assert parsed.command == "run-slate"
    assert not hasattr(parsed, "matchup_evidence_class")
    verified = parser.parse_args([
        "verify-slate",
        "--manifest-identity", "/tmp/manifest.json",
        "--mechanics-result-identity", "/tmp/mechanics.json",
    ])
    assert verified.command == "verify-slate"
    assert not hasattr(verified, "matchup_source_snapshot_identity")
    assert not hasattr(verified, "matchup_evidence_class")
    with pytest.raises(SystemExit):
        parser.parse_args([
            "run-slate",
            "--manifest-identity", "/tmp/manifest.json",
            "--source-ordinal", "0",
            "--matchup-source-snapshot-identity", "/tmp/matchup.json",
            "--matchup-evidence-class", execution.MATCHUP_EVIDENCE_PIT,
        ])
