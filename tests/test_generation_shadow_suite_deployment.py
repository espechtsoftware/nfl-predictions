from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cloud_generation_shadow_suite.sh"
BUILD = ROOT / "cloudbuild.generation-shadow-suite.yaml"
TEST_CODE_SHA = "1" * 40


def _install_fake_git(directory: Path, code_sha: str = TEST_CODE_SHA) -> None:
    """Make launcher tests independent of a checkout-local ``.git`` tree."""

    fake = directory / "git"
    fake.write_text(
        "#!/bin/sh\n"
        f"if [ \"$*\" = \"rev-parse --show-toplevel\" ]; then printf '%s\\n' '{ROOT}'; exit 0; fi\n"
        f"if [ \"$*\" = \"-C {ROOT} rev-parse HEAD\" ]; then printf '%s\\n' '{code_sha}'; exit 0; fi\n"
        f"case \"$*\" in \"-C {ROOT} cat-file -e {code_sha}^{{commit}}\") exit 0;; esac\n"
        "exit 98\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)


def test_launcher_and_build_contract_are_isolated_and_bounded() -> None:
    script = SCRIPT.read_text()
    build = BUILD.read_text()
    assert "generation-shadow-suite" in script
    assert "shadow-generation-suite" in script
    assert "--tasks 1" in script and "--parallelism 1" in script
    assert "--max-retries 0" in script and "--task-timeout 86400s" in script
    assert "--cpu 8" in script and "--memory 32Gi" in script
    assert "IMAGE_URI=$IMAGE" in script
    assert "ANALYSIS_IMAGE" not in script
    assert "--async --format=json" in script
    assert "scheduler" not in script.lower()
    assert "gcloud iam" not in script.lower()
    assert "money" in script.lower()
    assert "prospective_generation_shadow_suite.py" in build
    assert "prospective_generation_shadow_evaluation.py" in build
    assert "prospective_generation_shadow_field_bridge.py" in build
    assert "prospective_generation_shadow_operator.py" in build
    assert "test_prospective_generation_retrieval_crossing.py" in build
    assert (
        "--deselect=tests/test_prospective_boom_first.py::"
        "test_boom_first_cli_and_quota_safe_manual_launch_are_registered"
    ) in build
    assert "cloud_boom_first_paired_shadow.sh" not in build
    assert "resume_2026_production_schedulers.py" not in build
    assert "shadow-generation-suite --help" in build
    assert "shadow-generation-operator preregister --help" in build


def test_launcher_rejects_mutable_image_before_gcloud(tmp_path: Path) -> None:
    fake = tmp_path / "gcloud"
    fake.write_text("#!/bin/sh\nexit 99\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    result = subprocess.run(
        ["bash", str(SCRIPT), "example/image:latest", "0" * 40],
        cwd=ROOT, env=env, text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert "digest-pinned" in result.stderr


def test_launcher_deploys_validates_and_prints_execution(tmp_path: Path) -> None:
    code_sha = TEST_CODE_SHA
    image = "us.example/research/shadow@sha256:" + "a" * 64
    log = tmp_path / "calls.log"
    fake = tmp_path / "gcloud"
    fake.write_text(
        """#!/usr/bin/env python3
import json, os, sys
a=sys.argv[1:]
with open(os.environ['GCLOUD_LOG'],'a') as f: f.write(' '.join(a)+'\\n')
image=os.environ['EXPECTED_IMAGE']; sha=os.environ['EXPECTED_SHA']; job='generation-shadow-suite'
args=['shadow-generation-suite','--season','2026','--week','1','--draft-group-id','123',
 '--slate-lock-at','2026-09-13T17:00:00Z']
container={'image':image,'command':['nfl-dfs'],'args':args,
 'resources':{'limits':{'cpu':'8','memory':'32Gi'}},
 'env':[{'name':'CODE_SHA','value':sha},{'name':'IMAGE_URI','value':image}]}
if a[:3] == ['run','jobs','describe'] and any('value(metadata.name)' in x for x in a):
 sys.exit(1)
if a[:3] == ['run','jobs','describe']:
 print(json.dumps({'spec':{'template':{'spec':{'taskCount':1,'parallelism':1,
  'template':{'spec':{'maxRetries':0,'timeout':'86400s','serviceAccountName':
  'nfl-dfs-runner@nfl-predictions-503414.iam.gserviceaccount.com','containers':[container]}}}}}})); sys.exit()
if a[:3] == ['run','jobs','execute']:
 print(json.dumps({'metadata':{'name':job+'-abc12'}})); sys.exit()
if a[:4] == ['run','jobs','executions','describe']:
 print(json.dumps({'metadata':{'name':job+'-abc12','labels':{'run.googleapis.com/job':job}},
  'spec':{'taskCount':1,'parallelism':1,'template':{'spec':{'maxRetries':0,
  'timeout':'86400s','containers':[container]}}}})); sys.exit()
sys.exit(0)
"""
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    _install_fake_git(tmp_path, code_sha)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GCLOUD_LOG": str(log),
        "EXPECTED_IMAGE": image,
        "EXPECTED_SHA": code_sha,
        "GENERATION_SHADOW_EXECUTE": "1",
        "GENERATION_SHADOW_SEASON": "2026",
        "GENERATION_SHADOW_WEEK": "1",
        "GENERATION_SHADOW_DRAFT_GROUP_ID": "123",
        "GENERATION_SHADOW_SLATE_LOCK_AT": "2026-09-13T17:00:00Z",
        "GENERATION_SHADOW_ALLOW_CREATE": "1",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), image, code_sha], cwd=ROOT, env=env,
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generation-shadow-suite-abc12"
    calls = log.read_text()
    assert "run jobs deploy generation-shadow-suite" in calls
    assert "run jobs execute generation-shadow-suite" in calls
    assert "--async --format=json" in calls
    assert "--draft-group-id,123" in calls
    assert "scheduler" not in calls


def test_launcher_defaults_to_deploy_without_launching(tmp_path: Path) -> None:
    code_sha = TEST_CODE_SHA
    image = "us.example/research/shadow@sha256:" + "b" * 64
    log = tmp_path / "calls.log"
    fake = tmp_path / "gcloud"
    fake.write_text(
        """#!/usr/bin/env python3
import json, os, sys
a=sys.argv[1:]
with open(os.environ['GCLOUD_LOG'],'a') as f: f.write(' '.join(a)+'\\n')
image=os.environ['EXPECTED_IMAGE']; sha=os.environ['EXPECTED_SHA']
container={'image':image,'command':['nfl-dfs'],'args':['shadow-generation-suite'],
 'resources':{'limits':{'cpu':'8','memory':'32Gi'}},
 'env':[{'name':'CODE_SHA','value':sha},{'name':'IMAGE_URI','value':image}]}
if a[:3] == ['run','jobs','describe'] and any('value(metadata.name)' in x for x in a):
 sys.exit(1)
if a[:3] == ['run','jobs','describe']:
 print(json.dumps({'spec':{'template':{'spec':{'taskCount':1,'parallelism':1,
  'template':{'spec':{'maxRetries':0,'timeout':'86400s','serviceAccountName':
  'nfl-dfs-runner@nfl-predictions-503414.iam.gserviceaccount.com','containers':[container]}}}}}})); sys.exit()
if a[:3] == ['run','jobs','execute']:
 sys.exit(88)
sys.exit(0)
"""
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    _install_fake_git(tmp_path, code_sha)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GCLOUD_LOG": str(log),
        "EXPECTED_IMAGE": image,
        "EXPECTED_SHA": code_sha,
        "GENERATION_SHADOW_ALLOW_CREATE": "1",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), image, code_sha], cwd=ROOT,
        env=env, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "DEPLOYED:generation-shadow-suite"
    calls = log.read_text()
    assert "run jobs deploy generation-shadow-suite" in calls
    assert "run jobs execute generation-shadow-suite" not in calls


def test_launcher_execute_requires_explicit_slate_authority(tmp_path: Path) -> None:
    code_sha = TEST_CODE_SHA
    image = "us.example/research/shadow@sha256:" + "c" * 64
    fake = tmp_path / "gcloud"
    fake.write_text("#!/bin/sh\nexit 99\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    _install_fake_git(tmp_path, code_sha)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GENERATION_SHADOW_EXECUTE": "1",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), image, code_sha], cwd=ROOT,
        env=env, text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert "GENERATION_SHADOW_SEASON" in result.stderr


def test_launcher_does_not_create_an_unapproved_job(tmp_path: Path) -> None:
    image = "us.example/research/shadow@sha256:" + "d" * 64
    fake = tmp_path / "gcloud"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    _install_fake_git(tmp_path)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}

    result = subprocess.run(
        ["bash", str(SCRIPT), image, TEST_CODE_SHA], cwd=ROOT,
        env=env, text=True, capture_output=True,
    )

    assert result.returncode == 2
    assert "GENERATION_SHADOW_ALLOW_CREATE=1" in result.stderr


def test_launcher_uses_update_for_existing_dedicated_job() -> None:
    text = SCRIPT.read_text()
    assert 'gcloud run jobs update "$JOB"' in text
    assert 'gcloud run jobs deploy "$JOB"' in text
