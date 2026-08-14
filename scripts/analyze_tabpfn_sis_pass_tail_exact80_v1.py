#!/usr/bin/env python
"""Audit and score the frozen SIS pass-tail five-seed exact-80 pair."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys
import zlib

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research import tabpfn_sis_pass_tail_lineup_v1 as experiment  # noqa: E402
from nfl_dfs.research.served_tail_lineup import validate_candidate_panel  # noqa: E402


OUTPUT_CHUNK_PREFIX = "TABPFN_SIS_PASS_TAIL_EXACT80_V1_CHUNK="
OUTPUT_CHUNK_SIZE = 80_000
BOOTSTRAP_SEED = 8_142_026
BOOTSTRAP_RESAMPLES = 2_000


def encoded_report_chunks(report: dict) -> list[str]:
    raw = json.dumps(report, separators=(",", ":"), sort_keys=True).encode()
    encoded = base64.b64encode(zlib.compress(raw, level=9)).decode()
    return [encoded[index:index + OUTPUT_CHUNK_SIZE]
            for index in range(0, len(encoded), OUTPUT_CHUNK_SIZE)]


def _candidates(arm: str, replicate: int):
    panel = experiment.panel_id(arm, replicate)
    return query_df(f"""
        SELECT panel_run_id, code_sha, config_hash, lever_env, seeds,
               research_eligible, labels_complete, season, week, cand_ix,
               selected, selected_rank, players, actual_score, sim_mean,
               n_entries, n_sims, n_worlds, score_artifact_uri,
               score_artifact_sha256, tag, all_tags
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id=@panel AND season IN UNNEST(@seasons)
        ORDER BY season, week, cand_ix
    """, params={"panel": panel, "seasons": list(experiment.SEASONS)})


def _features(arm: str, replicate: int):
    return query_df(f"""
        SELECT * FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id=@panel AND season IN UNNEST(@seasons)
    """, params={
        "panel": experiment.panel_id(arm, replicate),
        "seasons": list(experiment.SEASONS),
    })


def _panel_failures(name: str, frame, expected_code_sha: str) -> list[str]:
    failures = validate_candidate_panel(
        name, frame, seasons=experiment.SEASONS, promoted=False,
        expected_code_sha=expected_code_sha, allow_season_config=True,
    )
    if frame.empty:
        return failures
    groups = frame.groupby(["season", "week"])
    if not frame.n_entries.eq(80).all() or not frame.n_sims.eq(10000).all() \
            or not frame.n_worlds.eq(10000).all():
        failures.append(f"{name} entry/world contract differs")
    if not groups.selected.sum().eq(80).all():
        failures.append(f"{name} exact-80 contract differs")
    artifacts = frame[[
        "season", "week", "score_artifact_uri", "score_artifact_sha256",
    ]].drop_duplicates()
    if len(artifacts) != 54 or artifacts.duplicated(["season", "week"]).any():
        failures.append(f"{name} artifact identity differs by slate")
    elif (~artifacts.score_artifact_uri.astype(str).str.startswith("gs://")).any() \
            or (~artifacts.score_artifact_sha256.astype(str).str.fullmatch(
                r"[0-9a-f]{64}")) .any():
        failures.append(f"{name} artifact provenance is invalid")
    return failures


def _score_report(frames: dict[tuple[str, int], object]) -> dict:
    metrics, weekly = {}, {}
    for key, frame in frames.items():
        label = f"{key[0]}-R{key[1]}"
        metrics[label], weekly[key] = experiment.arm_metrics(frame)
    paired, large = [], []
    for replicate in experiment.SEEDS:
        delta = weekly[("treatment", replicate)] - weekly[("control", replicate)]
        left = frames[("control", replicate)]
        right = frames[("treatment", replicate)]
        overlap = left[left.selected].merge(
            right[right.selected], on=["season", "week", "players"]
        ).groupby(["season", "week"]).size().reindex(delta.index, fill_value=0)
        paired.append({
            "replicate": f"R{replicate}",
            "treatment_weeks_better": int(delta.gt(0).sum()),
            "control_weeks_better": int(delta.lt(0).sum()),
            "ties": int(delta.eq(0).sum()),
            "mean_delta": float(delta.mean()),
            "mean_selected_overlap_of_80": float(overlap.mean()),
        })
        large.extend({
            "replicate": f"R{replicate}", "season": int(index[0]),
            "week": int(index[1]), "delta": float(value),
        } for index, value in delta.items() if abs(value) >= 10.0)
    aligned = np.column_stack([
        (weekly[("treatment", replicate)] - weekly[("control", replicate)]
         ).to_numpy(dtype=float)
        for replicate in experiment.SEEDS
    ])
    cluster_delta = aligned.mean(axis=1)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_RESAMPLES)
    for index in range(BOOTSTRAP_RESAMPLES):
        sample = rng.integers(0, len(cluster_delta), size=len(cluster_delta))
        draws[index] = cluster_delta[sample].mean()
    by_season = {}
    for season in experiment.SEASONS:
        item = {}
        for arm in ("control", "treatment"):
            values = []
            for replicate in experiment.SEEDS:
                values.append(weekly[(arm, replicate)].loc[season])
            combined = np.concatenate([value.to_numpy(dtype=float) for value in values])
            item[arm] = {
                "selected_tail": {
                    str(t): int((combined >= t).sum()) for t in experiment.TAILS
                },
                "selected_mean": float(combined.mean()),
                "selected_median": float(np.median(combined)),
            }
        by_season[str(season)] = item
    return {
        "metrics": metrics,
        "paired_seed_diagnostics": paired,
        "weekly_deltas_at_least_10": large,
        "by_season": by_season,
        "slate_clustered_bootstrap_diagnostic": {
            "clusters": int(len(cluster_delta)),
            "seed_replicates_averaged_within_cluster": len(experiment.SEEDS),
            "resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED,
            "mean_delta": float(cluster_delta.mean()),
            "ci95": [float(np.quantile(draws, 0.025)),
                     float(np.quantile(draws, 0.975))],
        },
        "decision": experiment.tail_first_decision(metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--phase-s-arm", choices=("control", "treatment"),
                        required=True)
    parser.add_argument("--phase-s-report-sha", required=True)
    parser.add_argument("--cache-validation-sha", required=True)
    parser.add_argument("--final-served-sha", required=True)
    args = parser.parse_args()
    frames, audits, failures = {}, {}, []
    for replicate in experiment.SEEDS:
        control = _candidates("control", replicate)
        treatment = _candidates("treatment", replicate)
        frames[("control", replicate)] = control
        frames[("treatment", replicate)] = treatment
        failures.extend(_panel_failures(
            f"control-R{replicate}", control, args.expected_code_sha))
        failures.extend(_panel_failures(
            f"treatment-R{replicate}", treatment, args.expected_code_sha))
        feature_audit = experiment.feature_invariance_audit(
            _features("control", replicate), _features("treatment", replicate))
        candidate_check = experiment.candidate_audit(control, treatment)
        audits[f"R{replicate}"] = {
            "features": feature_audit, "candidates": candidate_check,
        }
        failures.extend(experiment.mechanism_failures(
            control, treatment, feature_audit, candidate_check,
            expected_code_sha=args.expected_code_sha, replicate=replicate,
            phase_s_arm=args.phase_s_arm,
        ))
    report = {
        "protocol": "2026-08-14-sis-pass-tail-five-seed-exact80",
        "disposition": "valid" if not failures else "invalid",
        "mechanical_passes": not failures,
        "phase_s_arm": args.phase_s_arm,
        "expected_code_sha": args.expected_code_sha,
        "control_cache": experiment.CONTROL_TABLE,
        "treatment_cache": experiment.TREATMENT_TABLE,
        "control_schedules": experiment.CONTROL_SCHEDULES,
        "treatment_schedules": experiment.TREATMENT_SCHEDULES,
        "phase_s_report_sha256": args.phase_s_report_sha,
        "cache_validation_sha256": args.cache_validation_sha,
        "final_served_report_sha256": args.final_served_sha,
        "audits": audits, "failures": failures,
    }
    if not failures:
        report["result"] = _score_report(frames)
    chunks = encoded_report_chunks(report)
    for index, chunk in enumerate(chunks, start=1):
        print(f"{OUTPUT_CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}", flush=True)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
