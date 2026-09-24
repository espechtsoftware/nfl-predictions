"""Hermetic tests for the recourse-aware initial-book realized bridge."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import importlib.util
from pathlib import Path

import pytest

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS
from nfl_dfs.analysis.recourse_aware_initial import (
    TAILS,
    VERSION as MECHANISM_VERSION,
    aggregate_scorefree_folds,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_recourse_aware_initial_realized_bridge_v1 as bridge,
)


def _hash(value: object) -> str:
    return bridge.canonical_sha256_v1(value)


def _identity(uri: str, raw: bytes, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _Store:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.calls: list[dict[str, object]] = []

    @staticmethod
    def _key(value: object) -> tuple[str, str, str, int]:
        row = dict(value)  # type: ignore[arg-type]
        return (
            str(row["uri"]), str(row["generation"]),
            str(row["sha256"]), int(row["bytes"]),
        )

    def put_raw(self, identity: object, raw: bytes) -> None:
        self.values[self._key(identity)] = raw

    def put(self, identity: object, value: object) -> None:
        self.put_raw(identity, bridge.canonical_json_bytes_v1(value))

    def read_exact(self, identity: object) -> bytes:
        row = dict(identity)  # type: ignore[arg-type]
        self.calls.append(row)
        return self.values[self._key(row)]


def _coverage(events: dict[int, int]) -> dict[str, dict[str, float | int]]:
    return {
        str(threshold): {"events": value, "rate": value / 10_000}
        for threshold, value in events.items()
    }


def _metrics(*, reachable_p230: int) -> dict[str, object]:
    events = {
        240: 1, 230: reachable_p230, 220: 20, 210: 30,
        200: 50, 194: 100, 187: 200,
    }
    locked_counts = {str(index): 80 if index == 0 else 0 for index in range(10)}
    slot_counts = {str(index): 0 for index in range(9)}
    return {
        "version": MECHANISM_VERSION,
        "uses_realized_outcomes": False,
        "entries": 80,
        "worlds": 10_000,
        "initial_coverage": _coverage({**events, 230: 10}),
        "reachable_union_coverage": _coverage(events),
        "reachable_alternatives": 160,
        "alternatives_per_entry": {
            "minimum": 1, "median": 1.0, "mean": 1.0, "maximum": 1,
        },
        "distinct_locked_slot_signatures": 1,
        "locked_slot_count_distribution": locked_counts,
        "locked_slot_index_distribution": slot_counts,
        "locked_player_frequency": [],
        "locked_signature_frequency": [{"signature": [], "entries": 80}],
    }


def _rosters(season: int, week: int, arm: str) -> list[list[str]]:
    return [
        sorted(
            f"s{season}-w{week:02d}-{arm}-e{entry:03d}-p{slot}"
            for slot in range(9)
        )
        for entry in range(80)
    ]


def _fold(season: int, week: int, block: str) -> dict[str, object]:
    return {
        "version": MECHANISM_VERSION,
        "uses_realized_outcomes": False,
        "season": season,
        "week": week,
        "heldout_block": block,
        "training_blocks": [value for value in REGISTERED_BLOCKS if value != block],
        "candidate_budget": 200,
        "alternative_cap": 24,
        "control": _metrics(reachable_p230=10),
        "treatment": _metrics(reachable_p230=11),
        "selected_identity_overlap": 0,
        "selected_identity_jaccard": 0.0,
        "control_selected_rosters": _rosters(season, week, "control"),
        "treatment_selected_rosters": _rosters(season, week, "treatment"),
    }


def _receipt(season: int, week: int, block: str) -> dict[str, object]:
    ordinal = int(block[1:])
    uri = f"gs://fixture/worlds/{season}-w{week:02d}-{block}.npz"
    return {
        "block": block,
        "source_panel": bridge.SOURCE_PANELS[ordinal],
        "candidate_rows": 200,
        "uri": uri,
        "sha256": sha256(uri.encode()).hexdigest(),
        "generation": str(season * 10_000 + week * 10 + ordinal + 1),
        "updated": "2026-08-17T00:00:00Z",
        "bytes": 1_000 + ordinal,
    }


def _shard(season: int, week: int) -> dict[str, object]:
    return {
        "version": "recourse-aware-initial-book-scorefree-shard-v1",
        "run_id": bridge.RUN_ID,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": season,
        "week": week,
        "code_sha": bridge.FROZEN_CODE_SHA,
        "analysis_image": bridge.FROZEN_IMAGE,
        "source_hashes": bridge.FROZEN_SOURCE_HASHES,
        "source_panels": list(bridge.SOURCE_PANELS),
        "forensic_manifest_sha256": bridge.FORENSIC_MANIFEST_SHA256,
        "cbwu_report_sha256": bridge.CBWU_REPORT_SHA256,
        "decision_time": "2026-09-13T15:55:00-04:00",
        "artifact_receipts": [
            _receipt(season, week, block) for block in REGISTERED_BLOCKS
        ],
        "folds": [_fold(season, week, block) for block in REGISTERED_BLOCKS],
    }


def _scorefree_report() -> dict[str, object]:
    shards = [
        _shard(season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    folds = [fold for shard in shards for fold in shard["folds"]]  # type: ignore[index]
    source_artifacts = [
        receipt for shard in shards for receipt in shard["artifact_receipts"]  # type: ignore[index]
    ]
    aggregate = aggregate_scorefree_folds(folds)
    assert aggregate["passed"] is True
    return {
        **aggregate,
        "run_id": bridge.RUN_ID,
        "code_sha": bridge.FROZEN_CODE_SHA,
        "analysis_image": bridge.FROZEN_IMAGE,
        "source_hashes": bridge.FROZEN_SOURCE_HASHES,
        "source_panels": list(bridge.SOURCE_PANELS),
        "forensic_manifest_sha256": bridge.FORENSIC_MANIFEST_SHA256,
        "cbwu_report_sha256": bridge.CBWU_REPORT_SHA256,
        "source_artifacts": source_artifacts,
        "shards": shards,
    }


def _terminal_root(
    report: dict[str, object], report_identity: dict[str, object],
    *, passed: bool = True,
) -> dict[str, object]:
    ledger = []
    for source, shard in enumerate(report["shards"]):  # type: ignore[index]
        season = int(shard["season"])
        week = int(shard["week"])
        raw = bridge.canonical_line_json_bytes_v1(shard)
        ledger.append({
            "source_ordinal": source,
            "season": season,
            "week": week,
            "execution": f"fixture-execution-{source:02d}",
            "execution_metadata_sha256": sha256(
                f"execution:{source}".encode()
            ).hexdigest(),
            "shard_identity": _identity(
                bridge.SCOREFREE_REPORT_URI.removesuffix("report.json")
                + f"slate-{season}-{week}.json",
                raw,
                str(1_000 + source),
            ),
        })
    body = {
        "version": bridge.SCOREFREE_TERMINAL_SCHEMA,
        "run_id": bridge.RUN_ID,
        "job": "atlas-cbc-32g-full-2023-w8-v1",
        "job_uid": "1f4bcf0a-2300-4afa-9fc1-9981844c8275",
        "frozen_code_sha": bridge.FROZEN_CODE_SHA,
        "frozen_image": bridge.FROZEN_IMAGE,
        "transport_amendment_sha256": bridge.TRANSPORT_AMENDMENT_SHA256,
        "terminal_authority_amendment_sha256": (
            bridge.TERMINAL_AUTHORITY_AMENDMENT_SHA256
        ),
        "scorefree_report_identity": report_identity,
        "scorefree_report_sha256": report_identity["sha256"],
        "shard_count": 54,
        "fold_count": 270,
        "shard_identity_ledger": ledger,
        "shard_identity_ledger_sha256": _hash(ledger),
        "harvest_completion_sha256": "1" * 64,
        "grid_terminal_sha256": "2" * 64,
        "canary_completion_sha256": "3" * 64,
        "job_restoration_sha256": "4" * 64,
        "completion_sha256": "5" * 64,
        "passes_scorefree_gate": passed,
        "historical_policy_diagnostic_licensed": passed,
        "disposition": (
            "recourse-aware-initial-book-premise-passes"
            if passed else "recourse-aware-candidate-union-selector-premise-fails"
        ),
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "terminal_before_realized_outcome_read": True,
        "complete": True,
    }
    body["terminal_root_sha256"] = _hash(body)
    return body


@pytest.fixture(scope="module")
def scorefree_case() -> tuple[
    dict[str, object], bytes, dict[str, object], bytes, dict[str, object]
]:
    report = _scorefree_report()
    raw = bridge.canonical_line_json_bytes_v1(report)
    report_identity = _identity(bridge.SCOREFREE_REPORT_URI, raw, "17")
    terminal = _terminal_root(report, report_identity)
    terminal_raw = bridge.canonical_line_json_bytes_v1(terminal)
    terminal_identity = _identity(
        bridge.SCOREFREE_TERMINAL_URI, terminal_raw, "18"
    )
    return report, raw, report_identity, terminal_raw, terminal_identity


def _outcome_case(
    store: _Store,
) -> tuple[dict[str, object], dict[str, object]]:
    descriptors = []
    for source, (season, week) in enumerate(
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ):
        slate_id = f"{season}-w{week:02d}"
        rows = []
        for arm, base in (("control", 150), ("treatment", 151)):
            for entry, roster in enumerate(_rosters(season, week, arm)):
                rows.append({
                    "lineup_id": f"{slate_id}-{arm}-{entry:03d}",
                    "roster_player_ids": roster,
                    "realized_score_micro": (base + entry) * bridge.MICRO_DK_PER_POINT,
                })
        shard = {
            "source_ordinal": source,
            "slate_id": slate_id,
            "panel_freeze_identity": contract.PANEL_IDENTITY,
            "lineup_count": len(rows),
            "lineup_rows": rows,
            "lineup_rows_sha256": _hash(rows),
            "slate_attribution_sha256": sha256(
                f"attribution:{slate_id}".encode()
            ).hexdigest(),
        }
        shard_uri = f"gs://fixture/attribution/{source:02d}-{slate_id}.json"
        shard_raw = bridge.canonical_json_bytes_v1(shard)
        shard_identity = _identity(shard_uri, shard_raw, str(100 + source))
        store.put_raw(shard_identity, shard_raw)
        descriptors.append({
            "source_ordinal": source,
            "slate_id": slate_id,
            "slate_attribution_identity": shard_identity,
            "slate_attribution_sha256": shard["slate_attribution_sha256"],
            "lineup_count": len(rows),
        })
    root_uri = "gs://fixture/attribution/attribution-release.json"
    root = {
        "target_uri": root_uri,
        "panel_freeze_identity": contract.PANEL_IDENTITY,
        "panel_freeze_sha256": contract.PANEL_SELF_SHA256,
        "slate_attribution_objects": descriptors,
        "attribution_release_sha256": sha256(b"synthetic-release").hexdigest(),
    }
    root_raw = bridge.canonical_json_bytes_v1(root)
    root_identity = _identity(root_uri, root_raw, "99")
    store.put_raw(root_identity, root_raw)
    return root, root_identity


def _patch_score_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bridge.score_authority,
        "validate_attribution_release_score_authority_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        bridge.score_authority,
        "validate_slate_score_row_authority_v1",
        lambda value: dict(value),
    )


def test_metric_book_requires_exact_fields_and_rejects_deep_outcome_key() -> None:
    extra = _metrics(reachable_p230=11)
    extra["unregistered_metric"] = 1
    with pytest.raises(
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="metric-book identity differs",
    ):
        bridge._validate_metric_book(extra, candidate_budget=200)
    with pytest.raises(
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="contains outcome field",
    ):
        bridge._assert_scorefree({
            "safe": [{"nested": {"realized_score_micro": 1}}],
        })


def test_full_bridge_reports_rotated_fit_diagnostic_and_five_fold_rows(
    scorefree_case: tuple[
        dict[str, object], bytes, dict[str, object], bytes, dict[str, object]
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, scorefree_raw, report_identity, terminal_raw, terminal_identity = scorefree_case
    scorefree_store = _Store()
    scorefree_store.put_raw(report_identity, scorefree_raw)
    scorefree_store.put_raw(terminal_identity, terminal_raw)
    outcome_store = _Store()
    _, outcome_identity = _outcome_case(outcome_store)
    _patch_score_authority(monkeypatch)
    monkeypatch.setattr(bridge, "OUTCOME_AUTHORITY_IDENTITY", outcome_identity)

    result = bridge.build_recourse_aware_initial_realized_bridge_v1(
        scorefree_terminal_identity=terminal_identity,
        outcome_authority_identity=outcome_identity,
        mode=bridge.MODE_FULL_PANEL,
        read_scorefree_exact=scorefree_store.read_exact,
        read_outcome_exact=outcome_store.read_exact,
    )

    assert len(scorefree_store.calls) == 2
    assert len(outcome_store.calls) == 55
    assert result["scored_slate_count"] == 54
    assert result["realized_bridge_protocol_sha256"] == (
        bridge.REALIZED_PROTOCOL_SHA256
    )
    assert result["reachable_union_scored"] is False
    assert result["late_swap_policy_applied"] is False
    assert result["lineup_rescore_performed"] is False
    assert result["uses_realized_outcomes"] is True
    assert result["persisted_realized_attribution_read"] is True
    assert result["raw_outcome_source_queried"] is False
    assert result["scorecard_eligible"] is False
    assert result["all_block_54_week_benchmark_comparable"] is False
    assert result["ranking_beside_all_block_54_week_benchmark_forbidden"] is True
    control, treatment = result["rotated_fit_arm_diagnostics"]
    assert control["arm_id"] == "control"
    assert treatment["arm_id"] == "treatment"
    assert control["rotated_fit_mean_weekly_maximum_micro"] == {
        "numerator": 229 * bridge.MICRO_DK_PER_POINT * 270,
        "denominator": 270,
    }
    assert treatment["rotated_fit_mean_weekly_maximum_micro"] == {
        "numerator": 230 * bridge.MICRO_DK_PER_POINT * 270,
        "denominator": 270,
    }
    assert [
        row["heldout_rotation_week_count"] for row in control["fold_paths"]
    ] == [54] * 5
    assert all(row["production_final_fit"] is False for row in control["fold_paths"])
    paired = result["rotated_fit_paired_diagnostic"]
    assert paired["rotated_book_week_count"] == 270
    assert paired["rotated_fit_treatment_minus_control_mean_micro"] == {
        "numerator": bridge.MICRO_DK_PER_POINT * 270,
        "denominator": 270,
    }
    assert paired["treatment_wins"] == 270
    assert paired["ties"] == 0
    assert paired["treatment_losses"] == 0
    assert paired["at_or_above_threshold_book_week_count_deltas"]["230"] == 270
    assert paired["at_or_above_threshold_book_week_count_deltas"]["240"] == 0


def test_failed_scorefree_gate_never_opens_outcome_authority(
    scorefree_case: tuple[
        dict[str, object], bytes, dict[str, object], bytes, dict[str, object]
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, _, _, _, _ = scorefree_case
    changed = deepcopy(report)
    changed["passed"] = False
    changed["historical_policy_diagnostic_licensed"] = False
    changed["disposition"] = (
        "recourse-aware-candidate-union-selector-premise-fails"
    )
    raw = bridge.canonical_line_json_bytes_v1(changed)
    report_identity = _identity(bridge.SCOREFREE_REPORT_URI, raw, "19")
    terminal = _terminal_root(changed, report_identity, passed=False)
    terminal_raw = bridge.canonical_line_json_bytes_v1(terminal)
    terminal_identity = _identity(
        bridge.SCOREFREE_TERMINAL_URI, terminal_raw, "20"
    )
    terminal_store = _Store()
    terminal_store.put_raw(report_identity, raw)
    terminal_store.put_raw(terminal_identity, terminal_raw)
    outcome_store = _Store()
    _, outcome_identity = _outcome_case(outcome_store)
    _patch_score_authority(monkeypatch)
    monkeypatch.setattr(bridge, "OUTCOME_AUTHORITY_IDENTITY", outcome_identity)

    with pytest.raises(
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="authority/gate differs",
    ):
        bridge.build_recourse_aware_initial_realized_bridge_v1(
            scorefree_terminal_identity=terminal_identity,
            outcome_authority_identity=outcome_identity,
            mode=bridge.MODE_FULL_PANEL,
            read_scorefree_exact=terminal_store.read_exact,
            read_outcome_exact=outcome_store.read_exact,
        )
    assert len(terminal_store.calls) == 1
    assert outcome_store.calls == []


def test_deep_outcome_tamper_is_rejected_before_any_outcome_read(
    scorefree_case: tuple[
        dict[str, object], bytes, dict[str, object], bytes, dict[str, object]
    ],
) -> None:
    report, _, _, _, _ = scorefree_case
    changed = deepcopy(report)
    changed["shards"][17]["folds"][3]["treatment"][  # type: ignore[index]
        "nested_fixture"
    ] = {"realized_score_micro": 230_000_000}
    report_raw = bridge.canonical_line_json_bytes_v1(changed)
    report_identity = _identity(bridge.SCOREFREE_REPORT_URI, report_raw, "31")
    terminal = _terminal_root(changed, report_identity)
    terminal_raw = bridge.canonical_line_json_bytes_v1(terminal)
    terminal_identity = _identity(
        bridge.SCOREFREE_TERMINAL_URI, terminal_raw, "32"
    )
    scorefree_store = _Store()
    scorefree_store.put_raw(report_identity, report_raw)
    scorefree_store.put_raw(terminal_identity, terminal_raw)
    outcome_store = _Store()

    with pytest.raises(
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="contains outcome field",
    ):
        bridge.build_recourse_aware_initial_realized_bridge_v1(
            scorefree_terminal_identity=terminal_identity,
            outcome_authority_identity=bridge.OUTCOME_AUTHORITY_IDENTITY,
            mode=bridge.MODE_FULL_PANEL,
            read_scorefree_exact=scorefree_store.read_exact,
            read_outcome_exact=outcome_store.read_exact,
        )
    assert len(scorefree_store.calls) == 2
    assert outcome_store.calls == []


def test_missing_selected_roster_fails_instead_of_rescoring(
    scorefree_case: tuple[
        dict[str, object], bytes, dict[str, object], bytes, dict[str, object]
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, raw, report_identity, terminal_raw, terminal_identity = scorefree_case
    terminal_store = _Store()
    terminal_store.put_raw(report_identity, raw)
    terminal_store.put_raw(terminal_identity, terminal_raw)
    outcome_store = _Store()
    _, outcome_identity = _outcome_case(outcome_store)
    root_raw = outcome_store.values[outcome_store._key(outcome_identity)]
    root = json.loads(root_raw)
    first_identity = root["slate_attribution_objects"][0][
        "slate_attribution_identity"
    ]
    first_key = outcome_store._key(first_identity)
    first = json.loads(outcome_store.values[first_key])
    first["lineup_rows"] = first["lineup_rows"][1:]
    first["lineup_count"] = len(first["lineup_rows"])
    first["lineup_rows_sha256"] = _hash(first["lineup_rows"])
    changed_raw = bridge.canonical_json_bytes_v1(first)
    changed_identity = _identity(
        str(first_identity["uri"]), changed_raw, str(first_identity["generation"])
    )
    outcome_store.values.pop(first_key)
    outcome_store.put_raw(changed_identity, changed_raw)
    root["slate_attribution_objects"][0][
        "slate_attribution_identity"
    ] = changed_identity
    root["slate_attribution_objects"][0]["lineup_count"] = first["lineup_count"]
    new_root_raw = bridge.canonical_json_bytes_v1(root)
    new_root_identity = _identity(
        str(outcome_identity["uri"]), new_root_raw, str(outcome_identity["generation"])
    )
    outcome_store.values.pop(outcome_store._key(outcome_identity))
    outcome_store.put_raw(new_root_identity, new_root_raw)
    _patch_score_authority(monkeypatch)
    monkeypatch.setattr(bridge, "OUTCOME_AUTHORITY_IDENTITY", new_root_identity)

    with pytest.raises(
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="missing from no-rescore authority",
    ):
        bridge.build_recourse_aware_initial_realized_bridge_v1(
            scorefree_terminal_identity=terminal_identity,
            outcome_authority_identity=new_root_identity,
            mode=bridge.MODE_ONE_SLATE_SMOKE,
            read_scorefree_exact=terminal_store.read_exact,
            read_outcome_exact=outcome_store.read_exact,
        )


def test_terminal_report_requires_exact_newline_encoding_and_frozen_authority(
    scorefree_case: tuple[
        dict[str, object], bytes, dict[str, object], bytes, dict[str, object]
    ],
) -> None:
    report, raw, report_identity, terminal_raw, terminal_identity = scorefree_case
    store = _Store()
    without_newline = bridge.canonical_json_bytes_v1(
        json.loads(terminal_raw[:-1])
    )
    identity = _identity(bridge.SCOREFREE_TERMINAL_URI, without_newline, "21")
    store.put_raw(identity, without_newline)
    with pytest.raises(
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="newline law differs",
    ):
        bridge.reopen_terminal_scorefree_books_v1(
            scorefree_terminal_identity=identity,
            read_scorefree_exact=store.read_exact,
        )
    wrong_uri_identity = _identity("gs://fixture/terminal-root.json", terminal_raw, "22")
    store.put_raw(wrong_uri_identity, terminal_raw)
    with pytest.raises(
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="authority/gate differs",
    ):
        bridge.reopen_terminal_scorefree_books_v1(
            scorefree_terminal_identity=wrong_uri_identity,
            read_scorefree_exact=store.read_exact,
        )


def test_bridge_binders_use_real_persisted_attribution_validators() -> None:
    fixture_path = Path(
        "tests/test_corpus_r6_current_bank_crossed_screen_realized_bridge_v1.py"
    )
    spec = importlib.util.spec_from_file_location(
        "real_attribution_validator_fixture", fixture_path,
    )
    assert spec and spec.loader
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)

    root = fixture._persisted_score_root()
    root_raw = bridge.canonical_json_bytes_v1(root)
    root_identity = _identity(str(root["target_uri"]), root_raw, "41")
    assert bridge._bind_attribution_root_v1(
        root, identity=root_identity,
    ) == root

    shard = fixture._persisted_score_shard()
    shard_raw = bridge.canonical_json_bytes_v1(shard)
    shard_identity = _identity("gs://fixture/real-validator-shard.json", shard_raw, "42")
    descriptor = {
        "source_ordinal": shard["source_ordinal"],
        "slate_id": shard["slate_id"],
        "slate_attribution_identity": shard_identity,
        "slate_attribution_sha256": shard["slate_attribution_sha256"],
        "lineup_count": shard["lineup_count"],
    }
    assert bridge._bind_attribution_shard_v1(
        shard,
        identity=shard_identity,
        descriptor=descriptor,
        source_ordinal=0,
        slate_id="2023-w01",
    ) == shard
