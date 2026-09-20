#!/usr/bin/env python3
"""Frozen realized-outcome reader for the Week-3 selection-only shadow (production-owned).

Reads books.json + manifest.json from week3_shadow_runner.py and ONE outcomes file (CSV with columns `id`,
`actual_points` keyed by the run frame's player id; DST rows use the frame's DST id). The reader first verifies every
run-artifact hash recorded by the shadow manifest. A realized outcomes file must contain exactly one finite row for
each frame player id (including DST), with no duplicates or extras. For every arm: realized score
per ordered row, realized max and its row position, counts of rows clearing 200/210/220/230/240 (194 secondary),
prefix blocks (max per contest block), the global winner-score proxy (nfl2.selectors.winner_utility on the realized
max, the smoothed CDF of the 2023-2025 Millionaire winning scores), pool oracle (best realized candidate in the whole
run pool) and regret, and paired deltas versus control. Fails closed on any roster id absent from the outcomes file.

Rehearsal mode (`--synthetic-world W`) draws the outcome vector from column W of the incumbent bank so the reader can
be exercised before real outcomes exist; it writes a REHEARSAL marker and never reads a score table.

  LAB_PY scripts/week3_shadow_reader.py --shadow SHADOW_DIR --run RUN_DIR --clone LAB_CLONE --out OUT_DIR
                                        (--outcomes outcomes.csv | --synthetic-world W)
"""
import argparse, hashlib, json, pathlib, sys, time
import numpy as np, pandas as pd

LINES = [194, 200, 210, 220, 230, 240]
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
ap = argparse.ArgumentParser()
ap.add_argument("--shadow", required=True); ap.add_argument("--run", required=True); ap.add_argument("--clone", required=True); ap.add_argument("--out", required=True)
g = ap.add_mutually_exclusive_group(required=True); g.add_argument("--outcomes"); g.add_argument("--synthetic-world", type=int)
a = ap.parse_args()
sd, run, out = pathlib.Path(a.shadow), pathlib.Path(a.run), pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)


def fail_reader(message):
    (out / "READER-FAILED").write_text(f"{message}\n")
    print(f"READER FAILED: {message}", file=sys.stderr)
    sys.exit(3)


try:
    books = json.loads((sd / "books.json").read_text())
    manifest = json.loads((sd / "manifest.json").read_text())
except (OSError, json.JSONDecodeError) as e:
    fail_reader(f"invalid shadow metadata: {e}")

# The shadow manifest binds every run artifact used by the runner.  Refuse to
# score a book against a changed, incomplete, or substituted run directory.
input_hashes = manifest.get("inputs_sha256")
if not isinstance(input_hashes, dict) or not input_hashes:
    fail_reader("shadow manifest has no input hashes")
for name, expected in input_hashes.items():
    p = run / str(name)
    if not p.is_file():
        fail_reader(f"manifest input is missing: {p}")
    actual = sha(p)
    if str(expected).lower() != actual.lower():
        fail_reader(f"manifest input hash mismatch for {name}: expected {expected}, found {actual}")

try:
    fr = pd.read_parquet(run / "frame.parquet", columns=["id", "name", "pos"])
except Exception as e:
    fail_reader(f"cannot read frame.parquet: {e}")
if fr["id"].isna().any():
    fail_reader("frame.parquet contains null player ids")
ids = fr.id.astype(str).tolist()
if len(set(ids)) != len(ids):
    fail_reader("frame.parquet contains duplicate player ids")
if a.outcomes:
    try:
        oc = pd.read_csv(a.outcomes, dtype={"id": str})
    except Exception as e:
        fail_reader(f"cannot read outcomes file: {e}")
    if not {"id", "actual_points"}.issubset(oc.columns):
        fail_reader("outcomes file must contain id and actual_points columns")
    raw_ids = oc["id"]
    normalized_ids = raw_ids.astype(str).str.strip()
    if raw_ids.isna().any() or (normalized_ids == "").any() or normalized_ids.str.lower().eq("nan").any():
        fail_reader("outcomes file contains null or empty player ids")
    if normalized_ids.duplicated().any():
        dupes = normalized_ids[normalized_ids.duplicated(keep=False)].unique().tolist()
        fail_reader(f"outcomes file contains duplicate player ids: {dupes[:20]}")
    points = pd.to_numeric(oc["actual_points"], errors="coerce")
    if points.isna().any() or not np.isfinite(points.to_numpy(dtype=float)).all():
        fail_reader("outcomes file contains missing or non-finite actual_points")
    actual = dict(zip(normalized_ids, points.astype(float)))
    expected_ids, actual_ids = set(ids), set(actual)
    missing_ids = sorted(expected_ids - actual_ids)
    extra_ids = sorted(actual_ids - expected_ids)
    if missing_ids or extra_ids:
        fail_reader(f"outcomes ids must exactly match frame ids; missing={missing_ids[:20]} extra={extra_ids[:20]}")
    source = {"kind": "outcomes_file", "path": a.outcomes, "sha256": sha(a.outcomes), "rows": int(len(oc))}
else:
    bank = np.load(run / "incumbent_player_scores.npy", mmap_mode="r"); w = int(a.synthetic_world)
    if w < 0 or w >= bank.shape[1]:
        fail_reader(f"synthetic world {w} is outside incumbent bank columns [0, {bank.shape[1]})")
    actual = {pid: float(bank[i, w]) for i, pid in enumerate(ids)}; source = {"kind": "SYNTHETIC incumbent-bank world", "world": w}
try:
    cands = pd.read_parquet(run / "candidates.parquet", columns=["players"])
except Exception as e:
    fail_reader(f"cannot read candidates.parquet: {e}")
missing = sorted({p for ps in cands.players.astype(str) for p in ps.split(",") if p not in actual or pd.isna(actual[p])})
if missing:
    fail_reader(f"{len(missing)} roster ids absent from outcomes: {missing[:20]}")
pool_scores = np.array([sum(actual[p] for p in ps.split(",")) for ps in cands.players.astype(str)])
oracle = float(pool_scores.max()); oracle_ix = int(pool_scores.argmax())
sys.path.insert(0, str(pathlib.Path(a.clone) / "src"))
try:
    from nfl2.selectors import winner_utility
    def proxy(x):
        v = np.asarray(winner_utility(np.array([x], dtype=float))); return float(v.ravel()[0])
except Exception as e:  # the proxy is secondary; record its absence
    proxy = lambda x: None; proxy_err = str(e)[:120]
else:
    proxy_err = None

def read(arm):
    order = arm["order"]
    if not arm["feasible"] or not order: return {"feasible": False, "note": arm.get("note")}
    rows = [float(sum(actual[p] for p in ps)) for ps in arm["candidate_ids"]]
    r = np.array(rows); mx = float(r.max()); pos = int(r.argmax()) + 1
    pref = {}
    for b in books["blocks"]:
        seg = r[b["rows"][0] - 1: b["rows"][1]]
        if len(seg): pref[b["name"]] = {"rows": b["rows"], "max": float(seg.max()), "clears_200": int((seg >= 200).sum())}
    return {"feasible": True, "rows": len(rows), "realized_max": mx, "max_row_position": pos, "mean_row": float(r.mean()),
            "clears": {str(L): int((r >= L).sum()) for L in LINES}, "winner_score_proxy_of_max": proxy(mx),
            "pool_oracle": oracle, "regret": oracle - mx, "oracle_in_book": oracle_ix in set(order), "prefix_blocks": pref, "realized_rows": rows}

res = {k: read(v) for k, v in books["arms"].items()}
ctrl = res.get("control", {})
for k, v in res.items():
    if v.get("feasible") and ctrl.get("feasible") and k != "control":
        v["vs_control"] = {"max_delta": v["realized_max"] - ctrl["realized_max"], "regret_delta": v["regret"] - ctrl["regret"],
                           "clears_delta": {L: v["clears"][L] - ctrl["clears"][L] for L in v["clears"]}}
report = {"schema": "week3-shadow-reader/v1", "read_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "label": "REHEARSAL" if a.synthetic_world is not None else manifest.get("label"),
          "shadow_manifest_sha256": sha(sd / "manifest.json"), "books_sha256": sha(sd / "books.json"), "outcomes": source, "pool_size": int(len(cands)),
          "pool_oracle": oracle, "winner_proxy_error": proxy_err, "arms": res, "reader_sha256": sha(__file__)}
(out / "realized.json").write_text(json.dumps(report, indent=2) + "\n")
if a.synthetic_world is not None: (out / "REHEARSAL").write_text("synthetic outcomes drawn from a simulated world; not a realized result\n")
lines = ["| arm | feasible | realized max (row) | 194 | 200 | 210 | 220 | 230 | 240 | oracle | regret | vs control max |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for k, v in res.items():
    if not v.get("feasible"): lines.append(f"| {k} | no | | | | | | | | | | |"); continue
    c = v["clears"]; d = v.get("vs_control", {}).get("max_delta")
    lines.append(f"| {k} | yes | {v['realized_max']:.2f} ({v['max_row_position']}) | {c['194']} | {c['200']} | {c['210']} | {c['220']} | {c['230']} | {c['240']} | {v['pool_oracle']:.2f} | {v['regret']:.2f} | {'' if d is None else f'{d:+.2f}'} |")
(out / "realized.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))
