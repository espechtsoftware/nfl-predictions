from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from itertools import combinations, product
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import lr8_exact_solvers as exact
from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_lr8_later_period_source as runner  # noqa: E402


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"),
        ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"),
        ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"),
        ("rb-e", "RB", "E", "F", "g3"),
        ("wr-a1", "WR", "A", "B", "g1"),
        ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"),
        ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"),
        ("wr-f", "WR", "F", "E", "g3"),
        ("te-a", "TE", "A", "B", "g1"),
        ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"),
        ("te-d", "TE", "D", "C", "g2"),
        ("te-e", "TE", "E", "F", "g3"),
        ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"),
        ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game, 5_000)
        for player_id, position, team, opponent, game in rows
    ), key=lambda player: player.player_id))


def _legal_rosters(count: int = 88) -> tuple[tuple[str, ...], ...]:
    players = _players()
    positions = {
        position: [
            player.player_id for player in players if player.position == position
        ] for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result: list[tuple[str, ...]] = []
    for qb, rbs, wrs, te, dst in product(
        positions["QB"],
        combinations(positions["RB"], 2),
        combinations(positions["WR"], 4),
        positions["TE"],
        positions["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            lr8.audit_dk_classic_identity(players, roster)
        except lr8.LR8Error:
            continue
        if roster not in result:
            result.append(roster)
        if len(result) == count:
            return tuple(result)
    raise AssertionError("test catalog did not produce enough legal rosters")


def _artifact_receipts() -> list[dict[str, object]]:
    rows = []
    for index, (season, week, block) in enumerate(later.EXPECTED_ARTIFACT_KEYS):
        seed = rw.WORLD_BLOCKS.index(block)
        digest = f"{index + 1:064x}"[-64:]
        if (season, week, block) == later.REPAIRED_R3_KEY:
            digest = later.REPAIRED_R3_SHA256
        rows.append({
            "bytes": 1_000,
            "candidate_rows": 88,
            "generation": str(index + 1),
            "panel_run_id": later.SOURCE_PANELS[seed],
            "season": season,
            "seed": seed,
            "sha256": digest,
            "updated": "2026-08-16T00:00:00+00:00",
            "uri": f"gs://worlds/{season}/w{week}/{block}.npz",
            "week": week,
        })
    return rows


def _base_source() -> dict[str, object]:
    path = ROOT / (
        "reports/production-law-dependence-runs/"
        "20260817-production-law-dependence-source-lock-v1/source-lock.json"
    )
    return json.loads(path.read_bytes())


def _query_receipt(label: str) -> dict[str, object]:
    if label == "candidate":
        job_id = "test-r0-candidates"
        sql_sha = later.CANDIDATE_SQL_SHA256
    elif label == "catalog":
        job_id = "test-full-catalog"
        sql_sha = later.CATALOG_SQL_SHA256
    else:
        raise AssertionError("unknown query fixture")
    return {
        "job_id": job_id,
        "location": later.LOCATION,
        "sql_sha256": sql_sha,
        "parameters_sha256": later.canonical_sha256(
            later.source_parameter_payload("2026-08-21T12:00:00+00:00")
        ),
        "created": "2026-08-21T12:00:00+00:00",
        "started": "2026-08-21T12:00:01+00:00",
        "ended": "2026-08-21T12:00:02+00:00",
        "total_bytes_processed": 1,
        "cache_hit": False,
        "error_result": None,
    }


def test_candidate_sql_adapts_warehouse_csv_to_roster_array():
    assert "SPLIT(players, ',') AS players" in later.CANDIDATE_SQL
    assert later.CANDIDATE_SQL_SHA256 == sha256(
        later.CANDIDATE_SQL.encode("utf-8")
    ).hexdigest()


def _source_inputs():
    base = _base_source()
    artifacts = {
        (row["season"], row["week"], row["seed"]): row
        for row in base["artifact_receipts"]
    }
    max_candidates = max(
        int(row["candidate_rows"])
        for row in base["artifact_receipts"]
        if row["seed"] == 0
    )
    rosters = _legal_rosters(max_candidates)
    candidates = []
    catalog = []
    for season, week in later.EXPECTED_SLATE_KEYS:
        r0 = artifacts[(season, week, 0)]
        candidates.extend({
            "panel_run_id": later.R0_PANEL,
            "season": season,
            "week": week,
            "cand_ix": index,
            "players": list(roster),
            "score_artifact_uri": r0["uri"],
            "score_artifact_sha256": r0["sha256"],
        } for index, roster in enumerate(rosters[:int(r0["candidate_rows"])]))
        catalog.extend({
            "season": season,
            "week": week,
            "id": player.player_id,
            "pos": player.position,
            "team": player.team,
            "opp": player.opponent,
            "game_id": player.game_id,
            "salary": player.salary,
        } for player in _players())
    return base, candidates, catalog


def _build_source() -> dict[str, object]:
    base, candidates, catalog = _source_inputs()
    base_sha = later.BASE_SOURCE_SHA256
    return later.build_source_freeze(
        base_source_lock=base,
        base_source_lock_object={
            "uri": later.BASE_SOURCE_URI,
            "generation": later.BASE_SOURCE_GENERATION,
            "sha256": base_sha,
            "bytes": later.BASE_SOURCE_BYTES,
        },
        base_source_lock_sha256=base_sha,
        r0_candidate_rows=candidates,
        full_catalog_rows=catalog,
        query_provenance={
            "candidate_query": _query_receipt("candidate"),
            "catalog_query": _query_receipt("catalog"),
            "candidate_table": runner.CANDIDATE_TABLE,
            "catalog_table": runner.CATALOG_TABLE,
            "source_snapshot_at": "2026-08-21T12:00:00+00:00",
        },
        runtime_identity={
            "run_id": "test",
            "code_sha": "b" * 40,
            "image": f"image@sha256:{'c' * 64}",
            "job": "test-job",
        },
    )


@pytest.fixture(scope="module")
def source_freeze() -> dict[str, object]:
    return _build_source()


def test_source_freeze_is_exact_54_by_5_outcome_blind(source_freeze):
    assert len(source_freeze["slates"]) == 54
    assert sum(
        len(row["artifact_receipts"]) for row in source_freeze["slates"]
    ) == 270
    assert all(
        len(row["incumbent_candidates"])
        == row["artifact_receipts"][0]["candidate_rows"]
        for row in source_freeze["slates"]
    )
    assert source_freeze["source_query"]["realized_columns_selected"] == []
    assert source_freeze["uses_realized_outcomes"] is False
    assert source_freeze["b1_inputs_used"] is False
    assert later.validate_source_freeze(
        source_freeze,
        expected_freeze_sha256=source_freeze["freeze_sha256"],
    ) == source_freeze


def test_source_freeze_rejects_fractional_salary_and_outcome_source():
    base, candidates, catalog = _source_inputs()
    catalog[0] = {**catalog[0], "salary": 5_000.5}
    kwargs = {
        "base_source_lock": base,
        "base_source_lock_object": {
            "uri": later.BASE_SOURCE_URI,
            "generation": later.BASE_SOURCE_GENERATION,
            "sha256": later.BASE_SOURCE_SHA256,
            "bytes": later.BASE_SOURCE_BYTES,
        },
        "base_source_lock_sha256": later.BASE_SOURCE_SHA256,
        "r0_candidate_rows": candidates,
        "full_catalog_rows": catalog,
        "query_provenance": {
            "candidate_query": _query_receipt("candidate"),
            "catalog_query": _query_receipt("catalog"),
            "candidate_table": runner.CANDIDATE_TABLE,
            "catalog_table": runner.CATALOG_TABLE,
            "source_snapshot_at": "2026-08-21T12:00:00+00:00",
        },
        "runtime_identity": {
            "run_id": "test", "code_sha": "b" * 40,
            "image": f"image@sha256:{'c' * 64}", "job": "test-job",
        },
    }
    with pytest.raises(later.LR8LaterSourceError, match="salary"):
        later.build_source_freeze(**kwargs)
    clean_catalog = _source_inputs()[2]
    poisoned_base = deepcopy(base)
    poisoned_base["uses_realized_outcomes"] = True
    with pytest.raises(later.LR8LaterSourceError, match="source-lock identity"):
        later.build_source_freeze(
            **{**kwargs, "base_source_lock": poisoned_base,
               "full_catalog_rows": clean_catalog}
        )


def test_source_freeze_rejects_rehashed_query_or_base_object(source_freeze):
    poison = deepcopy(source_freeze)
    poison["source_query"]["candidate_table"] = "p.d.alternate"
    body = dict(poison)
    body.pop("freeze_sha256")
    poison["freeze_sha256"] = later.canonical_sha256(body)
    with pytest.raises(later.LR8LaterSourceError, match="query exact identity"):
        later.validate_source_freeze(
            poison, expected_freeze_sha256=poison["freeze_sha256"]
        )

    base, candidates, catalog = _source_inputs()
    with pytest.raises(later.LR8LaterSourceError, match="object identity"):
        later.build_source_freeze(
            base_source_lock=base,
            base_source_lock_object={
                "uri": later.BASE_SOURCE_URI,
                "generation": "1",
                "sha256": later.BASE_SOURCE_SHA256,
                "bytes": later.BASE_SOURCE_BYTES,
            },
            base_source_lock_sha256=later.BASE_SOURCE_SHA256,
            r0_candidate_rows=candidates,
            full_catalog_rows=catalog,
            query_provenance={
                "candidate_query": _query_receipt("candidate"),
                "catalog_query": _query_receipt("catalog"),
                "candidate_table": runner.CANDIDATE_TABLE,
                "catalog_table": runner.CATALOG_TABLE,
                "source_snapshot_at": "2026-08-21T12:00:00+00:00",
            },
            runtime_identity={
                "run_id": "test", "code_sha": "b" * 40,
                "image": f"image@sha256:{'c' * 64}", "job": "test-job",
            },
        )


def _npz(
    *, player_ids: tuple[str, ...], candidate_rows: int = 88,
    dtype: np.dtype = np.dtype("float32"),
) -> bytes:
    buffer = BytesIO()
    np.savez_compressed(
        buffer,
        cand_ix=np.arange(candidate_rows, dtype=np.int64),
        totals=np.zeros((candidate_rows, rw.WORLDS_PER_BLOCK), dtype=np.float32),
        tail_line=np.asarray([194.0], dtype=np.float64),
        player_ids=np.asarray(player_ids),
        player_draws=np.zeros(
            (len(player_ids), rw.WORLDS_PER_BLOCK), dtype=dtype
        ),
    )
    return buffer.getvalue()


def _source_with_artifact_bodies(
    source: dict[str, object], *, missing_player: bool = False,
) -> tuple[dict[str, object], dict[str, bytes]]:
    frozen = deepcopy(source)
    row = frozen["slates"][0]
    player_ids = tuple(value["id"] for value in row["catalog"])
    bodies = {}
    for receipt in row["artifact_receipts"]:
        ids = player_ids[:-1] if missing_player and receipt["block"] == "R4" else player_ids
        raw = _npz(
            player_ids=ids, candidate_rows=int(receipt["candidate_rows"])
        )
        receipt["sha256"] = sha256(raw).hexdigest()
        receipt["bytes"] = len(raw)
        bodies[receipt["block"]] = raw
    row["artifact_receipts_sha256"] = later.canonical_sha256(
        row["artifact_receipts"]
    )
    body = dict(frozen)
    body.pop("freeze_sha256")
    frozen["freeze_sha256"] = later.canonical_sha256(body)
    return frozen, bodies


def test_prepare_real_five_block_matrix_and_reject_catalog_gap(source_freeze):
    frozen, bodies = _source_with_artifact_bodies(source_freeze)
    prepared = later.prepare_later_slate(
        frozen,
        expected_source_freeze_sha256=frozen["freeze_sha256"],
        season=2023,
        week=1,
        artifact_bodies=bodies,
    )
    assert prepared.player_draws.shape == (len(_players()), 50_000)
    assert prepared.player_draws.dtype == np.float32
    assert prepared.player_draws.flags.writeable is False
    poisoned, poisoned_bodies = _source_with_artifact_bodies(
        source_freeze, missing_player=True
    )
    with pytest.raises(later.LR8LaterSourceError, match="full DK catalog"):
        later.prepare_later_slate(
            poisoned,
            expected_source_freeze_sha256=poisoned["freeze_sha256"],
            season=2023,
            week=1,
            artifact_bodies=poisoned_bodies,
        )


def _anatomy_artifact() -> dict[str, object]:
    players = _players()
    rosters = _legal_rosters()
    rows = []
    for index, (season, week) in enumerate(lr8.TRAINING_CELLS):
        rows.append(lr8.AnatomyTrainingRow(
            season=season,
            week=week,
            features=lr8.lineup_anatomy(players, rosters[index]),
            realized_total_micro=(190 + 15 * (index % 2)) * rw.MICRO_DK_SCALE,
        ))
    return lr8.fit_soft_anatomy_law(rows)


class _NullProofStep:
    def __init__(self, *, retain_receipt: bool = True) -> None:
        self.retain_receipt = retain_receipt
        self.last_proof = None
        self.last_evidence_receipts = ()

    def __call__(self, request: lr8.PricingRequest):
        request_sha = exact.pricing_request_sha256(request)
        result = {"roster": None, "null": True}
        proof_bytes = later.canonical_json({
            "request_sha256": request_sha, "result": result,
        })
        proof_sha = sha256(proof_bytes).hexdigest()
        self.last_proof = exact.ExactSolveProofBundle(
            schema="test-proof-v1",
            solve_kind="pricing",
            request_sha256=request_sha,
            result_payload=result,
            proof_bytes=proof_bytes,
            proof_sha256=proof_sha,
            solve_evidence=(),
        )
        self.last_evidence_receipts = ({
            "uri": f"gs://proofs/{proof_sha}.json",
            "generation": "1",
            "sha256": proof_sha,
            "bytes": len(proof_bytes),
        },) if self.retain_receipt else ()
        return None


def _prepared_for_cell(source_hash: str) -> later.PreparedLaterSlate:
    players = _players()
    worlds = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    draws = np.zeros((len(players), len(worlds)), dtype=np.float32)
    draws.flags.writeable = False
    return later.PreparedLaterSlate(
        season=2023,
        week=1,
        slate_id="2023-w01",
        players=players,
        world_ids=worlds,
        player_draws=draws,
        incumbent_candidates=_legal_rosters(),
        source_freeze_sha256=source_hash,
        artifact_sha256_by_block={block: "e" * 64 for block in rw.WORLD_BLOCKS},
    )


@pytest.fixture(scope="module")
def smoke_cell(source_freeze) -> dict[str, object]:
    return later.run_construction_cell(
        _prepared_for_cell(source_freeze["freeze_sha256"]),
        anatomy_artifact=_anatomy_artifact(),
        pricing_steps={"A": _NullProofStep(), "B": _NullProofStep()},
        mode="smoke",
        proof_validator=lambda proof: None,
    )


def test_construction_captures_exact_proof_envelopes_and_poison(
    smoke_cell, source_freeze,
):
    assert smoke_cell["pricing_optimality_proven"] is True
    assert len(smoke_cell["pricing_proofs"]) == 2
    assert all(row["proof_object"]["sha256"] == row["proof_sha256"]
               for row in smoke_cell["pricing_proofs"])
    prepared = _prepared_for_cell(source_freeze["freeze_sha256"])
    with pytest.raises(later.LR8LaterSourceError, match="no evidence"):
        later.run_construction_cell(
            prepared,
            anatomy_artifact=_anatomy_artifact(),
            pricing_steps={
                "A": _NullProofStep(retain_receipt=False),
                "B": _NullProofStep(),
            },
            mode="smoke",
            proof_validator=lambda proof: None,
        )


def test_smoke_terminal_and_mechanics_book_binding_fail_closed(
    smoke_cell, source_freeze,
):
    authority = _smoke_authority(smoke_cell)
    poison_authority = deepcopy(authority)
    poison_authority["terminal"]["failed_count"] = 1
    terminal_body = dict(poison_authority["terminal"])
    terminal_body.pop("terminal_sha256")
    poison_authority["terminal"]["terminal_sha256"] = later.canonical_sha256(
        terminal_body
    )
    terminal_raw = later.canonical_json(poison_authority["terminal"])
    poison_authority["terminal_object"] = _object_receipt(
        "gs://cells/poison-terminal.json", terminal_raw
    )
    with pytest.raises(later.LR8LaterSourceError, match="terminal status"):
        later.validate_smoke_authority(
            poison_authority,
            source_freeze_sha256=smoke_cell["source_freeze_sha256"],
            anatomy_artifact_sha256=smoke_cell["anatomy_artifact_sha256"],
        )

    cells, _, _ = _full_cells(smoke_cell, source_freeze)
    poison_cell = deepcopy(cells[0])
    poison_cell["book_cells"][0]["control_book"] = poison_cell[
        "book_cells"
    ][0]["control_candidates"][1:81]
    book_body = dict(poison_cell["book_cells"][0])
    book_body.pop("cell_sha256")
    poison_cell["book_cells"][0]["cell_sha256"] = later.canonical_sha256(
        book_body
    )
    poison_cell["book_cells_sha256"] = later.canonical_sha256(
        poison_cell["book_cells"]
    )
    cell_body = dict(poison_cell)
    cell_body.pop("cell_sha256")
    poison_cell["cell_sha256"] = later.canonical_sha256(cell_body)
    with pytest.raises(later.LR8LaterSourceError, match="mechanics"):
        later.validate_construction_cell(
            poison_cell,
            expected_cell_sha256=poison_cell["cell_sha256"],
            mode="full",
        )


def _object_receipt(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _smoke_authority(smoke_cell: dict[str, object]) -> dict[str, object]:
    smoke_raw = later.canonical_json(smoke_cell)
    smoke_object = _object_receipt("gs://cells/smoke.json", smoke_raw)
    terminal = {
        "schema": later.SMOKE_TERMINAL_VERSION,
        "execution_name": "lr8-later-smoke-fixture",
        "execution_metadata_object": _object_receipt(
            "gs://cells/smoke-execution.json", b"execution"
        ),
        "finish_ledger_object": _object_receipt(
            "gs://cells/smoke-finish.sha256", b"finish"
        ),
        "smoke_object": smoke_object,
        "smoke_sha256": smoke_cell["cell_sha256"],
        "source_freeze_sha256": smoke_cell["source_freeze_sha256"],
        "anatomy_artifact_sha256": smoke_cell["anatomy_artifact_sha256"],
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
    return {
        "object": smoke_object,
        "smoke_sha256": smoke_cell["cell_sha256"],
        "source_freeze_sha256": smoke_cell["source_freeze_sha256"],
        "anatomy_artifact_sha256": smoke_cell["anatomy_artifact_sha256"],
        "terminal": terminal,
        "terminal_object": _object_receipt(
            "gs://cells/smoke-terminal.json", terminal_raw
        ),
    }


def test_runner_generation_reopens_smoke_terminal_transitive_objects(
    monkeypatch, smoke_cell,
):
    expected = _smoke_authority(smoke_cell)
    receipts = {
        "smoke": expected["object"],
        "smoke_terminal": expected["terminal_object"],
    }
    args_values = {
        "mode": "full",
        "smoke_cell_sha256": smoke_cell["cell_sha256"],
        "smoke_terminal_manifest_sha256": expected["terminal"][
            "terminal_sha256"
        ],
    }
    for prefix, receipt in receipts.items():
        for key in ("uri", "generation", "sha256", "bytes"):
            args_values[f"{prefix}_{key}"] = receipt[key]
    bodies = {
        expected["object"]["uri"]: later.canonical_json(smoke_cell),
        expected["terminal_object"]["uri"]: later.canonical_json(
            expected["terminal"]
        ),
        expected["terminal"]["execution_metadata_object"]["uri"]: b"execution",
        expected["terminal"]["finish_ledger_object"]["uri"]: b"finish",
    }
    opened = []

    def load(_client, receipt):
        opened.append(receipt["uri"])
        return bodies[receipt["uri"]]

    monkeypatch.setattr(runner, "_load", load)
    actual = runner._smoke_authority(SimpleNamespace(**args_values), object())
    assert actual == expected
    assert opened == list(bodies)


def _full_cells(
    smoke_cell: dict[str, object], source_freeze: dict[str, object],
):
    authority = _smoke_authority(smoke_cell)
    template = later.run_construction_cell(
        _prepared_for_cell(source_freeze["freeze_sha256"]),
        anatomy_artifact=_anatomy_artifact(),
        pricing_steps={"A": _NullProofStep(), "B": _NullProofStep()},
        mode="full",
        smoke_authority=authority,
        proof_validator=lambda proof: None,
    )
    cells = []
    receipts = []
    for season, week in later.EXPECTED_SLATE_KEYS:
        cell = deepcopy(template)
        cell["season"] = season
        cell["week"] = week
        cell["slate_id"] = f"{season}-w{week:02d}"
        cell["mechanics"]["season"] = season
        cell["mechanics"]["week"] = week
        cell["mechanics"]["slate_id"] = cell["slate_id"]
        mechanics_body = dict(cell["mechanics"])
        mechanics_body.pop("report_sha256")
        cell["mechanics"]["report_sha256"] = later.canonical_sha256(
            mechanics_body
        )
        for book in cell["book_cells"]:
            book["season"] = season
            book["week"] = week
            body = dict(book)
            body.pop("cell_sha256")
            book["cell_sha256"] = later.canonical_sha256(body)
        cell["book_cells_sha256"] = later.canonical_sha256(cell["book_cells"])
        body = dict(cell)
        body.pop("cell_sha256")
        cell["cell_sha256"] = later.canonical_sha256(body)
        raw = later.canonical_json(cell)
        cells.append(cell)
        receipts.append(_object_receipt(
            f"gs://cells/{season}-w{week:02d}.json", raw
        ))
    return cells, receipts, authority


def test_aggregate_freezes_exact_108_books_and_rejects_incomplete(
    smoke_cell, source_freeze,
):
    cells, receipts, authority = _full_cells(smoke_cell, source_freeze)
    source_raw = later.canonical_json(source_freeze)
    object_receipt = _object_receipt(
        "gs://freezes/source.json", source_raw
    )
    anatomy_freeze = {
        "freeze_sha256": "f" * 64,
        "anatomy_artifact_sha256": smoke_cell["anatomy_artifact_sha256"],
    }
    anatomy_receipt = _object_receipt(
        "gs://freezes/anatomy.json", later.canonical_json(anatomy_freeze)
    )
    freeze = later.aggregate_book_freeze(
        cells,
        cell_objects=receipts,
        source_freeze=source_freeze,
        source_freeze_object=object_receipt,
        anatomy_freeze=anatomy_freeze,
        anatomy_freeze_sha256="f" * 64,
        anatomy_freeze_object=anatomy_receipt,
        smoke_authority=authority,
    )
    assert freeze["cell_count"] == 54
    assert freeze["book_cell_count"] == 108
    assert len(freeze["book_cells"]) == 108
    assert len(freeze["catalogs"]) == 54
    assert freeze["later_period_score_read_licensed"] is True
    assert set(freeze["book_cells"][0]) == later.BOOK_CELL_FIELDS
    poisoned_fit = {**anatomy_freeze, "anatomy_artifact_sha256": "0" * 64}
    with pytest.raises(later.LR8LaterSourceError, match="fit freeze binding"):
        later.aggregate_book_freeze(
            cells,
            cell_objects=receipts,
            source_freeze=source_freeze,
            source_freeze_object=object_receipt,
            anatomy_freeze=poisoned_fit,
            anatomy_freeze_sha256="f" * 64,
            anatomy_freeze_object=_object_receipt(
                "gs://freezes/poison-fit.json",
                later.canonical_json(poisoned_fit),
            ),
            smoke_authority=authority,
        )
    with pytest.raises(later.LR8LaterSourceError, match="cell count"):
        later.aggregate_book_freeze(
            cells[:-1],
            cell_objects=receipts[:-1],
            source_freeze=source_freeze,
            source_freeze_object=object_receipt,
            anatomy_freeze=anatomy_freeze,
            anatomy_freeze_sha256="f" * 64,
            anatomy_freeze_object=anatomy_receipt,
            smoke_authority=authority,
        )


def test_cli_is_default_off_and_smoke_does_not_require_prior_smoke(monkeypatch):
    args = runner.parser().parse_args([
        "construct-cell", "--execute", "--mode", "smoke",
        "--cell-index", "0", "--evidence-root", "/tmp/lr8-evidence",
        "--output-uri", "gs://out/smoke.json", "--run-id", "run",
        "--job", "job", "--code-sha", "a" * 40,
        "--image", f"image@sha256:{'b' * 64}",
        "--source-uri", "gs://in/source.json", "--source-generation", "1",
        "--source-sha256", "c" * 64, "--source-bytes", "1",
        "--source-freeze-sha256", "d" * 64,
        "--fit-uri", "gs://in/fit.json", "--fit-generation", "1",
        "--fit-sha256", "e" * 64, "--fit-bytes", "1",
        "--fit-freeze-sha256", "f" * 64,
    ])
    assert args.smoke_uri is None
    monkeypatch.delenv(runner.ENABLED_ENV, raising=False)
    with pytest.raises(runner.LR8LaterRunnerError, match=runner.ENABLED_ENV):
        runner.construct_cell(args)
    assert "actual" not in runner.CANDIDATE_SQL.lower()
    assert "actual" not in runner.CATALOG_SQL.lower()
