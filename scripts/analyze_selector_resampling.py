#!/usr/bin/env python
"""Run the frozen, score-free selector world-resampling diagnostic."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from google.cloud import storage  # noqa: E402

from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.portfolio_effective_rank import (  # noqa: E402
    decode_score_artifact,
)
from nfl_dfs.research.selector_resampling import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    ENTRY_COUNT,
    LINE,
    WORLD_COUNT,
    analyze_selector_resampling,
    summarize_selector_resampling,
)


OUTPUT_PREFIX = "SELECTOR_RESAMPLING_JSON="
PROTOCOL = "2026-08-14-selector-resampling-score-free-v1"
SOURCE_PANEL = "20260813-sis-asoe-treatment-r0-v1"
SEASONS = (2023, 2024, 2025)
EXPECTED_SLATES = 54


def _split_gcs_uri(uri: str) -> tuple[str, str]:
    bucket, marker, path = str(uri).removeprefix("gs://").partition("/")
    if not marker or not bucket or not path:
        raise ValueError(f"invalid GCS URI {uri!r}")
    return bucket, path


def _download(uri: str) -> bytes:
    bucket, path = _split_gcs_uri(uri)
    return storage.Client().bucket(bucket).blob(path).download_as_bytes()


def _load(expected_code_sha: str):
    # Deliberately score-free: realized outcomes, players, standings and
    # payouts are absent from this query.
    return query_df(f"""
        SELECT panel_run_id, code_sha, season, week, cand_ix, selected,
               selected_rank, n_entries, n_sims, n_worlds, tail_line,
               score_artifact_uri, score_artifact_sha256
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id=@panel AND season IN UNNEST(@seasons)
        ORDER BY season, week, cand_ix
        """, params={
            "panel": SOURCE_PANEL,
            "seasons": list(SEASONS),
        })


def _artifact_for(group) -> tuple[np.ndarray, str, str]:
    uris = group.score_artifact_uri.fillna("").astype(str).unique()
    digests = group.score_artifact_sha256.fillna("").astype(str).unique()
    if len(uris) != 1 or len(digests) != 1 or not uris[0] or not digests[0]:
        raise ValueError("slate lacks one score-artifact identity")
    if not uris[0].startswith("gs://") or len(digests[0]) != 64:
        raise ValueError("score-artifact provenance is invalid")
    artifact = decode_score_artifact(_download(uris[0]), digests[0])
    totals = np.asarray(artifact["totals"], dtype=np.float32)
    line = np.asarray(artifact["tail_line"], dtype=float).reshape(-1)
    if line.size != 1 or not np.isclose(line[0], LINE, rtol=0.0, atol=1e-9):
        raise ValueError("score artifact tail line differs")
    expected_ix = group.cand_ix.astype(int).to_numpy()
    if not np.array_equal(expected_ix, np.arange(len(group))):
        raise ValueError("warehouse candidate indices are not canonical")
    if totals.shape != (len(group), WORLD_COUNT):
        raise ValueError("score artifact candidate/world shape differs")
    return totals, uris[0], digests[0]


def _upload_frequencies(uri: str, payload: dict) -> dict:
    encoded = json.dumps(
        payload, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    compressed = gzip.compress(encoded, compresslevel=9, mtime=0)
    digest = hashlib.sha256(compressed).hexdigest()
    bucket, path = _split_gcs_uri(uri)
    blob = storage.Client().bucket(bucket).blob(path)
    blob.metadata = {
        "sha256": digest,
        "protocol": PROTOCOL,
        "source_panel": SOURCE_PANEL,
    }
    blob.upload_from_string(
        compressed,
        content_type="application/gzip",
        if_generation_match=0,
    )
    return {
        "uri": uri,
        "sha256": digest,
        "compressed_bytes": len(compressed),
        "uncompressed_bytes": len(encoded),
        "content_encoding": "gzip",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--frequency-artifact-uri", required=True)
    args = parser.parse_args()

    failures: list[str] = []
    rows = _load(args.expected_code_sha)
    if rows.empty:
        failures.append("source candidate panel is empty")
    else:
        if not rows.panel_run_id.astype(str).eq(SOURCE_PANEL).all():
            failures.append("source panel identity differs")
        if not rows.code_sha.astype(str).eq(args.expected_code_sha).all():
            failures.append("source code identity differs")
        if rows.duplicated(["season", "week", "cand_ix"]).any():
            failures.append("candidate indices repeat")
        groups = rows.groupby(["season", "week"], sort=True)
        if len(groups) != EXPECTED_SLATES or \
                set(rows.season.astype(int)) != set(SEASONS):
            failures.append("source slate/season set differs")
        if not rows.n_entries.eq(ENTRY_COUNT).all() or \
                not rows.n_sims.eq(WORLD_COUNT).all() or \
                not rows.n_worlds.eq(WORLD_COUNT).all() or \
                not np.isclose(
                    rows.tail_line.astype(float), LINE,
                    rtol=0.0, atol=1e-9,
                ).all():
            failures.append("entry/world/line contract differs")
        if not groups.selected.sum().eq(ENTRY_COUNT).all():
            failures.append("source panel is not exact-80")

    slates: list[dict] = []
    artifact_sources: list[dict] = []
    if not failures:
        for (season, week), group in rows.groupby(
                ["season", "week"], sort=True):
            label = f"{int(season)}w{int(week)}"
            try:
                group = group.sort_values("cand_ix", kind="stable").copy()
                selected = group[
                    group.selected.fillna(False).astype(bool)
                ].sort_values("selected_rank", kind="stable")
                ranks = selected.selected_rank.astype(int).tolist()
                if ranks != list(range(ENTRY_COUNT)):
                    raise ValueError("selected ranks are not canonical 0-based")
                expected = selected.cand_ix.astype(int).tolist()
                totals, source_uri, source_sha = _artifact_for(group)
                result = analyze_selector_resampling(
                    totals,
                    expected,
                    season=int(season),
                    week=int(week),
                )
                slates.append(result)
                artifact_sources.append({
                    "season": int(season),
                    "week": int(week),
                    "score_artifact_uri": source_uri,
                    "score_artifact_sha256": source_sha,
                })
            except Exception as exc:
                failures.append(f"{label} mechanical failure: {exc}")
                break

    report = {
        "protocol": PROTOCOL,
        "source_panel": SOURCE_PANEL,
        "expected_code_sha": args.expected_code_sha,
        "reads_realized_outcomes": False,
        "mechanical_passes": not failures,
        "failures": failures,
    }
    if not failures:
        frequency_payload = {
            "protocol": PROTOCOL,
            "source_panel": SOURCE_PANEL,
            "expected_code_sha": args.expected_code_sha,
            "reads_realized_outcomes": False,
            "slates": [
                {
                    "season": row["season"],
                    "week": row["week"],
                    "candidate_count": row["candidate_count"],
                    "candidate_frequencies": row["candidate_frequencies"],
                }
                for row in slates
            ],
        }
        summary = summarize_selector_resampling(slates)
        summary["source_score_artifacts"] = artifact_sources
        summary["bootstrap_resamples"] = BOOTSTRAP_RESAMPLES
        summary["world_count"] = WORLD_COUNT
        summary["entry_count"] = ENTRY_COUNT
        summary["line"] = LINE
        report["result"] = summary
        report["frequency_artifact"] = _upload_frequencies(
            args.frequency_artifact_uri, frequency_payload,
        )

    print(OUTPUT_PREFIX + json.dumps(
        report, separators=(",", ":"), sort_keys=True,
    ))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
