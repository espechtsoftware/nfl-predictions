#!/usr/bin/env python3
"""One-shot B1 corpus-tail evaluation and default-off 2026 shadow freeze.

The outcome-blind smoke and prospective shadow SQL never select realized
columns.  Historical mode is separately frozen and refuses to query until it
has verified the live, generation-pinned historical-outcome lease.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
from typing import Any

import pandas as pd
from google.api_core.exceptions import PreconditionFailed
from google.cloud import bigquery, storage

from nfl_dfs.research.b1_corpus_tail import (
    CorpusTailError,
    artifact_sha256,
    build_deduplicated_dataset,
    build_shadow_receipt,
    evaluate_six_week_adoption,
    historical_evaluation,
    write_create_once,
)

import run_b1_union_c_census as b1


PROJECT = "nfl-predictions-503414"
RUN_ID = "20260820-b1-corpus-tail-model-v1"
PROTOCOL = Path("reports/2026-08-20-b1-corpus-tail-model-protocol.md")
CANDIDATE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
LEASE_URI = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
HISTORICAL_ATTEMPT_URI = (
    "gs://nfl-predictions-503414-raw/research/b1-corpus-tail-runs/"
    f"{RUN_ID}/historical-attempt.json"
)
EXPECTED_PANELS = 51
EXPECTED_SOURCE_ROWS = 698_172
EXPECTED_DEDUP_ROWS = 127_778
EXPECTED_SLATES = 54

B1_PROTOCOL = Path("reports/2026-08-18-b1-union-c-census-protocol.md")
B1_REPORT = Path(
    "reports/b1-union-c-census-runs/20260818-b1-union-c-census-v1/report.json"
)
B1_RUNNER = Path("scripts/run_b1_union_c_census.py")
B1_PROTOCOL_SHA256 = "2d1cb29bda5fc25965661acb891566bd8e9daf108bb579ad9eca99d862c29789"
B1_REPORT_SHA256 = "4e654a58563391ed3020b0b221756070cd07fb10e962fc80e4bbedfd5f2631b6"
B1_RUNNER_SHA256 = "fc12e2871d638995603258f16d9e1beeee68f8a885ba3a53f9f32790d62c608f"

CANDIDATE_PRELOCK_COLUMNS = (
    "panel_run_id", "season", "week", "cand_ix", "players", "tag",
    "selected", "selected_rank", "salary", "p_line", "sim_mean", "sim_sd",
    "sim_q50", "sim_q90", "sim_q99", "sim_rank_p_line", "labels_complete",
)
PLAYER_PRELOCK_COLUMNS = (
    "season", "week", "id", "pos", "team", "opp", "game_id", "salary",
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require_exact_boolean_series(values: pd.Series, *, field: str) -> None:
    if values.isna().any() or not pd.api.types.is_bool_dtype(values.dtype):
        raise CorpusTailError(f"{field} is not exact boolean data")


def _require_b1_pins() -> None:
    for path, expected in (
        (B1_PROTOCOL, B1_PROTOCOL_SHA256),
        (B1_REPORT, B1_REPORT_SHA256),
        (B1_RUNNER, B1_RUNNER_SHA256),
    ):
        observed = _sha(path)
        if observed != expected:
            raise CorpusTailError(
                f"B1 source pin differs for {path}: expected {expected}, got {observed}"
            )
    if len(b1.ALL_PANELS) != EXPECTED_PANELS:
        raise CorpusTailError("B1 source panel population differs")


def _candidate_sql(*, outcomes: bool, one_slate: bool) -> str:
    columns = list(CANDIDATE_PRELOCK_COLUMNS)
    if outcomes:
        columns.append("actual_score")
    slate = " AND season = @season AND week = @week" if one_slate else ""
    return f"""
SELECT {', '.join(columns)}
FROM `{CANDIDATE_TABLE}`
WHERE panel_run_id IN UNNEST(@panels){slate}
ORDER BY panel_run_id, season, week, cand_ix
"""


def _player_sql(*, one_slate: bool) -> str:
    slate = " AND season = @season AND week = @week" if one_slate else ""
    return f"""
SELECT {', '.join(PLAYER_PRELOCK_COLUMNS)}
FROM `{PLAYER_TABLE}`
WHERE panel_run_id = @canonical_panel{slate}
ORDER BY season, week, id
"""


def _query(
    client: bigquery.Client,
    sql: str,
    parameters: list[bigquery.QueryParameter],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    job = client.query(
        sql, job_config=bigquery.QueryJobConfig(query_parameters=parameters),
    )
    frame = job.result().to_dataframe(create_bqstorage_client=False)
    return frame, {
        "job_id": job.job_id, "location": job.location,
        "created": job.created.isoformat() if job.created else None,
        "started": job.started.isoformat() if job.started else None,
        "ended": job.ended.isoformat() if job.ended else None,
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "query_sha256": sha256(sql.encode()).hexdigest(),
    }


def _source_frames(
    client: bigquery.Client,
    *,
    panels: list[str],
    canonical_panel: str,
    outcomes: bool,
    slate: tuple[int, int] | None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    params: list[bigquery.QueryParameter] = [
        bigquery.ArrayQueryParameter("panels", "STRING", panels),
    ]
    player_params: list[bigquery.QueryParameter] = [
        bigquery.ScalarQueryParameter("canonical_panel", "STRING", canonical_panel),
    ]
    if slate is not None:
        season, week = slate
        for target in (params, player_params):
            target.extend([
                bigquery.ScalarQueryParameter("season", "INT64", season),
                bigquery.ScalarQueryParameter("week", "INT64", week),
            ])
    candidates, candidate_job = _query(
        client, _candidate_sql(outcomes=outcomes, one_slate=slate is not None), params,
    )
    players, player_job = _query(
        client, _player_sql(one_slate=slate is not None), player_params,
    )
    return candidates, players, {
        "candidate_query": candidate_job, "player_query": player_job,
        "realized_outcome_columns_read": ["actual_score"] if outcomes else [],
    }


def _stable_frame_sha(frame: pd.DataFrame, order: list[str]) -> str:
    ordered = frame.sort_values(order, kind="stable").reset_index(drop=True)
    digest = sha256()
    digest.update(json.dumps(list(ordered.columns), separators=(",", ":")).encode())
    digest.update(b"\n")
    for values in ordered.itertuples(index=False, name=None):
        row = []
        for value in values:
            if value is None or pd.isna(value):
                row.append(None)
            elif hasattr(value, "item"):
                row.append(value.item())
            elif hasattr(value, "isoformat"):
                row.append(value.isoformat())
            else:
                row.append(value)
        digest.update(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _parse_slate(value: str) -> tuple[int, int]:
    try:
        season, week = map(int, value.split(":"))
    except Exception as exc:
        raise argparse.ArgumentTypeError("slate must be SEASON:WEEK") from exc
    return season, week


def _utc_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CorpusTailError(f"{field} timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusTailError(f"{field} timestamp is not ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CorpusTailError(f"{field} timestamp is not timezone-aware")
    return parsed


def _validate_protocol(expected_sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha or ""):
        raise CorpusTailError("historical mode requires an exact protocol SHA-256")
    observed = _sha(PROTOCOL)
    text = PROTOCOL.read_text(encoding="utf-8")
    if observed != expected_sha or "**Status:** FROZEN" not in text:
        raise CorpusTailError("corpus-tail protocol is not the exact frozen document")
    return observed


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or "/" not in uri[5:]:
        raise CorpusTailError("historical lease URI is invalid")
    return tuple(uri[5:].split("/", 1))  # type: ignore[return-value]


def _validate_live_lease(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    lease = receipt.get("lease", {})
    obj = receipt.get("object", {})
    if (
        lease.get("version") != "historical-outcome-active-v1"
        or lease.get("run_id") != RUN_ID
        or obj.get("uri") != LEASE_URI
        or obj.get("create_only") is not True
        or not str(obj.get("generation", "")).isdigit()
        or not re.fullmatch(r"[0-9a-f]{64}", str(obj.get("sha256", "")))
    ):
        raise CorpusTailError("historical-outcome lease receipt differs")
    bucket, name = _parse_gcs(LEASE_URI)
    client = storage.Client(project=PROJECT)
    live = client.bucket(bucket).blob(name)
    live.reload()
    generation = int(obj["generation"])
    if int(live.generation or 0) != generation:
        raise CorpusTailError("historical-outcome lease is not the current live generation")
    raw = live.download_as_bytes(if_generation_match=generation)
    if sha256(raw).hexdigest() != obj["sha256"] or json.loads(raw) != lease:
        raise CorpusTailError("live historical-outcome lease differs from receipt")
    return {"lease": lease, "object": obj}


def _create_historical_attempt(
    *, protocol_sha: str, lease: dict[str, Any], local_path: Path,
) -> dict[str, Any]:
    if local_path.exists():
        raise CorpusTailError("historical attempt receipt already exists")
    body = {
        "version": "b1-corpus-tail-historical-attempt-v1",
        "run_id": RUN_ID,
        "protocol_sha256": protocol_sha,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "lease": lease,
        "b1_protocol_sha256": B1_PROTOCOL_SHA256,
        "b1_report_sha256": B1_REPORT_SHA256,
        "b1_runner_sha256": B1_RUNNER_SHA256,
        "uses_realized_outcomes_at_creation": False,
        "retry_licensed": False,
        "production_licensed": False,
    }
    raw = (
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    bucket, name = _parse_gcs(HISTORICAL_ATTEMPT_URI)
    blob = storage.Client(project=PROJECT).bucket(bucket).blob(name)
    try:
        blob.upload_from_string(
            raw, content_type="application/json", if_generation_match=0,
        )
    except PreconditionFailed as exc:
        raise CorpusTailError(
            "historical attempt already exists; this one-shot may not run again"
        ) from exc
    blob.reload()
    receipt = {
        "attempt": body,
        "object": {
            "uri": HISTORICAL_ATTEMPT_URI,
            "generation": str(blob.generation),
            "metageneration": str(blob.metageneration),
            "bytes": len(raw),
            "sha256": sha256(raw).hexdigest(),
            "create_only": True,
        },
    }
    write_create_once(local_path, receipt)
    return receipt


def _smoke(client: bigquery.Client, slate: tuple[int, int], output: Path) -> int:
    _require_b1_pins()
    candidates, players, source = _source_frames(
        client, panels=sorted(b1.ALL_PANELS), canonical_panel=b1.CANONICAL_PANEL,
        outcomes=False, slate=slate,
    )
    dataset = build_deduplicated_dataset(
        candidates.drop(columns=["labels_complete"]), players,
        canonical_panel=b1.CANONICAL_PANEL, include_outcomes=False,
    )
    if candidates.panel_run_id.nunique() != EXPECTED_PANELS:
        raise CorpusTailError("outcome-blind smoke does not contain all B1 panels")
    control = dataset[dataset.canonical_selected]
    if len(control) != 80:
        raise CorpusTailError("outcome-blind smoke canonical control is not exact-80")
    receipt = {
        "version": "b1-corpus-tail-outcome-blind-smoke-v1",
        "status": "OUTCOME_BLIND_REALITY_SMOKE_OK",
        "run_id": RUN_ID, "season": slate[0], "week": slate[1],
        "source_panels": int(candidates.panel_run_id.nunique()),
        "source_candidate_rows": len(candidates), "catalog_rows": len(players),
        "deduplicated_rosters": len(dataset),
        "canonical_candidates": int(dataset.canonical_candidate.sum()),
        "canonical_selected": len(control),
        "candidate_frame_sha256": _stable_frame_sha(
            candidates, ["panel_run_id", "season", "week", "cand_ix"]),
        "player_frame_sha256": _stable_frame_sha(players, ["season", "week", "id"]),
        "source": source,
        "uses_realized_outcomes": False,
        "winner_fields_read": [],
        "production_licensed": False,
    }
    digest = write_create_once(output, receipt)
    print(json.dumps({"status": receipt["status"], "receipt": str(output), "sha256": digest}))
    return 0


def _historical(
    client: bigquery.Client,
    *,
    report_path: Path,
    model_path: Path,
    protocol_sha: str,
    lease_path: Path,
    attempt_path: Path,
) -> int:
    _require_b1_pins()
    protocol_sha = _validate_protocol(protocol_sha)
    lease = _validate_live_lease(lease_path)  # must precede the outcome query
    if report_path.exists() or model_path.exists():
        raise CorpusTailError("historical output or model target already exists")
    attempt = _create_historical_attempt(
        protocol_sha=protocol_sha, lease=lease, local_path=attempt_path,
    )
    candidates, players, source = _source_frames(
        client, panels=sorted(b1.ALL_PANELS), canonical_panel=b1.CANONICAL_PANEL,
        outcomes=True, slate=None,
    )
    _require_exact_boolean_series(
        candidates.labels_complete, field="historical labels_complete",
    )
    if not candidates.labels_complete.all():
        raise CorpusTailError("historical B1 source contains incomplete labels")
    dataset = build_deduplicated_dataset(
        candidates.drop(columns=["labels_complete"]), players,
        canonical_panel=b1.CANONICAL_PANEL, include_outcomes=True,
    )
    facts = (
        len(candidates), len(dataset),
        candidates.panel_run_id.nunique(),
        dataset[["season", "week"]].drop_duplicates().shape[0],
    )
    if facts != (EXPECTED_SOURCE_ROWS, EXPECTED_DEDUP_ROWS, EXPECTED_PANELS, EXPECTED_SLATES):
        raise CorpusTailError(f"historical B1 population differs: {facts}")
    report, artifact = historical_evaluation(dataset)
    artifact.update({
        "protocol_sha256": protocol_sha,
        "historical_run_id": RUN_ID,
        "historical_source_rows": len(candidates),
        "historical_deduplicated_rosters": len(dataset),
    })
    artifact["artifact_sha256"] = artifact_sha256(artifact)
    report["source_lock"] = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol_sha,
        "candidate_frame_sha256": _stable_frame_sha(
            candidates, ["panel_run_id", "season", "week", "cand_ix"]),
        "player_frame_sha256": _stable_frame_sha(players, ["season", "week", "id"]),
        "b1_protocol_sha256": B1_PROTOCOL_SHA256,
        "b1_report_sha256": B1_REPORT_SHA256,
        "b1_runner_sha256": B1_RUNNER_SHA256,
        "historical_lease": lease["object"],
        "historical_attempt": attempt["object"],
        **source,
    }
    report["model_artifact_sha256"] = artifact["artifact_sha256"]
    if report["historical_pass"]:
        model_file_sha = write_create_once(model_path, artifact)
        report["model_file_sha256"] = model_file_sha
    else:
        report["model_file_sha256"] = None
    report_file_sha = write_create_once(report_path, report)
    print(json.dumps({
        "historical_pass": report["historical_pass"],
        "report": str(report_path), "report_sha256": report_file_sha,
        "model_written": bool(report["historical_pass"]),
    }, sort_keys=True))
    return 0


def _shadow(
    client: bigquery.Client,
    *,
    slate: tuple[int, int], panels: list[str], canonical_panel: str,
    model_path: Path, output: Path, snapshot_id: str, lock_at: str,
) -> int:
    if slate[0] < 2026 or not panels or canonical_panel not in panels:
        raise CorpusTailError("shadow source panels/slate are invalid")
    candidates, players, source = _source_frames(
        client, panels=sorted(set(panels)), canonical_panel=canonical_panel,
        outcomes=False, slate=slate,
    )
    expected_panels = sorted(set(panels))
    returned_panels = sorted(set(candidates.panel_run_id.astype(str)))
    if returned_panels != expected_panels:
        raise CorpusTailError("prospective source did not return every requested panel")
    labels_complete = candidates.labels_complete
    _require_exact_boolean_series(labels_complete, field="prospective labels_complete")
    if labels_complete.any():
        raise CorpusTailError("prospective shadow source is already outcome-labeled")
    dataset = build_deduplicated_dataset(
        candidates.drop(columns=["labels_complete"]), players,
        canonical_panel=canonical_panel, include_outcomes=False,
    )
    artifact = json.loads(model_path.read_text(encoding="utf-8"))
    query_times = [
        _utc_timestamp(source[name].get("ended"), field=f"{name} completion")
        for name in ("candidate_query", "player_query")
    ]
    snapshot_at = max(query_times).astimezone(timezone.utc).isoformat()
    parsed_lock = _utc_timestamp(lock_at, field="contest lock")
    if max(query_times) >= parsed_lock:
        raise CorpusTailError("prospective source query did not complete before lock")
    source_identity = {
        "snapshot_id": snapshot_id, "snapshot_at": snapshot_at,
        "lock_at": parsed_lock.astimezone(timezone.utc).isoformat(),
        "panels": expected_panels, "canonical_panel": canonical_panel,
        "candidate_rows": len(candidates), "deduplicated_rosters": len(dataset),
        "candidate_frame_sha256": _stable_frame_sha(
            candidates, ["panel_run_id", "season", "week", "cand_ix"]),
        "player_frame_sha256": _stable_frame_sha(players, ["season", "week", "id"]),
        **source,
    }
    receipt = build_shadow_receipt(
        dataset, artifact, source_identity=source_identity,
        enabled=os.environ.get("CORPUS_TAIL_SHADOW_ENABLED", "0") == "1",
    )
    digest = write_create_once(output, receipt)
    print(json.dumps({"shadow": str(output), "sha256": digest, "entries": 80}))
    return 0


def _load_canonical_json(path: Path) -> Any:
    raw = path.read_bytes()

    def reject_constant(value: str) -> None:
        raise CorpusTailError(f"non-finite JSON value is forbidden: {value}")

    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CorpusTailError(f"duplicate JSON key is forbidden: {key}")
            result[key] = value
        return result

    value = json.loads(
        raw, parse_constant=reject_constant, object_pairs_hook=strict_object,
    )
    canonical = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    if raw != canonical:
        raise CorpusTailError(f"JSON file is not canonical: {path}")
    return value


def _load_pinned_json(identity: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(identity, dict) or set(identity) != {"path", "sha256"}:
        raise CorpusTailError(f"{label} identity schema differs")
    path_value = identity["path"]
    expected = identity["sha256"]
    if not isinstance(path_value, str) or not path_value:
        raise CorpusTailError(f"{label} path is absent")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise CorpusTailError(f"{label} SHA-256 is invalid")
    path = Path(path_value)
    if _sha(path) != expected:
        raise CorpusTailError(f"{label} bytes differ from their SHA-256")
    value = _load_canonical_json(path)
    if not isinstance(value, dict):
        raise CorpusTailError(f"{label} body is not an object")
    return value


def _exact_int(value: Any, *, label: str) -> int:
    if type(value) is not int:
        raise CorpusTailError(f"{label} must be an exact JSON integer")
    return value


def _book_keys(value: Any, *, challenger: bool) -> list[str]:
    if not isinstance(value, list) or len(value) != 80:
        raise CorpusTailError("shadow receipt book is not exact-80")
    expected_keys = (
        {"rank", "roster_key", "prelock_tail_score"}
        if challenger else {"rank", "roster_key"}
    )
    keys: list[str] = []
    for expected_rank, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise CorpusTailError("shadow receipt entry schema differs")
        if _exact_int(row["rank"], label="entry rank") != expected_rank:
            raise CorpusTailError("shadow receipt entry ranks are not canonical")
        roster_key = row["roster_key"]
        if not isinstance(roster_key, str) or len(roster_key.split(",")) != 9:
            raise CorpusTailError("shadow receipt roster key is invalid")
        if challenger:
            score = row["prelock_tail_score"]
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                raise CorpusTailError("shadow receipt tail score is non-finite")
        keys.append(roster_key)
    if len(set(keys)) != 80:
        raise CorpusTailError("shadow receipt book repeats a roster")
    return keys


def _grade_week(entry: Any, *, season: int, expected_week: int) -> dict[str, Any]:
    if not isinstance(entry, dict) or set(entry) != {
        "week", "shadow_receipt", "settled_scores",
    }:
        raise CorpusTailError("prospective grade week schema differs")
    if _exact_int(entry["week"], label="grade week") != expected_week:
        raise CorpusTailError("prospective grade weeks are not fixed Weeks 1 through 6")
    receipt = _load_pinned_json(entry["shadow_receipt"], label="shadow receipt")
    receipt_keys = {
        "version", "policy_version", "season", "week", "model_artifact_sha256",
        "source_identity", "candidate_budget_control", "candidate_budget_challenger",
        "entry_budget", "redundancy", "control_entries", "challenger_entries",
        "uses_realized_outcomes", "uses_winner_target_or_feature",
        "production_licensed", "prospective_adoption_gate_required",
    }
    if set(receipt) != receipt_keys:
        raise CorpusTailError("shadow receipt schema differs")
    if (
        receipt["version"] != "b1-corpus-tail-shadow-receipt-v1"
        or receipt["policy_version"] != "b1-corpus-tail-exact80-shadow-v1"
        or _exact_int(receipt["season"], label="receipt season") != season
        or _exact_int(receipt["week"], label="receipt week") != expected_week
        or receipt["uses_realized_outcomes"] is not False
        or receipt["uses_winner_target_or_feature"] is not False
        or receipt["production_licensed"] is not False
        or receipt["prospective_adoption_gate_required"] is not True
    ):
        raise CorpusTailError("shadow receipt boundary differs")
    control_budget = _exact_int(
        receipt["candidate_budget_control"], label="control candidate budget",
    )
    challenger_budget = _exact_int(
        receipt["candidate_budget_challenger"], label="challenger candidate budget",
    )
    if control_budget != challenger_budget or _exact_int(
        receipt["entry_budget"], label="entry budget",
    ) != 80:
        raise CorpusTailError("shadow receipt budgets differ")
    source_identity = receipt["source_identity"]
    if not isinstance(source_identity, dict):
        raise CorpusTailError("shadow source identity is absent")
    snapshot = _utc_timestamp(source_identity.get("snapshot_at"), field="snapshot")
    lock = _utc_timestamp(source_identity.get("lock_at"), field="contest lock")
    if snapshot >= lock:
        raise CorpusTailError("shadow receipt was not frozen before lock")
    query_times = []
    for name in ("candidate_query", "player_query"):
        query = source_identity.get(name)
        if not isinstance(query, dict):
            raise CorpusTailError("shadow receipt source query is absent")
        query_times.append(
            _utc_timestamp(query.get("ended"), field=f"{name} completion")
        )
    panels = source_identity.get("panels")
    canonical_panel = source_identity.get("canonical_panel")
    if (
        max(query_times) != snapshot
        or source_identity.get("realized_outcome_columns_read") != []
        or not isinstance(panels, list) or not panels
        or not isinstance(canonical_panel, str) or canonical_panel not in panels
    ):
        raise CorpusTailError("shadow receipt source/query binding differs")
    control_keys = _book_keys(receipt["control_entries"], challenger=False)
    challenger_keys = _book_keys(receipt["challenger_entries"], challenger=True)

    settled = _load_pinned_json(entry["settled_scores"], label="settled scores")
    if set(settled) != {
        "version", "season", "week", "labels_complete", "source_identity", "scores",
    }:
        raise CorpusTailError("settled score schema differs")
    if (
        settled["version"] != "b1-corpus-tail-settled-scores-v1"
        or _exact_int(settled["season"], label="settled season") != season
        or _exact_int(settled["week"], label="settled week") != expected_week
        or settled["labels_complete"] is not True
        or not isinstance(settled["scores"], list)
    ):
        raise CorpusTailError("settled score boundary differs")
    settled_source = settled["source_identity"]
    if not isinstance(settled_source, dict) or set(settled_source) != {
        "source", "job_id", "query_sha256", "captured_at",
    }:
        raise CorpusTailError("settled score source identity differs")
    if (
        settled_source["source"] != "replay_candidates_staging.actual_score"
        or not isinstance(settled_source["job_id"], str)
        or not settled_source["job_id"]
        or not isinstance(settled_source["query_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", settled_source["query_sha256"])
    ):
        raise CorpusTailError("settled score source identity differs")
    _utc_timestamp(settled_source["captured_at"], field="settled score capture")
    expected_rosters = set(control_keys) | set(challenger_keys)
    scores: dict[str, float] = {}
    for row in settled["scores"]:
        if not isinstance(row, dict) or set(row) != {"roster_key", "actual_score"}:
            raise CorpusTailError("settled score row schema differs")
        key = row["roster_key"]
        score = row["actual_score"]
        if (
            not isinstance(key, str) or key in scores or isinstance(score, bool)
            or not isinstance(score, (int, float)) or not math.isfinite(score)
        ):
            raise CorpusTailError("settled score row is invalid")
        scores[key] = float(score)
    if set(scores) != expected_rosters:
        raise CorpusTailError("settled scores do not exactly cover both frozen books")
    return {
        "season": season,
        "week": expected_week,
        "control_max": max(scores[key] for key in control_keys),
        "challenger_max": max(scores[key] for key in challenger_keys),
        "candidate_budget_control": control_budget,
        "candidate_budget_challenger": challenger_budget,
        "entries_control": len(control_keys),
        "entries_challenger": len(challenger_keys),
        "frozen_before_lock": True,
        "labels_complete": True,
        "receipt_valid": True,
    }


def _materialize_adoption_grades(path: Path) -> pd.DataFrame:
    manifest = _load_canonical_json(path)
    if not isinstance(manifest, dict) or set(manifest) != {"version", "season", "weeks"}:
        raise CorpusTailError("prospective grade manifest schema differs")
    season = _exact_int(manifest["season"], label="grade season")
    if manifest["version"] != "b1-corpus-tail-adoption-grade-manifest-v1" or season < 2026:
        raise CorpusTailError("prospective grade manifest boundary differs")
    weeks = manifest["weeks"]
    if not isinstance(weeks, list) or len(weeks) != 6:
        raise CorpusTailError("prospective grade manifest requires six weeks")
    return pd.DataFrame([
        _grade_week(entry, season=season, expected_week=week)
        for entry, week in zip(weeks, range(1, 7), strict=True)
    ])


def _adoption(grades_path: Path, output: Path) -> int:
    grades = _materialize_adoption_grades(grades_path)
    result = evaluate_six_week_adoption(grades)
    digest = write_create_once(output, result)
    print(json.dumps({
        "prospective_gate_passed": result["prospective_gate_passed"],
        "output": str(output), "sha256": digest,
    }, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--smoke", type=_parse_slate)
    modes.add_argument("--historical-report", type=Path)
    modes.add_argument("--shadow", type=_parse_slate)
    modes.add_argument("--adoption-grades", type=Path)
    parser.add_argument("--smoke-receipt", type=Path)
    parser.add_argument("--historical-model", type=Path)
    parser.add_argument("--protocol-sha256")
    parser.add_argument("--historical-lease-receipt", type=Path)
    parser.add_argument("--historical-attempt-receipt", type=Path)
    parser.add_argument("--shadow-panel", action="append", default=[])
    parser.add_argument("--shadow-canonical-panel")
    parser.add_argument("--model-artifact", type=Path)
    parser.add_argument("--shadow-output", type=Path)
    parser.add_argument("--snapshot-id")
    parser.add_argument("--lock-at")
    parser.add_argument("--adoption-output", type=Path)
    args = parser.parse_args(argv)

    if args.adoption_grades:
        if not args.adoption_output:
            parser.error("--adoption-grades requires --adoption-output")
        return _adoption(args.adoption_grades, args.adoption_output)
    client = bigquery.Client(project=PROJECT)
    if args.smoke:
        if not args.smoke_receipt:
            parser.error("--smoke requires --smoke-receipt")
        return _smoke(client, args.smoke, args.smoke_receipt)
    if args.historical_report:
        if not all((
            args.historical_model, args.protocol_sha256,
            args.historical_lease_receipt, args.historical_attempt_receipt,
        )):
            parser.error(
                "historical mode requires --historical-model, --protocol-sha256, "
                "--historical-lease-receipt, and --historical-attempt-receipt"
            )
        return _historical(
            client, report_path=args.historical_report,
            model_path=args.historical_model,
            protocol_sha=args.protocol_sha256,
            lease_path=args.historical_lease_receipt,
            attempt_path=args.historical_attempt_receipt,
        )
    if not all((
        args.shadow_canonical_panel, args.model_artifact, args.shadow_output,
        args.snapshot_id, args.lock_at,
    )):
        parser.error("shadow mode lacks its panel/model/output/snapshot contract")
    return _shadow(
        client, slate=args.shadow, panels=args.shadow_panel,
        canonical_panel=args.shadow_canonical_panel,
        model_path=args.model_artifact, output=args.shadow_output,
        snapshot_id=args.snapshot_id, lock_at=args.lock_at,
    )


if __name__ == "__main__":
    raise SystemExit(main())
