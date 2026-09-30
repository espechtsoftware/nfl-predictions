"""Offline tests for the Week-5 cloud path of the TabPFN ownership fit: scripts/tabpfn_gen/own_cloud.py (the job's
`ownership` mode) and scripts/ownership_tabpfn_cloud.sh (the laptop-side launcher), with a fake GCS and a fake gcloud."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("own_cloud", ROOT / "scripts" / "tabpfn_gen" / "own_cloud.py")
OC = importlib.util.module_from_spec(spec); spec.loader.exec_module(OC)
B = "gs://nfl-predictions-503414-raw/private"
sha = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731


class FakeGcs:
    def __init__(self, objects: dict[str, bytes]):
        self.o = dict(objects); self.gen = 100

    def download(self, uri):
        OC.split_uri(uri)
        if uri not in self.o:
            OC.refuse(f"cannot read {uri}: HTTP 404")
        return self.o[uri], "7"

    def upload(self, uri, data, content_type):
        OC.split_uri(uri)
        if uri in self.o:
            OC.refuse(f"{uri} already exists (outputs are create-only; use a fresh run tag)")
        self.o[uri] = data; self.gen += 1
        return str(self.gen)


def fake_fit(argv):
    out = Path(argv[argv.index("--out") + 1])
    out.write_text("dk_player_id,pred_own,pred_rank\n1,30.5,1\n2,4.0,2\n")
    Path(str(out) + ".receipt.json").write_text(json.dumps({"secs": 15.0, "gpu": "NVIDIA L4", "predictions": {"sum": 34.5}}))
    return 0


def _objs(feats=b"FEATURES"):
    return {f"{B}/l23/rows.parquet": b"ROWS", f"{B}/l23/rows_2026_w1w3.parquet": b"R26", f"{B}/own-tabpfn/t1/features.parquet": feats}


def _argv(fsha, out=f"{B}/own-tabpfn/t1/ownership_tabpfn.csv"):
    return ["--rows", f"{B}/l23/rows.parquet", "--rows-2026", f"{B}/l23/rows_2026_w1w3.parquet",
            "--features", f"{B}/own-tabpfn/t1/features.parquet", "--features-sha256", fsha, "--out", out]


def test_shim_runs_the_fit_and_writes_csv_and_receipt_with_identities(tmp_path, capsys):
    g = FakeGcs(_objs())
    s = OC.run(_argv(sha(b"FEATURES")), gcs=g, fit=fake_fit, work=tmp_path)
    csv = g.o[f"{B}/own-tabpfn/t1/ownership_tabpfn.csv"]
    rec = json.loads(g.o[f"{B}/own-tabpfn/t1/ownership_tabpfn.csv.receipt.json"])
    assert s["csv"]["sha256"] == sha(csv) == rec["cloud"]["csv"]["sha256"]
    assert rec["cloud"]["inputs"]["features"]["sha256"] == sha(b"FEATURES")
    assert rec["cloud"]["inputs"]["rows_2026"]["sha256"] == sha(b"R26") and rec["cloud"]["mode"] == "ownership"
    assert "local" not in rec["cloud"]["inputs"]["rows"]
    assert capsys.readouterr().out.startswith(OC.OUTPUT_PREFIX)


def test_shim_refuses_other_feature_bytes_public_paths_and_reused_tags(tmp_path):
    with pytest.raises(SystemExit, match="content identity"):
        OC.run(_argv(sha(b"OTHER")), gcs=FakeGcs(_objs()), fit=fake_fit, work=tmp_path)
    with pytest.raises(SystemExit, match="is not under"):
        OC.run(_argv(sha(b"FEATURES"), out="gs://nfl-predictions-503414-raw/public/x.csv"), gcs=FakeGcs(_objs()), fit=fake_fit, work=tmp_path)
    used = _objs(); used[f"{B}/own-tabpfn/t1/ownership_tabpfn.csv"] = b"old"
    with pytest.raises(SystemExit, match="already exists"):
        OC.run(_argv(sha(b"FEATURES")), gcs=FakeGcs(used), fit=fake_fit, work=tmp_path)


def test_shim_refuses_a_failed_fit(tmp_path):
    with pytest.raises(SystemExit, match="returned 2"):
        OC.run(_argv(sha(b"FEATURES")), gcs=FakeGcs(_objs()), fit=lambda argv: 2, work=tmp_path)


FAKE_GCLOUD = r'''#!/usr/bin/env python3
import hashlib, json, os, sys
from pathlib import Path
D = Path(os.environ["FAKE_BUCKET_DIR"]); P = "gs://nfl-predictions-503414-raw/"
loc = lambda u: D / u[len(P):] if u.startswith(P) else Path(u)
a = sys.argv[1:]
with open(os.environ["FAKE_CALLS"], "a") as f: f.write(" ".join(a[:3]) + "\n")
if a[:2] == ["storage", "cp"]:
    src, dst = [x for x in a[2:] if not x.startswith("--")]
    if "--no-clobber" in a and loc(dst).exists(): sys.exit(0)
    loc(dst).parent.mkdir(parents=True, exist_ok=True); loc(dst).write_bytes(loc(src).read_bytes()); sys.exit(0)
if a[:2] == ["storage", "cat"]:
    sys.stdout.buffer.write(loc(a[2]).read_bytes()); sys.exit(0)
if a[:3] == ["run", "jobs", "execute"]:
    rc = int(os.environ.get("FAKE_EXEC_RC", "0"))
    if rc: sys.exit(rc)
    args = [x for x in a if x.startswith("--args=")][0][len("--args="):].split(",")
    g = lambda k: args[args.index(k) + 1]
    feats = loc(g("--features")).read_bytes(); out = loc(g("--out"))
    csv = b"dk_player_id,pred_own,pred_rank\n1,30.5,1\n"
    out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(csv)
    h = lambda b: hashlib.sha256(b).hexdigest()
    img = os.environ.get("FAKE_IMAGE_SHA") or h(Path(os.environ["LOCAL_OT"]).read_bytes())
    rec = {"secs": 14.9, "gpu": "NVIDIA L4", "predictions": {"sum": 30.5}, "cloud": {"execution": "tabpfn-gen-x1",
           "image_ownership_tabpfn_sha256": img, "inputs": {"features": {"sha256": h(feats)}}, "csv": {"sha256": h(csv)}}}
    Path(str(out) + ".receipt.json").write_text(json.dumps(rec)); print("tabpfn-gen-x1"); sys.exit(0)
sys.exit(9)
'''


def _launch(tmp_path, tag="w5-1050", **env):
    gc = tmp_path / "gcloud"; gc.write_text(FAKE_GCLOUD); gc.chmod(0o755)
    (tmp_path / "bucket").mkdir(exist_ok=True)
    feats = tmp_path / "feats.parquet"; feats.write_bytes(b"FEATURES")
    e = dict(os.environ, GCLOUD=str(gc), FAKE_BUCKET_DIR=str(tmp_path / "bucket"), FAKE_CALLS=str(tmp_path / "calls"),
             LOCAL_OT=str(ROOT / "scripts" / "ownership_tabpfn.py"), **env)
    out = tmp_path / "o" / "ownership_tabpfn.csv"
    r = subprocess.run(["bash", str(ROOT / "scripts" / "ownership_tabpfn_cloud.sh"), str(feats), str(out), tag],
                       env=e, capture_output=True, text=True)
    return r, out, (tmp_path / "calls").read_text().splitlines() if (tmp_path / "calls").exists() else []


def test_launcher_happy_path_writes_the_csv_and_receipt(tmp_path):
    r, out, calls = _launch(tmp_path)
    assert r.returncode == 0, r.stderr
    assert out.read_text().startswith("dk_player_id,pred_own") and Path(str(out) + ".receipt.json").exists()
    assert "cloud ownership fit ok: execution tabpfn-gen-x1" in r.stdout
    assert sum(c.startswith("run jobs execute") for c in calls) == 1


def test_launcher_refuses_an_image_code_skew_unless_consciously_overridden(tmp_path):
    r, out, _ = _launch(tmp_path, FAKE_IMAGE_SHA="ab" * 32)
    assert r.returncode == 2 and "differs from this checkout" in r.stderr and not out.exists()
    r, out, _ = _launch(tmp_path / "again", FAKE_IMAGE_SHA="ab" * 32, OWN_TABPFN_IMAGE_SKEW_OK="ab" * 32) if (tmp_path / "again").mkdir() is None else None
    assert r.returncode == 0, r.stderr


def test_launcher_never_retries_a_failed_execution(tmp_path):
    r, out, calls = _launch(tmp_path, FAKE_EXEC_RC="1")
    assert r.returncode == 2 and "not retried" in r.stderr and not out.exists()
    assert sum(c.startswith("run jobs execute") for c in calls) == 1


def test_launcher_refuses_a_bad_tag(tmp_path):
    r, _, calls = _launch(tmp_path, tag="bad tag/..")
    assert r.returncode == 2 and "run tag" in r.stderr and calls == []


def test_launcher_refuses_a_stale_tag_holding_other_feature_bytes(tmp_path):
    stale = tmp_path / "bucket" / "private" / "own-tabpfn" / "w5-1050" / "features.parquet"
    stale.parent.mkdir(parents=True); stale.write_bytes(b"LAST WEEK")        # --no-clobber keeps the old object
    r, out, calls = _launch(tmp_path)
    assert r.returncode == 2 and "a stale run tag" in r.stderr and not out.exists()
    assert not any(c.startswith("run jobs execute") for c in calls)
