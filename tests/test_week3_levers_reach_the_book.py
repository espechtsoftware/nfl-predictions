"""The Week-3 availability and construction levers must be able to reach the ENTERED book.

WHY (external review 2026-09-22, §5.1; delegated by production HANDOFF e67103d7). Two adopted levers -- the
chalk fade and P_MIX -- were validated, adopted and then never consumed by the money path, because the path
crosses a repository boundary no guard crossed. This test walks every link of the Week-3 chain for eight levers:

  production (deployed project-slate, this branch = shipping tip 85824fd0 / image eadae06a):
    env var -> cascade_adjust function behaviour -> run_projections.project() write path -> player_projections
  nfl2 (the pinned live clone, EXPECT_SHA in scripts/week_env.sh on the integration branch):
    live_week.py reads proj_points under NFL2_LIVE_CENTER=production -> draws -> generate_candidates -> book
  host chain (integration branch): week_env exports the lever / sunday_build_host passes it and fails closed.

Layers A and B run everywhere (offline). Layer C reads nfl2 and the host scripts by `git show` at pinned
revisions -- never a working tree (the nfl2 main checkout may be mid-merge) -- and skips if either repo is absent.
Layer D (opt-in, NFL_DFS_CHECK_DEPLOYED=1) asks gcloud for the deployed project-slate image and env.
"""
from __future__ import annotations

import inspect
import os
import re
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.inference import cascade_adjust as CA
from nfl_dfs.inference import run_projections as RP

NFL2_REPO = Path(os.environ.get("NFL2_REPO", Path.home() / "projects" / "nfl2"))
PROD_REPO = Path(__file__).resolve().parents[1]
INTEGRATION_REF = os.environ.get("WEEK3_INTEGRATION_REF", "origin/production/week3-integration-20260921")
DEPLOYED_DIGEST = "sha256:42570ce05b8532988bfca8d5ecca5e1651634db49c9aa2756807907e48e9f51d"   # a65fc0cc, 2026-09-23
DEPLOYED_ENV = {"Q_HAIRCUT": "0.80", "CASCADE_DOUBTFUL": "1", "CASCADE_SKIP_PRICED_CARRIES": "1", "QB_Q_PRIMARY_BACKUP_SCALE": "0.20"}


# ---------------------------------------------------------------- A. behaviour: each env var changes the output

def _qb_frame():
    return pd.DataFrame([
        {"gsis_id": "Q1", "display_name": "Starter", "position": "QB", "team": "CHI", "status": None, "injury_status": None, "depth_rank": 1},
        {"gsis_id": "Q2", "display_name": "Backup", "position": "QB", "team": "CHI", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "M1", "display_name": "Mia Starter", "position": "QB", "team": "MIA", "status": None, "injury_status": "Doubtful", "depth_rank": 1},
        {"gsis_id": "M2", "display_name": "Mia Backup", "position": "QB", "team": "MIA", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "N2", "display_name": "Jet Backup", "position": "QB", "team": "NYJ", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "N3", "display_name": "Jet Third", "position": "QB", "team": "NYJ", "status": None, "injury_status": None, "depth_rank": 3},
    ])


def test_A_qb_backup_gate_and_both_refinements_change_the_gated_set(monkeypatch):
    for k in ("QB_BACKUP_GATE", "QB_DOUBTFUL_ABSENT", "QB_NO_DEPTH1_PROMOTE"):
        monkeypatch.delenv(k, raising=False)
    on = CA.find_backup_qbs(_qb_frame())
    assert "Q2" in on, "QB_BACKUP_GATE default must gate a backup behind a healthy starter"
    assert "M1" in on, "QB_DOUBTFUL_ABSENT default must treat a Doubtful starter as absent"
    assert "N3" in on, "QB_NO_DEPTH1_PROMOTE default must promote the shallowest QB and gate the rest"
    monkeypatch.setenv("QB_BACKUP_GATE", "0")
    assert CA.find_backup_qbs(_qb_frame()) == [], "QB_BACKUP_GATE=0 must disable the gate"
    monkeypatch.delenv("QB_BACKUP_GATE")
    monkeypatch.setenv("QB_DOUBTFUL_ABSENT", "0")
    assert "M1" not in CA.find_backup_qbs(_qb_frame()), "QB_DOUBTFUL_ABSENT=0 must change the MIA outcome"
    monkeypatch.delenv("QB_DOUBTFUL_ABSENT")
    monkeypatch.setenv("QB_NO_DEPTH1_PROMOTE", "0")
    assert "N3" not in CA.find_backup_qbs(_qb_frame()), "QB_NO_DEPTH1_PROMOTE=0 must leave NYJ alone"


def test_A_q_haircut_scales_proj_points(monkeypatch):
    feats = pd.DataFrame({"gsis_id": ["A", "B"], "status": ["Q", None], "injury_status": [None, None]})
    out = pd.DataFrame({"gsis_id": ["A", "B"], "proj_points": [10.0, 10.0], "value": [2.0, 2.0]})
    monkeypatch.setenv("Q_HAIRCUT", DEPLOYED_ENV["Q_HAIRCUT"])
    got = CA.apply_questionable_haircut(out, CA.find_questionable_players(feats), CA.questionable_haircut(feats))
    assert got.loc[got.gsis_id == "A", "proj_points"].item() == pytest.approx(8.0)
    assert got.loc[got.gsis_id == "B", "proj_points"].item() == 10.0


def test_A_cascade_doubtful_adds_non_qb_doubtful_sources(monkeypatch):
    feats = pd.DataFrame({"gsis_id": ["W", "Q"], "position": ["WR", "QB"], "status": ["D", "D"], "injury_status": [None, None]})
    monkeypatch.setenv("CASCADE_DOUBTFUL", "0")
    assert CA.find_out_players(feats) == []
    monkeypatch.setenv("CASCADE_DOUBTFUL", DEPLOYED_ENV["CASCADE_DOUBTFUL"])
    assert CA.find_out_players(feats) == ["W"], "QBs stay with the backup-QB gate"


def test_A_skip_priced_carries_reads_the_report_out_set(monkeypatch):
    feats = pd.DataFrame({"gsis_id": ["R1", "R2"], "injury_status": ["Out", None]})
    assert CA._report_out_ids(feats) == {"R1"}
    src = inspect.getsource(CA.adjust_for_inactives)
    assert 'os.environ.get(\n        "CASCADE_SKIP_PRICED_CARRIES"' in src or "CASCADE_SKIP_PRICED_CARRIES" in src
    assert "if out_id in priced" in src, "the carry-side skip must be wired inside the redistribution loop"


# ---------------------------------------------------------------- B. write path: project() applies them before the write

def test_B_project_applies_every_lever_before_the_projection_is_written():
    src = inspect.getsource(RP.project)
    for call in ("find_backup_qbs(", "questionable_haircut(", "find_questionable_players(",
                 "apply_questionable_haircut(", "zero_out_projections("):
        assert call in src, f"run_projections.project() no longer calls {call}"
    assert "out_ids + backup_ids" in src, "gated backup QBs must be zeroed with the out players"
    assert "adjust_for_inactives(" in inspect.getsource(RP._cascade_adjuster)
    assert "adjust=_cascade_adjuster(season)" in inspect.getsource(RP.run), "the cascade must be wired into run()"


# ---------------------------------------------------------------- C. pinned nfl2 + host chain (git show, never a working tree)

def _git_show(repo: Path, ref: str, path: str) -> str | None:
    if not (repo / ".git").exists():
        return None
    r = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _week_env() -> str | None:
    return _git_show(PROD_REPO, INTEGRATION_REF, "scripts/week_env.sh")


def _nfl2_pin() -> str | None:
    env = _week_env()
    m = re.search(r"EXPECT_SHA=\$\{EXPECT_SHA:-\$\{NFL2_EXPECT_SHA:-([0-9a-f]{40})\}\}", env or "")
    return m.group(1) if m else None


needs_chain = pytest.mark.skipif(_nfl2_pin() is None or not (NFL2_REPO / ".git").exists(),
                                 reason="integration branch or nfl2 repository not available on this host")


@needs_chain
def test_C_nfl2_consumes_production_proj_points_at_the_pin():
    lw = _git_show(NFL2_REPO, _nfl2_pin(), "scripts/live_week.py")
    assert lw, f"pinned nfl2 {_nfl2_pin()} not present in {NFL2_REPO}"
    assert 'environ.get("NFL2_LIVE_CENTER") == "production"' in lw
    assert "nfl_predictions.player_projections" in lw and "proj_points" in lw
    assert "mean_proj = np.where(_use, _prod, mean_proj)" in lw, "production proj_points must centre the draws"
    host = _git_show(PROD_REPO, INTEGRATION_REF, "scripts/sunday_build_host.sh")
    assert host and "NFL2_LIVE_CENTER=production" in host, "the Sunday build must run nfl2 production-centred"


@needs_chain
def test_C_doubtful_is_denylisted_before_any_solve_at_the_pin():
    live = _git_show(NFL2_REPO, _nfl2_pin(), "src/nfl2/live.py")
    m = re.search(r"DK_INACTIVE_STATUSES = frozenset\(\{([^}]*)\}\)", live or "")
    assert m and '"D"' in m.group(1), "Doubtful must be in DK_INACTIVE_STATUSES at the live pin"
    lw = _git_show(NFL2_REPO, _nfl2_pin(), "scripts/live_week.py")
    assert lw.index("apply_dk_status_invariant(fr)") < lw.index("generate_candidates("), \
        "the DK denylist must run before candidate generation"


@needs_chain
def test_C_max_per_game_flows_from_week_env_to_the_solver():
    pin = _nfl2_pin()
    env, host = _week_env(), _git_show(PROD_REPO, INTEGRATION_REF, "scripts/sunday_build_host.sh")
    assert re.search(r"export MAX_PER_GAME=\$\{MAX_PER_GAME:-4\}", env), "week_env must default MAX_PER_GAME to 4"
    assert host.count('"${MPG_ARGS[@]}"') >= 2, "both host live_week builds must carry the cap"
    assert "check_cap" in host and "exit 1" in host, "the host must fail closed when the receipt lacks the cap"
    lw = _git_show(NFL2_REPO, pin, "scripts/live_week.py")
    assert '"MAX_PER_GAME": str(a.max_per_game)' in lw and "env=_arm_env" in lw
    assert "check_paid_path_flags(" in lw, "the paid path must use the cap-permitting guard"
    a5 = _git_show(NFL2_REPO, pin, "src/nfl2/live_a5.py")
    assert "def check_paid_path_flags" in a5
    pipe = _git_show(NFL2_REPO, pin, "src/nfl2/pipeline.py")
    assert "optimize_many(pool, n_lineups=n_lev, stack=stack, objective_col=\"proj_tourney\", env=env)" in pipe
    assert "env=env), tag, world=k)" in pipe, "boom solves must receive the env carrying MAX_PER_GAME"
    lineup = _git_show(NFL2_REPO, pin, "src/nfl2/core/lineup.py")
    assert '_env.get("MAX_PER_GAME", "0")' in lineup and "<= max_pg" in lineup


# ---------------------------------------------------------------- D. deployed job (opt-in; needs gcloud auth)

@pytest.mark.skipif(os.environ.get("NFL_DFS_CHECK_DEPLOYED") != "1", reason="set NFL_DFS_CHECK_DEPLOYED=1 to query gcloud")
def test_D_deployed_project_slate_carries_the_levers():
    import json
    r = subprocess.run(["gcloud", "run", "jobs", "describe", "project-slate", "--region", "us-central1",
                        "--project", "nfl-predictions-503414", "--format", "json"], capture_output=True, text=True, check=True)
    c = json.loads(r.stdout)["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
    env = {e["name"]: e.get("value") for e in c.get("env", [])}
    assert c["image"].endswith(DEPLOYED_DIGEST), f"deployed image moved: {c['image']}"
    for k, v in DEPLOYED_ENV.items():
        assert env.get(k) == v, f"{k}: deployed {env.get(k)!r}, expected {v!r}"
    for k in ("QB_BACKUP_GATE", "QB_DOUBTFUL_ABSENT", "QB_NO_DEPTH1_PROMOTE"):
        assert env.get(k, "1") != "0", f"{k} is switched off on the deployed job"
