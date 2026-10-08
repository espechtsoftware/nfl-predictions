#!/usr/bin/env python3
"""Study 64 (S1): the weekly FP vs FP + ITT line (and the wind increment, FP + ENV vs FP + ITT) beside the frozen accuracy
reader (reports/2026-10-08-prereg-study64-env-calibration.md §4).

It reads scripts/weekly_projection_accuracy.py's OWN private player rows for the week (the same population and actuals:
~/private/projection-accuracy/accuracy-<season>-w<NN>.csv) and the frozen adjustment (scripts/s64_env_apply.py on the
week's T-70 frame and the union's proj_source.csv). THE IDENTITY GATE: on the joined ids, apply's fp must equal the
reader's fp (|diff| <= 1e-6), or it refuses -- the adjustment is added to the very numbers the reader scored. A reader
row outside apply's population gets adjustment 0 (counted).

Both comparisons use the READER'S OWN metrics and game-cluster bootstrap (B 2000, seed 1; imported, sha-pinned): the
challenger sits in the reader's "ours" slot and the incumbent in its "fp" slot, so its pair ours_vs_fp is the
improvement MAE(incumbent) - MAE(challenger).
    PRIMARY    FP + ITT vs FP. THE POOLED CHECK is the reader's own rule: "FP + ITT beats FP" when the pooled MAE is lower
               AND >= 95% of the pooled resamples are better; it makes the adjustment trial-eligible from W8 with at
               least 4 weeks (his decision); before that, and single weeks, are descriptive.
    WIND       FP + ENV vs FP + ITT: LOW CONFIDENCE (fitted on measured wind, applied to a forecast); reported, never a rule.
Writes PRIVATE rows (FP's numbers are licensed); prints MAE, bias, Spearman and the bootstrap only.

    python scripts/s64_env_line.py week --week 5 --rows <accuracy-2026-w05.csv> --frame <T-70 frame.parquet> \
        --proj-source <union proj_source.csv> --coeffs reports/2026-10-09-s64-env/s64_env_coefficients_v2.json \
        --out-dir ~/private/s64-env
    python scripts/s64_env_line.py pool --out-dir ~/private/s64-env
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
READER_SHA256 = "dadc647dd3bdeffade8526774f2b9849027962fe91df00f7e47268b866c0890d"           # scripts/weekly_projection_accuracy.py, the frozen accuracy reader
TRIAL_FROM_WEEK, MIN_WEEKS, SHARE, FP_TOL = 8, 4, 0.95, 1e-6
FIRST_WEEK = 5                                   # W5's main slate is the first prospective week; earlier rows are smokes


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def reader():
    got = hashlib.sha256((HERE / "weekly_projection_accuracy.py").read_bytes()).hexdigest()
    if got != READER_SHA256:
        raise SystemExit(f"S64 LINE REFUSED: weekly_projection_accuracy.py is {got[:12]}, not the pinned {READER_SHA256[:12]}")
    return _load("weekly_projection_accuracy")


def week_rows(rows: pd.DataFrame, env: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The reader's rows + itt_adj / env_adj by id (a row outside apply's population gets 0, counted), after THE IDENTITY
    GATE; fp_itt and fp_env from the reader's own fp, floored at 0."""
    e = env.assign(id=env["id"].astype(str)).set_index("id")
    d = rows.assign(id=rows["id"].astype(str)).copy()
    joined = d.id.isin(e.index)
    gap = (d.loc[joined, "fp"].to_numpy(float) - e.loc[d.id[joined], "fp"].to_numpy(float))
    if len(gap) and float(abs(gap).max()) > FP_TOL:
        raise SystemExit(f"S64 LINE REFUSED: apply's fp differs from the reader's fp on {int((abs(gap) > FP_TOL).sum())} of "
                         f"{len(gap)} joined players (max {float(abs(gap).max()):.4f}) -- not the same FP numbers")
    for c in ("itt_adj", "env_adj"):
        d[c] = d.id.map(e[c]).fillna(0.0)
    audit = {"rows": int(len(d)), "joined": int(joined.sum()), "without_env": int((~joined).sum()),
             "fp_max_abs_gap": round(float(abs(gap).max()), 9) if len(gap) else None}
    d["fp_itt"] = (d.fp + d.itt_adj).clip(lower=0.0)
    d["fp_env"] = (d.fp + d.env_adj).clip(lower=0.0)
    return d[["id", "pos", "game", "gsis_id", "season", "week", "fp", "itt_adj", "env_adj", "fp_itt", "fp_env", "actual"]], audit


def score(R, d: pd.DataFrame, challenger: str, incumbent: str) -> dict:
    """The reader's metrics and bootstrap with the challenger in its 'ours' slot and the incumbent in its 'fp' slot
    ('blend' = the incumbent, never read)."""
    x = d.assign(ours=d[challenger], fp=d[incumbent], blend=d[incumbent])
    met = R.metrics(x)
    return {"incumbent": met["fp"], "challenger": met["ours"], "improvement": R.bootstrap(x)["ours_vs_fp"]}


def reading(s: dict, weeks: list[int]) -> str:
    better = s["challenger"]["MAE"] < s["incumbent"]["MAE"] and s["improvement"]["share_better"] >= SHARE
    if max(weeks) < TRIAL_FROM_WEEK or len(weeks) < MIN_WEEKS:
        return (f"descriptive only (the pooled check rules from W{TRIAL_FROM_WEEK} with >= {MIN_WEEKS} weeks); "
                + ("FP + ITT leads so far" if better else "FP + ITT does not lead so far"))
    return ("FP + ITT beats FP (pooled MAE lower, >= 95% of resamples better): TRIAL-ELIGIBLE, his decision" if better
            else "FP + ITT does not beat FP: not trial-eligible")


def line(tag: str, names: tuple[str, str], s: dict) -> str:
    f, g, i = s["incumbent"], s["challenger"], s["improvement"]
    return (f"{tag}: MAE {names[0]} {f['MAE']:.3f} vs {names[1]} {g['MAE']:.3f} (bias {f['bias']:+.3f} / {g['bias']:+.3f}; "
            f"Spearman {f['spearman']:.3f} / {g['spearman']:.3f}); improvement {i['mean']:+.4f} [5-95% {i['p05']:+.4f}, "
            f"{i['p95']:+.4f}], share of resamples better {i['share_better']:.3f}")


def both(R, d: pd.DataFrame, tag: str) -> tuple[dict, list[str]]:
    p = score(R, d, "fp_itt", "fp")
    w = score(R, d, "fp_env", "fp_itt")
    return p, [line(f"{tag} PRIMARY", ("FP", "FP + ITT"), p),
               line(f"{tag} WIND (low confidence, never a rule)", ("FP + ITT", "FP + ENV"), w)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("week"); w.add_argument("--season", type=int, default=2026); w.add_argument("--week", type=int, required=True)
    w.add_argument("--rows", type=Path, required=True); w.add_argument("--frame", type=Path, required=True)
    w.add_argument("--proj-source", type=Path, required=True); w.add_argument("--coeffs", type=Path, required=True)
    w.add_argument("--out-dir", type=Path, required=True)
    p = sub.add_parser("pool"); p.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    R = reader()
    print(f"STUDY 64 LINE  sha256 {hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}  reader {READER_SHA256[:12]}")
    if a.cmd == "week":
        A = _load("s64_env_apply")
        coeffs = json.loads(a.coeffs.read_text())
        env = A.apply(pd.read_parquet(a.frame), pd.read_csv(a.proj_source, dtype={"id": str}), coeffs)
        d, audit = week_rows(pd.read_csv(a.rows, dtype={"id": str, "gsis_id": str, "game": str}), env)
        a.out_dir.mkdir(parents=True, exist_ok=True)
        stem = a.out_dir / f"s64-{a.season}-w{a.week:02d}"
        d.to_csv(f"{stem}.csv", index=False)
        meta = {"rows_source": str(a.rows), "rows_sha256": hashlib.sha256(a.rows.read_bytes()).hexdigest(),
                "coeffs_sha256": hashlib.sha256(a.coeffs.read_bytes()).hexdigest(), **audit,
                "out_sha256": hashlib.sha256(Path(f"{stem}.csv").read_bytes()).hexdigest()}
        Path(f"{stem}.json").write_text(json.dumps(meta, indent=1) + "\n")
        print(f"  W{a.week:02d} rows {audit['rows']} (joined {audit['joined']}, without an adjustment {audit['without_env']}; "
              f"fp identity max gap {audit['fp_max_abs_gap']})  coeffs {meta['coeffs_sha256'][:12]}")
        for ln in both(R, d, f"W{a.week:02d} (descriptive)")[1]:
            print("  " + ln)
        return 0
    files = sorted(a.out_dir.glob("s64-*-w*.csv"))
    if not files:
        raise SystemExit(f"no weekly s64 rows in {a.out_dir}")
    d = pd.concat([pd.read_csv(f, dtype={"id": str, "gsis_id": str, "game": str}) for f in files], ignore_index=True)
    early = sorted(int(x) for x in d.week[d.week < FIRST_WEEK].unique())
    if early:
        print(f"  left out of the pool: weeks {early} (before W{FIRST_WEEK}, the first prospective week)")
    d = d[d.week >= FIRST_WEEK]
    if d.empty:
        raise SystemExit(f"no weekly s64 rows from W{FIRST_WEEK} in {a.out_dir}")
    weeks = sorted(int(x) for x in d.week.unique())
    p, lines = both(R, d, f"POOLED weeks {weeks}")
    for ln in lines:
        print("  " + ln)
    print(f"  THE POOLED CHECK: {reading(p, weeks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
