from __future__ import annotations

from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_b1_corpus_tail_panel_producer as producer  # noqa: E402
import run_b1_corpus_tail_shadow_transport as shadow  # noqa: E402


CODE_SHA = "a" * 40
GENERATED = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
LOCK = datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)
IMAGE = shadow.IMAGE_REPOSITORY + "@sha256:" + "9" * 64


def _plan() -> tuple[producer.PanelSpec, ...]:
    return producer.panel_plan(
        season=2026,
        week=1,
        snapshot_id="2026w01-sunday-main-early",
    )


def _catalog_rows() -> list[dict]:
    rows = [
        {"id": "QB0", "gsis_id": "GSIS_QB0", "pos": "QB", "team": "A", "opp": "B", "game_id": "G1", "salary": 6000.0},
        {"id": "DST0", "gsis_id": "", "pos": "DST", "team": "H", "opp": "I", "game_id": "G4", "salary": 3000.0},
    ]
    for prefix, position, count, salary in (
        ("RB", "RB", 5, 5000.0),
        ("WR", "WR", 8, 4800.0),
        ("TE", "TE", 4, 4000.0),
    ):
        for index in range(count):
            teams = ("A", "B", "C", "D", "E", "F", "G", "H")
            team = teams[index % len(teams)]
            opp = "B" if team == "A" else "A" if team == "B" else "Z"
            rows.append({
                "id": f"{prefix}{index}",
                "gsis_id": f"GSIS_{prefix}{index}",
                "pos": position,
                "team": team,
                "opp": opp,
                "game_id": f"G{1 + index % 4}",
                "salary": salary,
            })
    return rows


def _rosters() -> list[tuple[str, ...]]:
    rb = [f"RB{i}" for i in range(5)]
    wr = [f"WR{i}" for i in range(8)]
    te = [f"TE{i}" for i in range(4)]
    result: list[tuple[str, ...]] = []
    shapes = (
        (2, 4, 1),
        (2, 3, 2),
        (3, 3, 1),
    )
    for n_rb, n_wr, n_te in shapes:
        for backs in itertools.combinations(rb, n_rb):
            for receivers in itertools.combinations(wr, n_wr):
                for ends in itertools.combinations(te, n_te):
                    result.append(("QB0", *backs, *receivers, *ends, "DST0"))
                    if len(result) == 80:
                        return result
    raise AssertionError("fixture could not produce 80 legal rosters")


def _source_frames(
    plan: tuple[producer.PanelSpec, ...] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    plan = _plan() if plan is None else plan
    catalog = _catalog_rows()
    salary = {row["id"]: int(row["salary"]) for row in catalog}
    rosters = _rosters()
    candidates: list[dict] = []
    players: list[dict] = []
    for panel_index, spec in enumerate(plan):
        slate_run_id = f"slate{panel_index}"
        provenance = producer._expected_candidate_provenance(
            spec, code_sha=CODE_SHA
        )
        if spec.role == "canonical":
            metadata = {
                "portfolio": "CBWU",
                "candidate_budget": 80,
                "candidate_source_counts": {
                    f"R{index}": 16 for index in range(5)
                },
                "novel_candidates_by_seed": {
                    f"R{index}": 80 for index in range(5)
                },
                "world_blocks": 5,
                "worlds_per_block": [10_000] * 5,
            }
        else:
            metadata = {
                "season": 2026,
                "week": 1,
                "tail_line": 194.0,
                "n_entries": 80,
                "candidate_generation_entries": 80,
                "latent_optimization_receipt": [],
                "latent_scenario_receipt": {},
            }
        for index, roster in enumerate(rosters):
            candidates.append({
                "generated_at": GENERATED,
                "panel_run_id": spec.panel_run_id,
                "slate_run_id": slate_run_id,
                "run_type": spec.run_type,
                "code_sha": CODE_SHA,
                "code_dirty": False,
                "config_hash": provenance["config_hash"],
                "lever_env": provenance["lever_env"],
                "seeds": provenance["seeds"],
                "candidate_batch_metadata": json.dumps(
                    metadata, sort_keys=True, separators=(",", ":")
                ),
                "labels_complete": False,
                "research_eligible": False,
                "season": 2026,
                "week": 1,
                "cand_ix": index,
                "players": ",".join(roster),
                "tag": "boom",
                "selected": True,
                "selected_rank": index,
                "salary": sum(salary[player] for player in roster),
                "p_line": 0.01 + index / 10_000,
                "sim_mean": 150.0 + index / 10,
                "sim_sd": 25.0,
                "sim_q50": 148.0 + index / 10,
                "sim_q90": 190.0 + index / 10,
                "sim_q99": 225.0 + index / 10,
                "sim_rank_p_line": index + 1,
                "tail_line": 194.0,
                "n_entries": 80,
                "n_sims": provenance["n_worlds"],
                "n_worlds": provenance["n_worlds"],
            })
        for row in catalog:
            players.append({
                "generated_at": GENERATED,
                "panel_run_id": spec.panel_run_id,
                "slate_run_id": slate_run_id,
                "code_sha": CODE_SHA,
                "config_hash": provenance["config_hash"],
                "research_eligible": False,
                "season": 2026,
                "week": 1,
                **row,
            })
    return (
        pd.DataFrame(candidates).loc[:, producer.CANDIDATE_COLUMNS],
        pd.DataFrame(players).loc[:, producer.PLAYER_COLUMNS],
    )


def _deployment_receipt(path: Path, *, uri: str | None = None) -> Path:
    value = {
        "version": "b1-corpus-tail-shadow-deployment-receipt-v1",
        "object": {
            "uri": shadow.DEPLOYMENT_URI if uri is None else uri,
            "generation": "123",
            "metageneration": "1",
            "bytes": 100,
            "sha256": "c" * 64,
            "create_only": True,
        },
    }
    path.write_bytes(producer._canonical_json(value))
    return path


def _authorized_deployment() -> dict:
    return {
        "status": "deployed-default-off-awaiting-explicit-week-intent",
        "season": 2026,
        "weeks": list(range(1, 7)),
        "production_licensed": False,
        "default_environment": {"CORPUS_TAIL_SHADOW_ENABLED": "0"},
        "code": {"commit_sha": CODE_SHA, "image": IMAGE},
        "historical_license": {
            "historical_gate_passed": True,
            "historical_lease_exact_generation_closed": True,
            "model_artifact_sha256": "d" * 64,
        },
    }


def _query_meta() -> dict:
    stamp = datetime(2026, 9, 13, 15, 30, tzinfo=timezone.utc).isoformat()
    return {
        "job_id": "job-1",
        "location": "US",
        "created": stamp,
        "started": stamp,
        "ended": stamp,
        "total_bytes_processed": 1,
        "query_sha256": "e" * 64,
    }


class Store:
    def classic_slates(self) -> pd.DataFrame:
        return pd.DataFrame({
            "draft_group_id": [123],
            "game_start": [LOCK],
            "teams": [8],
            "players": [100],
        })

    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        assert draft_group_id == 123
        return pd.DataFrame({
            "dk_player_id": list(range(1, 21)),
            "dk_draftable_id": list(range(101, 121)),
            "salary": [5000] * 20,
        })


@pytest.mark.parametrize(
    "column,value",
    (
        ("dk_player_id", 1.5),
        ("dk_draftable_id", 0),
        ("dk_draftable_id", 101),
        ("salary", 5000.75),
    ),
)
def test_salary_snapshot_rejects_fractional_nonpositive_or_duplicate_identity(
    column, value
):
    frame = Store().classic_salaries(123)
    frame[column] = frame[column].astype(object)
    frame.loc[1, column] = value

    class MalformedStore:
        def classic_salaries(self, draft_group_id):
            assert draft_group_id == 123
            return frame

    with pytest.raises(producer.PanelProducerError, match="salary snapshot"):
        producer._salary_inputs(MalformedStore(), 123)


def test_no_verification_query_can_read_an_outcome():
    for sql in (
        producer.schedule_sql(),
        producer.preflight_sql(),
        producer.candidate_sql(),
        producer.player_sql(),
    ):
        lowered = sql.lower()
        assert "actual" not in lowered
        assert "winner" not in lowered
        assert "payout" not in lowered


def test_plan_is_one_adopted_cbwu_control_plus_every_registered_seed():
    plan = _plan()
    assert [row.role for row in plan] == ["canonical"] + ["companion"] * 5
    assert [row.seed_index for row in plan[1:]] == list(range(5))
    assert [
        (row.projection_seed, row.role_seed) for row in plan[1:]
    ] == list(producer.ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs)
    assert len({row.panel_run_id for row in plan}) == 6
    assert plan == _plan()


def test_environment_is_current_policy_and_companion_disables_outer_cbwu():
    canonical, companion = _plan()[:2]
    canonical_env = producer.panel_environment(canonical, code_sha=CODE_SHA)
    companion_env = producer.panel_environment(companion, code_sha=CODE_SHA)
    assert canonical_env["MULTISEED_PORTFOLIO"] == "CBWU"
    assert canonical_env["MULTISEED_SEED_PAIRS"].startswith("R0=0:7331;")
    assert companion_env["MULTISEED_PORTFOLIO"] == ""
    assert companion_env["REPLAY_PROJECTION_SEED"] == str(
        producer.ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[0][0]
    )
    assert companion_env["ROLE_BELIEF_SEED"] == str(
        producer.ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[0][1]
    )
    for env in (canonical_env, companion_env):
        assert env["MODEL_REGISTRY_VARIANT"] == "tail_k1"
        assert env["GAME_SIM_MODE"] == "possession"
        assert env["MIN_LINEUP_SALARY"] == "49000"
        assert env["CAND_FEATURE_TABLE"] == producer.PLAYER_TABLE


def test_emitted_frames_satisfy_exact_b1_source_contract():
    candidates, players = _source_frames()
    result = producer.validate_source_frames(
        candidates,
        players,
        plan=_plan(),
        season=2026,
        week=1,
        code_sha=CODE_SHA,
        lock_at=LOCK,
    )
    assert result["canonical_candidates"] == 80
    assert result["canonical_selected"] == 80
    assert result["candidate_rows"] == 6 * 80
    assert result["deduplicated_rosters"] == 80
    assert set(result["panel_rows"]) == {row.panel_run_id for row in _plan()}


@pytest.mark.parametrize(
    "defect", ("labeled", "late", "missing-panel", "dirty", "wrong-law")
)
def test_source_validation_fails_closed_on_pit_or_identity_defect(defect: str):
    candidates, players = _source_frames()
    if defect == "labeled":
        candidates.loc[0, "labels_complete"] = True
    elif defect == "late":
        players.loc[0, "generated_at"] = LOCK
    elif defect == "missing-panel":
        panel = _plan()[-1].panel_run_id
        candidates = candidates[candidates.panel_run_id.ne(panel)]
    elif defect == "wrong-law":
        candidates.loc[0, "lever_env"] += ",MIN_LINEUP_SALARY=0"
    else:
        candidates.loc[0, "code_dirty"] = True
    with pytest.raises(producer.PanelProducerError):
        producer.validate_source_frames(
            candidates,
            players,
            plan=_plan(),
            season=2026,
            week=1,
            code_sha=CODE_SHA,
            lock_at=LOCK,
        )


def test_producer_is_default_off_before_any_read_or_write(monkeypatch, tmp_path):
    monkeypatch.delenv(producer.ENABLED_ENV, raising=False)
    with pytest.raises(producer.PanelProducerError, match="required explicitly"):
        producer.produce(
            season=2026,
            week=1,
            draft_group_id=123,
            snapshot_id="snap",
            lock_at=LOCK.isoformat(),
            receipt_uri=(
                "gs://nfl-predictions-503414-raw/research/b1/source-receipt.json"
            ),
            deployment_receipt=tmp_path / "absent.json",
            code_sha=CODE_SHA,
            bq_client=object(),
            storage_client=object(),
            store=Store(),
            query=lambda *args: (_ for _ in ()).throw(
                AssertionError("disabled producer queried data")
            ),
        )


def test_success_publishes_attempt_then_builds_companions_before_canonical(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(producer.ENABLED_ENV, "1")
    plan = _plan()
    candidates, players = _source_frames(plan)
    calls = []
    frames = [
        pd.DataFrame({
            "season": [2026],
            "week": [1],
            "gameday": ["2026-09-13"],
            "game_type": ["REG"],
        }),
        pd.DataFrame({
            "source": ["candidates", "players"],
            "row_count": [0, 0],
        }),
        candidates,
        players,
    ]

    def query(client, sql, parameters):
        del client, sql
        assert len(parameters) in (1, 2)
        return frames.pop(0), _query_meta()

    def builder(spec, **kwargs):
        calls.append(("build", spec.role, spec.seed_index, kwargs["code_sha"]))
        return 80

    uploads = []

    def upload(client, *, uri, value):
        del client
        uploads.append((uri, value["version"]))
        return {
            "uri": uri,
            "generation": str(len(uploads)),
            "metageneration": "1",
            "bytes": len(producer._canonical_json(value)),
            "sha256": "f" * 64,
            "created_at": GENERATED.isoformat(),
            "create_only": True,
        }

    monkeypatch.setattr(
        producer,
        "_load_deployment_authorization",
        lambda *args, **kwargs: (
            _authorized_deployment(),
            {
                "uri": shadow.DEPLOYMENT_URI,
                "generation": "123",
                "metageneration": "1",
                "bytes": 100,
                "sha256": "c" * 64,
                "create_only": True,
            },
            "e" * 64,
        ),
    )
    receipt_uri = producer.canonical_receipt_uri(
        season=2026,
        week=1,
        snapshot_id="2026w01-sunday-main-early",
    )
    monkeypatch.setattr(producer, "_upload_create_once", upload)
    result = producer.produce(
        season=2026,
        week=1,
        draft_group_id=123,
        snapshot_id="2026w01-sunday-main-early",
        lock_at=LOCK.isoformat(),
        receipt_uri=receipt_uri,
        deployment_receipt=_deployment_receipt(tmp_path / "deployment.json"),
        code_sha=CODE_SHA,
        bq_client=object(),
        storage_client=object(),
        store=Store(),
        builder=builder,
        query=query,
        now=lambda: GENERATED,
    )
    assert [row[1:] for row in calls] == [
        ("companion", 0, CODE_SHA),
        ("companion", 1, CODE_SHA),
        ("companion", 2, CODE_SHA),
        ("companion", 3, CODE_SHA),
        ("companion", 4, CODE_SHA),
        ("canonical", None, CODE_SHA),
    ]
    assert [version for _, version in uploads] == [
        producer.ATTEMPT_VERSION,
        producer.RECEIPT_VERSION,
    ]
    receipt = result["receipt"]
    assert receipt["canonical_panel"] == plan[0].panel_run_id
    assert receipt["companion_panels"] == [row.panel_run_id for row in plan[1:]]
    assert receipt["realized_outcome_columns_read"] == []
    assert receipt["labels_complete"] is False
    assert receipt["production_licensed"] is False
    assert frames == []


def test_schedule_proof_binds_week_to_lock_sunday():
    good = pd.DataFrame({
        "season": [2026, 2026],
        "week": [1, 1],
        "gameday": ["2026-09-10", "2026-09-13"],
        "game_type": ["REG", "REG"],
    })
    assert producer._validate_schedule(
        good, season=2026, week=1, lock_at=LOCK
    ) == "2026-09-13"
    wrong_week = good.assign(week=2)
    with pytest.raises(producer.PanelProducerError, match="another week"):
        producer._validate_schedule(
            wrong_week, season=2026, week=1, lock_at=LOCK
        )


def test_same_snapshot_cannot_select_an_alternate_receipt_namespace(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(producer.ENABLED_ENV, "1")
    with pytest.raises(producer.PanelProducerError, match="not canonical"):
        producer.produce(
            season=2026,
            week=1,
            draft_group_id=123,
            snapshot_id="same-snapshot",
            lock_at=LOCK.isoformat(),
            receipt_uri=producer.RECEIPT_ROOT + "/alternate/source-receipt.json",
            deployment_receipt=tmp_path / "not-read.json",
            code_sha=CODE_SHA,
            bq_client=object(),
            storage_client=object(),
            store=Store(),
            builder=lambda *args, **kwargs: 80,
            query=lambda *args: (_ for _ in ()).throw(
                AssertionError("noncanonical receipt queried data")
            ),
            now=lambda: GENERATED,
        )


def test_deployment_authorization_pins_official_object_and_runtime(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("CODE_SHA", CODE_SHA)
    monkeypatch.setenv("ANALYSIS_IMAGE", IMAGE)
    path = _deployment_receipt(tmp_path / "deployment.json")
    expected_observed = {
        "uri": shadow.DEPLOYMENT_URI,
        "generation": "123",
        "metageneration": "1",
        "bytes": 100,
        "sha256": "c" * 64,
    }

    def load(client, identity):
        assert client == "storage"
        assert identity == {**expected_observed, "create_only": True}
        return _authorized_deployment(), expected_observed

    monkeypatch.setattr(shadow, "_load_remote_deployment", load)
    deployment, observed, receipt_sha = producer._load_deployment_authorization(
        path,
        storage_client="storage",
        code_sha=CODE_SHA,
        week=1,
    )
    assert deployment == _authorized_deployment()
    assert observed == {**expected_observed, "create_only": True}
    assert receipt_sha == producer.sha256(path.read_bytes()).hexdigest()


def test_locally_forgeable_boolean_license_is_not_an_authorization(tmp_path):
    path = tmp_path / "forged.json"
    path.write_bytes(producer._canonical_json({
        "historical_gate_passed": True,
        "historical_lease_exact_generation_closed": True,
        "model_artifact_sha256": "d" * 64,
    }))
    with pytest.raises(producer.PanelProducerError, match="schema differs"):
        producer._load_deployment_authorization(
            path,
            storage_client="unused",
            code_sha=CODE_SHA,
            week=1,
        )


@pytest.mark.parametrize("defect", ("copied-object", "wrong-code", "wrong-image"))
def test_deployment_authorization_fails_closed_on_provenance_defect(
    defect, monkeypatch, tmp_path
):
    monkeypatch.setenv("CODE_SHA", CODE_SHA)
    monkeypatch.setenv("ANALYSIS_IMAGE", IMAGE)
    uri = "gs://copied/deployment.json" if defect == "copied-object" else None
    path = _deployment_receipt(tmp_path / "deployment.json", uri=uri)
    monkeypatch.setattr(
        shadow,
        "_load_remote_deployment",
        lambda *args: (_authorized_deployment(), {}),
    )
    if defect == "wrong-code":
        monkeypatch.setenv("CODE_SHA", "f" * 40)
    elif defect == "wrong-image":
        monkeypatch.setenv("ANALYSIS_IMAGE", IMAGE[:-1] + "8")
    with pytest.raises(producer.PanelProducerError):
        producer._load_deployment_authorization(
            path,
            storage_client="storage",
            code_sha=CODE_SHA,
            week=1,
        )


def test_create_once_receipt_verifies_the_exact_uploaded_generation():
    class Blob:
        generation = 7
        metageneration = 1
        size = 0
        time_created = GENERATED

        def __init__(self, *, pinned: bool):
            self.pinned = pinned
            self.raw = b""

        def upload_from_string(self, raw, **kwargs):
            assert not self.pinned
            assert kwargs["if_generation_match"] == 0
            self.raw = raw
            pinned.raw = raw
            pinned.size = len(raw)

        def reload(self):
            assert self.pinned

        def download_as_bytes(self, **kwargs):
            assert self.pinned
            assert kwargs["if_generation_match"] == 7
            return self.raw

    current = Blob(pinned=False)
    pinned = Blob(pinned=True)

    class Bucket:
        def blob(self, name, generation=None):
            assert name == "path/receipt.json"
            if generation is None:
                return current
            assert generation == 7
            return pinned

    class Client:
        def bucket(self, name):
            assert name == "bucket"
            return Bucket()

    identity = producer._upload_create_once(
        Client(),
        uri="gs://bucket/path/receipt.json",
        value={"version": "test"},
    )
    assert identity["generation"] == "7"
    assert identity["bytes"] == len(current.raw)
    assert identity["created_at"] == GENERATED.isoformat()
