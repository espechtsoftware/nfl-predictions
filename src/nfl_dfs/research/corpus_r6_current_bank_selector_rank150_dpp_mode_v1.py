"""Authority and process mode for exact rank-150 plus DPP selectors.

The grouped selector successor is an exact 24-cell/fold experiment: eight
frozen broad views times three rank-80 selectors.  This module is a distinct
32-cell/fold mode.  For every same frozen broad view it executes the three
native ranking laws to an exact depth of 150 and one quality-weighted DPP
ranking to an exact depth of 150.  Every cell exposes literal nested
80/100/150 books.

This module deliberately reuses the current-bank matrix capability, sampling
authority, score-row ledger, pure selector implementations and successor
held-out prefix contract.  It does not reuse or impersonate the grouped
24-fit runtime, process budget, authority response, fold receipt or slate
result.  It performs no object-store I/O and reads no held-out or realized
outcome.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import re
import sys
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as source_authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as source_adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_runtime_v1 as source_runtime,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)


MODE_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-process-mode/v1"
)
MODE_ID: Final = "rank150-three-native-plus-effective-shots-dpp-v1"
RUNTIME_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-observed-runtime/v1"
)
RUNTIME_MODE: Final = "rank150-dpp-matrix-selector"
PROCESS_BUDGET_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-process-budget/v1"
)
MATRIX_CHILD_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-matrix-child-request/v1"
)
AUTHORITY_RESPONSE_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-authority-response/v1"
)
AUTHORITY_CELL_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-authority-cell/v1"
)
FOLD_RECEIPT_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-fold-receipt/v1"
)
SLATE_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-rank150-dpp-slate-result/v1"
)
SELECTOR_COORDINATE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-coordinate/v1"
)
PROCESS_ROLE: Final = "rank150-dpp-broad-fold-selector"
ENTRYPOINT_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_current_bank_selector_rank150_dpp_v1.py"
)
ENTRYPOINT_IMAGE_PATH: Final = f"/app/{ENTRYPOINT_RELATIVE_PATH}"
PYTHON_EXECUTABLE: Final = source_runtime.PYTHON_EXECUTABLE
PROCESS_ORDINAL_ENV: Final = "R6_RANK150_DPP_PROCESS_ORDINAL"

EXACT_VIEW_COUNT: Final = source_authority.EXACT_BROAD_VIEW_COUNT
EXACT_SELECTORS_PER_VIEW: Final = 4
EXACT_FIT_COUNT: Final = EXACT_VIEW_COUNT * EXACT_SELECTORS_PER_VIEW
EXACT_FOLDS_PER_SLATE: Final = contract.FOLDS_PER_SLATE
EXACT_FITS_PER_SLATE: Final = EXACT_FIT_COUNT * EXACT_FOLDS_PER_SLATE
ENTRY_BUDGETS: Final = rank150.ENTRY_BUDGETS
RANKING_DEPTH: Final = rank150.RANKING_DEPTH
MAX_BYTES_PER_CELL: Final = 4_000_000
FOLD_RECEIPT_BYTE_CEILING: Final = 160_000_000

_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_FALSE_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "heldout_score_columns_present": False,
    "heldout_artifact_identity_present": False,
    "corpus_regeneration_performed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "publication_authority": False,
    "promotion_authority": False,
    "decision_authority": False,
}


class CorpusR6CurrentBankSelectorRank150DppModeV1Error(ValueError):
    """The distinct 32-fit mode failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} cannot already be present")
    body[field] = _hash(body)
    return body


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    if value.get(field) != _hash({
        key: row for key, row in value.items() if key != field
    }):
        _fail(f"{label} self hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(str(exc)) from exc


def _bind(
    value: Mapping[str, object], identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            value, identity, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(str(exc)) from exc


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def entrypoint_source_sha256_v1() -> str:
    path = _repository_root_v1() / ENTRYPOINT_RELATIVE_PATH
    if not path.is_file():
        _fail("rank150/DPP matrix-child entrypoint is absent")
    return sha256(path.read_bytes()).hexdigest()


def canonical_matrix_selector_command_v1() -> list[str]:
    return [PYTHON_EXECUTABLE, ENTRYPOINT_IMAGE_PATH, "matrix-selector"]


def build_process_mode_v1() -> dict[str, object]:
    """Return the exact cloud/process descriptor for consolidated images."""
    rank_implementation = rank150.frozen_rank150_implementation_v1()
    diversity_contract = diversity.frozen_diversity_selector_contract_v1()
    return _with_hash({
        "schema_version": MODE_SCHEMA,
        "mode_id": MODE_ID,
        "process_role": PROCESS_ROLE,
        "runtime_schema": RUNTIME_SCHEMA,
        "runtime_mode": RUNTIME_MODE,
        "entrypoint_path": ENTRYPOINT_IMAGE_PATH,
        "entrypoint_sha256": entrypoint_source_sha256_v1(),
        "command": canonical_matrix_selector_command_v1(),
        "view_count_per_fold": EXACT_VIEW_COUNT,
        "selector_count_per_view": EXACT_SELECTORS_PER_VIEW,
        "fit_count_per_fold": EXACT_FIT_COUNT,
        "fold_count_per_slate": EXACT_FOLDS_PER_SLATE,
        "fit_count_per_slate": EXACT_FITS_PER_SLATE,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "rank150_implementation_sha256": rank_implementation[
            "implementation_sha256"
        ],
        "diversity_contract_sha256": diversity_contract["contract_sha256"],
        "grouped_24_fit_mode_compatible": False,
        "grouped_24_fit_receipt_schema_claimed": False,
        "successor_evaluator_prefix_contract_compatible": True,
        "policy": dict(_FALSE_POLICY),
    }, field="process_mode_sha256")


def build_runtime_evidence_v1(
    *, environ: Mapping[str, str], observed_command: object,
    process_ordinal: int, pid: int, parent_pid: int,
) -> dict[str, object]:
    environment = dict(environ)
    if any(environment.get(key) for key in source_runtime._REDIRECT_ENV_KEYS):
        _fail("rank150/DPP runtime redirect environment is forbidden")
    command = [str(row) for row in _sequence(
        observed_command, label="rank150/DPP observed command"
    )]
    project_values = {
        environment[key]
        for key in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
        if environment.get(key)
    }
    commit = environment.get("CODE_SHA", "")
    image = environment.get("R6_RUNTIME_IMAGE_DIGEST", "")
    task_text = environment.get("CLOUD_RUN_TASK_INDEX", "")
    process_text = environment.get(PROCESS_ORDINAL_ENV, "")
    if (
        command != canonical_matrix_selector_command_v1()
        or project_values != {source_runtime.FIXED_GCP_PROJECT}
        or environment.get("GOOGLE_CLOUD_PROJECT")
        != source_runtime.FIXED_GCP_PROJECT
        or _COMMIT_RE.fullmatch(commit) is None
        or not image.startswith("sha256:")
        or _SHA_RE.fullmatch(image[7:]) is None
        or not task_text.isdecimal()
        or not process_text.isdecimal()
        or type(process_ordinal) is not int
        or int(process_text) != process_ordinal
        or type(pid) is not int
        or type(parent_pid) is not int
        or pid < 1
        or parent_pid < 1
        or pid == parent_pid
    ):
        _fail("rank150/DPP runtime environment/process binding differs")
    job = environment.get("CLOUD_RUN_JOB", "")
    execution = environment.get("CLOUD_RUN_EXECUTION", "")
    if not job or not execution or len(job) > 512 or len(execution) > 512:
        _fail("rank150/DPP Cloud Run job/execution binding is absent")
    entrypoint_sha = entrypoint_source_sha256_v1()
    body = {
        "schema_version": RUNTIME_SCHEMA,
        "runtime_mode": RUNTIME_MODE,
        "process_mode_sha256": build_process_mode_v1()["process_mode_sha256"],
        "project_id": source_runtime.FIXED_GCP_PROJECT,
        "storage_endpoint": source_runtime.FIXED_STORAGE_ENDPOINT,
        "code_commit": commit,
        "image_digest": image,
        "job_name": job,
        "execution_id": execution,
        "task_index": int(task_text),
        "process_ordinal": process_ordinal,
        "pid": pid,
        "parent_pid": parent_pid,
        "python_executable": PYTHON_EXECUTABLE,
        "python_version": sys.version.split()[0],
        "entrypoint_path": ENTRYPOINT_IMAGE_PATH,
        "entrypoint_sha256": entrypoint_sha,
        "command": command,
        "command_sha256": _hash({
            "command": command, "entrypoint_sha256": entrypoint_sha
        }),
        "redirect_environment_present": False,
        "outer_launch_authority_binding_required": True,
        "grouped_24_fit_runtime_compatibility_claimed": False,
    }
    return _with_hash(body, field="runtime_evidence_sha256")


def validate_runtime_evidence_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="rank150/DPP runtime evidence")
    _self_hash(item, field="runtime_evidence_sha256", label="runtime evidence")
    command = canonical_matrix_selector_command_v1()
    if (
        item.get("schema_version") != RUNTIME_SCHEMA
        or item.get("runtime_mode") != RUNTIME_MODE
        or item.get("process_mode_sha256")
        != build_process_mode_v1()["process_mode_sha256"]
        or item.get("project_id") != source_runtime.FIXED_GCP_PROJECT
        or item.get("storage_endpoint") != source_runtime.FIXED_STORAGE_ENDPOINT
        or _COMMIT_RE.fullmatch(str(item.get("code_commit", ""))) is None
        or not str(item.get("image_digest", "")).startswith("sha256:")
        or _SHA_RE.fullmatch(str(item.get("image_digest", ""))[7:]) is None
        or item.get("entrypoint_path") != ENTRYPOINT_IMAGE_PATH
        or item.get("entrypoint_sha256") != entrypoint_source_sha256_v1()
        or item.get("command") != command
        or item.get("command_sha256") != _hash({
            "command": command,
            "entrypoint_sha256": entrypoint_source_sha256_v1(),
        })
        or item.get("redirect_environment_present") is not False
        or item.get("outer_launch_authority_binding_required") is not True
        or item.get("grouped_24_fit_runtime_compatibility_claimed") is not False
    ):
        _fail("rank150/DPP runtime fixed binding differs")
    for field in ("task_index", "process_ordinal", "pid", "parent_pid"):
        if type(item.get(field)) is not int or int(item[field]) < 0:
            _fail(f"rank150/DPP runtime {field} differs")
    if item["pid"] < 1 or item["parent_pid"] < 1 or item["pid"] == item["parent_pid"]:
        _fail("rank150/DPP runtime process identity differs")
    for field in ("job_name", "execution_id", "python_version"):
        if type(item.get(field)) is not str or not item[field]:
            _fail(f"rank150/DPP runtime {field} differs")
    return item


def derive_current_process_runtime_evidence_v1(
    *, process_ordinal: int,
) -> dict[str, object]:
    return build_runtime_evidence_v1(
        environ=os.environ,
        observed_command=canonical_matrix_selector_command_v1(),
        process_ordinal=process_ordinal,
        pid=os.getpid(),
        parent_pid=os.getppid(),
    )


def _validated_scientific_authorities_v1(
    *, matrix_capability: object, training_score_matrix: object,
    runtime_evidence: object,
) -> tuple[
    dict[str, object], dict[str, object], np.ndarray, list[str],
    list[dict[str, object]], list[str], dict[str, object], dict[str, object],
]:
    try:
        capability = worker.validate_matrix_capability_v1(matrix_capability)
    except worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(str(exc)) from exc
    if capability["phase"] != contract.BROAD_SCREEN_PHASE:
        _fail("rank150/DPP mode accepts only the frozen broad sample authority")
    projection = _mapping(
        capability["projection_scientific_binding"], label="projection binding"
    )
    training_blocks = [str(row) for row in projection["training_blocks"]]
    try:
        lineup_ids, candidates = source_authority._validate_candidate_authority_v1(
            projection, training_blocks=training_blocks
        )
        samples = source_authority._validate_sample_authority_v1(
            capability, projection=projection
        )
        scores, ledger = source_authority._validate_matrix_authority_v1(
            training_score_matrix,
            projection=projection,
            descriptor=_mapping(
                capability["matrix_descriptor"], label="matrix descriptor"
            ),
        )
    except source_authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(str(exc)) from exc
    runtime = validate_runtime_evidence_v1(runtime_evidence)
    if (
        runtime["process_ordinal"] != capability["process_ordinal"]
        or runtime["task_index"] != capability["source_ordinal"]
    ):
        _fail("rank150/DPP runtime/capability coordinate differs")
    return (
        capability, runtime, scores, lineup_ids, candidates, training_blocks,
        samples, ledger,
    )


def _prefixes_v1(
    *, selected_ids: Sequence[str],
    candidate_by_id: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rosters = [
        list(candidate_by_id[lineup_id]["roster_player_ids"])
        for lineup_id in selected_ids
    ]
    rows: list[dict[str, object]] = []
    for size in ENTRY_BUDGETS:
        ids = list(selected_ids[:size])
        prefix_rosters = rosters[:size]
        rows.append({
            "prefix_size": size,
            "selected_lineup_ids_sha256": _hash(ids),
            "selected_rosters_sha256": _hash(prefix_rosters),
            "prefix_payload_sha256": _hash({
                "selected_lineup_ids": ids,
                "selected_rosters": prefix_rosters,
            }),
        })
    return rows


def _selector_coordinate_v1(
    *, ordinal: int, selector_family_id: str, selector_id: str,
    selector_semantics_sha256: str, adapter_id: str,
    executable_fingerprint_sha256: str,
) -> dict[str, object]:
    for label, digest in (
        ("selector semantics", selector_semantics_sha256),
        ("selector executable", executable_fingerprint_sha256),
    ):
        if _SHA_RE.fullmatch(digest) is None:
            _fail(f"{label} is not lowercase SHA-256")
    return _with_hash({
        "schema_version": SELECTOR_COORDINATE_SCHEMA,
        "selector_family_id": selector_family_id,
        "selector_ordinal": ordinal,
        "selector_id": selector_id,
        "selector_semantics_sha256": selector_semantics_sha256,
        "adapter_id": adapter_id,
        "executable_fingerprint_sha256": executable_fingerprint_sha256,
    }, field="selector_coordinate_sha256")


def _authority_cell_v1(
    *, view_ordinal: int, sample: Mapping[str, object],
    selected_ids: Sequence[str], selector_coordinate: Mapping[str, object],
    source_result_schema: str, source_result_sha256: str,
    source_selector_result_sha256: str, sampled_ledger: Mapping[str, object],
    candidate_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    retained = list(selected_ids)
    if len(retained) != RANKING_DEPTH or len(set(retained)) != RANKING_DEPTH:
        _fail("rank150/DPP authority cell is not one exact ranked 150")
    rosters = [
        list(candidate_by_id[lineup_id]["roster_player_ids"])
        for lineup_id in retained
    ]
    sampled = [str(row) for row in sample["sampled_lineup_ids"]]
    row_hash_by_id = {
        str(row["lineup_id"]): str(row["score_row_sha256"])
        for row in sampled_ledger["rows"]
    }
    ordinal_by_id = {
        lineup_id: ordinal for ordinal, lineup_id in enumerate(sampled)
    }
    if not set(retained) <= set(sampled) or set(row_hash_by_id) != set(sampled):
        _fail("rank150/DPP selection trace inputs differ")
    trace = [
        {
            "selection_ordinal": ordinal,
            "lineup_id": lineup_id,
            "sampled_lineup_ordinal": ordinal_by_id[lineup_id],
            "score_row_sha256": row_hash_by_id[lineup_id],
        }
        for ordinal, lineup_id in enumerate(retained)
    ]
    coordinate = dict(selector_coordinate)
    body = {
        "schema_version": AUTHORITY_CELL_SCHEMA,
        "replicate": 0,
        "view_ordinal": view_ordinal,
        "view_id": sample["view_id"],
        "sampled_lineup_ids": list(sample["sampled_lineup_ids"]),
        "sampled_lineup_ids_sha256": sample["sampled_lineup_ids_sha256"],
        "rank_seed_sha256": sample["seed_material_sha256"],
        "selector_coordinate": coordinate,
        "selector_coordinate_sha256": coordinate[
            "selector_coordinate_sha256"
        ],
        "source_result_schema": source_result_schema,
        "source_result_sha256": source_result_sha256,
        "source_selector_result_sha256": source_selector_result_sha256,
        "training_score_row_ledger": dict(sampled_ledger),
        "training_score_row_ledger_sha256": _hash(sampled_ledger),
        "selected_lineup_ids": retained,
        "selected_lineup_ids_sha256": _hash(retained),
        "selected_rosters_sha256": _hash(rosters),
        "prefixes": _prefixes_v1(
            selected_ids=retained, candidate_by_id=candidate_by_id
        ),
        "selection_trace": trace,
        "selection_trace_sha256": _hash(trace),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
    }
    return _with_hash(body, field="authority_cell_sha256")


def run_authority_bound_rank150_dpp_v1(
    *, matrix_capability: object, training_score_matrix: object,
    runtime_evidence: object,
) -> dict[str, object]:
    """Execute exactly 32 fit cells for one authenticated slate/fold."""
    (
        capability, runtime, scores, lineup_ids, candidates, training_blocks,
        samples, full_ledger,
    ) = _validated_scientific_authorities_v1(
        matrix_capability=matrix_capability,
        training_score_matrix=training_score_matrix,
        runtime_evidence=runtime_evidence,
    )
    presets = successor.frozen_native_preset_registry_v1()
    matrix_ordinal = {
        lineup_id: index for index, lineup_id in enumerate(lineup_ids)
    }
    candidate_by_id = {
        str(row["lineup_id"]): row for row in candidates
    }
    cells: list[dict[str, object]] = []
    view_receipts: list[dict[str, object]] = []
    for view_ordinal, raw_sample in enumerate(
        samples["replicates"][0]["views"]
    ):
        sample = _mapping(raw_sample, label=f"broad sample[{view_ordinal}]")
        sampled_ids = [str(row) for row in sample["sampled_lineup_ids"]]
        if len(sampled_ids) < RANKING_DEPTH:
            _fail("rank150/DPP broad view contains fewer than 150 candidates")
        sampled_candidates = [candidate_by_id[lineup_id] for lineup_id in sampled_ids]
        row_ordinals = np.asarray(
            [matrix_ordinal[lineup_id] for lineup_id in sampled_ids],
            dtype=np.int64,
        )
        sampled_scores = np.empty(
            (len(sampled_ids), scores.shape[1]), dtype=np.float64, order="C"
        )
        np.take(scores, row_ordinals, axis=0, out=sampled_scores)
        sampled_scores.flags.writeable = False
        try:
            rank_result = rank150.run_exact_rank150_continuation_v1(
                sampled_lineup_ids=sampled_ids,
                training_score_matrix=sampled_scores,
                candidate_rows=sampled_candidates,
                training_blocks=training_blocks,
                worlds_per_block=source_authority.EXACT_WORLDS_PER_BLOCK,
                preset_registry=presets,
            )
            dpp_result = diversity.run_effective_independent_shots_selector_v1(
                sampled_lineup_ids=sampled_ids,
                training_score_matrix=sampled_scores,
                candidate_rows=sampled_candidates,
                training_blocks=training_blocks,
                worlds_per_block=source_authority.EXACT_WORLDS_PER_BLOCK,
            )
        except (
            rank150.CorpusR6CurrentBankSelectorRank150V1Error,
            diversity.CorpusR6CurrentBankDiversitySelectorV1Error,
        ) as exc:
            raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(
                f"rank150/DPP selector execution failed: {exc}"
            ) from exc
        expected_matrix_sha = successor._matrix_sha(sampled_scores)
        expected_candidate_sha = _hash(sampled_candidates)
        expected_lineup_sha = _hash(sampled_ids)
        rank_input = _mapping(
            rank_result.get("input_binding"), label="rank150 input binding"
        )
        dpp_input = _mapping(
            dpp_result.get("input_binding"), label="DPP input binding"
        )
        if (
            rank_result.get("schema_version") != rank150.RESULT_SCHEMA
            or rank_result.get("result_sha256") != _hash({
                key: row for key, row in rank_result.items()
                if key != "result_sha256"
            })
            or rank_input.get("ordered_sampled_lineup_ids_sha256")
            != expected_lineup_sha
            or rank_input.get("sampled_candidate_rows_sha256")
            != expected_candidate_sha
            or rank_input.get("training_score_matrix_sha256")
            != expected_matrix_sha
            or rank_result.get("selector_count") != 3
            or len(rank_result.get("selectors", [])) != 3
            or rank_result.get("entry_budgets") != list(ENTRY_BUDGETS)
            or rank_result.get("ranking_depth") != RANKING_DEPTH
            or dpp_result.get("schema_version") != diversity.RESULT_SCHEMA
            or dpp_result.get("result_sha256") != _hash({
                key: row for key, row in dpp_result.items()
                if key != "result_sha256"
            })
            or dpp_input.get("ordered_sampled_lineup_ids_sha256")
            != expected_lineup_sha
            or dpp_input.get("sampled_candidate_rows_sha256")
            != expected_candidate_sha
            or dpp_input.get("training_score_matrix_sha256")
            != expected_matrix_sha
            or dpp_result.get("entry_budget") != RANKING_DEPTH
            or dpp_result.get("prefix_sizes") != list(ENTRY_BUDGETS)
        ):
            _fail("rank150/DPP pure result input/output binding differs")
        try:
            sampled_ledger = contract._sampled_score_row_ledger_from_full_v1(
                full_ledger, sampled_ids
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(str(exc)) from exc

        view_cells: list[dict[str, object]] = []
        for selector in rank_result["selectors"]:
            preset = presets[int(selector["ordinal"])]
            semantics = _hash({
                "rank150_implementation_sha256": rank_result[
                    "implementation_sha256"
                ],
                "preset_sha256": preset["preset_sha256"],
            })
            executable = _hash({
                "mode_id": MODE_ID,
                "rank150_implementation_sha256": rank_result[
                    "implementation_sha256"
                ],
                "base_executable_fingerprint_sha256": preset[
                    "executable_fingerprint_sha256"
                ],
            })
            coordinate = _selector_coordinate_v1(
                ordinal=int(selector["ordinal"]),
                selector_family_id="exact-rank150-current-bank-selectors-v1",
                selector_id=str(selector["preset_id"]),
                selector_semantics_sha256=semantics,
                adapter_id=f"{selector['adapter_id']}-rank150",
                executable_fingerprint_sha256=executable,
            )
            view_cells.append(_authority_cell_v1(
                view_ordinal=view_ordinal,
                sample=sample,
                selected_ids=selector["ranked_lineup_ids"],
                selector_coordinate=coordinate,
                source_result_schema=rank150.RESULT_SCHEMA,
                source_result_sha256=str(rank_result["result_sha256"]),
                source_selector_result_sha256=str(
                    selector["selector_result_sha256"]
                ),
                sampled_ledger=sampled_ledger,
                candidate_by_id=candidate_by_id,
            ))
        dpp_contract = dpp_result["strategy_contract"]
        dpp_coordinate = _selector_coordinate_v1(
            ordinal=3,
            selector_family_id="effective-independent-tail-shots-v1",
            selector_id=str(dpp_contract["strategy_id"]),
            selector_semantics_sha256=str(dpp_contract["contract_sha256"]),
            adapter_id="quality-weighted-greedy-dpp-rank150-v1",
            executable_fingerprint_sha256=_hash({
                "mode_id": MODE_ID,
                "contract_sha256": dpp_contract["contract_sha256"],
                "ranking_depth": RANKING_DEPTH,
            }),
        )
        view_cells.append(_authority_cell_v1(
            view_ordinal=view_ordinal,
            sample=sample,
            selected_ids=dpp_result["selected_lineup_ids"],
            selector_coordinate=dpp_coordinate,
            source_result_schema=diversity.RESULT_SCHEMA,
            source_result_sha256=str(dpp_result["result_sha256"]),
            source_selector_result_sha256=str(dpp_result["result_sha256"]),
            sampled_ledger=sampled_ledger,
            candidate_by_id=candidate_by_id,
        ))
        if len(view_cells) != EXACT_SELECTORS_PER_VIEW:
            _fail("rank150/DPP view selector lattice differs")
        cells.extend(view_cells)
        view_receipts.append(_with_hash({
            "view_ordinal": view_ordinal,
            "view_id": sample["view_id"],
            "sampled_lineup_ids_sha256": sample[
                "sampled_lineup_ids_sha256"
            ],
            "sampled_score_matrix_shape": list(sampled_scores.shape),
            "sampled_score_matrix_sha256": contract._float64_matrix_sha256_v1(
                sampled_scores, label="rank150/DPP sampled matrix"
            ),
            "sampled_matrix_copy_count": 1,
            "rank150_grouped_invocation_count": 1,
            "dpp_invocation_count": 1,
            "fit_count": EXACT_SELECTORS_PER_VIEW,
            "rank150_result_sha256": rank_result["result_sha256"],
            "dpp_result_sha256": dpp_result["result_sha256"],
            "cell_sha256s": [row["authority_cell_sha256"] for row in view_cells],
        }, field="view_receipt_sha256"))
        del sampled_scores

    if len(cells) != EXACT_FIT_COUNT or len(view_receipts) != EXACT_VIEW_COUNT:
        _fail("rank150/DPP exact 32-cell lattice differs")
    projection = capability["projection_scientific_binding"]
    binding = _with_hash({
        "matrix_capability_sha256": capability["matrix_capability_sha256"],
        "projection_sha256": projection["projection_sha256"],
        "candidate_lineup_order_sha256": projection[
            "candidate_lineup_order_sha256"
        ],
        "candidate_rosters_sha256": projection["candidate_rosters_sha256"],
        "candidate_rows_sha256": projection["candidate_rows_sha256"],
        "training_score_matrix_sha256": projection[
            "training_score_matrix_sha256"
        ],
        "samples_sha256": capability["samples_sha256"],
        "full_score_row_ledger_sha256": _hash(full_ledger),
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "process_mode_sha256": build_process_mode_v1()[
            "process_mode_sha256"
        ],
        "source_capability_fit_count_precharge": capability[
            "fit_count_precharge"
        ],
        "rank150_dpp_fit_count": EXACT_FIT_COUNT,
        "grouped_24_fit_parity_claimed": False,
    }, field="authority_binding_sha256")
    return _with_hash({
        "schema_version": AUTHORITY_RESPONSE_SCHEMA,
        "mode_id": MODE_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": capability["source_ordinal"],
        "fold_ordinal": capability["fold_ordinal"],
        "process_ordinal": capability["process_ordinal"],
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "training_blocks": list(training_blocks),
        "heldout_block": projection["heldout_block_label"],
        "worlds_per_block": source_authority.EXACT_WORLDS_PER_BLOCK,
        "process_mode": build_process_mode_v1(),
        "authority_binding": binding,
        "authority_binding_sha256": binding["authority_binding_sha256"],
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "full_candidate_score_row_ledger": full_ledger,
        "full_candidate_score_row_ledger_sha256": _hash(full_ledger),
        "view_count": EXACT_VIEW_COUNT,
        "selector_count_per_view": EXACT_SELECTORS_PER_VIEW,
        "fit_count": EXACT_FIT_COUNT,
        "views": view_receipts,
        "view_sha256s": [row["view_receipt_sha256"] for row in view_receipts],
        "cells": cells,
        "cell_sha256s": [row["authority_cell_sha256"] for row in cells],
        "policy": dict(_FALSE_POLICY),
    }, field="authority_response_sha256")


def compile_process_budget_v1(
    *, source_process_budget: object, source_process_budget_identity: object,
    matrix_capability: object | None = None, source_projection: object | None = None,
) -> dict[str, object]:
    """Replace the source 64-fit charge with the exact distinct 32 fits."""
    try:
        binding, capability = source_adapter._budget_projection_binding_v1(
            matrix_capability=matrix_capability,
            source_projection=source_projection,
        )
        source_budget = contract.validate_process_budget_v1(source_process_budget)
    except (
        source_adapter.CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error,
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
    ) as exc:
        raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(str(exc)) from exc
    source_identity = _bind(
        source_budget, source_process_budget_identity, label="source process budget"
    )
    source = int(source_budget["source_ordinal"])
    process = int(source_budget["process_ordinal"])
    fold = process - source * contract.FOLDS_PER_SLATE
    if (
        source_budget["process_role"] != "broad-fold-selector"
        or source_budget["phase"] != contract.BROAD_SCREEN_PHASE
        or fold != binding["fold_ordinal"]
        or binding["source_ordinal"] not in {None, source}
        or binding["process_ordinal"] not in {None, process}
        or int(source_budget["compute_fit_precharge"]) <= EXACT_FIT_COUNT
        or source_budget["write_object_count"] != 0
        or source_budget["write_allowlist"] != []
        or (
            capability is not None
            and capability["fit_count_precharge"]
            != source_budget["compute_fit_precharge"]
        )
    ):
        _fail("rank150/DPP source budget authority differs")
    return _with_hash({
        "schema_version": PROCESS_BUDGET_SCHEMA,
        "mode_id": MODE_ID,
        "process_role": PROCESS_ROLE,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": source,
        "fold_ordinal": fold,
        "process_ordinal": process,
        "slate_id": binding["slate_id"],
        "fit_scope_id": binding["fit_scope_id"],
        "training_blocks": binding["training_blocks"],
        "heldout_block": binding["heldout_block"],
        "source_projection_sha256": binding["projection_sha256"],
        "source_training_score_matrix_sha256": binding[
            "training_score_matrix_sha256"
        ],
        "source_control_process_budget_identity": source_identity,
        "source_control_process_budget_sha256": source_budget[
            "process_budget_sha256"
        ],
        "source_control_fit_precharge": source_budget["compute_fit_precharge"],
        "read_allowlist": list(source_budget["read_allowlist"]),
        "read_object_count": source_budget["read_object_count"],
        "read_byte_ceiling": source_budget["read_byte_ceiling"],
        "write_allowlist": [],
        "write_object_count": 0,
        "write_byte_ceiling": 0,
        "matrix_input_transport": "inherited-read-only-local-matrix",
        "matrix_response_byte_ceiling": (
            EXACT_FIT_COUNT * MAX_BYTES_PER_CELL
        ),
        "fold_receipt_byte_ceiling": FOLD_RECEIPT_BYTE_CEILING,
        "compute_fit_precharge": EXACT_FIT_COUNT,
        "view_count_precharge": EXACT_VIEW_COUNT,
        "selector_count_per_view_precharge": EXACT_SELECTORS_PER_VIEW,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "broad_only": True,
        "confirmation_supported": False,
        "grouped_24_fit_budget_compatible": False,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "current_generation_lookup_allowed": False,
        "policy": dict(_FALSE_POLICY),
    }, field="process_budget_sha256")


def validate_process_budget_v1(
    value: object, *, source_process_budget: object,
    source_process_budget_identity: object, matrix_capability: object | None = None,
    source_projection: object | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="rank150/DPP process budget")
    _self_hash(item, field="process_budget_sha256", label="process budget")
    expected = compile_process_budget_v1(
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
        source_projection=source_projection,
    )
    if _canonical(item) != _canonical(expected):
        _fail("rank150/DPP process budget differs from exact replay")
    return expected


def build_matrix_child_request_v1(
    *, source_process_budget: object, source_process_budget_identity: object,
    process_budget: object, process_budget_identity: object,
    matrix_capability: object, launch_intent_identity: object,
) -> dict[str, object]:
    body = {
        "schema_version": MATRIX_CHILD_REQUEST_SCHEMA,
        "mode_id": MODE_ID,
        "source_process_budget": _mapping(
            source_process_budget, label="source process budget"
        ),
        "source_process_budget_identity": _identity(
            source_process_budget_identity, label="source process budget"
        ),
        "process_budget": _mapping(process_budget, label="rank150/DPP budget"),
        "process_budget_identity": _identity(
            process_budget_identity, label="rank150/DPP budget"
        ),
        "matrix_capability": worker.validate_matrix_capability_v1(
            matrix_capability
        ),
        "launch_intent_identity": _identity(
            launch_intent_identity, label="launch intent"
        ),
        "object_store_client_exposed": False,
        "heldout_artifact_identity_exposed": False,
    }
    return _with_hash(body, field="child_request_sha256")


def validate_matrix_child_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="rank150/DPP matrix-child request")
    _self_hash(item, field="child_request_sha256", label="matrix-child request")
    expected = build_matrix_child_request_v1(
        source_process_budget=item.get("source_process_budget"),
        source_process_budget_identity=item.get("source_process_budget_identity"),
        process_budget=item.get("process_budget"),
        process_budget_identity=item.get("process_budget_identity"),
        matrix_capability=item.get("matrix_capability"),
        launch_intent_identity=item.get("launch_intent_identity"),
    )
    if (
        item.get("schema_version") != MATRIX_CHILD_REQUEST_SCHEMA
        or item.get("mode_id") != MODE_ID
        or item.get("object_store_client_exposed") is not False
        or item.get("heldout_artifact_identity_exposed") is not False
        or _canonical(item) != _canonical(expected)
    ):
        _fail("rank150/DPP matrix-child request differs from replay")
    return expected


def _validate_response_structure_v1(
    value: object, *, matrix_capability: Mapping[str, object],
    runtime_evidence: Mapping[str, object],
) -> dict[str, object]:
    response = _mapping(value, label="rank150/DPP authority response")
    _self_hash(
        response, field="authority_response_sha256", label="authority response"
    )
    cells = [
        _mapping(row, label=f"rank150/DPP cell[{index}]")
        for index, row in enumerate(
            _sequence(response.get("cells"), label="rank150/DPP cells")
        )
    ]
    capability = matrix_capability
    projection = capability["projection_scientific_binding"]
    runtime = validate_runtime_evidence_v1(runtime_evidence)
    if (
        response.get("schema_version") != AUTHORITY_RESPONSE_SCHEMA
        or response.get("mode_id") != MODE_ID
        or response.get("source_ordinal") != capability["source_ordinal"]
        or response.get("fold_ordinal") != capability["fold_ordinal"]
        or response.get("process_ordinal") != capability["process_ordinal"]
        or response.get("slate_id") != projection["slate_id"]
        or response.get("fit_scope_id") != projection["fit_scope_id"]
        or response.get("runtime_evidence_sha256")
        != runtime["runtime_evidence_sha256"]
        or response.get("view_count") != EXACT_VIEW_COUNT
        or response.get("selector_count_per_view")
        != EXACT_SELECTORS_PER_VIEW
        or response.get("fit_count") != EXACT_FIT_COUNT
        or len(cells) != EXACT_FIT_COUNT
        or response.get("cell_sha256s")
        != [row.get("authority_cell_sha256") for row in cells]
        or len(set(response["cell_sha256s"])) != EXACT_FIT_COUNT
    ):
        _fail("rank150/DPP authority response structure differs")
    coordinates: list[tuple[int, int]] = []
    for cell in cells:
        _self_hash(cell, field="authority_cell_sha256", label="authority cell")
        coordinate = _mapping(
            cell.get("selector_coordinate"), label="selector coordinate"
        )
        _self_hash(
            coordinate,
            field="selector_coordinate_sha256",
            label="selector coordinate",
        )
        if (
            cell.get("schema_version") != AUTHORITY_CELL_SCHEMA
            or cell.get("replicate") != 0
            or type(cell.get("view_ordinal")) is not int
            or coordinate.get("schema_version") != SELECTOR_COORDINATE_SCHEMA
            or type(coordinate.get("selector_ordinal")) is not int
            or cell.get("selector_coordinate_sha256")
            != coordinate["selector_coordinate_sha256"]
        ):
            _fail("rank150/DPP authority cell coordinate differs")
        coordinates.append((
            int(cell["view_ordinal"]), int(coordinate["selector_ordinal"])
        ))
    if sorted(coordinates) != [
        (view, selector)
        for view in range(EXACT_VIEW_COUNT)
        for selector in range(EXACT_SELECTORS_PER_VIEW)
    ]:
        _fail("rank150/DPP authority coordinate lattice differs")
    return response


def build_fold_receipt_v1(
    *, process_budget: object, process_budget_identity: object,
    source_process_budget: object, source_process_budget_identity: object,
    matrix_capability: object, runtime_evidence: object,
    authority_response: object, launch_intent_identity: object,
) -> dict[str, object]:
    budget = validate_process_budget_v1(
        process_budget,
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
    )
    budget_identity = _bind(
        budget, process_budget_identity, label="rank150/DPP process budget"
    )
    try:
        capability = worker.validate_matrix_capability_v1(matrix_capability)
    except worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150DppModeV1Error(str(exc)) from exc
    runtime = validate_runtime_evidence_v1(runtime_evidence)
    response = _validate_response_structure_v1(
        authority_response,
        matrix_capability=capability,
        runtime_evidence=runtime,
    )
    launch = _identity(launch_intent_identity, label="outer launch intent")
    if (
        budget["source_ordinal"] != capability["source_ordinal"]
        or budget["fold_ordinal"] != capability["fold_ordinal"]
        or budget["process_ordinal"] != capability["process_ordinal"]
        or runtime["process_ordinal"] != capability["process_ordinal"]
        or runtime["task_index"] != capability["source_ordinal"]
    ):
        _fail("rank150/DPP budget/runtime/capability coordinate differs")
    cells = response["cells"]
    receipt = _with_hash({
        "schema_version": FOLD_RECEIPT_SCHEMA,
        "mode_id": MODE_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": capability["source_ordinal"],
        "fold_ordinal": capability["fold_ordinal"],
        "process_ordinal": capability["process_ordinal"],
        "slate_id": budget["slate_id"],
        "fit_scope_id": budget["fit_scope_id"],
        "training_blocks": list(budget["training_blocks"]),
        "heldout_block": budget["heldout_block"],
        "process_budget_identity": budget_identity,
        "process_budget_sha256": budget["process_budget_sha256"],
        "source_control_process_budget_identity": budget[
            "source_control_process_budget_identity"
        ],
        "source_control_fit_precharge": budget[
            "source_control_fit_precharge"
        ],
        "launch_intent_identity": launch,
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "authority_response": response,
        "authority_response_sha256": response["authority_response_sha256"],
        "view_count": EXACT_VIEW_COUNT,
        "selector_count_per_view": EXACT_SELECTORS_PER_VIEW,
        "fit_count": EXACT_FIT_COUNT,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "cell_sha256s": list(response["cell_sha256s"]),
        "cells_sha256": _hash(cells),
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "grouped_24_fit_receipt_compatible": False,
        "publication_authority": False,
        "terminal_execution_attestation_required": True,
        "policy": dict(_FALSE_POLICY),
    }, field="rank150_dpp_fold_receipt_sha256")
    if len(_canonical(receipt)) > FOLD_RECEIPT_BYTE_CEILING:
        _fail("rank150/DPP fold receipt exceeds its exact byte ceiling")
    return receipt


def validate_evaluation_fold_receipt_v1(
    value: object, *, source_ordinal: int, fold_ordinal: int,
    projection: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Validate the score-free shape required by the successor evaluator."""
    receipt = _mapping(value, label="rank150/DPP evaluation fold receipt")
    _self_hash(
        receipt,
        field="rank150_dpp_fold_receipt_sha256",
        label="rank150/DPP fold receipt",
    )
    response = _mapping(
        receipt.get("authority_response"), label="rank150/DPP response"
    )
    _self_hash(
        response, field="authority_response_sha256", label="rank150/DPP response"
    )
    binding = _mapping(
        response.get("authority_binding"), label="rank150/DPP authority binding"
    )
    _self_hash(
        binding,
        field="authority_binding_sha256",
        label="rank150/DPP authority binding",
    )
    cells = [
        _mapping(row, label=f"rank150/DPP evaluation cell[{index}]")
        for index, row in enumerate(
            _sequence(response.get("cells"), label="rank150/DPP cells")
        )
    ]
    if (
        receipt.get("schema_version") != FOLD_RECEIPT_SCHEMA
        or response.get("schema_version") != AUTHORITY_RESPONSE_SCHEMA
        or receipt.get("source_ordinal") != source_ordinal
        or receipt.get("fold_ordinal") != fold_ordinal
        or receipt.get("heldout_block") != contract.WORLD_BLOCKS[fold_ordinal]
        or receipt.get("slate_id") != projection["slate_id"]
        or response.get("fit_scope_id") != projection["fit_scope_id"]
        or binding.get("projection_sha256") != projection["projection_sha256"]
        or binding.get("candidate_lineup_order_sha256")
        != projection["candidate_lineup_order_sha256"]
        or receipt.get("fit_count") != EXACT_FIT_COUNT
        or response.get("fit_count") != EXACT_FIT_COUNT
        or len(cells) != EXACT_FIT_COUNT
        or receipt.get("cell_sha256s")
        != [row.get("authority_cell_sha256") for row in cells]
        or response.get("cell_sha256s") != receipt.get("cell_sha256s")
        or receipt.get("source_control_fit_parity_claimed") is not False
        or receipt.get("source_control_receipt_compatible") is not False
        or receipt.get("grouped_24_fit_receipt_compatible") is not False
    ):
        _fail("rank150/DPP evaluation fold authority differs")
    candidate_by_id = {
        str(row["lineup_id"]): row for row in projection["candidates"]
    }
    coordinates: list[tuple[int, int]] = []
    for cell in cells:
        _self_hash(cell, field="authority_cell_sha256", label="authority cell")
        coordinate = _mapping(
            cell.get("selector_coordinate"), label="selector coordinate"
        )
        _self_hash(
            coordinate,
            field="selector_coordinate_sha256",
            label="selector coordinate",
        )
        sampled = [str(row) for row in cell["sampled_lineup_ids"]]
        selected = [str(row) for row in cell["selected_lineup_ids"]]
        rosters = [
            list(candidate_by_id[lineup_id]["roster_player_ids"])
            for lineup_id in selected
        ]
        if (
            cell.get("schema_version") != AUTHORITY_CELL_SCHEMA
            or cell.get("replicate") != 0
            or type(cell.get("view_ordinal")) is not int
            or coordinate.get("schema_version") != SELECTOR_COORDINATE_SCHEMA
            or type(coordinate.get("selector_ordinal")) is not int
            or sampled != sorted(set(sampled))
            or not set(selected) <= set(sampled) <= set(candidate_by_id)
            or len(selected) != RANKING_DEPTH
            or len(set(selected)) != RANKING_DEPTH
            or cell.get("sampled_lineup_ids_sha256") != _hash(sampled)
            or cell.get("selected_lineup_ids_sha256") != _hash(selected)
            or cell.get("selected_rosters_sha256") != _hash(rosters)
            or cell.get("prefixes")
            != _prefixes_v1(
                selected_ids=selected, candidate_by_id=candidate_by_id
            )
        ):
            _fail("rank150/DPP evaluation cell authority differs")
        coordinates.append((
            int(cell["view_ordinal"]), int(coordinate["selector_ordinal"])
        ))
    if sorted(coordinates) != [
        (view, selector)
        for view in range(EXACT_VIEW_COUNT)
        for selector in range(EXACT_SELECTORS_PER_VIEW)
    ]:
        _fail("rank150/DPP evaluation coordinate lattice differs")
    return receipt, cells


def build_slate_result_v1(
    *, source_ordinal: int, slate_id: str, fold_receipts: object,
    task_manifest_identity: object, task_binding_sha256: str,
    dispatcher_runtime_evidence: object,
) -> dict[str, object]:
    folds = [
        _mapping(row, label=f"rank150/DPP fold[{index}]")
        for index, row in enumerate(
            _sequence(fold_receipts, label="rank150/DPP folds")
        )
    ]
    runtime = _mapping(
        dispatcher_runtime_evidence, label="dispatcher runtime evidence"
    )
    if (
        type(source_ordinal) is not int
        or len(folds) != EXACT_FOLDS_PER_SLATE
        or [row.get("fold_ordinal") for row in folds]
        != list(range(EXACT_FOLDS_PER_SLATE))
        or any(row.get("source_ordinal") != source_ordinal for row in folds)
        or any(row.get("slate_id") != slate_id for row in folds)
        or any(row.get("fit_count") != EXACT_FIT_COUNT for row in folds)
        or _SHA_RE.fullmatch(task_binding_sha256) is None
    ):
        _fail("rank150/DPP slate fold lattice differs")
    for row in folds:
        _self_hash(
            row,
            field="rank150_dpp_fold_receipt_sha256",
            label="rank150/DPP fold receipt",
        )
    return _with_hash({
        "schema_version": SLATE_RESULT_SCHEMA,
        "mode_id": MODE_ID,
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "task_manifest_identity": _identity(
            task_manifest_identity, label="rank150/DPP task manifest"
        ),
        "task_binding_sha256": task_binding_sha256,
        "dispatcher_runtime_evidence": runtime,
        "dispatcher_runtime_evidence_sha256": _hash(runtime),
        "fold_count": EXACT_FOLDS_PER_SLATE,
        "fold_order": list(contract.WORLD_BLOCKS),
        "fold_receipts": folds,
        "fold_receipt_sha256s": [
            row["rank150_dpp_fold_receipt_sha256"] for row in folds
        ],
        "fit_count": EXACT_FITS_PER_SLATE,
        "fit_count_by_fold": [EXACT_FIT_COUNT] * EXACT_FOLDS_PER_SLATE,
        "entry_budgets": list(ENTRY_BUDGETS),
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "grouped_24_fit_result_compatible": False,
        "terminal_cloud_execution_attestation_present": False,
        "publication_mode": "create-once-exact-reopen",
        "policy": dict(_FALSE_POLICY),
    }, field="slate_result_sha256")


def validate_evaluation_slate_result_v1(
    value: object, *, projection_bundle: Mapping[str, object],
) -> dict[str, object]:
    result = _mapping(value, label="rank150/DPP slate result")
    _self_hash(result, field="slate_result_sha256", label="slate result")
    folds = [
        _mapping(row, label=f"rank150/DPP fold[{index}]")
        for index, row in enumerate(
            _sequence(result.get("fold_receipts"), label="rank150/DPP folds")
        )
    ]
    if (
        result.get("schema_version") != SLATE_RESULT_SCHEMA
        or result.get("mode_id") != MODE_ID
        or result.get("source_ordinal") != projection_bundle["source_ordinal"]
        or result.get("slate_id") != projection_bundle["slate_id"]
        or result.get("fold_count") != EXACT_FOLDS_PER_SLATE
        or result.get("fold_order") != list(contract.WORLD_BLOCKS)
        or result.get("fit_count") != EXACT_FITS_PER_SLATE
        or result.get("fit_count_by_fold")
        != [EXACT_FIT_COUNT] * EXACT_FOLDS_PER_SLATE
        or len(folds) != EXACT_FOLDS_PER_SLATE
        or result.get("fold_receipt_sha256s")
        != [row.get("rank150_dpp_fold_receipt_sha256") for row in folds]
        or result.get("source_control_fit_parity_claimed") is not False
        or result.get("source_control_receipt_compatible") is not False
        or result.get("grouped_24_fit_result_compatible") is not False
    ):
        _fail("rank150/DPP slate result authority differs")
    for fold, (receipt, projection) in enumerate(zip(
        folds, projection_bundle["fold_projections"], strict=True
    )):
        validate_evaluation_fold_receipt_v1(
            receipt,
            source_ordinal=int(result["source_ordinal"]),
            fold_ordinal=fold,
            projection=projection,
        )
    return result


__all__ = [
    "AUTHORITY_CELL_SCHEMA",
    "AUTHORITY_RESPONSE_SCHEMA",
    "ENTRYPOINT_IMAGE_PATH",
    "ENTRYPOINT_RELATIVE_PATH",
    "ENTRY_BUDGETS",
    "EXACT_FIT_COUNT",
    "EXACT_FITS_PER_SLATE",
    "EXACT_SELECTORS_PER_VIEW",
    "EXACT_VIEW_COUNT",
    "FOLD_RECEIPT_BYTE_CEILING",
    "FOLD_RECEIPT_SCHEMA",
    "MATRIX_CHILD_REQUEST_SCHEMA",
    "MODE_ID",
    "PROCESS_BUDGET_SCHEMA",
    "PROCESS_ORDINAL_ENV",
    "PROCESS_ROLE",
    "RUNTIME_MODE",
    "RUNTIME_SCHEMA",
    "SLATE_RESULT_SCHEMA",
    "CorpusR6CurrentBankSelectorRank150DppModeV1Error",
    "build_fold_receipt_v1",
    "build_matrix_child_request_v1",
    "build_process_mode_v1",
    "build_runtime_evidence_v1",
    "build_slate_result_v1",
    "canonical_matrix_selector_command_v1",
    "compile_process_budget_v1",
    "derive_current_process_runtime_evidence_v1",
    "entrypoint_source_sha256_v1",
    "run_authority_bound_rank150_dpp_v1",
    "validate_evaluation_fold_receipt_v1",
    "validate_evaluation_slate_result_v1",
    "validate_matrix_child_request_v1",
    "validate_process_budget_v1",
    "validate_runtime_evidence_v1",
]
