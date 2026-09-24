from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_fair_fill_current_bank_authority_v1 as authority


MANIFEST = Path("/tmp/r6-successor-source-manifest.json")
REAL = Path("/tmp/r6-successor-reality")
PROJECTION = Path("/tmp/r6-v6-task0-projection.json")
DIAGNOSIS = Path("/tmp/r6-current-bank-projection-diagnosis/2023-w01-inputs")


def _selection_with_lineage(path: Path) -> dict[str, object]:
    selection = json.loads(path.read_bytes())
    if "source_task_result_identity" not in selection:
        projection = json.loads(PROJECTION.read_bytes())["fold_projections"][0]
        envelope = json.loads(Path("/tmp/r6-current-bank-task-result-00.json").read_bytes())
        selection.update({
            "source_task_result_identity": projection["source_task_result_identity"],
            "source_task_result_payload_sha256": projection["task_result_payload_sha256"],
            "source_execution_manifest_sha256": envelope["execution_manifest_sha256"],
            "source_commit_sha": envelope["source_commit_sha"],
            "source_immutable_image": envelope["immutable_image"],
            "source_manifest_identity": envelope["manifest_identity"],
            "source_panel_sha256": "0" * 64,
            "source_panel_member_count": 54,
        })
        selection["sealed_selection_fold_sha256"] = authority.contract.canonical_sha256_v1({
            key: value for key, value in selection.items()
            if key != "sealed_selection_fold_sha256"
        })
    return selection


def _real_inputs() -> tuple[dict[str, object], dict[str, Path]]:
    required = [
        MANIFEST, PROJECTION, REAL / "topology.json",
        REAL / "fold-00-process-budget.json", DIAGNOSIS / "later-source-freeze.json",
    ]
    if any(not path.is_file() for path in required):
        pytest.skip("sealed V6 task0 local artifact cache is unavailable")
    manifest = json.loads(MANIFEST.read_bytes())
    projection = json.loads(PROJECTION.read_bytes())
    request = manifest["task_bindings"][0]["request"]
    paths = {
        request["topology_identity"]["uri"]: REAL / "topology.json",
        request["projection_bundle_identity"]["uri"]: PROJECTION,
        request["worker_process_budget_identities"][0]["uri"]:
            REAL / "fold-00-process-budget.json",
        projection["fold_projections"][0]["later_source_identity"]["uri"]:
            DIAGNOSIS / "later-source-freeze.json",
    }
    return manifest, paths


def test_real_sealed_manifest_compiles_exact_54x5_headers_without_reads() -> None:
    manifest, _ = _real_inputs()
    result = authority.validate_54x5_manifest_headers_v1(manifest)
    assert result["source_count"] == 54
    assert result["folds_per_source"] == 5
    assert result["recipe_count"] == 270
    assert result["object_body_open_count"] == 0
    assert all(not row["world_artifact_body_opened"] for row in result["recipes"])


def test_real_task0_selection_preparation_never_opens_heldout_world() -> None:
    manifest, paths = _real_inputs()
    opened: list[str] = []

    def read_exact(identity: dict[str, object]) -> bytes:
        uri = str(identity["uri"])
        opened.append(uri)
        if uri not in paths:
            raise AssertionError(f"unexpected object body open: {uri}")
        return paths[uri].read_bytes()

    package = authority.prepare_selection_package_v1(
        manifest, source_ordinal=0, fold_ordinal=0, read_exact=read_exact,
    )
    assert package["slate_id"] == "2023-w01"
    assert package["candidate_count"] == 3051
    assert package["training_blocks"] == ["R1", "R2", "R3", "R4"]
    assert package["heldout_block_label_only"] == "R0"
    assert package["heldout_world_identity_exposed"] is False
    assert package["heldout_world_body_open_count"] == 0
    assert len(opened) == 4
    assert not any("worlds-r0" in uri for uri in opened)


def test_training_materializer_cannot_request_a_fifth_identity() -> None:
    manifest, paths = _real_inputs()
    package = authority.prepare_selection_package_v1(
        manifest, source_ordinal=0, fold_ordinal=0,
        read_exact=lambda identity: paths[str(identity["uri"])].read_bytes(),
    )
    opened: list[str] = []

    def training_reader(identity: dict[str, object]) -> bytes:
        opened.append(str(identity["uri"]))
        return b"not-decoded-by-authority-boundary"

    bodies = authority.open_training_world_bodies_v1(
        package, read_exact=training_reader,
    )
    assert len(bodies) == 4
    assert opened == [
        str(identity["uri"])
        for identity in package["training_artifact_identities"]
    ]
    assert not any("worlds-r0" in uri for uri in opened)


def test_evaluation_rejects_forged_selection_before_any_object_read() -> None:
    path = Path("/tmp/r6-fair-fill-task0-fold0-sealed-selection.json")
    if not path.is_file():
        pytest.skip("real sealed task0 selection receipt is unavailable")
    manifest, _ = _real_inputs()
    selection = _selection_with_lineage(path)
    identity = authority.derive_create_once_selection_identity_v1(selection)
    forged = deepcopy(identity)
    forged["sha256"] = "0" * 64
    reads = 0

    def forbidden_read(_identity: dict[str, object]) -> bytes:
        nonlocal reads
        reads += 1
        raise AssertionError("evaluation opened authority before selection gate")

    with pytest.raises(
        authority.CorpusR6FairFillCurrentBankAuthorityV1Error,
        match="create-once derived authority",
    ):
        authority.evaluate_sealed_selection_fold_v1(
            manifest, selection_result=selection,
            selection_result_identity=forged, read_exact=forbidden_read,
        )
    assert reads == 0


def test_selection_identity_rejects_embedded_heldout_claim() -> None:
    path = Path("/tmp/r6-fair-fill-task0-fold0-sealed-selection.json")
    if not path.is_file():
        pytest.skip("real sealed task0 selection receipt is unavailable")
    selection = _selection_with_lineage(path)
    selection["heldout_artifact_identity_present"] = True
    selection["sealed_selection_fold_sha256"] = authority.contract.canonical_sha256_v1({
        key: value for key, value in selection.items()
        if key != "sealed_selection_fold_sha256"
    })
    with pytest.raises(
        authority.CorpusR6FairFillCurrentBankAuthorityV1Error,
        match="fields/policy differ",
    ):
        authority.derive_create_once_selection_identity_v1(selection)
