from __future__ import annotations

import ast
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_a2a_rank_factor_split_census as runner  # noqa: E402


def _artifact_rows() -> list[dict]:
    rows = []
    for index, (season, week, seed) in enumerate(runner._expected_grid()):
        uri = f"gs://synthetic/worlds/{season}-{week}-{seed}.npz"
        rows.append({
            "bytes": 100 + index,
            "candidate_rows": 80,
            "generation": str(1_000 + index),
            "panel_run_id": runner.SOURCE_PANELS[seed],
            "season": season,
            "seed": seed,
            "sha256": sha256(uri.encode()).hexdigest(),
            "updated": "2026-08-20T00:00:00+00:00",
            "uri": uri,
            "week": week,
        })
    return rows


def _gate(*, mechanical: bool, directional: bool) -> dict:
    passed = mechanical and directional
    if not mechanical:
        disposition = "a2a-scorefree-invalid"
        licenses = runner._licenses()
    elif not directional:
        disposition = "a2a-scorefree-mechanism-fails"
        licenses = runner._licenses()
    else:
        disposition = "a2a-scorefree-mechanism-passes"
        licenses = runner._licenses(historical_remeasurement=True)
    return {
        "passes": passed,
        "mechanical_invariants_pass": mechanical,
        "directional_conditions_pass": directional,
        "conditions": {"synthetic": directional},
        "disposition": disposition,
        "licenses": licenses,
        "aggregate": {"synthetic": True},
        "block_directions": {block: {} for block in runner.BLOCKS},
    }


def _catalog_for_grid() -> list[dict]:
    return [{
        "season": season,
        "week": week,
        "player_id": f"p-{season}-{week}",
        "position": "QB",
        "team": "AAA",
        "mean_projection": 20.0,
    } for season in runner.SEASONS for week in runner.WEEKS]


def _mock_run_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    aggregate_gate: dict | None = None,
) -> tuple[str, list[tuple[int, int, int]], list[bytes]]:
    protocol = tmp_path / "protocol.md"
    protocol.write_text("frozen synthetic protocol\n", encoding="utf-8")
    monkeypatch.setattr(runner, "PROTOCOL", protocol)
    monkeypatch.setattr(runner, "PROTOCOL_SHA256", sha256(
        protocol.read_bytes()
    ).hexdigest())
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setenv(
        "ANALYSIS_IMAGE", "registry.example/a2a@sha256:" + "b" * 64,
    )
    fake_gcs = object()
    monkeypatch.setattr(runner.storage, "Client", lambda project: fake_gcs)
    artifacts = _artifact_rows()
    catalog = _catalog_for_grid()
    monkeypatch.setattr(runner, "_load_source_lock", lambda *args, **kwargs: (
        {
            "uri": runner.SOURCE_LOCK_URI,
            "generation": runner.SOURCE_LOCK_GENERATION,
            "sha256": runner.SOURCE_LOCK_SHA256,
            "bytes": runner.SOURCE_LOCK_BYTES,
        },
        artifacts,
        catalog,
    ))
    downloaded: list[tuple[int, int, int]] = []

    def download(client, locked):
        key = (locked["season"], locked["week"], locked["seed"])
        downloaded.append(key)
        player_id = f"p-{locked['season']}-{locked['week']}"
        return [player_id], np.zeros((1, 2), dtype=np.float32), {
            "uri": locked["uri"],
            "generation": locked["generation"],
            "sha256": locked["sha256"],
            "bytes": locked["bytes"],
        }

    monkeypatch.setattr(runner, "_download_player_worlds", download)
    monkeypatch.setattr(
        runner,
        "_science_cell",
        lambda rows, ids, draws: {
            "version": "synthetic-cell-v1",
            "season": rows[0]["season"],
            "week": rows[0]["week"],
            "mechanics": {"passes": True},
        },
    )
    if aggregate_gate is not None:
        monkeypatch.setattr(
            runner,
            "_science_aggregate",
            lambda cells: {
                "block_reports": {
                    block: {"slates": len(reports)}
                    for block, reports in cells.items()
                },
                "gate": aggregate_gate,
            },
        )
    output_uri = "gs://synthetic/output.json"
    monkeypatch.setattr(runner, "_expected_output_uri", lambda mode: output_uri)
    uploads: list[bytes] = []

    def upload(client, uri, payload):
        uploads.append(payload)
        return {
            "uri": uri,
            "generation": "999",
            "sha256": sha256(payload).hexdigest(),
            "bytes": len(payload),
            "create_only": True,
        }

    monkeypatch.setattr(runner, "_upload_create_only", upload)
    return output_uri, downloaded, uploads


def test_runner_import_graph_has_no_outcome_or_lineup_path() -> None:
    path = ROOT / "scripts/run_a2a_rank_factor_split_census.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden = (
        "bigquery",
        "optimizer",
        "backtest",
        "final_served_dependence",
        "production_law_dependence",
        "run_production_law_dependence_remeasurement",
    )
    assert not any(token in module for module in imported for token in forbidden)
    assert "OUTCOME_SQL" not in source
    assert "client.query(" not in source
    assert "transform_and_measure_slate" in source
    assert "archive[\"player_ids\"]" in source
    assert "archive[\"player_draws\"]" in source
    assert "archive[\"totals\"]" not in source
    assert "archive[\"cand_ix\"]" not in source


def test_strict_and_canonical_json_reject_duplicates_and_nonfinite() -> None:
    with pytest.raises(RuntimeError, match="strict finite JSON"):
        runner._strict_json(b'{"a":1,"a":2}')
    with pytest.raises(RuntimeError, match="strict finite JSON"):
        runner._strict_json(b'{"a":NaN}')
    value = {"z": np.int64(2), "a": np.float32(1.5), "b": np.bool_(True)}
    assert runner._canonical_json_bytes(value) == b'{"a":1.5,"b":true,"z":2}\n'
    with pytest.raises(RuntimeError, match="non-finite"):
        runner._canonical_json_bytes({"bad": float("inf")})


def test_artifact_grid_is_complete_canonical_and_poison_closed() -> None:
    artifacts = _artifact_rows()
    assert len(runner._validate_artifact_grid(artifacts)) == 270
    with pytest.raises(RuntimeError, match="incomplete"):
        runner._validate_artifact_grid(artifacts[:-1])
    reordered = deepcopy(artifacts)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(RuntimeError, match="order"):
        runner._validate_artifact_grid(reordered)
    poisoned = deepcopy(artifacts)
    poisoned[4]["generation"] = "not-a-generation"
    with pytest.raises(RuntimeError, match="identity"):
        runner._validate_artifact_grid(poisoned)


def test_small_synthetic_catalog_validation_is_exact() -> None:
    rows = [
        {
            "season": 2023, "week": 1, "player_id": "p1",
            "position": "QB", "team": "AAA", "mean_projection": 20.0,
        },
        {
            "season": 2023, "week": 1, "player_id": "p2",
            "position": "WR", "team": "AAA", "mean_projection": 8.0,
        },
        {
            "season": 2023, "week": 2, "player_id": "p3",
            "position": "DST", "team": "BBB", "mean_projection": 7.0,
        },
    ]
    digest = runner._catalog_source_digest(rows)
    assert runner._validate_catalog(
        rows,
        expected_rows=3,
        expected_eligible=2,
        expected_sha256=digest,
        expected_slates={(2023, 1), (2023, 2)},
    ) == rows
    duplicate = deepcopy(rows)
    duplicate[1]["player_id"] = "p1"
    with pytest.raises(RuntimeError, match="canonical and unique"):
        runner._validate_catalog(
            duplicate,
            expected_rows=3,
            expected_eligible=2,
            expected_sha256=digest,
            expected_slates={(2023, 1), (2023, 2)},
        )
    nonfinite = deepcopy(rows)
    nonfinite[0]["mean_projection"] = float("nan")
    with pytest.raises(RuntimeError, match="catalog row"):
        runner._validate_catalog(
            nonfinite,
            expected_rows=3,
            expected_eligible=2,
            expected_sha256=digest,
            expected_slates={(2023, 1), (2023, 2)},
        )


def test_source_lock_content_identity_poison_fails_before_parse(monkeypatch) -> None:
    raw = b'{"synthetic":true}\n'
    uri = "gs://synthetic/source-lock.json"
    digest = sha256(raw).hexdigest()
    monkeypatch.setattr(runner, "SOURCE_LOCK_URI", uri)
    monkeypatch.setattr(runner, "SOURCE_LOCK_GENERATION", "12")
    monkeypatch.setattr(runner, "SOURCE_LOCK_SHA256", digest)
    monkeypatch.setattr(runner, "SOURCE_LOCK_BYTES", len(raw))
    monkeypatch.setattr(runner, "_validate_source_lock", lambda lock: ([], []))
    receipt = {
        "uri": uri, "generation": "12", "sha256": digest, "bytes": len(raw),
        "updated": "ignored-representation",
    }
    monkeypatch.setattr(
        runner, "live_object_receipt", lambda client, value: (receipt, raw),
    )
    lock_receipt, artifacts, catalog = runner._load_source_lock(
        object(), uri=uri, generation="12", digest=digest,
    )
    assert lock_receipt == {key: receipt[key] for key in (
        "uri", "generation", "sha256", "bytes",
    )}
    assert artifacts == [] and catalog == []
    monkeypatch.setattr(
        runner,
        "live_object_receipt",
        lambda client, value: (receipt, raw + b"poison"),
    )
    with pytest.raises(RuntimeError, match="content identity"):
        runner._load_source_lock(
            object(), uri=uri, generation="12", digest=digest,
        )


def test_artifact_decoder_never_materializes_candidate_arrays(monkeypatch) -> None:
    buffer = io.BytesIO()
    # Object arrays would raise under allow_pickle=False if the runner touched
    # candidate bodies.  Player-world arrays remain ordinary safe ndarrays.
    opaque = np.asarray([object()], dtype=object)
    np.savez(
        buffer,
        cand_ix=opaque,
        totals=opaque,
        tail_line=opaque,
        player_ids=np.asarray(["p1", "p2"]),
        player_draws=np.arange(8, dtype=np.float32).reshape(2, 4),
    )
    raw = buffer.getvalue()
    uri = "gs://synthetic/one.npz"
    receipt = {
        "uri": uri,
        "generation": "7",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "updated": "ignored-representation",
    }
    monkeypatch.setattr(runner, "WORLDS_PER_ARTIFACT", 4)
    monkeypatch.setattr(
        runner, "live_object_receipt", lambda client, value: (receipt, raw),
    )
    ids, draws, identity = runner._download_player_worlds(object(), receipt)
    assert ids == ["p1", "p2"]
    assert draws.shape == (2, 4)
    assert identity == {key: receipt[key] for key in (
        "uri", "generation", "sha256", "bytes",
    )}


def test_thin_science_adapters_use_only_the_published_api(monkeypatch) -> None:
    calls = []
    draws = np.zeros((1, 2), dtype=np.float32)
    report = {"mechanics": {"passes": True}}

    def transform(**kwargs):
        calls.append(("transform", kwargs))
        return kwargs["control_draws"].copy(), report

    monkeypatch.setattr(runner.science, "transform_and_measure_slate", transform)
    monkeypatch.setattr(runner, "WORLDS_PER_ARTIFACT", 2)
    assert runner._science_cell([], ["p1"], draws) is report
    assert calls[0][1] == {
        "catalog_rows": [],
        "player_ids": ["p1"],
        "control_draws": draws,
        "expected_worlds": 2,
    }

    monkeypatch.setattr(
        runner.science,
        "combine_reports",
        lambda rows: {"count": len(rows)},
    )
    gate = _gate(mechanical=True, directional=True)
    monkeypatch.setattr(
        runner.science,
        "evaluate_mechanism_gate",
        lambda blocks: gate if set(blocks) == set(runner.BLOCKS) else None,
    )
    combined = runner._science_aggregate({block: [{}] for block in runner.BLOCKS})
    assert combined == {
        "block_reports": {block: {"count": 1} for block in runner.BLOCKS},
        "gate": gate,
    }


def test_smoke_scope_is_exactly_2023_w1_r0_and_all_licenses_false(
    monkeypatch, tmp_path,
) -> None:
    output_uri, downloaded, uploads = _mock_run_boundaries(
        monkeypatch, tmp_path,
    )
    result = runner.run(
        mode="smoke",
        source_lock_uri=runner.SOURCE_LOCK_URI,
        source_lock_generation=runner.SOURCE_LOCK_GENERATION,
        source_lock_sha256=runner.SOURCE_LOCK_SHA256,
        output_uri=output_uri,
    )
    assert downloaded == [(2023, 1, 0)]
    assert result["scope"] == {
        "artifacts": 1,
        "slates": 1,
        "blocks": ["R0"],
        "worlds_per_artifact": 10_000,
    }
    assert result["disposition"] == "a2a-scorefree-smoke-passes"
    assert all(result[field] is False for field in runner.LICENSE_FIELDS)
    assert len(uploads) == 1
    serialized = json.loads(uploads[0])
    assert serialized["mode"] == "smoke"
    assert "output" not in serialized


def test_full_mode_consumes_exact_grid_aggregates_five_blocks_and_pass_licenses(
    monkeypatch, tmp_path,
) -> None:
    gate = _gate(mechanical=True, directional=True)
    output_uri, downloaded, uploads = _mock_run_boundaries(
        monkeypatch, tmp_path, aggregate_gate=gate,
    )
    result = runner.run(
        mode="full",
        source_lock_uri=runner.SOURCE_LOCK_URI,
        source_lock_generation=runner.SOURCE_LOCK_GENERATION,
        source_lock_sha256=runner.SOURCE_LOCK_SHA256,
        output_uri=output_uri,
    )
    assert downloaded == list(runner._expected_grid())
    assert len(result["artifact_reports"]) == 270
    assert set(result["block_reports"]) == set(runner.BLOCKS)
    assert {value["slates"] for value in result["block_reports"].values()} == {54}
    assert result["disposition"] == "a2a-scorefree-mechanism-passes"
    assert result["historical_remeasurement_licensed"] is True
    assert all(
        result[field] is False for field in runner.LICENSE_FIELDS
        if field != "historical_remeasurement_licensed"
    )
    assert len(uploads) == 1


def test_full_mode_rejects_incomplete_source_before_any_artifact_body(
    monkeypatch, tmp_path,
) -> None:
    output_uri, downloaded, uploads = _mock_run_boundaries(
        monkeypatch, tmp_path, aggregate_gate=_gate(
            mechanical=True, directional=True,
        ),
    )
    original = runner._load_source_lock

    def incomplete(*args, **kwargs):
        receipt, artifacts, catalog = original(*args, **kwargs)
        return receipt, artifacts[:-1], catalog

    monkeypatch.setattr(runner, "_load_source_lock", incomplete)
    with pytest.raises(RuntimeError, match="grid changed"):
        runner.run(
            mode="full",
            source_lock_uri=runner.SOURCE_LOCK_URI,
            source_lock_generation=runner.SOURCE_LOCK_GENERATION,
            source_lock_sha256=runner.SOURCE_LOCK_SHA256,
            output_uri=output_uri,
        )
    assert downloaded == []
    assert uploads == []


@pytest.mark.parametrize(
    ("mechanical", "directional", "disposition", "licensed"),
    [
        (False, False, "a2a-scorefree-invalid", False),
        (True, False, "a2a-scorefree-mechanism-fails", False),
        (True, True, "a2a-scorefree-mechanism-passes", True),
    ],
)
def test_full_disposition_and_license_truth_table(
    mechanical, directional, disposition, licensed,
) -> None:
    gate = _gate(mechanical=mechanical, directional=directional)
    observed_disposition, licenses = runner._full_disposition(gate)
    assert observed_disposition == disposition
    assert licenses["historical_remeasurement_licensed"] is licensed
    assert all(
        value is False for key, value in licenses.items()
        if key != "historical_remeasurement_licensed"
    )
    poisoned = deepcopy(gate)
    poisoned["production_change_licensed"] = True
    with pytest.raises(RuntimeError, match="schema"):
        runner._full_disposition(poisoned)
    poisoned = deepcopy(gate)
    poisoned["licenses"]["production_change_licensed"] = True
    with pytest.raises(RuntimeError, match="disposition/license"):
        runner._full_disposition(poisoned)


def test_create_only_upload_uses_generation_zero_precondition() -> None:
    calls = []

    class Blob:
        generation = "123"

        def upload_from_string(self, payload, **kwargs):
            calls.append((payload, kwargs))

        def reload(self):
            return None

    blob = Blob()
    client = SimpleNamespace(
        bucket=lambda name: SimpleNamespace(blob=lambda object_name: blob),
    )
    payload = b'{"finite":true}\n'
    receipt = runner._upload_create_only(
        client, "gs://synthetic/result.json", payload,
    )
    assert calls == [(payload, {
        "content_type": "application/json", "if_generation_match": 0,
    })]
    assert receipt["create_only"] is True
    assert receipt["sha256"] == sha256(payload).hexdigest()
