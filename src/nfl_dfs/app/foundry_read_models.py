"""Read models for the versioned Foundry observatory API.

Fixture-backed, bounded, GET-only read layer. The repository protocol is
the seam a later graph/BigQuery projection implements; nothing here can
write, launch, promote, or read a governed outcome. Every payload carries
its evidence tier, denominators, missingness, release identity, and
sanitized provenance references — raw bucket paths and receipt bodies
never leave the server.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from hashlib import sha256
import json
from typing import Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

API_SCHEMA: Final = "foundry-read-api-envelope/v1"
API_VERSION: Final = "v1"
MAX_PAGE_SIZE: Final = 200
DEFAULT_PAGE_SIZE: Final = 50
MAX_RESPONSE_BYTES: Final = 262_144

EvidenceTier = Literal[
    "synthetic-fixture",
    "exploratory",
    "preregistered-retrospective",
    "prospective",
]
Scope = Literal["simulated", "realized", "mixed", "identity-only"]


class FoundryReadError(RuntimeError):
    """Raised when a read cannot satisfy the bounded contract."""


class ReleaseIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)
    data_release: str
    graph_release: str | None = None
    ui_release: str | None = None


class Staleness(BaseModel):
    model_config = ConfigDict(frozen=True)
    generated_at_utc: str
    verified_at_utc: str | None
    age_seconds: int = Field(ge=0)
    stale: bool


class Provenance(BaseModel):
    """Sanitized provenance reference — an opaque application route."""

    model_config = ConfigDict(frozen=True)
    receipt_id: str
    receipt_route: str


class Denominator(BaseModel):
    model_config = ConfigDict(frozen=True)
    unit: str
    total: int = Field(ge=0)
    missing: int = Field(ge=0)
    note: str | None = None


class MetricDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric_id: str
    definition: str
    unit: str


class Release(BaseModel):
    model_config = ConfigDict(frozen=True)
    release_id: str
    kind: Literal["science", "verifier", "deployment-attestation"]
    version: str
    status: Literal["active", "superseded"]
    provenance: Provenance


class Preset(BaseModel):
    model_config = ConfigDict(frozen=True)
    preset_id: str
    kind: Literal["fill", "admission", "retrieval"]
    version: str
    parameters_note: str
    evidence_tier: EvidenceTier
    provenance: Provenance


class StrategyBundle(BaseModel):
    model_config = ConfigDict(frozen=True)
    bundle_id: str
    fill_preset_id: str
    admission_preset_id: str
    retrieval_preset_id: str
    entry_budget: int = Field(ge=1)
    science_release_id: str
    lifecycle: Literal[
        "nominated", "shadow-candidate", "limited-deployment", "rejected"
    ]
    provenance: Provenance


class MetricValue(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric: MetricDefinition
    value: float | int | None
    uncertainty_note: str | None
    denominator: Denominator
    fold: str
    scope: Scope
    evidence_tier: EvidenceTier


class Experiment(BaseModel):
    model_config = ConfigDict(frozen=True)
    experiment_id: str
    tier: Literal["E", "V", "P"]
    purpose: str
    bundle_ids: tuple[str, ...]
    status: Literal["draft", "frozen", "terminal"]
    provenance: Provenance


class Run(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    experiment_id: str
    status: Literal["planned", "running", "accepted", "failed"]
    accepted_task_count: int = Field(ge=0)
    task_count: int = Field(ge=0)
    provenance: Provenance


class Evaluation(BaseModel):
    model_config = ConfigDict(frozen=True)
    evaluation_id: str
    experiment_id: str
    disposition: Literal["books-frozen", "graded", "accepted", "inconclusive"]
    outcome_release_id: str | None
    evidence_tier: EvidenceTier
    provenance: Provenance


class Book(BaseModel):
    model_config = ConfigDict(frozen=True)
    book_id: str
    bundle_id: str
    slate_id: str
    entry_budget: int = Field(ge=1)
    membership_sha256: str
    scope: Scope
    evidence_tier: EvidenceTier
    provenance: Provenance


class CohortComparison(BaseModel):
    model_config = ConfigDict(frozen=True)
    cohort_a: str
    cohort_b: str
    winner_release_id: str | None
    metrics: tuple[MetricValue, ...]


class TraitEnrichment(BaseModel):
    model_config = ConfigDict(frozen=True)
    trait_id: str
    trait_version: str
    cohort: str
    winner_release_id: str | None
    lift: float | None
    support: Denominator
    evidence_tier: EvidenceTier


class LineupDetail(BaseModel):
    model_config = ConfigDict(frozen=True)
    lineup_id: str
    slate_id: str
    roster: tuple[str, ...]
    source_arms: tuple[str, ...]
    admitted_by: tuple[str, ...]
    selected_by: tuple[str, ...]
    realized_note: Literal["unavailable-not-authorized", "graded"]
    provenance: Provenance


class NetworkEdge(BaseModel):
    model_config = ConfigDict(frozen=True)
    source: str
    target: str
    relationship: str
    qualified_inferred: bool


class SourceCoverageRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    source: str
    slate_id: str
    grain: str
    denominator: Denominator
    evidence_tier: EvidenceTier


class ReceiptMeta(BaseModel):
    """Allowlisted sanitized receipt metadata — never a raw body."""

    model_config = ConfigDict(frozen=True)
    receipt_id: str
    receipt_type: str
    status: str
    sha256: str
    generated_at_utc: str


class FoundryStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    graph_available: bool
    accepted_slates: int = Field(ge=0)
    registered_presets: int = Field(ge=0)
    registered_bundles: int = Field(ge=0)
    open_experiments: int = Field(ge=0)
    authority_note: str


class FoundryRepository(Protocol):
    """The projection seam; every method is a bounded read."""

    def status(self) -> FoundryStatus: ...
    def releases(self) -> Sequence[Release]: ...
    def presets(self) -> Sequence[Preset]: ...
    def strategy_bundles(self) -> Sequence[StrategyBundle]: ...
    def experiments(self) -> Sequence[Experiment]: ...
    def experiment_metrics(self, experiment_id: str) -> Sequence[MetricValue]: ...
    def runs(self) -> Sequence[Run]: ...
    def evaluations(self) -> Sequence[Evaluation]: ...
    def book(self, book_id: str) -> Book | None: ...
    def cohort_compare(self, cohort_a: str, cohort_b: str) -> CohortComparison: ...
    def trait_enrichment(self, cohort: str) -> Sequence[TraitEnrichment]: ...
    def lineup_detail(self, slate_id: str, lineup_id: str) -> LineupDetail | None: ...
    def lineup_network(self, lineup_id: str) -> Sequence[NetworkEdge]: ...
    def source_coverage(self) -> Sequence[SourceCoverageRow]: ...
    def receipt(self, receipt_id: str) -> ReceiptMeta | None: ...
    def release_identity(self) -> ReleaseIdentity: ...
    def staleness(self, *, now_utc: str) -> Staleness: ...


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        text = base64.urlsafe_b64decode(cursor.encode()).decode()
    except (ValueError, binascii.Error) as exc:
        raise FoundryReadError("cursor is not decodable") from exc
    if not text.startswith("o:") or not text[2:].isdigit():
        raise FoundryReadError("cursor is not canonical")
    return int(text[2:])


def canonical_body_bytes(body: object) -> bytes:
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def content_etag(body: object) -> str:
    return f'"{sha256(canonical_body_bytes(body)).hexdigest()}"'


def enforce_response_budget(body: object) -> None:
    size = len(canonical_body_bytes(body))
    if size > MAX_RESPONSE_BYTES:
        raise FoundryReadError(
            f"response of {size} bytes exceeds the {MAX_RESPONSE_BYTES}-byte "
            "budget; narrow the page size or filters"
        )


# --------------------------------------------------------------------- #
# Deterministic fixture repository (Tier E, synthetic; no outcome reads) #
# --------------------------------------------------------------------- #

_FIXTURE_GENERATED_AT: Final = "2026-08-25T12:00:00Z"
_SOURCE_ARMS: Final = (
    "incumbent",
    "remove-salary-floor",
    "remove-qb-stack",
    "remove-bring-back",
    "allow-rb-vs-dst",
    "allow-two-rb",
    "remove-all-five-shared-constraints",
)
_T230: Final = (
    "coverage-ge-230-v1",
    "bounded-tail-ladder-ge-210-250-v1",
    "block-robust-bounded-tail-ge-210-250-v1",
    "individual-ge-230-rank-v1",
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
    """Deterministic synthetic projection used until a custodian-supplied
    accepted release is wired through the graph adapter."""

    evidence_tier: Final[EvidenceTier] = "synthetic-fixture"

    def __init__(self, *, graph_available: bool = False) -> None:
        self._graph_available = graph_available

    def status(self) -> FoundryStatus:
        return FoundryStatus(
            graph_available=self._graph_available,
            accepted_slates=54,
            registered_presets=len(self.presets()),
            registered_bundles=len(self.strategy_bundles()),
            open_experiments=1,
            authority_note=(
                "read-only observatory; no run, promotion, or outcome "
                "authority"
            ),
        )

    def releases(self) -> Sequence[Release]:
        return (
            Release(
                release_id="science-release-fixture-001",
                kind="science",
                version="0.1.0",
                status="active",
                provenance=_prov("receipt-science-001"),
            ),
            Release(
                release_id="verifier-release-fixture-001",
                kind="verifier",
                version="0.1.0",
                status="active",
                provenance=_prov("receipt-verifier-001"),
            ),
        )

    def presets(self) -> Sequence[Preset]:
        fills = tuple(
            Preset(
                preset_id=f"fill:r194:{arm}",
                kind="fill",
                version="v12",
                parameters_note="legal-feasibility relaxation arm",
                evidence_tier=self.evidence_tier,
                provenance=_prov(f"receipt-fill-{index}"),
            )
            for index, arm in enumerate(_SOURCE_ARMS)
        )
        retrievals = tuple(
            Preset(
                preset_id=f"retrieval:t230:{name}",
                kind="retrieval",
                version="v1",
                parameters_note="extreme-tail retrieval law",
                evidence_tier=self.evidence_tier,
                provenance=_prov(f"receipt-retrieval-{index}"),
            )
            for index, name in enumerate(_T230)
        )
        admission = (
            Preset(
                preset_id="admission:full-union",
                kind="admission",
                version="v1",
                parameters_note="all-arm union; no bounded shortlist",
                evidence_tier=self.evidence_tier,
                provenance=_prov("receipt-admission-0"),
            ),
        )
        return fills + admission + retrievals

    def strategy_bundles(self) -> Sequence[StrategyBundle]:
        return tuple(
            StrategyBundle(
                bundle_id=f"bundle:{name}:{budget}",
                fill_preset_id="fill:r194:incumbent",
                admission_preset_id="admission:full-union",
                retrieval_preset_id=f"retrieval:t230:{name}",
                entry_budget=budget,
                science_release_id="science-release-fixture-001",
                lifecycle="nominated",
                provenance=_prov(f"receipt-bundle-{name}-{budget}"),
            )
            for name in _T230[:2]
            for budget in (4, 14, 80)
        )

    def experiments(self) -> Sequence[Experiment]:
        return (
            Experiment(
                experiment_id="experiment:core-v1-fixture",
                tier="E",
                purpose="fixture wiring for the observatory read surface",
                bundle_ids=tuple(
                    bundle.bundle_id for bundle in self.strategy_bundles()
                ),
                status="frozen",
                provenance=_prov("receipt-experiment-core-v1"),
            ),
        )

    def experiment_metrics(self, experiment_id: str) -> Sequence[MetricValue]:
        if experiment_id != "experiment:core-v1-fixture":
            return ()
        definition = MetricDefinition(
            metric_id="weekly-maximum-mean",
            definition=(
                "mean over accepted slates of the selected book's maximum "
                "realized-equivalent simulated score"
            ),
            unit="dk_points",
        )
        return tuple(
            MetricValue(
                metric=definition,
                value=168.5 + index * 0.25,
                uncertainty_note="synthetic fixture value; no interval",
                denominator=Denominator(
                    unit="slates", total=54, missing=0, note=None
                ),
                fold=f"R{index}",
                scope="simulated",
                evidence_tier=self.evidence_tier,
            )
            for index in range(3)
        )

    def runs(self) -> Sequence[Run]:
        return (
            Run(
                run_id="run:v12-panel-fixture",
                experiment_id="experiment:core-v1-fixture",
                status="accepted",
                accepted_task_count=54,
                task_count=54,
                provenance=_prov("receipt-run-v12"),
            ),
        )

    def evaluations(self) -> Sequence[Evaluation]:
        return (
            Evaluation(
                evaluation_id="evaluation:core-v1-fixture",
                experiment_id="experiment:core-v1-fixture",
                disposition="books-frozen",
                outcome_release_id=None,
                evidence_tier=self.evidence_tier,
                provenance=_prov("receipt-evaluation-core-v1"),
            ),
        )

    def book(self, book_id: str) -> Book | None:
        bundles = {bundle.bundle_id for bundle in self.strategy_bundles()}
        for bundle_id in bundles:
            candidate = f"book:{bundle_id}:slate:2023-w1"
            if book_id == candidate:
                return Book(
                    book_id=candidate,
                    bundle_id=bundle_id,
                    slate_id="slate:2023-w1",
                    entry_budget=int(bundle_id.rsplit(":", 1)[1]),
                    membership_sha256=_hex(11),
                    scope="simulated",
                    evidence_tier=self.evidence_tier,
                    provenance=_prov("receipt-book-2023-w1"),
                )
        return None

    def cohort_compare(
        self, cohort_a: str, cohort_b: str
    ) -> CohortComparison:
        winner = "winner-release-governed-51" if "winners" in (
            cohort_a,
            cohort_b,
        ) else None
        definition = MetricDefinition(
            metric_id="qb-stack-prevalence",
            definition="fraction of lineups containing QB plus a teammate",
            unit="fraction",
        )
        return CohortComparison(
            cohort_a=cohort_a,
            cohort_b=cohort_b,
            winner_release_id=winner,
            metrics=(
                MetricValue(
                    metric=definition,
                    value=0.84 if cohort_a == "winners" else 0.61,
                    uncertainty_note="synthetic fixture value",
                    denominator=Denominator(
                        unit="lineups",
                        total=51 if cohort_a == "winners" else 400,
                        missing=0,
                        note="governed 51-winner release"
                        if winner
                        else None,
                    ),
                    fold="all-block",
                    scope="identity-only",
                    evidence_tier=self.evidence_tier,
                ),
            ),
        )

    def trait_enrichment(self, cohort: str) -> Sequence[TraitEnrichment]:
        winner = "winner-release-governed-51" if cohort == "winners" else None
        return tuple(
            TraitEnrichment(
                trait_id=trait,
                trait_version="v1",
                cohort=cohort,
                winner_release_id=winner,
                lift=None if trait == "coverage-matchup" else 1.2 + index / 10,
                support=Denominator(
                    unit="lineups",
                    total=51 if winner else 400,
                    missing=17 if trait == "coverage-matchup" else 0,
                    note="missing renders as missing, never zero",
                ),
                evidence_tier=self.evidence_tier,
            )
            for index, trait in enumerate(
                ("qb-stack", "bring-back", "coverage-matchup")
            )
        )

    def lineup_detail(
        self, slate_id: str, lineup_id: str
    ) -> LineupDetail | None:
        if slate_id != "slate:2023-w1" or lineup_id != "lineup:fixture-001":
            return None
        return LineupDetail(
            lineup_id=lineup_id,
            slate_id=slate_id,
            roster=tuple(f"player:00-00{index}" for index in range(9)),
            source_arms=("incumbent", "remove-qb-stack"),
            admitted_by=("admission:full-union",),
            selected_by=("retrieval:t230:coverage-ge-230-v1",),
            realized_note="unavailable-not-authorized",
            provenance=_prov("receipt-lineup-fixture-001"),
        )

    def lineup_network(self, lineup_id: str) -> Sequence[NetworkEdge]:
        if lineup_id != "lineup:fixture-001":
            return ()
        return (
            NetworkEdge(
                source=lineup_id,
                target="player:00-000",
                relationship="CONTAINS_PLAYER",
                qualified_inferred=False,
            ),
            NetworkEdge(
                source="player:00-000",
                target="defender:00-999",
                relationship="HAS_INFERRED_DEFENDER_EXPOSURE",
                qualified_inferred=True,
            ),
        )

    def source_coverage(self) -> Sequence[SourceCoverageRow]:
        return tuple(
            SourceCoverageRow(
                source=source,
                slate_id="slate:2023-w1",
                grain=grain,
                denominator=Denominator(
                    unit="players",
                    total=180,
                    missing=missing,
                    note=None if missing == 0 else "explicitly missing",
                ),
                evidence_tier=self.evidence_tier,
            )
            for source, grain, missing in (
                ("fantasy-points", "player-week", 0),
                ("sis", "route", 12),
                ("pfr", "player-week", 3),
            )
        )

    def receipt(self, receipt_id: str) -> ReceiptMeta | None:
        if not receipt_id.startswith("receipt-"):
            return None
        return ReceiptMeta(
            receipt_id=receipt_id,
            receipt_type="fixture",
            status="accepted",
            sha256=_hex(len(receipt_id)),
            generated_at_utc=_FIXTURE_GENERATED_AT,
        )

    def release_identity(self) -> ReleaseIdentity:
        return ReleaseIdentity(
            data_release="fixture-data-release-001",
            graph_release=None,
            ui_release=None,
        )

    def staleness(self, *, now_utc: str) -> Staleness:
        import datetime as _dt

        generated = _dt.datetime.fromisoformat(
            _FIXTURE_GENERATED_AT.replace("Z", "+00:00")
        )
        now = _dt.datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
        age = max(0, int((now - generated).total_seconds()))
        return Staleness(
            generated_at_utc=_FIXTURE_GENERATED_AT,
            verified_at_utc=_FIXTURE_GENERATED_AT,
            age_seconds=age,
            stale=age > 6 * 3600,
        )
