from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

import pytest

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_label_fit_adapter as fit_adapter
from nfl_dfs.research import lr8_later_period_evaluation as later
from nfl_dfs.research import lr8_later_period_source as source


RUN_ID = "20260821-lr8-later-period-v1"
JOB = "lr8-later-period"
CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64


def _rosters() -> list[list[str]]:
    skills = [f"p{index:02d}" for index in range(1, 17)]
    return [
        sorted(("a-dst", *chosen))
        for chosen in list(combinations(skills, 8))[:89]
    ]


def _freeze() -> tuple[dict[str, object], dict[str, object]]:
    rosters = _rosters()
    players = [
        {"id": "a-dst", "pos": "DST", "team": "D00"},
        *[
            {"id": f"p{index:02d}", "pos": "WR", "team": f"T{index:02d}"}
            for index in range(1, 17)
        ],
    ]
    catalogs = []
    book_cells = []
    for season, week in later.EXPECTED_SLATES:
        catalogs.append({
            "season": season,
            "week": week,
            "players": players,
            "catalog_sha256": later.canonical_sha256(players),
        })
        for fold in ("A", "B"):
            cell = {
                "season": season,
                "week": week,
                "fold_name": fold,
                "candidate_budget_control": 88,
                "candidate_budget_treatment": 88,
                "control_candidates": rosters[:88],
                "treatment_candidates": rosters[1:89],
                "control_book": rosters[:80],
                "treatment_book": [*rosters[1:80], rosters[88]],
            }
            book_cells.append({
                **cell,
                "cell_sha256": later.canonical_sha256(cell),
            })
    def object_receipt(label: str) -> dict[str, object]:
        return {
            "uri": f"gs://fixture/lr8/{label}.json",
            "generation": "1",
            "sha256": sha256(label.encode()).hexdigest(),
            "bytes": len(label) + 1,
        }

    source_hash = "1" * 64
    anatomy_hash = "2" * 64
    anatomy_freeze_hash = "4" * 64
    smoke_hash = "3" * 64
    smoke_object = object_receipt("later-source-smoke")
    terminal = {
        "schema": source.SMOKE_TERMINAL_VERSION,
        "execution_name": "lr8-later-smoke-fixture",
        "execution_metadata_object": object_receipt("smoke-execution"),
        "finish_ledger_object": object_receipt("smoke-finish-ledger"),
        "smoke_object": smoke_object,
        "smoke_sha256": smoke_hash,
        "source_freeze_sha256": source_hash,
        "anatomy_artifact_sha256": anatomy_hash,
        "task_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "retried_count": 0,
        "completed_condition": "True",
        "strict_terminal_success": True,
    }
    terminal["terminal_sha256"] = later.canonical_sha256(terminal)
    terminal_raw = later.canonical_json(terminal)
    terminal_object = {
        "uri": "gs://fixture/lr8/later-source-smoke-terminal.json",
        "generation": "1",
        "sha256": sha256(terminal_raw).hexdigest(),
        "bytes": len(terminal_raw),
    }
    cell_objects = [
        object_receipt(f"construction-cell-{index:02d}")
        for index in range(len(later.EXPECTED_SLATES))
    ]
    body = {
        "schema": source.BOOK_FREEZE_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "source_freeze_sha256": source_hash,
        "source_freeze_object": object_receipt("later-source-freeze"),
        "anatomy_artifact_sha256": anatomy_hash,
        "anatomy_freeze_sha256": anatomy_freeze_hash,
        "anatomy_freeze_object": object_receipt("anatomy-freeze"),
        "smoke_authority": {
            "object": smoke_object,
            "smoke_sha256": smoke_hash,
            "source_freeze_sha256": source_hash,
            "anatomy_artifact_sha256": anatomy_hash,
            "terminal": terminal,
            "terminal_object": terminal_object,
        },
        "seasons": list(lr8.EVALUATION_SEASONS),
        "weeks": list(lr8.EVALUATION_WEEKS),
        "cell_count": 54,
        "book_cell_count": 108,
        "cell_objects": cell_objects,
        "cell_object_manifest_sha256": later.canonical_sha256(cell_objects),
        "catalogs": catalogs,
        "catalogs_sha256": later.canonical_sha256(catalogs),
        "book_cells": book_cells,
        "book_cells_sha256": later.canonical_sha256(book_cells),
        "primary_deployment_rule": "odd_week_A_even_week_B",
        "candidate_and_entry_budgets_frozen": True,
        "pricing_optimality_proven": True,
        "later_period_score_read_licensed": True,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "historical_outcome_lease_acquired": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    frozen = {**body, "freeze_sha256": later.canonical_sha256(body)}
    raw = later.canonical_json(frozen)
    receipt = {
        "uri": "gs://fixture/lr8/later-period-108-book-freeze.json",
        "generation": "11",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return frozen, receipt


def _config(*, enabled: bool = True) -> later.SupplierConfig:
    frozen, _ = _freeze()
    return later.SupplierConfig(
        RUN_ID, JOB, CODE_SHA, IMAGE, str(frozen["freeze_sha256"]), enabled
    )


def _lease(config: later.SupplierConfig) -> dict[str, object]:
    body = {
        "version": fit_adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": config.run_id,
        "job": config.job,
        "code_sha": config.code_sha,
        "image": config.image,
        "acquired_at": "2026-08-21T00:00:00+00:00",
    }
    raw = later.canonical_json(body)
    return {
        "body": body,
        "object_receipt": {
            "uri": fit_adapter.HISTORICAL_OUTCOME_LEASE_URI,
            "generation": "7",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
            "create_only": True,
        },
    }


class Harness:
    def __init__(self, config: later.SupplierConfig):
        self.config = config
        self.lease = _lease(config)
        self.events: list[str] = []
        self.published: list[tuple[str, dict[str, object]]] = []
        self.query_mutator = lambda rows: rows
        self.reopen_mutator = lambda name, raw: raw
        self.lease_mutator = lambda call, value: value
        self.lease_calls = 0
        self.clock_values = iter((
            datetime(2026, 8, 21, 0, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 21, 0, 0, 3, tzinfo=timezone.utc),
        ))

    def clock(self) -> datetime:
        self.events.append("clock")
        return next(self.clock_values)

    def verify_lease(self) -> dict[str, object]:
        self.lease_calls += 1
        self.events.append(f"lease-{self.lease_calls}")
        return self.lease_mutator(self.lease_calls, deepcopy(self.lease))

    def metadata(self, table: str) -> dict[str, object]:
        self.events.append(f"metadata-{Path(table).name}")
        return {
            "table_id": table,
            "etag": f"etag/{table}",
            "modified": "2026-08-20T00:00:00+00:00",
            "num_rows": 10_000,
            "schema_sha256": sha256(table.encode()).hexdigest(),
        }

    def query(self, spec: later.QuerySpec) -> later.QueryResult:
        self.events.append("query")
        assert self.published[0][0].endswith("later-period-read-attempt.json")
        union = json.loads(
            later.canonical_json(self.published[0][1])
        )["union_player_count"]
        rows = []
        params = {row.name: row for row in spec.parameters}
        for key in [*params["dst_keys"].value, *params["skill_keys"].value]:
            season, week, source_key = str(key).split("|", 2)
            kind = "dst" if key in params["dst_keys"].value else "skill"
            rows.append({
                "season": int(season),
                "week": int(week),
                "source_kind": kind,
                "source_key": source_key,
                "realized_score": Decimal("-1") if kind == "dst" else Decimal("25"),
            })
        rows.sort(key=lambda row: (
            row["season"], row["week"], row["source_kind"], row["source_key"]
        ))
        assert len(rows) == union
        return later.QueryResult(
            rows=self.query_mutator(rows),
            job_receipt={
                "job_id": spec.job_id,
                "location": spec.location,
                "sql_sha256": spec.sql_sha256,
                "parameters_sha256": spec.parameters_sha256,
                "created": "2026-08-21T00:00:04+00:00",
                "started": "2026-08-21T00:00:05+00:00",
                "ended": "2026-08-21T00:00:06+00:00",
                "total_bytes_processed": 123,
                "cache_hit": False,
                "error_result": None,
            },
        )

    def publish(self, uri: str, raw: bytes) -> later.PublishedObject:
        self.events.append("publish")
        payload = json.loads(raw)
        self.published.append((uri, payload))
        name = Path(uri).name
        stamp = {
            "later-period-read-attempt.json": "2026-08-21T00:00:02+00:00",
            "later-period-player-score-source.json": (
                "2026-08-21T00:00:07+00:00"
            ),
            "later-period-evaluation.json": "2026-08-21T00:00:08+00:00",
        }[name]
        reopened = self.reopen_mutator(name, raw)
        return later.PublishedObject(
            receipt={
                "uri": uri,
                "generation": str(100 + len(self.published)),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "create_only": True,
            },
            reopened_raw=reopened,
            created_at=stamp,
            created=True,
        )


def _run(
    harness: Harness | None = None,
) -> tuple[later.EvaluationSupply, Harness]:
    config = harness.config if harness is not None else _config()
    active = harness or Harness(config)
    frozen, receipt = _freeze()
    result = later.supply_later_period_evaluation(
        config=config,
        book_freeze=frozen,
        book_freeze_receipt=receipt,
        verify_lease=active.verify_lease,
        read_table_metadata=active.metadata,
        execute_query=active.query,
        publish=active.publish,
        clock=active.clock,
    )
    return result, active


def test_default_off_precedes_freeze_clock_and_callbacks():
    def forbidden(*_args, **_kwargs):
        raise AssertionError("default-off supplier performed work")

    with pytest.raises(later.LR8LaterPeriodError, match="default-off"):
        later.supply_later_period_evaluation(
            config=later.SupplierConfig("bad", "bad", "bad", "bad", "bad"),
            book_freeze={},
            book_freeze_receipt={},
            verify_lease=forbidden,
            read_table_metadata=forbidden,
            execute_query=forbidden,
            publish=forbidden,
            clock=forbidden,
        )


def test_attempt_precedes_exact_union_query_and_reopened_replay():
    result, harness = _run()
    assert len(result.evaluation["score_rows"]) == 54 * 89
    assert len(result.source["rows"]) == 54 * 17
    assert all(
        row["realized_total_micro"] == 199_000_000
        for row in result.evaluation["score_rows"]
    )
    assert result.evaluation["exact_player_sum_reconciled"] is True
    assert result.evaluation["independent_evaluator_replay"] is True
    assert result.evaluation["evaluation_report"][
        "one_later_period_score_read"
    ] is True
    assert result.evaluation["lease_release_owner"] == later.LEASE_OWNER
    assert result.evaluation[
        "historical_outcome_lease_release_required"
    ] is True
    query_at = harness.events.index("query")
    first_publish = harness.events.index("publish")
    assert first_publish < query_at
    assert harness.lease_calls == 2
    assert len(harness.published) == 3
    assert result.evaluation["attempt_identity"]["generation"] == "101"
    assert result.evaluation["attempt_identity"][
        "historical_outcome_lease_generation"
    ] == "7"


@pytest.mark.parametrize("poison", ["missing", "extra", "decimal"])
def test_query_must_be_exact_union_exact_micro_data(poison: str):
    harness = Harness(_config())

    def mutate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if poison == "missing":
            return rows[:-1]
        if poison == "extra":
            return [*rows, {
                **rows[-1], "source_key": "not-in-frozen-union",
            }]
        result = deepcopy(rows)
        result[0]["realized_score"] = Decimal("1.0000001")
        return result

    harness.query_mutator = mutate
    with pytest.raises(later.LR8LaterPeriodError):
        _run(harness)
    assert harness.published[0][0].endswith("later-period-read-attempt.json")


def test_freeze_requires_exact_108_cells_and_score_read_license():
    frozen, receipt = _freeze()
    for mutate in (
        lambda value: value["book_cells"].pop(),
        lambda value: value.update(later_period_score_read_licensed=False),
    ):
        poison = deepcopy(frozen)
        mutate(poison)
        body = {key: value for key, value in poison.items() if key != "freeze_sha256"}
        poison["freeze_sha256"] = later.canonical_sha256(body)
        raw = later.canonical_json(poison)
        poison_receipt = {
            **receipt, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)
        }
        with pytest.raises(later.LR8LaterPeriodError):
            later.validate_book_freeze(
                poison,
                expected_freeze_sha256=str(poison["freeze_sha256"]),
                object_receipt=poison_receipt,
            )


def test_reopened_publication_mutation_fails_before_evaluation_closure():
    harness = Harness(_config())

    def mutate(name: str, raw: bytes) -> bytes:
        return raw + b" " if name.endswith("player-score-source.json") else raw

    harness.reopen_mutator = mutate
    with pytest.raises(later.LR8LaterPeriodError, match="reopen differs"):
        _run(harness)
    assert len(harness.published) == 2


def test_independent_replay_rejects_rehashed_query_or_roster_total():
    result, _ = _run()
    frozen, receipt = _freeze()
    books = later.validate_book_freeze(
        frozen,
        expected_freeze_sha256=str(frozen["freeze_sha256"]),
        object_receipt=receipt,
    )
    for mode in ("query", "total"):
        source = deepcopy(result.source)
        evaluation = deepcopy(result.evaluation)
        if mode == "query":
            source["query_spec"]["sql_sha256"] = "0" * 64
        else:
            evaluation["score_rows"][0]["realized_total_micro"] += 1
            evaluation["score_rows_sha256"] = later.canonical_sha256(
                evaluation["score_rows"]
            )
        with pytest.raises(later.LR8LaterPeriodError):
            later._replay(  # noqa: SLF001
                books=books,
                source=source,
                source_receipt=result.source_receipt,
                evaluation=evaluation,
                attempt=result.attempt,
                attempt_receipt=result.attempt_receipt,
                attempt_identity=result.evaluation["attempt_identity"],
            )


def test_live_lease_must_be_unchanged_across_the_query():
    harness = Harness(_config())

    def mutate(call: int, value: dict[str, object]) -> dict[str, object]:
        if call == 2:
            value["object_receipt"]["generation"] = "8"
        return value

    harness.lease_mutator = mutate
    with pytest.raises(later.LR8LaterPeriodError):
        _run(harness)
    assert any(event == "query" for event in harness.events)
    assert len(harness.published) == 1


def test_sql_contains_only_exact_key_player_dst_sources():
    exact_sql = later.AUTHORITATIVE_SCORE_SQL
    lowered = exact_sql.lower()
    assert "player_week_actuals" in lowered
    assert "team_defense_week" in lowered
    assert "@skill_keys" in lowered and "@dst_keys" in lowered
    assert (
        f"FROM `{later.SKILL_TABLE}` AS a "
        "FOR SYSTEM_TIME AS OF @source_snapshot_at"
    ) in exact_sql
    assert (
        f"FROM `{later.DST_TABLE}` AS d "
        "FOR SYSTEM_TIME AS OF @source_snapshot_at"
    ) in exact_sql
    assert "FOR SYSTEM_TIME AS OF @source_snapshot_at AS a" not in exact_sql
    assert "FOR SYSTEM_TIME AS OF @source_snapshot_at AS d" not in exact_sql
    assert "actual_score" not in lowered
    for forbidden in ("winner", "ownership", "payout", "contest"):
        assert forbidden not in lowered
