#!/usr/bin/env python3
"""Run the frozen outcome-viewed CBWU-OI construction diagnostic."""

from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.inference.multiseed_portfolio import (
    combine_cbwu_books,
    combine_cbwu_order_invariant_books,
)

from run_cbwu_seed_order_audit import (
    FORENSIC_MANIFEST_SHA256,
    PLAYER_TABLE,
    PROJECT,
    SOURCE_PANEL_IDS,
    SOURCE_SQL,
    _candidate_batch,
    _download_artifact,
    _parse_gcs,
    _query,
    _upload_create_only,
)
from run_exact_p_generator_constraint_census import _load_corrected_identities


PROTOCOL_PATH = Path(
    "reports/2026-08-15-cbwu-oi-construction-diagnostic-protocol.md"
)
PROTOCOL_SHA256 = (
    "3b458263b165b380e6adf1efdf6ed08fb423c91d6988b5741aa32b11beafe1ec"
)
CBWU_REPORT_PATH = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
IDENTITY_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-p-corrected-identities-v1/result.json"
)
IDENTITY_GENERATION = 1786831245271593
IDENTITY_SHA256 = (
    "ff456093841266cba1b0293dd56b0e2d5089588a61518568706900617eff6ad1"
)
RETAINED_TABLE = (
    f"{PROJECT}.nfl_forensic_review."
    "final_forensic_20260814_candidate_corpus_repair4"
)
OUTPUT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-cbwu-oi-construction-diagnostic-v1/result.json"
)
LINES = (187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0)
STRUCTURE_FIELDS = (
    "salary", "distinct_games", "largest_team_block", "qb_stack_count",
    "bring_back_count", "qb_salary", "rb_salary", "wr_salary",
    "te_salary", "dst_salary",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(lineup) -> tuple[str, ...]:
    return tuple(sorted(str(value) for value in lineup.ids))


def _structure(players: list[dict[str, Any]]) -> dict[str, int]:
    positions = Counter(str(row["pos"]).upper() for row in players)
    if (
        len(players) != 9
        or len({str(row["id"]) for row in players}) != 9
        or set(positions) != {"QB", "RB", "WR", "TE", "DST"}
        or positions["QB"] != 1
        or positions["DST"] != 1
        or positions["RB"] not in (2, 3)
        or positions["WR"] not in (3, 4)
        or positions["TE"] not in (1, 2)
    ):
        raise ValueError("CBWU-OI construction roster shape is illegal")
    salary = sum(int(row["salary"]) for row in players)
    games = {str(row["game_id"]) for row in players if str(row["game_id"])}
    qb = next(row for row in players if str(row["pos"]).upper() == "QB")
    qb_team, qb_opp = str(qb["team"]), str(qb["opp"])
    stack_pos = {"RB", "WR", "TE"}
    skill_teams = Counter(
        str(row["team"]) for row in players
        if str(row["pos"]).upper() != "DST"
    )
    qb_stack = sum(
        str(row["team"]) == qb_team and str(row["pos"]).upper() in stack_pos
        for row in players
    )
    bring_back = sum(
        str(row["team"]) == qb_opp and str(row["pos"]).upper() in stack_pos
        for row in players
    )
    rb_teams = Counter(
        str(row["team"]) for row in players
        if str(row["pos"]).upper() == "RB"
    )
    dst = next(row for row in players if str(row["pos"]).upper() == "DST")
    if (
        not 49_000 <= salary <= 50_000
        or len(games) < 2
        or qb_stack < 2
        or bring_back < 1
        or max(rb_teams.values(), default=0) > 1
        or any(
            str(row["pos"]).upper() == "RB"
            and str(row["team"]) == str(dst["opp"])
            for row in players
        )
    ):
        raise ValueError("CBWU-OI construction roster contract is illegal")
    result = {
        "salary": salary,
        "distinct_games": len(games),
        "largest_team_block": max(skill_teams.values()),
        "qb_stack_count": qb_stack,
        "bring_back_count": bring_back,
    }
    for pos in ("QB", "RB", "WR", "TE", "DST"):
        result[f"{pos.lower()}_salary"] = sum(
            int(row["salary"]) for row in players
            if str(row["pos"]).upper() == pos
        )
    return result


def _pool_static(lineups) -> dict[str, Any]:
    identities = [_identity(lineup) for lineup in lineups]
    if len(identities) != len(set(identities)):
        raise ValueError("CBWU-OI construction pool repeats candidates")
    structures = [_structure(list(lineup.players)) for lineup in lineups]
    pairs = set()
    stack_cores = set()
    for lineup in lineups:
        identity = _identity(lineup)
        pairs.update(combinations(identity, 2))
        qb = next(
            row for row in lineup.players if str(row["pos"]).upper() == "QB"
        )
        teammates = sorted(
            str(row["id"]) for row in lineup.players
            if str(row["team"]) == str(qb["team"])
            and str(row["pos"]).upper() in {"RB", "WR", "TE"}
        )
        stack_cores.update(
            (str(qb["id"]), *pair) for pair in combinations(teammates, 2)
        )
    return {
        "identities": identities,
        "structures": structures,
        "pair_reach": len(pairs),
        "stack_core_reach": len(stack_cores),
    }


def _summarize_structures(rows: list[dict[str, int]]) -> dict[str, dict[str, float]]:
    return {
        field: {
            "mean": float(np.mean([row[field] for row in rows])),
            "median": float(np.median([row[field] for row in rows])),
            "q10": float(np.quantile([row[field] for row in rows], 0.10)),
            "q90": float(np.quantile([row[field] for row in rows], 0.90)),
        }
        for field in STRUCTURE_FIELDS
    }


def _exact_p_static(
    static: dict[str, Any],
    exact_p: tuple[str, ...],
) -> dict[str, Any]:
    pset = set(exact_p)
    distances = np.asarray([
        9 - len(pset & set(roster)) for roster in static["identities"]
    ], dtype=int)
    minimum = int(distances.min())
    represented = set().union(*(set(row) for row in static["identities"]))
    return {
        "minimum_swaps_to_exact_p": minimum,
        "equally_closest_candidates": int(np.sum(distances == minimum)),
        "closest_identities": [
            list(static["identities"][index])
            for index in np.flatnonzero(distances == minimum)
        ],
        "exact_p_player_slots_represented": len(pset & represented),
        "pair_reach": int(static["pair_reach"]),
        "stack_core_reach": int(static["stack_core_reach"]),
        "structure": _summarize_structures(static["structures"]),
    }


def _score_pool(
    static: dict[str, Any],
    actuals: dict[str, float],
    exact_p_static: dict[str, Any],
) -> dict[str, Any]:
    scores = np.asarray([
        sum(actuals[player] for player in roster)
        for roster in static["identities"]
    ], dtype=float)
    if scores.size == 0 or not np.isfinite(scores).all():
        raise ValueError("CBWU-OI construction candidate scores are invalid")
    best = int(np.argmax(scores))
    best_score = float(scores[best])
    best_indices = np.flatnonzero(scores == best_score)
    return {
        "c_score": best_score,
        "c_identity": list(static["identities"][best]),
        "c_tie_count": int(len(best_indices)),
        "c_tied_identities": [
            list(static["identities"][index]) for index in best_indices
        ],
        **exact_p_static,
    }


def run(output_uri: str) -> dict[str, Any]:
    if output_uri != OUTPUT_URI:
        raise RuntimeError("CBWU-OI construction output differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("CBWU-OI construction code/image identity is required")
    if _sha256(PROTOCOL_PATH) != PROTOCOL_SHA256 or (
        _sha256(CBWU_REPORT_PATH) != CBWU_REPORT_SHA256
    ):
        raise RuntimeError("CBWU-OI construction protocol/source report differs")
    scorefree = json.loads(CBWU_REPORT_PATH.read_text(encoding="utf-8"))
    if scorefree.get("aggregate", {}).get("passes_scorefree_gate") is not True:
        raise RuntimeError("CBWU-OI score-free source did not pass")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = _query(bq, SOURCE_SQL, [bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SOURCE_PANEL_IDS),
    )])
    players = _query(bq, f"""
        SELECT manifest_sha256, season, week, player_id, player_name,
               position, team, opponent, game_id, salary, mean_projection
        FROM `{PLAYER_TABLE}`
        WHERE scope = 'phase-s-cbwu-54'
        ORDER BY season, week, player_id
    """)
    retained = _query(bq, f"""
        SELECT season, week, candidate_index, roster_ordered, tag
        FROM `{RETAINED_TABLE}`
        WHERE scope = 'phase-s-cbwu-54'
        ORDER BY season, week, candidate_index
    """)
    exact_p, _receipt = _load_corrected_identities(
        gcs, uri=IDENTITY_URI, generation=IDENTITY_GENERATION,
        sha256=IDENTITY_SHA256,
    )
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("CBWU-OI construction player manifest differs")
    if set(sources.panel_run_id.astype(str)) != set(SOURCE_PANEL_IDS):
        raise RuntimeError("CBWU-OI construction source panel set differs")
    source_keys = sources[["panel_run_id", "season", "week"]].drop_duplicates()
    if len(source_keys) != 270:
        raise RuntimeError("CBWU-OI construction source population differs")
    slates = sorted({
        (int(row.season), int(row.week)) for row in source_keys.itertuples()
    })
    if len(slates) != 54:
        raise RuntimeError("CBWU-OI construction slate population differs")
    exact_p_keys = sorted(zip(
        exact_p.season.astype(int), exact_p.week.astype(int), strict=True,
    ))
    if exact_p_keys != slates:
        raise RuntimeError("CBWU-OI construction exact-P population differs")

    static_rows = []
    artifact_receipts = []
    for season, week in slates:
        catalog = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        books = {}
        for seed, panel_id in enumerate(SOURCE_PANEL_IDS):
            group = sources[
                sources.panel_run_id.astype(str).eq(panel_id)
                & sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            uris = group.score_artifact_uri.astype(str).unique()
            digests = group.score_artifact_sha256.astype(str).unique()
            if group.empty or len(uris) != 1 or len(digests) != 1:
                raise RuntimeError("CBWU-OI construction source identity differs")
            artifact, receipt = _download_artifact(gcs, uris[0], digests[0])
            books[f"R{seed}"] = _candidate_batch(group, artifact, catalog)
            artifact_receipts.append({
                "seed": seed, "panel_run_id": panel_id, "season": season,
                "week": week, "candidate_rows": len(group), **receipt,
            })
        canonical = combine_cbwu_books(
            books, tuple(books), expected_worlds_per_book=10_000,
        )
        canonical_static = _pool_static(canonical.candidates)
        frozen = retained[
            retained.season.astype(int).eq(season)
            & retained.week.astype(int).eq(week)
        ].sort_values("candidate_index", kind="stable")
        frozen_ids = [
            tuple(sorted(value for value in str(raw).split(",") if value))
            for raw in frozen.roster_ordered
        ]
        if frozen_ids != canonical_static["identities"]:
            raise RuntimeError("canonical CBWU retained identities differ")
        expected_tags = []
        for lineup in canonical.candidates:
            seed_tags = [
                tag.split(":", 1)[1]
                for tag in canonical.all_tags[lineup.ids]
                if tag.startswith("candidate_seed:")
            ]
            if len(seed_tags) != 1:
                raise RuntimeError("canonical CBWU seed attribution differs")
            expected_tags.append(f"CBWU_{seed_tags[0]}")
        if frozen.tag.astype(str).tolist() != expected_tags:
            raise RuntimeError("canonical CBWU retained tags differ")

        rotations = tuple(
            tuple(books)[offset:] + tuple(books)[:offset] for offset in range(5)
        )
        oi_batches = [
            combine_cbwu_order_invariant_books(
                books, rotation, expected_worlds_per_book=10_000,
            )
            for rotation in rotations
        ]
        oi_static = _pool_static(oi_batches[0].candidates)
        if any(
            _pool_static(batch.candidates)["identities"]
            != oi_static["identities"]
            or not np.array_equal(
                np.asarray(batch.candidate_totals),
                np.asarray(oi_batches[0].candidate_totals),
            )
            for batch in oi_batches[1:]
        ):
            raise RuntimeError("CBWU-OI construction rotation differs")
        frozen_budget = len(books["R0"].candidates)
        if (
            len(canonical.candidates) != frozen_budget
            or len(oi_batches[0].candidates) != frozen_budget
        ):
            raise RuntimeError("CBWU-OI construction candidate budget differs")
        p_row = exact_p[
            exact_p.season.astype(int).eq(season)
            & exact_p.week.astype(int).eq(week)
        ]
        if len(p_row) != 1:
            raise RuntimeError("CBWU-OI construction exact-P slate differs")
        p_identity = tuple(str(p_row.iloc[0].players).split(","))
        if len(p_identity) != 9 or len(set(p_identity)) != 9:
            raise RuntimeError("CBWU-OI construction exact-P identity differs")
        catalog_by_id = {
            str(row.player_id): {
                "id": str(row.player_id),
                "pos": str(row.position),
                "team": str(row.team),
                "opp": str(row.opponent),
                "game_id": str(row.game_id),
                "salary": int(row.salary),
            }
            for row in catalog.itertuples(index=False)
        }
        if set(p_identity) - set(catalog_by_id):
            raise RuntimeError("CBWU-OI construction exact-P player differs")
        _structure([catalog_by_id[player] for player in p_identity])
        canonical_p_static = _exact_p_static(canonical_static, p_identity)
        oi_p_static = _exact_p_static(oi_static, p_identity)
        static_rows.append({
            "season": season,
            "week": week,
            "canonical_candidate_budget": len(canonical.candidates),
            "cbwu_oi_candidate_budget": len(oi_batches[0].candidates),
            "frozen_r0_candidate_budget": frozen_budget,
            "complete_union_candidates": int(
                oi_batches[0].metadata["complete_union_candidates"]
            ),
            "pool_identity_overlap": len(
                set(canonical_static["identities"])
                & set(oi_static["identities"])
            ),
            "exact_p": p_identity,
            "canonical_static": canonical_static,
            "oi_static": oi_static,
            "canonical_p_static": canonical_p_static,
            "oi_p_static": oi_p_static,
        })

    # Outcomes are deliberately queried only after every identity, legality,
    # source, retained-pool and rotation gate above has passed.
    actual_frame = _query(bq, f"""
        SELECT season, week, player_id, actual_score
        FROM `{PLAYER_TABLE}`
        WHERE scope = 'phase-s-cbwu-54'
        ORDER BY season, week, player_id
    """)
    records = []
    for row in static_rows:
        frame = actual_frame[
            actual_frame.season.astype(int).eq(row["season"])
            & actual_frame.week.astype(int).eq(row["week"])
        ]
        if frame.player_id.astype(str).duplicated().any():
            raise RuntimeError("CBWU-OI construction actual-score IDs repeat")
        scores = pd.to_numeric(frame.actual_score, errors="raise").astype(float)
        if not np.isfinite(scores).all():
            raise RuntimeError("CBWU-OI construction actual scores are invalid")
        actuals = dict(zip(frame.player_id.astype(str), scores, strict=True))
        needed = set().union(
            *(set(value) for value in row["canonical_static"]["identities"]),
            *(set(value) for value in row["oi_static"]["identities"]),
            set(row["exact_p"]),
        )
        if needed - set(actuals):
            raise RuntimeError("CBWU-OI construction actual-score join differs")
        canonical = _score_pool(
            row["canonical_static"], actuals, row["canonical_p_static"],
        )
        treatment = _score_pool(
            row["oi_static"], actuals, row["oi_p_static"],
        )
        records.append({
            "season": row["season"], "week": row["week"],
            "canonical_candidate_budget": row["canonical_candidate_budget"],
            "cbwu_oi_candidate_budget": row["cbwu_oi_candidate_budget"],
            "frozen_r0_candidate_budget": row["frozen_r0_candidate_budget"],
            "complete_union_candidates": row["complete_union_candidates"],
            "pool_identity_overlap": row["pool_identity_overlap"],
            "exact_p_identity": list(row["exact_p"]),
            "exact_p_score": float(sum(actuals[p] for p in row["exact_p"])),
            "canonical": canonical,
            "cbwu_oi": treatment,
            "c_score_delta": treatment["c_score"] - canonical["c_score"],
        })

    aggregate = {
        "slates": 54,
        "candidate_budget_equal_all_slates": all(
            row["canonical_candidate_budget"]
            == row["cbwu_oi_candidate_budget"]
            == row["frozen_r0_candidate_budget"]
            and row["frozen_r0_candidate_budget"] > 80
            for row in records
        ),
        "mean_candidate_budget": float(np.mean([
            row["frozen_r0_candidate_budget"] for row in records
        ])),
        "mean_complete_union_candidates": float(np.mean([
            row["complete_union_candidates"] for row in records
        ])),
        "mean_pool_identity_overlap": float(np.mean([
            row["pool_identity_overlap"] for row in records
        ])),
        "mean_c_score": {
            "canonical": float(np.mean([
                row["canonical"]["c_score"] for row in records
            ])),
            "cbwu_oi": float(np.mean([
                row["cbwu_oi"]["c_score"] for row in records
            ])),
        },
        "c_tail_counts": {
            str(int(line)): {
                "canonical": int(sum(
                    row["canonical"]["c_score"] >= line for row in records
                )),
                "cbwu_oi": int(sum(
                    row["cbwu_oi"]["c_score"] >= line for row in records
                )),
            }
            for line in LINES
        },
        "c_score_paired_signs": {
            "positive": int(sum(row["c_score_delta"] > 0 for row in records)),
            "zero": int(sum(row["c_score_delta"] == 0 for row in records)),
            "negative": int(sum(row["c_score_delta"] < 0 for row in records)),
        },
        "mean_minimum_swaps_to_exact_p": {
            "canonical": float(np.mean([
                row["canonical"]["minimum_swaps_to_exact_p"] for row in records
            ])),
            "cbwu_oi": float(np.mean([
                row["cbwu_oi"]["minimum_swaps_to_exact_p"] for row in records
            ])),
        },
    }
    report = {
        "version": "cbwu-oi-construction-diagnostic-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "corrected_identity_source": {
            "uri": IDENTITY_URI, "generation": IDENTITY_GENERATION,
            "sha256": IDENTITY_SHA256,
        },
        "cbwu_oi_scorefree_report_sha256": CBWU_REPORT_SHA256,
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_artifacts": artifact_receipts,
        "uses_realized_candidate_scores": True,
        "scores_cbwu_oi_selected_80": False,
        "historical_arm_licensed": False,
        "production_change_licensed": False,
        "aggregate": aggregate,
        "records": records,
        "consequence": (
            "outcome-viewed construction diagnosis only; cannot score or "
            "promote the CBWU-OI selected book"
        ),
    }
    payload = (json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode()
    report["output"] = _upload_create_only(gcs, output_uri, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    result = run(args.output_uri)
    print(json.dumps({
        "version": result["version"],
        "aggregate": result["aggregate"],
        "output": result["output"],
        "historical_arm_licensed": result["historical_arm_licensed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
