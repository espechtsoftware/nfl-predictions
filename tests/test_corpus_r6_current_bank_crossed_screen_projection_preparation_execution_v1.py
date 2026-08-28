from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_projection_preparation_v1 as preparation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


OUTPUT_PREFIX = (
    contract.OUTPUT_NAMESPACE
    + "fixture-current-bank-projection-preparation/"
)
CODE_COMMIT = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64
REUSED_JOB_NAME = "fixture-current-bank-reused-job"


def _identity(
    uri: str, raw: bytes, *, generation: int | str,
) -> dict[str, object]:
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
        self.read_counts: Counter[tuple[str, str, str, int]] = Counter()
        self.publish_attempts: list[str] = []
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

    def seed(self, identity: dict[str, object], raw: bytes) -> None:
        assert identity == _identity(
            str(identity["uri"]), raw, generation=str(identity["generation"])
        )
        self.values[self._key(identity)] = bytes(raw)
        self.current[str(identity["uri"])] = dict(identity)

    def read_exact(self, identity: Any) -> bytes:
        key = self._key(identity)
        self.read_counts[key] += 1
        return self.values[key]

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        self.publish_attempts.append(uri)
        if uri in self.current:
            raise RuntimeError("strict create-once collision")
        self.generation += 1
        identity = _identity(uri, raw, generation=self.generation)
        self.seed(identity, raw)
        self.publish_uris.append(uri)
        return identity

    def body(self, identity: Any) -> dict[str, object]:
        value = batch.parse_canonical_json_bytes(
            self.read_exact(identity), label="fixture authority"
        )
        assert isinstance(value, dict)
        return value


def _source_bytes() -> tuple[bytes, bytes]:
    root = Path(__file__).resolve().parents[1]
    return (
        (root / contract.MODULE_PATH).read_bytes(),
        (root / contract.CONTRACT_REPORT_PATH).read_bytes(),
    )


def _panel_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_MemoryStore, dict[str, object], dict[str, object]]:
    store = _MemoryStore()
    manifest_identity = _identity(
        "gs://fixture-current-bank-inputs/execution-manifest.json",
        b"execution-manifest",
        generation=2,
    )
    panel_index_identity = _identity(
        "gs://fixture-current-bank-inputs/fixed-panel-index.json",
        b"fixed-panel-index",
        generation=3,
    )
    rows: list[dict[str, object]] = []
    for source_ordinal in range(contract.PANEL_SLATE_COUNT):
        leaf_identity = _identity(
            (
                "gs://fixture-current-bank-inputs/slate-freezes/"
                f"slate-{source_ordinal:02d}.json"
            ),
            f"leaf-{source_ordinal:02d}".encode("ascii"),
            generation=100 + source_ordinal,
        )
        result_identity = _identity(
            (
                "gs://fixture-current-bank-inputs/task-results/"
                f"task-{source_ordinal:02d}.json"
            ),
            f"result-{source_ordinal:02d}".encode("ascii"),
            generation=200 + source_ordinal,
        )
        rows.append({
            "source_ordinal": source_ordinal,
            "slate_freeze_identity": leaf_identity,
            "task_result_identity": result_identity,
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
    raw = contract.canonical_json_bytes_v1(root)
    root_identity = _identity(
        "gs://fixture-current-bank-inputs/panel-freeze.json",
        raw,
        generation=1,
    )
    monkeypatch.setattr(contract, "PANEL_IDENTITY", root_identity)
    monkeypatch.setattr(
        contract, "PANEL_SELF_SHA256", root["panel_freeze_sha256"]
    )
    store.seed(root_identity, raw)
    return store, root, root_identity


def _prepare(
    store: _MemoryStore, root: dict[str, object], root_identity: dict[str, object],
) -> dict[str, object]:
    code_raw, report_raw = _source_bytes()
    return preparation.prepare_projection_first_layer_v1(
        output_prefix=OUTPUT_PREFIX,
        contract_module_bytes=code_raw,
        preoutput_report_bytes=report_raw,
        code_commit=CODE_COMMIT,
        image_digest=IMAGE_DIGEST,
        reused_job_name=REUSED_JOB_NAME,
        panel_root_body=root,
        panel_root_identity=root_identity,
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
    )


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = contract.canonical_sha256_v1(value)


def test_fresh_projection_preparation_publishes_exact_acyclic_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, root, root_identity = _panel_fixture(monkeypatch)
    result = _prepare(store, root, root_identity)
    lattice = preparation.projection_preparation_uri_lattice_v1(OUTPUT_PREFIX)

    assert store.publish_uris == list(lattice.values())
    assert store.publish_attempts == list(lattice.values())
    assert len(result["structural_identities"]) == 111
    assert result["structural_identities"][0] == root_identity
    assert result["structural_identities"][1] == root["manifest_identity"]
    assert result["structural_identities"][2] == root["panel_index_identity"]
    assert len({row["uri"] for row in result["structural_identities"]}) == 111
    assert result["manifest_identity"] == result[
        "projection_task_manifest_identity"
    ]

    code_raw, report_raw = _source_bytes()
    assert store.read_exact(result["code_identity"]) == code_raw
    assert store.read_exact(result["report_identity"]) == report_raw
    assert result["code_identity"]["sha256"] == (
        preparation.FROZEN_CONTRACT_MODULE_SHA256
    )
    assert result["report_identity"]["sha256"] == (
        preparation.FROZEN_PREOUTPUT_REPORT_SHA256
    )

    authorization = store.body(result["pre_design_run_authorization_identity"])
    topology = store.body(result["topology_identity"])
    bootstrap = store.body(result["bootstrap_manifest_identity"])
    design = store.body(result["design_identity"])
    budget = store.body(result["projection_process_budget_identity"])
    request = store.body(result["projection_task_request_identity"])
    manifest = store.body(result["projection_task_manifest_identity"])
    assert authorization["code_commit"] == CODE_COMMIT
    assert authorization["image_digest"] == IMAGE_DIGEST
    assert authorization["reused_job_name"] == REUSED_JOB_NAME
    assert bootstrap["run_identity"] == result[
        "pre_design_run_authorization_identity"
    ]
    assert design["code_identity"] == result["code_identity"]
    assert design["report_identity"] == result["report_identity"]
    assert request["process_budget_identity"] == result[
        "projection_process_budget_identity"
    ]
    assert request["prior_projection_identities"] == [None] * 54
    assert manifest["predecessor_layer_receipts"] == []
    assert manifest["task_bindings"][0]["request"] == request
    assert [
        row["identity"] for row in budget["read_allowlist"][4:]
    ] == result["structural_identities"]
    assert task_manifest.reopen_task_manifest_authority_v1(
        result["manifest_identity"], read_exact=store.read_exact
    )["manifest"] == manifest
    assert topology == design["topology"]

    receipt = result["preparation_receipt"]
    assert preparation.validate_projection_preparation_receipt_v1(
        receipt
    ) == receipt
    assert receipt["authority_publication_count"] == 9
    assert [
        row["authority_role"] for row in receipt["authority_publications"]
    ] == list(lattice)[:-1]
    assert receipt["projection_task_manifest_identity"] == result[
        "manifest_identity"
    ]
    assert store.body(result["preparation_receipt_identity"]) == receipt
    for identity in (
        result["code_identity"],
        result["report_identity"],
        result["pre_design_run_authorization_identity"],
        result["topology_identity"],
        result["bootstrap_manifest_identity"],
        result["design_identity"],
        result["projection_process_budget_identity"],
        result["projection_task_request_identity"],
        result["projection_task_manifest_identity"],
        result["preparation_receipt_identity"],
    ):
        assert store.read_counts[store._key(identity)] >= 1

    drifted = deepcopy(receipt)
    drifted["structural_identities"][3], drifted["structural_identities"][5] = (
        drifted["structural_identities"][5],
        drifted["structural_identities"][3],
    )
    drifted["structural_identities_sha256"] = contract.canonical_sha256_v1(
        drifted["structural_identities"]
    )
    _rehash(drifted, "projection_preparation_receipt_sha256")
    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error,
        match="fixed authority differs",
    ):
        preparation.validate_projection_preparation_receipt_v1(drifted)

    drifted = deepcopy(receipt)
    changed_root = drifted["panel_root_body"]
    changed_root["slate_freezes"][0]["task_result_identity"]["generation"] = "999"
    changed_root.pop("panel_freeze_sha256")
    changed_root["panel_freeze_sha256"] = contract.canonical_sha256_v1(
        changed_root
    )
    _rehash(drifted, "projection_preparation_receipt_sha256")
    with pytest.raises(
        ValueError,
        match="sealed panel root self-hash differs",
    ):
        preparation.validate_projection_preparation_receipt_v1(drifted)

    for field, record_index, changed_sha in (
        ("code_identity", 0, "0" * 64),
        ("report_identity", 1, "1" * 64),
    ):
        drifted = deepcopy(receipt)
        drifted[field]["sha256"] = changed_sha
        drifted["authority_publications"][record_index]["identity"] = deepcopy(
            drifted[field]
        )
        drifted["authority_publications_sha256"] = contract.canonical_sha256_v1(
            drifted["authority_publications"]
        )
        _rehash(drifted, "projection_preparation_receipt_sha256")
        with pytest.raises(
            preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error,
            match="fixed authority differs",
        ):
            preparation.validate_projection_preparation_receipt_v1(drifted)


def test_create_once_collision_mismatch_fails_without_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, root, root_identity = _panel_fixture(monkeypatch)
    uri = preparation.projection_preparation_uri_lattice_v1(OUTPUT_PREFIX)[
        "contract-module-source"
    ]
    store.seed(_identity(uri, b"wrong-source", generation=999), b"wrong-source")
    with pytest.raises(RuntimeError, match="create-once collision"):
        _prepare(store, root, root_identity)
    assert store.publish_attempts == [uri]
    assert store.publish_uris == []

    partial_store, partial_root, partial_identity = _panel_fixture(monkeypatch)
    topology_uri = preparation.projection_preparation_uri_lattice_v1(
        OUTPUT_PREFIX
    )["topology"]
    partial_store.seed(
        _identity(topology_uri, b"wrong-topology", generation=998),
        b"wrong-topology",
    )
    with pytest.raises(RuntimeError, match="create-once collision"):
        _prepare(partial_store, partial_root, partial_identity)
    expected = list(
        preparation.projection_preparation_uri_lattice_v1(OUTPUT_PREFIX).values()
    )
    assert partial_store.publish_attempts == expected[:4]
    assert partial_store.publish_uris == expected[:3]
    assert not any(uri in partial_store.current for uri in expected[4:])


def test_wrong_panel_root_or_frozen_source_rejects_before_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, root, root_identity = _panel_fixture(monkeypatch)
    changed = deepcopy(root)
    changed["slate_freezes"][0]["source_ordinal"] = 1
    code_raw, report_raw = _source_bytes()
    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error,
        match="supplied frozen panel-root body differs",
    ):
        preparation.prepare_projection_first_layer_v1(
            output_prefix=OUTPUT_PREFIX,
            contract_module_bytes=code_raw,
            preoutput_report_bytes=report_raw,
            code_commit=CODE_COMMIT,
            image_digest=IMAGE_DIGEST,
            reused_job_name=REUSED_JOB_NAME,
            panel_root_body=changed,
            panel_root_identity=root_identity,
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )
    assert store.publish_attempts == []

    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error,
        match="frozen source authority",
    ):
        preparation.prepare_projection_first_layer_v1(
            output_prefix=OUTPUT_PREFIX,
            contract_module_bytes=code_raw[:-1] + b"X",
            preoutput_report_bytes=report_raw,
            code_commit=CODE_COMMIT,
            image_digest=IMAGE_DIGEST,
            reused_job_name=REUSED_JOB_NAME,
            panel_root_body=root,
            panel_root_identity=root_identity,
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )
    assert store.publish_attempts == []


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("code_commit", "c" * 40),
        ("image_digest", "sha256:" + "d" * 64),
        ("reused_job_name", "different-valid-reused-job"),
    ],
)
def test_downstream_code_image_or_job_drift_rejects_before_publication(
    monkeypatch: pytest.MonkeyPatch, field: str, replacement: str,
) -> None:
    store, root, root_identity = _panel_fixture(monkeypatch)
    original = task_manifest.build_pre_design_run_authorization_v1

    def drifted_authorization(**kwargs: Any) -> dict[str, object]:
        changed = dict(kwargs)
        changed[field] = replacement
        return original(**changed)

    monkeypatch.setattr(
        task_manifest,
        "build_pre_design_run_authorization_v1",
        drifted_authorization,
    )
    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error,
        match="code/image/job authority differs",
    ):
        _prepare(store, root, root_identity)
    assert store.publish_attempts == []


def test_projection_budget_cannot_splice_a_rehashed_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, root, root_identity = _panel_fixture(monkeypatch)
    original_compile = contract.compile_publisher_process_budget_v1

    def drifted_compile(**kwargs: Any) -> dict[str, object]:
        budget = original_compile(**kwargs)
        reads = budget["read_allowlist"]
        reads[4]["identity"], reads[5]["identity"] = (
            reads[5]["identity"],
            reads[4]["identity"],
        )
        scientific = [row["identity"] for row in reads[4:]]
        budget["scientific_read_identities_sha256"] = (
            contract.canonical_sha256_v1(scientific)
        )
        _rehash(budget, "publisher_process_budget_sha256")
        return budget

    monkeypatch.setattr(
        contract, "compile_publisher_process_budget_v1", drifted_compile
    )
    monkeypatch.setattr(
        contract,
        "validate_publisher_process_budget_v1",
        lambda value, **_kwargs: dict(value),
    )
    with pytest.raises(
        preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error,
        match="budget structural inventory differs",
    ):
        _prepare(store, root, root_identity)
    lattice = preparation.projection_preparation_uri_lattice_v1(OUTPUT_PREFIX)
    assert store.publish_uris == list(lattice.values())[:6]
    assert lattice["projection-publisher-process-budget"] not in store.current


def test_preparation_boundary_has_no_prior_resume_or_discovery_input() -> None:
    import inspect

    parameters = set(
        inspect.signature(preparation.prepare_projection_first_layer_v1).parameters
    )
    assert parameters == {
        "output_prefix", "contract_module_bytes", "preoutput_report_bytes",
        "code_commit", "image_digest", "reused_job_name", "panel_root_body",
        "panel_root_identity", "publish_create_once", "read_exact",
    }
    assert not any(
        token in name
        for name in parameters
        for token in ("prior", "resume", "current", "list", "outcome", "graph")
    )
