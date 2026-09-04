"""Outcome-blind Week-1 participation-mixture selection and rehearsal.

The historical PREREG-054 result changed only the *judge*: every arm used the
same D800 candidate population, while Questionable/Doubtful players were
zeroed in a deterministic fraction of selection worlds.  This module ports
that narrow estimand to the live boundary.  It deliberately does not generate
lineups, read outcomes, or publish/enter a book.

The public helpers provide three fail-closed boundaries:

* a timestamped, content-bound injury/practice snapshot over the complete
  candidate player universe;
* the frozen walk-forward beta-smoothed P(active) map; and
* deterministic P_CTRL/P_MIX exact-K80 selection plus the real A5 prefixes.

If any designation is stale, unknown, unmapped, or inconsistent with the
candidate pool, certification fails.  The caller must then retain P_CTRL for
paid entries; this module never silently guesses a participation probability.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import math
import re
from typing import Final

import numpy as np

from .generation_exposure import canonical_sha256


SNAPSHOT_SCHEMA_VERSION: Final = "week1-participation-snapshot/v1"
MAP_SCHEMA_VERSION: Final = "week1-participation-map/v1"
SELECTION_SCHEMA_VERSION: Final = "week1-participation-selection/v1"
REHEARSAL_SCHEMA_VERSION: Final = "week1-participation-rehearsal/v1"
SEASON: Final = 2026
WEEK: Final = 1
DRAFT_GROUP_ID: Final = "151307"
LOCK_UTC: Final = "2026-09-13T17:00:00+00:00"
EXACT_K: Final = 80
A5_PREFIXES: Final = (3, 10, 20, 57)
ALPHA: Final = 2.0
REGIME_START: Final = 2022
PROVIDER_ABSENCE_SEMANTICS: Final = (
    "not-listed-means-no-active-designation"
)
NORMALIZATION_CONTRACT: Final = "injury-status-practice-aliases-v1"
MAP_VERSION: Final = "prereg054-live-alpha2-v1"

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PLAYER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_LINEUP_ID = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_STATUS_ALIASES: Final = {
    "": None,
    "NONE": None,
    "HEALTHY": None,
    "Q": "Questionable",
    "QUESTIONABLE": "Questionable",
    "D": "Doubtful",
    "DOUBTFUL": "Doubtful",
    "O": "Out",
    "OUT": "Out",
}
_PRACTICE_ALIASES: Final = {
    "": None,
    "NONE": None,
    "DNP": 0,
    "DID NOT PRACTICE": 0,
    "LIMITED": 1,
    "LIMITED PARTICIPATION": 1,
    "FULL": 2,
    "FULL PARTICIPATION": 2,
}


class Week1ParticipationMixtureError(ValueError):
    """A live P_MIX input or receipt violates the frozen boundary."""


def _fail(message: str) -> None:
    raise Week1ParticipationMixtureError(message)


def _timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value or value.strip() != value:
        _fail(f"{label} must be a canonical timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Week1ParticipationMixtureError(
            f"{label} must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} must be timezone-aware")
    utc = parsed.astimezone(timezone.utc)
    if value != utc.isoformat():
        _fail(f"{label} must use canonical UTC representation")
    return utc


def _player_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _PLAYER_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical player ID")
    return value


def _digest(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _lineup_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _LINEUP_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical lineup-v1 ID")
    return value


def _normalize_status(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail("raw injury status must be a string or null")
    key = value.strip().upper()
    if key not in _STATUS_ALIASES:
        _fail(f"unknown injury status {value!r}")
    return _STATUS_ALIASES[key]


def _normalize_practice(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is int:
        if value not in {0, 1, 2}:
            _fail("numeric practice level must be 0, 1, or 2")
        return value
    if not isinstance(value, str):
        _fail("raw practice level must be a string, integer, or null")
    key = value.strip().upper()
    if key not in _PRACTICE_ALIASES:
        _fail(f"unknown practice level {value!r}")
    return _PRACTICE_ALIASES[key]


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    header = f"{array.dtype.str}|{','.join(map(str, array.shape))}|".encode()
    return hashlib.sha256(header + array.tobytes()).hexdigest()


def _snapshot_hash(body: Mapping[str, object]) -> str:
    return canonical_sha256(dict(body))


def build_prelock_snapshot_v1(
    *,
    player_ids: Sequence[str],
    observations: Sequence[Mapping[str, object]],
    provider: str,
    provider_absence_semantics: str,
    provider_observed_at: str,
    ingested_at: str,
    cutoff_at: str,
    max_snapshot_age_seconds: int,
    raw_artifact: Mapping[str, object],
) -> dict[str, object]:
    """Build a complete, explicit no-designation-aware pre-lock snapshot."""

    ordered_ids = [_player_id(value, label="candidate player ID") for value in player_ids]
    if len(ordered_ids) != len(set(ordered_ids)) or not ordered_ids:
        _fail("candidate player universe must be nonempty and unique")
    if not isinstance(provider, str) or not provider.strip():
        _fail("snapshot provider must be nonempty")
    if provider_absence_semantics != PROVIDER_ABSENCE_SEMANTICS:
        _fail(
            "provider absence semantics must explicitly certify that an "
            "unlisted player has no active designation"
        )
    if type(max_snapshot_age_seconds) is not int or max_snapshot_age_seconds < 1:
        _fail("maximum snapshot age must be a positive integer")

    observed = _timestamp(provider_observed_at, label="provider observed time")
    ingested = _timestamp(ingested_at, label="ingestion time")
    cutoff = _timestamp(cutoff_at, label="build cutoff")
    lock = _timestamp(LOCK_UTC, label="Week-1 lock")
    if observed > ingested or ingested > cutoff or cutoff >= lock:
        _fail("snapshot chronology is not observed <= ingested <= cutoff < lock")
    age_seconds = int((cutoff - observed).total_seconds())
    if age_seconds > max_snapshot_age_seconds:
        _fail("designation snapshot is stale at the declared build cutoff")

    artifact = dict(raw_artifact)
    if set(artifact) != {"uri", "generation", "sha256", "bytes"}:
        _fail("raw snapshot artifact identity fields differ")
    uri = artifact.get("uri")
    generation = artifact.get("generation")
    byte_count = artifact.get("bytes")
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        _fail("raw snapshot artifact must be a GCS URI")
    if not isinstance(generation, str) or not generation.isdigit() or int(generation) < 1:
        _fail("raw snapshot artifact generation is invalid")
    if type(byte_count) is not int or byte_count < 1:
        _fail("raw snapshot artifact byte count is invalid")
    artifact = {
        "uri": uri,
        "generation": generation,
        "sha256": _digest(artifact.get("sha256"), label="raw artifact SHA-256"),
        "bytes": byte_count,
    }

    player_id_set = set(ordered_ids)
    by_player: dict[str, Mapping[str, object]] = {}
    for raw in observations:
        if not isinstance(raw, Mapping):
            _fail("snapshot observation must be a mapping")
        if set(raw) != {
            "player_id", "injury_status", "practice_level", "source_modified_at"
        }:
            _fail("snapshot observation fields differ")
        player = _player_id(raw.get("player_id"), label="observation player ID")
        if player in by_player:
            _fail("snapshot observations repeat a player")
        if player not in player_id_set:
            _fail("snapshot observation is outside the candidate player universe")
        source_modified = raw.get("source_modified_at")
        if source_modified is not None:
            modified = _timestamp(source_modified, label="source modified time")
            if modified > observed:
                _fail("source modified time follows provider observation time")
        by_player[player] = raw

    rows: list[dict[str, object]] = []
    for player in ordered_ids:
        raw = by_player.get(player)
        raw_status = None if raw is None else raw.get("injury_status")
        raw_practice = None if raw is None else raw.get("practice_level")
        rows.append({
            "player_id": player,
            "provider_row_present": raw is not None,
            "raw_injury_status": raw_status,
            "raw_practice_level": raw_practice,
            "injury_status": _normalize_status(raw_status),
            "practice_level": _normalize_practice(raw_practice),
            "source_modified_at": None if raw is None else raw.get("source_modified_at"),
        })

    body: dict[str, object] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "season": SEASON,
        "week": WEEK,
        "draft_group_id": DRAFT_GROUP_ID,
        "provider": provider.strip(),
        "provider_absence_semantics": provider_absence_semantics,
        "provider_observed_at": provider_observed_at,
        "ingested_at": ingested_at,
        "cutoff_at": cutoff_at,
        "lock_utc": LOCK_UTC,
        "max_snapshot_age_seconds": max_snapshot_age_seconds,
        "snapshot_age_seconds": age_seconds,
        "complete_candidate_player_universe": True,
        "raw_artifact": artifact,
        "rows": rows,
        "fallback_policy": "certification-failure-retains-p-ctrl",
        "outcome_fields_read": [],
    }
    body["snapshot_sha256"] = _snapshot_hash(body)
    return body


def validate_prelock_snapshot_v1(
    value: object, *, player_ids: Sequence[str]
) -> dict[str, object]:
    """Validate a snapshot by exact reconstruction and content identity."""

    if not isinstance(value, Mapping):
        _fail("participation snapshot must be a mapping")
    snapshot = dict(value)
    retained = snapshot.pop("snapshot_sha256", None)
    _digest(retained, label="snapshot SHA-256")
    if retained != _snapshot_hash(snapshot):
        _fail("snapshot SHA-256 differs")
    if (
        snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
        or snapshot.get("season") != SEASON
        or snapshot.get("week") != WEEK
        or snapshot.get("draft_group_id") != DRAFT_GROUP_ID
        or snapshot.get("lock_utc") != LOCK_UTC
        or snapshot.get("complete_candidate_player_universe") is not True
        or snapshot.get("fallback_policy") != "certification-failure-retains-p-ctrl"
        or snapshot.get("outcome_fields_read") != []
    ):
        _fail("participation snapshot boundary differs")
    rows = snapshot.get("rows")
    if not isinstance(rows, list):
        _fail("participation snapshot rows must be a list")
    expected = [_player_id(item, label="candidate player ID") for item in player_ids]
    observed_ids = [row.get("player_id") for row in rows if isinstance(row, Mapping)]
    if observed_ids != expected or len(rows) != len(expected):
        _fail("snapshot rows do not exactly cover the ordered candidate universe")
    # Re-run time and normalization checks rather than trusting derived fields.
    rebuilt = build_prelock_snapshot_v1(
        player_ids=expected,
        observations=[
            {
                "player_id": row["player_id"],
                "injury_status": row["raw_injury_status"],
                "practice_level": row["raw_practice_level"],
                "source_modified_at": row["source_modified_at"],
            }
            for row in rows
            if row.get("provider_row_present") is True
        ],
        provider=str(snapshot.get("provider", "")),
        provider_absence_semantics=str(
            snapshot.get("provider_absence_semantics", "")
        ),
        provider_observed_at=str(snapshot.get("provider_observed_at", "")),
        ingested_at=str(snapshot.get("ingested_at", "")),
        cutoff_at=str(snapshot.get("cutoff_at", "")),
        max_snapshot_age_seconds=snapshot.get("max_snapshot_age_seconds"),
        raw_artifact=snapshot.get("raw_artifact", {}),
    )
    if rebuilt != value:
        _fail("participation snapshot does not replay exactly")
    return dict(rebuilt)


def _class_name(status: str, practice_level: int | None) -> str:
    bucket = "none" if practice_level is None else str(practice_level)
    return f"{status}|{bucket}"


def fit_participation_map_v1(
    history: Sequence[Mapping[str, object]],
    *,
    source_artifact_sha256: str,
    target_season: int = SEASON,
) -> dict[str, object]:
    """Fit the frozen alpha=2 empirical map using only prior-season labels."""

    if type(target_season) is not int or target_season != SEASON:
        _fail("live participation map target season must be 2026")
    source_sha256 = _digest(
        source_artifact_sha256,
        label="participation-history source artifact SHA-256",
    )
    retained: list[tuple[int, str, bool]] = []
    for ordinal, raw in enumerate(history):
        if not isinstance(raw, Mapping) or set(raw) != {
            "season", "injury_status", "practice_level", "was_active"
        }:
            _fail(f"participation history[{ordinal}] fields differ")
        season = raw.get("season")
        if type(season) is not int or season < REGIME_START or season >= target_season:
            _fail("participation history must be from 2022 through 2025")
        status = _normalize_status(raw.get("injury_status"))
        practice = _normalize_practice(raw.get("practice_level"))
        active = raw.get("was_active")
        if status not in {"Questionable", "Doubtful"} or type(active) is not bool:
            _fail("participation history must contain designated rows with boolean labels")
        retained.append((season, _class_name(status, practice), active))
    if not retained:
        _fail("participation history is empty")
    trained_seasons = sorted({season for season, _, _ in retained})
    if trained_seasons != [2022, 2023, 2024, 2025]:
        _fail("participation history must cover every 2022-2025 season")

    counts: Counter[str] = Counter()
    active_counts: Counter[str] = Counter()
    for _, class_name, active in retained:
        counts[class_name] += 1
        active_counts[class_name] += int(active)
    probabilities = {
        class_name: round(
            (active_counts[class_name] + ALPHA)
            / (counts[class_name] + 2 * ALPHA),
            4,
        )
        for class_name in sorted(counts)
    }
    rows = [[season, cls, active] for season, cls, active in sorted(retained)]
    body: dict[str, object] = {
        "schema_version": MAP_SCHEMA_VERSION,
        "map_version": MAP_VERSION,
        "normalization_contract": NORMALIZATION_CONTRACT,
        "source_artifact_sha256": source_sha256,
        "target_season": target_season,
        "trained_seasons": trained_seasons,
        "alpha": ALPHA,
        "designated_rows": len(retained),
        "training_rows_sha256": canonical_sha256(rows),
        "class_counts": dict(sorted(counts.items())),
        "p_active": probabilities,
        "fit_method": "designation-x-practice-beta-binomial-v1",
    }
    body["map_sha256"] = canonical_sha256(body)
    return body


def _validated_map(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("participation map must be a mapping")
    result = dict(value)
    retained = result.pop("map_sha256", None)
    _digest(retained, label="participation map SHA-256")
    if retained != canonical_sha256(result):
        _fail("participation map SHA-256 differs")
    if (
        result.get("schema_version") != MAP_SCHEMA_VERSION
        or result.get("map_version") != MAP_VERSION
        or result.get("normalization_contract") != NORMALIZATION_CONTRACT
        or _digest(
            result.get("source_artifact_sha256"),
            label="participation-history source artifact SHA-256",
        )
        != result.get("source_artifact_sha256")
        or result.get("target_season") != SEASON
        or result.get("trained_seasons") != [2022, 2023, 2024, 2025]
        or result.get("alpha") != ALPHA
        or result.get("fit_method") != "designation-x-practice-beta-binomial-v1"
    ):
        _fail("participation map boundary differs")
    probabilities = result.get("p_active")
    if not isinstance(probabilities, Mapping) or not probabilities:
        _fail("participation map probabilities are absent")
    for class_name, probability in probabilities.items():
        if (
            not isinstance(class_name, str)
            or type(probability) not in {int, float}
            or not math.isfinite(float(probability))
            or not 0 < float(probability) <= 1
        ):
            _fail("participation map probability is invalid")
    result["map_sha256"] = retained
    return result


def _candidate_matrix(
    *,
    player_scores: np.ndarray,
    player_ids: Sequence[str],
    rosters: Sequence[Sequence[str]],
) -> np.ndarray:
    scores = np.asarray(player_scores, dtype=np.float32)
    if scores.ndim != 2 or scores.shape[0] != len(player_ids) or not np.isfinite(scores).all():
        _fail("player score bank must be a finite player-by-world matrix")
    positions = {player: index for index, player in enumerate(player_ids)}
    totals = np.empty((len(rosters), scores.shape[1]), dtype=np.float32)
    for index, raw_roster in enumerate(rosters):
        roster = list(raw_roster)
        if len(roster) != 9 or len(set(roster)) != 9:
            _fail("every candidate roster must contain nine unique players")
        if any(player not in positions for player in roster):
            _fail("candidate roster contains a player outside the score bank")
        totals[index] = scores[[positions[player] for player in roster]].sum(axis=0)
    return totals


def _select_expected_max(scores: np.ndarray, entries: int = EXACT_K) -> list[int]:
    matrix = np.asarray(scores, dtype=np.float64)
    if matrix.ndim != 2 or len(matrix) < entries or not np.isfinite(matrix).all():
        _fail("candidate matrix cannot support an exact finite K80 book")
    current = np.full(matrix.shape[1], -np.inf)
    selected: list[int] = []
    taken = np.zeros(len(matrix), dtype=bool)
    for _ in range(entries):
        base = 0.0 if not selected else float(current.mean())
        gains = np.maximum(matrix, current).mean(axis=1) - base
        gains[taken] = -np.inf
        best = int(np.argmax(gains))
        if not np.isfinite(gains[best]):
            _fail("expected-max selector stopped before exact K80")
        selected.append(best)
        taken[best] = True
        current = np.maximum(current, matrix[best])
    return selected


def build_participation_selection_v1(
    *,
    player_ids: Sequence[str],
    lineup_ids: Sequence[str],
    rosters: Sequence[Sequence[str]],
    incumbent_player_scores: np.ndarray,
    corrected_hsim_player_scores: np.ndarray,
    snapshot: Mapping[str, object],
    participation_map: Mapping[str, object],
    mixture_seed: int,
) -> dict[str, object]:
    """Select exact P_CTRL/P_MIX books from one immutable D800 population."""

    players = [_player_id(item, label="score-bank player ID") for item in player_ids]
    lineups = [_lineup_id(item, label="candidate lineup ID") for item in lineup_ids]
    if len(lineups) != len(rosters) or len(lineups) != len(set(lineups)):
        _fail("candidate lineup identities must be unique and roster-aligned")
    retained_rosters: list[list[str]] = []
    for ordinal, raw_roster in enumerate(rosters):
        roster = [
            _player_id(item, label=f"candidate roster[{ordinal}] player ID")
            for item in raw_roster
        ]
        if len(roster) != 9 or len(set(roster)) != 9:
            _fail("every candidate roster must contain nine unique players")
        expected_lineup_id = f"lineup-v1-{canonical_sha256(sorted(roster))}"
        if lineups[ordinal] != expected_lineup_id:
            _fail("candidate lineup ID does not bind its player membership")
        retained_rosters.append(roster)
    if type(mixture_seed) is not int or mixture_seed < 0:
        _fail("mixture seed must be a nonnegative integer")
    validated_snapshot = validate_prelock_snapshot_v1(snapshot, player_ids=players)
    validated_map = _validated_map(participation_map)

    incumbent = np.asarray(incumbent_player_scores, dtype=np.float32)
    corrected = np.asarray(corrected_hsim_player_scores, dtype=np.float32)
    if (
        incumbent.ndim != 2
        or corrected.ndim != 2
        or incumbent.shape[0] != len(players)
        or corrected.shape[0] != len(players)
        or incumbent.shape[1] != corrected.shape[1]
        or not np.isfinite(incumbent).all()
        or not np.isfinite(corrected).all()
    ):
        _fail("the two player score banks must be finite, aligned, and equal-width")

    probabilities = validated_map["p_active"]
    designated: list[tuple[int, str, float]] = []
    for index, row in enumerate(validated_snapshot["rows"]):
        status = row["injury_status"]
        if status == "Out":
            if any(players[index] in roster for roster in retained_rosters):
                _fail("candidate supply contains a player designated Out")
            continue
        if status not in {"Questionable", "Doubtful"}:
            continue
        class_name = _class_name(status, row["practice_level"])
        if class_name not in probabilities:
            _fail(f"participation map lacks live class {class_name}")
        designated.append((index, class_name, float(probabilities[class_name])))

    mixed_incumbent = incumbent.copy()
    mixed_corrected = corrected.copy()
    rng = np.random.default_rng(mixture_seed)
    mask_receipts: list[dict[str, object]] = []
    for player_index, class_name, probability in designated:
        per_bank: list[dict[str, object]] = []
        for bank_name, bank in (
            ("incumbent", mixed_incumbent),
            ("corrected_hsim", mixed_corrected),
        ):
            inactive = rng.random(bank.shape[1]) >= probability
            bank[player_index, inactive] = 0.0
            per_bank.append({
                "bank": bank_name,
                "inactive_world_count": int(inactive.sum()),
                "inactive_mask_sha256": _array_sha256(inactive.astype(np.uint8)),
            })
        mask_receipts.append({
            "player_id": players[player_index],
            "class": class_name,
            "p_active": probability,
            "banks": per_bank,
        })

    control_incumbent = _candidate_matrix(
        player_scores=incumbent, player_ids=players, rosters=retained_rosters
    )
    control_corrected = _candidate_matrix(
        player_scores=corrected, player_ids=players, rosters=retained_rosters
    )
    mixed_incumbent_totals = _candidate_matrix(
        player_scores=mixed_incumbent,
        player_ids=players,
        rosters=retained_rosters,
    )
    mixed_corrected_totals = _candidate_matrix(
        player_scores=mixed_corrected,
        player_ids=players,
        rosters=retained_rosters,
    )
    control_scores = np.concatenate([control_incumbent, control_corrected], axis=1)
    mixed_scores = np.concatenate(
        [mixed_incumbent_totals, mixed_corrected_totals], axis=1
    )
    control_indices = _select_expected_max(control_scores)
    mixed_indices = _select_expected_max(mixed_scores)
    control_ids = [lineups[index] for index in control_indices]
    mixed_ids = [lineups[index] for index in mixed_indices]
    shared = set(control_ids) & set(mixed_ids)

    body: dict[str, object] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "season": SEASON,
        "week": WEEK,
        "draft_group_id": DRAFT_GROUP_ID,
        "exact_k": EXACT_K,
        "candidate_count": len(lineups),
        "candidate_ids_sha256": canonical_sha256(lineups),
        "candidate_rosters_sha256": canonical_sha256(retained_rosters),
        "snapshot_sha256": validated_snapshot["snapshot_sha256"],
        "participation_map_sha256": validated_map["map_sha256"],
        "mixture_seed": mixture_seed,
        "law_weighting": "equal-column-mass",
        "selector": "greedy-expected-weekly-max-v1",
        "tie_break": "first-in-candidate-order-v1",
        "player_score_bank_receipts": {
            "incumbent": {
                "shape": list(incumbent.shape),
                "sha256": _array_sha256(incumbent),
            },
            "corrected_hsim": {
                "shape": list(corrected.shape),
                "sha256": _array_sha256(corrected),
            },
        },
        "designation_count": len(designated),
        "designation_masks": mask_receipts,
        "P_CTRL": {
            "ordered_lineup_ids": control_ids,
            "ordered_lineup_ids_sha256": canonical_sha256(control_ids),
            "candidate_score_matrix_sha256": _array_sha256(control_scores),
        },
        "P_MIX": {
            "ordered_lineup_ids": mixed_ids,
            "ordered_lineup_ids_sha256": canonical_sha256(mixed_ids),
            "candidate_score_matrix_sha256": _array_sha256(mixed_scores),
        },
        "membership_shared_count": len(shared),
        "membership_turnover_per_side": EXACT_K - len(shared),
        "a5_prefixes": {
            str(prefix): {
                "entry_count": prefix,
                "P_CTRL": control_ids[:prefix],
                "P_CTRL_sha256": canonical_sha256(control_ids[:prefix]),
                "P_MIX": mixed_ids[:prefix],
                "P_MIX_sha256": canonical_sha256(mixed_ids[:prefix]),
            }
            for prefix in A5_PREFIXES
        },
        "outcome_fields_read": [],
    }
    body["selection_receipt_sha256"] = canonical_sha256(body)
    return body


def certify_participation_replay_v1(**selection_inputs: object) -> dict[str, object]:
    """Execute the frozen selector twice and bind byte-equivalent receipts."""

    first = build_participation_selection_v1(**selection_inputs)
    second = build_participation_selection_v1(**selection_inputs)
    if first != second:
        _fail("P_MIX replay is not deterministic")
    body: dict[str, object] = {
        "schema_version": REHEARSAL_SCHEMA_VERSION,
        "season": SEASON,
        "week": WEEK,
        "draft_group_id": DRAFT_GROUP_ID,
        "deterministic_exact_replay": True,
        "selection_receipt_sha256": first["selection_receipt_sha256"],
        "snapshot_sha256": first["snapshot_sha256"],
        "participation_map_sha256": first["participation_map_sha256"],
        "exact_k": EXACT_K,
        "a5_prefixes": list(A5_PREFIXES),
        "fallback_on_any_validation_failure": "P_CTRL",
        "outcome_fields_read": [],
    }
    body["rehearsal_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "A5_PREFIXES",
    "EXACT_K",
    "MAP_VERSION",
    "NORMALIZATION_CONTRACT",
    "PROVIDER_ABSENCE_SEMANTICS",
    "Week1ParticipationMixtureError",
    "build_participation_selection_v1",
    "build_prelock_snapshot_v1",
    "certify_participation_replay_v1",
    "fit_participation_map_v1",
    "validate_prelock_snapshot_v1",
]
