#!/usr/bin/env python3
"""Capture native CBC failure evidence without persisting an ATLAS result."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

from google.cloud import bigquery, storage
import pulp


PROJECT = "nfl-predictions-503414"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
)
CODE_SHA = "60f296fdad769b30c0bb7334118698f156e462b9"
PROTOCOL_ID = "20260816-atlas-cbc-native-diagnostic-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    "atlas-cbc-native-diagnostic-runs/" + PROTOCOL_ID
)
ALLOWED_CELLS = {(2024, 15), (2024, 16)}
LAST_LOG = Path("/tmp/atlas-cbc-last.log")
MPS_PATH = Path.cwd() / "dfs-pulp.mps"
_BASE_CBC = pulp.PULP_CBC_CMD
_SOLVE_COUNT = 0
_ARTIFACT_PREFIX = ""


def _bytes_receipt(client: storage.Client, uri: str, raw: bytes) -> dict:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if not match:
        raise RuntimeError("ATLAS CBC diagnostic URI differs")
    blob = client.bucket(match.group(1)).blob(match.group(2))
    blob.upload_from_string(raw, if_generation_match=0)
    blob.reload()
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "size": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }


def _json_receipt(client: storage.Client, name: str, payload: dict) -> dict:
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return _bytes_receipt(client, f"{_ARTIFACT_PREFIX}/{name}", raw)


def _identity(status: str) -> dict:
    return {
        "version": "atlas-cbc-native-diagnostic-v1",
        "uses_realized_outcomes": False,
        "persists_lineups": False,
        "status": status,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": os.environ["ATLAS_CBC_DIAGNOSTIC_PROTOCOL_SHA256"],
        "diagnostic_source_sha256": os.environ[
            "ATLAS_CBC_DIAGNOSTIC_SOURCE_SHA256"
        ],
        "repair2_code_sha": CODE_SHA,
        "repair2_image": IMAGE,
        "execution": os.environ.get("CLOUD_RUN_EXECUTION", ""),
        "task_index": os.environ.get("CLOUD_RUN_TASK_INDEX", ""),
        "solve_count": _SOLVE_COUNT,
    }


def _persist_cbc_failure(exc: BaseException) -> None:
    client = storage.Client(project=PROJECT)
    artifacts = {}
    for name, path in (("cbc.log", LAST_LOG), ("problem.mps", MPS_PATH)):
        raw = path.read_bytes() if path.is_file() else b""
        artifacts[name] = _bytes_receipt(
            client, f"{_ARTIFACT_PREFIX}/{name}", raw,
        )
    payload = {
        **_identity("cbc-failure"),
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "artifacts": artifacts,
    }
    receipt = _json_receipt(client, "failure.json", payload)
    print("ATLAS_CBC_DIAGNOSTIC_FAILURE " + json.dumps(receipt, sort_keys=True))


class DiagnosticCBC(_BASE_CBC):
    """Unchanged packaged CBC solve with retained MPS and redirected output."""

    def __init__(self, *args, **kwargs):
        kwargs["msg"] = False
        kwargs["keepFiles"] = True
        kwargs["logPath"] = str(LAST_LOG)
        super().__init__(*args, **kwargs)

    def actualSolve(self, lp, **kwargs):  # noqa: N802 - PuLP API name
        global _SOLVE_COUNT
        _SOLVE_COUNT += 1
        try:
            return super().actualSolve(lp, **kwargs)
        except BaseException as exc:
            _persist_cbc_failure(exc)
            raise


def _load_books(runner, season: int, week: int):
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = runner._query(bq, runner.SOURCE_SQL, runner._source_params())
    players = runner._query(bq, runner.PLAYER_SQL, runner._player_params(season))
    sources = sources[
        sources.season.astype(int).eq(season)
        & sources.week.astype(int).eq(week)
    ].copy()
    catalog = players[players.week.astype(int).eq(week)].copy()
    if sources.empty or catalog.empty:
        raise RuntimeError("ATLAS CBC diagnostic source/catalog is empty")
    books = {}
    for seed, expected_panel in zip(
        runner.REGISTERED_SEEDS, runner.SOURCE_PANELS, strict=True,
    ):
        group = sources[
            sources.panel_run_id.astype(str).map(runner._canonical_panel).eq(
                expected_panel
            )
        ].copy()
        uris = group.score_artifact_uri.astype(str).unique()
        digests = group.score_artifact_sha256.astype(str).unique()
        if group.empty or len(uris) != 1 or len(digests) != 1:
            raise RuntimeError("ATLAS CBC diagnostic native source differs")
        artifact, _ = runner._download_artifact(gcs, uris[0], digests[0])
        books[seed] = runner._candidate_batch(group, artifact, catalog)
    return books


def run(season: int, week: int, artifact_prefix: str) -> None:
    global _ARTIFACT_PREFIX
    if (season, week) not in ALLOWED_CELLS or artifact_prefix != (
        f"{PREFIX}/season-{season}-week-{week}"
    ):
        raise RuntimeError("ATLAS CBC diagnostic cell/prefix differs")
    if os.environ.get("CODE_SHA") != CODE_SHA or \
            os.environ.get("ANALYSIS_IMAGE") != IMAGE:
        raise RuntimeError("ATLAS CBC diagnostic repair2 identity differs")
    for key in (
        "ATLAS_CBC_DIAGNOSTIC_PROTOCOL_SHA256",
        "ATLAS_CBC_DIAGNOSTIC_SOURCE_SHA256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", os.environ.get(key, "")):
            raise RuntimeError("ATLAS CBC diagnostic hash identity is required")
    _ARTIFACT_PREFIX = artifact_prefix

    scripts = str(Path.cwd() / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import run_atlas_matched_diversity_mvp as runner

    runner.validate_local_sources()
    pulp.PULP_CBC_CMD = DiagnosticCBC
    books = _load_books(runner, season, week)
    pricing = runner.price_native_interactions(books)
    nonboom = [
        lineup
        for seed in runner.REGISTERED_SEEDS
        for lineup in books[seed].candidates
        if str(lineup.tag) != "boom"
    ]
    seed = runner.REGISTERED_SEEDS[0]
    native = books[seed]
    positions = [str(row.get("pos", "")) for row in native.player_rows]
    bound = runner.roster_slot_upper_bound(native.row_draws, positions)
    world_order = runner.rank_worlds(bound, 40)
    stack = runner.StackRules(qb_stack_min=2, bring_back_min=1)
    env = {"MIN_LINEUP_SALARY": "49000"}
    exact = runner.solve_exact_worlds(
        native.player_rows, native.row_draws, world_order,
        stack=stack, env=env,
    )
    clusters = runner.build_structural_clusters(world_order, exact)
    runner.enumerate_matched_diversity_lineups(
        player_rows=native.player_rows,
        row_draws=native.row_draws,
        clusters=clusters,
        exact_worlds=exact,
        interaction_weights=pricing["weights_by_source"][seed],
        nonboom_lineups=nonboom,
        prior_atlas_rosters=set(),
        stack=stack,
        env=env,
    )
    client = storage.Client(project=PROJECT)
    receipt = _json_receipt(client, "success.json", _identity("r0-complete"))
    print("ATLAS_CBC_DIAGNOSTIC_SUCCESS " + json.dumps(receipt, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--artifact-prefix", required=True)
    args = parser.parse_args()
    run(args.season, args.week, args.artifact_prefix)


if __name__ == "__main__":
    main()
