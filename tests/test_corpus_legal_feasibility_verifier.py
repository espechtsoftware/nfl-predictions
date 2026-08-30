"""Offline unit tests for the independent corpus authority verifier."""

from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path

import numpy as np
import pulp
import pytest

from nfl_dfs.research import corpus_legal_feasibility_verifier as verifier
from nfl_dfs.research import residual_world_columns as rw


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_SOURCE = (
    ROOT
    / "src"
    / "nfl_dfs"
    / "research"
    / "corpus_legal_feasibility_verifier.py"
)


def _identity(
    uri: str, raw: bytes, *, generation: str = "1"
) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _MemoryReader:
    def __init__(self, values: dict[tuple[str, str], bytes]) -> None:
        self.values = values
        self.calls: list[tuple[str, str]] = []

    def read_generation(self, *, uri: str, generation: str) -> bytes:
        self.calls.append((uri, generation))
        return self.values[(uri, generation)]


def _players(*, salary: int = 5_500) -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"),
        ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"),
        ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"),
        ("wr-a1", "WR", "A", "B", "g1"),
        ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"),
        ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"),
        ("te-a", "TE", "A", "B", "g1"),
        ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"),
        ("te-e", "TE", "E", "F", "g3"),
        ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"),
        ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted(
        (
            rw.PlayerSpec(player_id, position, team, opponent, game_id, salary)
            for player_id, position, team, opponent, game_id in rows
        ),
        key=lambda player: player.player_id,
    ))


def _clean_roster() -> tuple[str, ...]:
    return tuple(sorted((
        "q-a",
        "rb-a1",
        "rb-c",
        "wr-a1",
        "wr-a2",
        "wr-b",
        "wr-c1",
        "te-b",
        "dst-e",
    )))


def test_verifier_source_does_not_import_execution_helpers() -> None:
    tree = ast.parse(VERIFIER_SOURCE.read_text(encoding="utf-8"))
    forbidden = {
        "AuthorityBundle",
        "DraftAuthorityBundle",
        "SolverEvidenceShard",
        "audit_dk_classic",
        "build_fresh_legal_model",
        "cross_score_full_union",
        "default_cbc_solver",
        "finalize_generation_matrix",
        "first_occurrence_unique",
        "house_rule_violations",
        "select_exact80",
        "validate_canonical_batch_result",
        "validate_canonical_variant_result",
    }
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "nfl_dfs.research.corpus_legal_feasibility"
        for alias in node.names
    }
    assert not imported & forbidden
    assert imported == {
        "ATTEMPT_LEDGER_SCHEMA",
        "AUTHORITY_BUNDLE_SCHEMA",
        "BATCH_RESULT_SCHEMA",
        "CBC_OPTIONS",
        "CBC_OPTIONS_PAYLOAD",
        "CBC_THREADS",
        "DRAFT_AUTHORITY_BUNDLE_SCHEMA",
        "EVIDENCE_PACK_CODEC",
        "EVIDENCE_SHARDS_PER_TASK",
        "EVIDENCE_SHARDS_PER_VARIANT",
        "EVIDENCE_SHARD_VISITS",
        "MATRIX_AUTHORITY_SCHEMA",
        "MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES",
        "MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES",
        "MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES",
        "MAX_SOLVER_EVIDENCE_BYTES_PER_STAGE",
        "RUNTIME_POLICY_SCHEMA",
        "SOLVER_PROOF_SCHEMA",
        "SOURCE_COLUMN_ORDER",
        "VARIANT_RESULT_SCHEMA",
        "VISITS_PER_BLOCK",
        "WORLD_SCHEDULE_SCHEMA",
    }
    public = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "verify_corpus_legal_feasibility_authority"
    )
    assert [argument.arg for argument in public.args.kwonlyargs] == [
        "task_request_bytes",
        "task_result_identity",
        "evidence_contract_identity",
        "object_reader",
        "repository_root",
    ]
    source = VERIFIER_SOURCE.read_text(encoding="utf-8")
    assert "_read_bounded_evidence_file" not in source
    assert "compressed_inode" not in source
    assert "compressed_path" not in source
    assert "key in os.environ" not in source
    assert verifier._CODE_SOURCE_IMPLEMENTATION_PATHS == (
        "src/nfl_dfs/optimizer/lineup.py",
        "src/nfl_dfs/research/corpus_artifact_source_authority.py",
        "src/nfl_dfs/research/corpus_legal_feasibility.py",
        "src/nfl_dfs/research/corpus_legal_feasibility_verifier.py",
        "src/nfl_dfs/research/corpus_parametric_batch.py",
        "src/nfl_dfs/research/effective_policy_rule_inventory.py",
        "src/nfl_dfs/research/lr8_later_period_source.py",
        "src/nfl_dfs/research/residual_world_columns.py",
    )


def test_canonical_parser_rejects_duplicate_noncanonical_and_nonfinite() -> None:
    assert verifier._parse_canonical_json_bytes(
        b'{"a":1,"b":[false,null]}', label="test"
    ) == {"a": 1, "b": [False, None]}
    for raw in (
        b'{"a":1,"a":2}',
        b'{"b":2, "a":1}',
        b'{"a":NaN}',
    ):
        with pytest.raises(verifier.CorpusLegalFeasibilityVerificationError):
            verifier._parse_canonical_json_bytes(raw, label="test")


def test_independent_dk_and_house_audits() -> None:
    players = _players()
    roster = _clean_roster()
    assert verifier._audit_dk_classic(players, roster) == roster
    assert verifier._house_rule_violations(players, roster) == ()
    low_salary_players = _players(salary=5_000)
    assert verifier._house_rule_violations(
        low_salary_players, roster
    ) == ("min_lineup_salary",)
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="canonical sorted",
    ):
        verifier._audit_dk_classic(players, tuple(reversed(roster)))


def test_independent_dk_audit_accepts_one_game_across_two_teams() -> None:
    roster = tuple(sorted((
        "q-a", "rb-a1", "rb-a2", "rb-b", "wr-a1", "wr-a2", "wr-b",
        "te-a", "dst-b",
    )))
    assert verifier._audit_dk_classic(_players(), roster) == roster


def test_first_occurrence_union_is_stable_and_canonical() -> None:
    roster = _clean_roster()
    alternate = tuple(sorted((set(roster) - {"wr-c1"}) | {"wr-c2"}))
    unique, first = verifier._first_occurrence_unique(
        (roster, alternate, roster, alternate)
    )
    assert unique == (roster, alternate)
    assert first == (0, 1)


def test_float64_cross_score_hashes_all_50000_worlds() -> None:
    players = _players()
    roster = _clean_roster()
    alternate = tuple(sorted((set(roster) - {"wr-c1"}) | {"wr-c2"}))
    player_row = np.arange(len(players), dtype=np.float32)[:, None]
    world_column = (
        np.arange(verifier.EXPECTED_WORLD_COUNT, dtype=np.float32)[None, :]
        % np.float32(19.0)
    ) / np.float32(100.0)
    draws = np.ascontiguousarray(
        np.float32(8.0) + player_row / np.float32(10.0) + world_column
    )
    draws.flags.writeable = False
    scores = verifier._cross_score_full_union(
        players, draws, (roster, alternate)
    )
    assert scores.dtype == np.dtype(np.float64)
    assert scores.shape == (2, 50_000)
    assert scores.flags.writeable is False
    player_index = {
        player.player_id: index for index, player in enumerate(players)
    }
    expected = draws[
        [player_index[player_id] for player_id in roster]
    ].sum(axis=0, dtype=np.float64)
    np.testing.assert_array_equal(scores[0], expected)
    assert verifier._matrix_content_sha256(
        scores, dtype="float64-le"
    ) == verifier._matrix_content_sha256(scores.copy(), dtype="float64-le")


def test_direct_exact80_selector_uses_first_occurrence_final_tie() -> None:
    scores = np.zeros((80, verifier.EXPECTED_WORLD_COUNT), dtype=np.float64)
    scores[0, 0] = 200.0
    scores[1, 0] = 200.0
    receipt = verifier._select_exact80(scores)
    assert receipt["selected_indices"] == list(range(80))
    assert receipt["entry_count"] == 80
    assert receipt["world_count"] == 50_000


def test_full_batch_shape_rejects_missing_or_reordered_arm() -> None:
    verifier._require_full_batch_shape(verifier.PARAMETER_SET_ORDER)
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="all seven",
    ):
        verifier._require_full_batch_shape(verifier.PARAMETER_SET_ORDER[:-1])


def _terminal_fixture() -> tuple[
    bytes,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    str,
]:
    prefix = "gs://bucket/batch/task-0000/variants/"
    evidence_raw = b'{"evidence":"contract"}'
    evidence_identity = _identity(
        "gs://bucket/batch/governance/pre-run-evidence-contract.json",
        evidence_raw,
        generation="9",
    )
    authorities = {
        role: _identity(
            f"{prefix}authorities/{role}.json",
            f"authority-{role}".encode(),
        )
        for role in verifier._TASK_AUTHORITY_OBJECT_ROLES
    }
    runtime_rows = []
    result_rows = []
    task_variants = []
    for ordinal, parameter_set_id in enumerate(verifier.PARAMETER_SET_ORDER):
        policy_identity = _identity(
            f"{prefix}{parameter_set_id}/effective-policy.json",
            f"policy-{ordinal}".encode(),
        )
        result_identity = _identity(
            f"{prefix}{parameter_set_id}/result.json",
            f"result-{ordinal}".encode(),
        )
        runtime_rows.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "object_identity": policy_identity,
        })
        result_rows.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "object_identity": result_identity,
        })
        task_variants.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "effective_policy_receipt": policy_identity,
            "result_object": result_identity,
        })
    immutable_image = {
        "uri": "us-docker.pkg.dev/project/repo/image@sha256:" + "1" * 64,
        "digest": "sha256:" + "1" * 64,
    }
    request = {"task_index": 0, "task_request_sha256": "2" * 64}
    manifest = {
        "batch_manifest_sha256": "3" * 64,
        "common_law": {"immutable_image": immutable_image},
        "tasks": [{
            "task_sha256": "4" * 64,
            "variant_output_prefix": prefix,
        }],
    }
    execution = {
        "execution_id": "execution-1",
        "execution_uid": "uid-1",
        "attempt": 1,
        "retry_count": 0,
        "terminal_status": "succeeded",
        "terminal_receipt": {},
    }
    task_result = {
        "execution": execution,
        "variant_results": task_variants,
    }
    evidence_sha = "5" * 64
    body: dict[str, object] = {
        "schema": verifier.TASK_TERMINAL_SCHEMA,
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "evidence_contract_identity": evidence_identity,
        "evidence_contract_sha256": evidence_sha,
        "task_request_sha256": request["task_request_sha256"],
        "task_index": 0,
        "task_sha256": manifest["tasks"][0]["task_sha256"],
        "execution_id": execution["execution_id"],
        "execution_uid": execution["execution_uid"],
        "task_attempt": 0,
        "max_retries": 0,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "retried_count": 0,
        "completed_condition": "True",
        "strict_terminal_success": True,
        "runtime_image_terminal_verification": {
            "source_commit_sha": "6" * 40,
            "cloud_build_id": "12345678-1234-1234-1234-123456789abc",
            "immutable_image": immutable_image,
            "terminal_verification_required": True,
        },
        "ambient_score_relevant_keys_present": [],
        "authorities": authorities,
        "runtime_policy_objects": runtime_rows,
        "variant_result_objects": result_rows,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    terminal_sha = verifier._canonical_sha256(body)
    raw = verifier._canonical_json_bytes({
        **body, "terminal_receipt_sha256": terminal_sha,
    })
    terminal_identity = _identity(f"{prefix}task-terminal.json", raw)
    execution["terminal_receipt"] = terminal_identity
    return (
        raw,
        terminal_identity,
        request,
        manifest,
        task_result,
        evidence_identity,
        evidence_sha,
    )


def test_task_terminal_requires_zero_platform_attempt_and_retries() -> None:
    (
        raw,
        identity,
        request,
        manifest,
        task_result,
        evidence_identity,
        evidence_sha,
    ) = _terminal_fixture()
    parsed = verifier._validate_task_terminal_receipt(
        raw,
        terminal_identity=identity,
        request=request,
        manifest=manifest,
        task_result=task_result,
        evidence_contract_identity=evidence_identity,
        evidence_contract_sha256=evidence_sha,
    )
    assert parsed["strict_terminal_success"] is True

    for field in ("task_attempt", "max_retries", "retried_count"):
        changed = dict(parsed)
        changed.pop("terminal_receipt_sha256")
        changed[field] = 1
        changed_sha = verifier._canonical_sha256(changed)
        changed_raw = verifier._canonical_json_bytes({
            **changed, "terminal_receipt_sha256": changed_sha,
        })
        changed_identity = _identity(str(identity["uri"]), changed_raw)
        changed_result = {
            **task_result,
            "execution": {
                **task_result["execution"],
                "terminal_receipt": changed_identity,
            },
        }
        with pytest.raises(
            verifier.CorpusLegalFeasibilityVerificationError,
            match="terminal status/retry/license",
        ):
            verifier._validate_task_terminal_receipt(
                changed_raw,
                terminal_identity=changed_identity,
                request=request,
                manifest=manifest,
                task_result=changed_result,
                evidence_contract_identity=evidence_identity,
                evidence_contract_sha256=evidence_sha,
            )

    incomplete = dict(parsed)
    incomplete.pop("terminal_receipt_sha256")
    incomplete["variant_result_objects"] = incomplete[
        "variant_result_objects"
    ][:-1]
    incomplete_sha = verifier._canonical_sha256(incomplete)
    incomplete_raw = verifier._canonical_json_bytes({
        **incomplete,
        "terminal_receipt_sha256": incomplete_sha,
    })
    incomplete_identity = _identity(str(identity["uri"]), incomplete_raw)
    incomplete_result = {
        **task_result,
        "execution": {
            **task_result["execution"],
            "terminal_receipt": incomplete_identity,
        },
    }
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="all seven",
    ):
        verifier._validate_task_terminal_receipt(
            incomplete_raw,
            terminal_identity=incomplete_identity,
            request=request,
            manifest=manifest,
            task_result=incomplete_result,
            evidence_contract_identity=evidence_identity,
            evidence_contract_sha256=evidence_sha,
        )


def test_published_root_requires_all_70_generation_pinned_pairs() -> None:
    rows = []
    for ordinal in range(verifier.EVIDENCE_SHARDS_PER_TASK):
        compressed = _identity(
            f"gs://bucket/task/solver-evidence/shard-{ordinal:03d}.zlib",
            f"compressed-{ordinal}".encode(),
        )
        index = _identity(
            f"gs://bucket/task/solver-evidence/shard-{ordinal:03d}.index.json",
            f"index-{ordinal}".encode(),
        )
        rows.append({
            "global_shard_ordinal": ordinal,
            "compressed_object_identity": compressed,
            "index_object_identity": index,
            "index_sha256": "1" * 64,
            "index_object_sha256": index["sha256"],
            "shard_root_sha256": "2" * 64,
        })
    shards = verifier._normalize_published_shards({"published_shards": rows})
    assert len(shards) == 70
    assert shards[-1].global_shard_ordinal == 69

    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="all 70",
    ):
        verifier._normalize_published_shards({"published_shards": rows[:-1]})
    repeated = [dict(row) for row in rows]
    repeated[-1]["compressed_object_identity"] = rows[0][
        "compressed_object_identity"
    ]
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="URIs repeat",
    ):
        verifier._normalize_published_shards({"published_shards": repeated})

    (
        terminal_raw,
        terminal_identity,
        _,
        _,
        _,
        _,
        _,
    ) = _terminal_fixture()
    terminal = verifier._parse_self_hashed_payload(
        terminal_raw,
        label="task terminal receipt",
        hash_field="terminal_receipt_sha256",
    )
    overlap = [dict(row) for row in rows]
    overlap[0]["compressed_object_identity"] = terminal["authorities"][
        "source_binding"
    ]
    overlap_shards = verifier._normalize_published_shards({
        "published_shards": overlap,
    })
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="globally create-once unique",
    ):
        verifier._require_disjoint_task_output_uris(
            terminal=terminal,
            terminal_identity=terminal_identity,
            shards=overlap_shards,
        )


def test_task_verifier_requires_every_frozen_score_free_gate() -> None:
    rows = [{
        "id": gate_id,
        "required_for_outcome_read": True,
    } for gate_id in verifier._TASK_VERIFIER_GATE_IDS]
    contract = {"pre_outcome_gate_registry": rows}
    assert verifier._require_task_verifier_gates(contract) == (
        verifier._TASK_VERIFIER_GATE_IDS
    )

    contract["pre_outcome_gate_registry"] = rows[:-1]
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="omits a required",
    ):
        verifier._require_task_verifier_gates(contract)


def test_paired_relaxation_monotonicity_checks_every_aligned_visit() -> None:
    attempts = []
    for variant, parameter_set_id in enumerate(verifier.PARAMETER_SET_ORDER):
        for visit in range(2):
            attempts.append({
                "variant_ordinal": variant,
                "parameter_set_id": parameter_set_id,
                "visit_ordinal": visit,
                "world": {"block": "R0", "index": visit},
                "status": "optimal",
                "primary_optimum_micro": 100 + visit + variant,
            })
    summary = verifier._paired_primary_optimum_summary(
        attempts, visits_per_variant=2
    )
    assert summary["aligned_comparison_count"] == 12
    assert summary["all_deltas_nonnegative"] is True

    changed = [dict(row) for row in attempts]
    changed[2]["primary_optimum_micro"] = 99
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="monotonicity fails",
    ):
        verifier._paired_primary_optimum_summary(
            changed, visits_per_variant=2
        )


def test_outside_incumbent_law_gate_is_nonvacuous() -> None:
    roster = _clean_roster()
    incumbent = verifier._outside_law_nonvacuity_summary(
        _players(),
        (roster,),
        variant_ordinal=0,
        parameter_set_id="incumbent",
    )
    assert incumbent["outside_incumbent_law_unique_count"] == 0

    salary_relaxation = verifier._outside_law_nonvacuity_summary(
        _players(salary=5_000),
        (roster,),
        variant_ordinal=1,
        parameter_set_id="remove-salary-floor",
    )
    assert salary_relaxation["qualifying_witness_count"] == 1
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="nonvacuity fails",
    ):
        verifier._outside_law_nonvacuity_summary(
            _players(),
            (roster,),
            variant_ordinal=1,
            parameter_set_id="remove-salary-floor",
        )


def test_self_hashed_payload_and_generation_reader_fail_closed() -> None:
    body = {"schema": "test/v1", "value": 7}
    digest = verifier._canonical_sha256(body)
    raw = verifier._canonical_json_bytes({**body, "receipt_sha256": digest})
    assert verifier._parse_self_hashed_payload(
        raw, label="test receipt", hash_field="receipt_sha256"
    )["value"] == 7
    with pytest.raises(verifier.CorpusLegalFeasibilityVerificationError):
        verifier._parse_self_hashed_payload(
            verifier._canonical_json_bytes({
                **body, "receipt_sha256": "0" * 64,
            }),
            label="test receipt",
            hash_field="receipt_sha256",
        )

    retained = b"retained evidence"
    identity = _identity("gs://bucket/shard-000.zlib", retained, generation="7")
    reader = _MemoryReader({
        ("gs://bucket/shard-000.zlib", "7"): retained,
    })
    observed, normalized = verifier._read_generation_pinned_object(
        reader,
        identity,
        maximum_bytes=1024,
        label="test shard",
    )
    assert observed == retained
    assert normalized == identity
    assert reader.calls == [("gs://bucket/shard-000.zlib", "7")]

    poisoned = _MemoryReader({
        ("gs://bucket/shard-000.zlib", "7"): b"different evidence",
    })
    with pytest.raises(verifier.CorpusLegalFeasibilityVerificationError):
        verifier._read_generation_pinned_object(
            poisoned,
            identity,
            maximum_bytes=1024,
            label="test shard",
        )
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="byte bound",
    ):
        verifier._read_generation_pinned_object(
            reader,
            identity,
            maximum_bytes=len(retained) - 1,
            label="test shard",
        )
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="oversized",
    ):
        verifier.verify_corpus_legal_feasibility_authority(
            task_request_bytes=b"x" * (verifier.MAX_TASK_REQUEST_BYTES + 1),
            task_result_identity={},
            evidence_contract_identity={},
            object_reader=reader,
            repository_root=ROOT,
        )


def test_stage_receipt_requires_requested_and_host_watchdog_bounds() -> None:
    model = b"exact mps\n"
    solver = {
        "binary_sha256": "1" * 64,
        "options_sha256": "2" * 64,
    }
    receipt = {
        "stage": "lexicographic_combined_optimum",
        "status": "optimal",
        "pulp_status": 1,
        "pulp_solution_status": 1,
        "remaining_before_microseconds": 100_000_000,
        "cbc_requested_microseconds": 99_000_000,
        "host_watchdog_microseconds": 98_000_000,
        "elapsed_microseconds": 2_000_000,
        "remaining_after_microseconds": 97_000_000,
        "objective_sha256": "3" * 64,
        "witness_sha256": "4" * 64,
        "log_sha256": sha256(b"log").hexdigest(),
        "log_bytes": 3,
        "solution_sha256": sha256(b"solution").hexdigest(),
        "solution_bytes": 8,
        "model_sha256": sha256(model).hexdigest(),
        "model_bytes": len(model),
        "model_pre_exec_sha256": sha256(model).hexdigest(),
        "model_post_exit_sha256": sha256(model).hexdigest(),
        "model_regular_exclusive_inode": True,
        "model_path_command_bound": True,
        "raw_command_sha256": "5" * 64,
        "exact_terminal_record": "Result - Optimal solution found",
        "warning_or_forbidden_marker_detected": False,
        "solver_binary_sha256": solver["binary_sha256"],
        "solver_options_sha256": solver["options_sha256"],
    }
    verifier._validate_stage_receipt_common(
        receipt,
        expected_stage="lexicographic_combined_optimum",
        expected_status="optimal",
        expected_objective_sha256="3" * 64,
        expected_witness_sha256="4" * 64,
        expected_model=model,
        solver_authority=solver,
    )
    invalid = dict(receipt)
    invalid["host_watchdog_microseconds"] = 99_000_001
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="timing receipt",
    ):
        verifier._validate_stage_receipt_common(
            invalid,
            expected_stage="lexicographic_combined_optimum",
            expected_status="optimal",
            expected_objective_sha256="3" * 64,
            expected_witness_sha256="4" * 64,
            expected_model=model,
            solver_authority=solver,
        )


def test_cbc_log_parser_accepts_exact_suffix_and_terminal_newline(tmp_path) -> None:
    binary = Path(str(pulp.PULP_CBC_CMD(msg=False).path)).resolve()
    model = b"synthetic exact integer MPS\n"
    model_sha = sha256(model).hexdigest()
    model_path = tmp_path / f"{model_sha}.mps"
    model_path.write_bytes(model)
    solution_path = tmp_path / f"{model_sha}.sol"
    requested_microseconds = 1_000_000
    tokens = [
        str(binary),
        str(model_path),
        "-max",
        "-sec",
        "1.000000",
    ]
    for option in verifier.CBC_OPTIONS:
        name, value = option.split(" ", 1)
        tokens.extend((f"-{name}", value))
    tokens.extend((
        "-ratio",
        "0.0",
        "-allow",
        "0.0",
        "-threads",
        str(verifier.CBC_THREADS),
        "-timeMode",
        "elapsed",
        "-solve",
        "-printingOptions",
        "all",
        "-solution",
        str(solution_path),
    ))
    command = "command line - " + " ".join(tokens) + " (default strategy 1)"
    log = (
        command
        + "\nCoin0008I MODEL read with 0 errors\n"
        + "Result - Optimal solution found\n"
    ).encode("utf-8")
    receipt = {
        "raw_command_sha256": sha256(command.encode("utf-8")).hexdigest(),
        "cbc_requested_microseconds": requested_microseconds,
        "exact_terminal_record": "Result - Optimal solution found",
        "warning_or_forbidden_marker_detected": False,
    }
    solver = {
        "binary_sha256": sha256(binary.read_bytes()).hexdigest(),
    }

    verifier._validate_cbc_command_and_log(
        log,
        receipt=receipt,
        expected_status="optimal",
        model_sha256=model_sha,
        solver_authority=solver,
    )

    infeasible_terminal = "Problem is infeasible - 0.00 seconds"
    infeasible_log = (
        command
        + "\nCoin0008I MODEL read with 0 errors\n"
        + infeasible_terminal
        + "\n"
    ).encode("utf-8")
    verifier._validate_cbc_command_and_log(
        infeasible_log,
        receipt={
            **receipt,
            "exact_terminal_record": infeasible_terminal,
        },
        expected_status="infeasible",
        model_sha256=model_sha,
        solver_authority=solver,
    )

    missing_suffix_command = command.removesuffix(" (default strategy 1)")
    missing_suffix_log = log.replace(
        command.encode("utf-8"), missing_suffix_command.encode("utf-8"), 1
    )
    with pytest.raises(
        verifier.CorpusLegalFeasibilityVerificationError,
        match="default-strategy suffix",
    ):
        verifier._validate_cbc_command_and_log(
            missing_suffix_log,
            receipt={
                **receipt,
                "raw_command_sha256": sha256(
                    missing_suffix_command.encode("utf-8")
                ).hexdigest(),
            },
            expected_status="optimal",
            model_sha256=model_sha,
            solver_authority=solver,
        )
