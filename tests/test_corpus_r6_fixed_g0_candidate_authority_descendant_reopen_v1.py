from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_descendant_reopen_v1 as reopen,
)
from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as release,
)
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as core_v1
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v2 as core
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_outer_candidate_authority_v3 as capture,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import (
    test_corpus_r6_fixed_g0_candidate_authority_release_v2 as release_fixture,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "corpus_r6_fixed_g0_actual_candidate_binding_v2.json"
)
HISTORICAL_CAPABILITY_SHA = (
    "cf92683b9a5469b67d977db3dba568aff7c93f5d15cd15ce5aa0d06592b1467d"
)
DESCENDANT_CAPABILITY_SHA_AT_05DF = (
    "d47081b01d786389087a4e60addb68004424f52c0e96989e5e576f7ef355b670"
)
DESCENDANT_BINDING_SHA_AT_05DF = (
    "d612adfc1a89d5b0894d4e8653af7282a53d3ea8673d87848709edc3695d7dc9"
)


def _actual_binding() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _project_descendant(
    retained: dict[str, object],
    *,
    capability_sha: str,
) -> dict[str, object]:
    projected = deepcopy(retained)
    projected["catalog_recovery_code_and_lock_binding"]["capability_sha256"] = (
        capability_sha
    )
    projected.pop("candidate_implementation_binding_sha256")
    projected["candidate_implementation_binding_sha256"] = source.canonical_sha256(
        projected
    )
    return projected


def _rehash(body: dict[str, object], field: str) -> None:
    body.pop(field, None)
    body[field] = source.canonical_sha256(body)


def _fixture_v1_bundle_with_replay_head(
    monkeypatch: pytest.MonkeyPatch,
    *,
    historical_head: str,
) -> dict[str, object]:
    store = release_fixture.fixture_v1.MemoryExactStore()
    state = release_fixture._install_core_fixture(monkeypatch, store=store)
    release_fixture._publish(store, state)
    bundle = core._downgrade_bundle(deepcopy(state["expected_bundle"]))
    terminal_binding = {
        "relative_path": "reports/fixture-final-lock.json",
        "git_commit_sha": historical_head,
        "sha256": source.canonical_sha256("fixture-final-lock"),
        "bytes": 123,
        "projection_successor_final_lock_sha256": source.canonical_sha256(
            "fixture-final-lock-body"
        ),
    }
    receipts = bundle["slate_derivation_receipts"]
    for receipt in receipts:
        receipt["catalog_terminal_final_lock_binding"] = deepcopy(
            terminal_binding
        )
        _rehash(receipt, "slate_derivation_sha256")
    panel = bundle["panel_derivation_receipt"]
    panel["catalog_terminal_final_lock_binding"] = deepcopy(terminal_binding)
    panel["g0_source_commit_sha"] = historical_head
    for ordinal, row in enumerate(panel["slates"]):
        row["slate_derivation_sha256"] = receipts[ordinal][
            "slate_derivation_sha256"
        ]
    manifest_sha = source.canonical_sha256(receipts)
    panel["slate_derivation_manifest_sha256"] = manifest_sha
    _rehash(panel, "panel_derivation_sha256")
    bundle["slate_derivation_manifest_sha256"] = manifest_sha
    bundle["panel_derivation_receipt"] = panel
    _rehash(bundle, "candidate_authority_bundle_sha256")
    return bundle


def _rebuild_v1_bundle_hash_cascade(bundle: dict[str, object]) -> None:
    receipts = bundle["slate_derivation_receipts"]
    panel = bundle["panel_derivation_receipt"]
    for ordinal, receipt in enumerate(receipts):
        panel["slates"][ordinal]["slate_derivation_sha256"] = receipt[
            "slate_derivation_sha256"
        ]
    manifest_sha = source.canonical_sha256(receipts)
    panel["slate_derivation_manifest_sha256"] = manifest_sha
    _rehash(panel, "panel_derivation_sha256")
    bundle["slate_derivation_manifest_sha256"] = manifest_sha
    bundle["panel_derivation_receipt"] = panel
    _rehash(bundle, "candidate_authority_bundle_sha256")


def _changed_leaf_paths(
    retained: object,
    projected: object,
    *,
    path: tuple[object, ...] = (),
) -> set[tuple[object, ...]]:
    if isinstance(retained, dict) and isinstance(projected, dict):
        assert set(retained) == set(projected)
        changed: set[tuple[object, ...]] = set()
        for key in retained:
            changed.update(
                _changed_leaf_paths(
                    retained[key], projected[key], path=(*path, key)
                )
            )
        return changed
    if isinstance(retained, list) and isinstance(projected, list):
        assert len(retained) == len(projected)
        changed = set()
        for ordinal, (left, right) in enumerate(zip(retained, projected, strict=True)):
            changed.update(
                _changed_leaf_paths(left, right, path=(*path, ordinal))
            )
        return changed
    return set() if retained == projected else {path}


def test_actual_published_root_accepts_only_observed_replay_head_hash_drift() -> None:
    retained = _actual_binding()
    assert retained["candidate_implementation_binding_sha256"] == (
        "e83013fb151da77263966c86632dd7c663a8caa5f9327ff5fda4c6890fa8283c"
    )
    core._validate_hash(
        retained,
        field="candidate_implementation_binding_sha256",
        label="actual retained candidate binding",
    )
    descendant = _project_descendant(
        retained, capability_sha=DESCENDANT_CAPABILITY_SHA_AT_05DF
    )
    assert descendant["candidate_implementation_binding_sha256"] == (
        DESCENDANT_BINDING_SHA_AT_05DF
    )
    assert (
        reopen.validate_replay_head_only_binding_drift_v1(
            retained_binding=retained,
            descendant_binding=descendant,
            historical_capability_sha256=HISTORICAL_CAPABILITY_SHA,
            descendant_capability_sha256=DESCENDANT_CAPABILITY_SHA_AT_05DF,
        )
        == retained
    )


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("catalog_inner_object_count",), 109),
        (
            (
                "catalog_recovery_code_and_lock_binding",
                "final_lock_commit_sha",
            ),
            "f" * 40,
        ),
        (
            ("candidate_implementation_measurements", 0, "sha256"),
            "f" * 64,
        ),
        (("uses_realized_outcomes",), True),
    ),
)
def test_coherently_rehashed_non_head_drift_is_rejected(
    path: tuple[object, ...],
    replacement: object,
) -> None:
    retained = _actual_binding()
    descendant = _project_descendant(
        retained, capability_sha=DESCENDANT_CAPABILITY_SHA_AT_05DF
    )
    target: object = descendant
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    descendant.pop("candidate_implementation_binding_sha256")
    descendant["candidate_implementation_binding_sha256"] = source.canonical_sha256(
        descendant
    )
    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="drift exceeds replay-time capability SHA",
    ):
        reopen.validate_replay_head_only_binding_drift_v1(
            retained_binding=retained,
            descendant_binding=descendant,
            historical_capability_sha256=HISTORICAL_CAPABILITY_SHA,
            descendant_capability_sha256=DESCENDANT_CAPABILITY_SHA_AT_05DF,
        )


def test_resolved_capability_hash_must_match_each_binding() -> None:
    retained = _actual_binding()
    descendant = _project_descendant(
        retained, capability_sha=DESCENDANT_CAPABILITY_SHA_AT_05DF
    )
    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="capability SHA differs from resolved authority",
    ):
        reopen.validate_replay_head_only_binding_drift_v1(
            retained_binding=retained,
            descendant_binding=descendant,
            historical_capability_sha256="a" * 64,
            descendant_capability_sha256=DESCENDANT_CAPABILITY_SHA_AT_05DF,
        )


def test_v1_replay_head_projection_changes_exactly_168_recursive_leaves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical_head = "1" * 40
    descendant_head = "2" * 40
    retained = _fixture_v1_bundle_with_replay_head(
        monkeypatch, historical_head=historical_head
    )
    projected = reopen._project_v1_replay_head_only_bundle(
        retained,
        historical_head=historical_head,
        descendant_head=descendant_head,
    )

    expected: set[tuple[object, ...]] = {
        ("candidate_authority_bundle_sha256",),
        ("slate_derivation_manifest_sha256",),
        (
            "panel_derivation_receipt",
            "catalog_terminal_final_lock_binding",
            "git_commit_sha",
        ),
        ("panel_derivation_receipt", "g0_source_commit_sha"),
        (
            "panel_derivation_receipt",
            "slate_derivation_manifest_sha256",
        ),
        ("panel_derivation_receipt", "panel_derivation_sha256"),
    }
    for ordinal in range(source.TASK_COUNT):
        expected.update({
            (
                "slate_derivation_receipts",
                ordinal,
                "catalog_terminal_final_lock_binding",
                "git_commit_sha",
            ),
            (
                "slate_derivation_receipts",
                ordinal,
                "slate_derivation_sha256",
            ),
            (
                "panel_derivation_receipt",
                "slates",
                ordinal,
                "slate_derivation_sha256",
            ),
        })
    assert len(expected) == 168
    assert _changed_leaf_paths(retained, projected) == expected
    assert all(
        receipt["catalog_terminal_final_lock_binding"]["git_commit_sha"]
        == descendant_head
        for receipt in projected["slate_derivation_receipts"]
    )
    assert projected["panel_derivation_receipt"]["g0_source_commit_sha"] == (
        descendant_head
    )


def test_v1_replay_head_projection_rejects_stable_lock_binding_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical_head = "1" * 40
    retained = _fixture_v1_bundle_with_replay_head(
        monkeypatch, historical_head=historical_head
    )
    receipt = retained["slate_derivation_receipts"][1]
    receipt["catalog_terminal_final_lock_binding"]["sha256"] = "f" * 64
    _rehash(receipt, "slate_derivation_sha256")
    _rebuild_v1_bundle_hash_cascade(retained)

    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="slate terminal bindings differ",
    ):
        reopen._project_v1_replay_head_only_bundle(
            retained,
            historical_head=historical_head,
            descendant_head="2" * 40,
        )


@pytest.mark.parametrize(
    ("defect", "message"),
    (
        ("receipt-schema", "schema/order differs"),
        ("receipt-cardinality", "receipt cardinality differs"),
        ("receipt-order", "schema/order differs"),
        ("panel-cardinality", "panel slate cardinality differs"),
        ("panel-order", "receipt order differs"),
    ),
)
def test_v1_replay_head_projection_rejects_schema_cardinality_and_order_drift(
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
    message: str,
) -> None:
    historical_head = "1" * 40
    retained = _fixture_v1_bundle_with_replay_head(
        monkeypatch, historical_head=historical_head
    )
    receipts = retained["slate_derivation_receipts"]
    panel = retained["panel_derivation_receipt"]
    if defect == "receipt-schema":
        receipts[0]["schema_version"] = "wrong/v1"
        _rehash(receipts[0], "slate_derivation_sha256")
        _rebuild_v1_bundle_hash_cascade(retained)
    elif defect == "receipt-cardinality":
        receipts.pop()
        retained["slate_derivation_manifest_sha256"] = source.canonical_sha256(
            receipts
        )
        _rehash(retained, "candidate_authority_bundle_sha256")
    elif defect == "receipt-order":
        receipts[0], receipts[1] = receipts[1], receipts[0]
        retained["slate_derivation_manifest_sha256"] = source.canonical_sha256(
            receipts
        )
        _rehash(retained, "candidate_authority_bundle_sha256")
    elif defect == "panel-cardinality":
        panel["slates"].pop()
        _rehash(panel, "panel_derivation_sha256")
        retained["panel_derivation_receipt"] = panel
        _rehash(retained, "candidate_authority_bundle_sha256")
    else:
        panel["slates"][0], panel["slates"][1] = (
            panel["slates"][1],
            panel["slates"][0],
        )
        _rehash(panel, "panel_derivation_sha256")
        retained["panel_derivation_receipt"] = panel
        _rehash(retained, "candidate_authority_bundle_sha256")

    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match=message,
    ):
        reopen._project_v1_replay_head_only_bundle(
            retained,
            historical_head=historical_head,
            descendant_head="2" * 40,
        )


def test_replay_head_transitive_guard_path_surface_is_exact() -> None:
    expected_implementation = {
        "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v1.py",
        "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v2.py",
        "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_release_v2.py",
        "src/nfl_dfs/research/corpus_r6_fixed_g0_catalog_recovery_downstream_v1.py",
        "src/nfl_dfs/research/corpus_r6_fixed_g0_catalog_recovery_v1.py",
        "src/nfl_dfs/research/corpus_extreme_tail_panel_execution.py",
        "src/nfl_dfs/research/corpus_v12_panel_index.py",
        "src/nfl_dfs/research/corpus_artifact_source_authority.py",
        "src/nfl_dfs/research/corpus_parametric_batch.py",
        "src/nfl_dfs/research/lr8_later_period_source.py",
        "src/nfl_dfs/research/lr8_historical_arm.py",
        "src/nfl_dfs/research/residual_world_columns.py",
        "src/nfl_dfs/research/object_identity.py",
        "src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_projection_successor_v1.py",
        "src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py",
        "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py",
        "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py",
        "src/nfl_dfs/research/corpus_v12_import.py",
        "src/nfl_dfs/research/corpus_legal_feasibility.py",
    }
    expected_selection = {
        "reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index/g0-authority-lock-v1.json",
        "reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index/panel-index-live/published.json",
        "reports/corpus-parametric-runs/20260823-foundry-production-v12a/transport-live-v12a/batch-accepted.json",
        "reports/corpus-parametric-runs/20260823-foundry-production-v12b/transport-live-v12b/batch-accepted.json",
        "reports/2026-08-26-r6-player-catalog-fixed-g0-projection-successor-final-lock.json",
        "reports/2026-08-26-r6-player-catalog-fixed-g0-projection-successor-review-lock.json",
        "reports/2026-08-26-r6-player-catalog-fixed-g0-final-release-lock.json",
        "reports/2026-08-26-r6-fixed-g0-catalog-projection-source-completion-schema-failure.md",
        "reports/2026-08-26-r6-fixed-g0-projection-successor-focused-test-output.txt",
    }
    assert set(reopen.REPLAY_HEAD_STABLE_IMPLEMENTATION_PATHS) == (
        expected_implementation
    )
    assert set(reopen.REPLAY_HEAD_STABLE_SELECTION_PATHS) == expected_selection
    assert set(reopen.REPLAY_HEAD_STABLE_PATHS) == (
        expected_implementation | expected_selection
    )
    assert reopen.ADAPTER_MODULE_PATH not in reopen.REPLAY_HEAD_STABLE_PATHS


def test_transitive_guard_requires_historical_current_and_runtime_bytes_equal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    historical_head = "1" * 40
    descendant_head = "2" * 40
    raw_by_path: dict[str, bytes] = {}
    for relative_path in reopen.REPLAY_HEAD_STABLE_PATHS:
        raw = f"fixture:{relative_path}\n".encode()
        raw_by_path[relative_path] = raw
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    monkeypatch.setattr(reopen, "_G0_RUNTIME_SELECTION_PATHS", {})
    status_calls: list[tuple[str, ...]] = []

    def status(_root: Path, paths: tuple[str, ...]) -> bytes:
        status_calls.append(paths)
        return b""

    def blob(_root: Path, _commit: str, path: str) -> bytes:
        return raw_by_path[path]

    reopen._require_transitive_replay_paths_stable(
        repository_root=tmp_path,
        historical_head=historical_head,
        descendant_head=descendant_head,
        git_blob=blob,
        git_status=status,
    )
    assert status_calls == [reopen.REPLAY_HEAD_STABLE_PATHS]

    changed_path = reopen.REPLAY_HEAD_STABLE_IMPLEMENTATION_PATHS[0]

    def changed_dependency(
        _root: Path, commit: str, path: str,
    ) -> bytes:
        if commit == descendant_head and path == changed_path:
            return raw_by_path[path] + b"descendant drift"
        return raw_by_path[path]

    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="changed between candidate and descendant HEAD",
    ):
        reopen._require_transitive_replay_paths_stable(
            repository_root=tmp_path,
            historical_head=historical_head,
            descendant_head=descendant_head,
            git_blob=changed_dependency,
            git_status=status,
        )

    changed_lock = reopen.REPLAY_HEAD_STABLE_SELECTION_PATHS[0]

    def changed_historical_lock(
        _root: Path, commit: str, path: str,
    ) -> bytes:
        if commit == historical_head and path == changed_lock:
            return raw_by_path[path] + b"historical drift"
        return raw_by_path[path]

    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="changed between candidate and descendant HEAD",
    ):
        reopen._require_transitive_replay_paths_stable(
            repository_root=tmp_path,
            historical_head=historical_head,
            descendant_head=descendant_head,
            git_blob=changed_historical_lock,
            git_status=status,
        )


def test_transitive_guard_rejects_dirty_current_path_set(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="must be tracked-clean",
    ):
        reopen._require_transitive_replay_paths_stable(
            repository_root=tmp_path,
            historical_head="1" * 40,
            descendant_head="2" * 40,
            git_blob=lambda *_: b"fixture",
            git_status=lambda *_: b" M dependency.py\n",
        )


def test_historical_head_callback_is_repository_root_bound(tmp_path: Path) -> None:
    callback = reopen._historical_git_head(
        repository_root=tmp_path,
        historical_head="1" * 40,
    )
    assert callback(tmp_path) == "1" * 40
    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="repository root differs",
    ):
        callback(tmp_path / "alternate")


def test_final_clean_head_recheck_rejects_replay_toctou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reopen.catalog_adapter,
        "SubprocessGitRepositoryV1",
        lambda _root: SimpleNamespace(
            require_current_clean_head=lambda: "3" * 40
        ),
    )
    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="clean HEAD changed during descendant replay",
    ):
        reopen._require_current_head_unchanged(
            repository_root=Path("/fixture"), expected_head="2" * 40
        )


def test_adapter_is_part_of_capture_plan_measured_implementation() -> None:
    assert reopen.ADAPTER_MODULE_PATH in (
        capture.CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS
    )
    assert capture.candidate_descendant is reopen


def test_replay_boundary_requires_ancestry_and_both_durable_heads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound_head = "1" * 40
    current_head = "2" * 40
    repository = SimpleNamespace(require_current_clean_head=lambda: current_head)
    monkeypatch.setattr(
        reopen.catalog_adapter,
        "SubprocessGitRepositoryV1",
        lambda _root: repository,
    )
    ancestry: list[tuple[str, str]] = []
    reachable: list[str] = []
    monkeypatch.setattr(
        reopen.recovery,
        "require_git_ancestor_v1",
        lambda _repository, *, ancestor_commit_sha, descendant_commit_sha, **_: (
            ancestry.append((ancestor_commit_sha, descendant_commit_sha))
        ),
    )
    monkeypatch.setattr(
        reopen.recovery,
        "require_commit_reachable_from_remote_v1",
        lambda _repository, *, commit_sha: reachable.append(commit_sha),
    )
    historical_capability = SimpleNamespace(
        current_clean_commit_sha=bound_head,
        capability_sha256=HISTORICAL_CAPABILITY_SHA,
        stable="same",
    )
    descendant_capability = SimpleNamespace(
        current_clean_commit_sha=current_head,
        capability_sha256=DESCENDANT_CAPABILITY_SHA_AT_05DF,
        stable="same",
    )
    historical_attempt = SimpleNamespace(stable="same")
    descendant_attempt = SimpleNamespace(stable="same")

    def resolve(*, current_head: str, **_: object):
        if current_head == bound_head:
            return historical_capability, historical_attempt
        assert current_head == "2" * 40
        return descendant_capability, descendant_attempt

    monkeypatch.setattr(reopen.recovery, "resolve_tracked_attempt_binding_v1", resolve)
    monkeypatch.setattr(
        reopen,
        "_capability_stable_projection",
        lambda capability: {"stable": capability.stable},
    )
    monkeypatch.setattr(
        reopen,
        "_attempt_stable_projection",
        lambda attempt, **_: {"stable": attempt.stable},
    )

    result = reopen._resolve_replay_heads(
        repository_root=Path("/fixture"), bound_head=bound_head
    )
    assert result[0] == current_head
    assert ancestry == [(bound_head, current_head)]
    assert reachable == [bound_head, current_head]


def test_replay_boundary_rejects_non_durable_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound_head = "1" * 40
    current_head = "2" * 40
    repository = SimpleNamespace(require_current_clean_head=lambda: current_head)
    monkeypatch.setattr(
        reopen.catalog_adapter,
        "SubprocessGitRepositoryV1",
        lambda _root: repository,
    )
    monkeypatch.setattr(
        reopen.recovery, "require_git_ancestor_v1", lambda *_, **__: None
    )

    def require_remote(_repository: object, *, commit_sha: str) -> None:
        if commit_sha == current_head:
            raise ValueError("current head is not durable")

    monkeypatch.setattr(
        reopen.recovery,
        "require_commit_reachable_from_remote_v1",
        require_remote,
    )
    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="candidate replay Git boundary differs",
    ):
        reopen._resolve_replay_heads(
            repository_root=Path("/fixture"), bound_head=bound_head
        )


def test_replay_boundary_rejects_stable_lock_or_code_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound_head = "1" * 40
    current_head = "2" * 40
    repository = SimpleNamespace(require_current_clean_head=lambda: current_head)
    monkeypatch.setattr(
        reopen.catalog_adapter,
        "SubprocessGitRepositoryV1",
        lambda _root: repository,
    )
    monkeypatch.setattr(
        reopen.recovery, "require_git_ancestor_v1", lambda *_, **__: None
    )
    monkeypatch.setattr(
        reopen.recovery,
        "require_commit_reachable_from_remote_v1",
        lambda *_, **__: None,
    )
    historical_capability = SimpleNamespace(
        current_clean_commit_sha=bound_head,
        capability_sha256=HISTORICAL_CAPABILITY_SHA,
        stable="original",
    )
    descendant_capability = SimpleNamespace(
        current_clean_commit_sha=current_head,
        capability_sha256=DESCENDANT_CAPABILITY_SHA_AT_05DF,
        stable="drift",
    )

    def resolve(*, current_head: str, **_: object):
        capability = (
            historical_capability
            if current_head == bound_head
            else descendant_capability
        )
        return capability, SimpleNamespace(stable="same")

    monkeypatch.setattr(reopen.recovery, "resolve_tracked_attempt_binding_v1", resolve)
    monkeypatch.setattr(
        reopen,
        "_capability_stable_projection",
        lambda capability: {"stable": capability.stable},
    )
    monkeypatch.setattr(
        reopen,
        "_attempt_stable_projection",
        lambda attempt, **_: {"stable": attempt.stable},
    )
    with pytest.raises(
        reopen.CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error,
        match="changed beyond its replay-time HEAD",
    ):
        reopen._resolve_replay_heads(
            repository_root=Path("/fixture"), bound_head=bound_head
        )


def test_descendant_adapter_still_byte_rebuilds_complete_candidate_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = release_fixture.fixture_v1.MemoryExactStore()
    state = release_fixture._install_core_fixture(monkeypatch, store=store)
    retained_binding = state["binding"]
    retained_binding["catalog_recovery_code_and_lock_binding"]["capability_sha256"] = (
        HISTORICAL_CAPABILITY_SHA
    )
    retained_binding.pop("candidate_implementation_binding_sha256")
    retained_binding["candidate_implementation_binding_sha256"] = (
        source.canonical_sha256(retained_binding)
    )
    root, root_identity = release_fixture._publish(store, state)
    expected_bundle = deepcopy(state["expected_bundle"])
    assert expected_bundle is not None
    store.read_calls.clear()

    current_head = "2" * 40
    historical_capability = SimpleNamespace(capability_sha256=HISTORICAL_CAPABILITY_SHA)
    descendant_capability = SimpleNamespace(
        capability_sha256=DESCENDANT_CAPABILITY_SHA_AT_05DF
    )
    monkeypatch.setattr(
        reopen,
        "_resolve_replay_heads",
        lambda **_: (
            current_head,
            historical_capability,
            object(),
            descendant_capability,
            object(),
        ),
    )
    transitive_closure_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        reopen,
        "_require_transitive_replay_paths_stable",
        lambda *, historical_head, descendant_head, **_: (
            transitive_closure_calls.append((historical_head, descendant_head))
        ),
    )
    final_head_calls: list[str] = []
    monkeypatch.setattr(
        reopen,
        "_require_current_head_unchanged",
        lambda *, expected_head, **_: final_head_calls.append(expected_head),
    )
    head_projection_calls: list[tuple[str, str]] = []

    def project_head(
        value: object,
        *,
        historical_head: str,
        descendant_head: str,
    ) -> dict[str, object]:
        head_projection_calls.append((historical_head, descendant_head))
        projected = deepcopy(value)
        for receipt in projected["slate_derivation_receipts"]:
            receipt["catalog_binding"] = {"fixture": True}
            _rehash(receipt, "slate_derivation_sha256")
        _rebuild_v1_bundle_hash_cascade(projected)
        return projected

    monkeypatch.setattr(
        reopen, "_project_v1_replay_head_only_bundle", project_head
    )
    descendant_binding = _project_descendant(
        retained_binding, capability_sha=DESCENDANT_CAPABILITY_SHA_AT_05DF
    )
    authority = SimpleNamespace(
        inner_replay_receipt_identity=state["catalog_receipt_identity"]
    )
    monkeypatch.setattr(
        core,
        "_open_outer_and_binding",
        lambda **_: (authority, deepcopy(descendant_binding)),
    )
    replay_completed = 0
    outer_manifest_checked = False
    v1_validated_heads: list[str] = []
    bundle_upgraded = False

    def gated_reader(**_: object):
        def complete() -> None:
            nonlocal replay_completed
            replay_completed += 1

        return store.read_exact, complete

    def validate_v1(value: object, **kwargs: object) -> dict[str, object]:
        observed_head = kwargs["git_head"](kwargs["repository_root"])
        v1_validated_heads.append(observed_head)
        projected = deepcopy(value)
        if observed_head == current_head:
            assert all(
                receipt["catalog_binding"] == {"fixture": True}
                for receipt in projected["slate_derivation_receipts"]
            )
        else:
            assert observed_head == "1" * 40
            assert all(
                "catalog_binding" not in receipt
                for receipt in projected["slate_derivation_receipts"]
            )
        return projected

    def require_outer(**_: object) -> None:
        nonlocal outer_manifest_checked
        outer_manifest_checked = True

    def upgrade_bundle(
        _value: object,
        *,
        binding: object,
    ) -> dict[str, object]:
        nonlocal bundle_upgraded
        bundle_upgraded = True
        assert binding == retained_binding
        return deepcopy(expected_bundle)

    monkeypatch.setattr(core, "_outer_manifest_gated_reader", gated_reader)
    monkeypatch.setattr(
        core_v1, "validate_fixed_g0_candidate_authority_v1", validate_v1
    )
    monkeypatch.setattr(core, "_require_outer_manifest", require_outer)
    monkeypatch.setattr(core, "_upgrade_bundle", upgrade_bundle)
    callbacks = release_fixture._callbacks(store)
    callbacks["git_head"] = lambda _root: current_head
    reopened = reopen.reopen_fixed_g0_candidate_authority_from_descendant_v1(
        root_identity, **callbacks
    )

    assert reopened.root == root
    assert reopened.authority_bundle == expected_bundle
    assert v1_validated_heads == [current_head, "1" * 40]
    assert replay_completed == 2
    assert outer_manifest_checked is True
    assert bundle_upgraded is True
    assert head_projection_calls == [("1" * 40, current_head)]
    assert transitive_closure_calls == [("1" * 40, current_head)]
    assert final_head_calls == [current_head]
    assert store.read_calls[0].endswith(release.ROOT_FILENAME)
    assert len(store.read_calls) == release.TOTAL_OBJECT_COUNT
