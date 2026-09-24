#!/usr/bin/env python3
"""Local-only operator for the R6 fair fill/profile/selector retest lane."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys

import numpy as np

from nfl_dfs.research import corpus_r6_fair_fill_retest_v1 as retest
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import residual_world_columns as rw


class OperatorError(ValueError):
    """The local retest operator received an invalid package."""


def _read_json(path: Path, *, label: str) -> object:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OperatorError(f"cannot read {label}: {path}: {exc}") from exc
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OperatorError(f"{label} is not strict JSON: {path}") from exc


def _write_json_create_once(path: Path, value: object) -> None:
    body = profiles.canonical_json_bytes_v1(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(body)
            handle.flush()
    except FileExistsError as exc:
        raise OperatorError(f"refusing to overwrite existing output: {path}") from exc
    except OSError as exc:
        raise OperatorError(f"cannot write output: {path}: {exc}") from exc


def _emit(path: str, value: object) -> None:
    if path == "-":
        sys.stdout.buffer.write(profiles.canonical_json_bytes_v1(value) + b"\n")
        return
    _write_json_create_once(Path(path), value)


def _preflight_outputs(paths: Sequence[str]) -> None:
    if len(set(paths)) != len(paths):
        raise OperatorError("output paths must be distinct")
    if list(paths).count("-") > 1:
        raise OperatorError("at most one output may use stdout")
    existing = [path for path in paths if path != "-" and Path(path).exists()]
    if existing:
        raise OperatorError(f"refusing to overwrite existing output: {existing[0]}")


def _read_cells(paths: Sequence[str]) -> list[dict[str, object]]:
    cells: list[dict[str, object]] = []
    for raw_path in paths:
        value = _read_json(Path(raw_path), label="candidate cell")
        try:
            cells.append(retest.validate_candidate_cell_v1(value))
        except retest.CorpusR6FairFillRetestV1Error as exc:
            raise OperatorError(f"invalid candidate cell {raw_path}: {exc}") from exc
    cells.sort(key=lambda row: str(row["cell_id"]))
    return cells


def _load_matrix(path: str, *, label: str) -> np.ndarray:
    source = Path(path)
    try:
        matrix = np.load(source, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise OperatorError(f"cannot load {label} .npy: {source}: {exc}") from exc
    if not isinstance(matrix, np.ndarray) or matrix.ndim != 2:
        raise OperatorError(f"{label} must be one two-dimensional .npy array")
    if matrix.dtype != np.dtype(np.float64):
        raise OperatorError(f"{label} must have exact float64 dtype")
    retained = np.ascontiguousarray(matrix, dtype=np.float64)
    if not np.isfinite(retained).all():
        raise OperatorError(f"{label} contains non-finite values")
    retained.flags.writeable = False
    return retained


def _registry_command(args: argparse.Namespace) -> None:
    body = {
        "schema": "corpus-r6-fair-fill-local-registry-package/v1",
        "fill_registry": retest.fill_strategy_registry_v1(),
        "construction_profile_registry": retest.construction_profile_registry_v1(),
        "selector_registry": retest.selector_registry_v1(),
        "incumbent_control_registry": retest.incumbent_control_registry_v1(),
        "controller": retest.compile_fair_fill_retest_controller_v1(),
        "operator_capabilities": [
            "registry",
            "compile-score-free-fold",
            "freeze-selection-from-training-simulated-matrix",
            "evaluate-only-after-reopening-create-once-selection",
        ],
        "cloud_access": False,
        "realized_outcome_input": False,
    }
    body["package_sha256"] = profiles.canonical_sha256_v1(body)
    _preflight_outputs([args.output])
    _emit(args.output, body)


def _compile_command(args: argparse.Namespace) -> None:
    _preflight_outputs([args.controller_output, args.plan_output])
    cells = _read_cells(args.cell)
    try:
        controller = retest.compile_fair_fill_retest_controller_v1(
            candidate_cells=cells,
            allow_non_authoritative=args.allow_non_authoritative,
        )
        plan = retest.build_fair_fill_fold_plan_v1(
            candidate_cells=cells,
            heldout_block=args.heldout_block,
            allow_non_authoritative=args.allow_non_authoritative,
            allow_diagnostic=args.allow_diagnostic,
        )
    except retest.CorpusR6FairFillRetestV1Error as exc:
        raise OperatorError(str(exc)) from exc
    _emit(args.controller_output, controller)
    _emit(args.plan_output, plan)


def _plan_cell(
    plan: Mapping[str, object], *, cell_id: str
) -> dict[str, object]:
    matches = [
        dict(row)
        for row in plan["cell_plans"]
        if isinstance(row, Mapping) and row.get("cell_id") == cell_id
    ]
    if len(matches) != 1:
        raise OperatorError("requested cell ID is absent from the fold plan")
    return matches[0]


def _select_command(args: argparse.Namespace) -> None:
    _preflight_outputs([args.selector_output])
    try:
        plan = retest.validate_fair_fill_fold_plan_v1(
            _read_json(Path(args.plan), label="fold plan")
        )
    except retest.CorpusR6FairFillRetestV1Error as exc:
        raise OperatorError(f"invalid fold plan: {exc}") from exc
    cell = _plan_cell(plan, cell_id=args.cell_id)
    candidate_rows = [dict(row) for row in cell["sampled_candidate_rows"]]
    lineup_ids = [str(value) for value in cell["sampled_lineup_ids"]]
    full_rows = [dict(row) for row in cell["eligible_candidate_rows"]]
    full_ids = [str(row["lineup_id"]) for row in full_rows]
    full_training = _load_matrix(
        args.full_training_matrix, label="full-corpus training score matrix"
    )
    if full_training.shape != (
        len(full_ids), 4 * rw.WORLDS_PER_BLOCK
    ):
        raise OperatorError(
            "full training matrix shape must be full_candidate_count x 40000"
        )
    ordinal = {lineup_id: index for index, lineup_id in enumerate(full_ids)}
    training = np.ascontiguousarray(
        full_training[[ordinal[lineup_id] for lineup_id in lineup_ids]],
        dtype=np.float64,
    )
    try:
        selection = retest.bind_fair_fill_selection_inputs_v1(
            plan_sha256=str(plan["plan_sha256"]),
            cell_id=args.cell_id,
            heldout_block=str(plan["heldout_block"]),
            training_blocks=[str(value) for value in plan["training_blocks"]],
            worlds_per_block=rw.WORLDS_PER_BLOCK,
            sampled_lineup_ids=lineup_ids,
            candidate_rows=candidate_rows,
            training_score_matrix=training,
        )
        selector_result = retest.run_fair_fill_selectors_v1(selection)
        controls = retest.run_incumbent_control_sensitivity_v1(
            cell_id=args.cell_id,
            full_candidate_rows=full_rows,
            full_training_score_matrix=full_training,
            equal_size_lineup_ids=lineup_ids,
            training_blocks=[str(value) for value in plan["training_blocks"]],
            worlds_per_block=rw.WORLDS_PER_BLOCK,
        )
    except retest.CorpusR6FairFillRetestV1Error as exc:
        raise OperatorError(str(exc)) from exc
    package = {
        "schema": "corpus-r6-fair-fill-local-selection-package/v1",
        "plan_sha256": plan["plan_sha256"],
        "cell_id": args.cell_id,
        "successor_selector_result": selector_result,
        "successor_selector_result_sha256": selector_result[
            "selector_result_sha256"
        ],
        "incumbent_control_sensitivity": controls,
        "incumbent_control_sensitivity_sha256": controls[
            "sensitivity_result_sha256"
        ],
        "heldout_bytes_opened": False,
        "realized_outcomes_read": False,
    }
    package["selection_package_sha256"] = profiles.canonical_sha256_v1(package)
    _emit(args.selector_output, package)


def _evaluate_command(args: argparse.Namespace) -> None:
    """Open heldout bytes only after reopening a frozen selector result."""
    _preflight_outputs([args.evaluation_output])
    try:
        plan = retest.validate_fair_fill_fold_plan_v1(
            _read_json(Path(args.plan), label="fold plan")
        )
    except retest.CorpusR6FairFillRetestV1Error as exc:
        raise OperatorError(f"invalid fold plan: {exc}") from exc
    cell = _plan_cell(plan, cell_id=args.cell_id)
    # This ordering is deliberate: heldout bytes cannot open until a separate
    # create-once selection result has been reopened and structurally bound.
    selection_package = _read_json(
        Path(args.selector_result), label="create-once selector result"
    )
    if (
        not isinstance(selection_package, Mapping)
        or selection_package.get("schema")
        != "corpus-r6-fair-fill-local-selection-package/v1"
        or selection_package.get("selection_package_sha256")
        != profiles.canonical_sha256_v1({
            key: value for key, value in selection_package.items()
            if key != "selection_package_sha256"
        })
        or selection_package.get("plan_sha256") != plan["plan_sha256"]
        or selection_package.get("cell_id") != args.cell_id
        or selection_package.get("heldout_bytes_opened") is not False
        or selection_package.get("realized_outcomes_read") is not False
    ):
        raise OperatorError("selection package authority differs")
    full_heldout = _load_matrix(
        args.full_heldout_matrix, label="full-corpus heldout score matrix"
    )
    candidate_rows = [dict(row) for row in cell["sampled_candidate_rows"]]
    lineup_ids = [str(value) for value in cell["sampled_lineup_ids"]]
    full_rows = [dict(row) for row in cell["eligible_candidate_rows"]]
    full_ids = [str(row["lineup_id"]) for row in full_rows]
    if full_heldout.shape != (len(full_ids), rw.WORLDS_PER_BLOCK):
        raise OperatorError(
            "full heldout matrix shape must be full_candidate_count x 10000"
        )
    ordinal = {lineup_id: index for index, lineup_id in enumerate(full_ids)}
    heldout = np.ascontiguousarray(
        full_heldout[[ordinal[lineup_id] for lineup_id in lineup_ids]],
        dtype=np.float64,
    )
    try:
        evaluation = retest.bind_fair_fill_evaluation_inputs_v1(
            plan_sha256=str(plan["plan_sha256"]),
            cell_id=args.cell_id,
            heldout_block=str(plan["heldout_block"]),
            worlds_per_block=rw.WORLDS_PER_BLOCK,
            sampled_lineup_ids=lineup_ids,
            rosters=[row["roster_player_ids"] for row in candidate_rows],
            heldout_score_matrix=heldout,
        )
        evaluation_result = retest.evaluate_fair_fill_selector_result_v1(
            evaluation,
            selector_result=selection_package["successor_selector_result"],
        )
        control_evaluation = retest.evaluate_incumbent_control_sensitivity_v1(
            sensitivity_result=selection_package[
                "incumbent_control_sensitivity"
            ],
            full_lineup_ids=full_ids,
            full_heldout_score_matrix=full_heldout,
        )
    except retest.CorpusR6FairFillRetestV1Error as exc:
        raise OperatorError(str(exc)) from exc
    package = {
        "schema": "corpus-r6-fair-fill-local-evaluation-package/v1",
        "selection_package_sha256": selection_package[
            "selection_package_sha256"
        ],
        "successor_evaluation": evaluation_result,
        "successor_evaluation_sha256": evaluation_result[
            "evaluation_result_sha256"
        ],
        "incumbent_control_evaluation": control_evaluation,
        "incumbent_control_evaluation_sha256": control_evaluation[
            "evaluation_result_sha256"
        ],
        "simulated_scores_only": True,
        "realized_outcomes_read": False,
    }
    package["evaluation_package_sha256"] = profiles.canonical_sha256_v1(package)
    _emit(args.evaluation_output, package)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Local score-free compiler and simulated-world executor for the "
            "R6 fair fill retest. No cloud or realized-outcome input exists."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    registry = commands.add_parser("registry", help="export frozen registries")
    registry.add_argument("--output", default="-", help="create-once JSON path or -")
    registry.set_defaults(handler=_registry_command)

    compile_parser = commands.add_parser(
        "compile", help="compile candidate-cell JSON into one fair fold"
    )
    compile_parser.add_argument("--cell", action="append", required=True)
    compile_parser.add_argument(
        "--heldout-block", choices=rw.WORLD_BLOCKS, required=True
    )
    compile_parser.add_argument("--plan-output", required=True)
    compile_parser.add_argument("--controller-output", required=True)
    compile_parser.add_argument("--allow-non-authoritative", action="store_true")
    compile_parser.add_argument("--allow-diagnostic", action="store_true")
    compile_parser.set_defaults(handler=_compile_command)

    select = commands.add_parser(
        "select", help="freeze seven selectors from training columns only"
    )
    select.add_argument("--plan", required=True)
    select.add_argument("--cell-id", required=True)
    select.add_argument("--full-training-matrix", required=True)
    select.add_argument("--selector-output", required=True)
    select.set_defaults(handler=_select_command)

    evaluate = commands.add_parser(
        "evaluate", help="open heldout matrix after frozen selector result"
    )
    evaluate.add_argument("--plan", required=True)
    evaluate.add_argument("--cell-id", required=True)
    evaluate.add_argument("--selector-result", required=True)
    evaluate.add_argument("--full-heldout-matrix", required=True)
    evaluate.add_argument("--evaluation-output", required=True)
    evaluate.set_defaults(handler=_evaluate_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except OperatorError as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
