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
    replay_completed = False
    outer_manifest_checked = False
    v1_validated = False
    bundle_upgraded = False

    def gated_reader(**_: object):
        def complete() -> None:
            nonlocal replay_completed
            replay_completed = True

        return store.read_exact, complete

    def validate_v1(value: object, **_: object) -> dict[str, object]:
        nonlocal v1_validated
        v1_validated = True
        projected = core._downgrade_bundle(expected_bundle)
        assert source.canonical_json_bytes(value) == source.canonical_json_bytes(
            projected
        )
        for receipt in projected["slate_derivation_receipts"]:
            receipt["catalog_binding"] = {"fixture": True}
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
    assert v1_validated is True
    assert replay_completed is True
    assert outer_manifest_checked is True
    assert bundle_upgraded is True
    assert store.read_calls[0].endswith(release.ROOT_FILENAME)
    assert len(store.read_calls) == release.TOTAL_OBJECT_COUNT
