#!/usr/bin/env python3
"""Stack-relaxation carved-budget arm (A3): do open solves reach the
winners' shape region, and does the book score?

Operator-approved direction (2026-08-19: "I'm in favor of relaxing
them"; carve size delegated and decided at k=8 absolute per seed). Per
slate and per seed pair this runner rebuilds the control book via the
ATLAS reproduction path (exact source reproduction gate) and a treatment
book identical except for ONE lever: OPEN_BOOM_SOLVES=8 — eight of the
boom visits at a deterministic stride solve without the QB-stack and
bring-back minima (RB prohibitions and salary bounds unchanged). Both
arms run the unchanged production exact-80 selection and one outcome
read scores the books.

Mechanism gates (the census made them quantitative): the carve must
actually produce open-shaped candidates (structure census of open-tagged
rosters against the winner-mode region: stack <=1 / no bring-back /
concentration <=3), and the selected books report the winner-overlap-
versus-chance instrument. A score gain without mechanism is volume, not
aim, and says so in the receipt.

Smoke mode is outcome-blind: generation, reproduction and budget gates,
open-candidate census, exact-80 selection, and receipt serialization
run; no actuals query is issued.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_all_boom_reallocation_c as ab  # noqa: E402
import run_all_boom_selection_s as sarm  # noqa: E402
import run_atlas_minimal_world_selection_c as base  # noqa: E402

from nfl_dfs.analysis.winner_structure_census import (  # noqa: E402
    roster_structure,
    structure_census,
)

VERSION = "stack-relaxation-carve-v1"
RUN_ID = "20260819-stack-relaxation-carve-v1"
PROTOCOL_SHA256 = "3bc1ace97dc0eb5120a16e961aad2d84f4258f008c1f3a9da8a7f5c80866e7bf"
PROJECT = "nfl-predictions-503414"
TREATMENT_LEVERS = {"OPEN_BOOM_SOLVES": "8"}


def _treatment_env(block: int, season: int, code_sha: str) -> dict[str, str]:
    env = base._generation_env(block, season, code_sha)
    env.update(TREATMENT_LEVERS)
    return env


def _validate_lever_env_except_treatment(
    cell: dict, env: dict[str, str],
) -> None:
    """Acquisition-record parity on every key EXCEPT the one predeclared
    treatment lever, whose treatment value is asserted."""
    recorded = dict(
        item.split("=", 1)
        for item in re.split(
            r",(?=[A-Z][A-Z0-9_]*=)", str(cell["lever_env"]))
        if "=" in item
    )
    mismatched = {
        key: (value, env.get(key, ""))
        for key, value in recorded.items()
        if key not in TREATMENT_LEVERS and str(env.get(key, "")) != value
    }
    if mismatched:
        raise RuntimeError(
            "stack-carve reconstructed environment differs from the "
            f"acquisition record: {sorted(mismatched)}")
    for key, value in TREATMENT_LEVERS.items():
        if str(env.get(key, "")) != value:
            raise RuntimeError(f"stack-carve treatment lever differs: {key}")


def _slate_structure_maps(slate) -> tuple[dict, dict, dict]:
    pos_of = dict(zip(slate.id.astype(str), slate.pos.astype(str).str.upper()))
    team_of = dict(zip(slate.id.astype(str), slate.team.astype(str)))
    opp_of = dict(zip(slate.id.astype(str), slate.opp.astype(str)))
    return pos_of, team_of, opp_of


def _open_census(batch, slate) -> dict:
    """Structure census of the carve's open-tagged rosters."""
    pos_of, team_of, opp_of = _slate_structure_maps(slate)
    structures = []
    for roster, tags in batch.all_tags.items():
        if "open" not in tags:
            continue
        structures.append(
            roster_structure(sorted(roster), pos_of, team_of, opp_of))
    if not structures:
        return {"n": 0}
    census = structure_census(structures)
    census["n_outside_mandate"] = int(sum(
        1 for s in structures
        if s["qb_stack"] < 2 or s["bring_back"] < 1))
    return census


def run(season: int, week: int, output_uri: str, smoke: bool) -> dict:
    base.validate_frozen_inputs()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not smoke and (
        not re.fullmatch(r"[0-9a-f]{40}", code_sha)
        or not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image)
    ):
        raise RuntimeError(
            "stack-carve needs CODE_SHA and an immutable ANALYSIS_IMAGE")
    from google.cloud import bigquery, storage
    from run_cbwu_seed_order_audit import (
        _download_artifact, _query, _upload_create_only,
    )

    grid = json.loads(base.SOURCE_GRID.read_text())
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    params = [
        bigquery.ArrayQueryParameter(
            "panel_ids", "STRING", list(base.SOURCE_PANEL_IDS)),
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
    ]
    natives = _query(bq, base.NATIVE_SQL, params)
    snapshots = _query(bq, base.SNAPSHOT_SQL, params)

    receipt: dict[str, Any] = {
        "version": VERSION,
        "run_id": RUN_ID,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "treatment_levers": dict(TREATMENT_LEVERS),
        "smoke": bool(smoke),
        "uses_realized_outcomes": not smoke,
        "production_change_licensed": False,
        "seeds": [],
    }
    recovery_slate = (season, week) == base.RECOVERY_CELL[1:]
    blocks = [0, 1, 2, 4] if recovery_slate else list(range(5))
    if recovery_slate:
        receipt["recovery_four_seed_slate"] = True

    prepared: list[dict] = []
    for block in blocks:
        panel = base.SOURCE_PANEL_IDS[block]
        cell = base._grid_cell(grid, panel, season, week)
        control_env = base._generation_env(
            block, season, code_sha or "0" * 40)
        base._validate_lever_env(cell, control_env)
        treatment_env = _treatment_env(block, season, code_sha or "0" * 40)
        _validate_lever_env_except_treatment(cell, treatment_env)
        panel_natives = natives[
            natives.panel_run_id.astype(str).eq(panel)].copy()
        if panel_natives.empty:
            raise RuntimeError(f"stack-carve natives missing for {panel}")
        snapshot = snapshots[
            snapshots.panel_run_id.astype(str).eq(panel)].copy()
        if snapshot.empty:
            raise RuntimeError(f"stack-carve snapshot missing for {panel}")
        artifact, art_receipt = _download_artifact(
            gcs, str(cell["score_artifact_uri"]),
            str(cell["score_artifact_sha256"]))
        slate = base._slate_frame(
            snapshot, np.asarray(artifact["player_ids"]))
        draws = np.asarray(artifact["player_draws"], dtype=np.float64)
        ordered = panel_natives.sort_values("cand_ix", kind="stable")
        role_identities = [
            frozenset(v for v in str(row["players"]).split(",") if v)
            for _, row in ordered.iterrows()
            if str(row["tag"]) == "epi"
        ]
        prepared.append({
            "block": block, "panel": panel,
            "control_env": control_env, "treatment_env": treatment_env,
            "slate": slate, "draws": draws, "artifact": artifact,
            "art_receipt": art_receipt, "panel_natives": panel_natives,
            "ordered": ordered, "role_identities": role_identities,
        })

    control_batches: dict[str, base.CandidateBatch] = {}
    for item in prepared:
        control = base._inject_role_natives(
            base._generate(
                item["slate"], item["draws"], item["control_env"],
                treatment=False,
                role_identities=item["role_identities"]),
            item["panel_natives"], item["slate"], item["artifact"])
        item["reproduction"] = base._reproduction_check(
            control, item["panel_natives"], item["artifact"])
        control_batches[f"R{item['block']}"] = control

    treatment_batches: dict[str, base.CandidateBatch] = {}
    total_open = 0
    for item in prepared:
        generated = base._generate(
            item["slate"], item["draws"], item["treatment_env"],
            treatment=False,
            role_identities=item["role_identities"])
        treatment, shortfall = ab._budget_and_roles(
            generated, item["ordered"], item["slate"], item["artifact"])
        control = control_batches[f"R{item['block']}"]
        if len(treatment.candidates) != len(control.candidates):
            raise RuntimeError(
                "stack-carve arm budgets differ: control "
                f"{len(control.candidates)} vs treatment "
                f"{len(treatment.candidates)}")
        open_census = _open_census(treatment, item["slate"])
        total_open += int(open_census.get("n", 0))
        treatment_batches[f"R{item['block']}"] = treatment
        receipt["seeds"].append({
            "block": item["block"],
            "panel_run_id": item["panel"],
            "artifact": item["art_receipt"],
            "reproduction": item["reproduction"],
            "native_count": int(len(item["ordered"])),
            "treatment_count": int(len(treatment.candidates)),
            "shortfall": int(shortfall),
            "open_census": open_census,
        })
    # Vacuity gate: a carve that produces no surviving open candidates
    # anywhere is a dead lever and must fail loudly, not report a score.
    if total_open == 0:
        raise RuntimeError("stack-carve produced zero open candidates")
    receipt["open_candidates_total"] = int(total_open)

    selections: dict[str, list[tuple[str, ...]]] = {}
    if not recovery_slate:
        for arm, batches in (
            ("control", control_batches), ("treatment", treatment_batches),
        ):
            identities, _ = sarm._select_identities(batches)
            selections[arm] = identities
        receipt["selected_book_intersection"] = len(
            set(map(tuple, selections["control"]))
            & set(map(tuple, selections["treatment"])))
        # How much of the carve reached the BOOK (not just the pool)?
        open_rosters = {
            frozenset(r)
            for batch in treatment_batches.values()
            for r, tags in batch.all_tags.items() if "open" in tags
        }
        receipt["open_selected_count"] = int(sum(
            1 for identity in selections["treatment"]
            if frozenset(identity) in open_rosters))

    if not smoke:
        native_actuals = _query(bq, base.NATIVE_ACTUALS_SQL, params)
        player_actuals = _query(bq, base.PLAYER_ACTUALS_SQL, params)
        if player_actuals.id.astype(str).duplicated().any():
            raise RuntimeError("stack-carve player actuals are not unique")
        actuals = {
            str(row["id"]): float(row["actual"])
            for _, row in player_actuals.iterrows()
        }
        receipt["actual_parity_max_delta"] = base._actual_parity(
            native_actuals, actuals)
        receipt["control"] = base._score_books(control_batches, actuals)
        receipt["treatment"] = base._score_books(treatment_batches, actuals)
        for arm in selections:
            recomputed = max(
                sum(actuals[p] for p in identity)
                for identity in selections[arm]
            )
            sarm._require_close(
                f"{arm} S identity-capture", recomputed,
                receipt[arm]["s_score"])
        expected_atlas = sarm._expected_cell(
            sarm.ATLAS_CELLS, season, week)
        sarm._require_close(
            "control C vs ATLAS receipt",
            receipt["control"]["c_score"],
            expected_atlas["control"]["c_score"])
        if expected_atlas["control"].get("s_score") is not None:
            sarm._require_close(
                "control S vs ATLAS receipt",
                receipt["control"]["s_score"],
                expected_atlas["control"]["s_score"])
        receipt["cross_run_reproduction"] = True
        if receipt["control"].get("s_score") is not None:
            receipt["paired_delta_s"] = (
                receipt["treatment"]["s_score"]
                - receipt["control"]["s_score"])
        receipt["paired_delta_c"] = (
            receipt["treatment"]["c_score"]
            - receipt["control"]["c_score"])
        winner = sarm._winner_rosters().get((season, week))
        if winner is not None and selections:
            receipt["winner_overlap"] = {
                arm: sarm._selected_overlap(selections[arm], winner)
                for arm in selections
            }

    # Serialize on EVERY path; only the upload stays gated (canary lesson).
    payload = json.dumps(
        receipt, sort_keys=True, separators=(",", ":")).encode()
    if not smoke:
        receipt["upload"] = _upload_create_only(gcs, output_uri, payload)
    return receipt


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    receipt = run(args.season, args.week, args.output_uri, args.smoke)
    print(json.dumps({
        "run_id": receipt["run_id"],
        "season": receipt["season"],
        "week": receipt["week"],
        "smoke": receipt["smoke"],
        "seeds": len(receipt["seeds"]),
        "open_candidates_total": receipt.get("open_candidates_total"),
        "open_selected_count": receipt.get("open_selected_count"),
        "selected_book_intersection": receipt.get(
            "selected_book_intersection"),
        "paired_delta_s": receipt.get("paired_delta_s"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
