from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import os
import shlex
import subprocess
import sys
from types import ModuleType

import pytest

from nfl_dfs.research import corpus_artifact_source_authority as authority
from nfl_dfs.research import corpus_expansion_build as expansion_build
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_parametric_batch import TASK_WORLD_SOURCE_ROLES


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_corpus_artifact_source_transport.py"
SHELL = ROOT / "scripts" / "cloud_corpus_artifact_source_v1_reuse.sh"
NOW = "2026-08-21T18:00:00+00:00"
ENABLED = {"CORPUS_ARTIFACT_SOURCE_AUTHORITY_ENABLED": "1"}
RUN_ID = "20260821-artifact-source-cloud-test-v1"
OUTPUT_PREFIX = f"gs://dedicated-source/output/{RUN_ID}/"
DELIVERY_PREFIX = f"gs://dedicated-source/delivery/{RUN_ID}/"
SERVICE_ACCOUNT = (
    "corpus-source-research@nfl-predictions-503414.iam.gserviceaccount.com"
)
JOB_NAME = "reused-source-job"
CODE_SHA = "a" * 40
IMAGE = f"us-central1-docker.pkg.dev/p/r/source@sha256:{'b' * 64}"
BUILD_ID = "12345678-abcd-abcd-abcd-123456789abc"


@pytest.fixture()
def transport() -> ModuleType:
    name = "run_corpus_artifact_source_transport_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    sys.modules[name] = imported
    spec.loader.exec_module(imported)
    return imported


def _base_source_lock(
    module: ModuleType,
) -> tuple[bytes, dict[str, object], dict[tuple[str, str], bytes]]:
    receipts: list[dict[str, object]] = []
    objects: dict[tuple[str, str], bytes] = {}
    for season, week in later.EXPECTED_SLATE_KEYS:
        for seed, block in enumerate(rw.WORLD_BLOCKS):
            ordinal = len(receipts)
            raw = f"npz-{ordinal:03d}-{block}".encode("ascii")
            artifact_sha = sha256(raw).hexdigest()
            uri = (
                f"gs://nfl-predictions-503414-raw/research/"
                f"production-law-dependence-runs/inputs/{season}/w{week:02d}/{block}.npz"
            )
            generation = str(100_000 + ordinal)
            receipts.append({
                "bytes": len(raw),
                "candidate_rows": 1,
                "generation": generation,
                "panel_run_id": later.SOURCE_PANELS[seed],
                "season": season,
                "seed": seed,
                "sha256": artifact_sha,
                "updated": "2026-08-21T00:00:00+00:00",
                "uri": uri,
                "week": week,
            })
            objects[(uri, generation)] = raw
    value = {
        "version": later.BASE_SOURCE_VERSION,
        "run_id": later.BASE_SOURCE_RUN_ID,
        "source_panels": list(later.SOURCE_PANELS),
        "slates": len(later.EXPECTED_SLATE_KEYS),
        "artifact_count": len(receipts),
        "artifact_receipts": receipts,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "uses_realized_outcomes": False,
    }
    raw = module.source.canonical_json_bytes(value)
    identity = {
        "uri": later.BASE_SOURCE_URI,
        "generation": later.BASE_SOURCE_GENERATION,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    objects[(str(identity["uri"]), str(identity["generation"]))] = raw
    return raw, identity, objects


def _plan(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], bytes, dict[tuple[str, str], bytes]]:
    repaired_ordinal = (
        later.EXPECTED_ARTIFACT_KEYS.index(later.REPAIRED_R3_KEY)
    )
    repaired_raw = f"npz-{repaired_ordinal:03d}-R3".encode("ascii")
    monkeypatch.setattr(
        later, "REPAIRED_R3_SHA256", sha256(repaired_raw).hexdigest()
    )
    raw, identity, objects = _base_source_lock(module)
    monkeypatch.setattr(module.source, "BASE_SOURCE_OBJECT", identity)
    plan = module.source.build_execution_plan(
        run_id=RUN_ID,
        registered_at="2026-08-21T00:00:00+00:00",
        source_snapshot_at="2026-08-21T01:00:00+00:00",
        output_prefix=OUTPUT_PREFIX,
        code_sha=CODE_SHA,
        image=IMAGE,
        job=JOB_NAME,
        base_source_lock_bytes=raw,
    )
    return plan, module.source.canonical_json_bytes(plan), objects


class FakeStorage:
    def __init__(
        self, module: ModuleType, initial: Mapping[tuple[str, str], bytes]
    ) -> None:
        self.module = module
        self.objects = dict(initial)
        self.current = {uri: generation for uri, generation in initial}
        self.next_generation = 900_000
        self.inventory_calls: list[str] = []

    def read(self, identity: Mapping[str, object]) -> bytes:
        retained = self.module.object_identity(identity, label="fake read")
        raw = self.objects[(str(retained["uri"]), str(retained["generation"]))]
        if (
            len(raw) != retained["bytes"]
            or sha256(raw).hexdigest() != retained["sha256"]
        ):
            raise self.module.CorpusArtifactSourceTransportError(
                "fake generation identity differs"
            )
        return raw

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if any(existing_uri == uri for existing_uri, _ in self.objects):
            raise self.module.CorpusArtifactSourceTransportError(
                "fake create-once collision"
            )
        generation = str(self.next_generation)
        self.next_generation += 1
        identity = self.module.identity_for_bytes(
            uri=uri, generation=generation, raw=raw
        )
        self.objects[(uri, generation)] = raw
        self.current[uri] = generation
        return identity

    def resolve_current(self, uri: str) -> tuple[Mapping[str, object], bytes]:
        generation = self.current[uri]
        return self.resolve_generation(uri, generation)

    def resolve_generation(
        self, uri: str, generation: str
    ) -> tuple[Mapping[str, object], bytes]:
        raw = self.objects[(uri, generation)]
        return self.module.identity_for_bytes(
            uri=uri, generation=generation, raw=raw
        ), raw

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        self.inventory_calls.append(prefix)
        rows = [
            {"uri": uri, "generation": generation, "bytes": len(raw)}
            for (uri, generation), raw in self.objects.items()
            if uri.startswith(prefix)
        ]
        return sorted(rows, key=lambda row: (row["uri"], row["generation"]))


def _build_metadata(module: ModuleType, *, include_smokes: bool = True) -> dict[str, object]:
    image_tag = IMAGE.rsplit("@", 1)[0] + ":source-test"
    command_sets = {
        "focused-corpus-research-tests": expansion_build.FOCUSED_TEST_COMMANDS,
        "smoke-corpus-artifact-source": expansion_build.SOURCE_SMOKE_COMMANDS,
        "smoke-corpus-parametric-expansion": (
            expansion_build.PARAMETRIC_SMOKE_COMMANDS
        ),
        "smoke-corpus-neo4j-transport": expansion_build.NEO4J_SMOKE_COMMANDS,
    }
    steps: list[dict[str, object]] = []
    for step_id, name, entrypoint in expansion_build.EXPECTED_STEP_SPECS:
        if step_id == "build-image":
            args = [
                "build", "-f", expansion_build.EXPANSION_DOCKERFILE,
                "-t", image_tag, ".",
            ]
        else:
            commands = tuple(
                tuple(image_tag if token == "${_IMAGE}" else token for token in row)
                for row in command_sets[step_id]
            )
            args = ["-ceu", "\n".join(shlex.join(row) for row in commands)]
        step: dict[str, object] = {"name": name, "id": step_id, "args": args}
        if entrypoint:
            step["entrypoint"] = entrypoint
        steps.append(step)
    if not include_smokes:
        steps.pop()
    for step in steps:
        step.update({"status": "SUCCESS", "exitCode": 0})
    return {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": {
            "revision": CODE_SHA,
            "url": module.EXPECTED_CODE_REPOSITORY,
        }},
        "sourceProvenance": {"resolvedGitSource": {
            "revision": CODE_SHA,
            "url": module.EXPECTED_CODE_REPOSITORY,
        }},
        "substitutions": {"_IMAGE": image_tag},
        "images": [image_tag],
        "artifacts": {"images": [image_tag]},
        "timeout": "10800s",
        "options": {
            "logging": "LEGACY", "machineType": "E2_HIGHCPU_8", "pool": {},
        },
        "results": {"images": [{
            "name": image_tag,
            "digest": IMAGE.rsplit("@", 1)[1],
        }]},
        "steps": steps,
    }


def _job(
    module: ModuleType, *, generation: str, parked: bool,
) -> dict[str, object]:
    container: dict[str, object] = {
        "image": IMAGE if parked else "old-image",
        "command": module.PARKED_COMMAND if parked else ["old"],
        "args": module.PARKED_ARGS if parked else ["old"],
        "env": [
            {"name": module.ENABLE_ENV, "value": "1"},
            {"name": module.IMAGE_ENV, "value": IMAGE},
            {"name": module.BUILD_ENV, "value": BUILD_ID},
            {"name": module.CODE_ENV, "value": CODE_SHA},
        ] if parked else [],
        "resources": {"limits": module.EXPECTED_RESOURCES},
    }
    return {
        "metadata": {
            "name": JOB_NAME,
            "uid": "job-uid-1",
            "generation": generation,
        },
        "spec": {"template": {
            "metadata": {
                "annotations": {
                    "run.googleapis.com/client-name": "gcloud",
                    "run.googleapis.com/client-version": "579.0.0",
                    "run.googleapis.com/execution-environment": "gen2",
                },
                "labels": {"client.knative.dev/nonce": "test-nonce"},
            },
            "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": module.EXPECTED_TIMEOUT_SECONDS,
                "serviceAccountName": SERVICE_ACCOUNT,
                "containers": [container],
            }},
        }}},
        "status": {
            "observedGeneration": generation,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _census_row(name: str, *, state: str = "True") -> dict[str, object]:
    return {
        "metadata": {"name": name},
        "status": {"conditions": [{"type": "Completed", "status": state}]},
    }


def _execution(
    module: ModuleType,
    contract: Mapping[str, object],
    *,
    intent_identity: Mapping[str, object],
    state: str,
) -> dict[str, object]:
    status: dict[str, object] = {
        "conditions": [{"type": "Completed", "status": state}],
    }
    if state == "True":
        status["succeededCount"] = 1
    return {
        "metadata": {
            "name": (
                f"projects/{module.PROJECT}/locations/{module.REGION}/jobs/"
                f"{JOB_NAME}/executions/{JOB_NAME}-abc12"
            ),
            "uid": "execution-uid-1",
            "labels": {
                "run.googleapis.com/job": JOB_NAME,
                "run.googleapis.com/jobUid": "job-uid-1",
                "run.googleapis.com/jobGeneration": "5",
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": module.EXPECTED_TIMEOUT_SECONDS,
                "serviceAccountName": SERVICE_ACCOUNT,
                "containers": [{
                    "image": IMAGE,
                    "command": module.PARKED_COMMAND,
                    "args": module.cloud_worker_args(
                        contract["plan_object"], intent_identity
                    ),
                    "env": [
                        {"name": module.ENABLE_ENV, "value": "1"},
                        {"name": module.IMAGE_ENV, "value": IMAGE},
                        {"name": module.BUILD_ENV, "value": BUILD_ID},
                        {"name": module.CODE_ENV, "value": CODE_SHA},
                    ],
                    "resources": {"limits": module.EXPECTED_RESOURCES},
                }],
            }},
        },
        "status": status,
    }


def _iam_evidence(
    module: ModuleType,
    storage: FakeStorage,
    plan: Mapping[str, object],
) -> dict[str, object]:
    _base, receipts, _raw = module._base_source_receipts(storage, plan)
    plan_uri = module._governance_uris(DELIVERY_PREFIX)["plan"]
    required = module._required_read_uris(
        plan_identity={
            "uri": plan_uri,
            "generation": "1",
            "sha256": "0" * 64,
            "bytes": 1,
        },
        plan=plan,
        receipts=receipts,
    ) + [module._governance_uris(DELIVERY_PREFIX)["launch_ledger"]]
    read_prefixes, read_exact_uris = module.derive_minimal_read_authority(
        required_read_uris=required,
        output_prefix=OUTPUT_PREFIX,
    )
    member = f"serviceAccount:{SERVICE_ACCOUNT}"
    roles = {
        module.STORAGE_GET_PERMISSION: (
            f"projects/{module.PROJECT}/roles/corpusSourceObjectGetV1"
        ),
        module.STORAGE_CREATE_PERMISSION: (
            f"projects/{module.PROJECT}/roles/corpusSourceObjectCreateV1"
        ),
        module.BIGQUERY_JOB_PERMISSION: (
            f"projects/{module.PROJECT}/roles/corpusSourceQueryJobV1"
        ),
        module.BIGQUERY_DATA_PERMISSION: (
            f"projects/{module.PROJECT}/roles/corpusSourceTableReadV1"
        ),
    }

    def expression(
        prefixes: Sequence[str], exact_uris: Sequence[str] = (),
    ) -> str:
        clauses = [
            f'resource.name.startsWith("{module._resource_prefix(prefix)}")'
            for prefix in prefixes
        ]
        clauses.extend(
            f'resource.name == "{module._resource_name(uri)}"'
            for uri in exact_uris
        )
        return " || ".join(clauses)

    by_bucket: dict[str, list[str]] = {}
    for prefix in read_prefixes:
        bucket = prefix.removeprefix("gs://").split("/", 1)[0]
        by_bucket.setdefault(bucket, []).append(prefix)
    exact_by_bucket: dict[str, list[str]] = {}
    for uri in read_exact_uris:
        bucket = uri.removeprefix("gs://").split("/", 1)[0]
        exact_by_bucket.setdefault(bucket, []).append(uri)
        by_bucket.setdefault(bucket, [])
    bucket_policies = []
    bucket_metadata = []
    for bucket in sorted(by_bucket):
        bindings: list[dict[str, object]] = [{
            "role": roles[module.STORAGE_GET_PERMISSION],
            "members": [member],
            "condition": {
                "title": module.RUNTIME_READ_CONDITION_TITLE,
                "expression": expression(
                    sorted(by_bucket[bucket]),
                    sorted(exact_by_bucket.get(bucket, [])),
                ),
            },
        }]
        if OUTPUT_PREFIX.startswith(f"gs://{bucket}/"):
            bindings.append({
                "role": roles[module.STORAGE_CREATE_PERMISSION],
                "members": [member],
                "condition": {
                    "title": module.RUNTIME_CREATE_CONDITION_TITLE,
                    "expression": expression([OUTPUT_PREFIX]),
                },
            })
        bucket_policies.append({
            "bucket": bucket,
            "policy": {
                "version": 3,
                "etag": f"policy-etag-{bucket}",
                "bindings": bindings,
            },
        })
        bucket_metadata.append({
            "bucket": bucket,
            "metadata": {
                "name": bucket,
                "etag": f"metadata-etag-{bucket}",
                "metageneration": "1",
                "iamConfiguration": {
                    "uniformBucketLevelAccess": {"enabled": True},
                    "publicAccessPrevention": "enforced",
                },
            },
        })

    def asset_result(
        role: str,
        resource: str,
        *,
        permission: str,
        title: str | None = None,
        prefixes: Sequence[str] = (),
        exact_uris: Sequence[str] = (),
    ) -> dict[str, object]:
        binding: dict[str, object] = {"role": role, "members": [member]}
        acl: dict[str, object] = {
            "accesses": [{"role": role}, {"permission": permission}],
            "resources": [{"fullResourceName": resource}],
        }
        if title is not None:
            binding["condition"] = {
                "title": title,
                "expression": expression(prefixes, exact_uris),
            }
            acl["conditionEvaluation"] = {"evaluationValue": "CONDITIONAL"}
        return {
            "accessControlLists": [acl],
            "attachedResourceFullName": resource,
            "fullyExplored": True,
            "nonCriticalErrors": [],
            "iamBinding": binding,
            "identityList": {
                "identities": [{"name": member}],
                "groupEdges": [],
            },
        }

    runtime_results = [asset_result(
        roles[module.BIGQUERY_JOB_PERMISSION],
        f"//cloudresourcemanager.googleapis.com/projects/{module.PROJECT}",
        permission=module.BIGQUERY_JOB_PERMISSION,
    )]
    runtime_results.extend(
        asset_result(
            roles[module.BIGQUERY_DATA_PERMISSION],
            "//bigquery.googleapis.com/projects/"
            + table.replace(".", "/datasets/", 1).replace(".", "/tables/", 1),
            permission=module.BIGQUERY_DATA_PERMISSION,
        )
        for table in module.QUERY_TABLES
    )
    for bucket in sorted(by_bucket):
        resource = f"//storage.googleapis.com/{bucket}"
        runtime_results.append(asset_result(
            roles[module.STORAGE_GET_PERMISSION],
            resource,
            permission=module.STORAGE_GET_PERMISSION,
            title=module.RUNTIME_READ_CONDITION_TITLE,
            prefixes=sorted(by_bucket[bucket]),
            exact_uris=sorted(exact_by_bucket.get(bucket, [])),
        ))
        if OUTPUT_PREFIX.startswith(f"gs://{bucket}/"):
            runtime_results.append(asset_result(
                roles[module.STORAGE_CREATE_PERMISSION],
                resource,
                permission=module.STORAGE_CREATE_PERMISSION,
                title=module.RUNTIME_CREATE_CONDITION_TITLE,
                prefixes=[OUTPUT_PREFIX],
            ))

    def asset_response(
        identity: str, results: Sequence[Mapping[str, object]]
    ) -> dict[str, object]:
        return {
            "fullyExplored": True,
            "nonCriticalErrors": [],
            "mainAnalysis": {
                "analysisQuery": {
                    "identitySelector": {"identity": identity},
                    "options": module._CLOUD_ASSET_OPTIONS,
                    "scope": f"projects/{module.PROJECT}",
                },
                "analysisResults": list(results),
                "fullyExplored": True,
                "nonCriticalErrors": [],
            },
        }

    body = {
        "schema_version": module.RUNTIME_IAM_SCHEMA,
        "captured_at_utc": NOW,
        "project": module.PROJECT,
        "service_account": SERVICE_ACCOUNT,
        "required_read_uris_sha256": module.canonical_sha256(sorted(required)),
        "read_prefixes": read_prefixes,
        "read_exact_uris": read_exact_uris,
        "read_authority_sha256": module.canonical_sha256({
            "read_prefixes": read_prefixes,
            "read_exact_uris": read_exact_uris,
        }),
        "output_prefix": OUTPUT_PREFIX,
        "query_tables": list(module.QUERY_TABLES),
        "project_policy": {
            "version": 1,
            "etag": "project-policy-etag",
            "bindings": [{
            "role": roles[module.BIGQUERY_JOB_PERMISSION],
            "members": [member],
            }],
        },
        "query_table_policies": [{
            "table": table,
            "policy": {
                "version": 1,
                "etag": f"table-policy-etag-{ordinal}",
                "bindings": [{
                "role": roles[module.BIGQUERY_DATA_PERMISSION],
                "members": [member],
                }],
            },
        } for ordinal, table in enumerate(module.QUERY_TABLES)],
        "custom_role_definitions": [
            {
                "name": role,
                "etag": f"role-etag-{ordinal}",
                "stage": "GA",
                "deleted": False,
                "includedPermissions": [permission],
            }
            for ordinal, (permission, role) in enumerate(
                sorted(roles.items(), key=lambda row: row[1])
            )
        ],
        "bucket_policies": bucket_policies,
        "bucket_metadata": bucket_metadata,
        "effective_access_analyses": {
            "runtime_identity": asset_response(member, runtime_results),
            "all_users": asset_response("allUsers", []),
            "all_authenticated_users": asset_response(
                "allAuthenticatedUsers", []
            ),
        },
    }
    return module._self_hash(body, field="iam_evidence_sha256")


def _public_principal_search_proof(
    module: ModuleType,
    identity: str,
) -> dict[str, object]:
    return {
        "schema_version": module.PUBLIC_PRINCIPAL_SEARCH_SCHEMA,
        "search_all_iam_policies_request": {
            "scope": f"projects/{module.PROJECT}",
            "query": f"policy:{identity}",
            "pageSize": module.PUBLIC_PRINCIPAL_SEARCH_PAGE_SIZE,
        },
        "search_all_iam_policies_response": {},
        "resource_manager_project": {
            "name": f"projects/{module.PROJECT_NUMBER}",
            "projectId": module.PROJECT,
            "state": "ACTIVE",
            "displayName": "NFL predictions",
            "createTime": "2025-01-01T00:00:00Z",
            "updateTime": "2026-08-21T18:00:00Z",
            "etag": "retained-project-etag",
        },
    }


def _query_rows(role: str) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for season, week in later.EXPECTED_SLATE_KEYS:
        player_id = f"player-{season}-{week:02d}"
        if role == "r0_candidates":
            rows.append({
                "panel_run_id": later.R0_PANEL,
                "season": season,
                "week": week,
                "cand_ix": 0,
                "players": [player_id],
                "score_artifact_uri": f"gs://candidate/{season}/w{week:02d}.npz",
                "score_artifact_sha256": sha256(
                    f"score-{season}-{week}".encode("ascii")
                ).hexdigest(),
            })
        elif role == "artifact_catalog":
            rows.append({
                "season": season,
                "week": week,
                "id": player_id,
                "pos": "QB",
                "team": "AAA",
                "opp": "BBB",
                "game_id": f"{season}_{week}_AAA_BBB",
                "salary": 5000,
            })
        else:
            rows.append({"season": season, "week": week, "id": player_id})
    return tuple(rows)


def _query_receipt(identity: Mapping[str, object]) -> dict[str, object]:
    return {
        "job_id": identity["job_id"],
        "location": identity["location"],
        "sql_sha256": identity["sql_sha256"],
        "parameters_sha256": identity["parameters_sha256"],
        "created": "2026-08-21T00:00:01+00:00",
        "started": "2026-08-21T00:00:02+00:00",
        "ended": "2026-08-21T00:00:03+00:00",
        "total_bytes_processed": 1,
        "cache_hit": False,
        "error_result": None,
    }


def _fake_source_freeze(
    module: ModuleType,
    plan: Mapping[str, object],
    storage: FakeStorage,
) -> dict[str, object]:
    _base, receipts, _raw = module._base_source_receipts(storage, plan)
    slates = []
    for task_index, (season, week) in enumerate(later.EXPECTED_SLATE_KEYS):
        task_receipts = []
        for role_index, (role, block) in enumerate(zip(
            TASK_WORLD_SOURCE_ROLES, rw.WORLD_BLOCKS, strict=True
        )):
            retained = receipts[task_index * 5 + role_index]
            task_receipts.append({
                "block": block,
                "uri": retained["uri"],
                "generation": retained["generation"],
                "sha256": retained["sha256"],
                "bytes": retained["bytes"],
            })
        slates.append({
            "season": season,
            "week": week,
            "slate_id": f"{season}-w{week:02d}",
            "artifact_receipts": task_receipts,
        })
    return {"slates": slates, "freeze_sha256": "c" * 64}


def _install_fake_semantics(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    source_freeze: Mapping[str, object],
) -> list[int]:
    verified_counts: list[int] = []
    completion = {
        "task_count": 54,
        "artifact_count": 270,
        "completion_sha256": "d" * 64,
    }
    completion_raw = module.canonical_json_bytes(completion)
    monkeypatch.setattr(
        module.later, "build_source_freeze", lambda **_kwargs: source_freeze
    )
    monkeypatch.setattr(
        module.authority,
        "validate_completion_bytes",
        lambda raw: module.strict_json_bytes(raw, label="fake completion"),
    )

    def fake_verify(**kwargs: object) -> bytes:
        count = 0
        for record in kwargs["artifact_bodies"]:
            assert isinstance(record, authority.RetainedArtifactBody)
            count += 1
        verified_counts.append(count)
        assert count == 270
        return completion_raw

    monkeypatch.setattr(
        module.authority,
        "verify_artifact_supported_source_authority",
        fake_verify,
    )
    return verified_counts


def _publish_source_terminal(
    module: ModuleType,
    storage: FakeStorage,
    plan: Mapping[str, object],
    source_freeze: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    uris = plan["publication_uris"]
    identities: dict[str, dict[str, object]] = {}
    raws: dict[str, bytes] = {}

    def publish(role: str, raw: bytes) -> dict[str, object]:
        identity = dict(storage.publish(str(uris[role]), raw))
        identities[role] = identity
        raws[role] = raw
        return identity

    publish(
        "prefix_claim",
        module.source.canonical_json_bytes(module.source.build_prefix_claim(plan)),
    )
    registration = plan["registration"]
    publish("registration", module.authority.canonical_json_bytes(registration))
    query_identities = module.source._query_identities(registration)
    captures: dict[str, dict[str, object]] = {}
    for role in module.source.QUERY_ROLES:
        capture = module.source.build_query_capture(
            role=role,
            query_identity=query_identities[role],
            query_outcome=module.source.QueryOutcome(
                rows=_query_rows(role),
                receipt=_query_receipt(query_identities[role]),
            ),
            registered_at=str(registration["registered_at"]),
        )
        captures[role] = capture
        publish(role, module.source.canonical_json_bytes(capture))
    source_raw = module.later.canonical_json(source_freeze)
    publish("later_source_freeze", source_raw)
    salary = module.source.build_salary_diagnostic(
        registration=registration,
        salary_capture=captures["salary_player_ids"],
    )
    publish("salary_diagnostic", module.authority.canonical_json_bytes(salary))
    completion = {
        "task_count": 54,
        "artifact_count": 270,
        "completion_sha256": "d" * 64,
    }
    publish(
        "source_authority_completion", module.canonical_json_bytes(completion)
    )
    before_roles = (
        "prefix_claim", "registration", *module.source.QUERY_ROLES,
        "later_source_freeze", "salary_diagnostic",
        "source_authority_completion",
    )
    plan_identity, _plan_raw = storage.resolve_current(
        module._governance_uris(DELIVERY_PREFIX)["plan"]
    )
    intent_identity, _intent_raw = storage.resolve_current(
        module._governance_uris(DELIVERY_PREFIX)["launch_ledger"]
    )
    _base, artifact_receipts, _base_raw = module._base_source_receipts(
        storage, plan
    )
    producer_sequence = [
        plan_identity,
        intent_identity,
        plan["base_source_lock_object"],
        identities["prefix_claim"],
        identities["registration"],
        *(identities[role] for role in module.source.QUERY_ROLES),
        identities["later_source_freeze"],
        identities["salary_diagnostic"],
        *(
            {
                key: receipt[key]
                for key in ("uri", "generation", "sha256", "bytes")
            }
            for receipt in artifact_receipts
        ),
        identities["source_authority_completion"],
        *(identities[role] for role in before_roles),
    ]
    producer_events = [
        {"ordinal": ordinal, "identity": identity}
        for ordinal, identity in enumerate(producer_sequence)
    ]
    producer_get_trace = module.source._self_hash({
        "schema": module.source.PRODUCER_GET_TRACE_SCHEMA,
        "delivered_plan_object": plan_identity,
        "delivered_intent_object": intent_identity,
        "events": producer_events,
        "event_count": len(producer_events),
        "events_sha256": module.source.canonical_sha256(producer_events),
        "absence_check_uris": list(
            module.source._publication_uris(OUTPUT_PREFIX).values()
        ),
        "object_list_used": False,
        "complete": True,
    }, field="trace_sha256")

    query_events: list[dict[str, object]] = []
    query_identities = module.source._query_identities(registration)
    query_specs = module.source._query_specs(registration)
    for role in module.source.QUERY_ROLES:
        query_events.append({
            "ordinal": len(query_events),
            "operation": "require-unused-job-id",
            "job_id": query_identities[role]["job_id"],
        })
    for role in module.source.QUERY_ROLES:
        sql, parameters = query_specs[role]
        query_events.append({
            "ordinal": len(query_events),
            "operation": "run-query",
            "role": role,
            "job_id": query_identities[role]["job_id"],
            "sql_sha256": sha256(sql.encode("utf-8")).hexdigest(),
            "parameters_sha256": module.source.canonical_sha256(
                list(parameters)
            ),
            "receipt_sha256": module.source.canonical_sha256(
                captures[role]["query_receipt"]
            ),
        })
    producer_query_trace = module.source._self_hash({
        "schema": module.source.PRODUCER_QUERY_TRACE_SCHEMA,
        "events": query_events,
        "event_count": len(query_events),
        "events_sha256": module.source.canonical_sha256(query_events),
        "complete": True,
    }, field="trace_sha256")
    publication = module.source._build_publication_completion(
        plan=plan,
        claim_identity=identities["prefix_claim"],
        registration_identity=identities["registration"],
        capture_identities={role: identities[role] for role in module.source.QUERY_ROLES},
        captures=captures,
        source_identity=identities["later_source_freeze"],
        source_freeze=source_freeze,
        salary_identity=identities["salary_diagnostic"],
        salary_diagnostic=salary,
        completion_identity=identities["source_authority_completion"],
        completion=completion,
        inventory_before_publication=module.source._inventory_rows(
            [identities[role] for role in before_roles]
        ),
        producer_get_trace=producer_get_trace,
        producer_query_trace=producer_query_trace,
    )
    publish(
        "publication_completion", module.source.canonical_json_bytes(publication)
    )
    return identities


def _configured(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    dict[str, object], FakeStorage, dict[str, object], dict[str, object],
    list[dict[str, object]],
]:
    plan, plan_raw, initial = _plan(module, monkeypatch)
    storage = FakeStorage(module, initial)
    baseline = [_census_row(f"{JOB_NAME}-old01")]
    configured = module.configure_transport(
        plan_raw=plan_raw,
        runtime_iam=_iam_evidence(module, storage, plan),
        delivery_prefix=DELIVERY_PREFIX,
        build_metadata=_build_metadata(module),
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        image=IMAGE,
        service_account=SERVICE_ACCOUNT,
        job_before=_job(module, generation="4", parked=False),
        job_after=_job(module, generation="5", parked=True),
        executions_before=baseline,
        executions_after=baseline,
        schedulers_before=[],
        schedulers_after=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        storage=storage,
        execute=True,
        environ=ENABLED,
    )
    contract_raw = storage.read(configured["transport_contract"])
    contract = module.validate_transport_contract(
        module.strict_json_bytes(contract_raw, label="configured contract")
    )
    return plan, storage, contract, configured, baseline


def test_configure_binds_exact_plan_raw_iam_build_job_and_pristine_prefixes(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, storage, contract, configured, baseline = _configured(
        transport, monkeypatch
    )
    assert configured["launch_permitted"] is False
    assert contract["plan_sha256"] == plan["plan_sha256"]
    assert contract["execution_names_before"] == [f"{JOB_NAME}-old01"]
    assert contract["job"]["generation"] == "5"
    assert contract["reuse_job_before"]["generation"] == "4"
    assert contract["service_account"] == SERVICE_ACCOUNT
    assert contract["worker_args"] == transport.cloud_worker_base_args(
        contract["plan_object"]
    )
    assert "--execute" not in contract["worker_args"]
    assert len(storage.inventory(DELIVERY_PREFIX)) == 3
    assert storage.inventory(OUTPUT_PREFIX) == []
    assert baseline[0]["status"]["conditions"][0]["status"] == "True"
    assert DELIVERY_PREFIX in storage.inventory_calls
    assert OUTPUT_PREFIX in storage.inventory_calls


def test_one_shot_launch_recover_bind_and_full_270_terminal_replay(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, storage, contract, configured, baseline = _configured(
        transport, monkeypatch
    )
    contract_identity = configured["transport_contract"]
    ready = transport.consume_launch(
        storage=storage,
        contract_identity=contract_identity,
        parked_job=_job(transport, generation="5", parked=True),
        executions=baseline,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert ready["launch_permitted"] is True
    assert ready["automatic_retry_licensed"] is False
    second = transport.consume_launch(
        storage=storage,
        contract_identity=contract_identity,
        parked_job=_job(transport, generation="5", parked=True),
        executions=baseline,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert second["launch_permitted"] is False
    assert second["worker_args"] == []
    assert second["recovery_action"] == "recover-only-never-relaunch"

    active_execution = _execution(
        transport,
        contract,
        intent_identity=ready["launch_ledger"],
        state="Unknown",
    )
    active_census = [*baseline, _census_row(f"{JOB_NAME}-abc12", state="Unknown")]
    recovered = transport.recover_execution_name(
        storage=storage,
        contract_identity=contract_identity,
        parked_job=_job(transport, generation="5", parked=True),
        executions=active_census,
        schedulers=[],
        all_regions_complete=True,
        execute=True,
        environ=ENABLED,
    )
    assert recovered["execution_id"] == f"{JOB_NAME}-abc12"
    assert recovered["census_only"] is True
    bound = transport.bind_execution(
        storage=storage,
        contract_identity=contract_identity,
        execution_metadata=active_execution,
        parked_job=_job(transport, generation="5", parked=True),
        executions=active_census,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert bound["execution_id"] == f"{JOB_NAME}-abc12"

    source_freeze = _fake_source_freeze(transport, plan, storage)
    replay_counts = _install_fake_semantics(
        transport, monkeypatch, source_freeze
    )
    publications = _publish_source_terminal(
        transport, storage, plan, source_freeze
    )
    terminal_execution = _execution(
        transport,
        contract,
        intent_identity=ready["launch_ledger"],
        state="True",
    )
    terminal_census = [*baseline, _census_row(f"{JOB_NAME}-abc12", state="True")]
    rogue = dict(storage.publish(OUTPUT_PREFIX + "rogue.json", b"rogue"))
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="rogue object",
    ):
        transport.accept_terminal(
            storage=storage,
            contract_identity=contract_identity,
            terminal_execution_metadata=terminal_execution,
            parked_job=_job(transport, generation="5", parked=True),
            executions=terminal_census,
            schedulers=[],
            all_regions_complete=True,
            accepted_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    storage.objects.pop((str(rogue["uri"]), str(rogue["generation"])))
    storage.current.pop(str(rogue["uri"]))

    completion_identity = publications["source_authority_completion"]
    completion_key = (
        str(completion_identity["uri"]), str(completion_identity["generation"])
    )
    retained_completion = storage.objects[completion_key]
    storage.objects[completion_key] = retained_completion.replace(b'"d', b'"e', 1)
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="completion differs|identity differs",
    ):
        transport.accept_terminal(
            storage=storage,
            contract_identity=contract_identity,
            terminal_execution_metadata=terminal_execution,
            parked_job=_job(transport, generation="5", parked=True),
            executions=terminal_census,
            schedulers=[],
            all_regions_complete=True,
            accepted_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    storage.objects[completion_key] = retained_completion
    accepted = transport.accept_terminal(
        storage=storage,
        contract_identity=contract_identity,
        terminal_execution_metadata=terminal_execution,
        parked_job=_job(transport, generation="5", parked=True),
        executions=terminal_census,
        schedulers=[],
        all_regions_complete=True,
        accepted_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert accepted["accepted"] is True
    assert accepted["partial_result"] is False
    assert accepted["source_authority_completion"] == publications[
        "source_authority_completion"
    ]
    assert replay_counts == [270, 270]
    assert len(storage.inventory(OUTPUT_PREFIX)) == 9
    assert len(storage.inventory(DELIVERY_PREFIX)) == 6


def test_raw_iam_replay_rejects_public_and_overbroad_roles(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, _plan_raw, initial = _plan(transport, monkeypatch)
    storage = FakeStorage(transport, initial)
    evidence = _iam_evidence(transport, storage, plan)
    _base, receipts, _raw = transport._base_source_receipts(storage, plan)
    required = transport._required_read_uris(
        plan_identity={
            "uri": transport._governance_uris(DELIVERY_PREFIX)["plan"],
            "generation": "1",
            "sha256": "0" * 64,
            "bytes": 1,
        },
        plan=plan,
        receipts=receipts,
    ) + [transport._governance_uris(DELIVERY_PREFIX)["launch_ledger"]]
    validated = transport.validate_runtime_iam_evidence(
        evidence,
        service_account=SERVICE_ACCOUNT,
        required_read_uris=required,
        output_prefix=OUTPUT_PREFIX,
    )
    assert validated["query_tables"] == list(transport.QUERY_TABLES)

    minimal_public = deepcopy(evidence)
    minimal_public.pop("iam_evidence_sha256")
    for key in ("all_users", "all_authenticated_users"):
        analysis = minimal_public["effective_access_analyses"][key]
        analysis.pop("nonCriticalErrors")
        main = analysis["mainAnalysis"]
        main.pop("nonCriticalErrors")
        main.pop("analysisResults")
        main["analysisQuery"].pop("options")
    minimal_public = transport._self_hash(
        minimal_public, field="iam_evidence_sha256"
    )
    transport.validate_runtime_iam_evidence(
        minimal_public,
        service_account=SERVICE_ACCOUNT,
        required_read_uris=required,
        output_prefix=OUTPUT_PREFIX,
    )

    public = dict(evidence)
    public.pop("iam_evidence_sha256")
    public["project_policy"] = {
        "version": evidence["project_policy"]["version"],
        "etag": evidence["project_policy"]["etag"],
        "bindings": [
        *evidence["project_policy"]["bindings"],
        {"role": "roles/viewer", "members": ["allUsers"]},
        ],
    }
    public = transport._self_hash(public, field="iam_evidence_sha256")
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="public principal",
    ):
        transport.validate_runtime_iam_evidence(
            public,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=required,
            output_prefix=OUTPUT_PREFIX,
        )

    broad = dict(evidence)
    broad.pop("iam_evidence_sha256")
    broad["project_policy"] = {
        "version": evidence["project_policy"]["version"],
        "etag": evidence["project_policy"]["etag"],
        "bindings": [{
            "role": "roles/editor",
            "members": [f"serviceAccount:{SERVICE_ACCOUNT}"],
        }],
    }
    broad = transport._self_hash(broad, field="iam_evidence_sha256")
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="overbroad",
    ):
        transport.validate_runtime_iam_evidence(
            broad,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=required,
            output_prefix=OUTPUT_PREFIX,
        )

    incomplete = deepcopy(evidence)
    incomplete.pop("iam_evidence_sha256")
    incomplete["effective_access_analyses"]["runtime_identity"][
        "fullyExplored"
    ] = False
    incomplete = transport._self_hash(
        incomplete, field="iam_evidence_sha256"
    )
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="incomplete or differs",
    ):
        transport.validate_runtime_iam_evidence(
            incomplete,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=required,
            output_prefix=OUTPUT_PREFIX,
        )

    effective_public = deepcopy(evidence)
    effective_public.pop("iam_evidence_sha256")
    effective_public["effective_access_analyses"]["all_users"][
        "mainAnalysis"
    ]["analysisResults"] = [{"retained": "public result"}]
    effective_public = transport._self_hash(
        effective_public, field="iam_evidence_sha256"
    )
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="public access exists",
    ):
        transport.validate_runtime_iam_evidence(
            effective_public,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=required,
            output_prefix=OUTPUT_PREFIX,
        )


def test_public_principal_search_fallback_is_bounded_and_fail_closed(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, plan_raw, initial = _plan(transport, monkeypatch)
    storage = FakeStorage(transport, initial)
    evidence = _iam_evidence(transport, storage, plan)
    fallback_body = deepcopy(evidence)
    fallback_body.pop("iam_evidence_sha256")
    fallback_body["effective_access_analyses"]["all_users"] = (
        _public_principal_search_proof(transport, "allUsers")
    )
    fallback_body["effective_access_analyses"]["all_authenticated_users"] = (
        _public_principal_search_proof(transport, "allAuthenticatedUsers")
    )
    fallback = transport._self_hash(
        fallback_body, field="iam_evidence_sha256"
    )

    _base, receipts, _raw = transport._base_source_receipts(storage, plan)
    required = transport._required_read_uris(
        plan_identity={
            "uri": transport._governance_uris(DELIVERY_PREFIX)["plan"],
            "generation": "1",
            "sha256": "0" * 64,
            "bytes": 1,
        },
        plan=plan,
        receipts=receipts,
    ) + [transport._governance_uris(DELIVERY_PREFIX)["launch_ledger"]]
    validated = transport.validate_runtime_iam_evidence(
        fallback,
        service_account=SERVICE_ACCOUNT,
        required_read_uris=required,
        output_prefix=OUTPUT_PREFIX,
    )
    assert validated == fallback

    capture_body = {
        "schema_version": transport.RUNTIME_IAM_CAPTURE_SCHEMA,
        "captured_at_utc": fallback["captured_at_utc"],
        "project": fallback["project"],
        **{
            key: deepcopy(fallback[key])
            for key in (
                "project_policy", "query_table_policies",
                "custom_role_definitions", "bucket_policies",
                "bucket_metadata", "effective_access_analyses",
            )
        },
    }
    capture = transport._self_hash(capture_body, field="capture_sha256")
    base_identity = plan["base_source_lock_object"]
    base_raw = initial[(
        str(base_identity["uri"]), str(base_identity["generation"])
    )]
    rebuilt = transport.build_runtime_iam_evidence(
        policy_capture=capture,
        plan_raw=plan_raw,
        base_source_lock_raw=base_raw,
        delivery_prefix=DELIVERY_PREFIX,
        service_account=SERVICE_ACCOUNT,
    )
    assert rebuilt["effective_access_analyses"] == (
        fallback["effective_access_analyses"]
    )

    tampered_capture = deepcopy(capture)
    tampered_capture["effective_access_analyses"]["all_users"][
        "search_all_iam_policies_request"
    ]["query"] = "policy:allAuthenticatedUsers"
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="policy capture self-hash differs",
    ):
        transport.build_runtime_iam_evidence(
            policy_capture=tampered_capture,
            plan_raw=plan_raw,
            base_source_lock_raw=base_raw,
            delivery_prefix=DELIVERY_PREFIX,
            service_account=SERVICE_ACCOUNT,
        )

    def wrong_scope(proof: dict[str, object]) -> None:
        proof["search_all_iam_policies_request"]["scope"] = (
            "projects/another-project"
        )

    def wrong_query(proof: dict[str, object]) -> None:
        proof["search_all_iam_policies_request"]["query"] = (
            "policy:allAuthenticatedUsers"
        )

    def wrong_page_size(proof: dict[str, object]) -> None:
        proof["search_all_iam_policies_request"]["pageSize"] = 499

    def nonempty_results(proof: dict[str, object]) -> None:
        proof["search_all_iam_policies_response"] = {
            "results": [{"resource": "//cloudresourcemanager.googleapis.com/x"}]
        }

    def response_field(field: str):
        def mutate(proof: dict[str, object]) -> None:
            proof["search_all_iam_policies_response"][field] = []

        return mutate

    def wrong_project_name(proof: dict[str, object]) -> None:
        proof["resource_manager_project"]["name"] = "projects/123456789"

    def wrong_project_id(proof: dict[str, object]) -> None:
        proof["resource_manager_project"]["projectId"] = "another-project"

    def inactive_project(proof: dict[str, object]) -> None:
        proof["resource_manager_project"]["state"] = "DELETE_REQUESTED"

    def parented_project(proof: dict[str, object]) -> None:
        proof["resource_manager_project"]["parent"] = "organizations/123"

    def truncated_project(proof: dict[str, object]) -> None:
        proof["resource_manager_project"].pop("state")

    def truncated_bundle(proof: dict[str, object]) -> None:
        proof.pop("resource_manager_project")

    cases = (
        ("scope", wrong_scope, "request for allUsers differs"),
        ("principal query", wrong_query, "request for allUsers differs"),
        ("page size", wrong_page_size, "request for allUsers differs"),
        (
            "nonempty",
            nonempty_results,
            "not a complete zero-result page",
        ),
        (
            "pagination",
            response_field("nextPageToken"),
            "not a complete zero-result page",
        ),
        (
            "unreachable",
            response_field("unreachable"),
            "not a complete zero-result page",
        ),
        (
            "errors",
            response_field("errors"),
            "not a complete zero-result page",
        ),
        (
            "API error",
            response_field("error"),
            "not a complete zero-result page",
        ),
        ("project number", wrong_project_name, "identity/state differs"),
        ("project ID", wrong_project_id, "identity/state differs"),
        ("project state", inactive_project, "identity/state differs"),
        ("project parent", parented_project, "must be parentless"),
        (
            "truncated project",
            truncated_project,
            "Resource Manager project fields differ",
        ),
        ("truncated bundle", truncated_bundle, "proof for allUsers fields differ"),
    )
    for label, mutate, expected_message in cases:
        candidate = deepcopy(fallback)
        candidate.pop("iam_evidence_sha256")
        proof = candidate["effective_access_analyses"]["all_users"]
        mutate(proof)
        candidate = transport._self_hash(
            candidate, field="iam_evidence_sha256"
        )
        try:
            transport.validate_runtime_iam_evidence(
                candidate,
                service_account=SERVICE_ACCOUNT,
                required_read_uris=required,
                output_prefix=OUTPUT_PREFIX,
            )
        except transport.CorpusArtifactSourceTransportError as exc:
            assert expected_message in str(exc), f"{label}: {exc}"
        else:
            pytest.fail(f"{label} public-principal proof was accepted")


def test_client_free_iam_builder_derives_exact_plan_and_270_object_boundary(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, plan_raw, initial = _plan(transport, monkeypatch)
    storage = FakeStorage(transport, initial)
    expected = _iam_evidence(transport, storage, plan)
    capture_body = {
        "schema_version": transport.RUNTIME_IAM_CAPTURE_SCHEMA,
        "captured_at_utc": expected["captured_at_utc"],
        "project": expected["project"],
        **{
            key: deepcopy(expected[key])
            for key in (
                "project_policy", "query_table_policies",
                "custom_role_definitions", "bucket_policies",
                "bucket_metadata", "effective_access_analyses",
            )
        },
    }
    capture = transport._self_hash(
        capture_body, field="capture_sha256"
    )
    base_identity = plan["base_source_lock_object"]
    base_raw = initial[(
        str(base_identity["uri"]), str(base_identity["generation"])
    )]

    rebuilt = transport.build_runtime_iam_evidence(
        policy_capture=capture,
        plan_raw=plan_raw,
        base_source_lock_raw=base_raw,
        delivery_prefix=DELIVERY_PREFIX,
        service_account=SERVICE_ACCOUNT,
    )

    assert rebuilt == expected
    assert len(rebuilt["read_prefixes"]) == len(later.EXPECTED_SLATE_KEYS)
    assert rebuilt["iam_evidence_sha256"] == expected["iam_evidence_sha256"]


def test_missing_build_smoke_and_partial_or_rogue_namespace_fail_closed(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="build step census/order differs",
    ):
        transport.validate_build_metadata(
            _build_metadata(transport, include_smokes=False),
            build_id=BUILD_ID,
            code_sha=CODE_SHA,
            image=IMAGE,
        )
    collision = _build_metadata(transport)
    collision["steps"][-1]["args"][-1] += " extra"
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="commands are not exact",
    ):
        transport.validate_build_metadata(
            collision,
            build_id=BUILD_ID,
            code_sha=CODE_SHA,
            image=IMAGE,
        )

    attached = _job(transport, generation="5", parked=True)
    task = attached["spec"]["template"]["spec"]["template"]["spec"]
    task["volumes"] = [{"name": "inherited", "secret": {"secret": "x"}}]
    task["containers"][0]["volumeMounts"] = [{
        "name": "inherited", "mountPath": "/secret"
    }]
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="attachment boundary",
    ):
        transport.validate_parked_job(
            attached,
            expected_job=transport.job_identity(attached),
            build={"image": IMAGE, "build_id": BUILD_ID, "code_sha": CODE_SHA},
            service_account=SERVICE_ACCOUNT,
        )

    for annotation in (
        "run.googleapis.com/vpc-access-connector",
        "run.googleapis.com/cloudsql-instances",
        "run.googleapis.com/network-interfaces",
    ):
        poisoned = _job(transport, generation="5", parked=True)
        poisoned["spec"]["template"]["metadata"]["annotations"][annotation] = (
            "inherited"
        )
        with pytest.raises(
            transport.CorpusArtifactSourceTransportError,
            match="template annotations.*fields differ",
        ):
            transport.validate_parked_job(
                poisoned,
                expected_job=transport.job_identity(poisoned),
                build={
                    "image": IMAGE,
                    "build_id": BUILD_ID,
                    "code_sha": CODE_SHA,
                },
                service_account=SERVICE_ACCOUNT,
            )

    for field, value in (
        ("startupProbe", {"tcpSocket": {"port": 8080}}),
        ("livenessProbe", {"httpGet": {"path": "/", "port": 8080}}),
        ("workingDir", "/tmp/inherited"),
        ("ports", [{"containerPort": 8080}]),
    ):
        poisoned = _job(transport, generation="5", parked=True)
        poisoned["spec"]["template"]["spec"]["template"]["spec"][
            "containers"
        ][0][field] = value
        with pytest.raises(
            transport.CorpusArtifactSourceTransportError,
            match="container attachment boundary",
        ):
            transport.validate_parked_job(
                poisoned,
                expected_job=transport.job_identity(poisoned),
                build={
                    "image": IMAGE,
                    "build_id": BUILD_ID,
                    "code_sha": CODE_SHA,
                },
                service_account=SERVICE_ACCOUNT,
            )

    networked = _job(transport, generation="5", parked=True)
    networked["spec"]["template"]["spec"]["template"]["spec"][
        "networkInterfaces"
    ] = [{"network": "default", "tags": ["inherited"]}]
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="task attachment boundary",
    ):
        transport.validate_parked_job(
            networked,
            expected_job=transport.job_identity(networked),
            build={"image": IMAGE, "build_id": BUILD_ID, "code_sha": CODE_SHA},
            service_account=SERVICE_ACCOUNT,
        )

    plan, plan_raw, initial = _plan(transport, monkeypatch)
    storage = FakeStorage(transport, initial)
    storage.publish(OUTPUT_PREFIX + "rogue.json", b"rogue")
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="not pristine",
    ):
        transport.configure_transport(
            plan_raw=plan_raw,
            runtime_iam=_iam_evidence(transport, storage, plan),
            delivery_prefix=DELIVERY_PREFIX,
            build_metadata=_build_metadata(transport),
            build_id=BUILD_ID,
            code_sha=CODE_SHA,
            image=IMAGE,
            service_account=SERVICE_ACCOUNT,
            job_before=_job(transport, generation="4", parked=False),
            job_after=_job(transport, generation="5", parked=True),
            executions_before=[],
            executions_after=[],
            schedulers_before=[],
            schedulers_after=[],
            all_regions_complete=True,
            created_at_utc=NOW,
            storage=storage,
            execute=True,
            environ=ENABLED,
        )

    _plan_value, partial_storage, _contract, partial_configured, baseline = (
        _configured(transport, monkeypatch)
    )
    partial_storage.publish(
        OUTPUT_PREFIX + "governance/prefix-claim.json", b"partial"
    )
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="not pristine",
    ):
        transport.consume_launch(
            storage=partial_storage,
            contract_identity=partial_configured["transport_contract"],
            parked_job=_job(transport, generation="5", parked=True),
            executions=baseline,
            schedulers=[],
            all_regions_complete=True,
            created_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )


def test_active_rogue_execution_and_scheduler_target_fail_closed(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _plan_value, storage, _contract, configured, baseline = _configured(
        transport, monkeypatch
    )
    contract_identity = configured["transport_contract"]
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="active execution",
    ):
        transport.consume_launch(
            storage=storage,
            contract_identity=contract_identity,
            parked_job=_job(transport, generation="5", parked=True),
            executions=[_census_row(f"{JOB_NAME}-old01", state="Unknown")],
            schedulers=[],
            all_regions_complete=True,
            created_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="scheduler targets",
    ):
        transport.consume_launch(
            storage=storage,
            contract_identity=contract_identity,
            parked_job=_job(transport, generation="5", parked=True),
            executions=baseline,
            schedulers=[{"httpTarget": {
                "uri": f"https://run.googleapis.com/jobs/{JOB_NAME}:run"
            }}],
            all_regions_complete=True,
            created_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    transport.consume_launch(
        storage=storage,
        contract_identity=contract_identity,
        parked_job=_job(transport, generation="5", parked=True),
        executions=baseline,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="exactly one new execution",
    ):
        transport.recover_execution_name(
            storage=storage,
            contract_identity=contract_identity,
            parked_job=_job(transport, generation="5", parked=True),
            executions=[
                *baseline,
                _census_row(f"{JOB_NAME}-abc12", state="Unknown"),
                _census_row(f"{JOB_NAME}-rogue", state="Unknown"),
            ],
            schedulers=[],
            all_regions_complete=True,
            execute=True,
            environ=ENABLED,
        )


def test_cli_gate_precedes_client_and_shell_has_separate_reuse_only_actions(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(transport.ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        transport,
        "GenerationPinnedStorage",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("GCS client must not be constructed")
        ),
    )
    with pytest.raises(
        transport.CorpusArtifactSourceTransportError,
        match="literal --execute",
    ):
        transport.main([
            "configure",
            "--plan-file", "/absent/plan.json",
            "--runtime-iam-file", "/absent/iam.json",
            "--delivery-prefix", DELIVERY_PREFIX,
            "--build-metadata-file", "/absent/build.json",
            "--build-id", BUILD_ID,
            "--code-sha", CODE_SHA,
            "--image", IMAGE,
            "--service-account", SERVICE_ACCOUNT,
            "--job-before-file", "/absent/job-before.json",
            "--job-after-file", "/absent/job-after.json",
            "--executions-before-file", "/absent/executions-before.json",
            "--executions-after-file", "/absent/executions-after.json",
            "--schedulers-before-file", "/absent/schedulers-before.json",
            "--schedulers-after-file", "/absent/schedulers-after.json",
            "--created-at-utc", NOW,
        ])

    build_file = tmp_path / "build.json"
    build_file.write_bytes(
        transport.canonical_json_bytes(_build_metadata(transport))
    )
    assert transport.main([
        "validate-build",
        "--build-metadata-file", str(build_file),
        "--build-id", BUILD_ID,
        "--code-sha", CODE_SHA,
        "--image", IMAGE,
    ]) == 0
    job_file = tmp_path / "job.json"
    job_file.write_bytes(
        transport.canonical_json_bytes(
            _job(transport, generation="5", parked=True)
        )
    )
    assert transport.main([
        "validate-parked-job",
        "--job-file", str(job_file),
        "--build-metadata-file", str(build_file),
        "--build-id", BUILD_ID,
        "--code-sha", CODE_SHA,
        "--image", IMAGE,
        "--service-account", SERVICE_ACCOUNT,
    ]) == 0

    source_text = SHELL.read_text(encoding="utf-8")
    for mode in ("configure", "consume-launch", "recover", "bind", "watch"):
        assert mode in source_text
    assert "gcloud run jobs update" in source_text
    assert "gcloud run jobs create" not in source_text
    assert "gcloud run jobs delete" not in source_text
    assert "gcloud run jobs replace" not in source_text
    assert "--clear-secrets" in source_text
    assert "--clear-volumes" in source_text
    assert "--clear-volume-mounts" in source_text
    assert "--clear-vpc-connector" in source_text
    assert "--clear-cloudsql-instances" in source_text
    assert "--clear-network" in source_text
    assert "--execution-environment" not in source_text
    assert "validate-build" in source_text
    assert "validate-parked-job" in source_text
    assert "rollback_existing_job" in source_text
    assert "run.googleapis.com/v1" in source_text
    assert "--max-retries 0" in source_text
    assert "--tasks 1" in source_text
    assert "--async" in source_text
    assert "ambiguous" in source_text and "never relaunch" in source_text
    assert "timestamp_for configured" in source_text
    assert "timestamp_for launch-consumed" in source_text
    assert "timestamp_for execution-bound" in source_text
    assert "timestamp_for terminal-accepted" in source_text
    assert "sleep " not in source_text


def test_shell_prevalidates_build_and_rolls_back_failed_configure(
    transport: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _plan_value, plan_raw, _initial = _plan(transport, monkeypatch)
    plan_file = tmp_path / "plan.json"
    plan_file.write_bytes(plan_raw)
    iam_file = tmp_path / "iam.json"
    iam_file.write_text("{}\n", encoding="utf-8")
    build_file = tmp_path / "build-source.json"
    build_file.write_bytes(
        transport.canonical_json_bytes(_build_metadata(transport))
    )
    prior = _job(transport, generation="4", parked=False)
    prior["metadata"]["resourceVersion"] = "rv4"
    updated = _job(transport, generation="5", parked=True)
    updated["metadata"]["resourceVersion"] = "rv5"
    restored = deepcopy(prior)
    restored["metadata"]["generation"] = "6"
    restored["metadata"]["resourceVersion"] = "rv6"
    restored["status"]["observedGeneration"] = "6"
    prior_file = tmp_path / "prior.json"
    updated_file = tmp_path / "updated.json"
    restored_file = tmp_path / "restored.json"
    for path, value in (
        (prior_file, prior),
        (updated_file, updated),
        (restored_file, restored),
    ):
        path.write_bytes(transport.canonical_json_bytes(value))

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state_file = tmp_path / "state.txt"
    log_file = tmp_path / "calls.log"
    fake_gcloud = fake_bin / "gcloud"
    fake_gcloud.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >>"$FAKE_LOG"
printf '%s\\n' ' '
if [[ "${1:-} ${2:-} ${3:-}" == "run jobs describe" ]]; then
  state="$(test -f "$FAKE_STATE" && command cat "$FAKE_STATE" || true)"
  if [[ "$state" == "rolledback" ]]; then
    command cat "$FAKE_RESTORED_JOB"
  elif [[ "$state" == "updated" ]]; then
    command cat "$FAKE_UPDATED_JOB"
  else
    command cat "$FAKE_PRIOR_JOB"
  fi
elif [[ "${1:-} ${2:-} ${3:-} ${4:-}" == "run jobs executions list" ]]; then
  printf '%s\\n' '[]'
elif [[ "${1:-} ${2:-} ${3:-}" == "scheduler locations list" ]]; then
  printf '%s\\n' '[{"locationId":"us-central1"}]'
elif [[ "${1:-} ${2:-} ${3:-}" == "scheduler jobs list" ]]; then
  printf '%s\\n' '[]'
elif [[ "${1:-} ${2:-}" == "builds describe" ]]; then
  command cat "$FAKE_BUILD"
elif [[ "${1:-} ${2:-} ${3:-}" == "run jobs update" ]]; then
  printf '%s\\n' updated >"$FAKE_STATE"
elif [[ "${1:-} ${2:-} ${3:-}" == "auth print-access-token " ]]; then
  printf '%s\\n' fake-token
elif [[ "${1:-} ${2:-}" == "auth print-access-token" ]]; then
  printf '%s\\n' fake-token
else
  printf '%s\\n' "unexpected fake gcloud call: $*" >&2
  exit 91
fi
""",
        encoding="utf-8",
    )
    fake_gcloud.chmod(0o755)
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
command cat >/dev/null
printf '%s\\n' "$*" >>"$FAKE_LOG"
printf '%s\\n' rolledback >"$FAKE_STATE"
printf '%s\\n' '{}'
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    python_wrapper = fake_bin / "python-wrapper"
    python_wrapper.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${2:-}" == "configure" ]]; then
  exit 9
fi
if [[ "${2:-}" == "validate-only" ]]; then
  exit 0
fi
exec "$REAL_PYTHON" "$@"
""",
        encoding="utf-8",
    )
    python_wrapper.chmod(0o755)
    run_dir = tmp_path / "run"
    environment = dict(os.environ)
    environment.update({
        "PATH": f"{fake_bin}:{environment['PATH']}",
        "REAL_PYTHON": sys.executable,
        "FAKE_LOG": str(log_file),
        "FAKE_STATE": str(state_file),
        "FAKE_PRIOR_JOB": str(prior_file),
        "FAKE_UPDATED_JOB": str(updated_file),
        "FAKE_RESTORED_JOB": str(restored_file),
        "FAKE_BUILD": str(build_file),
        "CORPUS_ARTIFACT_SOURCE_AUTHORITY_ENABLED": "1",
        "CORPUS_ARTIFACT_SOURCE_PYTHON": str(python_wrapper),
        "CORPUS_ARTIFACT_SOURCE_RUN_DIR": str(run_dir),
        "CORPUS_ARTIFACT_SOURCE_JOB": JOB_NAME,
        "CORPUS_ARTIFACT_SOURCE_IMAGE": IMAGE,
        "CORPUS_ARTIFACT_SOURCE_BUILD_ID": BUILD_ID,
        "CORPUS_ARTIFACT_SOURCE_CODE_SHA": CODE_SHA,
        "CORPUS_ARTIFACT_SOURCE_SERVICE_ACCOUNT": SERVICE_ACCOUNT,
        "CORPUS_ARTIFACT_SOURCE_PLAN_FILE": str(plan_file),
        "CORPUS_ARTIFACT_SOURCE_RUNTIME_IAM_FILE": str(iam_file),
        "CORPUS_ARTIFACT_SOURCE_DELIVERY_PREFIX": DELIVERY_PREFIX,
    })
    completed = subprocess.run(
        ["bash", str(SHELL), "--execute", "configure"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 9, completed.stderr
    assert state_file.read_text(encoding="utf-8").strip() == "rolledback"
    assert (run_dir / "rollback-restored.json").is_file()
    calls = log_file.read_text(encoding="utf-8")
    assert calls.index(f"builds describe {BUILD_ID}") < calls.index(
        f"run jobs update {JOB_NAME}"
    )
    assert "run.googleapis.com/v1/namespaces" in calls
