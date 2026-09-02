from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference import prospective_prelock_lineage_shadow_v1 as lineage_shadow
from nfl_dfs.inference.generation_exposure import SolveExposureLedger
from nfl_dfs.inference.prelock_candidate_lineage_v1 import (
    PrelockCandidateLineageError,
    canonical_json_bytes,
)
from nfl_dfs.inference.prelock_lineage_runtime_v1 import (
    PrelockLineageRuntimeError,
    RuntimePrelockLineageRecorder,
    build_prepared_entry_sidecar_v1,
    build_terminal_root_v1,
    publish_create_once_json,
    validate_runtime_envelope_v1,
)
from nfl_dfs.inference.prelock_lineage_settlement_v1 import (
    PrelockLineageSettlementError,
    build_first_loss_settlement_v1,
    build_individual_rescue_v1,
    reopen_frozen_selector_matrix_v1,
)
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries
from nfl_dfs.research import corpus_graph_vnext_contracts as graph_contract
from nfl_dfs.research.prelock_lineage_graph_summary_v1 import (
    validate_prelock_lineage_graph_summary_v1,
)


def _players() -> list[dict[str, object]]:
    positions = {
        1: "QB",
        2: "RB",
        3: "RB",
        4: "WR",
        5: "WR",
        6: "WR",
        7: "TE",
        8: "RB",
        9: "DST",
        10: "WR",
    }
    return [
        {
            "id": player_id,
            "name": f"P{player_id}",
            "pos": position,
            "team": "A" if player_id % 2 else "B",
            "opp": "B" if player_id % 2 else "A",
            "game_id": "A-B",
            "salary": 5_000,
            "proj": 20.0,
        }
        for player_id, position in positions.items()
    ]


def _batch() -> CandidateBatch:
    players = _players()
    by_id = {int(player["id"]): player for player in players}
    rosters = (
        (1, 2, 3, 4, 5, 6, 7, 8, 9),
        (1, 2, 3, 4, 5, 6, 7, 10, 9),
    )
    lineups = tuple(
        Lineup([by_id[player_id] for player_id in roster], tag="lev")
        for roster in rosters
    )
    draws = np.arange(60, dtype=np.float32).reshape(10, 6) / 10 + 15
    row_by_id = {int(player["id"]): ordinal for ordinal, player in enumerate(players)}
    totals = np.stack(
        [
            draws[[row_by_id[player_id] for player_id in roster]].sum(axis=0)
            for roster in rosters
        ]
    ).astype(np.float32)

    ledger = SolveExposureLedger(source_label="single")
    ledger.record(
        family="leverage",
        requested_ordinal=0,
        status="new",
        roster_ids=rosters[0],
    )
    ledger.record(
        family="leverage",
        requested_ordinal=1,
        retry_ordinal=0,
        status="dup",
        roster_ids=rosters[0],
    )
    ledger.record(
        family="leverage",
        requested_ordinal=1,
        retry_ordinal=1,
        status="new",
        roster_ids=rosters[1],
    )
    ledger.record(family="leverage", requested_ordinal=2, status="infeasible")
    ledger.record(family="leverage", requested_ordinal=3, status="exhausted")
    ledger.record(family="leverage", requested_ordinal=4, status="error")
    return CandidateBatch(
        candidates=lineups,
        candidate_totals=totals,
        player_ids=tuple(int(player["id"]) for player in players),
        player_rows=tuple(players),
        row_draws=draws,
        all_tags={lineup.ids: ("lev",) for lineup in lineups},
        metadata={
            "model_version": "model-v1",
            "candidate_input_receipt": {"sha256": "b" * 64},
            "generation_allocation": {"leverage_requested": 5},
            "generation_exposure_ledger": ledger.finalize(
                expected_requests_by_family={"leverage": 5}
            ),
        },
    )


def _header() -> dict[str, object]:
    return {
        "run_id": "runtime-lineage-001",
        "run_type": "shadow-capture",
        "season": 2026,
        "week": 1,
        "slate_id": "2026-w01-main",
        "draft_group_id": 12345,
        "contest_id": None,
        "slate_lock_at_utc": "2026-09-13T17:00:00Z",
        "frozen_at_utc": "2026-09-13T16:30:00Z",
        "entry_budget": 1,
        "policy_id": "week1-policy-v1",
        "selector_ids": ["coverage-selector-v1"],
        "effective_candidate_stage_id": "effective-candidates",
        "paid_strategy_id": None,
        "code_sha256": "a" * 64,
        "input_source_identities": [
            {
                "role": "salary-catalog",
                "uri": "gs://immutable/salary.csv",
                "generation": "123",
                "sha256": "c" * 64,
                "bytes": 100,
            }
        ],
    }


def _capture() -> tuple[dict[str, object], CandidateBatch, list[int]]:
    batch = _batch()
    published = []
    recorder = RuntimePrelockLineageRecorder(
        run_header=_header(),
        internal_to_draftable={
            player_id: player_id + 10_000 for player_id in batch.player_ids
        },
        salary_catalog_sha256="d" * 64,
        artifact_capture=published.append,
    )
    recorder(
        "pool_cap_admission",
        {
            "schema_version": "candidate-pool-cap-admission-trace/v1",
            "source_label": "single",
            "configured_cap": 0,
            "rows": [
                {
                    "input_ordinal": ordinal,
                    "output_ordinal": ordinal,
                    "internal_player_ids": sorted(str(value) for value in lineup.ids),
                    "source_family": "lev",
                    "retained": True,
                    "reason": "RETAINED_NATIVE",
                }
                for ordinal, lineup in enumerate(batch.candidates)
            ],
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        },
    )
    recorder(
        "native_candidate_batch",
        {
            "source_label": "single",
            "batch": batch,
        },
    )
    traces = []
    selected = select_tail_entries(
        batch.candidate_totals,
        1,
        float(batch.candidate_totals.mean()),
        trace_capture=traces.append,
    )
    recorder(
        "effective_candidate_selection",
        {
            "batch": batch,
            "tail_line": float(batch.candidate_totals.mean()),
            "selector_trace": traces[0],
            "raw_selected_indices": selected,
            "final_selected_indices": selected,
            "post_selector_peak_slice": 0,
            "post_selector_thesis_count": 0,
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        },
    )
    assert recorder.artifact == published[0]
    return published[0], batch, selected


def test_runtime_capture_reconciles_real_retry_and_selector_trace() -> None:
    artifact, batch, selected = _capture()
    reopened = validate_runtime_envelope_v1(artifact)

    assert reopened["sidecar"]["counts"] == {
        "proposal_request_count": 5,
        "solve_attempt_count": 5,
        "generated_occurrence_count": 3,
        "unique_generated_roster_count": 2,
        "dedupe_decision_count": 3,
        "admission_decision_count": 4,
        "effective_candidate_count": 2,
        "strategy_decision_count": 2,
        "raw_selected_count": 1,
        "final_book_lineup_count": 1,
        "prepared_entry_count": 0,
    }
    assert (
        reopened["sidecar"]["dedupe_decisions"][1]["disposition"]
        == "DUPLICATE_SAME_FAMILY"
    )
    assert "duration_seconds" not in canonical_json_bytes(reopened).decode()
    assert (
        reopened["matrix_identities"]["raw_selected_indices_sha256"]
        == sha256(canonical_json_bytes(selected)).hexdigest()
    )
    assert (
        reopened["matrix_identities"]["effective_candidate_totals"]["sha256"]
        == sha256(np.ascontiguousarray(batch.candidate_totals).tobytes()).hexdigest()
    )


def test_selector_trace_is_output_identical_and_dynamic() -> None:
    totals = np.array(
        [
            [200, 200, 100, 100],
            [200, 100, 200, 100],
            [100, 200, 200, 100],
            [100, 100, 100, 100],
        ],
        dtype=float,
    )
    ordinary = select_tail_entries(totals, 2, 150.0)
    traces = []
    traced = select_tail_entries(totals, 2, 150.0, trace_capture=traces.append)
    assert traced == ordinary
    assert traces[0]["selected_indices"] == ordinary
    assert traces[0]["steps"][0]["fresh_world_count"] == 2
    assert traces[0]["steps"][1]["fresh_world_count"] == 1
    assert traces[0]["decisions"][3]["selector_rank"] is None

    with pytest.raises(ValueError, match="binary-tail"):
        select_tail_entries(
            totals,
            2,
            150.0,
            env={"SELECT_LSE": "0.1"},
            trace_capture=lambda _: None,
        )


def test_prepared_sidecar_terminal_and_create_once(tmp_path) -> None:
    candidate, batch, selected = _capture()
    lineup = batch.candidates[selected[0]]
    draftable = {
        str(player_id): str(player_id + 10_000) for player_id in batch.player_ids
    }
    csv_bytes = b"filled-csv"
    event = {
        "schema_version": "paid-entry-capture/v1",
        "contest_id": "contest-1",
        "draft_group_id": 12345,
        "salary_catalog_sha256": "d" * 64,
        "csv_sha256": sha256(csv_bytes).hexdigest(),
        "csv_bytes": len(csv_bytes),
        "paid_export_receipt_sha256": "e" * 64,
        "entries": [
            {
                "export_ordinal": 0,
                "entry_id": "entry-1",
                "internal_player_ids": sorted(str(value) for value in lineup.ids),
                "dk_draftable_ids": sorted(
                    draftable[str(value)] for value in lineup.ids
                ),
                "paid_input_book_ordinal": 0,
                "slot_dk_draftable_ids": [
                    draftable[str(player["id"])] for player in lineup.slot_order()
                ],
            }
        ],
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    prepared = build_prepared_entry_sidecar_v1(candidate, event)
    mismatched_event = deepcopy(event)
    mismatched_event["entries"][0]["slot_dk_draftable_ids"][-1] = "999999"
    with pytest.raises(PrelockLineageRuntimeError, match="draftable roster"):
        build_prepared_entry_sidecar_v1(candidate, mismatched_event)
    candidate_bytes = canonical_json_bytes(candidate)
    prepared_bytes = canonical_json_bytes(prepared)
    matrix_bytes = np.ascontiguousarray(batch.candidate_totals).tobytes()

    terminal = build_terminal_root_v1(
        candidate_envelope=candidate,
        candidate_object_identity={
            "uri": "gs://immutable/candidate.json",
            "generation": "1",
            "sha256": sha256(candidate_bytes).hexdigest(),
            "bytes": len(candidate_bytes),
            "time_created": "2026-09-13T16:31:00Z",
        },
        selector_matrix_object_identity={
            "uri": "gs://immutable/selector-matrix.raw",
            "generation": "4",
            "sha256": sha256(matrix_bytes).hexdigest(),
            "bytes": len(matrix_bytes),
            "time_created": "2026-09-13T16:31:30Z",
        },
        prepared_entry_sidecar=prepared,
        prepared_entry_object_identity={
            "uri": "gs://immutable/prepared.json",
            "generation": "2",
            "sha256": sha256(prepared_bytes).hexdigest(),
            "bytes": len(prepared_bytes),
            "time_created": "2026-09-13T16:32:00Z",
        },
        csv_object_identity={
            "uri": "gs://immutable/filled.csv",
            "generation": "3",
            "sha256": sha256(csv_bytes).hexdigest(),
            "bytes": len(csv_bytes),
            "time_created": "2026-09-13T16:32:00Z",
        },
    )
    assert terminal["scope"] == "PAID_PREPARED_NOT_CONFIRMED"

    confirmed = build_first_loss_settlement_v1(
        candidate_envelope=candidate,
        opportunity_rosters=[
            {
                "opportunity_id": "prepared-final",
                "internal_player_ids": list(lineup.ids),
                "realized_score_milli": 240_000,
            }
        ],
        winner_score_milli=230_000,
        settled_at_utc="2026-09-14T00:00:00Z",
        prepared_entry_sidecar=prepared,
        confirmed_entries=[
            {
                "contest_id": "contest-1",
                "entry_id": "entry-1",
                "dk_draftable_ids": sorted(
                    draftable[str(value)] for value in lineup.ids
                ),
            }
        ],
    )
    assert confirmed["rows"][0]["first_observed_state"] == "PREPARED_CONFIRMED"
    with pytest.raises(
        PrelockLineageSettlementError,
        match="exact prepared EntryID and roster",
    ):
        build_first_loss_settlement_v1(
            candidate_envelope=candidate,
            opportunity_rosters=[
                {
                    "opportunity_id": "prepared-final",
                    "internal_player_ids": list(lineup.ids),
                    "realized_score_milli": 240_000,
                }
            ],
            winner_score_milli=230_000,
            settled_at_utc="2026-09-14T00:00:00Z",
            prepared_entry_sidecar=prepared,
            confirmed_entries=[
                {
                    "contest_id": "contest-1",
                    "entry_id": "entry-1",
                    "dk_draftable_ids": [f"wrong-{index}" for index in range(9)],
                }
            ],
        )

    destination = tmp_path / "terminal.json"
    first = publish_create_once_json(destination, terminal)
    second = publish_create_once_json(destination, terminal)
    assert first["created"] is True
    assert second["created"] is False
    changed = deepcopy(terminal)
    changed["scope"] = "SHADOW_CANDIDATE_ONLY"
    with pytest.raises(PrelockLineageRuntimeError, match="already differs"):
        publish_create_once_json(destination, changed)


def test_runtime_outcome_field_fails_before_publication() -> None:
    candidate, _, _ = _capture()
    tampered = deepcopy(candidate)
    tampered["actual_score"] = 250.0
    with pytest.raises((PrelockLineageRuntimeError, PrelockCandidateLineageError)):
        validate_runtime_envelope_v1(tampered)


def test_postlock_first_loss_and_individual_rescue_are_separate_and_nonjoint() -> None:
    candidate, batch, selected = _capture()
    omitted = 1 - selected[0]
    first_loss = build_first_loss_settlement_v1(
        candidate_envelope=candidate,
        opportunity_rosters=[
            {
                "opportunity_id": "final",
                "internal_player_ids": list(batch.candidates[selected[0]].ids),
                "realized_score_milli": 180_000,
            },
            {
                "opportunity_id": "omitted",
                "internal_player_ids": list(batch.candidates[omitted].ids),
                "realized_score_milli": 250_000,
            },
            {
                "opportunity_id": "outside",
                "internal_player_ids": [f"outside-{index}" for index in range(9)],
                "realized_score_milli": 260_000,
            },
        ],
        winner_score_milli=230_000,
        settled_at_utc="2026-09-14T00:00:00Z",
    )
    assert [row["first_observed_state"] for row in first_loss["rows"]] == [
        "FINAL_BOOK_NOT_PREPARED",
        "ELIGIBLE_NOT_SELECTED",
        "NOT_PRODUCED_IN_OBSERVED_REQUEST_UNIVERSE",
    ]
    scores = [250_000, 250_000]
    scores[selected[0]] = 180_000
    rescue = build_individual_rescue_v1(
        candidate_envelope=candidate,
        candidate_totals=batch.candidate_totals,
        realized_scores_milli=scores,
        winner_score_milli=230_000,
        tail_line=float(batch.candidate_totals.mean()),
        settled_at_utc="2026-09-14T00:00:00Z",
    )
    assert len(rescue["rows"]) == 1
    assert rescue["rows"][0]["forced_candidate_ordinal"] == omitted
    assert rescue["rows"][0]["individual_counterfactual_delta_milli"] == 70_000
    assert rescue["rows"][0]["rescued_book_beat_recorded_winner"] is True
    assert rescue["sum_is_jointly_achievable"] is False


def test_complete_engine_return_and_candidate_matrix_are_instrumentation_identical() -> (
    None
):
    pool = []
    ordinal = 0
    for pos, count, salary in (
        ("QB", 4, 6_000),
        ("RB", 8, 5_200),
        ("WR", 12, 4_800),
        ("TE", 6, 3_600),
        ("DST", 4, 2_800),
    ):
        for index in range(count):
            pool.append(
                {
                    "id": f"{pos}{index}",
                    "name": f"{pos}{index}",
                    "pos": pos,
                    "team": f"T{ordinal % 4}",
                    "opp": f"T{(ordinal + 1) % 4}",
                    "game_id": f"G{ordinal % 2}",
                    "salary": salary + 25 * index,
                    "proj": 9.0 + index % 5,
                    "season": 2025,
                    "week": 3,
                }
            )
            ordinal += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    draws = np.abs(np.random.default_rng(77).normal(10, 3, size=(len(pool), 32)))
    env = {
        "MIN_LINEUP_SALARY": "0",
        "N_QB_VARIANTS": "0",
        "N_DARKGAME": "0",
    }
    ordinary_batches = []
    ordinary = engine.tail_select_lineups(
        slate,
        pool,
        draws,
        tail_line=90.0,
        n_entries=2,
        stack=None,
        objective_col="proj",
        candidate_multiple=1,
        n_boom_solves=2,
        n_game_stacks=0,
        policy_env=env,
        candidate_capture=ordinary_batches.append,
        cand_log_table="",
    )
    header = {
        **_header(),
        "run_id": "engine-parity-001",
        "season": 2025,
        "week": 3,
        "slate_id": "2025-w03-main",
        "slate_lock_at_utc": "2025-09-21T17:00:00Z",
        "frozen_at_utc": "2025-09-21T16:30:00Z",
        "entry_budget": 2,
    }
    recorder = RuntimePrelockLineageRecorder(
        run_header=header,
        internal_to_draftable={
            row["id"]: 50_000 + index for index, row in enumerate(pool)
        },
        salary_catalog_sha256="d" * 64,
    )
    traced_batches = []
    traced = engine.tail_select_lineups(
        slate,
        pool,
        draws,
        tail_line=90.0,
        n_entries=2,
        stack=None,
        objective_col="proj",
        candidate_multiple=1,
        n_boom_solves=2,
        n_game_stacks=0,
        policy_env=env,
        candidate_capture=traced_batches.append,
        prelock_lineage_capture=recorder,
        cand_log_table="",
    )

    assert [lineup.ids for lineup in traced] == [lineup.ids for lineup in ordinary]
    assert len(ordinary_batches) == len(traced_batches) == 1
    assert [lineup.ids for lineup in traced_batches[0].candidates] == [
        lineup.ids for lineup in ordinary_batches[0].candidates
    ]
    assert (
        traced_batches[0].candidate_totals.tobytes()
        == ordinary_batches[0].candidate_totals.tobytes()
    )
    assert recorder.artifact is not None


def test_bounded_shadow_publishes_input_candidate_and_terminal_create_once(
    monkeypatch,
) -> None:
    batch = _batch()
    salaries = pd.DataFrame(
        {
            "dk_player_id": list(batch.player_ids),
            "dk_draftable_id": [10_000 + value for value in batch.player_ids],
            "salary": [5_000] * len(batch.player_ids),
        }
    )

    class Store:
        def classic_salaries(self, draft_group_id):
            return salaries.copy()

        def classic_slates(self):
            return pd.DataFrame(
                {
                    "draft_group_id": [12345],
                    "game_start": ["2026-09-13T17:00:00Z"],
                }
            )

    class DuplicateStore(Store):
        def classic_salaries(self, draft_group_id):
            return pd.concat((salaries, salaries.iloc[[0]]), ignore_index=True)

    class Blob:
        next_generation = 1

        def __init__(self, name):
            self.name = name
            self.generation = None
            self.time_created = None
            self.payload = None

        def upload_from_string(self, payload, *, content_type, if_generation_match):
            assert content_type in {"application/json", "application/octet-stream"}
            assert if_generation_match == 0
            if self.payload is not None:
                raise RuntimeError("precondition failed")
            self.payload = bytes(payload)
            self.generation = Blob.next_generation
            Blob.next_generation += 1
            self.time_created = datetime(2026, 9, 13, 16, tzinfo=UTC)

        def reload(self):
            return None

        def download_as_bytes(self):
            if self.payload is None:
                raise RuntimeError("missing object")
            return self.payload

    class Bucket:
        def __init__(self):
            self.blobs = {}

        def blob(self, name):
            if name not in self.blobs:
                self.blobs[name] = Blob(name)
            return self.blobs[name]

    class Storage:
        def __init__(self):
            self.selected_bucket = Bucket()

        def bucket(self, name):
            assert name == "test-bucket"
            return self.selected_bucket

    def fake_build_sim_lineups(*args, **kwargs):
        capture = kwargs["_prelock_lineage_capture"]
        capture(
            "pool_cap_admission",
            {
                "schema_version": "candidate-pool-cap-admission-trace/v1",
                "source_label": "single",
                "configured_cap": 0,
                "rows": [
                    {
                        "input_ordinal": ordinal,
                        "output_ordinal": ordinal,
                        "internal_player_ids": sorted(
                            str(value) for value in lineup.ids
                        ),
                        "source_family": "lev",
                        "retained": True,
                        "reason": "RETAINED_NATIVE",
                    }
                    for ordinal, lineup in enumerate(batch.candidates)
                ],
                "uses_realized_outcomes": False,
                "post_lock_data_read": False,
            },
        )
        capture("native_candidate_batch", {"source_label": "single", "batch": batch})
        traces = []
        selected = select_tail_entries(
            batch.candidate_totals,
            1,
            float(batch.candidate_totals.mean()),
            trace_capture=traces.append,
        )
        capture(
            "effective_candidate_selection",
            {
                "batch": batch,
                "tail_line": float(batch.candidate_totals.mean()),
                "selector_trace": traces[0],
                "raw_selected_indices": selected,
                "final_selected_indices": selected,
                "post_selector_peak_slice": 0,
                "post_selector_thesis_count": 0,
                "uses_realized_outcomes": False,
                "post_lock_data_read": False,
            },
        )
        return [batch.candidates[selected[0]]]

    monkeypatch.setattr(lineage_shadow, "ENTRY_BUDGET", 1)
    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups",
        fake_build_sim_lineups,
    )
    storage = Storage()
    implementation_sha256 = lineage_shadow.implementation_manifest_v1()[
        "implementation_sha256"
    ]
    with pytest.raises(
        lineage_shadow.ProspectivePrelockLineageShadowError,
        match="implementation manifest",
    ):
        lineage_shadow.run_prelock_lineage_shadow_v1(
            store=Store(),
            storage_client=storage,
            bucket_name="test-bucket",
            run_id="lineage-shadow-test",
            season=2026,
            week=1,
            draft_group_id=12345,
            expected_lock_at="2026-09-13T17:00:00Z",
            code_sha256="f" * 64,
            started_at=datetime(2026, 9, 13, 15, tzinfo=UTC),
            now_factory=lambda: datetime(2026, 9, 13, 16, 5, tzinfo=UTC),
        )
    assert storage.selected_bucket.blobs == {}
    with pytest.raises(
        lineage_shadow.ProspectivePrelockLineageShadowError,
        match="path-safe identifier",
    ):
        lineage_shadow.run_prelock_lineage_shadow_v1(
            store=Store(),
            storage_client=storage,
            bucket_name="test-bucket",
            run_id="../unsafe-run",
            season=2026,
            week=1,
            draft_group_id=12345,
            expected_lock_at="2026-09-13T17:00:00Z",
            code_sha256=implementation_sha256,
            started_at=datetime(2026, 9, 13, 15, tzinfo=UTC),
            now_factory=lambda: datetime(2026, 9, 13, 16, 5, tzinfo=UTC),
        )
    assert storage.selected_bucket.blobs == {}
    with pytest.raises(
        lineage_shadow.ProspectivePrelockLineageShadowError,
        match="repeats an internal player ID",
    ):
        lineage_shadow.run_prelock_lineage_shadow_v1(
            store=DuplicateStore(),
            storage_client=storage,
            bucket_name="test-bucket",
            run_id="lineage-shadow-test",
            season=2026,
            week=1,
            draft_group_id=12345,
            expected_lock_at="2026-09-13T17:00:00Z",
            code_sha256=implementation_sha256,
            started_at=datetime(2026, 9, 13, 15, tzinfo=UTC),
            now_factory=lambda: datetime(2026, 9, 13, 16, 5, tzinfo=UTC),
        )
    assert storage.selected_bucket.blobs == {}
    result = lineage_shadow.run_prelock_lineage_shadow_v1(
        store=Store(),
        storage_client=storage,
        bucket_name="test-bucket",
        run_id="lineage-shadow-test",
        season=2026,
        week=1,
        draft_group_id=12345,
        expected_lock_at="2026-09-13T17:00:00Z",
        code_sha256=implementation_sha256,
        started_at=datetime(2026, 9, 13, 15, tzinfo=UTC),
        now_factory=lambda: datetime(2026, 9, 13, 16, 5, tzinfo=UTC),
    )

    assert result["complete"] is True
    assert result["production_enabled"] is False
    assert set(storage.selected_bucket.blobs) == {
        "prelock_lineage/2026/week-01/lineage-shadow-test/input-authority.json",
        "prelock_lineage/2026/week-01/lineage-shadow-test/selector-matrix.raw",
        "prelock_lineage/2026/week-01/lineage-shadow-test/candidate-lineage.json",
        "prelock_lineage/2026/week-01/lineage-shadow-test/terminal.json",
        "prelock_lineage/2026/week-01/lineage-shadow-test/graph-summary-v2.json",
    }
    root = "prelock_lineage/2026/week-01/lineage-shadow-test/"
    candidate_value = json.loads(
        storage.selected_bucket.blobs[root + "candidate-lineage.json"].payload
    )
    frozen_matrix = reopen_frozen_selector_matrix_v1(
        candidate_envelope=candidate_value,
        raw_bytes=storage.selected_bucket.blobs[root + "selector-matrix.raw"].payload,
    )
    assert frozen_matrix.tobytes() == batch.candidate_totals.tobytes()
    assert frozen_matrix.flags.writeable is False
    terminal_value = json.loads(
        storage.selected_bucket.blobs[root + "terminal.json"].payload
    )
    graph_value = json.loads(
        storage.selected_bucket.blobs[root + "graph-summary-v2.json"].payload
    )
    terminal_blob = storage.selected_bucket.blobs[root + "terminal.json"]
    reopened = validate_prelock_lineage_graph_summary_v1(
        graph_value,
        candidate_envelope=candidate_value,
        terminal_root=terminal_value,
        terminal_object_identity={
            "uri": f"gs://test-bucket/{root}terminal.json",
            "generation": str(terminal_blob.generation),
            "sha256": sha256(terminal_blob.payload).hexdigest(),
            "bytes": len(terminal_blob.payload),
            "time_created": terminal_blob.time_created.isoformat(),
        },
    )
    assert reopened["summary_counts"] == candidate_value["sidecar"]["counts"]
    assert reopened["coverage"]["detailed_candidate_rows_included"] is False
    assert all(row["kind"] != "Lineup" for row in reopened["node_rows"])
    with pytest.raises(graph_contract.CorpusGraphVNextError):
        graph_contract.validate_node_row(
            {
                "kind": "MetricSet",
                "node_id": "forbidden-realized-metric",
                "namespace": "metric",
                "properties": {
                    "metric_set_id": "forbidden-realized-metric",
                    "definition_id": "actual-score",
                    "scope": "structural",
                    "value": 1,
                    "support": 1,
                    "missing": 0,
                },
            }
        )

    retry = lineage_shadow.run_prelock_lineage_shadow_v1(
        store=Store(),
        storage_client=storage,
        bucket_name="test-bucket",
        run_id="lineage-shadow-test",
        season=2026,
        week=1,
        draft_group_id=12345,
        expected_lock_at="2026-09-13T17:00:00Z",
        code_sha256=implementation_sha256,
        started_at=datetime(2026, 9, 13, 15, tzinfo=UTC),
        now_factory=lambda: datetime(2026, 9, 13, 16, 5, tzinfo=UTC),
    )
    assert retry == result
