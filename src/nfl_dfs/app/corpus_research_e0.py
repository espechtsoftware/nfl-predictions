"""One GET-only API over the accepted historical E0 aggregate artifact."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from nfl_dfs.research import corpus_r6_historical_realized_summary_v1 as summary_v1

log = logging.getLogger(__name__)

router = APIRouter(tags=["corpus research E0"])
SUMMARY_PATH_ENV = "CORPUS_RESEARCH_E0_HISTORICAL_SUMMARY_PATH"
ENDPOINT_SCHEMA = "corpus-r6-historical-realized-summary-api/v1"
MAX_SUMMARY_BYTES = 1_000_000


class HistoricalE0SummaryUnavailable(RuntimeError):
    """The explicitly configured aggregate artifact is unavailable or invalid."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


class HistoricalE0SummaryReader(Protocol):
    def read(self) -> dict[str, object]:
        """Return one fully validated accepted-E0 aggregate."""


@dataclass(frozen=True, slots=True)
class FileHistoricalE0SummaryReader:
    """Reopen and validate one explicitly configured local artifact per GET."""

    path: Path | None

    @classmethod
    def from_environment(cls) -> FileHistoricalE0SummaryReader:
        raw = os.environ.get(SUMMARY_PATH_ENV, "").strip()
        return cls(Path(raw) if raw else None)

    def read(self) -> dict[str, object]:
        if self.path is None:
            raise HistoricalE0SummaryUnavailable(
                "historical-e0-summary-not-configured",
                f"Set {SUMMARY_PATH_ENV} to the reviewed create-once artifact.",
            )
        try:
            before = self.path.stat()
            if (
                not self.path.is_file()
                or self.path.is_symlink()
                or before.st_size <= 0
                or before.st_size > MAX_SUMMARY_BYTES
            ):
                raise ValueError("summary path is not one bounded regular file")
            raw = self.path.read_bytes()
            after = self.path.stat()
            if (
                len(raw) != before.st_size
                or before.st_dev != after.st_dev
                or before.st_ino != after.st_ino
                or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                raise ValueError("summary artifact changed during read")
            value = json.loads(raw)
            summary = summary_v1.validate_historical_realized_summary_v1(value)
            if raw != summary_v1.canonical_json_bytes(summary) + b"\n":
                raise ValueError("summary artifact bytes are not canonical")
            return summary
        except HistoricalE0SummaryUnavailable:
            raise
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            summary_v1.CorpusR6HistoricalRealizedSummaryV1Error,
        ) as exc:
            raise HistoricalE0SummaryUnavailable(
                "historical-e0-summary-invalid-or-unavailable",
                "The configured historical E0 aggregate failed closed.",
            ) from exc


def get_historical_e0_summary_reader() -> HistoricalE0SummaryReader:
    return FileHistoricalE0SummaryReader.from_environment()


def _unavailable_payload(
    unavailable: HistoricalE0SummaryUnavailable,
) -> dict[str, object]:
    return {
        "schema_version": ENDPOINT_SCHEMA,
        "ready": False,
        "reason_code": unavailable.reason_code,
        "message": unavailable.message,
        "read_only": True,
        "summary_only": True,
        "descriptive_development_only": True,
        "neo4j_access": False,
        "promotion_authority": False,
        "decision_authority": False,
    }


@router.get("/api/corpus-research/e0/historical-realized-summary")
def historical_realized_summary(
    reader: HistoricalE0SummaryReader = Depends(  # noqa: B008
        get_historical_e0_summary_reader
    ),
) -> JSONResponse:
    """Return only the fully validated aggregate, or a fail-closed 503."""

    try:
        summary = summary_v1.validate_historical_realized_summary_v1(reader.read())
    except HistoricalE0SummaryUnavailable as exc:
        return JSONResponse(
            _unavailable_payload(exc),
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    except Exception:
        log.exception("Historical E0 aggregate failed at the API boundary")
        unavailable = HistoricalE0SummaryUnavailable(
            "historical-e0-summary-reader-boundary-failed",
            "The historical E0 aggregate reader failed closed.",
        )
        return JSONResponse(
            _unavailable_payload(unavailable),
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    return JSONResponse(
        {
            "schema_version": ENDPOINT_SCHEMA,
            "ready": True,
            "read_only": True,
            "summary_only": True,
            "descriptive_development_only": True,
            "neo4j_access": False,
            "promotion_authority": False,
            "decision_authority": False,
            "summary": summary,
        },
        headers={"Cache-Control": "no-store"},
    )


__all__ = [
    "ENDPOINT_SCHEMA",
    "MAX_SUMMARY_BYTES",
    "SUMMARY_PATH_ENV",
    "FileHistoricalE0SummaryReader",
    "HistoricalE0SummaryReader",
    "HistoricalE0SummaryUnavailable",
    "get_historical_e0_summary_reader",
    "historical_realized_summary",
    "router",
]
