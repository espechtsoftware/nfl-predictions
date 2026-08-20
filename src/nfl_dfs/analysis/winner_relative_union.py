"""Winner-relative census for the frozen B1 generated-roster union.

This module is deliberately descriptive.  It compares *actually generated*
candidate identities with an externally supplied first-place score by slate.
It does not accept or construct H/P hindsight oracles, simulated-world optima,
or counterfactual rosters.

Warehouse/file IO belongs in the runner.  Keeping the computation pure makes
the exact roster deduplication, score reconciliation, source attribution and
winner-relative buckets independently testable before any outcome read.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from .winner_structure_census import roster_structure


PROTOCOL_ID = "20260820-b1-winner-relative-census-v1"
ROSTER_SIZE = 9
SALARY_CAP = 50_000
POSITION_ORDER = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4}


class WinnerRelativeUnionError(ValueError):
    """Fail-closed contract violation."""


def score_cents(value: Any) -> int:
    """Normalize a DK score to the published hundredth-point precision."""
    if value is None or pd.isna(value):
        raise WinnerRelativeUnionError("score is missing")
    try:
        points = Decimal(str(value)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:  # pragma: no cover - Decimal error taxonomy varies
        raise WinnerRelativeUnionError(f"invalid score {value!r}") from exc
    if not points.is_finite():
        raise WinnerRelativeUnionError(f"non-finite score {value!r}")
    return int(points * 100)


def _points(cents: int) -> float:
    return float(Decimal(cents) / Decimal(100))


def _roster_ids(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, np.ndarray, pd.Series)):
        raw = [str(item) for item in value]
    else:
        raw = str(value).split(",")
    ids = tuple(sorted(item.strip() for item in raw if item.strip()))
    if len(ids) != ROSTER_SIZE or len(set(ids)) != ROSTER_SIZE:
        raise WinnerRelativeUnionError(
            f"roster is not nine unique player ids: {value!r}")
    return ids


def _json_tags(value: Any, fallback: str) -> list[str]:
    if value is None or (not isinstance(value, (list, tuple)) and pd.isna(value)):
        return [fallback]
    if isinstance(value, (list, tuple)):
        tags = [str(item) for item in value]
    else:
        text = str(value).strip()
        if not text:
            return [fallback]
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WinnerRelativeUnionError(
                f"all_tags is not JSON: {text!r}") from exc
        if not isinstance(parsed, list):
            raise WinnerRelativeUnionError("all_tags must decode to a list")
        tags = [str(item) for item in parsed]
    return sorted(set(tags or [fallback]))


def _optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _source_record(
    row: Any,
    panel_families: Mapping[str, str],
) -> dict[str, Any]:
    panel = str(row.panel_run_id)
    if panel not in panel_families:
        raise WinnerRelativeUnionError(
            f"panel {panel!r} lacks frozen source-family attribution")
    tag = str(row.tag)
    if row.selected is None or pd.isna(row.selected):
        raise WinnerRelativeUnionError(
            f"candidate has missing selected flag: {panel}")
    selected = bool(row.selected)
    selected_rank = _optional_int(row.selected_rank)
    if selected and (selected_rank is None or selected_rank < 0):
        raise WinnerRelativeUnionError(
            f"selected candidate lacks a nonnegative rank: {panel}")
    if not selected and selected_rank not in (None, -1):
        raise WinnerRelativeUnionError(
            f"unselected candidate has selected rank {selected_rank}: {panel}")
    return {
        "panel_run_id": panel,
        "source_family": str(panel_families[panel]),
        "cand_ix": int(row.cand_ix),
        "tag": tag,
        "all_tags": _json_tags(row.all_tags, tag),
        "selected": selected,
        "selected_rank": selected_rank if selected else None,
    }


def _catalog_for_slate(players: pd.DataFrame) -> pd.DataFrame:
    required = {
        "id", "name", "pos", "team", "opp", "game_id", "salary", "actual"
    }
    missing = required - set(players.columns)
    if missing:
        raise WinnerRelativeUnionError(
            f"player snapshot lacks {sorted(missing)}")
    frame = players.copy()
    frame["id"] = frame.id.astype(str)
    frame["pos"] = frame.pos.astype(str).str.upper()
    for column in ("id", "pos", "team", "opp", "game_id", "salary", "actual"):
        if frame[column].isna().any():
            raise WinnerRelativeUnionError(
                f"canonical snapshot has NULL {column}")
    for column in ("id", "pos", "team", "opp", "game_id"):
        if frame[column].astype(str).str.strip().eq("").any():
            raise WinnerRelativeUnionError(
                f"canonical snapshot has blank {column}")
    if frame.id.duplicated().any():
        duplicated = sorted(frame.loc[frame.id.duplicated(False), "id"].unique())
        raise WinnerRelativeUnionError(
            f"canonical snapshot has duplicate ids: {duplicated[:3]}")
    frame["salary"] = pd.to_numeric(frame.salary, errors="raise").astype(int)
    frame["actual"] = pd.to_numeric(frame.actual, errors="raise").astype(float)
    return frame.set_index("id", drop=False)


def _b1_legal(ids: Sequence[str], catalog: pd.DataFrame) -> tuple[bool, str]:
    """Reproduce the frozen B1 DK-legality screen exactly.

    The $49k floor and production stack/bring-back mandates are intentionally
    absent: the frozen B1 protocol classified them as strategy constraints.
    """
    missing = [pid for pid in ids if pid not in catalog.index]
    if missing:
        return False, "unmatched_players"
    rows = catalog.loc[list(ids)]
    salary = int(rows.salary.sum())
    if salary <= 0 or salary > SALARY_CAP:
        return False, "salary"
    shape = Counter(rows.pos.astype(str).str.upper())
    legal = (
        shape.get("QB", 0) == 1
        and shape.get("DST", 0) == 1
        and 2 <= shape.get("RB", 0) <= 3
        and 3 <= shape.get("WR", 0) <= 4
        and 1 <= shape.get("TE", 0) <= 2
        and sum(shape.get(pos, 0) for pos in ("RB", "WR", "TE")) == 7
    )
    return (True, "") if legal else (False, "position_shape")


def _anatomy(ids: Sequence[str], catalog: pd.DataFrame) -> dict[str, Any]:
    rows = catalog.loc[list(ids)].copy()
    pos_of = dict(zip(rows.id, rows.pos))
    team_of = dict(zip(rows.id, rows.team.astype(str)))
    opp_of = dict(zip(rows.id, rows.opp.astype(str)))
    structural = roster_structure(ids, pos_of, team_of, opp_of)

    salary_by_pos = {
        str(pos): int(group.salary.sum())
        for pos, group in rows.groupby("pos", observed=True)
    }
    actual_by_pos = {
        str(pos): float(group.actual.sum())
        for pos, group in rows.groupby("pos", observed=True)
    }
    team_counts = Counter(rows.team.astype(str))
    game_counts = Counter(rows.game_id.astype(str))
    position_counts = Counter(rows.pos.astype(str))
    flex_positions = [
        pos for pos, base in (("RB", 2), ("WR", 3), ("TE", 1))
        for _ in range(max(position_counts.get(pos, 0) - base, 0))
    ]
    if len(flex_positions) != 1:
        raise WinnerRelativeUnionError(
            f"cannot identify one FLEX position from {dict(position_counts)}")

    qb_row = rows[rows.pos.eq("QB")].iloc[0]
    stack_ids = sorted(
        row.id for row in rows.itertuples()
        if row.pos in ("WR", "TE") and str(row.team) == str(qb_row.team)
    )
    bring_back_ids = sorted(
        row.id for row in rows.itertuples()
        if row.pos in ("RB", "WR", "TE")
        and str(row.team) == str(qb_row.opp)
    )
    ordered = rows.reset_index(drop=True)
    ordered["_pos_order"] = ordered.pos.map(POSITION_ORDER).fillna(99)
    ordered = ordered.sort_values(
        ["_pos_order", "salary", "id"], ascending=[True, False, True])
    player_records = [
        {
            "id": str(row.id),
            "name": str(row.name),
            "pos": str(row.pos),
            "team": str(row.team),
            "opp": str(row.opp),
            "game_id": str(row.game_id),
            "salary": int(row.salary),
            "actual_score": float(row.actual),
        }
        for row in ordered.itertuples(index=False)
    ]
    return {
        **structural,
        "salary_total": int(rows.salary.sum()),
        "salary_left": int(SALARY_CAP - rows.salary.sum()),
        "salary_by_position": salary_by_pos,
        "actual_score_by_position": actual_by_pos,
        "flex_position": flex_positions[0],
        "n_teams": int(len(team_counts)),
        "max_team_concentration": int(max(team_counts.values())),
        "team_counts": dict(sorted(team_counts.items())),
        "game_counts": dict(sorted(game_counts.items())),
        "qb_id": str(qb_row.id),
        "qb_name": str(qb_row["name"]),
        "qb_team": str(qb_row.team),
        "stack_partner_ids": stack_ids,
        "bring_back_ids": bring_back_ids,
        "players": player_records,
    }


def _classify(margin_cents: int) -> str:
    if margin_cents > 0:
        return "beat"
    if margin_cents == 0:
        return "tie"
    if margin_cents >= -1_000:
        return "within_10_loss"
    if margin_cents >= -2_500:
        return "within_25_loss"
    return "outside_25"


def _roster_record(
    ids: tuple[str, ...],
    score: int,
    sources: Sequence[dict[str, Any]],
    catalog: pd.DataFrame,
    *,
    winner_cents: int,
) -> dict[str, Any]:
    ordered_sources = sorted(
        sources,
        key=lambda row: (
            row["panel_run_id"], row["cand_ix"], row["selected_rank"] or -1),
    )
    margin = score - winner_cents
    key = ",".join(ids)
    return {
        "roster_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "roster_ids": list(ids),
        "actual_score": _points(score),
        "winner_margin": _points(margin),
        "winner_class": _classify(margin),
        "selected_any": any(row["selected"] for row in ordered_sources),
        "selected_sources": [row for row in ordered_sources if row["selected"]],
        "sources": ordered_sources,
        "source_families": sorted(
            {row["source_family"] for row in ordered_sources}),
        "generator_tags": sorted({
            tag for row in ordered_sources for tag in row["all_tags"]
        }),
        "anatomy": _anatomy(ids, catalog),
    }


def _aggregate_anatomy(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"n_rosters": 0}
    anatomy = [record["anatomy"] for record in records]
    return {
        "n_rosters": len(records),
        "selected_any": int(sum(record["selected_any"] for record in records)),
        "salary_total_mean": float(np.mean([row["salary_total"] for row in anatomy])),
        "qb_salary_mean": float(np.mean([
            row["salary_by_position"]["QB"] for row in anatomy
        ])),
        "wr_salary_mean": float(np.mean([
            row["salary_by_position"]["WR"] for row in anatomy
        ])),
        "n_games_mean": float(np.mean([row["n_games"] for row in anatomy])),
        "max_game_concentration_mean": float(np.mean([
            row["max_game_concentration"] for row in anatomy
        ])),
        "qb_stack_distribution": dict(sorted(Counter(
            str(row["qb_stack"]) for row in anatomy).items())),
        "bring_back_distribution": dict(sorted(Counter(
            str(row["bring_back"]) for row in anatomy).items())),
        "flex_position_distribution": dict(sorted(Counter(
            row["flex_position"] for row in anatomy).items())),
    }


def winner_relative_union_census(
    candidates: pd.DataFrame,
    players: pd.DataFrame,
    winner_lines: Mapping[tuple[int, int], float],
    panel_families: Mapping[str, str],
    *,
    expected_panels: Sequence[str] | None = None,
    expected_slates: int | None = None,
    expected_distinct_legal_rosters: int | None = None,
    expected_winner_slates: int | None = None,
) -> dict[str, Any]:
    """Compute the winner-relative read of an already generated union.

    ``winner_lines`` is the only winner input.  The function has no argument
    for hindsight or simulated oracles, making population mixing explicit and
    difficult to do accidentally.
    """
    candidate_required = {
        "panel_run_id", "season", "week", "cand_ix", "tag", "all_tags",
        "selected", "selected_rank", "players", "actual_score",
    }
    player_required = {
        "season", "week", "id", "name", "pos", "team", "opp", "game_id",
        "salary", "actual",
    }
    if missing := candidate_required - set(candidates.columns):
        raise WinnerRelativeUnionError(
            f"candidate extract lacks {sorted(missing)}")
    if missing := player_required - set(players.columns):
        raise WinnerRelativeUnionError(
            f"player extract lacks {sorted(missing)}")
    if candidates.empty or players.empty:
        raise WinnerRelativeUnionError("candidate/player extract is empty")

    cand = candidates.copy()
    pframe = players.copy()
    for frame in (cand, pframe):
        frame["season"] = pd.to_numeric(frame.season, errors="raise").astype(int)
        frame["week"] = pd.to_numeric(frame.week, errors="raise").astype(int)
    cand["panel_run_id"] = cand.panel_run_id.astype(str)
    cand["cand_ix"] = pd.to_numeric(cand.cand_ix, errors="raise").astype(int)
    if cand.duplicated(["panel_run_id", "season", "week", "cand_ix"]).any():
        raise WinnerRelativeUnionError("duplicate panel/slate/candidate identity")

    actual_panels = set(cand.panel_run_id.unique())
    if expected_panels is not None and actual_panels != set(expected_panels):
        raise WinnerRelativeUnionError(
            "candidate panels differ from the frozen population: "
            f"missing={sorted(set(expected_panels) - actual_panels)}, "
            f"extra={sorted(actual_panels - set(expected_panels))}")
    if actual_panels - set(panel_families):
        raise WinnerRelativeUnionError(
            f"unattributed panels: {sorted(actual_panels - set(panel_families))}")

    slate_keys = sorted({
        (int(row.season), int(row.week))
        for row in cand[["season", "week"]].drop_duplicates().itertuples(index=False)
    })
    if expected_slates is not None and len(slate_keys) != expected_slates:
        raise WinnerRelativeUnionError(
            f"expected {expected_slates} slates, found {len(slate_keys)}")

    per_slate: list[dict[str, Any]] = []
    all_beating: list[dict[str, Any]] = []
    total_distinct = 0
    drops = Counter()
    score_mismatches = 0
    matched_keys: set[tuple[int, int]] = set()

    for season, week in slate_keys:
        slate_cand = cand[cand.season.eq(season) & cand.week.eq(week)]
        slate_players = pframe[
            pframe.season.eq(season) & pframe.week.eq(week)]
        if slate_players.empty:
            raise WinnerRelativeUnionError(
                f"{season} week {week}: canonical snapshot is missing")
        catalog = _catalog_for_slate(slate_players)
        roster_rows: dict[tuple[str, ...], dict[str, Any]] = {}

        for row in slate_cand.itertuples(index=False):
            ids = _roster_ids(row.players)
            legal, reason = _b1_legal(ids, catalog)
            if not legal:
                drops[f"{row.panel_run_id}:{reason}"] += 1
                continue
            revalued = score_cents(catalog.loc[list(ids), "actual"].sum())
            stored = score_cents(row.actual_score)
            if revalued != stored:
                score_mismatches += 1
                continue
            source = _source_record(row, panel_families)
            record = roster_rows.setdefault(
                ids, {"score_cents": revalued, "sources": []})
            if record["score_cents"] != revalued:
                raise WinnerRelativeUnionError(
                    f"{season} week {week}: one roster has inconsistent scores")
            record["sources"].append(source)

        if not roster_rows:
            raise WinnerRelativeUnionError(
                f"{season} week {week}: no legal reconciled roster survived")
        total_distinct += len(roster_rows)
        if (season, week) not in winner_lines:
            continue
        matched_keys.add((season, week))
        winner_cents = score_cents(winner_lines[(season, week)])
        best_cents = max(record["score_cents"] for record in roster_rows.values())
        best_ids = sorted(
            ids for ids, record in roster_rows.items()
            if record["score_cents"] == best_cents)
        best_records = [
            _roster_record(
                ids, best_cents, roster_rows[ids]["sources"], catalog,
                winner_cents=winner_cents)
            for ids in best_ids
        ]

        bucket_counts = Counter()
        beating_records: list[dict[str, Any]] = []
        for ids, record in roster_rows.items():
            classification = _classify(record["score_cents"] - winner_cents)
            bucket_counts[classification] += 1
            if classification in ("beat", "tie"):
                detailed = _roster_record(
                    ids, record["score_cents"], record["sources"], catalog,
                    winner_cents=winner_cents)
                beating_records.append(detailed)
                all_beating.append({
                    "season": season,
                    "week": week,
                    "winner_score": _points(winner_cents),
                    **detailed,
                })
        beating_records.sort(
            key=lambda row: (-row["actual_score"], row["roster_sha256"]))
        best_margin = best_cents - winner_cents
        per_slate.append({
            "season": season,
            "week": week,
            "winner_score": _points(winner_cents),
            "union_best_score": _points(best_cents),
            "union_margin": _points(best_margin),
            "best_class": _classify(best_margin),
            "n_distinct_legal_generated_rosters": len(roster_rows),
            "n_beating_rosters": int(bucket_counts["beat"]),
            "n_tying_rosters": int(bucket_counts["tie"]),
            "n_within_10_loss_rosters": int(bucket_counts["within_10_loss"]),
            "n_within_25_loss_rosters": int(bucket_counts["within_25_loss"]),
            "n_within_10_or_better": int(
                bucket_counts["beat"] + bucket_counts["tie"]
                + bucket_counts["within_10_loss"]),
            "n_within_25_or_better": int(
                bucket_counts["beat"] + bucket_counts["tie"]
                + bucket_counts["within_10_loss"]
                + bucket_counts["within_25_loss"]),
            "best_rosters": best_records,
            "beating_or_tying_rosters": beating_records,
        })

    if drops:
        raise WinnerRelativeUnionError(
            f"frozen B1 population acquired legality drops: {dict(drops)}")
    if score_mismatches:
        raise WinnerRelativeUnionError(
            f"{score_mismatches} candidate labels disagree with snapshot actuals")
    if (expected_distinct_legal_rosters is not None
            and total_distinct != expected_distinct_legal_rosters):
        raise WinnerRelativeUnionError(
            "frozen B1 distinct-roster count differs: "
            f"expected {expected_distinct_legal_rosters}, found {total_distinct}")
    if expected_winner_slates is not None and len(matched_keys) != expected_winner_slates:
        raise WinnerRelativeUnionError(
            f"expected {expected_winner_slates} winner slates, found {len(matched_keys)}")
    if not per_slate:
        raise WinnerRelativeUnionError("no candidate slates match winner lines")

    per_slate.sort(key=lambda row: (row["season"], row["week"]))
    all_beating.sort(
        key=lambda row: (
            row["season"], row["week"], -row["actual_score"],
            row["roster_sha256"]),
    )
    classifications = Counter(row["best_class"] for row in per_slate)
    margins = np.asarray([row["union_margin"] for row in per_slate], dtype=float)
    summary = {
        "n_winner_slates": len(per_slate),
        "slates_beaten": int(classifications["beat"]),
        "slates_tied": int(classifications["tie"]),
        "slates_within_10_loss": int(classifications["within_10_loss"]),
        "slates_within_25_loss": int(classifications["within_25_loss"]),
        "slates_outside_25": int(classifications["outside_25"]),
        "slates_within_10_or_better": int(sum(
            row["union_margin"] >= -10 for row in per_slate)),
        "slates_within_25_or_better": int(sum(
            row["union_margin"] >= -25 for row in per_slate)),
        "median_union_minus_winner": float(np.median(margins)),
        "mean_union_minus_winner": float(np.mean(margins)),
        "n_distinct_beating_or_tying_rosters": len(all_beating),
        "n_beating_or_tying_rosters_selected_any": int(sum(
            record["selected_any"] for record in all_beating)),
    }
    return {
        "protocol_id": PROTOCOL_ID,
        "population": {
            "name": "frozen_b1_actually_generated_union",
            "panels": len(actual_panels),
            "slates": len(slate_keys),
            "distinct_legal_generated_rosters": total_distinct,
            "matched_winner_slates": len(matched_keys),
            "slates_without_winner_line": [
                {"season": season, "week": week}
                for season, week in slate_keys if (season, week) not in winner_lines
            ],
        },
        "summary": summary,
        "beating_or_tying_anatomy": _aggregate_anatomy(all_beating),
        "per_slate": per_slate,
        "all_beating_or_tying_rosters": all_beating,
        "labels": {
            "uses_realized_outcomes": True,
            "descriptive_only": True,
            "fit_performed": False,
            "tuning_performed": False,
            "production_change_licensed": False,
            "contains_only_actually_generated_rosters": True,
            "contains_hindsight_h_or_p": False,
            "contains_simulated_world_optima": False,
        },
    }
