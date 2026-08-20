from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = str(REPO / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_a7_select_ladder as finish  # noqa: E402


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def test_external_pretty_json_is_strictly_canonicalized(tmp_path: Path) -> None:
    raw = tmp_path / "gcloud.raw.json"
    output = tmp_path / "gcloud.json"
    raw.write_bytes(b'{\n  "z": [2, 1],\n  "a": {"ok": true}\n}\n')
    value = finish._canonicalize_external_json(raw, output)
    assert value == {"a": {"ok": True}, "z": [2, 1]}
    assert output.read_bytes() == _canonical(value)
    assert raw.is_file()  # the shell removes raw only after canonical success


def test_registered_baseline_vector_uses_exact_manifest_bound_source(
    tmp_path: Path,
) -> None:
    relative = Path(
        "reports/multiseed-candidate-world-runs/"
        "20260813-multiseed-candidate-world-v1/report.json"
    )
    raw = (REPO / relative).read_bytes()
    manifest = {
        "baseline_vector": {"path": str(relative), "sha256": _sha(raw)},
    }
    vector = finish._registered_baseline_vector(manifest, root=REPO)
    source = json.loads(raw)
    expected = {
        (row["season"], row["week"]): float(
            row["fixed_budget_confirmation"]["CBWU"]["selected_best"]
        )
        for row in source["result"]["slates"]
    }
    assert len(vector) == 54
    assert vector == expected
    assert vector[(2023, 1)] == 173.64000000000001
    assert math.nextafter(vector[(2023, 1)], 0.0) == 173.64

    copied = tmp_path / "baseline-vector.json"
    copied.write_bytes(raw)
    copied_manifest = {
        "baseline_vector": {
            "path": copied.name, "sha256": _sha(raw),
        },
    }
    assert finish._registered_baseline_vector(
        copied_manifest, root=tmp_path,
    ) == expected
    copied.write_bytes(raw.replace(
        b'"selected_best": 173.64000000000001',
        b'"selected_best": 173.64',
        1,
    ))
    with pytest.raises(RuntimeError, match="source bytes differ"):
        finish._registered_baseline_vector(copied_manifest, root=tmp_path)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"truncated":',
        b'{"duplicate":1,"duplicate":2}',
        b'{"not_finite":NaN}',
        b'{"overflow":1e9999}',
    ],
)
def test_external_json_poison_never_creates_retained_file(
    tmp_path: Path, raw: bytes,
) -> None:
    source = tmp_path / "gcloud.raw.json"
    output = tmp_path / "gcloud.json"
    source.write_bytes(raw)
    with pytest.raises(RuntimeError, match="strict JSON|nonfinite"):
        finish._canonicalize_external_json(source, output)
    assert not output.exists()
    assert source.read_bytes() == raw


def test_job_and_execution_contracts_reject_retained_volume_or_env_state() -> None:
    code = "a" * 40
    image = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64
    job = _job_metadata(
        generation="2", code=code, image=image, mode="real-artifact-smoke",
    )
    finish._validate_updated_job_spec(
        job, code_sha=code, image=image, mode="real-artifact-smoke",
    )
    changed = json.loads(json.dumps(job))
    task = changed["spec"]["template"]["spec"]["template"]["spec"]
    task["volumes"] = [{"name": "override", "emptyDir": {}}]
    with pytest.raises(RuntimeError, match="executable contract differs"):
        finish._validate_updated_job_spec(
            changed, code_sha=code, image=image, mode="real-artifact-smoke",
        )
    changed = json.loads(json.dumps(job))
    container = changed["spec"]["template"]["spec"]["template"]["spec"][
        "containers"
    ][0]
    container["env"][0]["valueFrom"] = {"secretKeyRef": {}}
    with pytest.raises(RuntimeError, match="environment rows differ"):
        finish._validate_updated_job_spec(
            changed, code_sha=code, image=image, mode="real-artifact-smoke",
        )


@pytest.mark.parametrize("value", [1.9, True, "01", -1])
def test_execution_counter_rejects_coercible_or_noncanonical_values(
    value: object,
) -> None:
    with pytest.raises(RuntimeError, match="execution counter"):
        finish._as_count(value)
    assert finish._as_count(1) == 1
    assert finish._as_count(0) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("parallelism", True),
        ("taskCount", 1.0),
        ("maxRetries", False),
        ("timeoutSeconds", 7200),
    ],
)
def test_updated_job_rejects_noncanonical_numeric_fields(
    field: str, value: object,
) -> None:
    code = "a" * 40
    image = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64
    job = _job_metadata(
        generation="2", code=code, image=image, mode="real-artifact-smoke",
    )
    if field in {"parallelism", "taskCount"}:
        job["spec"]["template"]["spec"][field] = value
    else:
        job["spec"]["template"]["spec"]["template"]["spec"][field] = value
    with pytest.raises(RuntimeError, match="reused job"):
        finish._validate_updated_job_spec(
            job, code_sha=code, image=image, mode="real-artifact-smoke",
        )


def _metadata(uri: str, generation: str, raw: bytes) -> dict[str, Any]:
    return {
        "uri": uri, "generation": generation, "metageneration": "1",
        "bytes": len(raw), "sha256": _sha(raw),
    }


def _job_metadata(
    *, generation: str, code: str, image: str, mode: str,
    freeze_uri: str | None = None, freeze_generation: str | None = None,
    freeze_sha256: str | None = None,
) -> dict[str, Any]:
    contract = finish._registered_execution_contract(
        mode=mode, code_sha=code, image=image,
        freeze_manifest_uri=freeze_uri,
        freeze_manifest_generation=freeze_generation,
        freeze_manifest_sha256=freeze_sha256,
    )
    return {
        "metadata": {
            "name": finish.JOB, "uid": "job-uid", "generation": int(generation),
        },
        "spec": {"template": {"spec": {
            "taskCount": contract["tasks"],
            "parallelism": contract["parallelism"],
            "template": {"spec": {
                "containers": [{
                    "image": contract["image"],
                    "command": contract["command"],
                    "args": contract["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in contract["env"].items()
                    ],
                    "resources": {"limits": contract["resources"]},
                }],
                "maxRetries": contract["max_retries"],
                "timeoutSeconds": str(contract["timeout_seconds"]),
                "serviceAccountName": contract["service_account"],
            }},
        }}},
    }


def test_historical_prepare_inline_receipt_builder_executes_positive_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = (REPO / "scripts/cloud_a7_select_ladder.sh").read_text(
        encoding="utf-8",
    )
    anchor = "from finish_a7_select_ladder import (\n    RUN_ID"
    anchor_at = launcher.index(anchor)
    start = launcher.rindex("<<'PY'\n", 0, anchor_at) + len("<<'PY'\n")
    end = launcher.index("\nPY\n", anchor_at)
    snippet = launcher[start:end]

    out = tmp_path / "prepared"
    out.mkdir()
    code = "a" * 40
    image = "registry.invalid/nfl-dfs@sha256:" + "b" * 64
    build = "build-12345678"
    freeze_generation = "7"
    freeze_sha = "c" * 64
    claim = {"claim": {"job_uid": "job-uid"}, "object": {}}
    before = _job_metadata(
        generation="8", code=code, image=image, mode="support-census",
    )
    after = _job_metadata(
        generation="9", code=code, image=image, mode="historical",
        freeze_uri=finish.FREEZE_URI,
        freeze_generation=freeze_generation, freeze_sha256=freeze_sha,
    )
    (out / "job-before.json").write_bytes(_canonical(before))
    (out / "job-after.json").write_bytes(_canonical(after))
    (out / "a3-logical-release.json").write_bytes(_canonical({"ok": True}))
    claim_path = out / "job-claim-receipt.json"
    claim_path.write_bytes(_canonical(claim))
    support = {
        "build_id": build,
        "execution": {
            "job_generation": "8",
            "job_spec_sha256": finish._job_spec_sha256(before),
        },
    }
    support_raw = _canonical(support)
    (out / "support-terminal-receipt.json").write_bytes(support_raw)
    freeze = {
        "protocol_sha256": "d" * 64,
        "preflights": {"support": {"terminal": {"sha256": _sha(support_raw)}}},
        "job_claim": claim,
        "transport_repair_sha256": {},
    }
    (out / "freeze-validation.json").write_bytes(_canonical(freeze))
    monkeypatch.setattr(sys, "argv", [
        "-", str(out), image, code, build, finish.FREEZE_URI,
        freeze_generation, freeze_sha, finish.RESULT_URI, finish.JOB,
        finish.SERVICE_ACCOUNT, str(claim_path),
    ])
    exec(compile(snippet, "<historical-prepare-inline>", "exec"), {})
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["build_id"] == build
    assert manifest["freeze_manifest_sha256"] == freeze_sha


def _artifact_rows() -> list[dict[str, Any]]:
    return [
        {
            "panel_run_id": panel,
            "season": season,
            "week": week,
            "uri": f"gs://source/{panel}/{season}-{week}.npz",
            "generation": str(1000 + index),
            "sha256": f"{index:064x}"[-64:],
            "bytes": 100 + index,
            "candidate_rows": 88,
        }
        for index, (panel, season, week) in enumerate(
            (panel, season, week)
            for season in (2023, 2024, 2025)
            for week in range(1, 19)
            for panel in finish.SOURCE_PANEL_IDS
        )
    ]


def _preflight(
    *, mode: str, code: str, image: str, protocol_sha: str,
    implementation: dict[str, str], query_receipts: dict[str, Any],
    artifacts: list[dict[str, Any]], local_sources: dict[str, str],
) -> bytes:
    count = 1 if mode == "real-artifact-smoke" else 54
    lattice = (
        [(2023, 1)] if count == 1 else [
            (season, week) for season in (2023, 2024, 2025)
            for week in range(1, 19)
        ]
    )
    slates = [{
        "season": season,
        "week": week,
        "candidate_budget": 88,
        "world_count": 50_000,
        "candidate_identities_sha256": f"{season * 100 + week:064x}"[-64:],
        "candidate_tags_sha256": f"{season * 1000 + week:064x}"[-64:],
        "combined_input_receipts": {
            "candidate_totals": {
                "dtype": "<f4", "shape": [88, 50_000],
                "sha256": f"{season * 10_000 + week:064x}"[-64:],
            },
            "player_draws": {
                "dtype": "<f4", "shape": [200, 50_000],
                "sha256": f"{season * 100_000 + week:064x}"[-64:],
            },
            "player_ids_sha256": f"{season * 1_000_000 + week:064x}"[-64:],
        },
        "scorefree_receipt_sha256": f"{season * 10 + week:064x}"[-64:],
    } for season, week in lattice]
    artifact_rows = (
        [row for row in artifacts
         if (row["season"], row["week"]) == (2023, 1)]
        if count == 1 else artifacts
    )
    return _canonical({
        "version": "a7-select-ladder-preflight-receipt-v1",
        "run_id": finish.RUN_ID,
        "protocol_id": finish.PROTOCOL_ID,
        "mode": mode,
        "code_sha": code,
        "image": image,
        "protocol_sha256": protocol_sha,
        "source_report_sha256": local_sources["source_report"],
        "baseline_sha256": _sha(b"baseline\n"),
        "baseline_vector_sha256": _sha(b"vector\n"),
        "forensic_manifest_sha256": finish.FORENSIC_MANIFEST_SHA256,
        "local_source_receipts": local_sources,
        "implementation_receipts": {
            key: implementation[key]
            for key in finish.CORE_IMPLEMENTATION_KEYS
        },
        "query_content_receipts": query_receipts,
        "frozen_choices": finish.FROZEN_CHOICES,
        "source_panels": list(finish.SOURCE_PANEL_IDS),
        "source_preflight": {
            "panel_ids": list(finish.SOURCE_PANEL_IDS),
            "slates": [
                [season, week] for season in (2023, 2024, 2025)
                for week in range(1, 19)
            ],
            "slate_count": 54, "artifact_count": 270,
        },
        "source_artifact_count": len(artifact_rows),
        "source_artifacts_sha256": _sha(json.dumps(
            artifact_rows, sort_keys=True, separators=(",", ":"),
        ).encode()),
        "slates": slates,
        "support": None if count == 1 else {
            "version": "a7-r3-support-census-v1",
            "uses_realized_outcomes": False,
            "slates": 54,
            "definition": (
                "positive-ladder-gain-events-with-at-least-3-"
                "strict-q99-exceedances"
            ),
            "minimum_aggregate_events_per_arm": 100,
            "r3_positive_gain_events_by_block": {
                "control": [20, 20, 20, 20, 20],
                "treatment": [20, 20, 20, 20, 20],
            },
            "conditions": {
                "control_r3_events_at_least_100": True,
                "treatment_r3_events_at_least_100": True,
                "control_r3_supported_in_every_block": True,
                "treatment_r3_supported_in_every_block": True,
            },
            "passes": True,
        },
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    })


def _terminal(
    *, mode: str, code: str, image: str, protocol_sha: str,
    release_sha: str, claim: dict[str, Any], science: dict[str, Any],
    before: list[dict[str, Any]], job_generation: str,
    job_spec_sha256: str, prior_job_generation: str,
    prior_job_spec_sha256: str,
) -> bytes:
    support_passed = None if mode == "real-artifact-smoke" else True
    disposition = (
        "smoke-passed" if mode == "real-artifact-smoke" else "support-passed"
    )
    contract = finish._registered_execution_contract(
        mode=mode, code_sha=code, image=image,
    )
    after_uris = list(finish._preflight_expected_uris(
        mode, include_current_terminal=True,
    ))
    return _canonical({
        "version": "a7-select-ladder-preflight-terminal-v1",
        "run_id": finish.RUN_ID,
        "protocol_id": finish.PROTOCOL_ID,
        "mode": mode,
        "code_sha": code,
        "image": image,
        "build_id": "build-12345678",
        "protocol_sha256": protocol_sha,
        "a3_logical_release_sha256": release_sha,
        "job_claim_receipt_sha256": _sha(_canonical(claim)),
        "job_claim": claim,
        "execution": {
            "name": finish.JOB + "-" + ("smoke" if support_passed is None else "support"),
            "generation": 1,
            "job": finish.JOB,
            "job_uid": "job-uid",
            "job_generation": job_generation,
            "job_spec_sha256": job_spec_sha256,
            "prior_job_generation": prior_job_generation,
            "prior_job_spec_sha256": prior_job_spec_sha256,
            "completion_time": "2026-08-20T00:00:00Z",
            "completed_condition": True,
            "counters": {
                "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
            },
            "spec_sha256": "9" * 64,
            "contract": contract,
            "contract_sha256": _sha(_canonical(contract)),
        },
        "science_object": science,
        "prefix_inventory_before_terminal": before,
        "prefix_inventory_before_terminal_sha256": finish._inventory_sha256(before),
        "expected_inventory_after_terminal_uris": after_uris,
        "expected_inventory_after_terminal_uris_sha256": (
            finish._uri_inventory_sha256(after_uris)
        ),
        "preflight_receipt_sha256": science["sha256"],
        "support_passed": support_passed,
        "disposition": disposition,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    })


@dataclass
class Synthetic:
    root: Path
    out: Path
    frozen: finish.FrozenRun
    freeze: dict[str, Any]
    objects: dict[tuple[str, str], tuple[dict[str, Any], bytes]]
    execution: dict[str, Any]
    inventory: dict[str, dict[str, Any]]
    events: list[tuple[Any, ...]]

    def object_loader(self, uri: str, generation: str):
        self.events.append(("object", uri, generation))
        return self.objects[(uri, generation)]

    def execution_loader(self, name: str):
        self.events.append(("execution", name))
        return self.execution

    def inventory_loader(self, prefix: str):
        self.events.append(("inventory", prefix))
        return self.inventory

    def git_loader(self, root: Path, code: str, relative: str) -> bytes:
        assert root == self.root
        assert code == self.frozen.code_sha
        return (root / relative).read_bytes()

    def science_replayer(self, report, freeze, query_loader, object_loader):
        self.events.append(("science", len(report["slates"])))
        assert freeze == self.freeze
        uses_realized = report["uses_realized_outcomes"] is True
        return {
            "version": "a7-strict-science-replay-v1",
            "run_id": finish.RUN_ID,
            "outcome_replayed": uses_realized,
            "baseline_reproduced": uses_realized,
            "uses_realized_outcomes": uses_realized,
            "actual_score_query_executed": uses_realized,
            "disposition": (
                "historical-null-or-inconclusive-phase-s"
                if uses_realized else "tail-artifact-risk-phase-s"
            ),
            "production_change_licensed": False,
        }


@pytest.fixture
def synthetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Synthetic:
    for env_name in finish.TRANSPORT_REPAIR_ENV.values():
        monkeypatch.delenv(env_name, raising=False)
    root = tmp_path / "repo"
    out = root / "reports/a7-select-ladder-runs" / finish.RUN_ID
    out.mkdir(parents=True)
    code = "a" * 40
    image = "registry.invalid/nfl-dfs@sha256:" + "b" * 64
    implementation: dict[str, str] = {}
    for key, relative in finish.IMPLEMENTATION_PATHS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{key}\n".encode())
        implementation[key] = _sha(path.read_bytes())
    protocol_path = root / (
        "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol.md"
    )
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.write_bytes(b"frozen protocol\n")
    protocol_sha = _sha(protocol_path.read_bytes())
    for relative, raw in (
        ("reports/source.json", b"source\n"),
        ("reports/baseline.json", b"baseline\n"),
        ("reports/baseline-vector.json", b"vector\n"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    query_receipts = {
        "candidate_source": {
            "columns": list(finish.SOURCE_QUERY_COLUMNS),
            "rows": 100, "sha256": "2" * 64,
        },
        "player_source": {
            "columns": list(finish.PLAYER_QUERY_COLUMNS),
            "rows": 100, "sha256": "3" * 64,
        },
    }
    artifacts = _artifact_rows()
    local_sources = {
        "protocol": protocol_sha,
        "source_report": _sha(b"source\n"),
        "baseline": _sha(b"baseline\n"),
        "baseline_vector": _sha(b"vector\n"),
    }
    release = {
        "version": "stack-relaxation-carve-logical-release-v1",
        "run_id": "20260819-stack-relaxation-carve-v1",
        "status": "released-for-next-historical-arm",
        "next_run_id": finish.RUN_ID,
        "strict_harvest_complete": True,
        "strict_harvest_completion_sha256": "5" * 64,
        "historical_outcome_lease_released": True,
        "operator_approved": True,
        "released_at": "2026-08-20T00:00:00+00:00",
        "production_change_licensed": False,
    }
    release_path = out / "a3-logical-release.json"
    release_path.write_bytes(_canonical(release))
    release_sha = _sha(release_path.read_bytes())
    claim_job = _job_metadata(
        generation="6", code=code, image=image, mode="real-artifact-smoke",
    )
    smoke_spec_sha = finish._job_spec_sha256(claim_job)
    support_job = _job_metadata(
        generation="8", code=code, image=image, mode="support-census",
    )
    support_spec_sha = finish._job_spec_sha256(support_job)
    claim_body = finish._job_claim_body(
        code_sha=code, image=image, protocol_sha256=protocol_sha,
        a3_logical_release_sha256=release_sha, job_uid="job-uid",
        job_generation="6", job_spec_sha256=smoke_spec_sha,
        claimed_at="2026-08-20T00:00:01+00:00",
    )
    claim_raw = _canonical(claim_body)
    claim_meta = _metadata(finish.JOB_CLAIM_URI, "10", claim_raw)
    claim = {
        "claim": claim_body,
        "object": {**claim_meta, "create_only": True},
    }
    smoke_raw = _preflight(
        mode="real-artifact-smoke", code=code, image=image,
        protocol_sha=protocol_sha, implementation=implementation,
        query_receipts=query_receipts, artifacts=artifacts,
        local_sources=local_sources,
    )
    support_raw = _preflight(
        mode="support-census", code=code, image=image,
        protocol_sha=protocol_sha, implementation=implementation,
        query_receipts=query_receipts, artifacts=artifacts,
        local_sources=local_sources,
    )
    smoke_meta = _metadata(finish.SMOKE_URI, "11", smoke_raw)
    support_meta = _metadata(finish.SUPPORT_URI, "12", support_raw)
    smoke_terminal_raw = _terminal(
        mode="real-artifact-smoke", code=code, image=image,
        protocol_sha=protocol_sha, release_sha=release_sha, claim=claim,
        science=smoke_meta, before=[
            {key: claim_meta[key] for key in (
                "uri", "generation", "metageneration", "bytes", "sha256",
            )},
            smoke_meta,
        ], job_generation="7",
        job_spec_sha256=smoke_spec_sha, prior_job_generation="6",
        prior_job_spec_sha256=smoke_spec_sha,
    )
    smoke_terminal_meta = _metadata(
        finish.SMOKE_TERMINAL_URI, "13", smoke_terminal_raw,
    )
    support_terminal_raw = _terminal(
        mode="support-census", code=code, image=image,
        protocol_sha=protocol_sha, release_sha=release_sha, claim=claim,
        science=support_meta, before=[
            {key: claim_meta[key] for key in (
                "uri", "generation", "metageneration", "bytes", "sha256",
            )},
            smoke_meta,
            smoke_terminal_meta,
            support_meta,
        ], job_generation="8",
        job_spec_sha256=support_spec_sha, prior_job_generation="7",
        prior_job_spec_sha256=smoke_spec_sha,
    )
    support_terminal_meta = _metadata(
        finish.SUPPORT_TERMINAL_URI, "14", support_terminal_raw,
    )
    freeze_value = {
        "version": "a7-select-ladder-freeze-manifest-v1",
        "run_id": finish.RUN_ID,
        "protocol_id": finish.PROTOCOL_ID,
        "status": "frozen-for-one-historical-look",
        "operator_approved": True,
        "operator_approval_basis": finish.OPERATOR_APPROVAL_BASIS,
        "operator_approvals": finish.OPERATOR_APPROVALS,
        "protocol": {
            "path": str(protocol_path.relative_to(root)),
            "sha256": protocol_sha,
        },
        "code": {"commit_sha": code, "archive_sha256": "4" * 64},
        "image": {"uri": image},
        "implementation_sha256": implementation,
        "local_source_receipts": local_sources,
        "source_report": {"path": "reports/source.json", "sha256": _sha(b"source\n")},
        "baseline": {"path": "reports/baseline.json", "sha256": _sha(b"baseline\n")},
        "baseline_vector": {
            "path": "reports/baseline-vector.json", "sha256": _sha(b"vector\n"),
        },
        "source_artifacts": artifacts,
        "source_artifact_lock_sha256": finish._source_artifact_lock(artifacts),
        "query_content_receipts": query_receipts,
        "preflights": {
            "smoke": {
                "science": smoke_meta, "terminal": smoke_terminal_meta,
            },
            "support": {
                "science": support_meta, "terminal": support_terminal_meta,
            },
        },
        "job_claim": claim,
        "prefix_inventory_sha256": {
            "claimed": finish._inventory_sha256([claim_meta]),
            "smoke-complete": finish._inventory_sha256([
                claim_meta, smoke_meta, smoke_terminal_meta,
            ]),
            "support-complete": finish._inventory_sha256([
                claim_meta, smoke_meta, smoke_terminal_meta,
                support_meta, support_terminal_meta,
            ]),
        },
        "frozen_law": finish.FROZEN_CHOICES,
        "historical_looks": 1,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    freeze_raw = _canonical(freeze_value)
    freeze_uri, freeze_generation = finish.FREEZE_URI, "15"
    freeze_sha = _sha(freeze_raw)
    objects = {
        (freeze_uri, freeze_generation): (
            _metadata(freeze_uri, freeze_generation, freeze_raw), freeze_raw,
        ),
        (finish.SMOKE_URI, "11"): (smoke_meta, smoke_raw),
        (finish.SMOKE_TERMINAL_URI, "13"): (
            smoke_terminal_meta, smoke_terminal_raw,
        ),
        (finish.SUPPORT_URI, "12"): (support_meta, support_raw),
        (finish.SUPPORT_TERMINAL_URI, "14"): (
            support_terminal_meta, support_terminal_raw,
        ),
        (finish.JOB_CLAIM_URI, "10"): (claim_meta, claim_raw),
    }
    monkeypatch.setattr(finish, "_git_archive_sha", lambda *_args: "4" * 64)
    loader_events: list[tuple[Any, ...]] = []

    def initial_loader(uri: str, generation: str):
        loader_events.append(("preflight-object", uri))
        return objects[(uri, generation)]

    validation = finish.validate_freeze_for_launch(
        freeze_manifest_uri=freeze_uri,
        freeze_manifest_generation=freeze_generation,
        freeze_manifest_sha256=freeze_sha,
        expected_code_sha=code,
        expected_image=image,
        a3_release_path=release_path,
        root=root,
        object_loader=initial_loader,
        git_source_loader=lambda repo, commit, relative: (repo / relative).read_bytes(),
    )
    (out / "freeze-validation.json").write_bytes(_canonical(validation))
    build_id = "build-12345678"
    build = {
        "id": build_id, "status": "SUCCESS",
        "substitutions": {
            "COMMIT_SHA": code,
            "_IMAGE": "registry.invalid/nfl-dfs:frozen",
        },
        "steps": finish._expected_cloud_build_steps(
            "registry.invalid/nfl-dfs:frozen"
        ),
        "options": {"machineType": "E2_HIGHCPU_8"},
        "timeout": "10800s",
        "images": ["registry.invalid/nfl-dfs:frozen"],
        "serviceAccount": finish.BUILD_SERVICE_ACCOUNT,
        "logsBucket": finish.BUILD_LOGS_BUCKET,
        "secrets": None,
        "availableSecrets": None,
        "artifacts": {"images": ["registry.invalid/nfl-dfs:frozen"]},
        "results": {"images": [{
            "name": "registry.invalid/nfl-dfs:frozen",
            "digest": image.rsplit("@", 1)[1],
        }]},
        "source": {"gitSource": {
            "url": finish.GIT_SOURCE_URL, "revision": code,
        }},
        "sourceProvenance": {"resolvedGitSource": {
            "url": finish.GIT_SOURCE_URL, "revision": code,
        }},
    }
    (out / "build-metadata.json").write_bytes(_canonical(build))
    before = support_job
    historical_job = _job_metadata(
        generation="9", code=code, image=image, mode="historical",
        freeze_uri=freeze_uri, freeze_generation=freeze_generation,
        freeze_sha256=freeze_sha,
    )
    after = historical_job
    (out / "job-before.json").write_bytes(_canonical(before))
    (out / "job-after.json").write_bytes(_canonical(after))
    frozen = finish.FrozenRun(
        run_id=finish.RUN_ID, code_sha=code, image=image, build_id=build_id,
        protocol_sha256=protocol_sha,
        freeze_manifest_uri=freeze_uri,
        freeze_manifest_generation=freeze_generation,
        freeze_manifest_sha256=freeze_sha,
        freeze_validation_sha256=_sha((out / "freeze-validation.json").read_bytes()),
        a3_logical_release_sha256=_sha(release_path.read_bytes()),
        job=finish.JOB, job_uid="job-uid", job_generation="9",
        job_spec_sha256=finish._job_spec_sha256(historical_job),
        job_claim_receipt_sha256=_sha(_canonical(claim)),
    )
    launch_manifest = {
        "version": "a7-select-ladder-launch-manifest-v1",
        "run_id": finish.RUN_ID, "code_sha": code, "image": image,
        "build_id": build_id, "protocol_sha256": protocol_sha,
        "freeze_manifest_uri": freeze_uri,
        "freeze_manifest_generation": freeze_generation,
        "freeze_manifest_sha256": freeze_sha,
        "freeze_validation_sha256": frozen.freeze_validation_sha256,
        "transport_repair_sha256": validation[
            "transport_repair_sha256"
        ],
        "a3_logical_release_sha256": frozen.a3_logical_release_sha256,
        "job_claim": claim,
        "job_claim_receipt_sha256": frozen.job_claim_receipt_sha256,
        "job": finish.JOB, "job_uid": "job-uid", "job_generation": "9",
        "job_spec_sha256": frozen.job_spec_sha256,
        "service_account": finish.SERVICE_ACCOUNT,
        "output_uri": finish.RESULT_URI,
        "tasks": 1, "parallelism": 1, "cpu": "4", "memory": "16Gi",
        "timeout_seconds": 7200, "max_retries": 0,
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "job_update_mode": "reuse-only-update-existing",
    }
    (out / "manifest.json").write_bytes(_canonical(launch_manifest))
    (out / "job-claim-receipt.json").write_bytes(_canonical(claim))
    (out / "support-terminal-receipt.json").write_bytes(support_terminal_raw)
    prepared_names = {
        "manifest.json", "build-metadata.json", "freeze-validation.json",
        "a3-logical-release.json", "job-before.json", "job-after.json",
        "job-claim-receipt.json", "support-terminal-receipt.json",
    }
    (out / "prepared.sha256").write_bytes(finish._hash_ledger(
        [out / name for name in prepared_names], base=out,
    ))
    intent = {
        "version": "a7-select-ladder-launch-intent-v1",
        "run_id": finish.RUN_ID, "job": finish.JOB,
        "output_uri": finish.RESULT_URI,
        "created_at": "2026-08-20T00:01:00+00:00",
        "execution_started": "unknown-until-ledger-created",
    }
    (out / "launch-intent.json").write_bytes(_canonical(intent))
    execution_name = finish.JOB + "-synthetic"
    (out / "executions.txt").write_text(
        f"{finish.JOB} {execution_name} {finish.RESULT_URI}\n", encoding="utf-8",
    )
    lease_body = {
        "version": "historical-outcome-active-v1",
        "run_id": finish.RUN_ID, "job": finish.JOB,
        "code_sha": code, "image": image,
        "acquired_at": "2026-08-20T00:02:00+00:00",
    }
    lease_raw = _canonical(lease_body)
    lease_meta = _metadata(finish.LEASE_URI, "14", lease_raw)
    lease_receipt = {
        "lease": lease_body,
        "object": {
            "uri": finish.LEASE_URI, "generation": "14",
            "sha256": _sha(lease_raw), "bytes": len(lease_raw),
            "create_only": True,
        },
    }
    (out / "lease-receipt.json").write_bytes(_canonical(lease_receipt))
    (out / "launch.sha256").write_bytes(finish._hash_ledger(
        [out / name for name in (
            "manifest.json", "prepared.sha256", "launch-intent.json",
            "executions.txt", "lease-receipt.json",
        )], base=out,
    ))
    actual_query_rows = [{
        "panel_run_id": finish.SOURCE_PANEL_IDS[index % 5],
        "season": 2023 + (index // 90),
        "week": (index % 18) + 1,
        "cand_ix": index,
        "players": ",".join(f"P{index}-{slot}" for slot in range(9)),
        "actual_score": float(index),
    } for index in range(270)]
    actual_query_rows.sort(key=lambda row: (
        row["panel_run_id"], row["season"], row["week"], row["cand_ix"],
        row["players"],
    ))
    result_artifacts = [{
        **row,
        "seed": list(finish.SOURCE_PANEL_IDS).index(row["panel_run_id"]),
        "metageneration": "1",
        "md5_hash": "AQIDBA==",
        "crc32c": "BQYHCA==",
    } for row in artifacts]
    embedded_replay = {
        "version": "a7-strict-science-replay-v1",
        "run_id": finish.RUN_ID,
        "outcome_replayed": True,
        "baseline_reproduced": True,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "disposition": "historical-null-or-inconclusive-phase-s",
        "production_change_licensed": False,
    }
    result = {
        "version": "a7-select-ladder-phase-s-incumbent-v1",
        "run_id": finish.RUN_ID, "code_sha": code, "image": image,
        "protocol_sha256": protocol_sha,
        "source_report_sha256": freeze_value["source_report"]["sha256"],
        "baseline_sha256": freeze_value["baseline"]["sha256"],
        "baseline_vector_sha256": freeze_value["baseline_vector"]["sha256"],
        "forensic_manifest_sha256": finish.FORENSIC_MANIFEST_SHA256,
        "local_source_receipts": local_sources,
        "source_panels": list(finish.SOURCE_PANEL_IDS),
        "source_preflight": {
            "panel_ids": list(finish.SOURCE_PANEL_IDS),
            "slates": [
                [season, week] for season in (2023, 2024, 2025)
                for week in range(1, 19)
            ],
            "slate_count": 54, "artifact_count": 270,
        },
        "selector": {
            "control_env": finish.CONTROL_ENV,
            "treatment_env": finish.TREATMENT_ENV,
            "ladder_spec": finish.LADDER_SPEC, "entry_count": 80,
        },
        "implementation_receipts": {
            key: implementation[key]
            for key in finish.CORE_IMPLEMENTATION_KEYS
        },
        "query_content_receipts": query_receipts,
        "source_artifacts": result_artifacts,
        "smoke": False, "support_census": False,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "actual_query_content_receipt": {
            **finish._records_content_receipt(
                actual_query_rows, finish.ACTUAL_QUERY_COLUMNS,
            ),
        },
        "actual_query_rows": actual_query_rows,
        "freeze_manifest_uri": freeze_uri,
        "freeze_manifest_generation": freeze_generation,
        "freeze_manifest_sha256": freeze_sha,
        "freeze_evidence": {
            "manifest": freeze_value,
            "manifest_object": _metadata(
                freeze_uri, freeze_generation, freeze_raw,
            ),
            "smoke_receipt": json.loads(smoke_raw),
            "smoke_object": smoke_meta,
            "smoke_terminal_receipt": json.loads(smoke_terminal_raw),
            "smoke_terminal_object": smoke_terminal_meta,
            "support_receipt": json.loads(support_raw),
            "support_object": support_meta,
            "support_terminal_receipt": json.loads(support_terminal_raw),
            "support_terminal_object": support_terminal_meta,
            "source_artifact_lock_sha256": freeze_value[
                "source_artifact_lock_sha256"
            ],
            "implementation_sha256": implementation,
        },
        "scorefree": {},
        "outcome": {},
        "in_image_science_replay": {
            "version": "a7-in-image-science-replay-v1",
            "image": image,
            "finisher_sha256": implementation["finisher"],
            "receipt": embedded_replay,
            "receipt_sha256": _sha(_canonical(embedded_replay)),
        },
        "slates": [
            {"season": season, "week": week}
            for season in (2023, 2024, 2025) for week in range(1, 19)
        ],
    }
    result_raw = _canonical(result)
    result_meta = _metadata(finish.RESULT_URI, "15", result_raw)
    objects[(finish.LEASE_URI, "14")] = (lease_meta, lease_raw)
    objects[(finish.RESULT_URI, "15")] = (result_meta, result_raw)
    execution = {
        "metadata": {
            "name": execution_name, "generation": 1,
            "labels": {
                "run.googleapis.com/job": finish.JOB,
                "run.googleapis.com/jobUid": "job-uid",
                "run.googleapis.com/jobGeneration": "9",
            },
        },
        "spec": {
            "parallelism": 1, "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": image, "command": ["python"],
                    "args": [
                        "scripts/run_a7_select_ladder.py",
                        "--output-uri", finish.RESULT_URI,
                        "--freeze-manifest-uri", freeze_uri,
                        "--freeze-manifest-generation", freeze_generation,
                        "--freeze-manifest-sha256", freeze_sha,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": code},
                        {"name": "ANALYSIS_IMAGE", "value": image},
                        {"name": "A7_FREEZE_MANIFEST_URI", "value": freeze_uri},
                        {"name": "A7_FREEZE_MANIFEST_GENERATION", "value": freeze_generation},
                        {"name": "A7_FREEZE_MANIFEST_SHA256", "value": freeze_sha},
                    ],
                    "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                }],
                "maxRetries": 0, "timeoutSeconds": "7200",
                "serviceAccountName": finish.SERVICE_ACCOUNT,
            }},
        },
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1, "failedCount": 0, "cancelledCount": 0,
            "retriedCount": 0, "completionTime": "2026-08-20T00:10:00Z",
        },
    }
    inventory = {finish.RESULT_URI: result_meta}
    return Synthetic(
        root=root, out=out, frozen=frozen, freeze=freeze_value,
        objects=objects, execution=execution, inventory=inventory,
        events=[],
    )


def _finish(run: Synthetic):
    return finish.finish(
        run.out, root=run.root,
        execution_loader=run.execution_loader,
        inventory_loader=run.inventory_loader,
        object_loader=run.object_loader,
        query_loader=lambda: pytest.fail("synthetic replay queried sources"),
        science_replayer=run.science_replayer,
        git_source_loader=run.git_loader,
    )


def _preflight_execution_case(
    run: Synthetic,
) -> tuple[dict[str, Any], finish.PreflightRun]:
    execution = json.loads(json.dumps(run.execution))
    execution["spec"]["template"]["spec"]["containers"][0]["args"] = [
        "scripts/run_a7_select_ladder.py", "--smoke",
        "--preflight-receipt-uri", finish.SMOKE_URI,
    ]
    execution["spec"]["template"]["spec"]["containers"][0]["env"] = [
        {"name": "CODE_SHA", "value": run.frozen.code_sha},
        {"name": "ANALYSIS_IMAGE", "value": run.frozen.image},
    ]
    preflight = finish.PreflightRun(
        mode="real-artifact-smoke", code_sha=run.frozen.code_sha,
        image=run.frozen.image, build_id=run.frozen.build_id,
        protocol_sha256=run.frozen.protocol_sha256,
        a3_logical_release_sha256=run.frozen.a3_logical_release_sha256,
        job_claim_receipt_sha256=run.frozen.job_claim_receipt_sha256,
        job_uid=run.frozen.job_uid,
        job_generation=run.frozen.job_generation,
        job_spec_sha256=run.frozen.job_spec_sha256,
        prior_job_generation="8", prior_job_spec_sha256="8" * 64,
        target_uri=finish.SMOKE_URI,
    )
    return execution, preflight


@pytest.mark.parametrize("branch", ["historical", "preflight"])
def test_execution_gates_require_exact_json_integer_fields(
    synthetic: Synthetic, branch: str,
) -> None:
    if branch == "historical":
        valid = json.loads(json.dumps(synthetic.execution))

        def validate(value: dict[str, Any]) -> None:
            finish._validate_execution(
                value,
                execution=str(value["metadata"]["name"]),
                frozen=synthetic.frozen,
            )
    else:
        valid, preflight = _preflight_execution_case(synthetic)

        def validate(value: dict[str, Any]) -> None:
            finish._validate_preflight_execution(
                value,
                execution=str(value["metadata"]["name"]),
                run=preflight,
            )

    validate(valid)
    omitted_zero = json.loads(json.dumps(valid))
    for key in ("failedCount", "cancelledCount", "retriedCount"):
        del omitted_zero["status"][key]
    validate(omitted_zero)
    for poison in (1.9, True, "01", -1):
        changed = json.loads(json.dumps(valid))
        changed["status"]["succeededCount"] = poison
        with pytest.raises(RuntimeError):
            validate(changed)
    mutations = [
        (("metadata", "generation"), True),
        (("status", "observedGeneration"), 1.0),
        (("spec", "parallelism"), True),
        (("spec", "taskCount"), 1.0),
        (("spec", "template", "spec", "maxRetries"), False),
        (("spec", "template", "spec", "timeoutSeconds"), 7200),
    ]
    for path, poison in mutations:
        changed = json.loads(json.dumps(valid))
        target: dict[str, Any] = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = poison
        with pytest.raises(RuntimeError):
            validate(changed)


def test_reused_job_generation_chain_requires_json_integers() -> None:
    code = "a" * 40
    image = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64
    before = _job_metadata(
        generation="1", code=code, image=image, mode="real-artifact-smoke",
    )
    after = _job_metadata(
        generation="2", code=code, image=image, mode="real-artifact-smoke",
    )
    frozen = finish.FrozenRun(
        run_id=finish.RUN_ID, code_sha=code, image=image, build_id="build",
        protocol_sha256="c" * 64, freeze_manifest_uri=finish.FREEZE_URI,
        freeze_manifest_generation="1", freeze_manifest_sha256="d" * 64,
        freeze_validation_sha256="e" * 64,
        a3_logical_release_sha256="f" * 64, job=finish.JOB,
        job_uid="job-uid", job_generation="2",
        job_spec_sha256=finish._job_spec_sha256(after),
    )
    finish._validate_reused_job_receipts(
        before, after, frozen, expected_before_generation="1",
        expected_before_spec_sha256=finish._job_spec_sha256(before),
    )
    for which, poison in (("before", True), ("after", 2.0)):
        changed_before = json.loads(json.dumps(before))
        changed_after = json.loads(json.dumps(after))
        selected = changed_before if which == "before" else changed_after
        selected["metadata"]["generation"] = poison
        with pytest.raises(RuntimeError, match="generation"):
            finish._validate_reused_job_receipts(
                changed_before, changed_after, frozen,
                expected_before_generation="1",
                expected_before_spec_sha256=finish._job_spec_sha256(before),
            )


def _replace_result(run: Synthetic, value: dict[str, Any]) -> None:
    raw = _canonical(value)
    metadata = _metadata(finish.RESULT_URI, "15", raw)
    run.objects[(finish.RESULT_URI, "15")] = (metadata, raw)
    run.inventory[finish.RESULT_URI] = metadata


def _write_tail_close_receipts(out: Path) -> None:
    lease = out / "lease-receipt.json"
    completion = out / "completion.txt"
    closure = out / "tail-outcome-blind-closure"
    closure.mkdir()
    (closure / "lease-receipt.json").write_bytes(lease.read_bytes())
    archive_uri = (
        "gs://nfl-predictions-503414-raw/research-governance/archive/"
        "historical-outcome-stale-20260820-123456-"
        "a7-tail-artifact-no-outcome.json"
    )
    (closure / "abandon.txt").write_text(
        "HISTORICAL_OUTCOME_LEASE_ABANDONED " + archive_uri + "\n",
        encoding="utf-8",
    )
    (out / "lease-release.txt").write_text(
        "released_at=2026-08-20T12:34:56+00:00\n"
        f"run_id={finish.RUN_ID}\n"
        f"lease_receipt_sha256={finish._sha(lease)}\n"
        f"completion_sha256={finish._sha(completion)}\n"
        "lease_action=abandoned-after-proven-no-outcome-tail-closure\n"
        f"lease_archive_uri={archive_uri}\n"
        "lease_release_intent_uri=none\n"
        "lease_release_intent_generation=none\n"
        "lease_release_intent_sha256=none\n"
        "lease_release_intent_object_sha256=none\n",
        encoding="utf-8",
    )


def _rewrite_ledger_for_current_targets(path: Path, *, base: Path) -> None:
    names = [name for _digest, name in finish._parse_checksum_ledger(path)]
    path.write_bytes(finish._hash_ledger(
        [base / name for name in names], base=base,
    ))


def _minimal_completed_preflight(tmp_path: Path) -> Path:
    out = tmp_path / "preflight"
    out.mkdir()
    prepared_names = {
        "manifest.json", "build-metadata.json", "a3-logical-release.json",
        "job-claim-receipt.json", "job-before.json", "job-after.json",
    }
    for name in prepared_names:
        (out / name).write_bytes((name + "\n").encode("utf-8"))
    (out / "prepared.sha256").write_bytes(finish._hash_ledger(
        [out / name for name in prepared_names], base=out,
    ))
    (out / "executions.txt").write_text("one execution\n", encoding="utf-8")
    (out / "launch.sha256").write_bytes(finish._hash_ledger(
        [out / "manifest.json", out / "prepared.sha256", out / "executions.txt"],
        base=out,
    ))
    finals = {
        "preflight-receipt.json", "execution.json", "object-metadata.json",
        "job-claim-metadata.json", "terminal-receipt.json",
    }
    for name in finals:
        (out / name).write_bytes((name + "\n").encode("utf-8"))
    terminal_object_sha = "f" * 64
    (out / "terminal-object-metadata.json").write_bytes(_canonical({
        "sha256": terminal_object_sha,
    }))
    (out / "completion.txt").write_text(
        f"run_id={finish.RUN_ID}\n"
        "mode=real-artifact-smoke\n"
        "disposition=smoke-passed\n"
        "strict_terminal_harvest=true\n"
        "uses_realized_outcomes=false\n"
        "actual_score_query_executed=false\n"
        "production_change_licensed=false\n"
        "production_law_scorefree_transfer_licensed=false\n"
        "prospective_shadow_licensed=false\n"
        f"terminal_receipt_sha256={finish._sha(out / 'terminal-receipt.json')}\n"
        f"preflight_receipt_sha256={finish._sha(out / 'preflight-receipt.json')}\n"
        f"terminal_object_sha256={terminal_object_sha}\n",
        encoding="utf-8",
    )
    finish_names = {
        "manifest.json", "prepared.sha256", "launch.sha256", "executions.txt",
        *finals, "terminal-object-metadata.json", "completion.txt",
    }
    (out / "finish.sha256").write_bytes(finish._hash_ledger(
        [out / name for name in finish_names], base=out,
    ))
    finish._validate_preflight_complete(out, mode="real-artifact-smoke")
    return out


def test_strict_finisher_is_body_blind_until_terminal_inventory_and_freeze(
    synthetic: Synthetic,
) -> None:
    result = _finish(synthetic)
    assert result["status"] == "completed"
    kinds = [event[0] for event in synthetic.events]
    assert kinds[:2] == ["execution", "inventory"]
    result_position = synthetic.events.index(("object", finish.RESULT_URI, "15"))
    assert all(event[1] != finish.RESULT_URI for event in synthetic.events[2:result_position])
    assert kinds[result_position + 1] == "science"
    assert (synthetic.out / "finish.sha256").is_file()
    completion = (synthetic.out / "completion.txt").read_text(encoding="utf-8")
    assert "historical_outcome_lease_release_licensed=true" in completion
    assert "uses_realized_outcomes=true" in completion


def test_historical_restart_revalidates_nested_prepared_target(
    synthetic: Synthetic,
) -> None:
    _finish(synthetic)
    (synthetic.out / "build-metadata.json").write_bytes(b"changed\n")
    with pytest.raises(RuntimeError, match="completed artifact differs"):
        finish._validate_complete(synthetic.out)


def test_historical_restart_revalidates_nested_launch_target(
    synthetic: Synthetic,
) -> None:
    _finish(synthetic)
    (synthetic.out / "launch-intent.json").write_bytes(b"changed\n")
    _rewrite_ledger_for_current_targets(
        synthetic.out / "finish.sha256", base=synthetic.out,
    )
    with pytest.raises(RuntimeError, match="completed artifact differs"):
        finish._validate_complete(synthetic.out)


def test_preflight_restart_revalidates_nested_prepared_target(
    tmp_path: Path,
) -> None:
    out = _minimal_completed_preflight(tmp_path)
    (out / "build-metadata.json").write_bytes(b"changed\n")
    with pytest.raises(RuntimeError, match="completed artifact differs"):
        finish._validate_preflight_complete(out, mode="real-artifact-smoke")


def test_preflight_restart_revalidates_nested_launch_target(
    tmp_path: Path,
) -> None:
    out = _minimal_completed_preflight(tmp_path)
    (out / "executions.txt").write_bytes(b"changed\n")
    _rewrite_ledger_for_current_targets(out / "finish.sha256", base=out)
    with pytest.raises(RuntimeError, match="completed artifact differs"):
        finish._validate_preflight_complete(out, mode="real-artifact-smoke")


def test_realized_release_intent_is_create_once_and_restart_idempotent(
    synthetic: Synthetic,
) -> None:
    _finish(synthetic)
    events: list[tuple[object, ...]] = []

    def creator(uri: str, raw: bytes):
        events.append(("create", uri, _sha(raw)))
        metadata = _metadata(uri, "21", raw)
        synthetic.objects[(uri, "21")] = (metadata, raw)
        return metadata, raw

    def closer(intent: dict[str, Any], lease_raw: bytes) -> str:
        events.append(("delete", intent["lease_generation"], _sha(lease_raw)))
        assert intent["lease_sha256"] == _sha(lease_raw)
        return "deleted-registered-generation"

    first = finish.close_realized_lease(
        synthetic.out, object_creator=creator,
        object_loader=synthetic.object_loader, lease_closer=closer,
    )
    assert first["status"] == "already-closed"
    assert [event[0] for event in events] == ["create", "delete"]
    assert (synthetic.out / "lease-release-intent.json").is_file()
    assert (synthetic.out / "lease-release-intent-object.json").is_file()
    release = (synthetic.out / "lease-release.txt").read_text(encoding="utf-8")
    assert f"lease_release_intent_uri={finish.RELEASE_INTENT_URI}" in release

    events.clear()
    second = finish.close_realized_lease(
        synthetic.out,
        object_creator=lambda *_args: pytest.fail("recreated release intent"),
        object_loader=synthetic.object_loader,
        lease_closer=lambda *_args: pytest.fail("redeleted released lease"),
    )
    assert second == first
    assert events == []


def test_realized_release_rejects_changed_remote_tombstone(
    synthetic: Synthetic,
) -> None:
    _finish(synthetic)

    def creator(uri: str, raw: bytes):
        metadata = _metadata(uri, "21", raw)
        synthetic.objects[(uri, "21")] = (metadata, raw)
        return metadata, raw

    finish.close_realized_lease(
        synthetic.out, object_creator=creator,
        object_loader=synthetic.object_loader,
        lease_closer=lambda *_args: "already-absent-after-durable-intent",
    )
    metadata, raw = synthetic.objects[(finish.RELEASE_INTENT_URI, "21")]
    changed = raw + b" "
    synthetic.objects[(finish.RELEASE_INTENT_URI, "21")] = (
        {**metadata, "bytes": len(changed), "sha256": _sha(changed)}, changed,
    )
    with pytest.raises(RuntimeError, match="lease-release intent"):
        finish._validate_closed(
            synthetic.out, object_loader=synthetic.object_loader,
        )


def test_tail_artifact_closure_is_strictly_harvested_without_outcomes(
    synthetic: Synthetic,
) -> None:
    _, raw = synthetic.objects[(finish.RESULT_URI, "15")]
    report = json.loads(raw)
    report["uses_realized_outcomes"] = False
    report["actual_score_query_executed"] = False
    report["production_law_scorefree_transfer_licensed"] = False
    report["disposition"] = "tail-artifact-risk-phase-s"
    report.pop("actual_query_content_receipt")
    report.pop("actual_query_rows")
    report.pop("outcome")
    tail_replay = {
        "version": "a7-strict-science-replay-v1",
        "run_id": finish.RUN_ID,
        "outcome_replayed": False,
        "baseline_reproduced": False,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "disposition": "tail-artifact-risk-phase-s",
        "production_change_licensed": False,
    }
    report["in_image_science_replay"]["receipt"] = tail_replay
    report["in_image_science_replay"]["receipt_sha256"] = _sha(
        _canonical(tail_replay)
    )
    _replace_result(synthetic, report)

    result = _finish(synthetic)
    assert result["status"] == "completed"
    assert result["disposition"] == "tail-artifact-risk-phase-s"
    completion = (synthetic.out / "completion.txt").read_text(encoding="utf-8")
    assert "uses_realized_outcomes=false" in completion
    assert "actual_score_query_executed=false" in completion
    assert "historical_outcome_lease_release_licensed=true" in completion
    synthetic.events.clear()
    assert _finish(synthetic)["status"] == "already-complete"
    assert synthetic.events == []
    _write_tail_close_receipts(synthetic.out)
    first = finish._validate_closed(synthetic.out)
    second = finish._validate_closed(synthetic.out)
    assert first == second
    assert first["status"] == "already-closed"
    assert (synthetic.out / "lease-receipt.json").is_file()


def test_outcome_blind_result_without_tail_disposition_fails_before_replay(
    synthetic: Synthetic,
) -> None:
    _, raw = synthetic.objects[(finish.RESULT_URI, "15")]
    report = json.loads(raw)
    report["uses_realized_outcomes"] = False
    report["actual_score_query_executed"] = False
    _replace_result(synthetic, report)
    with pytest.raises(RuntimeError, match="result field population differs"):
        _finish(synthetic)
    assert not any(event[0] == "science" for event in synthetic.events)


def test_result_rejects_unknown_outcome_field_before_replay(
    synthetic: Synthetic,
) -> None:
    _, raw = synthetic.objects[(finish.RESULT_URI, "15")]
    report = json.loads(raw)
    report["actual_scores_backup"] = [1.0]
    _replace_result(synthetic, report)
    with pytest.raises(RuntimeError, match="result field population differs"):
        _finish(synthetic)
    assert not any(event[0] == "science" for event in synthetic.events)


def test_in_image_replay_requires_exact_schema_hash_and_local_equality(
    synthetic: Synthetic,
) -> None:
    _, raw = synthetic.objects[(finish.RESULT_URI, "15")]
    report = json.loads(raw)
    report["in_image_science_replay"]["receipt_sha256"] = "0" * 64
    _replace_result(synthetic, report)
    with pytest.raises(RuntimeError, match="in-image science replay receipt differs"):
        _finish(synthetic)

    report = json.loads(raw)
    embedded = report["in_image_science_replay"]["receipt"]
    embedded["disposition"] = "historical-positive-phase-s"
    report["in_image_science_replay"]["receipt_sha256"] = _sha(
        _canonical(embedded)
    )
    _replace_result(synthetic, report)
    with pytest.raises(RuntimeError, match="local/in-image science replay differs"):
        _finish(synthetic)


def test_tail_slate_and_arm_exact_key_sets_reject_hidden_outcomes() -> None:
    slate = {key: None for key in finish.RESULT_SLATE_COMMON_KEYS}
    slate["actual_scores_backup"] = [1.0]
    with pytest.raises(RuntimeError, match="slate field population differs"):
        finish._validate_result_slate_fields(
            slate, uses_realized_outcomes=False,
        )
    row = {"control": {
        key: None for key in finish.RESULT_ARM_COMMON_KEYS
    }}
    row["control"]["actual_scores_backup"] = [1.0]
    with pytest.raises(RuntimeError, match="control arm receipt differs"):
        finish._validate_arm_receipt(
            row=row, arm="control", identities=[], tags=[], selected=[],
            actual_values=None,
        )


def test_completed_finisher_is_idempotent_without_cloud_reads(
    synthetic: Synthetic,
) -> None:
    _finish(synthetic)
    synthetic.events.clear()
    result = _finish(synthetic)
    assert result["status"] == "already-complete"
    assert synthetic.events == []


def test_terminal_failure_closure_is_exact_idempotent_and_forbids_retry(
    synthetic: Synthetic,
) -> None:
    execution = json.loads(json.dumps(synthetic.execution))
    execution["status"]["conditions"][0]["status"] = "False"
    execution_name = execution["metadata"]["name"]
    closure = synthetic.out / f"failed-terminal-{execution_name}"
    closure.mkdir()
    execution_raw = _canonical(execution)
    (closure / "execution.json").write_bytes(execution_raw)
    lease = synthetic.out / "lease-receipt.json"
    lease.rename(closure / "lease-receipt.json")
    archive_uri = (
        "gs://nfl-predictions-503414-raw/research-governance/archive/"
        "historical-outcome-stale-20260820-123456-a7-terminal-failed.json"
    )
    (closure / "abandon.txt").write_text(
        "HISTORICAL_OUTCOME_LEASE_ABANDONED " + archive_uri + "\n",
        encoding="utf-8",
    )
    value = {
        "version": "a7-watcher-failure-closure-v1",
        "run_id": finish.RUN_ID,
        "reason": "a7-terminal-failed",
        "disposition": "closed-terminal-failed-no-retry",
        "execution": execution_name,
        "execution_sha256": _sha(execution_raw),
        "lease_receipt_sha256": finish._sha(closure / "lease-receipt.json"),
        "lease_archive_uri": archive_uri,
        "possible_historical_outcome_access": True,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    raw = _canonical(value)
    (closure / "failure-closure.json").write_bytes(raw)
    (closure / "failure-closure.sha256").write_text(
        f"{_sha(raw)}  failure-closure.json\n", encoding="utf-8",
    )
    first = finish._validate_failure_closure(synthetic.out)
    second = finish._validate_failure_closure(synthetic.out)
    assert first == second == {
        "status": "closed-no-retry", "run_id": finish.RUN_ID,
        "disposition": "closed-terminal-failed-no-retry",
        "possible_historical_outcome_access": True,
    }
    for mutation, expected in (
        ("missing", "fields differ"),
        ("true", "identity differs"),
        ("extra", "fields differ"),
    ):
        changed = json.loads(json.dumps(value))
        if mutation == "missing":
            changed.pop("production_law_scorefree_transfer_licensed")
        elif mutation == "true":
            changed["production_law_scorefree_transfer_licensed"] = True
        else:
            changed["transfer_authority"] = False
        changed_raw = _canonical(changed)
        (closure / "failure-closure.json").write_bytes(changed_raw)
        (closure / "failure-closure.sha256").write_text(
            f"{_sha(changed_raw)}  failure-closure.json\n", encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match=expected):
            finish._validate_failure_closure(synthetic.out)
    (closure / "failure-closure.json").write_bytes(raw)
    (closure / "failure-closure.sha256").write_text(
        f"{_sha(raw)}  failure-closure.json\n", encoding="utf-8",
    )
    assert not lease.exists()


def test_nonterminal_execution_blocks_every_object_body(synthetic: Synthetic) -> None:
    synthetic.execution["status"]["conditions"][0]["status"] = "Unknown"
    with pytest.raises(RuntimeError, match="not strict terminal success"):
        _finish(synthetic)
    assert [event[0] for event in synthetic.events] == ["execution"]


def test_exact_result_inventory_blocks_extra_object_before_body(
    synthetic: Synthetic,
) -> None:
    synthetic.inventory[finish.RESULT_URI + ".extra"] = {
        "uri": finish.RESULT_URI + ".extra", "generation": "16",
        "metageneration": "1", "bytes": 1,
    }
    with pytest.raises(RuntimeError, match="object inventory differs"):
        _finish(synthetic)
    assert [event[0] for event in synthetic.events] == ["execution", "inventory"]


def test_freeze_drift_blocks_result_body_and_science(synthetic: Synthetic) -> None:
    key = (synthetic.frozen.freeze_manifest_uri,
           synthetic.frozen.freeze_manifest_generation)
    metadata, raw = synthetic.objects[key]
    changed = raw + b" "
    synthetic.objects[key] = ({**metadata, "bytes": len(changed),
                               "sha256": _sha(changed)}, changed)
    with pytest.raises(RuntimeError, match="freeze manifest changed"):
        _finish(synthetic)
    assert not any(
        event[:2] == ("object", finish.RESULT_URI) for event in synthetic.events
    )
    assert not any(event[0] == "science" for event in synthetic.events)


def test_science_replay_failure_never_writes_completion(synthetic: Synthetic) -> None:
    def fail(*_args):
        raise RuntimeError("independent replay mismatch")

    with pytest.raises(RuntimeError, match="independent replay mismatch"):
        finish.finish(
            synthetic.out, root=synthetic.root,
            execution_loader=synthetic.execution_loader,
            inventory_loader=synthetic.inventory_loader,
            object_loader=synthetic.object_loader,
            query_loader=lambda: (None, None), science_replayer=fail,
            git_source_loader=synthetic.git_loader,
        )
    assert not (synthetic.out / "completion.txt").exists()
    assert not (synthetic.out / "finish.sha256").exists()


def test_finisher_has_no_actual_score_query_or_cloud_mutation_surface() -> None:
    source = Path(finish.__file__).read_text(encoding="utf-8")
    forbidden = (
        "_actual_sql", "replay_candidates_staging", "jobs execute",
        "jobs update", "jobs deploy", "jobs cancel",
    )
    assert all(token not in source for token in forbidden)
    assert "SOURCE_SQL" in source and "PLAYER_SQL" in source
    assert "select_books(totals)" in source
    assert "scorefree_book_receipt(" in source
    assert "aggregate_outcomes(" in source
    assert "if_generation_match=0" in source


def test_freeze_manifest_requires_all_operator_approvals(
    synthetic: Synthetic,
) -> None:
    value = json.loads(json.dumps(synthetic.freeze))
    value["operator_approvals"]["s80_co_primary_intersection"] = False
    with pytest.raises(RuntimeError, match="operator approvals differ"):
        finish._validate_freeze_manifest(
            value, expected_code_sha=synthetic.frozen.code_sha,
            expected_image=synthetic.frozen.image, root=synthetic.root,
            git_source_loader=synthetic.git_loader,
        )


@pytest.mark.parametrize(
    "extra_key,extra_value",
    [
        ("historical_outcome", {"mean_delta": 1.0}),
        ("outcome", {"mean_delta": 1.0}),
    ],
)
def test_freeze_manifest_rejects_extra_decision_or_science_fields(
    synthetic: Synthetic, extra_key: str, extra_value: object,
) -> None:
    value = json.loads(json.dumps(synthetic.freeze))
    value[extra_key] = extra_value
    with pytest.raises(RuntimeError, match="freeze-manifest fields differ"):
        finish._validate_freeze_manifest(
            value, expected_code_sha=synthetic.frozen.code_sha,
            expected_image=synthetic.frozen.image, root=synthetic.root,
            git_source_loader=synthetic.git_loader,
        )


def test_terminal_inventory_and_build_are_bound_to_known_phase_objects(
    synthetic: Synthetic,
) -> None:
    support = synthetic.freeze["preflights"]["support"]["terminal"]
    raw = synthetic.objects[(support["uri"], support["generation"])][1]
    value = json.loads(raw)
    kwargs = {
        "mode": "support-census",
        "science_object": synthetic.freeze["preflights"]["support"]["science"],
        "claim": synthetic.freeze["job_claim"],
        "code_sha": synthetic.frozen.code_sha,
        "image": synthetic.frozen.image,
        "protocol_sha256": synthetic.frozen.protocol_sha256,
        "a3_logical_release_sha256": synthetic.frozen.a3_logical_release_sha256,
        "build_id": synthetic.frozen.build_id,
        "prior_science_object": synthetic.freeze["preflights"]["smoke"]["science"],
        "prior_terminal_object": synthetic.freeze["preflights"]["smoke"]["terminal"],
    }
    finish._validate_preflight_terminal_receipt(value, **kwargs)
    changed = json.loads(json.dumps(value))
    changed["prefix_inventory_before_terminal"][0]["bytes"] += 1
    changed["prefix_inventory_before_terminal_sha256"] = finish._inventory_sha256(
        changed["prefix_inventory_before_terminal"]
    )
    with pytest.raises(RuntimeError, match="not bound to known objects"):
        finish._validate_preflight_terminal_receipt(changed, **kwargs)
    changed = json.loads(json.dumps(value))
    changed["build_id"] = "other-successful-build"
    with pytest.raises(RuntimeError, match="build identity differs"):
        finish._validate_preflight_terminal_receipt(changed, **kwargs)


@pytest.mark.parametrize("mode", ["real-artifact-smoke", "support-census"])
def test_final_preflight_inventory_replays_all_generation_pinned_sha_bytes(
    synthetic: Synthetic, mode: str,
) -> None:
    uris = finish._preflight_expected_uris(
        mode, include_current_terminal=True,
    )
    pinned: dict[str, tuple[dict[str, Any], bytes]] = {}
    receipts = []
    inventory: dict[str, dict[str, Any]] = {}
    for uri in uris:
        matches = [
            (metadata, raw)
            for (candidate, _generation), (metadata, raw) in synthetic.objects.items()
            if candidate == uri
        ]
        assert len(matches) == 1
        metadata, raw = matches[0]
        receipt = {**metadata, "sha256": _sha(raw)}
        pinned[uri] = (metadata, raw)
        receipts.append(receipt)
        inventory[uri] = {
            key: receipt[key]
            for key in ("uri", "generation", "metageneration", "bytes")
        }
    finish._validate_final_preflight_inventory(inventory, receipts, pinned)
    changed = json.loads(json.dumps(receipts))
    changed[-1]["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="final preflight pinned object changed"):
        finish._validate_final_preflight_inventory(inventory, changed, pinned)


def test_build_gate_binds_exact_committed_step_contract(synthetic: Synthetic) -> None:
    build_path = synthetic.out / "build-metadata.json"
    value = json.loads(build_path.read_bytes())
    finish._validate_build_metadata(
        value, build_id=synthetic.frozen.build_id,
        image=synthetic.frozen.image, code_sha=synthetic.frozen.code_sha,
    )
    value["steps"][0]["args"][1] = "PYTHONPATH=. pytest -q"
    with pytest.raises(RuntimeError, match="build/test/image gate differs"):
        finish._validate_build_metadata(
            value, build_id=synthetic.frozen.build_id,
            image=synthetic.frozen.image, code_sha=synthetic.frozen.code_sha,
        )
    value = json.loads(build_path.read_bytes())
    value["steps"][0]["allowExitCodes"] = [1]
    with pytest.raises(RuntimeError, match="build/test/image gate differs"):
        finish._validate_build_metadata(
            value, build_id=synthetic.frozen.build_id,
            image=synthetic.frozen.image, code_sha=synthetic.frozen.code_sha,
        )
    value = json.loads(build_path.read_bytes())
    value["options"]["env"] = ["PYTEST_ADDOPTS=--collect-only"]
    with pytest.raises(RuntimeError, match="build/test/image gate differs"):
        finish._validate_build_metadata(
            value, build_id=synthetic.frozen.build_id,
            image=synthetic.frozen.image, code_sha=synthetic.frozen.code_sha,
        )
    value = json.loads(build_path.read_bytes())
    value["availableSecrets"] = {"secretManager": [{"env": "PYTEST_ADDOPTS"}]}
    with pytest.raises(RuntimeError, match="build/test/image gate differs"):
        finish._validate_build_metadata(
            value, build_id=synthetic.frozen.build_id,
            image=synthetic.frozen.image, code_sha=synthetic.frozen.code_sha,
        )
    value = json.loads(build_path.read_bytes())
    value["source"]["gitSource"]["revision"] = "b" * 40
    with pytest.raises(RuntimeError, match="resolved Git source differs"):
        finish._validate_build_metadata(
            value, build_id=synthetic.frozen.build_id,
            image=synthetic.frozen.image, code_sha=synthetic.frozen.code_sha,
        )


def test_live_artifact_storage_checksums_are_exactly_bound() -> None:
    row = {
        "panel_run_id": "panel", "season": 2023, "week": 1,
        "uri": "gs://source/object", "generation": "1",
        "metageneration": "1", "sha256": "a" * 64, "bytes": 1,
        "candidate_rows": 88, "seed": 0, "md5_hash": "YWJjZA==",
        "crc32c": "ZWZnaA==",
    }
    finish._validate_live_artifact_result_receipts([row], [row])
    changed = {**row, "md5_hash": "aW52YWxpZA=="}
    with pytest.raises(RuntimeError, match="live source-artifact receipts differ"):
        finish._validate_live_artifact_result_receipts([changed], [row])


@pytest.mark.parametrize(
    "field,value",
    [
        ("production_law_scorefree_transfer_licensed", True),
        ("outcome", {"disposition": "historical-positive-phase-s"}),
        ("production_change_licensed", True),
        ("prospective_shadow_licensed", True),
    ],
)
def test_preflight_rejects_extra_or_licensed_fields(
    synthetic: Synthetic, field: str, value: object,
) -> None:
    smoke = synthetic.freeze["preflights"]["smoke"]["science"]
    raw = synthetic.objects[(smoke["uri"], smoke["generation"])][1]
    receipt = json.loads(raw)
    receipt[field] = value
    # Existing fields must stay literal false; unknown decision/science fields
    # are rejected by the exact compact-receipt key set.
    if field in {
        "production_change_licensed", "production_law_scorefree_transfer_licensed",
        "prospective_shadow_licensed",
    }:
        expected = "preflight identity differs"
    else:
        expected = "preflight fields differ"
    with pytest.raises(RuntimeError, match=expected):
        finish._validate_preflight_receipt(
            _canonical(receipt), mode="real-artifact-smoke",
            manifest=synthetic.freeze,
        )


def test_support_preflight_rejects_nested_hidden_science(
    synthetic: Synthetic,
) -> None:
    support = synthetic.freeze["preflights"]["support"]["science"]
    raw = synthetic.objects[(support["uri"], support["generation"])][1]
    receipt = json.loads(raw)
    receipt["support"]["historical_outcome_summary"] = {"max80_delta": 1.0}
    with pytest.raises(RuntimeError, match="support preflight did not pass"):
        finish._validate_preflight_receipt(
            _canonical(receipt), mode="support-census",
            manifest=synthetic.freeze,
        )


def test_freeze_reference_and_preflight_uris_are_exact(
    synthetic: Synthetic,
) -> None:
    with pytest.raises(RuntimeError, match="freeze-manifest reference differs"):
        finish.validate_freeze_for_launch(
            freeze_manifest_uri=finish.FREEZE_URI + ".copy",
            freeze_manifest_generation=synthetic.frozen.freeze_manifest_generation,
            freeze_manifest_sha256=synthetic.frozen.freeze_manifest_sha256,
            expected_code_sha=synthetic.frozen.code_sha,
            expected_image=synthetic.frozen.image,
            a3_release_path=synthetic.out / "a3-logical-release.json",
            root=synthetic.root,
            object_loader=lambda *_args: pytest.fail("opened wrong freeze URI"),
            git_source_loader=synthetic.git_loader,
        )
    value = json.loads(json.dumps(synthetic.freeze))
    value["preflights"]["smoke"]["science"]["uri"] = finish.SMOKE_URI + ".copy"
    with pytest.raises(RuntimeError, match="smoke preflight object identity differs"):
        finish._validate_freeze_manifest(
            value, expected_code_sha=synthetic.frozen.code_sha,
            expected_image=synthetic.frozen.image, root=synthetic.root,
            git_source_loader=synthetic.git_loader,
        )


def test_finisher_repair_override_is_exact_current_and_receipted(
    synthetic: Synthetic, monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = finish.IMPLEMENTATION_PATHS["finisher"]
    path = synthetic.root / relative
    frozen_raw = path.read_bytes()
    path.write_bytes(b"documented finisher repair\n")
    current_sha = _sha(path.read_bytes())

    def committed(repo: Path, code_sha: str, requested: str) -> bytes:
        assert repo == synthetic.root
        assert code_sha == synthetic.frozen.code_sha
        return frozen_raw if requested == relative else (repo / requested).read_bytes()

    monkeypatch.setenv("A7_FINISHER_REPAIR_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="frozen local source differs"):
        finish._validate_implementation_sources(
            synthetic.freeze["implementation_sha256"],
            code_sha=synthetic.frozen.code_sha, root=synthetic.root,
            git_source_loader=committed,
        )
    monkeypatch.setenv("A7_FINISHER_REPAIR_SHA256", current_sha)
    assert finish._validate_implementation_sources(
        synthetic.freeze["implementation_sha256"],
        code_sha=synthetic.frozen.code_sha, root=synthetic.root,
        git_source_loader=committed,
    ) == {"finisher": current_sha}


def test_aligned_candidate_scores_recompute_pool_and_fail_closed() -> None:
    identities = [
        [f"A{row}-{slot}" for slot in range(9)] for row in range(3)
    ]
    values, pool = finish._candidate_actual_map(
        [101.5, 99.0, 117.25], identities, retained_pool_c=117.25,
    )
    assert pool == 117.25
    assert values[tuple(sorted(identities[2]))] == 117.25
    with pytest.raises(RuntimeError, match="vector differs"):
        finish._candidate_actual_map(
            [101.5, 99.0], identities, retained_pool_c=101.5,
        )
    with pytest.raises(RuntimeError, match="pool C differs"):
        finish._candidate_actual_map(
            [101.5, 99.0, 117.25], identities, retained_pool_c=117.0,
        )
    with pytest.raises(RuntimeError, match="not finite"):
        finish._candidate_actual_map(
            [101.5, float("nan"), 117.25], identities,
            retained_pool_c=117.25,
        )
    expected = {
        tuple(sorted(identity)): score
        for identity, score in zip(
            identities, [101.5, 99.0, 117.25], strict=True,
        )
    }
    with pytest.raises(RuntimeError, match="aligned candidate scores differ"):
        finish._candidate_actual_map(
            [99.0, 101.5, 117.25], identities, retained_pool_c=117.25,
            expected_native=expected,
        )


def test_native_actual_query_rows_bind_duplicate_source_keys_and_scores() -> None:
    players = ",".join(f"P{slot}" for slot in range(9))
    source_rows = [{
        "panel_run_id": panel, "season": 2023, "week": 1,
        "cand_ix": index, "players": players,
    } for index, panel in enumerate(("panel-a", "panel-b"))]

    class Frame:
        def to_dict(self, mode: str):
            assert mode == "records"
            return source_rows

    retained = [
        {**row, "actual_score": 123.5} for row in source_rows
    ]
    receipt = finish._records_content_receipt(
        retained, finish.ACTUAL_QUERY_COLUMNS,
    )
    grouped, rebuilt = finish._validate_retained_actual_query(
        Frame(), retained, receipt,
    )
    assert rebuilt == receipt
    assert grouped[(2023, 1)][tuple(f"P{slot}" for slot in range(9))] == 123.5

    changed = json.loads(json.dumps(retained))
    changed[1]["actual_score"] = 123.0
    changed_receipt = finish._records_content_receipt(
        changed, finish.ACTUAL_QUERY_COLUMNS,
    )
    with pytest.raises(RuntimeError, match="duplicate native outcomes disagree"):
        finish._validate_retained_actual_query(
            Frame(), changed, changed_receipt,
        )
    with pytest.raises(RuntimeError, match="content receipt differs"):
        finish._validate_retained_actual_query(
            Frame(), retained, {**receipt, "sha256": "0" * 64},
        )
    with pytest.raises(RuntimeError, match="canonical order differs"):
        finish._validate_retained_actual_query(
            Frame(), list(reversed(retained)), receipt,
        )
