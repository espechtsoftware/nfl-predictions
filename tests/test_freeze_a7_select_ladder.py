from __future__ import annotations

from hashlib import sha256
import importlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
freeze = importlib.import_module("freeze_a7_select_ladder")
a7 = freeze.a7
transport = freeze.transport


def _source_artifacts() -> list[dict]:
    return [{
        "panel_run_id": panel,
        "season": season,
        "week": week,
        "uri": f"gs://bucket/{panel}/{season}-{week}",
        "generation": "1",
        "sha256": "a" * 64,
        "bytes": 10,
        "candidate_rows": 80,
    } for season in (2023, 2024, 2025) for week in range(1, 19)
      for panel in a7.SOURCE_PANEL_IDS]


def _object(uri: str, generation: int, marker: str) -> dict:
    return {
        "uri": uri,
        "generation": str(generation),
        "metageneration": "1",
        "sha256": marker * 64,
        "bytes": 10 + generation,
    }


def _receipts(artifacts: list[dict]) -> tuple[dict, dict]:
    lock = sha256(json.dumps(
        artifacts, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    common = {
        "code_sha": "b" * 40,
        "image": "registry.invalid/a@sha256:" + "c" * 64,
        "protocol_sha256": a7.PROTOCOL_SHA256,
        "local_source_receipts": {
            "protocol": a7.PROTOCOL_SHA256,
            "source_report": a7.SOURCE_REPORT_SHA256,
            "baseline": a7.BASELINE_SHA256,
            "baseline_vector": a7.BASELINE_VECTOR_SHA256,
        },
        "implementation_receipts": {
            key: "d" * 64 for key in a7.IMPLEMENTATION_PATHS
        },
        "query_content_receipts": {
            "candidate_source": {
                "columns": list(a7.SOURCE_QUERY_COLUMNS),
                "rows": 270,
                "sha256": "e" * 64,
            },
            "player_source": {
                "columns": list(a7.PLAYER_QUERY_COLUMNS),
                "rows": 1,
                "sha256": "f" * 64,
            },
        },
        "frozen_choices": a7.FROZEN_CHOICES,
    }
    smoke = {**common, "mode": "real-artifact-smoke", "support": None}
    support = {
        **common,
        "mode": "support-census",
        "support": {"passes": True},
        "source_artifacts_sha256": lock,
    }
    return smoke, support


def _claim() -> dict:
    return {
        "claim": {
            "job_uid": "job-uid",
            "job_generation": "7",
            "job_spec_sha256": "1" * 64,
        },
        "object": {
            **_object(a7.JOB_CLAIM_URI, 1, "2"),
            "create_only": True,
        },
    }


def _terminals() -> tuple[dict, dict]:
    smoke = {"execution": {
        "job_uid": "job-uid",
        "prior_job_generation": "7",
        "prior_job_spec_sha256": "1" * 64,
        "job_generation": "8",
        "job_spec_sha256": "3" * 64,
    }, "support_passed": None}
    support = {"execution": {
        "job_uid": "job-uid",
        "prior_job_generation": "8",
        "prior_job_spec_sha256": "3" * 64,
        "job_generation": "9",
        "job_spec_sha256": "4" * 64,
    }, "support_passed": True}
    return smoke, support


def _patch_build_boundary(
    monkeypatch, artifacts: list[dict], terminal_calls: list[dict] | None = None,
) -> None:
    monkeypatch.setattr(a7, "validate_execution_identity", lambda *args: None)
    monkeypatch.setattr(a7, "_validate_smoke_source_identity", lambda *args: None)
    monkeypatch.setattr(freeze, "_git_archive_sha256", lambda value: "5" * 64)
    monkeypatch.setattr(
        freeze, "_git_blob",
        lambda root, code, relative: (ROOT / relative).read_bytes(),
    )
    monkeypatch.setattr(a7, "verify_local_sha256", lambda value: {
        key: digest for key, (_, digest) in value.items()
    })
    full_implementation = {
        key: "d" * 64 for key in a7.FREEZE_IMPLEMENTATION_PATHS
    }
    monkeypatch.setattr(
        a7, "_freeze_implementation_receipts", lambda: full_implementation,
    )
    source_map = {
        (row["panel_run_id"], row["season"], row["week"]): {
            **row, "source_rows": row["candidate_rows"],
        }
        for row in artifacts
    }
    monkeypatch.setattr(a7, "_source_report", lambda: ({}, source_map, {}))
    monkeypatch.setattr(a7, "_locked_source_artifacts", lambda value: artifacts)
    monkeypatch.setattr(
        a7, "_validate_preflight_receipt", lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        transport, "_validate_job_claim_receipt",
        lambda value, **kwargs: value,
    )
    def validate_terminal(value, **kwargs):
        if terminal_calls is not None:
            terminal_calls.append(kwargs)
        return value

    monkeypatch.setattr(
        transport, "_validate_preflight_terminal_receipt", validate_terminal,
    )
    monkeypatch.setattr(
        transport, "_validate_freeze_manifest",
        lambda value, **kwargs: value,
    )


def _build(
    monkeypatch, terminal_calls: list[dict] | None = None,
) -> tuple[dict, dict, dict]:
    artifacts = _source_artifacts()
    smoke, support = _receipts(artifacts)
    _patch_build_boundary(monkeypatch, artifacts, terminal_calls)
    smoke_terminal, support_terminal = _terminals()
    manifest = freeze.build_manifest(
        smoke=smoke,
        support=support,
        smoke_object=_object(a7.SMOKE_RECEIPT_URI, 2, "6"),
        support_object=_object(a7.SUPPORT_RECEIPT_URI, 4, "7"),
        smoke_terminal=smoke_terminal,
        support_terminal=support_terminal,
        smoke_terminal_object=_object(a7.SMOKE_TERMINAL_URI, 3, "8"),
        support_terminal_object=_object(a7.SUPPORT_TERMINAL_URI, 5, "9"),
        job_claim=_claim(),
        a3_logical_release_sha256="a" * 64,
        archive_sha256="5" * 64,
    )
    return manifest, smoke, support


def test_freeze_manifest_binds_terminals_claim_inventories_and_false_licenses(
    monkeypatch,
):
    terminal_calls: list[dict] = []
    manifest, _smoke, _support = _build(monkeypatch, terminal_calls)
    assert set(manifest) == transport.FREEZE_MANIFEST_KEYS
    assert manifest["status"] == "frozen-for-one-historical-look"
    assert manifest["frozen_law"] == a7.FROZEN_CHOICES
    assert manifest["operator_approvals"] == a7.OPERATOR_APPROVALS
    assert len(manifest["source_artifacts"]) == 270
    assert set(manifest["preflights"]["smoke"]) == {"science", "terminal"}
    assert manifest["job_claim"]["claim"]["job_generation"] == "7"
    assert set(manifest["prefix_inventory_sha256"]) == {
        "claimed", "smoke-complete", "support-complete",
    }
    assert manifest["code"]["archive_sha256"] == "5" * 64
    assert manifest["uses_realized_outcomes"] is False
    assert manifest["production_change_licensed"] is False
    assert manifest["production_law_scorefree_transfer_licensed"] is False
    assert manifest["prospective_shadow_licensed"] is False
    assert len(terminal_calls) == 2
    assert "prior_science_object" not in terminal_calls[0]
    assert terminal_calls[1]["prior_science_object"] == \
        manifest["preflights"]["smoke"]["science"]
    assert terminal_calls[1]["prior_terminal_object"] == \
        manifest["preflights"]["smoke"]["terminal"]


def test_freeze_manifest_refuses_unsupported_archive_drift_and_broken_chain(
    monkeypatch,
):
    manifest, smoke, support = _build(monkeypatch)
    assert manifest
    smoke_terminal, support_terminal = _terminals()
    common = {
        "smoke": smoke,
        "support": support,
        "smoke_object": _object(a7.SMOKE_RECEIPT_URI, 2, "6"),
        "support_object": _object(a7.SUPPORT_RECEIPT_URI, 4, "7"),
        "smoke_terminal": smoke_terminal,
        "support_terminal": support_terminal,
        "smoke_terminal_object": _object(a7.SMOKE_TERMINAL_URI, 3, "8"),
        "support_terminal_object": _object(
            a7.SUPPORT_TERMINAL_URI, 5, "9",
        ),
        "job_claim": _claim(),
        "a3_logical_release_sha256": "a" * 64,
        "archive_sha256": "5" * 64,
    }

    support["support"] = {"passes": False}
    with pytest.raises(RuntimeError, match="unsupported"):
        freeze.build_manifest(**common)
    support["support"] = {"passes": True}

    with pytest.raises(RuntimeError, match="archive"):
        freeze.build_manifest(**{**common, "archive_sha256": "0" * 64})

    support_terminal["execution"]["prior_job_generation"] = "99"
    with pytest.raises(RuntimeError, match="job-generation chain"):
        freeze.build_manifest(**common)


def test_identity_rejects_off_path_zero_generation_and_bad_digest():
    with pytest.raises(RuntimeError, match="identity differs"):
        freeze._identity("https://example.com/x", "1", "a" * 64, 1)
    with pytest.raises(RuntimeError, match="identity differs"):
        freeze._identity("gs://bucket/x", "0", "a" * 64, 1)
    with pytest.raises(RuntimeError, match="identity differs"):
        freeze._identity("gs://bucket/x", "1", "not-a-sha", 1)


def test_historical_runner_reopens_exact_claim_terminals_and_freeze_schema(
    monkeypatch,
):
    terminal_calls: list[dict] = []
    manifest, smoke, support = _build(monkeypatch, terminal_calls)
    smoke_terminal, support_terminal = _terminals()
    manifest_identity = _object(a7.FREEZE_MANIFEST_URI, 6, "b")
    objects = {
        a7.FREEZE_MANIFEST_URI: manifest,
        a7.JOB_CLAIM_URI: manifest["job_claim"]["claim"],
        a7.SMOKE_RECEIPT_URI: smoke,
        a7.SUPPORT_RECEIPT_URI: support,
        a7.SMOKE_TERMINAL_URI: smoke_terminal,
        a7.SUPPORT_TERMINAL_URI: support_terminal,
    }

    def download(_client, identity):
        return objects[identity["uri"]], dict(identity)

    monkeypatch.setattr(a7, "_object_identity_from_env", lambda: manifest_identity)
    monkeypatch.setattr(a7, "_download_json_object_pinned", download)
    terminal_calls.clear()
    evidence = a7._load_freeze_evidence(
        object(), code_sha="b" * 40,
        image="registry.invalid/a@sha256:" + "c" * 64,
        local_source_receipts=manifest["local_source_receipts"],
        locked_source_artifacts=_source_artifacts(),
    )
    assert set(evidence) == {
        "manifest", "manifest_object", "smoke_receipt", "smoke_object",
        "support_receipt", "support_object", "smoke_terminal_receipt",
        "smoke_terminal_object", "support_terminal_receipt",
        "support_terminal_object", "source_artifact_lock_sha256",
        "implementation_sha256",
    }
    assert len(terminal_calls) == 2
    assert "prior_science_object" not in terminal_calls[0]
    assert terminal_calls[1]["prior_science_object"] == \
        manifest["preflights"]["smoke"]["science"]
    assert terminal_calls[1]["prior_terminal_object"] == \
        manifest["preflights"]["smoke"]["terminal"]

    manifest["extra_decision"] = True
    with pytest.raises(RuntimeError, match="freeze manifest differs"):
        a7._load_freeze_evidence(
            object(), code_sha="b" * 40,
            image="registry.invalid/a@sha256:" + "c" * 64,
            local_source_receipts=manifest["local_source_receipts"],
            locked_source_artifacts=_source_artifacts(),
        )
    del manifest["extra_decision"]

    manifest["preflights"]["smoke"]["science"]["uri"] = "gs://wrong/smoke"
    with pytest.raises(RuntimeError, match="object identity differs"):
        a7._load_freeze_evidence(
            object(), code_sha="b" * 40,
            image="registry.invalid/a@sha256:" + "c" * 64,
            local_source_receipts=manifest["local_source_receipts"],
            locked_source_artifacts=_source_artifacts(),
        )
