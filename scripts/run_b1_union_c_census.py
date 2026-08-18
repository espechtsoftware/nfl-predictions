#!/usr/bin/env python3
"""One-shot all-arms union-C census with order-statistic null (frozen B1).

Protocol: reports/2026-08-18-b1-union-c-census-protocol.md
(SHA-256 2d1cb29bda5fc25965661acb891566bd8e9daf108bb579ad9eca99d862c29789).
Diagnostic-only; licenses nothing.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

PROJECT = "nfl-predictions-503414"
PROTOCOL = Path("reports/2026-08-18-b1-union-c-census-protocol.md")
PROTOCOL_SHA = "2d1cb29bda5fc25965661acb891566bd8e9daf108bb579ad9eca99d862c29789"
CANONICAL_PANEL = "20260815-atlas-money-worlds-r0-v1"
FAMILIES = {  # homogeneous same-generator seed families
    "game-team-k": [f"20260813-game-team-k-r{i}-v1" for i in range(5)],
    "game-team-mult": [f"20260813-game-team-mult-r{i}-v1" for i in range(5)],
    "sis-asoe-control": [f"20260813-sis-asoe-control-r{i}-v1" for i in range(5)],
    "sis-asoe-treatment": [f"20260813-sis-asoe-treatment-r{i}-v1" for i in range(5)],
    "sis-pass-tail-control": [f"20260814-sis-pass-tail-control-r{i}-v1" for i in range(5)],
    "sis-pass-tail-treatment": [f"20260814-sis-pass-tail-treatment-r{i}-v1" for i in range(5)],
    "atlas-money-worlds": [f"20260815-atlas-money-worlds-r{i}-v1" for i in range(5)],
    "incumbent-mcseed": [f"20260813-incumbent-mcseed-r{i}-v1" for i in range(1, 5)],
}
SINGLES = [
    "20260811-lockfix-e80-k1-role12-poscal-usage-control-v1",
    "20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1",
    "20260811-lockfix-e80-k1-role12-position-control-v1",
    "20260811-lockfix-e80-k1-role12-position-scales-v1",
    "20260811-lockfix-e80-k1-role12-tail1025-v1",
    "20260812-pitclean-e80-active-label-usage-multinomial-v1",
    "20260812-pitclean-e80-selected-position-control-v2",
    "20260812-pitclean-e80-selected-position-scales-v2",
    "20260812-pitclean-e80-selected-tabpfn-active-v2",
    "20260812-pitclean-e80-selected-tabpfn-current-v2",
    "20260812-pitclean-e80-selected-usage-control-v2",
    "20260812-pitclean-e80-selected-usage-fitted-v2",
]
ALL_PANELS = sorted(set(sum(FAMILIES.values(), SINGLES.copy())))
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
R_SUBSAMPLES = 200
K_GRID = (1, 2, 5, 10, 20)
RNG_SEED = 20260818


def main() -> None:
    digest = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    if digest != PROTOCOL_SHA:
        raise SystemExit(f"protocol hash differs: {digest}")
    bq = bigquery.Client(project=PROJECT)
    cand = bq.query(
        f"""
        SELECT panel_run_id, season, week, players, actual_score
        FROM `{PROJECT}.nfl_predictions.replay_candidates_staging`
        WHERE panel_run_id IN UNNEST(@panels)
        """,
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("panels", "STRING", ALL_PANELS)]),
    ).result().to_dataframe(create_bqstorage_client=False)
    catalog = bq.query(
        f"""
        SELECT season, week, id, pos, salary
        FROM `{PROJECT}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = @panel
        """,
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("panel", "STRING", CANONICAL_PANEL)]),
    ).result().to_dataframe(create_bqstorage_client=False)

    slate_info: dict[tuple[int, int], dict] = {}
    for (season, week), group in catalog.groupby(["season", "week"]):
        slate_info[(int(season), int(week))] = {
            "salary": dict(zip(group.id.astype(str), group.salary.astype(int))),
            "pos": dict(zip(group.id.astype(str), group.pos.astype(str))),
        }

    def valid(ids: tuple[str, ...], info: dict) -> bool:
        if len(ids) != 9 or len(set(ids)) != 9:
            return False
        if any(i not in info["salary"] for i in ids):
            return False
        if not 0 < sum(info["salary"][i] for i in ids) <= 50_000:
            return False
        shape = Counter(info["pos"][i].upper() for i in ids)
        return (shape.get("QB") == 1 and shape.get("DST") == 1
                and 2 <= shape.get("RB", 0) <= 3 and 3 <= shape.get("WR", 0) <= 4
                and 1 <= shape.get("TE", 0) <= 2
                and shape.get("RB", 0) + shape.get("WR", 0) + shape.get("TE", 0) == 7)

    # per-slate: {roster_ids: (score, first_panel)}; per-panel drop counts
    per_slate: dict[tuple[int, int], dict] = defaultdict(dict)
    panel_books: dict[tuple[int, int], dict[str, dict]] = defaultdict(dict)
    drops: Counter = Counter()
    for row in cand.itertuples(index=False):
        key = (int(row.season), int(row.week))
        info = slate_info.get(key)
        if info is None:
            continue
        raw = row.players
        parts = tuple(sorted(
            str(v) for v in (raw if not isinstance(raw, str) else raw.split(","))
            if str(v)
        ))
        if not valid(parts, info):
            drops[row.panel_run_id] += 1
            continue
        score = float(row.actual_score)
        entry = per_slate[key].get(parts)
        if entry is None or score > entry[0]:
            per_slate[key][parts] = (score, row.panel_run_id)
        panel_books[key].setdefault(row.panel_run_id, {})[parts] = score

    slates = sorted(per_slate)
    union_max = {key: max(s for s, _ in per_slate[key].values()) for key in slates}
    maxima = np.array([union_max[k] for k in slates])
    attribution = Counter(
        max(per_slate[k].items(), key=lambda kv: kv[1][0])[1][1] for k in slates
    )

    rng = np.random.default_rng(RNG_SEED)
    hom_pool = [p for family in FAMILIES.values() for p in family]

    def curve(panel_pool: list[str], hetero: bool) -> dict:
        out = {}
        for k in K_GRID:
            if k > len(panel_pool):
                continue
            means = []
            for _ in range(R_SUBSAMPLES):
                if hetero:
                    pick = list(rng.choice(panel_pool, size=k, replace=False))
                else:
                    fam = FAMILIES[rng.choice(list(FAMILIES))]
                    if k > len(fam):
                        pick = fam + list(rng.choice(
                            [p for p in panel_pool if p not in fam],
                            size=k - len(fam), replace=False))
                    else:
                        pick = list(rng.choice(fam, size=k, replace=False))
                vals = []
                for key in slates:
                    books = panel_books[key]
                    scores = [
                        v for p in pick if p in books for v in books[p].values()
                    ]
                    if scores:
                        vals.append(max(scores))
                means.append(float(np.mean(vals)))
            arr = np.array(means)
            out[str(k)] = {
                "mean": float(arr.mean()),
                "q25": float(np.quantile(arr, 0.25)),
                "q75": float(np.quantile(arr, 0.75)),
            }
        return out

    report = {
        "protocol_sha256": PROTOCOL_SHA,
        "panels": len(ALL_PANELS),
        "slates": len(slates),
        "union_mean_c": float(maxima.mean()),
        "union_grid": {
            str(t): int((maxima >= t).sum()) for t in THRESHOLDS
        },
        "references": {"canonical_c": 181.07, "cbwu_oi_c": 186.73},
        "distinct_rosters_total": int(sum(len(v) for v in per_slate.values())),
        "drops_per_panel": dict(drops),
        "slate_max_attribution": dict(attribution.most_common()),
        "growth_curves": {
            "heterogeneous": curve(ALL_PANELS, hetero=True),
            "homogeneous": curve(hom_pool, hetero=False),
        },
        "labels": {
            "uses_realized_outcomes": True,
            "diagnostic_only": True,
            "licenses_adoption": False,
        },
    }
    out_path = Path(
        "reports/b1-union-c-census-runs/20260818-b1-union-c-census-v1")
    out_path.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True)
    (out_path / "report.json").write_text(payload)
    (out_path / "report.sha256").write_text(
        hashlib.sha256(payload.encode()).hexdigest() + "\n")
    print(json.dumps({
        "union_mean_c": report["union_mean_c"],
        "union_grid": report["union_grid"],
        "distinct_rosters": report["distinct_rosters_total"],
        "slates": report["slates"],
    }, indent=2))


if __name__ == "__main__":
    main()
