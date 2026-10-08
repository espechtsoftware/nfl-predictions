#!/usr/bin/env python3
"""Study row 67: the weekly $6,000-7,900 tier check (descriptive; it gates nothing).

Why this tier: over 2026 W1-4 our player picks lost the most there (-6.0 points per lineup), and our projection ran
about +0.6 above the market there (the outside reviewer's 10-07 brainstorm, M4). From Week 5 Fantasy Points' numbers drive
the build, so each Monday this checks FP against the market (props) and ours inside the tier.

Inputs: the frozen readers' OWN private rows, no new FP join.
  --accuracy  ~/private/projection-accuracy/accuracy-S-wWW.csv (+ .json), written by scripts/weekly_projection_accuracy.py
              (id, name, pos, game, gsis_id, season, week, ours, fp, actual, blend: its population and actuals);
  --fp-props  ~/private/fp-props-check/fp-props-S-wWW.csv (+ .json), written by scripts/weekly_fp_props_check.py (props on
              the prop-covered players, joined by id);
  --frame     the week's T-70 frame.parquet (salary by id), which must be the frame the accuracy sidecar names.
It refuses when a CSV's sha256 differs from its sidecar's rows_sha256, when the frame is not the accuracy sidecar's
frame, when the two sidecars disagree on the FP capture / cutoff / lock / contest, or when a joined row's fp differs
between the two readers (|diff| > 1e-6).

Metrics are the frozen accuracy reader's own (metrics() and bootstrap(), imported with the reader's sha256 pinned, as
scripts/s64_env_line.py does): MAE, bias = source - actual (positive = the source over-projected), Spearman, and the
game-cluster bootstrap within week (B 2000, seed 1), whose improvement = MAE(incumbent) - MAE(challenger).
  A. the tier's accuracy-reader rows: ours, fp and the reader's blend (0.5 ours + 0.5 fp);
  B. the prop-covered part: props sits in the reader's "ours" slot, FP in its "fp" slot and 0.5 FP + 0.5 props in its
     "blend" slot (so ours_vs_fp reads props vs FP);
  C. descriptive: the mean actual of each source's 5 highest-projected tier players, beside the tier mean.

    python scripts/tier_check.py week --season 2026 --week 5 --accuracy <accuracy-2026-w05.csv> \\
        --fp-props <fp-props-2026-w05.csv> --frame <T-70 run>/frame.parquet --out-dir ~/private/tier-check [--summary <path>]
    python scripts/tier_check.py pool --out-dir ~/private/tier-check [--summary <path>]
Writes PRIVATE rows (FP's numbers are licensed): <out-dir>/tier-S-wWW.csv + .json. Prints aggregates only. Weeks before
5 are printed as references and never pooled.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
READER_SHA256 = "dadc647dd3bdeffade8526774f2b9849027962fe91df00f7e47268b866c0890d"   # scripts/weekly_projection_accuracy.py
LO, HI, TOP_K, FP_TOL = 6000, 7900, 5, 1e-6
FIRST_WEEK = 5
SAME_KEYS = ("capture", "capture_before", "lock_utc", "contest")
COLS = ["id", "name", "pos", "game", "gsis_id", "season", "week", "salary", "ours", "fp", "blend", "props", "actual"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def reader():
    got = hashlib.sha256((HERE / "weekly_projection_accuracy.py").read_bytes()).hexdigest()
    if got != READER_SHA256:
        raise SystemExit(f"TIER CHECK REFUSED: weekly_projection_accuracy.py is {got[:12]}, not the pinned {READER_SHA256[:12]}")
    return _load("weekly_projection_accuracy")


def read_rows(csv: Path) -> tuple[pd.DataFrame, dict]:
    side_path = csv.with_suffix(".json")
    if not (csv.is_file() and side_path.is_file()):
        raise SystemExit(f"TIER CHECK REFUSED: {csv} or its .json sidecar is missing")
    side = json.loads(side_path.read_text())
    got = hashlib.sha256(csv.read_bytes()).hexdigest()
    if side.get("rows_sha256") != got:
        raise SystemExit(f"TIER CHECK REFUSED: {csv.name} is {got[:12]}, its sidecar says {str(side.get('rows_sha256'))[:12]}")
    return pd.read_csv(csv, dtype={"id": str, "game": str, "gsis_id": str}), side


def check_inputs(acc_side: dict, fpp_side: dict, frame: Path) -> None:
    if Path(str(acc_side.get("frame"))).resolve() != Path(frame).resolve():
        raise SystemExit(f"TIER CHECK REFUSED: --frame {frame} is not the accuracy reader's frame {acc_side.get('frame')}")
    for k in SAME_KEYS:
        if acc_side.get(k) != fpp_side.get(k):
            raise SystemExit(f"TIER CHECK REFUSED: the two readers disagree on {k}: {acc_side.get(k)!r} vs {fpp_side.get(k)!r}")


def tier_rows(acc: pd.DataFrame, fpp: pd.DataFrame, frame: pd.DataFrame, lo: int = LO, hi: int = HI) -> tuple[pd.DataFrame, dict]:
    """Pure: the accuracy rows whose T-70 salary is in [lo, hi], with props joined by id after the fp identity gate."""
    sal = frame.drop_duplicates("id").assign(id=lambda f: f["id"].astype(str)).set_index("id")["salary"]
    d = acc.assign(id=acc["id"].astype(str)).copy()
    d["salary"] = pd.to_numeric(d.id.map(sal), errors="coerce")
    audit = {"accuracy_rows": int(len(d)), "no_salary": int(d.salary.isna().sum())}
    d = d[d.salary.between(lo, hi)].copy()
    p = fpp.assign(id=fpp["id"].astype(str)).drop_duplicates("id").set_index("id")
    both = d.id.isin(p.index)
    gap = (d.loc[both, "fp"] - d.loc[both, "id"].map(p["fp"])).abs()
    if (gap > FP_TOL).any():
        raise SystemExit(f"TIER CHECK REFUSED: {int((gap > FP_TOL).sum())} joined rows have a different fp in the two readers "
                         f"(max |diff| {gap.max():.6f})")
    d["props"] = d.id.map(p["props"]).astype(float)
    audit.update({"tier": [lo, hi], "tier_rows": int(len(d)), "with_props": int(d.props.notna().sum()),
                  "by_pos": {k: int(v) for k, v in d.pos.value_counts().sort_index().items()}})
    return d[COLS].sort_values("id").reset_index(drop=True), audit


def top_k(d: pd.DataFrame, col: str, k: int = TOP_K) -> float:
    return float(d.sort_values([col, "id"], ascending=[False, True]).head(k).actual.mean())


def block(d: pd.DataFrame, title: str, R) -> str:
    """The printed aggregate block (no player rows)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"== TIER CHECK ${LO:,}-{HI:,}: {title} -- descriptive, gates nothing. bias = source - actual (+ = over-projected); "
              f"improvement = MAE(incumbent) - MAE(challenger), game clusters within week, B {R.B}, seed {R.SEED}")
        print(f"   tier rows {len(d)} in {d.game.nunique()} games; by position {d.pos.value_counts().sort_index().to_dict()}; "
              f"tier mean actual {d.actual.mean():.2f}")
        if len(d) == 0:
            return buf.getvalue()
        m, b = R.metrics(d), R.bootstrap(d)
        print("   A. the accuracy reader's tier rows:")
        for s in R.SOURCES:
            print(f"      {s:6s} MAE {m[s]['MAE']:.2f}  bias {m[s]['bias']:+.2f}  Spearman {m[s]['spearman']:+.2f}  "
                  f"top-{TOP_K} mean actual {top_k(d, s):.2f}")
        for k, v in b.items():
            print(f"      {k:14s} improvement {v['mean']:+.2f} [{v['p05']:+.2f}, {v['p95']:+.2f}]  better in {v['share_better']:.0%}")
        sub = d[d.props.notna()]
        if len(sub) == 0:
            print("   B. no prop-covered tier rows")
        else:
            slot = sub.assign(ours=sub.props, blend=0.5 * sub.fp + 0.5 * sub.props)
            m2, b2 = R.metrics(slot), R.bootstrap(slot)
            lab = {"ours": "props", "fp": "fp", "blend": "fp+props"}
            print(f"   B. the prop-covered part (n {len(sub)}; props in the reader's ours slot, 0.5 FP + 0.5 props in its blend slot):")
            for s in R.SOURCES:
                print(f"      {lab[s]:8s} MAE {m2[s]['MAE']:.2f}  bias {m2[s]['bias']:+.2f}  Spearman {m2[s]['spearman']:+.2f}  "
                      f"top-{TOP_K} mean actual {top_k(slot, s):.2f}")
            names = {"ours_vs_fp": "props_vs_fp", "blend_vs_fp": "fp+props_vs_fp", "blend_vs_ours": "fp+props_vs_props"}
            for k, v in b2.items():
                print(f"      {names[k]:18s} improvement {v['mean']:+.2f} [{v['p05']:+.2f}, {v['p95']:+.2f}]  better in {v['share_better']:.0%}")
    return buf.getvalue()


def _emit(text: str, summary: Path | None) -> None:
    print(text, end="")
    if summary:
        summary.parent.mkdir(parents=True, exist_ok=True)
        with summary.open("a") as f:
            f.write(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("week")
    w.add_argument("--season", type=int, required=True); w.add_argument("--week", type=int, required=True)
    w.add_argument("--accuracy", type=Path, required=True); w.add_argument("--fp-props", type=Path, required=True)
    w.add_argument("--frame", type=Path, required=True); w.add_argument("--out-dir", type=Path, required=True)
    w.add_argument("--lo", type=int, default=LO); w.add_argument("--hi", type=int, default=HI)
    w.add_argument("--summary", type=Path, default=None)
    p = sub.add_parser("pool"); p.add_argument("--out-dir", type=Path, required=True); p.add_argument("--summary", type=Path, default=None)
    a = ap.parse_args(argv)
    R = reader()
    if a.cmd == "week":
        acc, acc_side = read_rows(a.accuracy); fpp, fpp_side = read_rows(a.fp_props)
        check_inputs(acc_side, fpp_side, a.frame)
        if not ((acc.season == a.season) & (acc.week == a.week)).all():
            raise SystemExit(f"TIER CHECK REFUSED: {a.accuracy.name} is not {a.season} W{a.week}")
        d, audit = tier_rows(acc, fpp, pd.read_parquet(a.frame), a.lo, a.hi)
        a.out_dir.mkdir(parents=True, exist_ok=True)
        stem = a.out_dir / f"tier-{a.season}-w{a.week:02d}"
        d.to_csv(f"{stem}.csv", index=False)
        audit.update({"accuracy": str(a.accuracy), "accuracy_sha256": acc_side["rows_sha256"], "fp_props": str(a.fp_props),
                      "fp_props_sha256": fpp_side["rows_sha256"], "frame": str(a.frame), "reader_sha256": READER_SHA256,
                      "rows_sha256": hashlib.sha256(Path(f"{stem}.csv").read_bytes()).hexdigest(),
                      "written_utc": datetime.now(timezone.utc).isoformat()})
        Path(f"{stem}.json").write_text(json.dumps(audit, indent=1) + "\n")
        tag = "" if a.week >= FIRST_WEEK else " (REFERENCE: before Week 5, never pooled)"
        _emit(block(d, f"{a.season} W{a.week}{tag}", R), a.summary)
        return 0
    files = sorted(a.out_dir.glob("tier-*-w*.csv"))
    if not files:
        raise SystemExit(f"no tier rows in {a.out_dir}")
    pooled = pd.concat([pd.read_csv(f, dtype={"id": str, "game": str, "gsis_id": str}) for f in files], ignore_index=True)
    text = ""
    for (s, wk), g in pooled.groupby(["season", "week"]):
        tag = "" if wk >= FIRST_WEEK else " (REFERENCE: before Week 5, never pooled)"
        text += block(g, f"{s} W{wk}{tag}", R)
    counted = pooled[pooled.week >= FIRST_WEEK]
    text += block(counted, f"POOLED weeks >= {FIRST_WEEK}", R) if len(counted) else "== no counted week yet (weeks >= 5)\n"
    _emit(text, a.summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
