"""Canonical run context (emerging-technologies plan §4.1, 2026-08-05).

WHY: every replay arm, live build, shadow run, and calibration job so
far has carried its identity informally — a seed here, an env dump
there, a 12-hex run_id minted deep inside candidate persistence. That
made A/B forensics (stale image? wrong code path? rebuilt table?)
manual archaeology. This module is the one immutable identity record:
code SHA + dirty flag, a stable hash of the effective configuration,
data lineage, slate identifiers, model versions, the master seed plus
NAMED per-stream RNG seeds (plan §3.1: targets, carries, yardage,
turnovers, touchdowns each get an independent stream so toggling one
lever can never shift a sibling's draw order), and timing/status.

Offline by design: no BQ calls here. `to_bq_row()` returns a flat,
JSON-safe dict; persistence is the caller's problem (and must never
block the build — plan §3.4).
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import numpy as np

log = logging.getLogger(__name__)

RUN_TYPES = ("replay", "live_shadow", "live_build", "calibration",
             "data_build")

# Named RNG streams (plan §3.1/§4.1). Component draws each own a stream
# so an experiment that adds or removes draws in one channel (the
# 2026-08-05 TD-ledger draw-order regression) cannot shift any other
# channel's sequence.
DEFAULT_RNG_STREAMS = (
    "game_factor", "targets", "carries", "yardage", "turnovers",
    "touchdowns", "kicking", "dst", "ownership", "field",
)


def stable_hash(obj: Any) -> str:
    """sha256 of the canonical JSON encoding — insensitive to dict
    ordering, so the same effective config always hashes the same."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def stream_seed(master_seed: int, name: str) -> int:
    """Deterministic, platform-independent seed for a named stream.

    sha256-derived rather than SeedSequence.spawn so the mapping is a
    pure function of (master_seed, name): adding a new stream name can
    never renumber existing streams.
    """
    digest = hashlib.sha256(f"{master_seed}:{name}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def code_state(repo_dir: str | None = None) -> tuple[str, bool]:
    """(code_sha, dirty) via git; ("unknown", False) when git is
    unavailable — a run context must never crash the run it labels."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir,
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_dir,
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        return sha, bool(porcelain)
    except Exception:
        log.warning("git state unavailable; code_sha=unknown")
        return "unknown", False


@dataclass
class RunContext:
    """One immutable identity record per research or production run."""

    run_id: str
    run_type: str
    parent_run_id: str | None = None
    code_sha: str = "unknown"
    code_dirty: bool = False
    config_hash: str = ""
    config_json: str = "{}"
    data_snapshot_id: str | None = None
    max_source_timestamp: str | None = None
    season: int | None = None
    week: int | None = None
    slate_id: int | None = None
    draft_group_id: int | None = None
    contest_id: str | None = None
    model_versions: dict[str, str] = field(default_factory=dict)
    seed: int = 0
    rng_stream_seeds: dict[str, int] = field(default_factory=dict)
    n_sims: int | None = None
    n_candidates: int | None = None
    n_entries: int | None = None
    tail_threshold: float | None = None
    started_at: str = ""
    completed_at: str | None = None
    status: str = "running"
    failure_reason: str | None = None

    @classmethod
    def new(
        cls,
        run_type: str,
        *,
        config: Mapping[str, Any] | None = None,
        seed: int = 0,
        rng_streams: Iterable[str] = DEFAULT_RNG_STREAMS,
        repo_dir: str | None = None,
        parent_run_id: str | None = None,
        **fields: Any,
    ) -> "RunContext":
        if run_type not in RUN_TYPES:
            raise ValueError(
                f"run_type {run_type!r} not in {RUN_TYPES}")
        sha, dirty = code_state(repo_dir)
        cfg = dict(config or {})
        return cls(
            run_id=uuid.uuid4().hex,
            run_type=run_type,
            parent_run_id=parent_run_id,
            code_sha=sha,
            code_dirty=dirty,
            config_hash=stable_hash(cfg),
            config_json=json.dumps(cfg, sort_keys=True, default=str),
            seed=int(seed),
            rng_stream_seeds={n: stream_seed(int(seed), n)
                              for n in rng_streams},
            started_at=datetime.now(timezone.utc).isoformat(),
            **fields,
        )

    def rng(self, stream: str) -> np.random.Generator:
        """Independent generator for a registered named stream."""
        if stream not in self.rng_stream_seeds:
            raise KeyError(
                f"unregistered RNG stream {stream!r}; registered: "
                f"{sorted(self.rng_stream_seeds)}")
        return np.random.default_rng(self.rng_stream_seeds[stream])

    def complete(self) -> "RunContext":
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.status = "complete"
        return self

    def fail(self, reason: str) -> "RunContext":
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.status = "failed"
        self.failure_reason = str(reason)
        return self

    def to_bq_row(self) -> dict[str, Any]:
        """Flat, JSON-safe dict ready for a BQ load job: nested dicts
        are JSON-encoded strings, timestamps ISO-8601 strings."""
        row = asdict(self)
        row["model_versions"] = json.dumps(self.model_versions,
                                           sort_keys=True)
        row["rng_stream_seeds"] = json.dumps(
            self.rng_stream_seeds, sort_keys=True)
        return row
