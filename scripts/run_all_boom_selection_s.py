#!/usr/bin/env python3
"""All-boom SELECTION follow-up (S endpoint): does the boom-deep pool
improve the actual 80-lineup book?

The C arm (20260819-all-boom-reallocation-c-v1) proved the reallocation
raises the pool ceiling (+9.06 mean, 43/54) at the exact registered
budget — and its protocol licensed exactly one follow-up: an S endpoint
under the unchanged production selector. This runner measures it. Per
slate and per seed pair it rebuilds BOTH books:

- control: the ATLAS C control path verbatim — dose-zero regeneration
  plus verbatim role injection, gated by exact source reproduction
  against the registered natives;
- treatment: the all-boom path verbatim — CAND_MULT=0 / N_BOOM=200 /
  BOOM_UNIQUE_FILL=1, truncated to the native non-role count with role
  natives appended (identical candidate budget).

Both arms then run the UNCHANGED production selection
(combine_cbwu_books five-book union at the fixed budget,
select_tail_entries exact-80 at line 194) and one outcome read scores
the selected books. Cross-run binding gates: the control C and S must
reproduce the ATLAS C attempt-2 receipts and the treatment pool C must
reproduce the all-boom v1 receipts, both to 1e-6 — three frozen runs,
one shared truth. The winner-overlap mechanism gate reports each
selected book's best overlap with the slate's tracked Milly winner
against the exposure-preserving chance null (anatomy A instrument).

Smoke mode is outcome-blind: full generation, reproduction checks,
combination, exact-80 selection and receipt serialization run; no
actuals query is issued and no score is computed.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_all_boom_reallocation_c as ab  # noqa: E402
import run_atlas_minimal_world_selection_c as base  # noqa: E402

from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books  # noqa: E402
from nfl_dfs.optimizer.lineup import select_tail_entries  # noqa: E402
from nfl_dfs.research.real_winner_overlap import _book_overlap  # noqa: E402

VERSION = "all-boom-selection-s-v1"
RUN_ID = "20260819-all-boom-selection-s-v1"
PROTOCOL_SHA256 = "608740fda3b39e2c56b40ba76c68eb69ba52033374b8624a5bbee7a0621d99f4"
PROJECT = "nfl-predictions-503414"
ATLAS_CELLS = (
    ROOT / "reports/atlas-minimal-c-runs"
    / "20260818-atlas-minimal-world-selection-c-v1-attempt-2/cells"
)
ALLBOOM_CELLS = (
    ROOT / "reports/all-boom-reallocation-c-runs"
    / "20260819-all-boom-reallocation-c-v1/cells"
)
N1C_REPORT = (
    ROOT / "reports/winner-law-audit-runs"
    / "20260819-winner-world-optima-v1-report.json"
)
REPRODUCTION_ATOL = 1e-6
OVERLAP_NULL_REPS = 500
OVERLAP_SEED = 8163


def _expected_cell(cells_dir: Path, season: int, week: int) -> dict:
    path = cells_dir / f"slate-{season}-{week}.json"
    if not path.is_file():
        raise RuntimeError(f"pinned expectation missing: {path}")
    return json.loads(path.read_text())


def _winner_rosters() -> dict[tuple[int, int], list[str]]:
    report = json.loads(N1C_REPORT.read_text())
    return {
        (int(w["season"]), int(w["week"])): [
            str(p) for p in w["roster_ids"]
        ]
        for w in report["winners"]
    }


def _select_identities(
    batches: dict[str, base.CandidateBatch],
) -> tuple[list[tuple[str, ...]], Any]:
    """The unchanged production selection, returning roster identities.

    Mirrors base._score_books' selection calls exactly; the caller must
    verify the recomputed S equals the canonical one so this capture can
    never drift from the scored path.
    """
    combined = combine_cbwu_books(
        batches, tuple(batches),
        expected_worlds_per_book=base.WORLDS_PER_ARTIFACT,
    )
    picked = select_tail_entries(
        combined.candidate_totals, 80, base.TAIL_LINE,
        env={"SELECT_LSE": "0"},
    )
    identities = [
        base._identity(combined.candidates[index]) for index in picked
    ]
    if len(identities) != 80:
        raise RuntimeError(
            f"all-boom S selection returned {len(identities)} lineups")
    return identities, combined


def _selected_overlap(
    identities: list[tuple[str, ...]], winner_ids: list[str],
) -> dict:
    frame = pd.DataFrame(
        {"players": [",".join(identity) for identity in identities]})
    rng = np.random.default_rng(OVERLAP_SEED)
    return _book_overlap(frame, winner_ids, rng, OVERLAP_NULL_REPS)


def _require_close(label: str, got: float, want: float) -> None:
    if abs(float(got) - float(want)) > REPRODUCTION_ATOL:
        raise RuntimeError(
            f"all-boom S {label} differs from the pinned receipt: "
            f"{got!r} vs {want!r}")


def run(season: int, week: int, output_uri: str, smoke: bool) -> dict:
    base.validate_frozen_inputs()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not smoke and (
        not re.fullmatch(r"[0-9a-f]{40}", code_sha)
        or not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image)
    ):
        raise RuntimeError(
            "all-boom S needs CODE_SHA and an immutable ANALYSIS_IMAGE")
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
        "treatment_levers": dict(ab.TREATMENT_LEVERS),
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
        treatment_env = ab._treatment_env(
            block, season, code_sha or "0" * 40)
        ab._validate_lever_env_except_treatment(cell, treatment_env)
        panel_natives = natives[
            natives.panel_run_id.astype(str).eq(panel)].copy()
        if panel_natives.empty:
            raise RuntimeError(f"all-boom S natives missing for {panel}")
        snapshot = snapshots[
            snapshots.panel_run_id.astype(str).eq(panel)].copy()
        if snapshot.empty:
            raise RuntimeError(f"all-boom S snapshot missing for {panel}")
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
        reproduction = base._reproduction_check(
            control, item["panel_natives"], item["artifact"])
        control_batches[f"R{item['block']}"] = control
        item["reproduction"] = reproduction

    treatment_batches: dict[str, base.CandidateBatch] = {}
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
                "all-boom S arm budgets differ: control "
                f"{len(control.candidates)} vs treatment "
                f"{len(treatment.candidates)}")
        treatment_batches[f"R{item['block']}"] = treatment
        receipt["seeds"].append({
            "block": item["block"],
            "panel_run_id": item["panel"],
            "artifact": item["art_receipt"],
            "reproduction": item["reproduction"],
            "native_count": int(len(item["ordered"])),
            "treatment_count": int(len(treatment.candidates)),
            "shortfall": int(shortfall),
            "boom_uniques": int(sum(
                1 for c in treatment.candidates if c.tag == "boom")),
        })

    # Exact-80 selection runs in every mode; only scoring reads outcomes.
    selections: dict[str, list[tuple[str, ...]]] = {}
    if not recovery_slate:
        for arm, batches in (
            ("control", control_batches), ("treatment", treatment_batches),
        ):
            identities, _ = _select_identities(batches)
            selections[arm] = identities
        overlap_ids = set(map(tuple, selections["control"])) \
            & set(map(tuple, selections["treatment"]))
        receipt["selected_book_intersection"] = len(overlap_ids)

    if not smoke:
        native_actuals = _query(bq, base.NATIVE_ACTUALS_SQL, params)
        player_actuals = _query(bq, base.PLAYER_ACTUALS_SQL, params)
        if player_actuals.id.astype(str).duplicated().any():
            raise RuntimeError("all-boom S player actuals are not unique")
        actuals = {
            str(row["id"]): float(row["actual"])
            for _, row in player_actuals.iterrows()
        }
        receipt["actual_parity_max_delta"] = base._actual_parity(
            native_actuals, actuals)
        receipt["control"] = base._score_books(control_batches, actuals)
        receipt["treatment"] = base._score_books(treatment_batches, actuals)

        # The identity capture must reproduce the canonical S exactly.
        for arm in selections:
            recomputed = max(
                sum(actuals[p] for p in identity)
                for identity in selections[arm]
            )
            _require_close(
                f"{arm} S identity-capture", recomputed,
                receipt[arm]["s_score"])

        expected_atlas = _expected_cell(ATLAS_CELLS, season, week)
        _require_close(
            "control C vs ATLAS receipt",
            receipt["control"]["c_score"],
            expected_atlas["control"]["c_score"])
        if expected_atlas["control"].get("s_score") is not None:
            _require_close(
                "control S vs ATLAS receipt",
                receipt["control"]["s_score"],
                expected_atlas["control"]["s_score"])
        expected_allboom = _expected_cell(ALLBOOM_CELLS, season, week)
        _require_close(
            "treatment C vs all-boom receipt",
            receipt["treatment"]["c_score"],
            expected_allboom["treatment"]["c_score"])
        receipt["cross_run_reproduction"] = True

        if receipt["control"]["s_score"] is not None:
            receipt["paired_delta_s"] = (
                receipt["treatment"]["s_score"]
                - receipt["control"]["s_score"])
        receipt["paired_delta_c"] = (
            receipt["treatment"]["c_score"]
            - receipt["control"]["c_score"])

        winner = _winner_rosters().get((season, week))
        if winner is not None and selections:
            receipt["winner_overlap"] = {
                arm: _selected_overlap(selections[arm], winner)
                for arm in selections
            }

    # Serialize on EVERY path (2026-08-19 canary lesson): smoke must
    # exercise the full receipt contract; only the upload stays gated.
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
        "selected_book_intersection": receipt.get(
            "selected_book_intersection"),
        "paired_delta_s": receipt.get("paired_delta_s"),
        "cross_run_reproduction": receipt.get("cross_run_reproduction"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
