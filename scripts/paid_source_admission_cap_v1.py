#!/usr/bin/env python3
"""Admission-cap lever on the paid-source instrument (preregistration
reports/2026-09-15-prereg-admission-cap-lever.md).  Re-uses the 2026-09-15 ladder records' player annotations, so
the component producer is not re-run: per slate it recomputes lineup support, admits candidates under five rules
(cap200 / cap400 / cap800 / capall by mean matchup edge; tail200 by discovery tail count), selects K80 with
coverage-194-v1, and grades points and finish exactly as the ladder runner did.

Usage: paid_source_admission_cap_v1.py --ladder-results R --workdir W --results R2 [--ordinals ...] [--mechanics-only]
       paid_source_admission_cap_v1.py --read R2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd

from nfl_dfs.research import corpus_r6_paid_source_ablation_v1 as ablation
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paid_source_ladder_direct_v1 import (  # noqa: E402
    CANDIDATE_ROOT, CATALOG_RELEASE, FIELD_N, FRACS, MATRIX_TERMINAL, MICRO, MIN_OWNERSHIP_MASS, OWNERSHIP_PANEL, PREFIXES,
    boot, load_json, open_matrix, prefix_grade, realized_micro, sha256_file,
)
from prereg098_field_sampler import sample_field  # noqa: E402

ON, OFF = "fp-on-sis-on-v1", "fp-off-sis-off-v1"
RULES = ("cap200", "cap400", "cap800", "capall", "tail200")
CAPS = {"cap200": 200, "cap400": 400, "cap800": 800, "capall": None}
SCHEMA = "paid-source-admission-cap/v1"
STRATEGY = next(v for v in retrieval.frozen_retrieval_strategies(registry.ENTRY_BUDGET) if v["strategy_id"] == "coverage-194-v1")


def select(admitted: list[str], candidate_ids: list[str], matrix: np.memmap) -> list[str]:
    if len(admitted) < registry.ENTRY_BUDGET:
        return []
    admitted = sorted(admitted)                                   # lexical order fed to the selector, as the ablation does
    idx = {c: i for i, c in enumerate(candidate_ids)}
    scores = np.asarray(matrix)[np.asarray([idx[c] for c in admitted], dtype=np.int64)]
    local, _ = retrieval._run_strategy(STRATEGY, discovery_scores=scores, lineup_ids=admitted)
    return [admitted[i] for i in local]


def admit(rule: str, support: list[dict], tail_counts: np.ndarray, world_means: np.ndarray, candidate_ids: list[str]) -> list[str]:
    if rule == "tail200":
        order = sorted(range(len(candidate_ids)), key=lambda i: (-int(tail_counts[i]), -float(world_means[i]), candidate_ids[i]))
        return [candidate_ids[i] for i in order[:200]]
    qualifying = [r for r in support if r["qualifies_for_matchup_admission"] is True]
    ranked = sorted(qualifying, key=lambda r: (-float(r["matchup_edge_mean"]), str(r["candidate_id"])))
    cap = CAPS[rule]
    return [str(r["candidate_id"]) for r in (ranked if cap is None else ranked[:cap])]


def run_slate(ordinal: int, ladder_rec: dict, *, workdir: pathlib.Path, results: pathlib.Path, catalog_entry: dict, candidate_desc: dict,
              matrix_entry: dict, ownership: pd.DataFrame | None, mechanics_only: bool, keep_matrix: bool) -> None:
    t0 = time.time(); slate = catalog_entry["slate"]; season, week = int(slate["season"]), int(slate["week"])
    catalog, cat_id = load_json(catalog_entry["catalog_identity"]["uri"], workdir)
    cands, cand_id = load_json(candidate_desc["candidate_artifact_identity"]["uri"], workdir)
    matrix, matrix_ids, mat_id, mat_path = open_matrix(matrix_entry["matrix_identity"]["uri"], workdir)
    candidate_ids = [str(r["candidate_id"]) for r in cands["rows"]]
    if candidate_ids != matrix_ids or ladder_rec["inputs"]["candidates"]["sha256"] != cand_id["sha256"]:
        raise RuntimeError(f"ordinal {ordinal}: candidate order/identity differs from the ladder record")
    tail_counts = (np.asarray(matrix) >= np.float32(194.0)).sum(axis=1); world_means = np.asarray(matrix).mean(axis=1, dtype=np.float64)
    rec = {"schema_version": SCHEMA, "ordinal": ordinal, "season": season, "week": week, "slate_id": slate["slate_id"], "mechanics_only": mechanics_only,
           "inputs": {"catalog": cat_id, "candidates": cand_id, "matrix": mat_id, "ladder_record_sha256": ladder_rec["_sha256"]},
           "candidate_count": len(candidate_ids), "pool_tail194_candidates": int((tail_counts > 0).sum()), "cells": {}}
    plans = {}
    for source in (ON, OFF):
        ann = [{"gsis_id": a["gsis_id"], "family": a["family"], "matchup_edge_score": a["matchup_edge_score"], "qb_depth1": a["qb_depth1"]}
               for a in ladder_rec["cells"][source]["player_annotations"]]
        support = ablation._lineup_support(catalog=catalog, candidate_rows=cands["rows"], annotations=ann)
        for rule in RULES:
            if rule == "tail200" and source == OFF:
                continue
            admitted = admit(rule, support, tail_counts, world_means, candidate_ids)
            sel = select(admitted, candidate_ids, matrix)
            plans[(rule, source)] = (admitted, sel)
    if not mechanics_only:
        actual, act_rec = realized_micro(season, week, catalog["players"]); rec["actuals"] = act_rec
        score_by_id = {str(r["candidate_id"]): int(sum(actual[str(p)] for p in r["player_ids"])) for r in cands["rows"]}
        rec["pool_realized_ceiling_points"] = max(score_by_id.values()) / MICRO
        field_scores = None; own_mass = 0.0
        if ownership is not None:
            og = ownership[(ownership.season == season) & (ownership.week == week)]; own_mass = float(og.pct.sum())
            if own_mass >= MIN_OWNERSHIP_MASS:
                frame = pd.DataFrame([{"id": str(p["id"]), "pos": p["pos"], "team": p["team"], "salary": int(p["salary"])} for p in catalog["players"]])
                target = dict(zip(og.id.astype(str), (og.pct / 100.0).astype(float)))
                field, frec = sample_field(frame, target, n=FIELD_N, seed=98_000_000 + season * 100 + week)
                act_arr = np.array([actual[str(i)] for i in frame.id], dtype=np.int64)
                field_scores = np.sort(act_arr[field].sum(axis=1))[::-1]
                ranks = {k: max(1, int(round(f * FIELD_N))) for k, f in FRACS.items()}
                rec["field"] = {"seed": 98_000_000 + season * 100 + week, "ownership_mass": own_mass, "sampler": {k: v for k, v in frec.items() if k != "rounds"},
                                "realized_cut_points": {k: float(field_scores[r - 1] / MICRO) for k, r in ranks.items()}, "ranks": ranks}
        rec["finish_available"] = field_scores is not None
    for (rule, source), (admitted, sel) in plans.items():
        cell = {"rule": rule, "source": source, "admitted_count": len(admitted), "k80_feasible": len(sel) == registry.ENTRY_BUDGET,
                "selected_k80_candidate_ids": sel, "admitted_candidate_ids": admitted if rule != "capall" else None,
                "admitted_tail194_count": int(sum(1 for c in admitted if tail_counts[candidate_ids.index(c)] > 0)) if len(admitted) <= 800 else None}
        if not mechanics_only:
            cell["admitted_realized_ceiling_points"] = max(score_by_id[c] for c in admitted) / MICRO if admitted else None
            if sel:
                g = prefix_grade(sel, score_by_id)
                if field_scores is not None:
                    for k in PREFIXES:
                        g[f"k{k}"]["best_pct"] = float((field_scores > g[f"k{k}"]["weekly_max_micro"]).sum() / FIELD_N)
                        book = [score_by_id[c] for c in sel[:k]]
                        g[f"k{k}"]["events"] = {name: int(sum(b >= field_scores[r - 1] for b in book)) for name, r in rec["field"]["ranks"].items()}
                cell["grade"] = g
        rec["cells"][f"{rule}|{source}"] = cell
    rec["seconds"] = round(time.time() - t0, 1)
    (results / f"slate-{ordinal:02d}-{slate['slate_id']}.json").write_text(json.dumps(rec, sort_keys=True))
    del matrix
    if not keep_matrix:
        mat_path.unlink(missing_ok=True); (mat_path.parent / (mat_path.name + ".identity.json")).unlink(missing_ok=True)
    line = {"ordinal": ordinal, "slate": slate["slate_id"], "seconds": rec["seconds"]}
    for key, cell in rec["cells"].items():
        line[key] = {"admitted": cell["admitted_count"], "feasible": cell["k80_feasible"]}
        if "grade" in cell:
            line[key]["k20"] = cell["grade"]["k20"]["weekly_max_points"]; line[key]["ceiling"] = cell["admitted_realized_ceiling_points"]
    print(json.dumps(line), flush=True)


def main_run(a) -> int:
    workdir = pathlib.Path(a.workdir); results = pathlib.Path(a.results); results.mkdir(parents=True, exist_ok=True)
    ladder = pathlib.Path(a.ladder_results)
    cat_release, cat_rel_id = load_json(CATALOG_RELEASE, workdir); cand_root, cand_root_id = load_json(CANDIDATE_ROOT, workdir)
    terminal, term_id = load_json(MATRIX_TERMINAL, workdir)
    entries = {int(e["source_task_ordinal"]): e for e in cat_release["entries"]}
    cand_objs = {int(o["source_task_ordinal"]): o for o in cand_root["objects"]}
    mats = {int(m["source_task_ordinal"]): m for m in terminal["matrix_registry"]}
    ownership = None if a.mechanics_only else pd.read_parquet(OWNERSHIP_PANEL)
    manifest = {"schema_version": SCHEMA, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mechanics_only": a.mechanics_only,
                "ladder_results_dir": str(ladder), "ladder_manifest_sha256": sha256_file(ladder / "manifest.json"),
                "catalog_release": cat_rel_id, "candidate_root": cand_root_id, "matrix_terminal": term_id, "rules": list(RULES), "caps": CAPS,
                "runner_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                "ownership_panel_sha256": sha256_file(OWNERSHIP_PANEL) if ownership is not None else None, "strategy": STRATEGY["strategy_id"]}
    (results / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=1))
    ordinals = [int(x) for x in a.ordinals.split(",")] if a.ordinals else sorted(entries)
    for o in ordinals:
        out = results / f"slate-{o:02d}-{entries[o]['slate']['slate_id']}.json"
        if out.exists() and not a.force:
            print(json.dumps({"ordinal": o, "skipped": "exists"}), flush=True); continue
        lp = ladder / f"slate-{o:02d}-{entries[o]['slate']['slate_id']}.json"; lrec = json.loads(lp.read_text()); lrec["_sha256"] = sha256_file(lp)
        run_slate(o, lrec, workdir=workdir, results=results, catalog_entry=entries[o], candidate_desc=cand_objs[o], matrix_entry=mats[o],
                  ownership=ownership, mechanics_only=a.mechanics_only, keep_matrix=a.keep_matrices)
    return 0


def contrast(w: pd.DataFrame, a: str, b: str, col: str, label: str, level: float) -> str:
    from math import comb
    d = (w[f"{a}:{col}"] - w[f"{b}:{col}"]).dropna(); df = pd.DataFrame({"season": w.loc[d.index, "season"], "d": d})
    lo, hi = boot(df, "d", level=level); seasons = {int(s): float(df[df.season == s].d.mean()) for s in sorted(df.season.unique())}
    loso = {int(s): float(df[df.season != s].d.mean()) for s in sorted(df.season.unique())}
    nz = d[d != 0]; n = len(nz); k = int((nz > 0).sum()); p = min(1.0, sum(comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n * 2) if n else 1.0
    mean = float(d.mean())
    verdict = "PASS" if (lo > 0 and all(v >= 0 for v in seasons.values()) and all(v > 0 for v in loso.values()) and p < 0.05) else ("NEAR_MISS" if mean > 0 and lo > -abs(mean) / 2 else "NO_EFFECT")
    return f"{label}: {mean:+.5f} [{lo:+.5f}, {hi:+.5f}] W/L/T {(d>0).sum()}/{(d<0).sum()}/{(d==0).sum()} sign p={p:.3f} seasons {seasons} LOSO {loso} VERDICT={verdict}"


def main_read(results: pathlib.Path) -> int:
    rows = []
    for f in sorted(results.glob("slate-*.json")):
        r = json.loads(f.read_text())
        if r.get("mechanics_only"):
            raise SystemExit(f"{f.name} is mechanics-only")
        row = {"ordinal": r["ordinal"], "season": r["season"], "week": r["week"], "pool_ceiling": r["pool_realized_ceiling_points"], "pool_tail194": r["pool_tail194_candidates"]}
        for key, c in r["cells"].items():
            row[f"{key}:admitted"] = c["admitted_count"]; row[f"{key}:feasible"] = int(c["k80_feasible"]); row[f"{key}:ceiling"] = c["admitted_realized_ceiling_points"]
            row[f"{key}:ceil194"] = int((c["admitted_realized_ceiling_points"] or 0) >= 194)
            if "grade" in c:
                for k in PREFIXES:
                    row[f"{key}:k{k}_max"] = c["grade"][f"k{k}"]["weekly_max_points"]; row[f"{key}:k{k}_neg_best_pct"] = -c["grade"][f"k{k}"]["best_pct"] if "best_pct" in c["grade"][f"k{k}"] else np.nan
                    row[f"{key}:k{k}_ge194"] = int(c["grade"][f"k{k}"]["thresholds"]["194"]["max_at_or_above"])
        rows.append(row)
    w = pd.DataFrame(rows).sort_values(["season", "week"]).reset_index(drop=True)
    print(f"ADMISSION-CAP LEVER read: {len(w)} slates, seasons {sorted(w.season.unique())}; pool ceiling mean {w.pool_ceiling.mean():.2f}; pool slates with a 194+ {int((w.pool_ceiling >= 194).sum())}")
    fam = 1 - 0.05 / 4
    c200, call, ctail = f"cap200|{ON}", f"capall|{ON}", f"tail200|{ON}"
    print("\nPRIMARY (K20; family 0.9875; PASS iff interval > 0, seasons >= 0, LOSO > 0, sign p < 0.05):")
    print(contrast(w, call, c200, "k20_max", "1 points  capall - cap200 (on-on)", fam))
    print(contrast(w, call, c200, "k20_neg_best_pct", "2 finish  capall - cap200 (on-on)", fam))
    print(contrast(w, ctail, c200, "k20_max", "3 points  tail200 - cap200        ", fam))
    print(contrast(w, call, f"capall|{OFF}", "k20_max", "4 points  on-on - off-off at capall", fam))
    print("\nSECONDARY:")
    for k in (40, 80):
        print(contrast(w, call, c200, f"k{k}_max", f"points  capall - cap200 K{k}", 0.95)); print(contrast(w, call, c200, f"k{k}_neg_best_pct", f"finish  capall - cap200 K{k}", 0.95))
        print(contrast(w, ctail, c200, f"k{k}_max", f"points  tail200 - cap200 K{k}", 0.95)); print(contrast(w, call, f"capall|{OFF}", f"k{k}_max", f"points  on-on - off-off at capall K{k}", 0.95))
    print(contrast(w, ctail, c200, "k20_neg_best_pct", "finish  tail200 - cap200 K20", 0.95)); print(contrast(w, call, f"capall|{OFF}", "k20_neg_best_pct", "finish  on-on - off-off at capall K20", 0.95))
    for rule in ("cap400", "cap800"):
        print(contrast(w, f"{rule}|{ON}", c200, "k20_max", f"points  {rule} - cap200 (on-on)", 0.95))
    print("\nRULES (means; on-on unless noted):")
    for key in [f"{r}|{ON}" for r in RULES] + [f"{r}|{OFF}" for r in RULES if r != "tail200"]:
        if f"{key}:k20_max" in w:
            print(f"  {key:22s} admitted {w[f'{key}:admitted'].mean():7.1f} | feasible {int(w[f'{key}:feasible'].sum())}/54 | admitted ceiling {w[f'{key}:ceiling'].mean():7.2f} | slates admitted has 194+ {int(w[f'{key}:ceil194'].sum())} | K20 max {w[f'{key}:k20_max'].mean():7.2f} | K80 max {w[f'{key}:k80_max'].mean():7.2f} | K20 best_pct {(-w[f'{key}:k20_neg_best_pct']).mean()*100:.3f}% | weeks K80>=194 {int(w[f'{key}:k80_ge194'].sum())}")
    w.to_csv(results / "read_table.csv", index=False)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--ladder-results", default="/home/erich/week1-sunday/direct_runner/results")
    ap.add_argument("--workdir", default="/home/erich/week1-sunday/direct_runner/work"); ap.add_argument("--results", default="/home/erich/week1-sunday/direct_runner/results_cap")
    ap.add_argument("--ordinals", default=""); ap.add_argument("--mechanics-only", action="store_true"); ap.add_argument("--keep-matrices", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--read", default="")
    a = ap.parse_args(argv)
    return main_read(pathlib.Path(a.read)) if a.read else main_run(a)


if __name__ == "__main__":
    sys.exit(main())
