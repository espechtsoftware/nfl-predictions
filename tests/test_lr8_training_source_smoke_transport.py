from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import finish_lr8_training_source_smoke as transport  # noqa: E402


CODE_SHA = "a" * 40
IMAGE = transport.IMAGE_REPOSITORY + "@sha256:" + "b" * 64
BUILD_ID = "12345678-abcd-abcd-abcd-123456789abc"


def _cloudbuild() -> bytes:
    smoke = "\n".join(transport.REQUIRED_BUILD_SMOKES)
    return f"""
steps:
  - name: python:3.11-slim
    id: full-test-suite
    entrypoint: bash
    args: [-ceu, pytest]
  - name: gcr.io/cloud-builders/docker
    id: build-image
    args: [build, -t, '${{_IMAGE}}', .]
  - name: gcr.io/cloud-builders/docker
    id: smoke-atlas-mvp-runner
    entrypoint: bash
    args:
      - -ceu
      - |
        {smoke.replace(chr(10), chr(10) + '        ')}
images: ['${{_IMAGE}}']
timeout: 10800s
options:
  machineType: E2_HIGHCPU_8
""".encode()


def _git(_commit: str, path: str) -> bytes:
    if path == "cloudbuild.yaml":
        return _cloudbuild()
    return f"frozen:{path}\n".encode()


def _build() -> dict[str, object]:
    tag = transport._image_tag(CODE_SHA)
    steps = []
    for row in transport._expected_cloud_build_steps(tag):
        steps.append({**row, "status": "SUCCESS", "exitCode": 0})
    return {
        "id": BUILD_ID,
        "source": {"gitSource": {
            "url": transport.GIT_SOURCE_URL, "revision": CODE_SHA,
        }},
        "sourceProvenance": {"resolvedGitSource": {
            "url": transport.GIT_SOURCE_URL, "revision": CODE_SHA,
        }},
        "substitutions": {
            "_IMAGE": tag, "_CODE_SHA": CODE_SHA,
        },
        "steps": steps,
        "status": "SUCCESS",
        "images": [tag],
        "artifacts": {"images": [tag]},
        "timeout": "10800s",
        "options": {"machineType": "E2_HIGHCPU_8"},
        "serviceAccount": transport.BUILD_SERVICE_ACCOUNT,
        "logsBucket": transport.BUILD_LOGS_BUCKET,
        "results": {"images": [{
            "name": tag, "digest": IMAGE.rsplit("@", 1)[1],
        }]},
    }


def _job(*, generation: int, configured: bool) -> dict[str, object]:
    if configured:
        contract = transport._static_job_contract(
            code_sha=CODE_SHA, image=IMAGE,
        )
        task = {
            "containers": [{
                "image": contract["image"],
                "command": contract["command"],
                "args": contract["args"],
                "env": [
                    {"name": key, "value": value}
                    for key, value in contract["env"].items()
                ],
                "workingDir": "",
                "volumeMounts": [],
                "startupProbe": None,
                "resources": {"limits": contract["resources"]},
            }],
            "volumes": [],
            "maxRetries": 0,
            "timeoutSeconds": transport.TIMEOUT_SECONDS,
            "serviceAccountName": transport.SERVICE_ACCOUNT,
        }
        spec = {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": task},
        }}}
    else:
        spec = {"template": {"spec": {"old": True}}}
    return {
        "metadata": {
            "name": transport.JOB,
            "uid": transport.JOB_UID,
            "generation": generation,
        },
        "spec": spec,
    }


def _terminal_execution(manifest: dict[str, object], *, state: str = "True"):
    job = manifest["job"]
    contract = manifest["static_job_contract"]
    task = {
        "containers": [{
            "image": contract["image"],
            "command": contract["command"],
            "args": contract["args"],
            "env": [
                {"name": key, "value": value}
                for key, value in contract["env"].items()
            ],
            "workingDir": "",
            "volumeMounts": [],
            "startupProbe": None,
            "resources": {"limits": contract["resources"]},
        }],
        "volumes": [],
        "maxRetries": 0,
        "timeoutSeconds": transport.TIMEOUT_SECONDS,
        "serviceAccountName": transport.SERVICE_ACCOUNT,
    }
    status = {
        "conditions": [{"type": "Completed", "status": state}],
    }
    if state == "True":
        status.update({
            "succeededCount": 1,
            "completionTime": "2026-08-21T04:00:00Z",
        })
    elif state == "False":
        status.update({
            "failedCount": 1,
            "completionTime": "2026-08-21T04:00:00Z",
        })
    return {
        "metadata": {
            "name": transport.JOB + "-abcde",
            "generation": 1,
            "labels": {
                "run.googleapis.com/job": transport.JOB,
                "run.googleapis.com/jobUid": transport.JOB_UID,
                "run.googleapis.com/jobGeneration": job["generation"],
            },
        },
        "spec": {"taskCount": 1, "parallelism": 1, "template": {"spec": task}},
        "status": status,
    }


def _manifest() -> dict[str, object]:
    return transport._build_launch_manifest(
        code_sha=CODE_SHA,
        image=IMAGE,
        build_id=BUILD_ID,
        job=transport.JOB,
        job_uid=transport.JOB_UID,
        build_metadata=_build(),
        job_before=_job(generation=1, configured=False),
        job_after=_job(generation=2, configured=True),
        executions_before=[{
            "status": {"conditions": [{"type": "Completed", "status": "True"}]}
        }],
        executions_after=[{
            "status": {"conditions": [{"type": "Completed", "status": "True"}]}
        }],
        schedulers_before=[],
        schedulers_after=[],
        result_inventory_before=[],
        result_inventory_after=[],
        governance_inventory_before=[],
        governance_inventory_after=[],
        prepared_at="2026-08-21T03:00:00Z",
        git_source_loader=_git,
    )


def test_build_prepare_and_reuse_contract_fail_closed():
    assert transport._validate_build_metadata(
        _build(), build_id=BUILD_ID, image=IMAGE, code_sha=CODE_SHA,
        git_source_loader=_git,
    ) == transport._image_tag(CODE_SHA)
    manifest = _manifest()
    assert manifest["job"]["name"] == transport.JOB
    assert manifest["job"]["uid"] == transport.JOB_UID
    assert manifest["job"]["generation"] == "2"
    assert manifest["historical_outcome_lease_acquired"] is False
    assert manifest["source_contract"] == {
        "mode": "smoke", "season": 2019, "week": 1, "block": "R0",
        "projection_seed": 0, "worlds": 10_000,
        "unique_dk_only_optima": 40, "maximum_ordered_solves": 80,
        "target_player_labels_read": False,
        "candidate_labels_read": False, "actual_score_queried": False,
    }

    bad_build = deepcopy(_build())
    bad_build["source"]["gitSource"]["revision"] = "c" * 40
    with pytest.raises(transport.LR8SmokeTransportError, match="direct-Git"):
        transport._validate_build_metadata(
            bad_build, build_id=BUILD_ID, image=IMAGE, code_sha=CODE_SHA,
            git_source_loader=_git,
        )
    with pytest.raises(transport.LR8SmokeTransportError, match="name"):
        transport._job_name("some-other-idle-job")


@pytest.mark.parametrize("poison", ["active", "scheduled", "result", "governance"])
def test_preupdate_rejects_nonexclusive_reuse(poison: str):
    executions = [{
        "status": {"conditions": [{"type": "Completed", "status": "True"}]}
    }]
    schedulers: list[dict[str, object]] = []
    result: list[dict[str, object]] = []
    governance: list[dict[str, object]] = []
    if poison == "active":
        executions[0]["status"]["conditions"][0]["status"] = "Unknown"
    elif poison == "scheduled":
        schedulers.append({"httpTarget": {"uri": (
            "https://run.googleapis.com/apis/run.googleapis.com/v1/"
            f"namespaces/{transport.PROJECT}/jobs/{transport.JOB}:run"
        )}})
    elif poison == "result":
        result.append({"unexpected": True})
    else:
        governance.append({"unexpected": True})
    with pytest.raises(transport.LR8SmokeTransportError):
        transport._validate_prepare_inputs(
            code_sha=CODE_SHA, image=IMAGE, build_id=BUILD_ID,
            job=transport.JOB, job_uid=transport.JOB_UID,
            build_metadata=_build(), job_before=_job(
                generation=1, configured=False,
            ), executions_before=executions, schedulers_before=schedulers,
            result_inventory_before=result,
            governance_inventory_before=governance,
            git_source_loader=_git,
        )


def test_execution_truth_table_and_strict_terminal(monkeypatch: pytest.MonkeyPatch):
    manifest = _manifest()
    monkeypatch.setattr(
        transport, "_validate_launch_manifest", lambda value, **kwargs: value,
    )
    success = _terminal_execution(manifest)
    receipt = transport._strict_terminal_execution(
        success, execution=transport.JOB + "-abcde", manifest=manifest,
    )
    assert receipt["counters"] == {
        "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
    }
    for conditions, expected in (
        ([], "Unknown"),
        ([{"type": "Completed", "status": "Unknown"}], "Unknown"),
        ([{"type": "Completed", "status": "True"}], "True"),
        ([{"type": "Completed", "status": "False"}], "False"),
    ):
        value = _terminal_execution(manifest)
        value["status"] = {"conditions": conditions}
        state, _counts, _status = transport._validate_execution_contract(
            value, execution=transport.JOB + "-abcde", manifest=manifest,
        )
        assert state == expected
    duplicate = _terminal_execution(manifest)
    duplicate["status"]["conditions"].append(
        {"type": "Completed", "status": "True"}
    )
    with pytest.raises(transport.LR8SmokeTransportError, match="Completed"):
        transport._validate_execution_contract(
            duplicate, execution=transport.JOB + "-abcde", manifest=manifest,
        )


def _player_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    definitions = [
        ("qb-a", "QB"), ("qb-z", "QB"),
        *((f"rb-{index}", "RB") for index in range(5)),
        *((f"wr-{index}", "WR") for index in range(6)),
        *((f"te-{index}", "TE") for index in range(3)),
        *((f"dst-{index}", "DST") for index in range(2)),
    ]
    for index, (player_id, position) in enumerate(definitions):
        rows.append({
            "season": 2019, "week": 1, "id": player_id,
            "gsis_id": None if position == "DST" else player_id,
            "pos": position, "team": f"T{index:02d}",
            "opp": f"O{index:02d}", "game_id": f"g{index:02d}",
            "salary": 4_000, "mean_projection": 10.0,
        })
    return sorted(rows, key=lambda row: row["id"])


def _rosters() -> list[list[str]]:
    values = []
    for rbs, wrs, te, dst in product(
        combinations([f"rb-{index}" for index in range(4)], 2),
        combinations([f"wr-{index}" for index in range(6)], 3),
        [f"te-{index}" for index in range(3)],
        [f"dst-{index}" for index in range(2)],
    ):
        values.append(sorted(["qb-a", *rbs, "rb-4", *wrs, te, dst]))
        if len(values) == 40:
            return values
    raise AssertionError


def _result_fixture():
    objects: dict[str, bytes] = {}
    source_config = transport._source_config()
    specs = {
        spec.label: spec
        for spec in transport.source_runner._query_requests(source_config)
    }
    table_receipts = {
        table: {
            "table_id": table,
            "etag": "etag-" + sha256(table.encode()).hexdigest()[:12],
            "modified": "2026-08-21T02:00:00+00:00",
            "num_rows": 100,
            "schema_sha256": sha256(("schema:" + table).encode()).hexdigest(),
        }
        for table in (
            transport.CATALOG_TABLE, transport.CANDIDATE_TABLE,
            transport.PIT_TABLE, transport.TABPFN_TABLE,
        )
    }
    query_receipts = {
        label: {
            "job_id": spec.job_id,
            "location": spec.location,
            "query_sha256": spec.query_sha256,
            "parameters_sha256": spec.parameters_sha256,
            "created": "2026-08-21T02:00:00+00:00",
            "started": "2026-08-21T02:00:01+00:00",
            "ended": "2026-08-21T02:00:02+00:00",
            "total_bytes_processed": 100,
            "cache_hit": False,
            "error_result": None,
        }
        for label, spec in specs.items()
    }

    def put(uri: str, raw: bytes) -> dict[str, object]:
        objects[uri] = raw
        return {
            "uri": uri, "generation": "1", "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def extract(label: str, rows: list[dict[str, object]]):
        spec = specs[label]
        columns, _sort, filename = transport.source_runner._extract_contract(label)
        dependencies = transport.source_runner._table_dependencies(
            source_config, label,
        )
        body = {
            "schema": transport.source_runner.EXTRACT_VERSION,
            "label": label,
            "query": {
                "sql_sha256": spec.query_sha256,
                "parameters": transport.source_runner._parameter_payload(
                    spec.parameters
                ),
                "parameters_sha256": spec.parameters_sha256,
                "job_receipt": query_receipts[label],
            },
            "tables": [table_receipts[table] for table in dependencies],
            "columns": list(columns),
            "rows": rows,
            "rows_sha256": transport._sha_bytes(transport._canonical_json(rows)),
        }
        return put(
            f"{transport.RESULT_PREFIX}/extracts/{filename}",
            transport._canonical_json(body),
        )

    players = _player_rows()
    catalog_receipt = extract("canonical_catalog", players)
    incumbent_roster = sorted([
        "qb-z", "rb-0", "rb-1", "rb-4", "wr-0", "wr-1", "wr-2", "te-0",
        "dst-0",
    ])
    incumbent_receipt = extract("canonical_incumbents", [{
        "season": 2019, "week": 1, "cand_ix": 0, "players": incumbent_roster,
    }])
    pit_row = {column: None for column in transport.source_runner.PIT_COLUMNS}
    cache_row = {column: None for column in transport.source_runner.CACHE_COLUMNS}
    pit_receipt = extract("pit_panel_2019", [pit_row])
    cache_receipt = extract("tabpfn_2019", [cache_row])
    extracts = {
        "canonical_catalog": catalog_receipt,
        "canonical_incumbents": incumbent_receipt,
        "pit_panel_2019": pit_receipt,
        "tabpfn_2019": cache_receipt,
    }
    specs = transport._catalog_players(json.loads(objects[catalog_receipt["uri"]]))
    roster_values = _rosters()
    attempts = []
    requests = []
    candidates = []
    for index, roster in enumerate(roster_values):
        request_payload = {
            "season": 2019, "week": 1, "block": "R0",
            "projection_seed": 0, "world_index": index,
            "catalog_sha256": transport.training.catalog_sha256(specs),
            "player_scores_sha256": sha256(f"score-{index}".encode()).hexdigest(),
            "incumbent_no_goods_sha256": transport.training.identities_sha256(
                [incumbent_roster]
            ),
            "candidate_world_family": transport.training.CANDIDATE_WORLD_FAMILY,
            "role_belief_worlds_used": False,
            "hard_domain_id": transport.training.HARD_DOMAIN_ID,
            "former_house_rules_not_applied": list(
                transport.training.FORMER_HOUSE_RULES_NOT_APPLIED
            ),
        }
        request_sha = transport.training.canonical_sha256(request_payload)
        model_raw = f"mps-{index}".encode()
        domain_raw = transport._canonical_json({"domain": index})
        proof = {
            "schema": transport.exact_solvers.PROOF_SCHEMA,
            "solve_kind": transport.exact_solvers.TRAINING_SOLVE_KIND,
            "request_sha256": request_sha,
            "result": {
                "roster": roster, "objective_micro": 1_000_000 + index,
                "dk_classic_only": True,
                "incumbent_no_goods_enforced": True,
                "house_rules_applied": [],
            },
            "cbc_solve_evidence": [{
                "pulp_status": 1, "pulp_solution_status": 1, "threads": 1,
                "warm_start": False, "mip_start_sha256": None,
                "model_sha256": sha256(model_raw).hexdigest(),
                "variable_domain_manifest_sha256": sha256(domain_raw).hexdigest(),
            }],
        }
        base = f"{transport.RESULT_PREFIX}/solver-evidence/{request_sha}"
        receipts = [put(base + "/proof.json", transport._canonical_json(proof))]
        receipts.extend((
            put(base + "/00-cbc.log", f"log-{index}".encode()),
            put(base + "/00-model.sol", f"sol-{index}".encode()),
            put(base + "/00-model.mps", model_raw),
            put(base + "/00-variable-domain-manifest.json", domain_raw),
        ))
        attempts.append({
            "block": "R0", "projection_seed": 0, "world_index": index,
            "roster": roster, "objective_micro": 1_000_000 + index,
            "admitted_unique": True, "request_sha256": request_sha,
            "evidence_receipts": receipts,
            "evidence_manifest_sha256": transport.training.canonical_sha256(
                receipts
            ),
        })
        requests.append(request_payload)
        candidates.append({
            "season": 2019, "week": 1, "roster": roster,
            "anatomy_features": transport.training._anatomy_payload(  # noqa: SLF001
                transport.lr8.lineup_anatomy(specs, roster)
            ),
            "first_source_block": "R0", "first_source_world_index": index,
            "source_occurrences": [["R0", index]],
        })
    candidate_identities = [row["roster"] for row in candidates]
    anatomy = [{
        "roster": row["roster"], "features": row["anatomy_features"],
    } for row in candidates]
    legality = [{
        "roster": row["roster"],
        "hard_domain_id": transport.training.HARD_DOMAIN_ID,
        "dk_classic_legal": True, "former_house_rules_applied": [],
    } for row in candidates]
    world_order = list(range(transport.training.WORLDS_PER_BLOCK))
    smoke_freeze = {
        "version": transport.source_runner.SMOKE_SOLVE_FREEZE_VERSION,
        "season": 2019, "week": 1, "block": "R0", "projection_seed": 0,
        "source_environment_role_seed_nonoperative": (
            transport.training.BLOCK_SEED_PAIRS["R0"][1]
        ),
        "candidate_world_family": transport.training.CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "hard_domain_id": transport.training.HARD_DOMAIN_ID,
        "former_house_rules_not_applied": list(
            transport.training.FORMER_HOUSE_RULES_NOT_APPLIED
        ),
        "player_ids": [row.player_id for row in specs],
        "player_ids_sha256": transport.training.player_ids_sha256(
            [row.player_id for row in specs]
        ),
        "player_draws": {
            "dtype": "<f4", "shape": [len(specs), 10_000],
            "sha256": "d" * 64,
        },
        "world_order_law": transport.training.WORLD_ORDER_LAW,
        "world_order": world_order,
        "world_order_sha256": transport.training.canonical_sha256(world_order),
        "source_receipts": [pit_receipt, cache_receipt, catalog_receipt],
        "catalog_sha256": transport.training.catalog_sha256(specs),
        "incumbent_candidates_sha256": transport.training.identities_sha256(
            [incumbent_roster]
        ),
        "ordered_request_payloads": requests,
        "ordered_request_payloads_sha256": transport.training.canonical_sha256(
            requests
        ),
        "ordered_solve_attempt_count": 40,
        "ordered_solve_attempts": attempts,
        "ordered_solve_attempts_sha256": transport.training.canonical_sha256(
            attempts
        ),
        "unique_candidates": candidates,
        "unique_candidate_count": 40,
        "candidate_identities_sha256": transport.training.canonical_sha256(
            candidate_identities
        ),
        "anatomy_sha256": transport.training.canonical_sha256(anatomy),
        "legality_sha256": transport.training.canonical_sha256(legality),
    }
    freeze_receipt = put(
        transport.SMOKE_SOLVE_FREEZE_URI,
        transport._canonical_json(smoke_freeze),
    )
    manifest = {
        "version": transport.source_runner.RUNNER_VERSION,
        "mode": "smoke", "attempt_id": transport.ATTEMPT_ID,
        "canonical_panel_id": transport.training.CANONICAL_PANEL_ID,
        "lattice": [{"season": 2019, "weeks": [1], "blocks": ["R0"]}],
        "replay_environment": transport.source_runner.REPLAY_ENVIRONMENT,
        "table_receipts": table_receipts,
        "query_job_receipts": query_receipts,
        "extract_objects": extracts,
        "model_fits": {"2019": {
            "model_fit_input_sha256": "a" * 64,
            "model_fit_sha256": "b" * 64,
        }},
        "replay_blocks": [{
            "season": 2019, "block": "R0", "projection_seed": 0,
            "source_environment_role_seed_nonoperative": (
                transport.training.BLOCK_SEED_PAIRS["R0"][1]
            ),
            "slates": [{
                "season": 2019, "week": 1,
                "player_ids_sha256": smoke_freeze["player_ids_sha256"],
                "player_draws_sha256": smoke_freeze["player_draws"]["sha256"],
                "shape": smoke_freeze["player_draws"]["shape"],
            }],
        }],
        "solver_status": "exact_smoke_complete", "smoke_unique_candidates": 40,
        "training_source_freeze_object": None,
        "smoke_solve_freeze_object": freeze_receipt,
        "smoke_solve_freeze": {
            "block": "R0", "projection_seed": 0,
            "player_ids_sha256": smoke_freeze["player_ids_sha256"],
            "player_draws_sha256": smoke_freeze["player_draws"]["sha256"],
            "world_order_sha256": smoke_freeze["world_order_sha256"],
            "ordered_solve_attempt_count": 40,
            "ordered_solve_attempts_sha256": smoke_freeze[
                "ordered_solve_attempts_sha256"
            ],
            "unique_candidate_count": 40,
            "candidate_identities_sha256": smoke_freeze[
                "candidate_identities_sha256"
            ],
            "anatomy_sha256": smoke_freeze["anatomy_sha256"],
            "legality_sha256": smoke_freeze["legality_sha256"],
        },
        "prior_model_training_labels_queried": True,
        "prior_was_active_queried": True,
        "prior_model_training_seasons": {"2019": [2015, 2016, 2017, 2018]},
        "target_model_label_placeholders_all_null": True,
        "target_was_active_placeholder_all_null": True,
        "target_player_labels_read": False, "candidate_labels_read": False,
        "role_belief_worlds_used": False, "dst_correlated_draws_used": False,
        "build_slates_used": False, "actual_score_queried": False,
        "candidate_totals_queried": False, "y_dk_points_queried": False,
        "target_realized_labels_queried": False,
        "historical_candidate_label_read_licensed": False,
        "production_change_licensed": False,
    }
    manifest["manifest_sha256"] = transport._sha_bytes(
        transport._canonical_json(manifest)
    )
    put(transport.SMOKE_MANIFEST_URI, transport._canonical_json(manifest))
    inventory = []
    loaded = {}
    for uri in sorted(objects):
        metadata = {
            "uri": uri, "generation": "1", "metageneration": "1",
            "bytes": len(objects[uri]),
        }
        inventory.append(metadata)
        loaded[uri] = (metadata, objects[uri])
    return inventory, loaded, manifest, smoke_freeze


def test_independent_smoke_freeze_request_proof_and_inventory_replay():
    inventory, loaded, _manifest_value, _freeze = _result_fixture()
    manifest, freeze, replay = transport._validate_result_objects(
        inventory=inventory, loaded=loaded,
    )
    assert manifest["actual_score_queried"] is False
    assert freeze["unique_candidate_count"] == 40
    assert replay["proof_request_count"] == 40
    assert replay["unique_candidate_count"] == 40
    assert replay["retained_evidence_object_count"] == 200


@pytest.mark.parametrize("poison", ["request", "proof", "extra"])
def test_independent_smoke_replay_rejects_drift(poison: str):
    inventory, loaded, manifest, freeze = _result_fixture()
    if poison == "request":
        freeze = deepcopy(freeze)
        freeze["ordered_request_payloads"][0]["week"] = 2
        with pytest.raises(transport.LR8SmokeTransportError, match="request"):
            transport._replay_smoke_contract(
                manifest=manifest, smoke_freeze=freeze, loaded=loaded,
            )
    elif poison == "proof":
        proof_uri = next(uri for uri in loaded if uri.endswith("/proof.json"))
        metadata, raw = loaded[proof_uri]
        proof = json.loads(raw)
        proof["result"]["objective_micro"] += 1
        loaded[proof_uri] = (metadata, transport._canonical_json(proof))
        with pytest.raises(
            transport.LR8SmokeTransportError, match="evidence object|proof result",
        ):
            transport._replay_smoke_contract(
                manifest=manifest, smoke_freeze=freeze, loaded=loaded,
            )
    else:
        extra_uri = transport.RESULT_PREFIX + "/solver-evidence/extra.bin"
        raw = b"extra"
        loaded[extra_uri] = ({
            "uri": extra_uri, "generation": "1", "metageneration": "1",
            "bytes": len(raw),
        }, raw)
        with pytest.raises(transport.LR8SmokeTransportError, match="inventory"):
            transport._replay_smoke_contract(
                manifest=manifest, smoke_freeze=freeze, loaded=loaded,
            )


def test_finisher_reads_terminal_then_inventory_then_generation_pinned_bodies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    manifest = _manifest()
    execution = transport.JOB + "-abcde"
    events: list[str] = []
    manifest_raw = transport._canonical_json({"placeholder": "manifest"})
    freeze_raw = transport._canonical_json({"placeholder": "freeze"})
    metadata = [
        {"uri": transport.SMOKE_MANIFEST_URI, "generation": "1",
         "metageneration": "1", "bytes": len(manifest_raw)},
        {"uri": transport.SMOKE_SOLVE_FREEZE_URI, "generation": "1",
         "metageneration": "1", "bytes": len(freeze_raw)},
    ]
    metadata.sort(key=lambda row: row["uri"])
    bodies = {
        transport.SMOKE_MANIFEST_URI: manifest_raw,
        transport.SMOKE_SOLVE_FREEZE_URI: freeze_raw,
    }
    monkeypatch.setattr(
        transport, "_validate_launch", lambda out: (manifest, execution),
    )
    monkeypatch.setattr(
        transport, "_validate_launch_manifest", lambda value, **kwargs: value,
    )
    monkeypatch.setattr(
        transport, "_validate_result_objects", lambda **kwargs: (
            {"validated": True}, {"validated": True}, {"proof_request_count": 40},
        ),
    )
    (tmp_path / "manifest.json").write_bytes(transport._canonical_json(manifest))
    (tmp_path / "launch.sha256").write_text("mock launch ledger\n")

    def load_execution(_name: str):
        events.append("terminal")
        return _terminal_execution(manifest)

    def list_inventory(_prefix: str):
        events.append("inventory")
        return metadata

    def load_object(row):
        events.append("body:" + row["uri"])
        return row, bodies[row["uri"]]

    result = transport.finish(
        out=tmp_path, execution_loader=load_execution,
        inventory_loader=list_inventory, object_loader=load_object,
    )
    assert events[:2] == ["terminal", "inventory"]
    assert all(event.startswith("body:") for event in events[2:])
    assert result["historical_outcome_lease_acquired"] is False
    assert result["production_change_licensed"] is False


def test_shell_transport_is_update_only_no_lease_and_status_visible():
    launcher = (ROOT / "scripts/cloud_lr8_training_source_smoke.sh").read_text()
    watcher = (
        ROOT / "scripts/watch_lr8_training_source_smoke_queue.sh"
    ).read_text()
    assert "gcloud run jobs update" in launcher
    assert "gcloud run jobs execute" in launcher
    assert "gcloud run jobs create" not in launcher
    assert "gcloud run jobs deploy" not in launcher
    assert "gcloud run jobs delete" not in launcher
    assert "_CODE_SHA" not in launcher
    assert "historical_outcome_lease.py" not in launcher + watcher
    assert "--tasks 1 --parallelism 1" in launcher
    assert "--max-retries 0" in launcher
    assert 'printf \'%s %s %s\\n\'' in launcher
    assert "LR8 source smoke" in (
        ROOT / "scripts/chain_status.sh"
    ).read_text()
    assert transport.JOB in launcher + watcher
    assert transport.JOB_UID in launcher
    assert "watch_lr8_training_source_smoke_queue.sh" in (
        ROOT / "scripts/chain_status.sh"
    ).read_text() or "watch_[a-z0-9_]+\\.sh" in (
        ROOT / "scripts/chain_status.sh"
    ).read_text()
