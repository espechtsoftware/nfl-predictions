"""Versioned, bounded, GET-only Foundry observatory API.

This router remains deliberately unmounted.  Its production dependency is a
fail-closed unavailable repository; tests inject the explicit synthetic
fixture.  Every endpoint executes inside the same sanitized read boundary,
and every collection query receives a release-bound hard row cap and deadline
before the repository is called.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import datetime as dt
import logging
import re
from typing import Annotated, Final, TypeVar

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError

from nfl_dfs.app.foundry_read_models import (
    API_SCHEMA,
    API_VERSION,
    AuthorityContext,
    Book,
    CatalogQuery,
    CohortComparison,
    DEFAULT_PAGE_SIZE,
    DEFAULT_QUERY_DEADLINE_MS,
    Envelope,
    ErrorEnvelope,
    Evaluation,
    Experiment,
    FoundryBackendUnavailable,
    FoundryContractError,
    FoundryInvalidRequest,
    FoundryNotFound,
    FoundryRepository,
    FoundryResponseBudgetError,
    FoundryStatus,
    ID_PATTERN,
    LineupDetail,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_SIZE,
    MetricValue,
    NetworkEdge,
    PagePayload,
    PageRequest,
    Preset,
    QueryFilter,
    ReadRequest,
    ReceiptMeta,
    Release,
    ReleaseIdentity,
    RepositoryPage,
    Run,
    SourceCoverageRow,
    Staleness,
    StrategyBundle,
    TraitEnrichment,
    UnavailableFoundryRepository,
    canonical_filters,
    content_etag,
    decode_cursor,
    encode_cursor,
    enforce_response_budget,
    release_sha256,
)

logger = logging.getLogger(__name__)


class _SanitizedValidationRoute(APIRoute):
    """Keep FastAPI's pre-endpoint validation inside the public error law."""

    def get_route_handler(self):  # type: ignore[no-untyped-def]
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                return _error_response(
                    status_code=422,
                    response_type="invalid-request",
                    reason_code="invalid-request",
                    detail="The request parameters exceed the licensed bounds.",
                )

        return handler


router: Final = APIRouter(
    prefix="/api/v1/foundry",
    tags=["foundry read"],
    route_class=_SanitizedValidationRoute,
)
_UTC_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime(_UTC_FORMAT)


def default_foundry_repository() -> FoundryRepository:
    """Return no data until a reviewed release-bound adapter is configured."""

    return UnavailableFoundryRepository()


def get_foundry_repository() -> FoundryRepository:
    return default_foundry_repository()


@dataclass(frozen=True)
class _ResponseContext:
    release: ReleaseIdentity
    staleness: Staleness
    authority: AuthorityContext


StatusEnvelope = Envelope[FoundryStatus]
ReleasePageEnvelope = Envelope[PagePayload[Release]]
PresetPageEnvelope = Envelope[PagePayload[Preset]]
BundlePageEnvelope = Envelope[PagePayload[StrategyBundle]]
ExperimentPageEnvelope = Envelope[PagePayload[Experiment]]
MetricPageEnvelope = Envelope[PagePayload[MetricValue]]
RunPageEnvelope = Envelope[PagePayload[Run]]
EvaluationPageEnvelope = Envelope[PagePayload[Evaluation]]
BookEnvelope = Envelope[Book]
CohortEnvelope = Envelope[CohortComparison]
TraitPageEnvelope = Envelope[PagePayload[TraitEnrichment]]
LineupEnvelope = Envelope[LineupDetail]
NetworkPageEnvelope = Envelope[PagePayload[NetworkEdge]]
CoveragePageEnvelope = Envelope[PagePayload[SourceCoverageRow]]
ReceiptEnvelope = Envelope[ReceiptMeta]

_ERROR_RESPONSES: Final = {
    404: {"model": ErrorEnvelope, "description": "Canonical entity absent"},
    422: {"model": ErrorEnvelope, "description": "Invalid bounded request"},
    503: {"model": ErrorEnvelope, "description": "Read projection unavailable"},
}

PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Cursor = Annotated[str | None, Query(max_length=MAX_CURSOR_LENGTH)]
CanonicalQueryId = Annotated[
    str, Query(min_length=1, max_length=128, pattern=ID_PATTERN)
]
CanonicalPathId = Annotated[
    str, Path(min_length=1, max_length=128, pattern=ID_PATTERN)
]

_FORBIDDEN_PUBLIC_STRING: Final = re.compile(
    r"(?:gs://|bq://|(?:https?://)?storage\.googleapis\.com/|"
    r"bolt(?:\+s)?://|neo4j(?:\+s)?://|secretkeyref|"
    r"projects/[^/]+/secrets/|authorization\s*[=:]|bearer\s+[A-Za-z0-9._-]+|"
    r"(?:access[_-]?token|api[_-]?key|client[_-]?secret|password|private[_-]?key)\s*[=:])",
    re.IGNORECASE,
)


def _assert_public_payload_is_sanitized(value: object) -> None:
    """Reject raw storage/graph locations and credential-shaped strings."""

    if isinstance(value, str):
        if _FORBIDDEN_PUBLIC_STRING.search(value):
            raise FoundryContractError("public projection contains forbidden provenance")
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_public_payload_is_sanitized(key)
            _assert_public_payload_is_sanitized(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_public_payload_is_sanitized(item)


def _context(repository: FoundryRepository) -> _ResponseContext:
    return _ResponseContext(
        release=repository.release_identity(),
        staleness=repository.staleness(now_utc=_utc_now()),
        authority=repository.authority(),
    )


def _read_request(
    *,
    context: _ResponseContext,
    query_id: CatalogQuery,
    filters: Sequence[QueryFilter] = (),
    hard_row_cap: int = 1,
) -> ReadRequest:
    return ReadRequest(
        query_id=query_id,
        filters=canonical_filters(filters),
        release_sha256=release_sha256(context.release),
        deadline_ms=DEFAULT_QUERY_DEADLINE_MS,
        hard_row_cap=hard_row_cap,
    )


def _page_request(
    *,
    context: _ResponseContext,
    query_id: CatalogQuery,
    filters: Sequence[QueryFilter],
    cursor: str | None,
    page_size: int,
) -> PageRequest:
    retained_filters = canonical_filters(filters)
    offset = decode_cursor(
        cursor,
        query_id=query_id,
        filters=retained_filters,
        release=context.release,
    )
    return PageRequest(
        query_id=query_id,
        filters=retained_filters,
        release_sha256=release_sha256(context.release),
        deadline_ms=DEFAULT_QUERY_DEADLINE_MS,
        hard_row_cap=page_size,
        offset=offset,
        limit=page_size,
    )


def _etag_basis(body: dict[str, object]) -> dict[str, object]:
    """Omit only continuous age; retain the fresh/stale state transition."""

    staleness = body["staleness"]
    if not isinstance(staleness, dict):
        raise FoundryContractError("staleness is not an object")
    return {
        **body,
        "staleness": {
            "generated_at_utc": staleness["generated_at_utc"],
            "verified_at_utc": staleness["verified_at_utc"],
            "stale": staleness["stale"],
        },
    }


def _respond(
    request: Request,
    *,
    context: _ResponseContext,
    response_type: str,
    payload: object,
    envelope_model: type[BaseModel],
    next_cursor: str | None = None,
) -> Response:
    envelope = envelope_model.model_validate(
        {
            "schema_version": API_SCHEMA,
            "api_version": API_VERSION,
            "response_type": response_type,
            "release": context.release,
            "staleness": context.staleness,
            "authority": context.authority,
            "evidence_note": context.authority.note,
            "read_only": True,
            "payload": payload,
            "next_cursor": next_cursor,
        }
    )
    body = envelope.model_dump(mode="json")
    _assert_public_payload_is_sanitized(body)
    enforce_response_budget(body)
    etag = content_etag(_etag_basis(body))
    headers = {
        "ETag": etag,
        "Cache-Control": "private, no-cache",
        "X-Foundry-Age-Seconds": str(context.staleness.age_seconds),
        "X-Foundry-Stale": str(context.staleness.stale).lower(),
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(body, headers=headers)


def _error_response(
    *,
    status_code: int,
    response_type: str,
    reason_code: str,
    detail: str,
) -> JSONResponse:
    body = ErrorEnvelope.model_validate(
        {
            "response_type": response_type,
            "reason_code": reason_code,
            "detail": detail,
        }
    ).model_dump(mode="json")
    return JSONResponse(body, status_code=status_code, headers={"Cache-Control": "no-store"})


def _execute_read(operation: Callable[[], Response]) -> Response:
    """One sanitized boundary around every backend and serialization action."""

    try:
        return operation()
    except FoundryInvalidRequest:
        return _error_response(
            status_code=422,
            response_type="invalid-request",
            reason_code="invalid-request",
            detail="The cursor or filter is invalid for this release-bound query.",
        )
    except FoundryNotFound:
        return _error_response(
            status_code=404,
            response_type="not-found",
            reason_code="not-found",
            detail="The requested entity is not registered in this release.",
        )
    except FoundryResponseBudgetError:
        logger.exception("Foundry response exceeded its serialized budget")
        return _error_response(
            status_code=503,
            response_type="degraded",
            reason_code="response-budget-exceeded",
            detail="The bounded projection cannot serve this response safely.",
        )
    except (FoundryContractError, ValidationError, TypeError, ValueError, OverflowError):
        logger.exception("Foundry projection violated its read contract")
        return _error_response(
            status_code=503,
            response_type="degraded",
            reason_code="projection-contract-invalid",
            detail="The verified projection is unavailable because its contract failed.",
        )
    except FoundryBackendUnavailable:
        logger.exception("Foundry release-bound backend is unavailable")
        return _error_response(
            status_code=503,
            response_type="degraded",
            reason_code="backend-unavailable",
            detail="The release-bound Foundry projection is unavailable.",
        )
    except Exception:  # noqa: BLE001 - final fail-safe boundary
        logger.exception("Unexpected Foundry read backend failure")
        return _error_response(
            status_code=503,
            response_type="degraded",
            reason_code="backend-unavailable",
            detail="The release-bound Foundry projection is unavailable.",
        )


PageModelT = TypeVar("PageModelT", bound=BaseModel)


def _paged(
    request: Request,
    *,
    repository: FoundryRepository,
    query_id: CatalogQuery,
    response_type: str,
    filters: Sequence[QueryFilter],
    cursor: str | None,
    page_size: int,
    fetch: Callable[[PageRequest], RepositoryPage[PageModelT]],
    envelope_model: type[BaseModel],
    absent_when_empty: bool = False,
) -> Response:
    context = _context(repository)
    bounded_request = _page_request(
        context=context,
        query_id=query_id,
        filters=filters,
        cursor=cursor,
        page_size=page_size,
    )
    page = fetch(bounded_request)
    if not isinstance(page, RepositoryPage):
        raise FoundryContractError("repository did not return a bounded page")
    if page.offset != bounded_request.offset or len(page.rows) > bounded_request.limit:
        raise FoundryContractError("repository exceeded or changed the licensed page")
    if absent_when_empty and page.total == 0:
        raise FoundryNotFound("entity has no registered page")
    next_cursor = None
    if page.next_offset is not None:
        next_cursor = encode_cursor(
            offset=page.next_offset,
            query_id=query_id,
            filters=bounded_request.filters,
            release=context.release,
        )
    return _respond(
        request,
        context=context,
        response_type=response_type,
        payload={"rows": page.rows, "total": page.total, "offset": page.offset},
        next_cursor=next_cursor,
        envelope_model=envelope_model,
    )


@router.get("/status", response_model=StatusEnvelope, responses=_ERROR_RESPONSES)
def foundry_status(
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    def operation() -> Response:
        context = _context(repository)
        read = _read_request(context=context, query_id="status")
        return _respond(
            request,
            context=context,
            response_type="foundry-status",
            payload=repository.status(read),
            envelope_model=StatusEnvelope,
        )

    return _execute_read(operation)


@router.get("/releases", response_model=ReleasePageEnvelope, responses=_ERROR_RESPONSES)
def foundry_releases(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="releases", response_type="releases",
        filters=(), cursor=cursor, page_size=page_size, fetch=repository.releases,
        envelope_model=ReleasePageEnvelope,
    ))


@router.get("/presets", response_model=PresetPageEnvelope, responses=_ERROR_RESPONSES)
def foundry_presets(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="presets", response_type="presets",
        filters=(), cursor=cursor, page_size=page_size, fetch=repository.presets,
        envelope_model=PresetPageEnvelope,
    ))


@router.get("/strategy-bundles", response_model=BundlePageEnvelope, responses=_ERROR_RESPONSES)
def foundry_strategy_bundles(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="strategy-bundles",
        response_type="strategy-bundles", filters=(), cursor=cursor,
        page_size=page_size, fetch=repository.strategy_bundles,
        envelope_model=BundlePageEnvelope,
    ))


@router.get("/experiments", response_model=ExperimentPageEnvelope, responses=_ERROR_RESPONSES)
def foundry_experiments(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="experiments", response_type="experiments",
        filters=(), cursor=cursor, page_size=page_size, fetch=repository.experiments,
        envelope_model=ExperimentPageEnvelope,
    ))


@router.get(
    "/experiments/{experiment_id}/metrics",
    response_model=MetricPageEnvelope,
    responses=_ERROR_RESPONSES,
)
def foundry_experiment_metrics(
    experiment_id: CanonicalPathId,
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    filters = (QueryFilter(name="experiment-id", value=experiment_id),)
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="experiment-metrics",
        response_type="experiment-metrics", filters=filters, cursor=cursor,
        page_size=page_size,
        fetch=lambda read: repository.experiment_metrics(experiment_id, read),
        envelope_model=MetricPageEnvelope, absent_when_empty=True,
    ))


@router.get("/runs", response_model=RunPageEnvelope, responses=_ERROR_RESPONSES)
def foundry_runs(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="runs", response_type="runs",
        filters=(), cursor=cursor, page_size=page_size, fetch=repository.runs,
        envelope_model=RunPageEnvelope,
    ))


@router.get("/evaluations", response_model=EvaluationPageEnvelope, responses=_ERROR_RESPONSES)
def foundry_evaluations(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="evaluations", response_type="evaluations",
        filters=(), cursor=cursor, page_size=page_size, fetch=repository.evaluations,
        envelope_model=EvaluationPageEnvelope,
    ))


@router.get("/books/{book_id}", response_model=BookEnvelope, responses=_ERROR_RESPONSES)
def foundry_book(
    book_id: CanonicalPathId,
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    def operation() -> Response:
        context = _context(repository)
        read = _read_request(
            context=context, query_id="book",
            filters=(QueryFilter(name="book-id", value=book_id),),
        )
        book = repository.book(book_id, read)
        if book is None:
            raise FoundryNotFound("book absent")
        return _respond(
            request, context=context, response_type="book", payload=book,
            envelope_model=BookEnvelope,
        )

    return _execute_read(operation)


@router.get("/cohorts/compare", response_model=CohortEnvelope, responses=_ERROR_RESPONSES)
def foundry_cohort_compare(
    request: Request,
    cohort_a: CanonicalQueryId,
    cohort_b: CanonicalQueryId,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    def operation() -> Response:
        context = _context(repository)
        filters = (
            QueryFilter(name="cohort-a", value=cohort_a),
            QueryFilter(name="cohort-b", value=cohort_b),
        )
        read = _read_request(context=context, query_id="cohort-compare", filters=filters)
        return _respond(
            request, context=context, response_type="cohort-comparison",
            payload=repository.cohort_compare(cohort_a, cohort_b, read),
            envelope_model=CohortEnvelope,
        )

    return _execute_read(operation)


@router.get("/traits/enrichment", response_model=TraitPageEnvelope, responses=_ERROR_RESPONSES)
def foundry_trait_enrichment(
    request: Request,
    cohort: CanonicalQueryId,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    filters = (QueryFilter(name="cohort", value=cohort),)
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="trait-enrichment",
        response_type="trait-enrichment", filters=filters, cursor=cursor,
        page_size=page_size, fetch=lambda read: repository.trait_enrichment(cohort, read),
        envelope_model=TraitPageEnvelope,
    ))


@router.get(
    "/slates/{slate_id}/lineups/{lineup_id}",
    response_model=LineupEnvelope,
    responses=_ERROR_RESPONSES,
)
def foundry_lineup_detail(
    slate_id: CanonicalPathId,
    lineup_id: CanonicalPathId,
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    def operation() -> Response:
        context = _context(repository)
        filters = (
            QueryFilter(name="lineup-id", value=lineup_id),
            QueryFilter(name="slate-id", value=slate_id),
        )
        read = _read_request(context=context, query_id="lineup-detail", filters=filters)
        detail = repository.lineup_detail(slate_id, lineup_id, read)
        if detail is None:
            raise FoundryNotFound("lineup absent")
        return _respond(
            request, context=context, response_type="lineup-detail", payload=detail,
            envelope_model=LineupEnvelope,
        )

    return _execute_read(operation)


@router.get("/lineup-network", response_model=NetworkPageEnvelope, responses=_ERROR_RESPONSES)
def foundry_lineup_network(
    request: Request,
    lineup_id: CanonicalQueryId,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    filters = (QueryFilter(name="lineup-id", value=lineup_id),)
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="lineup-network",
        response_type="lineup-network", filters=filters, cursor=cursor,
        page_size=page_size, fetch=lambda read: repository.lineup_network(lineup_id, read),
        envelope_model=NetworkPageEnvelope,
    ))


@router.get("/source-coverage", response_model=CoveragePageEnvelope, responses=_ERROR_RESPONSES)
def foundry_source_coverage(
    request: Request,
    cursor: Cursor = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    return _execute_read(lambda: _paged(
        request, repository=repository, query_id="source-coverage",
        response_type="source-coverage", filters=(), cursor=cursor,
        page_size=page_size, fetch=repository.source_coverage,
        envelope_model=CoveragePageEnvelope,
    ))


@router.get("/receipts/{receipt_id}", response_model=ReceiptEnvelope, responses=_ERROR_RESPONSES)
def foundry_receipt(
    receipt_id: CanonicalPathId,
    request: Request,
    repository: FoundryRepository = Depends(get_foundry_repository),
) -> Response:
    def operation() -> Response:
        context = _context(repository)
        read = _read_request(
            context=context, query_id="receipt",
            filters=(QueryFilter(name="receipt-id", value=receipt_id),),
        )
        receipt = repository.receipt(receipt_id, read)
        if receipt is None:
            raise FoundryNotFound("receipt absent")
        return _respond(
            request, context=context, response_type="receipt-metadata", payload=receipt,
            envelope_model=ReceiptEnvelope,
        )

    return _execute_read(operation)
