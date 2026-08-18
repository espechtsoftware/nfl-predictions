"""Fast adversarial checks for the residual-world exact-proof boundary.

These tests intentionally use tiny hand-written models and retained artifacts.
They must never invoke CBC or the residual pricing loop: their purpose is to
make byte/profile, exact-arithmetic, command, and filesystem failures cheap to
reproduce before any long proof solve is licensed.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import (
    Decimal,
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    localcontext,
)
from pathlib import Path
import shlex
from types import SimpleNamespace

import pytest

from nfl_dfs.research import residual_world_columns as rw


_ONE_BINARY_MPS = (
    b"*SENSE:Maximize\n"
    b"NAME          MODEL\n"
    b"ROWS\n"
    b" N  OBJ\n"
    b" E  C0000000\n"
    b"COLUMNS\n"
    b"    MARK      'MARKER'                 'INTORG'\n"
    b"    X0000000  C0000000   1.000000000000e+00\n"
    b"    X0000000  OBJ        1.000000000000e+00\n"
    b"    MARK      'MARKER'                 'INTEND'\n"
    b"RHS\n"
    b"    RHS       C0000000   1.000000000000e+00\n"
    b"BOUNDS\n"
    b" BV BND       X0000000\n"
    b"ENDATA\n"
)


_TWO_BINARY_MPS = (
    b"*SENSE:Maximize\n"
    b"NAME          MODEL\n"
    b"ROWS\n"
    b" N  OBJ\n"
    b" E  C0000000\n"
    b"COLUMNS\n"
    b"    MARK      'MARKER'                 'INTORG'\n"
    b"    X0000000  C0000000   1.000000000000e+00\n"
    b"    X0000000  OBJ        1.000000000000e+00\n"
    b"    MARK      'MARKER'                 'INTEND'\n"
    b"    MARK      'MARKER'                 'INTORG'\n"
    b"    X0000001  C0000000  -1.000000000000e+00\n"
    b"    X0000001  OBJ       -1.000000000000e+00\n"
    b"    MARK      'MARKER'                 'INTEND'\n"
    b"RHS\n"
    b"    RHS       C0000000   0.000000000000e+00\n"
    b"BOUNDS\n"
    b" BV BND       X0000000\n"
    b" BV BND       X0000001\n"
    b"ENDATA\n"
)


_NONCONTIGUOUS_BOUNDS_MPS = (
    b"*SENSE:Maximize\n"
    b"NAME          MODEL\n"
    b"ROWS\n"
    b" N  OBJ\n"
    b" E  C0000000\n"
    b"COLUMNS\n"
    b"    X0000000  C0000000   1.000000000000e+00\n"
    b"    X0000000  OBJ        1.000000000000e+00\n"
    b"    MARK      'MARKER'                 'INTORG'\n"
    b"    X0000001  C0000000   1.000000000000e+00\n"
    b"    X0000001  OBJ        1.000000000000e+00\n"
    b"    MARK      'MARKER'                 'INTEND'\n"
    b"RHS\n"
    b"    RHS       C0000000   3.000000000000e+00\n"
    b"BOUNDS\n"
    b" LO BND       X0000000   2.000000000000e+00\n"
    b" BV BND       X0000001\n"
    b" UP BND       X0000000   3.000000000000e+00\n"
    b"ENDATA\n"
)


def _write_bytes(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def _profile_poison(name: str) -> bytes:
    if name == "crlf":
        return _ONE_BINARY_MPS.replace(b"\n", b"\r\n")
    if name == "missing_final_lf":
        return _ONE_BINARY_MPS[:-1]
    if name == "objective_not_first":
        return _ONE_BINARY_MPS.replace(
            b" N  OBJ\n E  C0000000\n",
            b" E  C0000000\n N  OBJ\n",
            1,
        )
    if name == "marker_starts_mid_column":
        return _ONE_BINARY_MPS.replace(
            b"    MARK      'MARKER'                 'INTORG'\n"
            b"    X0000000  C0000000   1.000000000000e+00\n"
            b"    X0000000  OBJ        1.000000000000e+00\n",
            b"    X0000000  C0000000   1.000000000000e+00\n"
            b"    MARK      'MARKER'                 'INTORG'\n"
            b"    X0000000  OBJ        1.000000000000e+00\n",
            1,
        )
    if name == "split_marker_block":
        return _ONE_BINARY_MPS.replace(
            b"    X0000000  C0000000   1.000000000000e+00\n"
            b"    X0000000  OBJ        1.000000000000e+00\n",
            b"    X0000000  C0000000   1.000000000000e+00\n"
            b"    MARK      'MARKER'                 'INTEND'\n"
            b"    MARK      'MARKER'                 'INTORG'\n"
            b"    X0000000  OBJ        1.000000000000e+00\n",
            1,
        )
    if name == "noncontiguous_bounds":
        return _NONCONTIGUOUS_BOUNDS_MPS
    raise AssertionError(f"unknown profile poison {name}")


def test_pinned_minimal_mps_fixture_is_valid(tmp_path):
    model = rw._parse_exact_mps(
        _write_bytes(tmp_path / "valid.mps", _ONE_BINARY_MPS)
    )
    assert model.columns == ("X0000000",)
    assert model.rows == ("C0000000",)
    assert model.bounds["X0000000"] == (0, 1)


@pytest.mark.parametrize(
    "poison",
    (
        "crlf",
        "missing_final_lf",
        "objective_not_first",
        "marker_starts_mid_column",
        "split_marker_block",
        "noncontiguous_bounds",
    ),
)
def test_raw_mps_writer_profile_poison_fails_closed(tmp_path, poison):
    path = _write_bytes(tmp_path / f"{poison}.mps", _profile_poison(poison))
    with pytest.raises(rw.SolverFailure):
        rw._parse_exact_mps(path)


@pytest.mark.parametrize(
    "token, expected_residual",
    (
        ("0.999999999", Decimal("-1e-9")),
        ("1.000000001", Decimal("1e-9")),
    ),
)
@pytest.mark.parametrize(
    "precision, rounding",
    (
        (8, ROUND_FLOOR),
        (9, ROUND_CEILING),
        (28, ROUND_HALF_EVEN),
        (80, ROUND_CEILING),
    ),
)
def test_integer_decode_boundary_is_inclusive_and_context_independent(
    token, expected_residual, precision, rounding,
):
    with localcontext() as context:
        context.prec = precision
        context.rounding = rounding
        canonical, signed_residual = rw._decode_integer_token(token, "test token")
    assert canonical == 1
    assert signed_residual == expected_residual


@pytest.mark.parametrize(
    "token",
    (
        "0.9999999989999999999999999999999999999999",
        "1.0000000010000000000000000000000000000001",
    ),
)
def test_integer_decode_just_over_literal_boundary_fails_under_low_precision(
    token,
):
    with localcontext() as context:
        context.prec = 8
        context.rounding = ROUND_FLOOR
        with pytest.raises(rw.SolverFailure, match="decode epsilon"):
            rw._decode_integer_token(token, "just-over token")


def test_problem_to_mps_correspondence_rejects_writer_rounding(tmp_path):
    coefficient = 123_456_789_012_345
    assert coefficient < 2**53
    problem = rw.pulp.LpProblem("writer_rounding", rw.pulp.LpMaximize)
    decision = rw.pulp.LpVariable("decision", 0, 1, cat="Binary")
    problem += decision <= 1, "legal"
    problem.setObjective(coefficient * decision)
    manifest = rw._variable_domain_manifest(problem)
    path = tmp_path / "writer-rounded.mps"
    problem.writeMPS(str(path), rename=1)
    parsed = rw._parse_exact_mps(path)
    assert parsed.coefficients[("X0000000", "OBJ")] != coefficient
    with pytest.raises(rw.SolverFailure, match="coefficients differ"):
        rw._validate_problem_matches_mps(problem, parsed, manifest)


def test_problem_to_mps_correspondence_rejects_writer_rounded_bound(tmp_path):
    lower = 123_456_789_012_345
    upper = lower + 1
    assert upper < 2**53
    problem = rw.pulp.LpProblem("writer_bound_rounding", rw.pulp.LpMaximize)
    decision = rw.pulp.LpVariable(
        "decision", lowBound=lower, upBound=upper, cat="Integer"
    )
    anchor = rw.pulp.LpVariable("anchor", 0, 1, cat="Binary")
    problem += anchor == 0, "anchor_row"
    problem.setObjective(decision)
    manifest = rw._variable_domain_manifest(problem)
    path = tmp_path / "writer-rounded-bound.mps"
    problem.writeMPS(str(path), rename=1)
    parsed = rw._parse_exact_mps(path)
    renamed = next(row[0] for row in manifest if row[1] == "decision")
    assert parsed.bounds[renamed] != (lower, upper)
    with pytest.raises(rw.SolverFailure, match="bounds differ"):
        rw._validate_problem_matches_mps(problem, parsed, manifest)


def test_problem_to_mps_correspondence_rejects_column_category_drift(tmp_path):
    problem = rw.pulp.LpProblem("category_drift", rw.pulp.LpMaximize)
    decision = rw.pulp.LpVariable("decision", 0, 1, cat="Binary")
    problem += decision == 1, "legal"
    problem.setObjective(decision)
    manifest = rw._variable_domain_manifest(problem)
    path = tmp_path / "category-drift.mps"
    problem.writeMPS(str(path), rename=1)
    parsed = rw._parse_exact_mps(path)
    renamed = manifest[0][0]
    poisoned_categories = dict(parsed.column_categories)
    poisoned_categories[renamed] = "continuous"
    poisoned = replace(parsed, column_categories=poisoned_categories)
    with pytest.raises(rw.SolverFailure, match="categories differ"):
        rw._validate_problem_matches_mps(problem, poisoned, manifest)


def test_zero_objective_is_materialized_before_pulp_can_inject_dummy(tmp_path):
    problem = rw.pulp.LpProblem("zero_objective", rw.pulp.LpMaximize)
    decision = rw.pulp.LpVariable("decision", 0, 1, cat="Binary")
    problem += decision == 1, "legal"
    problem.setObjective(rw.pulp.lpSum([]))

    rw._materialize_zero_objective(problem)
    variables_before = tuple(variable.name for variable in problem.variables())
    constraints_before = tuple(problem.constraints)
    assert "__dummy" not in variables_before
    assert "residual_explicit_zero_objective" in variables_before

    # The operation is an idempotent preparation boundary, not a second graph
    # mutation when serializers independently rebuild the same model.
    rw._materialize_zero_objective(problem)
    assert tuple(variable.name for variable in problem.variables()) == variables_before
    assert tuple(problem.constraints) == constraints_before

    manifest = rw._variable_domain_manifest(problem)
    path = tmp_path / "zero-objective.mps"
    problem.writeMPS(str(path), rename=1)
    assert tuple(variable.name for variable in problem.variables()) == variables_before
    parsed = rw._parse_exact_mps(path)
    rw._validate_problem_matches_mps(problem, parsed, manifest)


def test_l1_activity_profile_is_cancellation_safe_below_two_to_53(tmp_path):
    base = rw._parse_exact_mps(
        _write_bytes(tmp_path / "two-binary.mps", _TWO_BINARY_MPS)
    )
    safe = (1 << 52) - 1
    safe_model = replace(
        base,
        coefficients={
            key: safe if value > 0 else -safe
            for key, value in base.coefficients.items()
        },
    )
    # Both row and objective cancel at (1, 1), while their conservative L1
    # bound is 2**53 - 2 and therefore still exactly representable.
    rw._validate_mps_exact_activity_profile(safe_model)

    boundary = 1 << 52
    unsafe_model = replace(
        base,
        coefficients={
            key: boundary if value > 0 else -boundary
            for key, value in base.coefficients.items()
        },
    )
    with pytest.raises(rw.SolverFailure, match="worst-case.*exact range"):
        rw._validate_mps_exact_activity_profile(unsafe_model)


def test_huge_exponent_primal_or_dual_inf_is_never_masked():
    finite = (
        "Clp0006I 0 Obj 1 Primal inf 1.25 (1) Dual inf 2e-3 (2)\n"
    )
    assert rw._CBC_FORBIDDEN.search(
        rw._cbc_forbidden_marker_text(finite)
    ) is None

    for poison in (
        "Clp0006I 0 Obj 1 Primal inf 1e999999999 (1)\n",
        "Clp0006I 0 Obj 1 Primal inf 1 (1) Dual inf 1e999999999 (2)\n",
    ):
        with pytest.raises(rw.SolverFailure, match="binary64 range"):
            rw._cbc_forbidden_marker_text(poison)


def _cold_exact_command_fixture(tmp_path):
    cbc = tmp_path / "cbc"
    model = tmp_path / "model.mps"
    solution = tmp_path / "model.sol"
    cbc.write_bytes(b"test binary")
    model.write_bytes(_ONE_BINARY_MPS)
    solution.write_text("Optimal - objective value 1\n", encoding="utf-8")
    evidence = SimpleNamespace(
        cbc_path=str(cbc),
        model_path=str(model),
        solution_path=str(solution),
        mip_start_path=None,
        problem_sense=rw.pulp.LpMaximize,
        max_seconds=120,
        warm_start=False,
        cuts=False,
        preprocess_off=False,
    )
    tokens = [
        str(cbc), str(model), "-max", "-sec", "120", "-cuts", "off",
        "-randomSeed", str(rw.CBC_RANDOM_SEED),
        "-randomCbcSeed", str(rw.CBC_RANDOM_SEED),
        "-primalTolerance", "1e-9", "-integerTolerance", "1e-9",
        "-ratio", "0.0", "-allow", "0.0", "-threads", "1",
        "-timeMode", "elapsed", "-solve", "-printingOptions", "all",
        "-solution", str(solution),
    ]
    return evidence, tokens


def test_extra_cbc_positional_token_fails_closed(tmp_path):
    evidence, tokens = _cold_exact_command_fixture(tmp_path)
    rw._validate_retained_command(evidence, shlex.join(tokens))
    poisoned = list(tokens)
    poisoned.insert(poisoned.index("-solve"), "quit")
    with pytest.raises(rw.SolverFailure, match="exact registered grammar"):
        rw._validate_retained_command(evidence, shlex.join(poisoned))


def test_row_display_is_nonlicensing_but_exact_assignment_remains_decisive(
    tmp_path,
):
    model_path = tmp_path / "display-only.mps"
    model_path.write_bytes(_ONE_BINARY_MPS)
    manifest = (("X0000000", "scientific_x", "binary", 0, 1),)

    harmless_drift = (
        "Optimal - objective value 1.00000000\n"
        "0 C0000000 -3.0089264e-11 -0\n"
        "0 X0000000 1 0\n"
    )
    objective, _, affected, maximum_residual, _, _ = (
        rw._validate_solution_body(harmless_drift, model_path, manifest)
    )
    assert objective == 1
    assert affected == 0
    assert maximum_residual == 0

    above_decode_boundary = (
        "Optimal - objective value 1.00000000\n"
        "0 C0000000 1 0\n"
        "0 X0000000 0.000000001001 0\n"
    )
    with pytest.raises(rw.SolverFailure, match="decode epsilon"):
        rw._validate_solution_body(
            above_decode_boundary, model_path, manifest
        )

    benign_display_infeasible_assignment = (
        "Optimal - objective value 1.00000000\n"
        "0 C0000000 1 0\n"
        "0 X0000000 0 0\n"
    )
    with pytest.raises(rw.SolverFailure, match="violates an MPS row"):
        rw._validate_solution_body(
            benign_display_infeasible_assignment, model_path, manifest
        )


@pytest.mark.parametrize("symlink_kind", ("root", "parent"))
def test_evidence_root_or_parent_symlink_fails_closed(tmp_path, symlink_kind):
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    if symlink_kind == "root":
        real_root = real_parent / "real-root"
        real_root.mkdir()
        evidence_root = tmp_path / "root-link"
        evidence_root.symlink_to(real_root, target_is_directory=True)
    else:
        parent_link = tmp_path / "parent-link"
        parent_link.symlink_to(real_parent, target_is_directory=True)
        evidence_root = parent_link / "root"
        evidence_root.mkdir()
    with pytest.raises(
        (rw.ResidualWorldError, rw.SolverFailure), match="symlink|root",
    ):
        rw._audit_evidence_root_inventory(evidence_root, ())


def test_stable_artifact_read_detects_in_place_toctou(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"original bytes")
    original_read = rw.os.read
    mutated = False

    def racing_read(descriptor, count):
        nonlocal mutated
        payload = original_read(descriptor, count)
        if not mutated:
            mutated = True
            artifact.write_bytes(b"changed after the descriptor was opened")
        return payload

    monkeypatch.setattr(rw.os, "read", racing_read)
    with pytest.raises(rw.SolverFailure, match="changed while being read"):
        rw._stable_regular_file_bytes(artifact)
