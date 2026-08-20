#!/usr/bin/env python3
"""Run the frozen A7 incumbent-pool clipped-ladder selector arm.

Full mode reconstructs all 54 canonical CBWU slates and passes every
outcome-blind source, control-reproduction, legality, prefix, mechanism, and
simultaneous-extremes gate before issuing the single historical-score query.
Smoke mode reconstructs one real slate without formatting or executing that
query and writes only a compact create-only outcome-blind receipt. Support
census mode repeats the same boundary over all 54 slates.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import numpy as np
from google.cloud import bigquery, storage


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books  # noqa: E402
from nfl_dfs.research.portfolio_effective_rank import (  # noqa: E402
    decode_score_artifact,
)
from nfl_dfs.research.a7_select_ladder import (  # noqa: E402
    BLOCK_COUNT,
    CONTROL_ENV,
    ENTRY_COUNT,
    LADDER_SPEC,
    PROTOCOL_ID,
    TREATMENT_ENV,
    aggregate_outcomes,
    aggregate_scorefree,
    candidate_source_counts,
    score_ordered_book,
    scorefree_book_receipt,
    select_books,
    selected_identities,
    support_census as build_support_census,
    validate_control_baseline,
)
from nfl_dfs.research.source_preflight import (  # noqa: E402
    resolve_panel_artifacts,
    validate_execution_identity,
    verify_local_sha256,
)

from run_cbwu_seed_order_audit import (  # noqa: E402
    FORENSIC_MANIFEST_SHA256,
    PLAYER_SQL,
    PROJECT,
    SOURCE_PANEL_IDS,
    SOURCE_SQL,
    _candidate_batch,
    _parse_gcs,
    _query,
    _upload_create_only,
    validate_scorefree_queries,
)
from run_exact_n_scorefree import _is_production_legal  # noqa: E402
import finish_a7_select_ladder as a7_transport  # noqa: E402


VERSION = "a7-select-ladder-phase-s-incumbent-v1"
RUN_ID = PROTOCOL_ID
PROTOCOL_PATH = Path(
    "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol.md"
)
# Candidate-protocol digest. The protocol and implementation bytes remain
# unchanged across smoke, support census, and the one historical run. A
# separate immutable freeze manifest binds the two preflight receipts.
PROTOCOL_SHA256 = "987ad3eb8bd141427ce201348de165b9b337c1184de1fc8bdd32987bd1373cce"
SOURCE_REPORT_PATH = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
SOURCE_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
BASELINE_PATH = Path("reports/current-baseline.json")
BASELINE_SHA256 = (
    "1946ce8af123a4aad83c98d5fa204fb9f70cb47bd0113e3d5b9d492d23e864da"
)
BASELINE_VECTOR_PATH = Path(
    "reports/multiseed-candidate-world-runs/"
    "20260813-multiseed-candidate-world-v1/report.json"
)
BASELINE_VECTOR_SHA256 = (
    "a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239"
)
OUTPUT_URI = (
    "gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/"
    f"{RUN_ID}/result.json"
)
PREFLIGHT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/"
    f"{RUN_ID}/preflight"
)
SMOKE_RECEIPT_URI = f"{PREFLIGHT_PREFIX}/real-artifact-smoke.json"
SUPPORT_RECEIPT_URI = f"{PREFLIGHT_PREFIX}/support-census.json"
SMOKE_TERMINAL_URI = f"{PREFLIGHT_PREFIX}/real-artifact-smoke-terminal.json"
SUPPORT_TERMINAL_URI = f"{PREFLIGHT_PREFIX}/support-census-terminal.json"
JOB_CLAIM_URI = f"{PREFLIGHT_PREFIX}/job-claim.json"
FREEZE_MANIFEST_URI = f"{PREFLIGHT_PREFIX}/freeze-manifest.json"
WORLDS_PER_BLOCK = 10_000
IMPLEMENTATION_PATHS = {
    "selector": Path("src/nfl_dfs/optimizer/lineup.py"),
    "scientific_module": Path("src/nfl_dfs/research/a7_select_ladder.py"),
    "paired_statistics": Path("src/nfl_dfs/research/paired_max_stats.py"),
    "candidate_combiner": Path("src/nfl_dfs/inference/multiseed_portfolio.py"),
    "artifact_decoder": Path(
        "src/nfl_dfs/research/portfolio_effective_rank.py"
    ),
    "source_preflight": Path("src/nfl_dfs/research/source_preflight.py"),
    "source_query_helper": Path("scripts/run_cbwu_seed_order_audit.py"),
    "legality_helper": Path("scripts/run_exact_n_scorefree.py"),
    "runner": Path("scripts/run_a7_select_ladder.py"),
}
FREEZE_IMPLEMENTATION_PATHS = {
    **IMPLEMENTATION_PATHS,
    "lease_tool": Path("scripts/historical_outcome_lease.py"),
    "cloudbuild_config": Path("cloudbuild.yaml"),
    "freeze_builder": Path("scripts/freeze_a7_select_ladder.py"),
    "launcher": Path("scripts/cloud_a7_select_ladder.sh"),
    "watcher": Path("scripts/watch_a7_select_ladder_queue.sh"),
    "finisher": Path("scripts/finish_a7_select_ladder.py"),
}
FREEZE_MANIFEST_VERSION = "a7-select-ladder-freeze-manifest-v1"
FROZEN_CHOICES = {
    "simulation_law": "phase-s-finite-k-plus-sis-asoe",
    "ladder_spec": LADDER_SPEC,
    "mean_weight": 0,
    "control_tie_law": "marginal-p194-coverage_then-p194_then-mean",
    "treatment_tie_law": "marginal-ladder-gain_then-mean_then-lower-index",
    "primary_entry_count": 80,
    "non_gating_prefix_counts": [4, 14],
    "realism_quantile": "0.99",
    "realism_comparison": "strict-greater-than-within-block-higher-quantile",
    "realism_minimum_events_per_arm": 100,
    "realism_requires_every_block": True,
    "realism_r3_noninferiority_margin": 0.01,
    "realism_r3_noninferiority_margin_numerator": 1,
    "realism_r3_noninferiority_margin_denominator": 100,
    "paired_success": "mean-and-signed-rank-two-sided-p-le-0.05",
    "paired_sign_flip_exact_nonzero_limit": 20,
    "paired_sign_flip_monte_carlo_resamples": 200_000,
    "paired_sign_flip_monte_carlo_seed": 20_260_818,
    "paired_sign_flip_add_one_correction": True,
    "bootstrap_design": "season-stratified-within-season-resampling",
    "bootstrap_resamples": 10_000,
    "bootstrap_seed": 20_260_820,
    "bootstrap_quantile_method": "linear",
    "bootstrap_quantiles": [0.025, 0.975],
    "shoulder_noninferiority_slates": -1,
    "historical_looks": 1,
}
OPERATOR_APPROVALS = {
    "exact_ladder_and_no_mean": True,
    "r3_support_floor_and_noninferiority_margin": True,
    "s80_co_primary_intersection": True,
    "shoulder_noninferiority_margins": True,
    "s80_is_sole_gate": True,
    "n4_n14_are_non_gating": True,
}
SOURCE_QUERY_COLUMNS = (
    "panel_run_id", "season", "week", "cand_ix", "tag", "all_tags",
    "players", "score_artifact_uri", "score_artifact_sha256",
)
PLAYER_QUERY_COLUMNS = (
    "manifest_sha256", "season", "week", "player_id", "player_name",
    "position", "team", "opponent", "game_id", "salary",
    "mean_projection",
)
ACTUAL_QUERY_COLUMNS = (
    "panel_run_id", "season", "week", "cand_ix", "players", "actual_score",
)
PREFLIGHT_RECEIPT_KEYS = frozenset({
    "version", "run_id", "protocol_id", "mode", "code_sha", "image",
    "protocol_sha256", "source_report_sha256", "baseline_sha256",
    "baseline_vector_sha256", "forensic_manifest_sha256",
    "local_source_receipts", "implementation_receipts",
    "query_content_receipts", "frozen_choices", "source_panels",
    "source_preflight", "source_artifact_count", "source_artifacts_sha256",
    "slates", "support", "uses_realized_outcomes",
    "actual_score_query_executed", "production_change_licensed",
    "production_law_scorefree_transfer_licensed",
    "prospective_shadow_licensed",
})
PREFLIGHT_SLATE_KEYS = frozenset({
    "season", "week", "candidate_budget", "world_count",
    "candidate_identities_sha256", "candidate_tags_sha256",
    "combined_input_receipts", "scorefree_receipt_sha256",
})
QUERY_RECEIPT_KEYS = frozenset({"columns", "rows", "sha256"})
ARRAY_RECEIPT_KEYS = frozenset({"dtype", "shape", "sha256"})
SUPPORT_RECEIPT_KEYS = frozenset({
    "version", "uses_realized_outcomes", "slates", "definition",
    "minimum_aggregate_events_per_arm", "r3_positive_gain_events_by_block",
    "conditions", "passes",
})


def _implementation_receipts() -> dict[str, str]:
    receipts = {}
    for label, relative in IMPLEMENTATION_PATHS.items():
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"A7 implementation source is absent: {relative}")
        receipts[label] = sha256(path.read_bytes()).hexdigest()
    return receipts


def _freeze_implementation_receipts() -> dict[str, str]:
    receipts = {}
    for label, relative in FREEZE_IMPLEMENTATION_PATHS.items():
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"A7 freeze implementation source is absent: {relative}")
        receipts[label] = sha256(path.read_bytes()).hexdigest()
    return receipts


def _validate_smoke_source_identity(code_sha: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None:
        raise RuntimeError("A7 real-artifact preflight requires a full code SHA")
    paths = (
        *IMPLEMENTATION_PATHS.values(), PROTOCOL_PATH, SOURCE_REPORT_PATH,
        BASELINE_PATH, BASELINE_VECTOR_PATH,
    )
    for relative in paths:
        current = (ROOT / relative).read_bytes()
        try:
            committed = subprocess.run(
                ["git", "-C", str(ROOT), "show", f"{code_sha}:{relative}"],
                check=True, capture_output=True,
            ).stdout
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"A7 preflight commit lacks source: {relative}",
            ) from exc
        if current != committed:
            raise RuntimeError(f"A7 preflight source differs from commit: {relative}")


def _validate_preflight_identity(code_sha: str, image: str) -> None:
    if image:
        validate_execution_identity(code_sha, image)
    else:
        _validate_smoke_source_identity(code_sha)


def _array_receipt(value: np.ndarray) -> dict[str, Any]:
    array = np.ascontiguousarray(value)
    header = json.dumps({
        "dtype": array.dtype.str,
        "shape": list(array.shape),
    }, sort_keys=True, separators=(",", ":")).encode("ascii")
    return {
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "sha256": sha256(header + b"\0" + array.tobytes(order="C")).hexdigest(),
    }


def _canonical_query_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError("A7 source query contains a non-finite value")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise RuntimeError("A7 source query contains a non-finite decimal")
        return {"decimal": str(value.normalize())}
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return [_canonical_query_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise RuntimeError("A7 source query mapping key is not a string")
        return {
            key: _canonical_query_value(item)
            for key, item in sorted(value.items())
        }
    if hasattr(value, "isoformat"):
        return {"isoformat": str(value.isoformat())}
    raise RuntimeError(
        f"A7 source query contains an unsupported value type: {type(value)!r}",
    )


def _canonical_query_rows(
    frame: Any, columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    if tuple(str(value) for value in frame.columns) != columns:
        raise RuntimeError("A7 source query schema differs")
    keyed_rows: list[tuple[str, dict[str, Any]]] = []
    for raw in frame.to_dict("records"):
        row = {column: _canonical_query_value(raw[column]) for column in columns}
        encoded = json.dumps(
            row, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        keyed_rows.append((encoded, row))
    keyed_rows.sort(key=lambda item: item[0])
    if any(
        keyed_rows[index - 1][0] == keyed_rows[index][0]
        for index in range(1, len(keyed_rows))
    ):
        raise RuntimeError("A7 source query contains duplicate canonical rows")
    return [row for _, row in keyed_rows]


def _query_rows_content_receipt(
    rows: list[dict[str, Any]], columns: tuple[str, ...], *,
    require_encoded_order: bool = True,
) -> dict[str, Any]:
    encoded_rows = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(columns):
            raise RuntimeError("A7 retained query row schema differs")
        ordered = {column: row[column] for column in columns}
        encoded_rows.append(json.dumps(
            ordered, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))
    if (
        (require_encoded_order and encoded_rows != sorted(encoded_rows))
        or len(encoded_rows) != len(set(encoded_rows))
    ):
        raise RuntimeError("A7 retained query row order differs")
    encoded_rows.sort()
    payload = ("[" + ",".join(encoded_rows) + "]").encode("utf-8")
    return {
        "columns": list(columns),
        "rows": len(encoded_rows),
        "sha256": sha256(payload).hexdigest(),
    }


def _query_content_receipt(frame: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    return _query_rows_content_receipt(
        _canonical_query_rows(frame, columns), columns,
    )


def _preflight_receipt(report: dict[str, Any]) -> dict[str, Any]:
    if (
        report.get("uses_realized_outcomes") is not False
        or report.get("actual_score_query_executed") is not False
        or report.get("production_change_licensed") is not False
        or report.get("production_law_scorefree_transfer_licensed") is not False
        or report.get("prospective_shadow_licensed") is not False
    ):
        raise RuntimeError("A7 preflight crossed its outcome/license boundary")
    mode = "real-artifact-smoke" if report.get("smoke") else "support-census"
    rows = report.get("slates", [])
    row_receipts = []
    for row in rows:
        scorefree_digest = sha256(json.dumps({
            arm: row[arm]["scorefree"] for arm in ("control", "treatment")
        }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        row_receipts.append({
            "season": int(row["season"]),
            "week": int(row["week"]),
            "candidate_budget": int(row["candidate_budget"]),
            "world_count": int(row["world_count"]),
            "candidate_identities_sha256": row["candidate_identities_sha256"],
            "candidate_tags_sha256": row["candidate_tags_sha256"],
            "combined_input_receipts": row["combined_input_receipts"],
            "scorefree_receipt_sha256": scorefree_digest,
        })
    source_artifacts = [{
        key: row[key] for key in (
            "panel_run_id", "season", "week", "uri", "sha256",
            "generation", "bytes", "candidate_rows",
        )
    } for row in report.get("source_artifacts", [])]
    artifact_payload = json.dumps(
        source_artifacts, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode()
    receipt = {
        "version": "a7-select-ladder-preflight-receipt-v1",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "mode": mode,
        "code_sha": report["code_sha"],
        "image": report["image"],
        "protocol_sha256": report["protocol_sha256"],
        "source_report_sha256": report["source_report_sha256"],
        "baseline_sha256": report["baseline_sha256"],
        "baseline_vector_sha256": report["baseline_vector_sha256"],
        "forensic_manifest_sha256": report["forensic_manifest_sha256"],
        "local_source_receipts": report["local_source_receipts"],
        "implementation_receipts": report["implementation_receipts"],
        "query_content_receipts": report["query_content_receipts"],
        "frozen_choices": FROZEN_CHOICES,
        "source_panels": report["source_panels"],
        "source_preflight": report["source_preflight"],
        "source_artifact_count": len(report.get("source_artifacts", [])),
        "source_artifacts_sha256": sha256(artifact_payload).hexdigest(),
        "slates": row_receipts,
        "support": report.get("support"),
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return receipt


def _object_identity_from_env() -> dict[str, Any]:
    values = {
        "uri": os.environ.get("A7_FREEZE_MANIFEST_URI", "").strip(),
        "generation": os.environ.get(
            "A7_FREEZE_MANIFEST_GENERATION", "",
        ).strip(),
        "sha256": os.environ.get("A7_FREEZE_MANIFEST_SHA256", "").strip(),
    }
    if (
        values["uri"] != FREEZE_MANIFEST_URI
        or re.fullmatch(r"[1-9][0-9]*", values["generation"]) is None
        or re.fullmatch(r"[0-9a-f]{64}", values["sha256"]) is None
    ):
        raise RuntimeError("A7 freeze-manifest identity differs")
    return {
        "uri": values["uri"],
        "generation": values["generation"],
        "sha256": values["sha256"],
    }


def _download_json_object_pinned(
    client: storage.Client, identity: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    required = {"uri", "generation", "sha256"}
    allowed = required | {"bytes", "metageneration"}
    if not required <= set(identity) or not set(identity) <= allowed:
        raise RuntimeError("A7 immutable JSON object identity differs")
    uri = str(identity["uri"])
    generation = str(identity["generation"])
    digest = str(identity["sha256"])
    expected_bytes = int(identity["bytes"]) if "bytes" in identity else None
    expected_metageneration = str(identity.get("metageneration", "1"))
    bucket_name, object_name = _parse_gcs(uri)
    if (
        re.fullmatch(r"[1-9][0-9]*", generation) is None
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        or (expected_bytes is not None and expected_bytes <= 0)
        or expected_metageneration != "1"
    ):
        raise RuntimeError("A7 immutable JSON object metadata differs")
    blob = client.bucket(bucket_name).blob(
        object_name, generation=int(generation),
    )
    raw = blob.download_as_bytes(if_generation_match=int(generation))
    blob.reload(if_generation_match=int(generation))
    if (
        str(blob.generation) != generation
        or str(blob.metageneration or "") != expected_metageneration
        or int(blob.size or 0) != len(raw)
        or (expected_bytes is not None and len(raw) != expected_bytes)
        or sha256(raw).hexdigest() != digest
    ):
        raise RuntimeError("A7 immutable JSON object bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("A7 immutable JSON object is not canonical JSON") from exc
    canonical = (json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")
    if canonical != raw or not isinstance(value, dict):
        raise RuntimeError("A7 immutable JSON object is not canonical JSON")
    return value, {
        **identity,
        "bytes": len(raw),
        "metageneration": "1",
    }


def _is_sha256(value: object) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", str(value)) is not None


def _validate_query_receipt(
    value: object, *, columns: tuple[str, ...], label: str,
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != QUERY_RECEIPT_KEYS
        or value.get("columns") != list(columns)
        or type(value.get("rows")) is not int
        or int(value["rows"]) <= 0
        or not _is_sha256(value.get("sha256"))
    ):
        raise RuntimeError(f"A7 {label} query receipt differs")


def _validate_preflight_slate_rows(
    rows: object, *, expected_keys: list[tuple[int, int]],
) -> None:
    if not isinstance(rows, list) or len(rows) != len(expected_keys):
        raise RuntimeError("A7 preflight slate receipt population differs")
    for raw, expected_key in zip(rows, expected_keys, strict=True):
        if not isinstance(raw, dict) or set(raw) != PREFLIGHT_SLATE_KEYS:
            raise RuntimeError("A7 preflight slate receipt schema differs")
        budget = raw.get("candidate_budget")
        combined = raw.get("combined_input_receipts")
        if (
            (int(raw.get("season", 0)), int(raw.get("week", 0)))
            != expected_key
            or type(budget) is not int
            or int(budget) < ENTRY_COUNT
            or raw.get("world_count") != BLOCK_COUNT * WORLDS_PER_BLOCK
            or not _is_sha256(raw.get("candidate_identities_sha256"))
            or not _is_sha256(raw.get("candidate_tags_sha256"))
            or not _is_sha256(raw.get("scorefree_receipt_sha256"))
            or not isinstance(combined, dict)
            or set(combined) != {
                "candidate_totals", "player_draws", "player_ids_sha256",
            }
            or not _is_sha256(combined.get("player_ids_sha256"))
        ):
            raise RuntimeError("A7 preflight slate receipt differs")
        for field, first_dimension in (
            ("candidate_totals", int(budget)), ("player_draws", None),
        ):
            value = combined.get(field)
            if (
                not isinstance(value, dict)
                or set(value) != ARRAY_RECEIPT_KEYS
                or value.get("dtype") != "<f4"
                or not isinstance(value.get("shape"), list)
                or len(value["shape"]) != 2
                or type(value["shape"][0]) is not int
                or value["shape"][0] <= 0
                or value["shape"][1] != BLOCK_COUNT * WORLDS_PER_BLOCK
                or (first_dimension is not None and value["shape"][0] != (
                    first_dimension
                ))
                or not _is_sha256(value.get("sha256"))
            ):
                raise RuntimeError(f"A7 preflight {field} receipt differs")


def _validate_support_receipt(value: object) -> None:
    if not isinstance(value, dict) or set(value) != SUPPORT_RECEIPT_KEYS:
        raise RuntimeError("A7 compact support schema differs")
    cells = value.get("r3_positive_gain_events_by_block")
    if not isinstance(cells, dict) or set(cells) != {"control", "treatment"}:
        raise RuntimeError("A7 compact support cells differ")
    for arm in ("control", "treatment"):
        if (
            not isinstance(cells[arm], list)
            or len(cells[arm]) != BLOCK_COUNT
            or any(type(item) is not int or item < 0 for item in cells[arm])
        ):
            raise RuntimeError("A7 compact support block cells differ")
    conditions = {
        "control_r3_events_at_least_100": sum(cells["control"]) >= 100,
        "treatment_r3_events_at_least_100": sum(cells["treatment"]) >= 100,
        "control_r3_supported_in_every_block": all(
            item > 0 for item in cells["control"]
        ),
        "treatment_r3_supported_in_every_block": all(
            item > 0 for item in cells["treatment"]
        ),
    }
    if (
        value.get("version") != "a7-r3-support-census-v1"
        or value.get("uses_realized_outcomes") is not False
        or value.get("slates") != 54
        or value.get("definition") != (
            "positive-ladder-gain-events-with-at-least-3-strict-q99-exceedances"
        )
        or value.get("minimum_aggregate_events_per_arm") != 100
        or value.get("conditions") != conditions
        or value.get("passes") is not all(conditions.values())
    ):
        raise RuntimeError("A7 compact support receipt differs")


def _validate_preflight_receipt(
    receipt: dict[str, Any], *, mode: str, manifest: dict[str, Any],
) -> None:
    if (
        not isinstance(receipt, dict)
        or set(receipt) != PREFLIGHT_RECEIPT_KEYS
        or receipt.get("version") != "a7-select-ladder-preflight-receipt-v1"
        or receipt.get("run_id") != RUN_ID
        or receipt.get("protocol_id") != PROTOCOL_ID
        or receipt.get("mode") != mode
        or receipt.get("code_sha") != manifest.get("code", {}).get("commit_sha")
        or receipt.get("image") != manifest.get("image", {}).get("uri")
        or receipt.get("protocol_sha256") != PROTOCOL_SHA256
        or receipt.get("source_report_sha256") != SOURCE_REPORT_SHA256
        or receipt.get("baseline_sha256") != BASELINE_SHA256
        or receipt.get("baseline_vector_sha256") != BASELINE_VECTOR_SHA256
        or receipt.get("forensic_manifest_sha256") != FORENSIC_MANIFEST_SHA256
        or receipt.get("frozen_choices") != manifest.get("frozen_law")
        or receipt.get("implementation_receipts") != {
            key: manifest.get("implementation_sha256", {}).get(key)
            for key in IMPLEMENTATION_PATHS
        }
        or receipt.get("query_content_receipts") != manifest.get(
            "query_content_receipts"
        )
        or receipt.get("local_source_receipts") != manifest.get(
            "local_source_receipts"
        )
        or receipt.get("source_panels") != list(SOURCE_PANEL_IDS)
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("actual_score_query_executed") is not False
        or receipt.get("production_change_licensed") is not False
        or receipt.get(
            "production_law_scorefree_transfer_licensed"
        ) is not False
        or receipt.get("prospective_shadow_licensed") is not False
    ):
        raise RuntimeError(f"A7 {mode} receipt differs from freeze manifest")
    local_receipts = receipt.get("local_source_receipts")
    implementation_receipts = receipt.get("implementation_receipts")
    query_receipts = receipt.get("query_content_receipts")
    if (
        not isinstance(local_receipts, dict)
        or set(local_receipts) != {
            "protocol", "source_report", "baseline", "baseline_vector",
        }
        or not isinstance(implementation_receipts, dict)
        or set(implementation_receipts) != set(IMPLEMENTATION_PATHS)
        or any(not _is_sha256(value) for value in (
            *local_receipts.values(), *implementation_receipts.values(),
        ))
        or not isinstance(query_receipts, dict)
        or set(query_receipts) != {"candidate_source", "player_source"}
    ):
        raise RuntimeError("A7 preflight frozen receipt schema differs")
    _validate_query_receipt(
        query_receipts["candidate_source"], columns=SOURCE_QUERY_COLUMNS,
        label="candidate-source",
    )
    _validate_query_receipt(
        query_receipts["player_source"], columns=PLAYER_QUERY_COLUMNS,
        label="player-source",
    )
    rows = receipt.get("slates")
    source_preflight = receipt.get("source_preflight")
    expected_slates = [
        [season, week] for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    if source_preflight != {
        "panel_ids": list(SOURCE_PANEL_IDS),
        "slates": expected_slates,
        "slate_count": 54,
        "artifact_count": 270,
    }:
        raise RuntimeError("A7 preflight source census differs")
    source_artifacts = manifest.get("source_artifacts", [])
    if mode == "real-artifact-smoke":
        smoke_artifacts = [
            row for row in source_artifacts
            if (int(row["season"]), int(row["week"])) == (2023, 1)
        ]
        smoke_digest = sha256(json.dumps(
            smoke_artifacts, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")).hexdigest()
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or (int(rows[0]["season"]), int(rows[0]["week"])) != (2023, 1)
            or receipt.get("support") is not None
            or int(receipt.get("source_artifact_count", -1)) != 5
            or receipt.get("source_artifacts_sha256") != smoke_digest
        ):
            raise RuntimeError("A7 smoke receipt population differs")
        _validate_preflight_slate_rows(rows, expected_keys=[(2023, 1)])
    elif mode == "support-census":
        support = receipt.get("support")
        _validate_support_receipt(support)
        if (
            not isinstance(rows, list)
            or len(rows) != 54
            or not isinstance(support, dict)
            or support.get("passes") is not True
            or int(receipt.get("source_artifact_count", -1)) != 270
            or receipt.get("source_artifacts_sha256") != manifest.get(
                "source_artifact_lock_sha256"
            )
        ):
            raise RuntimeError("A7 support receipt population differs")
        _validate_preflight_slate_rows(
            rows,
            expected_keys=[
                (season, week) for season in (2023, 2024, 2025)
                for week in range(1, 19)
            ],
        )
    else:
        raise RuntimeError("A7 preflight mode differs")


def _load_freeze_evidence(
    client: storage.Client, *, code_sha: str, image: str,
    local_source_receipts: dict[str, Any],
    locked_source_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest_identity = _object_identity_from_env()
    manifest, manifest_object = _download_json_object_pinned(
        client, manifest_identity,
    )
    lock_payload = json.dumps(
        locked_source_artifacts, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    protocol = manifest.get("protocol")
    code = manifest.get("code")
    frozen_image = manifest.get("image")
    if (
        set(manifest) != a7_transport.FREEZE_MANIFEST_KEYS
        or manifest.get("version") != FREEZE_MANIFEST_VERSION
        or manifest.get("status") != "frozen-for-one-historical-look"
        or manifest.get("run_id") != RUN_ID
        or manifest.get("protocol_id") != PROTOCOL_ID
        or protocol != {
            "path": str(PROTOCOL_PATH), "sha256": PROTOCOL_SHA256,
        }
        or not isinstance(code, dict)
        or set(code) != {"commit_sha", "archive_sha256"}
        or code.get("commit_sha") != code_sha
        or re.fullmatch(r"[0-9a-f]{64}", str(
            code.get("archive_sha256", "")
        )) is None
        or frozen_image != {"uri": image}
        or manifest.get("operator_approved") is not True
        or manifest.get("operator_approval_basis") != (
            a7_transport.OPERATOR_APPROVAL_BASIS
        )
        or manifest.get("operator_approvals") != OPERATOR_APPROVALS
        or manifest.get("frozen_law") != FROZEN_CHOICES
        or a7_transport.FROZEN_CHOICES != FROZEN_CHOICES
        or manifest.get("implementation_sha256") != (
            _freeze_implementation_receipts()
        )
        or manifest.get("local_source_receipts") != local_source_receipts
        or manifest.get("source_report") != {
            "path": str(SOURCE_REPORT_PATH), "sha256": SOURCE_REPORT_SHA256,
        }
        or manifest.get("baseline") != {
            "path": str(BASELINE_PATH), "sha256": BASELINE_SHA256,
        }
        or manifest.get("baseline_vector") != {
            "path": str(BASELINE_VECTOR_PATH),
            "sha256": BASELINE_VECTOR_SHA256,
        }
        or manifest.get("source_artifacts") != locked_source_artifacts
        or manifest.get("source_artifact_lock_sha256") != sha256(
            lock_payload
        ).hexdigest()
        or int(manifest.get("historical_looks", 0)) != 1
        or manifest.get("uses_realized_outcomes") is not False
        or manifest.get("production_change_licensed") is not False
        or manifest.get(
            "production_law_scorefree_transfer_licensed"
        ) is not False
        or manifest.get("prospective_shadow_licensed") is not False
    ):
        raise RuntimeError("A7 freeze manifest differs")

    query_receipts = manifest.get("query_content_receipts")
    if not isinstance(query_receipts, dict) or set(query_receipts) != {
        "candidate_source", "player_source",
    }:
        raise RuntimeError("A7 freeze query receipt population differs")
    _validate_query_receipt(
        query_receipts["candidate_source"], columns=SOURCE_QUERY_COLUMNS,
        label="frozen candidate-source",
    )
    _validate_query_receipt(
        query_receipts["player_source"], columns=PLAYER_QUERY_COLUMNS,
        label="frozen player-source",
    )

    raw_claim = manifest.get("job_claim")
    claim_body = raw_claim.get("claim") if isinstance(raw_claim, dict) else None
    a3_release_sha256 = (
        claim_body.get("a3_logical_release_sha256")
        if isinstance(claim_body, dict) else ""
    )
    claim = a7_transport._validate_job_claim_receipt(
        raw_claim, code_sha=code_sha, image=image,
        protocol_sha256=PROTOCOL_SHA256,
        a3_logical_release_sha256=str(a3_release_sha256),
    )
    claim_identity = {
        key: value for key, value in claim["object"].items()
        if key != "create_only"
    }
    live_claim, live_claim_object = _download_json_object_pinned(
        client, claim_identity,
    )
    if live_claim != claim["claim"] or live_claim_object != claim_identity:
        raise RuntimeError("A7 durable job-claim object differs")

    objects = manifest.get("preflights")
    if not isinstance(objects, dict) or set(objects) != {"smoke", "support"}:
        raise RuntimeError("A7 freeze preflight object set differs")
    if any(
        not isinstance(objects[key], dict)
        or set(objects[key]) != {"science", "terminal"}
        for key in ("smoke", "support")
    ):
        raise RuntimeError("A7 freeze preflight binding differs")
    receipts: dict[str, dict[str, Any]] = {}
    object_receipts: dict[str, dict[str, Any]] = {}
    terminal_receipts: dict[str, dict[str, Any]] = {}
    terminal_objects: dict[str, dict[str, Any]] = {}
    for key, mode, science_uri, terminal_uri in (
        (
            "smoke", "real-artifact-smoke", SMOKE_RECEIPT_URI,
            SMOKE_TERMINAL_URI,
        ),
        (
            "support", "support-census", SUPPORT_RECEIPT_URI,
            SUPPORT_TERMINAL_URI,
        ),
    ):
        science_identity = objects[key].get("science")
        terminal_identity = objects[key].get("terminal")
        if (
            not isinstance(science_identity, dict)
            or set(science_identity) != {
                "uri", "generation", "metageneration", "bytes", "sha256",
            }
            or science_identity.get("uri") != science_uri
            or not isinstance(terminal_identity, dict)
            or set(terminal_identity) != {
                "uri", "generation", "metageneration", "bytes", "sha256",
            }
            or terminal_identity.get("uri") != terminal_uri
        ):
            raise RuntimeError("A7 freeze preflight object identity differs")
        receipt, science_object = _download_json_object_pinned(
            client, science_identity,
        )
        terminal, terminal_object = _download_json_object_pinned(
            client, terminal_identity,
        )
        _validate_preflight_receipt(receipt, mode=mode, manifest=manifest)
        prior_kwargs = {}
        if key == "support":
            prior_kwargs = {
                "prior_science_object": object_receipts["smoke"],
                "prior_terminal_object": terminal_objects["smoke"],
            }
        validated_terminal = a7_transport._validate_preflight_terminal_receipt(
            terminal, mode=mode, science_object=science_object, claim=claim,
            code_sha=code_sha, image=image,
            protocol_sha256=PROTOCOL_SHA256,
            a3_logical_release_sha256=str(a3_release_sha256),
            **prior_kwargs,
        )
        if validated_terminal["execution"].get("job_uid") != claim[
            "claim"
        ].get("job_uid"):
            raise RuntimeError("A7 preflight terminal job identity differs")
        if key == "support" and (
            receipt["support"].get("passes") is not True
            or validated_terminal.get("support_passed") is not True
        ):
            raise RuntimeError("A7 unsupported preflight cannot be frozen")
        receipts[key] = receipt
        object_receipts[key] = science_object
        terminal_receipts[key] = validated_terminal
        terminal_objects[key] = terminal_object
    smoke_inventory = [
        claim_identity, object_receipts["smoke"], terminal_objects["smoke"],
    ]
    support_inventory = [
        *smoke_inventory, object_receipts["support"],
        terminal_objects["support"],
    ]
    if manifest.get("prefix_inventory_sha256") != {
        "claimed": a7_transport._inventory_sha256([claim_identity]),
        "smoke-complete": a7_transport._inventory_sha256(smoke_inventory),
        "support-complete": a7_transport._inventory_sha256(
            support_inventory,
        ),
    }:
        raise RuntimeError("A7 frozen prefix-inventory hashes differ")
    smoke_execution = terminal_receipts["smoke"]["execution"]
    support_execution = terminal_receipts["support"]["execution"]
    if (
        smoke_execution["prior_job_generation"]
        != claim["claim"]["job_generation"]
        or smoke_execution["prior_job_spec_sha256"]
        != claim["claim"]["job_spec_sha256"]
        or support_execution["prior_job_generation"]
        != smoke_execution["job_generation"]
        or support_execution["prior_job_spec_sha256"]
        != smoke_execution["job_spec_sha256"]
    ):
        raise RuntimeError("A7 preflight job-generation chain differs")
    return {
        "manifest": manifest,
        "manifest_object": manifest_object,
        "smoke_receipt": receipts["smoke"],
        "smoke_object": object_receipts["smoke"],
        "support_receipt": receipts["support"],
        "support_object": object_receipts["support"],
        "smoke_terminal_receipt": terminal_receipts["smoke"],
        "smoke_terminal_object": terminal_objects["smoke"],
        "support_terminal_receipt": terminal_receipts["support"],
        "support_terminal_object": terminal_objects["support"],
        "source_artifact_lock_sha256": manifest[
            "source_artifact_lock_sha256"
        ],
        "implementation_sha256": manifest["implementation_sha256"],
    }


def _attach_in_image_science_replay(
    report: dict[str, Any], *, manifest: dict[str, Any], sources: Any,
    players: Any,
) -> None:
    """Run the independent finisher replay inside the immutable image.

    The image digest and the separately hashed finisher bytes are already
    frozen in ``manifest``.  Retaining this receipt closes the Python/runtime
    gap between the Cloud Run image and the later local harvest process.
    """
    if "in_image_science_replay" in report or "output" in report:
        raise RuntimeError("A7 in-image replay boundary is not pristine")
    reader = a7_transport._StorageReader()
    replay = a7_transport._replay_science(
        report, manifest, lambda: (sources, players), reader.load,
    )
    raw = (json.dumps(
        replay, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")
    report["in_image_science_replay"] = {
        "version": "a7-in-image-science-replay-v1",
        "image": manifest["image"]["uri"],
        "finisher_sha256": manifest["implementation_sha256"]["finisher"],
        "receipt": replay,
        "receipt_sha256": sha256(raw).hexdigest(),
    }


def _download_artifact_pinned(
    client: storage.Client, uri: str, digest: str, *, generation: str,
    expected_bytes: int,
) -> tuple[dict[str, np.ndarray], dict[str, str | int]]:
    """Read exactly the generation whose metadata is receipted."""
    bucket_name, object_name = _parse_gcs(uri)
    bucket = client.bucket(bucket_name)
    if not str(generation).isdigit() or int(expected_bytes) <= 0:
        raise RuntimeError("A7 source object metadata differs")
    pinned = bucket.blob(object_name, generation=int(generation))
    raw = pinned.download_as_bytes(if_generation_match=int(generation))
    pinned.reload(if_generation_match=int(generation))
    metageneration = str(pinned.metageneration or "")
    if not metageneration.isdigit() or str(pinned.generation) != generation or (
        int(pinned.size or 0) != int(expected_bytes)
    ) or (
        len(raw) != int(expected_bytes)
    ):
        raise RuntimeError("A7 source object changed during pinned download")
    if sha256(raw).hexdigest() != digest:
        raise RuntimeError("A7 source object content hash differs")
    artifact = decode_score_artifact(raw, digest)
    required = {"cand_ix", "totals", "player_ids", "player_draws"}
    if not required <= set(artifact):
        raise RuntimeError("A7 source artifact lacks candidate/player worlds")
    return artifact, {
        "uri": uri,
        "sha256": digest,
        "generation": generation,
        "metageneration": metageneration,
        "bytes": len(raw),
        "md5_hash": str(pinned.md5_hash or ""),
        "crc32c": str(pinned.crc32c or ""),
    }


def _actual_sql() -> str:
    """Return the outcome query only after every score-free gate passes."""
    return f"""
SELECT panel_run_id, season, week, cand_ix, players, actual_score
FROM `{PROJECT}.nfl_predictions.replay_candidates_staging`
WHERE panel_run_id IN UNNEST(@panel_ids)
ORDER BY panel_run_id, season, week, cand_ix
"""


def _identity(lineup) -> tuple[str, ...]:
    result = tuple(sorted(str(value) for value in lineup.ids))
    if len(result) != 9 or len(set(result)) != 9:
        raise RuntimeError("A7 source candidate identity is malformed")
    return result


def _candidate_identities(batch) -> list[list[str]]:
    result = [list(_identity(lineup)) for lineup in batch.candidates]
    if len(result) != len({tuple(value) for value in result}):
        raise RuntimeError("A7 combined candidate identities repeat")
    return result


def _candidate_tags(batch) -> list[list[str]]:
    result = []
    for lineup in batch.candidates:
        tags = [str(value) for value in batch.all_tags.get(lineup.ids, ())]
        if not tags or len(tags) != len(set(tags)):
            raise RuntimeError("A7 combined candidate tags differ")
        result.append(sorted(tags))
    return result


def _validate_baseline(value: dict[str, Any]) -> tuple[float, dict[str, int]]:
    money = value.get("money_book", {})
    expected = {
        "label": "registered production 80-entry book, realized weekly best",
        "mean_weekly_best": 176.06,
        "slates": 54,
        "at_or_above": {
            "187": 17, "194": 8, "200": 7, "210": 6,
            "220": 3, "230": 1, "240": 0,
        },
    }
    if any(money.get(key) != expected[key] for key in expected):
        raise RuntimeError("A7 registered money baseline differs")
    return float(money["mean_weekly_best"]), {
        str(key): int(count) for key, count in money["at_or_above"].items()
    }


def _baseline_vector() -> dict[tuple[int, int], float]:
    value = json.loads(BASELINE_VECTOR_PATH.read_text(encoding="utf-8"))
    if value.get("mechanical_passes") is not True or value.get("failures") != []:
        raise RuntimeError("A7 registered weekly baseline source did not pass")
    rows = value.get("result", {}).get("slates", [])
    result = {
        (int(row["season"]), int(row["week"])): float(
            row["fixed_budget_confirmation"]["CBWU"]["selected_best"]
        )
        for row in rows
    }
    expected = {(season, week) for season in (2023, 2024, 2025)
                for week in range(1, 19)}
    if len(rows) != 54 or set(result) != expected or not all(
        np.isfinite(value) for value in result.values()
    ):
        raise RuntimeError("A7 registered weekly baseline vector differs")
    return result


def _source_report() -> tuple[
    dict[tuple[int, int], dict],
    dict[tuple[str, int, int], dict[str, Any]],
    dict[str, Any],
]:
    value = json.loads(SOURCE_REPORT_PATH.read_text(encoding="utf-8"))
    if value.get("uses_realized_outcomes") is not False or value.get(
        "aggregate", {}
    ).get("passes_scorefree_gate") is not True or len(value.get("slates", [])) != 54:
        raise RuntimeError("A7 CBWU source report did not pass")
    by_slate = {
        (int(row["season"]), int(row["week"])): row
        for row in value["slates"]
    }
    if len(by_slate) != 54:
        raise RuntimeError("A7 CBWU source slate keys repeat")
    artifacts = value.get("source_artifacts", [])
    by_artifact: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in artifacts:
        key = (str(row["panel_run_id"]), int(row["season"]), int(row["week"]))
        if key in by_artifact or key[0] not in SOURCE_PANEL_IDS or not str(
            row.get("generation", "")
        ).isdigit() or int(row.get("bytes", 0)) <= 0:
            raise RuntimeError("A7 frozen source artifact identity differs")
        by_artifact[key] = {
            "panel_run_id": key[0], "season": key[1], "week": key[2],
            "uri": str(row["uri"]), "sha256": str(row["sha256"]),
            "generation": str(row["generation"]),
            "bytes": int(row["bytes"]),
            "source_rows": int(row["candidate_rows"]),
        }
    expected_artifacts = {
        (panel, season, week) for panel in SOURCE_PANEL_IDS
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if len(artifacts) != 270 or set(by_artifact) != expected_artifacts:
        raise RuntimeError("A7 frozen source artifact population differs")
    return by_slate, by_artifact, value


def _locked_source_artifacts(
    source_map: dict[tuple[str, int, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    panel_order = {panel: index for index, panel in enumerate(SOURCE_PANEL_IDS)}
    return sorted(
        [{
            "panel_run_id": row["panel_run_id"],
            "season": row["season"],
            "week": row["week"],
            "uri": row["uri"],
            "generation": row["generation"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
            "candidate_rows": row["source_rows"],
        } for row in source_map.values()],
        key=lambda row: (
            int(row["season"]), int(row["week"]),
            panel_order[str(row["panel_run_id"])],
        ),
    )


def _prepare_slate(
    *,
    season: int,
    week: int,
    sources,
    players,
    source_map: dict[tuple[str, int, int], dict[str, Any]],
    expected: dict[str, Any],
    gcs,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog = players[
        players.season.astype(int).eq(season)
        & players.week.astype(int).eq(week)
    ].copy()
    books = {}
    artifacts = []
    for seed, panel_id in enumerate(SOURCE_PANEL_IDS):
        group = sources[
            sources.panel_run_id.astype(str).eq(panel_id)
            & sources.season.astype(int).eq(season)
            & sources.week.astype(int).eq(week)
        ].copy()
        source = source_map[(panel_id, season, week)]
        artifact, receipt = _download_artifact_pinned(
            gcs, str(source["uri"]), str(source["sha256"]),
            generation=str(source["generation"]),
            expected_bytes=int(source["bytes"]),
        )
        books[f"R{seed}"] = _candidate_batch(group, artifact, catalog)
        artifacts.append({
            "seed": int(seed), "panel_run_id": panel_id,
            "season": int(season), "week": int(week),
            "candidate_rows": int(source["source_rows"]), **receipt,
        })

    order = tuple(books)
    if order != ("R0", "R1", "R2", "R3", "R4"):
        raise RuntimeError("A7 source block order differs")
    combined = combine_cbwu_books(
        books, order, expected_worlds_per_book=WORLDS_PER_BLOCK,
    )
    identities = _candidate_identities(combined)
    tags = _candidate_tags(combined)
    books_selected = select_books(np.asarray(combined.candidate_totals))
    control_ids = selected_identities(identities, books_selected["control"])
    if expected.get("order_invariant") is not True or control_ids != expected.get(
        "control", {}
    ).get("identities"):
        raise RuntimeError("A7 control exact-80 source reproduction differs")

    arms = {}
    for arm in ("control", "treatment"):
        selected = books_selected[arm]
        if not all(_is_production_legal(combined.candidates[index]) for index in selected):
            raise RuntimeError(f"A7 {arm} selected an illegal roster")
        selected_ids = selected_identities(identities, selected)
        arms[arm] = {
            "selector_env": dict(CONTROL_ENV if arm == "control" else TREATMENT_ENV),
            "indices": selected,
            "identities": selected_ids,
            "identity_overlap_with_control": (
                ENTRY_COUNT if arm == "control" else len(
                    {tuple(value) for value in control_ids}
                    & {tuple(value) for value in selected_ids}
                )
            ),
            "candidate_source_counts": candidate_source_counts(selected, tags),
            "selected_source_tags": [tags[int(index)] for index in selected],
            "scorefree": scorefree_book_receipt(
                candidate_totals=np.asarray(combined.candidate_totals),
                candidate_identities=identities,
                selected=selected,
                player_ids=combined.player_ids,
                player_draws=np.asarray(combined.row_draws),
            ),
        }
    row = {
        "season": int(season), "week": int(week),
        "uses_realized_outcomes": False,
        "candidate_budget": int(len(combined.candidates)),
        "world_count": int(combined.candidate_totals.shape[1]),
        "candidate_identities": identities,
        "candidate_identities_sha256": sha256(json.dumps(
            identities, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "candidate_tags_sha256": sha256(json.dumps(
            tags, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "combined_input_receipts": {
            "candidate_totals": _array_receipt(np.asarray(
                combined.candidate_totals,
            )),
            "player_draws": _array_receipt(np.asarray(combined.row_draws)),
            "player_ids_sha256": sha256(json.dumps(
                [str(value) for value in combined.player_ids],
                separators=(",", ":"),
            ).encode()).hexdigest(),
        },
        "candidate_pool_shared_across_arms": True,
        "control_source_reproduced": True,
        "control": arms["control"],
        "treatment": arms["treatment"],
    }
    return row, artifacts


def _actual_maps(sources, actuals) -> dict[tuple[int, int], dict[tuple[str, ...], float]]:
    source_keys = {
        (str(row.panel_run_id), int(row.season), int(row.week), int(row.cand_ix),
         str(row.players))
        for row in sources.itertuples(index=False)
    }
    actual_keys = {
        (str(row.panel_run_id), int(row.season), int(row.week), int(row.cand_ix),
         str(row.players))
        for row in actuals.itertuples(index=False)
    }
    if source_keys != actual_keys or len(actuals) != len(source_keys):
        raise RuntimeError("A7 outcome rows differ from the source candidate keys")
    grouped: dict[tuple[int, int], dict[tuple[str, ...], float]] = defaultdict(dict)
    for row in actuals.itertuples(index=False):
        identity = tuple(sorted(value for value in str(row.players).split(",") if value))
        if len(identity) != 9 or len(set(identity)) != 9:
            raise RuntimeError("A7 outcome roster identity is malformed")
        value = float(row.actual_score)
        if not np.isfinite(value):
            raise RuntimeError("A7 outcome score is non-finite")
        key = (int(row.season), int(row.week))
        prior = grouped[key].get(identity)
        if prior is not None and prior != value:
            raise RuntimeError("A7 duplicate roster outcomes disagree")
        grouped[key][identity] = value
    if len(grouped) != 54:
        raise RuntimeError("A7 outcome slate population differs")
    return dict(grouped)


def _retained_actual_query(
    actuals: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Normalize and bind every native outcome row, not only admitted rows."""
    if tuple(str(value) for value in actuals.columns) != ACTUAL_QUERY_COLUMNS:
        raise RuntimeError("A7 actual query schema differs")
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, int, int, int, str]] = set()
    for raw in actuals.to_dict("records"):
        row = {
            "panel_run_id": str(raw["panel_run_id"]),
            "season": int(raw["season"]),
            "week": int(raw["week"]),
            "cand_ix": int(raw["cand_ix"]),
            "players": str(raw["players"]),
            "actual_score": float(raw["actual_score"]),
        }
        if (
            row["panel_run_id"] not in SOURCE_PANEL_IDS
            or row["season"] not in (2023, 2024, 2025)
            or row["week"] not in range(1, 19)
            or row["cand_ix"] < 0
            or not row["players"]
            or not math.isfinite(row["actual_score"])
        ):
            raise RuntimeError("A7 retained actual-query row differs")
        key = (
            row["panel_run_id"], row["season"], row["week"],
            row["cand_ix"], row["players"],
        )
        if key in keys:
            raise RuntimeError("A7 retained actual-query keys repeat")
        keys.add(key)
        rows.append(row)
    rows.sort(key=lambda row: (
        row["panel_run_id"], row["season"], row["week"], row["cand_ix"],
        row["players"],
    ))
    receipt = _query_rows_content_receipt(
        rows, ACTUAL_QUERY_COLUMNS, require_encoded_order=False,
    )
    return rows, receipt


def run(
    *, output_uri: str | None, smoke: bool, support_census: bool = False,
) -> dict[str, Any]:
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if smoke and support_census:
        raise RuntimeError("A7 outcome-blind modes are mutually exclusive")
    outcome_blind = smoke or support_census
    freeze_env_present = any(os.environ.get(name, "").strip() for name in (
        "A7_FREEZE_MANIFEST_URI", "A7_FREEZE_MANIFEST_GENERATION",
        "A7_FREEZE_MANIFEST_SHA256",
    ))
    if not outcome_blind:
        if output_uri != OUTPUT_URI:
            raise RuntimeError("A7 output URI differs")
        validate_execution_identity(code_sha, image)
    else:
        if output_uri is not None:
            raise RuntimeError("A7 outcome-blind preflight cannot name an output URI")
        if freeze_env_present:
            raise RuntimeError("A7 outcome-blind preflight cannot consume a freeze manifest")
        _validate_preflight_identity(code_sha, image)

    local_receipts = verify_local_sha256({
        "protocol": (PROTOCOL_PATH, PROTOCOL_SHA256),
        "source_report": (SOURCE_REPORT_PATH, SOURCE_REPORT_SHA256),
        "baseline": (BASELINE_PATH, BASELINE_SHA256),
        "baseline_vector": (BASELINE_VECTOR_PATH, BASELINE_VECTOR_SHA256),
    })
    validate_scorefree_queries()
    expected_by_slate, locked_source_map, source_report = _source_report()
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_mean, baseline_counts = _validate_baseline(baseline)

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    freeze_evidence = None if outcome_blind else _load_freeze_evidence(
        gcs, code_sha=code_sha, image=image,
        local_source_receipts=local_receipts,
        locked_source_artifacts=_locked_source_artifacts(locked_source_map),
    )
    params = [bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SOURCE_PANEL_IDS),
    )]
    sources = _query(bq, SOURCE_SQL, params)
    players = _query(bq, PLAYER_SQL)
    query_content_receipts = {
        "candidate_source": _query_content_receipt(
            sources, SOURCE_QUERY_COLUMNS,
        ),
        "player_source": _query_content_receipt(
            players, PLAYER_QUERY_COLUMNS,
        ),
    }
    if freeze_evidence is not None and query_content_receipts != (
        freeze_evidence["manifest"]["query_content_receipts"]
    ):
        raise RuntimeError("A7 source query content differs from freeze manifest")
    preflight = resolve_panel_artifacts(
        sources.to_dict("records"), panel_ids=SOURCE_PANEL_IDS,
        expected_slates=54,
    )
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("A7 forensic player manifest differs")
    slates = [tuple(int(value) for value in key) for key in preflight["slates"]]
    if set(slates) != set(expected_by_slate) or len(slates) != 54:
        raise RuntimeError("A7 source slate population differs")
    query_source_map = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in preflight["artifacts"]
    }
    if set(query_source_map) != set(locked_source_map):
        raise RuntimeError("A7 query source artifact population differs")
    for key, locked in locked_source_map.items():
        queried = query_source_map[key]
        if any(queried[field] != locked[field] for field in (
            "panel_run_id", "season", "week", "uri", "sha256", "source_rows",
        )):
            raise RuntimeError("A7 query source differs from frozen artifact lock")
    source_map = locked_source_map
    selected_slates = [(2023, 1)] if smoke else sorted(slates)
    records = []
    artifact_receipts = []
    for season, week in selected_slates:
        row, receipts = _prepare_slate(
            season=season, week=week, sources=sources, players=players,
            source_map=source_map, expected=expected_by_slate[(season, week)],
            gcs=gcs,
        )
        records.append(row)
        artifact_receipts.extend(receipts)

    report: dict[str, Any] = {
        "version": VERSION,
        "run_id": RUN_ID,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_report_sha256": SOURCE_REPORT_SHA256,
        "baseline_sha256": BASELINE_SHA256,
        "baseline_vector_sha256": BASELINE_VECTOR_SHA256,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "local_source_receipts": local_receipts,
        "implementation_receipts": _implementation_receipts(),
        "query_content_receipts": query_content_receipts,
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_preflight": {
            key: preflight[key]
            for key in ("panel_ids", "slates", "slate_count", "artifact_count")
        },
        "source_artifacts": artifact_receipts,
        "selector": {
            "control_env": CONTROL_ENV,
            "treatment_env": TREATMENT_ENV,
            "ladder_spec": LADDER_SPEC,
            "entry_count": ENTRY_COUNT,
        },
        "smoke": bool(smoke),
        "support_census": bool(support_census),
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "slates": records,
    }
    if freeze_evidence is not None:
        manifest_object = freeze_evidence["manifest_object"]
        report.update({
            "freeze_manifest_uri": manifest_object["uri"],
            "freeze_manifest_generation": manifest_object["generation"],
            "freeze_manifest_sha256": manifest_object["sha256"],
            "freeze_evidence": freeze_evidence,
        })
    if outcome_blind:
        if support_census:
            report["support"] = build_support_census(records)
        # Exercise canonical finite serialization; never upload preflight output.
        json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return report

    current_support = build_support_census(records)
    support_report = dict(report)
    support_report["support_census"] = True
    support_report["support"] = current_support
    current_support_receipt = _preflight_receipt(support_report)
    if current_support_receipt != freeze_evidence["support_receipt"]:
        raise RuntimeError("A7 full inputs differ from frozen support census")

    scorefree = aggregate_scorefree(records)
    report["scorefree"] = scorefree
    if scorefree["conditions"]["realism_r3_supported"] is not True:
        raise RuntimeError("A7 score-free realism support disappeared")
    if scorefree["mechanics_passes"] is not True:
        raise RuntimeError("A7 score-free mechanism gate failed")
    if scorefree["conditions"]["realism_r3_noninferior"] is not True:
        report.update({
            "disposition": "tail-artifact-risk-phase-s",
            "production_law_scorefree_transfer_licensed": False,
            "prospective_shadow_licensed": False,
        })
        _attach_in_image_science_replay(
            report, manifest=freeze_evidence["manifest"], sources=sources,
            players=players,
        )
        payload = (json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n").encode("utf-8")
        report["output"] = _upload_create_only(gcs, str(output_uri), payload)
        return report

    # First and only outcome-facing boundary. Nothing above formats this SQL.
    actuals = _query(bq, _actual_sql(), params)
    actual_query_rows, actual_query_content_receipt = _retained_actual_query(
        actuals,
    )
    actual_maps = _actual_maps(sources, actuals)
    report["actual_query_rows"] = actual_query_rows
    report["actual_query_content_receipt"] = actual_query_content_receipt
    baseline_vector = _baseline_vector()
    for row in records:
        key = (int(row["season"]), int(row["week"]))
        actual_by_identity = actual_maps[key]
        try:
            candidate_actual_scores = [
                float(actual_by_identity[tuple(identity)])
                for identity in row["candidate_identities"]
            ]
        except KeyError as exc:
            raise RuntimeError(
                "A7 admitted candidate lacks a native outcome row",
            ) from exc
        if not candidate_actual_scores or not all(
            math.isfinite(value) for value in candidate_actual_scores
        ):
            raise RuntimeError("A7 admitted candidate score vector differs")
        row["candidate_actual_scores"] = candidate_actual_scores
        row["pool_c"] = float(max(candidate_actual_scores))
        row["control"]["realized"] = score_ordered_book(
            row["control"]["identities"], actual_by_identity,
        )
        row["uses_realized_outcomes"] = True

    # Fail before constructing any treatment outcome summary unless the exact
    # registered control book reproduces its frozen historical baseline.
    validate_control_baseline(
        records, baseline_mean=baseline_mean, baseline_counts=baseline_counts,
        baseline_vector=baseline_vector,
    )
    for row in records:
        key = (int(row["season"]), int(row["week"]))
        row["treatment"]["realized"] = score_ordered_book(
            row["treatment"]["identities"], actual_maps[key],
        )

    # Baseline reproduction is inside aggregate_outcomes and occurs before a
    # disposition is returned. A mismatch invalidates the one-shot arm.
    outcome = aggregate_outcomes(
        records, scorefree=scorefree, baseline_mean=baseline_mean,
        baseline_counts=baseline_counts, baseline_vector=baseline_vector,
    )
    report.update({
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "outcome": outcome,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": outcome[
            "production_law_scorefree_transfer_licensed"
        ],
        "prospective_shadow_licensed": False,
    })
    _attach_in_image_science_replay(
        report, manifest=freeze_evidence["manifest"], sources=sources,
        players=players,
    )
    payload = (json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")
    report["output"] = _upload_create_only(gcs, str(output_uri), payload)
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-uri")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--support-census", action="store_true")
    parser.add_argument("--smoke-receipt", type=Path)
    parser.add_argument("--preflight-receipt-uri")
    parser.add_argument("--freeze-manifest-uri")
    parser.add_argument("--freeze-manifest-generation")
    parser.add_argument("--freeze-manifest-sha256")
    args = parser.parse_args()
    preflight_modes = int(args.smoke) + int(args.support_census)
    if preflight_modes > 1 or (args.smoke_receipt is not None and not preflight_modes):
        parser.error(
            "choose at most one of --smoke/--support-census; local receipt "
            "requires an outcome-blind mode",
        )
    if bool(args.preflight_receipt_uri) != bool(preflight_modes):
        parser.error("outcome-blind mode requires --preflight-receipt-uri")
    freeze_args = (
        args.freeze_manifest_uri, args.freeze_manifest_generation,
        args.freeze_manifest_sha256,
    )
    if preflight_modes:
        if any(value is not None for value in freeze_args):
            parser.error("outcome-blind mode forbids freeze-manifest arguments")
    elif (
        any(value is None for value in freeze_args)
        or freeze_args != (
            os.environ.get("A7_FREEZE_MANIFEST_URI"),
            os.environ.get("A7_FREEZE_MANIFEST_GENERATION"),
            os.environ.get("A7_FREEZE_MANIFEST_SHA256"),
        )
    ):
        parser.error("full mode requires matching freeze-manifest args and env")
    report = run(
        output_uri=args.output_uri, smoke=args.smoke,
        support_census=args.support_census,
    )
    if preflight_modes:
        receipt = _preflight_receipt(report)
        expected_uri = SMOKE_RECEIPT_URI if args.smoke else SUPPORT_RECEIPT_URI
        if args.preflight_receipt_uri != expected_uri:
            raise RuntimeError("A7 preflight receipt URI differs")
        payload = (json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n").encode("utf-8")
        upload = _upload_create_only(
            storage.Client(project=PROJECT), expected_uri, payload,
        )
        report["preflight_receipt"] = receipt
        report["preflight_receipt_object"] = upload
        print("A7_PREFLIGHT_RECEIPT " + json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))
        print("A7_PREFLIGHT_RECEIPT_OBJECT " + json.dumps(
            upload, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))
    if args.smoke_receipt is not None:
        if args.smoke_receipt.exists():
            raise RuntimeError("A7 immutable smoke receipt already exists")
        args.smoke_receipt.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(
            report["preflight_receipt"], sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ) + "\n").encode("utf-8")
        with args.smoke_receipt.open("xb") as handle:
            handle.write(payload)
        digest_path = args.smoke_receipt.with_suffix(
            args.smoke_receipt.suffix + ".sha256"
        )
        with digest_path.open("x", encoding="utf-8") as handle:
            handle.write(
                f"{sha256(payload).hexdigest()}  "
                f"{args.smoke_receipt.name}\n"
            )
    print(json.dumps({
        "version": report["version"],
        "run_id": report["run_id"],
        "smoke": report["smoke"],
        "support_census": report["support_census"],
        "uses_realized_outcomes": report["uses_realized_outcomes"],
        "slates": len(report["slates"]),
        "scorefree_passes": report.get("scorefree", {}).get("passes"),
        "disposition": (
            report.get("outcome", {}).get("disposition")
            or report.get("disposition")
        ),
        "output": report.get("output"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
