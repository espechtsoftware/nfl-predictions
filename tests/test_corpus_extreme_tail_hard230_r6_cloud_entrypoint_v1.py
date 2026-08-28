from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from itertools import combinations, product
import json
from types import SimpleNamespace

import numpy as np
import pytest

import scripts.run_corpus_extreme_tail_hard230_r6_cloud_v1 as cli
from nfl_dfs.research import corpus_extreme_tail_hard230_population_successor_v1 as successor
from nfl_dfs.research import corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1 as cloud
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw


PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "hard230-r6-cloud-fixture/"
)


def _identity(
    path: str,
    generation: int = 1,
    *,
    raw: bytes | None = None,
) -> dict[str, object]:
    payload = raw if raw is not None else legal.canonical_json_bytes({"path": path})
    return {
        "uri": f"gs://hard230-r6-cloud-fixture/{path}",
        "generation": str(generation),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


class _Store:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}

    def seed(
        self, uri: str, value: object, *, generation: int
    ) -> dict[str, object]:
        raw = value if type(value) is bytes else legal.canonical_json_bytes(value)
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return dict(identity)

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.objects:
            prior, identity = self.objects[uri]
            if prior != raw:
                raise RuntimeError("create-once collision differs")
            return dict(identity)
        return self.seed(uri, raw, generation=len(self.objects) + 100)

    def read(self, identity: Mapping[str, object]) -> bytes:
        raw, retained = self.objects[str(identity["uri"])]
        if retained != identity:
            raise RuntimeError("generation-pinned identity differs")
        return raw


def _slate_ids() -> list[str]:
    return [
        f"{season}-w{week:02d}"
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]


def _panel() -> tuple[dict[str, object], list[dict[str, object]]]:
    accepted = []
    p0_identities = []
    for source_ordinal, slate in enumerate(_slate_ids()):
        arms = []
        for arm_ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER):
            identity = _identity(
                f"population/{slate}/{arm_id}.json",
                source_ordinal * 7 + arm_ordinal + 1,
            )
            if arm_ordinal == 0:
                p0_identities.append(identity)
            arms.append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": arm_id,
                "result_identity": identity,
            })
        accepted.append({
            "slate_id": slate,
            "lane_ordinal": 0 if source_ordinal < 28 else 1,
            "lane_id": "v12a" if source_ordinal < 28 else "v12b",
            "task_ordinal": source_ordinal if source_ordinal < 28 else source_ordinal - 28,
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": f"{source_ordinal + 1:064x}",
            "task_acceptance_identity": _identity(
                f"acceptance/{slate}.json", source_ordinal + 500
            ),
            "carrier_identity": _identity(
                f"carrier/{slate}.json", source_ordinal + 600
            ),
            "arms": arms,
        })
    body = {
        "schema_version": panel_index.PANEL_INDEX_SCHEMA,
        "publication_mode": panel_index.PUBLICATION_MODE,
        "panel_id": "v12:fixture",
        "artifact_source_authority_completion": _identity("source-completion.json", 2),
        "artifact_source_authority_completion_sha256": "a" * 64,
        "lane_count": 2,
        "lanes": [],
        "accepted_slate_count": 54,
        "accepted_slates": accepted,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": 54,
            "accepted_task_count": 54,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        **{field: False for field in panel_index._FALSE_PANEL_FIELDS},
    }
    body["panel_index_sha256"] = batch.canonical_sha256(body)
    assert set(body) == set(panel_index._PANEL_KEYS)
    return body, p0_identities


def _source_freeze() -> dict[str, object]:
    return {
        "freeze_sha256": "f" * 64,
        "slates": [{"slate_id": slate} for slate in _slate_ids()],
    }


def _prepare_fixture(monkeypatch: pytest.MonkeyPatch):
    store = _Store()
    panel, p0_identities = _panel()
    panel_identity = store.seed(
        "gs://hard230-r6-cloud-fixture/panel.json", panel, generation=10
    )
    freeze = _source_freeze()
    freeze_identity = store.seed(
        "gs://hard230-r6-cloud-fixture/later-source.json", freeze, generation=11
    )
    optimizer_identity = store.seed(
        "gs://hard230-r6-cloud-fixture/source.tar", b"source", generation=12
    )
    build_identity = store.seed(
        "gs://hard230-r6-cloud-fixture/build.json", {"complete": True}, generation=13
    )
    monkeypatch.setattr(
        cloud.decoder.later,
        "validate_source_freeze",
        lambda value, *, expected_freeze_sha256: value,
    )
    prepared = cloud.prepare_54_task_manifest_v1(
        panel_index_identity=panel_identity,
        later_source_freeze_identity=freeze_identity,
        optimizer_source_identity=optimizer_identity,
        terminal_build_receipt_identity=build_identity,
        output_prefix=PREFIX,
        source_commit_sha="1" * 40,
        immutable_image_digest="sha256:" + "2" * 64,
        reused_job_name="atlas-cbc-32g-full-2023-w8-v1",
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    manifest_raw = store.read(prepared["task_manifest_identity"])
    manifest = json.loads(manifest_raw.decode("utf-8"))
    return store, prepared, manifest, p0_identities


def test_preparation_publishes_one_fixed_54_task_manifest(monkeypatch) -> None:
    store, prepared, manifest, p0_identities = _prepare_fixture(monkeypatch)
    assert prepared["task_count"] == 54
    assert manifest["mode_id"] == cloud.MODE_ID
    assert manifest["one_manifest_one_mode"] is True
    assert manifest["task_count"] == 54
    assert [row["task_index"] for row in manifest["task_rows"]] == list(range(54))
    assert [row["slate_id"] for row in manifest["task_rows"]] == _slate_ids()
    assert [row["p0_population_receipt_identity"] for row in manifest["task_rows"]] == p0_identities
    config = prepared["cloud_run_job_configuration"]
    assert config["task_count"] == config["parallelism"] == 54
    assert config["max_retries"] == 0
    assert config["new_job_creation_allowed"] is False
    assert config["container_args"][-1] == "execute-task"

    repeated = cloud.prepare_54_task_manifest_v1(
        panel_index_identity=manifest["panel_index_identity"],
        later_source_freeze_identity=manifest["later_source_freeze_identity"],
        optimizer_source_identity=manifest["optimizer_source_identity"],
        terminal_build_receipt_identity=manifest["terminal_build_receipt_identity"],
        output_prefix=PREFIX,
        source_commit_sha="1" * 40,
        immutable_image_digest="sha256:" + "2" * 64,
        reused_job_name="atlas-cbc-32g-full-2023-w8-v1",
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    assert repeated["task_manifest_identity"] == prepared["task_manifest_identity"]


def test_preparation_rejects_panel_source_slate_order_drift(monkeypatch) -> None:
    store = _Store()
    panel, _ = _panel()
    panel_identity = store.seed("gs://hard230-r6-cloud-fixture/panel.json", panel, generation=1)
    freeze = _source_freeze()
    freeze["slates"][0], freeze["slates"][1] = freeze["slates"][1], freeze["slates"][0]
    freeze_identity = store.seed("gs://hard230-r6-cloud-fixture/source.json", freeze, generation=2)
    optimizer = store.seed("gs://hard230-r6-cloud-fixture/source.tar", b"source", generation=3)
    build = store.seed("gs://hard230-r6-cloud-fixture/build.json", {"ok": True}, generation=4)
    monkeypatch.setattr(
        cloud.decoder.later,
        "validate_source_freeze",
        lambda value, *, expected_freeze_sha256: value,
    )
    with pytest.raises(cloud.Hard230R6CloudEntrypointV1Error, match="order differs"):
        cloud.prepare_54_task_manifest_v1(
            panel_index_identity=panel_identity,
            later_source_freeze_identity=freeze_identity,
            optimizer_source_identity=optimizer,
            terminal_build_receipt_identity=build,
            output_prefix=PREFIX,
            source_commit_sha="1" * 40,
            immutable_image_digest="sha256:" + "2" * 64,
            reused_job_name="atlas-cbc-32g-full-2023-w8-v1",
            read_exact=store.read,
            publish_create_once=store.publish,
        )


def test_world_permutation_is_full_deterministic_and_identity_bound() -> None:
    common = {
        "slate_id": "2023-w01",
        "source_lineage": {"source": "fixture"},
        "p0_target_authority_identity": _identity("p0.json", 1),
        "population_receipt_identity": _identity("population.json", 2),
        "population_result_sha256": "a" * 64,
    }
    first_derivation, first = cloud.derive_world_permutation_v1(**common)
    second_derivation, second = cloud.derive_world_permutation_v1(**common)
    assert first == second
    assert first_derivation == second_derivation
    assert len(first) == 10_000
    assert sorted(first) == list(range(10_000))
    changed = deepcopy(common)
    changed["population_result_sha256"] = "b" * 64
    _, third = cloud.derive_world_permutation_v1(**changed)
    assert third != first


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"), ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"), ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"), ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"), ("rb-e", "RB", "E", "F", "g3"),
        ("wr-a1", "WR", "A", "B", "g1"), ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"), ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"), ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"), ("wr-f", "WR", "F", "E", "g3"),
        ("te-a", "TE", "A", "B", "g1"), ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"), ("te-d", "TE", "D", "C", "g2"),
        ("te-e", "TE", "E", "F", "g3"), ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"), ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game_id, 5_500)
        for player_id, position, team, opponent, game_id in rows
    ), key=lambda player: player.player_id))


def _legal_rosters(players: tuple[rw.PlayerSpec, ...], count: int) -> list[list[str]]:
    by_position = {
        position: [row.player_id for row in players if row.position == position]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    retained: list[list[str]] = []
    for qb, rbs, wrs, te, dst in product(
        by_position["QB"],
        combinations(by_position["RB"], 2),
        combinations(by_position["WR"], 4),
        by_position["TE"],
        by_position["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            audited = legal.audit_dk_classic(players, roster)
            legal._audit_profile_compliance(
                players, audited, legal.frozen_policy_profiles()[0]
            )
        except legal.CorpusLegalFeasibilityError:
            continue
        retained.append(list(audited))
        if len(retained) == count:
            return retained
    raise AssertionError("fixture lacks enough incumbent-legal rosters")


def _population_result(
    players: tuple[rw.PlayerSpec, ...], *, slate_id: str
) -> dict[str, object]:
    unique = _legal_rosters(players, 80)
    visits = [unique[index % len(unique)] for index in range(1_000)]
    body = {
        "schema": legal.VARIANT_RESULT_SCHEMA,
        "slate": {"season": 2023, "week": 1, "slate_id": slate_id},
        "later_source_freeze_manifest_sha256": "f" * 64,
        "artifact_sha256_by_block": {block: f"{index + 1:064x}" for index, block in enumerate(rw.WORLD_BLOCKS)},
        "task_source_binding": {"fixture": True},
        "visit_schedule_sha256": "1" * 64,
        "attempt_ledger_sha256": "2" * 64,
        "matrix_authority_sha256": "3" * 64,
        "solver_evidence_task_root_sha256": "4" * 64,
        "profile": {
            "ordinal": 0,
            "parameter_set_id": "incumbent",
            "parameter_set_sha256": "5" * 64,
        },
        "runtime_effective_policy": {"fixture": True},
        "coverage": {
            "scheduled_visits": 1_000,
            "attempted_visits": 1_000,
            "optimal_visits": 1_000,
            "unique_candidates": 80,
            "selected_entries": 80,
        },
        "variant_attempt_rows_sha256": "6" * 64,
        "visit_rosters": visits,
        "unique_rosters": unique,
        "first_occurrence_visit_indices": list(range(80)),
        "candidate_score_sha256": "7" * 64,
        "selector": {
            "candidate_count": 80,
            "world_count": 50_000,
            "entry_count": 80,
            "tail_line_dk": 194.0,
            "selected_indices": list(range(80)),
            "tie_law_applied": "fixture",
        },
        "selected_rosters": unique,
        "selected_score_sha256": "8" * 64,
        "house_rule_violation_census": {"fixture": True},
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["result_sha256"] = legal.canonical_sha256(body)
    return body


def test_execute_derives_exact_population_target_and_publishes_result(
    monkeypatch,
) -> None:
    store, prepared, manifest, _ = _prepare_fixture(monkeypatch)
    players = _players()
    population = _population_result(players, slate_id="2023-w01")
    population_identity = store.seed(
        manifest["task_rows"][0]["p0_population_receipt_identity"]["uri"],
        population,
        generation=int(manifest["task_rows"][0]["p0_population_receipt_identity"]["generation"]),
    )
    manifest["task_rows"][0]["p0_population_receipt_identity"] = population_identity
    manifest["task_rows_sha256"] = legal.canonical_sha256(manifest["task_rows"])
    manifest.pop("task_manifest_sha256")
    manifest["task_manifest_sha256"] = legal.canonical_sha256(manifest)
    manifest_raw = legal.canonical_json_bytes(manifest)
    manifest_uri = str(prepared["task_manifest_identity"]["uri"])
    store.objects[manifest_uri] = (
        manifest_raw,
        {
            "uri": manifest_uri,
            "generation": str(prepared["task_manifest_identity"]["generation"]),
            "sha256": sha256(manifest_raw).hexdigest(),
            "bytes": len(manifest_raw),
        },
    )
    manifest_identity = store.objects[manifest_uri][1]

    registry = tuple({
        "id": row.player_id, "pos": row.position, "team": row.team,
        "opp": row.opponent, "game_id": row.game_id, "salary": row.salary,
    } for row in players)
    source_sha = legal.canonical_sha256({"source": "fixture"})
    source_member_object = _identity("decoded/source-member.json", 50)
    source_member = {
        "member_id": "fixture-member",
        "slate_id": "2023-w01",
        "member_sha256": source_sha,
        "object_identity": source_member_object,
    }
    blocks = tuple({
        "block_id": block,
        "world_count": 10_000,
        "source_member_sha256": source_sha,
        "object_identity": _identity(f"decoded/{block}.npz", 60 + index),
    } for index, block in enumerate(rw.WORLD_BLOCKS))
    lineage = {
        "source_member_sha256": source_sha,
        "score_block_ids": list(rw.WORLD_BLOCKS),
        "score_block_identities_sha256": legal.canonical_sha256(blocks),
        "player_registry_sha256": legal.canonical_sha256(registry),
        "score_matrix_sha256": "9" * 64,
        "matrix_derivation_proof_identity_sha256": "a" * 64,
    }
    decoded = SimpleNamespace(
        players=players,
        player_registry=registry,
        score_matrix=np.zeros((len(players), 50_000), dtype="<i8"),
        source_lineage=lineage,
        source_member_identity=source_member,
        score_block_identities=blocks,
        score_matrix_identity={"matrix": "fixture"},
    )
    monkeypatch.setattr(cloud.decoder, "materialize_hard230_r6_source_v1", lambda **kwargs: decoded)
    observed: dict[str, object] = {}

    def fake_execute(**kwargs):
        observed.update(kwargs)
        root = {"schema": "fixture-process-root", "complete": True}
        root_identity = store.publish(
            f"{manifest['task_rows'][0]['task_output_prefix']}process/process-receipt.json",
            legal.canonical_json_bytes(root),
        )
        index = {"evidence_index_sha256": "b" * 64}
        index_identity = store.publish(
            f"{manifest['task_rows'][0]['task_output_prefix']}process/evidence-index.json",
            legal.canonical_json_bytes(index),
        )
        control = {
            "population_lineup_count": 80,
            "population_rosters_sha256": "c" * 64,
        }
        challenger = {
            "population_lineup_count": 79,
            "population_rosters_sha256": "d" * 64,
        }
        scientific = SimpleNamespace(receipt={
            "actual_shared_solver_call_count": 1_600,
            "hard230_exact_target_reached": False,
            "hard230_shortfall": 1,
            "score_blind_control_population": control,
            "hard230_challenger_population": challenger,
        })
        return SimpleNamespace(
            process_receipt={"process_receipt_sha256": "e" * 64},
            process_receipt_identity=root_identity,
            evidence_index=index,
            evidence_index_identity=index_identity,
            scientific_result=scientific,
        )

    monkeypatch.setattr(cloud.process, "execute_and_publish_process_v1", fake_execute)
    execution = cloud.execute_manifest_task_v1(
        manifest_identity=manifest_identity,
        task_index=0,
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    assert observed["p0_target_authority"]["retained_count"] == 80
    assert len(observed["world_permutation_authority"]["ordered_world_indices"]) == 10_000
    assert observed["process_budget"]["execution_mode"] == successor.RELEASE_EXECUTION_MODE
    assert execution.task_result["p0_target_count"] == 80
    assert execution.task_result["hard230_challenger_population_count"] == 79
    assert execution.task_result["hard230_shortfall"] == 1
    assert cloud.validate_task_result_v1(execution.task_result) == execution.task_result
    assert execution.task_result_identity["uri"].endswith("/task-result.json")


def test_run_authorization_and_task_result_tampering_fail_closed(monkeypatch) -> None:
    _, prepared, manifest, _ = _prepare_fixture(monkeypatch)
    authorization_raw = prepared["cloud_run_job_configuration"]["container_environment"][
        cloud.MANIFEST_IDENTITY_ENV
    ]
    assert json.loads(authorization_raw)["uri"].endswith("task-manifest.json")
    tampered = deepcopy(manifest)
    tampered["candidate_origin_id"] = "R1"
    tampered.pop("task_manifest_sha256")
    tampered["task_manifest_sha256"] = legal.canonical_sha256(tampered)
    run = cloud.build_run_authorization_v1(
        panel_index_identity=manifest["panel_index_identity"],
        later_source_freeze_identity=manifest["later_source_freeze_identity"],
        optimizer_source_identity=manifest["optimizer_source_identity"],
        terminal_build_receipt_identity=manifest["terminal_build_receipt_identity"],
        output_prefix=PREFIX,
        source_commit_sha="1" * 40,
        immutable_image_digest="sha256:" + "2" * 64,
        reused_job_name="atlas-cbc-32g-full-2023-w8-v1",
    )
    with pytest.raises(cloud.Hard230R6CloudEntrypointV1Error, match="replay differs"):
        cloud.validate_task_manifest_v1(tampered, run_authorization=run)


def test_cli_rejects_retry_attempt_before_scientific_execution(monkeypatch) -> None:
    monkeypatch.setenv(cloud.ENABLE_ENV, "1")
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "54")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "1")
    monkeypatch.setenv(
        cloud.MANIFEST_IDENTITY_ENV,
        legal.canonical_json_bytes(_identity("manifest.json", 1)).decode("utf-8"),
    )
    with pytest.raises(cli.RunHard230R6CloudV1Error, match="no-retry"):
        cli._execute_cloud_task(SimpleNamespace())
