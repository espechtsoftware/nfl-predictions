from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles


REAL_SOURCE_MANIFEST = Path("/tmp/r6-successor-source-manifest.json")
REAL_PROJECTION_BUNDLE = Path("/tmp/r6-successor-reality/slate-00.json")
REAL_LATER_SOURCE = Path(
    "/tmp/r6-current-bank-operator-8ae6c22a/165-later-source-freeze.json"
)


def _identity(uri: str, raw: bytes, generation: int = 1) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _source_rows() -> list[dict[str, object]]:
    rows = []
    for index in range(authority.TASK_COUNT):
        raw = f"projection-{index}".encode()
        rows.append({
            "source_ordinal": index,
            "source_task_binding_sha256": sha256(
                f"binding-{index}".encode()
            ).hexdigest(),
            "projection_bundle_identity": _identity(
                f"gs://fixture/projections/slate-{index:02d}.json",
                raw,
                generation=index + 1,
            ),
        })
    return rows


def _manifest(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    source = {
        "task_manifest_sha256": "a" * 64,
        "fixture": "source body is validated by the patched source adapter",
    }
    raw = authority.canonical_bytes_v1(source)
    identity = _identity("gs://fixture/source-manifest.json", raw)
    monkeypatch.setattr(authority, "_source_task_rows_v1", lambda value: _source_rows())
    return authority.build_task_manifest_v1(
        source_task_manifest_identity=identity,
        output_prefix=(
            contract.OUTPUT_NAMESPACE
            + "population-challengers/fixture-f7-f9-v1/"
        ),
        code_commit="b" * 40,
        image_digest="sha256:" + "c" * 64,
        reused_job_name="population-challenger",
        read_exact=lambda observed: raw if dict(observed) == identity else b"",
    )


def _rehash(value: dict[str, object], field: str) -> None:
    value[field] = authority.canonical_sha256_v1({
        key: item for key, item in value.items() if key != field
    })


def test_manifest_is_one_54_task_dispatch_with_equal_three_profile_work(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest = _manifest(monkeypatch)
    assert manifest["task_count"] == 54
    assert manifest["profile_count"] == 3
    assert manifest["solves_per_profile_per_slate"] == 1_000
    assert manifest["solves_per_task"] == 3_000
    assert manifest["total_solve_attempts"] == 162_000
    assert len(set(manifest["work_sha256_by_profile"].values())) == 1
    assert manifest["one_reused_job_for_all_tasks"] is True
    assert manifest["one_process_per_task_runs_all_profiles"] is True
    assert manifest["per_profile_deploy_allowed"] is False
    assert manifest["production_default_changes"] == []
    assert manifest["policy"]["uses_realized_outcomes"] is False
    assert manifest["inherited_constraint_surface"] == (
        profiles.InheritedConstraintSurface().payload()
    )
    assert manifest["inherited_constraint_conflicts"] == []
    for index, binding in enumerate(manifest["task_bindings"]):
        request = binding["request"]
        assert request["task_index"] == request["source_ordinal"] == index
        assert request["profile_order"] == list(profiles.PROFILE_ORDER)
        assert request["total_solves"] == 3_000
        assert len(set(request["work_sha256_by_profile"].values())) == 1
        assert binding["one_process_runs_all_profiles"] is True
        assert binding["dispatcher_command"] == list(authority.DISPATCHER_COMMAND)
    assert authority.validate_task_manifest_v1(deepcopy(manifest)) == manifest


def test_task_index_selects_one_exact_projection_and_output_namespace(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest = _manifest(monkeypatch)
    request = authority.task_request_v1(manifest, task_index=37)
    assert request["source_ordinal"] == 37
    assert request["projection_bundle_identity"]["uri"].endswith(
        "slate-37.json"
    )
    outputs = request["expected_outputs"]
    assert tuple(outputs["profile_lineup_uris"]) == profiles.PROFILE_ORDER
    assert outputs["task_result_uri"].endswith("slates/37/task-result.json")
    assert outputs["create_once"] is True


def test_rehashed_non_neutral_inherited_rule_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest = _manifest(monkeypatch)
    poisoned = deepcopy(manifest)
    binding = poisoned["task_bindings"][0]
    request = binding["request"]
    request["inherited_constraint_surface"]["qb_partner_min"] = 2
    _rehash(request, "request_sha256")
    binding["request_sha256"] = request["request_sha256"]
    _rehash(binding, "task_binding_sha256")
    poisoned["task_bindings_sha256"] = authority.canonical_sha256_v1(
        poisoned["task_bindings"]
    )
    _rehash(poisoned, "task_manifest_sha256")
    with pytest.raises(
        authority.CorpusR6PopulationChallengerAuthorityV1Error,
        match="equal-work/safety binding differs",
    ):
        authority.validate_task_manifest_v1(poisoned)


def test_rehashed_per_profile_work_change_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest = _manifest(monkeypatch)
    poisoned = deepcopy(manifest)
    poisoned["work_sha256_by_profile"][profiles.PROFILE_ORDER[-1]] = "d" * 64
    _rehash(poisoned, "task_manifest_sha256")
    with pytest.raises(
        authority.CorpusR6PopulationChallengerAuthorityV1Error,
        match="fixed authority differs",
    ):
        authority.validate_task_manifest_v1(poisoned)


def test_dispatcher_process_spec_binds_one_consolidated_image_command():
    spec = authority.dispatcher_process_spec_v1()
    assert spec["command"] == list(authority.DISPATCHER_COMMAND)
    assert spec["entrypoint_path"] == authority.DISPATCHER_IMAGE_PATH
    assert spec["one_process_runs_all_profiles_for_one_slate"] is True
    assert len(spec["entrypoint_sha256"]) == 64


@pytest.mark.skipif(
    not all(path.is_file() for path in (
        REAL_SOURCE_MANIFEST, REAL_PROJECTION_BUNDLE, REAL_LATER_SOURCE
    )),
    reason="local production-shaped outcome-blind artifacts are unavailable",
)
def test_real_54_slate_artifact_schema_smoke_reads_metadata_only():
    # Deliberately project an allow-list.  No candidate row, simulated matrix,
    # realized score, winner, rank, payout, or outcome value is accessed.
    source = json.loads(REAL_SOURCE_MANIFEST.read_bytes())
    projection = json.loads(REAL_PROJECTION_BUNDLE.read_bytes())
    later = json.loads(REAL_LATER_SOURCE.read_bytes())
    fold0 = projection["fold_projections"][0]
    slate = next(
        row for row in later["slates"] if row["slate_id"] == projection["slate_id"]
    )
    smoke = authority.build_outcome_blind_schema_projection_v1(
        source_manifest_metadata={
            key: source[key] for key in (
                "schema_version", "layer_id", "phase", "task_count",
                "uses_realized_outcomes", "task_manifest_sha256",
            )
        },
        projection_bundle_metadata={
            "schema_version": projection["schema_version"],
            "slate_id": projection["slate_id"],
            "source_ordinal": projection["source_ordinal"],
            "fold_count": projection["fold_count"],
            "fold_order": projection["fold_order"],
            "uses_realized_outcomes": projection["policy"][
                "uses_realized_outcomes"
            ],
            "historical_scoring_performed": projection["policy"][
                "historical_scoring_performed"
            ],
            "later_source_identity": fold0["later_source_identity"],
            "world_artifact_identities": fold0[
                "world_artifact_identities"
            ],
            "projection_bundle_sha256": projection[
                "projection_bundle_sha256"
            ],
        },
        later_source_metadata={
            "schema": later["schema"],
            "slate_count": later["slate_count"],
            "uses_realized_outcomes": later["uses_realized_outcomes"],
            "historical_scoring_licensed": later[
                "historical_scoring_licensed"
            ],
            "candidate_or_lineup_scores_read": later[
                "candidate_or_lineup_scores_read"
            ],
            "slate_id": slate["slate_id"],
            "season": slate["season"],
            "week": slate["week"],
            "catalog_count": len(slate["catalog"]),
            "artifact_blocks": [
                row["block"] for row in slate["artifact_receipts"]
            ],
        },
    )
    assert smoke["source_manifest"]["task_count"] == 54
    assert smoke["projection_bundle"]["slate_id"] == "2023-w01"
    assert smoke["later_source"]["catalog_count"] == 773
    assert smoke["outcome_or_score_values_read"] is False


@pytest.mark.skipif(
    not REAL_SOURCE_MANIFEST.is_file(),
    reason="local production-shaped source task manifest is unavailable",
)
def test_real_source_manifest_builds_exact_54_task_challenger_authority():
    raw = REAL_SOURCE_MANIFEST.read_bytes()
    identity = {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-current-bank-crossed-screens/"
            "20260828-r6-current-bank-crossed-screen-v6/authorities/"
            "task-manifests/01-broad-selection-receipt.json"
        ),
        "generation": "1787939485790168",
        "sha256": "ae8571ba9d2787e87a8f4820415b9c6d534b8181ee47d88d2566cbeed2745eb5",
        "bytes": 295788,
    }
    assert len(raw) == identity["bytes"]
    assert sha256(raw).hexdigest() == identity["sha256"]
    manifest = authority.build_task_manifest_v1(
        source_task_manifest_identity=identity,
        output_prefix=(
            contract.OUTPUT_NAMESPACE
            + "population-challengers/20260828-f7-f9-shared-bank-v1/"
        ),
        code_commit="e" * 40,
        image_digest="sha256:" + "f" * 64,
        reused_job_name="population-challenger",
        read_exact=lambda observed: raw if dict(observed) == identity else b"",
    )
    assert manifest["task_count"] == 54
    assert manifest["task_bindings"][0]["request"][
        "projection_bundle_identity"
    ]["sha256"] == (
        "01a74384b7b8255d42e059f110a8b64adc0a1efcb4a7a3908d003b280abfbcc3"
    )
