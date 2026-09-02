"""Fail-closed API for the accepted E0 historical-realized summary."""

from __future__ import annotations

import json
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from nfl_dfs.research import corpus_r6_historical_realized_summary_v1 as summary

router = APIRouter(tags=["corpus research"])

SUMMARY_PATH_ENV: Final = "CORPUS_R6_HISTORICAL_REALIZED_SUMMARY_PATH"
MAX_SUMMARY_BYTES: Final = 2 * 1024 * 1024
_NO_STORE: Final = {"Cache-Control": "no-store"}
_UNAVAILABLE: Final = {"detail": "Historical realized corpus summary unavailable."}

log = logging.getLogger(__name__)


class HistoricalRealizedSummaryReader(Protocol):
    """Read boundary used by the route dependency."""

    def read(self) -> object:
        """Return one candidate summary for route-boundary revalidation."""


def _parse_exact_summary_file(raw: bytes) -> dict[str, object]:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAX_SUMMARY_BYTES
        or not raw.endswith(b"\n")
        or raw.endswith(b"\n\n")
    ):
        raise ValueError("historical summary file envelope differs")
    payload = raw[:-1]

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                raise ValueError("historical summary repeats a JSON key")
            result[key] = value
        return result

    def reject_constant(token: str) -> object:
        raise ValueError(f"non-finite JSON token {token}")

    try:
        parsed = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("historical summary is not UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise TypeError("historical summary must be one JSON object")
    if summary.canonical_json_bytes(parsed) != payload:
        raise ValueError("historical summary is not canonical JSON plus LF")
    return summary.validate_historical_realized_summary_v1(parsed)


@dataclass(frozen=True, slots=True)
class FileHistoricalRealizedSummaryReader:
    """Read one configured local aggregate file on every request."""

    path: Path | None

    @classmethod
    def from_environment(cls) -> FileHistoricalRealizedSummaryReader:
        configured = os.environ.get(SUMMARY_PATH_ENV)
        return cls(Path(configured) if configured else None)

    def read(self) -> object:
        if self.path is None:
            raise ValueError("historical summary is not configured")
        if not self.path.is_absolute():
            raise ValueError("historical summary path must be absolute")
        current = Path(self.path.anchor)
        try:
            for part in self.path.parts[1:]:
                current /= part
                metadata = os.lstat(current)
                if stat.S_ISLNK(metadata.st_mode):
                    raise ValueError(
                        "historical summary path may not contain a symlink"
                    )
        except OSError as exc:
            raise ValueError("historical summary is unavailable") from exc
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size <= 0
            or metadata.st_size > MAX_SUMMARY_BYTES
        ):
            raise ValueError("historical summary file envelope differs")
        descriptor = -1
        try:
            descriptor = os.open(
                self.path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            before = os.fstat(descriptor)
            if (
                (before.st_dev, before.st_ino) != (metadata.st_dev, metadata.st_ino)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size <= 0
                or before.st_size > MAX_SUMMARY_BYTES
            ):
                raise ValueError("historical summary changed before read")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                raw = handle.read(MAX_SUMMARY_BYTES + 1)
            after = os.fstat(descriptor)
        except OSError as exc:
            raise ValueError("historical summary is unavailable") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if len(raw) != before.st_size or any(
            getattr(before, field) != getattr(after, field) for field in stable_fields
        ):
            raise ValueError("historical summary changed during read")
        return _parse_exact_summary_file(raw)


def get_historical_realized_summary_reader() -> HistoricalRealizedSummaryReader:
    """Construct the environment reader without opening its configured path."""

    return FileHistoricalRealizedSummaryReader.from_environment()


@router.get("/api/corpus-research/historical-realized-summary")
def historical_realized_summary(
    reader: HistoricalRealizedSummaryReader = Depends(  # noqa: B008
        get_historical_realized_summary_reader
    ),
) -> JSONResponse:
    try:
        candidate = reader.read()
        validated = summary.validate_historical_realized_summary_v1(candidate)
    except Exception:  # noqa: BLE001 - injected readers have provider-specific errors.
        log.warning("Historical realized corpus summary failed closed")
        return JSONResponse(_UNAVAILABLE, status_code=503, headers=_NO_STORE)
    return JSONResponse(validated, headers=_NO_STORE)


__all__ = [
    "MAX_SUMMARY_BYTES",
    "SUMMARY_PATH_ENV",
    "FileHistoricalRealizedSummaryReader",
    "HistoricalRealizedSummaryReader",
    "get_historical_realized_summary_reader",
    "historical_realized_summary",
    "router",
]
