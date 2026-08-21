#!/usr/bin/env python3
"""Fail-closed launcher preflight and strict harvest for frozen A7.

The module deliberately contains no deploy, execute, retry, cancel, upload, or
historical-score query path.  Before opening the result body it validates the
local launch receipts, strict terminal Cloud Run metadata, the live lease, and
the exact object inventory.  It then generation-pins the result and reruns only
the registered outcome-blind source queries and source-artifact reconstruction
to replay selection, score-free receipts, retained realized-book summaries,
and the frozen disposition.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np
from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import bigquery, storage


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books  # noqa: E402
from nfl_dfs.research.a7_select_ladder import (  # noqa: E402
    CONTROL_ENV,
    ENTRY_COUNT,
    LADDER_SPEC,
    PREFIX_COUNTS,
    PROTOCOL_ID,
    REPORT_THRESHOLDS,
    TREATMENT_ENV,
    aggregate_outcomes,
    aggregate_scorefree,
    candidate_source_counts,
    score_ordered_book,
    scorefree_book_receipt,
    select_books,
    selected_identities,
    validate_control_baseline,
)
from nfl_dfs.research.portfolio_effective_rank import (  # noqa: E402
    decode_score_artifact,
)
from nfl_dfs.research.source_preflight import (  # noqa: E402
    resolve_panel_artifacts,
)
from run_cbwu_seed_order_audit import (  # noqa: E402
    FORENSIC_MANIFEST_SHA256,
    PLAYER_TABLE,
    PROJECT,
    SOURCE_PANEL_IDS,
    SOURCE_SQL,
    _candidate_batch,
    _query,
)
from run_exact_n_scorefree import _is_production_legal  # noqa: E402


REGION = "us-central1"
RUN_ID = PROTOCOL_ID
V1_RUN_ID = "20260820-a7-select-ladder-phase-s-incumbent-v1"
V1_FAILURE_RELEASE_URI = (
    "gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/"
    f"{V1_RUN_ID}/preflight/failed-preflight-logical-release.json"
)
V1_FAILURE_RELEASE_OBJECT_RECEIPT_VERSION = (
    "a7-select-ladder-failed-preflight-logical-release-object-receipt-v1"
)
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/"
    f"{RUN_ID}"
)
RESULT_URI = f"{PREFIX}/result.json"
SMOKE_URI = f"{PREFIX}/preflight/real-artifact-smoke.json"
SUPPORT_URI = f"{PREFIX}/preflight/support-census.json"
SMOKE_TERMINAL_URI = f"{PREFIX}/preflight/real-artifact-smoke-terminal.json"
SUPPORT_TERMINAL_URI = f"{PREFIX}/preflight/support-census-terminal.json"
FREEZE_URI = f"{PREFIX}/preflight/freeze-manifest.json"
JOB_CLAIM_URI = f"{PREFIX}/preflight/job-claim.json"
RELEASE_INTENT_URI = f"{PREFIX}/lease-release-intent.json"
LEASE_URI = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
DEFAULT_OUT = ROOT / "reports/a7-select-ladder-runs" / RUN_ID
DEFAULT_PREFLIGHT_OUT = ROOT / "reports/a7-select-ladder-preflight-runs" / RUN_ID
DEFAULT_A3_RELEASE = (
    ROOT / "reports/stack-relaxation-carve-runs/"
    "20260819-stack-relaxation-carve-v1/logical-release.json"
)
DEFAULT_V1_FAILURE_RELEASE = (
    ROOT / "reports/a7-select-ladder-preflight-runs" / V1_RUN_ID
    / "failed-preflight-logical-release.json"
)
DEFAULT_V1_FAILURE_RELEASE_OBJECT = (
    ROOT / "reports/a7-select-ladder-preflight-runs" / V1_RUN_ID
    / "failed-preflight-logical-release-object.json"
)
PENDING_NAME = ".strict-harvest.pending"
JOB = "atlas-minimal-c-s2023-w1-v1"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
BUILD_SERVICE_ACCOUNT = (
    "projects/nfl-predictions-503414/serviceAccounts/" + SERVICE_ACCOUNT
)
BUILD_LOGS_BUCKET = "gs://817589974517.cloudbuild-logs.googleusercontent.com"
GIT_SOURCE_URL = "https://github.com/espechtsoftware/nfl-predictions.git"
CPU = "4"
MEMORY = "16Gi"
TIMEOUT_SECONDS = "7200"
PROTOCOL_PATH = Path(
    "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol-v2.md"
)
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
IMPLEMENTATION_PATHS = {
    "selector": "src/nfl_dfs/optimizer/lineup.py",
    "scientific_module": "src/nfl_dfs/research/a7_select_ladder.py",
    "paired_statistics": "src/nfl_dfs/research/paired_max_stats.py",
    "candidate_combiner": "src/nfl_dfs/inference/multiseed_portfolio.py",
    "artifact_decoder": "src/nfl_dfs/research/portfolio_effective_rank.py",
    "source_preflight": "src/nfl_dfs/research/source_preflight.py",
    "source_query_helper": "scripts/run_cbwu_seed_order_audit.py",
    "legality_helper": "scripts/run_exact_n_scorefree.py",
    "runner": "scripts/run_a7_select_ladder.py",
    "lease_tool": "scripts/historical_outcome_lease.py",
    "cloudbuild_config": "cloudbuild.yaml",
    "freeze_builder": "scripts/freeze_a7_select_ladder.py",
    "launcher": "scripts/cloud_a7_select_ladder.sh",
    "watcher": "scripts/watch_a7_select_ladder_queue.sh",
    "finisher": "scripts/finish_a7_select_ladder.py",
    "v1_failure_closer": (
        "scripts/close_a7_select_ladder_failed_preflight_v1.py"
    ),
}
CORE_IMPLEMENTATION_KEYS = tuple(
    key for key in IMPLEMENTATION_PATHS
    if key not in {
        "lease_tool", "cloudbuild_config", "freeze_builder", "launcher",
        "watcher", "finisher", "v1_failure_closer",
    }
)
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
    "bootstrap_quantiles": [0.025, 0.975],
    "bootstrap_quantile_method": "linear",
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
OPERATOR_APPROVAL_BASIS = (
    "user-authorized-proof-before-adoption-implementation-2026-08-20"
)
BASELINE_COUNTS = {
    "187": 17, "194": 8, "200": 7, "210": 6,
    "220": 3, "230": 1, "240": 0,
}
ALLOWED_DISPOSITIONS = {
    "tail-artifact-risk-phase-s",
    "rejected-phase-s-dose",
    "historical-null-or-inconclusive-phase-s",
    "historical-positive-phase-s",
}

# Keep the strict-harvest replay query byte-for-byte aligned with the v2
# runner.  Only SQL NULL is normalized; every other non-finite value reaches
# _canonical_query_value and remains fatal.
PLAYER_SQL = f"""
SELECT manifest_sha256, season, week, player_id, player_name, position,
       team, opponent, game_id, salary,
       COALESCE(mean_projection,0.0) AS mean_projection
FROM `{PLAYER_TABLE}`
WHERE scope = 'phase-s-cbwu-54'
ORDER BY season, week, player_id
"""

FREEZE_MANIFEST_KEYS = frozenset({
    "version", "status", "run_id", "protocol_id", "protocol", "code",
    "image", "operator_approved", "operator_approval_basis",
    "operator_approvals", "frozen_law", "implementation_sha256",
    "local_source_receipts", "query_content_receipts", "preflights",
    "historical_looks", "source_report", "baseline", "baseline_vector",
    "source_artifacts", "source_artifact_lock_sha256",
    "uses_realized_outcomes", "production_change_licensed",
    "production_law_scorefree_transfer_licensed", "prospective_shadow_licensed",
    "job_claim",
    "prefix_inventory_sha256",
})
PREFLIGHT_RECEIPT_KEYS = frozenset({
    "version", "run_id", "protocol_id", "mode", "code_sha", "image",
    "protocol_sha256", "source_report_sha256", "baseline_sha256",
    "baseline_vector_sha256", "forensic_manifest_sha256",
    "local_source_receipts", "implementation_receipts",
    "query_content_receipts", "frozen_choices", "source_panels",
    "source_preflight", "source_artifact_count",
    "source_artifacts_sha256", "slates", "support",
    "uses_realized_outcomes", "actual_score_query_executed",
    "production_change_licensed", "prospective_shadow_licensed",
    "production_law_scorefree_transfer_licensed",
})
PREFLIGHT_SLATE_KEYS = frozenset({
    "season", "week", "candidate_budget", "world_count",
    "candidate_identities_sha256", "candidate_tags_sha256",
    "combined_input_receipts", "scorefree_receipt_sha256",
})
SUPPORT_CENSUS_KEYS = frozenset({
    "version", "uses_realized_outcomes", "slates", "definition",
    "minimum_aggregate_events_per_arm", "r3_positive_gain_events_by_block",
    "conditions", "passes",
})
SUPPORT_CONDITION_KEYS = frozenset({
    "control_r3_events_at_least_100",
    "treatment_r3_events_at_least_100",
    "control_r3_supported_in_every_block",
    "treatment_r3_supported_in_every_block",
})
TRANSPORT_REPAIR_ENV = {
    "finisher": "A7_FINISHER_REPAIR_SHA256",
    "launcher": "A7_LAUNCHER_REPAIR_SHA256",
    "watcher": "A7_WATCHER_REPAIR_SHA256",
}
JOB_CLAIM_KEYS = frozenset({
    "version", "run_id", "protocol_id", "protocol_sha256", "code_sha",
    "image", "claimant_phase", "a3_logical_release_sha256",
    "v1_failed_preflight_release", "job",
    "job_uid", "job_generation", "job_spec_sha256", "claimed_at",
    "uses_realized_outcomes",
    "actual_score_query_executed", "production_change_licensed",
    "production_law_scorefree_transfer_licensed",
    "prospective_shadow_licensed",
})
JOB_CLAIM_RECEIPT_KEYS = frozenset({"claim", "object"})
PREFLIGHT_LAUNCH_MANIFEST_KEYS = frozenset({
    "version", "run_id", "protocol_id", "mode", "code_sha", "image",
    "build_id", "protocol_sha256", "a3_logical_release_sha256",
    "job_claim", "job_claim_receipt_sha256", "job", "job_uid",
    "job_generation", "job_spec_sha256", "prior_job_generation",
    "prior_job_spec_sha256", "service_account", "output_uri", "tasks",
    "parallelism", "cpu", "memory", "timeout_seconds", "max_retries",
    "uses_realized_outcomes", "actual_score_query_executed",
    "production_change_licensed", "production_law_scorefree_transfer_licensed",
    "prospective_shadow_licensed", "job_update_mode",
})
PREFLIGHT_TERMINAL_KEYS = frozenset({
    "version", "run_id", "protocol_id", "mode", "code_sha", "image",
    "build_id", "protocol_sha256", "a3_logical_release_sha256",
    "job_claim_receipt_sha256", "job_claim", "execution",
    "science_object", "prefix_inventory_before_terminal",
    "prefix_inventory_before_terminal_sha256",
    "expected_inventory_after_terminal_uris", "preflight_receipt_sha256",
    "expected_inventory_after_terminal_uris_sha256",
    "support_passed", "disposition",
    "uses_realized_outcomes", "actual_score_query_executed",
    "production_change_licensed", "production_law_scorefree_transfer_licensed",
    "prospective_shadow_licensed",
})
RESULT_COMMON_KEYS = frozenset({
    "version", "run_id", "code_sha", "image", "protocol_sha256",
    "source_report_sha256", "baseline_sha256", "baseline_vector_sha256",
    "forensic_manifest_sha256", "local_source_receipts",
    "implementation_receipts", "query_content_receipts", "source_panels",
    "source_preflight", "source_artifacts", "selector", "smoke",
    "support_census", "uses_realized_outcomes", "actual_score_query_executed",
    "production_change_licensed",
    "production_law_scorefree_transfer_licensed",
    "prospective_shadow_licensed", "slates", "freeze_manifest_uri",
    "freeze_manifest_generation", "freeze_manifest_sha256", "freeze_evidence",
    "scorefree",
    "in_image_science_replay",
})
RESULT_SLATE_COMMON_KEYS = frozenset({
    "season", "week", "uses_realized_outcomes", "candidate_budget",
    "world_count", "candidate_identities", "candidate_identities_sha256",
    "candidate_tags_sha256", "combined_input_receipts",
    "candidate_pool_shared_across_arms", "control_source_reproduced",
    "control", "treatment",
})
RESULT_ARM_COMMON_KEYS = frozenset({
    "selector_env", "indices", "identities", "identity_overlap_with_control",
    "candidate_source_counts", "selected_source_tags", "scorefree",
})


ExecutionLoader = Callable[[str], dict[str, Any]]
InventoryLoader = Callable[[str], Mapping[str, dict[str, Any]]]
ObjectLoader = Callable[[str, str], tuple[dict[str, Any], bytes]]
ObjectCreator = Callable[[str, bytes], tuple[dict[str, Any], bytes]]
GitSourceLoader = Callable[[Path, str, str], bytes]
QueryLoader = Callable[[], tuple[Any, Any]]
ScienceReplayer = Callable[
    [dict[str, Any], dict[str, Any], QueryLoader, ObjectLoader],
    dict[str, Any],
]
PreflightManifestBuilder = Callable[
    [dict[str, Any], str, str, Path, GitSourceLoader], dict[str, Any]
]


@dataclass(frozen=True)
class FrozenRun:
    run_id: str
    code_sha: str
    image: str
    build_id: str
    protocol_sha256: str
    freeze_manifest_uri: str
    freeze_manifest_generation: str
    freeze_manifest_sha256: str
    freeze_validation_sha256: str
    a3_logical_release_sha256: str
    job: str
    job_uid: str
    job_generation: str
    job_spec_sha256: str = ""
    job_claim_receipt_sha256: str = ""
    service_account: str = SERVICE_ACCOUNT
    output_uri: str = RESULT_URI


@dataclass(frozen=True)
class PreflightRun:
    mode: str
    code_sha: str
    image: str
    build_id: str
    protocol_sha256: str
    a3_logical_release_sha256: str
    job_claim_receipt_sha256: str
    job_uid: str
    job_generation: str
    job_spec_sha256: str
    prior_job_generation: str
    prior_job_spec_sha256: str
    target_uri: str


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n"
    ).encode("utf-8")


def _external_json_value(raw: bytes, *, label: str) -> object:
    """Decode external command JSON without accepting ambiguous forms."""

    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject_constant(token: str) -> object:
        raise ValueError(f"nonfinite JSON constant: {token}")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"A7 {label} is not strict JSON") from exc

    def validate(item: object) -> None:
        if isinstance(item, float):
            if not math.isfinite(item):
                raise RuntimeError(f"A7 {label} contains a nonfinite number")
        elif isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise RuntimeError(f"A7 {label} contains a non-string key")
            for child in item.values():
                validate(child)
        elif isinstance(item, list):
            for child in item:
                validate(child)
        elif item is not None and not isinstance(item, (bool, int, str)):
            raise RuntimeError(f"A7 {label} contains an unsupported value")

    if not isinstance(value, (dict, list)):
        raise RuntimeError(f"A7 {label} top-level value differs")
    validate(value)
    return value


def _canonicalize_external_json(
    raw_path: Path, output_path: Path, *, label: str = "external command JSON",
) -> object:
    """Canonicalize one successfully captured external JSON response."""
    if raw_path.is_symlink() or not raw_path.is_file() or output_path.exists():
        raise RuntimeError(f"A7 {label} path state differs")
    try:
        raw = raw_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"A7 {label} is unreadable") from exc
    value = _external_json_value(raw, label=label)
    _write_new(output_path, _canonical_json(value))
    return value


def _json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"A7 {label} is not valid JSON") from exc
    if not isinstance(value, dict) or raw != _canonical_json(value):
        raise RuntimeError(f"A7 {label} is not canonical JSON")
    return value


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"A7 {label} is unreadable: {path}") from exc
    return _json_object(raw, label=label)


def _registered_baseline_vector(
    manifest: Mapping[str, Any], *, root: Path = ROOT,
) -> dict[tuple[int, int], float]:
    """Reload the exact manifest-bound 54-cell baseline source at replay."""
    block = manifest.get("baseline_vector")
    if not isinstance(block, dict) or set(block) != {"path", "sha256"} or \
            not isinstance(block.get("path"), str):
        raise RuntimeError("A7 baseline-vector binding differs")
    digest = _hex(
        block.get("sha256"), length=64, label="baseline-vector SHA",
    )
    relative = Path(block["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("A7 baseline-vector path differs")
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("A7 baseline-vector source is absent")
    raw = path.read_bytes()
    if _sha_bytes(raw) != digest:
        raise RuntimeError("A7 baseline-vector source bytes differ")
    value = _external_json_value(raw, label="baseline-vector source")
    if not isinstance(value, dict) or value.get(
        "mechanical_passes"
    ) is not True or value.get("failures") != []:
        raise RuntimeError("A7 baseline-vector source did not pass")
    result_block = value.get("result")
    rows = result_block.get("slates") if isinstance(result_block, dict) else None
    if not isinstance(rows, list) or len(rows) != 54:
        raise RuntimeError("A7 baseline-vector slate population differs")
    expected_order = [
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    ]
    vector: dict[tuple[int, int], float] = {}
    order: list[tuple[int, int]] = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get("season")) is not int or \
                type(row.get("week")) is not int:
            raise RuntimeError("A7 baseline-vector slate row differs")
        key = (row["season"], row["week"])
        fixed = row.get("fixed_budget_confirmation")
        cbwu = fixed.get("CBWU") if isinstance(fixed, dict) else None
        score = cbwu.get("selected_best") if isinstance(cbwu, dict) else None
        if key in vector or type(score) not in (int, float) or \
                not math.isfinite(float(score)):
            raise RuntimeError("A7 baseline-vector value differs")
        vector[key] = float(score)
        order.append(key)
    if order != expected_order:
        raise RuntimeError("A7 baseline-vector slate order differs")
    return vector


def _write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)


def _hex(value: object, *, length: int, label: str) -> str:
    text = str(value)
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", text) is None:
        raise RuntimeError(f"A7 {label} differs")
    return text


def _positive_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise RuntimeError(f"A7 {label} differs")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"A7 {label} differs") from exc
    if result <= 0 or str(value) != str(result):
        raise RuntimeError(f"A7 {label} differs")
    return result


def _json_nonnegative_int(value: object, *, label: str) -> int:
    """Decode one JSON integer without Python's bool/int coercions."""
    if type(value) is not int or value < 0:
        raise RuntimeError(f"A7 {label} differs")
    return value


def _json_positive_int(value: object, *, label: str) -> int:
    result = _json_nonnegative_int(value, label=label)
    if result == 0:
        raise RuntimeError(f"A7 {label} differs")
    return result


def _exact_json_value(value: object, expected: object) -> bool:
    """Compare JSON values without treating booleans as integers."""
    return _canonical_json(value) == _canonical_json(expected)


def _finite(value: object, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"A7 {label} is not numeric") from exc
    if not math.isfinite(result):
        raise RuntimeError(f"A7 {label} is not finite")
    return result


def _git_blob(root: Path, code_sha: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{code_sha}:{relative}"],
        check=True, capture_output=True,
    ).stdout


def _git_archive_sha(root: Path, code_sha: str) -> str:
    process = subprocess.Popen(
        ["git", "-C", str(root), "archive", "--format=tar", code_sha],
        stdout=subprocess.PIPE,
    )
    assert process.stdout is not None
    digest = sha256()
    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(chunk)
    if process.wait() != 0:
        raise RuntimeError("A7 frozen source archive cannot be reconstructed")
    return digest.hexdigest()


def _validate_implementation_sources(
    implementation: Mapping[str, Any], *, code_sha: str, root: Path,
    git_source_loader: GitSourceLoader,
) -> dict[str, str]:
    if set(implementation) != set(IMPLEMENTATION_PATHS):
        raise RuntimeError("A7 freeze implementation population differs")
    repairs: dict[str, str] = {}
    for key, relative in IMPLEMENTATION_PATHS.items():
        expected = _hex(
            implementation.get(key), length=64,
            label=f"freeze implementation {key}",
        )
        local = root / relative
        if not local.is_file():
            raise RuntimeError(f"A7 frozen local source is absent: {relative}")
        current = _sha(local)
        committed = _sha_bytes(git_source_loader(root, code_sha, relative))
        if committed != expected:
            raise RuntimeError(f"A7 frozen committed source differs: {relative}")
        env_name = TRANSPORT_REPAIR_ENV.get(key)
        override = os.environ.get(env_name, "") if env_name else ""
        if current != expected:
            if env_name is None or override != current:
                raise RuntimeError(f"A7 frozen local source differs: {relative}")
            repairs[key] = current
        elif override:
            if override != current:
                raise RuntimeError(f"A7 {env_name} differs")
            repairs[key] = current
    return repairs


def _validate_a3_release(path: Path) -> dict[str, Any]:
    value = _load_json(path, label="A3 logical release")
    if set(value) != {
        "version", "run_id", "status", "next_run_id", "closure_mode",
        "strict_harvest_completed_before_read",
        "post_open_forensic_closure_complete", "forensic_closure_sha256",
        "forensic_closure_receipt",
        "original_result_commit", "aggregate_sha256", "result_report_sha256",
        "prior_arm_disposition", "historical_outcome_lease_clear",
        "historical_outcome_lease_state",
        "historical_outcome_lease_absence_checked_at", "operator_approved",
        "released_at", "cell_rerun_licensed", "scientific_retest_licensed",
        "production_change_licensed", "shadow_adoption_licensed",
        "a3_result_transport_to_a7_licensed",
    }:
        raise RuntimeError("A7 A3 logical release fields differ")
    closure = value.get("forensic_closure_receipt")
    closure_keys = {
        "version", "run_id", "status", "closure_mode", "protocol_sha256",
        "protocol_deviation_disclosed",
        "scientific_result_opened_before_strict_harvest",
        "recovery_reads_already_opened_realized_outcomes",
        "strict_harvest_completed_before_read", "original_result_commit",
        "prior_arm_disposition", "result_report", "aggregate", "cells",
        "launch", "preopen_material", "closure_implementation",
        "executions", "objects", "cell_rerun_licensed",
        "scientific_retest_licensed", "production_change_licensed",
        "shadow_adoption_licensed", "a3_result_transport_to_a7_licensed",
        "closed_at",
    }
    if not isinstance(closure, dict) or set(closure) != closure_keys:
        raise RuntimeError("A7 A3 forensic closure fields differ")
    closure_fixed = {
        "version": "stack-relaxation-carve-post-open-forensic-closure-v1",
        "run_id": "20260819-stack-relaxation-carve-v1",
        "status": "post-open-forensic-closure-complete",
        "closure_mode": "post-open-forensic-provenance-recovery",
        "protocol_sha256": (
            "502c9c2c70ac0aa99ea5873c7fa99999557cd6f2aac5f6c95bfde1b33351e22b"
        ),
        "protocol_deviation_disclosed": True,
        "scientific_result_opened_before_strict_harvest": True,
        "recovery_reads_already_opened_realized_outcomes": True,
        "strict_harvest_completed_before_read": False,
        "original_result_commit": (
            "56b09e960e5445cc7cd54c22eceef7cb5e7ec8c0"
        ),
        "prior_arm_disposition": "negative-closed-at-this-dose",
        "cell_rerun_licensed": False,
        "scientific_retest_licensed": False,
        "production_change_licensed": False,
        "shadow_adoption_licensed": False,
        "a3_result_transport_to_a7_licensed": False,
    }
    if any(not _exact_json_value(closure.get(key), expected)
           for key, expected in closure_fixed.items()):
        raise RuntimeError("A7 A3 forensic closure differs")
    nested_fixed = {
        "result_report": {
            "path": "reports/2026-08-20-stack-relaxation-carve-results.md",
            "sha256": (
                "b8ae2d2684baa8a236e5e0cfeb31eec27d9b1a8697702d11cb30c16724cbe7ae"
            ),
        },
        "launch": {
            "manifest_sha256": (
                "6d822d6434aff3f16e00ac7e78216bcf583558abedbe93b0372683ba12edcbe7"
            ),
            "execution_ledger_sha256": (
                "8355974533586b549ba11bca0302b7ebc3ae792094283bb40645e7c6841ebc6f"
            ),
            "launch_receipt_sha256": (
                "8f883eed18dad935459f211bcd821a8dacadde284e6c4d9170ac5e6bb399df5b"
            ),
        },
        "preopen_material": {
            "finisher_sha256": (
                "c43505f61008dd217395ba21f6f485c9a87a72fd72a581123f68c565df2addf2"
            ),
            "tests_sha256": (
                "13a6359b1d4165737f9b9b38755d5e6924f15d946b410a6801ee4b499204a191"
            ),
            "addendum_sha256": (
                "fb2ad4f3239f08ef17e35f71e10fbfa1471b48e2b18c9be77730ade3594c4860"
            ),
            "was_untracked_at_result_commit": True,
        },
    }
    if any(not _exact_json_value(closure.get(key), expected)
           for key, expected in nested_fixed.items()):
        raise RuntimeError("A7 A3 forensic closure source binding differs")
    aggregate = closure.get("aggregate")
    cells = closure.get("cells")
    executions = closure.get("executions")
    objects = closure.get("objects")
    implementation = closure.get("closure_implementation")
    if not isinstance(aggregate, dict) or set(aggregate) != {
        "path", "sha256", "bytes", "recomputed_byte_identical",
    } or aggregate.get("path") != (
        "reports/stack-relaxation-carve-runs/"
        "20260819-stack-relaxation-carve-v1/aggregate-report.json"
    ) or aggregate.get("sha256") != (
        "2e08a551d116dc385b92ef123be3a6bb8296c71a75c822797d04c71bd669afdc"
    ) or not isinstance(aggregate.get("bytes"), int) or \
            isinstance(aggregate.get("bytes"), bool) or \
            aggregate["bytes"] <= 0 or \
            aggregate.get("recomputed_byte_identical") is not True:
        raise RuntimeError("A7 A3 forensic aggregate binding differs")
    for block, expected in (
        (cells, {"count": 54, "git_byte_identity": True,
                 "remote_generation_byte_identity": True}),
        (executions, {"count": 54, "all_strict_terminal": True}),
        (objects, {"count": 54, "exact_inventory": True,
                   "generation_pinned": True}),
    ):
        expected_keys = (
            {"count", "ledger_sha256", "git_byte_identity",
             "remote_generation_byte_identity"}
            if block is cells else
            ({"count", "metadata_ledger_sha256", "all_strict_terminal"}
             if block is executions else
             {"count", "metadata_ledger_sha256", "exact_inventory",
              "generation_pinned"})
        )
        if not isinstance(block, dict) or set(block) != expected_keys or any(
            not _exact_json_value(block.get(key), expected_value)
            for key, expected_value in expected.items()
        ) or re.fullmatch(r"[0-9a-f]{64}", str(
            block.get("ledger_sha256" if block is cells else
                      "metadata_ledger_sha256", "")
        )) is None:
            raise RuntimeError("A7 A3 forensic population binding differs")
    if not isinstance(implementation, dict) or set(implementation) != {
        "source_commit", "freeze_manifest_path", "freeze_manifest_sha256",
        "implementation", "operator_approved", "frozen_at",
    } or re.fullmatch(r"[0-9a-f]{40}", str(
        implementation.get("source_commit", "")
    )) is None or re.fullmatch(r"[0-9a-f]{64}", str(
        implementation.get("freeze_manifest_sha256", "")
    )) is None or implementation.get("freeze_manifest_path") != (
        "reports/2026-08-20-a3-post-open-forensic-closure-"
        "implementation-freeze.json"
    ) or implementation.get("operator_approved") is not True or \
            not isinstance(implementation.get("frozen_at"), str) or \
            not implementation["frozen_at"]:
        raise RuntimeError("A7 A3 forensic implementation binding differs")
    implementation_rows = implementation.get("implementation")
    expected_paths = {
        "script": "scripts/close_stack_relaxation_carve_post_open.py",
        "tests": "tests/test_close_stack_relaxation_carve_post_open.py",
        "protocol": (
            "reports/2026-08-20-a3-post-open-forensic-closure-protocol.md"
        ),
    }
    if not isinstance(implementation_rows, dict) or \
            set(implementation_rows) != set(expected_paths):
        raise RuntimeError("A7 A3 forensic implementation population differs")
    for key, relative in expected_paths.items():
        row = implementation_rows.get(key)
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or \
                row.get("path") != relative or re.fullmatch(
                    r"[0-9a-f]{64}", str(row.get("sha256", ""))
                ) is None:
            raise RuntimeError("A7 A3 forensic implementation row differs")
    frozen_implementation = {
        "source_commit": "bdd54da82c1244abced6a0eea6f234180685f062",
        "freeze_manifest_path": (
            "reports/2026-08-20-a3-post-open-forensic-closure-"
            "implementation-freeze.json"
        ),
        "freeze_manifest_sha256": (
            "07c54932e1494155c5302d94274c2bd3f0da7fd39c8450b912de7b4150067dcf"
        ),
        "implementation": {
            "script": {
                "path": "scripts/close_stack_relaxation_carve_post_open.py",
                "sha256": (
                    "bba975fc1de68935d5de2084f31c1cebeca2968063970b26553e210725210584"
                ),
            },
            "tests": {
                "path": "tests/test_close_stack_relaxation_carve_post_open.py",
                "sha256": (
                    "9338e079e4ace56989d6b28420685d46ff09b6cccc05e8e948f12f746c2e65be"
                ),
            },
            "protocol": {
                "path": (
                    "reports/2026-08-20-a3-post-open-forensic-"
                    "closure-protocol.md"
                ),
                "sha256": (
                    "502c9c2c70ac0aa99ea5873c7fa99999557cd6f2aac5f6c95bfde1b33351e22b"
                ),
            },
        },
        "operator_approved": True,
        "frozen_at": "2026-08-20T12:51:34.435948+00:00",
    }
    if not _exact_json_value(implementation, frozen_implementation):
        raise RuntimeError("A7 A3 forensic implementation identity differs")
    if implementation_rows["protocol"]["sha256"] != \
            closure_fixed["protocol_sha256"]:
        raise RuntimeError("A7 A3 forensic implementation protocol differs")
    if _sha_bytes(_canonical_json(closure)) != value.get(
        "forensic_closure_sha256"
    ):
        raise RuntimeError("A7 A3 forensic closure SHA differs")
    required = {
        "version": "stack-relaxation-carve-logical-release-v2",
        "run_id": "20260819-stack-relaxation-carve-v1",
        "status": (
            "released-for-next-historical-arm-after-post-open-forensic-closure"
        ),
        "next_run_id": V1_RUN_ID,
        "closure_mode": "post-open-forensic-provenance-recovery",
        "strict_harvest_completed_before_read": False,
        "post_open_forensic_closure_complete": True,
        "original_result_commit": (
            "56b09e960e5445cc7cd54c22eceef7cb5e7ec8c0"
        ),
        "aggregate_sha256": (
            "2e08a551d116dc385b92ef123be3a6bb8296c71a75c822797d04c71bd669afdc"
        ),
        "result_report_sha256": (
            "b8ae2d2684baa8a236e5e0cfeb31eec27d9b1a8697702d11cb30c16724cbe7ae"
        ),
        "prior_arm_disposition": "negative-closed-at-this-dose",
        "historical_outcome_lease_clear": True,
        "historical_outcome_lease_state": "absent",
        "operator_approved": True,
        "cell_rerun_licensed": False,
        "scientific_retest_licensed": False,
        "production_change_licensed": False,
        "shadow_adoption_licensed": False,
        "a3_result_transport_to_a7_licensed": False,
    }
    if any(not _exact_json_value(value.get(key), expected)
           for key, expected in required.items()) or \
            re.fullmatch(r"[0-9a-f]{64}", str(
                value.get("forensic_closure_sha256", "")
            )) is None:
        raise RuntimeError("A7 A3 logical release differs")
    parsed_timestamps: dict[str, datetime] = {}
    for key in (
        "closed_at", "historical_outcome_lease_absence_checked_at",
        "released_at",
    ):
        timestamp = closure.get(key) if key == "closed_at" else value.get(key)
        if not isinstance(timestamp, str) or not timestamp:
            raise RuntimeError("A7 A3 logical release timestamp differs")
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise RuntimeError("A7 A3 logical release timestamp differs") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise RuntimeError("A7 A3 logical release timestamp differs")
        parsed_timestamps[key] = parsed
    if not parsed_timestamps["closed_at"] <= parsed_timestamps[
        "historical_outcome_lease_absence_checked_at"
    ] <= parsed_timestamps["released_at"]:
        raise RuntimeError("A7 A3 logical release chronology differs")
    frozen_at = implementation.get("frozen_at")
    if not isinstance(frozen_at, str) or not frozen_at:
        raise RuntimeError("A7 A3 implementation freeze timestamp differs")
    try:
        parsed_frozen_at = datetime.fromisoformat(frozen_at)
    except ValueError as exc:
        raise RuntimeError("A7 A3 implementation freeze timestamp differs") from exc
    if parsed_frozen_at.tzinfo is None or parsed_frozen_at.utcoffset() != \
            timezone.utc.utcoffset(parsed_frozen_at) or \
            parsed_frozen_at > parsed_timestamps["closed_at"]:
        raise RuntimeError("A7 A3 implementation freeze chronology differs")
    return value


def _job_claim_body(
    *, code_sha: str, image: str, protocol_sha256: str,
    a3_logical_release_sha256: str,
    v1_failed_preflight_release: Mapping[str, Any], job_uid: str,
    job_generation: str, job_spec_sha256: str, claimed_at: str,
) -> dict[str, Any]:
    return {
        "version": "a7-select-ladder-job-claim-v2",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256,
        "code_sha": code_sha,
        "image": image,
        "claimant_phase": "smoke-support-freeze-historical",
        "a3_logical_release_sha256": a3_logical_release_sha256,
        "v1_failed_preflight_release": dict(v1_failed_preflight_release),
        "job": JOB,
        "job_uid": job_uid,
        "job_generation": job_generation,
        "job_spec_sha256": job_spec_sha256,
        "claimed_at": claimed_at,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }


def _validate_v1_failed_preflight_release_binding(
    value: object,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "prior_run_id", "next_run_id", "release_sha256",
        "object_receipt", "object_receipt_sha256",
    }:
        raise RuntimeError("A7-v2 v1 failed-preflight release binding differs")
    if value.get("prior_run_id") != V1_RUN_ID or value.get(
        "next_run_id"
    ) != RUN_ID:
        raise RuntimeError("A7-v2 v1 failed-preflight release lineage differs")
    release_sha = _hex(
        value.get("release_sha256"), length=64,
        label="v1 failed-preflight release SHA",
    )
    receipt_sha = _hex(
        value.get("object_receipt_sha256"), length=64,
        label="v1 failed-preflight release object-receipt SHA",
    )
    receipt = value.get("object_receipt")
    if not isinstance(receipt, dict) or set(receipt) != {
        "version", "run_id", "release_sha256", "object",
    } or receipt.get(
        "version"
    ) != V1_FAILURE_RELEASE_OBJECT_RECEIPT_VERSION or receipt.get(
        "run_id"
    ) != V1_RUN_ID or receipt.get(
        "release_sha256"
    ) != release_sha or receipt_sha != _sha_bytes(_canonical_json(receipt)):
        raise RuntimeError("A7-v2 v1 failed-preflight object receipt differs")
    obj = receipt.get("object")
    if not isinstance(obj, dict) or set(obj) != {
        "uri", "generation", "metageneration", "bytes", "sha256",
        "create_only",
    } or obj.get("create_only") is not True:
        raise RuntimeError("A7-v2 v1 failed-preflight object identity differs")
    metadata = _metadata_block(
        obj, uri=V1_FAILURE_RELEASE_URI,
        label="v1 failed-preflight logical release",
    )
    if obj != {**metadata, "create_only": True}:
        raise RuntimeError("A7-v2 v1 failed-preflight object identity differs")
    if metadata["sha256"] != release_sha:
        raise RuntimeError("A7-v2 v1 failed-preflight release body differs")
    return {
        "prior_run_id": V1_RUN_ID,
        "next_run_id": RUN_ID,
        "release_sha256": release_sha,
        "object_receipt": {
            "version": V1_FAILURE_RELEASE_OBJECT_RECEIPT_VERSION,
            "run_id": V1_RUN_ID,
            "release_sha256": release_sha,
            "object": {**metadata, "create_only": True},
        },
        "object_receipt_sha256": receipt_sha,
    }


def _validate_job_claim_receipt(
    value: object, *, code_sha: str, image: str, protocol_sha256: str,
    a3_logical_release_sha256: str, job_uid: str | None = None,
    job_generation: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != JOB_CLAIM_RECEIPT_KEYS:
        raise RuntimeError("A7 durable job-claim receipt fields differ")
    claim = value.get("claim")
    obj = value.get("object")
    if not isinstance(claim, dict) or set(claim) != JOB_CLAIM_KEYS or \
            not isinstance(obj, dict) or set(obj) != {
                "uri", "generation", "metageneration", "bytes", "sha256",
                "create_only",
            }:
        raise RuntimeError("A7 durable job-claim fields differ")
    fixed = {
        "version": "a7-select-ladder-job-claim-v2",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256,
        "code_sha": code_sha,
        "image": image,
        "claimant_phase": "smoke-support-freeze-historical",
        "a3_logical_release_sha256": a3_logical_release_sha256,
        "job": JOB,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    if any(claim.get(key) != expected for key, expected in fixed.items()) or \
            not str(claim.get("claimed_at", "")):
        raise RuntimeError("A7 durable job-claim identity differs")
    _validate_v1_failed_preflight_release_binding(
        claim.get("v1_failed_preflight_release")
    )
    actual_uid = str(claim.get("job_uid", ""))
    actual_generation = str(claim.get("job_generation", ""))
    _hex(claim.get("job_spec_sha256"), length=64, label="job-claim spec SHA")
    if not actual_uid or re.fullmatch(r"[1-9][0-9]*", actual_generation) is None or \
            (job_uid is not None and actual_uid != job_uid) or \
            (job_generation is not None and actual_generation != job_generation):
        raise RuntimeError("A7 durable job-claim job identity differs")
    if obj.get("create_only") is not True:
        raise RuntimeError("A7 durable job claim was not create-only")
    metadata = _metadata_block(obj, uri=JOB_CLAIM_URI, label="job claim")
    if metadata["sha256"] != _sha_bytes(_canonical_json(claim)) or \
            metadata["bytes"] != len(_canonical_json(claim)):
        raise RuntimeError("A7 durable job-claim object body differs")
    return {"claim": claim, "object": {**metadata, "create_only": True}}


def _job_spec_sha256(value: Mapping[str, Any]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, dict) or not spec:
        raise RuntimeError("A7 reused job spec is absent")
    return _sha_bytes(_canonical_json(spec))


def _validate_prior_job_state(
    value: Mapping[str, Any], *, job_uid: str, job_generation: str,
    job_spec_sha256: str,
) -> None:
    metadata = value.get("metadata")
    generation = _json_positive_int(
        metadata.get("generation") if isinstance(metadata, dict) else None,
        label="reused job generation",
    )
    if not isinstance(metadata, dict) or metadata.get("name") != JOB or \
            metadata.get("uid") != job_uid or str(generation) != \
            job_generation or _job_spec_sha256(value) != job_spec_sha256:
        raise RuntimeError("A7 reused job prior-generation/spec chain differs")


def _validate_updated_job_spec(
    value: Mapping[str, Any], *, code_sha: str, image: str, mode: str,
    freeze_manifest_uri: str | None = None,
    freeze_manifest_generation: str | None = None,
    freeze_manifest_sha256: str | None = None,
) -> str:
    """Validate the full executable contract of a post-update Cloud Run job."""
    spec = value.get("spec")
    outer = spec.get("template", {}).get("spec", {}) \
        if isinstance(spec, dict) else {}
    task = outer.get("template", {}).get("spec", {}) \
        if isinstance(outer, dict) else {}
    containers = task.get("containers", []) if isinstance(task, dict) else []
    if _json_positive_int(
        outer.get("parallelism"), label="reused job parallelism",
    ) != 1 or _json_positive_int(
        outer.get("taskCount"), label="reused job task count",
    ) != 1 or \
            len(containers) != 1:
        raise RuntimeError("A7 reused job task shape differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        or not isinstance(row["name"], str) or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise RuntimeError("A7 reused job environment rows differ")
    env = {
        row.get("name"): str(row.get("value", ""))
        for row in env_rows if isinstance(row, dict)
    }
    if mode == "real-artifact-smoke":
        args = [
            "scripts/run_a7_select_ladder.py", "--smoke",
            "--preflight-receipt-uri", SMOKE_URI,
        ]
        expected_env = {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image}
    elif mode == "support-census":
        args = [
            "scripts/run_a7_select_ladder.py", "--support-census",
            "--preflight-receipt-uri", SUPPORT_URI,
        ]
        expected_env = {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image}
    elif mode == "historical":
        if not all((
            freeze_manifest_uri, freeze_manifest_generation,
            freeze_manifest_sha256,
        )):
            raise RuntimeError("A7 historical job freeze reference is absent")
        args = [
            "scripts/run_a7_select_ladder.py", "--output-uri", RESULT_URI,
            "--freeze-manifest-uri", freeze_manifest_uri,
            "--freeze-manifest-generation", freeze_manifest_generation,
            "--freeze-manifest-sha256", freeze_manifest_sha256,
        ]
        expected_env = {
            "CODE_SHA": code_sha,
            "ANALYSIS_IMAGE": image,
            "A7_FREEZE_MANIFEST_URI": freeze_manifest_uri,
            "A7_FREEZE_MANIFEST_GENERATION": freeze_manifest_generation,
            "A7_FREEZE_MANIFEST_SHA256": freeze_manifest_sha256,
        }
    else:
        raise RuntimeError("A7 reused job mode differs")
    if len(env_rows) != len(env) or env != expected_env or \
            container.get("image") != image or \
            container.get("command") != ["python"] or \
            container.get("args") != args or \
            container.get("workingDir", "") != "" or container.get(
                "volumeMounts", []
            ) != [] or container.get("startupProbe") not in (None, {}) or \
            container.get("resources", {}).get("limits") != {
                "cpu": CPU, "memory": MEMORY,
            } or task.get("volumes", []) != [] or _json_nonnegative_int(
                task.get("maxRetries"), label="reused job max retries",
            ) != 0 or type(task.get("timeoutSeconds")) is not str or \
            task.get("timeoutSeconds") != TIMEOUT_SECONDS or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("A7 reused job executable contract differs")
    return _job_spec_sha256(value)


def _metadata_block(
    value: Mapping[str, Any], *, uri: str, label: str,
) -> dict[str, Any]:
    generation = str(value.get("generation", ""))
    metageneration = str(value.get("metageneration", ""))
    size = _positive_int(value.get("bytes"), label=f"{label} bytes")
    digest = _hex(value.get("sha256"), length=64, label=f"{label} SHA")
    if value.get("uri") != uri or re.fullmatch(
        r"[1-9][0-9]*", generation
    ) is None or metageneration != "1":
        raise RuntimeError(f"A7 {label} object identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "metageneration": metageneration,
        "bytes": size,
        "sha256": digest,
    }


def _validate_loaded_object(
    metadata: Mapping[str, Any], raw: bytes, expected: Mapping[str, Any],
    *, label: str,
) -> None:
    live = _metadata_block(metadata, uri=str(expected["uri"]), label=label)
    if any(live[key] != expected[key] for key in live) or \
            len(raw) != expected["bytes"] or _sha_bytes(raw) != expected["sha256"]:
        raise RuntimeError(f"A7 {label} changed")


def _inventory_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    normalized = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "uri", "generation", "metageneration", "bytes", "sha256",
        }:
            raise RuntimeError("A7 prefix inventory receipt differs")
        normalized.append({
            key: row[key]
            for key in ("uri", "generation", "metageneration", "bytes", "sha256")
        })
    return _sha_bytes(_canonical_json(normalized))


def _uri_inventory_sha256(uris: Sequence[str]) -> str:
    if any(not isinstance(uri, str) for uri in uris) or len(uris) != len(set(uris)):
        raise RuntimeError("A7 prefix inventory URI receipt differs")
    return _sha_bytes(_canonical_json(list(uris)))


def _registered_execution_contract(
    *, mode: str, code_sha: str, image: str,
    freeze_manifest_uri: str | None = None,
    freeze_manifest_generation: str | None = None,
    freeze_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    if mode == "real-artifact-smoke":
        args = [
            "scripts/run_a7_select_ladder.py", "--smoke",
            "--preflight-receipt-uri", SMOKE_URI,
        ]
        env = {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image}
    elif mode == "support-census":
        args = [
            "scripts/run_a7_select_ladder.py", "--support-census",
            "--preflight-receipt-uri", SUPPORT_URI,
        ]
        env = {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image}
    elif mode == "historical":
        if not all((
            freeze_manifest_uri, freeze_manifest_generation,
            freeze_manifest_sha256,
        )):
            raise RuntimeError("A7 historical job freeze reference is absent")
        args = [
            "scripts/run_a7_select_ladder.py", "--output-uri", RESULT_URI,
            "--freeze-manifest-uri", freeze_manifest_uri,
            "--freeze-manifest-generation", freeze_manifest_generation,
            "--freeze-manifest-sha256", freeze_manifest_sha256,
        ]
        env = {
            "CODE_SHA": code_sha,
            "ANALYSIS_IMAGE": image,
            "A7_FREEZE_MANIFEST_URI": freeze_manifest_uri,
            "A7_FREEZE_MANIFEST_GENERATION": freeze_manifest_generation,
            "A7_FREEZE_MANIFEST_SHA256": freeze_manifest_sha256,
        }
    else:
        raise RuntimeError("A7 reused job mode differs")
    return {
        "image": image,
        "command": ["python"],
        "args": args,
        "env": env,
        "working_dir": "",
        "volume_mounts": [],
        "volumes": [],
        "startup_probe": None,
        "secret_environment": False,
        "tasks": 1,
        "parallelism": 1,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "max_retries": 0,
        "timeout_seconds": int(TIMEOUT_SECONDS),
        "service_account": SERVICE_ACCOUNT,
    }


def _source_artifact_lock(rows: Sequence[Mapping[str, Any]]) -> str:
    normalized = [
        {
            "panel_run_id": str(row["panel_run_id"]),
            "season": int(row["season"]),
            "week": int(row["week"]),
            "uri": str(row["uri"]),
            "generation": str(row["generation"]),
            "sha256": str(row["sha256"]),
            "bytes": int(row["bytes"]),
            "candidate_rows": int(row["candidate_rows"]),
        }
        for row in rows
    ]
    return _sha_bytes(json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8"))


def _validate_source_artifacts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 270:
        raise RuntimeError("A7 freeze source-artifact population differs")
    result: list[dict[str, Any]] = []
    keys: set[tuple[str, int, int]] = set()
    uris: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {
            "panel_run_id", "season", "week", "uri", "generation",
            "sha256", "bytes", "candidate_rows",
        }:
            raise RuntimeError("A7 freeze source-artifact row differs")
        panel = str(raw.get("panel_run_id", ""))
        season = int(raw.get("season", 0))
        week = int(raw.get("week", 0))
        uri = str(raw.get("uri", ""))
        generation = str(raw.get("generation", ""))
        digest = _hex(raw.get("sha256"), length=64,
                      label="freeze source artifact SHA")
        size = _positive_int(raw.get("bytes"), label="freeze source artifact bytes")
        rows = _positive_int(
            raw.get("candidate_rows"), label="freeze source artifact rows",
        )
        key = (panel, season, week)
        if not panel or season not in (2023, 2024, 2025) or not 1 <= week <= 18 or \
                not re.fullmatch(r"gs://[^/]+/.+", uri) or \
                re.fullmatch(r"[1-9][0-9]*", generation) is None or \
                key in keys or uri in uris:
            raise RuntimeError("A7 freeze source-artifact identity differs")
        keys.add(key)
        uris.add(uri)
        result.append({
            "panel_run_id": panel, "season": season, "week": week,
            "uri": uri, "generation": generation, "sha256": digest,
            "bytes": size, "candidate_rows": rows,
        })
    panels = sorted({key[0] for key in keys})
    expected = {
        (panel, season, week) for panel in panels
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if len(panels) != 5 or keys != expected:
        raise RuntimeError("A7 freeze source-artifact lattice differs")
    canonical_order = [
        (panel, season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
        for panel in SOURCE_PANEL_IDS
    ]
    if [
        (row["panel_run_id"], row["season"], row["week"])
        for row in result
    ] != canonical_order:
        raise RuntimeError("A7 freeze source-artifact order differs")
    return result


def _validate_preflight_receipt(
    raw: bytes, *, mode: str, manifest: Mapping[str, Any],
    require_support_pass: bool = True,
) -> dict[str, Any]:
    value = _json_object(raw, label=f"{mode} preflight receipt")
    if set(value) != PREFLIGHT_RECEIPT_KEYS:
        raise RuntimeError(f"A7 {mode} preflight fields differ")
    implementation = manifest["implementation_sha256"]
    expected_core = {key: implementation[key] for key in CORE_IMPLEMENTATION_KEYS}
    fixed = {
        "version": "a7-select-ladder-preflight-receipt-v1",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "mode": mode,
        "code_sha": manifest["code"]["commit_sha"],
        "image": manifest["image"]["uri"],
        "protocol_sha256": manifest["protocol"]["sha256"],
        "source_report_sha256": manifest["source_report"]["sha256"],
        "baseline_sha256": manifest["baseline"]["sha256"],
        "baseline_vector_sha256": manifest["baseline_vector"]["sha256"],
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "local_source_receipts": manifest["local_source_receipts"],
        "implementation_receipts": expected_core,
        "query_content_receipts": manifest["query_content_receipts"],
        "frozen_choices": manifest["frozen_law"],
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_preflight": {
            "panel_ids": list(SOURCE_PANEL_IDS),
            "slates": [
                [season, week] for season in (2023, 2024, 2025)
                for week in range(1, 19)
            ],
            "slate_count": 54,
            "artifact_count": 270,
        },
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise RuntimeError(f"A7 {mode} preflight identity differs")
    slates = value.get("slates")
    expected_count = 1 if mode == "real-artifact-smoke" else 54
    if not isinstance(slates, list) or len(slates) != expected_count:
        raise RuntimeError(f"A7 {mode} preflight slate population differs")
    expected_lattice = (
        [(2023, 1)] if mode == "real-artifact-smoke" else [
            (season, week) for season in (2023, 2024, 2025)
            for week in range(1, 19)
        ]
    )
    for row, (season, week) in zip(slates, expected_lattice, strict=True):
        if not isinstance(row, dict) or set(row) != PREFLIGHT_SLATE_KEYS or \
                row.get("season") != season or row.get("week") != week or \
                type(row.get("candidate_budget")) is not int or row[
                    "candidate_budget"
                ] < ENTRY_COUNT or type(row.get("world_count")) is not int or \
                row["world_count"] <= 0:
            raise RuntimeError(f"A7 {mode} preflight slate receipt differs")
        for key in (
            "candidate_identities_sha256", "candidate_tags_sha256",
            "scorefree_receipt_sha256",
        ):
            _hex(row.get(key), length=64, label=f"preflight {key}")
        combined = row.get("combined_input_receipts")
        if not isinstance(combined, dict) or set(combined) != {
            "candidate_totals", "player_draws", "player_ids_sha256",
        } or re.fullmatch(r"[0-9a-f]{64}", str(
            combined.get("player_ids_sha256", "")
        )) is None:
            raise RuntimeError(f"A7 {mode} preflight combined receipt differs")
        for key in ("candidate_totals", "player_draws"):
            array = combined.get(key)
            if not isinstance(array, dict) or set(array) != {
                "dtype", "shape", "sha256",
            } or not isinstance(array.get("dtype"), str) or not isinstance(
                array.get("shape"), list
            ) or not array["shape"] or any(
                type(size) is not int or size <= 0 for size in array["shape"]
            ) or re.fullmatch(r"[0-9a-f]{64}", str(
                array.get("sha256", "")
            )) is None:
                raise RuntimeError(
                    f"A7 {mode} preflight {key} receipt differs"
                )
    source_artifacts = manifest["source_artifacts"]
    if mode == "support-census":
        support = value.get("support")
        if not isinstance(support, dict) or set(support) != SUPPORT_CENSUS_KEYS or \
                support.get("version") != "a7-r3-support-census-v1" or \
                support.get("uses_realized_outcomes") is not False or \
                support.get("slates") != 54 or support.get(
                    "definition"
                ) != (
                    "positive-ladder-gain-events-with-at-least-3-"
                    "strict-q99-exceedances"
                ) or support.get(
                    "minimum_aggregate_events_per_arm"
                ) != 100 or type(support.get("passes")) is not bool or \
                value.get("source_artifact_count") != 270 or value.get(
                    "source_artifacts_sha256"
                ) != manifest["source_artifact_lock_sha256"]:
            raise RuntimeError("A7 support preflight did not pass")
        conditions = support.get("conditions")
        blocks = support.get("r3_positive_gain_events_by_block")
        if not isinstance(conditions, dict) or set(
            conditions
        ) != SUPPORT_CONDITION_KEYS or not isinstance(blocks, dict) or set(blocks) != {
            "control", "treatment",
        } or any(
            not isinstance(blocks[arm], list) or len(blocks[arm]) != 5 or
            any(type(count) is not int or count < 0 for count in blocks[arm])
            for arm in ("control", "treatment")
        ):
            raise RuntimeError("A7 support preflight support cells differ")
        expected_conditions = {
            "control_r3_events_at_least_100": sum(blocks["control"]) >= 100,
            "treatment_r3_events_at_least_100": sum(blocks["treatment"]) >= 100,
            "control_r3_supported_in_every_block": all(
                count > 0 for count in blocks["control"]
            ),
            "treatment_r3_supported_in_every_block": all(
                count > 0 for count in blocks["treatment"]
            ),
        }
        if conditions != expected_conditions or support["passes"] is not all(
            expected_conditions.values()
        ) or require_support_pass and support["passes"] is not True:
            raise RuntimeError("A7 support preflight did not pass")
    else:
        smoke_artifacts = [
            row for row in source_artifacts
            if (int(row["season"]), int(row["week"])) == (2023, 1)
        ]
        smoke_sha = _sha_bytes(json.dumps(
            smoke_artifacts, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8"))
        if value.get("support") is not None or value.get(
            "source_artifact_count"
        ) != 5 or value.get("source_artifacts_sha256") != smoke_sha or \
                (int(slates[0]["season"]), int(slates[0]["week"])) != (2023, 1):
            raise RuntimeError("A7 smoke preflight population differs")
    return value


def _validate_preflight_terminal_receipt(
    value: object, *, mode: str, science_object: Mapping[str, Any],
    claim: Mapping[str, Any], code_sha: str, image: str,
    protocol_sha256: str, a3_logical_release_sha256: str,
    build_id: str | None = None,
    prior_science_object: Mapping[str, Any] | None = None,
    prior_terminal_object: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PREFLIGHT_TERMINAL_KEYS:
        raise RuntimeError("A7 preflight terminal-receipt fields differ")
    fixed = {
        "version": "a7-select-ladder-preflight-terminal-v1",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "mode": mode,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": protocol_sha256,
        "a3_logical_release_sha256": a3_logical_release_sha256,
        "job_claim": claim,
        "science_object": dict(science_object),
        "expected_inventory_after_terminal_uris": list(
            _preflight_expected_uris(mode, include_current_terminal=True)
        ),
        "preflight_receipt_sha256": science_object["sha256"],
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise RuntimeError("A7 preflight terminal-receipt identity differs")
    terminal_build_id = str(value.get("build_id", ""))
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", terminal_build_id) is None or \
            build_id is not None and terminal_build_id != build_id:
        raise RuntimeError("A7 preflight terminal build identity differs")
    support_passed = value.get("support_passed")
    disposition = value.get("disposition")
    if mode == "real-artifact-smoke":
        if support_passed is not None or disposition != "smoke-passed":
            raise RuntimeError("A7 smoke terminal disposition differs")
    elif type(support_passed) is not bool or disposition != (
        "support-passed" if support_passed else "invalid-unsupported"
    ):
        raise RuntimeError("A7 support terminal disposition differs")
    _hex(value.get("job_claim_receipt_sha256"), length=64,
         label="terminal job-claim receipt SHA")
    if _sha_bytes(_canonical_json(claim)) != value[
        "job_claim_receipt_sha256"
    ]:
        raise RuntimeError("A7 terminal job-claim receipt differs")
    execution = value.get("execution")
    if not isinstance(execution, dict) or set(execution) != {
        "name", "generation", "job", "job_uid", "job_generation",
        "job_spec_sha256", "prior_job_generation", "prior_job_spec_sha256",
        "completion_time", "completed_condition",
        "counters", "spec_sha256", "contract", "contract_sha256",
    } or _json_positive_int(
        execution.get("generation"), label="terminal execution generation",
    ) != 1 or execution.get("job") != JOB or \
            not str(execution.get("name", "")).startswith(JOB + "-") or \
            not str(execution.get("job_uid", "")) or re.fullmatch(
                r"[1-9][0-9]*", str(execution.get("job_generation", ""))
            ) is None or execution.get("completed_condition") is not True or \
            not _exact_json_value(execution.get("counters"), {
                "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
            }) or not str(execution.get("completion_time", "")):
        raise RuntimeError("A7 preflight terminal execution differs")
    _hex(
        execution.get("job_spec_sha256"), length=64,
        label="terminal job spec SHA",
    )
    _hex(
        execution.get("prior_job_spec_sha256"), length=64,
        label="terminal prior job spec SHA",
    )
    if re.fullmatch(
        r"[1-9][0-9]*", str(execution.get("prior_job_generation", ""))
    ) is None or int(execution["job_generation"]) <= int(
        execution["prior_job_generation"]
    ):
        raise RuntimeError("A7 preflight terminal job-generation chain differs")
    _hex(execution.get("spec_sha256"), length=64,
         label="terminal execution spec SHA")
    expected_contract = _registered_execution_contract(
        mode=mode, code_sha=code_sha, image=image,
    )
    if not _exact_json_value(
        execution.get("contract"), expected_contract,
    ) or execution.get(
        "contract_sha256"
    ) != _sha_bytes(_canonical_json(expected_contract)):
        raise RuntimeError("A7 preflight terminal execution contract differs")
    before = value.get("prefix_inventory_before_terminal")
    expected_uris = _preflight_expected_uris(mode)
    if not isinstance(before, list) or [
        row.get("uri") for row in before if isinstance(row, dict)
    ] != list(expected_uris) or len(before) != len(expected_uris):
        raise RuntimeError("A7 preflight terminal inventory differs")
    for row, uri in zip(before, expected_uris, strict=True):
        if not isinstance(row, dict) or set(row) != {
            "uri", "generation", "metageneration", "bytes", "sha256",
        }:
            raise RuntimeError("A7 preflight terminal inventory row differs")
        _metadata_block(row, uri=uri, label="terminal inventory")
    known_objects: list[Mapping[str, Any]] = [claim["object"]]
    if mode == "support-census":
        if prior_science_object is None or prior_terminal_object is None:
            raise RuntimeError("A7 support terminal prior inventory is absent")
        known_objects.extend((prior_science_object, prior_terminal_object))
    elif prior_science_object is not None or prior_terminal_object is not None:
        raise RuntimeError("A7 smoke terminal prior inventory differs")
    known_objects.append(science_object)
    normalized_known = [
        _metadata_block(
            row, uri=str(row.get("uri", "")),
            label="known terminal inventory",
        )
        for row in known_objects
    ]
    if before != normalized_known:
        raise RuntimeError("A7 terminal inventory is not bound to known objects")
    if value.get("prefix_inventory_before_terminal_sha256") != \
            _inventory_sha256(before) or value.get(
                "expected_inventory_after_terminal_uris_sha256"
            ) != _uri_inventory_sha256(
                value["expected_inventory_after_terminal_uris"]
            ):
        raise RuntimeError("A7 preflight terminal inventory hash differs")
    return value


def _validate_freeze_manifest(
    value: dict[str, Any], *, expected_code_sha: str,
    expected_image: str, root: Path, git_source_loader: GitSourceLoader,
) -> dict[str, Any]:
    if set(value) != FREEZE_MANIFEST_KEYS:
        raise RuntimeError("A7 freeze-manifest fields differ")
    fixed = {
        "version": "a7-select-ladder-freeze-manifest-v1",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "status": "frozen-for-one-historical-look",
        "operator_approved": True,
        "historical_looks": 1,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise RuntimeError("A7 freeze-manifest identity differs")
    basis = value.get("operator_approval_basis")
    if basis != OPERATOR_APPROVAL_BASIS or value.get(
        "operator_approvals"
    ) != OPERATOR_APPROVALS:
        raise RuntimeError("A7 freeze operator approvals differ")
    protocol = value.get("protocol")
    code = value.get("code")
    image = value.get("image")
    if not isinstance(protocol, dict) or set(protocol) != {"path", "sha256"} or \
            protocol.get("path") != (
        "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol-v2.md"
    ) or re.fullmatch(r"[0-9a-f]{64}", str(protocol.get("sha256", ""))) is None:
        raise RuntimeError("A7 freeze protocol binding differs")
    if not isinstance(code, dict) or set(code) != {
        "commit_sha", "archive_sha256",
    } or code.get("commit_sha") != expected_code_sha or \
            re.fullmatch(r"[0-9a-f]{40}", expected_code_sha) is None or \
            re.fullmatch(r"[0-9a-f]{64}", str(
                code.get("archive_sha256", "")
            )) is None:
        raise RuntimeError("A7 freeze source binding differs")
    if not isinstance(image, dict) or set(image) != {"uri"} or \
            image.get("uri") != expected_image or \
            re.fullmatch(r".+@sha256:[0-9a-f]{64}", expected_image) is None:
        raise RuntimeError("A7 freeze image binding differs")
    job_claim = value.get("job_claim")
    if not isinstance(job_claim, dict) or not isinstance(
        job_claim.get("claim"), dict
    ):
        raise RuntimeError("A7 freeze job-claim binding differs")
    claim_a3_sha = _hex(
        job_claim["claim"].get("a3_logical_release_sha256"), length=64,
        label="freeze job-claim A3 release SHA",
    )
    _validate_job_claim_receipt(
        job_claim, code_sha=expected_code_sha, image=expected_image,
        protocol_sha256=str(protocol["sha256"]),
        a3_logical_release_sha256=claim_a3_sha,
    )

    implementation = value.get("implementation_sha256")
    if not isinstance(implementation, dict):
        raise RuntimeError("A7 freeze implementation population differs")
    _validate_implementation_sources(
        implementation, code_sha=expected_code_sha, root=root,
        git_source_loader=git_source_loader,
    )
    protocol_path = root / str(protocol["path"])
    if not protocol_path.is_file() or _sha(protocol_path) != protocol["sha256"] or \
            _sha_bytes(git_source_loader(
                root, expected_code_sha, str(protocol["path"]),
            )) != protocol["sha256"]:
        raise RuntimeError("A7 frozen protocol bytes differ")
    if _git_archive_sha(root, expected_code_sha) != code["archive_sha256"]:
        raise RuntimeError("A7 frozen source archive differs")

    for label in ("source_report", "baseline", "baseline_vector"):
        block = value.get(label)
        if not isinstance(block, dict) or set(block) != {"path", "sha256"} or \
                not isinstance(block.get("path"), str) or \
                re.fullmatch(r"[0-9a-f]{64}", str(
                    block.get("sha256", "")
                )) is None:
            raise RuntimeError(f"A7 freeze {label} binding differs")
        path = root / block["path"]
        if not path.is_file() or _sha(path) != block["sha256"] or \
                _sha_bytes(git_source_loader(
                    root, expected_code_sha, block["path"],
                )) != block["sha256"]:
            raise RuntimeError(f"A7 freeze {label} bytes differ")

    artifacts = _validate_source_artifacts(value.get("source_artifacts"))
    if _source_artifact_lock(artifacts) != value.get(
        "source_artifact_lock_sha256"
    ):
        raise RuntimeError("A7 freeze source-artifact lock differs")
    query_receipts = value.get("query_content_receipts")
    if not isinstance(query_receipts, dict) or set(query_receipts) != {
        "candidate_source", "player_source",
    }:
        raise RuntimeError("A7 freeze query-content receipts differ")
    for label, columns in (
        ("candidate_source", SOURCE_QUERY_COLUMNS),
        ("player_source", PLAYER_QUERY_COLUMNS),
    ):
        receipt = query_receipts[label]
        if not isinstance(receipt, dict) or set(receipt) != {
            "columns", "rows", "sha256",
        } or receipt.get("columns") != list(columns) or \
                not isinstance(receipt.get("rows"), int) or receipt["rows"] <= 0 or \
                re.fullmatch(r"[0-9a-f]{64}", str(
                    receipt.get("sha256", "")
                )) is None:
            raise RuntimeError(f"A7 freeze {label} receipt differs")

    preflights = value.get("preflights")
    if not isinstance(preflights, dict) or set(preflights) != {"smoke", "support"}:
        raise RuntimeError("A7 freeze preflight population differs")
    if any(not isinstance(preflights[key], dict) or set(
        preflights[key]
    ) != {"science", "terminal"} or any(
        not isinstance(preflights[key][kind], dict) or set(
            preflights[key][kind]
        ) != {"uri", "generation", "metageneration", "bytes", "sha256"}
        for kind in ("science", "terminal")
    ) for key in ("smoke", "support")):
        raise RuntimeError("A7 freeze preflight object fields differ")
    _metadata_block(
        preflights["smoke"]["science"], uri=SMOKE_URI,
        label="smoke preflight",
    )
    _metadata_block(
        preflights["support"]["science"], uri=SUPPORT_URI,
        label="support preflight",
    )
    _metadata_block(
        preflights["smoke"]["terminal"], uri=SMOKE_TERMINAL_URI,
        label="smoke terminal",
    )
    _metadata_block(
        preflights["support"]["terminal"], uri=SUPPORT_TERMINAL_URI,
        label="support terminal",
    )
    claim_metadata = _metadata_block(
        job_claim["object"], uri=JOB_CLAIM_URI, label="job claim",
    )
    smoke_inventory = [
        claim_metadata,
        _metadata_block(
            preflights["smoke"]["science"], uri=SMOKE_URI,
            label="smoke preflight",
        ),
        _metadata_block(
            preflights["smoke"]["terminal"], uri=SMOKE_TERMINAL_URI,
            label="smoke terminal",
        ),
    ]
    support_inventory = [
        *smoke_inventory,
        _metadata_block(
            preflights["support"]["science"], uri=SUPPORT_URI,
            label="support preflight",
        ),
        _metadata_block(
            preflights["support"]["terminal"], uri=SUPPORT_TERMINAL_URI,
            label="support terminal",
        ),
    ]
    if value.get("prefix_inventory_sha256") != {
        "claimed": _inventory_sha256([claim_metadata]),
        "smoke-complete": _inventory_sha256(smoke_inventory),
        "support-complete": _inventory_sha256(support_inventory),
    }:
        raise RuntimeError("A7 frozen prefix-inventory hashes differ")
    local_sources = value.get("local_source_receipts")
    expected_local = {
        "protocol": value["protocol"]["sha256"],
        "source_report": value["source_report"]["sha256"],
        "baseline": value["baseline"]["sha256"],
        "baseline_vector": value["baseline_vector"]["sha256"],
    }
    if not isinstance(local_sources, dict) or set(local_sources) != set(
        expected_local
    ) or any(
        local_sources.get(key) != digest
        for key, digest in expected_local.items()
    ):
        raise RuntimeError("A7 freeze local-source receipts differ")
    if value.get("frozen_law") != FROZEN_CHOICES:
        raise RuntimeError("A7 frozen scientific law differs")
    return value


def validate_freeze_for_launch(
    *, freeze_manifest_uri: str, freeze_manifest_generation: str,
    freeze_manifest_sha256: str, expected_code_sha: str,
    expected_image: str, a3_release_path: Path = DEFAULT_A3_RELEASE,
    root: Path = ROOT, object_loader: ObjectLoader,
    git_source_loader: GitSourceLoader = _git_blob,
) -> dict[str, Any]:
    if freeze_manifest_uri != FREEZE_URI or \
            re.fullmatch(
                r"[1-9][0-9]*", freeze_manifest_generation
            ) is None or \
            re.fullmatch(r"[0-9a-f]{64}", freeze_manifest_sha256) is None:
        raise RuntimeError("A7 freeze-manifest reference differs")
    release = _validate_a3_release(a3_release_path)
    metadata, raw = object_loader(
        freeze_manifest_uri, freeze_manifest_generation,
    )
    freeze_expected = {
        "uri": freeze_manifest_uri,
        "generation": freeze_manifest_generation,
        "metageneration": "1",
        "bytes": len(raw),
        "sha256": freeze_manifest_sha256,
    }
    _validate_loaded_object(
        metadata, raw, freeze_expected, label="freeze manifest",
    )
    manifest = _validate_freeze_manifest(
        _json_object(raw, label="freeze manifest"),
        expected_code_sha=expected_code_sha, expected_image=expected_image,
        root=root, git_source_loader=git_source_loader,
    )
    claim = _validate_job_claim_receipt(
        manifest["job_claim"], code_sha=expected_code_sha,
        image=expected_image,
        protocol_sha256=manifest["protocol"]["sha256"],
        a3_logical_release_sha256=_sha(a3_release_path),
    )
    claim_expected = _metadata_block(
        claim["object"], uri=JOB_CLAIM_URI, label="job claim",
    )
    claim_live, claim_raw = object_loader(
        JOB_CLAIM_URI, claim_expected["generation"],
    )
    _validate_loaded_object(
        claim_live, claim_raw, claim_expected, label="job claim",
    )
    if _json_object(claim_raw, label="job claim") != claim["claim"]:
        raise RuntimeError("A7 durable job-claim body differs")
    repair_receipts = _validate_implementation_sources(
        manifest["implementation_sha256"], code_sha=expected_code_sha,
        root=root, git_source_loader=git_source_loader,
    )
    preflight_values: dict[str, dict[str, Any]] = {}
    terminal_values: dict[str, dict[str, Any]] = {}
    for key, mode in (
        ("smoke", "real-artifact-smoke"),
        ("support", "support-census"),
    ):
        expected = _metadata_block(
            manifest["preflights"][key]["science"],
            uri=SMOKE_URI if key == "smoke" else SUPPORT_URI,
            label=f"{key} preflight",
        )
        live, body = object_loader(expected["uri"], expected["generation"])
        _validate_loaded_object(live, body, expected, label=f"{key} preflight")
        preflight_values[key] = _validate_preflight_receipt(
            body, mode=mode, manifest=manifest,
        )
        terminal_expected = _metadata_block(
            manifest["preflights"][key]["terminal"],
            uri=(
                SMOKE_TERMINAL_URI if key == "smoke"
                else SUPPORT_TERMINAL_URI
            ),
            label=f"{key} terminal",
        )
        terminal_live, terminal_body = object_loader(
            terminal_expected["uri"], terminal_expected["generation"],
        )
        _validate_loaded_object(
            terminal_live, terminal_body, terminal_expected,
            label=f"{key} terminal",
        )
        terminal_values[key] = _validate_preflight_terminal_receipt(
            _json_object(terminal_body, label=f"{key} terminal"),
            mode=mode, science_object=expected, claim=claim,
            code_sha=expected_code_sha, image=expected_image,
            protocol_sha256=manifest["protocol"]["sha256"],
            a3_logical_release_sha256=_sha(a3_release_path),
            prior_science_object=(
                manifest["preflights"]["smoke"]["science"]
                if key == "support" else None
            ),
            prior_terminal_object=(
                manifest["preflights"]["smoke"]["terminal"]
                if key == "support" else None
            ),
        )
        if key == "support" and terminal_values[key][
            "support_passed"
        ] is not preflight_values[key]["support"]["passes"]:
            raise RuntimeError("A7 support terminal/science disposition differs")
    smoke_execution = terminal_values["smoke"]["execution"]
    support_execution = terminal_values["support"]["execution"]
    if terminal_values["smoke"]["build_id"] != terminal_values[
        "support"
    ]["build_id"] or smoke_execution["prior_job_generation"] != claim["claim"][
        "job_generation"
    ] or smoke_execution["prior_job_spec_sha256"] != claim["claim"][
        "job_spec_sha256"
    ] or support_execution["prior_job_generation"] != smoke_execution[
        "job_generation"
    ] or support_execution["prior_job_spec_sha256"] != smoke_execution[
        "job_spec_sha256"
    ]:
        raise RuntimeError("A7 frozen preflight job-generation/spec chain differs")
    return {
        "version": "a7-launch-freeze-validation-v1",
        "run_id": RUN_ID,
        "freeze_manifest": freeze_expected,
        "freeze_manifest_content_sha256": _sha_bytes(raw),
        "a3_logical_release_sha256": _sha(a3_release_path),
        "a3_logical_release": release,
        "job_claim": claim,
        "preflights": {
            key: {
                kind: _metadata_block(
                    manifest["preflights"][key][kind],
                    uri=(
                        SMOKE_URI if key == "smoke" and kind == "science" else
                        SUPPORT_URI if key == "support" and kind == "science" else
                        SMOKE_TERMINAL_URI if key == "smoke" else
                        SUPPORT_TERMINAL_URI
                    ),
                    label=f"{key} {kind}",
                ) for kind in ("science", "terminal")
            } for key in ("smoke", "support")
        },
        "preflight_content_sha256": {
            key: {
                kind: manifest["preflights"][key][kind]["sha256"]
                for kind in ("science", "terminal")
            } for key in ("smoke", "support")
        },
        "source_artifact_lock_sha256": manifest[
            "source_artifact_lock_sha256"
        ],
        "prefix_inventory_sha256": manifest["prefix_inventory_sha256"],
        "protocol_sha256": manifest["protocol"]["sha256"],
        "implementation_sha256": manifest["implementation_sha256"],
        "transport_repair_sha256": repair_receipts,
        "code_sha": expected_code_sha,
        "image": expected_image,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }


def _local_preflight_manifest(
    receipt: dict[str, Any], code_sha: str, image: str, root: Path,
    git_source_loader: GitSourceLoader,
) -> dict[str, Any]:
    # Importing the runner here is score-free: this path reads only frozen
    # source locks and constants and never formats or executes the outcome SQL.
    import run_a7_select_ladder as runner

    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image
    ) is None:
        raise RuntimeError("A7 preflight execution identity differs")
    local_paths = {
        "protocol": runner.PROTOCOL_PATH,
        "source_report": runner.SOURCE_REPORT_PATH,
        "baseline": runner.BASELINE_PATH,
        "baseline_vector": runner.BASELINE_VECTOR_PATH,
    }
    local_receipts: dict[str, str] = {}
    for key, relative in local_paths.items():
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"A7 preflight local source is absent: {relative}")
        digest = _sha(path)
        if _sha_bytes(git_source_loader(root, code_sha, str(relative))) != digest:
            raise RuntimeError(f"A7 preflight committed source differs: {relative}")
        local_receipts[key] = digest
    implementation = {
        key: _sha(root / relative) for key, relative in IMPLEMENTATION_PATHS.items()
    }
    if _validate_implementation_sources(
        implementation, code_sha=code_sha, root=root,
        git_source_loader=git_source_loader,
    ):
        raise RuntimeError("A7 preflight forbids post-commit transport repair")
    _expected, source_map, _report = runner._source_report()
    artifacts = runner._locked_source_artifacts(source_map)
    query_receipts = receipt.get("query_content_receipts")
    if not isinstance(query_receipts, dict):
        raise RuntimeError("A7 preflight query receipts differ")
    return {
        "code": {"commit_sha": code_sha},
        "image": {"uri": image},
        "protocol": {
            "path": str(runner.PROTOCOL_PATH),
            "sha256": local_receipts["protocol"],
        },
        "source_report": {
            "path": str(runner.SOURCE_REPORT_PATH),
            "sha256": local_receipts["source_report"],
        },
        "baseline": {
            "path": str(runner.BASELINE_PATH),
            "sha256": local_receipts["baseline"],
        },
        "baseline_vector": {
            "path": str(runner.BASELINE_VECTOR_PATH),
            "sha256": local_receipts["baseline_vector"],
        },
        "local_source_receipts": local_receipts,
        "implementation_sha256": implementation,
        "query_content_receipts": query_receipts,
        "frozen_law": FROZEN_CHOICES,
        "source_artifacts": artifacts,
        "source_artifact_lock_sha256": _source_artifact_lock(artifacts),
    }


def _expected_cloud_build_steps(image_tag: str) -> list[dict[str, Any]]:
    full_test = (
        "apt-get update\n"
        "apt-get install -y --no-install-recommends git libgomp1\n"
        "pip install --no-cache-dir '.[gcp,app,dev]'\n"
        "PYTHONPATH=. pytest\n"
    )
    smoke_commands = (
        ("python", "run_atlas_matched_diversity_mvp.py --help >/dev/null"),
        ("python", "run_atlas_historical_score_diagnostic.py --help >/dev/null"),
        ("python", "run_atlas_historical_score_diagnostic_v3.py --help >/dev/null"),
        ("python", "run_atlas_historical_score_diagnostic_v4.py --help >/dev/null"),
        ("python", "run_constraint_lattice_scorefree.py --help >/dev/null"),
        ("python", "aggregate_constraint_lattice_scorefree.py --help >/dev/null"),
        ("python", "run_constraint_lattice_support_census.py --help >/dev/null"),
        ("python", "aggregate_constraint_lattice_support_census.py --help >/dev/null"),
        ("python", "run_constraint_lattice_resource_preflight.py --help >/dev/null"),
        ("python", "run_recourse_aware_initial_scorefree.py --help >/dev/null"),
        ("python", "aggregate_recourse_aware_initial_scorefree.py --help >/dev/null"),
        ("python", "run_coherent_market_state_scorefree.py --help >/dev/null"),
        ("python", "aggregate_coherent_market_state_scorefree.py --help >/dev/null"),
        ("python", "run_coherent_market_state_historical_score.py --help >/dev/null"),
        ("python", "run_production_law_dependence_source_lock.py --help >/dev/null"),
        ("python", "run_production_law_dependence_remeasurement.py --help >/dev/null"),
        ("python", "run_a2a_rank_factor_split_census.py --help >/dev/null"),
        ("python", "run_a2a_production_law_dependence_remeasurement.py --help >/dev/null"),
        ("python", "finish_a2a_production_law_dependence_remeasurement.py --help >/dev/null"),
        ("bash", "cloud_a2a_production_law_dependence_remeasurement.sh"),
        ("bash", "watch_a2a_production_law_dependence_queue.sh"),
        ("python", "run_b1_corpus_tail_model.py --help >/dev/null"),
        ("python", "finish_b1_corpus_tail_model.py --help >/dev/null"),
        ("bash", "cloud_b1_corpus_tail_model.sh"),
        ("bash", "watch_b1_corpus_tail_queue.sh"),
        ("python", "run_b1_corpus_tail_panel_producer.py --help >/dev/null"),
        ("python", "run_b1_corpus_tail_shadow_transport.py --help >/dev/null"),
        ("python", "run_b1_authoritative_settlement.py --help >/dev/null"),
        ("bash", "cloud_b1_corpus_tail_shadow.sh"),
        ("python", "run_atlas_minimal_world_selection_c.py --help >/dev/null"),
        ("python", "run_a7_select_ladder.py --help >/dev/null"),
        ("python", "freeze_a7_select_ladder.py --help >/dev/null"),
        ("python", "finish_a7_select_ladder.py --help >/dev/null"),
        ("bash", "cloud_a7_select_ladder.sh"),
        ("bash", "watch_a7_select_ladder_queue.sh"),
        ("python", "run_lr8_training_source.py --help >/dev/null"),
        ("python", "finish_lr8_training_source_smoke.py --help >/dev/null"),
        ("bash", "cloud_lr8_training_source_smoke.sh"),
        ("bash", "watch_lr8_training_source_smoke_queue.sh"),
    )
    smoke = "".join(
        f"docker run --rm '{image_tag}' \\\n"
        f"  {kind} scripts/{command}\n"
        if kind == "python"
        else f"docker run --rm '{image_tag}' \\\n"
        f"  bash -n scripts/{command}\n"
        for kind, command in smoke_commands
    )
    common = {
        "env": [], "dir": "", "secretEnv": [], "status": "SUCCESS",
        "allowFailure": False, "allowExitCodes": [], "waitFor": [],
        "timeout": "", "script": "", "volumes": [],
        "automapSubstitutions": False, "exitCode": 0,
    }
    return [
        {
            **common, "name": "python:3.11-slim", "id": "full-test-suite",
            "entrypoint": "bash", "args": ["-ceu", full_test],
        },
        {
            **common, "name": "gcr.io/cloud-builders/docker",
            "id": "build-image", "entrypoint": "",
            "args": ["build", "-t", image_tag, "."],
        },
        {
            **common, "name": "gcr.io/cloud-builders/docker",
            "id": "smoke-atlas-mvp-runner", "entrypoint": "bash",
            "args": ["-ceu", smoke],
        },
    ]


def _validate_build_metadata(
    value: dict[str, Any], *, build_id: str, image: str, code_sha: str,
) -> None:
    meta = value.get("metadata", {})
    if value.get("id") != build_id and meta.get("build", {}).get("id") != build_id:
        # Synthetic and older gcloud JSON may omit id; absence is never accepted.
        raise RuntimeError("A7 build identity differs")
    digest = image.rsplit("@", 1)[-1]
    images = value.get("results", {}).get("images", [])
    substitutions = value.get("substitutions", {})
    # A caller-supplied substitution does not prove the submitted build context.
    # Only an exact direct-Git source resolved by Cloud Build to CODE_SHA is
    # accepted; local/storage uploads (including dirty worktrees) fail closed.
    source = value.get("source")
    provenance = value.get("sourceProvenance")
    expected_git_source = {"url": GIT_SOURCE_URL, "revision": code_sha}
    if source != {"gitSource": expected_git_source} or not isinstance(
        provenance, dict
    ) or not set(provenance) <= {"resolvedGitSource", "fileHashes"} or \
            provenance.get("resolvedGitSource") != expected_git_source or \
            provenance.get("fileHashes") not in (None, {}):
        raise RuntimeError("A7 build resolved Git source differs")
    declared_commits = {
        str(substitutions[key]) for key in ("COMMIT_SHA", "_CODE_SHA")
        if substitutions.get(key) is not None
    }
    image_tag = substitutions.get("_IMAGE")
    options = value.get("options")
    allowed_option_keys = {
        "machineType", "diskSizeGb", "substitutionOption",
        "dynamicSubstitutions", "automapSubstitutions",
        "logStreamingOption", "logging", "env", "secretEnv", "volumes",
        "sourceProvenanceHash", "requestedVerifyOption", "pool",
        "workerPool", "defaultLogsBucketBehavior", "enableStructuredLogging",
    }
    if not isinstance(options, dict) or not set(options) <= allowed_option_keys:
        raise RuntimeError("A7 build options population differs")
    normalized_options = {
        "machineType": options.get("machineType", "UNSPECIFIED"),
        "diskSizeGb": str(options.get("diskSizeGb", "100")),
        "substitutionOption": options.get("substitutionOption", "MUST_MATCH"),
        "dynamicSubstitutions": options.get("dynamicSubstitutions", False),
        "automapSubstitutions": options.get("automapSubstitutions", False),
        "logStreamingOption": options.get("logStreamingOption", "STREAM_DEFAULT"),
        "logging": options.get("logging", "LEGACY"),
        "env": options.get("env", []),
        "secretEnv": options.get("secretEnv", []),
        "volumes": options.get("volumes", []),
        "sourceProvenanceHash": options.get("sourceProvenanceHash", []),
        "requestedVerifyOption": options.get("requestedVerifyOption", "NOT_VERIFIED"),
        "pool": options.get("pool", {}),
        "workerPool": options.get("workerPool", ""),
        "defaultLogsBucketBehavior": options.get(
            "defaultLogsBucketBehavior",
            "DEFAULT_LOGS_BUCKET_BEHAVIOR_UNSPECIFIED",
        ),
        "enableStructuredLogging": options.get("enableStructuredLogging", False),
    }
    expected_options = {
        "machineType": "E2_HIGHCPU_8", "diskSizeGb": "100",
        "substitutionOption": "MUST_MATCH", "dynamicSubstitutions": False,
        "automapSubstitutions": False, "logStreamingOption": "STREAM_DEFAULT",
        "logging": "LEGACY", "env": [], "secretEnv": [], "volumes": [],
        "sourceProvenanceHash": [], "requestedVerifyOption": "NOT_VERIFIED",
        "pool": {}, "workerPool": "",
        "defaultLogsBucketBehavior": "DEFAULT_LOGS_BUCKET_BEHAVIOR_UNSPECIFIED",
        "enableStructuredLogging": False,
    }
    expected_steps = _expected_cloud_build_steps(str(image_tag))
    steps = value.get("steps")
    if not isinstance(steps, list) or len(steps) != len(expected_steps):
        raise RuntimeError("A7 build/test step population differs")
    normalized_steps = []
    for row in steps:
        if not isinstance(row, dict):
            raise RuntimeError("A7 build/test step differs")
        normalized_steps.append({
            "name": row.get("name"), "id": row.get("id"),
            "entrypoint": row.get("entrypoint", ""),
            "args": row.get("args", []), "env": row.get("env", []),
            "dir": row.get("dir", ""),
            "secretEnv": row.get("secretEnv", []),
            "status": row.get("status"),
            "allowFailure": row.get("allowFailure", False),
            "allowExitCodes": row.get("allowExitCodes", []),
            "waitFor": row.get("waitFor", []),
            "timeout": row.get("timeout", ""),
            "script": row.get("script", ""),
            "volumes": row.get("volumes", []),
            "automapSubstitutions": row.get("automapSubstitutions", False),
            "exitCode": row.get("exitCode", 0),
        })
    if normalized_options != expected_options or value.get("timeout") != "10800s" or \
            value.get("images") != [image_tag] or value.get("secrets") is not None or \
            value.get("availableSecrets") is not None or value.get(
                "serviceAccount"
            ) != BUILD_SERVICE_ACCOUNT or value.get(
                "logsBucket"
            ) != BUILD_LOGS_BUCKET or value.get("artifacts") != {
                "images": [image_tag]
            } or value.get("status") != "SUCCESS" or \
            normalized_steps != expected_steps or \
            any(
        value != code_sha for value in declared_commits
    ) or not isinstance(image_tag, str) or not any(
        row.get("digest") == digest and row.get("name") == image_tag
        for row in images
    ):
        raise RuntimeError("A7 build/test/image gate differs")


def _parse_checksum_ledger(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise RuntimeError(f"A7 checksum ledger differs: {path.name}")
        rows.append((match.group(1), match.group(2)))
    if not rows:
        raise RuntimeError(f"A7 checksum ledger is empty: {path.name}")
    return rows


def _validate_hash_ledger(
    path: Path, *, base: Path, expected: set[str],
) -> None:
    rows = _parse_checksum_ledger(path)
    if len(rows) != len(expected) or {name for _, name in rows} != expected:
        raise RuntimeError(f"A7 checksum population differs: {path.name}")
    for digest, name in rows:
        candidate = base / name
        try:
            candidate.resolve().relative_to(base.resolve())
        except ValueError as exc:
            raise RuntimeError("A7 checksum path escapes run directory") from exc
        if candidate.is_symlink() or not candidate.is_file() or _sha(candidate) != digest:
            raise RuntimeError(f"A7 completed artifact differs: {name}")


def _validate_lease_receipt(
    value: dict[str, Any], *, frozen: FrozenRun,
) -> dict[str, Any]:
    lease = value.get("lease")
    obj = value.get("object")
    if not isinstance(lease, dict) or not isinstance(obj, dict):
        raise RuntimeError("A7 historical-outcome lease receipt differs")
    if set(lease) != {
        "version", "run_id", "job", "code_sha", "image", "acquired_at",
    } or set(obj) != {
        "uri", "generation", "sha256", "bytes", "create_only",
    }:
        raise RuntimeError("A7 historical-outcome lease fields differ")
    fixed = {
        "version": "historical-outcome-active-v1",
        "run_id": frozen.run_id,
        "job": frozen.job,
        "code_sha": frozen.code_sha,
        "image": frozen.image,
    }
    if any(lease.get(key) != expected for key, expected in fixed.items()) or \
            not str(lease.get("acquired_at", "")):
        raise RuntimeError("A7 historical-outcome lease identity differs")
    expected = {
        "uri": LEASE_URI,
        "generation": str(obj.get("generation", "")),
        "metageneration": str(obj.get("metageneration", "1")),
        "bytes": int(obj.get("bytes", 0)),
        "sha256": str(obj.get("sha256", "")),
    }
    if obj.get("create_only") is not True:
        raise RuntimeError("A7 historical-outcome lease was not create-only")
    return _metadata_block(expected, uri=LEASE_URI, label="historical-outcome lease")


def _read_execution_ledger(path: Path, frozen: FrozenRun) -> str:
    rows = path.read_text(encoding="utf-8").splitlines()
    if len(rows) != 1:
        raise RuntimeError("A7 execution ledger is not exact one")
    fields = rows[0].split()
    if len(fields) != 3:
        raise RuntimeError("A7 execution ledger row differs")
    job, execution, uri = fields
    if job != frozen.job or uri != frozen.output_uri or \
            not execution.startswith(job + "-"):
        raise RuntimeError("A7 execution ledger identity differs")
    return execution


def _load_frozen_run(out: Path) -> tuple[FrozenRun, str, dict[str, Any]]:
    manifest = _load_json(out / "manifest.json", label="launch manifest")
    expected_keys = {
        "version", "run_id", "code_sha", "image", "build_id",
        "protocol_sha256", "freeze_manifest_uri",
        "freeze_manifest_generation", "freeze_manifest_sha256",
        "freeze_validation_sha256", "transport_repair_sha256",
        "a3_logical_release_sha256",
        "job_claim", "job_claim_receipt_sha256",
        "job", "job_uid", "job_generation", "job_spec_sha256",
        "service_account",
        "output_uri", "tasks", "parallelism", "cpu", "memory",
        "timeout_seconds", "max_retries", "uses_realized_outcomes",
        "production_change_licensed",
        "production_law_scorefree_transfer_licensed",
        "prospective_shadow_licensed", "job_update_mode",
    }
    if set(manifest) != expected_keys:
        raise RuntimeError("A7 launch manifest key population differs")
    fixed = {
        "version": "a7-select-ladder-launch-manifest-v1",
        "run_id": RUN_ID,
        "job": JOB,
        "service_account": SERVICE_ACCOUNT,
        "output_uri": RESULT_URI,
        "freeze_manifest_uri": FREEZE_URI,
        "tasks": 1,
        "parallelism": 1,
        "cpu": CPU,
        "memory": MEMORY,
        "timeout_seconds": int(TIMEOUT_SECONDS),
        "max_retries": 0,
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "job_update_mode": "reuse-only-update-existing",
    }
    if any(not _exact_json_value(
        manifest.get(key), expected,
    ) for key, expected in fixed.items()) or \
            re.fullmatch(r"[0-9a-f]{40}", str(
                manifest.get("code_sha", "")
            )) is None or re.fullmatch(r".+@sha256:[0-9a-f]{64}", str(
                manifest.get("image", "")
            )) is None or re.fullmatch(r"[1-9][0-9]*", str(
                manifest.get("freeze_manifest_generation", "")
            )) is None:
        raise RuntimeError("A7 launch manifest differs")
    repairs = manifest.get("transport_repair_sha256")
    if not isinstance(repairs, dict) or not set(repairs) <= set(
        TRANSPORT_REPAIR_ENV
    ) or any(re.fullmatch(r"[0-9a-f]{64}", str(value)) is None
             for value in repairs.values()):
        raise RuntimeError("A7 launch transport-repair receipt differs")
    for key in (
        "protocol_sha256", "freeze_manifest_sha256",
        "freeze_validation_sha256", "a3_logical_release_sha256",
        "job_claim_receipt_sha256",
        "job_spec_sha256",
    ):
        _hex(manifest.get(key), length=64, label=f"launch {key}")
    if not str(manifest.get("job_uid", "")) or not str(
        manifest.get("job_generation", "")
    ).isdigit():
        raise RuntimeError("A7 reused job receipt differs")
    frozen = FrozenRun(
        run_id=RUN_ID,
        code_sha=str(manifest["code_sha"]),
        image=str(manifest["image"]),
        build_id=str(manifest["build_id"]),
        protocol_sha256=str(manifest["protocol_sha256"]),
        freeze_manifest_uri=str(manifest["freeze_manifest_uri"]),
        freeze_manifest_generation=str(manifest["freeze_manifest_generation"]),
        freeze_manifest_sha256=str(manifest["freeze_manifest_sha256"]),
        freeze_validation_sha256=str(manifest["freeze_validation_sha256"]),
        a3_logical_release_sha256=str(manifest["a3_logical_release_sha256"]),
        job=JOB,
        job_uid=str(manifest["job_uid"]),
        job_generation=str(manifest["job_generation"]),
        job_spec_sha256=str(manifest["job_spec_sha256"]),
        job_claim_receipt_sha256=str(manifest["job_claim_receipt_sha256"]),
    )
    claim = _validate_job_claim_receipt(
        manifest.get("job_claim"), code_sha=frozen.code_sha,
        image=frozen.image, protocol_sha256=frozen.protocol_sha256,
        a3_logical_release_sha256=frozen.a3_logical_release_sha256,
        job_uid=frozen.job_uid,
    )
    if _sha_bytes(_canonical_json(claim)) != frozen.job_claim_receipt_sha256:
        raise RuntimeError("A7 launch job-claim receipt differs")
    execution = _read_execution_ledger(out / "executions.txt", frozen)
    return frozen, execution, manifest


def _validate_reused_job_receipts(
    before: dict[str, Any], after: dict[str, Any], frozen: FrozenRun, *,
    expected_before_generation: str | None = None,
    expected_before_spec_sha256: str | None = None,
) -> None:
    before_meta, after_meta = before.get("metadata", {}), after.get("metadata", {})
    before_generation = _json_positive_int(
        before_meta.get("generation"), label="reused job before generation",
    )
    after_generation = _json_positive_int(
        after_meta.get("generation"), label="reused job after generation",
    )
    if before_meta.get("name") != frozen.job or after_meta.get("name") != \
            frozen.job or not frozen.job_uid or before_meta.get("uid") != \
            frozen.job_uid or after_meta.get("uid") != frozen.job_uid or \
            after_generation <= before_generation or str(after_generation) != \
            frozen.job_generation:
        raise RuntimeError("A7 reuse-only job identity differs")
    if (expected_before_generation is None) != (
        expected_before_spec_sha256 is None
    ):
        raise RuntimeError("A7 prior job-chain receipt is incomplete")
    if expected_before_generation is not None:
        _validate_prior_job_state(
            before, job_uid=frozen.job_uid,
            job_generation=expected_before_generation,
            job_spec_sha256=str(expected_before_spec_sha256),
        )
    after_spec_sha = _job_spec_sha256(after)
    if frozen.job_spec_sha256 and after_spec_sha != frozen.job_spec_sha256:
        raise RuntimeError("A7 post-update job spec receipt differs")


def _load_preflight_run(
    out: Path, *, mode: str,
) -> tuple[PreflightRun, str, dict[str, Any], dict[str, Any]]:
    manifest = _load_json(out / "manifest.json", label=f"{mode} launch manifest")
    if set(manifest) != PREFLIGHT_LAUNCH_MANIFEST_KEYS:
        raise RuntimeError("A7 preflight launch-manifest fields differ")
    target = SMOKE_URI if mode == "real-artifact-smoke" else SUPPORT_URI
    fixed = {
        "version": "a7-select-ladder-preflight-launch-manifest-v1",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "mode": mode,
        "job": JOB,
        "service_account": SERVICE_ACCOUNT,
        "output_uri": target,
        "tasks": 1,
        "parallelism": 1,
        "cpu": CPU,
        "memory": MEMORY,
        "timeout_seconds": int(TIMEOUT_SECONDS),
        "max_retries": 0,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "job_update_mode": "reuse-only-update-existing",
    }
    if any(not _exact_json_value(
        manifest.get(key), expected,
    ) for key, expected in fixed.items()) or \
            re.fullmatch(r"[0-9a-f]{40}", str(
                manifest.get("code_sha", "")
            )) is None or re.fullmatch(r".+@sha256:[0-9a-f]{64}", str(
                manifest.get("image", "")
            )) is None or not str(manifest.get("job_uid", "")) or \
            re.fullmatch(r"[1-9][0-9]*", str(
                manifest.get("job_generation", "")
            )) is None or re.fullmatch(r"[1-9][0-9]*", str(
                manifest.get("prior_job_generation", "")
            )) is None:
        raise RuntimeError("A7 preflight launch-manifest identity differs")
    for key in (
        "protocol_sha256", "a3_logical_release_sha256",
        "job_claim_receipt_sha256", "job_spec_sha256",
        "prior_job_spec_sha256",
    ):
        _hex(manifest.get(key), length=64, label=f"preflight {key}")
    run = PreflightRun(
        mode=mode,
        code_sha=str(manifest["code_sha"]),
        image=str(manifest["image"]),
        build_id=str(manifest["build_id"]),
        protocol_sha256=str(manifest["protocol_sha256"]),
        a3_logical_release_sha256=str(manifest["a3_logical_release_sha256"]),
        job_claim_receipt_sha256=str(manifest["job_claim_receipt_sha256"]),
        job_uid=str(manifest["job_uid"]),
        job_generation=str(manifest["job_generation"]),
        job_spec_sha256=str(manifest["job_spec_sha256"]),
        prior_job_generation=str(manifest["prior_job_generation"]),
        prior_job_spec_sha256=str(manifest["prior_job_spec_sha256"]),
        target_uri=target,
    )
    ledger = (out / "executions.txt").read_text(encoding="utf-8").splitlines()
    if len(ledger) != 1 or len(ledger[0].split()) != 3:
        raise RuntimeError("A7 preflight execution ledger differs")
    ledger_job, execution, ledger_uri = ledger[0].split()
    if ledger_job != JOB or ledger_uri != target or not execution.startswith(
        JOB + "-"
    ):
        raise RuntimeError("A7 preflight execution-ledger identity differs")
    claim = _load_json(out / "job-claim-receipt.json", label="job claim receipt")
    if _sha(out / "job-claim-receipt.json") != run.job_claim_receipt_sha256 or \
            manifest.get("job_claim") != claim:
        raise RuntimeError("A7 preflight job-claim receipt binding differs")
    validated_claim = _validate_job_claim_receipt(
        claim, code_sha=run.code_sha, image=run.image,
        protocol_sha256=run.protocol_sha256,
        a3_logical_release_sha256=run.a3_logical_release_sha256,
        job_uid=run.job_uid,
    )
    release = _validate_a3_release(out / "a3-logical-release.json")
    if _sha(out / "a3-logical-release.json") != \
            run.a3_logical_release_sha256:
        raise RuntimeError("A7 preflight A3 logical-release binding differs")
    build = _load_json(out / "build-metadata.json", label="build metadata")
    _validate_build_metadata(
        build, build_id=run.build_id, image=run.image, code_sha=run.code_sha,
    )
    dummy = FrozenRun(
        run_id=RUN_ID, code_sha=run.code_sha, image=run.image,
        build_id=run.build_id, protocol_sha256=run.protocol_sha256,
        freeze_manifest_uri=FREEZE_URI, freeze_manifest_generation="1",
        freeze_manifest_sha256="0" * 64,
        freeze_validation_sha256="0" * 64,
        a3_logical_release_sha256=run.a3_logical_release_sha256,
        job=JOB, job_uid=run.job_uid, job_generation=run.job_generation,
        job_spec_sha256=run.job_spec_sha256,
    )
    if mode == "real-artifact-smoke":
        prior_generation = str(validated_claim["claim"]["job_generation"])
        prior_spec_sha = str(validated_claim["claim"]["job_spec_sha256"])
    else:
        prior_out = out.parent / "smoke"
        _validate_preflight_complete(prior_out, mode="real-artifact-smoke")
        prior_terminal = _load_json(
            prior_out / "terminal-receipt.json", label="smoke terminal receipt",
        )
        _validate_preflight_terminal_receipt(
            prior_terminal, mode="real-artifact-smoke",
            science_object=prior_terminal.get("science_object", {}),
            claim=validated_claim, code_sha=run.code_sha, image=run.image,
            protocol_sha256=run.protocol_sha256,
            a3_logical_release_sha256=run.a3_logical_release_sha256,
            build_id=run.build_id,
        )
        prior_generation = str(prior_terminal["execution"]["job_generation"])
        prior_spec_sha = str(prior_terminal["execution"]["job_spec_sha256"])
    if run.prior_job_generation != prior_generation or \
            run.prior_job_spec_sha256 != prior_spec_sha:
        raise RuntimeError("A7 preflight manifest prior-job chain differs")
    before = _load_json(out / "job-before.json", label="preflight job before")
    after = _load_json(out / "job-after.json", label="preflight job after")
    _validate_reused_job_receipts(
        before, after, dummy,
        expected_before_generation=prior_generation,
        expected_before_spec_sha256=prior_spec_sha,
    )
    if _validate_updated_job_spec(
        after, code_sha=run.code_sha, image=run.image, mode=mode,
    ) != run.job_spec_sha256:
        raise RuntimeError("A7 preflight post-update job spec differs")
    return run, execution, validated_claim, release


def _execution_metadata(name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="a7-gcloud-json-") as directory:
        raw_path = Path(directory) / "execution.raw.json"
        canonical_path = Path(directory) / "execution.json"
        with raw_path.open("xb") as handle:
            subprocess.run([
                "gcloud", "run", "jobs", "executions", "describe", name,
                "--project", PROJECT, "--region", REGION, "--format=json",
            ], check=True, stdout=handle)
        value = _canonicalize_external_json(
            raw_path, canonical_path, label="gcloud execution metadata",
        )
        raw_path.unlink()
    if not isinstance(value, dict):
        raise RuntimeError("A7 execution metadata is not an object")
    return value


def _as_count(value: object) -> int:
    return _json_nonnegative_int(value, label="execution counter")


def _execution_count(status: Mapping[str, Any], key: str) -> int:
    # Cloud Run's protobuf JSON omits zero-valued counters. An explicit value,
    # when present, must be a canonical JSON integer.
    return 0 if key not in status else _as_count(status[key])


def _validate_execution(
    metadata: dict[str, Any], *, execution: str, frozen: FrozenRun,
) -> None:
    meta = metadata.get("metadata", {})
    labels = meta.get("labels", {})
    status = metadata.get("status", {})
    completed = [row for row in status.get("conditions", [])
                 if row.get("type") == "Completed"]
    if meta.get("name") != execution or _json_positive_int(
        meta.get("generation"), label="execution generation",
    ) != 1 or \
            labels.get("run.googleapis.com/job") != frozen.job or \
            labels.get("run.googleapis.com/jobUid") != frozen.job_uid or \
            str(labels.get("run.googleapis.com/jobGeneration")) != \
            frozen.job_generation or _json_positive_int(
                status.get("observedGeneration"),
                label="execution observed generation",
            ) != 1:
        raise RuntimeError("A7 execution identity differs")
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            _execution_count(status, "succeededCount") != 1 or \
            _execution_count(status, "failedCount") != 0 or \
            _execution_count(status, "cancelledCount") != 0 or \
            _execution_count(status, "retriedCount") != 0 or \
            not status.get("completionTime"):
        raise RuntimeError("A7 execution is not strict terminal success")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if _json_positive_int(
        spec.get("parallelism"), label="execution parallelism",
    ) != 1 or _json_positive_int(
        spec.get("taskCount"), label="execution task count",
    ) != 1 or \
            len(containers) != 1:
        raise RuntimeError("A7 execution task shape differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        or not isinstance(row["name"], str) or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise RuntimeError("A7 execution environment rows differ")
    env = {row.get("name"): str(row.get("value", "")) for row in env_rows}
    expected_env = {
        "CODE_SHA": frozen.code_sha,
        "ANALYSIS_IMAGE": frozen.image,
        "A7_FREEZE_MANIFEST_URI": frozen.freeze_manifest_uri,
        "A7_FREEZE_MANIFEST_GENERATION": frozen.freeze_manifest_generation,
        "A7_FREEZE_MANIFEST_SHA256": frozen.freeze_manifest_sha256,
    }
    expected_args = [
        "scripts/run_a7_select_ladder.py",
        "--output-uri", frozen.output_uri,
        "--freeze-manifest-uri", frozen.freeze_manifest_uri,
        "--freeze-manifest-generation", frozen.freeze_manifest_generation,
        "--freeze-manifest-sha256", frozen.freeze_manifest_sha256,
    ]
    if len(env) != len(env_rows) or env != expected_env or \
            container.get("image") != frozen.image or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or \
            container.get("workingDir", "") != "" or container.get(
                "volumeMounts", []
            ) != [] or container.get("startupProbe") not in (None, {}) or \
            container.get("resources", {}).get("limits") != {
                "cpu": CPU, "memory": MEMORY,
            } or task.get("volumes", []) != [] or _json_nonnegative_int(
                task.get("maxRetries"), label="execution max retries",
            ) != 0 or type(task.get("timeoutSeconds")) is not str or \
            task.get("timeoutSeconds") != TIMEOUT_SECONDS or \
            task.get("serviceAccountName") != frozen.service_account:
        raise RuntimeError("A7 execution contract differs")


def _validate_preflight_execution(
    metadata: dict[str, Any], *, execution: str, run: PreflightRun,
) -> dict[str, Any]:
    meta = metadata.get("metadata", {})
    labels = meta.get("labels", {})
    status = metadata.get("status", {})
    completed = [
        row for row in status.get("conditions", [])
        if row.get("type") == "Completed"
    ]
    if meta.get("name") != execution or _json_positive_int(
        meta.get("generation"), label="preflight execution generation",
    ) != 1 or \
            labels.get("run.googleapis.com/job") != JOB or \
            labels.get("run.googleapis.com/jobUid") != run.job_uid or \
            str(labels.get("run.googleapis.com/jobGeneration")) != \
            run.job_generation or _json_positive_int(
                status.get("observedGeneration"),
                label="preflight execution observed generation",
            ) != 1:
        raise RuntimeError("A7 preflight execution identity differs")
    counters = {
        "succeeded": _execution_count(status, "succeededCount"),
        "failed": _execution_count(status, "failedCount"),
        "cancelled": _execution_count(status, "cancelledCount"),
        "retried": _execution_count(status, "retriedCount"),
    }
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            counters != {
                "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
            } or not status.get("completionTime"):
        raise RuntimeError("A7 preflight is not strict terminal success")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if _json_positive_int(
        spec.get("parallelism"), label="preflight execution parallelism",
    ) != 1 or _json_positive_int(
        spec.get("taskCount"), label="preflight execution task count",
    ) != 1 or \
            len(containers) != 1:
        raise RuntimeError("A7 preflight execution task shape differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        or not isinstance(row["name"], str) or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise RuntimeError("A7 preflight execution environment rows differ")
    env = {row.get("name"): str(row.get("value", "")) for row in env_rows}
    mode_flag = "--smoke" if run.mode == "real-artifact-smoke" else \
        "--support-census"
    expected_args = [
        "scripts/run_a7_select_ladder.py", mode_flag,
        "--preflight-receipt-uri", run.target_uri,
    ]
    if len(env) != len(env_rows) or env != {
        "CODE_SHA": run.code_sha, "ANALYSIS_IMAGE": run.image,
    } or container.get("image") != run.image or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or \
            container.get("workingDir", "") != "" or container.get(
                "volumeMounts", []
            ) != [] or container.get("startupProbe") not in (None, {}) or \
            container.get("resources", {}).get("limits") != {
                "cpu": CPU, "memory": MEMORY,
            } or task.get("volumes", []) != [] or _json_nonnegative_int(
                task.get("maxRetries"), label="preflight execution max retries",
            ) != 0 or type(task.get("timeoutSeconds")) is not str or \
            task.get("timeoutSeconds") != TIMEOUT_SECONDS or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("A7 preflight execution contract differs")
    contract = _registered_execution_contract(
        mode=run.mode, code_sha=run.code_sha, image=run.image,
    )
    return {
        "name": execution,
        "generation": 1,
        "job": JOB,
        "job_uid": run.job_uid,
        "job_generation": run.job_generation,
        "job_spec_sha256": run.job_spec_sha256,
        "prior_job_generation": run.prior_job_generation,
        "prior_job_spec_sha256": run.prior_job_spec_sha256,
        "completion_time": str(status["completionTime"]),
        "completed_condition": True,
        "counters": counters,
        "spec_sha256": _sha_bytes(_canonical_json(spec)),
        "contract": contract,
        "contract_sha256": _sha_bytes(_canonical_json(contract)),
    }


def _gcs_parts(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None:
        raise RuntimeError("A7 GCS URI differs")
    return match.group(1), match.group(2)


class _StorageReader:
    def __init__(self) -> None:
        self.client = storage.Client(project=PROJECT)

    def inventory(self, uri_prefix: str) -> dict[str, dict[str, Any]]:
        bucket_name, object_prefix = _gcs_parts(uri_prefix)
        result: dict[str, dict[str, Any]] = {}
        for blob in self.client.list_blobs(bucket_name, prefix=object_prefix):
            blob.reload()
            uri = f"gs://{bucket_name}/{blob.name}"
            if uri in result:
                raise RuntimeError("A7 live object inventory contains duplicates")
            result[uri] = self._metadata(uri, blob)
        return result

    @staticmethod
    def _metadata(uri: str, blob: Any) -> dict[str, Any]:
        return {
            "uri": uri,
            "generation": str(blob.generation or ""),
            "metageneration": str(blob.metageneration or ""),
            "bytes": int(blob.size or 0),
            "sha256": "",  # content SHA is checked after pinned download
            "md5_hash": str(blob.md5_hash or ""),
            "crc32c": str(blob.crc32c or ""),
            "etag": str(blob.etag or ""),
            "time_created": (
                blob.time_created.isoformat() if blob.time_created else ""
            ),
            "updated": blob.updated.isoformat() if blob.updated else "",
        }

    def load(self, uri: str, generation: str) -> tuple[dict[str, Any], bytes]:
        if re.fullmatch(r"[1-9][0-9]*", generation) is None:
            raise RuntimeError("A7 generation-pinned read lacks generation")
        bucket_name, name = _gcs_parts(uri)
        blob = self.client.bucket(bucket_name).blob(
            name, generation=int(generation),
        )
        raw = blob.download_as_bytes(if_generation_match=int(generation))
        blob.reload(if_generation_match=int(generation))
        metadata = self._metadata(uri, blob)
        metadata["sha256"] = _sha_bytes(raw)
        if metadata["generation"] != generation or \
                metadata["bytes"] != len(raw):
            raise RuntimeError(f"A7 generation-pinned object changed: {uri}")
        return metadata, raw

    def create(self, uri: str, raw: bytes) -> tuple[dict[str, Any], bytes]:
        bucket_name, name = _gcs_parts(uri)
        blob = self.client.bucket(bucket_name).blob(name)
        blob.upload_from_string(
            raw, content_type="application/json", if_generation_match=0,
        )
        generation = str(blob.generation or "")
        if re.fullmatch(r"[1-9][0-9]*", generation) is None:
            raise RuntimeError("A7 create-only object lacks generation")
        metadata, downloaded = self.load(uri, generation)
        if downloaded != raw:
            raise RuntimeError("A7 create-only object changed after upload")
        return metadata, downloaded

    def create_or_validate(
        self, uri: str, raw: bytes,
    ) -> tuple[dict[str, Any], bytes]:
        """Create once, or recover only the byte-identical prior creation."""
        try:
            return self.create(uri, raw)
        except PreconditionFailed:
            inventory = self.inventory(uri)
            if set(inventory) != {uri}:
                raise RuntimeError(
                    "A7 existing create-only object inventory differs"
                )
            generation = str(inventory[uri].get("generation", ""))
            metadata, downloaded = self.load(uri, generation)
            if downloaded != raw:
                raise RuntimeError("A7 existing create-only object differs")
            return metadata, downloaded


def create_job_claim(
    *, code_sha: str, image: str, job_metadata: Mapping[str, Any],
    a3_release_path: Path, v1_failure_release_path: Path,
    v1_failure_release_object_path: Path, receipt_path: Path,
    root: Path = ROOT,
    git_source_loader: GitSourceLoader = _git_blob,
    object_loader: ObjectLoader | None = None,
    object_creator: ObjectCreator | None = None,
) -> dict[str, Any]:
    # The close-only v1 module is needed only while transferring ownership;
    # historical runner/harvest imports do not depend on that administrative
    # implementation after the immutable v2 claim has bound its receipts.
    from close_a7_select_ladder_failed_preflight_v1 import (
        validate_failure_release_files,
    )

    if receipt_path.exists():
        raise RuntimeError("A7 immutable durable job-claim receipt exists")
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image
    ) is None:
        raise RuntimeError("A7 job-claim execution identity differs")
    _validate_a3_release(a3_release_path)
    release_sha = _sha(a3_release_path)
    v1_release, v1_object_receipt = validate_failure_release_files(
        v1_failure_release_path, v1_failure_release_object_path,
        require_next_run_id=RUN_ID,
    )
    v1_release_raw = v1_failure_release_path.read_bytes()
    v1_object_raw = v1_failure_release_object_path.read_bytes()
    v1_object = v1_object_receipt["object"]
    if object_loader is None:
        object_loader = _StorageReader().load
    live_metadata, live_raw = object_loader(
        V1_FAILURE_RELEASE_URI, str(v1_object["generation"]),
    )
    _validate_loaded_object(
        live_metadata, live_raw, v1_object,
        label="v1 failed-preflight logical release",
    )
    if live_raw != v1_release_raw:
        raise RuntimeError("A7-v2 v1 failed-preflight release changed")
    v1_binding = _validate_v1_failed_preflight_release_binding({
        "prior_run_id": v1_release["run_id"],
        "next_run_id": v1_release["next_run_id"],
        "release_sha256": _sha_bytes(v1_release_raw),
        "object_receipt": v1_object_receipt,
        "object_receipt_sha256": _sha_bytes(v1_object_raw),
    })
    protocol = root / PROTOCOL_PATH
    if not protocol.is_file():
        raise RuntimeError("A7 job-claim protocol is absent")
    protocol_sha = _sha(protocol)
    if _sha_bytes(
        git_source_loader(root, code_sha, str(PROTOCOL_PATH))
    ) != protocol_sha:
        raise RuntimeError("A7 job-claim protocol differs from commit")
    meta = job_metadata.get("metadata", {})
    uid = str(meta.get("uid", ""))
    generation = str(meta.get("generation", ""))
    if meta.get("name") != JOB or not uid or re.fullmatch(
        r"[1-9][0-9]*", generation
    ) is None:
        raise RuntimeError("A7 job-claim reused-job identity differs")
    claim = _job_claim_body(
        code_sha=code_sha, image=image, protocol_sha256=protocol_sha,
        a3_logical_release_sha256=release_sha,
        v1_failed_preflight_release=v1_binding, job_uid=uid,
        job_generation=generation, job_spec_sha256=_job_spec_sha256(job_metadata),
        claimed_at=datetime.now(timezone.utc).isoformat(),
    )
    raw = _canonical_json(claim)
    if object_creator is None:
        object_creator = _StorageReader().create
    metadata, downloaded = object_creator(JOB_CLAIM_URI, raw)
    if downloaded != raw:
        raise RuntimeError("A7 durable job claim changed after create")
    normalized = _metadata_block(
        {**metadata, "sha256": _sha_bytes(downloaded)},
        uri=JOB_CLAIM_URI, label="job claim",
    )
    value = {
        "claim": claim,
        "object": {**normalized, "create_only": True},
    }
    _validate_job_claim_receipt(
        value, code_sha=code_sha, image=image,
        protocol_sha256=protocol_sha,
        a3_logical_release_sha256=release_sha, job_uid=uid,
        job_generation=generation,
    )
    _write_new(receipt_path, _canonical_json(value))
    return value


def _validate_result_inventory(
    inventory: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    if set(inventory) != {RESULT_URI}:
        raise RuntimeError("A7 result object inventory differs")
    value = dict(inventory[RESULT_URI])
    generation = str(value.get("generation", ""))
    metageneration = str(value.get("metageneration", ""))
    size = _positive_int(value.get("bytes"), label="result object bytes")
    if value.get("uri") != RESULT_URI or re.fullmatch(
        r"[1-9][0-9]*", generation
    ) is None or metageneration != "1":
        raise RuntimeError("A7 result object metadata differs")
    value.update({"generation": generation, "metageneration": "1", "bytes": size})
    return value


def _preflight_expected_uris(
    mode: str, *, include_current_terminal: bool = False,
) -> tuple[str, ...]:
    if mode == "real-artifact-smoke":
        values = (JOB_CLAIM_URI, SMOKE_URI)
        return values + ((SMOKE_TERMINAL_URI,) if include_current_terminal else ())
    if mode == "support-census":
        values = (
            JOB_CLAIM_URI, SMOKE_URI, SMOKE_TERMINAL_URI, SUPPORT_URI,
        )
        return values + ((SUPPORT_TERMINAL_URI,) if include_current_terminal else ())
    raise RuntimeError("A7 preflight mode differs")


def _validate_preflight_inventory(
    inventory: Mapping[str, dict[str, Any]], *, mode: str,
    claim: Mapping[str, Any], include_current_terminal: bool = False,
) -> dict[str, dict[str, Any]]:
    expected_uris = _preflight_expected_uris(
        mode, include_current_terminal=include_current_terminal,
    )
    if set(inventory) != set(expected_uris):
        raise RuntimeError("A7 preflight object inventory differs")
    result: dict[str, dict[str, Any]] = {}
    for uri in expected_uris:
        value = dict(inventory[uri])
        generation = str(value.get("generation", ""))
        metageneration = str(value.get("metageneration", ""))
        size = _positive_int(
            value.get("bytes"), label="preflight inventory bytes",
        )
        if value.get("uri") != uri or re.fullmatch(
            r"[1-9][0-9]*", generation
        ) is None or metageneration != "1":
            raise RuntimeError("A7 preflight object metadata differs")
        result[uri] = {
            "uri": uri, "generation": generation,
            "metageneration": "1", "bytes": size,
        }
    claim_expected = _metadata_block(
        claim["object"], uri=JOB_CLAIM_URI, label="job claim",
    )
    if any(result[JOB_CLAIM_URI][key] != claim_expected[key]
           for key in result[JOB_CLAIM_URI]):
        raise RuntimeError("A7 preflight job-claim inventory differs")
    return result


def _validate_final_preflight_inventory(
    final_inventory: Mapping[str, Mapping[str, Any]],
    expected_receipts: Sequence[Mapping[str, Any]],
    pinned_objects: Mapping[str, tuple[Mapping[str, Any], bytes]],
) -> None:
    inventory_fields = ("uri", "generation", "metageneration", "bytes")
    expected = {str(row["uri"]): dict(row) for row in expected_receipts}
    if set(expected) != set(final_inventory) or set(expected) != set(
        pinned_objects
    ):
        raise RuntimeError("A7 preflight terminal inventory differs")
    for uri, receipt in expected.items():
        if dict(final_inventory[uri]) != {
            key: receipt[key] for key in inventory_fields
        }:
            raise RuntimeError("A7 preflight terminal inventory differs")
        metadata, raw = pinned_objects[uri]
        _validate_loaded_object(
            metadata, raw, receipt, label="final preflight pinned object",
        )


def _canonical_query_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError("A7 score-free query contains non-finite data")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise RuntimeError("A7 score-free query contains non-finite decimal")
        return {"decimal": str(value.normalize())}
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return [_canonical_query_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise RuntimeError("A7 score-free query key differs")
        return {key: _canonical_query_value(item)
                for key, item in sorted(value.items())}
    if hasattr(value, "isoformat"):
        return {"isoformat": str(value.isoformat())}
    raise RuntimeError("A7 score-free query value type differs")


def _records_content_receipt(
    records: Sequence[Mapping[str, Any]], columns: tuple[str, ...],
) -> dict[str, Any]:
    encoded: list[str] = []
    for raw in records:
        if set(raw) != set(columns):
            raise RuntimeError("A7 query record schema differs")
        row = {column: _canonical_query_value(raw[column]) for column in columns}
        encoded.append(json.dumps(
            row, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))
    encoded.sort()
    payload = ("[" + ",".join(encoded) + "]").encode("utf-8")
    return {
        "columns": list(columns), "rows": len(encoded),
        "sha256": _sha_bytes(payload),
    }


def _query_content_receipt(frame: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    if tuple(str(value) for value in frame.columns) != columns:
        raise RuntimeError("A7 score-free query schema differs")
    return _records_content_receipt(frame.to_dict("records"), columns)


def _scorefree_queries() -> tuple[Any, Any]:
    client = bigquery.Client(project=PROJECT)
    params = [bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SOURCE_PANEL_IDS),
    )]
    return _query(client, SOURCE_SQL, params), _query(client, PLAYER_SQL)


def _array_receipt(value: np.ndarray) -> dict[str, Any]:
    array = np.ascontiguousarray(value)
    header = json.dumps({
        "dtype": array.dtype.str, "shape": list(array.shape),
    }, sort_keys=True, separators=(",", ":")).encode("ascii")
    return {
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "sha256": _sha_bytes(header + b"\0" + array.tobytes(order="C")),
    }


def _identity(values: Sequence[object]) -> tuple[str, ...]:
    result = tuple(sorted(str(value) for value in values))
    if len(result) != 9 or len(set(result)) != 9 or any(not value for value in result):
        raise RuntimeError("A7 result roster identity differs")
    return result


def _candidate_identities(batch: Any) -> list[list[str]]:
    result = [list(_identity(lineup.ids)) for lineup in batch.candidates]
    if len(result) != len({tuple(value) for value in result}):
        raise RuntimeError("A7 replay candidate identities repeat")
    return result


def _candidate_tags(batch: Any) -> list[list[str]]:
    result: list[list[str]] = []
    for lineup in batch.candidates:
        tags = sorted(str(value) for value in batch.all_tags.get(lineup.ids, ()))
        if not tags or len(tags) != len(set(tags)):
            raise RuntimeError("A7 replay candidate tags differ")
        result.append(tags)
    return result


def _artifact_map(manifest: Mapping[str, Any]) -> dict[tuple[str, int, int], dict[str, Any]]:
    rows = _validate_source_artifacts(manifest.get("source_artifacts"))
    return {
        (row["panel_run_id"], row["season"], row["week"]): row
        for row in rows
    }


def _validate_artifact_result_receipts(
    result_rows: object, frozen_rows: Sequence[Mapping[str, Any]],
) -> None:
    if not isinstance(result_rows, list) or len(result_rows) != 270:
        raise RuntimeError("A7 result source-artifact population differs")
    expected = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in frozen_rows
    }
    expected_order = [
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"]))
        for row in frozen_rows
    ]
    seen: set[tuple[str, int, int]] = set()
    observed_order: list[tuple[str, int, int]] = []
    panel_seed = {panel: seed for seed, panel in enumerate(SOURCE_PANEL_IDS)}
    for raw in result_rows:
        if not isinstance(raw, dict) or set(raw) != {
            "panel_run_id", "season", "week", "uri", "sha256",
            "generation", "metageneration", "bytes", "candidate_rows",
            "seed", "md5_hash", "crc32c",
        }:
            raise RuntimeError("A7 result source-artifact row differs")
        key = (str(raw.get("panel_run_id", "")), int(raw.get("season", 0)),
               int(raw.get("week", 0)))
        source = expected.get(key)
        if source is None or key in seen or raw.get("seed") != panel_seed.get(
            key[0]
        ) or str(raw.get("metageneration", "")) != "1" or re.fullmatch(
            r"[A-Za-z0-9+/]+={0,2}", str(raw.get("md5_hash", ""))
        ) is None or re.fullmatch(
            r"[A-Za-z0-9+/]+={0,2}", str(raw.get("crc32c", ""))
        ) is None:
            raise RuntimeError("A7 result source-artifact identity differs")
        seen.add(key)
        observed_order.append(key)
        for result_key, source_key in (
            ("uri", "uri"), ("sha256", "sha256"),
            ("generation", "generation"), ("bytes", "bytes"),
            ("candidate_rows", "candidate_rows"),
        ):
            if raw.get(result_key) != source[source_key]:
                raise RuntimeError("A7 result source-artifact receipt differs")
    if set(expected) != seen or observed_order != expected_order:
        raise RuntimeError("A7 result source-artifact lattice differs")


def _decode_frozen_artifact(
    source: Mapping[str, Any], loader: ObjectLoader,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    metadata, raw = loader(str(source["uri"]), str(source["generation"]))
    expected = {
        "uri": str(source["uri"]),
        "generation": str(source["generation"]),
        "metageneration": str(metadata.get("metageneration", "")),
        "bytes": int(source["bytes"]),
        "sha256": str(source["sha256"]),
    }
    if expected["metageneration"] != "1":
        raise RuntimeError("A7 source artifact metageneration differs")
    _validate_loaded_object(metadata, raw, expected, label="source artifact")
    md5_hash = str(metadata.get("md5_hash", ""))
    crc32c = str(metadata.get("crc32c", ""))
    if re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", md5_hash) is None or \
            re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", crc32c) is None:
        raise RuntimeError("A7 source artifact storage checksums differ")
    artifact = decode_score_artifact(raw, str(source["sha256"]))
    required = {"cand_ix", "totals", "player_ids", "player_draws"}
    if not required <= set(artifact):
        raise RuntimeError("A7 source artifact lacks replay inputs")
    return artifact, {
        "uri": source["uri"], "generation": source["generation"],
        "metageneration": expected["metageneration"],
        "sha256": source["sha256"], "bytes": source["bytes"],
        "md5_hash": md5_hash, "crc32c": crc32c,
    }


def _validate_live_artifact_result_receipts(
    result_rows: object, live_rows: Sequence[Mapping[str, Any]],
) -> None:
    if not isinstance(result_rows, list) or result_rows != list(live_rows):
        raise RuntimeError("A7 replay live source-artifact receipts differ")


def _validate_scorefree_receipt(value: object, *, indices: list[int]) -> None:
    if not isinstance(value, dict) or value.get("ladder_spec") != LADDER_SPEC or \
            value.get("selection_order") != indices or value.get(
                "selection_order_sha256"
            ) != _sha_bytes(json.dumps(
                indices, separators=(",", ":"),
            ).encode("utf-8")):
        raise RuntimeError("A7 score-free order receipt differs")
    trace = value.get("trace")
    by_block = value.get("ladder_utility_by_block")
    total = value.get("total_ladder_utility")
    if not isinstance(trace, list) or len(trace) != ENTRY_COUNT or \
            not isinstance(by_block, list) or len(by_block) != 5 or \
            any(type(item) is not int or item < 0 for item in by_block) or \
            type(total) is not int or total <= 0 or sum(by_block) != total:
        raise RuntimeError("A7 score-free utility receipt differs")
    trace_blocks = [0] * 5
    trace_total = 0
    for position, row in enumerate(trace):
        if not isinstance(row, dict) or row.get("position") != position or \
                row.get("candidate_index") != indices[position] or \
                not isinstance(row.get("identity"), list) or \
                _identity(row["identity"]) != tuple(row["identity"]):
            raise RuntimeError("A7 score-free trace identity differs")
        blocks = row.get("marginal_gain_by_block")
        gain = row.get("marginal_gain")
        if not isinstance(blocks, list) or len(blocks) != 5 or any(
            type(item) is not int or item < 0 for item in blocks
        ) or type(gain) is not int or gain != sum(blocks):
            raise RuntimeError("A7 score-free trace gain differs")
        trace_total += gain
        trace_blocks = [left + right for left, right in zip(
            trace_blocks, blocks, strict=True,
        )]
    if trace_total != total or trace_blocks != by_block:
        raise RuntimeError("A7 score-free trace does not conserve utility")
    realism = value.get("realism")
    if not isinstance(realism, dict) or set(realism) != {"0.99", "0.995"}:
        raise RuntimeError("A7 score-free realism population differs")
    for q, block in realism.items():
        histogram = block.get("utility_by_extreme_player_count")
        by_world_block = block.get("utility_by_extreme_player_count_by_block")
        events = block.get("positive_gain_events_by_extreme_player_count_by_block")
        if not isinstance(histogram, list) or len(histogram) != 10 or any(
            type(item) is not int or item < 0 for item in histogram
        ) or sum(histogram) != total or not isinstance(by_world_block, list) or \
                not isinstance(events, list) or len(by_world_block) != 5 or \
                len(events) != 5:
            raise RuntimeError(f"A7 score-free realism {q} differs")
        for rows in (by_world_block, events):
            if any(not isinstance(row, list) or len(row) != 10 or any(
                type(item) is not int or item < 0 for item in row
            ) for row in rows):
                raise RuntimeError(f"A7 score-free realism {q} cells differ")
        if [sum(row) for row in by_world_block] != by_block or [
            sum(row[index] for row in by_world_block) for index in range(10)
        ] != histogram:
            raise RuntimeError(f"A7 score-free realism {q} does not conserve")
        for k in (2, 3, 4):
            expected = sum(histogram[k:]) / total
            if _finite(block.get(f"r{k}"), label=f"realism {q} r{k}") != expected:
                raise RuntimeError(f"A7 score-free realism {q} r{k} differs")


def _validate_result_header(
    report: dict[str, Any], manifest: Mapping[str, Any], frozen: FrozenRun, *,
    require_in_image_replay: bool = True,
) -> list[dict[str, Any]]:
    fixed = {
        "version": "a7-select-ladder-phase-s-incumbent-v2",
        "run_id": RUN_ID,
        "code_sha": frozen.code_sha,
        "image": frozen.image,
        "protocol_sha256": frozen.protocol_sha256,
        "source_report_sha256": manifest["source_report"]["sha256"],
        "baseline_sha256": manifest["baseline"]["sha256"],
        "baseline_vector_sha256": manifest["baseline_vector"]["sha256"],
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "local_source_receipts": manifest["local_source_receipts"],
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_preflight": {
            "panel_ids": list(SOURCE_PANEL_IDS),
            "slates": [
                [season, week] for season in (2023, 2024, 2025)
                for week in range(1, 19)
            ],
            "slate_count": 54,
            "artifact_count": 270,
        },
        "smoke": False,
        "support_census": False,
        "production_change_licensed": False,
        "prospective_shadow_licensed": False,
        "freeze_manifest_uri": frozen.freeze_manifest_uri,
        "freeze_manifest_generation": frozen.freeze_manifest_generation,
        "freeze_manifest_sha256": frozen.freeze_manifest_sha256,
    }
    if any(report.get(key) != expected for key, expected in fixed.items()) or \
            "output" in report:
        raise RuntimeError("A7 result identity differs")
    uses_realized = report.get("uses_realized_outcomes")
    queried_actuals = report.get("actual_score_query_executed")
    if type(uses_realized) is not bool or queried_actuals is not uses_realized:
        raise RuntimeError("A7 result outcome boundary differs")
    expected_keys = RESULT_COMMON_KEYS | (
        {"actual_query_content_receipt", "actual_query_rows", "outcome"}
        if uses_realized else {"disposition"}
    )
    if not require_in_image_replay:
        expected_keys = expected_keys - {"in_image_science_replay"}
    if set(report) != expected_keys:
        raise RuntimeError("A7 result field population differs")
    if not uses_realized:
        if report.get("disposition") != "tail-artifact-risk-phase-s" or \
                report.get(
                    "production_law_scorefree_transfer_licensed"
                ) is not False or "outcome" in report or \
                "actual_query_content_receipt" in report or \
                "actual_query_rows" in report:
            raise RuntimeError("A7 tail-artifact closure differs")
    elif "disposition" in report or type(report.get(
        "production_law_scorefree_transfer_licensed"
    )) is not bool or not isinstance(
        report.get("actual_query_content_receipt"), dict
    ) or not isinstance(report.get("actual_query_rows"), list):
        raise RuntimeError("A7 realized-result disposition boundary differs")
    if uses_realized:
        receipt = report["actual_query_content_receipt"]
        if set(receipt) != {"columns", "rows", "sha256"} or receipt.get(
            "columns"
        ) != list(ACTUAL_QUERY_COLUMNS) or type(receipt.get("rows")) is not int or \
                receipt["rows"] <= 0 or len(report["actual_query_rows"]) != \
                receipt["rows"] or re.fullmatch(r"[0-9a-f]{64}", str(
                    receipt.get("sha256", "")
                )) is None:
            raise RuntimeError("A7 realized actual-query receipt differs")
    selector = report.get("selector")
    if selector != {
        "control_env": CONTROL_ENV,
        "treatment_env": TREATMENT_ENV,
        "ladder_spec": LADDER_SPEC,
        "entry_count": ENTRY_COUNT,
    }:
        raise RuntimeError("A7 result selector law differs")
    if report.get("implementation_receipts") != {
        key: manifest["implementation_sha256"][key]
        for key in CORE_IMPLEMENTATION_KEYS
    } or report.get("query_content_receipts") != manifest[
        "query_content_receipts"
    ]:
        raise RuntimeError("A7 result implementation/query binding differs")
    evidence = report.get("freeze_evidence")
    if not isinstance(evidence, dict) or set(evidence) != {
        "manifest", "manifest_object", "smoke_receipt", "smoke_object",
        "support_receipt", "support_object", "source_artifact_lock_sha256",
        "smoke_terminal_receipt", "smoke_terminal_object",
        "support_terminal_receipt", "support_terminal_object",
        "implementation_sha256",
    }:
        raise RuntimeError("A7 result lacks freeze evidence")
    manifest_object = evidence.get("manifest_object")
    if evidence.get("manifest") != manifest or evidence.get(
        "source_artifact_lock_sha256"
    ) != manifest["source_artifact_lock_sha256"] or evidence.get(
        "implementation_sha256"
    ) != manifest["implementation_sha256"] or not isinstance(
        manifest_object, dict
    ) or manifest_object.get("uri") != frozen.freeze_manifest_uri or \
            manifest_object.get("generation") != frozen.freeze_manifest_generation or \
            manifest_object.get("sha256") != frozen.freeze_manifest_sha256 or \
            manifest_object.get("metageneration") != "1" or \
            int(manifest_object.get("bytes", 0)) <= 0 or evidence.get(
                "smoke_object"
            ) != manifest["preflights"]["smoke"]["science"] or evidence.get(
                "support_object"
            ) != manifest["preflights"]["support"]["science"] or evidence.get(
                "smoke_terminal_object"
            ) != manifest["preflights"]["smoke"]["terminal"] or evidence.get(
                "support_terminal_object"
            ) != manifest["preflights"]["support"]["terminal"]:
        raise RuntimeError("A7 result freeze evidence differs")
    rows = report.get("slates")
    expected_lattice = [(season, week) for season in (2023, 2024, 2025)
                        for week in range(1, 19)]
    if not isinstance(rows, list) or [
        (row.get("season"), row.get("week"))
        for row in rows if isinstance(row, dict)
    ] != expected_lattice or len(rows) != 54:
        raise RuntimeError("A7 result slate lattice differs")
    return rows


def _validate_in_image_science_replay(
    report: Mapping[str, Any], manifest: Mapping[str, Any], frozen: FrozenRun,
) -> dict[str, Any]:
    value = report.get("in_image_science_replay")
    if not isinstance(value, dict) or set(value) != {
        "version", "image", "finisher_sha256", "receipt", "receipt_sha256",
    } or value.get("version") != "a7-in-image-science-replay-v1" or \
            value.get("image") != frozen.image or value.get(
                "finisher_sha256"
            ) != manifest["implementation_sha256"]["finisher"] or not isinstance(
                value.get("receipt"), dict
            ) or value.get("receipt_sha256") != _sha_bytes(
                _canonical_json(value["receipt"])
            ):
        raise RuntimeError("A7 in-image science replay receipt differs")
    return value["receipt"]


def _candidate_actual_map(
    value: object, identities: Sequence[Sequence[str]], *, retained_pool_c: object,
    expected_native: Mapping[tuple[str, ...], float] | None = None,
) -> tuple[dict[tuple[str, ...], float], float]:
    if not isinstance(value, list) or len(value) != len(identities):
        raise RuntimeError("A7 candidate actual-score vector differs")
    result: dict[tuple[str, ...], float] = {}
    for identity, raw_score in zip(identities, value, strict=True):
        key = _identity(identity)
        if key in result:
            raise RuntimeError("A7 candidate actual-score identities repeat")
        result[key] = _finite(raw_score, label="candidate actual score")
    if expected_native is not None and any(
        expected_native.get(identity) != score
        for identity, score in result.items()
    ):
        raise RuntimeError("A7 aligned candidate scores differ from native outcomes")
    pool_c = max(result.values())
    if _finite(retained_pool_c, label="pool C") != pool_c:
        raise RuntimeError("A7 retained pool C differs from aligned candidate scores")
    return result, pool_c


def _validate_retained_actual_query(
    sources: Any, retained_rows: object, retained_receipt: object,
) -> tuple[dict[tuple[int, int], dict[tuple[str, ...], float]], dict[str, Any]]:
    if not isinstance(retained_rows, list) or any(
        not isinstance(row, dict) for row in retained_rows
    ):
        raise RuntimeError("A7 retained actual-query rows differ")
    source_records = sources.to_dict("records")
    source_keys = {
        (
            str(row["panel_run_id"]), int(row["season"]), int(row["week"]),
            int(row["cand_ix"]), str(row["players"]),
        )
        for row in source_records
    }
    retained_keys: set[tuple[str, int, int, int, str]] = set()
    grouped: dict[tuple[int, int], dict[tuple[str, ...], float]] = {}
    normalized: list[dict[str, Any]] = []
    for raw in retained_rows:
        if set(raw) != set(ACTUAL_QUERY_COLUMNS):
            raise RuntimeError("A7 retained actual-query row schema differs")
        row = {
            "panel_run_id": str(raw["panel_run_id"]),
            "season": int(raw["season"]),
            "week": int(raw["week"]),
            "cand_ix": int(raw["cand_ix"]),
            "players": str(raw["players"]),
            "actual_score": _finite(
                raw["actual_score"], label="retained actual-query score",
            ),
        }
        key = (
            row["panel_run_id"], row["season"], row["week"], row["cand_ix"],
            row["players"],
        )
        if key in retained_keys:
            raise RuntimeError("A7 retained actual-query keys repeat")
        retained_keys.add(key)
        identity = _identity([
            value for value in row["players"].split(",") if value
        ])
        slate = (row["season"], row["week"])
        values = grouped.setdefault(slate, {})
        prior = values.get(identity)
        if prior is not None and prior != row["actual_score"]:
            raise RuntimeError("A7 duplicate native outcomes disagree")
        values[identity] = row["actual_score"]
        normalized.append(row)
    if retained_keys != source_keys or len(retained_rows) != len(source_records):
        raise RuntimeError("A7 retained actual-query source keys differ")
    retained_order = [(
        row["panel_run_id"], row["season"], row["week"], row["cand_ix"],
        row["players"],
    ) for row in normalized]
    if retained_order != sorted(retained_order) or len(retained_order) != len(
        set(retained_order)
    ):
        raise RuntimeError("A7 retained actual-query canonical order differs")
    receipt = _records_content_receipt(normalized, ACTUAL_QUERY_COLUMNS)
    if retained_receipt != receipt:
        raise RuntimeError("A7 retained actual-query content receipt differs")
    return grouped, receipt


def _validate_arm_receipt(
    *, row: Mapping[str, Any], arm: str, identities: list[list[str]],
    tags: list[list[str]], selected: list[int],
    actual_values: Mapping[tuple[str, ...], float] | None,
) -> dict[str, Any]:
    value = row.get(arm)
    expected_keys = RESULT_ARM_COMMON_KEYS | (
        {"realized"} if actual_values is not None else set()
    )
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise RuntimeError(f"A7 {arm} arm receipt differs")
    expected_env = CONTROL_ENV if arm == "control" else TREATMENT_ENV
    if value.get("selector_env") != expected_env or value.get("indices") != selected:
        raise RuntimeError(f"A7 {arm} selection receipt differs")
    selected_ids = selected_identities(identities, selected)
    if value.get("identities") != selected_ids:
        raise RuntimeError(f"A7 {arm} selected identities differ")
    selected_tags = [tags[index] for index in selected]
    if value.get("selected_source_tags") != selected_tags or value.get(
        "candidate_source_counts"
    ) != candidate_source_counts(selected, tags):
        raise RuntimeError(f"A7 {arm} source attribution differs")
    _validate_scorefree_receipt(value.get("scorefree"), indices=selected)
    if actual_values is None:
        if "realized" in value:
            raise RuntimeError(f"A7 {arm} tail-artifact arm leaks outcomes")
        return value
    realized = value.get("realized")
    if not isinstance(realized, dict) or realized.get("identities") != selected_ids:
        raise RuntimeError(f"A7 {arm} retained score identities differ")
    scores = realized.get("scores")
    if not isinstance(scores, list) or len(scores) != ENTRY_COUNT:
        raise RuntimeError(f"A7 {arm} retained score population differs")
    for identity, raw_score in zip(selected_ids, scores, strict=True):
        score = _finite(raw_score, label=f"{arm} retained score")
        key = tuple(identity)
        if key not in actual_values or actual_values[key] != score:
            raise RuntimeError("A7 selected score differs from aligned candidate score")
    replayed = score_ordered_book(selected_ids, actual_values)
    if realized != replayed:
        raise RuntimeError(f"A7 {arm} realized-prefix receipt differs")
    return value


def _validate_result_slate_fields(
    row: Mapping[str, Any], *, uses_realized_outcomes: bool,
) -> None:
    expected = RESULT_SLATE_COMMON_KEYS | (
        {"candidate_actual_scores", "pool_c"}
        if uses_realized_outcomes else set()
    )
    if set(row) != expected:
        raise RuntimeError("A7 result slate field population differs")


def _replay_science(
    report: dict[str, Any], manifest: dict[str, Any],
    query_loader: QueryLoader, object_loader: ObjectLoader,
) -> dict[str, Any]:
    rows = _validate_result_header(
        report, manifest,
        FrozenRun(
            run_id=RUN_ID,
            code_sha=str(manifest["code"]["commit_sha"]),
            image=str(manifest["image"]["uri"]),
            build_id=str(report.get("build_id", "")),
            protocol_sha256=str(manifest["protocol"]["sha256"]),
            freeze_manifest_uri=str(report["freeze_manifest_uri"]),
            freeze_manifest_generation=str(report["freeze_manifest_generation"]),
            freeze_manifest_sha256=str(report["freeze_manifest_sha256"]),
            freeze_validation_sha256="0" * 64,
            a3_logical_release_sha256="0" * 64,
            job=JOB, job_uid="replay", job_generation="1",
        ), require_in_image_replay=False,
    )
    frozen_artifacts = _validate_source_artifacts(manifest["source_artifacts"])
    uses_realized = report["uses_realized_outcomes"] is True
    _validate_artifact_result_receipts(
        report.get("source_artifacts"), frozen_artifacts,
    )
    sources, players = query_loader()
    query_receipts = {
        "candidate_source": _query_content_receipt(
            sources, SOURCE_QUERY_COLUMNS,
        ),
        "player_source": _query_content_receipt(players, PLAYER_QUERY_COLUMNS),
    }
    if query_receipts != manifest["query_content_receipts"] or \
            query_receipts != report["query_content_receipts"]:
        raise RuntimeError("A7 replay score-free query content differs")
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("A7 replay player manifest differs")
    preflight = resolve_panel_artifacts(
        sources.to_dict("records"), panel_ids=SOURCE_PANEL_IDS,
        expected_slates=54,
    )
    if preflight.get("artifact_count") != 270 or preflight.get(
        "slate_count"
    ) != 54:
        raise RuntimeError("A7 replay source preflight differs")
    if uses_realized:
        native_actual_by_slate, actual_query_receipt = \
            _validate_retained_actual_query(
                sources, report.get("actual_query_rows"),
                report.get("actual_query_content_receipt"),
            )
    else:
        native_actual_by_slate, actual_query_receipt = {}, None
    source_map = _artifact_map(manifest)
    artifact_receipts: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    candidate_actual_by_slate: dict[
        tuple[int, int], dict[tuple[str, ...], float]
    ] = {}
    for result_row in rows:
        _validate_result_slate_fields(
            result_row, uses_realized_outcomes=uses_realized,
        )
        season, week = int(result_row["season"]), int(result_row["week"])
        catalog = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        books: dict[str, Any] = {}
        for seed, panel in enumerate(SOURCE_PANEL_IDS):
            group = sources[
                sources.panel_run_id.astype(str).eq(panel)
                & sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            source = source_map[(panel, season, week)]
            artifact, receipt = _decode_frozen_artifact(source, object_loader)
            books[f"R{seed}"] = _candidate_batch(group, artifact, catalog)
            artifact_receipts.append({
                "panel_run_id": panel, "season": season, "week": week,
                "candidate_rows": int(source["candidate_rows"]), "seed": seed,
                **receipt,
            })
        if tuple(books) != ("R0", "R1", "R2", "R3", "R4"):
            raise RuntimeError("A7 replay source-block order differs")
        combined = combine_cbwu_books(
            books, tuple(books), expected_worlds_per_book=10_000,
        )
        identities = _candidate_identities(combined)
        tags = _candidate_tags(combined)
        if result_row.get("candidate_identities") != identities or \
                result_row.get("candidate_identities_sha256") != _sha_bytes(
                    json.dumps(
                        identities, sort_keys=True, separators=(",", ":"),
                    ).encode("utf-8")
                ) or result_row.get("candidate_tags_sha256") != _sha_bytes(
                    json.dumps(
                        tags, sort_keys=True, separators=(",", ":"),
                    ).encode("utf-8")
                ):
            raise RuntimeError("A7 replay candidate identity/tag bytes differ")
        totals = np.asarray(combined.candidate_totals)
        draws = np.asarray(combined.row_draws)
        expected_inputs = {
            "candidate_totals": _array_receipt(totals),
            "player_draws": _array_receipt(draws),
            "player_ids_sha256": _sha_bytes(json.dumps(
                [str(value) for value in combined.player_ids],
                separators=(",", ":"),
            ).encode("utf-8")),
        }
        if result_row.get("combined_input_receipts") != expected_inputs or \
                result_row.get("candidate_budget") != len(identities) or \
                result_row.get("world_count") != 50_000 or \
                result_row.get("candidate_pool_shared_across_arms") is not True or \
                result_row.get("control_source_reproduced") is not True:
            raise RuntimeError("A7 replay combined input receipt differs")
        selected_books = select_books(totals)
        if uses_realized:
            native_values = native_actual_by_slate.get((season, week))
            if native_values is None:
                raise RuntimeError("A7 native outcomes lack result slate")
            actual_values, _pool_c = _candidate_actual_map(
                result_row.get("candidate_actual_scores"), identities,
                retained_pool_c=result_row.get("pool_c"),
                expected_native=native_values,
            )
            candidate_actual_by_slate[(season, week)] = actual_values
        else:
            if "candidate_actual_scores" in result_row:
                raise RuntimeError("A7 tail-artifact slate leaks outcomes")
            actual_values = None
        arms: dict[str, dict[str, Any]] = {}
        for arm in ("control", "treatment"):
            selected = selected_books[arm]
            if any(not _is_production_legal(combined.candidates[index])
                   for index in selected):
                raise RuntimeError(f"A7 replay {arm} selected illegal roster")
            arm_value = _validate_arm_receipt(
                row=result_row, arm=arm, identities=identities, tags=tags,
                selected=selected, actual_values=actual_values,
            )
            expected_scorefree = scorefree_book_receipt(
                candidate_totals=totals,
                candidate_identities=identities,
                selected=selected,
                player_ids=combined.player_ids,
                player_draws=draws,
            )
            if arm_value["scorefree"] != expected_scorefree:
                raise RuntimeError(f"A7 replay {arm} score-free receipt differs")
            arms[arm] = arm_value
        overlap = len(
            {tuple(value) for value in arms["control"]["identities"]}
            & {tuple(value) for value in arms["treatment"]["identities"]}
        )
        if arms["control"].get("identity_overlap_with_control") != ENTRY_COUNT or \
                arms["treatment"].get("identity_overlap_with_control") != overlap:
            raise RuntimeError("A7 replay arm-overlap receipt differs")
        if uses_realized:
            assert actual_values is not None
            if result_row.get("uses_realized_outcomes") is not True:
                raise RuntimeError("A7 realized slate outcome boundary differs")
        elif "pool_c" in result_row or result_row.get(
            "uses_realized_outcomes"
        ) is not False:
            raise RuntimeError("A7 tail-artifact slate leaks outcomes")
        replay_rows.append(dict(result_row))

    _validate_live_artifact_result_receipts(
        report["source_artifacts"], artifact_receipts,
    )
    scorefree = aggregate_scorefree(replay_rows)
    if report.get("scorefree") != scorefree:
        raise RuntimeError("A7 replay aggregate score-free receipt differs")
    if not uses_realized:
        conditions = scorefree.get("conditions")
        if not isinstance(conditions, dict) or scorefree.get(
            "mechanics_passes"
        ) is not True or conditions.get("realism_r3_supported") is not True or \
                conditions.get("realism_r3_noninferior") is not False or \
                scorefree.get("passes") is not False or report.get(
                    "disposition"
                ) != "tail-artifact-risk-phase-s":
            raise RuntimeError("A7 replay tail-artifact disposition differs")
        return {
            "version": "a7-strict-science-replay-v1",
            "run_id": RUN_ID,
            "slates": 54,
            "scorefree_query_content_receipts": query_receipts,
            "source_artifact_lock_sha256": manifest[
                "source_artifact_lock_sha256"
            ],
            "source_artifacts_generation_pinned": len(artifact_receipts),
            "combined_inputs_reconstructed": 54,
            "selection_books_replayed": 108,
            "scorefree_books_replayed": 108,
            "retained_realized_books_replayed": 0,
            "baseline_reproduced": False,
            "outcome_replayed": False,
            "uses_realized_outcomes": False,
            "actual_score_query_executed": False,
            "disposition": "tail-artifact-risk-phase-s",
            "production_change_licensed": False,
        }
    if scorefree.get("passes") is not True:
        raise RuntimeError("A7 realized replay lacks passed score-free gate")
    assert actual_query_receipt is not None
    baseline_vector = _registered_baseline_vector(manifest)
    baseline = validate_control_baseline(
        replay_rows, baseline_mean=176.06296296296293,
        baseline_counts=BASELINE_COUNTS, baseline_vector=baseline_vector,
    )
    outcome = aggregate_outcomes(
        replay_rows, scorefree=scorefree,
        baseline_mean=176.06296296296293, baseline_counts=BASELINE_COUNTS,
        baseline_vector=baseline_vector,
    )
    if report.get("outcome") != outcome or outcome.get("baseline") != baseline or \
            outcome.get("disposition") not in ALLOWED_DISPOSITIONS or \
            report.get("production_law_scorefree_transfer_licensed") is not (
                outcome["disposition"] == "historical-positive-phase-s"
            ):
        raise RuntimeError("A7 replay outcome/disposition differs")
    return {
        "version": "a7-strict-science-replay-v1",
        "run_id": RUN_ID,
        "slates": 54,
        "scorefree_query_content_receipts": query_receipts,
        "source_artifact_lock_sha256": manifest[
            "source_artifact_lock_sha256"
        ],
        "source_artifacts_generation_pinned": len(artifact_receipts),
        "combined_inputs_reconstructed": 54,
        "selection_books_replayed": 108,
        "scorefree_books_replayed": 108,
        "retained_realized_books_replayed": 108,
        "candidate_actual_scores_replayed": sum(
            len(values) for values in candidate_actual_by_slate.values()
        ),
        "actual_query_content_receipt": actual_query_receipt,
        "baseline_reproduced": True,
        "outcome_replayed": True,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "pool_c_recomputed_from_aligned_candidate_scores": True,
        "disposition": outcome["disposition"],
        "production_change_licensed": False,
    }


def _validate_launch_sources(
    out: Path, *, root: Path, git_source_loader: GitSourceLoader,
) -> tuple[FrozenRun, str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    required = {
        "manifest.json", "build-metadata.json", "freeze-validation.json",
        "a3-logical-release.json", "job-before.json", "job-after.json",
        "job-claim-receipt.json", "support-terminal-receipt.json",
        "prepared.sha256", "executions.txt", "lease-receipt.json",
        "launch-intent.json", "launch.sha256",
    }
    if not out.is_dir() or any(not (out / name).is_file() for name in required):
        raise RuntimeError("A7 launch receipt is incomplete")
    _validate_hash_ledger(
        out / "prepared.sha256", base=out,
        expected={
            "manifest.json", "build-metadata.json", "freeze-validation.json",
            "a3-logical-release.json", "job-before.json", "job-after.json",
            "job-claim-receipt.json", "support-terminal-receipt.json",
        },
    )
    _validate_hash_ledger(
        out / "launch.sha256", base=out,
        expected={
            "manifest.json", "prepared.sha256", "launch-intent.json", "executions.txt",
            "lease-receipt.json",
        },
    )
    frozen, execution, manifest = _load_frozen_run(out)
    intent = _load_json(out / "launch-intent.json", label="launch intent")
    if set(intent) != {
        "version", "run_id", "job", "output_uri", "created_at",
        "execution_started",
    } or intent.get("version") != "a7-select-ladder-launch-intent-v1" or \
            intent.get("run_id") != RUN_ID or intent.get("job") != frozen.job or \
            intent.get("output_uri") != frozen.output_uri or intent.get(
                "execution_started"
            ) != "unknown-until-ledger-created" or not str(
                intent.get("created_at", "")
            ):
        raise RuntimeError("A7 launch intent differs")
    if _sha(out / "freeze-validation.json") != frozen.freeze_validation_sha256 or \
            _sha(out / "a3-logical-release.json") != \
            frozen.a3_logical_release_sha256:
        raise RuntimeError("A7 immutable prelaunch receipt differs")
    release = _validate_a3_release(out / "a3-logical-release.json")
    freeze_validation = _load_json(
        out / "freeze-validation.json", label="freeze validation",
    )
    if set(freeze_validation) != {
        "version", "run_id", "freeze_manifest",
        "freeze_manifest_content_sha256", "a3_logical_release_sha256",
        "a3_logical_release", "preflights", "preflight_content_sha256",
        "source_artifact_lock_sha256", "protocol_sha256",
        "prefix_inventory_sha256",
        "implementation_sha256", "transport_repair_sha256", "code_sha",
        "job_claim",
        "image", "uses_realized_outcomes", "actual_score_query_executed",
        "production_change_licensed",
        "production_law_scorefree_transfer_licensed",
        "prospective_shadow_licensed",
    }:
        raise RuntimeError("A7 freeze-validation fields differ")
    expected_freeze_validation = {
        "version": "a7-launch-freeze-validation-v1",
        "run_id": RUN_ID,
        "code_sha": frozen.code_sha,
        "image": frozen.image,
        "a3_logical_release_sha256": frozen.a3_logical_release_sha256,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    if any(freeze_validation.get(key) != expected
           for key, expected in expected_freeze_validation.items()) or \
            freeze_validation.get("freeze_manifest", {}).get("uri") != \
            frozen.freeze_manifest_uri or freeze_validation.get(
                "freeze_manifest", {}
            ).get("generation") != frozen.freeze_manifest_generation or \
            freeze_validation.get("freeze_manifest_content_sha256") != \
            frozen.freeze_manifest_sha256 or freeze_validation.get(
                "protocol_sha256"
            ) != frozen.protocol_sha256:
        raise RuntimeError("A7 freeze-validation receipt differs")
    inventory_hashes = freeze_validation.get("prefix_inventory_sha256")
    if not isinstance(inventory_hashes, dict) or set(inventory_hashes) != {
        "claimed", "smoke-complete", "support-complete",
    }:
        raise RuntimeError("A7 freeze-validation inventory hashes differ")
    for key, digest in inventory_hashes.items():
        _hex(digest, length=64, label=f"freeze {key} inventory SHA")
    build = _load_json(out / "build-metadata.json", label="build metadata")
    _validate_build_metadata(
        build, build_id=frozen.build_id, image=frozen.image,
        code_sha=frozen.code_sha,
    )
    lease = _load_json(out / "lease-receipt.json", label="lease receipt")
    _validate_lease_receipt(lease, frozen=frozen)
    local_claim = _load_json(
        out / "job-claim-receipt.json", label="job claim receipt",
    )
    if _sha(out / "job-claim-receipt.json") != \
            frozen.job_claim_receipt_sha256 or local_claim != \
            manifest.get("job_claim") or local_claim != \
            freeze_validation.get("job_claim"):
        raise RuntimeError("A7 historical run job-claim binding differs")
    _validate_job_claim_receipt(
        local_claim, code_sha=frozen.code_sha, image=frozen.image,
        protocol_sha256=frozen.protocol_sha256,
        a3_logical_release_sha256=frozen.a3_logical_release_sha256,
        job_uid=frozen.job_uid,
    )
    support_terminal_path = out / "support-terminal-receipt.json"
    support_terminal = _load_json(
        support_terminal_path, label="support terminal receipt",
    )
    if _sha(support_terminal_path) != freeze_validation["preflights"][
        "support"
    ]["terminal"]["sha256"]:
        raise RuntimeError("A7 historical support-terminal binding differs")
    _validate_preflight_terminal_receipt(
        support_terminal, mode="support-census",
        science_object=support_terminal.get("science_object", {}),
        claim=local_claim, code_sha=frozen.code_sha, image=frozen.image,
        protocol_sha256=frozen.protocol_sha256,
        a3_logical_release_sha256=frozen.a3_logical_release_sha256,
        build_id=frozen.build_id,
        prior_science_object=freeze_validation["preflights"]["smoke"][
            "science"
        ],
        prior_terminal_object=freeze_validation["preflights"]["smoke"][
            "terminal"
        ],
    )
    if support_terminal.get("support_passed") is not True:
        raise RuntimeError("A7 historical preparation requires supported census")
    before = _load_json(out / "job-before.json", label="pre-update job metadata")
    after = _load_json(out / "job-after.json", label="post-update job metadata")
    _validate_reused_job_receipts(
        before, after, frozen,
        expected_before_generation=str(
            support_terminal["execution"]["job_generation"]
        ),
        expected_before_spec_sha256=str(
            support_terminal["execution"]["job_spec_sha256"]
        ),
    )
    if _validate_updated_job_spec(
        after, code_sha=frozen.code_sha, image=frozen.image, mode="historical",
        freeze_manifest_uri=frozen.freeze_manifest_uri,
        freeze_manifest_generation=frozen.freeze_manifest_generation,
        freeze_manifest_sha256=frozen.freeze_manifest_sha256,
    ) != frozen.job_spec_sha256:
        raise RuntimeError("A7 historical post-update job spec differs")
    if release != freeze_validation.get("a3_logical_release"):
        raise RuntimeError("A7 A3 release receipt was not frozen exactly")

    # Revalidate every scientific source against both worktree and commit.
    freeze_manifest_copy = out / "freeze-manifest.json"
    if freeze_manifest_copy.exists():
        raise RuntimeError("A7 result finisher cannot trust an unreceipted freeze copy")
    implementation = freeze_validation.get("implementation_sha256")
    if not isinstance(implementation, dict):
        raise RuntimeError("A7 freeze implementation receipt differs")
    repairs = _validate_implementation_sources(
        implementation, code_sha=frozen.code_sha, root=root,
        git_source_loader=git_source_loader,
    )
    if freeze_validation.get("transport_repair_sha256") != repairs or \
            manifest.get("transport_repair_sha256") != repairs:
        raise RuntimeError("A7 transport-repair receipt differs")
    return frozen, execution, manifest, freeze_validation, lease


def _validate_live_lease(
    lease: dict[str, Any], *, frozen: FrozenRun, object_loader: ObjectLoader,
) -> tuple[dict[str, Any], bytes]:
    expected = _validate_lease_receipt(lease, frozen=frozen)
    metadata, raw = object_loader(LEASE_URI, expected["generation"])
    _validate_loaded_object(metadata, raw, expected, label="historical-outcome lease")
    if _json_object(raw, label="live historical-outcome lease") != lease["lease"]:
        raise RuntimeError("A7 live historical-outcome lease body differs")
    return metadata, raw


def _hash_ledger(paths: Sequence[Path], *, base: Path) -> bytes:
    return "".join(
        f"{_sha(path)}  {path.relative_to(base)}\n" for path in sorted(paths)
    ).encode("utf-8")


def _validate_preflight_complete(out: Path, *, mode: str) -> dict[str, Any]:
    _validate_hash_ledger(
        out / "prepared.sha256", base=out,
        expected={
            "manifest.json", "build-metadata.json", "a3-logical-release.json",
            "job-claim-receipt.json", "job-before.json", "job-after.json",
        },
    )
    _validate_hash_ledger(
        out / "launch.sha256", base=out,
        expected={"manifest.json", "prepared.sha256", "executions.txt"},
    )
    expected = {
        "manifest.json", "prepared.sha256", "launch.sha256",
        "executions.txt", "preflight-receipt.json", "execution.json",
        "object-metadata.json", "job-claim-metadata.json",
        "terminal-receipt.json", "terminal-object-metadata.json",
        "completion.txt",
    }
    _validate_hash_ledger(out / "finish.sha256", base=out, expected=expected)
    completion = dict(
        line.split("=", 1) for line in (out / "completion.txt").read_text(
            encoding="utf-8",
        ).splitlines() if "=" in line
    )
    expected_disposition = (
        "smoke-passed" if mode == "real-artifact-smoke" else
        completion.get("disposition")
    )
    if completion.get("run_id") != RUN_ID or completion.get("mode") != mode or \
            expected_disposition not in {
                "smoke-passed", "support-passed", "invalid-unsupported",
            } or (mode == "support-census" and completion.get(
                "support_passed"
            ) != str(expected_disposition == "support-passed").lower()) or \
            completion.get("strict_terminal_harvest") != "true" or \
            completion.get("uses_realized_outcomes") != "false" or \
            completion.get("actual_score_query_executed") != "false" or \
            completion.get("production_change_licensed") != "false" or \
            completion.get(
                "production_law_scorefree_transfer_licensed"
            ) != "false" or completion.get(
                "prospective_shadow_licensed"
            ) != "false" or completion.get(
                "terminal_receipt_sha256"
            ) != _sha(out / "terminal-receipt.json") or completion.get(
                "preflight_receipt_sha256"
            ) != _sha(out / "preflight-receipt.json") or completion.get(
                "terminal_object_sha256"
            ) != _load_json(
                out / "terminal-object-metadata.json",
                label="preflight terminal object metadata",
            ).get("sha256"):
        raise RuntimeError("A7 preflight completion receipt differs")
    return {
        "status": "already-complete", "run_id": RUN_ID, "mode": mode,
        "terminal_receipt_sha256": completion["terminal_receipt_sha256"],
    }


def finish_preflight(
    *, mode: str, out: Path, root: Path = ROOT,
    execution_loader: ExecutionLoader | None = None,
    inventory_loader: InventoryLoader | None = None,
    object_loader: ObjectLoader | None = None,
    object_creator: ObjectCreator | None = None,
    manifest_builder: PreflightManifestBuilder = _local_preflight_manifest,
    git_source_loader: GitSourceLoader = _git_blob,
) -> dict[str, Any]:
    if mode not in {"real-artifact-smoke", "support-census"}:
        raise RuntimeError("A7 preflight mode differs")
    if (out / "finish.sha256").is_file():
        return _validate_preflight_complete(out, mode=mode)
    final_names = {
        "preflight-receipt.json", "execution.json", "object-metadata.json",
        "job-claim-metadata.json", "terminal-receipt.json",
        "terminal-object-metadata.json", "completion.txt",
    }
    if any((out / name).exists() for name in final_names) or \
            (out / PENDING_NAME).exists():
        raise RuntimeError("A7 partial or immutable preflight harvest exists")
    _validate_hash_ledger(
        out / "prepared.sha256", base=out,
        expected={
            "manifest.json", "build-metadata.json", "a3-logical-release.json",
            "job-claim-receipt.json", "job-before.json", "job-after.json",
        },
    )
    _validate_hash_ledger(
        out / "launch.sha256", base=out,
        expected={"manifest.json", "prepared.sha256", "executions.txt"},
    )
    run, execution, claim, _release = _load_preflight_run(out, mode=mode)
    if execution_loader is None:
        execution_loader = _execution_metadata
    reader: _StorageReader | None = None
    if inventory_loader is None or object_loader is None or object_creator is None:
        reader = _StorageReader()
    if inventory_loader is None:
        assert reader is not None
        inventory_loader = reader.inventory
    if object_loader is None:
        assert reader is not None
        object_loader = reader.load
    if object_creator is None:
        assert reader is not None
        object_creator = reader.create

    # Body-blind boundary: terminal metadata and the exact prefix inventory are
    # proved before either score-free preflight body is downloaded.
    execution_value = execution_loader(execution)
    execution_receipt = _validate_preflight_execution(
        execution_value, execution=execution, run=run,
    )
    inventory = _validate_preflight_inventory(
        inventory_loader(PREFIX + "/preflight/"), mode=mode, claim=claim,
    )
    loaded: dict[str, tuple[dict[str, Any], bytes]] = {}
    for uri in _preflight_expected_uris(mode):
        expected = inventory[uri]
        metadata, raw = object_loader(uri, expected["generation"])
        live = {
            **expected,
            "sha256": _sha_bytes(raw),
        }
        _validate_loaded_object(metadata, raw, live, label="preflight object")
        loaded[uri] = (live, raw)
    claim_metadata, claim_raw = loaded[JOB_CLAIM_URI]
    if _json_object(claim_raw, label="job claim") != claim["claim"] or \
            claim_metadata != {
                key: claim["object"][key]
                for key in ("uri", "generation", "metageneration", "bytes", "sha256")
            }:
        raise RuntimeError("A7 live durable job claim differs")

    target_metadata, target_raw = loaded[run.target_uri]
    target_receipt = _json_object(target_raw, label=f"{mode} preflight receipt")
    local_manifest = manifest_builder(
        target_receipt, run.code_sha, run.image, root, git_source_loader,
    )
    _validate_preflight_receipt(
        target_raw, mode=mode, manifest=local_manifest,
        require_support_pass=False,
    )
    if mode == "support-census":
        _validate_preflight_receipt(
            loaded[SMOKE_URI][1], mode="real-artifact-smoke",
            manifest=local_manifest, require_support_pass=False,
        )
        _validate_preflight_terminal_receipt(
            _json_object(
                loaded[SMOKE_TERMINAL_URI][1], label="smoke terminal",
            ),
            mode="real-artifact-smoke",
            science_object=loaded[SMOKE_URI][0], claim=claim,
            code_sha=run.code_sha, image=run.image,
            protocol_sha256=run.protocol_sha256,
            a3_logical_release_sha256=run.a3_logical_release_sha256,
            build_id=run.build_id,
        )

    inventory_receipt = []
    for uri in _preflight_expected_uris(mode):
        metadata, raw = loaded[uri]
        inventory_receipt.append({**metadata, "sha256": _sha_bytes(raw)})
    terminal = {
        "version": "a7-select-ladder-preflight-terminal-v1",
        "run_id": RUN_ID,
        "protocol_id": PROTOCOL_ID,
        "mode": mode,
        "code_sha": run.code_sha,
        "image": run.image,
        "build_id": run.build_id,
        "protocol_sha256": run.protocol_sha256,
        "a3_logical_release_sha256": run.a3_logical_release_sha256,
        "job_claim_receipt_sha256": run.job_claim_receipt_sha256,
        "job_claim": claim,
        "execution": execution_receipt,
        "science_object": target_metadata,
        "prefix_inventory_before_terminal": inventory_receipt,
        "prefix_inventory_before_terminal_sha256": _inventory_sha256(
            inventory_receipt
        ),
        "expected_inventory_after_terminal_uris": list(
            _preflight_expected_uris(mode, include_current_terminal=True)
        ),
        "expected_inventory_after_terminal_uris_sha256": _uri_inventory_sha256(
            _preflight_expected_uris(mode, include_current_terminal=True)
        ),
        "preflight_receipt_sha256": _sha_bytes(target_raw),
        "support_passed": (
            None if mode == "real-artifact-smoke"
            else target_receipt["support"]["passes"]
        ),
        "disposition": (
            "smoke-passed" if mode == "real-artifact-smoke" else
            "support-passed" if target_receipt["support"]["passes"] else
            "invalid-unsupported"
        ),
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    terminal_uri = (
        SMOKE_TERMINAL_URI
        if mode == "real-artifact-smoke" else SUPPORT_TERMINAL_URI
    )
    _validate_preflight_terminal_receipt(
        terminal, mode=mode, science_object=target_metadata, claim=claim,
        code_sha=run.code_sha, image=run.image,
        protocol_sha256=run.protocol_sha256,
        a3_logical_release_sha256=run.a3_logical_release_sha256,
        build_id=run.build_id,
        prior_science_object=(
            loaded[SMOKE_URI][0] if mode == "support-census" else None
        ),
        prior_terminal_object=(
            loaded[SMOKE_TERMINAL_URI][0]
            if mode == "support-census" else None
        ),
    )
    terminal_raw = _canonical_json(terminal)
    terminal_metadata, terminal_download = object_creator(
        terminal_uri, terminal_raw,
    )
    if terminal_download != terminal_raw:
        raise RuntimeError("A7 preflight terminal object changed after create")
    terminal_expected = _metadata_block(
        {**terminal_metadata, "sha256": _sha_bytes(terminal_download)},
        uri=terminal_uri, label="preflight terminal",
    )
    final_inventory = _validate_preflight_inventory(
        inventory_loader(PREFIX + "/preflight/"), mode=mode, claim=claim,
        include_current_terminal=True,
    )
    _validate_final_preflight_inventory(
        final_inventory,
        (*inventory_receipt, terminal_expected),
        {
            **loaded,
            terminal_uri: (terminal_metadata, terminal_download),
        },
    )
    pending = out / PENDING_NAME
    pending.mkdir()
    (pending / "preflight-receipt.json").write_bytes(target_raw)
    (pending / "execution.json").write_bytes(_canonical_json(execution_value))
    (pending / "object-metadata.json").write_bytes(
        _canonical_json(target_metadata)
    )
    (pending / "job-claim-metadata.json").write_bytes(
        _canonical_json(claim_metadata)
    )
    (pending / "terminal-receipt.json").write_bytes(_canonical_json(terminal))
    (pending / "terminal-object-metadata.json").write_bytes(
        _canonical_json(terminal_expected)
    )
    completion = (
        "\n".join((
            f"validated_at={datetime.now(timezone.utc).isoformat()}",
            f"run_id={RUN_ID}", f"mode={mode}",
            "strict_terminal_harvest=true",
            f"preflight_receipt_sha256={_sha_bytes(target_raw)}",
            f"terminal_receipt_sha256={_sha_bytes(_canonical_json(terminal))}",
            f"terminal_object_sha256={terminal_expected['sha256']}",
            f"terminal_object_generation={terminal_expected['generation']}",
            f"disposition={terminal['disposition']}",
            f"support_passed={str(terminal['support_passed']).lower()}",
            "uses_realized_outcomes=false",
            "actual_score_query_executed=false",
            "production_change_licensed=false",
            "production_law_scorefree_transfer_licensed=false",
            "prospective_shadow_licensed=false",
        )) + "\n"
    ).encode("utf-8")
    (pending / "completion.txt").write_bytes(completion)
    for name in sorted(final_names):
        source, target = pending / name, out / name
        if not source.is_file() or target.exists():
            raise RuntimeError("A7 preflight publication target differs")
        source.rename(target)
    pending.rmdir()
    finish_sources = [
        out / name for name in sorted({
            "manifest.json", "prepared.sha256", "launch.sha256",
            "executions.txt", *final_names,
        })
    ]
    _write_new(out / "finish.sha256", _hash_ledger(finish_sources, base=out))
    result = _validate_preflight_complete(out, mode=mode)
    result["status"] = "completed"
    print(
        "A7_PREFLIGHT_STRICTLY_HARVESTED", f"mode={mode}",
        f"execution={execution}",
        f"sha256={_sha_bytes(target_raw)}",
    )
    return result


def _validate_complete(out: Path) -> dict[str, Any]:
    _validate_hash_ledger(
        out / "prepared.sha256", base=out,
        expected={
            "manifest.json", "build-metadata.json", "freeze-validation.json",
            "a3-logical-release.json", "job-before.json", "job-after.json",
            "job-claim-receipt.json", "support-terminal-receipt.json",
        },
    )
    _validate_hash_ledger(
        out / "launch.sha256", base=out,
        expected={
            "manifest.json", "prepared.sha256", "launch-intent.json",
            "executions.txt", "lease-receipt.json",
        },
    )
    expected = {
        "manifest.json", "prepared.sha256", "launch.sha256",
        "launch-intent.json", "executions.txt", "lease-receipt.json", "freeze-manifest.json",
        "smoke-preflight.json", "support-preflight.json",
        "smoke-terminal.json", "support-terminal.json", "execution.json",
        "object-metadata.json", "live-lease-metadata.json",
        "job-claim-metadata.json",
        "science-replay.json", "report.json", "completion.txt",
    }
    _validate_hash_ledger(out / "finish.sha256", base=out, expected=expected)
    completion = dict(
        line.split("=", 1)
        for line in (out / "completion.txt").read_text(
            encoding="utf-8",
        ).splitlines() if "=" in line
    )
    disposition = completion.get("disposition")
    expected_realized = "false" if disposition == (
        "tail-artifact-risk-phase-s"
    ) else "true"
    if completion.get("run_id") != RUN_ID or disposition not in \
            ALLOWED_DISPOSITIONS or completion.get(
                "strict_science_replay"
            ) != "true" or completion.get(
                "uses_realized_outcomes"
            ) != expected_realized or completion.get(
                "actual_score_query_executed"
            ) != expected_realized or \
            completion.get("production_change_licensed") != "false" or \
            completion.get("prospective_shadow_licensed") != "false" or \
            completion.get("historical_outcome_lease_release_licensed") != "true" or \
            completion.get("historical_outcome_lease_released") != "false" or \
            completion.get("report_sha256") != _sha(out / "report.json") or \
            completion.get("science_replay_sha256") != _sha(
                out / "science-replay.json"
            ):
        raise RuntimeError("A7 strict completion receipt differs")
    return {
        "status": "already-complete", "run_id": RUN_ID,
        "disposition": disposition,
        "report_sha256": completion["report_sha256"],
    }


def _write_or_validate(path: Path, raw: bytes, *, label: str) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise RuntimeError(f"A7 {label} differs")
        return
    _write_new(path, raw)


def _realized_release_intent(out: Path) -> tuple[dict[str, Any], bytes]:
    complete = _validate_complete(out)
    if complete["disposition"] == "tail-artifact-risk-phase-s":
        raise RuntimeError("A7 outcome-blind completion forbids realized release")
    frozen, execution_name, _manifest = _load_frozen_run(out)
    execution_path = out / "execution.json"
    completion_path = out / "completion.txt"
    lease_path = out / "lease-receipt.json"
    execution = _load_json(execution_path, label="completed execution")
    _validate_execution(execution, execution=execution_name, frozen=frozen)
    lease = _load_json(lease_path, label="historical-outcome lease")
    lease_expected = _validate_lease_receipt(lease, frozen=frozen)
    completion = dict(
        line.split("=", 1)
        for line in completion_path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    if completion.get("uses_realized_outcomes") != "true" or completion.get(
        "actual_score_query_executed"
    ) != "true":
        raise RuntimeError("A7 realized release completion differs")
    value = {
        "version": "a7-realized-lease-release-intent-v1",
        "run_id": RUN_ID,
        "lease_uri": LEASE_URI,
        "lease_generation": lease_expected["generation"],
        "lease_sha256": lease_expected["sha256"],
        "lease_receipt_sha256": _sha(lease_path),
        "execution": execution_name,
        "execution_sha256": _sha(execution_path),
        "completion_sha256": _sha(completion_path),
        "disposition": complete["disposition"],
        "action": "delete-only-exact-generation-after-create-only-intent",
        "uses_realized_outcomes": True,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    return value, _canonical_json(value)


def _validate_release_intent_files(
    out: Path, *, object_loader: ObjectLoader | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected, raw = _realized_release_intent(out)
    body_path = out / "lease-release-intent.json"
    object_path = out / "lease-release-intent-object.json"
    body = _load_json(body_path, label="realized lease-release intent")
    metadata = _load_json(
        object_path, label="realized lease-release intent object",
    )
    if body != expected or body_path.read_bytes() != raw or set(metadata) != {
        "uri", "generation", "metageneration", "bytes", "sha256",
    }:
        raise RuntimeError("A7 realized lease-release intent differs")
    normalized = _metadata_block(
        metadata, uri=RELEASE_INTENT_URI, label="lease-release intent",
    )
    if normalized["sha256"] != _sha_bytes(raw) or normalized["bytes"] != len(raw):
        raise RuntimeError("A7 realized lease-release object differs")
    if object_loader is not None:
        live, downloaded = object_loader(
            RELEASE_INTENT_URI, normalized["generation"],
        )
        _validate_loaded_object(
            live, downloaded, normalized, label="lease-release intent",
        )
        if downloaded != raw:
            raise RuntimeError("A7 live lease-release intent differs")
    return body, normalized


def _delete_intended_lease(intent: Mapping[str, Any], lease_raw: bytes) -> str:
    """Delete only the active generation registered by the durable intent."""
    if intent.get("lease_uri") != LEASE_URI or intent.get(
        "lease_sha256"
    ) != _sha_bytes(lease_raw):
        raise RuntimeError("A7 realized lease-delete identity differs")
    generation = _positive_int(
        intent.get("lease_generation"), label="lease-delete generation",
    )
    bucket_name, name = _gcs_parts(LEASE_URI)
    blob = storage.Client(project=PROJECT).bucket(bucket_name).blob(name)
    try:
        blob.reload()
    except NotFound:
        return "already-absent-after-durable-intent"
    live_generation = str(blob.generation or "")
    if live_generation != str(generation):
        if re.fullmatch(r"[1-9][0-9]*", live_generation) is None:
            raise RuntimeError("A7 live lease generation differs")
        return "registered-generation-already-absent"
    downloaded = blob.download_as_bytes(if_generation_match=generation)
    if downloaded != lease_raw:
        raise RuntimeError("A7 live lease differs from release intent")
    blob.delete(if_generation_match=generation)
    return "deleted-registered-generation"


def close_realized_lease(
    out: Path = DEFAULT_OUT, *,
    object_creator: ObjectCreator | None = None,
    object_loader: ObjectLoader | None = None,
    lease_closer: Callable[[Mapping[str, Any], bytes], str] | None = None,
) -> dict[str, Any]:
    """Create the durable tombstone, then idempotently close one lease."""
    if (out / "lease-release.txt").is_file():
        return _validate_closed(out, object_loader=object_loader)
    expected, raw = _realized_release_intent(out)
    reader: _StorageReader | None = None
    if object_creator is None or object_loader is None:
        reader = _StorageReader()
    if object_creator is None:
        assert reader is not None
        object_creator = reader.create_or_validate
    if object_loader is None:
        assert reader is not None
        object_loader = reader.load
    metadata, downloaded = object_creator(RELEASE_INTENT_URI, raw)
    normalized = _metadata_block(
        metadata, uri=RELEASE_INTENT_URI, label="lease-release intent",
    )
    if downloaded != raw or normalized["sha256"] != _sha_bytes(raw) or \
            normalized["bytes"] != len(raw):
        raise RuntimeError("A7 created lease-release intent differs")
    _write_or_validate(
        out / "lease-release-intent.json", raw,
        label="local lease-release intent",
    )
    _write_or_validate(
        out / "lease-release-intent-object.json", _canonical_json(normalized),
        label="local lease-release intent object",
    )
    intent, intent_object = _validate_release_intent_files(
        out, object_loader=object_loader,
    )
    lease = _load_json(out / "lease-receipt.json", label="historical-outcome lease")
    lease_raw = _canonical_json(lease["lease"])
    closer = lease_closer or _delete_intended_lease
    close_status = closer(intent, lease_raw)
    if close_status not in {
        "deleted-registered-generation", "already-absent-after-durable-intent",
        "registered-generation-already-absent",
    }:
        raise RuntimeError("A7 realized lease-delete status differs")
    release_raw = (
        f"released_at={datetime.now(timezone.utc).isoformat()}\n"
        f"run_id={RUN_ID}\n"
        f"lease_receipt_sha256={_sha(out / 'lease-receipt.json')}\n"
        f"completion_sha256={_sha(out / 'completion.txt')}\n"
        "lease_action=released-after-realized-outcome\n"
        "lease_archive_uri=none\n"
        f"lease_release_intent_uri={RELEASE_INTENT_URI}\n"
        f"lease_release_intent_generation={intent_object['generation']}\n"
        f"lease_release_intent_sha256={intent_object['sha256']}\n"
        "lease_release_intent_object_sha256="
        f"{_sha(out / 'lease-release-intent-object.json')}\n"
    ).encode("utf-8")
    _write_or_validate(
        out / "lease-release.txt", release_raw,
        label="realized lease-close receipt",
    )
    return _validate_closed(out, object_loader=object_loader)


def _validate_closed(
    out: Path, *, object_loader: ObjectLoader | None = None,
) -> dict[str, Any]:
    """Revalidate the immutable harvest and its exact post-lease closure."""
    complete = _validate_complete(out)
    release_path = out / "lease-release.txt"
    lease_path = out / "lease-receipt.json"
    completion_path = out / "completion.txt"
    if any(path.is_symlink() or not path.is_file() for path in (
        release_path, lease_path, completion_path,
    )):
        raise RuntimeError("A7 lease-close receipt population differs")
    lines = release_path.read_text(encoding="utf-8").splitlines()
    expected_order = (
        "released_at", "run_id", "lease_receipt_sha256",
        "completion_sha256", "lease_action", "lease_archive_uri",
        "lease_release_intent_uri", "lease_release_intent_generation",
        "lease_release_intent_sha256",
        "lease_release_intent_object_sha256",
    )
    if len(lines) != len(expected_order) or any(
        "=" not in line for line in lines
    ):
        raise RuntimeError("A7 lease-close receipt fields differ")
    pairs = [line.split("=", 1) for line in lines]
    if tuple(key for key, _ in pairs) != expected_order:
        raise RuntimeError("A7 lease-close receipt fields differ")
    receipt = dict(pairs)
    try:
        released_at = datetime.fromisoformat(receipt["released_at"])
    except ValueError as exc:
        raise RuntimeError("A7 lease-close timestamp differs") from exc
    if released_at.tzinfo is None or released_at.utcoffset() != timezone.utc.utcoffset(
        released_at
    ) or receipt["run_id"] != RUN_ID or receipt[
        "lease_receipt_sha256"
    ] != _sha(lease_path) or receipt["completion_sha256"] != _sha(
        completion_path
    ):
        raise RuntimeError("A7 lease-close receipt identity differs")
    tail = complete["disposition"] == "tail-artifact-risk-phase-s"
    expected_action = (
        "abandoned-after-proven-no-outcome-tail-closure"
        if tail else "released-after-realized-outcome"
    )
    closure = out / "tail-outcome-blind-closure"
    intent_paths = (
        out / "lease-release-intent.json",
        out / "lease-release-intent-object.json",
    )
    if receipt["lease_action"] != expected_action:
        raise RuntimeError("A7 lease-close action differs")
    if tail:
        if closure.is_symlink() or not closure.is_dir():
            raise RuntimeError("A7 tail lease-closure directory differs")
        children = sorted(closure.iterdir(), key=lambda path: path.name)
        if [path.name for path in children] != [
            "abandon.txt", "lease-receipt.json",
        ] or any(path.is_symlink() or not path.is_file() for path in children):
            raise RuntimeError("A7 tail lease-closure inventory differs")
        closure_lease = closure / "lease-receipt.json"
        abandon_lines = (closure / "abandon.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        prefix = "HISTORICAL_OUTCOME_LEASE_ABANDONED "
        if closure_lease.read_bytes() != lease_path.read_bytes() or len(
            abandon_lines
        ) != 1 or not abandon_lines[0].startswith(prefix):
            raise RuntimeError("A7 tail lease-closure evidence differs")
        archive_uri = abandon_lines[0][len(prefix):]
        if re.fullmatch(
            r"gs://nfl-predictions-503414-raw/research-governance/archive/"
            r"historical-outcome-stale-[0-9]{8}-[0-9]{6}-"
            r"a7-tail-artifact-no-outcome\.json",
            archive_uri,
        ) is None or receipt["lease_archive_uri"] != archive_uri:
            raise RuntimeError("A7 tail lease archive identity differs")
        if any(path.exists() for path in intent_paths) or any(
            receipt[key] != "none" for key in (
                "lease_release_intent_uri",
                "lease_release_intent_generation",
                "lease_release_intent_sha256",
                "lease_release_intent_object_sha256",
            )
        ):
            raise RuntimeError("A7 tail lease-release intent differs")
    else:
        if closure.exists() or receipt["lease_archive_uri"] != "none":
            raise RuntimeError("A7 realized lease closure differs")
        _intent, intent_object = _validate_release_intent_files(
            out, object_loader=object_loader,
        )
        if receipt["lease_release_intent_uri"] != RELEASE_INTENT_URI or \
                receipt["lease_release_intent_generation"] != intent_object[
                    "generation"
                ] or receipt["lease_release_intent_sha256"] != intent_object[
                    "sha256"
                ] or receipt["lease_release_intent_object_sha256"] != _sha(
                    intent_paths[1]
                ):
            raise RuntimeError("A7 realized lease-release receipt differs")
    return {
        **complete,
        "status": "already-closed",
        "lease_action": expected_action,
        "lease_receipt_sha256": receipt["lease_receipt_sha256"],
    }


def _validate_failure_closure(out: Path) -> dict[str, Any]:
    """Validate a terminal/prelaunch closure and permanently forbid retry."""
    candidates = [out / "failed-prelaunch"] + sorted(
        out.glob("failed-terminal-*"), key=lambda path: path.name,
    )
    candidates = [path for path in candidates if path.exists()]
    if len(candidates) != 1 or candidates[0].is_symlink() or not candidates[
        0
    ].is_dir() or any((out / name).exists() for name in (
        "lease-receipt.json", "lease-release.txt", "finish.sha256",
    )):
        raise RuntimeError("A7 watcher failure-closure population differs")
    closure_dir = candidates[0]
    terminal = closure_dir.name.startswith("failed-terminal-")
    expected_files = {
        "abandon.txt", "failure-closure.json", "failure-closure.sha256",
        "lease-receipt.json",
    } | ({"execution.json"} if terminal else set())
    children = tuple(closure_dir.iterdir())
    if {path.name for path in children} != expected_files or any(
        path.is_symlink() or not path.is_file() for path in children
    ):
        raise RuntimeError("A7 watcher failure-closure inventory differs")
    _validate_hash_ledger(
        closure_dir / "failure-closure.sha256", base=closure_dir,
        expected={"failure-closure.json"},
    )
    value = _load_json(
        closure_dir / "failure-closure.json", label="watcher failure closure",
    )
    if set(value) != {
        "version", "run_id", "reason", "disposition", "execution",
        "execution_sha256", "lease_receipt_sha256", "lease_archive_uri",
        "possible_historical_outcome_access", "historical_retry_licensed",
        "production_change_licensed",
        "production_law_scorefree_transfer_licensed",
        "prospective_shadow_licensed",
    }:
        raise RuntimeError("A7 watcher failure-closure fields differ")
    manifest = _load_json(out / "manifest.json", label="launch manifest")
    lease_path = closure_dir / "lease-receipt.json"
    lease = _load_json(lease_path, label="closed historical-outcome lease")
    lease_value = lease.get("lease") if isinstance(lease, dict) else None
    if not isinstance(lease_value, dict) or lease_value.get(
        "version"
    ) != "historical-outcome-active-v1" or lease_value.get("run_id") != RUN_ID or \
            lease_value.get("job") != JOB or lease_value.get(
                "code_sha"
            ) != manifest.get("code_sha") or lease_value.get(
                "image"
            ) != manifest.get("image") or value.get("version") != (
                "a7-watcher-failure-closure-v1"
            ) or value.get("run_id") != RUN_ID or value.get(
                "lease_receipt_sha256"
            ) != _sha(lease_path) or value.get(
                "historical_retry_licensed"
            ) is not False or value.get("production_change_licensed") is not False or \
            value.get("production_law_scorefree_transfer_licensed") is not False or \
            value.get("prospective_shadow_licensed") is not False:
        raise RuntimeError("A7 watcher failure-closure identity differs")
    abandon_lines = (closure_dir / "abandon.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    prefix = "HISTORICAL_OUTCOME_LEASE_ABANDONED "
    if len(abandon_lines) != 1 or not abandon_lines[0].startswith(prefix) or \
            abandon_lines[0][len(prefix):] != value.get("lease_archive_uri"):
        raise RuntimeError("A7 watcher failure archive differs")
    reason = "a7-terminal-failed" if terminal else "a7-prelaunch-failed"
    expected_disposition = (
        "closed-terminal-failed-no-retry"
        if terminal else "closed-prelaunch-no-retry"
    )
    archive_pattern = (
        r"gs://nfl-predictions-503414-raw/research-governance/archive/"
        r"historical-outcome-stale-[0-9]{8}-[0-9]{6}-" + reason + r"\.json"
    )
    if value.get("reason") != reason or value.get(
        "disposition"
    ) != expected_disposition or re.fullmatch(
        archive_pattern, str(value.get("lease_archive_uri", ""))
    ) is None or value.get("possible_historical_outcome_access") is not terminal:
        raise RuntimeError("A7 watcher failure disposition differs")
    if terminal:
        execution_path = closure_dir / "execution.json"
        execution = _load_json(execution_path, label="failed execution")
        name = str(execution.get("metadata", {}).get("name", ""))
        completed = [
            row for row in execution.get("status", {}).get("conditions", [])
            if row.get("type") == "Completed"
        ]
        if name != value.get("execution") or not name.startswith(JOB + "-") or \
                value.get("execution_sha256") != _sha(execution_path) or len(
                    completed
                ) != 1 or completed[0].get("status") != "False":
            raise RuntimeError("A7 failed-terminal execution differs")
        rows = (out / "executions.txt").read_text(encoding="utf-8").splitlines()
        if rows != [f"{JOB} {name} {RESULT_URI}"]:
            raise RuntimeError("A7 failed-terminal execution ledger differs")
    elif value.get("execution") is not None or value.get(
        "execution_sha256"
    ) is not None or (out / "launch-intent.json").exists() or (
        out / "executions.txt"
    ).exists():
        raise RuntimeError("A7 prelaunch closure contains launch evidence")
    return {
        "status": "closed-no-retry", "run_id": RUN_ID,
        "disposition": expected_disposition,
        "possible_historical_outcome_access": terminal,
    }


def finish(
    out: Path = DEFAULT_OUT, *, root: Path = ROOT,
    execution_loader: ExecutionLoader | None = None,
    inventory_loader: InventoryLoader | None = None,
    object_loader: ObjectLoader | None = None,
    query_loader: QueryLoader = _scorefree_queries,
    science_replayer: ScienceReplayer = _replay_science,
    git_source_loader: GitSourceLoader = _git_blob,
) -> dict[str, Any]:
    if (out / "finish.sha256").is_file():
        return _validate_complete(out)
    final_names = {
        "freeze-manifest.json", "smoke-preflight.json",
        "support-preflight.json", "smoke-terminal.json",
        "support-terminal.json", "execution.json", "object-metadata.json",
        "live-lease-metadata.json", "job-claim-metadata.json",
        "science-replay.json", "report.json",
        "completion.txt",
    }
    if any((out / name).exists() for name in final_names) or \
            (out / PENDING_NAME).exists():
        raise RuntimeError("A7 partial or immutable strict harvest exists")
    frozen, execution, _launch_manifest, freeze_validation, lease = \
        _validate_launch_sources(
            out, root=root, git_source_loader=git_source_loader,
        )
    if execution_loader is None:
        execution_loader = _execution_metadata
    reader: _StorageReader | None = None
    if inventory_loader is None or object_loader is None:
        reader = _StorageReader()
    if inventory_loader is None:
        assert reader is not None
        inventory_loader = reader.inventory
    if object_loader is None:
        assert reader is not None
        object_loader = reader.load

    # Body-blind boundary: all terminal, lease, freeze/preflight, and exact
    # result-inventory checks complete before result.json is downloaded.
    execution_value = execution_loader(execution)
    _validate_execution(execution_value, execution=execution, frozen=frozen)
    inventory = _validate_result_inventory(inventory_loader(RESULT_URI))
    lease_metadata, _lease_raw = _validate_live_lease(
        lease, frozen=frozen, object_loader=object_loader,
    )
    freeze_expected = freeze_validation["freeze_manifest"]
    freeze_metadata, freeze_raw = object_loader(
        frozen.freeze_manifest_uri, frozen.freeze_manifest_generation,
    )
    _validate_loaded_object(
        freeze_metadata, freeze_raw, freeze_expected, label="freeze manifest",
    )
    freeze_manifest = _validate_freeze_manifest(
        _json_object(freeze_raw, label="freeze manifest"),
        expected_code_sha=frozen.code_sha, expected_image=frozen.image,
        root=root, git_source_loader=git_source_loader,
    )
    if freeze_validation.get("prefix_inventory_sha256") != freeze_manifest[
        "prefix_inventory_sha256"
    ]:
        raise RuntimeError("A7 live freeze inventory hashes differ")
    job_claim = _validate_job_claim_receipt(
        freeze_manifest["job_claim"], code_sha=frozen.code_sha,
        image=frozen.image, protocol_sha256=frozen.protocol_sha256,
        a3_logical_release_sha256=frozen.a3_logical_release_sha256,
        job_uid=frozen.job_uid,
    )
    claim_expected = _metadata_block(
        job_claim["object"], uri=JOB_CLAIM_URI, label="job claim",
    )
    claim_metadata, claim_raw = object_loader(
        JOB_CLAIM_URI, claim_expected["generation"],
    )
    _validate_loaded_object(
        claim_metadata, claim_raw, claim_expected, label="job claim",
    )
    if _json_object(claim_raw, label="job claim") != job_claim["claim"]:
        raise RuntimeError("A7 durable job claim changed before harvest")
    preflight_bodies: dict[str, bytes] = {}
    terminal_bodies: dict[str, bytes] = {}
    terminal_values: dict[str, dict[str, Any]] = {}
    for key, mode in (
        ("smoke", "real-artifact-smoke"),
        ("support", "support-census"),
    ):
        expected = _metadata_block(
            freeze_manifest["preflights"][key]["science"],
            uri=SMOKE_URI if key == "smoke" else SUPPORT_URI,
            label=f"{key} preflight",
        )
        metadata, raw = object_loader(expected["uri"], expected["generation"])
        _validate_loaded_object(metadata, raw, expected, label=f"{key} preflight")
        _validate_preflight_receipt(
            raw, mode=mode, manifest=freeze_manifest,
        )
        preflight_bodies[key] = raw
        terminal_expected = _metadata_block(
            freeze_manifest["preflights"][key]["terminal"],
            uri=(
                SMOKE_TERMINAL_URI if key == "smoke"
                else SUPPORT_TERMINAL_URI
            ),
            label=f"{key} terminal",
        )
        terminal_metadata, terminal_raw = object_loader(
            terminal_expected["uri"], terminal_expected["generation"],
        )
        _validate_loaded_object(
            terminal_metadata, terminal_raw, terminal_expected,
            label=f"{key} terminal",
        )
        terminal_value = _validate_preflight_terminal_receipt(
            _json_object(terminal_raw, label=f"{key} terminal"),
            mode=mode, science_object=expected, claim=job_claim,
            code_sha=frozen.code_sha, image=frozen.image,
            protocol_sha256=frozen.protocol_sha256,
            a3_logical_release_sha256=frozen.a3_logical_release_sha256,
            build_id=frozen.build_id,
            prior_science_object=(
                freeze_manifest["preflights"]["smoke"]["science"]
                if key == "support" else None
            ),
            prior_terminal_object=(
                freeze_manifest["preflights"]["smoke"]["terminal"]
                if key == "support" else None
            ),
        )
        if key == "support" and terminal_value["support_passed"] is not True:
            raise RuntimeError("A7 frozen support terminal did not pass")
        terminal_bodies[key] = terminal_raw
        terminal_values[key] = terminal_value
    smoke_execution = terminal_values["smoke"]["execution"]
    support_execution = terminal_values["support"]["execution"]
    if terminal_values["smoke"]["build_id"] != terminal_values[
        "support"
    ]["build_id"] or smoke_execution["prior_job_generation"] != job_claim["claim"][
        "job_generation"
    ] or smoke_execution["prior_job_spec_sha256"] != job_claim["claim"][
        "job_spec_sha256"
    ] or support_execution["prior_job_generation"] != smoke_execution[
        "job_generation"
    ] or support_execution["prior_job_spec_sha256"] != smoke_execution[
        "job_spec_sha256"
    ]:
        raise RuntimeError("A7 live preflight job-generation/spec chain differs")

    result_metadata, result_raw = object_loader(
        RESULT_URI, str(inventory["generation"]),
    )
    if result_metadata.get("uri") != RESULT_URI or result_metadata.get(
        "generation"
    ) != inventory["generation"] or result_metadata.get(
        "metageneration"
    ) != inventory["metageneration"] or result_metadata.get(
        "bytes"
    ) != inventory["bytes"] or len(result_raw) != inventory["bytes"]:
        raise RuntimeError("A7 result object changed during pinned download")
    report = _json_object(result_raw, label="result body")
    _validate_result_header(report, freeze_manifest, frozen)
    in_image_replay = _validate_in_image_science_replay(
        report, freeze_manifest, frozen,
    )
    for key in ("smoke", "support"):
        evidence_key = "smoke_receipt" if key == "smoke" else "support_receipt"
        if report["freeze_evidence"].get(evidence_key) != _json_object(
            preflight_bodies[key], label=f"{key} preflight receipt",
        ):
            raise RuntimeError("A7 result embedded preflight receipt differs")
        terminal_key = f"{key}_terminal_receipt"
        if report["freeze_evidence"].get(terminal_key) != _json_object(
            terminal_bodies[key], label=f"{key} terminal receipt",
        ):
            raise RuntimeError("A7 result embedded preflight terminal differs")
    replay_input = dict(report)
    del replay_input["in_image_science_replay"]
    replay = science_replayer(
        replay_input, freeze_manifest, query_loader, object_loader,
    )
    if replay != in_image_replay:
        raise RuntimeError("A7 local/in-image science replay differs")
    uses_realized = report["uses_realized_outcomes"] is True
    if replay.get("version") != "a7-strict-science-replay-v1" or \
            replay.get("run_id") != RUN_ID or replay.get(
                "outcome_replayed"
            ) is not uses_realized or replay.get(
                "baseline_reproduced"
            ) is not uses_realized or replay.get(
                "uses_realized_outcomes"
            ) is not uses_realized or replay.get(
                "actual_score_query_executed"
            ) is not uses_realized or \
            replay.get("production_change_licensed") is not False or \
            replay.get("disposition") not in ALLOWED_DISPOSITIONS:
        raise RuntimeError("A7 strict science replay receipt differs")
    if uses_realized != (
        replay["disposition"] != "tail-artifact-risk-phase-s"
    ):
        raise RuntimeError("A7 strict science replay outcome branch differs")

    pending = out / PENDING_NAME
    pending.mkdir()
    (pending / "freeze-manifest.json").write_bytes(freeze_raw)
    (pending / "smoke-preflight.json").write_bytes(preflight_bodies["smoke"])
    (pending / "support-preflight.json").write_bytes(preflight_bodies["support"])
    (pending / "smoke-terminal.json").write_bytes(terminal_bodies["smoke"])
    (pending / "support-terminal.json").write_bytes(terminal_bodies["support"])
    (pending / "execution.json").write_bytes(_canonical_json(execution_value))
    result_metadata = dict(result_metadata)
    result_metadata["sha256"] = _sha_bytes(result_raw)
    (pending / "object-metadata.json").write_bytes(_canonical_json(result_metadata))
    (pending / "live-lease-metadata.json").write_bytes(_canonical_json(
        lease_metadata,
    ))
    (pending / "job-claim-metadata.json").write_bytes(_canonical_json(
        claim_metadata,
    ))
    (pending / "science-replay.json").write_bytes(_canonical_json(replay))
    (pending / "report.json").write_bytes(result_raw)
    disposition = str(replay["disposition"])
    completion = (
        "\n".join((
            f"validated_at={datetime.now(timezone.utc).isoformat()}",
            f"run_id={RUN_ID}",
            f"disposition={disposition}",
            "executions=1", "objects=1", "scientific_bodies=1",
            "strict_science_replay=true",
            f"report_sha256={_sha_bytes(result_raw)}",
            f"science_replay_sha256={_sha_bytes(_canonical_json(replay))}",
            f"freeze_manifest_sha256={frozen.freeze_manifest_sha256}",
            f"uses_realized_outcomes={str(uses_realized).lower()}",
            f"actual_score_query_executed={str(uses_realized).lower()}",
            "production_change_licensed=false",
            "prospective_shadow_licensed=false",
            "historical_outcome_lease_release_licensed=true",
            "historical_outcome_lease_released=false",
        )) + "\n"
    ).encode("utf-8")
    (pending / "completion.txt").write_bytes(completion)
    for name in sorted(final_names):
        source, target = pending / name, out / name
        if not source.is_file() or target.exists():
            raise RuntimeError("A7 strict-harvest publication target differs")
        source.rename(target)
    pending.rmdir()
    finish_sources = [
        out / name for name in sorted({
            "manifest.json", "prepared.sha256", "launch.sha256",
            "launch-intent.json", "executions.txt", "lease-receipt.json", *final_names,
        })
    ]
    _write_new(out / "finish.sha256", _hash_ledger(finish_sources, base=out))
    result = _validate_complete(out)
    result["status"] = "completed"
    print(
        "A7_SELECT_LADDER_STRICTLY_HARVESTED",
        f"run_id={RUN_ID}", f"disposition={disposition}",
        f"sha256={_sha_bytes(result_raw)}",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate-freeze")
    validate_parser.add_argument("--freeze-manifest-uri", required=True)
    validate_parser.add_argument("--freeze-manifest-generation", required=True)
    validate_parser.add_argument("--freeze-manifest-sha256", required=True)
    validate_parser.add_argument("--code-sha", required=True)
    validate_parser.add_argument("--image", required=True)
    validate_parser.add_argument(
        "--a3-logical-release", type=Path, default=DEFAULT_A3_RELEASE,
    )
    validate_parser.add_argument("--receipt", type=Path, required=True)
    finish_parser = subparsers.add_parser("finish")
    finish_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    closed_parser = subparsers.add_parser("validate-closed")
    closed_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    release_parser = subparsers.add_parser("close-realized-lease")
    release_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    failure_parser = subparsers.add_parser("validate-failure-closure")
    failure_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    claim_parser = subparsers.add_parser("claim-job")
    claim_parser.add_argument("--code-sha", required=True)
    claim_parser.add_argument("--image", required=True)
    claim_parser.add_argument("--job-metadata", type=Path, required=True)
    claim_parser.add_argument(
        "--a3-logical-release", type=Path, default=DEFAULT_A3_RELEASE,
    )
    claim_parser.add_argument(
        "--v1-failed-preflight-release", type=Path,
        default=DEFAULT_V1_FAILURE_RELEASE,
    )
    claim_parser.add_argument(
        "--v1-failed-preflight-release-object", type=Path,
        default=DEFAULT_V1_FAILURE_RELEASE_OBJECT,
    )
    claim_parser.add_argument("--receipt", type=Path, required=True)
    preflight_parser = subparsers.add_parser("finish-preflight")
    preflight_parser.add_argument(
        "--mode", choices=("smoke", "support"), required=True,
    )
    preflight_parser.add_argument("--output-dir", type=Path, required=True)
    canonicalize_parser = subparsers.add_parser("canonicalize-external-json")
    canonicalize_parser.add_argument("--raw", type=Path, required=True)
    canonicalize_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate-freeze":
        if args.receipt.exists():
            raise RuntimeError("A7 immutable freeze-validation receipt exists")
        reader = _StorageReader()
        value = validate_freeze_for_launch(
            freeze_manifest_uri=args.freeze_manifest_uri,
            freeze_manifest_generation=args.freeze_manifest_generation,
            freeze_manifest_sha256=args.freeze_manifest_sha256,
            expected_code_sha=args.code_sha,
            expected_image=args.image,
            a3_release_path=args.a3_logical_release,
            object_loader=reader.load,
        )
        _write_new(args.receipt, _canonical_json(value))
        print(
            "A7_FREEZE_VALIDATED",
            f"sha256={_sha(args.receipt)}",
        )
    elif args.command == "canonicalize-external-json":
        _canonicalize_external_json(args.raw, args.output)
    elif args.command == "claim-job":
        value = create_job_claim(
            code_sha=args.code_sha, image=args.image,
            job_metadata=_load_json(args.job_metadata, label="job metadata"),
            a3_release_path=args.a3_logical_release,
            v1_failure_release_path=args.v1_failed_preflight_release,
            v1_failure_release_object_path=(
                args.v1_failed_preflight_release_object
            ),
            receipt_path=args.receipt,
        )
        print(
            "A7_DURABLE_JOB_CLAIMED",
            f"generation={value['object']['generation']}",
            f"sha256={value['object']['sha256']}",
        )
    elif args.command == "finish-preflight":
        finish_preflight(
            mode=(
                "real-artifact-smoke" if args.mode == "smoke"
                else "support-census"
            ),
            out=args.output_dir,
        )
    elif args.command == "finish":
        finish(args.output_dir)
    elif args.command == "close-realized-lease":
        value = close_realized_lease(args.output_dir)
        print(
            "A7_REALIZED_LEASE_CLOSED",
            f"run_id={value['run_id']}",
            f"lease_action={value['lease_action']}",
        )
    elif args.command == "validate-closed":
        complete = _validate_complete(args.output_dir)
        loader = (
            _StorageReader().load
            if complete["disposition"] != "tail-artifact-risk-phase-s"
            else None
        )
        value = _validate_closed(args.output_dir, object_loader=loader)
        print(
            "A7_SELECT_LADDER_CLOSURE_VALIDATED",
            f"run_id={value['run_id']}",
            f"lease_action={value['lease_action']}",
        )
    else:
        value = _validate_failure_closure(args.output_dir)
        print(
            "A7_SELECT_LADDER_FAILURE_CLOSURE_VALIDATED",
            f"run_id={value['run_id']}",
            f"disposition={value['disposition']}",
        )


if __name__ == "__main__":
    main()
