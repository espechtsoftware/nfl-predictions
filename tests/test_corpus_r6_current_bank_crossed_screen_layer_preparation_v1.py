from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_aggregate_v1 as aggregate,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_evaluation_v1 as evaluation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_layer_preparation_v1 as preparation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_projection_preparation_v1
    as projection_preparation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_assembler_v1 as selection,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


OUTPUT_PREFIX = contract.OUTPUT_NAMESPACE + "fixture-layer-preparation/"


def _identity(tag: str) -> dict[str, object]:
    raw = tag.encode("ascii")
    return {
        "uri": f"gs://fixture-layer-preparation/{tag}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _body_identity(
    uri: str, body: object, *, generation: int | str = 1,
) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(body)
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _MemoryStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.current: dict[str, dict[str, object]] = {}
        self.publish_uris: list[str] = []
        self.generation = 10_000

    @staticmethod
    def _key(value: Any) -> tuple[str, str, str, int]:
        return (
            str(value["uri"]),
            str(value["generation"]),
            str(value["sha256"]),
            int(value["bytes"]),
        )

    def seed_raw(self, identity: dict[str, object], raw: bytes) -> None:
        self.values[self._key(identity)] = bytes(raw)
        self.current[str(identity["uri"])] = dict(identity)

    def seed_body(
        self, uri: str, body: object, *, generation: int | str = 1,
    ) -> dict[str, object]:
        raw = contract.canonical_json_bytes_v1(body)
        identity = _body_identity(uri, body, generation=generation)
        self.seed_raw(identity, raw)
        return identity

    def read_exact(self, identity: Any) -> bytes:
        return self.values[self._key(identity)]

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.current:
            raise RuntimeError("strict create-once collision")
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.seed_raw(identity, raw)
        self.publish_uris.append(uri)
        return identity

    def body(self, identity: Any) -> dict[str, object]:
        return task_manifest.strict_json_v1(
            self.read_exact(identity), label="fixture authority"
        )


def test_manifest_request_builders_are_byte_exact_with_execution_builders() -> None:
    common = {
        "design_identity": _identity("design"),
        "topology_identity": _identity("topology"),
    }
    worker_budgets = [_identity(f"worker-{fold}") for fold in range(5)]
    selection_kwargs = {
        **common,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": 3,
        "projection_bundle_identity": _identity("projection-3"),
        "assembler_process_budget_identity": _identity("assembler-3"),
        "worker_process_budget_identities": worker_budgets,
    }
    assert task_manifest.build_selection_task_request_v1(
        **selection_kwargs
    ) == selection.build_slate_assembler_request_v1(**selection_kwargs)

    evaluation_kwargs = {
        **common,
        "phase": contract.CONFIRMATION_PHASE,
        "source_ordinal": 4,
        "projection_bundle_identity": _identity("projection-4"),
        "selection_receipt_identity": _identity("selection-4"),
        "process_budget_identity": _identity("evaluator-4"),
        "bootstrap_manifest_identity": _identity("bootstrap"),
        "launch_intent_identity": _identity("launch"),
        "nomination_identity": _identity("nomination"),
    }
    assert task_manifest.build_evaluation_task_request_v1(
        **evaluation_kwargs
    ) == evaluation.build_evaluator_request_v1(**evaluation_kwargs)

    broad = [_identity(f"broad-{index}") for index in range(54)]
    confirmation = [
        _identity(f"confirmation-{index}") for index in range(54)
    ]
    publisher_kwargs = {
        **common,
        "mode": aggregate.PUBLISH_AGGREGATE_FINALISTS,
        "bootstrap_manifest_identity": _identity("bootstrap"),
        "launch_intent_identity": _identity("launch"),
        "process_budget_identity": _identity("publisher"),
        "broad_evaluation_identities": broad,
        "nomination_identity": _identity("nomination"),
        "confirmation_evaluation_identities": confirmation,
    }
    assert task_manifest.build_publisher_task_request_v1(
        **publisher_kwargs
    ) == aggregate.build_publisher_request_v1(**publisher_kwargs)


@pytest.mark.parametrize(
    ("layer_id", "layer_ordinal", "expected_count"),
    [
        ("broad-selection-receipt", 1, 54 * 7 + 1),
        ("broad-evaluation-result", 2, 54 * 2 + 1),
        ("nomination", 3, 3),
        ("confirmation-selection-receipt", 4, 54 * 7 + 1),
        ("confirmation-evaluation-result", 5, 54 * 2 + 1),
        ("aggregate-finalists", 6, 3),
        ("terminal-root", 7, 3),
    ],
)
def test_all_seven_registered_authority_plans_are_exact_and_unique(
    layer_id: str, layer_ordinal: int, expected_count: int,
) -> None:
    plan = preparation.layer_preparation_authority_plan_v1(
        output_prefix=OUTPUT_PREFIX,
        layer_id=layer_id,
        layer_ordinal=layer_ordinal,
    )
    assert len(plan) == expected_count
    assert [row["publication_ordinal"] for row in plan] == list(
        range(expected_count)
    )
    assert len({row["uri"] for row in plan}) == expected_count
    assert plan[-1]["authority_role"] == "task-manifest"
    assert plan[-1]["uri"].endswith(
        f"/{layer_ordinal:02d}-{layer_id}.json"
    )


def test_outcome_or_caller_field_cannot_enter_any_canonical_request() -> None:
    request = task_manifest.build_selection_task_request_v1(
        phase=contract.BROAD_SCREEN_PHASE,
        source_ordinal=0,
        design_identity=_identity("design"),
        topology_identity=_identity("topology"),
        projection_bundle_identity=_identity("projection"),
        assembler_process_budget_identity=_identity("assembler"),
        worker_process_budget_identities=[
            _identity(f"worker-{fold}") for fold in range(5)
        ],
    )
    changed = deepcopy(request)
    changed["realized_outcome_rows"] = []
    changed["assembler_request_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in changed.items()
        if key != "assembler_request_sha256"
    })
    with pytest.raises(
        task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="request fields differ",
    ):
        task_manifest.render_child_command_v1(
            "broad-selection-receipt", changed
        )


def _projection_root_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    _MemoryStore, dict[str, object], dict[str, object], dict[str, object],
]:
    store = _MemoryStore()
    manifest_identity = _identity("panel-execution-manifest")
    panel_index_identity = _identity("panel-index")
    rows: list[dict[str, object]] = []
    for source in range(contract.PANEL_SLATE_COUNT):
        rows.append({
            "source_ordinal": source,
            "slate_freeze_identity": _identity(f"slate-{source:02d}"),
            "task_result_identity": _identity(f"task-result-{source:02d}"),
        })
    root: dict[str, object] = {
        "manifest_identity": manifest_identity,
        "panel_index_identity": panel_index_identity,
        "source_slate_count": contract.PANEL_SLATE_COUNT,
        "rank_80_book_count": contract.PANEL_RANK_80_BOOK_COUNT,
        "prefix_count": contract.PANEL_PREFIX_COUNT,
        "slate_freezes": rows,
    }
    root["panel_freeze_sha256"] = contract.canonical_sha256_v1(root)
    root_identity = store.seed_body(
        "gs://fixture-layer-preparation/panel-freeze.json", root
    )
    monkeypatch.setattr(contract, "PANEL_IDENTITY", root_identity)
    monkeypatch.setattr(
        contract, "PANEL_SELF_SHA256", root["panel_freeze_sha256"]
    )
    repository = Path(__file__).resolve().parents[1]
    projected = projection_preparation.prepare_projection_first_layer_v1(
        output_prefix=OUTPUT_PREFIX,
        contract_module_bytes=(repository / contract.MODULE_PATH).read_bytes(),
        preoutput_report_bytes=(
            repository / contract.CONTRACT_REPORT_PATH
        ).read_bytes(),
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        reused_job_name="fixture-layer-preparation-job",
        panel_root_body=root,
        panel_root_identity=root_identity,
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
    )
    core = task_manifest.reopen_task_manifest_authority_v1(
        projected["manifest_identity"], read_exact=store.read_exact
    )
    return store, projected, core, root_identity


def _fake_layer_receipts(
    *, store: _MemoryStore, topology: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    registry = task_manifest.layer_registry_v1(OUTPUT_PREFIX)
    output_identity_by_uri: dict[str, dict[str, object]] = {}
    for ordinal, row in enumerate(topology["objects"]):
        if row["role"] == "design":
            continue
        output_identity_by_uri[str(row["uri"])] = store.seed_body(
            str(row["uri"]), {}, generation=20_000 + ordinal
        )
    receipts: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []
    for descriptor in registry[:-1]:
        layer_id = str(descriptor["layer_id"])
        roles = set(descriptor["output_roles"])
        topology_rows = [
            row for row in topology["objects"] if row["role"] in roles
        ]
        task_records: list[dict[str, object]] = []
        if int(descriptor["task_count"]) == 1:
            grouped = [topology_rows]
        else:
            grouped = [[row] for row in topology_rows]
        for task_index, rows in enumerate(grouped):
            task_records.append({
                "task_index": task_index,
                "publication_records": [
                    {
                        "topology_ordinal": int(row["ordinal"]),
                        "role": str(row["role"]),
                        "identity": output_identity_by_uri[str(row["uri"])],
                    }
                    for row in rows
                ],
            })
        receipt_hash = sha256(layer_id.encode("ascii")).hexdigest()
        receipt = {
            "layer_id": layer_id,
            "layer_ordinal": int(descriptor["layer_ordinal"]),
            "layer_execution_receipt_sha256": receipt_hash,
            "task_records": task_records,
        }
        receipt_identity = _body_identity(
            str(descriptor["layer_execution_receipt_uri"]), receipt,
            generation=30_000 + int(descriptor["layer_ordinal"]),
        )
        receipts.append(receipt)
        bindings.append({
            "layer_id": layer_id,
            "receipt_identity": receipt_identity,
            "layer_execution_receipt_sha256": receipt_hash,
        })
    return receipts, bindings


def _fake_budget(
    *, process_role: str, hash_field: str, source: int = 0,
    fold: int | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "fixture-process-budget/v1",
        "contract_id": contract.CONTRACT_ID,
        "process_role": process_role,
        "source_ordinal": source,
        "fold_ordinal": fold,
        "uses_realized_outcomes": False,
    }
    body[hash_field] = contract.canonical_sha256_v1(body)
    return body


def _install_structural_preparation_stubs(
    *, monkeypatch: pytest.MonkeyPatch, store: _MemoryStore,
    projected: dict[str, object], core: dict[str, object],
    receipts: list[dict[str, object]], bindings: list[dict[str, object]],
) -> None:
    monkeypatch.setattr(
        task_manifest,
        "validate_layer_execution_receipt_v1",
        lambda value: dict(value),
    )

    def reopen(identity: Any, *, read_exact: Any) -> dict[str, object]:
        if dict(identity) == projected["manifest_identity"]:
            return deepcopy(core)
        body = store.body(identity)
        ordinal = int(body["layer_ordinal"])
        return {
            "manifest": body,
            "manifest_identity": dict(identity),
            "pre_design_run_authorization": core[
                "pre_design_run_authorization"
            ],
            "topology": core["topology"],
            "bootstrap_manifest": core["bootstrap_manifest"],
            "design": core["design"],
            "projection_process_budget": None,
            "predecessor_layer_receipts": deepcopy(receipts[:ordinal]),
        }

    monkeypatch.setattr(
        task_manifest, "reopen_task_manifest_authority_v1", reopen
    )

    def predecessor_chain(
        *, target_descriptor: dict[str, object], **_kwargs: Any,
    ) -> tuple[
        list[dict[str, object]], list[dict[str, object]],
        dict[str, list[dict[str, object]]], dict[str, object],
    ]:
        count = int(target_descriptor["layer_ordinal"])
        selected_receipts = deepcopy(receipts[:count])
        return (
            selected_receipts,
            deepcopy(bindings[:count]),
            preparation._expected_output_identities(
                topology=core["topology"], receipts=selected_receipts
            ),
            {"manifests_by_layer": {}},
        )

    monkeypatch.setattr(
        preparation, "_reopen_predecessor_chain", predecessor_chain
    )

    def compile_process_budget(**kwargs: Any) -> dict[str, object]:
        return _fake_budget(
            process_role=str(kwargs["process_role"]),
            hash_field="process_budget_sha256",
            source=int(kwargs["source_ordinal"]),
            fold=kwargs.get("fold_ordinal"),
        )

    def compile_evaluator_budget(**kwargs: Any) -> dict[str, object]:
        return _fake_budget(
            process_role=(
                "broad-evaluator"
                if kwargs.get("nomination_publication_identity") is None
                else "confirmation-evaluator"
            ),
            hash_field="evaluator_process_budget_sha256",
            source=int(kwargs["source_ordinal"]),
        )

    def compile_publisher_budget(**kwargs: Any) -> dict[str, object]:
        return _fake_budget(
            process_role=str(kwargs["process_role"]),
            hash_field="publisher_process_budget_sha256",
        )

    monkeypatch.setattr(contract, "compile_process_budget_v1", compile_process_budget)
    monkeypatch.setattr(
        contract, "validate_process_budget_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        contract, "compile_evaluator_process_budget_v1", compile_evaluator_budget
    )
    monkeypatch.setattr(
        contract,
        "validate_evaluator_process_budget_v1",
        lambda value, **_kwargs: dict(value),
    )
    monkeypatch.setattr(
        contract, "compile_publisher_process_budget_v1", compile_publisher_budget
    )
    monkeypatch.setattr(
        contract,
        "validate_publisher_process_budget_v1",
        lambda value, **_kwargs: dict(value),
    )


def test_projection_to_broad_selection_and_all_later_manifests_construct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, projected, core, _root_identity = _projection_root_fixture(monkeypatch)
    receipts, bindings = _fake_layer_receipts(
        store=store, topology=core["topology"]
    )
    _install_structural_preparation_stubs(
        monkeypatch=monkeypatch,
        store=store,
        projected=projected,
        core=core,
        receipts=receipts,
        bindings=bindings,
    )
    expected_counts = [54, 54, 1, 54, 54, 1, 1]
    registry = task_manifest.layer_registry_v1(OUTPUT_PREFIX)[1:]
    results: list[dict[str, object]] = []
    for descriptor, expected_count in zip(registry, expected_counts, strict=True):
        ordinal = int(descriptor["layer_ordinal"])
        predecessor_inputs = [
            {"identity": bindings[index]["receipt_identity"],
             "receipt": receipts[index]}
            for index in range(ordinal)
        ]
        result = preparation.prepare_registered_layer_v1(
            projection_preparation_receipt=projected["preparation_receipt"],
            projection_preparation_receipt_identity=projected[
                "preparation_receipt_identity"
            ],
            target_layer_id=str(descriptor["layer_id"]),
            target_layer_ordinal=ordinal,
            predecessor_layer_receipts=predecessor_inputs,
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )
        manifest_body = store.body(result["manifest_identity"])
        assert manifest_body["layer_id"] == descriptor["layer_id"]
        assert manifest_body["layer_ordinal"] == ordinal
        assert manifest_body["task_count"] == expected_count
        assert result["request_count"] == expected_count
        assert manifest_body["predecessor_layer_receipts"] == bindings[:ordinal]
        assert result["preparation_receipt"]["uses_realized_outcomes"] is False
        assert result["preparation_receipt"]["recovery_allowed"] is False
        assert result["authority_publications"][-1]["identity"] == result[
            "manifest_identity"
        ]
        results.append(result)

    broad_manifest = store.body(results[0]["manifest_identity"])
    assert [
        row["request"]["projection_bundle_identity"]
        for row in broad_manifest["task_bindings"]
    ] == [
        publication["identity"]
        for publication in receipts[0]["task_records"][0][
            "publication_records"
        ]
    ]
    assert all(
        row["request"]["prior_selection_receipt_identity"] is None
        for row in broad_manifest["task_bindings"]
    )
    terminal_manifest = store.body(results[-1]["manifest_identity"])
    terminal_request = terminal_manifest["task_bindings"][0]["request"]
    assert len(terminal_request["predecessor_identities"]) == 274
    assert terminal_request["predecessor_identities"][0] == core[
        "manifest"
    ]["design_identity"]


def test_exact_predecessor_chain_rejects_order_drift_and_outcome_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _projected, core, _root_identity = _projection_root_fixture(monkeypatch)
    registry = task_manifest.layer_registry_v1(OUTPUT_PREFIX)
    core_fields = {
        field: core["manifest"][field]
        for field in (
            "design_identity", "design_sha256", "topology_identity",
            "topology_sha256", "bootstrap_manifest_identity",
            "bootstrap_manifest_sha256",
            "pre_design_run_authorization_identity",
            "pre_design_run_authorization_sha256", "code_commit",
            "image_digest", "reused_job_name",
        )
    }
    projection_publications = [{
        "topology_ordinal": int(row["ordinal"]),
        "role": "projection",
        "identity": store.seed_body(
            str(row["uri"]), {}, generation=40_000 + int(row["ordinal"])
        ),
    } for row in core["topology"]["objects"] if row["role"] == "projection"]
    projection_receipt = {
        **core_fields,
        "layer_id": "projection",
        "layer_ordinal": 0,
        "manifest_identity": core["manifest_identity"],
        "predecessor_layer_receipts": [],
        "layer_execution_receipt_sha256": "1" * 64,
        "task_records": [{
            "task_index": 0,
            "publication_records": projection_publications,
        }],
    }
    projection_identity = store.seed_body(
        str(registry[0]["layer_execution_receipt_uri"]),
        projection_receipt,
        generation=50_000,
    )
    projection_binding = {
        "layer_id": "projection",
        "receipt_identity": projection_identity,
        "layer_execution_receipt_sha256": "1" * 64,
    }
    broad_manifest = {
        **core["manifest"],
        "layer_id": "broad-selection-receipt",
        "layer_ordinal": 1,
        "predecessor_layer_receipts": [projection_binding],
    }
    broad_manifest_identity = store.seed_body(
        str(registry[1]["manifest_uri"]), broad_manifest, generation=50_001
    )
    broad_rows = [
        row for row in core["topology"]["objects"]
        if row["role"] == "broad-selection-receipt"
    ]
    broad_receipt = {
        **core_fields,
        "layer_id": "broad-selection-receipt",
        "layer_ordinal": 1,
        "manifest_identity": broad_manifest_identity,
        "predecessor_layer_receipts": [projection_binding],
        "layer_execution_receipt_sha256": "2" * 64,
        "task_records": [
            {
                "task_index": source,
                "publication_records": [{
                    "topology_ordinal": int(row["ordinal"]),
                    "role": "broad-selection-receipt",
                    "identity": store.seed_body(
                        str(row["uri"]), {}, generation=51_000 + source
                    ),
                }],
            }
            for source, row in enumerate(broad_rows)
        ],
    }
    broad_identity = store.seed_body(
        str(registry[1]["layer_execution_receipt_uri"]),
        broad_receipt,
        generation=50_002,
    )
    broad_binding = {
        "layer_id": "broad-selection-receipt",
        "receipt_identity": broad_identity,
        "layer_execution_receipt_sha256": "2" * 64,
    }

    monkeypatch.setattr(
        task_manifest,
        "validate_layer_execution_receipt_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        task_manifest,
        "validate_layer_execution_receipt_authority_v1",
        lambda value, **_kwargs: dict(value),
    )

    def reopen(identity: Any, *, read_exact: Any) -> dict[str, object]:
        if dict(identity) == core["manifest_identity"]:
            return deepcopy(core)
        assert dict(identity) == broad_manifest_identity
        return {
            "manifest": deepcopy(broad_manifest),
            "manifest_identity": deepcopy(broad_manifest_identity),
            "pre_design_run_authorization": core[
                "pre_design_run_authorization"
            ],
            "topology": core["topology"],
            "bootstrap_manifest": core["bootstrap_manifest"],
            "design": core["design"],
            "projection_process_budget": None,
            "predecessor_layer_receipts": [projection_receipt],
        }

    monkeypatch.setattr(
        task_manifest, "reopen_task_manifest_authority_v1", reopen
    )
    target = registry[2]
    correct = [
        {"identity": projection_identity, "receipt": projection_receipt},
        {"identity": broad_identity, "receipt": broad_receipt},
    ]
    receipts, bindings, outputs, context = preparation._reopen_predecessor_chain(
        target_descriptor=target,
        predecessor_records_value=correct,
        core=core,
        read_exact=store.read_exact,
    )
    assert receipts == [projection_receipt, broad_receipt]
    assert bindings == [projection_binding, broad_binding]
    assert len(outputs["projection"]) == 54
    assert len(outputs["broad-selection-receipt"]) == 54
    assert context["manifests_by_layer"][
        "broad-selection-receipt"
    ] == broad_manifest
    assert context[
        "terminal_publication_identities_generation_exact"
    ] is True

    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error,
        match="order/identity differs",
    ):
        preparation._reopen_predecessor_chain(
            target_descriptor=target,
            predecessor_records_value=list(reversed(correct)),
            core=core,
            read_exact=store.read_exact,
        )

    drifted = deepcopy(broad_receipt)
    drifted["code_commit"] = "c" * 40
    drifted_identity = store.seed_body(
        str(registry[1]["layer_execution_receipt_uri"]),
        drifted,
        generation=50_003,
    )
    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error,
        match="authority graph differs",
    ):
        preparation._reopen_predecessor_chain(
            target_descriptor=target,
            predecessor_records_value=[
                correct[0], {"identity": drifted_identity, "receipt": drifted}
            ],
            core=core,
            read_exact=store.read_exact,
        )

    outcome_record = {**correct[0], "realized_outcome_rows": []}
    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error,
        match="input record fields differ",
    ):
        preparation._reopen_predecessor_chain(
            target_descriptor=registry[1],
            predecessor_records_value=[outcome_record],
            core=core,
            read_exact=store.read_exact,
        )


def test_layer_authority_collision_fails_create_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, projected, core, _root_identity = _projection_root_fixture(monkeypatch)
    receipts, bindings = _fake_layer_receipts(
        store=store, topology=core["topology"]
    )
    _install_structural_preparation_stubs(
        monkeypatch=monkeypatch,
        store=store,
        projected=projected,
        core=core,
        receipts=receipts,
        bindings=bindings,
    )
    first_uri = preparation.layer_preparation_authority_plan_v1(
        output_prefix=OUTPUT_PREFIX,
        layer_id="broad-selection-receipt",
        layer_ordinal=1,
    )[0]["uri"]
    store.seed_body(str(first_uri), {"collision": True}, generation=99_999)
    with pytest.raises(RuntimeError, match="create-once collision"):
        preparation.prepare_registered_layer_v1(
            projection_preparation_receipt=projected["preparation_receipt"],
            projection_preparation_receipt_identity=projected[
                "preparation_receipt_identity"
            ],
            target_layer_id="broad-selection-receipt",
            target_layer_ordinal=1,
            predecessor_layer_receipts=[{
                "identity": bindings[0]["receipt_identity"],
                "receipt": receipts[0],
            }],
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )


def test_request_scoped_exact_read_memo_is_generation_pinned() -> None:
    store = _MemoryStore()
    first = store.seed_body(
        "gs://fixture-layer-preparation/memo.json",
        {"generation": 1},
        generation=1,
    )
    second = store.seed_body(
        "gs://fixture-layer-preparation/memo.json",
        {"generation": 2},
        generation=2,
    )
    calls: list[dict[str, object]] = []

    def counted(identity: Any) -> bytes:
        calls.append(dict(identity))
        return store.read_exact(identity)

    memo = preparation._GenerationPinnedReadMemoV1(counted)
    assert memo.read_exact(first) == memo.read_exact(first)
    assert memo.read_exact(second) == memo.read_exact(second)
    assert calls == [first, second]
    assert memo.underlying_read_count == 2
    assert memo.cache_hit_count == 2


def test_request_scoped_exact_read_memo_does_not_retain_large_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _MemoryStore()
    identity = store.seed_body(
        "gs://fixture-layer-preparation/not-retained.json",
        {"larger": "than-one-byte"},
    )
    monkeypatch.setattr(
        preparation, "MAXIMUM_REQUEST_SCOPED_MEMO_OBJECT_BYTES", 1
    )
    memo = preparation._GenerationPinnedReadMemoV1(store.read_exact)

    assert memo.read_exact(identity) == memo.read_exact(identity)
    assert memo.underlying_read_count == 2
    assert memo.cache_hit_count == 0


def test_request_scoped_memo_reuses_real_projection_authority_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, projected, _core, _root_identity = _projection_root_fixture(
        monkeypatch
    )
    calls: list[dict[str, object]] = []

    def counted(identity: Any) -> bytes:
        calls.append(dict(identity))
        return store.read_exact(identity)

    memo = preparation._GenerationPinnedReadMemoV1(counted)
    first = task_manifest.reopen_task_manifest_authority_v1(
        projected["manifest_identity"], read_exact=memo.read_exact
    )
    first_underlying = memo.underlying_read_count
    second = task_manifest.reopen_task_manifest_authority_v1(
        projected["manifest_identity"], read_exact=memo.read_exact
    )

    assert first == second
    assert first_underlying == 6
    assert memo.underlying_read_count == first_underlying
    assert memo.cache_hit_count == first_underlying
    assert len(calls) == first_underlying


def test_broad_evaluation_publication_uses_terminal_administrative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _projected, core, _root_identity = _projection_root_fixture(
        monkeypatch
    )
    projections = [
        _identity(f"administrative-projection-{source}")
        for source in range(contract.PANEL_SLATE_COUNT)
    ]
    selections = [
        _identity(f"administrative-selection-{source}")
        for source in range(contract.PANEL_SLATE_COUNT)
    ]
    task_bindings = [
        {
            "task_index": source,
            "source_ordinal": source,
            "phase": contract.BROAD_SCREEN_PHASE,
            "process_role": "broad-slate-assembler",
            "request": {"source": source},
        }
        for source in range(contract.PANEL_SLATE_COUNT)
    ]
    administrative_calls: list[int] = []

    def compile_administrative(**kwargs: Any) -> dict[str, object]:
        administrative_calls.append(int(kwargs["source_ordinal"]))
        return _fake_budget(
            process_role="broad-evaluator",
            hash_field="evaluator_process_budget_sha256",
            source=int(kwargs["source_ordinal"]),
        )

    monkeypatch.setattr(
        preparation,
        "_broad_evaluator_process_budget_from_administrative_authorities_v1",
        compile_administrative,
    )
    monkeypatch.setattr(
        preparation,
        "_read_scientific_body",
        lambda *_args, **_kwargs: pytest.fail(
            "administrative broad preparation reopened a science body"
        ),
    )
    descriptor = task_manifest.layer_registry_v1(OUTPUT_PREFIX)[2]
    plan = preparation.layer_preparation_authority_plan_v1(
        output_prefix=OUTPUT_PREFIX,
        layer_id="broad-evaluation-result",
        layer_ordinal=2,
    )
    authority_records: list[dict[str, object]] = []
    requests, cursor = preparation._publish_evaluation_task_authorities(
        descriptor=descriptor,
        core=core,
        outputs={
            "projection": projections,
            "broad-selection-receipt": selections,
        },
        predecessor_context={
            "manifests_by_layer": {
                "broad-selection-receipt": {
                    "task_bindings": task_bindings,
                },
            },
            "terminal_publication_identities_generation_exact": True,
        },
        plan=plan,
        plan_cursor=0,
        authority_records=authority_records,
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
    )

    assert len(requests) == contract.PANEL_SLATE_COUNT
    assert cursor == len(plan) - 1
    assert len(authority_records) == contract.PANEL_SLATE_COUNT * 2
    assert administrative_calls == list(range(contract.PANEL_SLATE_COUNT))


def test_administrative_broad_evaluator_budget_is_legacy_byte_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _projected, core, _root_identity = _projection_root_fixture(
        monkeypatch
    )
    topology = core["topology"]
    source = 0
    projection_uri = next(
        str(row["uri"])
        for row in topology["objects"]
        if row["role"] == "projection"
    )
    selection_uri = next(
        str(row["uri"])
        for row in topology["objects"]
        if row["role"] == "broad-selection-receipt"
    )
    projection_identity = store.seed_body(
        projection_uri, {"fixture": "projection"}, generation=70_000
    )
    selection_identity = store.seed_body(
        selection_uri, {"fixture": "selection"}, generation=70_001
    )
    later_source_identity = _identity("administrative-later-source")
    world_identities = {
        block: _identity(f"administrative-world-{block}")
        for block in contract.WORLD_BLOCKS
    }
    fake_bundle = {
        "source_ordinal": source,
        "fold_projections": [
            {
                "training_blocks": [
                    block for block in contract.WORLD_BLOCKS
                    if block != contract.WORLD_BLOCKS[fold]
                ],
                "later_source_identity": later_source_identity,
                "world_artifact_identities": {
                    f"world_artifact_{block.lower()}": identity
                    for block, identity in world_identities.items()
                },
            }
            for fold in range(contract.FOLDS_PER_SLATE)
        ],
    }
    monkeypatch.setattr(
        contract,
        "validate_projection_bundle_authority_v1",
        lambda *_args, **_kwargs: deepcopy(fake_bundle),
    )
    monkeypatch.setattr(
        contract,
        "validate_selection_receipt_authority_v1",
        lambda *_args, **_kwargs: {
            "phase": contract.BROAD_SCREEN_PHASE,
        },
    )
    worker_budgets = [
        contract.compile_process_budget_v1(
            process_role="broad-fold-selector",
            projection_bundle={"fixture": "projection"},
            projection_bundle_identity=projection_identity,
            topology=topology,
            topology_identity=core["manifest"]["topology_identity"],
            source_ordinal=source,
            fold_ordinal=fold,
        )
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    worker_identities = [
        store.seed_body(
            f"gs://fixture-layer-preparation/worker-{fold}.json",
            budget,
            generation=71_000 + fold,
        )
        for fold, budget in enumerate(worker_budgets)
    ]
    assembler_identity = store.seed_body(
        "gs://fixture-layer-preparation/assembler.json",
        {"fixture": "assembler"},
        generation=72_000,
    )
    selection_request = task_manifest.build_selection_task_request_v1(
        phase=contract.BROAD_SCREEN_PHASE,
        source_ordinal=source,
        design_identity=core["manifest"]["design_identity"],
        topology_identity=core["manifest"]["topology_identity"],
        projection_bundle_identity=projection_identity,
        assembler_process_budget_identity=assembler_identity,
        worker_process_budget_identities=worker_identities,
    )
    legacy = contract.compile_evaluator_process_budget_v1(
        design=core["design"],
        design_publication_identity=core["manifest"]["design_identity"],
        bootstrap_manifest=core["bootstrap_manifest"],
        bootstrap_manifest_identity=core["manifest"][
            "bootstrap_manifest_identity"
        ],
        launch_intent_identity=core["manifest"][
            "pre_design_run_authorization_identity"
        ],
        projection_bundle={"fixture": "projection"},
        projection_bundle_identity=projection_identity,
        topology_identity=core["manifest"]["topology_identity"],
        source_ordinal=source,
        selection_receipt={"phase": contract.BROAD_SCREEN_PHASE},
        selection_receipt_identity=selection_identity,
    )
    reads: list[dict[str, object]] = []

    def counted(identity: Any) -> bytes:
        reads.append(dict(identity))
        return store.read_exact(identity)

    administrative = (
        preparation._broad_evaluator_process_budget_from_administrative_authorities_v1(
            core=core,
            source_ordinal=source,
            projection_bundle_identity=projection_identity,
            selection_receipt_identity=selection_identity,
            selection_request=selection_request,
            read_exact=counted,
        )
    )
    assert contract.canonical_json_bytes_v1(administrative) == (
        contract.canonical_json_bytes_v1(legacy)
    )
    assert reads == worker_identities[:2]
    assert projection_identity not in reads
    assert selection_identity not in reads


def test_administrative_broad_evaluator_rejects_cross_fold_world_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _projected, core, _root_identity = _projection_root_fixture(
        monkeypatch
    )
    topology = core["topology"]
    projection_identity = store.seed_body(
        next(
            str(row["uri"])
            for row in topology["objects"] if row["role"] == "projection"
        ),
        {"fixture": "projection"},
        generation=80_000,
    )
    selection_identity = store.seed_body(
        next(
            str(row["uri"])
            for row in topology["objects"]
            if row["role"] == "broad-selection-receipt"
        ),
        {"fixture": "selection"},
        generation=80_001,
    )
    later_source_identity = _identity("drift-later-source")
    worlds = {
        block: _identity(f"drift-world-{block}")
        for block in contract.WORLD_BLOCKS
    }

    def bundle_for_fold(fold: int) -> dict[str, object]:
        return {
            "source_ordinal": 0,
            "fold_projections": [
                {
                    "training_blocks": [
                        block for block in contract.WORLD_BLOCKS
                        if block != contract.WORLD_BLOCKS[index]
                    ],
                    "later_source_identity": later_source_identity,
                    "world_artifact_identities": {
                        f"world_artifact_{block.lower()}": (
                            _identity("drifted-world-R2")
                            if fold == 1 and index == 1 and block == "R2"
                            else identity
                        )
                        for block, identity in worlds.items()
                    },
                }
                for index in range(contract.FOLDS_PER_SLATE)
            ],
        }

    active_bundle = bundle_for_fold(0)
    monkeypatch.setattr(
        contract,
        "validate_projection_bundle_authority_v1",
        lambda *_args, **_kwargs: deepcopy(active_bundle),
    )
    worker_budgets = []
    for fold in range(contract.FOLDS_PER_SLATE):
        active_bundle = bundle_for_fold(fold)
        worker_budgets.append(contract.compile_process_budget_v1(
            process_role="broad-fold-selector",
            projection_bundle={},
            projection_bundle_identity=projection_identity,
            topology=topology,
            topology_identity=core["manifest"]["topology_identity"],
            source_ordinal=0,
            fold_ordinal=fold,
        ))
    worker_identities = [
        store.seed_body(
            f"gs://fixture-layer-preparation/drift-worker-{fold}.json",
            budget,
            generation=81_000 + fold,
        )
        for fold, budget in enumerate(worker_budgets)
    ]
    request = task_manifest.build_selection_task_request_v1(
        phase=contract.BROAD_SCREEN_PHASE,
        source_ordinal=0,
        design_identity=core["manifest"]["design_identity"],
        topology_identity=core["manifest"]["topology_identity"],
        projection_bundle_identity=projection_identity,
        assembler_process_budget_identity=_identity("drift-assembler"),
        worker_process_budget_identities=worker_identities,
    )
    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error,
        match="world identity differs",
    ):
        preparation._broad_evaluator_process_budget_from_administrative_authorities_v1(
            core=core,
            source_ordinal=0,
            projection_bundle_identity=projection_identity,
            selection_receipt_identity=selection_identity,
            selection_request=request,
            read_exact=store.read_exact,
        )
