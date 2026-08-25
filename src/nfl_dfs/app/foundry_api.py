"""Versioned, bounded, GET-only Foundry observatory API.

NOT wired into the live application: integration is a separately reviewed
step behind the lead checkpoint. Tests mount this router on their own app.

Every successful response is one envelope carrying the API schema, the
response type, release identity, staleness, evidence tier/scope, and the
payload. The router exposes no write method, accepts only typed bounded
parameters, paginates by opaque cursor, enforces a canonical-bytes
response budget, and serves ETag/304 revalidation. When the projection
backend is unavailable the API stays healthy and visibly degraded (503
envelope, never a crash)."""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from nfl_dfs.app.foundry_read_models import (
    API_SCHEMA,
    API_VERSION,
    DEFAULT_PAGE_SIZE,
    FixtureFoundryRepository,
    FoundryReadError,
    FoundryRepository,
    MAX_PAGE_SIZE,
    ReleaseIdentity,
    Staleness,
    content_etag,
    decode_cursor,
    encode_cursor,
    enforce_response_budget,
)

router: Final = APIRouter(prefix="/api/v1/foundry", tags=["foundry read"])

_UTC_NOW_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).strftime(_UTC_NOW_FORMAT)


def default_foundry_repository() -> FoundryRepository:
    return FixtureFoundryRepository()


def get_foundry_repository() -> FoundryRepository:
    return default_foundry_repository()


class Envelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: str
    api_version: str
    response_type: str
    release: ReleaseIdentity
    staleness: Staleness
    evidence_note: str
    read_only: bool
    payload: object
    next_cursor: str | None = None


_EVIDENCE_NOTE: Final = (
    "fixture-backed observatory read; evidence tiers are carried per row "
    "and are never promoted by this API"
)


def _respond(
    request: Request,
    *,
    repository: FoundryRepository,
    response_type: str,
    payload: object,
    next_cursor: str | None = None,
) -> Response:
    envelope = Envelope(
        schema_version=API_SCHEMA,
        api_version=API_VERSION,
        response_type=response_type,
        release=repository.release_identity(),
        staleness=repository.staleness(now_utc=_utc_now()),
        evidence_note=_EVIDENCE_NOTE,
        read_only=True,
        payload=payload,
        next_cursor=next_cursor,
    )
    body = envelope.model_dump(mode="json")
    enforce_response_budget(body)
    etag = content_etag({**body, "staleness": None})
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(
        body, headers={"ETag": etag, "Cache-Control": "no-store"}
    )


def _degraded(detail: str) -> JSONResponse:
    return JSONResponse(
        {
            "schema_version": API_SCHEMA,
            "api_version": API_VERSION,
            "response_type": "degraded",
            "detail": detail,
            "read_only": True,
        },
        status_code=503,
        headers={"Cache-Control": "no-store"},
    )


def _bad_request(detail: str) -> JSONResponse:
    return JSONResponse(
        {
            "schema_version": API_SCHEMA,
            "api_version": API_VERSION,
            "response_type": "invalid-request",
            "detail": detail,
            "read_only": True,
        },
        status_code=422,
        headers={"Cache-Control": "no-store"},
    )


def _not_found(detail: str) -> JSONResponse:
    return JSONResponse(
        {
            "schema_version": API_SCHEMA,
            "api_version": API_VERSION,
            "response_type": "not-found",
            "detail": detail,
            "read_only": True,
        },
        status_code=404,
        headers={"Cache-Control": "no-store"},
    )


PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Cursor = Annotated[str | None, Query(max_length=128)]
CanonicalId = Annotated[
    str, Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9:._/-]+$")
]


def _paged(
    request: Request,
    repository: FoundryRepository,
    response_type: str,
    rows: list[object],
    cursor: str | None,
    page_size: int,
) -> Response:
    try:
        offset = decode_cursor(cursor)
    except FoundryReadError as exc:
        return _bad_request(str(exc))
    window = rows[offset : offset + page_size]
    next_cursor = (
        encode_cursor(offset + page_size)
        if offset + page_size < len(rows)
        else None
    )
    return _respond(
        request,
        repository=repository,
        response_type=response_type,
        payload={"rows": window, "total": len(rows), "offset": offset},
        next_cursor=next_cursor,
    )


def _rows(models: object) -> list[object]:
    return [model.model_dump(mode="json") for model in models]  # type: ignore[attr-defined]


@router.get("/status")
def foundry_status(
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    try:
        payload = repository.status().model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 - degraded, never a crash
        return _degraded(f"projection backend unavailable: {exc}")
    return _respond(
        request,
        repository=repository,
        response_type="foundry-status",
        payload=payload,
    )


@router.get("/releases")
def foundry_releases(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "releases", _rows(repository.releases()),
        cursor, page_size,
    )


@router.get("/presets")
def foundry_presets(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "presets", _rows(repository.presets()),
        cursor, page_size,
    )


@router.get("/strategy-bundles")
def foundry_strategy_bundles(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "strategy-bundles",
        _rows(repository.strategy_bundles()), cursor, page_size,
    )


@router.get("/experiments")
def foundry_experiments(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "experiments", _rows(repository.experiments()),
        cursor, page_size,
    )


@router.get("/experiments/{experiment_id}/metrics")
def foundry_experiment_metrics(
    experiment_id: str,
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    rows = _rows(repository.experiment_metrics(experiment_id))
    if not rows:
        return _not_found(f"experiment {experiment_id} has no metrics")
    return _paged(
        request, repository, "experiment-metrics", rows, cursor, page_size
    )


@router.get("/runs")
def foundry_runs(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "runs", _rows(repository.runs()),
        cursor, page_size,
    )


@router.get("/evaluations")
def foundry_evaluations(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "evaluations", _rows(repository.evaluations()),
        cursor, page_size,
    )


@router.get("/books/{book_id}")
def foundry_book(
    book_id: str,
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    book = repository.book(book_id)
    if book is None:
        return _not_found(f"book {book_id} is not registered")
    return _respond(
        request,
        repository=repository,
        response_type="book",
        payload=book.model_dump(mode="json"),
    )


@router.get("/cohorts/compare")
def foundry_cohort_compare(
    request: Request,
    cohort_a: CanonicalId,
    cohort_b: CanonicalId,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    comparison = repository.cohort_compare(cohort_a, cohort_b)
    return _respond(
        request,
        repository=repository,
        response_type="cohort-comparison",
        payload=comparison.model_dump(mode="json"),
    )


@router.get("/traits/enrichment")
def foundry_trait_enrichment(
    request: Request,
    cohort: CanonicalId,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "trait-enrichment",
        _rows(repository.trait_enrichment(cohort)), cursor, page_size,
    )


@router.get("/slates/{slate_id}/lineups/{lineup_id}")
def foundry_lineup_detail(
    slate_id: str,
    lineup_id: str,
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    detail = repository.lineup_detail(slate_id, lineup_id)
    if detail is None:
        return _not_found(f"lineup {lineup_id} on {slate_id} is not indexed")
    return _respond(
        request,
        repository=repository,
        response_type="lineup-detail",
        payload=detail.model_dump(mode="json"),
    )


@router.get("/lineup-network")
def foundry_lineup_network(
    request: Request,
    lineup_id: CanonicalId,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "lineup-network",
        _rows(repository.lineup_network(lineup_id)), cursor, page_size,
    )


@router.get("/source-coverage")
def foundry_source_coverage(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _paged(
        request, repository, "source-coverage",
        _rows(repository.source_coverage()), cursor, page_size,
    )


@router.get("/receipts/{receipt_id}")
def foundry_receipt(
    receipt_id: str,
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    receipt = repository.receipt(receipt_id)
    if receipt is None:
        return _not_found(f"receipt {receipt_id} is not registered")
    return _respond(
        request,
        repository=repository,
        response_type="receipt-metadata",
        payload=receipt.model_dump(mode="json"),
    )
