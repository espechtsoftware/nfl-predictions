"""The `ownership` mode of the tabpfn-gen job (Week 5; operator routing 2026-09-29/30): runs `ownership_tabpfn.py fit`
on inputs in the PRIVATE bucket and writes its pred_own csv + receipt back there. Invoked per execution by overriding
the container args (the image has no ENTRYPOINT; its default CMD stays `python /app/gen.py`, so the weekly projection
refresh is unchanged):

  gcloud run jobs execute tabpfn-gen --region us-central1 --wait --update-env-vars TABPFN_DISABLE_TELEMETRY=1 \
    --args=python,/app/own_cloud.py,--rows,gs://B/private/l23/rows.parquet,--rows-2026,gs://B/private/l23/rows_2026_w1w3.parquet,\
--features,gs://B/private/own-tabpfn/TAG/features.parquet,--features-sha256,SHA,--out,gs://B/private/own-tabpfn/TAG/ownership_tabpfn.csv

Content identity (CLAUDE.md rule 2): the caller passes the sha256 of the features it uploaded and the shim refuses any
other bytes; the receipt carries the input shas, the object generations written, and the sha256 of the
ownership_tabpfn.py baked into this image, so the caller can refuse a code skew. No new packages: GCS through the
JSON API with google-auth + requests (both already in the image). Every refusal exits nonzero and prints
"OWNERSHIP TABPFN REFUSED: ..." (the caller then keeps the blend, loudly).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
from pathlib import Path

os.environ.setdefault("TABPFN_DISABLE_TELEMETRY", "1")
PRIVATE_PREFIX = "gs://nfl-predictions-503414-raw/private/"
OUTPUT_PREFIX = "OWN_TABPFN_JSON="
HERE = Path(__file__).resolve().parent
OT_PATH = HERE / "ownership_tabpfn.py"


def refuse(why: str):
    raise SystemExit(f"OWNERSHIP TABPFN REFUSED: {why}")


def split_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith(PRIVATE_PREFIX):
        refuse(f"{uri} is not under {PRIVATE_PREFIX} (inputs and outputs carry third-party values)")
    bucket, _, name = uri[len("gs://"):].partition("/")
    if not name or name.endswith("/"):
        refuse(f"{uri} is not an object path")
    return bucket, name


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Gcs:
    """Minimal GCS JSON-API client (download, upload with a create-only precondition)."""

    def __init__(self, session=None):
        if session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
            session = AuthorizedSession(creds)
        self.s = session

    def download(self, uri: str) -> tuple[bytes, str]:
        bucket, name = split_uri(uri)
        q = urllib.parse.quote(name, safe="")
        meta = self.s.get(f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{q}", timeout=60)
        if meta.status_code != 200:
            refuse(f"cannot read {uri}: HTTP {meta.status_code}")
        gen = str(meta.json()["generation"])
        r = self.s.get(f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{q}",
                       params={"alt": "media", "generation": gen}, timeout=300)
        if r.status_code != 200:
            refuse(f"cannot download {uri}#{gen}: HTTP {r.status_code}")
        return r.content, gen

    def upload(self, uri: str, data: bytes, content_type: str) -> str:
        bucket, name = split_uri(uri)
        r = self.s.post(f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o",
                        params={"uploadType": "media", "name": name, "ifGenerationMatch": "0"},
                        data=data, headers={"Content-Type": content_type}, timeout=300)
        if r.status_code == 412:
            refuse(f"{uri} already exists (outputs are create-only; use a fresh run tag)")
        if r.status_code != 200:
            refuse(f"cannot upload {uri}: HTTP {r.status_code}")
        return str(r.json()["generation"])


def run(argv: list[str] | None = None, gcs: Gcs | None = None, fit=None, work: Path = Path("/tmp/own-tabpfn")) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True); ap.add_argument("--rows-2026")
    ap.add_argument("--features", required=True); ap.add_argument("--features-sha256", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    split_uri(a.out)
    if not a.out.endswith(".csv"):
        refuse(f"--out {a.out} must name the .csv the union reads")
    gcs = gcs or Gcs()
    work.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for key, uri in (("rows", a.rows), ("rows_2026", a.rows_2026), ("features", a.features)):
        if not uri:
            continue
        data, gen = gcs.download(uri)
        local = work / f"{key}.parquet"
        local.write_bytes(data)
        inputs[key] = {"uri": uri, "generation": gen, "sha256": sha256_bytes(data), "bytes": len(data), "local": local}
    if inputs["features"]["sha256"] != a.features_sha256:
        refuse(f"the features object's sha256 {inputs['features']['sha256'][:12]}… is not the caller's "
               f"{a.features_sha256[:12]}… (content identity)")
    out_local = work / "ownership_tabpfn.csv"
    argv_fit = ["fit", "--rows", str(inputs["rows"]["local"]), "--features", str(inputs["features"]["local"]),
                "--out", str(out_local)]
    if "rows_2026" in inputs:
        argv_fit += ["--rows-2026", str(inputs["rows_2026"]["local"])]
    if fit is None:
        sys.path.insert(0, str(HERE))
        import ownership_tabpfn as ot
        fit = ot.main
    rc = fit(argv_fit)
    if rc not in (0, None):
        refuse(f"ownership_tabpfn.py fit returned {rc}")
    csv_bytes = out_local.read_bytes()
    receipt = json.loads(Path(str(out_local) + ".receipt.json").read_text())
    receipt["cloud"] = {
        "job": "tabpfn-gen", "mode": "ownership", "execution": os.environ.get("CLOUD_RUN_EXECUTION", ""),
        "image_ownership_tabpfn_sha256": sha256_bytes(OT_PATH.read_bytes()) if OT_PATH.exists() else None,
        "inputs": {k: {kk: vv for kk, vv in v.items() if kk != "local"} for k, v in inputs.items()},
        "csv": {"uri": a.out, "sha256": sha256_bytes(csv_bytes), "bytes": len(csv_bytes)}}
    receipt["cloud"]["csv"]["generation"] = gcs.upload(a.out, csv_bytes, "text/csv")
    rec_bytes = json.dumps(receipt, indent=1, default=str).encode()
    rec_gen = gcs.upload(a.out + ".receipt.json", rec_bytes, "application/json")
    summary = {"csv": receipt["cloud"]["csv"], "receipt": {"uri": a.out + ".receipt.json", "generation": rec_gen,
               "sha256": sha256_bytes(rec_bytes)}, "image_ownership_tabpfn_sha256": receipt["cloud"]["image_ownership_tabpfn_sha256"],
               "predictions": receipt.get("predictions"), "secs": receipt.get("secs"), "gpu": receipt.get("gpu")}
    print(OUTPUT_PREFIX + json.dumps(summary, sort_keys=True, default=str), flush=True)
    return summary


if __name__ == "__main__":
    run()
