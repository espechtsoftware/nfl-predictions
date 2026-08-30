from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib

import pytest

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross
from nfl_dfs.research import corpus_r6_construction_allocation_shard_v1 as shard
from tests import test_corpus_r6_construction_allocation_cross_v1 as fixtures


def _source_authority(
    season: int, week: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    slate_id = f"{season}-w{week:02d}"
    lock = fixtures._identity(f"{slate_id}-lock")
    audit = fixtures._identity(f"{slate_id}-audit")
    receipts = {
        role: {
            "sha256": hashlib.sha256(
                f"{slate_id}/{role}".encode("ascii")
            ).hexdigest(),
            "bytes": 17,
            "rows": 1,
            "columns": ["fixture"],
        }
        for role in (
            "mixed_walk_forward_panel",
            "prelock_dst_projection",
            "common_lock_market_points",
            "tabpfn_marginals",
        )
    }
    manifest = cross.source_manifest_v1(
        season=season,
        week=week,
        slate_id=slate_id,
        input_frame_receipts=receipts,
        lock_identity=lock,
        audit_bank_identity=audit,
    )
    raw = cross.canonical_json_bytes(manifest)
    source = {
        "uri": f"gs://fixture/{slate_id}-source.json",
        "generation": "17",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return source, manifest, audit


def _rehash_shard(value: dict[str, object]) -> dict[str, object]:
    result = deepcopy(value)
    scientific = {
        key: nested
        for key, nested in result.items()
        if key not in {
            "scientific_sha256", "execution_observations", "shard_sha256",
        }
    }
    result["scientific_sha256"] = cross.canonical_sha256(scientific)
    shard_body = {
        key: nested for key, nested in result.items()
        if key != "shard_sha256"
    }
    result["shard_sha256"] = cross.canonical_sha256(shard_body)
    return result


def test_default_cloud_run_cardinality_is_one_task_per_exact_g0_slate():
    assert len(cross.EXPECTED_SLATE_IDS) == 54
    assert cross.EXPECTED_SLATE_IDS == tuple(
        f"{season}-w{week:02d}"
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    )


def test_shards_collect_to_direct_bytes_and_fail_closed(monkeypatch):
    policy = replace(
        ADOPTED_CLASSIC_POLICY,
        multiseed_worlds_per_block=3,
    )
    expected = ("2023-w01", "2023-w02")
    monkeypatch.setattr(cross, "ADOPTED_CLASSIC_POLICY", policy)
    monkeypatch.setattr(cross, "WORLDS_PER_BLOCK", 3)
    monkeypatch.setattr(cross, "EXPECTED_SLATE_IDS", expected)

    native_builder, _, _ = fixtures._fixture_builder(policy)
    slates = []
    for week in (1, 2):
        source, manifest, audit = _source_authority(2023, week)
        slates.append(cross.CrossSlate(
            2023,
            week,
            f"2023-w{week:02d}",
            source,
            manifest,
            audit,
        ))
    authority = cross.CrossPanelAuthority(
        panel_id=cross.FOUNDRY_G0_PANEL_ID,
        expected_slate_ids=expected,
        identity=dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
    )
    common = {
        "panel_id": "construction-allocation-shard-fixture-v1",
        "code_sha": "abcdef123456",
        "image_digest": "sha256:" + "b" * 64,
        "panel_authority": authority,
    }
    direct = cross.build_score_blind_cross_v1(
        list(reversed(slates)), native_builder, **common,
    )
    roots = [
        shard.build_score_blind_cross_shard_v1(
            slate,
            native_builder,
            expected_slate_ordinal=ordinal,
            runtime_execution_coordinate={
                "job_name": "fixture-reused-job",
                "execution_name": "fixture-execution-54",
                "task_index": ordinal,
                "task_count": len(cross.EXPECTED_SLATE_IDS),
                "task_attempt": 0,
            },
            **common,
        )
        for ordinal, slate in enumerate(slates)
    ]
    assert all(
        shard.validate_score_blind_cross_shard_v1(root) == root
        for root in roots
    )
    collected = shard.collect_score_blind_cross_shards_v1(roots)
    assert collected == direct
    assert cross.validate_score_blind_cross_v1(collected) == direct

    with pytest.raises(shard.ConstructionAllocationShardError):
        shard.collect_score_blind_cross_shards_v1(list(reversed(roots)))
    with pytest.raises(shard.ConstructionAllocationShardError):
        shard.collect_score_blind_cross_shards_v1([roots[0], roots[0]])
    with pytest.raises(shard.ConstructionAllocationShardError):
        shard.collect_score_blind_cross_shards_v1([roots[0]])

    different_image = deepcopy(roots[1])
    different_image["image_digest"] = "sha256:" + "c" * 64
    different_image = _rehash_shard(different_image)
    assert shard.validate_score_blind_cross_shard_v1(different_image)
    with pytest.raises(
        shard.ConstructionAllocationShardError,
        match="common authority",
    ):
        shard.collect_score_blind_cross_shards_v1([
            roots[0], different_image,
        ])

    timed = deepcopy(roots[0])
    timed["execution_observations"]["generation_timing_seconds"][
        "cells"
    ][cross.CELL_ORDER[0]][0]["leverage"] = 99.0
    timed = _rehash_shard(timed)
    assert timed["scientific_sha256"] == roots[0]["scientific_sha256"]
    assert timed["shard_sha256"] != roots[0]["shard_sha256"]
    assert shard.validate_score_blind_cross_shard_v1(timed) == timed

    forged_support = deepcopy(roots[0])
    forged_support["selection_scientific"]["cells"][
        cross.CELL_ORDER[0]
    ]["selection_certificate"]["support_sha256"] = "0" * 64
    forged_support = _rehash_shard(forged_support)
    with pytest.raises(shard.ConstructionAllocationShardError):
        shard.validate_score_blind_cross_shard_v1(forged_support)
