from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.generation_exposure import SolveExposureLedger
from nfl_dfs.inference import prospective_generation_shadow_suite as suite
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries


def _fixture():
    players = [{
        "id": f"p{index:03d}",
        "name": f"P{index}",
        "pos": "WR",
        "team": f"T{index % 8}",
        "opp": f"T{(index + 1) % 8}",
        "game_id": f"G{index % 4}",
        "salary": 5_000,
    } for index in range(88)]
    draws = np.zeros((len(players), 50_000), dtype=np.float32)
    lineups = tuple(
        Lineup([*players[:8], players[8 + index]], tag="lev")
        for index in range(80)
    )
    totals = np.zeros((80, 50_000), dtype=np.float32)
    for lineup in lineups:
        lineup.model_version = "tail-k1/test"
        lineup.role_model_version = "tail-k1-role/test"
    def ledger(source: str, counts: dict[str, int]):
        builder = SolveExposureLedger(source_label=source)
        for family, count in counts.items():
            for ordinal in range(count):
                builder.record(
                    family=family,
                    requested_ordinal=ordinal,
                    status="exhausted",
                )
        return builder.finalize(expected_requests_by_family=counts)
    batches = {}
    selected = {}
    for arm in suite.ARM_ORDER:
        leverage, boom = {
            "incumbent-160-40": (160, 40),
            "boom-first-40-160": (40, 160),
            "cross-law-40-100-60": (40, 100),
            "boom-dose-40-360": (40, 360),
            "ceiling-all-boom-0-200": (0, 0),
        }[arm]
        ledgers = {
            label: ledger(
                label,
                {"leverage": leverage, "boom": boom, "role_epistemic": 12},
            )
            for label in suite.SEED_LABELS
        }
        transform_name = (
            "cross_law_discovery" if arm == "cross-law-40-100-60"
            else "all_boom_ceiling" if arm == "ceiling-all-boom-0-200"
            else None
        )
        transforms = {
            label: (
                {transform_name: {
                    "receipt_sha256": "a" * 64,
                    **(
                        {"exposure_ledger": ledger(
                            f"{label}-xlaw", {"boom:xlaw": 60}
                        )}
                        if transform_name == "cross_law_discovery"
                        else {"solve_exposure_ledger": ledger(
                            f"{label}-ceiling", {"boom": 200}
                        )}
                    ),
                }}
                if transform_name else {}
            )
            for label in suite.SEED_LABELS
        }
        batch = CandidateBatch(
            candidates=lineups,
            candidate_totals=totals,
            player_ids=tuple(player["id"] for player in players),
            player_rows=tuple(players),
            row_draws=draws,
            all_tags={lineup.ids: (lineup.tag,) for lineup in lineups},
            metadata={
                "portfolio": "CBWU",
                "world_blocks": 5,
                "worlds_per_block": [10_000] * 5,
                "native_generation_exposure_ledgers": ledgers,
                "native_generation_transform_receipts": transforms,
            },
        )
        batches[arm] = batch
        picked = select_tail_entries(
            totals, suite.ENTRIES, suite.TAIL_LINE,
            env=suite.arm_environments()[arm],
        )
        selected[arm] = [lineups[index] for index in picked]
    mapping = {
        player["id"]: f"dk-{index:03d}"
        for index, player in enumerate(players)
    }
    audit = np.ones((len(players), suite.AUDIT_WORLD_COUNT), dtype=np.float32)
    audit_receipt = {
        "schema_version": "prospective-generation-independent-audit-bank/v1",
        "world_seed": suite.AUDIT_WORLD_SEED,
        "world_count": suite.AUDIT_WORLD_COUNT,
        "model_version": "tail-k1/test",
        "player_order_sha256": suite.canonical_sha256(
            [str(player["id"]) for player in players]
        ),
        "world_bank_receipt": suite._array_receipt(audit),
        "candidate_solves_run": 0,
        "used_for_selection": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    audit_receipt["receipt_sha256"] = suite.canonical_sha256(audit_receipt)
    return batches, selected, mapping, audit, audit_receipt


def test_arm_environments_freeze_every_requested_arm() -> None:
    environments = suite.arm_environments()
    receipt = suite.validate_arm_environments(environments)

    assert tuple(environments) == suite.ARM_ORDER
    assert receipt["per_block_allocations"]["incumbent-160-40"] == {
        "leverage": 160,
        "base_boom": 40,
        "role": 12,
        "transformed_boom": 0,
        "requested_core": 200,
        "requested_replacement_budget_native": 52,
        "requested_core_plus_role": 212,
    }
    assert receipt["per_block_allocations"]["boom-dose-40-360"][
        "base_boom"
    ] == 360
    assert receipt["per_slate_five_block_allocations"][
        "cross-law-40-100-60"
    ]["transformed_boom"] == 300


def test_arm_environment_drift_fails_closed() -> None:
    environments = suite.arm_environments()
    environments["cross-law-40-100-60"]["SELECT_LSE"] = "0.1"
    with pytest.raises(suite.ProspectiveGenerationShadowError):
        suite.validate_arm_environments(environments)


def test_multiarm_receipt_freezes_pools_prefixes_and_diagnostics() -> None:
    batches, selected, mapping, audit, audit_receipt = _fixture()
    receipt = suite.multiarm_prelock_receipt(
        batches, selected, mapping, suite.arm_environments(),
        audit_row_draws=audit,
        audit_bank_receipt=audit_receipt,
    )

    assert receipt["player_worlds_identical_across_all_arms"] is True
    assert set(receipt["arm_receipts"]) == set(suite.ARM_ORDER)
    assert set(receipt["memberships"]) == {"20", "40", "80"}
    assert all(
        len(receipt["memberships"]["80"][arm]) == 80
        for arm in suite.ARM_ORDER
    )
    assert receipt["registry"]["decision_rules"][
        "interim_horizon_weeks"
    ] == 8
    assert receipt["paired_comparisons"]["ceiling-all-boom-0-200"][
        "comparator"
    ] == "boom-first-40-160"
    assert receipt["arm_receipts"]["cross-law-40-100-60"][
        "simulated_diagnostics"
    ]["selected_family_counts"]
    crossing = receipt["generation_retrieval_crossing"]
    assert crossing["candidate_solves_requested_by_crossing"] == 0
    assert crossing["population_order"] == [
        "incumbent-160-40",
        "boom-first-40-160",
    ]
    assert len(crossing["cell_order"]) == 4
    assert crossing["report_thresholds"] == [194, 200, 210, 220, 230, 240]
    assert receipt["generation_retrieval_crossing_sha256"] == crossing[
        "receipt_sha256"
    ]
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["production_enabled"] is False
    assert receipt["audit_world_bank_used_for_selection"] is False
    assert receipt["thresholds"] == [194, 200, 210, 220, 230, 240]
    assert len(receipt["receipt_sha256"]) == 64


def test_multiarm_receipt_rejects_world_or_ledger_drift() -> None:
    batches, selected, mapping, audit, audit_receipt = _fixture()
    altered = dict(batches)
    changed = np.array(batches["boom-first-40-160"].row_draws, copy=True)
    changed[0, 0] = 1.0
    altered["boom-first-40-160"] = replace(
        batches["boom-first-40-160"], row_draws=changed
    )
    with pytest.raises(
        suite.ProspectiveGenerationShadowError,
        match="CBWU selection bank",
    ):
        suite.multiarm_prelock_receipt(
            altered, selected, mapping, suite.arm_environments(),
            audit_row_draws=audit,
            audit_bank_receipt=audit_receipt,
        )

    missing = dict(batches)
    metadata = deepcopy(missing["boom-first-40-160"].metadata)
    metadata["native_generation_exposure_ledgers"].pop("R4")
    missing["boom-first-40-160"] = replace(
        missing["boom-first-40-160"], metadata=metadata
    )
    with pytest.raises(
        suite.ProspectiveGenerationShadowError,
        match="exposure-ledger grid",
    ):
        suite.multiarm_prelock_receipt(
            missing, selected, mapping, suite.arm_environments(),
            audit_row_draws=audit,
            audit_bank_receipt=audit_receipt,
        )


def test_cli_exposes_generation_suite() -> None:
    from pathlib import Path

    cli = Path("src/nfl_dfs/cli.py").read_text()
    assert '"shadow-generation-suite"' in cli
    assert "prospective_generation_shadow_suite.main(" in cli
    assert 'p.add_argument("--draft-group-id", type=int, required=True)' in cli
    assert '"--slate-lock-at"' in cli


def test_trusted_object_creation_and_draft_group_lock_are_enforced() -> None:
    class Store:
        def classic_slates(self):
            return pd.DataFrame({
                "draft_group_id": [123, 123, 999],
                "game_start": [
                    "2026-09-13T17:00:00Z",
                    "2026-09-13T20:00:00Z",
                    "2026-09-14T00:00:00Z",
                ],
            })

    lock_at = suite._draft_group_lock_at(Store(), 123)
    assert lock_at == datetime(2026, 9, 13, 17, tzinfo=timezone.utc)

    class Blob:
        generation = 17
        time_created = datetime(2026, 9, 13, 16, tzinfo=timezone.utc)

        def upload_from_string(self, payload, **kwargs):
            self.payload = payload
            self.kwargs = kwargs

        def reload(self):
            return None

    blob = Blob()

    class Client:
        class Bucket:
            def blob(self, _name):
                return blob

        def bucket(self, _name):
            return self.Bucket()

    receipt = suite._json_create_only(
        Client(),
        bucket_name="bucket",
        object_name="terminal.json",
        value={"complete": True},
        must_precede=lock_at,
    )
    assert receipt["generation"] == 17
    assert receipt["precedes_slate_lock"] is True
    assert blob.kwargs["if_generation_match"] == 0

    blob.time_created = lock_at
    with pytest.raises(
        suite.ProspectiveGenerationShadowError,
        match="not frozen before slate lock",
    ):
        suite._json_create_only(
            Client(),
            bucket_name="bucket",
            object_name="late.json",
            value={"complete": True},
            must_precede=lock_at,
        )


def test_audit_bank_must_be_independent_of_every_selection_block() -> None:
    batches, selected, mapping, _audit, audit_receipt = _fixture()
    repeated = np.asarray(batches[suite.ARM_ORDER[0]].row_draws)[:, :10_000]
    tampered = dict(audit_receipt)
    tampered["world_bank_receipt"] = suite._array_receipt(repeated)
    tampered.pop("receipt_sha256")
    tampered["receipt_sha256"] = suite.canonical_sha256(tampered)
    with pytest.raises(
        suite.ProspectiveGenerationShadowError,
        match="repeats a selection/generation block",
    ):
        suite.multiarm_prelock_receipt(
            batches,
            selected,
            mapping,
            suite.arm_environments(),
            audit_row_draws=repeated,
            audit_bank_receipt=tampered,
        )
