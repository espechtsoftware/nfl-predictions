"""Fail-closed API for the accepted E0 historical-realized summary."""

from __future__ import annotations

import json
import logging
import os
import stat
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from nfl_dfs.research import corpus_r6_historical_realized_summary_v1 as summary

router = APIRouter(tags=["corpus research"])

SUMMARY_PATH_ENV: Final = "CORPUS_R6_HISTORICAL_REALIZED_SUMMARY_PATH"
MAX_SUMMARY_BYTES: Final = 2 * 1024 * 1024
FIRST_OBSERVED_ABSENCE_QUERY_SCHEMA: Final = (
    "corpus-r6-historical-realized-first-observed-absence-query/v1"
)
STRATEGY_RESCUE_QUERY_SCHEMA: Final = (
    "corpus-r6-historical-realized-strategy-rescue-query/v1"
)
_NO_STORE: Final = {"Cache-Control": "no-store"}
_UNAVAILABLE: Final = {"detail": "Historical realized corpus summary unavailable."}
_STRATEGY_NOT_FOUND: Final = {
    "detail": "Historical realized corpus strategy unavailable."
}

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


class HistoricalRealizedStrategyNotFoundError(LookupError):
    """The validated aggregate does not contain the requested strategy."""


def _query_authority_boundary(validated: dict[str, object]) -> dict[str, object]:
    """Copy the source aggregate's closed authority boundary into a query."""

    return {
        "uses_realized_outcomes": validated["uses_realized_outcomes"],
        "persisted_realized_labels_only": validated["persisted_realized_labels_only"],
        "separate_from_corpus_graph_vnext_v2": validated[
            "separate_from_corpus_graph_vnext_v2"
        ],
        "raw_outcome_query_performed": False,
        "lineup_rescore_performed": False,
        "individual_rows_included": False,
        "neo4j_mutation_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy_feedback_authority": False,
        "query_response_complete": True,
        "complete_prelock_candidate_lineage_available": False,
    }


def first_observed_absence_query(candidate: object) -> dict[str, object]:
    """Return the bounded E0 final-book absence view.

    This is deliberately not named or represented as a causal first-loss
    result.  E0 observes final-fit book membership but contains neither a
    complete pre-lock stage trace nor roster identities for failed solver
    requests.
    """

    validated = summary.validate_historical_realized_summary_v1(candidate)
    funnel = deepcopy(validated["outcome_funnel_summary"])
    if not isinstance(funnel, dict):  # Defensive even after source validation.
        raise TypeError("historical outcome funnel must be an object")
    response: dict[str, object] = {
        "schema_version": FIRST_OBSERVED_ABSENCE_QUERY_SCHEMA,
        "query_name": "first-observed-absence-at-final-book",
        "source_summary": {
            "schema_version": validated["schema_version"],
            "summary_sha256": validated["summary_sha256"],
        },
        "evidence_class": validated["evidence_class"],
        "threshold_dk": validated["threshold_dk"],
        "threshold_micro": validated["threshold_micro"],
        "outcome_funnel_summary": funnel,
        "interpretation_boundary": {
            "localization": "observed-final-fit-book-membership-only",
            "causal_first_loss_claim": False,
            "source_emitted_selector_rejection": False,
            "failed_solver_request_has_roster_identity": False,
            "ordinary_solver_requests_define_finite_roster_universe": False,
            "roster_level_not_produced_claim_available": False,
        },
    }
    response.update(_query_authority_boundary(validated))
    return response


def strategy_rescue_query(
    candidate: object, *, strategy_id: str | None = None
) -> dict[str, object]:
    """Return all strategy rescue aggregates or one exact strategy row."""

    validated = summary.validate_historical_realized_summary_v1(candidate)
    source_rows = validated["strategy_rescue_summary"]
    if not isinstance(source_rows, list):  # Defensive after source validation.
        raise TypeError("historical strategy rescue summary must be an array")
    rows = [deepcopy(row) for row in source_rows]
    if strategy_id is not None:
        rows = [row for row in rows if row.get("strategy_id") == strategy_id]
        if not rows:
            raise HistoricalRealizedStrategyNotFoundError(strategy_id)
    response: dict[str, object] = {
        "schema_version": STRATEGY_RESCUE_QUERY_SCHEMA,
        "query_name": "historical-strategy-rescue-summary",
        "source_summary": {
            "schema_version": validated["schema_version"],
            "summary_sha256": validated["summary_sha256"],
        },
        "evidence_class": validated["evidence_class"],
        "threshold_dk": validated["threshold_dk"],
        "threshold_micro": validated["threshold_micro"],
        "strategy_filter": {
            "mode": "all" if strategy_id is None else "exact",
            "strategy_id": strategy_id,
        },
        "row_count": len(rows),
        "strategy_rescue_summary": rows,
        "interpretation_boundary": {
            "rescue_basis": (
                "per-slate-hindsight-eligible-maximum-minus-observed-"
                "selected-book-maximum"
            ),
            "counterfactual_selector_rerun_performed": False,
            "forecast_or_promised_gain_claim": False,
            "rescue_sum_is_jointly_achievable": False,
        },
    }
    response.update(_query_authority_boundary(validated))
    return response


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


@router.get("/api/corpus-research/historical-realized-summary/first-observed-absence")
def historical_first_observed_absence(
    reader: HistoricalRealizedSummaryReader = Depends(  # noqa: B008
        get_historical_realized_summary_reader
    ),
) -> JSONResponse:
    try:
        response = first_observed_absence_query(reader.read())
    except Exception:  # noqa: BLE001 - injected readers have provider-specific errors.
        log.warning("Historical realized corpus first-observed-absence query failed")
        return JSONResponse(_UNAVAILABLE, status_code=503, headers=_NO_STORE)
    return JSONResponse(response, headers=_NO_STORE)


@router.get("/api/corpus-research/historical-realized-summary/rescue")
def historical_strategy_rescue(
    strategy_id: str | None = None,
    reader: HistoricalRealizedSummaryReader = Depends(  # noqa: B008
        get_historical_realized_summary_reader
    ),
) -> JSONResponse:
    try:
        response = strategy_rescue_query(reader.read(), strategy_id=strategy_id)
    except HistoricalRealizedStrategyNotFoundError:
        return JSONResponse(_STRATEGY_NOT_FOUND, status_code=404, headers=_NO_STORE)
    except Exception:  # noqa: BLE001 - injected readers have provider-specific errors.
        log.warning("Historical realized corpus strategy-rescue query failed")
        return JSONResponse(_UNAVAILABLE, status_code=503, headers=_NO_STORE)
    return JSONResponse(response, headers=_NO_STORE)


__all__ = [
    "FIRST_OBSERVED_ABSENCE_QUERY_SCHEMA",
    "MAX_SUMMARY_BYTES",
    "STRATEGY_RESCUE_QUERY_SCHEMA",
    "SUMMARY_PATH_ENV",
    "FileHistoricalRealizedSummaryReader",
    "HistoricalRealizedStrategyNotFoundError",
    "HistoricalRealizedSummaryReader",
    "first_observed_absence_query",
    "get_historical_realized_summary_reader",
    "historical_first_observed_absence",
    "historical_realized_summary",
    "historical_strategy_rescue",
    "router",
    "strategy_rescue_query",
]
