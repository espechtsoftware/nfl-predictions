#!/usr/bin/env python
"""Mechanical audit and frozen multi-seed candidate/world exact-80 result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from google.cloud import storage  # noqa: E402

from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.multiseed_candidate_world import (  # noqa: E402
    ARMS, evaluate_factorial_slate, summarize_factorial,
    summarize_standalone_seed_books,
)
from nfl_dfs.research.portfolio_effective_rank import (  # noqa: E402
    decode_score_artifact,
)


OUTPUT_PREFIX = "MULTISEED_CANDIDATE_WORLD_JSON="
SEASONS = (2023, 2024, 2025)
BOOTSTRAP_SEED = 8_132_027
BOOTSTRAP_RESAMPLES = 2_000


def _panel(source_arm: str, replicate: int) -> str:
    return f"20260813-sis-asoe-{source_arm}-r{replicate}-v1"


def _download(uri: str) -> bytes:
    bucket, marker, path = str(uri).removeprefix("gs://").partition("/")
    if not marker or not bucket or not path:
        raise ValueError(f"invalid score artifact URI {uri!r}")
    return storage.Client().bucket(bucket).blob(path).download_as_bytes()


def _load(expected_code_sha: str, source_arm: str):
    frames = {}
    failures = []
    for replicate in range(5):
        panel = _panel(source_arm, replicate)
        frame = query_df(f"""
            SELECT panel_run_id, code_sha, season, week, cand_ix, players,
                   selected, selected_rank, actual_score, labels_complete,
                   n_entries, n_sims, n_worlds, score_artifact_uri,
                   score_artifact_sha256
            FROM `{settings.predictions}.replay_candidates_staging`
            WHERE panel_run_id=@panel AND season IN UNNEST(@seasons)
            ORDER BY season, week, cand_ix
            """, params={"panel": panel, "seasons": list(SEASONS)})
        label = f"R{replicate}"
        if frame.empty:
            failures.append(f"{label} candidate panel is empty")
            continue
        if not frame.panel_run_id.astype(str).eq(panel).all() or \
                not frame.code_sha.astype(str).eq(expected_code_sha).all():
            failures.append(f"{label} panel/code identity differs")
        groups = frame.groupby(["season", "week"])
        if len(groups) != 54 or set(frame.season.astype(int)) != set(SEASONS):
            failures.append(f"{label} slate/season set differs")
        if not frame.labels_complete.fillna(False).astype(bool).all() or \
                frame.actual_score.isna().any():
            failures.append(f"{label} labels are incomplete")
        if not frame.n_entries.eq(80).all() or not frame.n_sims.eq(10000).all() \
                or not frame.n_worlds.eq(10000).all():
            failures.append(f"{label} entry/world contract differs")
        if not groups.selected.sum().eq(80).all():
            failures.append(f"{label} does not select exact-80 on every slate")
        frames[replicate] = frame
    return frames, failures


def _artifact_for(group):
    uris = group.score_artifact_uri.fillna("").astype(str).unique()
    digests = group.score_artifact_sha256.fillna("").astype(str).unique()
    if len(uris) != 1 or len(digests) != 1 or not uris[0] or not digests[0]:
        raise ValueError("slate lacks one artifact identity")
    artifact = decode_score_artifact(_download(uris[0]), digests[0])
    if not {"player_ids", "player_draws"} <= set(artifact):
        raise ValueError("slate artifact lacks player worlds")
    return artifact


def _compact_slate(season: int, week: int, result: dict) -> dict:
    arms = {}
    incumbent = result["arms"]["C0W0"]["selected_best"]
    for arm in ARMS:
        value = result["arms"][arm]
        arms[arm] = {
            key: val for key, val in value.items()
            if key != "selected_rosters"
        }
        arms[arm]["selected_delta_c0w0"] = float(
            value["selected_best"] - incumbent
        )
    standalone = {
        seed: {
            key: val for key, val in value.items()
            if key != "selected_rosters"
        }
        for seed, value in result["standalone_seed_books"].items()
    }
    confirmation = {
        arm: {
            key: val for key, val in value.items()
            if key != "selected_rosters"
        }
        for arm, value in result["fixed_budget_confirmation"].items()
    }
    return {
        "season": season, "week": week,
        "novel_candidates_by_seed": result["novel_candidates_by_seed"],
        "standalone_seed_books": standalone,
        "fixed_budget_confirmation": confirmation,
        "arms": arms,
    }


def _bootstrap(slates: list[dict]) -> dict:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    output = {}
    incumbent = np.asarray([
        slate["arms"]["C0W0"]["selected_best"] for slate in slates
    ])
    for arm in ARMS[1:]:
        delta = np.asarray([
            slate["arms"][arm]["selected_best"] for slate in slates
        ]) - incumbent
        samples = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
        for index in range(BOOTSTRAP_RESAMPLES):
            chosen = rng.integers(0, len(delta), size=len(delta))
            samples[index] = float(delta[chosen].mean())
        output[arm] = {
            "mean_delta": float(delta.mean()),
            "ci95": [
                float(np.quantile(samples, 0.025)),
                float(np.quantile(samples, 0.975)),
            ],
        }
    return {
        "clusters": len(slates), "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED, "arms_vs_c0w0": output,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--source-arm", choices=("control", "treatment"),
                        required=True)
    args = parser.parse_args()
    frames, failures = _load(args.expected_code_sha, args.source_arm)
    slates = []
    full_results = []
    if not failures:
        for season in SEASONS:
            weeks = sorted(set(frames[0].loc[
                frames[0].season.astype(int).eq(season), "week"
            ].astype(int)))
            for week in weeks:
                try:
                    seed_rows, artifacts = {}, {}
                    for replicate in range(5):
                        frame = frames[replicate]
                        group = frame[
                            frame.season.astype(int).eq(season)
                            & frame.week.astype(int).eq(week)
                        ].copy()
                        seed_rows[replicate] = group
                        artifacts[replicate] = _artifact_for(group)
                    result = evaluate_factorial_slate(seed_rows, artifacts)
                    full_results.append(result)
                    slates.append(_compact_slate(season, week, result))
                except Exception as exc:
                    failures.append(f"{season}w{week} mechanical failure: {exc}")
                    break
            if failures:
                break
    report = {
        "protocol": "2026-08-13-multiseed-candidate-world-factorial",
        "source_arm": args.source_arm,
        "expected_code_sha": args.expected_code_sha,
        "mechanical_passes": not failures,
        "failures": failures,
    }
    if not failures:
        summary = summarize_factorial(full_results)
        summary["standalone_seed_noise_floor"] = \
            summarize_standalone_seed_books(full_results)
        summary["weekly_deltas_at_least_10"] = [
            {
                "season": slate["season"], "week": slate["week"],
                "arm": arm,
                "delta": slate["arms"][arm]["selected_delta_c0w0"],
            }
            for slate in slates for arm in ARMS[1:]
            if abs(slate["arms"][arm]["selected_delta_c0w0"]) >= 10.0
        ]
        summary["by_season"] = {
            str(season): summarize_factorial([
                result for result, slate in zip(full_results, slates)
                if slate["season"] == season
            ])["metrics"]
            for season in SEASONS
        }
        summary["slate_clustered_bootstrap_diagnostic"] = _bootstrap(slates)
        summary["slates"] = slates
        report["result"] = summary
    print(OUTPUT_PREFIX + json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
