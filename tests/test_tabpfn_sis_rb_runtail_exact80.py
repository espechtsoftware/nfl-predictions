import base64
import importlib.util
import json
from pathlib import Path
import zlib

import pytest

from nfl_dfs.research import tabpfn_sis_rb_runtail_lineup_v1 as lineup


ROOT = Path(__file__).parents[1]
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "_sis_rb_runtail_execution",
    ROOT / "scripts" / "verify_tabpfn_sis_rb_runtail_exact80_execution.py",
)
execution_check = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(execution_check)
ANALYZER_SPEC = importlib.util.spec_from_file_location(
    "_sis_rb_runtail_analyzer",
    ROOT / "scripts" / "analyze_tabpfn_sis_rb_runtail_exact80_v1.py",
)
analyzer = importlib.util.module_from_spec(ANALYZER_SPEC)
ANALYZER_SPEC.loader.exec_module(analyzer)

IMAGE = "us-central1-docker.pkg.dev/project/repository/image@sha256:abc"
CODE_SHA = "a" * 40
CONTROL_SCHEDULES = {
    2023: "QB:0.9,RB:0.95,TE:1,WR:1.05",
    2024: "QB:0.91,RB:0.96,TE:0.99,WR:1.04",
    2025: "QB:0.92,RB:0.97,TE:0.98,WR:1.03",
}
TREATMENT_SCHEDULES = {
    2023: "QB:0.93,RB:0.98,TE:1.01,WR:1.02",
    2024: "QB:0.94,RB:0.99,TE:1,WR:1.01",
    2025: "QB:0.95,RB:1,TE:0.99,WR:1",
}


def _execution(arm="control", replicate=3, season=2024):
    family = f"sisrt{arm[0]}{replicate}"
    panel = lineup.panel_id(arm, replicate)
    job = f"replay-{family}-{season}"
    name = f"{job}-abcde"
    base_seed, role_seed = lineup.SEEDS[replicate]
    table = lineup.CONTROL_TABLE if arm == "control" else lineup.TREATMENT_TABLE
    schedules = CONTROL_SCHEDULES if arm == "control" else TREATMENT_SCHEDULES
    values = {
        "GCP_PROJECT": execution_check.PROJECT,
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": table,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": execution_check.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "SERVED_POSITION_SCALES": schedules[season],
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": lineup.FITTED_K,
        "PANEL_RUN_ID": panel,
        "CODE_SHA": CODE_SHA,
        "CAND_LOG_TABLE": (
            f"{execution_check.PROJECT}.nfl_predictions.replay_candidates_staging"
        ),
        "CAND_FEATURE_TABLE": (
            f"{execution_check.PROJECT}.nfl_predictions.slate_player_features"
        ),
        "CAND_ARTIFACT_BUCKET": f"{execution_check.PROJECT}-raw",
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "REPLAY_LINEUPS_TABLE": (
            f"{execution_check.PROJECT}.nfl_features."
            f"replay_lineups_{family}_{season}"
        ),
    }
    payload = {
        "metadata": {"name": name, "labels": {"run.googleapis.com/job": job}},
        "spec": {"template": {"spec": {
            "containers": [{
                "args": ["replay", "--season", str(season), "--contest",
                         "gpp", "--entries", "80"],
                "command": ["nfl-dfs"],
                "env": [{"name": key, "value": value}
                        for key, value in values.items()],
                "image": IMAGE,
                "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
            }],
            "maxRetries": 0,
            "timeoutSeconds": "14400",
        }}},
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
        },
    }
    expected = {
        "arm": arm,
        "replicate": replicate,
        "season": season,
        "panel": panel,
        "job": job,
        "execution_name": name,
        "image": IMAGE,
        "code_sha": CODE_SHA,
        "control_schedules": CONTROL_SCHEDULES,
        "treatment_schedules": TREATMENT_SCHEDULES,
    }
    return payload, expected


def test_frozen_ids_tables_seed_books_and_tail_order():
    assert lineup.panel_id("treatment", 4) == \
        "20260814-sis-runtail-treatment-r4-v1"
    assert lineup.CONTROL_TABLE == "tabpfn_sis_rb_runtail_control_v1"
    assert lineup.TREATMENT_TABLE == "tabpfn_sis_rb_runtail_treatment_v1"
    assert lineup.TAILS == (240, 230, 220, 210, 200, 194, 187)
    assert lineup.SEEDS[2] == (2875959182, 1630284992)


def test_dynamic_schedules_are_complete_canonical_and_bounded():
    lineup.validate_schedule_specs(CONTROL_SCHEDULES)
    with pytest.raises(ValueError, match="incomplete"):
        lineup.validate_schedule_specs({2023: CONTROL_SCHEDULES[2023]})
    invalid = dict(CONTROL_SCHEDULES)
    invalid[2025] = "RB:1,QB:1,TE:1,WR:1"
    with pytest.raises(ValueError, match="canonical"):
        lineup.validate_schedule_specs(invalid)
    invalid[2025] = "QB:0.7,RB:1,TE:1,WR:1"
    with pytest.raises(ValueError, match="outside grid"):
        lineup.validate_schedule_specs(invalid)


def test_every_registered_execution_spec_verifies():
    for arm in ("control", "treatment"):
        for replicate in lineup.SEEDS:
            for season in lineup.SEASONS:
                payload, expected = _execution(arm, replicate, season)
                assert not execution_check.execution_failures(payload, **expected)


def test_wrong_cache_schedule_and_composition_fail_closed():
    payload, expected = _execution("treatment", 2, 2025)
    env = payload["spec"]["template"]["spec"]["containers"][0]["env"]
    for item in env:
        if item["name"] == "TABPFN_MARGINAL_TABLE":
            item["value"] = lineup.CONTROL_TABLE
        if item["name"] == "SERVED_POSITION_SCALES":
            item["value"] = "QB:1,RB:1,TE:1,WR:1"
    env.append({"name": "SIS_ASOE_TARGET_ALLOCATION", "value": "1"})
    failures = execution_check.execution_failures(payload, **expected)
    assert "execution environment TABPFN_MARGINAL_TABLE differs" in failures
    assert "execution environment SERVED_POSITION_SCALES differs" in failures
    assert "execution unexpectedly composes SIS_ASOE_TARGET_ALLOCATION" in failures


def test_nonterminal_is_allowed_only_for_launch_provenance():
    payload, expected = _execution()
    payload["status"] = {
        "conditions": [{"type": "Completed", "status": "Unknown"}]
    }
    assert execution_check.execution_failures(payload, **expected)
    assert not execution_check.execution_failures(
        payload, require_success=False, **expected)


def test_analyzer_transport_and_schedule_base64_round_trip():
    report = {"disposition": "valid", "payload": "x" * 250_000}
    encoded = "".join(analyzer.encoded_report_chunks(report))
    assert json.loads(zlib.decompress(base64.b64decode(encoded))) == report
    schedule_json = json.dumps(CONTROL_SCHEDULES, separators=(",", ":"))
    schedule_b64 = base64.b64encode(schedule_json.encode()).decode()
    assert analyzer._decoded_schedules(schedule_b64) == CONTROL_SCHEDULES
    assert analyzer.BOOTSTRAP_SEED == 8_142_028


def test_cloud_harness_binds_both_score_free_gates_and_no_asoe():
    launcher = (ROOT / "scripts" /
                "cloud_tabpfn_sis_rb_runtail_exact80_v1.sh").read_text()
    finisher = (ROOT / "scripts" /
                "cloud_finish_tabpfn_sis_rb_runtail_exact80_v1.sh").read_text()
    harvester = (ROOT / "scripts" /
                 "cloud_harvest_tabpfn_sis_rb_runtail_exact80_v1.sh").read_text()
    assert "tabpfn-sis-rb-runtail-caches-valid" in launcher
    assert "tabpfn-sis-rb-runtail-final-served-passes" in launcher
    assert "SIS_ASOE_TARGET_ALLOCATION=1" not in launcher
    assert "20260814-sis-runtail-${ARM}-r${REP}-v1" in launcher
    assert "needs exactly 30 cells" in finisher
    assert "TABPFN_SIS_RB_RUNTAIL_EXACT80_V1_CHUNK" in harvester
