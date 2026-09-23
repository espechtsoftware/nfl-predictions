"""One-command check of a project-slate run's availability proof lines (Week 3 on). Read-only.

Pulls the log lines of ONE project-slate execution (the newest by default) and checks:
  * market blend source is props (the money path is props-or-nothing);
  * `questionable haircut: x0.800 on N` (the deployed Q_HAIRCUT);
  * `backup-QB gate: zeroed N` with N in a sanity range (Week 2 had ~49 gated QBs);
  * `cascade: adjusted slate for N inactive(s): ids` present;
  * every `carries already priced ... carry side skipped` id is one of the cascade's ids (CASCADE_SKIP_PRICED_CARRIES);
  * the execution's image digest equals --digest (default: the deployed eadae06a...).
With --expected <file holding the dry-run tool's output>, the gate / haircut / cascade counts must match it exactly.

  python week3_proof_lines.py [--execution NAME] [--freshness 2d] [--expected dryrun.txt] [--digest sha256:...]
Exit 0 = every check passed; 1 = a check failed; 2 = no project-slate execution with proof lines found.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

PROJECT, REGION, JOB = "nfl-predictions-503414", "us-central1", "project-slate"
DEPLOYED = "sha256:eadae06aa94e79a065af3c23370f9fc8618341da6c611f55b5224f83e11d5634"
PAT = {
    "market": re.compile(r"market blend source: (\S+) \((\d+)/(\d+) rows\)"),
    "gate": re.compile(r"backup-QB gate: zeroed (\d+) QB"),
    "haircut": re.compile(r"questionable haircut: x([0-9.]+) on (\d+) Questionable"),
    "cascade": re.compile(r"cascade: adjusted slate for (\d+) inactive\(s\): (.*)$"),
    "skip": re.compile(r"cascade: (\S+) carries already priced by team_vacated_carry_share; carry side skipped"),
}


def gcloud(args: list[str]) -> str:
    return subprocess.run(["gcloud", *args, "--project", PROJECT], capture_output=True, text=True, check=True).stdout


def lines_for(execution: str | None, freshness: str) -> tuple[str, list[str]]:
    flt = (f'resource.type="cloud_run_job" AND resource.labels.job_name="{JOB}" AND ('
           + " OR ".join(f'textPayload:"{s}"' for s in ("market blend source", "backup-QB gate", "questionable haircut",
                                                        "cascade: adjusted", "carry side skipped")) + ")")
    if execution:
        flt += f' AND labels."run.googleapis.com/execution_name"="{execution}"'
    rows = json.loads(gcloud(["logging", "read", flt, "--freshness", freshness, "--limit", "2000", "--format", "json"]) or "[]")
    if not rows:
        return "", []
    newest = execution or max(rows, key=lambda r: r["timestamp"])["labels"]["run.googleapis.com/execution_name"]
    mine = sorted((r for r in rows if r["labels"].get("run.googleapis.com/execution_name") == newest), key=lambda r: r["timestamp"])
    return newest, [r.get("textPayload", "") for r in mine]


def parse(lines: list[str]) -> dict:
    out = {"skips": []}
    for ln in lines:
        for k, p in PAT.items():
            m = p.search(ln)
            if not m:
                continue
            if k == "skip":
                out["skips"].append(m.group(1))
            elif k == "cascade":
                out["cascade"] = (int(m.group(1)), [s.strip() for s in m.group(2).split(",") if s.strip()])
            else:
                out[k] = m.groups()
    return out


def expected_from(path: str) -> dict:
    txt = open(path).read()
    e = {}
    for k, p in (("gate", PAT["gate"]), ("haircut", PAT["haircut"]), ("cascade", PAT["cascade"])):
        m = p.search(txt)
        if m:
            e[k] = m.groups()
    return e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execution"); ap.add_argument("--freshness", default="2d"); ap.add_argument("--expected")
    ap.add_argument("--digest", default=DEPLOYED); ap.add_argument("--gate-range", default="10,90")
    a = ap.parse_args()
    ex, lines = lines_for(a.execution, a.freshness)
    if not ex:
        print("no project-slate execution with proof lines in the window"); return 2
    got = parse(lines); fails = []
    img = json.loads(gcloud(["run", "jobs", "executions", "describe", ex, "--region", REGION, "--format", "json"]))
    image = img["spec"]["template"]["spec"]["containers"][0]["image"]
    print(f"execution {ex}  image ...{image[-20:]}")
    if not image.endswith(a.digest):
        fails.append(f"image {image} is not {a.digest}")
    m = got.get("market")
    print(f"  market blend source: {m}")
    if not m or m[0] != "props":
        fails.append("market blend source is not props")
    h = got.get("haircut")
    print(f"  questionable haircut: {h}")
    if not h or abs(float(h[0]) - 0.8) > 1e-9:
        fails.append("Q_HAIRCUT x0.800 line missing or wrong")
    g = got.get("gate"); lo, hi = (int(v) for v in a.gate_range.split(","))
    print(f"  backup-QB gate zeroed: {g}")
    if not g or not (lo <= int(g[0]) <= hi):
        fails.append(f"backup-QB gate count {g} outside {lo}-{hi}")
    c = got.get("cascade")
    print(f"  cascade adjusted: {c[0] if c else None} ids; carry-side skips: {len(got['skips'])}")
    if not c:
        fails.append("cascade line missing")
    elif not set(got["skips"]) <= set(c[1]):
        fails.append(f"carry-skip ids not in the cascade set: {sorted(set(got['skips']) - set(c[1]))}")
    if a.expected:
        e = expected_from(a.expected)
        for k, want in e.items():
            have = got.get(k)
            have_n = have[0] if k != "haircut" else have[1] if have else None
            want_n = want[0] if k != "haircut" else want[1]
            if k == "cascade":
                have_n = str(c[0]) if c else None
            print(f"  expected {k}: {want_n}  observed: {have_n}")
            if str(have_n) != str(want_n):
                fails.append(f"{k}: observed {have_n} != dry-run expectation {want_n}")
    for f in fails:
        print("FAIL:", f)
    print("PASS" if not fails else "FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
