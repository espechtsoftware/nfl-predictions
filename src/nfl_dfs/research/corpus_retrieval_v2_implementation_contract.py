"""Fail-closed implementation identity for the public R6-v2 comparators.

The retrieval strategy registry historically self-hashed its declarative laws,
but did not publish a separate identity for the Python implementation that
dispatches and executes those laws.  This module supplies that missing seam
without modifying the engine.  It binds all seven public v2 strategies, their
dispatch and selector source, the complete engine source file, and numerical
runtime facts that can affect exact ties.

Absolute filesystem paths are retained only as diagnostics.  Contract identity
uses logical module IDs plus content hashes, so the same source-bearing cloud
image can validate from a different installation path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
import platform
import sys
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_retrieval_engine as engine
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


CONTRACT_SCHEMA: Final = "corpus-retrieval-v2-implementation-contract/v1"
IMPLEMENTATION_ID: Final = "dense-public-r6-v2-comparator-engine-v1"
SOURCE_MODULE_LOGICAL_ID: Final = "nfl_dfs.research.corpus_retrieval_engine"
SOURCE_FILE_NAME: Final = "corpus_retrieval_engine.py"
SOURCE_FILE_BYTES: Final = 156_603
SOURCE_FILE_SHA256: Final = (
    "f69262c7468752ce40f0ae5ed55151046d4e9aacdad96fb1db6450188581c10a"
)
ENTRY_BUDGET: Final = 80
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
DISCOVERY_BLOCKS: Final = ("R0", "R1", "R2", "R3")
HELDOUT_BLOCKS: Final = ("R4",)
WORLDS_PER_BLOCK: Final = 10_000
PRIMARY_EVENT_THRESHOLD: Final = 200.0
PRIMARY_EVENT_OPERATOR: Final = ">"

_REGISTRY_SHA256: Final = (
    "cfaff695692ada8149b1b06afb772daf7cf457230dd9265b1f01a40582000f67"
)
_REGISTRY_POINTERS_SHA256: Final = (
    "0ecfc0b4f86de8c0a42d1f538395ad86cde787e8cc652e7e682d2336c70b41bd"
)
_STRATEGY_HASHES: Final = {
    "coverage-194-v1": (
        "1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f"
    ),
    "strict-200-coverage-v1": (
        "9689bb11de4616e4a6295ae0a5b0ec30aa174097f1965867fdc08d7b2e7d02de"
    ),
    "tail-ladder-200-210-220-v1": (
        "5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea"
    ),
    "mean-score-v1": (
        "5c880aeca7c8ec3386a9d44b111937fada857f569cb324dd2163987b333654c6"
    ),
    "expected-max-v1": (
        "ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780"
    ),
    "block-supported-tail-ladder-v1": (
        "1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b"
    ),
    "regime-robust-ladder-v1": (
        "125610a3fda4c230bacd44f1778e43fe03905a504d55ec6fe4c424c0cbbd0e7b"
    ),
}
_CALLABLE_SOURCE_IDENTITIES: Final = {
    "_strategy": (606, "96f800591336f168645bf4650f94b36aa23afb413bef26fa36da5a295c26855c"),
    "frozen_retrieval_strategies": (2751, "0175127fb23b517085b70eb129399efb3eb71119bf7ac16a00a67887992c533b"),
    "frozen_retrieval_strategies_v2": (3081, "3e7916f6369197d82bd6a8517028956831d2feeab651a180c499a49811d53157"),
    "validate_retrieval_strategy_v2": (858, "a65912a717b2666118c85d60deecb0b81e389b10c93e0c53cef395b101dfecce"),
    "suite_strategy_law": (358, "4810e11c24fdc0ff0b922ff338c98c30da15ee911aa9df53f6b47f72d0d25529"),
    "validate_suite_manifest": (4545, "72a7afb81468a585d5c80ac820fc5e6f9de7464da5c3a3f8da8e9d55b46f3da0"),
    "_prepare_task_sources": (8627, "5354e4ad0c450ce6218f29976a533e041c0af450794568a064b1b066009756a0"),
    "_support": (302, "e33646f962b8f13d06ae36e52a85d90d93549e70b8c9a79effd484e01e6caeb5"),
    "_discovery_lineup_view": (1547, "1734e4f5e13409a83e7f0fcb5ef593557d009482484bf54ca404726354daa964"),
    "_select_coverage": (1925, "42226767f95cc323fc1938b65d87207b7c0d4e0782b8d8f1702d523c3a69ace2"),
    "_select_ladder": (1951, "0cb37297d220371c1dae384ee61379fb2881bac595b89b8fc84abb32eaec4e46"),
    "_select_mean": (854, "2caab38561cb7e74d6d12d3013cae7fc7f203bfaa79b0aab294a3ed3f1ef5371"),
    "_discovery_block_view": (542, "e93936079a29d7e9fe1c3df115893d2527dcd0324e502a2facc267586f939f14"),
    "_select_expected_max": (1997, "9b966361d80d3354f62150b9ea421deb769a1d76ed3aea7733bd439c2aa41adc"),
    "_select_block_supported_ladder": (2797, "6fd1be7ac32f0cb1f4e43dd74f35eb09ecb24786f16b34fb14b2690309506da3"),
    "_select_blockmin_ladder": (3489, "ae7cf9763ac64e7632296028c9cad4b0e90289da02e7ff41d655dcd8a899ca98"),
    "_run_strategy": (1643, "a80971d912469998a1650857c5a13d8385957b68751b747b9a8e04bec96b3378"),
    "_run_discovery_strategy": (1360, "efcb9aa9b406abd799d22c52962a79eb77286ca75f1b3a847c7d0ff64b6a3ad7"),
}
_CALLABLE_ORDER: Final = tuple(_CALLABLE_SOURCE_IDENTITIES)
_METHOD_TO_CALLABLE: Final = (
    {
        "method": "greedy-threshold-coverage-v1",
        "callable": "_select_coverage",
        "strategy_ids": ["coverage-194-v1", "strict-200-coverage-v1"],
    },
    {
        "method": "greedy-tail-ladder-v1",
        "callable": "_select_ladder",
        "strategy_ids": ["tail-ladder-200-210-220-v1"],
    },
    {
        "method": "rank-mean-score-v1",
        "callable": "_select_mean",
        "strategy_ids": ["mean-score-v1"],
    },
    {
        "method": "greedy-expected-max-v1",
        "callable": "_select_expected_max",
        "strategy_ids": ["expected-max-v1"],
    },
    {
        "method": "greedy-block-supported-ladder-v1",
        "callable": "_select_block_supported_ladder",
        "strategy_ids": ["block-supported-tail-ladder-v1"],
    },
    {
        "method": "greedy-blockmin-ladder-v1",
        "callable": "_select_blockmin_ladder",
        "strategy_ids": ["regime-robust-ladder-v1"],
    },
)
_PYTHON_VERSION: Final = "3.14.4"
_PYTHON_IMPLEMENTATION: Final = "CPython"
_PYTHON_EXECUTABLE_BYTES: Final = 7_481_192
_PYTHON_EXECUTABLE_SHA256: Final = (
    "b8d8288faefdd300201f43fcf00f6f539a27218eeed3a3dff5ab10b9c4c99700"
)
_NUMPY_VERSION: Final = "2.5.1"
_NUMPY_CORE_BYTES: Final = 10_674_137
_NUMPY_CORE_SHA256: Final = (
    "f34681e97d7eb6d5c3eabe1f4e4262ca07f79ce2727aeadc408369216859d429"
)
_CPU_FEATURES_TRUE: Final = (
    "AVX", "AVX2", "BMI", "BMI2", "CX16", "F16C", "FMA3", "LAHF",
    "LZCNT", "MMX", "MOVBE", "POPCNT", "SSE", "SSE2", "SSE3",
    "SSE41", "SSE42", "SSSE3", "X86_V2", "X86_V3",
)
_EXPECTED_CONTRACT_SHA256: Final = (
    "01f62c080451f6d090da782c47474e86ae8302a1a57df698d2df16fb5dcffac7"
)

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
    "selection_execution_authority",
)


class CorpusRetrievalV2ImplementationContractError(ValueError):
    """The public comparator implementation differs from its frozen identity."""


def _fail(message: str) -> None:
    raise CorpusRetrievalV2ImplementationContractError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str
) -> None:
    if set(value) != expected:
        _fail(f"{label} fields differ")


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise CorpusRetrievalV2ImplementationContractError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as exc:
        raise CorpusRetrievalV2ImplementationContractError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _require_sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _content_identity(path: Path, *, label: str) -> tuple[int, str]:
    digest = sha256()
    byte_count = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                byte_count += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise CorpusRetrievalV2ImplementationContractError(
            f"{label} cannot be read"
        ) from exc
    return byte_count, digest.hexdigest()


def _source_module_evidence() -> tuple[dict[str, object], str]:
    raw_path = getattr(engine, "__file__", None)
    if type(raw_path) is not str or not raw_path:
        _fail("retrieval engine has no source-bearing module path")
    path = Path(raw_path).resolve()
    if path.suffix != ".py" or path.name != SOURCE_FILE_NAME:
        _fail("retrieval implementation contract requires the .py source file")
    byte_count, source_hash = _content_identity(
        path, label="retrieval engine source"
    )
    return (
        {
            "logical_module_id": SOURCE_MODULE_LOGICAL_ID,
            "source_file_name": SOURCE_FILE_NAME,
            "source_encoding": "utf-8",
            "source_bytes": byte_count,
            "whole_source_sha256": source_hash,
        },
        str(path),
    )


def _callable_source_evidence(
    source_path: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    expected_path = Path(source_path).resolve()
    for ordinal, name in enumerate(_CALLABLE_ORDER):
        value = getattr(engine, name, None)
        if not callable(value):
            _fail(f"retrieval engine callable {name} is absent")
        callable_path = inspect.getsourcefile(value)
        if callable_path is None or Path(callable_path).resolve() != expected_path:
            _fail(f"retrieval engine callable {name} is not source-bound")
        try:
            source = inspect.getsource(value).encode("utf-8")
        except (OSError, TypeError) as exc:
            raise CorpusRetrievalV2ImplementationContractError(
                f"retrieval engine callable {name} source is unavailable"
            ) from exc
        rows.append(
            {
                "ordinal": ordinal,
                "callable_name": name,
                "callable_logical_id": f"{SOURCE_MODULE_LOGICAL_ID}:{name}",
                "source_bytes": len(source),
                "source_sha256": sha256(source).hexdigest(),
            }
        )
    return rows


def _registry_evidence() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    try:
        registry = engine.frozen_retrieval_strategies_v2(ENTRY_BUDGET)
    except Exception as exc:  # pragma: no cover - normalized fail-closed seam
        raise CorpusRetrievalV2ImplementationContractError(
            "imported public v2 strategy registry cannot be resolved"
        ) from exc
    if not isinstance(registry, list):
        _fail("imported public v2 strategy registry is not an array")
    normalized = deepcopy(registry)
    pointers: list[dict[str, object]] = []
    for ordinal, raw in enumerate(normalized):
        strategy = _mapping(raw, label=f"strategy[{ordinal}]")
        retained_hash = _require_sha256(
            strategy.get("strategy_sha256"),
            label=f"strategy[{ordinal}] hash",
        )
        remainder = {
            key: value
            for key, value in strategy.items()
            if key != "strategy_sha256"
        }
        if (
            strategy.get("ordinal") != ordinal
            or _sha(remainder, label=f"strategy[{ordinal}]") != retained_hash
        ):
            _fail(f"strategy[{ordinal}] self-identity or order differs")
        pointers.append(
            {
                "ordinal": ordinal,
                "strategy_id": strategy.get("strategy_id"),
                "method": strategy.get("method"),
                "strategy_sha256": retained_hash,
            }
        )
    return normalized, pointers


def _runtime_evidence() -> tuple[dict[str, object], dict[str, str]]:
    python_path = Path(sys.executable).resolve()
    numpy_core_path = Path(np._core._multiarray_umath.__file__).resolve()
    python_bytes, python_hash = _content_identity(
        python_path, label="Python executable"
    )
    numpy_bytes, numpy_hash = _content_identity(
        numpy_core_path, label="NumPy core binary"
    )
    try:
        cpu_features = tuple(
            sorted(
                key
                for key, enabled in np._core._multiarray_umath.__cpu_features__.items()
                if enabled
            )
        )
    except AttributeError as exc:
        raise CorpusRetrievalV2ImplementationContractError(
            "NumPy CPU feature evidence is unavailable"
        ) from exc
    version = sys.version_info
    runtime = {
        "python_implementation": platform.python_implementation(),
        "python_version": f"{version.major}.{version.minor}.{version.micro}",
        "python_executable_bytes": python_bytes,
        "python_executable_sha256": python_hash,
        "numpy_version": np.__version__,
        "numpy_core_binary_bytes": numpy_bytes,
        "numpy_core_binary_sha256": numpy_hash,
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "byteorder": sys.byteorder,
        "dtype_float32": np.dtype(np.float32).str,
        "dtype_float64": np.dtype(np.float64).str,
        "dtype_int64": np.dtype(np.int64).str,
        "dtype_bool": np.dtype(np.bool_).str,
        "numpy_error_policy": dict(np.geterr()),
        "numpy_cpu_features_true": list(cpu_features),
    }
    return runtime, {
        "absolute_python_executable_path": str(python_path),
        "absolute_numpy_core_binary_path": str(numpy_core_path),
    }


def _guard_current_engine(
    *,
    source: Mapping[str, object],
    callables: Sequence[Mapping[str, object]],
    registry: Sequence[Mapping[str, object]],
    pointers: Sequence[Mapping[str, object]],
    runtime: Mapping[str, object],
) -> None:
    if (
        source
        != {
            "logical_module_id": SOURCE_MODULE_LOGICAL_ID,
            "source_file_name": SOURCE_FILE_NAME,
            "source_encoding": "utf-8",
            "source_bytes": SOURCE_FILE_BYTES,
            "whole_source_sha256": SOURCE_FILE_SHA256,
        }
        or _sha(registry, label="public v2 registry") != _REGISTRY_SHA256
        or _sha(pointers, label="public v2 registry pointers")
        != _REGISTRY_POINTERS_SHA256
        or [row.get("strategy_id") for row in pointers]
        != list(_STRATEGY_HASHES)
        or {
            str(row.get("strategy_id")): row.get("strategy_sha256")
            for row in pointers
        }
        != _STRATEGY_HASHES
    ):
        _fail("public v2 source or strategy registry drifted")
    observed_callables = {
        str(row.get("callable_name")): (
            row.get("source_bytes"),
            row.get("source_sha256"),
        )
        for row in callables
    }
    if (
        tuple(observed_callables) != _CALLABLE_ORDER
        or observed_callables != _CALLABLE_SOURCE_IDENTITIES
    ):
        _fail("public v2 callable or dispatch source drifted")
    expected_runtime = {
        "python_implementation": _PYTHON_IMPLEMENTATION,
        "python_version": _PYTHON_VERSION,
        "python_executable_bytes": _PYTHON_EXECUTABLE_BYTES,
        "python_executable_sha256": _PYTHON_EXECUTABLE_SHA256,
        "numpy_version": _NUMPY_VERSION,
        "numpy_core_binary_bytes": _NUMPY_CORE_BYTES,
        "numpy_core_binary_sha256": _NUMPY_CORE_SHA256,
        "platform_system": "Linux",
        "platform_machine": "x86_64",
        "byteorder": "little",
        "dtype_float32": "<f4",
        "dtype_float64": "<f8",
        "dtype_int64": "<i8",
        "dtype_bool": "|b1",
        "numpy_error_policy": {
            "divide": "warn",
            "over": "warn",
            "under": "ignore",
            "invalid": "warn",
        },
        "numpy_cpu_features_true": list(_CPU_FEATURES_TRUE),
    }
    if runtime != expected_runtime:
        _fail("public v2 numerical runtime identity drifted")
    if (
        engine.DEFAULT_ENTRY_BUDGET != ENTRY_BUDGET
        or engine.PRIMARY_EVENT_THRESHOLD != PRIMARY_EVENT_THRESHOLD
        or engine.PRIMARY_EVENT_OPERATOR != PRIMARY_EVENT_OPERATOR
        or engine.WORLDS_PER_BLOCK != WORLDS_PER_BLOCK
        or tuple(engine.WORLD_BLOCKS) != WORLD_BLOCKS
        or tuple(engine.DISCOVERY_BLOCKS) != DISCOVERY_BLOCKS
        or tuple(engine.HELDOUT_BLOCKS) != HELDOUT_BLOCKS
    ):
        _fail("public v2 threshold, budget, or block constants drifted")


def _contract_identity_from_current() -> tuple[dict[str, object], dict[str, object]]:
    source, source_path = _source_module_evidence()
    callables = _callable_source_evidence(source_path)
    registry, pointers = _registry_evidence()
    runtime, runtime_paths = _runtime_evidence()
    _guard_current_engine(
        source=source,
        callables=callables,
        registry=registry,
        pointers=pointers,
        runtime=runtime,
    )
    callable_by_name = {
        str(row["callable_name"]): row for row in callables
    }
    method_mapping = [
        {
            **deepcopy(row),
            "callable_source_sha256": callable_by_name[str(row["callable"])][
                "source_sha256"
            ],
        }
        for row in _METHOD_TO_CALLABLE
    ]
    identity = {
        "schema_version": CONTRACT_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "source_module": source,
        "strategy_registry": registry,
        "strategy_registry_sha256": _sha(
            registry, label="public v2 strategy registry"
        ),
        "strategy_registry_pointers": pointers,
        "strategy_registry_pointers_sha256": _sha(
            pointers, label="public v2 strategy pointers"
        ),
        "strategy_count": 7,
        "canonical_registry_order": [
            str(row["strategy_id"]) for row in pointers
        ],
        "method_to_callable": method_mapping,
        "method_to_callable_sha256": _sha(
            method_mapping, label="method-to-callable mapping"
        ),
        "callable_sources": callables,
        "callable_sources_sha256": _sha(
            callables, label="public v2 callable sources"
        ),
        "dispatch_sources": {
            "strategy_dispatch_callable": "_run_strategy",
            "strategy_dispatch_source_sha256": callable_by_name[
                "_run_strategy"
            ]["source_sha256"],
            "heldout_safe_dispatch_callable": "_run_discovery_strategy",
            "heldout_safe_dispatch_source_sha256": callable_by_name[
                "_run_discovery_strategy"
            ]["source_sha256"],
        },
        "execution_laws": {
            "entry_budget": ENTRY_BUDGET,
            "exact_budget_required": True,
            "candidate_minimum": ENTRY_BUDGET,
            "world_blocks": list(WORLD_BLOCKS),
            "discovery_blocks": list(DISCOVERY_BLOCKS),
            "heldout_blocks": list(HELDOUT_BLOCKS),
            "worlds_per_block": WORLDS_PER_BLOCK,
            "selection_world_count": len(DISCOVERY_BLOCKS) * WORLDS_PER_BLOCK,
            "heldout_content_used_for_selection": False,
            "source_score_dtype": "<f4",
            "threshold_cast_dtype": "float32",
            "mean_and_expected_max_accumulator_dtype": "float64",
            "event_and_utility_count_dtype": "int64",
            "boolean_event_mask_dtype": "bool",
            "primary_event": {
                "threshold": PRIMARY_EVENT_THRESHOLD,
                "operator": PRIMARY_EVENT_OPERATOR,
            },
            "coverage_194_event": {"threshold": 194.0, "operator": ">="},
            "ladder_rungs": [
                {"threshold": 200.0, "operator": ">", "weight": 1},
                {"threshold": 210.0, "operator": ">", "weight": 4},
                {"threshold": 220.0, "operator": ">", "weight": 12},
            ],
            "block_supported_scaling": "distinct-discovery-block-count",
            "block_shape_law": (
                "whole-10000-world-blocks-with-at-least-two-blocks"
            ),
            "coverage_zero_gain_law": (
                "fill-by-individual-count-mean-lineup-id-to-exact-budget"
            ),
            "canonical_tie_source": "strategy-registry-tie-law",
            "lineup_id_final_tie_order": "ascending",
        },
        "runtime_identity": runtime,
        "packed_preweek_overlap": {
            "strategy_id": "coverage-194-v1",
            "public_dense_implementation_still_bound_here": True,
            "six_additionally_protected_strategy_ids": [
                str(row["strategy_id"]) for row in pointers[1:]
            ],
        },
        "evidence_role": "implementation-identity-only-nonpublication",
        "absolute_paths_are_diagnostic_only": True,
        **_false_authorities(),
    }
    diagnostics = {
        "absolute_source_path": source_path,
        **runtime_paths,
        "excluded_from_implementation_contract_sha256": True,
    }
    return identity, diagnostics


def frozen_retrieval_v2_implementation_contract_v1() -> dict[str, object]:
    """Return the exact source/runtime-bound public comparator contract."""
    identity, diagnostics = _contract_identity_from_current()
    retained_hash = _sha(identity, label="retrieval v2 implementation identity")
    if retained_hash != _EXPECTED_CONTRACT_SHA256:
        _fail("public v2 implementation identity drifted")
    return {
        "contract_identity": identity,
        "implementation_contract_sha256": retained_hash,
        "diagnostics": diagnostics,
    }


def validate_retrieval_v2_implementation_contract_v1(
    value: object,
) -> dict[str, object]:
    """Validate identity exactly while allowing a different absolute path."""
    item = _mapping(value, label="retrieval v2 implementation contract")
    _exact_keys(
        item,
        {
            "contract_identity",
            "implementation_contract_sha256",
            "diagnostics",
        },
        label="retrieval v2 implementation contract",
    )
    identity = _mapping(item.get("contract_identity"), label="contract identity")
    retained_hash = _require_sha256(
        item.get("implementation_contract_sha256"),
        label="implementation contract hash",
    )
    if _sha(identity, label="retained implementation identity") != retained_hash:
        _fail("retrieval v2 implementation contract self-hash differs")
    diagnostics = _mapping(item.get("diagnostics"), label="contract diagnostics")
    _exact_keys(
        diagnostics,
        {
            "absolute_source_path",
            "absolute_python_executable_path",
            "absolute_numpy_core_binary_path",
            "excluded_from_implementation_contract_sha256",
        },
        label="contract diagnostics",
    )
    if (
        any(
            type(diagnostics.get(field)) is not str
            or not diagnostics.get(field)
            for field in (
                "absolute_source_path",
                "absolute_python_executable_path",
                "absolute_numpy_core_binary_path",
            )
        )
        or diagnostics.get("excluded_from_implementation_contract_sha256")
        is not True
    ):
        _fail("retrieval v2 diagnostic paths differ")
    expected = frozen_retrieval_v2_implementation_contract_v1()
    if _canonical(identity, label="retained contract identity") != _canonical(
        expected["contract_identity"], label="current contract identity"
    ):
        _fail("retrieval v2 implementation identity differs from canonical replay")
    return expected


__all__ = [
    "CONTRACT_SCHEMA",
    "CorpusRetrievalV2ImplementationContractError",
    "IMPLEMENTATION_ID",
    "frozen_retrieval_v2_implementation_contract_v1",
    "validate_retrieval_v2_implementation_contract_v1",
]
