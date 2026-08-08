"""Prove an instrumentation-only replay exactly reproduces its reference.

The reference must already be accepted/promoted.  The candidate is read from
staging, so a failed reproduction can never become a research source.  Full
candidate-by-world artifacts are compared as arrays in addition to warehouse
summaries; matching a few score thresholds is not treated as exact parity.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402


CANDIDATE_COLUMNS = [
    "labels_complete", "season", "week", "cand_ix", "tag", "all_tags",
    "selected", "selected_rank", "salary", "p_line", "sim_mean", "sim_sd",
    "sim_q50", "sim_q90", "sim_q99", "sim_rank_p_line", "actual_score",
    "actual_rank", "tail_line", "n_entries", "n_sims", "n_locks",
    "n_theses", "players", "n_worlds", "bitorder", "clear_bits",
    "clear_bits_187", "clear_bits_194", "clear_bits_200",
]
CANDIDATE_COMPARE_FIELDS = [
    field for field in CANDIDATE_COLUMNS
    if field not in {"season", "week", "cand_ix", "players"}
]
CANDIDATE_TOLERANCES = {
    # These are float32 reductions over an otherwise byte-identical world
    # row.  Moving the row within the candidate matrix can change SIMD
    # accumulation at the last few bits; the full array comparison below is
    # the stronger invariant.
    "sim_mean": 1e-4,
    "sim_sd": 1e-4,
    "sim_q50": 1e-4,
    "sim_q90": 1e-4,
    "sim_q99": 1e-4,
}

# The ensemble audit adds model_ensemble_size, model_member_spec and dynamic
# ensemble_point_* columns.  Everything that existed before that audit must
# remain identical in an instrumentation-only rebuild.
FEATURE_FIELDS = [
    "season", "week", "id", "gsis_id", "name", "pos", "team", "opp",
    "game_id", "salary", "proj", "proj_tourney", "own_est",
    "mean_projection", "proj_p10", "proj_p50", "proj_p90", "proj_std",
    "target_share_last", "carry_share_last", "snap_share_last",
    "target_share_jump", "carry_share_jump", "snap_share_jump",
    "target_share_l4", "carry_share_l4", "snap_share_l4", "dk_points_l4",
    "implied_team_total", "spread", "game_total", "is_cold_start",
    "depth_rank", "depth_rank_delta", "team_vacated_target_share",
    "team_vacated_carry_share", "salary_delta_wow", "games_played_prior",
    "actual", "consensus_div", "market_points", "model_points_pre",
    "feature_missing",
]
FEATURE_COMPARE_FIELDS = [
    field for field in FEATURE_FIELDS
    if field not in {"season", "week", "id"}
]
FEATURE_TOLERANCES = {
    field: 1e-8 for field in FEATURE_COMPARE_FIELDS
    if field not in {
        "gsis_id", "name", "pos", "team", "opp", "game_id",
        "is_cold_start", "feature_missing",
    }
}


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def _candidates(panel: str, promoted: bool) -> pd.DataFrame:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    fields = ", ".join(CANDIDATE_COLUMNS)
    return query_df(f"""
        SELECT {fields}, score_artifact_uri, score_artifact_sha256
        FROM `{settings.predictions}.{table}`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _features(panel: str, promoted: bool) -> pd.DataFrame:
    eligibility = "AND research_eligible" if promoted else ""
    fields = ", ".join(FEATURE_FIELDS)
    return query_df(f"""
        SELECT {fields}
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _frame_report(source: pd.DataFrame, candidate: pd.DataFrame,
                  keys: list[str], fields: list[str],
                  tolerances: dict[str, float] | None = None,
                  ) -> tuple[dict, list[str]]:
    failures: list[str] = []
    if source.empty:
        failures.append("reference frame is empty")
    if candidate.empty:
        failures.append("candidate frame is empty")
    for name, frame in (("reference", source), ("candidate", candidate)):
        missing = set(keys + fields) - set(frame.columns)
        if missing:
            failures.append(f"{name} frame missing {sorted(missing)}")
        if not missing and frame.duplicated(keys).any():
            failures.append(f"{name} frame has duplicate keys")
    if failures:
        return {}, failures

    compare_fields = [field for field in fields if field not in keys]
    left = source.set_index(keys)[compare_fields].sort_index()
    right = candidate.set_index(keys)[compare_fields].sort_index()
    missing_reference = right.index.difference(left.index)
    missing_candidate = left.index.difference(right.index)
    if len(missing_reference):
        failures.append(
            f"candidate has {len(missing_reference)} keys absent from reference")
    if len(missing_candidate):
        failures.append(
            f"reference has {len(missing_candidate)} keys absent from candidate")
    common = left.index.intersection(right.index)
    left = left.loc[common]
    right = right.loc[common]
    mismatch_counts: dict[str, int] = {}
    max_abs_deltas: dict[str, float] = {}
    for col in compare_fields:
        both_null = left[col].isna() & right[col].isna()
        tolerance = (tolerances or {}).get(col)
        if tolerance is not None:
            left_numeric = pd.to_numeric(left[col], errors="coerce")
            right_numeric = pd.to_numeric(right[col], errors="coerce")
            delta = (left_numeric - right_numeric).abs()
            equal = both_null | (
                left_numeric.notna() & right_numeric.notna()
                & delta.le(tolerance))
            max_abs_deltas[col] = (
                float(delta.max()) if delta.notna().any() else 0.0)
        else:
            equal = left[col].eq(right[col]) | both_null
        count = int((~equal).sum())
        mismatch_counts[col] = count
        if count:
            failures.append(f"{col} differs in {count} rows")
    return {
        "reference_rows": int(len(source)),
        "candidate_rows": int(len(candidate)),
        "common_rows": int(len(common)),
        "reference_only_keys": int(len(missing_candidate)),
        "candidate_only_keys": int(len(missing_reference)),
        "mismatch_counts": mismatch_counts,
        "max_abs_deltas": max_abs_deltas,
    }, failures


def _load_artifact(uri: str) -> dict[str, np.ndarray]:
    from google.cloud import storage

    bucket, separator, path = uri.replace("gs://", "", 1).partition("/")
    if not separator or not bucket or not path:
        raise ValueError(f"invalid artifact URI {uri!r}")
    payload = storage.Client().bucket(bucket).blob(path).download_as_bytes()
    with np.load(io.BytesIO(payload)) as archive:
        return {name: archive[name].copy() for name in archive.files}


def _array_report(source: dict[str, np.ndarray],
                  candidate: dict[str, np.ndarray]) -> tuple[dict, list[str]]:
    failures: list[str] = []
    source_names = set(source)
    candidate_names = set(candidate)
    if source_names != candidate_names:
        failures.append("artifact members differ")
    reports: dict[str, dict] = {}
    for name in sorted(source_names & candidate_names):
        left = source[name]
        right = candidate[name]
        same_shape = left.shape == right.shape
        exact = same_shape and np.array_equal(left, right, equal_nan=True)
        entry = {
            "reference_shape": list(left.shape),
            "candidate_shape": list(right.shape),
            "exact": bool(exact),
        }
        if same_shape and np.issubdtype(left.dtype, np.number):
            delta = np.abs(left.astype(float) - right.astype(float))
            entry["max_abs_delta"] = (
                float(np.nanmax(delta)) if delta.size else 0.0)
        reports[name] = entry
        if not exact:
            failures.append(f"artifact member {name} differs")
    return reports, failures


def _align_artifacts_by_roster(
        source_rows: pd.DataFrame, candidate_rows: pd.DataFrame,
        source: dict[str, np.ndarray], candidate: dict[str, np.ndarray],
        ) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], int, list[str]]:
    """Put score matrices in canonical roster order, not ephemeral cand_ix."""
    failures: list[str] = []
    for name, rows, arrays in (
            ("reference", source_rows, source),
            ("candidate", candidate_rows, candidate)):
        if rows.players.duplicated().any():
            failures.append(f"{name} artifact rows have duplicate rosters")
        if not {"cand_ix", "totals", "tail_line"} <= set(arrays):
            failures.append(f"{name} artifact is missing required members")
            continue
        expected_ix = np.arange(len(rows), dtype=np.int64)
        if not np.array_equal(
                np.asarray(arrays["cand_ix"], dtype=np.int64), expected_ix):
            failures.append(f"{name} artifact cand_ix is not canonical")
        if arrays["totals"].shape[0] != len(rows):
            failures.append(f"{name} artifact row count differs from warehouse")
    source_rosters = set(source_rows.players)
    candidate_rosters = set(candidate_rows.players)
    if source_rosters != candidate_rosters:
        failures.append("artifact roster universes differ")
    if failures:
        return {}, {}, 0, failures

    rosters = sorted(source_rosters)
    source_ix = (source_rows.set_index("players").loc[rosters, "cand_ix"]
                 .astype(int).to_numpy())
    candidate_ix = (candidate_rows.set_index("players").loc[rosters, "cand_ix"]
                    .astype(int).to_numpy())
    moved = int((source_ix != candidate_ix).sum())
    return (
        {"totals": source["totals"][source_ix],
         "tail_line": source["tail_line"]},
        {"totals": candidate["totals"][candidate_ix],
         "tail_line": candidate["tail_line"]},
        moved,
        [],
    )


def _artifact_report(source: pd.DataFrame,
                     candidate: pd.DataFrame) -> tuple[dict, list[str]]:
    failures: list[str] = []
    report: dict[str, dict] = {}
    keys = ["season", "week"]
    source_slates = {tuple(map(int, key)): group
                     for key, group in source.groupby(keys)}
    candidate_slates = {tuple(map(int, key)): group
                        for key, group in candidate.groupby(keys)}
    if set(source_slates) != set(candidate_slates):
        failures.append("artifact slate universes differ")
    for key in sorted(set(source_slates) & set(candidate_slates)):
        source_uris = source_slates[key].score_artifact_uri.dropna().unique()
        candidate_uris = candidate_slates[key].score_artifact_uri.dropna().unique()
        label = f"{key[0]}-w{key[1]}"
        if len(source_uris) != 1 or len(candidate_uris) != 1:
            failures.append(f"{label} does not have one artifact per arm")
            continue
        try:
            source_arrays = _load_artifact(str(source_uris[0]))
            candidate_arrays = _load_artifact(str(candidate_uris[0]))
            aligned_source, aligned_candidate, moved, alignment_failures = (
                _align_artifacts_by_roster(
                    source_slates[key], candidate_slates[key],
                    source_arrays, candidate_arrays))
            if alignment_failures:
                failures.extend(
                    f"{label}: {failure}" for failure in alignment_failures)
                continue
            arrays, array_failures = _array_report(
                aligned_source, aligned_candidate)
        except Exception as exc:
            failures.append(f"{label} artifact load failed: {exc}")
            continue
        report[label] = {
            "candidate_order_moved_rows": moved,
            "arrays": arrays,
        }
        failures.extend(f"{label}: {failure}" for failure in array_failures)
    return report, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", help="accepted/promoted reference panel")
    parser.add_argument("candidate", help="instrumented staging panel")
    parser.add_argument("--output")
    args = parser.parse_args()

    source_candidates = _candidates(args.reference, promoted=True)
    rebuilt_candidates = _candidates(args.candidate, promoted=False)
    candidate_report, candidate_failures = _frame_report(
        source_candidates, rebuilt_candidates,
        ["season", "week", "players"], CANDIDATE_COMPARE_FIELDS,
        CANDIDATE_TOLERANCES)
    feature_report, feature_failures = _frame_report(
        _features(args.reference, promoted=True),
        _features(args.candidate, promoted=False),
        ["season", "week", "id"], FEATURE_COMPARE_FIELDS,
        FEATURE_TOLERANCES)
    artifact_report, artifact_failures = _artifact_report(
        source_candidates, rebuilt_candidates)
    failures = candidate_failures + feature_failures + artifact_failures
    report = {
        "reference": args.reference,
        "candidate": args.candidate,
        "candidate_parity": candidate_report,
        "feature_parity": feature_report,
        "artifacts": artifact_report,
        "passes": not failures,
        "failures": failures,
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    # Cloud Logging may split a pretty-printed document into hundreds of
    # entries sharing one timestamp, whose retrieval order is not stable.
    # Emit one sub-256KB compact record atomically; keep pretty output when a
    # caller supplies a durable file destination.
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    if args.output:
        Path(args.output).write_text(payload + "\n")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
