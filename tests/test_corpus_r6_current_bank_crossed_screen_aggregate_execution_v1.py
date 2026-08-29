from __future__ import annotations

import ast
from copy import deepcopy
from hashlib import sha256
import importlib.util
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import weakref

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_aggregate_v1 as aggregate,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = (
    ROOT / "scripts" / "run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py"
)


def _load_cli():
    spec = importlib.util.spec_from_file_location("r6_aggregate_cli_test", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(uri: str, raw: bytes, generation: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _tag_identity(name: str) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1({"tag": name})
    return _identity(
        f"gs://nfl-predictions-503414-corpus-retrieval/fixture/{name}.json",
        raw,
        str(100_000 + len(name)),
    )


class MemoryExactCreateOnceTransport:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, dict[str, object]] = {}
        self.events: list[tuple[str, str, str | None]] = []
        self.next_generation = 2_000_000

    def add_json(
        self, uri: str, body: object, *, generation: str | None = None,
    ) -> dict[str, object]:
        raw = contract.canonical_json_bytes_v1(body)
        return self.add_raw(uri, raw, generation=generation)

    def add_raw(
        self, uri: str, raw: bytes, *, generation: str | None = None,
    ) -> dict[str, object]:
        retained_generation = generation or str(self.next_generation)
        self.next_generation += 1
        identity = _identity(uri, raw, retained_generation)
        self.objects[(uri, retained_generation)] = raw
        self.current[uri] = identity
        return identity

    def read_exact(self, identity_value) -> bytes:
        identity = contract._safe_object_identity(
            identity_value, label="memory exact identity"
        )
        self.events.append(
            ("read", str(identity["uri"]), str(identity["generation"]))
        )
        try:
            raw = self.objects[(str(identity["uri"]), str(identity["generation"]))]
        except KeyError as exc:
            raise aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "exact generation is absent"
            ) from exc
        if (
            len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            raise aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "exact identity differs"
            )
        return raw

    def publish_create_once(self, uri: str, raw: bytes, prior):
        prior_generation = None if prior is None else str(prior["generation"])
        self.events.append(("publish", uri, prior_generation))
        if uri in self.current:
            if prior is None:
                raise aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error(
                    "collision lacks prior authority"
                )
            retained = contract._safe_object_identity(
                prior, label="memory prior identity"
            )
            if retained["uri"] != uri or self.read_exact(retained) != raw:
                raise aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error(
                    "collision differs from prior authority"
                )
            return retained
        created = self.add_raw(uri, raw)
        assert self.read_exact(created) == raw
        return created


class Fixture:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.role = aggregate.MODE_PROCESS_ROLE[mode]
        self.store = MemoryExactCreateOnceTransport()
        self.output_prefix = contract.OUTPUT_NAMESPACE + f"fixture-d-{mode}/"
        self.topology = contract.build_result_topology_v1(self.output_prefix)
        self.topology_identity = self.store.add_json(
            "gs://nfl-predictions-503414-corpus-retrieval/fixture/topology-"
            f"{mode}.json",
            self.topology,
        )
        self.launch = {
            "schema_version": "fixture-pre-design-run-authorization/v1",
            "contract_id": contract.CONTRACT_ID,
            "process_role": self.role,
            "cloud_execution_attestation": False,
        }
        self.launch_identity = self.store.add_json(
            "gs://nfl-predictions-503414-corpus-retrieval/fixture/launch-"
            f"{mode}.json",
            self.launch,
        )
        self.run_identity = self.launch_identity
        command = aggregate.canonical_publisher_command_v1(mode)
        entrypoint_sha = sha256(Path(command[1]).read_bytes()).hexdigest()
        specs = []
        for role in contract.PROCESS_ROLES:
            if role == self.role:
                retained_command = command
                path = command[1]
                digest = entrypoint_sha
                chain = [{
                    "component_role": "main",
                    "command": retained_command,
                    "entrypoint_path": path,
                    "entrypoint_sha256": digest,
                }]
            elif role.endswith("fold-selector"):
                chain = []
                for component_role in ("artifact-broker", "matrix-selector"):
                    retained_command = [
                        "/usr/bin/python3", f"/app/{role}-{component_role}.py"
                    ]
                    path = retained_command[1]
                    digest = sha256(
                        f"{role}-{component_role}".encode("utf-8")
                    ).hexdigest()
                    chain.append({
                        "component_role": component_role,
                        "command": retained_command,
                        "entrypoint_path": path,
                        "entrypoint_sha256": digest,
                    })
            else:
                retained_command = ["/usr/bin/python3", f"/app/{role}.py"]
                path = retained_command[1]
                digest = sha256(role.encode("utf-8")).hexdigest()
                chain = [{
                    "component_role": "main",
                    "command": retained_command,
                    "entrypoint_path": path,
                    "entrypoint_sha256": digest,
                }]
            specs.append({
                "process_role": role,
                "process_chain": chain,
            })
        self.bootstrap = contract.build_bootstrap_manifest_v1(
            topology=self.topology,
            topology_identity=self.topology_identity,
            run_identity=self.run_identity,
            code_commit="a" * 40,
            image_digest="sha256:" + "b" * 64,
            process_specs=specs,
        )
        self.bootstrap_identity = self.store.add_json(
            "gs://nfl-predictions-503414-corpus-retrieval/fixture/bootstrap-"
            f"{mode}.json",
            self.bootstrap,
        )
        self.design = contract.build_design_v1(
            output_prefix=self.output_prefix,
            code_identity=_tag_identity(f"code-{mode}"),
            report_identity=_tag_identity(f"report-{mode}"),
            topology_identity=self.topology_identity,
            bootstrap_manifest=self.bootstrap,
            bootstrap_manifest_identity=self.bootstrap_identity,
        )
        self.design_identity = self.store.add_json(
            str(self.topology["objects"][0]["uri"]), self.design
        )
        self.broad: list[dict[str, object]] = []
        self.confirmation: list[dict[str, object]] = []
        self.nomination_identity: dict[str, object] | None = None
        self.predecessors: list[dict[str, object]] = []
        if mode in {
            aggregate.PUBLISH_NOMINATION,
            aggregate.PUBLISH_AGGREGATE_FINALISTS,
        }:
            broad_rows = [
                row for row in self.topology["objects"]
                if row["role"] == "broad-evaluation-result"
            ]
            self.broad = [
                self.store.add_json(
                    str(row["uri"]),
                    {
                        "kind": "broad-evaluation",
                        "source_ordinal": source,
                        "slate_id": f"fixture-slate-{source:02d}",
                        "phase": contract.BROAD_SCREEN_PHASE,
                        "publication_role": "broad-evaluation-result",
                        "design_publication_identity": self.design_identity,
                        "design_sha256": self.design["design_sha256"],
                        "topology_identity": self.topology_identity,
                    },
                )
                for source, row in enumerate(broad_rows)
            ]
        if mode == aggregate.PUBLISH_AGGREGATE_FINALISTS:
            nomination_row = next(
                row for row in self.topology["objects"]
                if row["role"] == "nomination"
            )
            self.nomination_identity = self.store.add_json(
                str(nomination_row["uri"]),
                {"kind": "nomination", "derived": True},
            )
            confirmation_rows = [
                row for row in self.topology["objects"]
                if row["role"] == "confirmation-evaluation-result"
            ]
            self.confirmation = [
                self.store.add_json(
                    str(row["uri"]),
                    {
                        "kind": "confirmation-evaluation",
                        "source_ordinal": source,
                        "slate_id": f"fixture-slate-{source:02d}",
                        "phase": contract.CONFIRMATION_PHASE,
                        "publication_role": "confirmation-evaluation-result",
                        "design_publication_identity": self.design_identity,
                        "design_sha256": self.design["design_sha256"],
                        "topology_identity": self.topology_identity,
                    },
                )
                for source, row in enumerate(confirmation_rows)
            ]
        if mode == aggregate.PUBLISH_TERMINAL_ROOT:
            for descriptor in self.topology["objects"][:-1]:
                ordinal = int(descriptor["ordinal"])
                if ordinal == 0:
                    self.predecessors.append(self.design_identity)
                    continue
                self.predecessors.append(self.store.add_json(
                    str(descriptor["uri"]),
                    {
                        "kind": str(descriptor["role"]),
                        "ordinal": ordinal,
                    },
                ))
        scientific = (
            self.broad
            if mode == aggregate.PUBLISH_NOMINATION
            else [*self.broad, self.nomination_identity, *self.confirmation]
            if mode == aggregate.PUBLISH_AGGREGATE_FINALISTS
            else self.predecessors
        )
        self.budget = contract.compile_publisher_process_budget_v1(
            process_role=self.role,
            design=self.design,
            design_publication_identity=self.design_identity,
            topology_identity=self.topology_identity,
            bootstrap_manifest=self.bootstrap,
            bootstrap_manifest_identity=self.bootstrap_identity,
            launch_intent_identity=self.launch_identity,
            scientific_read_identities=scientific,
        )
        self.budget_identity = self.store.add_json(
            "gs://nfl-predictions-503414-corpus-retrieval/fixture/budget-"
            f"{mode}.json",
            self.budget,
        )

    def request(self, **priors) -> dict[str, object]:
        return aggregate.build_publisher_request_v1(
            mode=self.mode,
            design_identity=self.design_identity,
            topology_identity=self.topology_identity,
            bootstrap_manifest_identity=self.bootstrap_identity,
            launch_intent_identity=self.launch_identity,
            process_budget_identity=self.budget_identity,
            broad_evaluation_identities=self.broad,
            nomination_identity=self.nomination_identity,
            confirmation_evaluation_identities=self.confirmation,
            predecessor_identities=self.predecessors,
            **priors,
        )

    def runtime(self) -> dict[str, object]:
        return aggregate.derive_observed_runtime_evidence_v1(
            mode=self.mode,
            environ={
                "GOOGLE_CLOUD_PROJECT": aggregate.FIXED_GCP_PROJECT,
                "CODE_SHA": "a" * 40,
                "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
                "CLOUD_RUN_TASK_INDEX": "0",
                "R6_AGGREGATE_PROCESS_ORDINAL": "0",
                "CLOUD_RUN_JOB": "fixture-job",
                "CLOUD_RUN_EXECUTION": "fixture-execution",
            },
            argv=aggregate.canonical_publisher_command_v1(self.mode),
            pid=17,
            parent_pid=9,
        )


def _publisher_task_binding_fixture(
    fixture: Fixture,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, str], dict[str, object]
]:
    """Build one structurally exact nomination task binding without cloud I/O."""
    assert fixture.mode == aggregate.PUBLISH_NOMINATION
    request = fixture.request()
    layer = task_manifest._layer("nomination")
    descriptor = task_manifest._layer_descriptor(
        fixture.output_prefix, layer.layer_id
    )
    output_row = next(
        row for row in fixture.topology["objects"]
        if row["role"] == "nomination"
    )
    budget = next(
        row for row in fixture.design["publication_budgets"]
        if row["uri"] == output_row["uri"]
    )
    outputs = [{
        "topology_ordinal": int(output_row["ordinal"]),
        "role": "nomination",
        "source_ordinal": None,
        "uri": output_row["uri"],
        "maximum_bytes": int(budget["max_bytes"]),
        "create_once": True,
        "prior_identity": request["prior_nomination_identity"],
    }]
    command = task_manifest.render_child_command_v1(layer.layer_id, request)
    component = task_manifest._main_process_component(layer)
    request_raw = contract.canonical_json_bytes_v1(request)
    task_body = {
        "task_ordinal": 0,
        "task_index": 0,
        "source_ordinal": None,
        "process_ordinal": 0,
        "phase": contract.BROAD_SCREEN_PHASE,
        "process_role": "broad-nomination-publisher",
        "request_schema": request["schema_version"],
        "request": request,
        "request_bytes": len(request_raw),
        "request_sha256": sha256(request_raw).hexdigest(),
        "expected_outputs": outputs,
        "expected_outputs_sha256": task_manifest._canonical_sha(outputs),
        "child_command": command,
        "child_command_sha256": task_manifest._canonical_sha({
            "command": command,
            "entrypoint_sha256": component["entrypoint_sha256"],
        }),
        "child_stdout_byte_ceiling": layer.child_stdout_byte_ceiling,
        "child_stderr_byte_ceiling": task_manifest.MAXIMUM_CHILD_STDERR_BYTES,
        "maximum_wall_seconds": layer.maximum_wall_seconds,
        "maximum_peak_rss_bytes": 24 * 1024 * 1024 * 1024,
        "task_terminal_evidence_uri": (
            f"{fixture.output_prefix}authorities/task-terminal-evidence/"
            "nomination/task-000.json"
        ),
    }
    task_body["task_science_binding_sha256"] = (
        task_manifest._task_science_binding_sha256_v1(task_body)
    )
    task = task_manifest._with_hash(
        task_body, field="task_binding_sha256"
    )
    predecessors = []
    for offset, predecessor in enumerate(layer.predecessor_layers):
        predecessor_raw = contract.canonical_json_bytes_v1({
            "fixture": "predecessor-layer-receipt",
            "layer_id": predecessor,
        })
        predecessor_uri = task_manifest._layer_descriptor(
            fixture.output_prefix, predecessor
        )["layer_execution_receipt_uri"]
        predecessors.append({
            "layer_id": predecessor,
            "receipt_identity": _identity(
                str(predecessor_uri), predecessor_raw, str(929290 + offset)
            ),
            "layer_execution_receipt_sha256": f"{offset + 1:x}" * 64,
        })
    # Normalize the deliberately distinct hashes to exactly 64 hex digits.
    for offset, row in enumerate(predecessors):
        row["layer_execution_receipt_sha256"] = format(
            offset + 1, "064x"
        )
    dispatcher = task_manifest.canonical_dispatcher_process_spec_v1()
    required_specs = task_manifest._required_process_specs(layer)
    host_terminal_resolution = (
        task_manifest._host_terminal_generation_resolution_authority_v1([task])
    )
    manifest_body = {
        "schema_version": task_manifest.TASK_MANIFEST_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "output_prefix": fixture.output_prefix,
        "layer_ordinal": descriptor["layer_ordinal"],
        "layer_id": layer.layer_id,
        "phase": layer.phase,
        "process_role": layer.process_role,
        "mode": layer.mode,
        "task_count": 1,
        "manifest_uri": descriptor["manifest_uri"],
        "layer_execution_receipt_uri": descriptor[
            "layer_execution_receipt_uri"
        ],
        "design_identity": fixture.design_identity,
        "design_sha256": fixture.design["design_sha256"],
        "topology_identity": fixture.topology_identity,
        "topology_sha256": fixture.topology["topology_sha256"],
        "bootstrap_manifest_identity": fixture.bootstrap_identity,
        "bootstrap_manifest_sha256": fixture.bootstrap[
            "bootstrap_manifest_sha256"
        ],
        "pre_design_run_authorization_identity": fixture.launch_identity,
        "pre_design_run_authorization_sha256": fixture.launch_identity[
            "sha256"
        ],
        "code_commit": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "reused_job_name": "fixture-job",
        "dispatcher_process_spec": dispatcher,
        "dispatcher_process_spec_sha256": task_manifest._canonical_sha(
            dispatcher
        ),
        "required_process_specs": required_specs,
        "required_process_specs_sha256": task_manifest._canonical_sha(
            required_specs
        ),
        "predecessor_layer_receipts": predecessors,
        "predecessor_layer_receipts_sha256": task_manifest._canonical_sha(
            predecessors
        ),
        "task_bindings": [task],
        "task_bindings_sha256": task_manifest._canonical_sha([task]),
        "task_index_selects_exactly_one_request": True,
        "caller_manifest_request_or_command_accepted": False,
        "one_reused_job_across_layers": True,
        "per_task_deploy_allowed": False,
        "current_generation_resolution_allowed": False,
        "current_generation_resolution_policy_scope": (
            "scientific-and-task-input-authorities-only"
        ),
        "host_terminal_evidence_generation_resolution_authority": (
            host_terminal_resolution
        ),
        "host_terminal_evidence_generation_resolution_authority_sha256": (
            task_manifest._canonical_sha(host_terminal_resolution)
        ),
        "listing_allowed": False,
        "uses_realized_outcomes": False,
        "graph_capability_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    manifest = task_manifest._with_hash(
        manifest_body, field="task_manifest_sha256"
    )
    manifest_raw = contract.canonical_json_bytes_v1(manifest)
    manifest_identity = _identity(
        str(descriptor["manifest_uri"]), manifest_raw, "919191"
    )
    environment = task_manifest.child_task_binding_environment_v1(
        manifest, manifest_identity=manifest_identity, task_index=0
    )
    evidence = task_manifest.validate_child_task_binding_v1(
        manifest,
        manifest_identity=manifest_identity,
        environ=environment,
        raw_request=request_raw,
        observed_command=command,
        expected_process_role=layer.process_role,
        expected_phase=layer.phase,
        expected_process_ordinal=0,
    )
    return manifest, manifest_identity, environment, evidence


def _hashed(body: dict[str, object], field: str) -> dict[str, object]:
    return aggregate._with_hash(body, field=field)


def _install_scientific_stubs(monkeypatch, observations: dict[str, object]) -> None:
    def validate_evaluation(value):
        return dict(value)

    def compact_evaluation(record):
        body = record["body"]
        scalars = {
            stem: {"numerator": int(record["source_ordinal"]) + 1, "denominator": 1}
            for stem in contract._AGGREGATE_METRIC_STEMS
        }
        return {
            "source_ordinal": record["source_ordinal"],
            "slate_id": record["slate_id"],
            "phase": record["phase"],
            "identity": record["identity"],
            "body": {
                "topology_identity": body["topology_identity"],
                "folds": [{
                    "fold_ordinal": 0,
                    "heldout_block": contract.WORLD_BLOCKS[0],
                    "book_metric_rows": [{
                        "prefix_size": contract.ENTRY_BUDGET,
                        "replicate": 0,
                        "view_id": contract.PRIMARY_BASELINE_VIEW_ID,
                        "strategy_id": contract.PRIMARY_BASELINE_STRATEGY_ID,
                        "aggregate_scalars": scalars,
                        "unused_full_row_payload": "x" * 1_024,
                    }],
                }],
            },
        }

    def build_broad_from_records(**kwargs):
        rows = kwargs["records"]
        assert [row["source_ordinal"] for row in rows] == list(range(54))
        observations["nomination_sources"] = len(rows)
        return _hashed({
            "kind": "derived-broad-phase-authority",
            "design_publication_identity": kwargs["retained_design_identity"],
            "run_identity": kwargs["run_identity"],
            "record_count": len(rows),
            "policy": dict(contract.POLICY_CLAIMS),
        }, "broad_phase_authority_sha256")

    def nominees(broad):
        return _hashed({
            "kind": "derived-nominees",
            "broad_phase_authority_sha256": broad[
                "broad_phase_authority_sha256"
            ],
            "policy": dict(contract.POLICY_CLAIMS),
        }, "nomination_sha256")

    def validate_nomination_body(value):
        return dict(value)

    def validate_nomination_authority(value, *, publication_identity):
        aggregate._bind(value, publication_identity, label="nomination")
        return dict(value)

    def build_aggregate_from_records(**kwargs):
        broad = kwargs["broad_records"]
        confirmation = kwargs["confirmation_records"]
        assert [row["source_ordinal"] for row in broad] == list(range(54))
        assert [row["source_ordinal"] for row in confirmation] == list(range(54))
        observations["aggregate_counts"] = (len(broad), len(confirmation))
        return _hashed({
            "kind": "derived-aggregate",
            "topology": kwargs["retained_design"]["topology"],
            "nomination_publication_identity": kwargs[
                "nomination_publication_identity"
            ],
            "caller_values_accepted": False,
            "policy": dict(contract.POLICY_CLAIMS),
        }, "aggregate_mechanics_sha256")

    def validate_aggregate(value, *, publication_identity):
        aggregate._bind(value, publication_identity, label="aggregate")
        observations["finalist_input_generation"] = publication_identity[
            "generation"
        ]
        return value

    def finalists(value, *, aggregate_publication_identity):
        assert observations["finalist_input_generation"] == (
            aggregate_publication_identity["generation"]
        )
        return _hashed({
            "kind": "derived-finalists",
            "aggregate_publication_identity": aggregate_publication_identity,
            "policy": dict(contract.POLICY_CLAIMS),
        }, "finalist_function_sha256")

    def finalist_publication(*, finalists, aggregate, aggregate_publication_identity):
        assert finalists["aggregate_publication_identity"] == (
            aggregate_publication_identity
        )
        return _hashed({
            "kind": "derived-finalist-publication",
            "aggregate_publication_identity": aggregate_publication_identity,
            "finalists": finalists,
            "aggregate_sha256": aggregate["aggregate_mechanics_sha256"],
            "policy": dict(contract.POLICY_CLAIMS),
        }, "finalist_publication_sha256")

    def validate_finalist(value, **kwargs):
        aggregate._bind(value, kwargs["publication_identity"], label="finalist")
        assert value["aggregate_publication_identity"] == (
            kwargs["aggregate_publication_identity"]
        )
        return value

    def build_root(
        *, design, design_publication_identity, predecessor_opener,
        maximum_compact_evaluation_state_bytes, resource_checkpoint,
    ):
        assert maximum_compact_evaluation_state_bytes == 64_000_000
        retained = []
        for descriptor in design["topology"]["objects"][:-1]:
            body, identity = predecessor_opener(descriptor)
            assert identity["uri"] == descriptor["uri"]
            assert isinstance(body, dict)
            retained.append({
                "ordinal": descriptor["ordinal"],
                "role": descriptor["role"],
                "identity": identity,
            })
            del body
            resource_checkpoint(f"fixture terminal predecessor {descriptor['ordinal']}")
        observations["terminal_ordinals"] = [row["ordinal"] for row in retained]
        observations["terminal_resource_checkpoints"] = len(retained)
        return _hashed({
            "schema_version": contract.ROOT_SCHEMA,
            "design_publication_identity": design_publication_identity,
            "predecessor_count": len(retained),
            "predecessors_sha256": contract.canonical_sha256_v1(retained),
            "predecessor_opener_call_count": len(retained),
            "retained_full_evaluation_body_count": 0,
            "retained_compact_evaluation_record_count": 108,
            "retained_compact_evaluation_state_bytes": 12_345,
            "streaming_body_list_accepted": False,
            "policy": dict(contract.POLICY_CLAIMS),
        }, "root_sha256")

    monkeypatch.setattr(contract, "validate_evaluation_result_v1", validate_evaluation)
    monkeypatch.setattr(
        contract, "_compact_evaluation_record_v1", compact_evaluation
    )
    monkeypatch.setattr(
        contract, "_build_broad_phase_authority_from_records_v1",
        build_broad_from_records,
    )
    monkeypatch.setattr(
        contract, "deterministic_nominees_from_broad_authority_v1", nominees
    )
    monkeypatch.setattr(
        contract, "validate_nomination_publication_v1", validate_nomination_body
    )
    monkeypatch.setattr(
        contract, "validate_nomination_publication_authority_v1",
        validate_nomination_authority,
    )
    monkeypatch.setattr(
        contract, "_build_aggregate_mechanics_from_records_v1",
        build_aggregate_from_records,
    )
    monkeypatch.setattr(
        contract, "validate_aggregate_mechanics_authority_v1", validate_aggregate
    )
    monkeypatch.setattr(
        contract, "deterministic_finalists_from_aggregate_v1", finalists
    )
    monkeypatch.setattr(
        contract, "build_finalist_publication_v1", finalist_publication
    )
    monkeypatch.setattr(
        contract, "validate_finalist_publication_authority_v1", validate_finalist
    )
    monkeypatch.setattr(contract, "build_terminal_root_from_stream_v1", build_root)
    monkeypatch.setattr(
        contract,
        "validate_terminal_root_from_stream_authority_v1",
        lambda *args, **kwargs: pytest.fail(
            "publisher must not consume a second 274-object validation pass"
        ),
    )


@pytest.mark.parametrize(
    ("mode", "scientific_count", "roles"),
    [
        (aggregate.PUBLISH_NOMINATION, 54, ["nomination"]),
        (
            aggregate.PUBLISH_AGGREGATE_FINALISTS,
            109,
            ["aggregate", "confirmed-finalists"],
        ),
        (aggregate.PUBLISH_TERMINAL_ROOT, 274, ["root"]),
    ],
)
def test_each_mode_derives_then_create_once_and_exact_resumes(
    monkeypatch, mode, scientific_count, roles,
):
    observations: dict[str, object] = {}
    _install_scientific_stubs(monkeypatch, observations)
    fixture = Fixture(mode)
    first = aggregate.run_publisher_v1(
        fixture.request(),
        observed_runtime=fixture.runtime(),
        read_exact=fixture.store.read_exact,
        publish_create_once=fixture.store.publish_create_once,
    )
    assert aggregate.validate_publisher_envelope_v1(first) == first
    assert first["scientific_read_count"] == scientific_count
    assert first["read_object_count"] == scientific_count + 5
    assert [row["role"] for row in first["publications"]] == roles
    assert first["all_writes_precharged_before_first_create"] is True
    assert first["resource_precharge_sha256"] == first[
        "resource_precharge"
    ]["resource_precharge_sha256"]
    assert first["maximum_retained_full_evaluation_body_count"] == 1
    assert first["retained_compact_evaluation_record_count"] == (
        54 if mode == aggregate.PUBLISH_NOMINATION else 108
    )
    assert first["observed_elapsed_milliseconds"] <= 1_800_000
    assert first["observed_peak_rss_bytes"] <= 24 * 1024 * 1024 * 1024
    assert 2 <= first["retained_compact_evaluation_state_bytes"] <= 64_000_000
    assert first["runtime_observation"][
        "cloud_values_are_unattested_observations"
    ] is True
    assert first["runtime_observation"][
        "terminal_execution_attestation_required"
    ] is True

    prior_kwargs = {}
    for publication in first["publications"]:
        key = {
            "nomination": "prior_nomination_identity",
            "aggregate": "prior_aggregate_identity",
            "confirmed-finalists": "prior_finalist_identity",
            "root": "prior_root_identity",
        }[publication["role"]]
        prior_kwargs[key] = publication["identity"]
    resumed = aggregate.run_publisher_v1(
        fixture.request(**prior_kwargs),
        observed_runtime=fixture.runtime(),
        read_exact=fixture.store.read_exact,
        publish_create_once=fixture.store.publish_create_once,
    )
    assert [row["identity"] for row in resumed["publications"]] == [
        row["identity"] for row in first["publications"]
    ]
    if mode == aggregate.PUBLISH_NOMINATION:
        assert observations["nomination_sources"] == 54
    elif mode == aggregate.PUBLISH_AGGREGATE_FINALISTS:
        assert observations["aggregate_counts"] == (54, 54)
    else:
        assert observations["terminal_ordinals"] == list(range(274))
        assert observations["terminal_resource_checkpoints"] == 274
        assert first["terminal_predecessor_opener_call_count"] == 274
        assert first["terminal_full_predecessor_body_list_materialized"] is False


def test_streamed_evaluations_release_each_validated_full_body(monkeypatch):
    observations: dict[str, object] = {}
    _install_scientific_stubs(monkeypatch, observations)
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    prior: weakref.ReferenceType | None = None
    references: list[weakref.ReferenceType] = []

    class TrackableEvaluation(dict):
        pass

    def tracked_validate(value):
        nonlocal prior
        if prior is not None:
            assert prior() is None
        tracked = TrackableEvaluation(value)
        prior = weakref.ref(tracked)
        references.append(prior)
        return tracked

    monkeypatch.setattr(
        contract, "validate_evaluation_result_v1", tracked_validate
    )
    envelope = aggregate.run_publisher_v1(
        fixture.request(), observed_runtime=fixture.runtime(),
        read_exact=fixture.store.read_exact,
        publish_create_once=fixture.store.publish_create_once,
        _clock=lambda: 0.0, _peak_rss_bytes=lambda: 1,
    )
    assert len(references) == contract.PANEL_SLATE_COUNT
    assert all(reference() is None for reference in references)
    assert envelope["maximum_retained_full_evaluation_body_count"] == 1
    assert envelope["retained_compact_evaluation_record_count"] == 54


def test_resource_precharge_exact_limits_and_rss_algebra(monkeypatch):
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    request = deepcopy(fixture.request())
    exact = dict(request["broad_evaluation_identities"][0])
    exact["bytes"] = aggregate.MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
    request["broad_evaluation_identities"][0] = exact
    precharge = aggregate._compile_resource_precharge_v1(
        request=request, topology=fixture.topology,
        scientific_identities=request["broad_evaluation_identities"],
    )
    assert precharge["maximum_single_scientific_body_bytes"] == 768_000_000
    assert precharge["maximum_compact_evaluation_state_bytes"] == 64_000_000
    assert precharge["maximum_peak_rss_bytes"] == 24 * 1024 * 1024 * 1024
    assert precharge["maximum_address_space_bytes"] == 24 * 1024 * 1024 * 1024
    assert precharge["required_cloud_run_container_memory_bytes"] == (
        32 * 1024 * 1024 * 1024
    )
    too_large = deepcopy(request)
    too_large["broad_evaluation_identities"][0]["bytes"] += 1
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="scientific body exceeds resource precharge",
    ):
        aggregate._compile_resource_precharge_v1(
            request=too_large, topology=fixture.topology,
            scientific_identities=too_large["broad_evaluation_identities"],
        )
    assert aggregate.PUBLISHER_WORST_CASE_RSS_BYTES == 20_010_450_944
    assert aggregate.PUBLISHER_WORST_CASE_RSS_BYTES < (
        aggregate.MAXIMUM_PUBLISHER_PEAK_RSS_BYTES
    )
    assert (
        aggregate.MAXIMUM_PUBLISHER_PEAK_RSS_BYTES
        - aggregate.PUBLISHER_WORST_CASE_RSS_BYTES
    ) == 5_759_352_832

    state = [aggregate.resource.RLIM_INFINITY, aggregate.resource.RLIM_INFINITY]
    writes: list[tuple[int, tuple[int, int]]] = []

    def get_limit(_resource):
        return tuple(state)

    def set_limit(resource_id, limits):
        writes.append((resource_id, limits))
        state[:] = limits

    assert aggregate._require_address_space_limit_v1(
        _getrlimit=get_limit, _setrlimit=set_limit
    ) == aggregate.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES
    assert writes == [(
        aggregate.resource.RLIMIT_AS,
        (
            aggregate.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES,
            aggregate.resource.RLIM_INFINITY,
        ),
    )]
    writes.clear()
    assert aggregate._require_address_space_limit_v1(
        _getrlimit=get_limit, _setrlimit=set_limit
    ) == aggregate.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES
    assert writes == []
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="hard address-space limit",
    ):
        aggregate._require_address_space_limit_v1(
            _getrlimit=lambda _resource: (
                aggregate.resource.RLIM_INFINITY,
                aggregate.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES - 1,
            ),
            _setrlimit=lambda *_args: pytest.fail(
                "insufficient hard limit must fail before setrlimit"
            ),
        )


def test_resource_overflow_wall_and_rss_fail_before_publication(monkeypatch):
    observations: dict[str, object] = {}
    _install_scientific_stubs(monkeypatch, observations)
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    monkeypatch.setattr(
        aggregate, "MAXIMUM_COMPACT_EVALUATION_STATE_BYTES", 256
    )
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="compact evaluation state exceeds resource precharge",
    ):
        aggregate.run_publisher_v1(
            fixture.request(), observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
            _clock=lambda: 0.0, _peak_rss_bytes=lambda: 1,
        )
    assert not any(event[0] == "publish" for event in fixture.store.events)

    monkeypatch.setattr(
        aggregate, "MAXIMUM_COMPACT_EVALUATION_STATE_BYTES", 64_000_000
    )
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    ticks = iter((0.0, 5_401.0))
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="wall-time ceiling",
    ):
        aggregate.run_publisher_v1(
            fixture.request(), observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
            _clock=lambda: next(ticks), _peak_rss_bytes=lambda: 1,
        )
    scientific_uris = {row["uri"] for row in fixture.broad}
    assert not any(
        event[0] == "read" and event[1] in scientific_uris
        for event in fixture.store.events
    )

    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="peak-RSS ceiling",
    ):
        aggregate.run_publisher_v1(
            fixture.request(), observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
            _clock=lambda: 0.0,
            _peak_rss_bytes=lambda: 24 * 1024 * 1024 * 1024 + 1,
        )


def test_request_rejects_caller_science_and_bad_mode_lattices():
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    request = fixture.request()
    for forbidden, value in (
        ("broad_phase_grid", {"rows": []}),
        ("nominees", ["caller-choice"]),
        ("paired_comparisons", []),
        ("bootstrap_rows", []),
        ("output_uri", "gs://caller/output.json"),
        ("scientific_bodies", [{}]),
        ("caller_metrics", [1]),
    ):
        changed = dict(request)
        changed[forbidden] = value
        changed["publisher_request_sha256"] = contract.canonical_sha256_v1({
            key: retained for key, retained in changed.items()
            if key != "publisher_request_sha256"
        })
        with pytest.raises(
            aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
            match="fields differ",
        ):
            aggregate.validate_publisher_request_v1(changed)
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="nomination publisher request lattice",
    ):
        aggregate.build_publisher_request_v1(
            mode=aggregate.PUBLISH_NOMINATION,
            design_identity=fixture.design_identity,
            topology_identity=fixture.topology_identity,
            bootstrap_manifest_identity=fixture.bootstrap_identity,
            launch_intent_identity=fixture.launch_identity,
            process_budget_identity=fixture.budget_identity,
            broad_evaluation_identities=fixture.broad[:-1],
        )
    terminal = Fixture(aggregate.PUBLISH_TERMINAL_ROOT)
    for predecessors in (terminal.predecessors[:-1], [*terminal.predecessors, _tag_identity("x")]):
        with pytest.raises(
            aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
            match="terminal publisher request lattice",
        ):
            aggregate.build_publisher_request_v1(
                mode=aggregate.PUBLISH_TERMINAL_ROOT,
                design_identity=terminal.design_identity,
                topology_identity=terminal.topology_identity,
                bootstrap_manifest_identity=terminal.bootstrap_identity,
                launch_intent_identity=terminal.launch_identity,
                process_budget_identity=terminal.budget_identity,
                predecessor_identities=predecessors,
            )


def test_reordered_scientific_identity_fails_before_first_scientific_read(
    monkeypatch,
):
    _install_scientific_stubs(monkeypatch, {})
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    reordered = list(fixture.broad)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    request = aggregate.build_publisher_request_v1(
        mode=fixture.mode,
        design_identity=fixture.design_identity,
        topology_identity=fixture.topology_identity,
        bootstrap_manifest_identity=fixture.bootstrap_identity,
        launch_intent_identity=fixture.launch_identity,
        process_budget_identity=fixture.budget_identity,
        broad_evaluation_identities=reordered,
    )
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="publisher scientific read URI/order differs|process budget differs",
    ):
        aggregate.run_publisher_v1(
            request,
            observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
        )
    scientific_uris = {row["uri"] for row in fixture.broad}
    assert not any(
        event[0] == "read" and event[1] in scientific_uris
        for event in fixture.store.events
    )


def test_runtime_spoof_and_arbitrary_command_fail_closed(monkeypatch):
    _install_scientific_stubs(monkeypatch, {})
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    runtime = fixture.runtime()
    runtime["code_commit"] = "c" * 40
    runtime["runtime_evidence_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in runtime.items()
        if key != "runtime_evidence_sha256"
    })
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="runtime observation differs",
    ):
        aggregate.run_publisher_v1(
            fixture.request(),
            observed_runtime=runtime,
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
        )
    command = aggregate.canonical_publisher_command_v1(fixture.mode)
    command[-1] = aggregate.PUBLISH_TERMINAL_ROOT
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="command differs",
    ):
        aggregate.derive_observed_runtime_evidence_v1(
            mode=fixture.mode,
            environ={
                "GOOGLE_CLOUD_PROJECT": aggregate.FIXED_GCP_PROJECT,
                "CODE_SHA": "a" * 40,
                "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
                "CLOUD_RUN_TASK_INDEX": "0",
                "R6_AGGREGATE_PROCESS_ORDINAL": "0",
                "CLOUD_RUN_JOB": "fixture-job",
                "CLOUD_RUN_EXECUTION": "fixture-execution",
            },
            argv=command,
            pid=1,
            parent_pid=1,
        )


def test_terminal_reorder_body_tamper_and_exact_274_gate(monkeypatch):
    _install_scientific_stubs(monkeypatch, {})
    fixture = Fixture(aggregate.PUBLISH_TERMINAL_ROOT)
    reordered = list(fixture.predecessors)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    request = aggregate.build_publisher_request_v1(
        mode=fixture.mode,
        design_identity=fixture.design_identity,
        topology_identity=fixture.topology_identity,
        bootstrap_manifest_identity=fixture.bootstrap_identity,
        launch_intent_identity=fixture.launch_identity,
        process_budget_identity=fixture.budget_identity,
        predecessor_identities=reordered,
    )
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="URI/order differs|process budget differs",
    ):
        aggregate.run_publisher_v1(
            request,
            observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
        )
    tampered = deepcopy(fixture.request())
    victim = dict(tampered["predecessor_identities"][17])
    victim["sha256"] = "0" * 64
    tampered["predecessor_identities"][17] = victim
    tampered["publisher_request_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in tampered.items()
        if key != "publisher_request_sha256"
    })
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error
    ):
        aggregate.run_publisher_v1(
            tampered,
            observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
        )


def test_create_once_collision_needs_exact_prior_generation_and_body(monkeypatch):
    _install_scientific_stubs(monkeypatch, {})
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    first = aggregate.run_publisher_v1(
        fixture.request(),
        observed_runtime=fixture.runtime(),
        read_exact=fixture.store.read_exact,
        publish_create_once=fixture.store.publish_create_once,
    )
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="collision lacks prior",
    ):
        aggregate.run_publisher_v1(
            fixture.request(),
            observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
        )
    prior = dict(first["publications"][0]["identity"])
    prior["generation"] = str(int(prior["generation"]) + 10)
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="exact generation is absent",
    ):
        aggregate.run_publisher_v1(
            fixture.request(prior_nomination_identity=prior),
            observed_runtime=fixture.runtime(),
            read_exact=fixture.store.read_exact,
            publish_create_once=fixture.store.publish_create_once,
        )
    changed_raw = contract.canonical_json_bytes_v1({"different": True})
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="collision differs",
    ):
        fixture.store.publish_create_once(
            str(first["publications"][0]["identity"]["uri"]),
            changed_raw,
            first["publications"][0]["identity"],
        )


def test_invalid_request_and_redirect_rejected_before_client(monkeypatch):
    cli = _load_cli()
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    raw = contract.canonical_json_bytes_v1(fixture.request())
    environ = {
        cli.ENABLE_ENV: "1",
        "GOOGLE_CLOUD_PROJECT": aggregate.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_TASK_INDEX": "0",
        "R6_AGGREGATE_PROCESS_ORDINAL": "0",
        "CLOUD_RUN_JOB": "fixture-job",
        "CLOUD_RUN_EXECUTION": "fixture-execution",
        "STORAGE_EMULATOR_HOST": "http://hostile.invalid",
    }
    argv = aggregate.canonical_publisher_command_v1(fixture.mode)
    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="redirect environment",
    ):
        cli.validate_preclient_invocation_v1(
            argv=argv,
            environ=environ,
            raw_request=raw,
            pid=2,
            parent_pid=1,
        )

    constructed = 0

    class ForbiddenClient:
        def __init__(self):
            nonlocal constructed
            constructed += 1

    bad_request = dict(fixture.request())
    bad_request["caller_metrics"] = [1]
    bad_request["publisher_request_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in bad_request.items()
        if key != "publisher_request_sha256"
    })
    stdin = SimpleNamespace(
        buffer=io.BytesIO(contract.canonical_json_bytes_v1(bad_request))
    )
    monkeypatch.setattr(cli, "GCSExactCreateOnceTransportV1", ForbiddenClient)
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "argv", [str(CLI_PATH), fixture.mode])
    monkeypatch.setattr(cli.os, "environ", {key: value for key, value in environ.items()
                                           if key != "STORAGE_EMULATOR_HOST"})
    with pytest.raises(cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error):
        cli.main()
    assert constructed == 0


def test_publisher_child_binding_rejects_missing_spliced_manifest_output_command_and_index():
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    manifest, manifest_identity, environment, _ = (
        _publisher_task_binding_fixture(fixture)
    )
    request_raw = contract.canonical_json_bytes_v1(fixture.request())
    command = aggregate.canonical_publisher_command_v1(fixture.mode)
    error = task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error

    with pytest.raises(error, match="environment fields differ"):
        task_manifest.parse_child_task_binding_environment_v1({})

    for key in (
        task_manifest.CHILD_TASK_BINDING_HASH_ENV,
        task_manifest.CHILD_REQUEST_HASH_ENV,
        task_manifest.CHILD_OUTPUTS_HASH_ENV,
        task_manifest.CHILD_COMMAND_HASH_ENV,
    ):
        spliced_environment = dict(environment)
        spliced_environment[key] = "f" * 64
        with pytest.raises(error, match="task binding differs"):
            task_manifest.validate_child_task_binding_v1(
                manifest,
                manifest_identity=manifest_identity,
                environ=spliced_environment,
                raw_request=request_raw,
                observed_command=command,
            )

    with pytest.raises(error, match="request bytes differ"):
        task_manifest.validate_child_task_binding_v1(
            manifest,
            manifest_identity=manifest_identity,
            environ=environment,
            raw_request=request_raw + b"\n",
            observed_command=command,
        )

    wrapper_command = [command[0], "-m", "hostile.publisher.wrapper"]
    with pytest.raises(error, match="task binding differs"):
        task_manifest.validate_child_task_binding_v1(
            manifest,
            manifest_identity=manifest_identity,
            environ=environment,
            raw_request=request_raw,
            observed_command=wrapper_command,
        )

    spliced_manifest = dict(manifest)
    spliced_manifest["reused_job_name"] = "spliced-job"
    spliced_manifest["task_manifest_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in spliced_manifest.items()
        if key != "task_manifest_sha256"
    })
    spliced_raw = contract.canonical_json_bytes_v1(spliced_manifest)
    spliced_identity = _identity(
        str(manifest_identity["uri"]), spliced_raw, "919192"
    )
    with pytest.raises(error, match="environment manifest authority differs"):
        task_manifest.validate_child_task_binding_v1(
            spliced_manifest,
            manifest_identity=spliced_identity,
            environ=environment,
            raw_request=request_raw,
            observed_command=command,
        )

    wrong_index = dict(environment)
    wrong_index[task_manifest.CHILD_TASK_INDEX_ENV] = "1"
    with pytest.raises(error, match="outside the registered layer"):
        task_manifest.parse_child_task_binding_environment_v1(wrong_index)


def test_publisher_cli_binds_manifest_before_authority_execution(monkeypatch):
    cli = _load_cli()
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    manifest, manifest_identity, child_environment, evidence = (
        _publisher_task_binding_fixture(fixture)
    )
    request = fixture.request()
    raw = contract.canonical_json_bytes_v1(request)
    environment = {
        **child_environment,
        cli.ENABLE_ENV: "1",
        "GOOGLE_CLOUD_PROJECT": aggregate.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_TASK_INDEX": "0",
        "R6_AGGREGATE_PROCESS_ORDINAL": "0",
        "CLOUD_RUN_JOB": "fixture-job",
        "CLOUD_RUN_EXECUTION": "fixture-execution",
    }
    # The durable manifest correctly freezes the deployed /app command.  This
    # focused in-process CLI invocation observes the local repository path, so
    # its pre-client scalar must describe those actual local kernel argv bytes.
    local_command = aggregate.canonical_publisher_command_v1(fixture.mode)
    environment[task_manifest.CHILD_COMMAND_HASH_ENV] = (
        contract.canonical_sha256_v1({
            "command": local_command,
            "entrypoint_sha256": sha256(Path(local_command[1]).read_bytes()).hexdigest(),
        })
    )
    events: list[str] = []
    manifest_raw = contract.canonical_json_bytes_v1(manifest)

    class Transport:
        def __init__(self) -> None:
            events.append("client")

        def read_exact(self, identity_value):
            events.append("manifest-read")
            assert dict(identity_value) == manifest_identity
            return manifest_raw

        def publish_create_once(self, *_args, **_kwargs):
            raise AssertionError("mock publisher core must not publish")

    def reopen(**kwargs):
        assert kwargs["raw_request"] == raw
        assert kwargs["observed_command"] == (
            aggregate.canonical_publisher_command_v1(fixture.mode)
        )
        assert kwargs["read_exact"](manifest_identity) == manifest_raw
        events.append("binding-validated")
        return evidence

    def run_publisher(request_value, **_kwargs):
        events.append("publisher-core")
        assert request_value == request
        body = {
            "schema_version": aggregate.PUBLISHER_ENVELOPE_SCHEMA,
            "mode": fixture.mode,
            "process_role": fixture.role,
            "process_ordinal": 0,
            "publisher_request_sha256": request["publisher_request_sha256"],
        }
        body["publisher_envelope_sha256"] = contract.canonical_sha256_v1(body)
        return body

    output = io.BytesIO()
    monkeypatch.setattr(cli, "_read_stdin_bounded_v1", lambda: raw)
    monkeypatch.setattr(
        cli,
        "observed_process_command_v1",
        lambda: aggregate.canonical_publisher_command_v1(fixture.mode),
    )
    monkeypatch.setattr(cli, "GCSExactCreateOnceTransportV1", Transport)
    monkeypatch.setattr(
        cli, "reopen_controller_task_after_client_v1", reopen
    )
    monkeypatch.setattr(
        cli.publisher, "_require_address_space_limit_v1",
        lambda: events.append("address-space-limit")
        or aggregate.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES,
    )
    monkeypatch.setattr(cli.publisher, "run_publisher_v1", run_publisher)
    monkeypatch.setattr(cli.os, "environ", environment)
    monkeypatch.setattr(cli.sys, "stdout", SimpleNamespace(buffer=output))
    assert cli.main() == 0
    bound = aggregate.strict_json_v1(
        output.getvalue()[:-1], label="bound publisher stdout"
    )
    assert bound["task_binding_evidence"] == evidence
    assert bound["publisher_envelope_sha256"] == contract.canonical_sha256_v1({
        key: value for key, value in bound.items()
        if key != "publisher_envelope_sha256"
    })
    assert events == [
        "address-space-limit", "client", "manifest-read",
        "binding-validated", "publisher-core",
    ]
    for key in (
        task_manifest.CHILD_REQUEST_HASH_ENV,
        task_manifest.CHILD_COMMAND_HASH_ENV,
    ):
        spliced = dict(environment)
        spliced[key] = "f" * 64
        events.clear()
        monkeypatch.setattr(cli.os, "environ", spliced)
        with pytest.raises(
            cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error,
            match="deterministic publication failed",
        ):
            cli.main()
        assert events == []


def test_publisher_kernel_command_and_missing_binding_fail_before_client(
    monkeypatch,
):
    cli = _load_cli()
    fixture = Fixture(aggregate.PUBLISH_NOMINATION)
    canonical = aggregate.canonical_publisher_command_v1(fixture.mode)
    raw_cmdline = b"\0".join(
        token.encode("utf-8") for token in canonical
    ) + b"\0"
    assert cli.observed_process_command_v1(raw_cmdline) == canonical
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="canonical publisher entrypoint",
    ):
        cli.observed_process_command_v1(
            b"\0".join([
                canonical[0].encode("utf-8"), b"-m", b"hostile.wrapper",
            ]) + b"\0"
        )

    first = b"/usr/bin/python3"
    second = str(CLI_PATH.resolve()).encode("utf-8")
    third_length = (
        cli.MAXIMUM_PROCESS_COMMAND_BYTES - len(first) - len(second) - 3
    )
    exact_ceiling = b"\0".join([
        first, second, b"x" * third_length,
    ]) + b"\0"
    assert len(exact_ceiling) == cli.MAXIMUM_PROCESS_COMMAND_BYTES
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="canonical publisher entrypoint",
    ):
        cli.observed_process_command_v1(exact_ceiling)
    plus_one = b"\0".join([
        first, second, b"x" * (third_length + 1),
    ]) + b"\0"
    assert len(plus_one) == cli.MAXIMUM_PROCESS_COMMAND_BYTES + 1
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="kernel process command differs",
    ):
        cli.observed_process_command_v1(plus_one)

    controller_reads = 0

    def forbidden_controller_read(_identity):
        nonlocal controller_reads
        controller_reads += 1
        raise AssertionError("nonzero publisher ordinal must fail before read")

    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="process ordinal differs",
    ):
        cli.reopen_controller_task_after_client_v1(
            parsed_binding={}, environ={}, raw_request=b"{}",
            observed_command=canonical, read_exact=forbidden_controller_read,
            expected_process_role=fixture.role,
            expected_phase=contract.BROAD_SCREEN_PHASE,
            expected_process_ordinal=1,
        )
    assert controller_reads == 0

    constructed = 0

    class ForbiddenClient:
        def __init__(self) -> None:
            nonlocal constructed
            constructed += 1

    monkeypatch.setattr(
        cli, "_read_stdin_bounded_v1",
        lambda: contract.canonical_json_bytes_v1(fixture.request()),
    )
    monkeypatch.setattr(cli, "GCSExactCreateOnceTransportV1", ForbiddenClient)
    monkeypatch.setattr(cli.os, "environ", {})
    with pytest.raises(cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error):
        cli.main()
    assert constructed == 0


def test_cli_transport_has_no_resolver_and_enforces_output_byte_ceiling(monkeypatch):
    cli = _load_cli()
    forbidden_methods = {
        "list", "list_blobs", "reload", "get_blob", "current_generation",
        "resolve", "metadata",
    }
    assert forbidden_methods.isdisjoint(vars(cli.GCSExactCreateOnceTransportV1))
    exact_raw = b"{}"
    exact_identity = _identity(
        f"gs://{cli.FIXED_BUCKET}/fixture/exact.json", exact_raw, "123456"
    )
    download_kwargs: list[dict[str, object]] = []

    class FakeBlob:
        def __init__(self, returned: bytes) -> None:
            self.returned = returned

        def download_as_bytes(self, **kwargs):
            download_kwargs.append(kwargs)
            return self.returned

    class FakeBucket:
        def __init__(self, returned: bytes) -> None:
            self.returned = returned

        def blob(self, _name, *, generation):
            assert generation == int(exact_identity["generation"])
            return FakeBlob(self.returned)

    class FakeClient:
        def __init__(self, returned: bytes) -> None:
            self.returned = returned

        def bucket(self, name):
            assert name == cli.FIXED_BUCKET
            return FakeBucket(self.returned)

    transport = object.__new__(cli.GCSExactCreateOnceTransportV1)
    transport._client = FakeClient(exact_raw)
    assert transport.read_exact(exact_identity) == exact_raw
    assert download_kwargs == [{
        "start": 0,
        "end": len(exact_raw),
        "if_generation_match": int(exact_identity["generation"]),
        "retry": None,
    }]
    oversized = dict(exact_identity)
    oversized["bytes"] = (
        aggregate.MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES + 1
    )
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="process body ceiling",
    ):
        transport.read_exact(oversized)
    assert len(download_kwargs) == 1
    transport._client = FakeClient(exact_raw + b"x")
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="exact-read body differs",
    ):
        transport.read_exact(exact_identity)
    assert len(download_kwargs) == 2

    body = {"large": "x" * 200}
    raw = contract.canonical_json_bytes_v1(body)
    descriptor = {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/fixture/too-large.json"
        ),
        "max_bytes": len(raw) - 1,
        "create_once": True,
    }
    called = 0

    def forbidden_publish(uri, value, prior):
        nonlocal called
        called += 1
        raise AssertionError("publish must not be reached")

    with pytest.raises(
        aggregate.CorpusR6CurrentBankCrossedScreenAggregateV1Error,
        match="byte ceiling",
    ):
        aggregate._publish_v1(
            body=body,
            descriptor=descriptor,
            prior_identity=None,
            publish_create_once=forbidden_publish,
        )
    assert called == 0


def test_production_files_are_json_only_and_dependency_closed():
    module_path = (
        ROOT / "src" / "nfl_dfs" / "research"
        / "corpus_r6_current_bank_crossed_screen_aggregate_v1.py"
    )
    for path in (module_path, CLI_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        assert not any(
            token in module_name
            for module_name in imported
            for token in (
                "residual_world", "later_period", "numpy", "selector",
                "selection_", "graph", "neo4j", "outcome", "scorer",
            )
        )
    source = module_path.read_text(encoding="utf-8")
    assert "build_terminal_root_from_stream_v1" in source
    assert "contract._minimal_aggregate_evaluation_record_v1" in source
    assert "def _minimal_aggregate_record_v1" not in source
    assert "contract.build_terminal_root_v1" not in source
    assert "predecessor_bodies=" not in source
