#!/usr/bin/env python3
"""Capture CBC child and cgroup evidence without persisting ATLAS results."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import signal
import sys

from google.cloud import bigquery, storage
import pulp
import pulp.apis.coin_api as coin_api


PROJECT = "nfl-predictions-503414"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
)
CODE_SHA = "60f296fdad769b30c0bb7334118698f156e462b9"
PROTOCOL_ID = "20260816-atlas-cbc-resource-diagnostic-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    "atlas-cbc-resource-diagnostic-runs/" + PROTOCOL_ID
)
ALLOWED_CELLS = {(2024, 7), (2024, 15), (2024, 16)}
LAST_LOG = Path("/tmp/atlas-cbc-resource-last.log")
MPS_PATH = Path.cwd() / "dfs-pulp.mps"
_BASE_CBC = pulp.PULP_CBC_CMD
_ORIGINAL_POPEN = coin_api.subprocess.Popen
_SOLVE_COUNT = 0
_CHILD_PROCESS_COUNT = 0
_FIRST_CGROUP_BEFORE: dict | None = None
_LAST_CHILD: dict | None = None
_OOM_KILL_DELTA_TOTAL = 0
_MAX_PEAK_BYTES: int | None = None
_MAX_PEAK_RATIO: float | None = None
_ARTIFACT_PREFIX = ""


def _parse_int(value: str) -> int | str | None:
    value = value.strip()
    if value == "max":
        return value
    try:
        return int(value)
    except ValueError:
        return None


def _read_pairs(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                values[parts[0]] = int(parts[1])
            except ValueError:
                pass
    return values


def _current_cgroup_dir() -> Path | None:
    proc = Path("/proc/self/cgroup")
    if proc.is_file():
        for line in proc.read_text(encoding="utf-8").splitlines():
            if line.startswith("0::"):
                relative = line.split("::", 1)[1].lstrip("/")
                candidate = Path("/sys/fs/cgroup") / relative
                if (candidate / "memory.events").is_file():
                    return candidate
    root = Path("/sys/fs/cgroup")
    if (root / "memory.events").is_file():
        return root
    return None


def _read_cgroup_snapshot() -> dict:
    root = _current_cgroup_dir()
    if root is not None:
        snapshot = {
            "version": 2,
            "path": str(root),
            "events": _read_pairs(root / "memory.events"),
        }
        for name in ("memory.current", "memory.peak", "memory.max"):
            path = root / name
            snapshot[name.replace(".", "_")] = (
                _parse_int(path.read_text(encoding="utf-8"))
                if path.is_file() else None
            )
        snapshot["available"] = bool(snapshot["events"]) and all(
            snapshot.get(key) is not None
            for key in ("memory_current", "memory_peak", "memory_max")
        )
        return snapshot

    root = Path("/sys/fs/cgroup/memory")
    snapshot = {
        "version": 1,
        "path": str(root),
        "events": {
            "failcnt": int((root / "memory.failcnt").read_text().strip())
            if (root / "memory.failcnt").is_file() else 0,
        },
        "memory_current": _parse_int(
            (root / "memory.usage_in_bytes").read_text()
        ) if (root / "memory.usage_in_bytes").is_file() else None,
        "memory_peak": _parse_int(
            (root / "memory.max_usage_in_bytes").read_text()
        ) if (root / "memory.max_usage_in_bytes").is_file() else None,
        "memory_max": _parse_int(
            (root / "memory.limit_in_bytes").read_text()
        ) if (root / "memory.limit_in_bytes").is_file() else None,
    }
    snapshot["available"] = all(
        snapshot.get(key) is not None
        for key in ("memory_current", "memory_peak", "memory_max")
    )
    return snapshot


def _signal_name(returncode: int) -> str | None:
    if returncode >= 0:
        return None
    try:
        return signal.Signals(-returncode).name
    except ValueError:
        return f"SIGNAL_{-returncode}"


def _update_resource_evidence(before: dict, after: dict, returncode: int) -> None:
    global _FIRST_CGROUP_BEFORE, _LAST_CHILD, _OOM_KILL_DELTA_TOTAL
    global _MAX_PEAK_BYTES, _MAX_PEAK_RATIO
    if _FIRST_CGROUP_BEFORE is None:
        _FIRST_CGROUP_BEFORE = before
    before_oom = int(before.get("events", {}).get("oom_kill", 0))
    after_oom = int(after.get("events", {}).get("oom_kill", 0))
    oom_delta = max(0, after_oom - before_oom)
    _OOM_KILL_DELTA_TOTAL += oom_delta
    peak = after.get("memory_peak")
    limit = after.get("memory_max")
    ratio = None
    if isinstance(peak, int):
        _MAX_PEAK_BYTES = peak if _MAX_PEAK_BYTES is None else max(
            _MAX_PEAK_BYTES, peak
        )
    if isinstance(peak, int) and isinstance(limit, int) and limit > 0:
        ratio = float(peak / limit)
        if math.isfinite(ratio):
            _MAX_PEAK_RATIO = ratio if _MAX_PEAK_RATIO is None else max(
                _MAX_PEAK_RATIO, ratio
            )
    _LAST_CHILD = {
        "returncode": int(returncode),
        "terminating_signal": _signal_name(int(returncode)),
        "cgroup_before": before,
        "cgroup_after": after,
        "oom_kill_delta": oom_delta,
        "memory_peak_ratio": ratio,
    }


class _TrackedProcess:
    def __init__(self, *args, **kwargs):
        global _CHILD_PROCESS_COUNT
        _CHILD_PROCESS_COUNT += 1
        self._before = _read_cgroup_snapshot()
        self._process = _ORIGINAL_POPEN(*args, **kwargs)

    def wait(self, *args, **kwargs):
        returncode = self._process.wait(*args, **kwargs)
        _update_resource_evidence(
            self._before, _read_cgroup_snapshot(), int(returncode)
        )
        return returncode

    def __getattr__(self, name):
        return getattr(self._process, name)


def _tracking_popen(*args, **kwargs):
    return _TrackedProcess(*args, **kwargs)


def _resource_summary() -> dict:
    return {
        "child_process_count": _CHILD_PROCESS_COUNT,
        "first_cgroup_before": _FIRST_CGROUP_BEFORE,
        "last_child": _LAST_CHILD,
        "oom_kill_delta_total": _OOM_KILL_DELTA_TOTAL,
        "maximum_memory_peak_bytes": _MAX_PEAK_BYTES,
        "maximum_memory_peak_ratio": _MAX_PEAK_RATIO,
    }


def _bytes_receipt(client: storage.Client, uri: str, raw: bytes) -> dict:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if not match:
        raise RuntimeError("ATLAS CBC resource diagnostic URI differs")
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
        "version": "atlas-cbc-resource-diagnostic-v1",
        "uses_realized_outcomes": False,
        "persists_lineups": False,
        "status": status,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": os.environ["ATLAS_CBC_RESOURCE_PROTOCOL_SHA256"],
        "diagnostic_source_sha256": os.environ[
            "ATLAS_CBC_RESOURCE_SOURCE_SHA256"
        ],
        "repair2_code_sha": CODE_SHA,
        "repair2_image": IMAGE,
        "execution": os.environ.get("CLOUD_RUN_EXECUTION", ""),
        "task_index": os.environ.get("CLOUD_RUN_TASK_INDEX", ""),
        "solve_count": _SOLVE_COUNT,
        "resource_evidence": _resource_summary(),
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
    print("ATLAS_CBC_RESOURCE_FAILURE " + json.dumps(receipt, sort_keys=True))


class DiagnosticCBC(_BASE_CBC):
    """Unchanged CBC solve with native log and child/cgroup observation."""

    def __init__(self, *args, **kwargs):
        kwargs["msg"] = False
        kwargs["keepFiles"] = True
        kwargs["logPath"] = str(LAST_LOG)
        super().__init__(*args, **kwargs)

    def actualSolve(self, lp, **kwargs):  # noqa: N802 - PuLP API name
        global _SOLVE_COUNT
        _SOLVE_COUNT += 1
        coin_api.subprocess.Popen = _tracking_popen
        try:
            return super().actualSolve(lp, **kwargs)
        except BaseException as exc:
            _persist_cbc_failure(exc)
            raise
        finally:
            coin_api.subprocess.Popen = _ORIGINAL_POPEN


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
        raise RuntimeError("ATLAS CBC resource diagnostic source/catalog is empty")
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
            raise RuntimeError("ATLAS CBC resource diagnostic native source differs")
        artifact, _ = runner._download_artifact(gcs, uris[0], digests[0])
        books[seed] = runner._candidate_batch(group, artifact, catalog)
    return books


def run(season: int, week: int, artifact_prefix: str) -> None:
    global _ARTIFACT_PREFIX
    if (season, week) not in ALLOWED_CELLS or artifact_prefix != (
        f"{PREFIX}/season-{season}-week-{week}"
    ):
        raise RuntimeError("ATLAS CBC resource diagnostic cell/prefix differs")
    if os.environ.get("CODE_SHA") != CODE_SHA or \
            os.environ.get("ANALYSIS_IMAGE") != IMAGE:
        raise RuntimeError("ATLAS CBC resource diagnostic repair2 identity differs")
    for key in (
        "ATLAS_CBC_RESOURCE_PROTOCOL_SHA256",
        "ATLAS_CBC_RESOURCE_SOURCE_SHA256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", os.environ.get(key, "")):
            raise RuntimeError("ATLAS CBC resource diagnostic hash is required")
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
    env = {"MIN_LINEUP_SALARY": "49000", "MIN_GAMES": "2"}
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
    print("ATLAS_CBC_RESOURCE_SUCCESS " + json.dumps(receipt, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--artifact-prefix", required=True)
    args = parser.parse_args()
    run(args.season, args.week, args.artifact_prefix)


if __name__ == "__main__":
    main()
