from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = str(REPO / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_stack_relaxation_carve as finish  # noqa: E402


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _raw(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _provenance(frozen: finish.FrozenRun) -> dict[str, object]:
    return {
        "version": "stack-relaxation-carve-provenance-addendum-v1",
        "run_id": frozen.run_id,
        "attestation_scope": (
            "mechanical-source-identity-correction-before-scientific-harvest"
        ),
        "original_manifest_sha256": frozen.original_manifest_sha256,
        "original_execution_ledger_sha256": frozen.execution_ledger_sha256,
        "original_launch_receipt_sha256": frozen.launch_receipt_sha256,
        "code_sha": frozen.code_sha,
        "build_id": frozen.build_id,
        "image": frozen.image,
        "protocol_sha256": frozen.protocol_sha256,
        "runner_sha256": frozen.runner_sha256,
        "upload_helper_sha256": frozen.upload_helper_sha256,
        "manifest_recorded_chain_path": "scripts/cloud_all_boom_s_chain.sh",
        "manifest_recorded_chain_sha256": frozen.recorded_chain_sha256,
        "actual_chain_path": "scripts/cloud_stack_carve_chain.sh",
        "actual_chain_sha256": frozen.actual_chain_sha256,
        "actual_chain_at_code_sha256": frozen.actual_chain_sha256,
        "finisher_path": "scripts/finish_stack_relaxation_carve.py",
        "finisher_sha256": _sha(Path(finish.__file__)),
        "aggregation_source": "scripts/cloud_stack_carve_chain.sh:144-232",
        "correction_is_metadata_only": True,
        "cell_rerun_licensed": False,
        "scientific_result_body_inspected_before_freeze": False,
        "watcher_stopped_before_harvest": True,
        "cloud_execution_cancelled": False,
        "aggregate_preexisting": False,
        "historical_outcome_lease_object_present_during_audit": False,
        "logical_outcome_lane_remains_occupied_until_strict_harvest": True,
        "uploaded_body_contains_upload_receipt": False,
        "production_change_licensed": False,
    }


def _arm(*, recovery: bool, score: float) -> dict[str, object]:
    return {
        "c_score": score + 10.0,
        "pool_unique": 100,
        "pool_mean": score - 5.0,
        "s_score": None if recovery else score,
        "selected_mean": None if recovery else score - 10.0,
        **({"four_seed_recovery": True} if recovery else {}),
        "thresholds": {
            str(line): 0 for line in (187, 194, 200, 210, 220, 230, 240)
        },
    }


def _cell_body(
    cell: finish.Cell, frozen: finish.FrozenRun,
) -> bytes:
    recovery = (cell.season, cell.week) == (2025, 1)
    blocks = [0, 1, 2, 4] if recovery else [0, 1, 2, 3, 4]
    seeds = []
    for block in blocks:
        seeds.append({
            "block": block,
            "panel_run_id": f"panel-{block}",
            "artifact": {
                "uri": f"gs://source/artifact-{block}.npz",
                "sha256": "c" * 64,
                "generation": "1",
                "updated": "2026-08-19T00:00:00+00:00",
                "bytes": 100,
            },
            "reproduction": {
                "generated_candidates": 100,
                "artifact_candidates": 100,
                "registered_candidates": 100,
                "mode": "bq-identities-and-artifact-totals",
                "max_total_delta": 0.0,
            },
            "native_count": 100,
            "treatment_count": 100,
            "shortfall": 0,
            "open_census": {"n": 1, "n_outside_mandate": 1},
        })
    control = _arm(recovery=recovery, score=180.0)
    treatment = _arm(recovery=recovery, score=180.0)
    value: dict[str, Any] = {
        "version": "stack-relaxation-carve-v1",
        "run_id": frozen.run_id,
        "season": cell.season,
        "week": cell.week,
        "code_sha": frozen.code_sha,
        "image": frozen.image,
        "protocol_sha256": frozen.protocol_sha256,
        "treatment_levers": {"OPEN_BOOM_SOLVES": "8"},
        "smoke": False,
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "seeds": seeds,
        "open_candidates_total": len(blocks),
        "actual_parity_max_delta": 0.0,
        "control": control,
        "treatment": treatment,
        "paired_delta_c": 0.0,
        "cross_run_reproduction": True,
    }
    if recovery:
        value["recovery_four_seed_slate"] = True
    else:
        value.update({
            "selected_book_intersection": 80,
            "open_selected_count": 1,
            "paired_delta_s": 0.0,
            "winner_overlap": {
                "control": {"max_minus_null": 0.0},
                "treatment": {"max_minus_null": 0.0},
            },
        })
    return _raw(value)


def _execution(
    cell: finish.Cell, frozen: finish.FrozenRun,
) -> dict[str, object]:
    return {
        "metadata": {
            "name": cell.execution,
            "generation": 1,
            "labels": {
                "run.googleapis.com/job": cell.job,
                "run.googleapis.com/jobUid": frozen.job_uid,
                "run.googleapis.com/jobGeneration": frozen.job_generation,
            },
        },
        "spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": frozen.image,
                    "command": ["python"],
                    "args": [
                        "scripts/run_stack_relaxation_carve.py",
                        "--season", str(cell.season),
                        "--week", str(cell.week),
                        "--output-uri", cell.uri,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": frozen.code_sha},
                        {"name": "ANALYSIS_IMAGE", "value": frozen.image},
                    ],
                    "resources": {"limits": {
                        "cpu": "4", "memory": "16Gi",
                    }},
                }],
                "maxRetries": 0,
                "timeoutSeconds": "7200",
                "serviceAccountName": frozen.service_account,
            }},
        },
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "completionTime": "2026-08-20T04:47:39Z",
        },
    }


@dataclass
class SyntheticRun:
    root: Path
    out: Path
    provenance: Path
    frozen: finish.FrozenRun
    cells: list[finish.Cell]
    executions: dict[str, dict[str, object]]
    inventory: dict[str, dict[str, object]]
    bodies: dict[str, bytes]
    events: list[tuple]

    def execution_loader(self, name: str) -> dict[str, Any]:
        self.events.append(("execution", name))
        return self.executions[name]  # type: ignore[return-value]

    def inventory_loader(self, prefix: str) -> dict[str, dict[str, Any]]:
        self.events.append(("inventory", prefix))
        return self.inventory  # type: ignore[return-value]

    def downloader(self, uri: str, metadata: dict[str, Any]) -> bytes:
        self.events.append(("download", uri, metadata["generation"]))
        assert metadata["generation"] == self.inventory[uri]["generation"]
        return self.bodies[uri]

    def git_loader(self, root: Path, code_sha: str, relative: str) -> bytes:
        assert root == self.root
        assert code_sha == self.frozen.code_sha
        return (root / relative).read_bytes()


@pytest.fixture
def synthetic_run(tmp_path: Path) -> SyntheticRun:
    root = tmp_path / "repo"
    out = root / "reports/stack-relaxation-carve-runs" / finish.RUN_ID
    out.mkdir(parents=True)
    source_raw = {
        "reports/2026-08-19-stack-relaxation-carve-protocol.md": b"protocol\n",
        "scripts/run_stack_relaxation_carve.py": b"runner\n",
        "scripts/run_cbwu_seed_order_audit.py": b"upload helper\n",
        "scripts/cloud_all_boom_s_chain.sh": b"recorded wrong chain\n",
        "scripts/cloud_stack_carve_chain.sh": b"actual chain\n",
    }
    for relative, raw in source_raw.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    frozen = replace(
        finish.FROZEN,
        code_sha="a" * 40,
        image="example/image@sha256:" + "b" * 64,
        build_id="build-id",
        protocol_sha256=_sha(
            root / "reports/2026-08-19-stack-relaxation-carve-protocol.md"
        ),
        runner_sha256=_sha(root / "scripts/run_stack_relaxation_carve.py"),
        upload_helper_sha256=_sha(
            root / "scripts/run_cbwu_seed_order_audit.py"
        ),
        recorded_chain_sha256=_sha(
            root / "scripts/cloud_all_boom_s_chain.sh"
        ),
        actual_chain_sha256=_sha(
            root / "scripts/cloud_stack_carve_chain.sh"
        ),
        original_manifest_sha256="0" * 64,
        execution_ledger_sha256="0" * 64,
        launch_receipt_sha256="0" * 64,
        job_uid="synthetic-job-uid",
    )
    manifest = {
        "run_id": frozen.run_id,
        "image": frozen.image,
        "code_sha": frozen.code_sha,
        "build_id": frozen.build_id,
        "output_prefix": frozen.output_prefix,
        "protocol_sha256": frozen.protocol_sha256,
        "runner_sha256": frozen.runner_sha256,
        "chain_sha256": frozen.recorded_chain_sha256,
        "quota_note": f"reused job {frozen.job} (frozen-chain rule 5)",
        "uses_realized_outcomes": "true",
        "production_change_licensed": "false",
        "predeclared_prior": "uncertain-modest-dose",
        "cells": "54",
        "canary": "2023-1",
    }
    manifest_path = out / "manifest.txt"
    manifest_path.write_text(
        "".join(f"{key}={value}\n" for key, value in manifest.items()),
        encoding="utf-8",
    )
    cells = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            execution = f"{frozen.job}-s{season}w{week}"
            uri = f"{frozen.output_prefix}/slate-{season}-{week}.json"
            cells.append(finish.Cell(
                season, week, frozen.job, execution, uri,
            ))
    ledger_path = out / "executions.txt"
    ledger_path.write_text("".join(
        f"{cell.season} {cell.week} {cell.job} {cell.execution} {cell.uri}\n"
        for cell in cells
    ), encoding="utf-8")
    frozen = replace(
        frozen,
        original_manifest_sha256=_sha(manifest_path),
        execution_ledger_sha256=_sha(ledger_path),
    )
    launch_path = out / "launch.sha256"
    launch_path.write_text(
        f"{frozen.original_manifest_sha256}  {manifest_path.resolve()}\n"
        f"{frozen.execution_ledger_sha256}  {ledger_path.resolve()}\n",
        encoding="utf-8",
    )
    frozen = replace(frozen, launch_receipt_sha256=_sha(launch_path))
    provenance = root / "reports/provenance.json"
    provenance.write_text(
        json.dumps(_provenance(frozen), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    bodies = {cell.uri: _cell_body(cell, frozen) for cell in cells}
    executions = {
        cell.execution: _execution(cell, frozen) for cell in cells
    }
    inventory = {
        cell.uri: {
            "uri": cell.uri,
            "generation": str(index + 100),
            "metageneration": "1",
            "size": len(bodies[cell.uri]),
            "md5_hash": "",
            "crc32c": "",
            "etag": "",
            "time_created": "2026-08-20T04:00:00+00:00",
            "updated": "2026-08-20T04:00:00+00:00",
        }
        for index, cell in enumerate(cells)
    }
    return SyntheticRun(
        root, out, provenance, frozen, cells, executions,
        inventory, bodies, [],
    )


def _finish(run: SyntheticRun) -> dict[str, Any]:
    return finish.finish(
        run.out, run.provenance, frozen=run.frozen, root=run.root,
        execution_loader=run.execution_loader,
        inventory_loader=run.inventory_loader,
        downloader=run.downloader,
        git_source_loader=run.git_loader,
    )


def test_strict_finisher_harvests_synthetic_grid_and_is_idempotent(
    synthetic_run: SyntheticRun,
) -> None:
    result = _finish(synthetic_run)
    assert result["status"] == "completed"
    assert len(list((synthetic_run.out / "cells").glob("*.json"))) == 54
    assert len(list((synthetic_run.out / "execution-metadata").glob("*.json"))) == 54
    assert len(list((synthetic_run.out / "object-metadata").glob("*.json"))) == 54
    kinds = [event[0] for event in synthetic_run.events]
    assert kinds[:54] == ["execution"] * 54
    assert kinds[54] == "inventory"
    assert kinds[55:] == ["download"] * 54
    report = json.loads(
        (synthetic_run.out / "aggregate-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["n_slates"] == 54
    assert report["n_paired_s"] == 53
    assert report["tied_s"] == 53

    def forbidden(*_args, **_kwargs):
        raise AssertionError("completed harvest consulted cloud state")

    second = finish.finish(
        synthetic_run.out, synthetic_run.provenance,
        frozen=synthetic_run.frozen, root=synthetic_run.root,
        execution_loader=forbidden,
        inventory_loader=forbidden,
        downloader=forbidden,
        git_source_loader=forbidden,
    )
    assert second["status"] == "already-complete"


def test_nonterminal_execution_blocks_every_body_download(
    synthetic_run: SyntheticRun,
) -> None:
    name = synthetic_run.cells[-1].execution
    metadata = synthetic_run.executions[name]
    metadata["status"]["conditions"][0]["status"] = "Unknown"  # type: ignore[index]
    metadata["status"].pop("completionTime")  # type: ignore[union-attr]
    with pytest.raises(RuntimeError, match="not strict terminal success"):
        _finish(synthetic_run)
    assert not any(event[0] == "download" for event in synthetic_run.events)
    assert not (synthetic_run.out / finish.PENDING_NAME).exists()


@pytest.mark.parametrize("drift", ["missing", "extra", "metageneration"])
def test_inventory_drift_blocks_every_body_download(
    synthetic_run: SyntheticRun, drift: str,
) -> None:
    if drift == "missing":
        synthetic_run.inventory.pop(synthetic_run.cells[0].uri)
    elif drift == "extra":
        synthetic_run.inventory[synthetic_run.frozen.output_prefix + "/extra.json"] = {
            "uri": synthetic_run.frozen.output_prefix + "/extra.json",
            "generation": "999", "metageneration": "1", "size": 1,
        }
    else:
        synthetic_run.inventory[synthetic_run.cells[0].uri]["metageneration"] = "2"
    with pytest.raises(RuntimeError, match="object (inventory|metadata) differs"):
        _finish(synthetic_run)
    assert not any(event[0] == "download" for event in synthetic_run.events)
    assert not (synthetic_run.out / finish.PENDING_NAME).exists()


def test_generation_pinned_download_rejects_body_identity_drift(
    synthetic_run: SyntheticRun,
) -> None:
    cell = synthetic_run.cells[0]
    value = json.loads(synthetic_run.bodies[cell.uri])
    value["code_sha"] = "f" * 40
    synthetic_run.bodies[cell.uri] = _raw(value)
    synthetic_run.inventory[cell.uri]["size"] = len(
        synthetic_run.bodies[cell.uri]
    )
    with pytest.raises(RuntimeError, match="cell identity differs"):
        _finish(synthetic_run)
    downloads = [event for event in synthetic_run.events if event[0] == "download"]
    assert downloads == [(
        "download", cell.uri, synthetic_run.inventory[cell.uri]["generation"],
    )]
    assert not (synthetic_run.out / "aggregate-report.json").exists()
    assert not (synthetic_run.out / "finish.sha256").exists()
    assert (synthetic_run.out / finish.PENDING_NAME).is_dir()


def test_provenance_drift_stops_before_cloud_metadata(
    synthetic_run: SyntheticRun,
) -> None:
    value = json.loads(synthetic_run.provenance.read_text(encoding="utf-8"))
    value["actual_chain_sha256"] = "f" * 64
    synthetic_run.provenance.write_text(
        json.dumps(value, sort_keys=True), encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="provenance addendum differs"):
        _finish(synthetic_run)
    assert synthetic_run.events == []


def test_partial_harvest_is_never_overwritten(
    synthetic_run: SyntheticRun,
) -> None:
    (synthetic_run.out / "aggregate-report.json").write_text(
        "partial", encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="partial or immutable"):
        _finish(synthetic_run)
    assert (synthetic_run.out / "aggregate-report.json").read_text() == "partial"
    assert synthetic_run.events == []


def test_finisher_source_has_no_launch_or_cloud_mutation_path() -> None:
    source = Path(finish.__file__).read_text(encoding="utf-8")
    forbidden = (
        "jobs execute", "jobs deploy", "builds submit", "jobs cancel",
        "upload_from_string", "bigquery.Client",
    )
    assert all(token not in source for token in forbidden)
