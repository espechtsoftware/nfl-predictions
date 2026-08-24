from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from nfl_dfs.research import corpus_parametric_snapshot as snapshot
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
    first_occurrence_unique,
)
from nfl_dfs.research.corpus_parametric_batch import PARAMETER_SET_ORDER
from nfl_dfs.research import corpus_v12_import as v12


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}


def _roster(index: int) -> tuple[str, ...]:
    return tuple(sorted(f"p{index:02d}-{slot}" for slot in range(9)))


def _schedule() -> list[dict[str, object]]:
    return [
        {"block": block, "index": index}
        for block in rw.WORLD_BLOCKS
        for index in range(2)
    ]


def _variants() -> list[dict[str, object]]:
    schedule = _schedule()
    schedule_sha = canonical_sha256(schedule)
    variants = []
    for ordinal, arm_id in enumerate(PARAMETER_SET_ORDER):
        visits = [
            list(_roster((ordinal + visit) % 13))
            for visit in range(len(schedule))
        ]
        unique, first = first_occurrence_unique(visits)
        selected_indices = list(range(min(3, len(unique))))
        variants.append({
            "slate": dict(SLATE),
            "profile": {"ordinal": ordinal, "parameter_set_id": arm_id},
            "later_source_freeze_manifest_sha256": "a" * 64,
            "visit_schedule_sha256": schedule_sha,
            "visit_rosters": visits,
            "unique_rosters": [list(row) for row in unique],
            "first_occurrence_visit_indices": list(first),
            "selector": {"selected_indices": selected_indices},
            "selected_rosters": [list(unique[index]) for index in selected_indices],
            "result_sha256": f"{ordinal + 10:064x}",
            "candidate_score_sha256": f"{ordinal + 20:064x}",
            "selected_score_sha256": f"{ordinal + 30:064x}",
        })
    return variants


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _carrier(variants: list[dict[str, object]]) -> tuple[dict[str, object], bytes]:
    object_rows = []
    result_rows = []
    for ordinal, arm_id in enumerate(PARAMETER_SET_ORDER):
        result_raw = canonical_json_bytes(variants[ordinal])
        result_identity = _identity(
            f"gs://fixture/arms/{ordinal}/result.json", result_raw
        )
        object_rows.append({
            "ordinal": ordinal,
            "parameter_set_id": arm_id,
            "object_identity": result_identity,
        })
        result_rows.append({
            "ordinal": ordinal,
            "parameter_set_id": arm_id,
            "parameter_set_sha256": f"{ordinal + 100:064x}",
            "effective_policy_receipt": {"fixture": True},
            "result_object": result_identity,
        })
    body: dict[str, object] = {
        "schema_version": "fixture-v12-carrier/v1",
        "variant_result_objects": object_rows,
        "variant_results": result_rows,
    }
    body["task_result_sha256"] = canonical_sha256(body)
    return body, canonical_json_bytes(body)


def _acceptance(
    carrier_identity: dict[str, object], science_sha: str
) -> tuple[dict[str, object], bytes]:
    body = {
        "arm_census": [
            {
                "attempted_visits": 10,
                "optimal_visits": 10,
                "ordinal": ordinal,
                "parameter_set_id": arm_id,
                "scheduled_visits": 10,
                "selected_entries": 3,
                "unique_candidates": 10,
                "visit_roster_rows": 10,
            }
            for ordinal, arm_id in enumerate(PARAMETER_SET_ORDER)
        ],
        "carrier_identity": carrier_identity,
        "defects": [],
        "gate": "fixture-independent-acceptance",
        "passed": True,
        "science_projection_sha256": science_sha,
        "solver_all_optimal": True,
        "uses_realized_outcomes": False,
        "verifier_accepted": True,
    }
    return body, json.dumps(body, indent=2, sort_keys=True).encode()


def _transport_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _transport_sha(value: object) -> str:
    return sha256(_transport_bytes(value)).hexdigest()


def _evidence_identity(name: str) -> dict[str, object]:
    return _identity(f"gs://fixture/evidence/{name}.json", name.encode())


def _authoritative_acceptance(
    carrier_identity: dict[str, object], *, task_index: int = 0
) -> tuple[dict[str, object], bytes]:
    scheduler_sha = "2" * 64
    governance = {
        "governance_mode": "live-all-region-census",
        "deployment_attestation_sha256": None,
        "governance_observed_at_utc": "2026-08-24T12:00:00Z",
        "attestation_created_at_utc": None,
        "attestation_expires_at_utc": None,
        "scheduler_census_sha256": scheduler_sha,
    }
    terminal = {
        "execution_id": "verifier-1",
        "execution_name": "verifier-1",
        "execution_uid": "verifier-uid-1",
        "task_index": task_index,
        "phase": "verifier",
        "state": "True",
        "counters": {
            "succeeded": 1,
            "failed": 0,
            "cancelled": 0,
            "retried": 0,
        },
        "metadata_sha256": "3" * 64,
    }
    census = {
        "job": {
            "name": "fixture-job",
            "uid": "fixture-job-uid",
            "generation": "7",
            "observed_generation": "7",
            "spec_sha256": "4" * 64,
        },
        "phase": "verifier",
        "task_index": task_index,
        "execution_id": terminal["execution_id"],
        "execution_uid": terminal["execution_uid"],
        "execution_names": ["producer-1", "verifier-1"],
        "execution_census_sha256": "5" * 64,
        "scheduler_census_sha256": scheduler_sha,
        "launch_governance_authorization_sha256": _transport_sha(governance),
        "terminal_scheduler_census_sha256": scheduler_sha,
        "governance_authorization": governance,
        "all_regions_complete": True,
        "exactly_one_new_execution": True,
        "no_active_executions": True,
        "job_remains_parked": True,
    }
    body: dict[str, object] = {
        "schema_version": "corpus-parametric-task-acceptance/v1",
        "accepted_at_utc": "2026-08-24T12:00:00Z",
        "transport_contract": _evidence_identity("transport-contract"),
        "retrieval_task0_prerequisite_identity": _evidence_identity(
            "retrieval-prerequisite"
        ),
        "task_index": task_index,
        "task_sha256": "6" * 64,
        "producer_close": _evidence_identity("producer-close"),
        "science_terminal": _evidence_identity("science-terminal"),
        "task_result": carrier_identity,
        "verifier_worker_completion": _evidence_identity("verifier-completion"),
        "independent_verification": _evidence_identity(
            "independent-verification"
        ),
        "independent_verification_sha256": "7" * 64,
        "verifier_terminal_execution": terminal,
        "terminal_governance_census": census,
        "evidence_object_count": 140,
        "complete_evidence_receipt": True,
        "independent_verification_complete": True,
        "strict_verifier_terminal_success": True,
        "accepted": True,
        "partial_result": False,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    body["task_acceptance_sha256"] = _transport_sha(body)
    return body, _transport_bytes(body)


def test_reopen_reconciles_dual_carrier_and_binds_task_acceptance(
    monkeypatch,
) -> None:
    variants = _variants()
    carrier, carrier_raw = _carrier(variants)
    carrier_identity = _identity("gs://fixture/task/task-result.json", carrier_raw)
    science_sha = "f" * 64
    _, acceptance_raw = _acceptance(carrier_identity, science_sha)
    acceptance_identity = _identity(
        "gs://fixture/task/acceptance.json", acceptance_raw
    )
    store = {
        carrier_identity["uri"]: carrier_raw,
        acceptance_identity["uri"]: acceptance_raw,
    }

    monkeypatch.setattr(
        snapshot,
        "read_task_variant_results",
        lambda *args, **kwargs: (carrier, deepcopy(variants)),
    )
    monkeypatch.setattr(
        snapshot,
        "extract_task_science",
        lambda values: {"science_projection_sha256": science_sha},
    )
    imported = v12.reopen_v12_task(
        acceptance_receipt_identity=acceptance_identity,
        carrier_identity=carrier_identity,
        read_exact=lambda identity: store[str(identity["uri"])],
        require_authoritative=False,
    )
    receipt = imported.compatibility_receipt
    assert receipt["carrier_dialect"] == "dual-consistent"
    assert receipt["acceptance_dialect"] == "local-independent-gate-compatibility"
    assert receipt["authoritative_task_acceptance_verified"] is False
    assert receipt["acceptance_receipt_content_checks_passed"] is True
    assert receipt["independent_acceptance_authority_verified"] is False
    assert receipt["terminal_panel_membership_verified"] is False
    assert receipt["uses_realized_outcomes"] is False
    assert len(receipt["result_objects"]) == 7
    assert len(receipt["arms"]) == 7
    remainder = dict(receipt)
    retained = remainder.pop("compatibility_import_sha256")
    assert canonical_sha256(remainder) == retained


def test_reopen_accepts_authoritative_transport_terminal_and_binds_result(
    monkeypatch,
) -> None:
    variants = _variants()
    carrier, carrier_raw = _carrier(variants)
    carrier_identity = _identity("gs://fixture/task/task-result.json", carrier_raw)
    science_sha = "f" * 64
    acceptance, acceptance_raw = _authoritative_acceptance(carrier_identity)
    acceptance_identity = _identity(
        "gs://fixture/task/accepted-terminal.json", acceptance_raw
    )
    store = {
        carrier_identity["uri"]: carrier_raw,
        acceptance_identity["uri"]: acceptance_raw,
    }
    monkeypatch.setattr(
        snapshot,
        "read_task_variant_results",
        lambda *args, **kwargs: (carrier, deepcopy(variants)),
    )
    monkeypatch.setattr(
        snapshot,
        "extract_task_science",
        lambda values: {"science_projection_sha256": science_sha},
    )

    imported = v12.reopen_v12_task(
        acceptance_receipt_identity=acceptance_identity,
        carrier_identity=carrier_identity,
        read_exact=lambda identity: store[str(identity["uri"])],
        require_authoritative=True,
    )
    receipt = imported.compatibility_receipt
    assert receipt["acceptance_dialect"] == "transport-accepted-terminal-v1"
    assert receipt["acceptance_schema"] == (
        "corpus-parametric-task-acceptance/v1"
    )
    assert receipt["accepted_task_index"] == 0
    assert receipt["accepted_task_acceptance_sha256"] == acceptance[
        "task_acceptance_sha256"
    ]
    assert receipt["authoritative_task_acceptance_verified"] is True
    assert receipt["accepted_task_result_binding_verified"] is True
    assert receipt["independent_acceptance_authority_verified"] is True
    assert receipt["uses_realized_outcomes"] is False


def test_authoritative_terminal_rejects_self_hash_tamper_and_result_misbinding(
    monkeypatch,
) -> None:
    variants = _variants()
    carrier, carrier_raw = _carrier(variants)
    carrier_identity = _identity("gs://fixture/task/task-result.json", carrier_raw)
    science_sha = "f" * 64
    acceptance, _ = _authoritative_acceptance(carrier_identity)
    monkeypatch.setattr(
        snapshot,
        "read_task_variant_results",
        lambda *args, **kwargs: (carrier, deepcopy(variants)),
    )
    monkeypatch.setattr(
        snapshot,
        "extract_task_science",
        lambda values: {"science_projection_sha256": science_sha},
    )

    tampered = deepcopy(acceptance)
    tampered["accepted"] = False
    tampered_raw = _transport_bytes(tampered)
    tampered_identity = _identity(
        "gs://fixture/task/tampered-terminal.json", tampered_raw
    )
    tampered_store = {
        carrier_identity["uri"]: carrier_raw,
        tampered_identity["uri"]: tampered_raw,
    }
    with pytest.raises(v12.CorpusV12ImportError, match="self-hash differs"):
        v12.reopen_v12_task(
            acceptance_receipt_identity=tampered_identity,
            carrier_identity=carrier_identity,
            read_exact=lambda identity: tampered_store[str(identity["uri"])],
            require_authoritative=True,
        )

    misbound = deepcopy(acceptance)
    misbound["task_result"] = _evidence_identity("different-task-result")
    misbound_without_hash = {
        key: value
        for key, value in misbound.items()
        if key != "task_acceptance_sha256"
    }
    misbound["task_acceptance_sha256"] = _transport_sha(misbound_without_hash)
    misbound_raw = _transport_bytes(misbound)
    misbound_identity = _identity(
        "gs://fixture/task/misbound-terminal.json", misbound_raw
    )
    misbound_store = {
        carrier_identity["uri"]: carrier_raw,
        misbound_identity["uri"]: misbound_raw,
    }
    with pytest.raises(v12.CorpusV12ImportError, match="task result identities differ"):
        v12.reopen_v12_task(
            acceptance_receipt_identity=misbound_identity,
            carrier_identity=carrier_identity,
            read_exact=lambda identity: misbound_store[str(identity["uri"])],
            require_authoritative=True,
        )

    nonterminal = deepcopy(acceptance)
    nonterminal["verifier_terminal_execution"]["state"] = "False"
    nonterminal_without_hash = {
        key: value
        for key, value in nonterminal.items()
        if key != "task_acceptance_sha256"
    }
    nonterminal["task_acceptance_sha256"] = _transport_sha(
        nonterminal_without_hash
    )
    nonterminal_raw = _transport_bytes(nonterminal)
    nonterminal_identity = _identity(
        "gs://fixture/task/nonterminal-acceptance.json", nonterminal_raw
    )
    nonterminal_store = {
        carrier_identity["uri"]: carrier_raw,
        nonterminal_identity["uri"]: nonterminal_raw,
    }
    with pytest.raises(
        v12.CorpusV12ImportError, match="terminal execution binding differs"
    ):
        v12.reopen_v12_task(
            acceptance_receipt_identity=nonterminal_identity,
            carrier_identity=carrier_identity,
            read_exact=lambda identity: nonterminal_store[str(identity["uri"])],
            require_authoritative=True,
        )


def test_local_gate_receipt_cannot_satisfy_authoritative_import(monkeypatch) -> None:
    variants = _variants()
    carrier, carrier_raw = _carrier(variants)
    carrier_identity = _identity("gs://fixture/task/task-result.json", carrier_raw)
    science_sha = "f" * 64
    _, acceptance_raw = _acceptance(carrier_identity, science_sha)
    acceptance_identity = _identity(
        "gs://fixture/task/local-acceptance.json", acceptance_raw
    )
    store = {
        carrier_identity["uri"]: carrier_raw,
        acceptance_identity["uri"]: acceptance_raw,
    }
    monkeypatch.setattr(
        snapshot,
        "read_task_variant_results",
        lambda *args, **kwargs: (carrier, deepcopy(variants)),
    )
    monkeypatch.setattr(
        snapshot,
        "extract_task_science",
        lambda values: {"science_projection_sha256": science_sha},
    )
    with pytest.raises(v12.CorpusV12ImportError, match="compatibility-only"):
        v12.reopen_v12_task(
            acceptance_receipt_identity=acceptance_identity,
            carrier_identity=carrier_identity,
            read_exact=lambda identity: store[str(identity["uri"])],
            require_authoritative=True,
        )


def test_reopen_rejects_dual_binding_and_selected_book_drift(monkeypatch) -> None:
    variants = _variants()
    carrier, carrier_raw = _carrier(variants)
    carrier_identity = _identity("gs://fixture/task/task-result.json", carrier_raw)
    science_sha = "f" * 64
    _, acceptance_raw = _acceptance(carrier_identity, science_sha)
    acceptance_identity = _identity(
        "gs://fixture/task/acceptance.json", acceptance_raw
    )
    store = {
        carrier_identity["uri"]: carrier_raw,
        acceptance_identity["uri"]: acceptance_raw,
    }
    monkeypatch.setattr(
        snapshot,
        "extract_task_science",
        lambda values: {"science_projection_sha256": science_sha},
    )

    bad_carrier = deepcopy(carrier)
    bad_carrier["variant_results"][0]["result_object"] = deepcopy(
        bad_carrier["variant_results"][1]["result_object"]
    )
    monkeypatch.setattr(
        snapshot,
        "read_task_variant_results",
        lambda *args, **kwargs: (bad_carrier, deepcopy(variants)),
    )
    with pytest.raises(v12.CorpusV12ImportError, match="dual carrier"):
        v12.reopen_v12_task(
            acceptance_receipt_identity=acceptance_identity,
            carrier_identity=carrier_identity,
            read_exact=lambda identity: store[str(identity["uri"])],
            require_authoritative=False,
        )

    bad_variants = deepcopy(variants)
    bad_variants[0]["selected_rosters"][0] = list(_roster(99))
    monkeypatch.setattr(
        snapshot,
        "read_task_variant_results",
        lambda *args, **kwargs: (carrier, bad_variants),
    )
    with pytest.raises(v12.CorpusV12ImportError, match="selected book"):
        v12.reopen_v12_task(
            acceptance_receipt_identity=acceptance_identity,
            carrier_identity=carrier_identity,
            read_exact=lambda identity: store[str(identity["uri"])],
            require_authoritative=False,
        )


def test_candidate_provenance_uses_every_arm_and_block_occurrence() -> None:
    variants = _variants()
    provenance = v12.build_candidate_provenance(
        variants, visit_schedule=_schedule(), require_authoritative=False
    )
    candidates = provenance["candidates"]
    assert provenance["visit_occurrence_count"] == 70
    assert provenance["visits_per_block"] == 2
    assert [row["lineup_id"] for row in candidates] == sorted(
        row["lineup_id"] for row in candidates
    )
    roster_zero = list(_roster(0))
    row = next(row for row in candidates if row["roster_player_ids"] == roster_zero)
    expected_occurrences = [
        (ordinal, visit)
        for ordinal in range(7)
        for visit in range(10)
        if (ordinal + visit) % 13 == 0
    ]
    assert row["occurrence_count"] == len(expected_occurrences)
    assert sum(row["occurrence_counts_by_block"].values()) == len(
        expected_occurrences
    )
    assert row["source_arms"] == sorted({
        PARAMETER_SET_ORDER[ordinal] for ordinal, _ in expected_occurrences
    })
    assert provenance["uses_realized_outcomes"] is False


def test_candidate_provenance_rejects_schedule_and_dedup_drift() -> None:
    variants = _variants()
    wrong_schedule = deepcopy(_schedule())
    wrong_schedule[0]["index"] = 99
    with pytest.raises(v12.CorpusV12ImportError, match="schedule/slate/profile"):
        v12.build_candidate_provenance(
            variants, visit_schedule=wrong_schedule, require_authoritative=False
        )

    bad_variants = deepcopy(variants)
    bad_variants[3]["first_occurrence_visit_indices"][0] = 1
    with pytest.raises(v12.CorpusV12ImportError, match="first-occurrence"):
        v12.build_candidate_provenance(
            bad_variants, visit_schedule=_schedule(), require_authoritative=False
        )
