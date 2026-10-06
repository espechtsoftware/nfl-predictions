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


def service(iap="true", latest="nfl-dfs-app-00100-new", traffic=None, **ann):
    a = {"run.googleapis.com/iap-enabled": iap} if iap is not None else {}
    a.update(ann)
    return {"metadata": {"annotations": a},
            "status": {"latestReadyRevisionName": latest,
                       "traffic": traffic if traffic is not None else [{"percent": 100, "latestRevision": True,
                                                                        "revisionName": latest}]}}


def test_iam_check_accepts_iap_only_and_flags_public(tmp_path):
    iam = _iam()
    assert iam.public_bindings(IAP_ONLY) == []
    pub = {"bindings": IAP_ONLY["bindings"] + [{"role": "roles/run.invoker", "members": ["allUsers"]},
                                               {"role": "roles/run.invoker", "members": ["allAuthenticatedUsers"]}]}
    assert len(iam.public_bindings(pub)) == 2
    assert iam.service_problems(service(**{"run.googleapis.com/invoker-iam-disabled": "true"}))
    assert iam.service_problems(service()) == []
    ok, bad, svc = tmp_path / "ok.json", tmp_path / "bad.json", tmp_path / "svc.json"
    ok.write_text(json.dumps(IAP_ONLY)); bad.write_text(json.dumps(pub)); svc.write_text(json.dumps(service()))
    assert iam.main(["--service", str(svc), "--policy", str(ok)]) == 0
    assert iam.main(["--service", str(svc), "--policy", str(bad)]) == 1


@pytest.mark.parametrize("iap", [None, "false", "TRUE-ish"])
def test_iam_check_requires_the_iap_annotation(tmp_path, iap):
    iam = _iam()
    assert iam.service_problems(service(iap=iap))
    svc = tmp_path / "svc.json"
    svc.write_text(json.dumps(service(iap=iap)))
    assert iam.main(["--service", str(svc)]) == 1


def test_iam_check_traffic_must_be_100_on_latest(tmp_path, capsys):
    iam = _iam()
    assert iam.traffic_problems(service()) == []
    named = service(traffic=[{"percent": 100, "revisionName": "nfl-dfs-app-00100-new"}])
    assert iam.traffic_problems(named) == []
    pinned = service(traffic=[{"percent": 100, "revisionName": "nfl-dfs-app-00099-old"}])
    assert iam.traffic_problems(pinned)
    split = service(traffic=[{"percent": 50, "latestRevision": True},
                             {"percent": 50, "revisionName": "nfl-dfs-app-00099-old"}])
    assert iam.traffic_problems(split)
    assert iam.traffic_problems({"status": {}})
    svc = tmp_path / "svc.json"
    svc.write_text(json.dumps(pinned))
    assert iam.main(["--service", str(svc), "--traffic"]) == 1
    out = capsys.readouterr()
    assert "00099-old" in out.out and "not 100%" in out.err


STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$GCLOUD_LOG"
case "$*" in
  "artifacts docker images describe"*) echo "sha256:$(printf 'a%.0s' {1..64})" ;;
  "run services describe"*"latestReadyRevisionName"*) echo "nfl-dfs-app-00099-old" ;;
  "run services describe"*"--format=json"*)
     if [[ -f "$GCLOUD_LOG.updated" ]]; then cat "$AFTER_FILE"; else cat "$BEFORE_FILE"; fi ;;
  "secrets describe"*) [[ -n "${SECRETS_PRESENT:-}" ]] || exit 1 ;;
  "run services update-traffic"*) ;;
  "run services update"*) touch "$GCLOUD_LOG.updated" ;;
  "run services get-iam-policy"*) cat "$POLICY_FILE" ;;
  *) echo "unexpected gcloud $*" >&2; exit 9 ;;
esac
"""

DATE_STUB = r"""#!/usr/bin/env bash
if [[ "$*" == "-u +%s" ]]; then echo "$FAKE_NOW"; else exec /usr/bin/date "$@"; fi
"""


def run(tmp_path, *args, now="2026-10-05T00:00:00Z", force=None, policy=IAP_ONLY, secrets=False,
        before=None, after=None):
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "gcloud").write_text(STUB); (bin_ / "gcloud").chmod(0o755)
    (bin_ / "date").write_text(DATE_STUB); (bin_ / "date").chmod(0o755)
    pol = tmp_path / "policy.json"; pol.write_text(json.dumps(policy))
    log = tmp_path / "gcloud.log"
    for f in (log, tmp_path / "gcloud.log.updated"):
        if f.exists():
            f.unlink()
    (tmp_path / "before.json").write_text(json.dumps(before or service(latest="nfl-dfs-app-00099-old")))
    (tmp_path / "after.json").write_text(json.dumps(after or service()))
    fake_now = subprocess.run(["/usr/bin/date", "-u", "-d", now, "+%s"], capture_output=True, text=True).stdout.strip()
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "GCLOUD_LOG": str(log),
           "POLICY_FILE": str(pol), "FAKE_NOW": fake_now, "BEFORE_FILE": str(tmp_path / "before.json"),
           "AFTER_FILE": str(tmp_path / "after.json")}
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
@pytest.mark.parametrize("now,refused", [
    ("2026-10-10T04:59:00Z", False),  # Fri 23:59 CDT
    ("2026-10-10T05:00:00Z", True),   # Sat 00:00 CDT
    ("2026-10-10T18:00:00Z", True),   # Sat 13:00 CDT
    ("2026-10-11T20:29:00Z", True),   # Sun 15:29 CDT
    ("2026-10-11T20:30:00Z", False),  # Sun 15:30 CDT: window closed
    ("2026-10-12T14:00:00Z", False),  # Mon
    ("2026-11-07T05:59:00Z", False),  # Fri 23:59 CST (after the DST change)
    ("2026-11-07T06:00:00Z", True),   # Sat 00:00 CST
    ("2026-11-08T21:29:00Z", True),   # Sun 15:29 CST
    ("2026-11-08T21:30:00Z", False),  # Sun 15:30 CST
])
def test_deploy_refuses_every_weekend_money_window(tmp_path, now, refused):
    p, calls = run(tmp_path, "dashboard-abc1234", now=now)
    if refused:
        assert p.returncode == 2 and "weekend money window" in p.stderr and calls == []
    else:
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
    update = [c for c in calls if c.startswith("run services update ")]
    assert len(update) == 1
    to_latest = [i for i, c in enumerate(calls) if c.startswith("run services update-traffic")]
    assert len(to_latest) == 1 and "--to-latest" in calls[to_latest[0]]
    assert calls.index(update[0]) < to_latest[0]
    assert "traffic [('nfl-dfs-app-00100-new', 100, True)]" in p.stdout
    u = update[0]
    image = u.split("--image ", 1)[1].split()[0]
    assert "nfl-dfs-app" in u and "@sha256:" in image and not image.endswith(":latest")
    assert "--command nfl-dfs --args dashboard" in u and "CODE_SHA=abc1234" in u
    assert "MILLY_NEO4J" not in u and "--update-secrets" not in u      # graph is local only (10-04)
    assert not any(c.startswith("secrets") for c in calls)
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


@pytest.mark.skipif(not Path("/usr/bin/date").exists(), reason="needs coreutils date")
def test_deploy_refuses_when_iap_is_off_before_the_update(tmp_path):
    p, calls = run(tmp_path, "dashboard-abc1234", before=service(iap=None, latest="nfl-dfs-app-00099-old"))
    assert p.returncode == 2 and "not IAP-protected" in p.stderr
    assert not any(c.startswith("run services update") for c in calls)


@pytest.mark.skipif(not Path("/usr/bin/date").exists(), reason="needs coreutils date")
def test_deploy_fails_when_traffic_stays_pinned(tmp_path):
    pinned = service(traffic=[{"percent": 100, "revisionName": "nfl-dfs-app-00099-old"}])
    p, _ = run(tmp_path, "dashboard-abc1234", after=pinned)
    assert p.returncode == 1 and "not 100%" in p.stderr and "update-traffic nfl-dfs-app" in p.stderr
