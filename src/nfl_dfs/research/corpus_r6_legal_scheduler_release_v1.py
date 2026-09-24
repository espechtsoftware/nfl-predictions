"""Guarded, explicitly non-authoritative R6 legal-scheduler release.

The scheduler substrate deliberately accepts caller-supplied identity claims.
This module adds exact byte reads, strict input validation, bounded cumulative
work accounting, deterministic create-once payloads, and generation-exact
reopening.  Those controls make the result useful for outcome-free research,
but they do *not* make it adopted evidence: the configuration, storage
callbacks, producer code/image claim, and process-local ledger are not bound by
an independently fixed trusted adapter.

Consequently every persisted object carries fixed false authority and
promotion flags.  A future authoritative adapter must compile/pin the adopted
configuration, attest the runtime code/image, use a durable compare-and-swap
ledger, and supply a trusted generation-pinned object-store implementation.
Nothing a caller passes to this generic boundary can turn those flags true.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from threading import Lock
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_legal_scheduler_v1 as scheduler
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.object_identity import content_identity


CONFIGURATION_SCHEMA: Final = (
    "corpus-r6-legal-scheduler-generic-release-configuration/v1"
)
SOURCE_SCHEMA: Final = "corpus-r6-legal-scheduler-source-batch/v1"
CANDIDATE_SCHEMA: Final = "corpus-r6-legal-scheduler-incumbent-bank/v1"
RECEIPT_SCHEMA: Final = "corpus-r6-legal-scheduler-nonauthoritative-batch/v1"
ROOT_SCHEMA: Final = "corpus-r6-legal-scheduler-nonauthoritative-root/v1"
LEDGER_SCHEMA: Final = "corpus-r6-legal-scheduler-process-ledger-charge/v1"

# These are transport/input denial-of-service guards.  The scheduler itself
# separately enforces player/world/dose hard maxima.
MAX_SOURCE_BYTES: Final = 256 * 1024 * 1024
MAX_CANDIDATE_BYTES: Final = 4 * 1024 * 1024
MAX_WORK_UNIT: Final = int(np.iinfo(np.int64).max)
_INT64_MAX: Final = int(np.iinfo(np.int64).max)

# One wrapper computation creates a typed result and then asks the substrate to
# replay that result from the same raw inputs before serializing its receipt.
PRODUCER_PASSES_PER_COMPUTE: Final = 2
# Thirty-two is a deliberately loose accounting ceiling for input
# materialization, repeated canonicalization/min/max scans, hashing/binding and
# the two producer passes.  In particular, the feasible-core producer performs
# three canonical matrix materializations plus one hash traversal per producer
# pass, in addition to the wrapper materialization.  The former value of eight
# was therefore not a ceiling.
PLAYER_WORLD_CELL_PASSES_PER_COMPUTE: Final = 32
OUTER_INCUMBENT_AUDIT_PASSES: Final = 1
# Each of the two feasible producer passes calls ``_canonical_incumbents``
# twice.  Every such call performs both the DK audit and the profile audit, so
# there are eight producer-side incumbent audit passes, plus the outer pass.
FEASIBLE_PRODUCER_INCUMBENT_AUDIT_PASSES: Final = 8
CLASSIC_SKILL_PATTERN_COUNT: Final = len(rw.CLASSIC_SKILL_PATTERNS)

# Generic output is deliberately segregated from adopted/production evidence.
# Callers may choose a bucket and one run suffix, but never an authoritative
# namespace within that bucket.
GENERIC_OUTPUT_OBJECT_PREFIX: Final = (
    "research/non-authoritative/corpus-r6-legal-scheduler/"
)

WORK_FIELDS: Final = (
    "source_bytes",
    "candidate_bytes",
    "player_world_cells",
    "theta_evaluations",
    "theta_player_world_cells",
    "incumbent_roster_audits",
    "incumbent_player_audits",
    "incumbent_score_cells",
    "combination_candidates",
    "core_candidates",
    "beam_expansions",
    "witness_roster_audits",
    "witness_player_audits",
    "retained_read_bytes",
    "publication_write_bytes",
    "publication_reopen_bytes",
)

_SLATE_ID: Final = re.compile(r"[0-9]{4}-w(?:0[1-9]|1[0-8])")
_BATCH_ID: Final = re.compile(r"(R[0-4])-b[0-9]{3}")
_ATTEMPT_ID: Final = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")


class CorpusR6LegalSchedulerReleaseV1Error(ValueError):
    """The guarded generic scheduler-release contract was violated."""


def _fail(message: str) -> None:
    raise CorpusR6LegalSchedulerReleaseV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def add_self_hash_v1(value: Mapping[str, object], field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"self-hash field {field} already exists")
    body[field] = canonical_sha256_v1(body)
    return body


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        _fail(f"{label} fields differ")


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be a nonempty string")
    return value


def _integer(
    value: object,
    label: str,
    minimum: int = 0,
    maximum: int = MAX_WORK_UNIT,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def _digest(value: object, label: str) -> str:
    retained = _string(value, label)
    if len(retained) != 64 or any(
        character not in "0123456789abcdef" for character in retained
    ):
        _fail(f"{label} must be lowercase SHA-256")
    return retained


def _canonical_gcs_uri(value: object, label: str) -> str:
    uri = _string(value, label)
    if not uri.startswith("gs://"):
        _fail(f"{label} must be a canonical gs:// URI")
    bucket, separator, name = uri[5:].partition("/")
    if (
        not separator
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]", bucket) is None
        or not name
        or name.startswith("/")
        or name.endswith("/")
        or "//" in name
        or "\\" in name
        or any(character.isspace() or ord(character) < 32 for character in name)
        or any(part in {".", ".."} for part in name.split("/"))
        or any(character in "?#" for character in name)
    ):
        _fail(f"{label} must be a canonical gs:// URI")
    return uri


def _gcs_object_name(uri: str) -> str:
    retained = _canonical_gcs_uri(uri, "GCS URI")
    return retained[5:].partition("/")[2]


def _identity(value: object, label: str) -> dict[str, object]:
    item = _mapping(value, label)
    _exact_keys(item, {"uri", "generation", "sha256", "bytes"}, label)
    try:
        uri, generation, digest, size = content_identity(item)
    except (KeyError, TypeError, ValueError) as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(
            f"{label} content identity differs"
        ) from exc
    retained_uri = _canonical_gcs_uri(uri, f"{label} uri")
    if (
        type(item["generation"]) is not str
        or generation != item["generation"]
        or generation.startswith("0")
        or len(generation) > 32
        or int(generation) <= 0
    ):
        _fail(f"{label} generation must be one canonical positive integer string")
    if type(item["bytes"]) is not int or not 0 < size <= MAX_WORK_UNIT:
        _fail(f"{label} byte count differs")
    return {
        "uri": retained_uri,
        "generation": generation,
        "sha256": _digest(digest, f"{label} SHA-256"),
        "bytes": size,
    }


ReadExact = Callable[[object], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


def _generic_authority_status() -> dict[str, object]:
    """Fixed status; callers have no seam that can elevate these flags."""
    return {
        "authoritative": False,
        "promotion_authority": False,
        "adopted_configuration_bound": False,
        "caller_independent_configuration_verified": False,
        "durable_cas_ledger_verified": False,
        "trusted_create_once_adapter_verified": False,
        "trusted_exact_read_adapter_verified": False,
        "runtime_code_image_attested": False,
        "outcome_free_source_lineage_attested": False,
        "generic_callback_boundary_only": True,
        "future_fixed_trusted_adapter_required": True,
    }


def _unattested_outcome_status() -> dict[str, object]:
    """Describe the caller assertion without converting it into evidence."""
    return {
        "caller_asserted_no_outcome_reads": True,
        "caller_assertion_only": True,
        "source_lineage_attested": False,
        "outcome_free_authority": False,
        "promotion_eligible": False,
    }


def _work_accounting_law() -> dict[str, object]:
    """Return the immutable accounting law embedded in every receipt."""
    return {
        "input_phase_charged_before_exact_reads": True,
        "source_and_candidate_validation_covered_by_input_byte_charges": True,
        "compute_phase_charged_before_matrix_materialization": True,
        "retained_objects_charged_before_exact_reopen": True,
        "publication_write_and_reopen_charged_before_publication": True,
        "publication_charges_excluded_from_self_referential_payload": True,
        "every_retry_and_reopen_compute_charged": True,
        "producer_passes_per_compute": PRODUCER_PASSES_PER_COMPUTE,
        "player_world_cell_passes_per_compute": (
            PLAYER_WORLD_CELL_PASSES_PER_COMPUTE
        ),
        "ledger_receipts_excluded_from_deterministic_payload": True,
    }


def _zero_work() -> dict[str, int]:
    return {field: 0 for field in WORK_FIELDS}


def _work_vector(value: object, label: str) -> dict[str, int]:
    item = _mapping(value, label)
    _exact_keys(item, set(WORK_FIELDS), label)
    return {
        field: _integer(item[field], f"{label} {field}")
        for field in WORK_FIELDS
    }


def _add_work(left: Mapping[str, int], right: Mapping[str, int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for field in WORK_FIELDS:
        total = int(left[field]) + int(right[field])
        if total > MAX_WORK_UNIT:
            _fail("cumulative run work overflows signed int64 accounting")
        result[field] = total
    return result


@dataclass(slots=True)
class InMemoryAtomicRunLedgerV1:
    """Thread-safe process-local cumulative ledger for hermetic/research use.

    Every call is charged.  Retrying the same logical release therefore
    consumes additional budget instead of receiving a free idempotent compute.
    This ledger is intentionally rejected as durable or authoritative by every
    persisted status object.
    """

    _lock: Lock
    _totals: dict[str, dict[str, int]]
    _limits: dict[str, dict[str, int]]
    _charges: list[dict[str, object]]
    _retry_phase_counts: dict[tuple[str, str, str], int]

    def __init__(self) -> None:
        self._lock = Lock()
        self._totals = {}
        self._limits = {}
        self._charges = []
        self._retry_phase_counts = {}

    def reserve(
        self,
        *,
        run_id: str,
        retry_key: str,
        phase: str,
        charge: Mapping[str, int],
        limits: Mapping[str, int],
    ) -> Mapping[str, object]:
        normalized_run = _string(run_id, "run id")
        normalized_retry = _digest(retry_key, "retry key")
        normalized_phase = _string(phase, "ledger phase")
        if normalized_phase not in {
            "input",
            "compute",
            "retained-root-read",
            "retained-receipt-read",
            "publication-receipt",
            "publication-root",
        }:
            _fail("ledger phase is unsupported")
        normalized_charge = _work_vector(charge, "ledger charge")
        normalized_limits = _work_vector(limits, "ledger limits")
        if not any(normalized_charge.values()):
            _fail("ledger charge must reserve nonzero work")

        with self._lock:
            prior_limits = self._limits.get(normalized_run)
            if prior_limits is not None and prior_limits != normalized_limits:
                _fail("run work limits changed after the first reservation")
            previous = self._totals.get(normalized_run, _zero_work())
            after = _add_work(previous, normalized_charge)
            if any(
                after[field] > normalized_limits[field] for field in WORK_FIELDS
            ):
                _fail(f"cumulative run budget exhausted before {normalized_phase}")

            retry_phase = (normalized_run, normalized_retry, normalized_phase)
            phase_ordinal = self._retry_phase_counts.get(retry_phase, 0) + 1
            body: dict[str, object] = {
                "schema_version": LEDGER_SCHEMA,
                "run_id": normalized_run,
                "retry_key": normalized_retry,
                "phase": normalized_phase,
                "charge_ordinal": len(self._charges),
                "retry_phase_invocation_ordinal": phase_ordinal,
                "charge": normalized_charge,
                "cumulative_before": previous,
                "cumulative_after": after,
                "limits": normalized_limits,
                "atomic_charge_before_phase": True,
                "every_invocation_charged": True,
                "process_local": True,
                "durable_cas_verified": False,
                "authoritative": False,
            }
            receipt = add_self_hash_v1(body, "ledger_charge_sha256")
            self._limits[normalized_run] = normalized_limits
            self._totals[normalized_run] = after
            self._retry_phase_counts[retry_phase] = phase_ordinal
            self._charges.append(receipt)
            return dict(receipt)

    def totals(self, run_id: str) -> dict[str, int]:
        """Return a defensive copy for validation/tests."""
        normalized_run = _string(run_id, "run id")
        with self._lock:
            return dict(self._totals.get(normalized_run, _zero_work()))


def _validate_ledger_charge(
    value: object,
    *,
    run_id: str,
    retry_key: str,
    phase: str,
    charge: Mapping[str, int],
    limits: Mapping[str, int],
) -> dict[str, object]:
    item = _mapping(value, "ledger charge receipt")
    _exact_keys(
        item,
        {
            "schema_version",
            "run_id",
            "retry_key",
            "phase",
            "charge_ordinal",
            "retry_phase_invocation_ordinal",
            "charge",
            "cumulative_before",
            "cumulative_after",
            "limits",
            "atomic_charge_before_phase",
            "every_invocation_charged",
            "process_local",
            "durable_cas_verified",
            "authoritative",
            "ledger_charge_sha256",
        },
        "ledger charge receipt",
    )
    retained_hash = _digest(item["ledger_charge_sha256"], "ledger charge SHA")
    body = dict(item)
    body.pop("ledger_charge_sha256")
    if canonical_sha256_v1(body) != retained_hash:
        _fail("ledger charge receipt self-hash differs")
    previous = _work_vector(item["cumulative_before"], "cumulative work before")
    after = _work_vector(item["cumulative_after"], "cumulative work after")
    normalized_charge = _work_vector(charge, "expected ledger charge")
    normalized_limits = _work_vector(limits, "expected ledger limits")
    if (
        item["schema_version"] != LEDGER_SCHEMA
        or item["run_id"] != run_id
        or item["retry_key"] != retry_key
        or item["phase"] != phase
        or item["charge"] != normalized_charge
        or item["limits"] != normalized_limits
        or after != _add_work(previous, normalized_charge)
        or any(after[field] > normalized_limits[field] for field in WORK_FIELDS)
        or item["atomic_charge_before_phase"] is not True
        or item["every_invocation_charged"] is not True
        or item["process_local"] is not True
        or item["durable_cas_verified"] is not False
        or item["authoritative"] is not False
    ):
        _fail("ledger charge receipt semantics differ")
    _integer(item["charge_ordinal"], "charge ordinal")
    _integer(
        item["retry_phase_invocation_ordinal"],
        "retry phase invocation ordinal",
        minimum=1,
    )
    return item


def validate_release_configuration_v1(value: object) -> dict[str, object]:
    """Validate a caller configuration without treating it as authority."""
    configuration = _mapping(value, "generic release configuration")
    _exact_keys(
        configuration,
        {
            "schema_version",
            "configuration_id",
            "run_id",
            "slate_id",
            "batch_id",
            "attempt_id",
            "proxy_id",
            "source_identity",
            "candidate_identity",
            "profile_id",
            "profile_payload_sha256",
            "dose_sha256",
            "producer_identity_claim",
            "work_limits",
            "receipt_uri",
            "root_uri",
            "terminal",
            "caller_asserted_no_outcome_reads",
            "release_configuration_sha256",
        },
        "generic release configuration",
    )
    retained_hash = _digest(
        configuration["release_configuration_sha256"], "configuration SHA"
    )
    body = dict(configuration)
    body.pop("release_configuration_sha256")
    if canonical_sha256_v1(body) != retained_hash:
        _fail("generic release configuration self-hash differs")
    if (
        configuration["schema_version"] != CONFIGURATION_SCHEMA
        or configuration["proxy_id"] not in scheduler.SUPPORTED_PROXY_IDS
        or configuration["terminal"] is not True
        or configuration["caller_asserted_no_outcome_reads"] is not True
    ):
        _fail("generic release configuration fixed law differs")
    for field in (
        "configuration_id",
        "run_id",
        "slate_id",
        "batch_id",
        "attempt_id",
        "profile_id",
    ):
        _string(configuration[field], field)
    if (
        _SLATE_ID.fullmatch(str(configuration["slate_id"])) is None
        or _BATCH_ID.fullmatch(str(configuration["batch_id"])) is None
        or _ATTEMPT_ID.fullmatch(str(configuration["attempt_id"])) is None
    ):
        _fail("generic release configuration coordinate format differs")

    source_identity = _identity(configuration["source_identity"], "source identity")
    candidate_identity = _identity(
        configuration["candidate_identity"], "candidate identity"
    )
    if source_identity["bytes"] > MAX_SOURCE_BYTES:
        _fail("source identity exceeds the hard byte maximum")
    if candidate_identity["bytes"] > MAX_CANDIDATE_BYTES:
        _fail("candidate identity exceeds the hard byte maximum")
    _digest(configuration["profile_payload_sha256"], "profile SHA")
    _digest(configuration["dose_sha256"], "dose SHA")
    producer = _mapping(
        configuration["producer_identity_claim"], "producer identity claim"
    )
    _exact_keys(
        producer,
        {"proxy_id", "code_sha256", "image_digest"},
        "producer identity claim",
    )
    try:
        expected_producer = scheduler.ProducerIdentity(**producer)
    except (scheduler.CorpusR6LegalSchedulerError, TypeError, ValueError) as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(
            "producer identity claim is malformed"
        ) from exc
    if expected_producer.proxy_id != configuration["proxy_id"]:
        _fail("configuration producer/proxy binding differs")
    _work_vector(configuration["work_limits"], "work limits")

    receipt_uri = _canonical_gcs_uri(configuration["receipt_uri"], "receipt URI")
    root_uri = _canonical_gcs_uri(configuration["root_uri"], "root URI")
    if (
        receipt_uri == root_uri
        or receipt_uri.rsplit("/", 1)[0] != root_uri.rsplit("/", 1)[0]
        or not _gcs_object_name(receipt_uri).startswith(
            GENERIC_OUTPUT_OBJECT_PREFIX
        )
        or not _gcs_object_name(root_uri).startswith(GENERIC_OUTPUT_OBJECT_PREFIX)
        or receipt_uri in {source_identity["uri"], candidate_identity["uri"]}
        or root_uri in {source_identity["uri"], candidate_identity["uri"]}
    ):
        _fail(
            "generic outputs must share the fixed non-authoritative research "
            "namespace and remain distinct from inputs"
        )
    return configuration


def _exact_json(
    identity: object,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object], bytes]:
    retained_identity = _identity(identity, f"{label} identity")
    try:
        raw = read_exact(retained_identity)
    except Exception as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(
            f"{label} generation-pinned exact read failed"
        ) from exc
    if type(raw) is not bytes:
        _fail(f"{label} exact reader did not return bytes")
    if (
        len(raw) != retained_identity["bytes"]
        or sha256(raw).hexdigest() != retained_identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ from identity")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(f"{label} is not JSON") from exc
    item = _mapping(value, label)
    if canonical_json_bytes_v1(item) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return item, retained_identity, raw


def _validate_source(
    value: object,
    configuration: Mapping[str, object],
) -> tuple[
    tuple[rw.PlayerSpec, ...],
    tuple[tuple[int, ...], ...],
    tuple[rw.WorldId, ...],
]:
    source = _mapping(value, "scheduler source batch")
    _exact_keys(
        source,
        {
            "schema_version",
            "slate_id",
            "batch_id",
            "players",
            "player_scores_micro",
            "ordered_world_ids",
            "source_batch_sha256",
        },
        "scheduler source batch",
    )
    retained_hash = _digest(source["source_batch_sha256"], "source batch SHA")
    body = dict(source)
    body.pop("source_batch_sha256")
    if canonical_sha256_v1(body) != retained_hash:
        _fail("source batch self-hash differs")
    if (
        source["schema_version"] != SOURCE_SCHEMA
        or source["slate_id"] != configuration["slate_id"]
        or source["batch_id"] != configuration["batch_id"]
    ):
        _fail("source batch coordinate differs")

    raw_players = _sequence(source["players"], "source players")
    if not raw_players or len(raw_players) > scheduler.MAX_PLAYERS_PER_BATCH:
        _fail("source player count is outside the hard batch range")
    players: list[rw.PlayerSpec] = []
    for ordinal, raw in enumerate(raw_players):
        row = _mapping(raw, f"source player[{ordinal}]")
        _exact_keys(
            row,
            {"player_id", "position", "team", "opponent", "game_id", "salary"},
            f"source player[{ordinal}]",
        )
        normalized = {
            "player_id": _string(row["player_id"], f"source player[{ordinal}] id"),
            "position": _string(
                row["position"], f"source player[{ordinal}] position"
            ),
            "team": _string(row["team"], f"source player[{ordinal}] team"),
            "opponent": _string(
                row["opponent"], f"source player[{ordinal}] opponent"
            ),
            "game_id": _string(
                row["game_id"], f"source player[{ordinal}] game id"
            ),
            "salary": _integer(
                row["salary"], f"source player[{ordinal}] salary", minimum=1
            ),
        }
        try:
            player = rw.PlayerSpec(**normalized)
        except (rw.ResidualWorldError, TypeError, ValueError) as exc:
            raise CorpusR6LegalSchedulerReleaseV1Error(
                f"source player[{ordinal}] is invalid"
            ) from exc
        if player.position != row["position"]:
            _fail(f"source player[{ordinal}] position is not canonical")
        players.append(player)
    if len({player.player_id for player in players}) != len(players):
        _fail("source player ids repeat")

    raw_worlds = _sequence(source["ordered_world_ids"], "world ids")
    if not raw_worlds or len(raw_worlds) > scheduler.MAX_WORLDS_PER_BATCH:
        _fail("source world count is outside the hard batch range")
    worlds: list[rw.WorldId] = []
    for ordinal, raw in enumerate(raw_worlds):
        row = _mapping(raw, f"world id[{ordinal}]")
        _exact_keys(row, {"block", "index"}, f"world id[{ordinal}]")
        try:
            worlds.append(rw.WorldId(row["block"], row["index"]))
        except (rw.ResidualWorldError, TypeError, ValueError) as exc:
            raise CorpusR6LegalSchedulerReleaseV1Error(
                f"world id[{ordinal}] is invalid"
            ) from exc
    batch_match = _BATCH_ID.fullmatch(str(configuration["batch_id"]))
    assert batch_match is not None
    if (
        len(set(worlds)) != len(worlds)
        or any(world.block != batch_match.group(1) for world in worlds)
    ):
        _fail("source world schedule/batch coordinate differs")

    raw_scores = _sequence(source["player_scores_micro"], "score matrix")
    if len(raw_scores) != len(players):
        _fail("source score matrix player dimension differs")
    retained_scores: list[tuple[int, ...]] = []
    maximum = 0
    for player_ordinal, raw_row in enumerate(raw_scores):
        score_row = _sequence(raw_row, f"score matrix row[{player_ordinal}]")
        if len(score_row) != len(worlds):
            _fail("source score matrix world dimension differs")
        retained_row: list[int] = []
        for world_ordinal, raw_score in enumerate(score_row):
            if (
                type(raw_score) is not int
                or not -_INT64_MAX - 1 <= raw_score <= _INT64_MAX
            ):
                _fail(
                    "source score matrix cells must be signed int64 integers "
                    f"at [{player_ordinal},{world_ordinal}]"
                )
            retained_row.append(raw_score)
            maximum = max(maximum, abs(raw_score))
        retained_scores.append(tuple(retained_row))
    if maximum * rw.ROSTER_SIZE > _INT64_MAX:
        _fail("nine-player source score sum exceeds signed int64")
    return tuple(players), tuple(retained_scores), tuple(worlds)


def _materialize_score_matrix(scores: Sequence[Sequence[int]]) -> np.ndarray:
    matrix = np.ascontiguousarray(scores, dtype=np.int64)
    if matrix.ndim != 2:
        _fail("source score matrix materialization differs")
    matrix.flags.writeable = False
    return matrix


def _validate_candidates(
    value: object,
    configuration: Mapping[str, object],
) -> tuple[tuple[str, ...], ...]:
    item = _mapping(value, "incumbent bank")
    _exact_keys(
        item,
        {
            "schema_version",
            "slate_id",
            "candidate_bank_id",
            "incumbent_rosters",
            "incumbent_bank_sha256",
        },
        "incumbent bank",
    )
    retained_hash = _digest(item["incumbent_bank_sha256"], "incumbent bank SHA")
    body = dict(item)
    body.pop("incumbent_bank_sha256")
    if canonical_sha256_v1(body) != retained_hash:
        _fail("incumbent bank self-hash differs")
    if (
        item["schema_version"] != CANDIDATE_SCHEMA
        or item["slate_id"] != configuration["slate_id"]
    ):
        _fail("incumbent bank coordinate differs")
    _string(item["candidate_bank_id"], "candidate bank id")
    raw_rosters = _sequence(item["incumbent_rosters"], "incumbent rosters")
    if not raw_rosters or len(raw_rosters) > scheduler.MAX_INCUMBENT_CANDIDATES:
        _fail("incumbent count is outside the hard batch range")
    rosters: list[tuple[str, ...]] = []
    observed: set[tuple[str, ...]] = set()
    for ordinal, raw in enumerate(raw_rosters):
        roster = tuple(
            _string(player, f"incumbent roster[{ordinal}] player id")
            for player in _sequence(raw, f"incumbent roster[{ordinal}]")
        )
        if (
            len(roster) != rw.ROSTER_SIZE
            or len(set(roster)) != rw.ROSTER_SIZE
            or roster != tuple(sorted(roster))
            or roster in observed
        ):
            _fail(f"incumbent roster[{ordinal}] structure differs")
        observed.add(roster)
        rosters.append(roster)
    return tuple(rosters)


def _fixed_inputs(
    configuration: Mapping[str, object],
) -> tuple[
    legal.EffectivePolicyProfile,
    scheduler.SalaryPositionDose | scheduler.FeasibleCoreDose,
    scheduler.ProducerIdentity,
]:
    profiles = [
        profile
        for profile in legal.frozen_policy_profiles()
        if profile.parameter_set_id == configuration["profile_id"]
        and canonical_sha256_v1(profile.as_payload())
        == configuration["profile_payload_sha256"]
    ]
    if len(profiles) != 1:
        _fail("fixed in-code profile differs from configuration")
    if configuration["proxy_id"] == scheduler.POSITION_SALARY_PROXY_ID:
        dose: scheduler.SalaryPositionDose | scheduler.FeasibleCoreDose = (
            scheduler.DEFAULT_SALARY_POSITION_DOSE
        )
    else:
        dose = scheduler.DEFAULT_FEASIBLE_CORE_DOSE
    if dose.receipt().dose_sha256 != configuration["dose_sha256"]:
        _fail("fixed in-code dose differs from configuration")
    try:
        producer = scheduler.ProducerIdentity(
            **_mapping(
                configuration["producer_identity_claim"],
                "producer identity claim",
            )
        )
    except (scheduler.CorpusR6LegalSchedulerError, TypeError, ValueError) as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(
            "producer identity claim differs"
        ) from exc
    return profiles[0], dose, producer


def _validate_incumbents(
    incumbents: Sequence[Sequence[str]],
    players: Sequence[rw.PlayerSpec],
    profile: legal.EffectivePolicyProfile,
) -> None:
    observed: set[tuple[str, ...]] = set()
    for ordinal, raw_roster in enumerate(incumbents):
        roster = tuple(raw_roster)
        if roster in observed:
            _fail(f"incumbent roster[{ordinal}] repeats")
        try:
            scheduler.audit_profile_roster(players, roster, profile)
        except scheduler.CorpusR6LegalSchedulerError as exc:
            raise CorpusR6LegalSchedulerReleaseV1Error(
                f"incumbent roster[{ordinal}] is not legal under the profile"
            ) from exc
        observed.add(roster)


def _input_charge(configuration: Mapping[str, object]) -> dict[str, int]:
    charge = _zero_work()
    source_identity = _identity(configuration["source_identity"], "source identity")
    candidate_identity = _identity(
        configuration["candidate_identity"], "candidate identity"
    )
    charge["source_bytes"] = int(source_identity["bytes"])
    charge["candidate_bytes"] = int(candidate_identity["bytes"])
    return charge


def _compute_charge(
    *,
    players: Sequence[object],
    worlds: Sequence[object],
    incumbents: Sequence[object],
    dose: scheduler.SalaryPositionDose | scheduler.FeasibleCoreDose,
) -> dict[str, int]:
    player_count = len(players)
    world_count = len(worlds)
    incumbent_count = len(incumbents)
    charge = _zero_work()
    charge["player_world_cells"] = (
        PLAYER_WORLD_CELL_PASSES_PER_COMPUTE * player_count * world_count
    )
    audit_passes = OUTER_INCUMBENT_AUDIT_PASSES
    if isinstance(dose, scheduler.SalaryPositionDose):
        theta_count = len(dose.theta_micro_per_salary_dollar)
        charge["theta_evaluations"] = (
            PRODUCER_PASSES_PER_COMPUTE * theta_count * world_count
        )
        charge["theta_player_world_cells"] = (
            PRODUCER_PASSES_PER_COMPUTE
            * theta_count
            * player_count
            * world_count
        )
    else:
        audit_passes += FEASIBLE_PRODUCER_INCUMBENT_AUDIT_PASSES
        charge["incumbent_score_cells"] = (
            PRODUCER_PASSES_PER_COMPUTE * incumbent_count * world_count
        )
        charge["combination_candidates"] = (
            PRODUCER_PASSES_PER_COMPUTE
            * dose.max_combination_candidates
            * world_count
        )
        charge["core_candidates"] = (
            PRODUCER_PASSES_PER_COMPUTE
            * dose.max_core_candidates
            * world_count
        )
        charge["beam_expansions"] = (
            PRODUCER_PASSES_PER_COMPUTE
            * dose.max_state_expansions
            * world_count
        )
        # Every completed beam may be profile-audited, including a structural
        # core that already fills all slots and therefore consumes no state
        # expansion.  Reserve the full cores x shapes x beam ceiling, plus the
        # final witness audit performed for every world, in both producer
        # passes.
        witness_audits_per_world = (
            dose.max_cores * CLASSIC_SKILL_PATTERN_COUNT * dose.beam_width + 1
        )
        charge["witness_roster_audits"] = (
            PRODUCER_PASSES_PER_COMPUTE
            * witness_audits_per_world
            * world_count
        )
        charge["witness_player_audits"] = (
            charge["witness_roster_audits"] * rw.ROSTER_SIZE
        )
    charge["incumbent_roster_audits"] = audit_passes * incumbent_count
    charge["incumbent_player_audits"] = (
        audit_passes * incumbent_count * rw.ROSTER_SIZE
    )
    return _work_vector(charge, "computed work reservation")


def _retry_key(configuration: Mapping[str, object]) -> str:
    return canonical_sha256_v1(
        {
            field: configuration[field]
            for field in (
                "release_configuration_sha256",
                "run_id",
                "slate_id",
                "batch_id",
                "attempt_id",
                "proxy_id",
            )
        }
    )


def _deterministic_reservation(
    input_charge: Mapping[str, int],
    compute_charge: Mapping[str, int],
) -> dict[str, int]:
    return _add_work(input_charge, compute_charge)


def _retained_read_charge(identity_value: object) -> dict[str, int]:
    identity = _identity(identity_value, "retained object identity")
    charge = _zero_work()
    charge["retained_read_bytes"] = int(identity["bytes"])
    return charge


def _publication_charge(raw: bytes) -> dict[str, int]:
    if type(raw) is not bytes or not raw:
        _fail("publication charge requires nonempty canonical bytes")
    charge = _zero_work()
    charge["publication_write_bytes"] = len(raw)
    charge["publication_reopen_bytes"] = len(raw)
    return charge


def _build_receipt(
    *,
    configuration: Mapping[str, object],
    source_identity: Mapping[str, object],
    candidate_identity: Mapping[str, object],
    work_reservation: Mapping[str, int],
    result: scheduler.TypedProxyResult,
    proxy_receipt: scheduler.ProxyReceipt,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "coordinates": {
            field: configuration[field]
            for field in (
                "run_id",
                "slate_id",
                "batch_id",
                "attempt_id",
                "proxy_id",
            )
        },
        "release_configuration_sha256": configuration[
            "release_configuration_sha256"
        ],
        "source_identity": dict(source_identity),
        "candidate_identity": dict(candidate_identity),
        "work_reservation": dict(work_reservation),
        "work_limits": _work_vector(configuration["work_limits"], "work limits"),
        "work_accounting_law": _work_accounting_law(),
        "scheduler_result_sha256": result.result_sha256,
        "scheduler_proxy_receipt": json.loads(proxy_receipt.canonical_payload),
        "scheduler_proxy_receipt_sha256": proxy_receipt.receipt_sha256,
        "authority_status": _generic_authority_status(),
        "outcome_freedom_status": _unattested_outcome_status(),
        "promotion_eligible": False,
        "complete": True,
    }
    return add_self_hash_v1(body, "batch_receipt_sha256")


def _reserve(
    *,
    ledger: InMemoryAtomicRunLedgerV1,
    configuration: Mapping[str, object],
    retry_key: str,
    phase: str,
    charge: Mapping[str, int],
) -> dict[str, object]:
    if type(ledger) is not InMemoryAtomicRunLedgerV1:
        _fail(
            "generic wrapper requires its fixed process-local ledger; a trusted "
            "durable adapter is not implemented"
        )
    limits = _work_vector(configuration["work_limits"], "work limits")
    return _validate_ledger_charge(
        ledger.reserve(
            run_id=str(configuration["run_id"]),
            retry_key=retry_key,
            phase=phase,
            charge=charge,
            limits=limits,
        ),
        run_id=str(configuration["run_id"]),
        retry_key=retry_key,
        phase=phase,
        charge=charge,
        limits=limits,
    )


def _compute_receipt(
    *,
    release_configuration: object,
    read_exact: ReadExact,
    ledger: InMemoryAtomicRunLedgerV1,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    configuration = validate_release_configuration_v1(release_configuration)
    retry_key = _retry_key(configuration)
    input_charge = _input_charge(configuration)
    input_ledger_charge = _reserve(
        ledger=ledger,
        configuration=configuration,
        retry_key=retry_key,
        phase="input",
        charge=input_charge,
    )

    source, source_identity, _ = _exact_json(
        configuration["source_identity"], read_exact, "scheduler source"
    )
    candidates, candidate_identity, _ = _exact_json(
        configuration["candidate_identity"], read_exact, "incumbent bank"
    )
    players, scores, worlds = _validate_source(source, configuration)
    incumbents = _validate_candidates(candidates, configuration)
    profile, dose, producer = _fixed_inputs(configuration)

    compute_charge = _compute_charge(
        players=players,
        worlds=worlds,
        incumbents=incumbents,
        dose=dose,
    )
    compute_ledger_charge = _reserve(
        ledger=ledger,
        configuration=configuration,
        retry_key=retry_key,
        phase="compute",
        charge=compute_charge,
    )

    # No scheduler computation or matrix materialization is allowed before the
    # compute reservation above succeeds.
    _validate_incumbents(incumbents, players, profile)
    matrix = _materialize_score_matrix(scores)
    source_claim = scheduler.SourceArtifactIdentity(
        uri=str(source_identity["uri"]),
        generation=int(source_identity["generation"]),
        byte_count=int(source_identity["bytes"]),
        sha256=str(source_identity["sha256"]),
        scientific_contract_sha256=str(source["source_batch_sha256"]),
    )
    try:
        if configuration["proxy_id"] == scheduler.POSITION_SALARY_PROXY_ID:
            assert isinstance(dose, scheduler.SalaryPositionDose)
            result: scheduler.TypedProxyResult = (
                scheduler.produce_position_salary_proxy(
                    player_scores_micro=matrix,
                    players=players,
                    ordered_world_ids=worlds,
                    profile=profile,
                    source_artifact=source_claim,
                    producer_identity=producer,
                    dose=dose,
                )
            )
        else:
            assert isinstance(dose, scheduler.FeasibleCoreDose)
            result = scheduler.produce_feasible_core_proxy(
                player_scores_micro=matrix,
                players=players,
                ordered_world_ids=worlds,
                profile=profile,
                incumbent_candidates=incumbents,
                source_artifact=source_claim,
                producer_identity=producer,
                dose=dose,
            )
        proxy_receipt = scheduler.build_proxy_receipt(
            result,
            players=players,
            player_scores_micro=matrix,
            ordered_world_ids=worlds,
            selected_count=min(80, len(worlds)),
        )
    except scheduler.CorpusR6LegalSchedulerError as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(
            "scheduler producer/replay failed"
        ) from exc
    if proxy_receipt.authoritative is not False:
        _fail("scheduler substrate unexpectedly claimed authority")
    receipt = _build_receipt(
        configuration=configuration,
        source_identity=source_identity,
        candidate_identity=candidate_identity,
        work_reservation=_deterministic_reservation(input_charge, compute_charge),
        result=result,
        proxy_receipt=proxy_receipt,
    )
    return receipt, (input_ledger_charge, compute_ledger_charge)


def _publish_and_exact_reopen(
    *,
    uri: str,
    raw: bytes,
    label: str,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        published = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusR6LegalSchedulerReleaseV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(published, f"published {label} identity")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"published {label} identity differs")
    reopened, reopened_identity, reopened_raw = _exact_json(
        identity, read_exact, f"published {label}"
    )
    if reopened_identity != identity or reopened_raw != raw:
        _fail(f"published {label} exact reopen differs")
    return reopened, identity


def _build_root(
    *,
    configuration: Mapping[str, object],
    receipt: Mapping[str, object],
    receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": ROOT_SCHEMA,
        "coordinates": dict(_mapping(receipt["coordinates"], "coordinates")),
        "release_configuration_sha256": configuration[
            "release_configuration_sha256"
        ],
        "batch_receipt_identity": dict(receipt_identity),
        "batch_receipt_sha256": receipt["batch_receipt_sha256"],
        "receipt_published_and_exact_reopened_before_root": True,
        "authority_status": _generic_authority_status(),
        "outcome_freedom_status": _unattested_outcome_status(),
        "promotion_eligible": False,
        "complete": True,
    }
    return add_self_hash_v1(body, "release_root_sha256")


def build_and_publish_release_v1(
    *,
    release_configuration: object,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    ledger: InMemoryAtomicRunLedgerV1,
) -> dict[str, object]:
    """Compute a deterministic non-authoritative receipt and publish root last.

    Each publisher return is generation-exact-read immediately and byte
    compared.  Callback behavior is still not trusted/adopted authority, which
    is why every returned and persisted status remains false.
    """
    configuration = validate_release_configuration_v1(release_configuration)
    receipt, ledger_charges = _compute_receipt(
        release_configuration=configuration,
        read_exact=read_exact,
        ledger=ledger,
    )
    receipt_raw = canonical_json_bytes_v1(receipt)
    retry_key = _retry_key(configuration)
    receipt_publication_charge = _reserve(
        ledger=ledger,
        configuration=configuration,
        retry_key=retry_key,
        phase="publication-receipt",
        charge=_publication_charge(receipt_raw),
    )
    reopened_receipt, receipt_identity = _publish_and_exact_reopen(
        uri=str(configuration["receipt_uri"]),
        raw=receipt_raw,
        label="batch receipt",
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    if reopened_receipt != receipt:
        _fail("published batch receipt semantic reopen differs")

    root = _build_root(
        configuration=configuration,
        receipt=receipt,
        receipt_identity=receipt_identity,
    )
    root_raw = canonical_json_bytes_v1(root)
    root_publication_charge = _reserve(
        ledger=ledger,
        configuration=configuration,
        retry_key=retry_key,
        phase="publication-root",
        charge=_publication_charge(root_raw),
    )
    reopened_root, root_identity = _publish_and_exact_reopen(
        uri=str(configuration["root_uri"]),
        raw=root_raw,
        label="release root",
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    if reopened_root != root:
        _fail("published release root semantic reopen differs")
    return {
        "root": root,
        "root_identity": root_identity,
        "receipt": receipt,
        "receipt_identity": receipt_identity,
        "ledger_charges": ledger_charges
        + (receipt_publication_charge, root_publication_charge),
        "authority_status": _generic_authority_status(),
        "publication_exact_reopen_verified": True,
    }


def _validate_retained_receipt(
    receipt: object,
    *,
    configuration: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(receipt, "retained batch receipt")
    _exact_keys(
        item,
        {
            "schema_version",
            "coordinates",
            "release_configuration_sha256",
            "source_identity",
            "candidate_identity",
            "work_reservation",
            "work_limits",
            "work_accounting_law",
            "scheduler_result_sha256",
            "scheduler_proxy_receipt",
            "scheduler_proxy_receipt_sha256",
            "authority_status",
            "outcome_freedom_status",
            "promotion_eligible",
            "complete",
            "batch_receipt_sha256",
        },
        "retained batch receipt",
    )
    retained_hash = _digest(item["batch_receipt_sha256"], "batch receipt SHA")
    body = dict(item)
    body.pop("batch_receipt_sha256")
    expected_coordinates = {
        field: configuration[field]
        for field in (
            "run_id",
            "slate_id",
            "batch_id",
            "attempt_id",
            "proxy_id",
        )
    }
    if (
        item["schema_version"] != RECEIPT_SCHEMA
        or canonical_sha256_v1(body) != retained_hash
        or item["coordinates"] != expected_coordinates
        or item["release_configuration_sha256"]
        != configuration["release_configuration_sha256"]
        or _identity(item["source_identity"], "retained source identity")
        != _identity(configuration["source_identity"], "configured source identity")
        or _identity(item["candidate_identity"], "retained candidate identity")
        != _identity(
            configuration["candidate_identity"], "configured candidate identity"
        )
        or _work_vector(item["work_limits"], "retained work limits")
        != _work_vector(configuration["work_limits"], "configured work limits")
        or item["work_accounting_law"] != _work_accounting_law()
        or item["authority_status"] != _generic_authority_status()
        or item["outcome_freedom_status"] != _unattested_outcome_status()
        or item["promotion_eligible"] is not False
        or item["complete"] is not True
    ):
        _fail("retained batch receipt law differs")
    _work_vector(item["work_reservation"], "retained work reservation")
    _digest(item["scheduler_result_sha256"], "scheduler result SHA")
    _digest(item["scheduler_proxy_receipt_sha256"], "proxy receipt SHA")
    return item


def _validate_retained_root(
    root: object,
    *,
    configuration: Mapping[str, object],
    root_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(root, "retained release root")
    _exact_keys(
        item,
        {
            "schema_version",
            "coordinates",
            "release_configuration_sha256",
            "batch_receipt_identity",
            "batch_receipt_sha256",
            "receipt_published_and_exact_reopened_before_root",
            "authority_status",
            "outcome_freedom_status",
            "promotion_eligible",
            "complete",
            "release_root_sha256",
        },
        "retained release root",
    )
    retained_hash = _digest(item["release_root_sha256"], "release root SHA")
    body = dict(item)
    body.pop("release_root_sha256")
    expected_coordinates = {
        field: configuration[field]
        for field in (
            "run_id",
            "slate_id",
            "batch_id",
            "attempt_id",
            "proxy_id",
        )
    }
    if (
        item["schema_version"] != ROOT_SCHEMA
        or canonical_sha256_v1(body) != retained_hash
        or item["coordinates"] != expected_coordinates
        or item["release_configuration_sha256"]
        != configuration["release_configuration_sha256"]
        or item["authority_status"] != _generic_authority_status()
        or item["receipt_published_and_exact_reopened_before_root"] is not True
        or item["outcome_freedom_status"] != _unattested_outcome_status()
        or item["promotion_eligible"] is not False
        or item["complete"] is not True
        or root_identity["uri"] != configuration["root_uri"]
    ):
        _fail("retained release root law differs")
    _identity(item["batch_receipt_identity"], "retained batch receipt identity")
    _digest(item["batch_receipt_sha256"], "retained batch receipt SHA")
    return item


def reopen_release_v1(
    root_identity: object,
    *,
    release_configuration: object,
    read_exact: ReadExact,
    ledger: InMemoryAtomicRunLedgerV1,
) -> dict[str, object]:
    """Generation-exact-reopen and fully recompute one retained release.

    Reopening performs no publication.  Its fresh input and compute work is
    charged again, then deterministic receipt/root bytes are compared with the
    retained objects.
    """
    configuration = validate_release_configuration_v1(release_configuration)
    retry_key = _retry_key(configuration)
    expected_root_identity = _identity(root_identity, "release root identity")
    if expected_root_identity["uri"] != configuration["root_uri"]:
        _fail("release root identity URI differs from configured root")
    root_read_charge = _reserve(
        ledger=ledger,
        configuration=configuration,
        retry_key=retry_key,
        phase="retained-root-read",
        charge=_retained_read_charge(expected_root_identity),
    )
    root, retained_root_identity, root_raw = _exact_json(
        expected_root_identity, read_exact, "release root"
    )
    retained_root = _validate_retained_root(
        root,
        configuration=configuration,
        root_identity=retained_root_identity,
    )
    expected_receipt_identity = _identity(
        retained_root["batch_receipt_identity"],
        "retained batch receipt identity",
    )
    if expected_receipt_identity["uri"] != configuration["receipt_uri"]:
        _fail("retained batch receipt URI differs from configured receipt")
    receipt_read_charge = _reserve(
        ledger=ledger,
        configuration=configuration,
        retry_key=retry_key,
        phase="retained-receipt-read",
        charge=_retained_read_charge(expected_receipt_identity),
    )
    receipt, receipt_identity, receipt_raw = _exact_json(
        expected_receipt_identity,
        read_exact,
        "batch receipt",
    )
    retained_receipt = _validate_retained_receipt(
        receipt,
        configuration=configuration,
    )
    if (
        receipt_identity["uri"] != configuration["receipt_uri"]
        or receipt_identity != retained_root["batch_receipt_identity"]
        or retained_receipt["batch_receipt_sha256"]
        != retained_root["batch_receipt_sha256"]
    ):
        _fail("retained root/receipt binding differs")

    rebuilt_receipt, ledger_charges = _compute_receipt(
        release_configuration=configuration,
        read_exact=read_exact,
        ledger=ledger,
    )
    if canonical_json_bytes_v1(rebuilt_receipt) != receipt_raw:
        _fail("retained batch receipt predecessor replay differs")
    rebuilt_root = _build_root(
        configuration=configuration,
        receipt=rebuilt_receipt,
        receipt_identity=receipt_identity,
    )
    if canonical_json_bytes_v1(rebuilt_root) != root_raw:
        _fail("retained release root predecessor replay differs")
    return {
        "root": retained_root,
        "root_identity": retained_root_identity,
        "receipt": retained_receipt,
        "receipt_identity": receipt_identity,
        "ledger_charges": (root_read_charge, receipt_read_charge)
        + ledger_charges,
        "authority_status": _generic_authority_status(),
        "publication_performed": False,
        "exact_reopen_and_predecessor_replay_verified": True,
    }


__all__ = [
    "CANDIDATE_SCHEMA",
    "CONFIGURATION_SCHEMA",
    "CorpusR6LegalSchedulerReleaseV1Error",
    "InMemoryAtomicRunLedgerV1",
    "LEDGER_SCHEMA",
    "GENERIC_OUTPUT_OBJECT_PREFIX",
    "RECEIPT_SCHEMA",
    "ROOT_SCHEMA",
    "SOURCE_SCHEMA",
    "WORK_FIELDS",
    "add_self_hash_v1",
    "build_and_publish_release_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "reopen_release_v1",
    "validate_release_configuration_v1",
]
