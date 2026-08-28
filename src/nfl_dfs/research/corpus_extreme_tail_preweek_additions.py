"""Outcome-blind pre-Week-1 selector additions and a 230 coverage oracle.

The two selectors in this module consume the same exact fit-scope binding as
``corpus_extreme_tail_preweek_selectors``.  They materialize one deterministic
rank 80 and expose only its exact 4/14/80 prefixes.  The maximum-coverage MIP is
strictly a diagnostic: it reports a witnessed lower bound and a safe upper
bound, and it never grants outcome, publication, or production authority.

Score scans are row-chunked and event matrices are bit-packed.  The MIP sparse
incidence is materialized only inside a frozen envelope; outside that envelope
the diagnostic returns the greedy witness and a conservative analytical upper
bound without constructing an unbounded Python model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import math
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Final

import numpy as np
import pulp

from nfl_dfs.research import corpus_extreme_tail_preweek_selectors as preweek
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


RECEIPT_SCHEMA: Final = "extreme-tail-preweek-additions/v1"
INPUT_BINDING_SCHEMA: Final = "extreme-tail-preweek-additions-input/v1"
IMPLEMENTATION_SCHEMA: Final = "extreme-tail-preweek-additions-implementation/v1"
STRATEGY_SCHEMA: Final = "extreme-tail-preweek-addition-strategy/v1"
SELECTOR_SCHEMA: Final = "extreme-tail-preweek-addition-selector/v1"
BOOK_SCHEMA: Final = "extreme-tail-preweek-addition-book/v1"
ORACLE_SCHEMA: Final = "maximum-coverage-ge-230-oracle-diagnostic/v1"
ORACLE_ROW_SCHEMA: Final = "maximum-coverage-ge-230-oracle-row/v1"
IMPLEMENTATION_ID: Final = "packed-convex-block-support-cbc-oracle-v1"
RECEIPT_LAW_ID: Final = "frozen-preweek-historical-additions/v1"

ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
PRODUCTION_WORLDS_PER_BLOCK: Final = 10_000
CANDIDATE_CHUNK_ROWS: Final = 64
PACKED_BITORDER: Final = "little"
CONVEX_PIVOT: Final = 200.0
CONVEX_EXPONENT: Final = 2
TAIL_RUNGS: Final = (
    (210.0, ">=", 1),
    (220.0, ">=", 2),
    (230.0, ">=", 4),
    (240.0, ">=", 8),
    (250.0, ">=", 16),
)
ORACLE_THRESHOLD: Final = 230.0
ORACLE_OPERATOR: Final = ">="
ORACLE_NODE_LIMITS: Final = {4: 100_000, 14: 250_000, 80: 500_000}
ORACLE_REQUIRED_MODES: Final = {4: "exact", 14: "exact", 80: "bounded"}
ORACLE_MAX_CANDIDATES: Final = 20_000
ORACLE_MAX_OPPORTUNITY_WORLDS: Final = 50_000
ORACLE_MAX_EVENT_EDGES: Final = 2_000_000
PULP_VERSION: Final = "3.3.2"
CBC_VERSION: Final = "2.10.3"
CBC_BUILD_DATE: Final = "Dec 15 2019"
CBC_EXECUTABLE_SHA256: Final = (
    "2e17077752aa52b06385ad248c9e90bb4f1ce34038c34c94e1012ca6adea5cc7"
)
CBC_EXECUTABLE_BYTES: Final = 7_178_823
CBC_THREADS: Final = 1
CBC_GAP_REL: Final = 0.0
CBC_GAP_ABS: Final = 0.0
CBC_PRESOLVE: Final = True
CBC_CUTS: Final = True
CBC_STRONG: Final = 0
CBC_WARM_START: Final = True
CBC_TIME_MODE: Final = "cpu"
CBC_TIME_LIMIT_SECONDS: Final = None
CBC_SEED_OPTIONS: Final = ("randomSeed 1", "randomCbcSeed 1")
CBC_WORK_LIMIT_LAW: Final = "deterministic-cbc-maxNodes-by-entry-budget"
CBC_PROOF_SCHEMA: Final = "deterministic-cbc-maximum-coverage-proof/v1"

_PREWEEK_IMPLEMENTATION_ID: Final = "packed-chunked-preweek-selectors-v1"
_PREWEEK_IMPLEMENTATION_SHA256: Final = (
    "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f"
)
_PREWEEK_STRATEGY_HASHES: Final = {
    "complete-union-inclusive-r194-rank-v1": (
        "94507da865b236f9780320eed9039882edeab73682910279f1c4c2b900c7ec95"
    ),
    "individual-training-maximum-rank-v1": (
        "7d0c3458accdd91e96aa8bb7513fd333e0804ae846216e823242d839cbc177c2"
    ),
    "training-hit-ge-230-admission-v1": (
        "4f5ffe15d0df57f245426113f48c63b0e1abee68dd4a903b94ff6e9fe0728fda"
    ),
}
_NEIGHBOR_EXPECTED_MAX_SHA256: Final = (
    "ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780"
)
_NEIGHBOR_BLOCK_SUPPORT_SHA256: Final = (
    "1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b"
)
_EXPECTED_IMPLEMENTATION_SHA256: Final = (
    "1c94e9635d6038f629c40ce81cc2b3b3ed4fcad600e4832a0f231c5c9c19403d"
)
_EXPECTED_STRATEGY_HASHES: Final = {
    "convex-excess-expected-max-ge-200-v1": (
        "189dc6986c7d70b8315f9e41cb1fe5c6fce35c54f2756729254a0e1614dd1082"
    ),
    "block-supported-bounded-tail-ge-210-250-v1": (
        "a2070561cfb0a2c2c049b27d5e5ff71682a87d3568254b09ebf987a58d775954"
    ),
    "maximum-coverage-ge-230-oracle-diagnostic-v1": (
        "b40a7ed84af58f62ba1c4d814bcaf6f360ffb09e286963d348790f9f007b6b6e"
    ),
}

_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
    "publication_authority",
    "panel_membership_authority",
    "source_replay_authority",
    "realized_grade_open_authority",
    "outcome_authority",
)
_POPCOUNT: Final = np.asarray(
    [value.bit_count() for value in range(256)], dtype=np.uint8
)
_CBC_UPPER_RE: Final = re.compile(
    r"^Upper bound:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*$",
    re.MULTILINE,
)
_CBC_NODES_RE: Final = re.compile(
    r"^Enumerated nodes:\s*(\d+)\s*$", re.MULTILINE
)


class CorpusExtremeTailPreweekAdditionsError(ValueError):
    """A pre-Week-1 addition violates its exact frozen contract."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailPreweekAdditionsError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailPreweekAdditionsError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailPreweekAdditionsError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = _sha(result, label=field)
    return result


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _candidate_chunks(row_count: int):
    for start in range(0, row_count, CANDIDATE_CHUNK_ROWS):
        yield start, min(start + CANDIDATE_CHUNK_ROWS, row_count)


def _score_rows(
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    start: int,
    stop: int,
    *,
    column_start: int | None = None,
    column_stop: int | None = None,
) -> np.ndarray:
    rows = canonical_source_rows[start:stop]
    if column_start is None:
        values = scores[rows]
    else:
        values = scores[rows, column_start:column_stop]
    return np.ascontiguousarray(values, dtype=np.float64)


def _score_matrix_hash(
    scores: np.ndarray, canonical_source_rows: np.ndarray
) -> str:
    digest = sha256()
    digest.update(
        canonical_json_bytes(
            {
                "dtype": "float64-le",
                "shape": [len(canonical_source_rows), scores.shape[1]],
            }
        )
    )
    digest.update(b"\0")
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        chunk = np.ascontiguousarray(
            scores[canonical_source_rows[start:stop]], dtype="<f8"
        )
        digest.update(memoryview(chunk).cast("B"))
    return digest.hexdigest()


def _row_means(
    scores: np.ndarray, canonical_source_rows: np.ndarray
) -> np.ndarray:
    result = np.empty(len(canonical_source_rows), dtype=np.float64)
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        result[start:stop] = _score_rows(
            scores, canonical_source_rows, start, stop
        ).mean(axis=1, dtype=np.float64)
    return result


def _pack_event_mask(
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    *,
    threshold: float,
    operator: str,
    column_start: int,
    column_stop: int,
) -> np.ndarray:
    width = column_stop - column_start
    if width < 1:
        _fail("event mask requires a positive column width")
    packed = np.empty(
        (len(canonical_source_rows), (width + 7) // 8), dtype=np.uint8
    )
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        chunk = _score_rows(
            scores,
            canonical_source_rows,
            start,
            stop,
            column_start=column_start,
            column_stop=column_stop,
        )
        if operator == ">=":
            events = chunk >= threshold
        elif operator == ">":
            events = chunk > threshold
        else:
            _fail(f"unsupported event operator {operator!r}")
        packed[start:stop] = np.packbits(
            events, axis=1, bitorder=PACKED_BITORDER
        )
    return packed


def _row_counts_by_block(
    packed_by_block: Sequence[np.ndarray],
) -> np.ndarray:
    if not packed_by_block:
        _fail("packed event law requires at least one block")
    row_count = packed_by_block[0].shape[0]
    result = np.zeros(row_count, dtype=np.int64)
    for packed in packed_by_block:
        if packed.dtype != np.uint8 or packed.shape[0] != row_count:
            _fail("packed event blocks differ")
        for start, stop in _candidate_chunks(row_count):
            result[start:stop] += _POPCOUNT[packed[start:stop]].sum(
                axis=1, dtype=np.int64
            )
    return result


def _packed_incidence_hash(
    *,
    packed_by_block: Sequence[np.ndarray],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    threshold: float,
    operator: str,
) -> str:
    digest = sha256()
    digest.update(
        canonical_json_bytes(
            {
                "candidate_count": int(packed_by_block[0].shape[0]),
                "training_blocks": list(training_blocks),
                "worlds_per_block": worlds_per_block,
                "threshold": threshold,
                "operator": operator,
                "encoding": "numpy-packbits-uint8",
                "bitorder": PACKED_BITORDER,
            }
        )
    )
    digest.update(b"\0")
    for block, packed in zip(training_blocks, packed_by_block, strict=True):
        digest.update(block.encode("utf-8"))
        digest.update(b"\0")
        digest.update(memoryview(np.ascontiguousarray(packed)).cast("B"))
        digest.update(b"\0")
    return digest.hexdigest()


def _guard_upstream_contracts() -> dict[str, object]:
    if (
        tuple(rw.WORLD_BLOCKS) != WORLD_BLOCKS
        or retrieval.WORLDS_PER_BLOCK != PRODUCTION_WORLDS_PER_BLOCK
        or tuple(preweek.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or preweek.RANKING_DEPTH != RANKING_DEPTH
        or preweek.FIT_SCOPE_BINDING_SCHEMA
        != "extreme-tail-preweek-fit-scope-binding/v1"
    ):
        _fail("imported world, budget, or fit-scope constants drifted")
    implementation = _mapping(
        preweek.frozen_preweek_selector_implementation_v1(),
        label="upstream preweek implementation",
    )
    retained = implementation.get("implementation_sha256")
    remainder = {
        key: value
        for key, value in implementation.items()
        if key != "implementation_sha256"
    }
    if (
        implementation.get("implementation_id") != _PREWEEK_IMPLEMENTATION_ID
        or retained != _PREWEEK_IMPLEMENTATION_SHA256
        or _sha(remainder, label="upstream preweek implementation") != retained
    ):
        _fail("upstream preweek implementation identity drifted")
    observed_preweek: dict[str, str] = {}
    for raw in preweek.frozen_preweek_selector_registry_v1():
        strategy = _mapping(raw, label="upstream preweek strategy")
        selector_id = strategy.get("selector_id")
        retained_hash = strategy.get("strategy_sha256")
        remainder = {
            key: value
            for key, value in strategy.items()
            if key != "strategy_sha256"
        }
        if (
            type(selector_id) is not str
            or type(retained_hash) is not str
            or selector_id in observed_preweek
            or _sha(remainder, label="upstream preweek strategy")
            != retained_hash
        ):
            _fail("upstream preweek strategy self-identity drifted")
        observed_preweek[selector_id] = retained_hash
    if observed_preweek != _PREWEEK_STRATEGY_HASHES:
        _fail("upstream preweek strategy registry drifted")
    observed_neighbors: dict[str, str] = {}
    for raw in retrieval.frozen_retrieval_strategies_v2(RANKING_DEPTH):
        strategy = _mapping(raw, label="neighbor retrieval strategy")
        strategy_id = strategy.get("strategy_id")
        if strategy_id in {"expected-max-v1", "block-supported-tail-ladder-v1"}:
            retained_hash = strategy.get("strategy_sha256")
            remainder = {
                key: value
                for key, value in strategy.items()
                if key != "strategy_sha256"
            }
            if (
                type(retained_hash) is not str
                or _sha(remainder, label="neighbor retrieval strategy")
                != retained_hash
            ):
                _fail("neighbor retrieval strategy self-identity drifted")
            observed_neighbors[str(strategy_id)] = retained_hash
    if observed_neighbors != {
        "expected-max-v1": _NEIGHBOR_EXPECTED_MAX_SHA256,
        "block-supported-tail-ladder-v1": _NEIGHBOR_BLOCK_SUPPORT_SHA256,
    }:
        _fail("neighbor expected-max or block-support strategy drifted")
    if tuple(preweek._FALSE_AUTHORITY_FIELDS) + ("outcome_authority",) != (  # noqa: SLF001
        _FALSE_AUTHORITY_FIELDS
    ):
        _fail("false-authority field registry drifted")
    return {
        "preweek_implementation_id": _PREWEEK_IMPLEMENTATION_ID,
        "preweek_implementation_sha256": _PREWEEK_IMPLEMENTATION_SHA256,
        "preweek_strategy_hashes": dict(observed_preweek),
        "neighbor_strategy_hashes": dict(observed_neighbors),
    }


def frozen_preweek_additions_implementation_v1() -> dict[str, object]:
    """Return the exact bounded-memory selector/oracle implementation law."""
    body = {
        "schema_version": IMPLEMENTATION_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "candidate_chunk_rows": CANDIDATE_CHUNK_ROWS,
        "canonical_candidate_order": "ascending-lineup-id",
        "canonical_score_hash": "float64-le-row-chunked-in-canonical-order",
        "event_encoding": "numpy-packbits-uint8-little",
        "convex_transform": "max(0,s-200)^2-float64-no-sweep",
        "convex_state": "one-current-best-score-vector",
        "block_support_law": "candidate-rung-distinct-fit-block-event-count",
        "rank_law": "one-exact-rank-80-with-prefixes-4-14-80",
        "zero_gain_law": "continue-by-frozen-tie-order-to-rank-80",
        "oracle_backend": {
            "pulp_version": PULP_VERSION,
            "solver": "PULP_CBC_CMD",
            "cbc_version": CBC_VERSION,
            "cbc_build_date": CBC_BUILD_DATE,
            "cbc_executable_content_sha256": CBC_EXECUTABLE_SHA256,
            "cbc_executable_bytes": CBC_EXECUTABLE_BYTES,
            "executable_path_law": "exact-resolved-bundled-pulp-cbc-path-bound",
            "gap_relative": CBC_GAP_REL,
            "gap_absolute": CBC_GAP_ABS,
            "presolve": CBC_PRESOLVE,
            "cuts": CBC_CUTS,
            "strong": CBC_STRONG,
            "warm_start": CBC_WARM_START,
            "threads": CBC_THREADS,
            "seed_options": list(CBC_SEED_OPTIONS),
            "time_mode": CBC_TIME_MODE,
            "time_limit_seconds": CBC_TIME_LIMIT_SECONDS,
            "work_limit_law": CBC_WORK_LIMIT_LAW,
            "node_limits": {
                str(key): value for key, value in ORACLE_NODE_LIMITS.items()
            },
        },
        "oracle_lower_bound": "deterministic-greedy-inclusive-230-witness",
        "oracle_upper_bound_fallback": (
            "min-opportunities-sum-largest-individual-inclusive-230-counts"
        ),
        "oracle_sparse_model_envelope": {
            "maximum_candidates": ORACLE_MAX_CANDIDATES,
            "maximum_opportunity_worlds": ORACLE_MAX_OPPORTUNITY_WORLDS,
            "maximum_event_edges": ORACLE_MAX_EVENT_EDGES,
        },
        "oracle_tie_role": "diagnostic-objective-bounds-not-book-selector",
        "oracle_proof_law": {
            "schema_version": CBC_PROOF_SCHEMA,
            "durable_evidence": (
                "inline-canonical-terminal-log-and-feasible-witness"
            ),
            "wall_clock_fields_in_identity": False,
            "canonical_replay_law": (
                "same-binary-options-model-and-maxNodes-work-budget"
            ),
        },
        "full_score_matrix_copy": False,
        "dense_candidate-by-world-boolean-matrix": False,
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "outer_exact_source_replay_required": True,
    }
    return _self_hash(body, "implementation_sha256")


def _strategy(
    *,
    ordinal: int,
    strategy_id: str,
    method: str,
    parameters: Mapping[str, object],
    tie_law: Sequence[str],
    role: str,
) -> dict[str, object]:
    implementation = frozen_preweek_additions_implementation_v1()
    body = {
        "schema_version": STRATEGY_SCHEMA,
        "ordinal": ordinal,
        "strategy_id": strategy_id,
        "method": method,
        "parameters": dict(parameters),
        "tie_law": list(tie_law),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": implementation["implementation_sha256"],
        "selection_inputs": "fit-scope-simulated-scores-only",
        "role": role,
    }
    return _self_hash(body, "strategy_sha256")


def frozen_preweek_additions_registry_v1() -> list[dict[str, object]]:
    """Return the two selectors and one non-selector diagnostic contract."""
    return [
        _strategy(
            ordinal=0,
            strategy_id="convex-excess-expected-max-ge-200-v1",
            method="greedy-convex-excess-expected-max-v1",
            parameters={
                "utility": "max(0,s-200)^2",
                "pivot": CONVEX_PIVOT,
                "exponent": CONVEX_EXPONENT,
                "parameter_sweep": False,
            },
            tie_law=[
                "largest-marginal-mean-convex-excess-expected-max-gain",
                "largest-individual-strict-gt-200-count",
                "largest-fit-world-mean-score",
                "ascending-lineup-id",
            ],
            role="fixed-aggressive-convex-expected-max-comparator",
        ),
        _strategy(
            ordinal=1,
            strategy_id="block-supported-bounded-tail-ge-210-250-v1",
            method="greedy-distinct-block-supported-inclusive-tail-ladder-v1",
            parameters={
                "rungs": [
                    {
                        "threshold": threshold,
                        "operator": operator,
                        "weight": weight,
                    }
                    for threshold, operator, weight in TAIL_RUNGS
                ],
                "support_scaling": "distinct-fit-block-count-per-candidate-rung",
            },
            tie_law=[
                "largest-block-supported-marginal-rung-utility",
                "largest-individual-strict-gt-200-count",
                "largest-fit-world-mean-score",
                "ascending-lineup-id",
            ],
            role="fixed-230-native-distinct-block-supported-selector",
        ),
        _strategy(
            ordinal=2,
            strategy_id="maximum-coverage-ge-230-oracle-diagnostic-v1",
            method="deterministic-exact-or-bounded-cbc-maximum-coverage-v1",
            parameters={
                "threshold": ORACLE_THRESHOLD,
                "operator": ORACLE_OPERATOR,
                "required_modes": {
                    str(key): value for key, value in ORACLE_REQUIRED_MODES.items()
                },
                "node_limits": {
                    str(key): value for key, value in ORACLE_NODE_LIMITS.items()
                },
                "work_limit_law": CBC_WORK_LIMIT_LAW,
                "time_limit_seconds": CBC_TIME_LIMIT_SECONDS,
                "time_mode": CBC_TIME_MODE,
                "wall_clock_fields_in_identity": False,
                "threads": CBC_THREADS,
                "seed_options": list(CBC_SEED_OPTIONS),
                "gap_relative": CBC_GAP_REL,
                "gap_absolute": CBC_GAP_ABS,
                "presolve": CBC_PRESOLVE,
                "cuts": CBC_CUTS,
                "strong": CBC_STRONG,
                "warm_start": CBC_WARM_START,
                "cbc_executable_content_sha256": CBC_EXECUTABLE_SHA256,
            },
            tie_law=[
                "objective-count-only-no-oracle-book-selection-authority",
                "greedy-witness-ties-by-count-mean-lineup-id",
            ],
            role="diagnostic-greedy-conversion-gap-only-not-a-selector",
        ),
    ]


def _guard_local_contracts() -> None:
    implementation = frozen_preweek_additions_implementation_v1()
    retained = implementation["implementation_sha256"]
    remainder = {
        key: value
        for key, value in implementation.items()
        if key != "implementation_sha256"
    }
    if (
        retained != _EXPECTED_IMPLEMENTATION_SHA256
        or _sha(remainder, label="local implementation") != retained
    ):
        _fail("local addition implementation contract drifted")
    observed: dict[str, str] = {}
    for raw in frozen_preweek_additions_registry_v1():
        strategy = _mapping(raw, label="local strategy")
        strategy_id = strategy.get("strategy_id")
        retained_hash = strategy.get("strategy_sha256")
        remainder = {
            key: value
            for key, value in strategy.items()
            if key != "strategy_sha256"
        }
        if (
            type(strategy_id) is not str
            or type(retained_hash) is not str
            or strategy_id in observed
            or _sha(remainder, label="local strategy") != retained_hash
        ):
            _fail("local strategy self-identity drifted")
        observed[strategy_id] = retained_hash
    if observed != _EXPECTED_STRATEGY_HASHES:
        _fail("local addition strategy registry drifted")


def _cbc_runtime_identity() -> dict[str, object]:
    if pulp.__version__ != PULP_VERSION:
        _fail("PuLP version differs from the frozen oracle backend")
    solver = pulp.PULP_CBC_CMD(msg=False)
    raw_path = solver.available()
    if not raw_path:
        _fail("the frozen bundled CBC solver is unavailable")
    path = Path(str(raw_path)).resolve()
    try:
        executable_bytes = path.stat().st_size
        digest = sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        executable_sha256 = digest.hexdigest()
    except OSError as exc:
        raise CorpusExtremeTailPreweekAdditionsError(
            "the frozen bundled CBC executable cannot be content-hashed"
        ) from exc
    if (
        executable_sha256 != CBC_EXECUTABLE_SHA256
        or executable_bytes != CBC_EXECUTABLE_BYTES
    ):
        _fail("CBC executable content identity differs from the frozen backend")
    try:
        completed = subprocess.run(
            [str(path), "-version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CorpusExtremeTailPreweekAdditionsError(
            "the frozen bundled CBC version cannot be inspected"
        ) from exc
    version_match = re.search(r"Version:\s*([^\s]+)", completed.stdout)
    build_match = re.search(r"Build Date:\s*(.+?)\s*$", completed.stdout, re.MULTILINE)
    if (
        version_match is None
        or version_match.group(1) != CBC_VERSION
        or build_match is None
        or build_match.group(1) != CBC_BUILD_DATE
    ):
        _fail("CBC version/build differs from the frozen oracle backend")
    return {
        "pulp_version": PULP_VERSION,
        "solver": "PULP_CBC_CMD",
        "cbc_version": CBC_VERSION,
        "cbc_build_date": CBC_BUILD_DATE,
        "executable_path": str(path),
        "executable_content_sha256": executable_sha256,
        "executable_bytes": executable_bytes,
        "gap_relative": CBC_GAP_REL,
        "gap_absolute": CBC_GAP_ABS,
        "presolve": CBC_PRESOLVE,
        "cuts": CBC_CUTS,
        "strong": CBC_STRONG,
        "warm_start": CBC_WARM_START,
        "threads": CBC_THREADS,
        "seed_options": list(CBC_SEED_OPTIONS),
        "node_limits": {
            str(key): value for key, value in ORACLE_NODE_LIMITS.items()
        },
        "deterministic_work_limit_law": CBC_WORK_LIMIT_LAW,
        "time_mode": CBC_TIME_MODE,
        "time_limit_seconds": CBC_TIME_LIMIT_SECONDS,
        "wall_clock_fields_in_identity": False,
    }


def _validated_scope(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool,
) -> tuple[
    list[str],
    np.ndarray,
    np.ndarray,
    tuple[str, ...],
    dict[str, object],
]:
    _guard_upstream_contracts()
    _guard_local_contracts()
    try:
        fit_scope = preweek.build_extreme_tail_preweek_fit_scope_binding_v1(
            lineup_ids=lineup_ids,
            fit_scores=fit_scores,
            training_blocks=training_blocks,
            heldout_block=heldout_block,
            worlds_per_block=worlds_per_block,
            candidate_mask_sha256=candidate_mask_sha256,
            occurrence_lineage_sha256=occurrence_lineage_sha256,
            source_manifest_identity=source_manifest_identity,
            source_member_identity=source_member_identity,
            source_score_matrix_identity=source_score_matrix_identity,
            require_production_width=require_production_width,
        )
    except preweek.CorpusExtremeTailPreweekSelectorsError as exc:
        raise CorpusExtremeTailPreweekAdditionsError(str(exc)) from exc
    raw_ids = list(_sequence(lineup_ids, label="lineup IDs"))
    canonical_source_rows = np.asarray(
        sorted(range(len(raw_ids)), key=raw_ids.__getitem__), dtype=np.int64
    )
    canonical_ids = [raw_ids[int(index)] for index in canonical_source_rows]
    if canonical_ids != fit_scope.get("ordered_lineup_ids"):
        _fail("canonical lineup order differs from the fit-scope binding")
    scores = np.asarray(fit_scores)
    if _score_matrix_hash(scores, canonical_source_rows) != _mapping(
        fit_scope.get("score_matrix_binding"), label="score-matrix binding"
    ).get("canonical_fit_score_matrix_sha256"):
        _fail("fit score matrix differs from the fit-scope binding")
    blocks = tuple(_sequence(fit_scope.get("training_blocks"), label="blocks"))
    if any(type(block) is not str for block in blocks):
        _fail("fit-scope block IDs differ")
    return canonical_ids, scores, canonical_source_rows, blocks, fit_scope


def _row_strict_200_counts(
    *,
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
) -> np.ndarray:
    result = np.empty(len(canonical_source_rows), dtype=np.int64)
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        result[start:stop] = np.count_nonzero(
            _score_rows(scores, canonical_source_rows, start, stop) > 200.0,
            axis=1,
        )
    return result


def _utility(values: np.ndarray) -> np.ndarray:
    result = np.maximum(values - CONVEX_PIVOT, 0.0)
    np.square(result, out=result)
    if not np.isfinite(result).all():
        _fail("convex-excess utility overflows finite float64")
    return result


def _select_convex_expected_max(
    *,
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    lineup_ids: Sequence[str],
    means: np.ndarray,
    primary_counts: np.ndarray,
    ranking_depth: int = RANKING_DEPTH,
) -> tuple[list[int], list[dict[str, object]]]:
    if (
        type(ranking_depth) is not int
        or ranking_depth < 1
        or ranking_depth > len(lineup_ids)
    ):
        _fail("convex expected-max ranking depth is infeasible")
    world_count = scores.shape[1]
    current_scores = np.full(world_count, CONVEX_PIVOT, dtype=np.float64)
    current_utility = np.zeros(world_count, dtype=np.float64)
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < ranking_depth:
        best: int | None = None
        best_gain = -1.0
        best_key: tuple[object, ...] | None = None
        for start, stop in _candidate_chunks(len(lineup_ids)):
            values = _score_rows(scores, canonical_source_rows, start, stop)
            np.maximum(values, current_scores, out=values)
            transformed = _utility(values)
            gains = (transformed - current_utility).mean(
                axis=1, dtype=np.float64
            )
            if not np.isfinite(gains).all():
                _fail("convex expected-max marginal gain is non-finite")
            gains = np.maximum(gains, 0.0)
            for offset, raw_gain in enumerate(gains):
                index = start + offset
                if not remaining[index]:
                    continue
                gain = float(raw_gain)
                key = (
                    -gain,
                    -int(primary_counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_gain = gain
                    best_key = key
        if best is None:
            _fail("convex expected-max rank ended before requested depth")
        selected.append(best)
        trace.append(
            {
                "selection_rank": len(selected) - 1,
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "marginal_mean_convex_excess_expected_max_gain": best_gain,
                "individual_strict_gt_200_world_count": int(
                    primary_counts[best]
                ),
                "fit_world_mean_score": float(means[best]),
            }
        )
        selected_scores = _score_rows(
            scores, canonical_source_rows, best, best + 1
        )[0]
        np.maximum(current_scores, selected_scores, out=current_scores)
        current_utility = _utility(current_scores)
        remaining[best] = False
    return selected, trace


def _select_block_supported_ladder(
    *,
    packed_by_rung: Sequence[Sequence[np.ndarray]],
    lineup_ids: Sequence[str],
    means: np.ndarray,
    primary_counts: np.ndarray,
) -> tuple[list[int], list[dict[str, object]]]:
    if len(packed_by_rung) != len(TAIL_RUNGS):
        _fail("block-supported ladder rung count differs")
    block_count = len(packed_by_rung[0])
    if block_count not in {4, 5}:
        _fail("block-supported ladder requires four or five fit blocks")
    row_count = len(lineup_ids)
    supports: list[np.ndarray] = []
    for by_block in packed_by_rung:
        if len(by_block) != block_count:
            _fail("block-supported ladder block count differs by rung")
        support = np.zeros(row_count, dtype=np.int64)
        for packed in by_block:
            support += (_row_counts_by_block([packed]) > 0).astype(np.int64)
        supports.append(support)
    covered = [
        [np.zeros(packed.shape[1], dtype=np.uint8) for packed in by_block]
        for by_block in packed_by_rung
    ]
    remaining = np.ones(row_count, dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < RANKING_DEPTH:
        best: int | None = None
        best_utility = -1
        best_key: tuple[object, ...] | None = None
        for start, stop in _candidate_chunks(row_count):
            utility = np.zeros(stop - start, dtype=np.int64)
            for rung_ordinal, (_threshold, _operator, weight) in enumerate(
                TAIL_RUNGS
            ):
                fresh = np.zeros(stop - start, dtype=np.int64)
                for block_ordinal in range(block_count):
                    packed = packed_by_rung[rung_ordinal][block_ordinal]
                    unseen = np.bitwise_not(covered[rung_ordinal][block_ordinal])
                    fresh += _POPCOUNT[
                        np.bitwise_and(packed[start:stop], unseen)
                    ].sum(axis=1, dtype=np.int64)
                utility += weight * supports[rung_ordinal][start:stop] * fresh
            for offset, raw_utility in enumerate(utility):
                index = start + offset
                if not remaining[index]:
                    continue
                marginal = int(raw_utility)
                key = (
                    -marginal,
                    -int(primary_counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_utility = marginal
                    best_key = key
        if best is None:
            _fail("block-supported ladder rank ended before 80")
        selected.append(best)
        trace.append(
            {
                "selection_rank": len(selected) - 1,
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "marginal_block_supported_rung_utility": best_utility,
                "individual_strict_gt_200_world_count": int(
                    primary_counts[best]
                ),
                "fit_world_mean_score": float(means[best]),
                "distinct_block_support_by_rung": [
                    int(support[best]) for support in supports
                ],
            }
        )
        for rung_ordinal in range(len(TAIL_RUNGS)):
            for block_ordinal in range(block_count):
                covered[rung_ordinal][block_ordinal] |= packed_by_rung[
                    rung_ordinal
                ][block_ordinal][best]
        remaining[best] = False
    return selected, trace


def _select_greedy_230_witness(
    *,
    packed_by_block: Sequence[np.ndarray],
    lineup_ids: Sequence[str],
    means: np.ndarray,
) -> tuple[list[int], list[dict[str, object]]]:
    counts = _row_counts_by_block(packed_by_block)
    covered = [
        np.zeros(packed.shape[1], dtype=np.uint8) for packed in packed_by_block
    ]
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    cumulative = 0
    while len(selected) < RANKING_DEPTH:
        best: int | None = None
        best_gain = -1
        best_key: tuple[object, ...] | None = None
        for start, stop in _candidate_chunks(len(lineup_ids)):
            gains = np.zeros(stop - start, dtype=np.int64)
            for packed, seen in zip(packed_by_block, covered, strict=True):
                gains += _POPCOUNT[
                    np.bitwise_and(packed[start:stop], np.bitwise_not(seen))
                ].sum(axis=1, dtype=np.int64)
            for offset, raw_gain in enumerate(gains):
                index = start + offset
                if not remaining[index]:
                    continue
                gain = int(raw_gain)
                key = (
                    -gain,
                    -int(counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_gain = gain
                    best_key = key
        if best is None:
            _fail("inclusive-230 greedy witness ended before 80")
        cumulative += best_gain
        selected.append(best)
        trace.append(
            {
                "selection_rank": len(selected) - 1,
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "marginal_new_inclusive_230_world_count": best_gain,
                "cumulative_inclusive_230_world_count": cumulative,
                "individual_inclusive_230_world_count": int(counts[best]),
                "fit_world_mean_score": float(means[best]),
            }
        )
        for packed, seen in zip(packed_by_block, covered, strict=True):
            seen |= packed[best]
        remaining[best] = False
    return selected, trace


def _book(
    *,
    strategy: Mapping[str, object],
    fit_scope_id: str,
    input_binding_sha256: str,
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    budget: int,
) -> dict[str, object]:
    indices = [int(value) for value in selected[:budget]]
    prefix_trace = [dict(row) for row in trace[:budget]]
    if (
        budget not in ENTRY_BUDGETS
        or len(indices) != budget
        or len(set(indices)) != budget
        or len(prefix_trace) != budget
    ):
        _fail("selector book is not an exact unique prefix")
    selected_ids = [lineup_ids[index] for index in indices]
    for rank, (index, lineup_id, row) in enumerate(
        zip(indices, selected_ids, prefix_trace, strict=True)
    ):
        if (
            row.get("selection_rank") != rank
            or row.get("canonical_lineup_index") != index
            or row.get("lineup_id") != lineup_id
        ):
            _fail("selector trace cannot replay its book prefix")
    source_rows = canonical_source_rows[np.asarray(indices, dtype=np.int64)]
    body = {
        "schema_version": BOOK_SCHEMA,
        "book_id": f"{fit_scope_id}:{strategy['strategy_id']}:exact-{budget}",
        "fit_scope_id": fit_scope_id,
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "input_binding_sha256": input_binding_sha256,
        "entry_budget": budget,
        "entry_count": budget,
        "ranking_depth": RANKING_DEPTH,
        "ranking_prefix_law": "exact-prefix-of-one-deterministic-rank-80",
        "selected_canonical_indices": indices,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": _sha(
            selected_ids, label="selected lineup IDs"
        ),
        "selected_fit_score_matrix_sha256": _score_matrix_hash(
            scores, source_rows
        ),
        "marginal_trace": prefix_trace,
        "marginal_trace_sha256": _sha(prefix_trace, label="marginal trace"),
        **_false_authorities(),
    }
    return _self_hash(body, "book_sha256")


def _selector_receipt(
    *,
    strategy: Mapping[str, object],
    fit_scope_id: str,
    input_binding_sha256: str,
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
) -> dict[str, object]:
    if (
        len(selected) != RANKING_DEPTH
        or len(set(selected)) != RANKING_DEPTH
        or len(trace) != RANKING_DEPTH
    ):
        _fail("selector must materialize one exact unique rank 80")
    rank_ids = [lineup_ids[int(index)] for index in selected]
    books = [
        _book(
            strategy=strategy,
            fit_scope_id=fit_scope_id,
            input_binding_sha256=input_binding_sha256,
            selected=selected,
            trace=trace,
            lineup_ids=lineup_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            budget=budget,
        )
        for budget in ENTRY_BUDGETS
    ]
    body = {
        "schema_version": SELECTOR_SCHEMA,
        "fit_scope_id": fit_scope_id,
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "input_binding_sha256": input_binding_sha256,
        "status": "feasible-exact-rank-80",
        "ranking_depth": RANKING_DEPTH,
        "rank_80_canonical_indices": [int(value) for value in selected],
        "rank_80_lineup_ids": rank_ids,
        "rank_80_lineup_ids_sha256": _sha(rank_ids, label="rank 80 IDs"),
        "rank_trace": [dict(row) for row in trace],
        "rank_trace_sha256": _sha(trace, label="rank trace"),
        "entry_budgets": list(ENTRY_BUDGETS),
        "book_count": len(books),
        "books": books,
        **_false_authorities(),
    }
    return _self_hash(body, "selector_receipt_sha256")


def _opportunity_count(packed_by_block: Sequence[np.ndarray]) -> int:
    total = 0
    for packed in packed_by_block:
        union = np.bitwise_or.reduce(packed, axis=0)
        total += int(_POPCOUNT[union].sum(dtype=np.int64))
    return total


def _analytical_upper_bound(
    *, counts: np.ndarray, opportunity_count: int, budget: int
) -> int:
    if opportunity_count == 0:
        return 0
    largest = np.sort(counts)[-budget:]
    return min(opportunity_count, int(largest.sum(dtype=np.int64)))


def _sparse_incidence(
    *,
    packed_by_block: Sequence[np.ndarray],
    worlds_per_block: int,
) -> list[tuple[int, list[int]]]:
    world_to_candidates = [
        [] for _ in range(len(packed_by_block) * worlds_per_block)
    ]
    for candidate in range(packed_by_block[0].shape[0]):
        for block_ordinal, packed in enumerate(packed_by_block):
            bits = np.unpackbits(
                packed[candidate], bitorder=PACKED_BITORDER,
                count=worlds_per_block,
            )
            for local_world in np.flatnonzero(bits):
                world_to_candidates[
                    block_ordinal * worlds_per_block + int(local_world)
                ].append(candidate)
    return [
        (world, candidates)
        for world, candidates in enumerate(world_to_candidates)
        if candidates
    ]


def _cbc_log_upper_bound(log: str) -> float | None:
    match = _CBC_UPPER_RE.search(log)
    if match is None:
        return None
    value = float(match.group(1))
    return value if math.isfinite(value) else None


def _safe_integer_upper_from_cbc(value: float, *, cap: int) -> int:
    # CBC prints a rounded decimal bound.  At a printed integer on a
    # non-optimal solve, add one before capping rather than risk understating
    # the true relaxation bound by the log's hidden decimal precision.
    if value == math.floor(value):
        return min(cap, int(value) + 1)
    return min(cap, int(math.ceil(value)))


def _canonical_solver_log(log: str) -> list[str]:
    """Retain only terminal proof lines; exclude paths and all clock telemetry."""
    prefixes = (
        "Result - ",
        "Objective value:",
        "Upper bound:",
        "Gap:",
        "Enumerated nodes:",
        "Total iterations:",
        "Problem is infeasible",
        "No feasible solution found",
    )
    return [
        " ".join(line.strip().split())
        for line in log.splitlines()
        if line.strip().startswith(prefixes)
    ]


def _solver_proof(
    *,
    proof_kind: str,
    model_identity_sha256: str,
    backend: Mapping[str, object],
    node_limit: int,
    canonical_log: Sequence[str],
    solver_status: str,
    solution_status: str,
    terminal_reason: str,
    exact: bool,
    incumbent: int | None,
    upper_bound: int,
    enumerated_nodes: int,
    selected_indices: Sequence[int],
) -> dict[str, object]:
    log_lines = list(canonical_log)
    body = {
        "schema_version": CBC_PROOF_SCHEMA,
        "proof_kind": proof_kind,
        "model_identity_sha256": model_identity_sha256,
        "backend_identity_sha256": _sha(backend, label="CBC backend identity"),
        "execution_options": {
            "gap_relative": CBC_GAP_REL,
            "gap_absolute": CBC_GAP_ABS,
            "presolve": CBC_PRESOLVE,
            "cuts": CBC_CUTS,
            "strong": CBC_STRONG,
            "warm_start": CBC_WARM_START,
            "threads": CBC_THREADS,
            "seed_options": list(CBC_SEED_OPTIONS),
            "node_limit": node_limit,
            "work_limit_law": CBC_WORK_LIMIT_LAW,
            "time_mode": CBC_TIME_MODE,
            "time_limit_seconds": CBC_TIME_LIMIT_SECONDS,
        },
        "solver_status": solver_status,
        "solution_status": solution_status,
        "terminal_reason": terminal_reason,
        "exact_optimum_proven": exact,
        "incumbent_world_count": incumbent,
        "upper_bound_world_count": upper_bound,
        "enumerated_nodes": enumerated_nodes,
        "witness_selected_canonical_indices": [
            int(value) for value in selected_indices
        ],
        "canonical_solver_log": log_lines,
        "canonical_solver_log_sha256": _sha(
            log_lines, label="canonical CBC terminal log"
        ),
        "raw_solver_log_retention": "excluded-load-sensitive-telemetry",
        "wall_clock_telemetry_in_identity": False,
    }
    return _self_hash(body, "solver_proof_sha256")


def _solve_oracle_budget(
    *,
    budget: int,
    sparse_incidence: Sequence[tuple[int, Sequence[int]]] | None,
    candidate_count: int,
    opportunity_count: int,
    event_edge_count: int,
    analytical_upper_bound: int,
    greedy_indices: Sequence[int],
    lineup_ids: Sequence[str],
    greedy_coverage: int,
    backend: Mapping[str, object],
    input_binding_sha256: str,
    event_incidence_sha256: str,
) -> dict[str, object]:
    required_mode = ORACLE_REQUIRED_MODES[budget]
    node_limit = ORACLE_NODE_LIMITS[budget]
    model_identity_sha256 = _sha(
        {
            "input_binding_sha256": input_binding_sha256,
            "event_incidence_sha256": event_incidence_sha256,
            "entry_budget": budget,
            "candidate_count": candidate_count,
            "opportunity_world_count": opportunity_count,
            "event_edge_count": event_edge_count,
            "objective": "maximize-distinct-inclusive-230-covered-worlds",
            "candidate_constraint": "sum-binary-candidate-selection-equals-budget",
            "coverage_constraint": "binary-world-covered-le-sum-selected-hitters",
        },
        label="maximum-coverage MIP model identity",
    )
    selected_indices = [int(value) for value in greedy_indices[:budget]]
    selected_ids = [lineup_ids[index] for index in selected_indices]
    lower_bound = greedy_coverage
    upper_bound = analytical_upper_bound
    incumbent = None
    solver_reported_upper = None
    enumerated_nodes = 0
    solver_status = "not-run"
    solution_status = "not-run"
    log = ""
    exact = opportunity_count == 0
    attempted = False
    if opportunity_count == 0:
        terminal_reason = "zero-opportunities-optimal-proven"
    elif sparse_incidence is None:
        terminal_reason = "sparse-model-envelope-bounded"
    else:
        attempted = True
        model = pulp.LpProblem(
            f"maximum_coverage_ge_230_n_{budget}", pulp.LpMaximize
        )
        x = [
            pulp.LpVariable(f"candidate_{index:08d}", cat="Binary")
            for index in range(candidate_count)
        ]
        y = {
            world: pulp.LpVariable(f"world_{world:08d}", cat="Binary")
            for world, _candidates in sparse_incidence
        }
        model += pulp.lpSum(y.values())
        model += pulp.lpSum(x) == budget
        for world, candidates in sparse_incidence:
            model += y[world] <= pulp.lpSum(x[index] for index in candidates)
        greedy_set = set(selected_indices)
        for index, variable in enumerate(x):
            variable.setInitialValue(1 if index in greedy_set else 0)
        covered_worlds = {
            world
            for world, candidates in sparse_incidence
            if any(index in greedy_set for index in candidates)
        }
        for world, variable in y.items():
            variable.setInitialValue(1 if world in covered_worlds else 0)
        with tempfile.TemporaryDirectory(prefix="preweek-cbc-") as temp_dir:
            log_path = Path(temp_dir) / "cbc.log"
            solver = pulp.PULP_CBC_CMD(
                msg=False,
                gapRel=CBC_GAP_REL,
                gapAbs=CBC_GAP_ABS,
                presolve=CBC_PRESOLVE,
                cuts=CBC_CUTS,
                strong=CBC_STRONG,
                options=list(CBC_SEED_OPTIONS),
                warmStart=CBC_WARM_START,
                threads=CBC_THREADS,
                logPath=str(log_path),
                timeMode=CBC_TIME_MODE,
                maxNodes=node_limit,
            )
            try:
                model.solve(solver)
                log = log_path.read_text(encoding="utf-8")
            except (OSError, pulp.PulpError) as exc:
                log = ""
                solver_status = f"solver-error:{type(exc).__name__}"
                terminal_reason = "solver-error-analytical-bound"
            else:
                solver_status = pulp.LpStatus.get(model.status, "Unknown")
                solution_status = pulp.LpSolution.get(
                    model.sol_status, "Unknown"
                )
                nodes_match = _CBC_NODES_RE.search(log)
                if nodes_match is not None:
                    enumerated_nodes = int(nodes_match.group(1))
                solver_reported_upper = _cbc_log_upper_bound(log)
                raw_selected = [
                    index
                    for index, variable in enumerate(x)
                    if variable.value() is not None and variable.value() > 0.5
                ]
                if len(raw_selected) == budget:
                    raw_selected_set = set(raw_selected)
                    selected_worlds = sum(
                        1
                        for _world, candidates in sparse_incidence
                        if any(index in raw_selected_set for index in candidates)
                    )
                    incumbent = selected_worlds
                    if selected_worlds > lower_bound:
                        lower_bound = selected_worlds
                        selected_indices = raw_selected
                        selected_ids = [lineup_ids[index] for index in raw_selected]
                optimal_log = "Result - Optimal solution found" in log
                exact = optimal_log and incumbent is not None
                if exact:
                    upper_bound = int(incumbent)
                    terminal_reason = "optimal-proven"
                else:
                    if solver_reported_upper is not None:
                        upper_bound = max(
                            lower_bound,
                            _safe_integer_upper_from_cbc(
                                solver_reported_upper,
                                cap=analytical_upper_bound,
                            ),
                        )
                    if (
                        "Stopped on node limit" in log
                        or "Exiting on maximum nodes" in log
                    ):
                        terminal_reason = "node-budget-bounded"
                    else:
                        terminal_reason = "solver-no-proof-bounded"
    if lower_bound > upper_bound:
        _fail("oracle lower bound exceeds its safe upper bound")
    absolute_gap = upper_bound - lower_bound
    relative_gap = 0.0 if upper_bound == 0 else absolute_gap / upper_bound
    status = (
        "exact-optimum-proven"
        if exact
        else (
            "required-exact-not-proven"
            if required_mode == "exact"
            else "bounded-diagnostic"
        )
    )
    proof_kind = (
        "cbc-terminal-proof"
        if attempted and not solver_status.startswith("solver-error:")
        else (
            "cbc-solver-error-proof"
            if attempted
            else "analytical-no-mip-proof"
        )
    )
    proof = _solver_proof(
        proof_kind=proof_kind,
        model_identity_sha256=model_identity_sha256,
        backend=backend,
        node_limit=node_limit,
        canonical_log=_canonical_solver_log(log),
        solver_status=solver_status,
        solution_status=solution_status,
        terminal_reason=terminal_reason,
        exact=exact,
        incumbent=incumbent,
        upper_bound=upper_bound,
        enumerated_nodes=enumerated_nodes,
        selected_indices=selected_indices,
    )
    body = {
        "schema_version": ORACLE_ROW_SCHEMA,
        "entry_budget": budget,
        "required_mode": required_mode,
        "status": status,
        "terminal_reason": terminal_reason,
        "solver_attempted": attempted,
        "exact_optimum_proven": exact,
        "incumbent_world_count": incumbent,
        "lower_bound_world_count": lower_bound,
        "upper_bound_world_count": upper_bound,
        "absolute_gap_world_count": absolute_gap,
        "relative_gap": relative_gap,
        "relative_gap_rational": {
            "numerator": absolute_gap,
            "denominator": upper_bound,
        },
        "opportunity_world_count": opportunity_count,
        "candidate_count": candidate_count,
        "event_edge_count": event_edge_count,
        "analytical_upper_bound_world_count": analytical_upper_bound,
        "solver_reported_upper_bound": solver_reported_upper,
        "solver_status": solver_status,
        "solution_status": solution_status,
        "enumerated_nodes": enumerated_nodes,
        "deterministic_work_limit_law": CBC_WORK_LIMIT_LAW,
        "node_limit": node_limit,
        "time_mode": backend["time_mode"],
        "time_limit_seconds": backend["time_limit_seconds"],
        "wall_clock_telemetry_in_identity": False,
        "threads": backend["threads"],
        "seed_options": backend["seed_options"],
        "gap_relative": backend["gap_relative"],
        "gap_absolute": backend["gap_absolute"],
        "presolve": backend["presolve"],
        "cuts": backend["cuts"],
        "strong": backend["strong"],
        "warm_start": backend["warm_start"],
        "model_identity_sha256": model_identity_sha256,
        "solver_proof": proof,
        "solver_proof_sha256": proof["solver_proof_sha256"],
        "witness_selected_canonical_indices": selected_indices,
        "witness_selected_lineup_ids": selected_ids,
        "witness_selected_lineup_ids_sha256": _sha(
            selected_ids, label="oracle witness lineup IDs"
        ),
        "diagnostic_only": True,
        "oracle_book_selection_authority": False,
        **_false_authorities(),
    }
    return _self_hash(body, "oracle_row_sha256")


def _oracle_receipt(
    *,
    strategy: Mapping[str, object],
    fit_scope_id: str,
    fit_scope_binding_sha256: str,
    input_binding_sha256: str,
    packed_by_block: Sequence[np.ndarray],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    lineup_ids: Sequence[str],
    means: np.ndarray,
    backend: Mapping[str, object],
) -> dict[str, object]:
    counts = _row_counts_by_block(packed_by_block)
    opportunity_count = _opportunity_count(packed_by_block)
    event_edge_count = int(counts.sum(dtype=np.int64))
    incidence_hash = _packed_incidence_hash(
        packed_by_block=packed_by_block,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
        threshold=ORACLE_THRESHOLD,
        operator=ORACLE_OPERATOR,
    )
    greedy_indices, greedy_trace = _select_greedy_230_witness(
        packed_by_block=packed_by_block,
        lineup_ids=lineup_ids,
        means=means,
    )
    greedy_ids = [lineup_ids[index] for index in greedy_indices]
    model_inside_envelope = (
        len(lineup_ids) <= ORACLE_MAX_CANDIDATES
        and opportunity_count <= ORACLE_MAX_OPPORTUNITY_WORLDS
        and event_edge_count <= ORACLE_MAX_EVENT_EDGES
    )
    sparse = (
        _sparse_incidence(
            packed_by_block=packed_by_block,
            worlds_per_block=worlds_per_block,
        )
        if model_inside_envelope and opportunity_count > 0
        else None
    )
    if sparse is not None:
        observed_edges = sum(len(candidates) for _world, candidates in sparse)
        if len(sparse) != opportunity_count or observed_edges != event_edge_count:
            _fail("sparse oracle incidence differs from packed event lineage")
    rows = []
    for budget in ENTRY_BUDGETS:
        greedy_coverage = int(
            greedy_trace[budget - 1]["cumulative_inclusive_230_world_count"]
        )
        rows.append(
            _solve_oracle_budget(
                budget=budget,
                sparse_incidence=sparse,
                candidate_count=len(lineup_ids),
                opportunity_count=opportunity_count,
                event_edge_count=event_edge_count,
                analytical_upper_bound=_analytical_upper_bound(
                    counts=counts,
                    opportunity_count=opportunity_count,
                    budget=budget,
                ),
                greedy_indices=greedy_indices,
                lineup_ids=lineup_ids,
                greedy_coverage=greedy_coverage,
                backend=backend,
                input_binding_sha256=input_binding_sha256,
                event_incidence_sha256=incidence_hash,
            )
        )
    body = {
        "schema_version": ORACLE_SCHEMA,
        "oracle_id": f"{fit_scope_id}:maximum-coverage-ge-230-oracle-diagnostic-v1",
        "fit_scope_id": fit_scope_id,
        "fit_scope_binding_sha256": fit_scope_binding_sha256,
        "input_binding_sha256": input_binding_sha256,
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "threshold": ORACLE_THRESHOLD,
        "operator": ORACLE_OPERATOR,
        "training_blocks": list(training_blocks),
        "worlds_per_block": worlds_per_block,
        "candidate_count": len(lineup_ids),
        "opportunity_world_count": opportunity_count,
        "event_edge_count": event_edge_count,
        "event_incidence_sha256": incidence_hash,
        "model_inside_frozen_sparse_envelope": model_inside_envelope,
        "sparse_model_envelope": {
            "maximum_candidates": ORACLE_MAX_CANDIDATES,
            "maximum_opportunity_worlds": ORACLE_MAX_OPPORTUNITY_WORLDS,
            "maximum_event_edges": ORACLE_MAX_EVENT_EDGES,
        },
        "backend": dict(backend),
        "greedy_witness_rank_80_lineup_ids": greedy_ids,
        "greedy_witness_rank_80_lineup_ids_sha256": _sha(
            greedy_ids, label="oracle greedy rank IDs"
        ),
        "greedy_witness_trace": greedy_trace,
        "greedy_witness_trace_sha256": _sha(
            greedy_trace, label="oracle greedy trace"
        ),
        "entry_budgets": list(ENTRY_BUDGETS),
        "row_count": len(rows),
        "rows": rows,
        "rows_sha256": _sha(
            [row["oracle_row_sha256"] for row in rows],
            label="oracle row hashes",
        ),
        "solver_proof_sha256s": [
            row["solver_proof_sha256"] for row in rows
        ],
        "solver_proof_sha256s_sha256": _sha(
            [row["solver_proof_sha256"] for row in rows],
            label="durable solver proof hashes",
        ),
        "evidence_role": "diagnostic-conversion-gap-only",
        "not_a_post_result_book_selector": True,
        "standalone_source_authority": False,
        "outer_exact_source_replay_required": True,
        **_false_authorities(),
    }
    return _self_hash(body, "oracle_sha256")


def run_extreme_tail_preweek_additions_v1(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Run both fixed selectors and the diagnostic 230 coverage oracle."""
    (
        canonical_ids,
        scores,
        canonical_source_rows,
        blocks,
        fit_scope,
    ) = _validated_scope(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        candidate_mask_sha256=candidate_mask_sha256,
        occurrence_lineage_sha256=occurrence_lineage_sha256,
        source_manifest_identity=source_manifest_identity,
        source_member_identity=source_member_identity,
        source_score_matrix_identity=source_score_matrix_identity,
        require_production_width=require_production_width,
    )
    implementation = frozen_preweek_additions_implementation_v1()
    registry = frozen_preweek_additions_registry_v1()
    upstream = _guard_upstream_contracts()
    backend = _cbc_runtime_identity()
    input_body = {
        "schema_version": INPUT_BINDING_SCHEMA,
        "fit_scope_id": fit_scope["fit_scope_id"],
        "fit_scope_binding": fit_scope,
        "fit_scope_binding_sha256": fit_scope["fit_scope_binding_sha256"],
        "candidate_mask_sha256": fit_scope["candidate_mask_sha256"],
        "occurrence_lineage_sha256": fit_scope["occurrence_lineage_sha256"],
        "score_matrix_binding": fit_scope["score_matrix_binding"],
        "source_manifest_identity": fit_scope["source_manifest_identity"],
        "source_member_identity": fit_scope["source_member_identity"],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "convex_utility": "max(0,s-200)^2",
        "convex_parameter_sweep": False,
        "tail_rungs": [
            {"threshold": threshold, "operator": operator, "weight": weight}
            for threshold, operator, weight in TAIL_RUNGS
        ],
        "oracle_threshold": ORACLE_THRESHOLD,
        "oracle_operator": ORACLE_OPERATOR,
        "oracle_backend": backend,
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": implementation["implementation_sha256"],
        "strategy_registry_sha256": _sha(
            registry, label="addition strategy registry"
        ),
        "upstream_contracts": upstream,
        "require_production_width": require_production_width,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        "standalone_source_authority": False,
        "outer_exact_source_replay_required": True,
        **_false_authorities(),
    }
    input_binding = _self_hash(input_body, "input_binding_sha256")
    input_hash = str(input_binding["input_binding_sha256"])
    means = _row_means(scores, canonical_source_rows)
    primary_counts = _row_strict_200_counts(
        scores=scores, canonical_source_rows=canonical_source_rows
    )

    convex_selected, convex_trace = _select_convex_expected_max(
        scores=scores,
        canonical_source_rows=canonical_source_rows,
        lineup_ids=canonical_ids,
        means=means,
        primary_counts=primary_counts,
    )
    convex_receipt = _selector_receipt(
        strategy=registry[0],
        fit_scope_id=str(fit_scope["fit_scope_id"]),
        input_binding_sha256=input_hash,
        selected=convex_selected,
        trace=convex_trace,
        lineup_ids=canonical_ids,
        scores=scores,
        canonical_source_rows=canonical_source_rows,
    )

    packed_by_rung = [
        [
            _pack_event_mask(
                scores,
                canonical_source_rows,
                threshold=threshold,
                operator=operator,
                column_start=block_ordinal * worlds_per_block,
                column_stop=(block_ordinal + 1) * worlds_per_block,
            )
            for block_ordinal in range(len(blocks))
        ]
        for threshold, operator, _weight in TAIL_RUNGS
    ]
    block_selected, block_trace = _select_block_supported_ladder(
        packed_by_rung=packed_by_rung,
        lineup_ids=canonical_ids,
        means=means,
        primary_counts=primary_counts,
    )
    block_receipt = _selector_receipt(
        strategy=registry[1],
        fit_scope_id=str(fit_scope["fit_scope_id"]),
        input_binding_sha256=input_hash,
        selected=block_selected,
        trace=block_trace,
        lineup_ids=canonical_ids,
        scores=scores,
        canonical_source_rows=canonical_source_rows,
    )

    packed_230 = packed_by_rung[2]
    oracle = _oracle_receipt(
        strategy=registry[2],
        fit_scope_id=str(fit_scope["fit_scope_id"]),
        fit_scope_binding_sha256=str(fit_scope["fit_scope_binding_sha256"]),
        input_binding_sha256=input_hash,
        packed_by_block=packed_230,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
        lineup_ids=canonical_ids,
        means=means,
        backend=backend,
    )
    selectors = [convex_receipt, block_receipt]
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "receipt_law_id": RECEIPT_LAW_ID,
        "fit_scope_id": fit_scope["fit_scope_id"],
        "fit_scope_binding_sha256": fit_scope["fit_scope_binding_sha256"],
        "input_binding": input_binding,
        "input_binding_sha256": input_hash,
        "implementation": implementation,
        "implementation_sha256": implementation["implementation_sha256"],
        "strategy_registry": registry,
        "strategy_registry_sha256": _sha(
            registry, label="addition strategy registry"
        ),
        "selector_count": len(selectors),
        "selectors": selectors,
        "selectors_sha256": _sha(
            [row["selector_receipt_sha256"] for row in selectors],
            label="selector receipt hashes",
        ),
        "oracle": oracle,
        "oracle_sha256": oracle["oracle_sha256"],
        "entry_budgets": list(ENTRY_BUDGETS),
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        "standalone_source_authority": False,
        "outer_exact_source_replay_required": True,
        **_false_authorities(),
    }
    return _self_hash(body, "receipt_sha256")


def validate_extreme_tail_preweek_additions_v1(
    receipt: object,
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Replay a receipt against the exact source identities and fit matrix."""
    item = _mapping(receipt, label="preweek addition receipt")
    if item.get("schema_version") != RECEIPT_SCHEMA:
        _fail("preweek addition receipt schema differs")
    retained_hash = item.get("receipt_sha256")
    if type(retained_hash) is not str:
        _fail("preweek addition receipt hash is absent")
    remainder = {key: value for key, value in item.items() if key != "receipt_sha256"}
    if _sha(remainder, label="preweek addition receipt") != retained_hash:
        _fail("preweek addition receipt self-hash differs")
    expected = run_extreme_tail_preweek_additions_v1(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        candidate_mask_sha256=candidate_mask_sha256,
        occurrence_lineage_sha256=occurrence_lineage_sha256,
        source_manifest_identity=source_manifest_identity,
        source_member_identity=source_member_identity,
        source_score_matrix_identity=source_score_matrix_identity,
        require_production_width=require_production_width,
    )
    if _canonical(item, label="retained receipt") != _canonical(
        expected, label="replayed receipt"
    ):
        _fail("preweek addition receipt differs from canonical replay")
    return expected


__all__ = [
    "CorpusExtremeTailPreweekAdditionsError",
    "ENTRY_BUDGETS",
    "RANKING_DEPTH",
    "frozen_preweek_additions_implementation_v1",
    "frozen_preweek_additions_registry_v1",
    "run_extreme_tail_preweek_additions_v1",
    "validate_extreme_tail_preweek_additions_v1",
]
