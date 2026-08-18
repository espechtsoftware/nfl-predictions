#!/usr/bin/env python3
"""One-shot B2': volume-scaled OI admission at the registered budget.

Protocol: reports/2026-08-18-b2prime-volume-oi-admission-protocol.md
(SHA-256 b3cbf2505e2c253bf2e9f500e28cb3ad65bc609b93ec660023b8c431c89e3512).
Member of the authorized offseason one-shot family. `--smoke SEASON WEEK`
runs the outcome-blind mechanics on one slate and prints admission
composition only.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
# Script-to-script imports need scripts/ on sys.path under BOTH
# invocation modes: as a file (parent dir) and as injected -c
# source (cwd-relative scripts/).
_scripts_dir = (_Path(__file__).parent if "__file__" in globals()
                else _Path("scripts"))
_sys.path.insert(0, str(_scripts_dir.resolve()))

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.optimizer.lineup import select_tail_entries
from run_b1_union_c_census import ALL_PANELS, FAMILIES
from run_cbwu_seed_order_audit import _download_artifact

PROJECT = "nfl-predictions-503414"
PROTOCOL = Path("reports/2026-08-18-b2prime-volume-oi-admission-protocol.md")
PROTOCOL_SHA = "b3cbf2505e2c253bf2e9f500e28cb3ad65bc609b93ec660023b8c431c89e3512"
MONEY_PANELS = FAMILIES["atlas-money-worlds"]
SOURCE_GRID = Path(
    "reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/"
    "source-grid.json")
SOURCE_GRID_SHA = "9a18458c63f0155b72f3847c705fbd0bdde9b64c923a5b63cc4a1f42bfe3445b"
CANONICAL_PANEL = MONEY_PANELS[0]
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
TAIL_LINE = 194.0
ARM_KS = (5, 10, 20, 51)
CACHE = Path.home() / "nfl-panels" / "b2prime-artifact-cache"


def arm_books(k: int) -> list[str]:
    rest = [p for p in sorted(ALL_PANELS) if p not in MONEY_PANELS]
    return (MONEY_PANELS + rest)[:k]


def load_frozen() -> None:
    for path, want in ((PROTOCOL, PROTOCOL_SHA), (SOURCE_GRID, SOURCE_GRID_SHA)):
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != want:
            raise SystemExit(f"frozen input differs: {path} {got}")


def slate_worlds(gcs, grid, season: int, week: int):
    """Concatenated 5-block production-law draws + player-row index."""
    blocks, order = [], None
    for panel in MONEY_PANELS:
        cells = [c for c in grid if c["panel_run_id"] == panel
                 and int(c["season"]) == season and int(c["week"]) == week]
        if not cells:
            continue  # r3 2025-W1 recovery: four blocks by convention
        raw = CACHE / f"{panel}-{season}-{week}.npz"
        if raw.exists():
            data = np.load(raw, allow_pickle=True)
            ids = [str(v) for v in data["player_ids"]]
            draws = data["player_draws"]
        else:
            artifact, _ = _download_artifact(
                gcs, str(cells[0]["score_artifact_uri"]),
                str(cells[0]["score_artifact_sha256"]))
            ids = [str(v) for v in np.asarray(artifact["player_ids"])]
            draws = np.asarray(artifact["player_draws"], dtype=np.float32)
            CACHE.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(raw, player_ids=np.array(ids), player_draws=draws)
        if order is None:
            order = ids
        elif ids != order:
            index = {p: i for i, p in enumerate(ids)}
            draws = draws[[index[p] for p in order]]
        blocks.append(draws)
    return order, np.concatenate(blocks, axis=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", nargs=2, type=int, metavar=("SEASON", "WEEK"))
    args = parser.parse_args()
    load_frozen()
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    grid = json.loads(SOURCE_GRID.read_text())

    cand = bq.query(
        f"""SELECT panel_run_id, season, week, players, actual_score
        FROM `{PROJECT}.nfl_predictions.replay_candidates_staging`
        WHERE panel_run_id IN UNNEST(@panels)""",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("panels", "STRING", sorted(ALL_PANELS))]),
    ).result().to_dataframe(create_bqstorage_client=False)
    catalog = bq.query(
        f"""SELECT season, week, id, pos, salary, proj_tourney
        FROM `{PROJECT}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = @p""",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("p", "STRING", CANONICAL_PANEL)]),
    ).result().to_dataframe(create_bqstorage_client=False)

    from run_b1_union_c_census import main as _unused  # noqa: F401  (import parity)

    info_by_slate = {}
    for (season, week), g in catalog.groupby(["season", "week"]):
        info_by_slate[(int(season), int(week))] = {
            "salary": dict(zip(g.id.astype(str), g.salary.astype(int))),
            "pos": dict(zip(g.id.astype(str), g.pos.astype(str))),
            "proj": dict(zip(g.id.astype(str), g.proj_tourney.astype(float))),
        }

    def legal(ids, info):
        if len(ids) != 9 or len(set(ids)) != 9:
            return False
        if any(i not in info["salary"] for i in ids):
            return False
        if not 0 < sum(info["salary"][i] for i in ids) <= 50_000:
            return False
        shape = Counter(info["pos"][i].upper() for i in ids)
        return (shape.get("QB") == 1 and shape.get("DST") == 1
                and 2 <= shape.get("RB", 0) <= 3
                and 3 <= shape.get("WR", 0) <= 4
                and 1 <= shape.get("TE", 0) <= 2
                and sum(shape.get(x, 0) for x in ("RB", "WR", "TE")) == 7)

    budgets = Counter()
    rosters_by_slate: dict[tuple, dict[tuple, dict]] = {}
    for row in cand.itertuples(index=False):
        key = (int(row.season), int(row.week))
        info = info_by_slate.get(key)
        if info is None:
            continue
        raw = row.players
        ids = tuple(sorted(str(v) for v in (
            raw if not isinstance(raw, str) else raw.split(",")) if str(v)))
        if not legal(ids, info):
            continue
        slot = rosters_by_slate.setdefault(key, {})
        entry = slot.setdefault(ids, {"panels": set(), "actual": float(row.actual_score)})
        entry["panels"].add(row.panel_run_id)
        if row.panel_run_id == CANONICAL_PANEL:
            budgets[key] += 1

    slates = ([tuple(args.smoke)] if args.smoke else sorted(rosters_by_slate))
    arms = {k: {"c": [], "s": [], "admitted_src": Counter()} for k in ARM_KS}
    per_slate_rows = []
    for key in slates:
        season, week = key
        info = info_by_slate[key]
        order, draws = slate_worlds(gcs, grid, season, week)
        row_of = {p: i for i, p in enumerate(order)}
        static = {p: info["proj"].get(p, 0.0) for p in info["proj"]}
        slot = rosters_by_slate[key]
        all_ids = sorted(slot)
        totals = np.empty((len(all_ids), draws.shape[1]), dtype=np.float32)
        for ix, ids in enumerate(all_ids):
            rows = [row_of[p] for p in ids if p in row_of]
            base = draws[rows].sum(axis=0) if rows else 0.0
            const = sum(static.get(p, 0.0) for p in ids if p not in row_of)
            totals[ix] = base + const
        budget = budgets[key]
        if budget <= 0:
            raise SystemExit(f"no registered budget for {key}")
        slate_row = {"season": season, "week": week, "budget": budget,
                     "union": len(all_ids)}
        for k in ARM_KS:
            books = set(arm_books(k))
            member = [ix for ix, ids in enumerate(all_ids)
                      if slot[ids]["panels"] & books]
            sub = totals[member]
            take = min(budget, len(member))
            admitted_ix = select_tail_entries(
                sub, take, TAIL_LINE, env={"SELECT_LSE": "0"})
            admitted = [member[i] for i in admitted_ix]
            sel_ix = select_tail_entries(
                totals[admitted], min(80, len(admitted)), TAIL_LINE,
                env={"SELECT_LSE": "0"})
            selected = [admitted[i] for i in sel_ix]
            slate_row[f"k{k}_pool"] = len(member)
            if args.smoke:
                slate_row[f"k{k}_admitted"] = len(admitted)
                continue
            c_val = max(slot[all_ids[ix]]["actual"] for ix in admitted)
            s_val = max(slot[all_ids[ix]]["actual"] for ix in selected)
            arms[k]["c"].append(c_val)
            arms[k]["s"].append(s_val)
            slate_row[f"k{k}_c"] = c_val
            slate_row[f"k{k}_s"] = s_val
            for ix in admitted:
                for p in sorted(slot[all_ids[ix]]["panels"]):
                    arms[k]["admitted_src"][p] += 1
                    break
        per_slate_rows.append(slate_row)
        print(json.dumps(slate_row))

    if args.smoke:
        return
    report = {"protocol_sha256": PROTOCOL_SHA, "arms": {}}
    base_c = np.array(arms[5]["c"])
    for k in ARM_KS:
        c = np.array(arms[k]["c"]); s = np.array(arms[k]["s"])
        report["arms"][str(k)] = {
            "mean_c": float(c.mean()), "mean_s": float(s.mean()),
            "grid_c": {str(t): int((c >= t).sum()) for t in THRESHOLDS},
            "grid_s": {str(t): int((s >= t).sum()) for t in THRESHOLDS},
            "mcnemar_194_vs_k5": [
                int(((c >= 194) & (base_c < 194)).sum()),
                int(((base_c >= 194) & (c < 194)).sum())],
            "mcnemar_210_vs_k5": [
                int(((c >= 210) & (base_c < 210)).sum()),
                int(((base_c >= 210) & (c < 210)).sum())],
            "admitted_sources": dict(arms[k]["admitted_src"].most_common(8)),
        }
    out = Path("reports/b2prime-runs/20260818-b2prime-volume-oi-v1")
    out.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"report": report, "slates": per_slate_rows}, indent=2, sort_keys=True)
    (out / "report.json").write_text(payload)
    (out / "report.sha256").write_text(
        hashlib.sha256(payload.encode()).hexdigest() + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
