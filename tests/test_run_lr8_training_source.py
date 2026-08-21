from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import re
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_lr8_training_source as runner  # noqa: E402


PROJECT = "nfl-predictions-503414"
TABLES = {
    "catalog": f"{PROJECT}.nfl_predictions.slate_player_features",
    "candidate": f"{PROJECT}.nfl_predictions.replay_candidates_staging",
    "pit": f"{PROJECT}.nfl_features.player_week_training",
    "tabpfn": f"{PROJECT}.nfl_features.tabpfn_projections_pit_v2",
}


class _Member:
    def __init__(self, value: str):
        self.value = value

    def model_to_string(self) -> str:
        return self.value


def _model(value: str = "fitted-model") -> object:
    return SimpleNamespace(models={"targets": _Member(value)})


def _binding(value: str = "fitted-model") -> runner.FittedModelBinding:
    model = _model(value)
    return runner.FittedModelBinding(
        model=model,
        model_sha256=runner._component_model_sha256(model),
    )


def _players() -> list[dict[str, object]]:
    values = (
        ("01-qb", "QB", "AAA", "BBB", "g1", 5_500),
        ("02-rb", "RB", "AAA", "BBB", "g1", 5_000),
        ("03-rb", "RB", "CCC", "DDD", "g2", 5_000),
        ("04-wr", "WR", "AAA", "BBB", "g1", 5_000),
        ("05-wr", "WR", "BBB", "AAA", "g1", 5_000),
        ("06-wr", "WR", "CCC", "DDD", "g2", 5_000),
        ("07-wr", "WR", "DDD", "CCC", "g2", 5_000),
        ("08-te", "TE", "BBB", "AAA", "g1", 4_500),
        ("09-dst", "DST", "CCC", "DDD", "g2", 3_000),
    )
    return [{
        "season": 2019,
        "week": 1,
        "id": player_id,
        "gsis_id": None if position == "DST" else player_id,
        "pos": position,
        "team": team,
        "opp": opponent,
        "game_id": game_id,
        "salary": salary,
        "mean_projection": 6.25 if position == "DST" else 10.0,
    } for player_id, position, team, opponent, game_id, salary in values]


def _catalog_frame() -> pd.DataFrame:
    return pd.DataFrame(_players(), columns=runner.CATALOG_COLUMNS)


def _incumbent_frame() -> pd.DataFrame:
    return pd.DataFrame([{
        "season": 2019,
        "week": 1,
        "cand_ix": 0,
        "players": [row["id"] for row in _players()],
    }], columns=runner.INCUMBENT_COLUMNS)


def _pit_row(
    *, season: int, gsis_id: str, position: str = "QB", target: bool,
) -> dict[str, object]:
    row: dict[str, object] = {}
    for column in runner.PIT_COLUMNS:
        if column == "season":
            row[column] = season
        elif column == "week":
            row[column] = 1
        elif column == "gsis_id":
            row[column] = gsis_id
        elif column == "position":
            row[column] = position
        elif column == "team":
            row[column] = "AAA"
        elif column == "opponent":
            row[column] = "BBB"
        elif column == "game_id":
            row[column] = "g1"
        elif column == "injury_status":
            row[column] = ""
        elif column in ("is_rookie", "draft_round"):
            row[column] = 0
        elif column == "salary":
            row[column] = 5_000
        elif column == "was_active":
            row[column] = None if target else True
        elif column in runner.MODEL_LABEL_COLUMNS:
            row[column] = None if target else 1.0
        else:
            row[column] = 1.0
    return row


def _pit_frame() -> pd.DataFrame:
    rows = [
        _pit_row(season=season, gsis_id=f"prior-{season}", target=False)
        for season in runner.training.MODEL_TRAINING_SEASONS[2019]
    ]
    rows.extend(
        _pit_row(
            season=2019,
            gsis_id=str(player["id"]),
            position=str(player["pos"]),
            target=True,
        )
        for player in _players()
        if player["pos"] != "DST"
    )
    return pd.DataFrame(rows, columns=runner.PIT_COLUMNS)


def _cache_frame() -> pd.DataFrame:
    rows = []
    for player in _players():
        if player["pos"] == "DST":
            continue
        row = {"season": 2019, "week": 1, "gsis_id": player["id"]}
        row.update({column: 1.0 for column in runner.QUANTILE_COLUMNS})
        rows.append(row)
    return pd.DataFrame(rows, columns=runner.CACHE_COLUMNS)


def _job(spec: runner.QuerySpec) -> dict[str, object]:
    return {
        "job_id": spec.job_id,
        "location": spec.location,
        "query_sha256": spec.query_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "created": "2026-08-20T12:00:00+00:00",
        "started": "2026-08-20T12:00:01+00:00",
        "ended": "2026-08-20T12:00:02+00:00",
        "total_bytes_processed": 123,
        "cache_hit": False,
        "error_result": None,
    }


def _metadata(table: str) -> dict[str, object]:
    return {
        "table_id": table,
        "etag": f"etag-{table}",
        "modified": "2026-08-20T11:59:00+00:00",
        "num_rows": 100,
        "schema_sha256": sha256(table.encode()).hexdigest(),
    }


class _MemoryPublisher:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.reopens: list[tuple[str, str]] = []

    def __call__(self, uri: str, raw: bytes) -> runner.PublishedObject:
        created = uri not in self.objects
        if not created and self.objects[uri] != raw:
            raise runner.LR8SourceRunnerError("create-only collision")
        self.objects.setdefault(uri, raw)
        reopened = self.objects[uri]
        generation = "1"
        self.reopens.append((uri, generation))
        return runner.PublishedObject(
            receipt={
                "uri": uri,
                "generation": generation,
                "sha256": sha256(reopened).hexdigest(),
                "bytes": len(reopened),
            },
            reopened_raw=reopened,
            created=created,
        )


def _config(tmp_path: Path, *, mode: str = "smoke") -> runner.RunnerConfig:
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    return runner.RunnerConfig(
        mode=mode,
        attempt_id="lr8-smoke-test-01",
        project=PROJECT,
        bucket="lr8-source-test-bucket",
        catalog_table=TABLES["catalog"],
        candidate_table=TABLES["candidate"],
        pit_table=TABLES["pit"],
        tabpfn_table=TABLES["tabpfn"],
        evidence_root=evidence.resolve(),
        execute=True,
        enabled=True,
    )


def _query(frames: dict[str, pd.DataFrame]):
    def execute(spec: runner.QuerySpec):
        return frames[spec.label].copy(deep=True), _job(spec)

    return execute


def _adapter(binding: runner.FittedModelBinding, calls: list[dict[str, object]]):
    def materialize(panel, audited_slates, **kwargs):
        observed = runner.components.train(
            panel,
            target_season=kwargs["target_season"],
            num_boost_round=runner.MODEL_BOOST_ROUNDS,
        )
        assert observed is binding.model
        assert kwargs["provenance"] == runner.replay_source.ReplaySourceProvenance()
        calls.append(kwargs)
        audited = audited_slates[0]
        player_ids = tuple(player.player_id for player in audited.players)
        draws = np.full(
            (len(player_ids), runner.training.WORLDS_PER_BLOCK),
            1.25,
            dtype=np.float32,
        )
        draws.flags.writeable = False
        slate = runner.training.ReplaySlateWorlds(
            season=2019,
            week=1,
            player_ids=player_ids,
            player_draws=draws,
            player_ids_sha256=runner.training.player_ids_sha256(player_ids),
            player_draws_sha256=runner.training.array_sha256(draws),
            source_receipts=audited.replay_source_receipts,
            target_outcome_fields_read=(),
        )
        return runner.training.PITReplayBlock(
            target_season=2019,
            block="R0",
            projection_seed=0,
            source_environment_role_seed_nonoperative=7331,
            replay_path_id=runner.training.PIT_REPLAY_PATH_ID,
            model_training_seasons=(2015, 2016, 2017, 2018),
            model_fit_input_sha256=kwargs["model_fit_input_sha256"],
            model_fit_sha256=kwargs["model_fit_sha256"],
            fit_source_receipts=kwargs["fit_source_receipts"],
            slates=(slate,),
            target_player_labels_read=False,
            candidate_labels_read=False,
            candidate_world_family=runner.training.CANDIDATE_WORLD_FAMILY,
            role_belief_worlds_used=False,
            b1_inputs_used=False,
            a2a_inputs_used=False,
            later_period_inputs_used=False,
        )

    return materialize


def _frozen_smoke() -> object:
    attempts = []
    candidates = []
    anatomy_width = len(runner.training.lr8.ANATOMY_FEATURES)
    canonical_players = tuple(runner.rw.PlayerSpec.from_mapping({
        "id": row["id"],
        "pos": row["pos"],
        "team": row["team"],
        "opp": row["opp"],
        "game_id": row["game_id"],
        "salary": row["salary"],
    }) for row in _players())
    catalog_sha = runner.training.catalog_sha256(canonical_players)
    incumbent_sha = runner.training.identities_sha256((tuple(
        row["id"] for row in _players()
    ),))
    player_ids = tuple(player.player_id for player in canonical_players)
    player_draws = np.zeros(
        (len(player_ids), runner.training.WORLDS_PER_BLOCK), dtype=np.float32
    )
    player_draws.flags.writeable = False
    for index in range(runner.training.UNIQUE_OPTIMA_PER_BLOCK):
        roster = tuple(f"p{index:02d}-{slot}" for slot in range(9))
        evidence = ({
            "uri": f"gs://lr8-test/evidence-{index}.json",
            "generation": "1",
            "sha256": sha256(f"evidence-{index}".encode()).hexdigest(),
            "bytes": index + 1,
        },)
        score_column = np.array(
            player_draws[:, index], dtype=np.float32, copy=True, order="C"
        )
        score_column.flags.writeable = False
        request_payload = {
            "season": 2019,
            "week": 1,
            "block": "R0",
            "projection_seed": 0,
            "world_index": index,
            "catalog_sha256": catalog_sha,
            "player_scores_sha256": runner.training.array_sha256(score_column),
            "incumbent_no_goods_sha256": incumbent_sha,
            "candidate_world_family": runner.training.CANDIDATE_WORLD_FAMILY,
            "role_belief_worlds_used": False,
            "hard_domain_id": runner.training.HARD_DOMAIN_ID,
            "former_house_rules_not_applied": list(
                runner.training.FORMER_HOUSE_RULES_NOT_APPLIED
            ),
        }
        attempts.append(runner.training.SolveAttempt(
            block="R0",
            projection_seed=0,
            world_index=index,
            roster=roster,
            objective_micro=1_000_000 + index,
            admitted_unique=True,
            request_sha256=runner.training.canonical_sha256(request_payload),
            evidence_receipts=evidence,
            evidence_manifest_sha256=runner.training.canonical_sha256(
                list(evidence)
            ),
        ))
        candidates.append(runner.training.FrozenCandidate(
            season=2019,
            week=1,
            roster=roster,
            anatomy_features=tuple(0.0 for _ in range(anatomy_width)),
            first_source_block="R0",
            first_source_world_index=index,
            source_occurrences=(("R0", index),),
        ))
    attempt_payload = [{
        "block": attempt.block,
        "projection_seed": attempt.projection_seed,
        "world_index": attempt.world_index,
        "roster": list(attempt.roster),
        "objective_micro": attempt.objective_micro,
        "admitted_unique": attempt.admitted_unique,
        "request_sha256": attempt.request_sha256,
        "evidence_receipts": list(attempt.evidence_receipts),
        "evidence_manifest_sha256": attempt.evidence_manifest_sha256,
    } for attempt in attempts]
    candidate_payload = [list(candidate.roster) for candidate in candidates]
    anatomy_payload = [{
        "roster": list(candidate.roster),
        "features": runner.training._anatomy_payload(  # noqa: SLF001
            candidate.anatomy_features
        ),
    } for candidate in candidates]
    legality_payload = [{
        "roster": list(candidate.roster),
        "hard_domain_id": runner.training.HARD_DOMAIN_ID,
        "dk_classic_legal": True,
        "former_house_rules_applied": [],
    } for candidate in candidates]
    world_order = tuple(range(runner.training.WORLDS_PER_BLOCK))
    return runner.training.FrozenBlockSource(
        block="R0",
        projection_seed=0,
        source_environment_role_seed_nonoperative=7331,
        player_ids=player_ids,
        player_draws=player_draws,
        player_ids_sha256=runner.training.player_ids_sha256(player_ids),
        player_draws_sha256=runner.training.array_sha256(player_draws),
        world_order=world_order,
        world_order_sha256=runner.training.canonical_sha256(list(world_order)),
        source_receipts=({
            "uri": "gs://lr8-test/replay-source.json",
            "generation": "1",
            "sha256": "9" * 64,
            "bytes": 1,
        },),
        solve_attempts=tuple(attempts),
        solve_attempts_sha256=runner.training.canonical_sha256(attempt_payload),
        candidates=tuple(candidates),
        candidate_identities_sha256=runner.training.canonical_sha256(
            candidate_payload
        ),
        anatomy_sha256=runner.training.canonical_sha256(anatomy_payload),
        legality_sha256=runner.training.canonical_sha256(legality_payload),
    )


def _frames() -> dict[str, pd.DataFrame]:
    return {
        "canonical_catalog": _catalog_frame(),
        "canonical_incumbents": _incumbent_frame(),
        "pit_panel_2019": _pit_frame(),
        "tabpfn_2019": _cache_frame(),
    }


def test_sql_is_static_parameterized_and_target_outcome_blind():
    catalog = runner.catalog_sql(TABLES["catalog"])
    incumbent = runner.incumbent_sql(TABLES["candidate"])
    panel = runner.pit_panel_sql(TABLES["pit"], TABLES["catalog"])
    cache = runner.tabpfn_sql(TABLES["tabpfn"], TABLES["catalog"])
    for sql in (catalog, incumbent, panel, cache):
        assert re.search(r"select\s+\*", sql, re.I) is None
        assert not any(token in sql.lower() for token in (
            "actual_score", "contest_rank", "payout", "winner_score",
        ))
        assert "@" in sql
    assert "SPLIT(c.players, ',') AS players" in incumbent
    assert "JOIN target_skill AS c" in panel
    assert "y_dk_points" not in panel
    for column in runner.MODEL_LABEL_COLUMNS:
        assert f"CAST(NULL AS FLOAT64) AS {column}" in panel
    assert "CAST(NULL AS BOOL) AS was_active" in panel
    assert "p.`was_active`" in panel
    assert "p.proj, p.mean_projection" in catalog
    assert re.search(r"CAST\s*\(\s*p\.salary", catalog, re.I) is None


@pytest.mark.parametrize(
    "value",
    [
        5_000,
        np.int64(5_000),
        pd.Series([5_000], dtype="Int64").iloc[0],
        5_000.0,
        np.float64(5_000.0),
    ],
)
def test_catalog_salary_accepts_only_proven_exact_positive_values(value):
    assert runner._exact_catalog_salary(value) == 5_000


@pytest.mark.parametrize(
    "value",
    [
        True,
        np.bool_(False),
        "5000",
        5_000.5,
        np.float64(5_000.5),
        float("nan"),
        float("inf"),
        float("-inf"),
        0,
        0.0,
        -1,
        -1.0,
        None,
        pd.NA,
    ],
)
def test_catalog_salary_rejects_rounding_and_malformed_values(value):
    with pytest.raises(
        runner.LR8SourceRunnerError,
        match="finite positive exact integer",
    ):
        runner._exact_catalog_salary(value)


def test_exact_lattices_and_default_off(tmp_path):
    assert runner.lattice("smoke") == ((2019, (1,), ("R0",)),)
    full = runner.lattice("full-source")
    assert len(full) == 2
    assert sum(len(weeks) for _, weeks, _ in full) == 35
    assert all(blocks == ("R0", "R1") for _, _, blocks in full)

    config = replace(_config(tmp_path), execute=False)
    with pytest.raises(runner.LR8SourceRunnerError, match="--execute"):
        runner.run_source(
            config,
            query=lambda _: (_ for _ in ()).throw(AssertionError()),
            table_metadata=lambda _: (_ for _ in ()).throw(AssertionError()),
            publish=lambda *_: (_ for _ in ()).throw(AssertionError()),
            solver_factory=None,
        )


def test_smoke_reopens_sources_reuses_exact_fit_and_requires_40(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    publisher = _MemoryPublisher()
    binding = _binding()
    config = _config(tmp_path)
    frames = _frames()
    # The live source schema is FLOAT NULLABLE even though DK salary values
    # are integral.  Preserve that raw scalar truth through the extract and
    # prove integrality only at the PlayerSpec boundary.
    frames["canonical_catalog"]["salary"] = frames[
        "canonical_catalog"
    ]["salary"].astype(float)
    adapter_calls: list[dict[str, object]] = []
    factory_calls: list[dict[str, object]] = []

    def factory(**kwargs):
        factory_calls.append(kwargs)
        return lambda request: None

    monkeypatch.setattr(runner, "_smoke_solve", lambda *args: _frozen_smoke())
    monkeypatch.setattr(
        runner.replay_source.replay,
        "build_slates",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("build_slates must not run")
        ),
    )
    result = runner.run_source(
        config,
        query=_query(frames),
        table_metadata=_metadata,
        publish=publisher,
        model_fitter=lambda panel, season: binding,
        adapter=_adapter(binding, adapter_calls),
        solver_factory=factory,
    )
    manifest = result["manifest"]
    assert manifest["mode"] == "smoke"
    assert manifest["solver_status"] == "exact_smoke_complete"
    assert manifest["smoke_unique_candidates"] == 40
    assert manifest["smoke_solve_freeze"]["unique_candidate_count"] == 40
    solve_receipt = manifest["smoke_solve_freeze_object"]
    solve_body = runner._strict_json(
        publisher.objects[solve_receipt["uri"]], label="smoke solve freeze"
    )
    assert solve_body["version"] == runner.SMOKE_SOLVE_FREEZE_VERSION
    assert len(solve_body["ordered_solve_attempts"]) == 40
    assert len(solve_body["ordered_request_payloads"]) == 40
    assert len(solve_body["unique_candidates"]) == 40
    assert runner.training.canonical_sha256(
        solve_body["ordered_solve_attempts"]
    ) == solve_body["ordered_solve_attempts_sha256"]
    assert runner.training.canonical_sha256(
        solve_body["ordered_request_payloads"]
    ) == solve_body["ordered_request_payloads_sha256"]
    for attempt, request_payload in zip(
        solve_body["ordered_solve_attempts"],
        solve_body["ordered_request_payloads"],
        strict=True,
    ):
        assert runner.training.canonical_sha256(
            request_payload
        ) == attempt["request_sha256"]
    assert manifest["target_player_labels_read"] is False
    assert manifest["prior_model_training_labels_queried"] is True
    assert manifest["prior_model_training_seasons"] == {
        "2019": [2015, 2016, 2017, 2018]
    }
    assert manifest["actual_score_queried"] is False
    assert manifest["candidate_totals_queried"] is False
    assert manifest["role_belief_worlds_used"] is False
    assert manifest["build_slates_used"] is False
    assert len(adapter_calls) == 1
    assert adapter_calls[0]["block"] == "R0"
    assert len(factory_calls) == 1
    assert Path(factory_calls[0]["evidence_root"]).is_absolute()
    assert callable(factory_calls[0]["publish_evidence"])
    assert len(publisher.objects) == 6
    assert all(generation == "1" for _, generation in publisher.reopens)
    assert result["manifest_object"]["generation"] == "1"
    catalog_extract = runner._strict_json(
        publisher.objects[f"{config.output_root}/extracts/catalog.json"],
        label="catalog extract",
    )
    assert all(
        isinstance(row["salary"], float)
        and row["salary"].is_integer()
        for row in catalog_extract["rows"]
    )


def test_target_label_poison_fails_before_fit(tmp_path):
    frames = _frames()
    panel = frames["pit_panel_2019"]
    panel.loc[panel.season == 2019, "y_targets"] = 1.0
    with pytest.raises(runner.LR8SourceRunnerError, match="placeholders"):
        runner.run_source(
            _config(tmp_path),
            query=_query(frames),
            table_metadata=_metadata,
            publish=_MemoryPublisher(),
            model_fitter=lambda *_: (_ for _ in ()).throw(AssertionError()),
            adapter=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError()
            ),
            solver_factory=lambda **kwargs: lambda request: None,
        )


def test_table_and_query_job_metadata_drift_fail_closed(tmp_path):
    calls: defaultdict[str, int] = defaultdict(int)

    def drifting(table: str):
        calls[table] += 1
        receipt = _metadata(table)
        if calls[table] == 2 and table == TABLES["pit"]:
            receipt["etag"] = "changed"
        return receipt

    with pytest.raises(runner.LR8SourceRunnerError, match="metadata drifted"):
        runner.run_source(
            _config(tmp_path),
            query=_query(_frames()),
            table_metadata=drifting,
            publish=_MemoryPublisher(),
            model_fitter=lambda *_: (_ for _ in ()).throw(AssertionError()),
            solver_factory=lambda **kwargs: lambda request: None,
        )

    def bad_query(spec: runner.QuerySpec):
        receipt = _job(spec)
        receipt["query_sha256"] = "f" * 64
        return _frames()[spec.label], receipt

    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(runner.LR8SourceRunnerError, match="job receipt differs"):
        runner.run_source(
            replace(_config(tmp_path / "unused"), evidence_root=other.resolve()),
            query=bad_query,
            table_metadata=_metadata,
            publish=_MemoryPublisher(),
            solver_factory=lambda **kwargs: lambda request: None,
        )


def test_smoke_and_full_refuse_without_exact_solver(tmp_path):
    for index, mode in enumerate(("smoke", "full-source")):
        root = tmp_path / f"run-{index}"
        root.mkdir()
        evidence = root / "evidence"
        evidence.mkdir()
        config = replace(
            runner.RunnerConfig(
                mode=mode,
                attempt_id=f"lr8-refusal-{index}",
                project=PROJECT,
                bucket="lr8-source-test-bucket",
                catalog_table=TABLES["catalog"],
                candidate_table=TABLES["candidate"],
                pit_table=TABLES["pit"],
                tabpfn_table=TABLES["tabpfn"],
                evidence_root=evidence.resolve(),
                execute=True,
                enabled=True,
            )
        )
        with pytest.raises(runner.LR8SourceRunnerError, match="exact solver"):
            runner.run_source(
                config,
                query=lambda _: (_ for _ in ()).throw(AssertionError()),
                table_metadata=lambda _: (_ for _ in ()).throw(AssertionError()),
                publish=lambda *_: (_ for _ in ()).throw(AssertionError()),
                solver_factory=None,
            )


def test_model_binding_detects_nonreuse_and_mutation():
    binding = _binding("stable")
    with pytest.raises(runner.LR8SourceRunnerError, match="did not reuse"):
        with runner._bound_replay_model(
            binding, target_season=2019, expected_calls=1
        ):
            pass

    changed = _binding("before")
    with pytest.raises(runner.LR8SourceRunnerError, match="mutated"):
        with runner._bound_replay_model(
            changed, target_season=2019, expected_calls=1
        ):
            assert runner.components.train(
                pd.DataFrame(), target_season=2019, num_boost_round=400
            ) is changed.model
            changed.model.models["targets"].value = "after"


def test_evidence_publisher_uploads_proof_and_all_retained_artifacts(tmp_path):
    evidence_root = tmp_path / "evidence"
    solve_root = evidence_root / "solve"
    solve_root.mkdir(parents=True)
    paths = {}
    for name in ("cbc.log", "model.sol", "model.mps", "domain.json", "model.mst"):
        path = solve_root / name
        path.write_bytes(f"bytes:{name}".encode())
        paths[name] = path
    evidence = SimpleNamespace(
        log_path=paths["cbc.log"],
        log_sha256=sha256(paths["cbc.log"].read_bytes()).hexdigest(),
        solution_path=paths["model.sol"],
        solution_sha256=sha256(paths["model.sol"].read_bytes()).hexdigest(),
        model_path=paths["model.mps"],
        model_sha256=sha256(paths["model.mps"].read_bytes()).hexdigest(),
        variable_domain_manifest_path=paths["domain.json"],
        variable_domain_manifest_sha256=sha256(
            paths["domain.json"].read_bytes()
        ).hexdigest(),
        mip_start_path=paths["model.mst"],
        mip_start_sha256=sha256(paths["model.mst"].read_bytes()).hexdigest(),
    )
    proof = b'{"proof":true}'
    bundle = SimpleNamespace(
        proof_bytes=proof,
        proof_sha256=sha256(proof).hexdigest(),
        request_sha256="a" * 64,
        solve_evidence=(evidence,),
    )
    publisher = _MemoryPublisher()
    receipts = runner._evidence_publisher(
        evidence_root=evidence_root.resolve(),
        output_root="gs://bucket/root",
        publish=publisher,
    )(bundle)
    assert len(receipts) == 6
    assert len(publisher.objects) == 6
    assert any(uri.endswith("proof.json") for uri in publisher.objects)
    assert any(uri.endswith("00-model.mst") for uri in publisher.objects)
    assert all(receipt["generation"] == "1" for receipt in receipts)


class _FakeBlob:
    def __init__(self, store, records, name: str, generation=None):
        self.store = store
        self.records = records
        self.name = name
        self.requested_generation = generation
        self.generation = generation

    def upload_from_string(self, raw, *, content_type, if_generation_match):
        self.records.append((self.name, content_type, if_generation_match))
        if self.name in self.store:
            raise RuntimeError("precondition")
        self.store[self.name] = (bytes(raw), "7")
        self.generation = "7"

    def reload(self):
        self.generation = self.store[self.name][1]

    def download_as_bytes(self, *, if_generation_match):
        raw, generation = self.store[self.name]
        assert str(if_generation_match) == generation
        assert str(self.requested_generation) == generation
        return raw


class _FakeBucket:
    def __init__(self, store, records):
        self.store = store
        self.records = records

    def blob(self, name, generation=None):
        return _FakeBlob(self.store, self.records, name, generation)


class _FakeStorage:
    def __init__(self):
        self.store = {}
        self.records = []

    def bucket(self, name):
        assert name == "bucket"
        return _FakeBucket(self.store, self.records)


def test_create_only_publish_idempotency_collision_and_content_types(monkeypatch):
    storage = _FakeStorage()
    monkeypatch.setattr(runner, "_precondition_failed", lambda exc: True)
    uri = "gs://bucket/extract.json"
    first = runner._default_publish(storage, uri, b"one")
    second = runner._default_publish(storage, uri, b"one")
    assert first.created is True
    assert second.created is False
    assert first.receipt["generation"] == "7"
    assert storage.records[0] == ("extract.json", "application/json", 0)
    with pytest.raises(runner.LR8SourceRunnerError, match="collision"):
        runner._default_publish(storage, uri, b"two")
    assert runner._content_type("gs://bucket/model.mps").startswith("text/plain")
    assert runner._content_type("gs://bucket/raw.bin") == "application/octet-stream"


@pytest.mark.parametrize("bad", [False, None, 1, "yes"])
def test_execute_and_enabled_are_literal_bools(tmp_path, bad):
    config = _config(tmp_path)
    config = replace(config, execute=bad)
    with pytest.raises(runner.LR8SourceRunnerError):
        runner._validate_config(config)
