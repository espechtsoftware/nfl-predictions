"""Dashboard deploy assets: the IAM/IAP assertion, and the deploy script's
guards and gcloud calls against a stub gcloud (nothing reaches GCP)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "deploy_dashboard.sh"


def _iam():
    spec = importlib.util.spec_from_file_location("dashboard_iam_check", REPO / "scripts" / "dashboard_iam_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


IAP_ONLY = {"bindings": [{"role": "roles/run.invoker",
                          "members": ["serviceAccount:service-1@gcp-sa-iap.iam.gserviceaccount.com"]}]}


def test_iam_check_accepts_iap_only_and_flags_public(tmp_path):
    iam = _iam()
    assert iam.public_bindings(IAP_ONLY) == []
    pub = {"bindings": IAP_ONLY["bindings"] + [{"role": "roles/run.invoker", "members": ["allUsers"]},
                                               {"role": "roles/run.invoker", "members": ["allAuthenticatedUsers"]}]}
    assert len(iam.public_bindings(pub)) == 2
    assert iam.service_problems({"metadata": {"annotations": {"run.googleapis.com/invoker-iam-disabled": "true"}}})
    assert iam.service_problems({"metadata": {"annotations": {}}}) == []
    ok, bad, svc = tmp_path / "ok.json", tmp_path / "bad.json", tmp_path / "svc.json"
    ok.write_text(json.dumps(IAP_ONLY)); bad.write_text(json.dumps(pub)); svc.write_text("{}")
    assert iam.main([str(ok), str(svc)]) == 0
    assert iam.main([str(bad), str(svc)]) == 1
    empty = tmp_path / "empty.json"
    empty.write_text("")
    assert iam.main([str(empty)]) == 0                   # no bindings at all: nothing public


STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$GCLOUD_LOG"
case "$*" in
  "artifacts docker images describe"*) echo "sha256:$(printf 'a%.0s' {1..64})" ;;
  "run services describe"*"latestReadyRevisionName"*) echo "nfl-dfs-app-00099-old" ;;
  "run services describe"*"--format=json"*) echo '{"metadata":{"annotations":{}}}' ;;
  "secrets describe"*) [[ -n "${SECRETS_PRESENT:-}" ]] || exit 1 ;;
  "run services update"*) ;;
  "run services get-iam-policy"*) cat "$POLICY_FILE" ;;
  *) echo "unexpected gcloud $*" >&2; exit 9 ;;
esac
"""

DATE_STUB = r"""#!/usr/bin/env bash
if [[ "$*" == "-u +%s" ]]; then echo "$FAKE_NOW"; else exec /usr/bin/date "$@"; fi
"""


def run(tmp_path, *args, now="2026-10-05T00:00:00Z", force=None, policy=IAP_ONLY, secrets=False):
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "gcloud").write_text(STUB); (bin_ / "gcloud").chmod(0o755)
    (bin_ / "date").write_text(DATE_STUB); (bin_ / "date").chmod(0o755)
    pol = tmp_path / "policy.json"; pol.write_text(json.dumps(policy))
    log = tmp_path / "gcloud.log"
    if log.exists():
        log.unlink()
    fake_now = subprocess.run(["/usr/bin/date", "-u", "-d", now, "+%s"], capture_output=True, text=True).stdout.strip()
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "GCLOUD_LOG": str(log),
           "POLICY_FILE": str(pol), "FAKE_NOW": fake_now}
    env.pop("FORCE", None)
    if force:
        env["FORCE"] = force
    if secrets:
        env["SECRETS_PRESENT"] = "1"
    p = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)
    calls = log.read_text().splitlines() if log.exists() else []
    return p, calls


@pytest.mark.skipif(not Path("/usr/bin/date").exists(), reason="needs coreutils date")
def test_deploy_refuses_before_sunday_window_unless_forced(tmp_path):
    p, calls = run(tmp_path, "dashboard-abc1234", now="2026-10-04T20:29:00Z")
    assert p.returncode == 2 and "REFUSED" in p.stderr and calls == []
    p, calls = run(tmp_path, "dashboard-abc1234", now="2026-10-04T20:29:00Z", force="1")
    assert p.returncode == 0, p.stderr


@pytest.mark.skipif(not Path("/usr/bin/date").exists(), reason="needs coreutils date")
@pytest.mark.parametrize("ref", ["latest", "nfl-dfs:latest", "some-other-tag"])
def test_deploy_refuses_mutable_or_foreign_tags(tmp_path, ref):
    p, calls = run(tmp_path, ref)
    assert p.returncode == 2 and calls == []


@pytest.mark.skipif(not Path("/usr/bin/date").exists(), reason="needs coreutils date")
def test_deploy_updates_only_the_service_by_digest_and_keeps_iap(tmp_path):
    p, calls = run(tmp_path, "dashboard-abc1234", secrets=True)
    assert p.returncode == 0, p.stderr
    update = [c for c in calls if c.startswith("run services update")]
    assert len(update) == 1
    u = update[0]
    image = u.split("--image ", 1)[1].split()[0]
    assert "nfl-dfs-app" in u and "@sha256:" in image and not image.endswith(":latest")
    assert "--command nfl-dfs --args dashboard" in u and "CODE_SHA=abc1234" in u
    assert "MILLY_NEO4J_URI=milly-neo4j-uri:latest" in u
    assert not any("allow-unauthenticated" in c for c in calls)
    assert not any(c.startswith(("run jobs", "run deploy", "builds")) for c in calls)
    assert "update-traffic nfl-dfs-app" in p.stdout and "nfl-dfs-app-00099-old=100" in p.stdout


@pytest.mark.skipif(not Path("/usr/bin/date").exists(), reason="needs coreutils date")
def test_deploy_fails_loudly_with_rollback_when_public(tmp_path):
    public = {"bindings": [{"role": "roles/run.invoker", "members": ["allUsers"]}]}
    p, _ = run(tmp_path, "dashboard-abc1234", policy=public)
    assert p.returncode == 1
    assert "allUsers" in p.stderr and "update-traffic nfl-dfs-app" in p.stderr


def test_deploy_script_never_opens_the_service():
    text = SCRIPT.read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "--allow-unauthenticated" not in code and "add-iam-policy-binding" not in code


def test_cloudbuild_dashboard_contract():
    cfg = yaml.safe_load((REPO / "cloudbuild.dashboard.yaml").read_text())
    assert cfg["images"] == ["${_IMAGE}"]
    assert cfg["substitutions"]["_IMAGE"].endswith("nfl-dfs:dashboard-${_SHORT_SHA}")
    code = [ln for ln in (REPO / "cloudbuild.dashboard.yaml").read_text().splitlines()
            if not ln.lstrip().startswith("#")]
    assert not any(":latest" in ln for ln in code)
    tests = cfg["steps"][0]["args"][-1]
    assert "tests/test_dashboard_" in tests and "PYTHONPATH=src pytest tests/" in tests
    assert sorted(p.name for p in (REPO / "tests").glob("test_dashboard_*.py")) == sorted(
        set(__import__("re").findall(r"tests/(test_dashboard_\w+\.py)", tests)))
