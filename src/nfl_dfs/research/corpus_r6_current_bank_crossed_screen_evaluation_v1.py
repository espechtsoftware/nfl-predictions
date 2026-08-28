"""Leakage-closed held-out evaluator for the R6 current-bank crossed screen.

The evaluator starts only from an immutable per-slate selection receipt.  It
reopens the receipt (and the deterministic nomination in confirmation), then
constructs a finite scientific read capability containing the later-source
catalog and exactly the five held-out world artifacts.  It has no selector
import or callable and accepts no caller-created matrix, metric row, selected
lineup, player/game map, or output URI.

Transport is injected.  The guarded CLI owns the fixed-endpoint GCS adapter;
tests use an in-memory exact-object store.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import resource
import sys
from time import monotonic
from typing import Final
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)


EVALUATOR_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-evaluator-request/v1"
)
EVALUATOR_RUNTIME_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-evaluator-runtime/v1"
)
EVALUATOR_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-evaluator-envelope/v1"
)
FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"
EVALUATOR_SCRIPT_BASENAME: Final = (
    "run_corpus_r6_current_bank_crossed_screen_evaluation_v1.py"
)
_REDIRECT_ENV_KEYS: Final = (
    "STORAGE_EMULATOR_HOST",
    "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "PYTHONHOME",
    "PYTHONPATH",
    "LD_PRELOAD",
    "R6_GCS_ENDPOINT",
    "R6_PROJECT_OVERRIDE",
    "R6_EVALUATOR_COMMAND",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_API_USE_MTLS_ENDPOINT",
    "GOOGLE_API_USE_CLIENT_CERTIFICATE",
    "GCE_METADATA_HOST",
    "GCE_METADATA_ROOT",
    "GCE_METADATA_IP",
    "CLOUDSDK_CONFIG",
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")

# This process is deliberately a scorer, not a solver.  These frozen DK and
# resource constants are repeated locally so importing the evaluator cannot
# transitively import PuLP, optimizer, selector, or exact-solver surfaces.
ROSTER_SIZE: Final = 9
SALARY_CAP: Final = 50_000
MAX_FROM_TEAM: Final = 8
MIN_GAMES: Final = 2
MAXIMUM_PLAYER_COUNT: Final = 512
MAXIMUM_SOURCE_CANDIDATE_ROWS: Final = (
    contract.MAX_SELECTION_CANDIDATES_PER_FOLD
)
MAXIMUM_EVALUATION_CANDIDATES: Final = 8_192
MAXIMUM_LATER_SOURCE_BYTES: Final = 8_000_000
MAXIMUM_COMPRESSED_WORLD_BYTES: Final = 128_000_000
MAXIMUM_PLAYER_ID_MEMBER_BYTES: Final = 1_000_000
MAXIMUM_PLAYER_DRAW_MEMBER_BYTES: Final = (
    MAXIMUM_PLAYER_COUNT * contract.WORLDS_PER_BLOCK * np.dtype(np.float32).itemsize
    + 65_536
)
MAXIMUM_SCORE_MATRIX_BYTES: Final = (
    MAXIMUM_EVALUATION_CANDIDATES
    * contract.WORLDS_PER_BLOCK
    * np.dtype(np.float64).itemsize
)
MAXIMUM_CANDIDATE_WORLD_ADDITIONS_PER_FOLD: Final = (
    MAXIMUM_EVALUATION_CANDIDATES * contract.WORLDS_PER_BLOCK * ROSTER_SIZE
)
MAXIMUM_EVALUATOR_WALL_SECONDS: Final = 1_800
MAXIMUM_EVALUATOR_PEAK_RSS_BYTES: Final = 7_500_000_000
MAXIMUM_ENVELOPE_BYTES: Final = 2_000_000
NPZ_MEMBERS: Final = frozenset({
    "cand_ix.npy", "totals.npy", "tail_line.npy", "player_ids.npy",
    "player_draws.npy",
})

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[
    [str, bytes, Mapping[str, object] | None], Mapping[str, object]
]
LoadArtifactWorlds = Callable[[Mapping[str, object], bytes], object]
CrossScore = Callable[..., np.ndarray]


@dataclass(frozen=True, slots=True)
class ScoringPlayerV1:
    """The exact solver-free catalog fields needed for held-out addition."""

    player_id: str
    position: str
    team: str
    opponent: str
    game_id: str
    salary: int


@dataclass(frozen=True, slots=True)
class ScoringWorldBlockV1:
    """Only the two NPZ values the evaluator is authorized to materialize."""

    block: str
    player_ids: tuple[str, ...]
    player_draws: np.ndarray


class CorpusR6CurrentBankCrossedScreenEvaluationV1Error(ValueError):
    """The immutable held-out evaluator could not prove its authority."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} must be a nonnegative integer")
    return value


def _bounded_string(value: object, *, label: str, maximum: int = 512) -> str:
    retained = _string(value, label=label)
    if len(retained.encode("utf-8")) > maximum:
        _fail(f"{label} exceeds its byte ceiling")
    return retained


def _scoring_player_v1(value: object) -> ScoringPlayerV1:
    row = _mapping(value, label="later-source player")
    player_id = _bounded_string(row.get("id"), label="player id", maximum=256)
    position = _bounded_string(
        row.get("pos"), label="player position", maximum=8
    ).upper()
    team = _bounded_string(row.get("team"), label="player team", maximum=16)
    opponent = _bounded_string(
        row.get("opp"), label="player opponent", maximum=16
    )
    game_id = _bounded_string(
        row.get("game_id"), label="player game id", maximum=128
    )
    salary = _integer(row.get("salary"), label="player salary")
    if (
        position not in {"QB", "RB", "WR", "TE", "DST"}
        or team == opponent
        or salary > SALARY_CAP
    ):
        _fail("later-source player catalog differs")
    return ScoringPlayerV1(
        player_id=player_id,
        position=position,
        team=team,
        opponent=opponent,
        game_id=game_id,
        salary=salary,
    )


def _peak_rss_bytes_v1() -> int:
    # Linux reports ru_maxrss in KiB.  Cloud Run and the supported local
    # execution environment are Linux; fail closed on any impossible value.
    retained = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1_024
    if retained < 0:
        _fail("evaluator peak RSS observation differs")
    return retained


def _require_resource_checkpoint_v1(*, started_at: float, label: str) -> None:
    elapsed = monotonic() - started_at
    if elapsed < 0 or elapsed > MAXIMUM_EVALUATOR_WALL_SECONDS:
        _fail(f"{label} exceeds evaluator wall-time ceiling")
    if _peak_rss_bytes_v1() > MAXIMUM_EVALUATOR_PEAK_RSS_BYTES:
        _fail(f"{label} exceeds evaluator peak-RSS ceiling")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc


def _bind(
    body: Mapping[str, object], identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            body, identity, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    body[field] = contract.canonical_sha256_v1(body)
    return body


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    if value.get(field) != contract.canonical_sha256_v1({
        key: retained for key, retained in value.items() if key != field
    }):
        _fail(f"{label} self hash differs")


def strict_json_v1(raw: bytes, *, label: str) -> dict[str, object]:
    """Parse one UTF-8 JSON object while rejecting duplicate keys."""
    if type(raw) is not bytes:
        _fail(f"{label} exact reader must return bytes")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    def reject_nonfinite_constant(value: str) -> object:
        _fail(f"{label} contains non-finite JSON constant {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonfinite_constant,
        )
    except CorpusR6CurrentBankCrossedScreenEvaluationV1Error:
        raise
    except Exception as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    return _mapping(value, label=label)


def _read_exact_bytes(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} bytes differ from exact identity")
    return raw, identity


def _read_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _read_exact_bytes(
        identity_value, read_exact=read_exact, label=label
    )
    body = strict_json_v1(raw, label=label)
    _bind(body, identity, label=label)
    return body, identity


def build_evaluator_request_v1(
    *,
    phase: str,
    source_ordinal: int,
    design_identity: object,
    topology_identity: object,
    projection_bundle_identity: object,
    selection_receipt_identity: object,
    process_budget_identity: object,
    bootstrap_manifest_identity: object,
    launch_intent_identity: object,
    nomination_identity: object | None = None,
    prior_evaluation_identity: object | None = None,
) -> dict[str, object]:
    """Build the fixed evaluator request; scientific values are not inputs."""
    retained_phase = _string(phase, label="evaluator phase")
    source = _integer(source_ordinal, label="evaluator source ordinal")
    if source >= contract.PANEL_SLATE_COUNT:
        _fail("evaluator source ordinal differs")
    if retained_phase == contract.BROAD_SCREEN_PHASE:
        if nomination_identity is not None:
            _fail("broad evaluator request cannot accept nomination authority")
        nomination = None
    elif retained_phase == contract.CONFIRMATION_PHASE:
        if nomination_identity is None:
            _fail("confirmation evaluator request requires nomination authority")
        nomination = _identity(nomination_identity, label="nomination identity")
    else:
        _fail("evaluator phase differs")
    prior = (
        None
        if prior_evaluation_identity is None
        else _identity(prior_evaluation_identity, label="prior evaluation identity")
    )
    body = {
        "schema_version": EVALUATOR_REQUEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": retained_phase,
        "source_ordinal": source,
        "process_ordinal": source,
        "design_identity": _identity(design_identity, label="design identity"),
        "topology_identity": _identity(topology_identity, label="topology identity"),
        "projection_bundle_identity": _identity(
            projection_bundle_identity, label="projection bundle identity"
        ),
        "selection_receipt_identity": _identity(
            selection_receipt_identity, label="selection receipt identity"
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="process budget identity"
        ),
        "bootstrap_manifest_identity": _identity(
            bootstrap_manifest_identity, label="bootstrap manifest identity"
        ),
        "launch_intent_identity": _identity(
            launch_intent_identity, label="launch intent identity"
        ),
        "nomination_identity": nomination,
        "prior_evaluation_identity": prior,
        "caller_heldout_identities_accepted": False,
        "caller_matrix_or_metric_input_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="evaluator_request_sha256")


def validate_evaluator_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="evaluator request")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "process_ordinal", "design_identity", "topology_identity",
        "projection_bundle_identity", "selection_receipt_identity",
        "process_budget_identity", "bootstrap_manifest_identity",
        "launch_intent_identity", "nomination_identity",
        "prior_evaluation_identity", "caller_heldout_identities_accepted",
        "caller_matrix_or_metric_input_accepted", "policy",
        "evaluator_request_sha256",
    }:
        _fail("evaluator request fields differ")
    _self_hash(item, field="evaluator_request_sha256", label="evaluator request")
    expected = build_evaluator_request_v1(
        phase=item.get("phase"),
        source_ordinal=item.get("source_ordinal"),
        design_identity=item.get("design_identity"),
        topology_identity=item.get("topology_identity"),
        projection_bundle_identity=item.get("projection_bundle_identity"),
        selection_receipt_identity=item.get("selection_receipt_identity"),
        process_budget_identity=item.get("process_budget_identity"),
        bootstrap_manifest_identity=item.get("bootstrap_manifest_identity"),
        launch_intent_identity=item.get("launch_intent_identity"),
        nomination_identity=item.get("nomination_identity"),
        prior_evaluation_identity=item.get("prior_evaluation_identity"),
    )
    if (
        item.get("schema_version") != EVALUATOR_REQUEST_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("process_ordinal") != item.get("source_ordinal")
        or item.get("caller_heldout_identities_accepted") is not False
        or item.get("caller_matrix_or_metric_input_accepted") is not False
        or item.get("policy") != contract.POLICY_CLAIMS
        or contract.canonical_json_bytes_v1(item)
        != contract.canonical_json_bytes_v1(expected)
    ):
        _fail("evaluator request canonical replay differs")
    return expected


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def canonical_evaluator_command_v1() -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str((_repository_root_v1() / "scripts" / EVALUATOR_SCRIPT_BASENAME).resolve()),
        "evaluate-slate",
    ]


def derive_observed_runtime_evidence_v1(
    *, source_ordinal: int, phase: str, environ: Mapping[str, str],
    argv: object, pid: int, parent_pid: int,
) -> dict[str, object]:
    """Bind the observed immutable process; no request may supply this body."""
    environment = dict(environ)
    source = _integer(source_ordinal, label="runtime source ordinal")
    if source >= contract.PANEL_SLATE_COUNT:
        _fail("runtime source ordinal differs")
    retained_phase = _string(phase, label="runtime phase")
    if retained_phase not in {
        contract.BROAD_SCREEN_PHASE, contract.CONFIRMATION_PHASE,
    }:
        _fail("runtime phase differs")
    for key in _REDIRECT_ENV_KEYS:
        if environment.get(key):
            _fail(f"redirect environment {key} is forbidden")
    projects = {
        environment[key]
        for key in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
        if environment.get(key)
    }
    code_commit = environment.get("CODE_SHA", "")
    image_digest = environment.get("R6_RUNTIME_IMAGE_DIGEST", "")
    task_index = environment.get("CLOUD_RUN_TASK_INDEX", "")
    process_ordinal = environment.get("R6_EVALUATOR_PROCESS_ORDINAL", "")
    job_name = environment.get("CLOUD_RUN_JOB", "")
    execution_id = environment.get("CLOUD_RUN_EXECUTION", "")
    if (
        projects != {FIXED_GCP_PROJECT}
        or _COMMIT.fullmatch(code_commit) is None
        or not image_digest.startswith("sha256:")
        or _SHA256.fullmatch(image_digest[7:]) is None
        or not task_index.isdecimal()
        or not process_ordinal.isdecimal()
        or int(task_index) != source
        or int(process_ordinal) != source
        or not job_name
        or len(job_name.encode("utf-8")) > 256
        or not execution_id
        or len(execution_id.encode("utf-8")) > 256
    ):
        _fail("observed evaluator environment differs")
    command = [
        _string(row, label=f"runtime argv[{index}]")
        for index, row in enumerate(_sequence(argv, label="runtime argv"))
    ]
    canonical = canonical_evaluator_command_v1()
    if command != canonical:
        _fail("observed evaluator command differs")
    entrypoint = Path(canonical[1])
    if not entrypoint.is_file():
        _fail("evaluator entrypoint is absent")
    entrypoint_sha = sha256(entrypoint.read_bytes()).hexdigest()
    body = {
        "schema_version": EVALUATOR_RUNTIME_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": retained_phase,
        "source_ordinal": source,
        "process_ordinal": source,
        "project_id": FIXED_GCP_PROJECT,
        "code_commit": code_commit,
        "image_digest": image_digest,
        "job_name": job_name,
        "execution_id": execution_id,
        "task_index": int(task_index),
        "pid": _integer(pid, label="runtime pid"),
        "parent_pid": _integer(parent_pid, label="runtime parent pid"),
        "python_executable": canonical[0],
        "python_version": sys.version.split()[0],
        "entrypoint_path": canonical[1],
        "entrypoint_sha256": entrypoint_sha,
        "command": canonical,
        "command_sha256": contract.canonical_sha256_v1({
            "command": canonical, "entrypoint_sha256": entrypoint_sha,
        }),
        "storage_endpoint": FIXED_STORAGE_ENDPOINT,
        "redirect_environment_present": False,
        "evidence_strength": "process-environment-observation-only",
        "outer_launch_authority_binding_required": True,
        "outer_launch_authority_identity": None,
    }
    return _with_hash(body, field="runtime_evidence_sha256")


def validate_observed_runtime_evidence_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="evaluator runtime evidence")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "process_ordinal", "project_id", "code_commit", "image_digest",
        "job_name", "execution_id", "task_index", "pid", "parent_pid",
        "python_executable", "python_version", "entrypoint_path",
        "entrypoint_sha256", "command", "command_sha256", "storage_endpoint",
        "redirect_environment_present", "evidence_strength",
        "outer_launch_authority_binding_required",
        "outer_launch_authority_identity", "runtime_evidence_sha256",
    }:
        _fail("evaluator runtime evidence fields differ")
    _self_hash(item, field="runtime_evidence_sha256", label="runtime evidence")
    canonical = canonical_evaluator_command_v1()
    entrypoint = Path(canonical[1])
    entrypoint_sha = sha256(entrypoint.read_bytes()).hexdigest()
    if (
        item.get("schema_version") != EVALUATOR_RUNTIME_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("project_id") != FIXED_GCP_PROJECT
        or item.get("storage_endpoint") != FIXED_STORAGE_ENDPOINT
        or item.get("redirect_environment_present") is not False
        or item.get("evidence_strength")
        != "process-environment-observation-only"
        or item.get("outer_launch_authority_binding_required") is not True
        or item.get("outer_launch_authority_identity") is not None
        or item.get("process_ordinal") != item.get("source_ordinal")
        or item.get("phase") not in {
            contract.BROAD_SCREEN_PHASE, contract.CONFIRMATION_PHASE,
        }
        or item.get("command") != canonical
        or item.get("python_executable") != canonical[0]
        or item.get("entrypoint_path") != canonical[1]
        or item.get("entrypoint_sha256") != entrypoint_sha
        or item.get("command_sha256") != contract.canonical_sha256_v1({
            "command": canonical, "entrypoint_sha256": entrypoint_sha,
        })
        or _COMMIT.fullmatch(str(item.get("code_commit", ""))) is None
        or not str(item.get("image_digest", "")).startswith("sha256:")
        or _SHA256.fullmatch(str(item.get("image_digest", ""))[7:]) is None
        or item.get("task_index") != item.get("source_ordinal")
    ):
        _fail("evaluator runtime fixed binding differs")
    for field in ("source_ordinal", "process_ordinal", "task_index", "pid", "parent_pid"):
        _integer(item.get(field), label=f"runtime {field}")
    for field in ("job_name", "execution_id", "python_version"):
        _bounded_string(item.get(field), label=f"runtime {field}", maximum=256)
    return item


class ExactAllowlistedScientificReadClientV1:
    """One-pass later-source/R0..R4 capability created after receipt replay."""

    def __init__(
        self, *, allowed_rows: Sequence[Mapping[str, object]],
        read_exact: ReadExact,
    ) -> None:
        expected_roles = [
            "later-source", *[f"heldout-world-{block}" for block in contract.WORLD_BLOCKS]
        ]
        rows = [_mapping(row, label=f"scientific allowlist[{index}]")
                for index, row in enumerate(allowed_rows)]
        if (
            len(rows) != len(expected_roles)
            or [row.get("role") for row in rows] != expected_roles
            or any(set(row) != {"role", "identity"} for row in rows)
        ):
            _fail("scientific allowlist role/order differs")
        identities = [
            _identity(row["identity"], label=f"scientific {row['role']} identity")
            for row in rows
        ]
        if len({str(row["uri"]) for row in identities}) != len(identities):
            _fail("scientific allowlist URI repeats")
        self._rows = [
            {"role": role, "identity": identity}
            for role, identity in zip(expected_roles, identities, strict=True)
        ]
        self._read_exact = read_exact
        self._next = 0
        self._ledger: list[dict[str, object]] = []

    def read(self, role: str, identity_value: object) -> bytes:
        retained_role = _string(role, label="scientific read role")
        if self._next >= len(self._rows):
            _fail("scientific capability is exhausted")
        expected = self._rows[self._next]
        identity = _identity(identity_value, label=f"{retained_role} read identity")
        if retained_role != expected["role"] or identity != expected["identity"]:
            _fail("scientific object is not addressable at this read ordinal")
        raw, _ = _read_exact_bytes(
            identity, read_exact=self._read_exact, label=retained_role
        )
        self._ledger.append({
            "ordinal": self._next,
            "channel": "process-budget-scientific",
            "role": retained_role,
            "identity": identity,
        })
        self._next += 1
        return raw

    def require_complete(self) -> list[dict[str, object]]:
        if self._next != len(self._rows):
            _fail("scientific capability did not read its exact six-object lattice")
        return [dict(row) for row in self._ledger]


def _later_slate_v1(
    later_source_body: Mapping[str, object], *, slate_id: str,
) -> tuple[dict[str, object], tuple[ScoringPlayerV1, ...]]:
    """Validate the outcome-blind scoring slice without solver imports."""
    frozen = _mapping(later_source_body, label="later source")
    expected_hash = _string(
        frozen.get("freeze_sha256"), label="later source self hash"
    )
    body_without_hash = {
        key: value for key, value in frozen.items() if key != "freeze_sha256"
    }
    policy_fields = (
        "uses_realized_outcomes", "candidate_or_lineup_scores_read",
        "b1_inputs_used", "a2a_inputs_used", "production_inputs_used",
        "historical_scoring_licensed", "production_change_licensed",
    )
    slates = _sequence(frozen.get("slates"), label="later source slates")
    if (
        _SHA256.fullmatch(expected_hash) is None
        or sha256(json.dumps(
            body_without_hash,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")).hexdigest() != expected_hash
        or frozen.get("world_blocks") != list(contract.WORLD_BLOCKS)
        or frozen.get("worlds_per_block") != contract.WORLDS_PER_BLOCK
        or frozen.get("slate_count") != contract.PANEL_SLATE_COUNT
        or len(slates) != contract.PANEL_SLATE_COUNT
        or any(frozen.get(field) is not False for field in policy_fields)
    ):
        _fail("later source freeze scoring authority differs")
    matching = [
        _mapping(row, label="later source slate")
        for row in slates
        if isinstance(row, Mapping) and row.get("slate_id") == slate_id
    ]
    if len(matching) != 1:
        _fail("later source contains no unique evaluator slate")
    slate = _mapping(matching[0], label="later source evaluator slate")
    raw_catalog = _sequence(slate.get("catalog"), label="later source catalog")
    raw_receipts = _sequence(
        slate.get("artifact_receipts"), label="later source artifact receipts"
    )
    if (
        not 1 <= len(raw_catalog) <= MAXIMUM_PLAYER_COUNT
        or slate.get("catalog_sha256")
        != contract.canonical_sha256_v1(raw_catalog)
        or len(raw_receipts) != contract.FOLDS_PER_SLATE
        or slate.get("artifact_receipts_sha256")
        != contract.canonical_sha256_v1(raw_receipts)
    ):
        _fail("later source evaluator slate scoring surface differs")
    players = tuple(_scoring_player_v1(row) for row in raw_catalog)
    player_ids = tuple(player.player_id for player in players)
    if player_ids != tuple(sorted(set(player_ids))):
        _fail("later source evaluator player catalog order differs")
    return slate, players


def _npy_member_header_v1(
    archive: ZipFile, *, name: str,
) -> tuple[tuple[int, ...], bool, np.dtype, int]:
    """Inspect an NPY header and exact member size before materialization."""
    try:
        info = archive.getinfo(name)
        with archive.open(info, "r") as stream:
            version = np.lib.format.read_magic(stream)
            if version == (1, 0):
                shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(
                    stream, max_header_size=10_000
                )
            elif version == (2, 0):
                shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(
                    stream, max_header_size=10_000
                )
            else:
                _fail(f"world artifact {name} NPY version differs")
            header_bytes = stream.tell()
    except CorpusR6CurrentBankCrossedScreenEvaluationV1Error:
        raise
    except Exception as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            f"world artifact {name} header is unreadable"
        ) from exc
    retained_dtype = np.dtype(dtype)
    if retained_dtype.hasobject or fortran_order:
        _fail(f"world artifact {name} dtype/order differs")
    element_count = 1
    for dimension in shape:
        if type(dimension) is not int or dimension < 0:
            _fail(f"world artifact {name} shape differs")
        element_count *= dimension
    expected_bytes = header_bytes + element_count * retained_dtype.itemsize
    if info.file_size != expected_bytes:
        _fail(f"world artifact {name} declared size differs")
    return tuple(shape), bool(fortran_order), retained_dtype, info.file_size


def _load_artifact_worlds_v1(
    receipt: Mapping[str, object], raw: bytes,
) -> ScoringWorldBlockV1:
    """Materialize only bounded player ids/draws from the exact NPZ body."""
    if type(raw) is not bytes or not 1 <= len(raw) <= MAXIMUM_COMPRESSED_WORLD_BYTES:
        _fail("world artifact compressed body exceeds its resource ceiling")
    retained_receipt = _mapping(receipt, label="world artifact receipt")
    block = _string(retained_receipt.get("block"), label="world artifact block")
    candidate_rows = _integer(
        retained_receipt.get("candidate_rows"), label="world artifact candidate rows"
    )
    if (
        block not in contract.WORLD_BLOCKS
        or not 1 <= candidate_rows <= MAXIMUM_SOURCE_CANDIDATE_ROWS
        or retained_receipt.get("bytes") != len(raw)
        or retained_receipt.get("sha256") != sha256(raw).hexdigest()
    ):
        _fail("world artifact receipt/resource authority differs")
    try:
        with ZipFile(BytesIO(raw), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (
                len(names) != len(set(names))
                or set(names) != NPZ_MEMBERS
                or any(
                    info.is_dir()
                    or info.flag_bits & 0x1
                    or info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                    for info in infos
                )
            ):
                _fail("world artifact NPZ member lattice differs")
            cand_shape, _, cand_dtype, _ = _npy_member_header_v1(
                archive, name="cand_ix.npy"
            )
            totals_shape, _, totals_dtype, _ = _npy_member_header_v1(
                archive, name="totals.npy"
            )
            tail_shape, _, tail_dtype, _ = _npy_member_header_v1(
                archive, name="tail_line.npy"
            )
            player_id_shape, _, player_id_dtype, player_id_bytes = (
                _npy_member_header_v1(archive, name="player_ids.npy")
            )
            draw_shape, _, draw_dtype, draw_bytes = _npy_member_header_v1(
                archive, name="player_draws.npy"
            )
            player_count = player_id_shape[0] if len(player_id_shape) == 1 else -1
            if (
                cand_shape != (candidate_rows,)
                or cand_dtype.kind not in {"i", "u"}
                or totals_shape != (candidate_rows, contract.WORLDS_PER_BLOCK)
                or totals_dtype.kind != "f"
                or tail_shape not in {(1,), ()}
                or tail_dtype.kind != "f"
                or not 1 <= player_count <= MAXIMUM_PLAYER_COUNT
                or player_id_dtype.kind not in {"U", "S"}
                or player_id_bytes > MAXIMUM_PLAYER_ID_MEMBER_BYTES
                or draw_shape != (player_count, contract.WORLDS_PER_BLOCK)
                or draw_dtype != np.dtype(np.float32)
                or draw_bytes > MAXIMUM_PLAYER_DRAW_MEMBER_BYTES
            ):
                _fail("world artifact NPZ resource/shape contract differs")
            with np.load(BytesIO(raw), allow_pickle=False) as artifact:
                player_ids_array = np.asarray(artifact["player_ids"])
                player_draws = np.asarray(artifact["player_draws"])
    except CorpusR6CurrentBankCrossedScreenEvaluationV1Error:
        raise
    except (BadZipFile, OSError, ValueError, KeyError) as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "world artifact NPZ is unreadable"
        ) from exc
    player_ids = tuple(player_ids_array.astype(str).tolist())
    if (
        len(player_ids) != player_count
        or len(set(player_ids)) != player_count
        or any(not player_id or len(player_id.encode("utf-8")) > 256 for player_id in player_ids)
        or player_draws.dtype != np.dtype(np.float32)
        or player_draws.shape != (player_count, contract.WORLDS_PER_BLOCK)
        or not np.isfinite(player_draws).all()
    ):
        _fail("world artifact materialized player surface differs")
    draws = np.ascontiguousarray(player_draws, dtype=np.float32)
    draws.flags.writeable = False
    return ScoringWorldBlockV1(
        block=block, player_ids=player_ids, player_draws=draws
    )


def _artifact_receipt_v1(
    slate: Mapping[str, object], *, block: str, expected_identity: object,
) -> dict[str, object]:
    matching = [
        _mapping(row, label=f"later source {block} receipt")
        for row in _sequence(slate.get("artifact_receipts"), label="artifact receipts")
        if isinstance(row, Mapping) and row.get("block") == block
    ]
    if len(matching) != 1:
        _fail(f"later source does not contain one {block} artifact receipt")
    receipt = matching[0]
    expected = _identity(expected_identity, label=f"expected {block} artifact")
    observed = {key: receipt.get(key) for key in ("uri", "generation", "sha256", "bytes")}
    if observed != expected:
        _fail(f"later source {block} artifact differs from projection authority")
    return receipt


def _score_heldout_fold_v1(
    *,
    projection: Mapping[str, object],
    players: Sequence[ScoringPlayerV1],
    receipt: Mapping[str, object],
    raw_artifact: bytes,
    load_artifact_worlds: LoadArtifactWorlds,
    cross_score: CrossScore,
) -> np.ndarray:
    try:
        loaded = load_artifact_worlds(receipt, raw_artifact)
    except Exception as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "held-out artifact scientific validation failed"
        ) from exc
    block = str(projection["heldout_block"])
    if getattr(loaded, "block", None) != block:
        _fail("loaded held-out block differs")
    player_ids = tuple(player.player_id for player in players)
    loaded_ids = tuple(getattr(loaded, "player_ids", ()))
    if set(loaded_ids) != set(player_ids) or len(loaded_ids) != len(player_ids):
        _fail("held-out player universe differs from later-source catalog")
    index = {player_id: row for row, player_id in enumerate(loaded_ids)}
    draws = np.asarray(getattr(loaded, "player_draws", None))
    if (
        draws.dtype != np.dtype(np.float32)
        or draws.shape != (len(player_ids), contract.WORLDS_PER_BLOCK)
        or not np.isfinite(draws).all()
    ):
        _fail("held-out player-world matrix differs")
    aligned = np.ascontiguousarray(
        draws[[index[player_id] for player_id in player_ids]], dtype=np.float32
    )
    rosters = [row["roster_player_ids"] for row in projection["candidates"]]
    try:
        scores = cross_score(
            players, aligned, rosters, expected_worlds=contract.WORLDS_PER_BLOCK
        )
    except Exception as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "held-out candidate cross-score failed"
        ) from exc
    retained = np.asarray(scores)
    if (
        retained.dtype != np.dtype(np.float64)
        or retained.shape != (len(rosters), contract.WORLDS_PER_BLOCK)
        or not np.isfinite(retained).all()
    ):
        _fail("held-out candidate score matrix differs")
    result = np.ascontiguousarray(retained, dtype=np.float64)
    result.flags.writeable = False
    return result


def _audit_dk_classic_v1(
    players: Sequence[ScoringPlayerV1], roster_value: object,
) -> tuple[str, ...]:
    """Recheck only the platform legality needed before scientific scoring."""
    roster = tuple(
        _string(player_id, label="candidate roster player id")
        for player_id in _sequence(roster_value, label="candidate roster")
    )
    if (
        roster != tuple(sorted(roster))
        or len(roster) != ROSTER_SIZE
        or len(set(roster)) != ROSTER_SIZE
    ):
        _fail("candidate roster is not one canonical nine-player identity")
    by_id = {player.player_id: player for player in players}
    if len(by_id) != len(players) or not set(roster) <= set(by_id):
        _fail("candidate roster player universe differs")
    chosen = [by_id[player_id] for player_id in roster]
    positions = Counter(player.position for player in chosen)
    if not (
        positions == Counter({
            "QB": 1,
            "RB": positions["RB"],
            "WR": positions["WR"],
            "TE": positions["TE"],
            "DST": 1,
        })
        and 2 <= positions["RB"] <= 3
        and 3 <= positions["WR"] <= 4
        and 1 <= positions["TE"] <= 2
        and sum(positions.values()) == ROSTER_SIZE
        and 0 < sum(player.salary for player in chosen) <= SALARY_CAP
        and max(Counter(player.team for player in chosen).values())
        <= MAX_FROM_TEAM
        and len({player.game_id for player in chosen}) >= MIN_GAMES
    ):
        _fail("candidate roster DK Classic legality differs")
    return roster


def _cross_score_full_union_v1(
    players: Sequence[ScoringPlayerV1], player_draws: np.ndarray,
    rosters: Sequence[Sequence[object]], *, expected_worlds: int,
) -> np.ndarray:
    """Cross-score immutable candidates without importing any solver surface."""
    rows = tuple(players)
    matrix = np.asarray(player_draws)
    if (
        matrix.dtype != np.dtype(np.float32)
        or matrix.shape != (len(rows), expected_worlds)
        or not np.isfinite(matrix).all()
    ):
        _fail("cross-score player matrix differs")
    identities = tuple(_audit_dk_classic_v1(rows, roster) for roster in rosters)
    if (
        not identities
        or len(identities) > MAXIMUM_EVALUATION_CANDIDATES
        or len(set(identities)) != len(identities)
        or len(identities) * expected_worlds * np.dtype(np.float64).itemsize
        > MAXIMUM_SCORE_MATRIX_BYTES
        or len(identities) * expected_worlds * ROSTER_SIZE
        > MAXIMUM_CANDIDATE_WORLD_ADDITIONS_PER_FOLD
    ):
        _fail("cross-score candidate roster order is empty or duplicated")
    index = {player.player_id: row for row, player in enumerate(rows)}
    scores = np.empty((len(identities), expected_worlds), dtype=np.float64)
    for candidate_index, roster in enumerate(identities):
        scores[candidate_index] = matrix[
            [index[player_id] for player_id in roster]
        ].sum(axis=0, dtype=np.float64)
    if not np.isfinite(scores).all():
        _fail("cross-score candidate totals are non-finite")
    scores.flags.writeable = False
    return scores


def _read_row_v1(
    *, ordinal: int, channel: str, role: str, identity: object,
) -> dict[str, object]:
    return {
        "ordinal": _integer(ordinal, label="read ordinal"),
        "channel": _string(channel, label="read channel"),
        "role": _string(role, label="read role"),
        "identity": _identity(identity, label=f"{role} read identity"),
    }


def _compile_resource_precharge_v1(
    *, bundle: Mapping[str, object], scientific_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    projections = _sequence(
        bundle.get("fold_projections"), label="resource fold projections"
    )
    if len(projections) != contract.FOLDS_PER_SLATE:
        _fail("resource fold projection lattice differs")
    candidate_counts: list[int] = []
    matrix_bytes: list[int] = []
    additions: list[int] = []
    for fold, projection_value in enumerate(projections):
        projection = _mapping(
            projection_value, label=f"resource projection[{fold}]"
        )
        candidates = _sequence(
            projection.get("candidates"), label=f"resource candidates[{fold}]"
        )
        count = len(candidates)
        retained_matrix_bytes = (
            count * contract.WORLDS_PER_BLOCK * np.dtype(np.float64).itemsize
        )
        retained_additions = count * contract.WORLDS_PER_BLOCK * ROSTER_SIZE
        if (
            not 1 <= count <= MAXIMUM_EVALUATION_CANDIDATES
            or retained_matrix_bytes > MAXIMUM_SCORE_MATRIX_BYTES
            or retained_additions > MAXIMUM_CANDIDATE_WORLD_ADDITIONS_PER_FOLD
        ):
            _fail("evaluation projection exceeds resource precharge")
        candidate_counts.append(count)
        matrix_bytes.append(retained_matrix_bytes)
        additions.append(retained_additions)
    identities = [
        _identity(row.get("identity"), label=f"scientific resource[{index}]")
        for index, row in enumerate(scientific_rows)
    ]
    if (
        len(identities) != 1 + contract.FOLDS_PER_SLATE
        or identities[0]["bytes"] > MAXIMUM_LATER_SOURCE_BYTES
        or any(
            identity["bytes"] > MAXIMUM_COMPRESSED_WORLD_BYTES
            for identity in identities[1:]
        )
    ):
        _fail("scientific input exceeds compressed resource precharge")
    body = {
        "schema_version": "corpus-r6-current-bank-evaluator-resource-precharge/v1",
        "candidate_counts_by_fold": candidate_counts,
        "score_matrix_bytes_by_fold": matrix_bytes,
        "candidate_world_additions_by_fold": additions,
        "maximum_player_count": MAXIMUM_PLAYER_COUNT,
        "maximum_source_candidate_rows": MAXIMUM_SOURCE_CANDIDATE_ROWS,
        "maximum_evaluation_candidates": MAXIMUM_EVALUATION_CANDIDATES,
        "maximum_later_source_bytes": MAXIMUM_LATER_SOURCE_BYTES,
        "maximum_compressed_world_bytes": MAXIMUM_COMPRESSED_WORLD_BYTES,
        "maximum_player_draw_member_bytes": MAXIMUM_PLAYER_DRAW_MEMBER_BYTES,
        "maximum_score_matrix_bytes": MAXIMUM_SCORE_MATRIX_BYTES,
        "maximum_candidate_world_additions_per_fold": (
            MAXIMUM_CANDIDATE_WORLD_ADDITIONS_PER_FOLD
        ),
        "maximum_wall_seconds": MAXIMUM_EVALUATOR_WALL_SECONDS,
        "maximum_peak_rss_bytes": MAXIMUM_EVALUATOR_PEAK_RSS_BYTES,
        "maximum_envelope_bytes": MAXIMUM_ENVELOPE_BYTES,
    }
    return _with_hash(body, field="resource_precharge_sha256")


def _compile_evaluator_budget_v1(
    *, request: Mapping[str, object], design: Mapping[str, object],
    bootstrap_manifest: Mapping[str, object], bundle: Mapping[str, object],
    receipt: Mapping[str, object],
    nomination_publication: Mapping[str, object] | None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "design": design,
        "design_publication_identity": request["design_identity"],
        "bootstrap_manifest": bootstrap_manifest,
        "bootstrap_manifest_identity": request["bootstrap_manifest_identity"],
        "launch_intent_identity": request["launch_intent_identity"],
        "projection_bundle": bundle,
        "projection_bundle_identity": request["projection_bundle_identity"],
        "topology_identity": request["topology_identity"],
        "source_ordinal": request["source_ordinal"],
        "selection_receipt": receipt,
        "selection_receipt_identity": request["selection_receipt_identity"],
    }
    if nomination_publication is not None:
        kwargs.update({
            "nomination_publication": nomination_publication,
            "nomination_publication_identity": request["nomination_identity"],
        })
    try:
        return contract.compile_evaluator_process_budget_v1(**kwargs)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc


def _build_runtime_observation_v1(
    *, request: Mapping[str, object], bootstrap_manifest: Mapping[str, object],
    process_budget: Mapping[str, object], observed_runtime: Mapping[str, object],
) -> dict[str, object]:
    try:
        return contract.build_runtime_observation_v1(
            bootstrap_manifest=bootstrap_manifest,
            bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
            process_budget=process_budget,
            process_budget_identity=request["process_budget_identity"],
            launch_intent_identity=request["launch_intent_identity"],
            observed_code_commit=observed_runtime["code_commit"],
            observed_image_digest=observed_runtime["image_digest"],
            observed_command=observed_runtime["command"],
            observed_entrypoint_sha256=observed_runtime["entrypoint_sha256"],
            cloud_job_name=observed_runtime["job_name"],
            cloud_execution_name=observed_runtime["execution_id"],
            cloud_task_index=observed_runtime["task_index"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc


def _build_result_v1(
    *, request: Mapping[str, object], design: Mapping[str, object],
    topology: Mapping[str, object], bundle: Mapping[str, object],
    receipt: Mapping[str, object], later_source_body: Mapping[str, object],
    process_budget: Mapping[str, object],
    bootstrap_manifest: Mapping[str, object],
    runtime_observation: Mapping[str, object],
    fold_stream: object,
    nomination_publication: Mapping[str, object] | None,
) -> dict[str, object]:
    del topology  # Bound independently and through design/bundle/process budget.
    kwargs: dict[str, object] = {
        "design": design,
        "design_publication_identity": request["design_identity"],
        "topology_identity": request["topology_identity"],
        "selection_receipt": receipt,
        "selection_receipt_identity": request["selection_receipt_identity"],
        "projection_bundle": bundle,
        "projection_bundle_identity": request["projection_bundle_identity"],
        "heldout_fold_input_stream": fold_stream,
        "later_source_body": later_source_body,
        "evaluator_process_budget": process_budget,
        "evaluator_process_budget_identity": request["process_budget_identity"],
        "bootstrap_manifest": bootstrap_manifest,
        "bootstrap_manifest_identity": request["bootstrap_manifest_identity"],
        "runtime_observation": runtime_observation,
        "launch_intent_identity": request["launch_intent_identity"],
    }
    if nomination_publication is not None:
        kwargs.update({
            "nomination_publication": nomination_publication,
            "nomination_publication_identity": request["nomination_identity"],
        })
    try:
        return contract.build_evaluation_result_v1(**kwargs)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc


def run_evaluator_v1(
    request_value: object,
    *,
    observed_runtime: object,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Exact-reopen one receipt, consume R0..R4 once, and publish one result."""
    started_at = monotonic()
    request = validate_evaluator_request_v1(request_value)
    runtime_evidence = validate_observed_runtime_evidence_v1(observed_runtime)
    if (
        runtime_evidence["phase"] != request["phase"]
        or runtime_evidence["source_ordinal"] != request["source_ordinal"]
    ):
        _fail("observed evaluator runtime differs from request")
    _require_resource_checkpoint_v1(started_at=started_at, label="evaluator start")
    ledger: list[dict[str, object]] = []

    def opened_json(role: str, identity_value: object, *, channel: str) -> dict[str, object]:
        body, identity = _read_json(
            identity_value, read_exact=read_exact, label=role
        )
        ledger.append(_read_row_v1(
            ordinal=len(ledger), channel=channel, role=role, identity=identity
        ))
        return body

    def opened_bytes(role: str, identity_value: object, *, channel: str) -> bytes:
        raw, identity = _read_exact_bytes(
            identity_value, read_exact=read_exact, label=role
        )
        ledger.append(_read_row_v1(
            ordinal=len(ledger), channel=channel, role=role, identity=identity
        ))
        return raw

    # Bootstrap and receipt/nomination authorities are exact-reopened before a
    # scientific capability capable of addressing held-out artifacts exists.
    design = opened_json(
        "design", request["design_identity"], channel="bootstrap-authority"
    )
    topology = opened_json(
        "topology", request["topology_identity"], channel="bootstrap-authority"
    )
    bootstrap_manifest = opened_json(
        "bootstrap-manifest", request["bootstrap_manifest_identity"],
        channel="bootstrap-authority",
    )
    opened_bytes(
        "launch-intent", request["launch_intent_identity"],
        channel="bootstrap-authority",
    )
    bundle = opened_json(
        "projection-bundle", request["projection_bundle_identity"],
        channel="process-budget",
    )
    receipt = opened_json(
        "selection-receipt", request["selection_receipt_identity"],
        channel="process-budget",
    )
    nomination_publication: dict[str, object] | None = None
    if request["phase"] == contract.CONFIRMATION_PHASE:
        nomination_publication = opened_json(
            "nomination", request["nomination_identity"], channel="process-budget"
        )
    process_budget = opened_json(
        "process-budget", request["process_budget_identity"],
        channel="bootstrap-authority",
    )

    try:
        retained_design = contract.validate_design_authority_v1(
            design, publication_identity=request["design_identity"]
        )
        retained_topology = contract.validate_result_topology_v1(topology)
        _bind(retained_topology, request["topology_identity"], label="topology")
        if (
            retained_design["topology"] != retained_topology
            or retained_design["topology_identity"] != request["topology_identity"]
            or retained_design["bootstrap_manifest"] != bootstrap_manifest
            or retained_design["bootstrap_manifest_identity"]
            != request["bootstrap_manifest_identity"]
        ):
            _fail("evaluator design/topology/bootstrap authority differs")
        retained_bundle = contract.validate_projection_bundle_authority_v1(
            bundle,
            publication_identity=request["projection_bundle_identity"],
            topology=retained_topology,
            topology_identity=request["topology_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc
    if (
        retained_bundle["source_ordinal"] != request["source_ordinal"]
        or receipt.get("phase") != request["phase"]
        or receipt.get("source_ordinal") != request["source_ordinal"]
    ):
        _fail("evaluator phase/source authority differs")

    compiled_budget = _compile_evaluator_budget_v1(
        request=request,
        design=retained_design,
        bootstrap_manifest=bootstrap_manifest,
        bundle=retained_bundle,
        receipt=receipt,
        nomination_publication=nomination_publication,
    )
    try:
        retained_budget = contract.validate_evaluator_process_budget_v1(
            process_budget,
            design=retained_design,
            design_publication_identity=request["design_identity"],
            bootstrap_manifest=bootstrap_manifest,
            bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
            launch_intent_identity=request["launch_intent_identity"],
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc
    _bind(retained_budget, request["process_budget_identity"], label="process budget")
    if contract.canonical_json_bytes_v1(retained_budget) != contract.canonical_json_bytes_v1(
        compiled_budget
    ):
        _fail("published evaluator process budget differs from exact compilation")
    writes = list(retained_budget["write_allowlist"])
    if len(writes) != 1:
        _fail("evaluator process budget requires one publication")
    write = _mapping(writes[0], label="evaluator write budget")
    prior = request["prior_evaluation_identity"]
    if prior is not None and (
        prior["uri"] != write["uri"]
        or int(prior["bytes"]) > int(write["max_bytes"])
    ):
        _fail(
            "prior evaluation identity URI/bytes differ from exact topology output"
        )

    read_rows = [
        _mapping(row, label=f"process budget read[{index}]")
        for index, row in enumerate(retained_budget["read_allowlist"])
    ]
    allowed_roles = [
        "later-source", *[f"heldout-world-{block}" for block in contract.WORLD_BLOCKS]
    ]
    scientific_rows = [row for row in read_rows if row.get("role") in allowed_roles]
    if [row.get("role") for row in scientific_rows] != allowed_roles:
        _fail("evaluator process budget scientific lattice differs")
    resource_precharge = _compile_resource_precharge_v1(
        bundle=retained_bundle, scientific_rows=scientific_rows
    )
    # Runtime/bootstrap equality is a hard boundary: no scientific read
    # capability is constructed until this observation validates.
    runtime_observation = _build_runtime_observation_v1(
        request=request,
        bootstrap_manifest=bootstrap_manifest,
        process_budget=retained_budget,
        observed_runtime=runtime_evidence,
    )
    _require_resource_checkpoint_v1(
        started_at=started_at, label="pre-scientific evaluator"
    )
    gate = ExactAllowlistedScientificReadClientV1(
        allowed_rows=scientific_rows, read_exact=read_exact
    )
    later_source_raw = gate.read("later-source", scientific_rows[0]["identity"])
    later_source_body = strict_json_v1(later_source_raw, label="later-source")
    _bind(
        later_source_body, scientific_rows[0]["identity"], label="later-source"
    )
    slate, players = _later_slate_v1(
        later_source_body, slate_id=str(retained_bundle["slate_id"])
    )
    _require_resource_checkpoint_v1(
        started_at=started_at, label="later-source evaluator"
    )

    consumed_folds: list[int] = []

    def heldout_stream() -> object:
        for fold in range(contract.FOLDS_PER_SLATE):
            _require_resource_checkpoint_v1(
                started_at=started_at, label=f"heldout fold {fold} start"
            )
            block = contract.WORLD_BLOCKS[fold]
            role = f"heldout-world-{block}"
            projection = retained_bundle["fold_projections"][fold]
            artifact_identity = scientific_rows[fold + 1]["identity"]
            receipt_body = _artifact_receipt_v1(
                slate, block=block, expected_identity=artifact_identity
            )
            raw_artifact = gate.read(role, artifact_identity)
            scores = _score_heldout_fold_v1(
                projection=projection,
                players=players,
                receipt=receipt_body,
                raw_artifact=raw_artifact,
                load_artifact_worlds=_load_artifact_worlds_v1,
                cross_score=_cross_score_full_union_v1,
            )
            _require_resource_checkpoint_v1(
                started_at=started_at, label=f"heldout fold {fold} scored"
            )
            consumed_folds.append(fold)
            yield {
                "fold_ordinal": fold,
                "heldout_artifact_identity": artifact_identity,
                "heldout_score_matrix": scores,
            }
            del scores, raw_artifact

    result = _build_result_v1(
        request=request,
        design=retained_design,
        topology=retained_topology,
        bundle=retained_bundle,
        receipt=receipt,
        later_source_body=later_source_body,
        process_budget=retained_budget,
        bootstrap_manifest=bootstrap_manifest,
        runtime_observation=runtime_observation,
        fold_stream=heldout_stream(),
        nomination_publication=nomination_publication,
    )
    if consumed_folds != list(range(contract.FOLDS_PER_SLATE)):
        _fail("evaluation result did not consume the exact R0-through-R4 stream")
    _require_resource_checkpoint_v1(
        started_at=started_at, label="evaluation result construction"
    )
    scientific_ledger = gate.require_complete()
    try:
        retained_result = contract.validate_evaluation_result_v1(result)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenEvaluationV1Error(str(exc)) from exc
    output_raw = contract.canonical_json_bytes_v1(retained_result)
    if len(output_raw) > int(write["max_bytes"]):
        _fail("evaluation result exceeds its precharged byte ceiling")
    published = _identity(
        publish_create_once(str(write["uri"]), output_raw, prior),
        label="published evaluation identity",
    )
    _bind(retained_result, published, label="published evaluation")
    if published["uri"] != write["uri"]:
        _fail("published evaluation URI differs from process budget")
    _require_resource_checkpoint_v1(
        started_at=started_at, label="evaluation publication"
    )

    full_ledger = [*ledger, *[
        {**row, "ordinal": len(ledger) + index}
        for index, row in enumerate(scientific_ledger)
    ]]
    body = {
        "schema_version": EVALUATOR_ENVELOPE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": request["phase"],
        "source_ordinal": request["source_ordinal"],
        "process_ordinal": request["process_ordinal"],
        "evaluator_request_sha256": request["evaluator_request_sha256"],
        "runtime_observation": runtime_observation,
        "runtime_observation_sha256": runtime_observation[
            "runtime_observation_sha256"
        ],
        "process_budget_identity": request["process_budget_identity"],
        "process_budget_sha256": retained_budget[
            "evaluator_process_budget_sha256"
        ],
        "read_ledger": full_ledger,
        "read_ledger_sha256": contract.canonical_sha256_v1(full_ledger),
        "read_object_count": len(full_ledger),
        "receipt_read_ordinal": next(
            row["ordinal"] for row in full_ledger if row["role"] == "selection-receipt"
        ),
        "nomination_read_ordinal": (
            next(row["ordinal"] for row in full_ledger if row["role"] == "nomination")
            if nomination_publication is not None else None
        ),
        "first_heldout_read_ordinal": next(
            row["ordinal"] for row in full_ledger
            if str(row["role"]).startswith("heldout-world-")
        ),
        "heldout_artifact_read_count": contract.FOLDS_PER_SLATE,
        "fold_stream_consumption_order": consumed_folds,
        "evaluation_result_sha256": retained_result["evaluation_result_sha256"],
        "evaluation_publication_identity": published,
        "publication_bytes": len(output_raw),
        "publication_byte_ceiling": int(write["max_bytes"]),
        "resource_precharge": resource_precharge,
        "resource_precharge_sha256": resource_precharge[
            "resource_precharge_sha256"
        ],
        "observed_elapsed_milliseconds": int((monotonic() - started_at) * 1_000),
        "observed_peak_rss_bytes": _peak_rss_bytes_v1(),
        "selector_imported_or_callable": False,
        "caller_matrix_or_metric_input_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    envelope = _with_hash(body, field="evaluator_envelope_sha256")
    if (
        len(contract.canonical_json_bytes_v1(envelope)) + 1
        > MAXIMUM_ENVELOPE_BYTES
    ):
        _fail("evaluator envelope exceeds its byte ceiling")
    return envelope


__all__ = [
    "EVALUATOR_ENVELOPE_SCHEMA",
    "EVALUATOR_REQUEST_SCHEMA",
    "EVALUATOR_RUNTIME_SCHEMA",
    "ExactAllowlistedScientificReadClientV1",
    "CorpusR6CurrentBankCrossedScreenEvaluationV1Error",
    "build_evaluator_request_v1",
    "canonical_evaluator_command_v1",
    "derive_observed_runtime_evidence_v1",
    "run_evaluator_v1",
    "strict_json_v1",
    "validate_evaluator_request_v1",
    "validate_observed_runtime_evidence_v1",
]
