#!/usr/bin/env python3
"""Offline synthetic harness for the default-off LR8 historical arm.

This runner intentionally refuses non-synthetic inputs.  It exercises the
fit, construction, and later-period evaluator contracts without BigQuery,
GCS, Cloud Run, shared leases, or real outcomes.  A separate source-locked
transport is required before the registered one-shot historical arm can run.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import residual_world_columns as rw  # noqa: E402
from nfl_dfs.research.lr8_historical_arm import (  # noqa: E402
    AnatomyTrainingRow,
    FrozenBookCell,
    LaterPeriodScoreRow,
    LR8Error,
    canonical_json,
    evaluate_frozen_later_period_once,
    fit_soft_anatomy_law,
    mechanics_payload,
    run_lr8_mechanics,
)


def _keys(value: object, expected: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise LR8Error(f"{label} fields differ")
    return value


def load_canonical(path: Path) -> object:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LR8Error("LR8 input is invalid JSON") from exc
    if canonical_json(value) != raw:
        raise LR8Error("LR8 input is not canonical JSON")
    return value


def write_create_only(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)


def _base(value: object, *, schema: str, expected: set[str]) -> dict[str, Any]:
    payload = _keys(value, expected | {"schema", "synthetic_fixture"}, label=schema)
    if payload["schema"] != schema or payload["synthetic_fixture"] is not True:
        raise LR8Error("offline LR8 runner accepts only its exact synthetic schema")
    return payload


def _fit(value: object) -> dict[str, object]:
    payload = _base(
        value,
        schema="lr8-soft-anatomy-fit-synthetic-v1",
        expected={"rows"},
    )
    rows = []
    if not isinstance(payload["rows"], list):
        raise LR8Error("synthetic training rows must be a list")
    for index, raw in enumerate(payload["rows"]):
        row = _keys(
            raw,
            {"season", "week", "features", "realized_total_micro"},
            label=f"training row {index}",
        )
        if not isinstance(row["features"], list):
            raise LR8Error("synthetic training features must be a list")
        rows.append(AnatomyTrainingRow(
            season=row["season"],
            week=row["week"],
            features=tuple(row["features"]),
            realized_total_micro=row["realized_total_micro"],
        ))
    return fit_soft_anatomy_law(rows)


def _proposal_plan(value: object, fold: str) -> tuple[tuple[str, ...] | None, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise LR8Error(f"fold {fold} proposal plan must contain 1..8 rows")
    plan: list[tuple[str, ...] | None] = []
    seen_null = False
    for item in value:
        if item is None:
            if seen_null:
                raise LR8Error(f"fold {fold} proposal plan repeats null")
            seen_null = True
            plan.append(None)
            continue
        if seen_null:
            raise LR8Error(f"fold {fold} proposal plan continues after first null")
        if not isinstance(item, list):
            raise LR8Error(f"fold {fold} proposal is not a roster")
        plan.append(tuple(item))
    if len(plan) < 8 and not seen_null:
        raise LR8Error(f"fold {fold} short proposal plan lacks terminal null")
    return tuple(plan)


def _mechanics(value: object) -> dict[str, object]:
    payload = _base(
        value,
        schema="lr8-historical-mechanics-synthetic-v1",
        expected={
            "season", "week", "slate_id", "players", "world_ids",
            "player_draws", "incumbent_candidates", "anatomy_artifact",
            "fold_proposals",
        },
    )
    players = payload["players"]
    if not isinstance(players, list):
        raise LR8Error("synthetic player catalog must be a list")
    for index, player in enumerate(players):
        _keys(
            player, {"id", "pos", "team", "opp", "game_id", "salary"},
            label=f"player {index}",
        )
    raw_worlds = payload["world_ids"]
    if not isinstance(raw_worlds, list):
        raise LR8Error("synthetic world ids must be a list")
    worlds = []
    for index, raw in enumerate(raw_worlds):
        row = _keys(raw, {"block", "index"}, label=f"world {index}")
        worlds.append(rw.WorldId(row["block"], row["index"]))
    candidates = payload["incumbent_candidates"]
    if not isinstance(candidates, list) or any(
        not isinstance(roster, list) for roster in candidates
    ):
        raise LR8Error("synthetic incumbent candidates must be nested lists")
    proposals = _keys(
        payload["fold_proposals"], {"A", "B"}, label="fold proposals"
    )
    plans = {fold: _proposal_plan(proposals[fold], fold) for fold in ("A", "B")}
    positions = {"A": 0, "B": 0}

    def pricing(fold: str):
        def next_proposal(request):
            if request.fold_name != fold:
                raise AssertionError("pricing request crossed folds")
            index = positions[fold]
            if index >= len(plans[fold]):
                raise LR8Error(f"fold {fold} pricing consumed an incomplete plan")
            positions[fold] += 1
            return plans[fold][index]
        return next_proposal

    result = run_lr8_mechanics(
        season=payload["season"],
        week=payload["week"],
        slate_id=payload["slate_id"],
        players=players,
        world_ids=worlds,
        raw_player_draws=np.asarray(payload["player_draws"], dtype=np.float32),
        incumbent_candidates=candidates,
        anatomy_artifact=payload["anatomy_artifact"],
        pricing_steps={"A": pricing("A"), "B": pricing("B")},
    )
    report = mechanics_payload(result)
    report["synthetic_fixture"] = True
    report["mocked_pricing_proposals"] = True
    report["report_sha256"] = __import__(
        "hashlib"
    ).sha256(canonical_json({
        key: item for key, item in report.items() if key != "report_sha256"
    })).hexdigest()
    return report


def _evaluate(value: object) -> dict[str, object]:
    payload = _base(
        value,
        schema="lr8-later-period-evaluation-synthetic-v1",
        expected={"book_cells", "score_rows", "attempt_identity"},
    )
    if not isinstance(payload["book_cells"], list) or not isinstance(
        payload["score_rows"], list
    ):
        raise LR8Error("synthetic evaluation rows must be lists")
    cells = []
    for index, raw in enumerate(payload["book_cells"]):
        row = _keys(raw, {
            "season", "week", "fold_name", "candidate_budget_control",
            "candidate_budget_treatment", "control_candidates",
            "treatment_candidates", "control_book", "treatment_book",
            "freeze_sha256",
        }, label=f"book cell {index}")
        cells.append(FrozenBookCell(
            season=row["season"],
            week=row["week"],
            fold_name=row["fold_name"],
            candidate_budget_control=row["candidate_budget_control"],
            candidate_budget_treatment=row["candidate_budget_treatment"],
            control_candidates=tuple(
                tuple(roster) for roster in row["control_candidates"]
            ),
            treatment_candidates=tuple(
                tuple(roster) for roster in row["treatment_candidates"]
            ),
            control_book=tuple(tuple(roster) for roster in row["control_book"]),
            treatment_book=tuple(tuple(roster) for roster in row["treatment_book"]),
            freeze_sha256=row["freeze_sha256"],
        ))
    scores = []
    for index, raw in enumerate(payload["score_rows"]):
        row = _keys(
            raw, {"season", "week", "roster", "realized_total_micro"},
            label=f"score row {index}",
        )
        scores.append(LaterPeriodScoreRow(
            season=row["season"],
            week=row["week"],
            roster=tuple(row["roster"]),
            realized_total_micro=row["realized_total_micro"],
        ))
    report = evaluate_frozen_later_period_once(
        cells, scores, attempt_identity=payload["attempt_identity"]
    )
    report["synthetic_fixture"] = True
    report["report_sha256"] = __import__(
        "hashlib"
    ).sha256(canonical_json({
        key: item for key, item in report.items() if key != "report_sha256"
    })).hexdigest()
    return report


def run_payload(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LR8Error("LR8 synthetic input must be an object")
    schema = value.get("schema")
    if schema == "lr8-soft-anatomy-fit-synthetic-v1":
        return _fit(value)
    if schema == "lr8-historical-mechanics-synthetic-v1":
        return _mechanics(value)
    if schema == "lr8-later-period-evaluation-synthetic-v1":
        return _evaluate(value)
    raise LR8Error("LR8 synthetic input schema differs")


def run(input_path: Path, output_path: Path | None = None) -> dict[str, object]:
    report = run_payload(load_canonical(input_path))
    raw = canonical_json(report)
    if output_path is not None:
        write_create_only(output_path, raw)
    return report


def _local_path(raw: str, *, label: str) -> Path:
    if "://" in raw:
        raise LR8Error(f"{label} must be a local path")
    return Path(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="canonical synthetic JSON")
    parser.add_argument("--output", help="optional create-only local JSON")
    args = parser.parse_args()
    report = run(
        _local_path(args.input, label="input"),
        _local_path(args.output, label="output") if args.output else None,
    )
    print(canonical_json({
        "schema": report.get("schema", report.get("version")),
        "protocol_id": report.get("protocol_id"),
        "synthetic_fixture": report.get("synthetic_fixture", True),
        "production_change_licensed": report.get(
            "production_change_licensed", False
        ),
    }).decode("utf-8"))


if __name__ == "__main__":
    main()
