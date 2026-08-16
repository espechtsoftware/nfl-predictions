#!/usr/bin/env python3
"""Run one frozen score-free ATLAS matched-diversity MVP season."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re

import numpy as np
from google.cloud import bigquery, storage

from nfl_dfs.analysis.atlas_matched_diversity import (
    REGISTERED_SEEDS,
    build_structural_clusters,
    conditional_interaction_coverage,
    enumerate_matched_diversity_lineups,
    price_native_interactions,
    replace_native_boom_book,
    summarize_candidate_and_exact80,
)
from nfl_dfs.analysis.atlas_world_ranking import (
    rank_worlds,
    roster_slot_upper_bound,
    solve_exact_worlds,
)
from nfl_dfs.inference.multiseed_portfolio import (
    combine_cbwu_books,
    combine_cbwu_order_invariant_books,
)
from nfl_dfs.optimizer.lineup import StackRules

from run_cbwu_seed_order_audit import (
    _candidate_batch,
    _download_artifact,
    _query,
    _upload_create_only,
)


PROJECT = "nfl-predictions-503414"
SOURCE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
SOURCE_PANELS = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
REPAIR_PANEL = "20260816-atlas-mvp-repair-r3-2025-v1"
PROTOCOL = Path("reports/2026-08-16-atlas-matched-diversity-mvp-protocol.md")
PROTOCOL_SHA256 = (
    "badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf"
)
PAIR_REACH_AMENDMENT = Path(
    "reports/2026-08-16-atlas-mvp-pair-reach-amendment.md"
)
PAIR_REACH_AMENDMENT_SHA256 = (
    "2e3734c595159d64748ab2eeec2de61194b665d43ef6854140e5378bac464a33"
)
TRANSFER_REPORT = Path(
    "reports/atlas-money-transfer-runs/"
    "20260815-atlas-current-money-transfer-v1/report.json"
)
TRANSFER_REPORT_SHA256 = (
    "8e568f8e5e343319ab4e4f48421b41f3266e56ecb592abce77f3ed6d246cd446"
)
CBWU_REPORT = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
REPAIR_VALIDATION = Path(
    "reports/atlas-mvp-source-repair-runs/"
    "20260816-atlas-mvp-source-repair-r3-2025-v1/validation.json"
)
REPAIR_VALIDATION_SHA256 = (
    "4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37"
)
REPAIR_EXECUTION = REPAIR_VALIDATION.with_name("execution.json")
REPAIR_EXECUTION_SHA256 = (
    "f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7"
)
REPAIR_COMPLETION = REPAIR_VALIDATION.with_name("completion.txt")
REPAIR_COMPLETION_SHA256 = (
    "7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592"
)
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    "20260816-atlas-matched-diversity-mvp-v1"
)
SOURCE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags, players,
       score_artifact_uri, score_artifact_sha256
FROM `{SOURCE_TABLE}`
WHERE (
  panel_run_id IN UNNEST(@source_panels)
  AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1)
) OR (
  panel_run_id=@repair_panel AND season=2025 AND week=1
)
ORDER BY panel_run_id, season, week, cand_ix
"""
PLAYER_SQL = f"""
SELECT season, week, id AS player_id, name AS player_name, pos AS position,
       team, opp AS opponent, game_id, salary, proj AS mean_projection
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season=@season
ORDER BY season, week, player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual_score", "actual_rank", "actual_ownership", "actual ",
    "selected_rank", "selected ", "payout", "contest_rank",
    "labels_complete",
)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_local_sources() -> dict:
    expected = {
        str(PROTOCOL): PROTOCOL_SHA256,
        str(PAIR_REACH_AMENDMENT): PAIR_REACH_AMENDMENT_SHA256,
        str(TRANSFER_REPORT): TRANSFER_REPORT_SHA256,
        str(CBWU_REPORT): CBWU_REPORT_SHA256,
        str(REPAIR_VALIDATION): REPAIR_VALIDATION_SHA256,
        str(REPAIR_EXECUTION): REPAIR_EXECUTION_SHA256,
        str(REPAIR_COMPLETION): REPAIR_COMPLETION_SHA256,
    }
    for raw_path, digest in expected.items():
        path = Path(raw_path)
        if not path.is_file() or _file_sha(path) != digest:
            raise RuntimeError(f"ATLAS MVP source differs: {path}")
    transfer = json.loads(TRANSFER_REPORT.read_text(encoding="utf-8"))
    cbwu = json.loads(CBWU_REPORT.read_text(encoding="utf-8"))
    repair = json.loads(REPAIR_VALIDATION.read_text(encoding="utf-8"))
    repair_execution = json.loads(REPAIR_EXECUTION.read_text(encoding="utf-8"))
    repair_completion = dict(
        line.rstrip("\n").split("=", 1)
        for line in REPAIR_COMPLETION.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    if transfer.get("gate", {}).get("passes_original_all_six") is not True or \
            cbwu.get("aggregate", {}).get("passes_scorefree_gate") is not True or \
            repair.get("valid") is not True or \
            any(source.get("uses_realized_outcomes") is not False
                for source in (transfer, cbwu, repair)):
        raise RuntimeError("ATLAS MVP source disposition differs")
    terminal = [
        row for row in repair_execution.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"
    ]
    if len(terminal) != 1 or terminal[0].get("status") != "True" or \
            repair_completion.get("disposition") != "valid-mvp-source" or \
            repair_completion.get("uses_realized_outcomes") != "false":
        raise RuntimeError("ATLAS MVP repair execution/completion differs")
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    if present:
        raise RuntimeError(
            "ATLAS MVP query contains forbidden fields: " + ", ".join(present)
        )
    return expected


def _source_params():
    return [
        bigquery.ArrayQueryParameter("source_panels", "STRING", list(SOURCE_PANELS)),
        bigquery.ScalarQueryParameter("r3_panel", "STRING", SOURCE_PANELS[3]),
        bigquery.ScalarQueryParameter("repair_panel", "STRING", REPAIR_PANEL),
    ]


def _player_params(season: int):
    return [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", SOURCE_PANELS[0]),
        bigquery.ScalarQueryParameter("season", "INT64", season),
    ]


def _canonical_panel(panel: str) -> str:
    return SOURCE_PANELS[3] if panel == REPAIR_PANEL else panel


def _top_jaccard(left: dict, right: dict) -> float:
    a, b = set(left["top_20_players"]), set(right["top_20_players"])
    return float(len(a & b) / len(a | b)) if a or b else 1.0


def _run_slate(season: int, week: int, books, artifact_receipts) -> dict:
    # These shared transports perform the complete native total/player-world
    # reconstruction preflight before any expensive ATLAS solve begins.
    p0 = combine_cbwu_books(
        books, REGISTERED_SEEDS, expected_worlds_per_book=10_000,
    )
    p1 = combine_cbwu_order_invariant_books(
        books, REGISTERED_SEEDS, expected_worlds_per_book=10_000,
    )
    pricing = price_native_interactions(books)
    nonboom = []
    for seed in REGISTERED_SEEDS:
        nonboom.extend(
            lineup for lineup in books[seed].candidates
            if str(lineup.tag) != "boom"
        )
    stack = StackRules(qb_stack_min=2, bring_back_min=1)
    env = {"MIN_LINEUP_SALARY": "49000"}
    treatment_books = {}
    construction = {}
    global_atlas: set[frozenset] = set()
    for seed in REGISTERED_SEEDS:
        native = books[seed]
        positions = [str(row.get("pos", "")) for row in native.player_rows]
        bound = roster_slot_upper_bound(native.row_draws, positions)
        world_order = rank_worlds(bound, 40)
        exact = solve_exact_worlds(
            native.player_rows, native.row_draws, world_order,
            stack=stack, env=env,
        )
        clusters = build_structural_clusters(world_order, exact)
        additions, enumeration = enumerate_matched_diversity_lineups(
            player_rows=native.player_rows, row_draws=native.row_draws,
            clusters=clusters, exact_worlds=exact,
            interaction_weights=pricing["weights_by_source"][seed],
            nonboom_lineups=nonboom, prior_atlas_rosters=global_atlas,
            stack=stack, env=env,
        )
        identities = {lineup.ids for lineup in additions}
        if len(identities) != 40 or identities & global_atlas:
            raise RuntimeError("ATLAS MVP per-seed/global count differs")
        global_atlas.update(identities)
        treatment_books[seed] = replace_native_boom_book(native, additions)
        construction[seed] = {
            "pricing": pricing["receipts"][seed],
            "clusters": clusters,
            "exact_top40": {str(world): exact[world] for world in world_order},
            "enumeration": enumeration,
        }
    if len(global_atlas) != 200:
        raise RuntimeError("ATLAS MVP global addition count differs")

    p2 = combine_cbwu_order_invariant_books(
        treatment_books, REGISTERED_SEEDS, expected_worlds_per_book=10_000,
    )
    summaries = {
        name: summarize_candidate_and_exact80(batch)
        for name, batch in (("P0", p0), ("P1", p1), ("P2", p2))
    }
    interaction = {
        name: [
            conditional_interaction_coverage(batch.candidates, pricing, seed)
            for seed in REGISTERED_SEEDS
        ] for name, batch in (("P1", p1), ("P2", p2))
    }
    return {
        "season": season,
        "week": week,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "native_candidate_counts": {
            seed: len(books[seed].candidates) for seed in REGISTERED_SEEDS
        },
        "native_boom_counts": {
            seed: sum(str(row.tag) == "boom" for row in books[seed].candidates)
            for seed in REGISTERED_SEEDS
        },
        "global_atlas_additions": len(global_atlas),
        "artifact_receipts": artifact_receipts,
        "construction": construction,
        "interaction_coverage": interaction,
        "top20_player_jaccard_P1_P2": {
            "candidate": _top_jaccard(
                summaries["P1"]["candidate_structure"],
                summaries["P2"]["candidate_structure"],
            ),
            "exact80": _top_jaccard(
                summaries["P1"]["exact80_structure"],
                summaries["P2"]["exact80_structure"],
            ),
        },
        **summaries,
    }


def run(season: int, output_uri: str) -> dict:
    if season not in {2023, 2024, 2025} or output_uri != (
        f"{OUTPUT_PREFIX}/season-{season}.json"
    ):
        raise RuntimeError("ATLAS MVP season/output identity differs")
    source_hashes = validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("ATLAS MVP code/image identity is required")
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = _query(bq, SOURCE_SQL, _source_params())
    players = _query(bq, PLAYER_SQL, _player_params(season))
    sources = sources[sources.season.astype(int).eq(season)].copy()
    keys = sources[["panel_run_id", "season", "week"]].drop_duplicates()
    if len(keys) != 90 or sorted(keys.week.astype(int).unique()) != list(range(1, 19)):
        raise RuntimeError("ATLAS MVP season source grid differs")
    rows = []
    for week in range(1, 19):
        catalog = players[players.week.astype(int).eq(week)].copy()
        books = {}
        artifact_receipts = []
        for seed, expected_panel in zip(REGISTERED_SEEDS, SOURCE_PANELS, strict=True):
            group = sources[
                sources.week.astype(int).eq(week)
                & sources.panel_run_id.astype(str).map(_canonical_panel).eq(expected_panel)
            ].copy()
            uris = group.score_artifact_uri.astype(str).unique()
            digests = group.score_artifact_sha256.astype(str).unique()
            if group.empty or len(uris) != 1 or len(digests) != 1:
                raise RuntimeError("ATLAS MVP native source identity differs")
            artifact, receipt = _download_artifact(gcs, uris[0], digests[0])
            books[seed] = _candidate_batch(group, artifact, catalog)
            artifact_receipts.append({
                "seed": seed, "source_panel": str(group.panel_run_id.iloc[0]),
                "canonical_panel": expected_panel, "candidate_rows": len(group),
                **receipt,
            })
        rows.append(_run_slate(season, week, books, artifact_receipts))
        print("ATLAS_MVP_SLATE_COMPLETE", season, week, flush=True)
    payload = {
        "version": "atlas-matched-diversity-mvp-v1",
        "uses_realized_outcomes": False,
        "season": season,
        "code_sha": code_sha,
        "analysis_image": image,
        "source_hashes": source_hashes,
        "slates": rows,
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("ATLAS_MVP_SEASON_RESULT " + json.dumps(upload, sort_keys=True))
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.season, args.output_uri)


if __name__ == "__main__":
    main()
