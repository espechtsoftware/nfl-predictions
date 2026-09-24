"""Terminal-first rotated-fit grading for recourse-aware initial books.

The score-free recourse experiment retains one exact control and treatment
80-entry initial book for each of five held-out folds on every one of the 54
R6 slates.  This bridge validates that complete, passed score-free report
before it is given any realized-outcome capability.  It then projects the
already-persisted full-union ``realized_score_micro`` rows onto those books.

The bridge deliberately does *not* score the reachable-union ceiling, choose a
late-swap alternative, query a raw outcome source, or rescore a lineup.  The
five held-out folds reuse each slate five times, so their 270 book-weeks are a
paired rotated-fit diagnostic only.  They are not an all-block final-fit
54-week benchmark and must never be ranked beside one.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import math
import re
from typing import Final
from zoneinfo import ZoneInfo

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS
from nfl_dfs.analysis.recourse_aware_initial import (
    ALTERNATIVE_CAP,
    PROTOCOL_SHA256,
    TAILS,
    VERSION as MECHANISM_VERSION,
    aggregate_scorefree_folds,
)
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_realized_score_authority_adapter_v1 as score_authority,
)


BRIDGE_SCHEMA: Final = "corpus-r6-recourse-aware-initial-realized-bridge/v1"
TERMINAL_BOOK_PROOF_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-terminal-book-proof/v1"
)
ROSTER_SCORE_ROW_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-realized-roster-row/v1"
)
BOOK_WEEK_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-realized-book-week/v1"
)
FOLD_PATH_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-realized-fold-path/v1"
)
ARM_RESULT_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-realized-arm-result/v1"
)
ROTATED_FIT_PAIRED_DIAGNOSTIC_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-realized-rotated-fit-paired-diagnostic/v1"
)
PUBLICATION_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-realized-publication-envelope/v1"
)
CLOUD_ENTRYPOINT_REGISTRATION_SCHEMA: Final = (
    "corpus-r6-recourse-aware-initial-realized-cloud-entrypoint/v1"
)

MODE_ONE_SLATE_SMOKE: Final = "one-slate-smoke"
MODE_FULL_PANEL: Final = "full-54"
ARMS: Final = ("control", "treatment")
ENTRY_BUDGET: Final = 80
PANEL_SLATE_COUNT: Final = 54
FOLD_COUNT: Final = 5
MICRO_DK_PER_POINT: Final = score_authority.MICRO_DK_PER_POINT
THRESHOLDS_DK: Final = score_authority.THRESHOLDS_DK

RUN_ID: Final = "20260817-recourse-aware-initial-book-scorefree-v1"
REALIZED_PROTOCOL_RELATIVE_PATH: Final = (
    "reports/2026-08-29-recourse-aware-initial-book-realized-bridge-protocol.md"
)
REALIZED_PROTOCOL_SHA256: Final = (
    "957e1f45b8d96771f4b3c309384e495688093c062d7d32031c886f371c3fd9bb"
)
SCOREFREE_REPORT_URI: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    f"recourse-aware-initial-book-runs/{RUN_ID}/report.json"
)
SCOREFREE_TERMINAL_URI: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    f"recourse-aware-initial-book-runs/{RUN_ID}/terminal-root.json"
)
SCOREFREE_TERMINAL_SCHEMA: Final = (
    "recourse-aware-initial-book-single-job-terminal-root-v1"
)
TRANSPORT_AMENDMENT_SHA256: Final = (
    "22783dff9d5ff8a74cf9b79183901957c55ba0599823d752ef9d65b765a74a0f"
)
TERMINAL_AUTHORITY_AMENDMENT_SHA256: Final = (
    "d43588901cb9c47f927646e5d394a4036cb5e8a7e626fb4208674bb82f93501a"
)
FROZEN_CODE_SHA: Final = "96f4487bdefa297f66d03e4aca896728581540b2"
FROZEN_IMAGE: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs@sha256:"
    "9956f2b4444bc60255c29a1844c23a1f772d6b0c85ae1a532e032ece975e86ed"
)
FROZEN_SOURCE_HASHES: Final = {
    "reports/2026-08-16-constraint-lattice-scorefree-protocol.md": (
        "f8591d24dd56749e5b56235f9636687fd41bd1a78991fdb60cfbb092ee65bf62"
    ),
    "reports/2026-08-16-constraint-lattice-source-and-execution-amendment.md": (
        "35ea1f0dba3be5311631d51057c7667cb624bcdc19be75e2b202c57e297e8321"
    ),
    "reports/2026-08-17-recourse-aware-initial-book-execution-protocol.md": (
        "3991fdbf36c2018b2ec11625a6be62990c100fdf1f47bde3985c2327e3248c9b"
    ),
    "reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md": (
        "0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077"
    ),
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json": (
        "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
    ),
}
SOURCE_PANELS: Final = tuple(
    f"20260813-sis-asoe-treatment-r{block}-v1" for block in range(FOLD_COUNT)
)
FORENSIC_MANIFEST_SHA256: Final = (
    "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
)
CBWU_REPORT_SHA256: Final = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)

OUTCOME_AUTHORITY_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-attributions/"
        "20260827-foundry-v12-r6-full-union-attribution-v1/"
        "attribution-release.json"
    ),
    "generation": "1787852572673874",
    "sha256": "caaddba5ef709b1e4df8c60480e2a50a37063917ef9b8d3c788f5e107133722b",
    "bytes": 114_551,
}
OUTPUT_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-recourse-aware-initial-realized/"
)
SMOKE_OUTPUT_FILENAME: Final = (
    "recourse-aware-initial-realized-one-slate-smoke.json"
)
FULL_OUTPUT_FILENAME: Final = (
    "recourse-aware-initial-realized-full-54-rotated-fit-diagnostic.json"
)
OUTPUT_FILENAME_BY_MODE: Final = {
    MODE_ONE_SLATE_SMOKE: SMOKE_OUTPUT_FILENAME,
    MODE_FULL_PANEL: FULL_OUTPUT_FILENAME,
}
ENTRYPOINT_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_recourse_aware_initial_realized_bridge_v1.py"
)
ENTRYPOINT_IMAGE_PATH: Final = f"/app/{ENTRYPOINT_RELATIVE_PATH}"
ENTRYPOINT_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    ENTRYPOINT_IMAGE_PATH,
    "publish",
)

MAXIMUM_SCOREFREE_REPORT_BYTES: Final = 256_000_000
MAXIMUM_ATTRIBUTION_ROOT_BYTES: Final = 4_000_000
MAXIMUM_ATTRIBUTION_SHARD_BYTES: Final = 512_000_000
MAXIMUM_REPORT_BYTES: Final = 512_000_000

ReadExact = Callable[[Mapping[str, object]], bytes]
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SHARD_SCHEMA: Final = "recourse-aware-initial-book-scorefree-shard-v1"
_REPORT_SCHEMA: Final = "recourse-aware-initial-book-scorefree-report-v1"
_FORBIDDEN_SCOREFREE_KEYS: Final = frozenset({
    "actual_score", "final_score", "actual_rank", "actual_ownership",
    "selected_rank", "contest_rank", "payout", "roi", "labels_complete",
    "realized_score_micro", "realized_score", "outcome_snapshot",
    "outcome_authority", "persisted_realized_attribution",
})
_OUTCOME_LIKE_KEY_TOKENS: Final = (
    "actual_score", "actual_rank", "actual_ownership", "contest_rank",
    "final_score", "outcome", "payout", "realized_score", "roi",
)
_REPORT_FIELDS: Final = frozenset({
    "version", "mechanism_version", "protocol_sha256",
    "uses_realized_outcomes", "production_change_licensed",
    "historical_policy_diagnostic_licensed", "mechanical", "aggregate",
    "by_block", "by_season", "selection_effective_rank",
    "leave_one_slate_out_influence", "gate_diagnostics", "conditions",
    "passed", "disposition", "run_id", "code_sha", "analysis_image",
    "source_hashes", "source_panels", "forensic_manifest_sha256",
    "cbwu_report_sha256", "source_artifacts", "shards",
})
_SHARD_FIELDS: Final = frozenset({
    "version", "run_id", "uses_realized_outcomes",
    "production_change_licensed", "historical_scoring_licensed", "season",
    "week", "code_sha", "analysis_image", "source_hashes", "source_panels",
    "forensic_manifest_sha256", "cbwu_report_sha256", "decision_time",
    "artifact_receipts", "folds",
})
_FOLD_FIELDS: Final = frozenset({
    "version", "uses_realized_outcomes", "season", "week",
    "heldout_block", "training_blocks", "candidate_budget",
    "alternative_cap", "control", "treatment", "selected_identity_overlap",
    "selected_identity_jaccard", "control_selected_rosters",
    "treatment_selected_rosters",
})
_METRIC_FIELDS: Final = frozenset({
    "version", "uses_realized_outcomes", "entries", "worlds",
    "initial_coverage", "reachable_union_coverage", "reachable_alternatives",
    "alternatives_per_entry", "distinct_locked_slot_signatures",
    "locked_slot_count_distribution", "locked_slot_index_distribution",
    "locked_player_frequency", "locked_signature_frequency",
})
_TERMINAL_ROOT_FIELDS: Final = frozenset({
    "version", "run_id", "job", "job_uid", "frozen_code_sha",
    "frozen_image", "transport_amendment_sha256",
    "terminal_authority_amendment_sha256",
    "scorefree_report_identity", "scorefree_report_sha256", "shard_count",
    "fold_count", "shard_identity_ledger", "shard_identity_ledger_sha256",
    "harvest_completion_sha256", "grid_terminal_sha256",
    "canary_completion_sha256", "job_restoration_sha256",
    "completion_sha256", "passes_scorefree_gate",
    "historical_policy_diagnostic_licensed", "disposition",
    "uses_realized_outcomes", "production_change_licensed",
    "terminal_before_realized_outcome_read", "complete",
    "terminal_root_sha256",
})


class CorpusR6RecourseAwareInitialRealizedBridgeV1Error(ValueError):
    """The recourse terminal-first realized bridge failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6RecourseAwareInitialRealizedBridgeV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6RecourseAwareInitialRealizedBridgeV1Error(str(exc)) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def canonical_line_json_bytes_v1(value: object) -> bytes:
    """Return the exact newline-terminated encoding used by the frozen report."""
    return canonical_json_bytes_v1(value) + b"\n"


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6RecourseAwareInitialRealizedBridgeV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _signed_integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be one exact integer")
    return value


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    body[field] = canonical_sha256_v1(body)
    return body


def _fraction(numerator: int, denominator: int) -> dict[str, int]:
    if denominator < 1:
        _fail("fraction denominator must be positive")
    return {"numerator": numerator, "denominator": denominator}


def _assert_scorefree(value: object, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized == "uses_realized_outcomes":
                if child is not False:
                    _fail(f"score-free terminal outcome law differs at {path}.{key}")
            elif normalized == "terminal_before_realized_outcome_read":
                if child is not True:
                    _fail(f"score-free terminal ordering law differs at {path}.{key}")
            elif normalized in _FORBIDDEN_SCOREFREE_KEYS or any(
                token in normalized for token in _OUTCOME_LIKE_KEY_TOKENS
            ):
                _fail(f"score-free terminal contains outcome field {path}.{key}")
            _assert_scorefree(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_scorefree(child, path=f"{path}[{index}]")


def _open_json_v1(
    identity_value: object,
    *,
    read_exact: ReadExact,
    maximum_bytes: int,
    label: str,
    newline_terminated: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes or not callable(read_exact):
        _fail(f"{label} exact-read boundary differs")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ from identity")
    parse_raw = raw[:-1] if newline_terminated and raw.endswith(b"\n") else raw
    if newline_terminated and (not raw.endswith(b"\n") or parse_raw.endswith(b"\n")):
        _fail(f"{label} newline law differs")
    try:
        value = batch.parse_canonical_json_bytes(parse_raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6RecourseAwareInitialRealizedBridgeV1Error(str(exc)) from exc
    return _mapping(value, label=label), identity


def _roster_grid(value: object) -> tuple[tuple[str, ...], ...]:
    rows = _sequence(value, label="score-free selected rosters")
    rosters: list[tuple[str, ...]] = []
    for raw in rows:
        roster = tuple(str(player) for player in _sequence(raw, label="selected roster"))
        if len(roster) != 9 or tuple(sorted(roster)) != roster or len(set(roster)) != 9:
            _fail("score-free selected roster differs")
        rosters.append(roster)
    if len(rosters) != ENTRY_BUDGET or len(set(rosters)) != ENTRY_BUDGET:
        _fail("score-free exact-80 roster grid differs")
    return tuple(rosters)


def _validate_metric_book(value: object, *, candidate_budget: int) -> None:
    metric = _mapping(value, label="score-free metric book")
    if (
        set(metric) != _METRIC_FIELDS
        or metric.get("version") != MECHANISM_VERSION
        or metric.get("uses_realized_outcomes") is not False
        or metric.get("entries") != ENTRY_BUDGET
        or metric.get("worlds") != 10_000
    ):
        _fail("score-free metric-book identity differs")
    expected_tails = {str(int(threshold)) for threshold in TAILS}
    for family in ("initial_coverage", "reachable_union_coverage"):
        coverage = _mapping(metric.get(family), label=f"score-free {family}")
        if set(coverage) != expected_tails:
            _fail("score-free metric-book tail grid differs")
        previous: int | None = None
        for threshold in sorted((int(raw) for raw in coverage), reverse=True):
            row = _mapping(coverage[str(threshold)], label="score-free tail row")
            events, rate = row.get("events"), row.get("rate")
            if (
                set(row) != {"events", "rate"}
                or type(events) is not int
                or not 0 <= events <= 10_000
                or not isinstance(rate, (int, float))
                or not math.isfinite(float(rate))
                or not math.isclose(float(rate), events / 10_000, rel_tol=0.0,
                                    abs_tol=1e-12)
                or (previous is not None and events < previous)
            ):
                _fail("score-free metric-book tail value differs")
            previous = events
    reachable = metric.get("reachable_alternatives")
    alternatives = _mapping(
        metric.get("alternatives_per_entry"), label="score-free alternative breadth"
    )
    if (
        type(reachable) is not int
        or not 1 <= reachable <= candidate_budget
        or set(alternatives) != {"minimum", "median", "mean", "maximum"}
    ):
        _fail("score-free alternative breadth differs")
    minimum = alternatives["minimum"]
    median_value = alternatives["median"]
    mean_value = alternatives["mean"]
    maximum = alternatives["maximum"]
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or not isinstance(median_value, (int, float))
        or not isinstance(mean_value, (int, float))
        or not 1 <= minimum <= median_value <= maximum <= ALTERNATIVE_CAP
        or not minimum <= mean_value <= maximum
    ):
        _fail("score-free alternative distribution differs")
    locked_counts = _mapping(
        metric.get("locked_slot_count_distribution"),
        label="score-free locked-slot counts",
    )
    slot_counts = _mapping(
        metric.get("locked_slot_index_distribution"),
        label="score-free locked-slot indices",
    )
    if (
        set(locked_counts) != {str(index) for index in range(10)}
        or set(slot_counts) != {str(index) for index in range(9)}
        or any(type(raw) is not int or raw < 0 for raw in locked_counts.values())
        or any(type(raw) is not int or raw < 0 for raw in slot_counts.values())
        or sum(locked_counts.values()) != ENTRY_BUDGET
    ):
        _fail("score-free locked-slot distribution differs")
    locked_total = sum(index * int(locked_counts[str(index)]) for index in range(10))
    if sum(int(value) for value in slot_counts.values()) != locked_total:
        _fail("score-free locked-slot total differs")
    players = [
        _mapping(row, label="score-free locked player")
        for row in _sequence(metric.get("locked_player_frequency"),
                             label="score-free locked players")
    ]
    if (
        players != sorted(players, key=lambda row: str(row.get("player_id", "")))
        or len({str(row.get("player_id", "")) for row in players}) != len(players)
        or any(
            set(row) != {"player_id", "entries"}
            or not str(row["player_id"])
            or type(row["entries"]) is not int
            or not 1 <= int(row["entries"]) <= ENTRY_BUDGET
            for row in players
        )
        or sum(int(row["entries"]) for row in players) != locked_total
    ):
        _fail("score-free locked-player distribution differs")
    signatures = [
        _mapping(row, label="score-free locked signature")
        for row in _sequence(metric.get("locked_signature_frequency"),
                             label="score-free locked signatures")
    ]
    if (
        not signatures
        or sum(int(row.get("entries", 0)) for row in signatures) != ENTRY_BUDGET
        or metric.get("distinct_locked_slot_signatures") != len(signatures)
    ):
        _fail("score-free locked-signature distribution differs")
    canonical: list[tuple[tuple[int, str], ...]] = []
    for row in signatures:
        signature = _sequence(row.get("signature"), label="locked signature")
        normalized = tuple(
            (int(item[0]), str(item[1]))
            for item in (
                _sequence(raw, label="locked signature member") for raw in signature
            )
        )
        if (
            set(row) != {"signature", "entries"}
            or type(row["entries"]) is not int
            or int(row["entries"]) <= 0
            or len(normalized) > 9
            or any(not 0 <= slot < 9 or not player for slot, player in normalized)
            or len({slot for slot, _ in normalized}) != len(normalized)
            or len({player for _, player in normalized}) != len(normalized)
        ):
            _fail("score-free locked signature is malformed")
        canonical.append(normalized)
    if canonical != sorted(canonical) or len(set(canonical)) != len(canonical):
        _fail("score-free locked signature order differs")


def _validate_fold(
    value: object, *, season: int, week: int, block: str,
) -> tuple[dict[str, object], dict[str, tuple[tuple[str, ...], ...]]]:
    row = _mapping(value, label="score-free fold")
    candidate_budget = row.get("candidate_budget")
    if (
        set(row) != _FOLD_FIELDS
        or row.get("version") != MECHANISM_VERSION
        or row.get("uses_realized_outcomes") is not False
        or row.get("season") != season
        or row.get("week") != week
        or row.get("heldout_block") != block
        or row.get("training_blocks")
        != [value for value in REGISTERED_BLOCKS if value != block]
        or type(candidate_budget) is not int
        or candidate_budget < ENTRY_BUDGET
        or row.get("alternative_cap") != ALTERNATIVE_CAP
    ):
        _fail("score-free fold identity/mechanics differ")
    _validate_metric_book(row.get("control"), candidate_budget=candidate_budget)
    _validate_metric_book(row.get("treatment"), candidate_budget=candidate_budget)
    books = {
        arm: _roster_grid(row.get(f"{arm}_selected_rosters")) for arm in ARMS
    }
    overlap = len(set(books["control"]) & set(books["treatment"]))
    expected_jaccard = overlap / (2 * ENTRY_BUDGET - overlap)
    if (
        row.get("selected_identity_overlap") != overlap
        or not isinstance(row.get("selected_identity_jaccard"), (int, float))
        or not math.isclose(
            float(row["selected_identity_jaccard"]), expected_jaccard,
            rel_tol=0.0, abs_tol=1e-12,
        )
    ):
        _fail("score-free selected identity overlap differs")
    return row, books


def _validate_receipt(value: object, *, expected_block: str) -> dict[str, object]:
    row = _mapping(value, label="score-free artifact receipt")
    expected_fields = {
        "block", "source_panel", "candidate_rows", "uri", "sha256",
        "generation", "updated", "bytes",
    }
    block_ordinal = int(expected_block[1:])
    if (
        set(row) != expected_fields
        or row.get("block") != expected_block
        or row.get("source_panel") != SOURCE_PANELS[block_ordinal]
        or type(row.get("candidate_rows")) is not int
        or int(row["candidate_rows"]) < ENTRY_BUDGET
        or type(row.get("uri")) is not str
        or not str(row["uri"]).startswith("gs://")
        or type(row.get("generation")) is not str
        or not str(row["generation"]).isdigit()
        or int(str(row["generation"])) < 1
        or type(row.get("updated")) is not str
        or not row["updated"]
        or type(row.get("bytes")) is not int
        or int(row["bytes"]) < 1
    ):
        _fail("score-free artifact receipt differs")
    _digest(row.get("sha256"), label="score-free artifact receipt SHA")
    return row


def _validate_decision_time(value: object) -> None:
    if type(value) is not str:
        _fail("score-free decision time differs")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CorpusR6RecourseAwareInitialRealizedBridgeV1Error(
            "score-free decision time differs"
        ) from exc
    if stamp.tzinfo is None or stamp.astimezone(
        ZoneInfo("America/New_York")
    ).strftime("%H:%M") != "15:55":
        _fail("score-free decision time differs")


def _validate_scorefree_terminal_root_v1(
    value: object, *, identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    root = _mapping(value, label="recourse score-free terminal root")
    _assert_scorefree(root)
    if set(root) != _TERMINAL_ROOT_FIELDS:
        _fail("score-free terminal-root fields differ")
    retained_hash = _digest(
        root.get("terminal_root_sha256"), label="score-free terminal-root SHA"
    )
    if retained_hash != canonical_sha256_v1({
        key: child for key, child in root.items()
        if key != "terminal_root_sha256"
    }):
        _fail("score-free terminal-root self hash differs")
    for field in (
        "shard_identity_ledger_sha256", "harvest_completion_sha256",
        "grid_terminal_sha256", "canary_completion_sha256",
        "job_restoration_sha256", "completion_sha256",
    ):
        _digest(root.get(field), label=f"score-free terminal {field}")
    if (
        identity.get("uri") != SCOREFREE_TERMINAL_URI
        or root.get("version") != SCOREFREE_TERMINAL_SCHEMA
        or root.get("run_id") != RUN_ID
        or root.get("job") != "atlas-cbc-32g-full-2023-w8-v1"
        or root.get("job_uid") != "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
        or root.get("frozen_code_sha") != FROZEN_CODE_SHA
        or root.get("frozen_image") != FROZEN_IMAGE
        or root.get("transport_amendment_sha256")
        != TRANSPORT_AMENDMENT_SHA256
        or root.get("terminal_authority_amendment_sha256")
        != TERMINAL_AUTHORITY_AMENDMENT_SHA256
        or root.get("shard_count") != PANEL_SLATE_COUNT
        or root.get("fold_count") != PANEL_SLATE_COUNT * FOLD_COUNT
        or root.get("passes_scorefree_gate") is not True
        or root.get("historical_policy_diagnostic_licensed") is not True
        or root.get("disposition")
        != "recourse-aware-initial-book-premise-passes"
        or root.get("uses_realized_outcomes") is not False
        or root.get("production_change_licensed") is not False
        or root.get("terminal_before_realized_outcome_read") is not True
        or root.get("complete") is not True
    ):
        _fail("score-free terminal-root authority/gate differs")
    report_identity = _identity(
        root.get("scorefree_report_identity"), label="score-free report identity"
    )
    if (
        report_identity["uri"] != SCOREFREE_REPORT_URI
        or root.get("scorefree_report_sha256") != report_identity["sha256"]
    ):
        _fail("score-free terminal-root report binding differs")
    ledger = [
        _mapping(row, label=f"score-free shard ledger[{index}]")
        for index, row in enumerate(_sequence(
            root.get("shard_identity_ledger"), label="score-free shard ledger"
        ))
    ]
    expected_grid = [
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    if (
        len(ledger) != PANEL_SLATE_COUNT
        or root.get("shard_identity_ledger_sha256") != canonical_sha256_v1(ledger)
    ):
        _fail("score-free terminal-root shard ledger hash/count differs")
    identities: set[tuple[str, str, str, int]] = set()
    for source, (row, (season, week)) in enumerate(zip(
        ledger, expected_grid, strict=True,
    )):
        if set(row) != {
            "source_ordinal", "season", "week", "execution",
            "execution_metadata_sha256", "shard_identity",
        } or row.get("source_ordinal") != source or row.get("season") != season or \
                row.get("week") != week or type(row.get("execution")) is not str or \
                not row["execution"]:
            _fail("score-free terminal-root shard coordinate differs")
        _digest(
            row.get("execution_metadata_sha256"),
            label="score-free execution metadata SHA",
        )
        shard_identity = _identity(
            row.get("shard_identity"), label="score-free shard identity"
        )
        expected_uri = SCOREFREE_REPORT_URI.removesuffix("report.json") + (
            f"slate-{season}-{week}.json"
        )
        identity_key = (
            str(shard_identity["uri"]), str(shard_identity["generation"]),
            str(shard_identity["sha256"]), int(shard_identity["bytes"]),
        )
        if shard_identity["uri"] != expected_uri or identity_key in identities:
            _fail("score-free terminal-root shard identity differs")
        identities.add(identity_key)
    return root, report_identity, ledger


def reopen_terminal_scorefree_books_v1(
    *, scorefree_terminal_identity: object, read_scorefree_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open terminal root and replay all 54x5 books before outcomes."""
    terminal_body, terminal_identity = _open_json_v1(
        scorefree_terminal_identity,
        read_exact=read_scorefree_exact,
        maximum_bytes=MAXIMUM_SCOREFREE_REPORT_BYTES,
        label="recourse score-free terminal root",
        newline_terminated=True,
    )
    terminal_root, scorefree_report_identity, shard_ledger = (
        _validate_scorefree_terminal_root_v1(
            terminal_body, identity=terminal_identity,
        )
    )
    report, identity = _open_json_v1(
        scorefree_report_identity,
        read_exact=read_scorefree_exact,
        maximum_bytes=MAXIMUM_SCOREFREE_REPORT_BYTES,
        label="recourse score-free terminal report",
        newline_terminated=True,
    )
    if identity != scorefree_report_identity:
        _fail("score-free terminal report identity differs")
    _assert_scorefree(report)
    if (
        set(report) != _REPORT_FIELDS
        or report.get("version") != _REPORT_SCHEMA
        or report.get("mechanism_version") != MECHANISM_VERSION
        or report.get("protocol_sha256") != PROTOCOL_SHA256
        or report.get("run_id") != RUN_ID
        or report.get("code_sha") != FROZEN_CODE_SHA
        or report.get("analysis_image") != FROZEN_IMAGE
        or report.get("source_hashes") != FROZEN_SOURCE_HASHES
        or report.get("source_panels") != list(SOURCE_PANELS)
        or report.get("forensic_manifest_sha256") != FORENSIC_MANIFEST_SHA256
        or report.get("cbwu_report_sha256") != CBWU_REPORT_SHA256
        or report.get("uses_realized_outcomes") is not False
        or report.get("production_change_licensed") is not False
        or report.get("historical_policy_diagnostic_licensed") is not True
        or report.get("passed") is not True
        or report.get("disposition")
        != "recourse-aware-initial-book-premise-passes"
        or report.get("mechanical") != {
            "slates": PANEL_SLATE_COUNT,
            "folds": PANEL_SLATE_COUNT * FOLD_COUNT,
            "worlds_per_fold": 10_000,
            "all_valid": True,
        }
    ):
        _fail("score-free terminal report authority/gate differs")
    conditions = _mapping(report.get("conditions"), label="score-free conditions")
    expected_conditions = {
        "reachable_p230_strict_and_three_blocks",
        "reachable_p240_p220_p210_nondecline",
        "initial_p240_p230_p220_nondecline",
        "initial_p194_retention_at_least_95pct",
        "mean_reachable_alternatives_nondecline",
        "locked_slot_signature_nondecline",
    }
    if set(conditions) != expected_conditions or any(value is not True for value in conditions.values()):
        _fail("score-free terminal report did not pass every frozen condition")

    shards = [
        _mapping(row, label=f"score-free shard[{index}]")
        for index, row in enumerate(_sequence(report.get("shards"), label="score-free shards"))
    ]
    expected_grid = [
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    if len(shards) != PANEL_SLATE_COUNT or [
        (row.get("season"), row.get("week")) for row in shards
    ] != expected_grid:
        _fail("score-free terminal slate grid differs")
    for shard, ledger_row in zip(shards, shard_ledger, strict=True):
        shard_identity = _identity(
            ledger_row.get("shard_identity"), label="score-free shard identity"
        )
        shard_raw = canonical_line_json_bytes_v1(shard)
        if (
            shard_identity["sha256"] != sha256(shard_raw).hexdigest()
            or shard_identity["bytes"] != len(shard_raw)
        ):
            _fail("score-free report shard differs from terminal identity ledger")

    all_folds: list[dict[str, object]] = []
    all_receipts: list[dict[str, object]] = []
    slate_books: list[dict[str, object]] = []
    receipt_identities: set[tuple[str, str, str, int]] = set()
    for source_ordinal, (shard, coordinate) in enumerate(zip(shards, expected_grid, strict=True)):
        season, week = coordinate
        if (
            set(shard) != _SHARD_FIELDS
            or shard.get("version") != _SHARD_SCHEMA
            or shard.get("run_id") != RUN_ID
            or shard.get("uses_realized_outcomes") is not False
            or shard.get("production_change_licensed") is not False
            or shard.get("historical_scoring_licensed") is not False
            or shard.get("season") != season
            or shard.get("week") != week
            or shard.get("code_sha") != FROZEN_CODE_SHA
            or shard.get("analysis_image") != FROZEN_IMAGE
            or shard.get("source_hashes") != FROZEN_SOURCE_HASHES
            or shard.get("source_panels") != list(SOURCE_PANELS)
            or shard.get("forensic_manifest_sha256") != FORENSIC_MANIFEST_SHA256
            or shard.get("cbwu_report_sha256") != CBWU_REPORT_SHA256
        ):
            _fail("score-free shard authority differs")
        _validate_decision_time(shard.get("decision_time"))
        raw_receipts = _sequence(
            shard.get("artifact_receipts"), label="score-free artifact receipts"
        )
        raw_folds = _sequence(shard.get("folds"), label="score-free folds")
        if len(raw_receipts) != FOLD_COUNT or len(raw_folds) != FOLD_COUNT:
            _fail("score-free shard fold/receipt grid differs")
        books_by_arm: dict[str, list[tuple[tuple[str, ...], ...]]] = {
            arm: [] for arm in ARMS
        }
        for fold_ordinal, block in enumerate(REGISTERED_BLOCKS):
            receipt = _validate_receipt(raw_receipts[fold_ordinal], expected_block=block)
            receipt_key = (
                str(receipt["uri"]), str(receipt["generation"]),
                str(receipt["sha256"]), int(receipt["bytes"]),
            )
            if receipt_key in receipt_identities:
                _fail("score-free artifact receipt identity repeats")
            receipt_identities.add(receipt_key)
            all_receipts.append(receipt)
            fold, books = _validate_fold(
                raw_folds[fold_ordinal], season=season, week=week, block=block
            )
            all_folds.append(fold)
            for arm in ARMS:
                books_by_arm[arm].append(books[arm])
        slate_id = f"{season}-w{week:02d}"
        slate_books.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "season": season,
            "week": week,
            "books": books_by_arm,
        })
    if report.get("source_artifacts") != all_receipts:
        _fail("score-free terminal source-artifact ledger differs")

    rebuilt = aggregate_scorefree_folds(all_folds)
    for key, expected in rebuilt.items():
        if report.get(key) != expected:
            _fail(f"score-free terminal aggregate replay differs at {key}")

    proof_rows: list[dict[str, object]] = []
    for slate in slate_books:
        books = _mapping(slate["books"], label="score-free slate books")
        for arm in ARMS:
            arm_books = _sequence(books[arm], label="score-free arm books")
            for fold_ordinal, rosters in enumerate(arm_books):
                proof_rows.append(_with_hash({
                    "schema_version": TERMINAL_BOOK_PROOF_SCHEMA,
                    "source_ordinal": slate["source_ordinal"],
                    "slate_id": slate["slate_id"],
                    "season": slate["season"],
                    "week": slate["week"],
                    "arm_id": arm,
                    "fold_ordinal": fold_ordinal,
                    "heldout_block": REGISTERED_BLOCKS[fold_ordinal],
                    "entry_budget": ENTRY_BUDGET,
                    "selected_rosters_sha256": canonical_sha256_v1(
                        [list(roster) for roster in rosters]
                    ),
                    "scorefree_report_identity": identity,
                    "scorefree_report_raw_sha256": identity["sha256"],
                    "scorefree_report_content_sha256": canonical_sha256_v1(report),
                    "scorefree_terminal_identity": terminal_identity,
                    "scorefree_terminal_root_sha256": terminal_root[
                        "terminal_root_sha256"
                    ],
                }, field="terminal_book_proof_sha256"))
    return {
        "scorefree_terminal_root": terminal_root,
        "scorefree_terminal_identity": terminal_identity,
        "scorefree_terminal_root_sha256": terminal_root["terminal_root_sha256"],
        "scorefree_report": report,
        "scorefree_report_identity": identity,
        "scorefree_report_content_sha256": canonical_sha256_v1(report),
        "slate_books": slate_books,
        "terminal_book_proofs": proof_rows,
        "terminal_book_proofs_sha256": canonical_sha256_v1(proof_rows),
        "terminal_book_proof_complete": True,
        "outcome_capability_used": False,
    }


def _bind_attribution_root_v1(
    value: object, *, identity: Mapping[str, object],
) -> dict[str, object]:
    try:
        root = score_authority.validate_attribution_release_score_authority_v1(value)
    except score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error as exc:
        raise CorpusR6RecourseAwareInitialRealizedBridgeV1Error(str(exc)) from exc
    if (
        root.get("target_uri") != identity["uri"]
        or canonical_sha256_v1(root) != identity["sha256"]
        or len(canonical_json_bytes_v1(root)) != identity["bytes"]
    ):
        _fail("recourse attribution root differs from exact identity")
    return root


def _bind_attribution_shard_v1(
    value: object,
    *,
    identity: Mapping[str, object],
    descriptor: Mapping[str, object],
    source_ordinal: int,
    slate_id: str,
) -> dict[str, object]:
    try:
        shard = score_authority.validate_slate_score_row_authority_v1(value)
    except score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error as exc:
        raise CorpusR6RecourseAwareInitialRealizedBridgeV1Error(str(exc)) from exc
    if (
        descriptor.get("source_ordinal") != source_ordinal
        or descriptor.get("slate_id") != slate_id
        or descriptor.get("slate_attribution_identity") != identity
        or descriptor.get("slate_attribution_sha256")
        != shard.get("slate_attribution_sha256")
        or descriptor.get("lineup_count") != shard.get("lineup_count")
        or shard.get("source_ordinal") != source_ordinal
        or shard.get("slate_id") != slate_id
        or shard.get("panel_freeze_identity") != contract.PANEL_IDENTITY
        or canonical_sha256_v1(shard) != identity["sha256"]
        or len(canonical_json_bytes_v1(shard)) != identity["bytes"]
    ):
        _fail("recourse attribution shard descriptor/slate binding differs")
    return shard


def _selected_rosters_for_slate(
    slate: Mapping[str, object],
) -> set[tuple[str, ...]]:
    books = _mapping(slate.get("books"), label="terminal slate books")
    return {
        tuple(str(player) for player in roster)
        for arm in ARMS
        for book in _sequence(books[arm], label="terminal arm books")
        for roster in _sequence(book, label="terminal selected book")
    }


def _score_row_authority_v1(
    *,
    source_ordinal: int,
    slate_id: str,
    selected_rosters: set[tuple[str, ...]],
    shard: Mapping[str, object],
    shard_identity: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[tuple[str, ...], dict[str, object]]]:
    rows = [
        _mapping(row, label="persisted recourse score row")
        for row in _sequence(shard.get("lineup_rows"), label="persisted lineup rows")
    ]
    aliases: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        roster = tuple(
            str(value)
            for value in _sequence(row.get("roster_player_ids"), label="persisted roster")
        )
        if roster in selected_rosters:
            aliases[roster].append(row)
    missing = sorted(selected_rosters - set(aliases))
    if missing:
        _fail("selected recourse roster is missing from no-rescore authority")
    score_rows: list[dict[str, object]] = []
    by_roster: dict[tuple[str, ...], dict[str, object]] = {}
    for roster in sorted(aliases):
        source_rows = sorted(aliases[roster], key=lambda row: str(row.get("lineup_id")))
        scores = {
            _signed_integer(row.get("realized_score_micro"), label="persisted realized score")
            for row in source_rows
        }
        if len(scores) != 1:
            _fail("one selected recourse roster has conflicting persisted scores")
        lineup_ids = [str(row.get("lineup_id")) for row in source_rows]
        if any(not lineup_id for lineup_id in lineup_ids) or len(set(lineup_ids)) != len(lineup_ids):
            _fail("selected recourse score-row aliases differ")
        source_hashes = [canonical_sha256_v1(row) for row in source_rows]
        score_row = _with_hash({
            "schema_version": ROSTER_SCORE_ROW_SCHEMA,
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "roster_player_ids": list(roster),
            "roster_identity_sha256": canonical_sha256_v1(list(roster)),
            "lineup_ids": lineup_ids,
            "lineup_ids_sha256": canonical_sha256_v1(lineup_ids),
            "persisted_lineup_row_sha256s": source_hashes,
            "persisted_lineup_row_sha256s_sha256": canonical_sha256_v1(source_hashes),
            "realized_score_micro": next(iter(scores)),
            "slate_attribution_identity": dict(shard_identity),
            "slate_attribution_sha256": shard["slate_attribution_sha256"],
            "lineup_rows_sha256": shard["lineup_rows_sha256"],
        }, field="roster_score_row_sha256")
        score_rows.append(score_row)
        by_roster[roster] = score_row
    return score_rows, by_roster


def _threshold_counts(maxima: Sequence[int]) -> dict[str, int]:
    return {
        str(threshold): sum(
            value >= threshold * MICRO_DK_PER_POINT for value in maxima
        )
        for threshold in THRESHOLDS_DK
    }


def _score_arm_v1(
    *,
    arm: str,
    terminal: Mapping[str, object],
    scored_by_source: Mapping[int, Mapping[tuple[str, ...], Mapping[str, object]]],
    source_ordinals: Sequence[int],
    proof_by_coordinate: Mapping[tuple[int, str, int], Mapping[str, object]],
) -> dict[str, object]:
    slate_by_source = {
        int(row["source_ordinal"]): row
        for row in (
            _mapping(raw, label="terminal slate")
            for raw in _sequence(terminal.get("slate_books"), label="terminal slates")
        )
    }
    fold_paths: list[dict[str, object]] = []
    all_maxima: list[int] = []
    for fold_ordinal, block in enumerate(REGISTERED_BLOCKS):
        book_weeks: list[dict[str, object]] = []
        maxima: list[int] = []
        for source in source_ordinals:
            slate = slate_by_source[source]
            books = _mapping(slate["books"], label="terminal slate books")
            rosters = [
                tuple(str(player) for player in roster)
                for roster in _sequence(
                    _sequence(books[arm], label="terminal arm books")[fold_ordinal],
                    label="terminal selected rosters",
                )
            ]
            authorities = scored_by_source[source]
            if not set(rosters) <= set(authorities):
                _fail("recourse book lacks a cached no-rescore score")
            scores = [int(authorities[roster]["realized_score_micro"]) for roster in rosters]
            maximum = max(scores)
            maximum_rosters = sorted(
                canonical_sha256_v1(list(roster))
                for roster, score in zip(rosters, scores, strict=True)
                if score == maximum
            )
            score_row_hashes = [
                str(authorities[roster]["roster_score_row_sha256"]) for roster in rosters
            ]
            proof = proof_by_coordinate[(source, arm, fold_ordinal)]
            row = _with_hash({
                "schema_version": BOOK_WEEK_SCHEMA,
                "source_ordinal": source,
                "slate_id": slate["slate_id"],
                "season": slate["season"],
                "week": slate["week"],
                "arm_id": arm,
                "fold_ordinal": fold_ordinal,
                "heldout_block": block,
                "entry_budget": ENTRY_BUDGET,
                "terminal_book_proof_sha256": proof["terminal_book_proof_sha256"],
                "selected_rosters_sha256": proof["selected_rosters_sha256"],
                "selected_roster_score_row_sha256s_sha256": canonical_sha256_v1(
                    score_row_hashes
                ),
                "weekly_maximum_realized_score_micro": maximum,
                "weekly_maximum_roster_identity_sha256s": maximum_rosters,
                "weekly_maximum_roster_identity_sha256s_sha256": canonical_sha256_v1(
                    maximum_rosters
                ),
                "at_or_above_threshold_dk": {
                    str(threshold): maximum >= threshold * MICRO_DK_PER_POINT
                    for threshold in THRESHOLDS_DK
                },
            }, field="book_week_sha256")
            book_weeks.append(row)
            maxima.append(maximum)
            all_maxima.append(maximum)
        fold_paths.append(_with_hash({
            "schema_version": FOLD_PATH_SCHEMA,
            "arm_id": arm,
            "fold_ordinal": fold_ordinal,
            "heldout_block": block,
            "heldout_rotation_week_count": len(book_weeks),
            "heldout_rotation_evidence": True,
            "production_final_fit": False,
            "all_block_54_week_benchmark_comparable": False,
            "book_weeks": book_weeks,
            "book_weeks_sha256": canonical_sha256_v1(book_weeks),
            "weekly_maximum_sum_micro": sum(maxima),
            "heldout_rotation_mean_weekly_maximum_micro": _fraction(
                sum(maxima), len(maxima)
            ),
            "at_or_above_threshold_week_counts": _threshold_counts(maxima),
        }, field="fold_path_sha256"))
    return _with_hash({
        "schema_version": ARM_RESULT_SCHEMA,
        "arm_id": arm,
        "entry_budget": ENTRY_BUDGET,
        "fold_path_count": FOLD_COUNT,
        "fold_paths": fold_paths,
        "fold_paths_sha256": canonical_sha256_v1(fold_paths),
        "rotated_book_week_count": len(all_maxima),
        "rotated_fit_weekly_maximum_sum_micro": sum(all_maxima),
        "rotated_fit_mean_weekly_maximum_micro": _fraction(
            sum(all_maxima), len(all_maxima)
        ),
        "at_or_above_threshold_book_week_counts": _threshold_counts(all_maxima),
        "mean_at_or_above_threshold_weeks_per_fold": {
            threshold: _fraction(count, FOLD_COUNT)
            for threshold, count in _threshold_counts(all_maxima).items()
        },
        "inclusive_threshold_law": "weekly-maximum-greater-than-or-equal-to",
        "reachable_union_scored": False,
        "late_swap_policy_applied": False,
        "lineup_rescore_performed": False,
        "evidence_class": "five-fold-heldout-rotation-diagnostic",
        "all_block_final_fit_performed": False,
        "all_block_54_week_benchmark_comparable": False,
        "ranking_beside_all_block_54_week_benchmark_forbidden": True,
    }, field="arm_result_sha256")


def _rotated_fit_paired_diagnostic_v1(
    arm_results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    rows_by_arm: dict[str, dict[tuple[int, int], Mapping[str, object]]] = {}
    for arm in ARMS:
        rows: dict[tuple[int, int], Mapping[str, object]] = {}
        for path in _sequence(arm_results[arm].get("fold_paths"), label="arm fold paths"):
            fold_path = _mapping(path, label="arm fold path")
            fold = int(fold_path["fold_ordinal"])
            for raw in _sequence(fold_path.get("book_weeks"), label="arm book weeks"):
                row = _mapping(raw, label="arm book week")
                rows[(int(row["source_ordinal"]), fold)] = row
        rows_by_arm[arm] = rows
    if set(rows_by_arm["control"]) != set(rows_by_arm["treatment"]):
        _fail("recourse rotated-fit paired coordinate lattice differs")
    deltas: list[int] = []
    threshold_deltas = {str(threshold): 0 for threshold in THRESHOLDS_DK}
    by_fold: list[dict[str, object]] = []
    for fold in range(FOLD_COUNT):
        fold_deltas: list[int] = []
        fold_threshold_deltas = {str(threshold): 0 for threshold in THRESHOLDS_DK}
        for coordinate in sorted(rows_by_arm["control"]):
            if coordinate[1] != fold:
                continue
            control = rows_by_arm["control"][coordinate]
            treatment = rows_by_arm["treatment"][coordinate]
            delta = int(treatment["weekly_maximum_realized_score_micro"]) - int(
                control["weekly_maximum_realized_score_micro"]
            )
            deltas.append(delta)
            fold_deltas.append(delta)
            for threshold in THRESHOLDS_DK:
                key = str(threshold)
                difference = int(bool(treatment["at_or_above_threshold_dk"][key])) - int(
                    bool(control["at_or_above_threshold_dk"][key])
                )
                threshold_deltas[key] += difference
                fold_threshold_deltas[key] += difference
        by_fold.append({
            "fold_ordinal": fold,
            "heldout_block": REGISTERED_BLOCKS[fold],
            "heldout_rotation_week_count": len(fold_deltas),
            "heldout_rotation_evidence": True,
            "production_final_fit": False,
            "all_block_54_week_benchmark_comparable": False,
            "treatment_minus_control_sum_micro": sum(fold_deltas),
            "treatment_minus_control_mean_micro": _fraction(
                sum(fold_deltas), len(fold_deltas)
            ),
            "treatment_wins": sum(value > 0 for value in fold_deltas),
            "ties": sum(value == 0 for value in fold_deltas),
            "treatment_losses": sum(value < 0 for value in fold_deltas),
            "at_or_above_threshold_week_count_deltas": fold_threshold_deltas,
        })
    return _with_hash({
        "schema_version": ROTATED_FIT_PAIRED_DIAGNOSTIC_SCHEMA,
        "control_arm_result_sha256": arm_results["control"]["arm_result_sha256"],
        "treatment_arm_result_sha256": arm_results["treatment"]["arm_result_sha256"],
        "rotated_book_week_count": len(deltas),
        "heldout_rotation_fold_row_count": len(by_fold),
        "rotated_fit_treatment_minus_control_sum_micro": sum(deltas),
        "rotated_fit_treatment_minus_control_mean_micro": _fraction(
            sum(deltas), len(deltas)
        ),
        "treatment_wins": sum(value > 0 for value in deltas),
        "ties": sum(value == 0 for value in deltas),
        "treatment_losses": sum(value < 0 for value in deltas),
        "at_or_above_threshold_book_week_count_deltas": threshold_deltas,
        "heldout_rotation_fold_rows": by_fold,
        "heldout_rotation_fold_rows_sha256": canonical_sha256_v1(by_fold),
        "paired_law": "same-slate-same-heldout-fold-control-versus-treatment",
        "evidence_class": "five-fold-heldout-rotation-paired-diagnostic",
        "diagnostic_scope": (
            "train-four-blocks-score-one-heldout-block-rotated-five-times"
        ),
        "all_block_final_fit_performed": False,
        "all_block_54_week_benchmark_comparable": False,
        "ranking_beside_all_block_54_week_benchmark_forbidden": True,
        "winner_selection_performed": False,
        "historical_retune_licensed": False,
    }, field="rotated_fit_paired_diagnostic_sha256")


def build_recourse_aware_initial_realized_bridge_v1(
    *,
    scorefree_terminal_identity: object,
    outcome_authority_identity: object,
    mode: str,
    read_scorefree_exact: ReadExact,
    read_outcome_exact: ReadExact,
) -> dict[str, object]:
    """Grade frozen initial books from persisted no-rescore score rows."""
    if mode not in {MODE_ONE_SLATE_SMOKE, MODE_FULL_PANEL}:
        _fail("recourse realized bridge mode differs")
    supplied_outcome_identity = _identity(
        outcome_authority_identity, label="recourse outcome authority"
    )
    if supplied_outcome_identity != OUTCOME_AUTHORITY_IDENTITY:
        _fail("recourse outcome authority is not the frozen comparison release")
    if not callable(read_outcome_exact):
        _fail("recourse outcome exact reader must be callable")
    terminal = reopen_terminal_scorefree_books_v1(
        scorefree_terminal_identity=scorefree_terminal_identity,
        read_scorefree_exact=read_scorefree_exact,
    )
    if terminal.get("terminal_book_proof_complete") is not True:
        _fail("recourse terminal book proof is incomplete before outcome boundary")

    # First realized-outcome capability use.  Everything above is score-free.
    outcome_body, outcome_identity = _open_json_v1(
        supplied_outcome_identity,
        read_exact=read_outcome_exact,
        maximum_bytes=MAXIMUM_ATTRIBUTION_ROOT_BYTES,
        label="recourse no-rescore attribution release",
    )
    outcome_open_count = 1
    outcome_root = _bind_attribution_root_v1(outcome_body, identity=outcome_identity)
    if (
        outcome_root.get("panel_freeze_identity") != contract.PANEL_IDENTITY
        or outcome_root.get("panel_freeze_sha256") != contract.PANEL_SELF_SHA256
    ):
        _fail("recourse outcome authority panel differs")
    descriptors = [
        _mapping(row, label=f"recourse attribution descriptor[{index}]")
        for index, row in enumerate(
            _sequence(outcome_root.get("slate_attribution_objects"),
                      label="recourse attribution descriptors")
        )
    ]
    slates = [
        _mapping(row, label="recourse terminal slate")
        for row in _sequence(terminal.get("slate_books"), label="recourse terminal slates")
    ]
    expected_slate_ids = [str(row["slate_id"]) for row in slates]
    if (
        len(descriptors) != PANEL_SLATE_COUNT
        or [row.get("source_ordinal") for row in descriptors]
        != list(range(PANEL_SLATE_COUNT))
        or [row.get("slate_id") for row in descriptors] != expected_slate_ids
    ):
        _fail("recourse outcome authority slate lattice differs")
    source_ordinals = [0] if mode == MODE_ONE_SLATE_SMOKE else list(range(PANEL_SLATE_COUNT))

    score_row_ledgers: list[dict[str, object]] = []
    scored_by_source: dict[int, dict[tuple[str, ...], dict[str, object]]] = {}
    for source in source_ordinals:
        descriptor = descriptors[source]
        shard_body, shard_identity = _open_json_v1(
            descriptor["slate_attribution_identity"],
            read_exact=read_outcome_exact,
            maximum_bytes=MAXIMUM_ATTRIBUTION_SHARD_BYTES,
            label=f"recourse no-rescore attribution shard[{source}]",
        )
        outcome_open_count += 1
        shard = _bind_attribution_shard_v1(
            shard_body,
            identity=shard_identity,
            descriptor=descriptor,
            source_ordinal=source,
            slate_id=expected_slate_ids[source],
        )
        selected_rosters = _selected_rosters_for_slate(slates[source])
        score_rows, by_roster = _score_row_authority_v1(
            source_ordinal=source,
            slate_id=expected_slate_ids[source],
            selected_rosters=selected_rosters,
            shard=shard,
            shard_identity=shard_identity,
        )
        score_row_ledgers.append({
            "source_ordinal": source,
            "slate_id": expected_slate_ids[source],
            "selected_roster_count": len(selected_rosters),
            "roster_score_lookup_count": len(score_rows),
            "roster_score_rows": score_rows,
            "roster_score_rows_sha256": canonical_sha256_v1(score_rows),
            "slate_attribution_identity": shard_identity,
            "slate_attribution_sha256": shard["slate_attribution_sha256"],
            "lineup_rows_sha256": shard["lineup_rows_sha256"],
        })
        scored_by_source[source] = by_roster

    proofs = [
        _mapping(row, label="recourse terminal book proof")
        for row in _sequence(terminal.get("terminal_book_proofs"),
                             label="recourse terminal book proofs")
    ]
    proof_by_coordinate = {
        (int(row["source_ordinal"]), str(row["arm_id"]), int(row["fold_ordinal"])): row
        for row in proofs
    }
    if len(proof_by_coordinate) != PANEL_SLATE_COUNT * len(ARMS) * FOLD_COUNT:
        _fail("recourse terminal book-proof coordinate lattice differs")
    arm_results = {
        arm: _score_arm_v1(
            arm=arm,
            terminal=terminal,
            scored_by_source=scored_by_source,
            source_ordinals=source_ordinals,
            proof_by_coordinate=proof_by_coordinate,
        )
        for arm in ARMS
    }
    expected_rotation_weeks = len(source_ordinals)
    for arm in ARMS:
        result = arm_results[arm]
        paths = _sequence(result.get("fold_paths"), label="rotated-fit fold paths")
        if (
            len(paths) != FOLD_COUNT
            or result.get("rotated_book_week_count")
            != expected_rotation_weeks * FOLD_COUNT
            or any(
                _mapping(path, label="rotated-fit fold path").get(
                    "heldout_rotation_week_count"
                ) != expected_rotation_weeks
                for path in paths
            )
        ):
            _fail("recourse rotated-fit smoke/full topology differs")
    diagnostic = _rotated_fit_paired_diagnostic_v1(arm_results)
    report = {
        "schema_version": BRIDGE_SCHEMA,
        "mode": mode,
        "realized_bridge_protocol_sha256": REALIZED_PROTOCOL_SHA256,
        "scorefree_terminal_identity": terminal["scorefree_terminal_identity"],
        "scorefree_terminal_root_sha256": terminal[
            "scorefree_terminal_root_sha256"
        ],
        "scorefree_report_identity": terminal["scorefree_report_identity"],
        "scorefree_report_content_sha256": terminal[
            "scorefree_report_content_sha256"
        ],
        "scorefree_gate_passed_before_outcome_open": True,
        "terminal_book_proof_complete_before_outcome_open": True,
        "terminal_book_proofs_sha256": terminal["terminal_book_proofs_sha256"],
        "outcome_authority_identity": outcome_identity,
        "outcome_authority_sha256": outcome_root["attribution_release_sha256"],
        "panel_freeze_identity": contract.PANEL_IDENTITY,
        "panel_freeze_sha256": contract.PANEL_SELF_SHA256,
        "scored_source_ordinals": source_ordinals,
        "scored_slate_count": len(source_ordinals),
        "outcome_exact_open_count": outcome_open_count,
        "score_row_ledgers": score_row_ledgers,
        "score_row_ledgers_sha256": canonical_sha256_v1(score_row_ledgers),
        "roster_score_lookup_count": sum(
            int(row["roster_score_lookup_count"]) for row in score_row_ledgers
        ),
        "score_lookup_deduplication_law": (
            "one-persisted-realized-score-per-distinct-roster-per-slate-"
            "reused-across-heldout-folds-and-arms"
        ),
        "rotated_fit_arm_diagnostics": [arm_results[arm] for arm in ARMS],
        "rotated_fit_arm_diagnostics_sha256": canonical_sha256_v1(
            [arm_results[arm] for arm in ARMS]
        ),
        "rotated_fit_paired_diagnostic": diagnostic,
        "heldout_rotation_fold_row_count": FOLD_COUNT,
        "thresholds_dk": list(THRESHOLDS_DK),
        "inclusive_threshold_law": "weekly-maximum-greater-than-or-equal-to",
        "score_target": "frozen-initial-book-only",
        "reachable_union_scored": False,
        "late_swap_policy_applied": False,
        "uses_realized_outcomes": True,
        "persisted_realized_attribution_read": True,
        "raw_outcome_source_queried": False,
        "bigquery_client_constructed": False,
        "lineup_rescore_performed": False,
        "score_row_authority": (
            "persisted-full-union-attribution-lineup-realized-score-micro"
        ),
        "historical_retune_licensed": False,
        "evidence_class": "five-fold-heldout-rotation-paired-diagnostic",
        "diagnostic_scope": (
            "train-four-blocks-score-one-heldout-block-rotated-five-times"
        ),
        "all_block_final_fit_performed": False,
        "all_block_54_week_benchmark_comparable": False,
        "fold_rows_are_production_final_fit": False,
        "scorecard_eligible": False,
        "ranking_beside_all_block_54_week_benchmark_forbidden": True,
        "promotion_authority": False,
        "decision_authority": False,
        "graph_mutation_performed": False,
    }
    report["realized_bridge_sha256"] = canonical_sha256_v1(report)
    if len(canonical_json_bytes_v1(report)) > MAXIMUM_REPORT_BYTES:
        _fail("recourse realized bridge report exceeds its byte ceiling")
    return report


def build_publication_envelope_v1(
    *, report: object, report_identity: object,
) -> dict[str, object]:
    retained = _mapping(report, label="recourse realized bridge report")
    if (
        retained.get("schema_version") != BRIDGE_SCHEMA
        or retained.get("mode") not in {MODE_ONE_SLATE_SMOKE, MODE_FULL_PANEL}
        or retained.get("scorecard_eligible") is not False
        or retained.get("all_block_54_week_benchmark_comparable") is not False
        or retained.get(
            "ranking_beside_all_block_54_week_benchmark_forbidden"
        ) is not True
        or retained.get("realized_bridge_sha256")
        != canonical_sha256_v1({
            key: value for key, value in retained.items()
            if key != "realized_bridge_sha256"
        })
    ):
        _fail("recourse realized bridge report self hash differs")
    identity = _identity(report_identity, label="recourse realized bridge identity")
    raw = canonical_json_bytes_v1(retained)
    if (
        identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
        or not str(identity["uri"]).startswith(OUTPUT_NAMESPACE)
        or not str(identity["uri"]).endswith(
            f"/{OUTPUT_FILENAME_BY_MODE[str(retained['mode'])]}"
        )
    ):
        _fail("recourse realized bridge publication identity differs")
    diagnostic = _mapping(
        retained.get("rotated_fit_paired_diagnostic"),
        label="recourse rotated-fit paired diagnostic",
    )
    return _with_hash({
        "schema_version": PUBLICATION_ENVELOPE_SCHEMA,
        "mode": retained["mode"],
        "realized_bridge_identity": identity,
        "realized_bridge_sha256": retained["realized_bridge_sha256"],
        "scorefree_terminal_identity": retained["scorefree_terminal_identity"],
        "scorefree_report_identity": retained["scorefree_report_identity"],
        "outcome_authority_identity": retained["outcome_authority_identity"],
        "scored_slate_count": retained["scored_slate_count"],
        "control_arm_result_sha256": diagnostic["control_arm_result_sha256"],
        "treatment_arm_result_sha256": diagnostic["treatment_arm_result_sha256"],
        "rotated_fit_paired_diagnostic_sha256": diagnostic[
            "rotated_fit_paired_diagnostic_sha256"
        ],
        "uses_realized_outcomes": True,
        "persisted_realized_attribution_read": True,
        "raw_outcome_source_queried": False,
        "scorecard_eligible": False,
        "all_block_54_week_benchmark_comparable": False,
        "ranking_beside_all_block_54_week_benchmark_forbidden": True,
        "publication_mode": "create-once-exact-reopen",
        "evidence_class": "five-fold-heldout-rotation-paired-diagnostic",
        "lineup_rescore_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, field="publication_envelope_sha256")


def cloud_entrypoint_registration_v1() -> dict[str, object]:
    return _with_hash({
        "schema_version": CLOUD_ENTRYPOINT_REGISTRATION_SCHEMA,
        "process_role": "recourse-aware-initial-realized-bridge-publisher",
        "entrypoint_relative_path": ENTRYPOINT_RELATIVE_PATH,
        "entrypoint_image_path": ENTRYPOINT_IMAGE_PATH,
        "command": list(ENTRYPOINT_COMMAND),
        "realized_bridge_protocol_relative_path": REALIZED_PROTOCOL_RELATIVE_PATH,
        "realized_bridge_protocol_sha256": REALIZED_PROTOCOL_SHA256,
        "publication_mode": "create-once-exact-reopen",
        "maximum_report_bytes": MAXIMUM_REPORT_BYTES,
        "uses_realized_outcomes": True,
        "persisted_realized_attribution_read": True,
        "raw_outcome_source_queried": False,
        "lineup_rescore_performed": False,
        "reachable_union_scored": False,
        "late_swap_policy_applied": False,
        "evidence_class": "five-fold-heldout-rotation-paired-diagnostic",
        "scorecard_eligible": False,
        "all_block_54_week_benchmark_comparable": False,
        "ranking_beside_all_block_54_week_benchmark_forbidden": True,
        "graph_mutation_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, field="cloud_entrypoint_registration_sha256")


__all__ = [
    "ARMS",
    "BRIDGE_SCHEMA",
    "CLOUD_ENTRYPOINT_REGISTRATION_SCHEMA",
    "CorpusR6RecourseAwareInitialRealizedBridgeV1Error",
    "ENTRYPOINT_COMMAND",
    "ENTRYPOINT_IMAGE_PATH",
    "ENTRYPOINT_RELATIVE_PATH",
    "FOLD_COUNT",
    "MAXIMUM_REPORT_BYTES",
    "MODE_FULL_PANEL",
    "MODE_ONE_SLATE_SMOKE",
    "OUTCOME_AUTHORITY_IDENTITY",
    "FULL_OUTPUT_FILENAME",
    "OUTPUT_FILENAME_BY_MODE",
    "OUTPUT_NAMESPACE",
    "PUBLICATION_ENVELOPE_SCHEMA",
    "REALIZED_PROTOCOL_RELATIVE_PATH",
    "REALIZED_PROTOCOL_SHA256",
    "SCOREFREE_REPORT_URI",
    "SCOREFREE_TERMINAL_URI",
    "SMOKE_OUTPUT_FILENAME",
    "THRESHOLDS_DK",
    "build_publication_envelope_v1",
    "build_recourse_aware_initial_realized_bridge_v1",
    "canonical_json_bytes_v1",
    "canonical_line_json_bytes_v1",
    "canonical_sha256_v1",
    "cloud_entrypoint_registration_v1",
    "reopen_terminal_scorefree_books_v1",
]
