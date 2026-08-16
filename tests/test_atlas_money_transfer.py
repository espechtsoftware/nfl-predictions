import json
import importlib.util
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.research import atlas_money_transfer as transfer
from nfl_dfs.research.atlas_money_source_grid import (
    parse_artifact_name,
    validate_environment_receipt,
    validate_object_interval,
    validate_player_world_payload,
)


CODE_SHA = "a" * 40
PROJECT = "nfl-predictions-503414"
ROOT = Path(__file__).resolve().parents[1]
HARVEST_SPEC = importlib.util.spec_from_file_location(
    "harvest_atlas_money_source_grid",
    ROOT / "scripts" / "harvest_atlas_money_source_grid.py",
)
assert HARVEST_SPEC and HARVEST_SPEC.loader
harvest = importlib.util.module_from_spec(HARVEST_SPEC)
HARVEST_SPEC.loader.exec_module(harvest)


def test_canonical_receipt_is_the_public_production_multinomial_law():
    receipt = transfer.canonical_policy_receipt()
    public = ADOPTED_CLASSIC_POLICY.public_identity()
    assert receipt["policy_id"] == public["policy_id"]
    assert receipt["engine_environment_sha256"] == (
        public["engine_environment_receipt"]["sha256"]
    )
    assert receipt["simulation_law"]["usage_allocation"] == (
        "production-multinomial"
    )


@pytest.mark.parametrize("block", range(5))
@pytest.mark.parametrize("season", (2023, 2024, 2025))
def test_acquisition_environment_changes_only_single_block_plumbing(
    block, season,
):
    env = transfer.acquisition_environment(
        block=block, season=season, code_sha=CODE_SHA, project=PROJECT,
    )
    projection_seed, role_seed = transfer.SEED_PAIRS[block]
    assert env["GAME_SIM_MODE"] == "possession"
    assert env["GAME_SIM_TEAM_FACTORS"] == "1"
    assert env["GAME_SIM_USAGE"] == ""
    assert "DIRICHLET_K" not in env
    assert env["TD_LEDGER"] == ""
    assert env["TABPFN_MARGINAL_TABLE"] == ""
    assert env["SERVED_POSITION_SCALES"] == (
        "QB:0.970,RB:1.005,TE:0.940,WR:1.070"
    )
    assert env["CAND_ARTIFACT_PLAYER_WORLDS"] == "1"
    assert env["PANEL_RUN_ID"] == transfer.panel_id(block)
    assert env["REPLAY_PROJECTION_SEED"] == str(projection_seed)
    assert env["ROLE_BELIEF_SEED"] == str(role_seed)
    assert env["MULTISEED_PORTFOLIO"] == ""
    assert env["MULTISEED_SEED_PAIRS"] == ""
    assert env["MULTISEED_WORLDS_PER_BLOCK"] == ""
    assert env["MULTISEED_CANDIDATE_ENTRY_BASIS"] == ""


def test_environment_receipt_and_gcloud_serialization_are_stable():
    env = transfer.acquisition_environment(
        block=2, season=2024, code_sha=CODE_SHA, project=PROJECT,
    )
    first = transfer.environment_receipt(env)
    second = transfer.environment_receipt(dict(reversed(list(env.items()))))
    assert first == second
    assert json.loads(json.dumps(first))["values"] == env
    text = transfer.gcloud_environment(env)
    assert text.startswith("BLEND_MODEL_WEIGHT=0.45|")
    assert "|GAME_SIM_USAGE=|" in f"|{text}|"
    with pytest.raises(ValueError, match="safely"):
        transfer.gcloud_environment({"BAD": "a|b"})


def test_logged_lever_parser_preserves_comma_values_and_validates_source():
    env = transfer.acquisition_environment(
        block=3, season=2025, code_sha=CODE_SHA, project=PROJECT,
    )
    logged_keys = {
        "CAND_ARTIFACT_PLAYER_WORLDS", "EPISTEMIC_FAMILY",
        "GAME_SIM_MODE", "GAME_SIM_TEAM_FACTORS", "GAME_SIM_USAGE",
        "MODEL_ENSEMBLE", "MODEL_REGISTRY_VARIANT",
        "MULTISEED_CANDIDATE_ENTRY_BASIS", "MULTISEED_PORTFOLIO",
        "MULTISEED_SEED_PAIRS", "MULTISEED_WORLDS_PER_BLOCK",
        "REPLAY_PROJECTION_SEED", "ROLE_BELIEF_FEATURES",
        "ROLE_BELIEF_SEED", "SERVED_POSITION_SCALES",
        "SIM_WIDEN_DRAWS", "TABPFN_MARGINALS",
        "TABPFN_MARGINAL_TABLE", "TD_LEDGER",
    }
    text = ",".join(
        f"{key}={env[key]}" for key in sorted(logged_keys)
    )
    parsed = transfer.validate_logged_source_environment(text, 3)
    assert parsed["ROLE_BELIEF_FEATURES"] == env["ROLE_BELIEF_FEATURES"]
    assert parsed["SERVED_POSITION_SCALES"] == env["SERVED_POSITION_SCALES"]
    with pytest.raises(ValueError, match="differs"):
        transfer.validate_logged_source_environment(
            text + ",DIRICHLET_K=28.154043586960896", 3,
        )
    generated = transfer.source_environment_lever_text(env, 3)
    assert transfer.validate_logged_source_environment(generated, 3) == (
        transfer.expected_logged_source_environment(3)
    )


def test_artifact_native_source_receipt_validates_name_interval_and_payload():
    parsed = parse_artifact_name(
        "cand_scores/20260815-atlas-money-worlds-r2-v1/"
        "2024_w17_deadbeef.npz"
    )
    assert parsed == {
        "panel_run_id": "20260815-atlas-money-worlds-r2-v1",
        "season": 2024,
        "week": 17,
        "slate_run_id": "deadbeef",
    }
    validate_object_interval(
        created="2026-08-16T01:01:00Z",
        execution_start="2026-08-16T01:00:00Z",
        execution_complete="2026-08-16T01:02:00Z",
    )
    with pytest.raises(ValueError, match="outside"):
        validate_object_interval(
            created="2026-08-16T01:03:00Z",
            execution_start="2026-08-16T01:00:00Z",
            execution_complete="2026-08-16T01:02:00Z",
        )
    buffer = BytesIO()
    np.savez_compressed(
        buffer,
        cand_ix=np.arange(2, dtype=np.int32),
        totals=np.ones((2, 10_000), dtype=np.float32),
        tail_line=np.asarray(194.0, dtype=np.float32),
        player_ids=np.asarray(["p1", "p2"]),
        player_draws=np.ones((2, 10_000), dtype=np.float32),
    )
    summary = validate_player_world_payload(buffer.getvalue())
    assert summary["source_rows"] == 2
    assert summary["players"] == 2
    assert summary["worlds"] == 10_000


def test_environment_receipt_is_recomputed_not_trusted():
    env = transfer.acquisition_environment(
        block=0, season=2023, code_sha=CODE_SHA, project=PROJECT,
    )
    receipt = transfer.environment_receipt(env)
    assert validate_environment_receipt(receipt) == env
    receipt["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash differs"):
        validate_environment_receipt(receipt)


def test_hybrid_grid_recovers_only_missing_candidate_metadata(
    monkeypatch, tmp_path,
):
    run_dir = tmp_path / "run"
    (run_dir / "environment-receipts").mkdir(parents=True)
    (run_dir / "execution-metadata").mkdir()
    ledger = []
    executions = {}
    for block in range(5):
        for season in (2023, 2024, 2025):
            panel = transfer.panel_id(block)
            execution = f"exec-r{block}-{season}"
            ledger.append(f"{block} {season} {panel} job {execution}")
            env = transfer.acquisition_environment(
                block=block, season=season, code_sha=CODE_SHA,
                project=PROJECT,
            )
            (run_dir / "environment-receipts" /
             f"r{block}-{season}.json").write_text(
                json.dumps(transfer.environment_receipt(env)),
                encoding="utf-8",
            )
            (run_dir / "execution-metadata" / f"{execution}.json").write_text(
                json.dumps({"status": {
                    "conditions": [{"type": "Completed", "status": "True"}],
                    "succeededCount": 1,
                    "failedCount": 0,
                    "startTime": "2026-08-16T01:00:00Z",
                    "completionTime": "2026-08-16T02:00:00Z",
                }}),
                encoding="utf-8",
            )
            executions[(panel, season)] = (execution, env)
    (run_dir / "executions.txt").write_text(
        "\n".join(ledger) + "\n", encoding="utf-8",
    )

    buffer = BytesIO()
    np.savez_compressed(
        buffer,
        cand_ix=np.arange(2, dtype=np.int32),
        totals=np.ones((2, 10_000), dtype=np.float32),
        tail_line=np.asarray(194.0, dtype=np.float32),
        player_ids=np.asarray(["p1", "p2"]),
        player_draws=np.ones((2, 10_000), dtype=np.float32),
    )
    payload = buffer.getvalue()
    digest = __import__("hashlib").sha256(payload).hexdigest()

    class Blob:
        def __init__(self, name):
            self.name = name
            self.generation = 1
            self.time_created = datetime(
                2026, 8, 16, 1, 30, tzinfo=timezone.utc,
            )
            self.size = len(payload)

        def download_as_bytes(self):
            return payload

    blobs = []
    rows = []
    missing = (transfer.panel_id(3), 2025, 1)
    for block in range(5):
        panel = transfer.panel_id(block)
        for season in (2023, 2024, 2025):
            env = executions[(panel, season)][1]
            lever_env = transfer.source_environment_lever_text(env, block)
            for week in range(1, 19):
                name = (
                    f"cand_scores/{panel}/{season}_w{week}_"
                    f"{block}{season}{week:02x}.npz"
                )
                blobs.append(Blob(name))
                if (panel, season, week) != missing:
                    rows.append({
                        "panel_run_id": panel,
                        "season": season,
                        "week": week,
                        "score_artifact_uri": f"gs://{PROJECT}-raw/{name}",
                        "score_artifact_sha256": digest,
                        "code_sha": CODE_SHA,
                        "lever_env": lever_env,
                        "source_rows": 2,
                        "uri_count": 1,
                        "sha_count": 1,
                        "code_count": 1,
                        "lever_count": 1,
                    })

    class Client:
        def __init__(self, project):
            assert project == PROJECT

        def bucket(self, name):
            assert name == f"{PROJECT}-raw"
            return object()

        def list_blobs(self, name, prefix):
            assert name == f"{PROJECT}-raw"
            return [blob for blob in blobs if blob.name.startswith(prefix)]

    monkeypatch.setattr(harvest.storage, "Client", Client)
    grid, counts = harvest.build_grid(
        project=PROJECT,
        bucket_name=f"{PROJECT}-raw",
        run_dir=run_dir,
        bq_rows=rows,
        code_sha=CODE_SHA,
    )
    assert len(grid) == 270
    assert counts == {"candidate_table": 269, "gcs_artifact_recovery": 1}
    recovered = [row for row in grid if row["source_binding"].startswith("gcs")]
    assert len(recovered) == 1
    assert (recovered[0]["panel_run_id"], recovered[0]["season"],
            recovered[0]["week"]) == missing
    assert recovered[0]["players_if_recovered"] == 2


@pytest.mark.parametrize("block", (-1, 5))
def test_invalid_block_is_rejected(block):
    with pytest.raises(ValueError, match="block"):
        transfer.acquisition_environment(
            block=block, season=2024, code_sha=CODE_SHA, project=PROJECT,
        )


def test_cloud_launcher_is_create_only_scorefree_and_policy_bound():
    text = (ROOT / "scripts/cloud_atlas_money_worlds.sh").read_text()
    assert "strict Phase S ATLAS harvest must complete first" in text
    assert "policy_environment_sha256=$POLICY_SHA" in text
    assert "CAND_ARTIFACT_PLAYER_WORLDS" not in text
    assert "atlas_money_world_env.py" in text
    assert "uses_realized_outcomes=false" in text
    assert "usage_allocation=production-multinomial" in text
    assert "--memory 16Gi" in text
    assert "--max-retries 0" in text
    assert "--task-timeout 4h" in text
    assert "COUNT(*) AS n" in text


def test_acquisition_finisher_binds_execution_and_complete_source_grid():
    text = (ROOT / "scripts/cloud_finish_atlas_money_worlds.sh").read_text()
    harvester = (
        ROOT / "scripts/harvest_atlas_money_source_grid.py"
    ).read_text()
    assert 'row.get("type") == "Completed"' in text
    assert 'actual_env != receipt.get("values")' in text
    assert 'container.get("image") != image' in text
    assert '"cpu": "4", "memory": "16Gi"' in text
    assert 'len(rows) != 270' in text
    assert 'len(reference) != 54' in text
    assert "harvest_atlas_money_source_grid.py" in text
    assert "artifact_native_repair_sha256" in text
    assert "gcs_artifact_recovery" in text
    assert "blob.download_as_bytes()" in harvester
    assert "validate_object_interval" in harvester
    assert "set(objects) != expected" in harvester
    assert "labels_complete" not in text
    assert "actual_score" not in text
    assert "selected" not in text


def test_transfer_runner_is_packaged_and_scorefree_source_bound():
    runner = (ROOT / "scripts/run_atlas_money_transfer.py").read_text()
    docker = (ROOT / "Dockerfile").read_text()
    assert "aggregate_transfer_gate" in runner
    assert "validate_logged_source_environment" in runner
    assert "resolve_panel_artifacts" in runner
    assert "FORBIDDEN_SOURCE_TOKENS" in runner
    assert '"labels_complete"' in runner
    assert "candidate_or_lineup_scores_read" in runner
    assert "production_change_licensed" in runner
    assert "LAW_SEPARATION_AMENDMENT_SHA256" in runner
    assert "ARTIFACT_NATIVE_REPAIR_SHA256" in runner
    assert "source_binding_counts" in runner
    assert "ENVIRONMENT_RECEIPTS_SHA256" in runner
    assert "_combination_reach_summary" in runner
    assert '"transfer_disposition"' in runner
    assert '"effect_may_be_law_dependent": True' in runner
    assert "COPY scripts/run_atlas_money_transfer.py" in docker


def test_transfer_cloud_contract_is_create_only_and_strictly_harvested():
    launch = (ROOT / "scripts/cloud_atlas_money_transfer.sh").read_text()
    finish = (
        ROOT / "scripts/cloud_finish_atlas_money_transfer.sh"
    ).read_text()
    assert "strict ATLAS money-world acquisition is incomplete" in launch
    assert "gcloud storage objects describe" in launch
    assert "--memory 32Gi" in launch
    assert "--max-retries 0" in launch
    assert "ACQUISITION_MANIFEST_SHA256" in launch
    assert "LAW_SEPARATION_AMENDMENT_SHA256" in launch
    assert "ARTIFACT_NATIVE_REPAIR_SHA256" in launch
    assert "ENVIRONMENT_RECEIPTS_SHA256" in launch
    assert 'row.get("type") == "Completed"' in finish
    assert 'container.get("image") != manifest.get("image")' in finish
    assert 'preflight.get("artifact_count") != 270' in finish
    assert 'gate.get("passes_part_a_transfer")' in finish
    assert 'sum(paired.values()) != 10800' in finish
    assert "transfer mechanical/effect disposition differs" in finish
    assert "transfer combination-reach output differs" in finish
    assert "production_change_licensed" in finish
