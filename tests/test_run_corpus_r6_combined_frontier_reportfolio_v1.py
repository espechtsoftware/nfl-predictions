from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import run_corpus_r6_combined_frontier_reportfolio_v1 as subject


_D = "d" * 64
_E = "e" * 64
_F = "f" * 64
_COMMIT = "a" * 40
_IMAGE = "sha256:" + "b" * 64
_SOURCE_TERMINAL_URI = "gs://source/predecessor/descriptive-terminal-v2.json"
_OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-combined-frontier-reportfolio/test-v1/"
)


def _identity(uri: str, value: object) -> dict[str, object]:
    raw = subject._canonical(value)
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _opaque_identity(uri: str) -> dict[str, object]:
    return {"uri": uri, "generation": "1", "sha256": _D, "bytes": 1}


def _predecessor_terminal() -> dict[str, object]:
    descriptors = []
    for ordinal in range(subject.TASK_COUNT):
        descriptors.append({
            "source_ordinal": ordinal,
            "slate_id": f"slate-{ordinal:02d}",
            "task_result_identity": _opaque_identity(
                f"gs://source/results/{ordinal:02d}.json"
            ),
            "task_result_sha256": _D,
            "science_result_sha256": _E,
            "union_lineup_count": 300,
        })
    return {
        "terminal_uri": _SOURCE_TERMINAL_URI,
        "terminal_sha256": _F,
        "task_manifest_identity": _opaque_identity("gs://source/manifest.json"),
        "task_manifest_sha256": _D,
        "later_source_identity": _opaque_identity("gs://source/later.json"),
        "task_results": descriptors,
    }


def _manifest(monkeypatch):
    terminal = _predecessor_terminal()
    monkeypatch.setattr(
        subject.predecessor_execution,
        "validate_descriptive_terminal_envelope_v2",
        lambda value: value,
    )
    terminal_identity = _identity(_SOURCE_TERMINAL_URI, terminal)
    manifest = subject.build_manifest_v1(
        predecessor_terminal=terminal,
        predecessor_terminal_identity=terminal_identity,
        terminal_build_receipt_identity=_opaque_identity(
            "gs://build/terminal-receipt.json"
        ),
        code_commit=_COMMIT,
        image_digest=_IMAGE,
        immutable_image_uri=f"us-central1/repository/image@{_IMAGE}",
        output_prefix=_OUTPUT_PREFIX,
    )
    manifest_identity = _identity(str(manifest["manifest_uri"]), manifest)
    return manifest, manifest_identity, terminal, terminal_identity


def _runtime(manifest, manifest_identity, *, ordinal: int = 0):
    environment = {
        "CLOUD_RUN_TASK_INDEX": str(ordinal),
        "CLOUD_RUN_TASK_COUNT": str(subject.TASK_COUNT),
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_JOB": subject.FIXED_REUSED_JOB_NAME,
        "CLOUD_RUN_EXECUTION": "frontier-execution-1",
        subject.ENABLE_ENV: subject.ENABLE_VALUE,
        subject.MANIFEST_IDENTITY_ENV: subject._canonical(
            manifest_identity
        ).decode("utf-8"),
        "CODE_SHA": manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": manifest["image_digest"],
    }
    return subject.build_runtime_authority_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        environment=environment,
        observed_command=subject.EXPECTED_COMMAND,
    )


def _raw_provider_terminal(
    manifest, manifest_identity, *, execution_id="frontier-execution-1"
):
    return {
        "execution_id": execution_id,
        "job_name": subject.FIXED_REUSED_JOB_NAME,
        "job_uid": subject.FIXED_REUSED_JOB_UID,
        "task_count": 54,
        "succeeded_count": 54,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
        "terminal": True,
        "provider_observed": True,
        "job_observation": subject.expected_provider_job_observation_v1(
            manifest=manifest, manifest_identity=manifest_identity
        ),
    }


def _provider_proof(manifest, manifest_identity, *, execution_id="frontier-execution-1"):
    return subject.build_provider_terminal_execution_v1(
        _raw_provider_terminal(
            manifest, manifest_identity, execution_id=execution_id
        ),
        manifest=manifest,
        manifest_identity=manifest_identity,
    )


class _Store:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}
        self.publications: list[str] = []

    def seed(self, identity, value):
        raw = subject._canonical(value)
        assert identity["bytes"] == len(raw)
        assert identity["sha256"] == sha256(raw).hexdigest()
        self.objects[str(identity["uri"])] = (raw, dict(identity))

    def read_exact(self, identity):
        raw, retained = self.objects[str(identity["uri"])]
        assert retained == identity
        return raw

    def open_known(self, uri, maximum_bytes):
        raw, identity = self.objects[uri]
        assert len(raw) <= maximum_bytes
        return raw, identity

    def publish_create_once(self, uri, raw):
        if uri in self.objects:
            retained, identity = self.objects[uri]
            assert retained == raw
            return identity
        identity = {
            "uri": uri,
            "generation": str(len(self.publications) + 10),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        self.publications.append(uri)
        return identity


def test_prepare_binds_exact_54_predecessor_results_and_is_score_free(
    monkeypatch,
):
    manifest, _manifest_identity, terminal, terminal_identity = _manifest(monkeypatch)
    store = _Store()
    outcome_calls = []
    monkeypatch.setattr(
        subject,
        "_open_predecessor_terminal",
        lambda _identity_value, *, store: (terminal, terminal_identity),
    )
    build_identity = manifest["terminal_build_receipt_identity"]
    monkeypatch.setattr(
        subject.l2b_panel,
        "_read_terminal_build_receipt",
        lambda *args, **kwargs: ({"complete": True}, build_identity),
    )
    monkeypatch.setattr(
        subject.grader,
        "open_outcome_snapshot_surface_v1",
        lambda *args, **kwargs: outcome_calls.append(True),
    )
    request = {
        "predecessor_terminal_identity": terminal_identity,
        "terminal_build_receipt_identity": build_identity,
        "code_commit": _COMMIT,
        "image_digest": _IMAGE,
        "immutable_image_uri": f"us-central1/repository/image@{_IMAGE}",
        "output_prefix": _OUTPUT_PREFIX,
    }
    result = subject.prepare_from_request_v1(request, store=store)
    prepared = subject._strict_json(
        store.objects[str(result["manifest_identity"]["uri"])][0],
        label="prepared manifest",
        maximum_bytes=subject.MAXIMUM_MANIFEST_BYTES,
    )
    assert len(prepared["task_bindings"]) == 54
    assert prepared["selector_ids"] == list(subject.SELECTOR_IDS)
    assert prepared["entry_budgets"] == [80, 100, 150]
    assert prepared["complete_union_candidate_source"] is True
    assert prepared["candidate_sieve_law"] == subject.frontier.SIEVE_LAW
    assert prepared["candidate_sieve_limit"] == 250
    assert prepared["old_book_membership_used_for_sieve"] is False
    assert prepared["predecessor_eight_selectors_rerun"] is False
    assert prepared["population_regeneration_performed"] is False
    assert prepared["outcome_columns_read"] == []
    assert outcome_calls == []

    tampered = deepcopy(prepared)
    tampered["task_bindings"][0]["predecessor_task_result_identity"][
        "generation"
    ] = "2"
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match=r"manifest fixed law differs|binding\[0\] differs",
    ):
        subject.validate_manifest_v1(tampered)


def test_provider_configure_launch_and_exact_terminal_status(monkeypatch):
    manifest, manifest_identity, _terminal, _terminal_identity = _manifest(monkeypatch)
    expected_observation = subject.expected_provider_job_observation_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )

    class Provider:
        configured = None

        def describe_job_identity(self, job_name):
            return {
                "job_name": subject.FIXED_REUSED_JOB_NAME,
                "job_uid": subject.FIXED_REUSED_JOB_UID,
                "project_id": subject.FIXED_PROJECT,
                "region": subject.FIXED_REGION,
                "provider_observed": True,
            }

        def update_existing_job(self, desired):
            self.configured = desired

        def describe_job(self, job_name):
            return expected_observation

        def launch_existing_job(self, job_name):
            return "frontier-execution-1"

        def describe_execution(self, execution_id):
            return _raw_provider_terminal(manifest, manifest_identity)

    provider = Provider()
    monkeypatch.setattr(
        subject, "_open_manifest", lambda _identity_value, *, store: (
            manifest, manifest_identity
        )
    )
    configured = subject.configure_existing_job_v1(
        manifest_identity=manifest_identity, store=object(), provider=provider
    )
    assert configured["new_job_created"] is False
    assert provider.configured["container_command"] == [
        subject.EXPECTED_COMMAND[0]
    ]
    assert provider.configured["container_args"] == list(
        subject.EXPECTED_COMMAND[1:]
    )
    assert provider.configured["task_count"] == 54
    assert provider.configured["max_retries"] == 0
    authority = provider.configured["container_environment"].pop(
        subject.JOB_AUTHORITY_SHA_ENV
    )
    assert authority == subject._hash(expected_observation)

    launched = subject.launch_existing_job_v1(
        manifest_identity=manifest_identity, store=object(), provider=provider
    )
    assert launched["execution_id"] == "frontier-execution-1"
    proof = subject.status_existing_execution_v1(
        manifest_identity=manifest_identity,
        execution_id="frontier-execution-1",
        store=object(),
        provider=provider,
    )
    assert proof["succeeded_count"] == 54
    assert proof["terminal"] is True
    assert subject.validate_provider_terminal_execution_v1(
        proof, manifest=manifest, manifest_identity=manifest_identity
    ) == proof
    fabricated = deepcopy(proof)
    fabricated["execution_id"] = "fabricated-execution"
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match="provider terminal proof differs",
    ):
        subject.validate_provider_terminal_execution_v1(
            fabricated, manifest=manifest, manifest_identity=manifest_identity
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("terminal", False, "not exact 54/54 terminal"),
        ("succeeded_count", 53, "not exact 54/54 terminal"),
        ("failed_count", 1, "not exact 54/54 terminal"),
        ("provider_observed", False, "not exact 54/54 terminal"),
    ],
)
def test_provider_terminal_rejects_fabricated_or_nonterminal_observation(
    monkeypatch, field, value, message
):
    manifest, manifest_identity, _terminal, _terminal_identity = _manifest(monkeypatch)
    raw = _raw_provider_terminal(manifest, manifest_identity)
    raw[field] = value
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match=message,
    ):
        subject.build_provider_terminal_execution_v1(
            raw, manifest=manifest, manifest_identity=manifest_identity
        )


def test_provider_terminal_rejects_mismatched_job_observation(monkeypatch):
    manifest, manifest_identity, _terminal, _terminal_identity = _manifest(monkeypatch)
    raw = _raw_provider_terminal(manifest, manifest_identity)
    raw["job_observation"] = deepcopy(raw["job_observation"])
    raw["job_observation"]["source_commit"] = "c" * 40
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match="provider job observation differs",
    ):
        subject.build_provider_terminal_execution_v1(
            raw, manifest=manifest, manifest_identity=manifest_identity
        )


def test_task_runs_only_new_frontier_core_on_exact_predecessor_matrix(monkeypatch):
    manifest, manifest_identity, _terminal, _terminal_identity = _manifest(monkeypatch)
    runtime = _runtime(manifest, manifest_identity)
    predecessor_result = {
        "task_result_sha256": _D,
        "science_result_sha256": _E,
        "science_result": {"sealed": "combined-eight-book-result"},
    }
    scores = np.ascontiguousarray(np.ones((300, 16)), dtype=np.float64)
    calls = []

    def _run(*, combined_result, all_block_score_matrix, source_ordinal):
        calls.append((combined_result, all_block_score_matrix, source_ordinal))
        return {"result_sha256": _F}

    normalized = {
        "source_ordinal": 0,
        "slate_id": "slate-00",
        "populations": [],
        "books": [{} for _ in range(12)],
        "later_source_identity": manifest["later_source_identity"],
    }
    monkeypatch.setattr(subject.frontier, "run_combined_frontier_reportfolio_v1", _run)
    monkeypatch.setattr(
        subject.frontier,
        "normalized_slate_for_grader_v1",
        lambda value, *, source_ordinal: normalized,
    )
    monkeypatch.setattr(
        subject.predecessor_science,
        "run_combined_population_all_block_v1",
        lambda *args, **kwargs: pytest.fail("old eight selectors were rerun"),
    )
    result = subject.build_task_result_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        runtime_authority=runtime,
        predecessor_task_result=predecessor_result,
        predecessor_task_result_identity=manifest["task_bindings"][0][
            "predecessor_task_result_identity"
        ],
        all_block_score_matrix=scores,
    )
    assert calls == [
        (predecessor_result["science_result"], scores, 0)
    ]
    assert result["book_count"] == 12
    assert result["entry_budgets"] == [80, 100, 150]
    assert result["predecessor_matrix_exact_sha_verified"] is True
    assert result["predecessor_eight_selectors_rerun"] is False
    assert result["population_regeneration_performed"] is False
    assert result["outcome_columns_read"] == []


def test_task_reconstructs_only_persisted_union_matrix_and_requires_old_sha(
    monkeypatch,
):
    manifest, _manifest_identity, terminal, terminal_identity = _manifest(monkeypatch)
    binding = manifest["task_bindings"][0]
    source_manifest = {
        "task_bindings": [{"profile_source_request": {"sealed": True}}],
    }
    source_manifest_identity = manifest["predecessor_task_manifest_identity"]
    players = tuple(SimpleNamespace(player_id=f"P{i:03d}") for i in range(20))
    scores = np.ascontiguousarray(np.ones((300, 16)), dtype=np.float64)
    union_rows = [{
        "lineup_id": f"L{i:03d}",
        "roster_player_ids": [f"P{slot:03d}" for slot in range(9)],
    } for i in range(300)]
    predecessor_result = {
        "source_ordinal": 0,
        "slate_id": "slate-00",
        "task_result_sha256": binding["predecessor_task_result_sha256"],
        "science_result_sha256": binding["predecessor_science_result_sha256"],
        "science_result": {
            "matrix_binding": {
                "shape": [300, 16],
                "player_ids_sha256": subject._hash(
                    [player.player_id for player in players]
                ),
                "score_matrix_sha256": subject.predecessor_science._score_matrix_sha256(
                    scores
                ),
            },
            "union": {"union_lineup_count": 300, "union_lineups": union_rows},
        },
    }
    prepared = SimpleNamespace(
        players=players,
        player_draws=np.ascontiguousarray(np.ones((20, 16)), dtype=np.float32),
        slate_id="slate-00",
    )
    monkeypatch.setattr(
        subject,
        "_open_predecessor_terminal",
        lambda _identity_value, *, store: (terminal, terminal_identity),
    )
    monkeypatch.setattr(
        subject.prior_operator,
        "_open_manifest",
        lambda _identity_value, *, store: (source_manifest, source_manifest_identity),
    )
    monkeypatch.setattr(
        subject,
        "_read_json",
        lambda *args, **kwargs: (
            predecessor_result, binding["predecessor_task_result_identity"]
        ),
    )
    monkeypatch.setattr(
        subject.predecessor_execution,
        "validate_task_result_v1",
        lambda *args, **kwargs: predecessor_result,
    )
    monkeypatch.setattr(
        subject.crossed,
        "_load_task_sources_v1",
        lambda *args, **kwargs: (
            prepared, {}, {"later_source_identity": manifest["later_source_identity"]}
        ),
    )
    monkeypatch.setattr(
        subject.predecessor_science,
        "run_combined_population_all_block_v1",
        lambda *args, **kwargs: pytest.fail("old selectors/populations were rerun"),
    )
    monkeypatch.setattr(subject, "cross_score_full_union", lambda *a, **k: scores)
    store = SimpleNamespace(read_exact=lambda identity: b"")
    retained, retained_identity, rebuilt = subject._reconstruct_predecessor_matrix_v1(
        manifest=manifest, source_ordinal=0, store=store
    )
    assert retained is predecessor_result
    assert retained_identity == binding["predecessor_task_result_identity"]
    assert rebuilt is scores

    tampered = scores.copy()
    tampered[0, 0] += 1.0
    monkeypatch.setattr(subject, "cross_score_full_union", lambda *a, **k: tampered)
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match="reconstructed predecessor matrix differs",
    ):
        subject._reconstruct_predecessor_matrix_v1(
            manifest=manifest, source_ordinal=0, store=store
        )


def test_real_artifact_smoke_is_task0_outcome_blind_and_never_publishes(
    monkeypatch,
):
    manifest, manifest_identity, _terminal, _terminal_identity = _manifest(monkeypatch)
    predecessor_identity = manifest["task_bindings"][0][
        "predecessor_task_result_identity"
    ]
    predecessor_result = {
        "task_result_sha256": _D,
        "science_result": {
            "matrix_binding": {"score_matrix_sha256": _E},
        },
    }
    scores = np.ascontiguousarray(np.ones((300, 16)), dtype=np.float64)
    frontier_result = {
        "result_sha256": _F,
        "frontier": {
            "shortlist_law": subject.frontier.SIEVE_LAW,
            "old_book_membership_used_for_sieve": False,
            "complete_union_lineup_count": 300,
            "complete_union_lineup_ids_sha256": _D,
            "complete_union_sieve_evidence_sha256": _E,
            "complete_union_modeled_world_mean_vector_payload_sha256": _D,
            "complete_union_modeled_world_mean_vector_binding_sha256": _E,
            "candidate_count": 250,
            "candidate_lineup_ids_sha256": _F,
            "candidate_sieve_evidence_sha256": _D,
            "prior_eight_book_union_count": 160,
            "prior_eight_book_union_lineup_ids_sha256": _E,
            "candidate_in_prior_eight_books_count": 150,
            "candidate_absent_from_prior_eight_books_count": 100,
            "source_books_sha256": _F,
        },
        "selectors": [
            {"strategy_id": selector_id} for selector_id in subject.SELECTOR_IDS
        ],
    }
    normalized = {
        "source_ordinal": 0,
        "slate_id": "slate-00",
        "populations": [],
        "books": [{} for _ in range(12)],
        "later_source_identity": manifest["later_source_identity"],
    }
    store = _Store()
    outcome_calls = []
    monkeypatch.setattr(
        subject, "_open_manifest", lambda _identity_value, *, store: (
            manifest, manifest_identity
        )
    )
    monkeypatch.setattr(
        subject,
        "_reconstruct_predecessor_matrix_v1",
        lambda **kwargs: (predecessor_result, predecessor_identity, scores),
    )
    monkeypatch.setattr(
        subject.frontier,
        "run_combined_frontier_reportfolio_v1",
        lambda **kwargs: frontier_result,
    )
    monkeypatch.setattr(
        subject.frontier,
        "normalized_slate_for_grader_v1",
        lambda *args, **kwargs: normalized,
    )
    monkeypatch.setattr(
        subject.grader,
        "open_outcome_snapshot_surface_v1",
        lambda *args, **kwargs: outcome_calls.append(True),
    )
    receipt = subject.smoke_from_request_v1(
        {"manifest_identity": manifest_identity}, store=store
    )
    assert receipt["source_ordinal"] == 0
    assert receipt["book_count"] == 12
    assert receipt["complete_union_lineup_count"] == 300
    assert receipt["candidate_sieve_count"] == 250
    assert receipt["candidate_absent_from_prior_eight_books_count"] == 100
    assert receipt["publication_performed"] is False
    assert receipt["population_regeneration_performed"] is False
    assert receipt["outcome_columns_read"] == []
    assert store.publications == []
    assert outcome_calls == []
    frontier_result["frontier"][
        "candidate_in_prior_eight_books_count"
    ] = 250
    frontier_result["frontier"][
        "candidate_absent_from_prior_eight_books_count"
    ] = 0
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match="smoke normalized binding differs",
    ):
        subject.smoke_from_request_v1(
            {"manifest_identity": manifest_identity}, store=store
        )


def test_preflight_smoke_needs_only_predecessor_terminal_and_proves_novel_sieve(
    monkeypatch,
):
    manifest, _manifest_identity, terminal, terminal_identity = _manifest(monkeypatch)
    predecessor_identity = manifest["task_bindings"][0][
        "predecessor_task_result_identity"
    ]
    predecessor_result = {
        "task_result_sha256": _D,
        "science_result": {
            "matrix_binding": {"score_matrix_sha256": _E},
        },
    }
    scores = np.ascontiguousarray(np.ones((300, 16)), dtype=np.float64)
    frontier_result = {
        "result_sha256": _F,
        "frontier": {
            "shortlist_law": subject.frontier.SIEVE_LAW,
            "old_book_membership_used_for_sieve": False,
            "complete_union_lineup_count": 300,
            "complete_union_lineup_ids_sha256": _D,
            "complete_union_sieve_evidence_sha256": _E,
            "complete_union_modeled_world_mean_vector_payload_sha256": _D,
            "complete_union_modeled_world_mean_vector_binding_sha256": _E,
            "candidate_count": 250,
            "candidate_lineup_ids_sha256": _F,
            "candidate_sieve_evidence_sha256": _D,
            "prior_eight_book_union_count": 160,
            "prior_eight_book_union_lineup_ids_sha256": _E,
            "candidate_in_prior_eight_books_count": 150,
            "candidate_absent_from_prior_eight_books_count": 100,
            "source_books_sha256": _F,
        },
        "selectors": [
            {"strategy_id": selector_id} for selector_id in subject.SELECTOR_IDS
        ],
    }
    normalized = {
        "source_ordinal": 0,
        "slate_id": "slate-00",
        "populations": [],
        "books": [{} for _ in range(12)],
        "later_source_identity": manifest["later_source_identity"],
    }
    store = _Store()
    monkeypatch.setattr(
        subject,
        "_open_predecessor_terminal",
        lambda _identity_value, *, store: (terminal, terminal_identity),
    )

    def _reconstruct(*, manifest, source_ordinal, store):
        assert source_ordinal == 0
        assert "terminal_build_receipt_identity" not in manifest
        assert manifest["task_bindings"][0]["predecessor_union_lineup_count"] == 300
        return predecessor_result, predecessor_identity, scores

    monkeypatch.setattr(subject, "_reconstruct_predecessor_matrix_v1", _reconstruct)
    monkeypatch.setattr(
        subject.frontier,
        "run_combined_frontier_reportfolio_v1",
        lambda **kwargs: frontier_result,
    )
    monkeypatch.setattr(
        subject.frontier,
        "normalized_slate_for_grader_v1",
        lambda *args, **kwargs: normalized,
    )
    monkeypatch.setattr(
        subject,
        "_open_manifest",
        lambda *args, **kwargs: pytest.fail("preflight smoke opened build manifest"),
    )
    monkeypatch.setattr(
        subject.grader,
        "open_outcome_snapshot_surface_v1",
        lambda *args, **kwargs: pytest.fail("preflight smoke opened outcomes"),
    )
    receipt = subject.preflight_smoke_from_request_v1(
        {"predecessor_terminal_identity": terminal_identity}, store=store
    )
    assert receipt["complete_union_lineup_count"] == 300
    assert receipt["candidate_sieve_count"] == 250
    assert receipt["candidate_absent_from_prior_eight_books_count"] == 100
    assert receipt["publication_performed"] is False
    assert receipt["outcome_columns_read"] == []
    assert store.publications == []


def test_collect_publishes_exact_54_by_12_normalized_surface_before_terminal(
    monkeypatch,
):
    manifest, manifest_identity, _terminal, _terminal_identity = _manifest(monkeypatch)
    store = _Store()
    pairs = []
    slates = []
    for ordinal in range(54):
        task_result = {
            "slate_id": f"slate-{ordinal:02d}",
            "task_result_sha256": _D,
            "frontier_result_sha256": _E,
            "normalized_slate_sha256": _F,
            "runtime_authority": {"execution_id": "frontier-execution-1"},
        }
        pairs.append((task_result, _opaque_identity(f"gs://new/{ordinal}.json")))
        slates.append({
            "source_ordinal": ordinal,
            "slate_id": f"slate-{ordinal:02d}",
            "populations": [{"population_id": "frontier", "dimensions": {}, "lineups": []}],
            "books": [{} for _ in range(12)],
            "later_source_identity": manifest["later_source_identity"],
        })
    outcome_calls = []
    monkeypatch.setattr(
        subject, "_open_manifest", lambda _identity_value, *, store: (
            manifest, manifest_identity
        )
    )
    monkeypatch.setattr(
        subject,
        "_open_all_task_results",
        lambda **kwargs: (pairs, tuple(slates)),
    )
    monkeypatch.setattr(
        subject.grader,
        "open_outcome_snapshot_surface_v1",
        lambda *args, **kwargs: outcome_calls.append(True),
    )
    class Provider:
        def __init__(self, observed_execution_id):
            self.observed_execution_id = observed_execution_id
            self.calls = []

        def describe_execution(self, execution_id):
            self.calls.append(execution_id)
            return _raw_provider_terminal(
                manifest,
                manifest_identity,
                execution_id=self.observed_execution_id,
            )

    provider = Provider("frontier-execution-1")
    result = subject.collect_from_request_v1(
        {
            "manifest_identity": manifest_identity,
            "execution_id": "frontier-execution-1",
        },
        store=store,
        provider=provider,
    )
    assert provider.calls == ["frontier-execution-1"]
    assert store.publications == [
        manifest["normalized_surface_uri"], manifest["terminal_uri"]
    ]
    surface = subject._strict_json(
        store.objects[manifest["normalized_surface_uri"]][0],
        label="surface",
        maximum_bytes=subject.MAXIMUM_NORMALIZED_SURFACE_BYTES,
    )
    assert len(surface["slates"]) == 54
    assert all(len(slate["books"]) == 12 for slate in surface["slates"])
    assert result["aggregate_book_count"] == 54 * 12
    assert surface["population_regeneration_performed"] is False
    assert surface["outcome_columns_read"] == []
    assert outcome_calls == []
    monkeypatch.setattr(
        subject.grader,
        "validate_external_normalized_terminal_v1",
        lambda *, adapter_id, slates: tuple(slates),
    )
    reopened, _terminal_identity, _retained_manifest, _normalized = (
        subject._reopen_terminal_and_surface_v1(
            result["terminal_identity"],
            store=store,
            reopen_task_results=False,
        )
    )
    assert reopened["provider_terminal_execution"]["execution_id"] == (
        "frontier-execution-1"
    )
    assert reopened[
        "provider_exact_54_of_54_terminal_validated_before_terminal"
    ] is True

    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match="provider status execution ID differs",
    ):
        subject.collect_from_request_v1(
            {
                "manifest_identity": manifest_identity,
                "execution_id": "frontier-execution-2",
            },
            store=store,
            provider=Provider("frontier-execution-1"),
        )


def test_grade_opens_outcomes_only_after_score_free_terminal_replay(monkeypatch):
    manifest, _manifest_identity, _terminal, terminal_identity = _manifest(monkeypatch)
    normalized = tuple({
        "source_ordinal": ordinal,
        "slate_id": f"slate-{ordinal:02d}",
        "populations": [],
        "books": [],
        "later_source_identity": manifest["later_source_identity"],
    } for ordinal in range(54))
    terminal = {
        "terminal_sha256": _D,
        "normalized_surface_identity": _opaque_identity("gs://new/surface.json"),
        "normalized_surface_sha256": _E,
        "later_source_identity": manifest["later_source_identity"],
    }
    events = []
    monkeypatch.setattr(
        subject,
        "_reopen_terminal_and_surface_v1",
        lambda *args, **kwargs: (
            events.append("terminal") or terminal,
            terminal_identity,
            manifest,
            normalized,
        ),
    )

    def _open_outcomes(**kwargs):
        assert events == ["terminal"]
        events.append("outcomes")
        snapshot = {
            "later_source_freeze_identity": manifest["later_source_identity"],
            "outcome_snapshot_sha256": _F,
        }
        keys = {
            ordinal: (2023, ordinal + 1, f"slate-{ordinal:02d}")
            for ordinal in range(54)
        }
        return snapshot, _opaque_identity("gs://outcomes/snapshot.json"), {}, keys

    monkeypatch.setattr(
        subject.grader, "open_outcome_snapshot_surface_v1", _open_outcomes
    )
    monkeypatch.setattr(
        subject.grader,
        "score_normalized_slates_v1",
        lambda **kwargs: [{"source_ordinal": ordinal} for ordinal in range(54)],
    )
    monkeypatch.setattr(
        subject.grader,
        "aggregate_normalized_slate_grades_v1",
        lambda grades: [{"coordinate": "one", "mean": 180.0}],
    )
    store = _Store()
    result = subject.grade_from_request_v1({
        "terminal_identity": terminal_identity,
        "outcome_snapshot_identity": _opaque_identity("gs://outcomes/snapshot.json"),
    }, store=store)
    assert events == ["terminal", "outcomes"]
    assert result["aggregate_cell_count"] == 1
    assert store.publications == [manifest["descriptive_grade_uri"]]


def test_cli_is_default_off_before_constructing_any_cloud_client(monkeypatch):
    monkeypatch.delenv(subject.ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        subject.prior_operator,
        "GCSExactTransportV1",
        lambda: pytest.fail("cloud client constructed while default-off"),
    )
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match="execution requires --execute",
    ):
        subject.main(["task"])
    with pytest.raises(
        subject.RunCorpusR6CombinedFrontierReportfolioV1Error,
        match="execution requires --execute",
    ):
        subject.main(["task", "--execute"])
