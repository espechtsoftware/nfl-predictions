"""Strict, bounded read contracts for the Foundry observatory API.

The production repository is deliberately unavailable until a separately
reviewed release-bound adapter is configured.  The fixture repository in this
module is synthetic and is only suitable for explicit dependency injection in
offline tests.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
import datetime as dt
from hashlib import sha256
import json
import math
from typing import Annotated, Final, Generic, Literal, Never, Protocol, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

API_SCHEMA: Final = "foundry-read-api-envelope/v1"
API_VERSION: Final = "v1"
MAX_PAGE_SIZE: Final = 200
DEFAULT_PAGE_SIZE: Final = 50
MAX_RESPONSE_BYTES: Final = 262_144
MAX_CURSOR_LENGTH: Final = 512
MAX_CURSOR_OFFSET: Final = 100_000_000
MAX_TOTAL_ROWS: Final = 100_000_000
MAX_QUERY_DEADLINE_MS: Final = 5_000
DEFAULT_QUERY_DEADLINE_MS: Final = 2_000
MAX_ABS_METRIC_VALUE: Final = 1_000_000_000_000

ID_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}$"
TOKEN_PATTERN: Final = r"^[a-z0-9][a-z0-9._-]{0,63}$"
SHA_PATTERN: Final = r"^[0-9a-f]{64}$"
UTC_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"

CanonicalId = Annotated[str, Field(min_length=1, max_length=128, pattern=ID_PATTERN)]
CanonicalToken = Annotated[
    str, Field(min_length=1, max_length=64, pattern=TOKEN_PATTERN)
]
Sha256Hex = Annotated[str, Field(min_length=64, max_length=64, pattern=SHA_PATTERN)]
BoundedText = Annotated[str, Field(min_length=1, max_length=1_024)]
ShortText = Annotated[str, Field(min_length=1, max_length=256)]
UtcTimestamp = Annotated[str, Field(min_length=20, max_length=20)]

EvidenceTier = Literal[
    "synthetic-fixture",
    "exploratory",
    "preregistered-retrospective",
    "prospective",
]
Scope = Literal["simulated", "realized", "mixed", "identity-only"]
CatalogQuery = Literal[
    "status",
    "releases",
    "presets",
    "strategy-bundles",
    "experiments",
    "experiment-metrics",
    "runs",
    "evaluations",
    "book",
    "cohort-compare",
    "trait-enrichment",
    "lineup-detail",
    "lineup-network",
    "source-coverage",
    "receipt",
]


class FoundryReadError(RuntimeError):
    """Base failure at the public read boundary."""


class FoundryInvalidRequest(FoundryReadError):
    """A bounded client cursor or filter is invalid."""


class FoundryBackendUnavailable(FoundryReadError):
    """No release-bound projection backend is available."""


class FoundryContractError(FoundryReadError):
    """An adapter result violates the strict projection contract."""


class FoundryResponseBudgetError(FoundryContractError):
    """A response exceeds the licensed serialized budget."""


class FoundryNotFound(FoundryReadError):
    """A canonical requested entity is absent from the bound release."""


class StrictReadModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        allow_inf_nan=False,
        revalidate_instances="always",
        strict=True,
    )


def _real_utc(value: str) -> str:
    try:
        dt.datetime.strptime(value, UTC_FORMAT)
    except ValueError as exc:
        raise ValueError("timestamp is not real second-precision UTC") from exc
    return value


class ReleaseIdentity(StrictReadModel):
    data_release: CanonicalId
    graph_release: CanonicalId | None = None
    ui_release: CanonicalId | None = None


class Staleness(StrictReadModel):
    generated_at_utc: UtcTimestamp
    verified_at_utc: UtcTimestamp | None
    age_seconds: int = Field(ge=0, le=315_576_000)
    stale: bool

    @field_validator("generated_at_utc", "verified_at_utc")
    @classmethod
    def timestamps_are_real(cls, value: str | None) -> str | None:
        return None if value is None else _real_utc(value)

    @model_validator(mode="after")
    def verification_is_ordered(self) -> Staleness:
        if self.verified_at_utc is not None and self.verified_at_utc < self.generated_at_utc:
            raise ValueError("verification precedes generation")
        return self


class AuthorityContext(StrictReadModel):
    evidence_tier: EvidenceTier
    scope: Scope
    authority: Literal["synthetic-fixture", "release-bound-read"]
    outcome_authorized: bool
    note: BoundedText

    @model_validator(mode="after")
    def fixture_is_outcome_free(self) -> AuthorityContext:
        if self.authority == "synthetic-fixture" and self.outcome_authorized:
            raise ValueError("synthetic fixture claims outcome authority")
        if self.scope in {"realized", "mixed"} and not self.outcome_authorized:
            raise ValueError("outcome scope lacks outcome authority")
        return self


class Provenance(StrictReadModel):
    """Sanitized pointer to an opaque application route, never a bucket URI."""

    receipt_id: CanonicalId
    receipt_route: Annotated[str, Field(min_length=26, max_length=160)]

    @model_validator(mode="after")
    def route_matches_receipt(self) -> Provenance:
        expected = f"/api/v1/foundry/receipts/{self.receipt_id}"
        if self.receipt_route != expected:
            raise ValueError("receipt route does not match receipt id")
        return self


class Denominator(StrictReadModel):
    unit: CanonicalToken
    total: int = Field(ge=0, le=MAX_TOTAL_ROWS)
    missing: int = Field(ge=0, le=MAX_TOTAL_ROWS)
    note: BoundedText | None = None

    @model_validator(mode="after")
    def missing_is_subset(self) -> Denominator:
        if self.missing > self.total:
            raise ValueError("missing exceeds total")
        return self


class MetricDefinition(StrictReadModel):
    metric_id: CanonicalId
    definition: BoundedText
    unit: CanonicalToken


class Release(StrictReadModel):
    release_id: CanonicalId
    kind: Literal["science", "verifier", "deployment-attestation"]
    version: ShortText
    status: Literal["active", "superseded"]
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance


class Preset(StrictReadModel):
    preset_id: CanonicalId
    kind: Literal["fill", "admission", "retrieval"]
    version: ShortText
    parameters_note: BoundedText
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance


class StrategyBundle(StrictReadModel):
    bundle_id: CanonicalId
    fill_preset_id: CanonicalId
    admission_preset_id: CanonicalId
    retrieval_preset_id: CanonicalId
    entry_budget: int = Field(ge=1, le=1_000)
    science_release_id: CanonicalId
    lifecycle: Literal[
        "nominated", "shadow-candidate", "limited-deployment", "rejected"
    ]
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance


class MetricValue(StrictReadModel):
    metric: MetricDefinition
    value: float | int | None
    uncertainty_note: BoundedText | None
    denominator: Denominator
    fold: CanonicalId
    scope: Scope
    outcome_release_id: CanonicalId | None = None
    evidence_tier: EvidenceTier
    provenance: Provenance

    @field_validator("value")
    @classmethod
    def value_is_finite(cls, value: float | int | None):
        if isinstance(value, bool):
            raise ValueError("metric value is boolean")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("metric value is non-finite")
        if value is not None and abs(value) > MAX_ABS_METRIC_VALUE:
            raise ValueError("metric value exceeds numeric bound")
        return value

    @model_validator(mode="after")
    def scope_matches_outcome(self) -> MetricValue:
        if (self.scope in {"realized", "mixed"}) != (self.outcome_release_id is not None):
            raise ValueError("metric scope and outcome release differ")
        return self


class Experiment(StrictReadModel):
    experiment_id: CanonicalId
    tier: Literal["E", "V", "P"]
    purpose: BoundedText
    bundle_ids: tuple[CanonicalId, ...] = Field(max_length=128)
    status: Literal["draft", "frozen", "terminal"]
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance


class Run(StrictReadModel):
    run_id: CanonicalId
    experiment_id: CanonicalId
    status: Literal["planned", "running", "accepted", "failed"]
    accepted_task_count: int = Field(ge=0, le=100_000)
    task_count: int = Field(ge=0, le=100_000)
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance

    @model_validator(mode="after")
    def task_census_is_coherent(self) -> Run:
        if self.accepted_task_count > self.task_count:
            raise ValueError("accepted tasks exceed total tasks")
        if self.status == "accepted" and (
            self.task_count == 0 or self.accepted_task_count != self.task_count
        ):
            raise ValueError("accepted run is incomplete")
        return self


class Evaluation(StrictReadModel):
    evaluation_id: CanonicalId
    experiment_id: CanonicalId
    disposition: Literal["books-frozen", "graded", "accepted", "inconclusive"]
    outcome_release_id: CanonicalId | None
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance

    @model_validator(mode="after")
    def disposition_is_coherent(self) -> Evaluation:
        if self.disposition in {"graded", "accepted"} and self.outcome_release_id is None:
            raise ValueError("graded evaluation lacks outcome release")
        if self.disposition == "books-frozen" and self.outcome_release_id is not None:
            raise ValueError("ungraded evaluation carries outcome release")
        if (self.scope in {"realized", "mixed"}) != (self.outcome_release_id is not None):
            raise ValueError("evaluation scope and outcome release differ")
        return self


class Book(StrictReadModel):
    book_id: CanonicalId
    bundle_id: CanonicalId
    slate_id: CanonicalId
    entry_budget: int = Field(ge=1, le=1_000)
    membership_sha256: Sha256Hex
    scope: Scope
    outcome_release_id: CanonicalId | None = None
    evidence_tier: EvidenceTier
    provenance: Provenance

    @model_validator(mode="after")
    def scope_matches_outcome(self) -> Book:
        if (self.scope in {"realized", "mixed"}) != (self.outcome_release_id is not None):
            raise ValueError("book scope and outcome release differ")
        return self


class CohortComparison(StrictReadModel):
    cohort_a: CanonicalId
    cohort_b: CanonicalId
    winner_release_id: CanonicalId | None
    outcome_release_id: CanonicalId | None = None
    metrics: tuple[MetricValue, ...] = Field(max_length=64)
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance

    @model_validator(mode="after")
    def winner_is_release_bound(self) -> CohortComparison:
        has_winner = "winner" in self.cohort_a.lower() or "winner" in self.cohort_b.lower()
        if has_winner != (self.winner_release_id is not None):
            raise ValueError("winner cohort and release identity differ")
        if (self.scope in {"realized", "mixed"}) != (self.outcome_release_id is not None):
            raise ValueError("cohort scope and outcome release differ")
        return self


class TraitEnrichment(StrictReadModel):
    trait_id: CanonicalId
    trait_version: ShortText
    cohort: CanonicalId
    winner_release_id: CanonicalId | None
    outcome_release_id: CanonicalId | None = None
    lift: float | None
    support: Denominator
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance

    @field_validator("lift")
    @classmethod
    def lift_is_finite(cls, value: float | None):
        if value is not None and not math.isfinite(value):
            raise ValueError("trait lift is non-finite")
        if value is not None and abs(value) > MAX_ABS_METRIC_VALUE:
            raise ValueError("trait lift exceeds numeric bound")
        return value

    @model_validator(mode="after")
    def winner_is_release_bound(self) -> TraitEnrichment:
        if ("winner" in self.cohort.lower()) != (self.winner_release_id is not None):
            raise ValueError("winner cohort and release identity differ")
        if (self.scope in {"realized", "mixed"}) != (self.outcome_release_id is not None):
            raise ValueError("trait scope and outcome release differ")
        return self


class LineupDetail(StrictReadModel):
    lineup_id: CanonicalId
    slate_id: CanonicalId
    roster: tuple[CanonicalId, ...] = Field(min_length=9, max_length=9)
    source_arms: tuple[CanonicalId, ...] = Field(max_length=32)
    admitted_by: tuple[CanonicalId, ...] = Field(max_length=32)
    selected_by: tuple[CanonicalId, ...] = Field(max_length=32)
    realized_note: Literal["unavailable-not-authorized", "graded"]
    outcome_release_id: CanonicalId | None = None
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance

    @model_validator(mode="after")
    def grade_is_release_bound(self) -> LineupDetail:
        graded = self.realized_note == "graded"
        if graded != (self.outcome_release_id is not None):
            raise ValueError("lineup grade and outcome release differ")
        if graded != (self.scope in {"realized", "mixed"}):
            raise ValueError("lineup grade and scope differ")
        return self


class NetworkEdge(StrictReadModel):
    source: CanonicalId
    target: CanonicalId
    relationship: CanonicalId
    qualified_inferred: bool
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance


class SourceCoverageRow(StrictReadModel):
    source: CanonicalId
    slate_id: CanonicalId
    grain: CanonicalId
    denominator: Denominator
    evidence_tier: EvidenceTier
    scope: Scope
    provenance: Provenance


class ReceiptMeta(StrictReadModel):
    receipt_id: CanonicalId
    receipt_type: CanonicalToken
    status: Literal["accepted", "superseded", "rejected"]
    sha256: Sha256Hex
    generation: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[0-9]+$")]
    bytes: int = Field(ge=1, le=10_000_000_000)
    generated_at_utc: UtcTimestamp

    @field_validator("generated_at_utc")
    @classmethod
    def timestamp_is_real(cls, value: str) -> str:
        return _real_utc(value)


class FoundryStatus(StrictReadModel):
    graph_available: bool
    accepted_slates: int = Field(ge=0, le=10_000)
    registered_presets: int = Field(ge=0, le=100_000)
    registered_bundles: int = Field(ge=0, le=100_000)
    open_experiments: int = Field(ge=0, le=100_000)
    authority_note: BoundedText
    evidence_tier: EvidenceTier
    scope: Scope


class QueryFilter(StrictReadModel):
    name: CanonicalToken
    value: CanonicalId


class ReadRequest(StrictReadModel):
    query_id: CatalogQuery
    filters: tuple[QueryFilter, ...] = Field(max_length=16)
    release_sha256: Sha256Hex
    deadline_ms: int = Field(ge=1, le=MAX_QUERY_DEADLINE_MS)
    hard_row_cap: int = Field(ge=1, le=MAX_PAGE_SIZE)

    @model_validator(mode="after")
    def filters_are_canonical(self) -> ReadRequest:
        keys = [(item.name, item.value) for item in self.filters]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("filters are not sorted and unique")
        return self


class PageRequest(ReadRequest):
    offset: int = Field(ge=0, le=MAX_CURSOR_OFFSET)
    limit: int = Field(ge=1, le=MAX_PAGE_SIZE)

    @model_validator(mode="after")
    def cap_matches_page(self) -> PageRequest:
        if self.hard_row_cap != self.limit:
            raise ValueError("hard row cap differs from page limit")
        return self


RowT = TypeVar("RowT", bound=BaseModel)


class RepositoryPage(StrictReadModel, Generic[RowT]):
    rows: tuple[RowT, ...] = Field(max_length=MAX_PAGE_SIZE)
    total: int = Field(ge=0, le=MAX_TOTAL_ROWS)
    offset: int = Field(ge=0, le=MAX_CURSOR_OFFSET)
    next_offset: int | None = Field(default=None, ge=1, le=MAX_CURSOR_OFFSET)

    @model_validator(mode="after")
    def census_is_coherent(self) -> RepositoryPage[RowT]:
        consumed = self.offset + len(self.rows)
        if consumed > self.total:
            raise ValueError("page rows exceed total")
        if self.next_offset is None and consumed < self.total:
            raise ValueError("page omits a required next offset")
        if self.next_offset is not None and (
            self.next_offset != consumed or self.next_offset >= self.total
        ):
            raise ValueError("next offset is inconsistent")
        return self


class PagePayload(StrictReadModel, Generic[RowT]):
    rows: tuple[RowT, ...] = Field(max_length=MAX_PAGE_SIZE)
    total: int = Field(ge=0, le=MAX_TOTAL_ROWS)
    offset: int = Field(ge=0, le=MAX_CURSOR_OFFSET)


PayloadT = TypeVar("PayloadT")


class Envelope(StrictReadModel, Generic[PayloadT]):
    schema_version: Literal["foundry-read-api-envelope/v1"] = API_SCHEMA
    api_version: Literal["v1"] = API_VERSION
    response_type: CanonicalId
    release: ReleaseIdentity
    staleness: Staleness
    authority: AuthorityContext
    evidence_note: BoundedText
    read_only: Literal[True] = True
    payload: PayloadT
    next_cursor: Annotated[str, Field(max_length=MAX_CURSOR_LENGTH)] | None = None


ErrorReason = Literal[
    "backend-unavailable",
    "projection-contract-invalid",
    "response-budget-exceeded",
    "invalid-request",
    "not-found",
]


class ErrorEnvelope(StrictReadModel):
    schema_version: Literal["foundry-read-api-envelope/v1"] = API_SCHEMA
    api_version: Literal["v1"] = API_VERSION
    response_type: Literal["degraded", "invalid-request", "not-found"]
    reason_code: ErrorReason
    detail: ShortText
    read_only: Literal[True] = True


class CursorState(StrictReadModel):
    api_version: Literal["v1"] = API_VERSION
    query_id: CatalogQuery
    filters_sha256: Sha256Hex
    release_sha256: Sha256Hex
    offset: int = Field(ge=0, le=MAX_CURSOR_OFFSET)


def canonical_body_bytes(body: object) -> bytes:
    try:
        return json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise FoundryContractError("value is not canonical JSON") from exc


def canonical_sha256(body: object) -> str:
    return sha256(canonical_body_bytes(body)).hexdigest()


def release_sha256(release: ReleaseIdentity) -> str:
    return canonical_sha256(release.model_dump(mode="json"))


def canonical_filters(filters: Sequence[QueryFilter]) -> tuple[QueryFilter, ...]:
    retained = tuple(sorted(filters, key=lambda item: (item.name, item.value)))
    if len(retained) > 16 or len(retained) != len(
        {(item.name, item.value) for item in retained}
    ):
        raise FoundryInvalidRequest("filters are not bounded and unique")
    return retained


def filters_sha256(filters: Sequence[QueryFilter]) -> str:
    return canonical_sha256(
        [row.model_dump(mode="json") for row in canonical_filters(filters)]
    )


def encode_cursor(
    *,
    offset: int,
    query_id: CatalogQuery,
    filters: Sequence[QueryFilter],
    release: ReleaseIdentity,
) -> str:
    state = CursorState(
        query_id=query_id,
        filters_sha256=filters_sha256(filters),
        release_sha256=release_sha256(release),
        offset=offset,
    )
    return base64.urlsafe_b64encode(
        canonical_body_bytes(state.model_dump(mode="json"))
    ).decode("ascii").rstrip("=")


def decode_cursor(
    cursor: str | None,
    *,
    query_id: CatalogQuery,
    filters: Sequence[QueryFilter],
    release: ReleaseIdentity,
) -> int:
    if cursor is None:
        return 0
    if len(cursor) > MAX_CURSOR_LENGTH:
        raise FoundryInvalidRequest("cursor exceeds bound")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != cursor:
            raise FoundryInvalidRequest("cursor is not canonical base64url")
        state = CursorState.model_validate(json.loads(raw.decode("utf-8")))
    except FoundryInvalidRequest:
        raise
    except (UnicodeError, ValueError, TypeError, binascii.Error, ValidationError) as exc:
        raise FoundryInvalidRequest("cursor is not canonical") from exc
    if state.query_id != query_id:
        raise FoundryInvalidRequest("cursor query differs")
    if state.filters_sha256 != filters_sha256(filters):
        raise FoundryInvalidRequest("cursor filters differ")
    if state.release_sha256 != release_sha256(release):
        raise FoundryInvalidRequest("cursor release differs")
    return state.offset


def content_etag(body: object) -> str:
    return f'"{canonical_sha256(body)}"'


def enforce_response_budget(body: object) -> None:
    size = len(canonical_body_bytes(body))
    if size > MAX_RESPONSE_BYTES:
        raise FoundryResponseBudgetError(
            f"response of {size} bytes exceeds {MAX_RESPONSE_BYTES} bytes"
        )


class FoundryRepository(Protocol):
    """Release-bound read seam. Every collection method is query-bounded."""

    def release_identity(self) -> ReleaseIdentity: ...
    def staleness(self, *, now_utc: str) -> Staleness: ...
    def authority(self) -> AuthorityContext: ...
    def status(self, request: ReadRequest) -> FoundryStatus: ...
    def releases(self, request: PageRequest) -> RepositoryPage[Release]: ...
    def presets(self, request: PageRequest) -> RepositoryPage[Preset]: ...
    def strategy_bundles(self, request: PageRequest) -> RepositoryPage[StrategyBundle]: ...
    def experiments(self, request: PageRequest) -> RepositoryPage[Experiment]: ...
    def experiment_metrics(self, experiment_id: str, request: PageRequest) -> RepositoryPage[MetricValue]: ...
    def runs(self, request: PageRequest) -> RepositoryPage[Run]: ...
    def evaluations(self, request: PageRequest) -> RepositoryPage[Evaluation]: ...
    def book(self, book_id: str, request: ReadRequest) -> Book | None: ...
    def cohort_compare(self, cohort_a: str, cohort_b: str, request: ReadRequest) -> CohortComparison: ...
    def trait_enrichment(self, cohort: str, request: PageRequest) -> RepositoryPage[TraitEnrichment]: ...
    def lineup_detail(self, slate_id: str, lineup_id: str, request: ReadRequest) -> LineupDetail | None: ...
    def lineup_network(self, lineup_id: str, request: PageRequest) -> RepositoryPage[NetworkEdge]: ...
    def source_coverage(self, request: PageRequest) -> RepositoryPage[SourceCoverageRow]: ...
    def receipt(self, receipt_id: str, request: ReadRequest) -> ReceiptMeta | None: ...


class UnavailableFoundryRepository:
    """Fail-closed production default until a reviewed adapter is supplied."""

    @staticmethod
    def _unavailable(*_args: object, **_kwargs: object) -> Never:
        raise FoundryBackendUnavailable("release-bound repository is not configured")

    release_identity = _unavailable
    staleness = _unavailable
    authority = _unavailable
    status = _unavailable
    releases = _unavailable
    presets = _unavailable
    strategy_bundles = _unavailable
    experiments = _unavailable
    experiment_metrics = _unavailable
    runs = _unavailable
    evaluations = _unavailable
    book = _unavailable
    cohort_compare = _unavailable
    trait_enrichment = _unavailable
    lineup_detail = _unavailable
    lineup_network = _unavailable
    source_coverage = _unavailable
    receipt = _unavailable


# Explicit synthetic test fixture ------------------------------------------------

_FIXTURE_TIME: Final = "2026-08-25T12:00:00Z"
_ARMS: Final = (
    "incumbent", "remove-salary-floor", "remove-qb-stack", "remove-bring-back",
    "allow-rb-vs-dst", "allow-two-rb", "remove-all-five-shared-constraints",
)
_RETRIEVALS: Final = (
    "coverage-ge-230-v1", "bounded-tail-ladder-ge-210-250-v1",
    "block-robust-bounded-tail-ge-210-250-v1", "individual-ge-230-rank-v1",
    "support-switched-policy-v1",
)


def _hex(seed: int) -> str:
    return sha256(f"foundry-fixture-{seed}".encode()).hexdigest()


def _prov(receipt_id: str) -> Provenance:
    return Provenance(
        receipt_id=receipt_id,
        receipt_route=f"/api/v1/foundry/receipts/{receipt_id}",
    )


class FixtureFoundryRepository:
    """Deterministic, unmistakably synthetic dependency for offline tests."""

    evidence_tier: Final[EvidenceTier] = "synthetic-fixture"

    def __init__(self, *, graph_available: bool = False) -> None:
        self._graph_available = graph_available

    def release_identity(self) -> ReleaseIdentity:
        return ReleaseIdentity(data_release="fixture-data-release-001")

    def authority(self) -> AuthorityContext:
        return AuthorityContext(
            evidence_tier=self.evidence_tier,
            scope="identity-only",
            authority="synthetic-fixture",
            outcome_authorized=False,
            note="explicit synthetic test fixture; no governed source or outcome was read",
        )

    def staleness(self, *, now_utc: str) -> Staleness:
        generated = dt.datetime.strptime(_FIXTURE_TIME, UTC_FORMAT)
        now = dt.datetime.strptime(_real_utc(now_utc), UTC_FORMAT)
        if now < generated:
            raise FoundryContractError("fixture clock precedes generation")
        age = int((now - generated).total_seconds())
        return Staleness(
            generated_at_utc=_FIXTURE_TIME,
            verified_at_utc=_FIXTURE_TIME,
            age_seconds=age,
            stale=age > 21_600,
        )

    def _check(self, request: ReadRequest, query_id: CatalogQuery) -> None:
        if request.query_id != query_id:
            raise FoundryContractError("cross-query request")
        if request.release_sha256 != release_sha256(self.release_identity()):
            raise FoundryContractError("cross-release request")

    @staticmethod
    def _page(rows: Sequence[RowT], request: PageRequest) -> RepositoryPage[RowT]:
        window = tuple(rows[request.offset : request.offset + request.limit])
        consumed = request.offset + len(window)
        return RepositoryPage(
            rows=window,
            total=len(rows),
            offset=request.offset,
            next_offset=consumed if consumed < len(rows) else None,
        )

    def _presets(self) -> tuple[Preset, ...]:
        common = dict(evidence_tier=self.evidence_tier, scope="simulated")
        fills = tuple(
            Preset(
                preset_id=f"fill:fixture:r194:{arm}", kind="fill", version="v12-fixture",
                parameters_note="synthetic feasibility arm",
                provenance=_prov(f"receipt-fixture-fill-{i}"), **common,
            )
            for i, arm in enumerate(_ARMS)
        )
        admission = (
            Preset(
                preset_id="admission:fixture-full-union", kind="admission",
                version="v1-fixture", parameters_note="synthetic all-arm union",
                provenance=_prov("receipt-fixture-admission-0"), **common,
            ),
        )
        retrievals = tuple(
            Preset(
                preset_id=f"retrieval:fixture:t230:{name}", kind="retrieval",
                version="v1-fixture", parameters_note="synthetic tail retrieval",
                provenance=_prov(f"receipt-fixture-retrieval-{i}"), **common,
            )
            for i, name in enumerate(_RETRIEVALS)
        )
        return fills + admission + retrievals

    def _bundles(self) -> tuple[StrategyBundle, ...]:
        return tuple(
            StrategyBundle(
                bundle_id=f"bundle:fixture:{name}:{budget}",
                fill_preset_id="fill:fixture:r194:incumbent",
                admission_preset_id="admission:fixture-full-union",
                retrieval_preset_id=f"retrieval:fixture:t230:{name}",
                entry_budget=budget,
                science_release_id="fixture-science-release-001",
                lifecycle="nominated", evidence_tier=self.evidence_tier,
                scope="simulated", provenance=_prov(f"receipt-fixture-bundle-{i}-{budget}"),
            )
            for i, name in enumerate(_RETRIEVALS[:2]) for budget in (4, 14, 80)
        )

    def status(self, request: ReadRequest) -> FoundryStatus:
        self._check(request, "status")
        return FoundryStatus(
            graph_available=self._graph_available, accepted_slates=54,
            registered_presets=13, registered_bundles=6, open_experiments=1,
            authority_note="synthetic fixture; no run, promotion, or outcome authority",
            evidence_tier=self.evidence_tier, scope="identity-only",
        )

    def releases(self, request: PageRequest) -> RepositoryPage[Release]:
        self._check(request, "releases")
        rows = tuple(
            Release(
                release_id=f"fixture-{kind}-release-001", kind=kind,
                version="0.1.0-fixture", status="active",
                evidence_tier=self.evidence_tier, scope="identity-only",
                provenance=_prov(f"receipt-fixture-{kind}-001"),
            )
            for kind in ("science", "verifier")
        )
        return self._page(rows, request)

    def presets(self, request: PageRequest) -> RepositoryPage[Preset]:
        self._check(request, "presets")
        return self._page(self._presets(), request)

    def strategy_bundles(self, request: PageRequest) -> RepositoryPage[StrategyBundle]:
        self._check(request, "strategy-bundles")
        return self._page(self._bundles(), request)

    def experiments(self, request: PageRequest) -> RepositoryPage[Experiment]:
        self._check(request, "experiments")
        rows = (
            Experiment(
                experiment_id="experiment:fixture-core-v1", tier="E",
                purpose="synthetic observatory contract fixture",
                bundle_ids=tuple(row.bundle_id for row in self._bundles()), status="frozen",
                evidence_tier=self.evidence_tier, scope="simulated",
                provenance=_prov("receipt-fixture-experiment-core-v1"),
            ),
        )
        return self._page(rows, request)

    def experiment_metrics(self, experiment_id: str, request: PageRequest) -> RepositoryPage[MetricValue]:
        self._check(request, "experiment-metrics")
        expected = (QueryFilter(name="experiment-id", value=experiment_id),)
        if request.filters != expected:
            raise FoundryContractError("experiment filter differs")
        rows: tuple[MetricValue, ...] = ()
        if experiment_id == "experiment:fixture-core-v1":
            definition = MetricDefinition(
                metric_id="weekly-maximum-mean",
                definition="synthetic mean of selected-book simulated maxima",
                unit="dk_points",
            )
            rows = tuple(
                MetricValue(
                    metric=definition, value=168.5 + i * 0.25,
                    uncertainty_note="synthetic fixture value; no interval",
                    denominator=Denominator(unit="slates", total=54, missing=0),
                    fold=f"R{i}", scope="simulated", evidence_tier=self.evidence_tier,
                    provenance=_prov(f"receipt-fixture-metric-{i}"),
                )
                for i in range(3)
            )
        return self._page(rows, request)

    def runs(self, request: PageRequest) -> RepositoryPage[Run]:
        self._check(request, "runs")
        return self._page((Run(
            run_id="run:fixture-v12-panel", experiment_id="experiment:fixture-core-v1",
            status="accepted", accepted_task_count=54, task_count=54,
            evidence_tier=self.evidence_tier, scope="simulated",
            provenance=_prov("receipt-fixture-run-v12"),
        ),), request)

    def evaluations(self, request: PageRequest) -> RepositoryPage[Evaluation]:
        self._check(request, "evaluations")
        return self._page((Evaluation(
            evaluation_id="evaluation:fixture-core-v1",
            experiment_id="experiment:fixture-core-v1", disposition="books-frozen",
            outcome_release_id=None, evidence_tier=self.evidence_tier, scope="simulated",
            provenance=_prov("receipt-fixture-evaluation-core-v1"),
        ),), request)

    def book(self, book_id: str, request: ReadRequest) -> Book | None:
        self._check(request, "book")
        if request.filters != (QueryFilter(name="book-id", value=book_id),):
            raise FoundryContractError("book filter differs")
        for bundle in self._bundles():
            candidate = f"book:{bundle.bundle_id}:slate:2023-w1"
            if candidate == book_id:
                return Book(
                    book_id=candidate, bundle_id=bundle.bundle_id, slate_id="slate:2023-w1",
                    entry_budget=bundle.entry_budget, membership_sha256=_hex(11),
                    scope="simulated", evidence_tier=self.evidence_tier,
                    provenance=_prov("receipt-fixture-book-2023-w1"),
                )
        return None

    def cohort_compare(self, cohort_a: str, cohort_b: str, request: ReadRequest) -> CohortComparison:
        self._check(request, "cohort-compare")
        expected = canonical_filters((
            QueryFilter(name="cohort-a", value=cohort_a),
            QueryFilter(name="cohort-b", value=cohort_b),
        ))
        if request.filters != expected:
            raise FoundryContractError("cohort filters differ")
        winner = "fixture-winner-release-51" if (
            "winner" in cohort_a.lower() or "winner" in cohort_b.lower()
        ) else None
        metric = MetricValue(
            metric=MetricDefinition(
                metric_id="qb-stack-prevalence",
                definition="synthetic fraction containing QB plus teammate", unit="fraction",
            ),
            value=0.84 if "winner" in cohort_a.lower() else 0.61,
            uncertainty_note="synthetic fixture value",
            denominator=Denominator(unit="lineups", total=51 if winner else 400, missing=0),
            fold="all-block", scope="identity-only", evidence_tier=self.evidence_tier,
            provenance=_prov("receipt-fixture-cohort-metric"),
        )
        return CohortComparison(
            cohort_a=cohort_a, cohort_b=cohort_b, winner_release_id=winner,
            outcome_release_id=None,
            metrics=(metric,), evidence_tier=self.evidence_tier, scope="identity-only",
            provenance=_prov("receipt-fixture-cohort-comparison"),
        )

    def trait_enrichment(self, cohort: str, request: PageRequest) -> RepositoryPage[TraitEnrichment]:
        self._check(request, "trait-enrichment")
        if request.filters != (QueryFilter(name="cohort", value=cohort),):
            raise FoundryContractError("trait filter differs")
        winner = "fixture-winner-release-51" if "winner" in cohort.lower() else None
        rows = tuple(
            TraitEnrichment(
                trait_id=trait, trait_version="v1-fixture", cohort=cohort,
                winner_release_id=winner, outcome_release_id=None,
                lift=None if trait == "coverage-matchup" else 1.2 + i / 10,
                support=Denominator(
                    unit="lineups", total=51 if winner else 400,
                    missing=17 if trait == "coverage-matchup" else 0,
                    note="missing is explicit, never zero",
                ),
                evidence_tier=self.evidence_tier, scope="identity-only",
                provenance=_prov(f"receipt-fixture-trait-{i}"),
            )
            for i, trait in enumerate(("qb-stack", "bring-back", "coverage-matchup"))
        )
        return self._page(rows, request)

    def lineup_detail(self, slate_id: str, lineup_id: str, request: ReadRequest) -> LineupDetail | None:
        self._check(request, "lineup-detail")
        expected = canonical_filters((
            QueryFilter(name="lineup-id", value=lineup_id),
            QueryFilter(name="slate-id", value=slate_id),
        ))
        if request.filters != expected:
            raise FoundryContractError("lineup filters differ")
        if (slate_id, lineup_id) != ("slate:2023-w1", "lineup:fixture-001"):
            return None
        return LineupDetail(
            lineup_id=lineup_id, slate_id=slate_id,
            roster=tuple(f"player:00-00{i}" for i in range(9)),
            source_arms=("incumbent", "remove-qb-stack"),
            admitted_by=("admission:fixture-full-union",),
            selected_by=("retrieval:fixture:t230:coverage-ge-230-v1",),
            realized_note="unavailable-not-authorized", evidence_tier=self.evidence_tier,
            scope="simulated", provenance=_prov("receipt-fixture-lineup-001"),
        )

    def lineup_network(self, lineup_id: str, request: PageRequest) -> RepositoryPage[NetworkEdge]:
        self._check(request, "lineup-network")
        if request.filters != (QueryFilter(name="lineup-id", value=lineup_id),):
            raise FoundryContractError("network filter differs")
        rows: tuple[NetworkEdge, ...] = ()
        if lineup_id == "lineup:fixture-001":
            rows = (
                NetworkEdge(
                    source=lineup_id, target="player:00-000", relationship="CONTAINS_PLAYER",
                    qualified_inferred=False, evidence_tier=self.evidence_tier,
                    scope="identity-only", provenance=_prov("receipt-fixture-network-0"),
                ),
                NetworkEdge(
                    source="player:00-000", target="defender:00-999",
                    relationship="HAS_INFERRED_DEFENDER_EXPOSURE", qualified_inferred=True,
                    evidence_tier=self.evidence_tier, scope="identity-only",
                    provenance=_prov("receipt-fixture-network-1"),
                ),
            )
        return self._page(rows, request)

    def source_coverage(self, request: PageRequest) -> RepositoryPage[SourceCoverageRow]:
        self._check(request, "source-coverage")
        rows = tuple(
            SourceCoverageRow(
                source=source, slate_id="slate:2023-w1", grain=grain,
                denominator=Denominator(
                    unit="players", total=180, missing=missing,
                    note=None if missing == 0 else "explicitly missing",
                ),
                evidence_tier=self.evidence_tier, scope="identity-only",
                provenance=_prov(f"receipt-fixture-source-{i}"),
            )
            for i, (source, grain, missing) in enumerate((
                ("fantasy-points", "player-week", 0), ("sis", "route", 12),
                ("pfr", "player-week", 3),
            ))
        )
        return self._page(rows, request)

    def receipt(self, receipt_id: str, request: ReadRequest) -> ReceiptMeta | None:
        self._check(request, "receipt")
        if request.filters != (QueryFilter(name="receipt-id", value=receipt_id),):
            raise FoundryContractError("receipt filter differs")
        if not receipt_id.startswith("receipt-fixture-"):
            return None
        return ReceiptMeta(
            receipt_id=receipt_id, receipt_type="fixture", status="accepted",
            sha256=_hex(len(receipt_id)), generation=str(1_788_000_000_000_000 + len(receipt_id)),
            bytes=1_024 + len(receipt_id), generated_at_utc=_FIXTURE_TIME,
        )
