"""Lossless, fail-closed groundwork for the Millionaire winner registry v2.

Registry v1 intentionally remains immutable.  This module builds a separate
score-only *candidate* ledger from the raw, tracked winner artifacts.  It does
not decide which of several same-week Millionaire contests is the program's
target and it never promotes a locally reported score to an official score.

The important v2 boundary is that ``(season, week)`` is descriptive metadata,
not contest identity.  Every source observation survives independently,
including byte-equivalent rosters and multiple observations for one week.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


CANDIDATE_LEDGER_SCHEMA = "winner-registry-v2-candidate-ledger/1"
TARGET_POLICY_SCHEMA = "winner-registry-v2-target-contest-policy/1"
ADJUDICATION_SCHEMA = "winner-registry-v2-adjudication-receipt/1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCEPTED_CONTEST_FIELDS = (
    "season",
    "week",
    "draftkings_contest_id",
    "contest_name",
    "contest_family",
    "slate_date",
    "lock_time_utc",
    "roster_format",
    "entry_fee_usd",
    "top_prize_usd",
)
_REQUIRED_POLICY_FIELDS = (
    "platform",
    "sport",
    "roster_format",
    "slate_scope",
    "contest_family",
    "selection_rule",
    "multiple_contest_rule",
)
_SCORE_FIELDS = (
    "official_target_winning_score",
    "captured_roster_points_sum",
    "article_or_summary_reported_score",
)


class WinnerRegistryV2Error(ValueError):
    """Raised when candidate or adjudication evidence is not self-proving."""


@dataclass(frozen=True)
class WinnerSourceSpec:
    """Exact parsing contract for one tracked source artifact."""

    relative_path: str
    source_role: str
    season_field: str | None
    default_season: int | None
    week_field: str
    rows_per_observation: int
    roster_points_field: str | None
    reported_score_field: str | None


DEFAULT_SOURCE_SPECS: tuple[WinnerSourceSpec, ...] = (
    WinnerSourceSpec(
        relative_path="reports/milly-winners-2019-2023-2024.csv",
        source_role="user_supplied_roster_capture",
        season_field="season",
        default_season=None,
        week_field="week",
        rows_per_observation=9,
        roster_points_field="fantasy_points",
        reported_score_field=None,
    ),
    WinnerSourceSpec(
        relative_path="reports/milly_rosters_2023_2024.csv",
        source_role="article_derived_roster_capture",
        season_field="season",
        default_season=None,
        week_field="week",
        rows_per_observation=9,
        roster_points_field="pts",
        reported_score_field="winning_score",
    ),
    WinnerSourceSpec(
        relative_path="reports/2025-milly-rosters.csv",
        source_role="user_supplied_roster_capture",
        season_field=None,
        default_season=2025,
        week_field="week",
        rows_per_observation=9,
        roster_points_field="pts",
        reported_score_field=None,
    ),
    WinnerSourceSpec(
        relative_path="reports/2025-milly-winners.csv",
        source_role="summary_derived_score_capture",
        season_field=None,
        default_season=2025,
        week_field="week",
        rows_per_observation=1,
        roster_points_field=None,
        reported_score_field="score",
    ),
)


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON value with one stable, content-identity encoding."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def content_sha256(value: Any) -> str:
    """Return the SHA-256 of :func:`canonical_json_bytes`."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    """Return an exact local content identity without interpreting the file."""
    payload = path.read_bytes()
    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _canonical_decimal(value: str, *, label: str) -> str:
    raw = value.strip()
    if not raw:
        raise WinnerRegistryV2Error(f"{label} is blank")
    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise WinnerRegistryV2Error(f"{label} is not decimal: {value!r}") from exc
    if not parsed.is_finite():
        raise WinnerRegistryV2Error(f"{label} must be finite")
    normalized = format(parsed.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def _decimal_sum(rows: Sequence[Mapping[str, str]], field: str) -> str:
    total = Decimal("0")
    for offset, row in enumerate(rows):
        raw = str(row.get(field, ""))
        try:
            value = Decimal(raw.strip())
        except InvalidOperation as exc:
            raise WinnerRegistryV2Error(
                f"row offset {offset} field {field!r} is not decimal: {raw!r}"
            ) from exc
        if not value.is_finite():
            raise WinnerRegistryV2Error(
                f"row offset {offset} field {field!r} must be finite"
            )
        total += value
    return _canonical_decimal(str(total), label=f"sum({field})")


def _one_reported_score(
    rows: Sequence[Mapping[str, str]], field: str
) -> str:
    values = {
        _canonical_decimal(str(row.get(field, "")), label=field)
        for row in rows
    }
    if len(values) != 1:
        raise WinnerRegistryV2Error(
            f"one source observation has conflicting {field!r}: {sorted(values)}"
        )
    return next(iter(values))


def _artifact_id(relative_path: str, identity: Mapping[str, Any]) -> str:
    return "wsrc2-" + content_sha256(
        {
            "relative_path": relative_path,
            "bytes": identity["bytes"],
            "sha256": identity["sha256"],
        }
    )[:24]


def _observation_id(observation: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in observation.items()
        if key != "observation_id"
    }
    return "wobs2-" + content_sha256(payload)[:32]


def _ledger_hash(ledger: Mapping[str, Any]) -> str:
    return content_sha256(
        {key: value for key, value in ledger.items() if key != "ledger_sha256"}
    )


def _physical_chunks(
    rows: Sequence[tuple[int, dict[str, str]]],
    spec: WinnerSourceSpec,
) -> Iterable[list[tuple[int, dict[str, str]]]]:
    """Yield fixed-roster observations without merging equal week labels."""
    current: list[tuple[int, dict[str, str]]] = []
    current_key: tuple[int, int] | None = None
    for line_number, row in rows:
        season = (
            int(row[spec.season_field])
            if spec.season_field is not None
            else int(spec.default_season or 0)
        )
        week = int(row[spec.week_field])
        key = (season, week)
        if current and (key != current_key or len(current) == spec.rows_per_observation):
            if len(current) != spec.rows_per_observation:
                raise WinnerRegistryV2Error(
                    f"{spec.relative_path} {current_key} has a partial "
                    f"{len(current)}-row observation"
                )
            yield current
            current = []
        current_key = key
        current.append((line_number, row))
    if current:
        if len(current) != spec.rows_per_observation:
            raise WinnerRegistryV2Error(
                f"{spec.relative_path} {current_key} has a partial "
                f"{len(current)}-row observation"
            )
        yield current


def _roster_content_hash(
    rows: Sequence[Mapping[str, str]], spec: WinnerSourceSpec
) -> str | None:
    if spec.roster_points_field is None:
        return None
    excluded = {
        value
        for value in (
            spec.season_field,
            spec.week_field,
            spec.reported_score_field,
        )
        if value is not None
    }
    roster_payload = [
        {key: value for key, value in row.items() if key not in excluded}
        for row in rows
    ]
    return content_sha256(roster_payload)


def _load_source(
    repo_root: Path,
    spec: WinnerSourceSpec,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = repo_root / spec.relative_path
    if not path.is_file():
        raise WinnerRegistryV2Error(f"required source artifact missing: {path}")
    identity = file_identity(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise WinnerRegistryV2Error(f"source artifact has no CSV header: {path}")
        raw_header = list(reader.fieldnames)
        parsed_rows = [
            (line_number, dict(row))
            for line_number, row in enumerate(reader, start=2)
        ]
    if not parsed_rows:
        raise WinnerRegistryV2Error(f"source artifact has no data rows: {path}")

    source_artifact_id = _artifact_id(spec.relative_path, identity)
    artifact = {
        "source_artifact_id": source_artifact_id,
        "repo_relative_path": spec.relative_path,
        "source_role": spec.source_role,
        "format": "text/csv",
        "bytes": identity["bytes"],
        "sha256": identity["sha256"],
        "raw_header": raw_header,
        "physical_layout": {
            "header_row": 1,
            "data_row_range": {
                "start": parsed_rows[0][0],
                "end": parsed_rows[-1][0],
            },
            "data_row_count": len(parsed_rows),
        },
        "interpretation": {
            "season_field": spec.season_field,
            "default_season": spec.default_season,
            "week_field": spec.week_field,
            "rows_per_observation": spec.rows_per_observation,
            "roster_points_field": spec.roster_points_field,
            "reported_score_field": spec.reported_score_field,
        },
    }

    observations: list[dict[str, Any]] = []
    ordinal_by_slate: dict[tuple[int, int], int] = {}
    for chunk in _physical_chunks(parsed_rows, spec):
        lines = [item[0] for item in chunk]
        raw_rows = [item[1] for item in chunk]
        season = (
            int(raw_rows[0][spec.season_field])
            if spec.season_field is not None
            else int(spec.default_season or 0)
        )
        week = int(raw_rows[0][spec.week_field])
        slate_label = (season, week)
        ordinal_by_slate[slate_label] = ordinal_by_slate.get(slate_label, 0) + 1
        captured_sum = (
            _decimal_sum(raw_rows, spec.roster_points_field)
            if spec.roster_points_field is not None
            else None
        )
        reported_score = (
            _one_reported_score(raw_rows, spec.reported_score_field)
            if spec.reported_score_field is not None
            else None
        )
        observation: dict[str, Any] = {
            "source_artifact_id": source_artifact_id,
            "source_observation_ordinal": len(observations) + 1,
            "same_source_slate_ordinal": ordinal_by_slate[slate_label],
            "season": season,
            "week": week,
            "season_week_label": f"{season}-w{week:02d}",
            "contest_identity": {
                "identity_status": "unresolved",
                "season": None,
                "week": None,
                "draftkings_contest_id": None,
                "contest_name": None,
                "contest_family": None,
                "slate_date": None,
                "lock_time_utc": None,
                "roster_format": None,
                "entry_fee_usd": None,
                "top_prize_usd": None,
            },
            "target_policy_match_status": "unresolved",
            "scores": {
                "official_target_winning_score": None,
                "captured_roster_points_sum": captured_sum,
                "article_or_summary_reported_score": reported_score,
            },
            "physical_rows": {
                "start": lines[0],
                "end": lines[-1],
                "count": len(lines),
            },
            "source_record_sha256": content_sha256(raw_rows),
            "roster_content_sha256_excluding_season_week": _roster_content_hash(
                raw_rows, spec
            ),
            "raw_records": raw_rows,
        }
        observation["observation_id"] = _observation_id(observation)
        observations.append(observation)
    return artifact, observations


def build_candidate_ledger(
    repo_root: str | Path,
    *,
    source_specs: Sequence[WinnerSourceSpec] = DEFAULT_SOURCE_SPECS,
) -> dict[str, Any]:
    """Build a deterministic, unadjudicated ledger from every configured row."""
    root = Path(repo_root).resolve()
    artifacts: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for spec in source_specs:
        artifact, source_observations = _load_source(root, spec)
        artifacts.append(artifact)
        observations.extend(source_observations)

    ledger: dict[str, Any] = {
        "schema_version": CANDIDATE_LEDGER_SCHEMA,
        "registry_status": "candidate_only_unadjudicated",
        "uses_realized_outcomes": True,
        "official_target_score_count": 0,
        "source_artifact_count": len(artifacts),
        "source_artifacts": artifacts,
        "observation_count": len(observations),
        "distinct_season_week_label_count": len(
            {(row["season"], row["week"]) for row in observations}
        ),
        "observations": observations,
        "non_identity_warning": (
            "season and week are labels only; neither identifies a contest"
        ),
        "promotion_boundary": (
            "no observation is official or accepted until a frozen target-contest "
            "policy and a fail-closed adjudication receipt validate"
        ),
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    validate_candidate_ledger(ledger)
    return ledger


def validate_candidate_ledger(ledger: Mapping[str, Any]) -> None:
    """Fail closed on mutation, row loss, score conflation, or promotion."""
    if ledger.get("schema_version") != CANDIDATE_LEDGER_SCHEMA:
        raise WinnerRegistryV2Error("unexpected candidate-ledger schema")
    if ledger.get("registry_status") != "candidate_only_unadjudicated":
        raise WinnerRegistryV2Error("candidate ledger has a promoted status")
    if ledger.get("ledger_sha256") != _ledger_hash(ledger):
        raise WinnerRegistryV2Error("candidate ledger content hash mismatch")
    artifacts = ledger.get("source_artifacts")
    observations = ledger.get("observations")
    if not isinstance(artifacts, list) or not isinstance(observations, list):
        raise WinnerRegistryV2Error("ledger artifacts/observations must be lists")
    if ledger.get("source_artifact_count") != len(artifacts):
        raise WinnerRegistryV2Error("source artifact count mismatch")
    if ledger.get("observation_count") != len(observations):
        raise WinnerRegistryV2Error("observation count mismatch")

    artifact_by_id: dict[str, Mapping[str, Any]] = {}
    for artifact in artifacts:
        artifact_id = artifact.get("source_artifact_id")
        if not isinstance(artifact_id, str) or artifact_id in artifact_by_id:
            raise WinnerRegistryV2Error("source artifact IDs are missing or duplicate")
        for field in ("repo_relative_path", "sha256", "bytes", "physical_layout"):
            if artifact.get(field) in (None, ""):
                raise WinnerRegistryV2Error(
                    f"source artifact {artifact_id} missing {field}"
                )
        if not _SHA256_RE.fullmatch(str(artifact["sha256"])):
            raise WinnerRegistryV2Error(f"source artifact {artifact_id} has bad SHA")
        expected_id = _artifact_id(str(artifact["repo_relative_path"]), artifact)
        if artifact_id != expected_id:
            raise WinnerRegistryV2Error(f"source artifact {artifact_id} ID mismatch")
        artifact_by_id[artifact_id] = artifact

    seen: set[str] = set()
    official_count = 0
    for observation in observations:
        observation_id = observation.get("observation_id")
        if not isinstance(observation_id, str) or observation_id in seen:
            raise WinnerRegistryV2Error("observation IDs are missing or duplicate")
        seen.add(observation_id)
        if observation_id != _observation_id(observation):
            raise WinnerRegistryV2Error(f"observation {observation_id} ID mismatch")
        artifact_id = observation.get("source_artifact_id")
        if artifact_id not in artifact_by_id:
            raise WinnerRegistryV2Error(
                f"observation {observation_id} has unknown source artifact"
            )
        raw_records = observation.get("raw_records")
        physical_rows = observation.get("physical_rows")
        if not isinstance(raw_records, list) or not raw_records:
            raise WinnerRegistryV2Error(
                f"observation {observation_id} has no raw records"
            )
        if not isinstance(physical_rows, Mapping):
            raise WinnerRegistryV2Error(
                f"observation {observation_id} has no physical row range"
            )
        if physical_rows.get("count") != len(raw_records):
            raise WinnerRegistryV2Error(
                f"observation {observation_id} raw row count mismatch"
            )
        if physical_rows.get("end") - physical_rows.get("start") + 1 != len(raw_records):
            raise WinnerRegistryV2Error(
                f"observation {observation_id} physical range is not exact"
            )
        if observation.get("source_record_sha256") != content_sha256(raw_records):
            raise WinnerRegistryV2Error(
                f"observation {observation_id} raw-record hash mismatch"
            )
        scores = observation.get("scores")
        if not isinstance(scores, Mapping) or set(scores) != set(_SCORE_FIELDS):
            raise WinnerRegistryV2Error(
                f"observation {observation_id} score fields are not separated"
            )
        if scores["official_target_winning_score"] is not None:
            official_count += 1
            raise WinnerRegistryV2Error(
                f"candidate observation {observation_id} makes an official claim"
            )
        for field in _SCORE_FIELDS[1:]:
            value = scores[field]
            if value is not None:
                _canonical_decimal(str(value), label=field)
        contest = observation.get("contest_identity")
        if not isinstance(contest, Mapping) or contest.get("identity_status") != "unresolved":
            raise WinnerRegistryV2Error(
                f"candidate observation {observation_id} claims contest identity"
            )
    if ledger.get("official_target_score_count") != official_count:
        raise WinnerRegistryV2Error("official score count mismatch")
    distinct_labels = len(
        {(row.get("season"), row.get("week")) for row in observations}
    )
    if ledger.get("distinct_season_week_label_count") != distinct_labels:
        raise WinnerRegistryV2Error("season/week label count mismatch")


def verify_source_files(ledger: Mapping[str, Any], repo_root: str | Path) -> None:
    """Reopen every source and compare exact bytes to the ledger identity."""
    validate_candidate_ledger(ledger)
    root = Path(repo_root).resolve()
    for artifact in ledger["source_artifacts"]:
        path = root / artifact["repo_relative_path"]
        if not path.is_file():
            raise WinnerRegistryV2Error(f"source artifact is missing: {path}")
        actual = file_identity(path)
        expected = {"bytes": artifact["bytes"], "sha256": artifact["sha256"]}
        if actual != expected:
            raise WinnerRegistryV2Error(
                f"source artifact content identity changed: {path}"
            )


def target_contest_policy_template() -> dict[str, Any]:
    """Return the explicit unresolved policy that must precede adjudication."""
    template: dict[str, Any] = {
        "schema_version": TARGET_POLICY_SCHEMA,
        "template_status": "draft_unresolved_do_not_use_for_acceptance",
        "policy_id": None,
        "policy_status": "draft_unresolved",
        "effective_scope": {"first_season": None, "last_season": None},
        "target_definition": {
            "platform": "DraftKings",
            "sport": "NFL",
            "roster_format": "Classic",
            "slate_scope": "Sunday main/common-lock",
            "contest_family": None,
            "selection_rule": None,
            "multiple_contest_rule": None,
        },
        "required_contest_identity_fields": list(_ACCEPTED_CONTEST_FIELDS),
        "required_score_fields": list(_SCORE_FIELDS),
        "official_score_authority": "draftkings_official_contest_export",
        "policy_owner": None,
        "approved_at_utc": None,
        "reason": (
            "Resolve which same-week Millionaire contest is the target before "
            "any observation is accepted. Season/week and highest score are not "
            "selection rules."
        ),
    }
    template["template_sha256"] = content_sha256(template)
    return template


def adjudication_receipt_template() -> dict[str, Any]:
    """Return a non-executable receipt shape; every claim starts pending."""
    template: dict[str, Any] = {
        "schema_version": ADJUDICATION_SCHEMA,
        "template_status": "pending_example_not_an_adjudication",
        "receipt_id": None,
        "receipt_sha256": None,
        "observation_id": None,
        "decision": "pending",
        "target_policy_id": None,
        "target_policy_sha256": None,
        "target_contest_identity": {
            field: None for field in _ACCEPTED_CONTEST_FIELDS
        },
        "scores": {field: None for field in _SCORE_FIELDS},
        "source_evidence": [],
        "adjudicator": {"name": None, "role": None},
        "adjudicated_at_utc": None,
        "reason": None,
    }
    template["template_sha256"] = content_sha256(template)
    return template


def seal_target_contest_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Add deterministic identity/hash fields to a completed policy."""
    sealed = json.loads(json.dumps(policy))
    sealed.pop("template_sha256", None)
    sealed["template_status"] = "operational_policy"
    sealed["policy_status"] = "frozen"
    id_payload = {
        key: value
        for key, value in sealed.items()
        if key not in {"policy_id", "policy_sha256"}
    }
    sealed["policy_id"] = "wtpol2-" + content_sha256(id_payload)[:24]
    sealed["policy_sha256"] = content_sha256(
        {key: value for key, value in sealed.items() if key != "policy_sha256"}
    )
    validate_target_contest_policy(sealed, require_frozen=True)
    return sealed


def validate_target_contest_policy(
    policy: Mapping[str, Any], *, require_frozen: bool
) -> None:
    """Validate a draft template or require an immutable operational policy."""
    if policy.get("schema_version") != TARGET_POLICY_SCHEMA:
        raise WinnerRegistryV2Error("unexpected target-contest-policy schema")
    if not require_frozen:
        if policy.get("policy_status") not in {"draft_unresolved", "frozen"}:
            raise WinnerRegistryV2Error("unknown target policy status")
        return
    if policy.get("policy_status") != "frozen":
        raise WinnerRegistryV2Error("target policy is not frozen")
    target = policy.get("target_definition")
    if not isinstance(target, Mapping):
        raise WinnerRegistryV2Error("target policy has no target definition")
    for field in _REQUIRED_POLICY_FIELDS:
        if target.get(field) in (None, ""):
            raise WinnerRegistryV2Error(f"frozen target policy missing {field}")
    if policy.get("official_score_authority") \
            != "draftkings_official_contest_export":
        raise WinnerRegistryV2Error("frozen target policy weakens score authority")
    scope = policy.get("effective_scope")
    if not isinstance(scope, Mapping):
        raise WinnerRegistryV2Error("frozen target policy has no effective scope")
    try:
        first_season = int(scope["first_season"])
        last_season = int(scope["last_season"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WinnerRegistryV2Error(
            "frozen target policy effective scope is not integral"
        ) from exc
    if first_season > last_season:
        raise WinnerRegistryV2Error("frozen target policy effective scope is reversed")
    for field in ("policy_owner", "approved_at_utc", "reason"):
        if policy.get(field) in (None, ""):
            raise WinnerRegistryV2Error(f"frozen target policy missing {field}")
    if set(policy.get("required_contest_identity_fields", [])) \
            != set(_ACCEPTED_CONTEST_FIELDS):
        raise WinnerRegistryV2Error(
            "frozen target policy weakens contest identity requirements"
        )
    if set(policy.get("required_score_fields", [])) != set(_SCORE_FIELDS):
        raise WinnerRegistryV2Error(
            "frozen target policy weakens separated score requirements"
        )
    policy_id = policy.get("policy_id")
    policy_sha = policy.get("policy_sha256")
    if not isinstance(policy_id, str) or not policy_id.startswith("wtpol2-"):
        raise WinnerRegistryV2Error("frozen target policy has no deterministic ID")
    if not isinstance(policy_sha, str) or not _SHA256_RE.fullmatch(policy_sha):
        raise WinnerRegistryV2Error("frozen target policy has no SHA-256")
    expected_sha = content_sha256(
        {key: value for key, value in policy.items() if key != "policy_sha256"}
    )
    if policy_sha != expected_sha:
        raise WinnerRegistryV2Error("target policy content hash mismatch")
    id_payload = {
        key: value
        for key, value in policy.items()
        if key not in {"policy_id", "policy_sha256"}
    }
    expected_id = "wtpol2-" + content_sha256(id_payload)[:24]
    if policy_id != expected_id:
        raise WinnerRegistryV2Error("target policy deterministic ID mismatch")


def seal_adjudication_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Add a deterministic ID and SHA to a completed adjudication receipt."""
    sealed = json.loads(json.dumps(receipt))
    sealed.pop("template_sha256", None)
    sealed["template_status"] = "operational_receipt"
    id_payload = {
        key: value
        for key, value in sealed.items()
        if key not in {"receipt_id", "receipt_sha256"}
    }
    sealed["receipt_id"] = "wadj2-" + content_sha256(id_payload)[:32]
    sealed["receipt_sha256"] = content_sha256(
        {key: value for key, value in sealed.items() if key != "receipt_sha256"}
    )
    return sealed


def _validate_evidence_identity(evidence: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "evidence_id",
        "source_uri",
        "authority_class",
        "content_sha256",
        "bytes",
        "captured_at_utc",
        "physical_rows",
        "supports",
    ):
        if evidence.get(field) in (None, "", []):
            raise WinnerRegistryV2Error(f"{label} missing {field}")
    if not _SHA256_RE.fullmatch(str(evidence["content_sha256"])):
        raise WinnerRegistryV2Error(f"{label} has invalid content SHA-256")
    if not isinstance(evidence["bytes"], int) or evidence["bytes"] <= 0:
        raise WinnerRegistryV2Error(f"{label} has invalid byte count")
    rows = evidence["physical_rows"]
    if not isinstance(rows, Mapping) or not isinstance(rows.get("start"), int) \
            or not isinstance(rows.get("end"), int) \
            or rows["start"] > rows["end"]:
        raise WinnerRegistryV2Error(f"{label} has invalid physical row range")
    if not isinstance(evidence["supports"], list):
        raise WinnerRegistryV2Error(f"{label} supports must be a list")


def validate_adjudication_receipt(
    receipt: Mapping[str, Any],
    *,
    ledger: Mapping[str, Any],
    target_policy: Mapping[str, Any],
) -> None:
    """Validate one receipt and fail closed on every accepted claim.

    Pending/rejected receipts retain evidence but cannot enter an accepted
    winner cohort.  An accepted receipt must bind one candidate observation,
    the frozen target policy, exact contest identity, the original candidate
    artifact, and an official DraftKings contest export supporting both the
    contest ID and the official score.
    """
    validate_candidate_ledger(ledger)
    if receipt.get("schema_version") != ADJUDICATION_SCHEMA:
        raise WinnerRegistryV2Error("unexpected adjudication-receipt schema")
    decision = receipt.get("decision")
    if decision not in {"pending", "rejected", "accepted"}:
        raise WinnerRegistryV2Error("unknown adjudication decision")
    if decision != "accepted":
        return

    validate_target_contest_policy(target_policy, require_frozen=True)
    observation_by_id = {
        row["observation_id"]: row for row in ledger["observations"]
    }
    observation_id = receipt.get("observation_id")
    if observation_id not in observation_by_id:
        raise WinnerRegistryV2Error("accepted receipt has unknown observation")
    observation = observation_by_id[observation_id]
    if receipt.get("target_policy_id") != target_policy["policy_id"] \
            or receipt.get("target_policy_sha256") != target_policy["policy_sha256"]:
        raise WinnerRegistryV2Error("accepted receipt does not bind frozen policy")

    contest = receipt.get("target_contest_identity")
    if not isinstance(contest, Mapping):
        raise WinnerRegistryV2Error("accepted receipt has no contest identity")
    for field in _ACCEPTED_CONTEST_FIELDS:
        if contest.get(field) in (None, ""):
            raise WinnerRegistryV2Error(
                f"accepted receipt contest identity missing {field}"
            )
    try:
        contest_season = int(contest["season"])
        contest_week = int(contest["week"])
    except (TypeError, ValueError) as exc:
        raise WinnerRegistryV2Error(
            "accepted receipt contest season/week are not integers"
        ) from exc
    if (contest_season, contest_week) != (
        observation["season"],
        observation["week"],
    ):
        raise WinnerRegistryV2Error(
            "accepted receipt contest season/week disagree with observation"
        )
    effective_scope = target_policy["effective_scope"]
    if not (
        int(effective_scope["first_season"])
        <= contest_season
        <= int(effective_scope["last_season"])
    ):
        raise WinnerRegistryV2Error(
            "accepted receipt contest is outside frozen policy effective scope"
        )
    target_definition = target_policy["target_definition"]
    if contest["contest_family"] != target_definition["contest_family"]:
        raise WinnerRegistryV2Error(
            "accepted receipt contest family disagrees with frozen policy"
        )
    if contest["roster_format"] != target_definition["roster_format"]:
        raise WinnerRegistryV2Error(
            "accepted receipt roster format disagrees with frozen policy"
        )

    scores = receipt.get("scores")
    if not isinstance(scores, Mapping) or set(scores) != set(_SCORE_FIELDS):
        raise WinnerRegistryV2Error("accepted receipt score fields are not separated")
    official_score = scores["official_target_winning_score"]
    if official_score is None:
        raise WinnerRegistryV2Error("accepted receipt has no official target score")
    official_score = _canonical_decimal(
        str(official_score), label="official_target_winning_score"
    )
    for field in _SCORE_FIELDS[1:]:
        if scores[field] != observation["scores"][field]:
            raise WinnerRegistryV2Error(
                f"accepted receipt rewrites candidate {field}"
            )

    evidence_rows = receipt.get("source_evidence")
    if not isinstance(evidence_rows, list) or not evidence_rows:
        raise WinnerRegistryV2Error("accepted receipt has no source evidence")
    for index, evidence in enumerate(evidence_rows):
        if not isinstance(evidence, Mapping):
            raise WinnerRegistryV2Error("source evidence must be objects")
        _validate_evidence_identity(evidence, label=f"source_evidence[{index}]")

    artifact = next(
        row
        for row in ledger["source_artifacts"]
        if row["source_artifact_id"] == observation["source_artifact_id"]
    )
    candidate_supported = any(
        evidence.get("source_artifact_id") == artifact["source_artifact_id"]
        and evidence.get("content_sha256") == artifact["sha256"]
        and evidence.get("bytes") == artifact["bytes"]
        and "candidate_observation" in evidence.get("supports", [])
        for evidence in evidence_rows
    )
    if not candidate_supported:
        raise WinnerRegistryV2Error(
            "accepted receipt does not bind the original candidate artifact"
        )

    official_supported = any(
        evidence.get("authority_class") == "draftkings_official_contest_export"
        and "official_target_winning_score" in evidence.get("supports", [])
        and "target_contest_identity" in evidence.get("supports", [])
        and str(evidence.get("extracted_fields", {}).get(
            "draftkings_contest_id", ""))
        == str(contest["draftkings_contest_id"])
        and _canonical_decimal(
            str(evidence.get("extracted_fields", {}).get(
                "official_target_winning_score", "")),
            label="official evidence score",
        ) == official_score
        for evidence in evidence_rows
        if isinstance(evidence.get("extracted_fields"), Mapping)
    )
    if not official_supported:
        raise WinnerRegistryV2Error(
            "official score lacks a matching DraftKings contest-export source"
        )

    adjudicator = receipt.get("adjudicator")
    if not isinstance(adjudicator, Mapping) or adjudicator.get("name") in (None, "") \
            or adjudicator.get("role") in (None, ""):
        raise WinnerRegistryV2Error("accepted receipt has no adjudicator identity")
    for field in ("adjudicated_at_utc", "reason"):
        if receipt.get(field) in (None, ""):
            raise WinnerRegistryV2Error(f"accepted receipt missing {field}")

    receipt_id = receipt.get("receipt_id")
    receipt_sha = receipt.get("receipt_sha256")
    id_payload = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_id", "receipt_sha256"}
    }
    expected_id = "wadj2-" + content_sha256(id_payload)[:32]
    expected_sha = content_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    if receipt_id != expected_id or receipt_sha != expected_sha:
        raise WinnerRegistryV2Error("accepted receipt deterministic identity mismatch")


def accepted_observations(
    ledger: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    target_policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return accepted records only after every receipt validates."""
    validate_candidate_ledger(ledger)
    accepted: list[dict[str, Any]] = []
    seen_observations: set[str] = set()
    seen_contest_ids: set[str] = set()
    seen_policy_slates: set[tuple[int, int]] = set()
    by_id = {row["observation_id"]: row for row in ledger["observations"]}
    for receipt in receipts:
        validate_adjudication_receipt(
            receipt, ledger=ledger, target_policy=target_policy
        )
        if receipt.get("decision") != "accepted":
            continue
        observation_id = str(receipt["observation_id"])
        if observation_id in seen_observations:
            raise WinnerRegistryV2Error(
                f"multiple accepted receipts for observation {observation_id}"
            )
        contest = receipt["target_contest_identity"]
        contest_id = str(contest["draftkings_contest_id"])
        slate = (int(contest["season"]), int(contest["week"]))
        if contest_id in seen_contest_ids:
            raise WinnerRegistryV2Error(
                f"duplicate accepted target contest ID {contest_id}"
            )
        if slate in seen_policy_slates:
            raise WinnerRegistryV2Error(
                f"multiple accepted target contests for policy slate {slate}"
            )
        seen_observations.add(observation_id)
        seen_contest_ids.add(contest_id)
        seen_policy_slates.add(slate)
        accepted.append(
            {
                "observation": by_id[observation_id],
                "adjudication_receipt": dict(receipt),
            }
        )
    return accepted
