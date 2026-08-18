"""Integration poisons for the hard-wired residual-world dose harness.

The four state-machine branches live in ``test_residual_world_columns``.
These tests reuse that module's exact 50,000-world fixture and concentrate on
the independent bindings that must fail closed around the state machine.
Only retained CBC proof parsing is stubbed; selector/pricer calls and numeric
pricing reconstruction continue through the production harness.
"""

from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

import test_residual_world_columns as dose_fixture
from nfl_dfs.research import residual_world_columns as rw


@pytest.mark.parametrize(
    ("poison", "match"),
    (
        (lambda size: list(range(79)), "exact-80 unique"),
        (lambda size: [*range(79), 0], "exact-80 unique"),
        (lambda size: [*range(79), size], "out-of-range"),
        (lambda size: [False, *range(1, 80)], "must be an integer"),
    ),
    ids=("short", "duplicate", "out-of-range", "boolean"),
)
def test_fold_dose_rejects_malformed_direct_selector_indices_before_pricing(
    monkeypatch, tmp_path, poison, match,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, _, _, _,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)
    pricing_calls: list[object] = []

    def poisoned_selector(values, entries, line, env):
        assert entries == rw.ENTRY_COUNT
        assert line == float(rw.CONTROL_TAIL_LINE_DK)
        assert env == {"SELECT_LSE": "0"}
        return poison(values.shape[0])

    def forbidden_pricer(*args, **kwargs):
        pricing_calls.append((args, kwargs))
        raise AssertionError("pricing ran after a malformed selector receipt")

    monkeypatch.setattr(rw, "select_tail_entries", poisoned_selector)
    monkeypatch.setattr(rw, "solve_residual_pricing", forbidden_pricer)
    evidence_root = tmp_path / "selector-poison"
    with pytest.raises(rw.ResidualWorldError, match=match):
        rw.run_fold_doses(
            prepared,
            players,
            worlds,
            raw,
            controls,
            tags,
            selector,
            control_micro,
            evidence_root=evidence_root,
        )
    assert pricing_calls == []
    assert not evidence_root.exists()


@pytest.mark.parametrize(
    "poison_kind",
    ("order", "metadata", "quota", "malformed-row"),
)
def test_fold_dose_independently_rejects_every_active_receipt_poison(
    monkeypatch, tmp_path, poison_kind,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, neither, _, _,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)
    original = rw.select_block_stratified_worlds
    pricing_calls: list[object] = []

    def poisoned_selection(*args, **kwargs):
        receipt = original(*args, **kwargs)
        quotas = tuple(args[3])
        if not quotas or quotas[0][1] != 22:
            return receipt
        if poison_kind == "order":
            return (receipt[1], receipt[0], *receipt[2:])
        if poison_kind == "metadata":
            return (
                replace(
                    receipt[0],
                    book_max_micro=receipt[0].book_max_micro - 1,
                ),
                *receipt[1:],
            )
        if poison_kind == "malformed-row":
            return (*receipt[:-1], object())

        # Preserve length, uniqueness and row validity while moving one slot
        # from the final block into the first.  The independent reconstruction
        # must reject the wrong 23/22/21 quota even though every row is legal.
        selected_ids = {selection.world_id for selection in receipt}
        expanded_first_block = rw._independent_block_selection(
            args[0], args[1], args[2], ((quotas[0][0], quotas[0][1] + 1),)
        )
        replacement = next(
            selection
            for selection in expanded_first_block
            if selection.world_id not in selected_ids
        )
        return (*receipt[:-1], replacement)

    def forbidden_pricer(*args, **kwargs):
        pricing_calls.append((args, kwargs))
        return dose_fixture._fake_pricer((neither[87],), [])(*args, **kwargs)

    monkeypatch.setattr(rw, "select_block_stratified_worlds", poisoned_selection)
    monkeypatch.setattr(rw, "solve_residual_pricing", forbidden_pricer)
    with pytest.raises(
        rw.ResidualWorldError,
        match="malformed row|independent deterministic|block quotas are malformed",
    ):
        rw.run_fold_doses(
            prepared,
            players,
            worlds,
            raw,
            controls,
            tags,
            selector,
            control_micro,
            evidence_root=tmp_path / f"active-{poison_kind}",
        )
    assert pricing_calls == []


def test_heldout_only_draw_mutation_cannot_change_construction_or_reuse_prepared(
    monkeypatch, tmp_path,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, _, _, _,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)
    changed_raw = raw.copy()
    heldout_column = rw.WORLDS_PER_BLOCK  # R1:0 is held out by fold A.
    assert worlds[heldout_column] == rw.WorldId("R1", 0)
    changed_raw[0, heldout_column] += np.float32(1.0)
    changed_player_micro = rw.to_micro_dk(changed_raw)
    changed_selector, changed_control_micro = rw._cross_score_rosters(
        players, changed_raw, changed_player_micro, controls
    )

    independently_prepared = rw.prepare_fold_reservoir(
        "A",
        players,
        worlds,
        changed_raw,
        controls,
        tags,
        changed_selector,
        changed_control_micro,
        prepared.reservoir_bounds,
    )
    assert independently_prepared.player_draws_sha256 != (
        prepared.player_draws_sha256
    )
    assert independently_prepared.control_book == prepared.control_book
    assert independently_prepared.pruning == prepared.pruning
    assert independently_prepared.reservoir_selections == (
        prepared.reservoir_selections
    )
    assert independently_prepared.reservoir_sha256 == prepared.reservoir_sha256

    pricing_calls: list[object] = []

    def forbidden_pricer(*args, **kwargs):
        pricing_calls.append((args, kwargs))
        raise AssertionError("stale prepared data reached the pricing step")

    monkeypatch.setattr(rw, "solve_residual_pricing", forbidden_pricer)
    with pytest.raises(
        rw.ResidualWorldError,
        match="prepared fold/source/Q_C binding changed",
    ):
        rw.run_fold_doses(
            prepared,
            players,
            worlds,
            changed_raw,
            controls,
            tags,
            changed_selector,
            changed_control_micro,
            evidence_root=tmp_path / "stale-heldout",
        )
    assert pricing_calls == []


@pytest.mark.parametrize("poison_kind", ("illegal-control", "bare-source-tags"))
def test_fold_dose_rejects_illegal_control_or_non_nested_source_tags(
    monkeypatch, tmp_path, poison_kind,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, _, _, _,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)
    poisoned_controls = controls
    poisoned_tags = tags
    poisoned_selector = selector
    poisoned_control_micro = control_micro
    match = "illegal position shape"
    if poison_kind == "illegal-control":
        # Keep all nine IDs inside the exact slate catalog, but omit QB so the
        # independent Classic legality audit—not membership or score-matrix
        # alignment—is what rejects the control row.
        illegal_identity = tuple(sorted(
            player.player_id
            for player in players
            if player.position != "QB"
        )[:9])
        assert len(illegal_identity) == 9
        assert all(
            player_id in {player.player_id for player in players}
            for player_id in illegal_identity
        )
        assert not any(
            player.player_id in illegal_identity and player.position == "QB"
            for player in players
        )
        poisoned_controls = (
            illegal_identity,
            *controls[1:],
        )
        poisoned_selector, poisoned_control_micro = rw._cross_score_rosters(
            players,
            raw,
            rw.to_micro_dk(raw),
            poisoned_controls,
        )
    else:
        poisoned_tags = tuple(row[0] for row in tags)
        match = "source tag row must be a sequence"

    pricing_calls: list[object] = []

    def forbidden_pricer(*args, **kwargs):
        pricing_calls.append((args, kwargs))
        raise AssertionError("invalid source data reached pricing")

    monkeypatch.setattr(rw, "solve_residual_pricing", forbidden_pricer)
    with pytest.raises(rw.ResidualWorldError, match=match):
        rw.run_fold_doses(
            prepared,
            players,
            worlds,
            raw,
            poisoned_controls,
            poisoned_tags,
            poisoned_selector,
            poisoned_control_micro,
            evidence_root=tmp_path / poison_kind,
        )
    assert pricing_calls == []


def test_direct_selector_and_pricer_spies_observe_exact_fold_dose_contract(
    monkeypatch, tmp_path,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, neither, column_only, selector_calls,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)
    selector_calls.clear()

    def exact_selector(values, entries, line, env):
        selector_calls.append(
            (values.shape, values.dtype, entries, line, dict(env))
        )
        return list(range(80))

    numeric_calls = []
    delegate = dose_fixture._fake_pricer(
        (column_only[0], neither[87]), numeric_calls
    )
    pricer_calls = []

    def exact_pricer_spy(
        players_arg, scores, maxima, lower, upper, *,
        control_rosters, previous_columns, solver_factory, **kwargs,
    ):
        pricer_calls.append({
            "players": tuple(players_arg),
            "scores_shape": scores.shape,
            "scores_dtype": scores.dtype,
            "maxima": tuple(int(value) for value in maxima),
            "controls": tuple(control_rosters),
            "previous": tuple(previous_columns),
            "solver_factory": solver_factory,
            "extra": dict(kwargs),
        })
        return delegate(
            players_arg,
            scores,
            maxima,
            lower,
            upper,
            control_rosters=control_rosters,
            previous_columns=previous_columns,
            solver_factory=solver_factory,
            **kwargs,
        )

    monkeypatch.setattr(rw, "select_tail_entries", exact_selector)
    monkeypatch.setattr(rw, "solve_residual_pricing", exact_pricer_spy)
    monkeypatch.setattr(
        rw, "_audit_pricing_evidence_semantics", lambda *args: None
    )
    result = rw.run_fold_doses(
        prepared,
        players,
        worlds,
        raw,
        controls,
        tags,
        selector,
        control_micro,
        evidence_root=tmp_path / "direct-spies",
    )

    assert result.generated_columns == (column_only[0],)
    assert result.stopped_on_first_null is True
    assert result.null_iteration == 2
    assert result.selector_call_count == 10
    assert [call[0][0] for call in selector_calls] == [
        88, 87, 86, 85, 84, 83, 82, 81, 80, 88,
    ]
    assert all(call[0][1] == 30_000 for call in selector_calls)
    assert all(call[1] == np.dtype(np.float32) for call in selector_calls)
    assert all(call[2:] == (80, 194.0, {"SELECT_LSE": "0"}) for call in selector_calls)

    assert len(pricer_calls) == 2
    assert all(call["players"] == players for call in pricer_calls)
    assert all(call["scores_shape"] == (len(players), 66) for call in pricer_calls)
    assert all(call["scores_dtype"] == np.dtype(np.int64) for call in pricer_calls)
    assert all(call["controls"] == controls for call in pricer_calls)
    assert [call["previous"] for call in pricer_calls] == [
        (), (column_only[0],),
    ]
    assert all(callable(call["solver_factory"]) for call in pricer_calls)
    assert all(call["extra"] == {} for call in pricer_calls)
    assert [step.complete_no_goods for step in result.steps] == [
        controls, (*controls, column_only[0]),
    ]
    assert result.treatment_source_tags[-1] == (
        "residual_world:fold_A:column_01",
    )
    assert result.generated_score_parity.sha256 == (
        result.generated_score_parity_sha256
    )
    assert result.treatment_score_parity.sha256 == (
        result.treatment_score_parity_sha256
    )
    payload = rw.fold_dose_scientific_payload(result)
    assert payload["generated_score_parity_sha256"] == (
        result.generated_score_parity.sha256
    )
    assert payload["generated_score_parity"] == (
        rw._score_parity_scientific_receipt(result.generated_score_parity)
    )
    assert payload["treatment_score_parity_sha256"] == (
        result.treatment_score_parity.sha256
    )
    assert payload["treatment_score_parity"] == (
        rw._score_parity_scientific_receipt(result.treatment_score_parity)
    )
    assert {
        name: payload[name] for name in rw.UNLICENSED_SCIENTIFIC_FLAGS
    } == {
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
    }

    # Serialization is itself a fail-closed audit boundary: stored hashes or
    # manifests cannot conceal a mutation to any earlier dose receipt.
    first = result.steps[0]
    poisoned_maxima = (
        first.reservoir_maxima_micro[0] + 1,
        *first.reservoir_maxima_micro[1:],
    )
    with pytest.raises(rw.ResidualWorldError, match="reservoir maxima hash"):
        rw.fold_dose_scientific_payload(replace(
            result,
            steps=(replace(
                first, reservoir_maxima_micro=poisoned_maxima
            ), *result.steps[1:]),
        ))
    with pytest.raises(rw.ResidualWorldError, match="complete no-good"):
        rw.fold_dose_scientific_payload(replace(
            result,
            steps=(replace(
                first,
                complete_no_goods=tuple(reversed(first.complete_no_goods)),
            ), *result.steps[1:]),
        ))
    assert first.treatment_pool_after is not None
    with pytest.raises(rw.ResidualWorldError, match="treatment pool/book"):
        rw.fold_dose_scientific_payload(replace(
            result,
            steps=(replace(
                first,
                treatment_pool_after=tuple(
                    reversed(first.treatment_pool_after)
                ),
            ), *result.steps[1:]),
        ))
    with pytest.raises(rw.ResidualWorldError, match="evidence manifest"):
        rw.fold_dose_scientific_payload(replace(
            result, pricing_evidence_manifest_sha256="0" * 64
        ))


def test_null_dose_binds_deterministic_empty_and_treatment_parity_receipts(
    monkeypatch, tmp_path,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, neither, _, _,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)
    monkeypatch.setattr(
        rw, "solve_residual_pricing", dose_fixture._fake_pricer(
            (neither[87],), []
        )
    )
    monkeypatch.setattr(
        rw, "_audit_pricing_evidence_semantics", lambda *args: None
    )
    result = rw.run_fold_doses(
        prepared,
        players,
        worlds,
        raw,
        controls,
        tags,
        selector,
        control_micro,
        evidence_root=tmp_path / "null-parity",
    )
    assert result.generated_columns == ()
    assert result.generated_selector_totals.shape == (0, 50_000)
    assert result.generated_micro_totals.shape == (0, 50_000)
    expected_empty = rw._validate_roster_micro_parity(
        players,
        raw,
        rw.to_micro_dk(raw),
        (),
        np.empty((0, 50_000), dtype=np.float32),
        np.empty((0, 50_000), dtype=np.int64),
    )
    expected_treatment = rw._validate_roster_micro_parity(
        players,
        raw,
        rw.to_micro_dk(raw),
        result.treatment_candidates,
        result.treatment_selector_totals,
        result.treatment_micro_totals,
    )
    assert result.generated_score_parity == expected_empty
    assert result.generated_score_parity_sha256 == expected_empty.sha256
    assert result.treatment_score_parity == expected_treatment
    assert result.treatment_score_parity_sha256 == expected_treatment.sha256

    payload = rw.fold_dose_scientific_payload(result)
    assert payload["generated_score_parity_sha256"] == expected_empty.sha256
    assert payload["generated_score_parity"] == (
        rw._score_parity_scientific_receipt(expected_empty)
    )
    assert payload["treatment_score_parity_sha256"] == expected_treatment.sha256
    assert payload["treatment_score_parity"] == (
        rw._score_parity_scientific_receipt(expected_treatment)
    )
    assert all(
        payload[name] is False for name in rw.UNLICENSED_SCIENTIFIC_FLAGS
    )
    with pytest.raises(
        rw.ResidualWorldError, match="score-parity receipt hash changed"
    ):
        rw.fold_dose_scientific_payload(replace(
            result, generated_score_parity_sha256="0" * 64
        ))


@pytest.mark.parametrize(
    ("poison_kind", "match"),
    (
        (
            "generated-selector",
            "selector totals do not reconstruct canonically",
        ),
        ("treatment-micro", "micro totals do not reconstruct"),
    ),
)
def test_final_aggregate_parity_rejects_generated_or_treatment_corruption(
    monkeypatch, tmp_path, poison_kind, match,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, neither, column_only, _,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)
    monkeypatch.setattr(
        rw, "solve_residual_pricing", dose_fixture._fake_pricer(
            (column_only[0], neither[87]), []
        )
    )
    monkeypatch.setattr(
        rw, "_audit_pricing_evidence_semantics", lambda *args: None
    )
    original_parity = rw._validate_roster_micro_parity
    generated_validations = 0

    def poison_final_parity(
        players_arg,
        raw_arg,
        player_micro_arg,
        identities,
        selector_arg,
        micro_arg,
    ):
        nonlocal generated_validations
        canonical = tuple(rw.canonical_identity(value) for value in identities)
        selector_values = selector_arg
        micro_values = micro_arg
        if canonical == (column_only[0],):
            generated_validations += 1
            if (
                poison_kind == "generated-selector"
                and generated_validations == 2
            ):
                selector_values = np.array(selector_arg, copy=True)
                selector_values[0, 0] = np.float32(-999.0)
        if (
            poison_kind == "treatment-micro"
            and len(canonical) == len(controls)
            and canonical != controls
        ):
            micro_values = np.array(micro_arg, copy=True)
            micro_values[0, 0] += 1
        return original_parity(
            players_arg,
            raw_arg,
            player_micro_arg,
            canonical,
            selector_values,
            micro_values,
        )

    monkeypatch.setattr(rw, "_validate_roster_micro_parity", poison_final_parity)
    with pytest.raises(rw.ResidualWorldError, match=match):
        rw.run_fold_doses(
            prepared,
            players,
            worlds,
            raw,
            controls,
            tags,
            selector,
            control_micro,
            evidence_root=tmp_path / poison_kind,
        )
    if poison_kind == "generated-selector":
        assert generated_validations == 2


def test_world_bound_defensively_copies_list_inputs_and_is_frozen():
    roster = list(dose_fixture._legal_rosters()[0])
    evidence = [
        dose_fixture._dummy_cbc_evidence("lower-quotient"),
        dose_fixture._dummy_cbc_evidence("lower-remainder"),
    ]
    bound = rw.WorldLegalBound(
        rw.WorldId("R0", 0),
        180_000_000,
        260_000_000,
        roster,
        list(roster),
        evidence,
        list(evidence),
    )
    expected_roster = tuple(sorted(roster))
    roster.clear()
    evidence.clear()
    assert bound.lower_roster == expected_roster
    assert bound.upper_roster == expected_roster
    assert len(bound.lower_evidence) == len(bound.upper_evidence) == 2
    assert isinstance(bound.lower_roster, tuple)
    assert isinstance(bound.lower_evidence, tuple)
    with pytest.raises(FrozenInstanceError):
        bound.lower_micro = 0


def test_prepared_scientific_hash_excludes_operational_solver_paths_and_times(
    monkeypatch,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, _, _, _,
    ) = dose_fixture._prepare_dose_fixture(monkeypatch)

    def relocate(evidence: rw.CbcSolveEvidence, suffix: str):
        return replace(
            evidence,
            evidence_directory=f"/machine-{suffix}/evidence",
            log_path=f"/machine-{suffix}/evidence/cbc.log",
            solution_path=f"/machine-{suffix}/evidence/model.sol",
            model_path=f"/machine-{suffix}/evidence/model.mps",
            cpu_seconds=Decimal("17.25"),
            wall_seconds=Decimal("19.75"),
        )

    relocated_bounds = tuple(
        replace(
            bound,
            lower_evidence=tuple(
                relocate(value, f"lower-{index}-{evidence_index}")
                for evidence_index, value in enumerate(bound.lower_evidence)
            ),
            upper_evidence=tuple(
                relocate(value, f"upper-{index}-{evidence_index}")
                for evidence_index, value in enumerate(bound.upper_evidence)
            ),
        )
        for index, bound in enumerate(prepared.reservoir_bounds)
    )
    relocated = rw.prepare_fold_reservoir(
        "A",
        players,
        worlds,
        raw,
        controls,
        tags,
        selector,
        control_micro,
        relocated_bounds,
    )
    original_payload = rw.prepared_fold_scientific_payload(prepared)
    relocated_payload = rw.prepared_fold_scientific_payload(relocated)
    assert relocated_payload == original_payload
    assert all(
        original_payload[name] is False
        for name in rw.UNLICENSED_SCIENTIFIC_FLAGS
    )
    assert rw.prepared_fold_sha256(relocated) == rw.prepared_fold_sha256(prepared)
    serialized = json.dumps(relocated_payload, sort_keys=True)
    assert "/machine-" not in serialized
    assert "cpu_seconds" not in serialized
    assert "wall_seconds" not in serialized


def test_prepared_scientific_hash_matches_in_two_fresh_processes(
    monkeypatch, tmp_path,
):
    prepared, *_ = dose_fixture._prepare_dose_fixture(monkeypatch)
    pickle_path = tmp_path / "prepared.pkl"
    pickle_path.write_bytes(pickle.dumps(prepared, protocol=5))
    command = [
        sys.executable,
        "-c",
        (
            "import pickle,sys;"
            "from nfl_dfs.research.residual_world_columns import "
            "prepared_fold_sha256;"
            "p=pickle.load(open(sys.argv[1],'rb'));"
            "print(prepared_fold_sha256(p))"
        ),
        str(pickle_path),
    ]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    observed = [
        subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        for _ in range(2)
    ]
    assert observed == [rw.prepared_fold_sha256(prepared)] * 2


def test_unlicensed_payload_validator_rejects_missing_or_nonliteral_false():
    valid = {
        name: False for name in rw.UNLICENSED_SCIENTIFIC_FLAGS
    }
    rw.validate_unlicensed_scientific_payload(valid)
    for name in rw.UNLICENSED_SCIENTIFIC_FLAGS:
        missing = dict(valid)
        missing.pop(name)
        poisoned_values = (missing, {**valid, name: True}, {**valid, name: "false"})
        for poisoned in poisoned_values:
            with pytest.raises(
                rw.ResidualWorldError,
                match="missing an exact false authorization flag",
            ):
                rw.validate_unlicensed_scientific_payload(poisoned)
