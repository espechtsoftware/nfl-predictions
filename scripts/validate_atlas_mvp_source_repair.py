#!/usr/bin/env python3
"""Strict array, roster and legality validation for the ATLAS MVP repair."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json

import numpy as np

from nfl_dfs.research.atlas_mvp_source_repair import (
    ORIGINAL_ARTIFACT_SHA256,
)


ALLOWED_TAGS = {"lev", "epi", "game", "dark", "qbvar", "boom"}
ARRAY_KEYS = ("player_ids", "player_draws", "cand_ix", "totals", "tail_line")


def _digest(path: str) -> str:
    value = sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _load_npz(path: str) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as source:
        if set(source.files) != set(ARRAY_KEYS):
            raise ValueError(f"artifact keys differ: {sorted(source.files)}")
        return {key: np.asarray(source[key]) for key in ARRAY_KEYS}


def _position_legal(rows: list[dict]) -> bool:
    counts = Counter(str(row["pos"]) for row in rows)
    return (
        len(rows) == 9
        and counts["QB"] == 1 and counts["DST"] == 1
        and 2 <= counts["RB"] <= 3
        and 3 <= counts["WR"] <= 4
        and 1 <= counts["TE"] <= 2
    )


def validate(
    *, original_path: str, repaired_path: str,
    candidate_path: str, feature_path: str,
    expected_candidates: int = 248, expected_players: int = 589,
) -> dict:
    original_digest = _digest(original_path)
    if original_digest != ORIGINAL_ARTIFACT_SHA256:
        raise ValueError("original Week 1 artifact SHA-256 differs")
    original = _load_npz(original_path)
    repaired = _load_npz(repaired_path)
    for key in ARRAY_KEYS:
        left, right = original[key], repaired[key]
        numeric = np.issubdtype(left.dtype, np.number) and \
            np.issubdtype(right.dtype, np.number)
        arrays_equal = (
            np.array_equal(left, right, equal_nan=True)
            if numeric else np.array_equal(left, right)
        )
        if not arrays_equal:
            raise ValueError(f"repaired Week 1 {key} array differs")
    totals = repaired["totals"]
    player_draws = repaired["player_draws"]
    player_ids = [str(value) for value in repaired["player_ids"].tolist()]
    cand_ix = repaired["cand_ix"]
    if totals.shape != (expected_candidates, 10_000) or \
            player_draws.shape != (expected_players, 10_000) or \
            not np.array_equal(
                cand_ix, np.arange(expected_candidates, dtype=cand_ix.dtype),
            ) or len(player_ids) != expected_players or \
            len(set(player_ids)) != expected_players:
        raise ValueError("repaired Week 1 artifact shape/identity differs")

    candidates = json.load(open(candidate_path, encoding="utf-8"))
    features = json.load(open(feature_path, encoding="utf-8"))
    if len(candidates) != expected_candidates:
        raise ValueError("repair candidate count differs")
    if not features:
        raise ValueError("repair feature catalog is empty")
    feature_by_id: dict[str, dict] = {}
    for row in features:
        player_id = str(row["id"])
        normalized = {
            "id": player_id,
            "pos": str(row["pos"]),
            "team": str(row["team"]),
            "opp": str(row["opp"]),
            "game_id": str(row.get("game_id") or ""),
            "salary": int(round(float(row["salary"]))),
        }
        if player_id in feature_by_id and feature_by_id[player_id] != normalized:
            raise ValueError("repair feature player identity is ambiguous")
        feature_by_id[player_id] = normalized
    if set(feature_by_id) != set(player_ids):
        raise ValueError("repair feature and artifact player catalogs differ")

    player_row = {player_id: ix for ix, player_id in enumerate(player_ids)}
    seen_rosters: set[tuple[str, ...]] = set()
    seen_indices: set[int] = set()
    tags = Counter()
    max_abs_total_error = 0.0
    for candidate in candidates:
        index = int(candidate["cand_ix"])
        if index in seen_indices or not 0 <= index < len(totals):
            raise ValueError("repair candidate index differs/repeats")
        seen_indices.add(index)
        tag = str(candidate["tag"])
        if tag not in ALLOWED_TAGS:
            raise ValueError("repair candidate tag is not registered")
        tags[tag] += 1
        ids = [value for value in str(candidate["players"]).split(",") if value]
        roster = tuple(sorted(ids))
        if len(ids) != 9 or len(set(ids)) != 9 or roster in seen_rosters:
            raise ValueError("repair candidate roster differs/repeats")
        if any(player_id not in feature_by_id for player_id in ids):
            raise ValueError("repair candidate references an unknown player")
        seen_rosters.add(roster)
        rows = [feature_by_id[player_id] for player_id in ids]
        if not _position_legal(rows):
            raise ValueError("repair candidate position constraints differ")
        salary = sum(row["salary"] for row in rows)
        if salary != int(round(float(candidate["salary"]))) or \
                not 49_000 <= salary <= 50_000:
            raise ValueError("repair candidate salary constraints differ")
        games = {row["game_id"] for row in rows if row["game_id"]}
        if len(games) < 2:
            raise ValueError("repair candidate game-count constraint differs")
        teams = Counter(row["team"] for row in rows)
        if max(teams.values()) > 8:
            raise ValueError("repair candidate team-count constraint differs")
        qb = next(row for row in rows if row["pos"] == "QB")
        catchers = sum(
            row["team"] == qb["team"] and row["pos"] in {"WR", "TE"}
            for row in rows
        )
        bring_backs = sum(
            row["team"] == qb["opp"] and row["pos"] in {"RB", "WR", "TE"}
            for row in rows
        )
        if catchers < 2 or bring_backs < 1:
            raise ValueError("repair candidate stack constraints differ")
        rb_teams = [row["team"] for row in rows if row["pos"] == "RB"]
        if len(rb_teams) != len(set(rb_teams)):
            raise ValueError("repair candidate same-team RB constraint differs")
        dst = next(row for row in rows if row["pos"] == "DST")
        if any(row["pos"] == "RB" and row["team"] == dst["opp"] for row in rows):
            raise ValueError("repair candidate RB/DST constraint differs")
        reconstructed = player_draws[[player_row[player_id] for player_id in ids]].sum(
            axis=0, dtype=np.float32,
        )
        error = float(np.max(np.abs(reconstructed - totals[index])))
        max_abs_total_error = max(max_abs_total_error, error)
        if error > 1e-4:
            raise ValueError("repair candidate totals do not reconstruct")
    if seen_indices != set(range(expected_candidates)) or \
            len(seen_rosters) != expected_candidates:
        raise ValueError("repair candidate identity grid is incomplete")
    if tags["boom"] != 40:
        raise ValueError("repair exact boom count differs")
    return {
        "valid": True,
        "uses_realized_outcomes": False,
        "original_artifact_sha256": original_digest,
        "repaired_artifact_sha256": _digest(repaired_path),
        "arrays_exact": list(ARRAY_KEYS),
        "players": len(player_ids),
        "worlds": int(totals.shape[1]),
        "candidates": len(candidates),
        "unique_rosters": len(seen_rosters),
        "exact_boom_candidates": tags["boom"],
        "tag_counts": dict(sorted(tags.items())),
        "max_abs_total_error": max_abs_total_error,
        "legal_rosters": len(seen_rosters),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--repaired", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = validate(
        original_path=args.original, repaired_path=args.repaired,
        candidate_path=args.candidates, feature_path=args.features,
    )
    with open(args.output, "x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        "ATLAS_MVP_SOURCE_REPAIR_VALIDATED",
        f"candidates={report['candidates']}",
        f"boom={report['exact_boom_candidates']}",
        f"max_abs_error={report['max_abs_total_error']:.8g}",
    )


if __name__ == "__main__":
    main()
