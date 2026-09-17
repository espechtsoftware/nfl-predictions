#!/usr/bin/env python3
"""Paid-source influence ladder, direct runner (draft preregistration
reports/2026-09-14-prereg-paid-source-influence-ladder-DRAFT.md).

Runs the frozen Fantasy Points x SIS 2x2 retrieval ablation's *pure computation*
(corpus_r6_matchup_component_producer_v1._derive_semantic_slate,
corpus_r6_paid_source_ablation_v1._source_view/_lineup_support/_coverage_selection,
corpus_retrieval_engine coverage-194-v1) on the frozen inputs (seven-pack v4 row
objects, fixed-G0 structural catalogs, candidate-v2 accepted candidates, the
exp5 discovery matrices) WITHOUT the create-once / provider-receipt / git-bound
authority chain.  Every input is recorded by uri + bytes + sha256 in the run
manifest.  Adds the stage-influence sidecar and the finish endpoint (an
ownership-consistent 200,000-lineup field from prereg098_field_sampler scored
on realized points).

Modes
  --mechanics-only   outcome-blind: no realized point is read (LAB_RULES shape)
  default            adds realized K20/K40/K80 prefix maxima, thresholds and the
                     finish endpoint per cell and slate
  --read DIR         frozen reader over a results directory (verbatim output is
                     what enters the ledger)

Usage: paid_source_ladder_direct_v1.py --workdir W --results R [--ordinals 0,1,...] [--mechanics-only]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from nfl_dfs.research import corpus_r6_matchup_component_producer_v1 as producer
from nfl_dfs.research import corpus_r6_paid_source_ablation_v1 as ablation
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prereg098_field_sampler import sample_field  # noqa: E402

SEVEN_PACK_RELEASE = (
    "gs://nfl-predictions-503414-corpus-source/research/"
    "corpus-r6-matchup-seven-pack-captures-v1/20260911-fp-sis-seven-pack-successor-v4/upstream-release.json"
)
CATALOG_RELEASE = (
    "gs://nfl-predictions-503414-corpus-source/research/source/"
    "20260826-r6-player-catalog-fixed-g0-v1/catalog-release.json"
)
CANDIDATE_ROOT = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-fixed-g0-candidate-authorities-v2/20260830-fixed-g0-candidate-authority-v2/candidate-authority-release-v2.json"
)
MATRIX_TERMINAL = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-paid-source-discovery-matrices/exp5-discovery-matrix-20260911e/terminal.json"
)
OWNERSHIP_PANEL = pathlib.Path("/home/erich/week1-sunday/direct_runner/ownership_2023_2025_catalog_ids.parquet")
PROJECT = "nfl-predictions-503414"
CELLS = tuple(registry.MATCHUP_CELL_ORDER)          # on-on, off-on, on-off, off-off
CONTROL = CELLS[0]
PREFIXES = (20, 40, 80)
THRESHOLDS = (194, 200, 210, 220, 230, 240)
MICRO = 1_000_000
REF_FIELD = 832_342
FIELD_N = 200_000
FRACS = {"top100": 100 / REF_FIELD, "top1000": 1000 / REF_FIELD, "cash": 173_275 / REF_FIELD}
MIN_OWNERSHIP_MASS = 800.0
SCHEMA = "paid-source-ladder-direct/v1"


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(16 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(uri: str, workdir: pathlib.Path, *, keep: bool = True) -> tuple[pathlib.Path, dict]:
    """Copy one GCS object into the cache (once) and return (path, identity)."""
    cache = workdir / "cache"; cache.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(uri.encode()).hexdigest()[:16] + "-" + uri.rsplit("/", 1)[-1]
    path = cache / name; meta = cache / (name + ".identity.json")
    if not (path.exists() and meta.exists()):
        subprocess.run(["gcloud", "storage", "cp", "--no-user-output-enabled", uri, str(path)], check=True)
        meta.write_text(json.dumps({"uri": uri, "bytes": path.stat().st_size, "sha256": sha256_file(path)}, sort_keys=True))
    return path, json.loads(meta.read_text())


def load_json(uri: str, workdir: pathlib.Path) -> tuple[dict, dict]:
    path, ident = fetch(uri, workdir)
    return json.loads(path.read_text()), ident


def open_matrix(uri: str, workdir: pathlib.Path) -> tuple[np.memmap, list[str], dict, pathlib.Path]:
    path, ident = fetch(uri, workdir)
    with open(path, "rb") as f:
        header_raw = f.readline(16 * 1024 * 1024)
    header = json.loads(header_raw[:-1].decode())
    shape = tuple(int(x) for x in header["shape"])
    if header["dtype"] != "<f8" or len(shape) != 2:
        raise RuntimeError("discovery matrix header differs from the frozen contract")
    matrix = np.memmap(path, dtype="<f8", mode="r", offset=len(header_raw), shape=shape)
    return matrix, [str(c) for c in header["candidate_ids"]], {**ident, "candidate_ids_sha256": header["candidate_ids_sha256"], "shape": list(shape)}, path


def bq_json(sql: str) -> list[dict]:
    raw = subprocess.run(["bq", "query", "--project_id", PROJECT, "--use_legacy_sql=false", "--format=json", "--max_rows=1000000", sql],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(raw)


def realized_micro(season: int, week: int, catalog_players: list[dict]) -> tuple[dict[str, int], dict]:
    """Realized DK points per catalog id in integer micro-DK (1e6 per point): skill players from
    nfl_features.player_week_actuals, DSTs from nfl_features.team_defense_week (the replay's scorer)."""
    rows = bq_json(f"SELECT gsis_id, dk_points FROM `nfl_features.player_week_actuals` WHERE season={season} AND week={week}")
    pts = {str(r["gsis_id"]): float(r["dk_points"]) for r in rows if r.get("dk_points") is not None}
    dst = bq_json(f"SELECT team, dst_dk_points FROM `nfl_features.team_defense_week` WHERE season={season} AND week={week}")
    for r in dst:
        if r.get("dst_dk_points") is not None:
            pts[f"DST_{r['team']}"] = float(r["dst_dk_points"])
    out, missing = {}, []
    for p in catalog_players:
        i = str(p["id"])
        if i in pts:
            out[i] = int(round(pts[i] * MICRO))
        else:
            out[i] = 0; missing.append(i)
    return out, {"catalog_players": len(catalog_players), "missing_actual_count": len(missing), "missing_ids": missing[:50]}


def prefix_grade(selected: list[str], score_by_id: dict[str, int]) -> dict:
    scores = [score_by_id[c] for c in selected]           # selector order, never re-sorted (grader law)
    out = {}
    for k in PREFIXES:
        s = scores[:k]; best = max(s)
        out[f"k{k}"] = {"weekly_max_micro": best, "weekly_max_points": best / MICRO, "mean_micro": sum(s) / len(s),
                        "best_ordinal": int(np.argmax(s)),
                        "thresholds": {str(t): {"max_at_or_above": best >= t * MICRO, "count_at_or_above": int(sum(x >= t * MICRO for x in s))} for t in THRESHOLDS}}
    return out


def component_change_count(ref_rows: list[dict], rows: list[dict]) -> dict:
    ref = {r["gsis_id"]: r for r in ref_rows}; raw_changed = pct_changed = edge_changed = 0; players = 0
    for r in rows:
        a = ref.get(r["gsis_id"])
        if a is None:
            continue
        players += 1
        raw_changed += sum(1 for c, v in r["raw_component_values"].items() if a["raw_component_values"].get(c) != v)
        pct_changed += sum(1 for c, v in r["component_values"].items() if a["component_values"].get(c) != v)
        edge_changed += int(a["matchup_edge_score"] != r["matchup_edge_score"])
    return {"players": players, "raw_component_value_changes": raw_changed, "percentile_changes": pct_changed, "edge_score_changes": edge_changed}


def run_slate(ordinal: int, *, views: dict, workdir: pathlib.Path, results: pathlib.Path, catalog_entry: dict, candidate_desc: dict,
              matrix_entry: dict, ownership: pd.DataFrame | None, mechanics_only: bool, seven_pack_identity: dict, keep_matrix: bool) -> dict:
    t0 = time.time(); slate = catalog_entry["slate"]; season, week = int(slate["season"]), int(slate["week"])
    catalog, cat_id = load_json(catalog_entry["catalog_identity"]["uri"], workdir)
    cands, cand_id = load_json(candidate_desc["candidate_artifact_identity"]["uri"], workdir)
    matrix, matrix_ids, mat_id, mat_path = open_matrix(matrix_entry["matrix_identity"]["uri"], workdir)
    candidate_ids = [str(r["candidate_id"]) for r in cands["rows"]]
    if candidate_ids != matrix_ids:
        raise RuntimeError(f"ordinal {ordinal}: matrix row order differs from the candidate artifact")
    rec = {"schema_version": SCHEMA, "ordinal": ordinal, "season": season, "week": week, "slate_id": slate["slate_id"],
           "inputs": {"catalog": cat_id, "candidates": cand_id, "matrix": mat_id, "seven_pack": seven_pack_identity},
           "candidate_count": len(candidate_ids), "world_count": int(matrix.shape[1]), "cells": {}, "mechanics_only": mechanics_only}
    cell_out = {}
    for cell_id in CELLS:
        cell = registry.matchup_cell_v1(cell_id); fp_on = cell["fantasy_points_enabled"] is True; sis_on = cell["sis_enabled"] is True
        slices, view = views[cell_id]
        semantic = producer._derive_semantic_slate(catalog=catalog, slices=slices)
        annotations = [dict(r) for r in semantic["annotation_rows"]]
        if not (fp_on and sis_on):
            for r in annotations:
                if r["family"] == "receiver" and any(r["raw_component_values"][c] is not None for c in ablation.JOINT_FP_SIS_COMPONENTS):
                    raise RuntimeError("joint Fantasy Points/SIS component survived a missing source")
        support = ablation._lineup_support(catalog=catalog, candidate_rows=cands["rows"], annotations=annotations)
        selection = ablation._coverage_selection(lineup_support=support, candidate_ids=candidate_ids, world_scores=matrix)
        if not selection["k80_feasible"] or len(selection["selected_k80_candidate_ids"]) != registry.ENTRY_BUDGET:
            raise RuntimeError(f"ordinal {ordinal} cell {cell_id}: K80 not feasible ({selection['admitted_candidate_count']} admitted)")
        cell_out[cell_id] = {"annotations": annotations, "support": support, "selection": selection, "view_sha256": view["source_view_sha256"],
                             "removed_slice_row_counts": view["removed_slice_row_counts"]}
    ref = cell_out[CONTROL]
    for cell_id in CELLS:
        c = cell_out[cell_id]; sel = c["selection"]
        rec["cells"][cell_id] = {
            "view_sha256": c["view_sha256"], "removed_slice_row_counts": c["removed_slice_row_counts"],
            "annotated_players": sum(1 for r in c["annotations"] if r["matchup_edge_score"] is not None),
            "component_support_counts": {comp: sum(1 for r in c["annotations"] if r["component_support"].get(comp)) for comp in sorted({k for r in c["annotations"] for k in r["component_support"]})},
            "qualifying_candidate_count": sel["qualifying_candidate_count"], "admitted_candidate_count": sel["admitted_candidate_count"],
            "admission_ranked_candidate_ids": sel["admission_ranked_candidate_ids"], "selected_k80_candidate_ids": sel["selected_k80_candidate_ids"],
            "selection_trace": sel["selection_trace"],
            "candidate_edge_means": {r["candidate_id"]: r["matchup_edge_mean"] for r in c["support"] if r["matchup_edge_mean"] is not None},
            "stage_influence_vs_control": {
                "components": component_change_count(ref["annotations"], c["annotations"]),
                "admission": ablation._turnover(ref["selection"]["admission_ranked_candidate_ids"], sel["admission_ranked_candidate_ids"], label="admission"),
                "k80": ablation._turnover(ref["selection"]["selected_k80_candidate_ids"], sel["selected_k80_candidate_ids"], label="k80"),
                "k20": ablation._turnover(ref["selection"]["selected_k80_candidate_ids"][:20], sel["selected_k80_candidate_ids"][:20], label="k20"),
            },
            "player_annotations": [{"gsis_id": r["gsis_id"], "family": r["family"], "matchup_edge_score": r["matchup_edge_score"], "qb_depth1": r.get("qb_depth1"),
                                    "component_values": r["component_values"], "component_support": r["component_support"], "raw_component_values": r["raw_component_values"]} for r in c["annotations"]],
        }
    if not mechanics_only:
        actual, act_rec = realized_micro(season, week, catalog["players"]); rec["actuals"] = act_rec
        score_by_id = {str(r["candidate_id"]): int(sum(actual[str(p)] for p in r["player_ids"])) for r in cands["rows"]}
        pool_best = max(score_by_id.values()); rec["pool_realized_ceiling_points"] = pool_best / MICRO
        rec["pool_threshold_counts"] = {str(t): int(sum(v >= t * MICRO for v in score_by_id.values())) for t in THRESHOLDS}
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
                rec["field"] = {"n": FIELD_N, "seed": 98_000_000 + season * 100 + week, "ownership_mass": own_mass, "sampler": {k: v for k, v in frec.items() if k != "rounds"},
                                "realized_cut_points": {k: float(field_scores[r - 1] / MICRO) for k, r in ranks.items()}, "median_points": float(np.median(field_scores) / MICRO), "ranks": ranks}
        rec["finish_available"] = field_scores is not None; rec["ownership_mass"] = own_mass
        for cell_id in CELLS:
            sel = cell_out[cell_id]["selection"]; g = prefix_grade(sel["selected_k80_candidate_ids"], score_by_id)
            adm_best = max(score_by_id[c] for c in sel["admitted_candidate_ids"])
            g["admitted_realized_ceiling_points"] = adm_best / MICRO
            if field_scores is not None:
                for k in PREFIXES:
                    best = g[f"k{k}"]["weekly_max_micro"]
                    g[f"k{k}"]["best_pct"] = float((field_scores > best).sum() / FIELD_N)
                    book = [score_by_id[c] for c in sel["selected_k80_candidate_ids"][:k]]
                    g[f"k{k}"]["events"] = {name: int(sum(b >= field_scores[r - 1] for b in book)) for name, r in rec["field"]["ranks"].items()}
            rec["cells"][cell_id]["grade"] = g
    rec["seconds"] = round(time.time() - t0, 1)
    out = results / f"slate-{ordinal:02d}-{slate['slate_id']}.json"; out.write_text(json.dumps(rec, sort_keys=True))
    del matrix
    if not keep_matrix:
        mat_path.unlink(missing_ok=True); (mat_path.parent / (mat_path.name + ".identity.json")).unlink(missing_ok=True)
    line = {"ordinal": ordinal, "slate": slate["slate_id"], "seconds": rec["seconds"], "candidates": len(candidate_ids)}
    for cell_id in CELLS:
        c = rec["cells"][cell_id]; line[cell_id] = {"admitted": c["admitted_candidate_count"], "k80_jaccard_vs_control": round(c["stage_influence_vs_control"]["k80"]["jaccard"], 3)}
        if "grade" in c:
            line[cell_id]["k20_max"] = c["grade"]["k20"]["weekly_max_points"]; line[cell_id]["k20_best_pct"] = c["grade"]["k20"].get("best_pct")
    print(json.dumps(line), flush=True)
    return rec


def build_views(packs: list[dict]) -> dict:
    full = producer._pack_slices(packs)
    views = {}
    for cell_id in CELLS:
        cell = registry.matchup_cell_v1(cell_id)
        views[cell_id] = ablation._source_view(full, fp_enabled=cell["fantasy_points_enabled"] is True, sis_enabled=cell["sis_enabled"] is True)
    return views


def main_run(a) -> int:
    workdir = pathlib.Path(a.workdir); results = pathlib.Path(a.results); results.mkdir(parents=True, exist_ok=True)
    release, rel_id = load_json(SEVEN_PACK_RELEASE, workdir)
    packs, pack_ids = [], []
    for pack in release["packs"]:
        body, ident = load_json(pack["exact_rows_identity"]["uri"], workdir); packs.append(body); pack_ids.append({"pack_id": pack["pack_id"], **ident})
    seven_pack_identity = {"release": rel_id, "packs": pack_ids}
    cat_release, cat_rel_id = load_json(CATALOG_RELEASE, workdir); cand_root, cand_root_id = load_json(CANDIDATE_ROOT, workdir)
    terminal, term_id = load_json(MATRIX_TERMINAL, workdir)
    entries = {int(e["source_task_ordinal"]): e for e in cat_release["entries"]}
    cand_objs = {int(o["source_task_ordinal"]): o for o in cand_root["objects"]}
    mats = {int(m["source_task_ordinal"]): m for m in terminal["matrix_registry"]}
    ownership = None
    if not a.mechanics_only:
        ownership = pd.read_parquet(OWNERSHIP_PANEL)
    manifest = {"schema_version": SCHEMA, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mechanics_only": a.mechanics_only,
                "seven_pack": seven_pack_identity, "catalog_release": cat_rel_id, "candidate_root": cand_root_id, "matrix_terminal": term_id,
                "sampler_sha256": hashlib.sha256((HERE / "prereg098_field_sampler.py").read_bytes()).hexdigest(),
                "runner_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                "ownership_panel_sha256": sha256_file(OWNERSHIP_PANEL) if ownership is not None else None,
                "cells": [registry.matchup_cell_v1(c) for c in CELLS], "admission_cap": registry.MATCHUP_ADMISSION_CAP, "entry_budget": registry.ENTRY_BUDGET,
                "field": {"n": FIELD_N, "ref_field": REF_FIELD, "fracs": FRACS, "min_ownership_mass": MIN_OWNERSHIP_MASS},
                "code": subprocess.run(["git", "-C", str(HERE.parent), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()}
    (results / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=1))
    t0 = time.time(); views = build_views(packs); print(json.dumps({"views_built_seconds": round(time.time() - t0, 1)}), flush=True)
    ordinals = [int(x) for x in a.ordinals.split(",")] if a.ordinals else sorted(entries)
    for o in ordinals:
        out = results / f"slate-{o:02d}-{entries[o]['slate']['slate_id']}.json"
        if out.exists() and not a.force:
            print(json.dumps({"ordinal": o, "skipped": "exists"}), flush=True); continue
        run_slate(o, views=views, workdir=workdir, results=results, catalog_entry=entries[o], candidate_desc=cand_objs[o], matrix_entry=mats[o],
                  ownership=ownership, mechanics_only=a.mechanics_only, seven_pack_identity=seven_pack_identity, keep_matrix=a.keep_matrices)
    return 0


# ----------------------------------------------------------------------------- reader (frozen with the preregistration)
def boot(df: pd.DataFrame, col: str, draws: int = 20_000, seed: int = 47, level: float = 0.9875) -> tuple[float, float]:
    rng = np.random.default_rng(seed); seasons = sorted(df.season.unique()); by = {s: df.loc[df.season == s, col].to_numpy() for s in seasons}
    means = np.array([np.concatenate([by[s] for s in rng.choice(seasons, size=len(seasons), replace=True)]).mean() for _ in range(draws)])
    a = (1 - level) / 2; return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def contrast(w: pd.DataFrame, a: str, b: str, col: str, sign: float, label: str, level: float) -> str:
    d = sign * (w[f"{a}:{col}"] - w[f"{b}:{col}"]); df = pd.DataFrame({"season": w.season, "d": d})
    lo, hi = boot(df, "d", level=level); seasons = {int(s): float(df[df.season == s].d.mean()) for s in sorted(df.season.unique())}
    loso = {int(s): float(df[df.season != s].d.mean()) for s in sorted(df.season.unique())}
    mean = float(d.mean())
    verdict = "PASS" if (lo > 0 and all(v >= 0 for v in seasons.values()) and all(v > 0 for v in loso.values())) else ("NEAR_MISS" if mean > 0 and lo > -abs(mean) / 2 else "NO_EFFECT")
    return f"{label}: {mean:+.5f} [{lo:+.5f}, {hi:+.5f}] W/L/T {(d>0).sum()}/{(d<0).sum()}/{(d==0).sum()} seasons {seasons} LOSO {loso} VERDICT={verdict}"


def main_read(results: pathlib.Path) -> int:
    files = sorted(results.glob("slate-*.json")); rows = []
    for f in files:
        r = json.loads(f.read_text())
        if r.get("mechanics_only"):
            raise SystemExit(f"{f.name} is mechanics-only; the reader needs outcome records")
        row = {"ordinal": r["ordinal"], "season": r["season"], "week": r["week"], "finish": r["finish_available"], "pool_ceiling": r["pool_realized_ceiling_points"]}
        for c in CELLS:
            g = r["cells"][c]["grade"]; inf = r["cells"][c]["stage_influence_vs_control"]
            for k in PREFIXES:
                row[f"{c}:k{k}_max"] = g[f"k{k}"]["weekly_max_points"]
                row[f"{c}:k{k}_neg_best_pct"] = -g[f"k{k}"]["best_pct"] if "best_pct" in g[f"k{k}"] else np.nan
                for t in (194, 200, 220):
                    row[f"{c}:k{k}_ge{t}"] = int(g[f"k{k}"]["thresholds"][str(t)]["max_at_or_above"])
                if "events" in g[f"k{k}"]:
                    for name, v in g[f"k{k}"]["events"].items(): row[f"{c}:k{k}_ev_{name}"] = v
            row[f"{c}:admitted_ceiling"] = g["admitted_realized_ceiling_points"]
            row[f"{c}:k80_jaccard"] = inf["k80"]["jaccard"]; row[f"{c}:k20_jaccard"] = inf["k20"]["jaccard"]; row[f"{c}:adm_jaccard"] = inf["admission"]["jaccard"]
            row[f"{c}:raw_changes"] = inf["components"]["raw_component_value_changes"]; row[f"{c}:edge_changes"] = inf["components"]["edge_score_changes"]
        rows.append(row)
    w = pd.DataFrame(rows).sort_values(["season", "week"]).reset_index(drop=True)
    on_on, off_on, on_off, off_off = CELLS
    print(f"PAID-SOURCE LADDER read: {len(w)} slates, seasons {sorted(w.season.unique())}, finish endpoint available on {int(w.finish.sum())} slates; runner manifest {json.loads((results / 'manifest.json').read_text())['runner_sha256'][:12]}")
    fam = 1 - 0.05 / 4
    print("\nCO-PRIMARY (K20; family level 0.9875; PASS iff interval > 0, every season >= 0, every LOSO > 0):")
    print(contrast(w, on_on, off_on, "k20_max", +1, "points  FP | SIS on ", fam))
    print(contrast(w, on_on, on_off, "k20_max", +1, "points  SIS | FP on ", fam))
    wf = w[w.finish]
    print(contrast(wf, on_on, off_on, "k20_neg_best_pct", +1, "finish  FP | SIS on ", fam))
    print(contrast(wf, on_on, on_off, "k20_neg_best_pct", +1, "finish  SIS | FP on ", fam))
    print("\nSECONDARY conditionals / interaction (K20 points):")
    print(contrast(w, on_off, off_off, "k20_max", +1, "points  FP | SIS off", 0.95))
    print(contrast(w, off_on, off_off, "k20_max", +1, "points  SIS | FP off", 0.95))
    inter = (w[f"{on_on}:k20_max"] - w[f"{off_on}:k20_max"] - w[f"{on_off}:k20_max"] + w[f"{off_off}:k20_max"])
    print(f"interaction (K20 points): {inter.mean():+.4f}; on-on vs off-off {(w[f'{on_on}:k20_max'] - w[f'{off_off}:k20_max']).mean():+.4f}")
    print("\nSECONDARY K40 / K80 (points and finish):")
    for k in (40, 80):
        print(contrast(w, on_on, off_on, f"k{k}_max", +1, f"points  FP | SIS on  K{k}", 0.95)); print(contrast(w, on_on, on_off, f"k{k}_max", +1, f"points  SIS | FP on  K{k}", 0.95))
        print(contrast(wf, on_on, off_on, f"k{k}_neg_best_pct", +1, f"finish  FP | SIS on  K{k}", 0.95)); print(contrast(wf, on_on, on_off, f"k{k}_neg_best_pct", +1, f"finish  SIS | FP on  K{k}", 0.95))
    print("\nLADDER (means per cell; rung 1-2 from the sidecar, rung 3 realized):")
    for c in CELLS:
        print(f"  {c:18s} raw component changes vs control {w[f'{c}:raw_changes'].mean():7.1f} | edge changes {w[f'{c}:edge_changes'].mean():6.1f} | admission jaccard {w[f'{c}:adm_jaccard'].mean():.3f} | K20 jaccard {w[f'{c}:k20_jaccard'].mean():.3f} | K80 jaccard {w[f'{c}:k80_jaccard'].mean():.3f} | K20 max {w[f'{c}:k20_max'].mean():7.2f} | K80 max {w[f'{c}:k80_max'].mean():7.2f} | K20 best_pct {(-wf[f'{c}:k20_neg_best_pct']).mean()*100:.3f}% | weeks K20>=194/200/220 {int(w[f'{c}:k20_ge194'].sum())}/{int(w[f'{c}:k20_ge200'].sum())}/{int(w[f'{c}:k20_ge220'].sum())} | admitted ceiling {w[f'{c}:admitted_ceiling'].mean():7.2f}")
    print(f"  pool realized ceiling mean {w.pool_ceiling.mean():.2f}")
    if wf.shape[0]:
        print("EVENTS per slate (mean, K80): " + " | ".join(f"{c}: top1000 {wf[f'{c}:k80_ev_top1000'].mean():.2f}, top100 {wf[f'{c}:k80_ev_top100'].mean():.3f}, cash {wf[f'{c}:k80_ev_cash'].mean():.1f}" for c in CELLS))
    w.to_csv(results / "read_table.csv", index=False)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--workdir", default="/home/erich/week1-sunday/direct_runner/work"); ap.add_argument("--results", default="/home/erich/week1-sunday/direct_runner/results")
    ap.add_argument("--ordinals", default=""); ap.add_argument("--mechanics-only", action="store_true"); ap.add_argument("--keep-matrices", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--read", default="")
    a = ap.parse_args(argv)
    if a.read:
        return main_read(pathlib.Path(a.read))
    return main_run(a)


if __name__ == "__main__":
    sys.exit(main())
