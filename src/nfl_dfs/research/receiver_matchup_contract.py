"""Metric-family-extensible point-in-time annotation contract (v2 pattern).

This is the P0 mechanism from the receiver/defender matchup plan
(`reports/2026-08-22-receiver-defender-matchup-intelligence-implementation-plan.md`
§5.6), generalized per operator request: ONE fail-closed contract pattern —
generation-pinned source identities, lock and maximum-source times, an exact
per-family field dictionary, explicit missingness reasons, a forbidden-
outcome name scan, per-player row uniqueness, and canonical create-once
self-hashing — instantiated per registered METRIC FAMILY. Receiver matchup
is family one; any future paid-metric family (FantasyPoints advanced, SIS
run/pass context, vendor captures) is added by registering a field
dictionary, never by loosening this contract.

A family definition may be PROVISIONAL while its feature layer is being
built; a provisional family validates rows structurally but cannot license
an analysis-grade annotation object. Freezing a family requires the plan's
P3 outcome-blind reality smoke (real accepted task-0 player catalog plus
one governed winner slate) — synthetic fixtures alone never freeze a family
(frozen-chain lesson 1).

Annotations carry no outcome, score-mutation, fill, retrieval, or policy
authority: `realized_outcomes_present=false` and
`active_in_score_matrix=false` are mandatory constants, and field names
that could smuggle a target-week outcome are rejected at family
registration time.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Final


ANNOTATION_CONTRACT_SCHEMA: Final = "corpus-matchup-context-annotations/v2"
FAMILY_DEFINITION_SCHEMA: Final = "corpus-annotation-metric-family/v1"

_SHA = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9\-./]{0,127}$")
_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Defense in depth against smuggled target-week outcomes.  Prior-window
# concession fields are legitimate pre-lock features and use the *_allowed_*
# / *_prior_* vocabulary; these patterns target the target-week vocabulary.
FORBIDDEN_FIELD_PATTERNS: Final = (
    re.compile(r"^(actual|realized|final|settled)_"),
    re.compile(r"_(actual|realized|final|rank|payout|roi|won|winner)$"),
    re.compile(r"^(contest|entry)_(rank|score|payout)"),
)

FIELD_TYPES: Final = frozenset({
    "string", "identifier", "number", "integer", "boolean", "percentile",
})

MISSING_REASON_CODES: Final = (
    "source-absent",
    "below-support-threshold",
    "identity-unresolved",
    "season-boundary-unsupported",
    "vendor-window-incomplete",
    "not-applicable-position",
)


class ReceiverMatchupContractError(ValueError):
    """Raised when an annotation family or object differs from contract."""


def _fail(message: str) -> None:
    raise ReceiverMatchupContractError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _fail(f"{label} must be an array")
    return value


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _identifier(value: object, *, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        _fail(f"{label} must be a bounded lowercase identifier")
    return value


def _timestamp(value: object, *, label: str) -> str:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        _fail(f"{label} must be an exact UTC timestamp")
    return value


def _sha_value(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def normalize_object_identity(
    value: object, *, label: str
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} identity fields differ")
    uri = item["uri"]
    generation = item["generation"]
    size = item["bytes"]
    if (
        type(uri) is not str
        or not (uri.startswith("gs://") or uri.startswith("bq://"))
        or type(generation) is not str
        or not generation
        or type(size) is not int
        or size <= 0
    ):
        _fail(f"{label} identity values differ")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _sha_value(item["sha256"], label=f"{label} sha256"),
        "bytes": size,
    }


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    field_type: str
    nullable: bool
    description: str

    def as_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "field_type": self.field_type,
            "nullable": self.nullable,
            "description": self.description,
        }


def _validate_field_spec(spec: FieldSpec) -> FieldSpec:
    if _FIELD_NAME.fullmatch(spec.name) is None:
        _fail(f"field name {spec.name!r} differs from the naming law")
    for pattern in FORBIDDEN_FIELD_PATTERNS:
        if pattern.search(spec.name):
            _fail(
                f"field name {spec.name!r} matches a forbidden target-week "
                "outcome pattern"
            )
    if spec.field_type not in FIELD_TYPES:
        _fail(f"field {spec.name!r} has unregistered type")
    if type(spec.nullable) is not bool or not spec.description:
        _fail(f"field {spec.name!r} spec is incomplete")
    return spec


@dataclass(frozen=True, slots=True)
class MetricFamily:
    """One versioned, self-hashed paid-metric annotation family."""

    family_id: str
    version: int
    provisional: bool
    source_roles: tuple[str, ...]
    fields: tuple[FieldSpec, ...]
    description: str

    def definition_payload(self) -> dict[str, object]:
        body = {
            "schema_version": FAMILY_DEFINITION_SCHEMA,
            "family_id": self.family_id,
            "version": self.version,
            "provisional": self.provisional,
            "source_roles": list(self.source_roles),
            "fields": [spec.as_payload() for spec in self.fields],
            "missing_reason_codes": list(MISSING_REASON_CODES),
            "description": self.description,
        }
        body["family_definition_sha256"] = canonical_sha256(body)
        return body


def define_metric_family(
    *,
    family_id: str,
    version: int,
    provisional: bool,
    source_roles: Sequence[str],
    fields: Sequence[FieldSpec],
    description: str,
) -> MetricFamily:
    _identifier(family_id, label="family id")
    if type(version) is not int or version < 1:
        _fail("family version must be a positive integer")
    roles = tuple(
        _identifier(role, label="source role") for role in source_roles
    )
    if not roles or len(set(roles)) != len(roles):
        _fail("family source roles must be nonempty and unique")
    validated = tuple(_validate_field_spec(spec) for spec in fields)
    if not validated or len({spec.name for spec in validated}) != len(
        validated
    ):
        _fail("family fields must be nonempty and unique")
    if not description:
        _fail("family description is required")
    return MetricFamily(
        family_id=family_id,
        version=version,
        provisional=bool(provisional),
        source_roles=roles,
        fields=validated,
        description=description,
    )


def _validate_field_value(
    spec: FieldSpec, value: object, *, label: str
) -> None:
    if value is None:
        if not spec.nullable:
            _fail(f"{label}.{spec.name} may not be null")
        return
    if spec.field_type == "string" and type(value) is str and value:
        return
    if spec.field_type == "identifier":
        _identifier(value, label=f"{label}.{spec.name}")
        return
    if spec.field_type == "number" and type(value) in {int, float} and not (
        isinstance(value, bool)
    ):
        if value != value or value in (float("inf"), float("-inf")):
            _fail(f"{label}.{spec.name} must be finite")
        return
    if (
        spec.field_type == "integer"
        and type(value) is int
        and not isinstance(value, bool)
    ):
        return
    if spec.field_type == "boolean" and type(value) is bool:
        return
    if (
        spec.field_type == "percentile"
        and type(value) in {int, float}
        and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
    ):
        return
    _fail(f"{label}.{spec.name} value differs from {spec.field_type}")


def build_annotation_object(
    *,
    family: MetricFamily,
    task_id: str,
    slate_id: str,
    lock_time_utc: str,
    maximum_source_time_utc: str,
    player_catalog_identity: Mapping[str, object],
    source_identities: Mapping[str, Mapping[str, object]],
    rows: Sequence[Mapping[str, object]],
    created_at_utc: str,
) -> dict[str, object]:
    """Build one canonical, self-hashed per-family annotation object."""
    if not isinstance(family, MetricFamily):
        _fail("family must be a registered MetricFamily")
    _identifier(task_id, label="task id")
    _identifier(slate_id, label="slate id")
    lock = _timestamp(lock_time_utc, label="lock time")
    max_source = _timestamp(
        maximum_source_time_utc, label="maximum source time"
    )
    if max_source >= lock:
        _fail("maximum source time must precede the slate lock")
    _timestamp(created_at_utc, label="created at")
    catalog = normalize_object_identity(
        player_catalog_identity, label="player catalog"
    )
    sources = _mapping(source_identities, label="source identities")
    if set(sources) != set(family.source_roles):
        _fail("annotation source roles differ from the family definition")
    normalized_sources = {
        role: normalize_object_identity(
            sources[role], label=f"source {role}"
        )
        for role in family.source_roles
    }
    field_by_name = {spec.name: spec for spec in family.fields}
    seen_players: set[str] = set()
    normalized_rows: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(
        _sequence(rows, label="annotation rows")
    ):
        row = _mapping(raw_row, label=f"annotation row[{ordinal}]")
        expected = {"player_id", "values", "missing"}
        if set(row) != expected:
            _fail(f"annotation row[{ordinal}] fields differ")
        player_id = _identifier(
            row["player_id"], label=f"row[{ordinal}].player_id"
        )
        if player_id in seen_players:
            _fail(f"annotation row repeats player {player_id!r}")
        seen_players.add(player_id)
        values = _mapping(row["values"], label=f"row[{ordinal}].values")
        if set(values) != set(field_by_name):
            _fail(f"row[{ordinal}] value fields differ from the dictionary")
        missing = _mapping(row["missing"], label=f"row[{ordinal}].missing")
        for name, value in values.items():
            spec = field_by_name[name]
            _validate_field_value(spec, value, label=f"row[{ordinal}]")
            if value is None:
                reason = missing.get(name)
                if reason not in MISSING_REASON_CODES:
                    _fail(
                        f"row[{ordinal}].{name} is null without a "
                        "registered missing reason"
                    )
        if set(missing) - {
            name for name, value in values.items() if value is None
        }:
            _fail(f"row[{ordinal}] carries reasons for non-null fields")
        normalized_rows.append({
            "player_id": player_id,
            "values": {name: values[name] for name in sorted(values)},
            "missing": {name: missing[name] for name in sorted(missing)},
        })
    normalized_rows.sort(key=lambda row: row["player_id"])
    body: dict[str, object] = {
        "schema_version": ANNOTATION_CONTRACT_SCHEMA,
        "publication_mode": "create_once",
        "family": family.definition_payload(),
        "task_id": task_id,
        "slate_id": slate_id,
        "lock_time_utc": lock,
        "maximum_source_time_utc": max_source,
        "created_at_utc": created_at_utc,
        "player_catalog": catalog,
        "source_identities": {
            role: normalized_sources[role]
            for role in sorted(normalized_sources)
        },
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
        "realized_outcomes_present": False,
        "active_in_score_matrix": False,
        "analysis_grade": not family.provisional,
        "fill_authority": False,
        "retrieval_authority": False,
        "production_policy_authority": False,
    }
    body["annotation_object_sha256"] = canonical_sha256(body)
    return body


def validate_annotation_bytes(
    raw: bytes,
    *,
    identity: Mapping[str, object] | None = None,
    expected_family: MetricFamily,
    require_analysis_grade: bool = True,
) -> dict[str, object]:
    """Fail-closed validation of one published annotation object."""
    if type(raw) is not bytes or not raw:
        _fail("annotation object must be nonempty raw bytes")
    if identity is not None:
        normalized = normalize_object_identity(
            identity, label="annotation object"
        )
        if (
            len(raw) != normalized["bytes"]
            or sha256(raw).hexdigest() != normalized["sha256"]
        ):
            _fail("annotation object content identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiverMatchupContractError(
            "annotation object is not valid JSON"
        ) from exc
    body = dict(_mapping(parsed, label="annotation object"))
    if canonical_json_bytes(body) != raw:
        _fail("annotation object bytes are not canonical")
    declared = _sha_value(
        body.get("annotation_object_sha256"),
        label="annotation object sha",
    )
    remainder = {
        key: value for key, value in body.items()
        if key != "annotation_object_sha256"
    }
    if canonical_sha256(remainder) != declared:
        _fail("annotation object self-hash differs")
    if body.get("schema_version") != ANNOTATION_CONTRACT_SCHEMA:
        _fail("annotation schema differs")
    if (
        body.get("realized_outcomes_present") is not False
        or body.get("active_in_score_matrix") is not False
        or body.get("fill_authority") is not False
        or body.get("retrieval_authority") is not False
        or body.get("production_policy_authority") is not False
        or body.get("publication_mode") != "create_once"
    ):
        _fail("annotation authority guards differ")
    expected_definition = expected_family.definition_payload()
    if body.get("family") != expected_definition:
        _fail("annotation family definition differs")
    if require_analysis_grade and body.get("analysis_grade") is not True:
        _fail(
            "annotation is provisional; analysis-grade use requires a "
            "frozen family (P3 reality smoke)"
        )
    rebuilt = build_annotation_object(
        family=expected_family,
        task_id=str(body["task_id"]),
        slate_id=str(body["slate_id"]),
        lock_time_utc=str(body["lock_time_utc"]),
        maximum_source_time_utc=str(body["maximum_source_time_utc"]),
        player_catalog_identity=_mapping(
            body["player_catalog"], label="player catalog"
        ),
        source_identities=_mapping(
            body["source_identities"], label="source identities"
        ),
        rows=_sequence(body["rows"], label="annotation rows"),
        created_at_utc=str(body["created_at_utc"]),
    )
    if canonical_json_bytes(rebuilt) != raw:
        _fail("annotation object does not replay from its own contents")
    return body


def receiver_matchup_family_v1(*, provisional: bool = True) -> MetricFamily:
    """Family one: receiver matchup context (plan §5.5, provisional at P0).

    The full role/concession/alignment/shell/defender dictionary freezes at
    P3 together with its feature layer and the outcome-blind reality smoke;
    this provisional registration carries the census-verified core so P1/P2
    builders target exact names from day one.
    """
    fields = (
        FieldSpec("role_label", "string", True, "consensus pre-lock role (WR1/WR2/WR3+/TE1/TE2+)"),
        FieldSpec("role_consensus_score", "percentile", True, "within-team consensus role percentile"),
        FieldSpec("role_component_count", "integer", True, "non-null role components used"),
        FieldSpec("role_supported", "boolean", False, "at least two components and two eligible teammates"),
        FieldSpec("opponent_role_concession_l8", "number", True, "opponent receiving DK allowed to this role, last eight prior games, shrunk"),
        FieldSpec("opponent_role_concession_over_expectation_l8", "number", True, "role concession minus frozen pre-lock expectations, last eight"),
        FieldSpec("wide_route_share_l4", "percentile", True, "receiver wide-alignment route share, W-4..W-1"),
        FieldSpec("slot_route_share_l4", "percentile", True, "receiver slot-alignment route share, W-4..W-1"),
        FieldSpec("defense_wide_vulnerability_l8", "number", True, "SIS wide-alignment defense vulnerability, strictly prior window"),
        FieldSpec("defense_slot_vulnerability_l8", "number", True, "SIS slot-alignment defense vulnerability, strictly prior window"),
        FieldSpec("defender_workload_quality_l8", "number", True, "workload-weighted prior defender quality for the receiver's alignment mix"),
        FieldSpec("defender_evidence_grain", "string", True, "sis-defender-alignment | pfr-nearest-defender | pfr-secondary-group"),
        FieldSpec("top_workload_defender_out", "boolean", True, "opponent's top prior-workload defender inactive at lock"),
        FieldSpec("shell_fit_edge_prior_season", "number", True, "FantasyPoints man/zone shell fit edge, prior season"),
        FieldSpec("matchup_edge_score", "percentile", True, "unweighted mean of supported component percentiles, within slate"),
        FieldSpec("matchup_component_count", "integer", False, "supported matchup components"),
        FieldSpec("easy_coverage_v1", "boolean", True, "frozen easy-coverage law: edge>=0.75 and no supported component below 0.40"),
    )
    return define_metric_family(
        family_id="receiver-matchup",
        version=1,
        provisional=provisional,
        source_roles=(
            "receiver-role-components",
            "defense-role-concessions",
            "sis-defender-alignment",
            "fantasy-points-alignment",
            "fantasy-points-shell-fit",
            "pfr-secondary",
        ),
        fields=fields,
        description=(
            "Point-in-time receiver matchup context: consensus role, "
            "opponent role concessions, alignment fit, defender workload "
            "quality, shell fit, and the frozen easy-coverage descriptor."
        ),
    )


def rb_matchup_family_v1(*, provisional: bool = True) -> MetricFamily:
    """Family two: RB matchup context (rushing + checkdown surfaces)."""
    fields = (
        FieldSpec("role_label", "string", True, "consensus pre-lock role (RB1/RB2/RB3+)"),
        FieldSpec("role_consensus_score", "percentile", True, "within-team consensus role percentile"),
        FieldSpec("role_component_count", "integer", True, "non-null role components used"),
        FieldSpec("role_supported", "boolean", False, "at least two components and two eligible teammates"),
        FieldSpec("opponent_rushing_concession_l8", "number", True, "opponent rushing DK allowed per game to this role, last eight prior games"),
        FieldSpec("opponent_receiving_concession_l8", "number", True, "opponent receiving DK allowed per game to this role (checkdown surface), last eight"),
        FieldSpec("opponent_rdef_epa_per_attempt_l8", "number", True, "opponent run-defense EPA allowed per attempt, strictly prior, attempt-weighted"),
        FieldSpec("opponent_rdef_boom_rate_l8", "number", True, "opponent run-defense boom rate allowed, strictly prior"),
        FieldSpec("matchup_edge_score", "percentile", True, "unweighted mean of supported component percentiles, within slate"),
        FieldSpec("matchup_component_count", "integer", False, "supported matchup components"),
        FieldSpec("easy_ground_matchup_v1", "boolean", True, "frozen law: edge>=0.75 and no supported component below 0.40"),
    )
    return define_metric_family(
        family_id="rb-matchup",
        version=1,
        provisional=provisional,
        source_roles=(
            "rb-role-components",
            "defense-rb-role-concessions",
            "team-run-defense-context",
        ),
        fields=fields,
        description=(
            "Point-in-time RB matchup context: consensus role, opponent "
            "rushing and checkdown-receiving concessions by role, run-"
            "defense unit context, and the frozen easy-ground descriptor."
        ),
    )


def qb_matchup_family_v1(*, provisional: bool = True) -> MetricFamily:
    """Family three: QB matchup context (concession, pressure, secondary)."""
    fields = (
        FieldSpec("opponent_qb_dk_concession_l8", "number", True, "opponent full-QB-DK points allowed per game, last eight prior games"),
        FieldSpec("opponent_pressures_per_game_l8", "number", True, "opponent pressures generated per game, strictly prior (fewer is offense-favorable; orientation applied at percentile time)"),
        FieldSpec("opponent_sacks_per_game_l8", "number", True, "opponent sacks per game, strictly prior"),
        FieldSpec("opponent_secondary_ypt_allowed_l6", "number", True, "opponent DB yards per target allowed, trailing six (production coverage table)"),
        FieldSpec("matchup_edge_score", "percentile", True, "unweighted mean of supported component percentiles, within slate"),
        FieldSpec("matchup_component_count", "integer", False, "supported matchup components"),
        FieldSpec("easy_pass_matchup_v1", "boolean", True, "frozen law: edge>=0.75 and no supported component below 0.40"),
    )
    return define_metric_family(
        family_id="qb-matchup",
        version=1,
        provisional=provisional,
        source_roles=(
            "qb-defense-concessions",
            "pfr-pass-rush-context",
            "secondary-coverage-quality",
        ),
        fields=fields,
        description=(
            "Point-in-time QB matchup context: opponent QB-DK concessions, "
            "pass-rush pressure context, secondary quality, and the frozen "
            "easy-pass descriptor."
        ),
    )


__all__ = [
    "ANNOTATION_CONTRACT_SCHEMA",
    "FAMILY_DEFINITION_SCHEMA",
    "FIELD_TYPES",
    "FORBIDDEN_FIELD_PATTERNS",
    "FieldSpec",
    "MISSING_REASON_CODES",
    "MetricFamily",
    "ReceiverMatchupContractError",
    "build_annotation_object",
    "canonical_json_bytes",
    "canonical_sha256",
    "define_metric_family",
    "normalize_object_identity",
    "qb_matchup_family_v1",
    "rb_matchup_family_v1",
    "receiver_matchup_family_v1",
    "validate_annotation_bytes",
]
