import base64
import importlib.util
import json
from pathlib import Path
import zlib


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_sis_pass_tail_execution",
    ROOT / "scripts" / "verify_tabpfn_sis_pass_tail_exact80_execution.py",
)
execution_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(execution_check)

ANALYZER_SPEC = importlib.util.spec_from_file_location(
    "_sis_pass_tail_analyzer",
    ROOT / "scripts" / "analyze_tabpfn_sis_pass_tail_exact80_v1.py",
)
analyzer = importlib.util.module_from_spec(ANALYZER_SPEC)
ANALYZER_SPEC.loader.exec_module(analyzer)

IMAGE = "us-central1-docker.pkg.dev/project/repository/image@sha256:abc"
CODE_SHA = "f92ce05"


def _execution(arm="control", replicate=3, season=2024,
               phase_s_arm="control"):
    experiment = execution_check.experiment
    family = f"sispt{arm[0]}{replicate}"
    panel = experiment.panel_id(arm, replicate)
    job = f"replay-{family}-{season}"
    name = f"{job}-abcde"
    base_seed, role_seed = experiment.SEEDS[replicate]
    table = (experiment.CONTROL_TABLE if arm == "control"
             else experiment.TREATMENT_TABLE)
    schedule = (experiment.CONTROL_SCHEDULES if arm == "control"
                else experiment.TREATMENT_SCHEDULES)[season]
    values = {
        "GCP_PROJECT": execution_check.PROJECT,
        "GAME_SIM_MODE": "possession", "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1", "TABPFN_MARGINAL_TABLE": table,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": execution_check.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed), "REPLACEMENT_SLOTS": "12",
        "N_CE": "0", "N_EPISTEMIC": "12", "N_GUMBEL": "0",
        "N_BOOM": "40", "SERVED_POSITION_SCALES": schedule,
        "GAME_SIM_USAGE": "dirichlet", "DIRICHLET_K": experiment.FITTED_K,
        "PANEL_RUN_ID": panel, "CODE_SHA": CODE_SHA,
        "CAND_LOG_TABLE": (
            f"{execution_check.PROJECT}.nfl_predictions.replay_candidates_staging"),
        "CAND_FEATURE_TABLE": (
            f"{execution_check.PROJECT}.nfl_predictions.slate_player_features"),
        "CAND_ARTIFACT_BUCKET": f"{execution_check.PROJECT}-raw",
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "REPLAY_LINEUPS_TABLE": (
            f"{execution_check.PROJECT}.nfl_features."
            f"replay_lineups_{family}_{season}"),
    }
    if phase_s_arm == "treatment":
        values.update({"SIS_ASOE_TARGET_ALLOCATION": "1",
                       "SIS_ASOE_BETA": experiment.FROZEN_BETA})
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
            }], "maxRetries": 0, "timeoutSeconds": "14400",
        }}},
        "status": {"conditions": [{"type": "Completed", "status": "True"}],
                   "succeededCount": 1},
    }
    expected = {
        "arm": arm, "replicate": replicate, "season": season,
        "panel": panel, "job": job, "execution_name": name,
        "image": IMAGE, "code_sha": CODE_SHA, "phase_s_arm": phase_s_arm,
    }
    return payload, expected


def test_every_registered_pass_tail_execution_spec_verifies():
    for phase_s_arm in ("control", "treatment"):
        for arm in ("control", "treatment"):
            for replicate in execution_check.experiment.SEEDS:
                for season in execution_check.experiment.SEASONS:
                    payload, expected = _execution(
                        arm, replicate, season, phase_s_arm)
                    assert not execution_check.execution_failures(
                        payload, **expected)


def test_wrong_cache_schedule_and_conditional_asoe_fail_closed():
    payload, expected = _execution("treatment", 2, 2025, "treatment")
    env = payload["spec"]["template"]["spec"]["containers"][0]["env"]
    for item in env:
        if item["name"] == "TABPFN_MARGINAL_TABLE":
            item["value"] = execution_check.experiment.CONTROL_TABLE
        if item["name"] == "SERVED_POSITION_SCALES":
            item["value"] = "QB:1,RB:1,TE:1,WR:1"
    env[:] = [item for item in env
              if item["name"] != "SIS_ASOE_TARGET_ALLOCATION"]
    failures = execution_check.execution_failures(payload, **expected)
    assert "execution environment TABPFN_MARGINAL_TABLE differs" in failures
    assert "execution environment SERVED_POSITION_SCALES differs" in failures
    assert "execution environment SIS_ASOE_TARGET_ALLOCATION differs" in failures


def test_nonterminal_is_allowed_only_during_launch_provenance_check():
    payload, expected = _execution()
    payload["status"] = {"conditions": [{"type": "Completed", "status": "Unknown"}]}
    assert execution_check.execution_failures(payload, **expected)
    assert not execution_check.execution_failures(
        payload, require_success=False, **expected)


def test_analyzer_chunk_transport_round_trips():
    report = {"disposition": "valid", "payload": "x" * 250_000}
    encoded = "".join(analyzer.encoded_report_chunks(report))
    assert json.loads(zlib.decompress(base64.b64decode(encoded))) == report
    assert all(len(chunk) <= analyzer.OUTPUT_CHUNK_SIZE
               for chunk in analyzer.encoded_report_chunks(report))
