"""Score-free diagnosis of where corrected exact-P rosters leave generation."""

from __future__ import annotations

from collections import Counter
import json
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from .final_forensic import canonical_game_id


PROTOCOL_ID = "20260815-exact-p-generator-constraint-census-v1"
SCOPE = "phase-s-cbwu-54"
SEED_ORDER = tuple(
    f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
)
BASE_FAMILIES = ("lev", "boom", "epi", "qbvar", "game", "dark")
STRUCTURE_FIELDS = (
    "salary", "distinct_games", "largest_team_block", "qb_stack_size",
    "bring_back_count", "qb_salary", "rb_salary", "wr_salary",
    "te_salary", "dst_salary",
)
FORBIDDEN_COLUMNS = frozenset({
    "actual", "actual_score", "actual_rank", "actual_ownership", "rank",
    "payout", "winnings",
})


def _require(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    if missing := columns - set(frame):
        raise ValueError(f"{label} lacks columns {sorted(missing)}")


def _reject_outcomes(frame: pd.DataFrame, label: str) -> None:
    if forbidden := FORBIDDEN_COLUMNS & set(frame):
        raise ValueError(f"{label} contains forbidden columns {sorted(forbidden)}")


def canonical_roster(value: object) -> tuple[str, ...]:
    players = tuple(sorted(item for item in str(value).split(",") if item))
    if len(players) != 9 or len(set(players)) != 9:
        raise ValueError("generator census encountered a malformed roster")
    return players


def _base_tags(value: object, primary: object) -> tuple[str, ...]:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("generator census all_tags is invalid JSON") from exc
    elif isinstance(value, (list, tuple)):
        decoded = list(value)
    elif value is None or (isinstance(value, float) and np.isnan(value)):
        decoded = []
    else:
        raise ValueError("generator census all_tags has invalid type")
    values = [str(item) for item in decoded]
    values.append(str(primary))
    families = []
    for family in BASE_FAMILIES:
        if any(tag == family or tag.startswith(f"{family}:") for tag in values):
            families.append(family)
    if not families:
        raise ValueError("generator census candidate has no registered base family")
    return tuple(families)


def _distance(left: Sequence[str], right: Sequence[str]) -> int:
    return int(9 - len(set(left) & set(right)))


def _shape(players: pd.DataFrame, roster: Sequence[str]) -> dict[str, float]:
    by_id = players.set_index("id", drop=False)
    unknown = sorted(set(roster) - set(by_id.index))
    if unknown:
        raise ValueError(f"generator census roster has unknown players {unknown}")
    chosen = by_id.loc[list(roster)]
    qbs = chosen[chosen.pos.eq("QB")]
    if len(qbs) != 1:
        raise ValueError("generator census roster does not have one QB")
    qb = qbs.iloc[0]
    games = [
        canonical_game_id(team, opponent)
        for team, opponent in zip(chosen.team, chosen.opp, strict=True)
    ]
    output = {
        "salary": float(chosen.salary.sum()),
        "distinct_games": float(len(set(games))),
        "largest_team_block": float(chosen.team.value_counts().max()),
        "qb_stack_size": float((
            chosen.team.eq(str(qb.team)) & chosen.pos.isin(("WR", "TE"))
        ).sum()),
        "bring_back_count": float((
            chosen.team.eq(str(qb.opp))
            & chosen.pos.isin(("RB", "WR", "TE"))
        ).sum()),
    }
    for position in ("QB", "RB", "WR", "TE", "DST"):
        output[f"{position.lower()}_salary"] = float(
            chosen.loc[chosen.pos.eq(position), "salary"].sum()
        )
    output["maximum_game_count"] = float(max(Counter(games).values()))
    return output


def _audit_exact_p(players: pd.DataFrame, roster: Sequence[str]) -> dict:
    shape = _shape(players, roster)
    chosen = players.set_index("id", drop=False).loc[list(roster)]
    failures: list[str] = []
    counts = chosen.pos.value_counts()
    if not (
        counts.get("QB", 0) == 1
        and counts.get("DST", 0) == 1
        and 2 <= counts.get("RB", 0) <= 3
        and 3 <= counts.get("WR", 0) <= 4
        and 1 <= counts.get("TE", 0) <= 2
    ):
        failures.append("position-counts")
    if not 49_000 <= shape["salary"] <= 50_000:
        failures.append("salary")
    if shape["distinct_games"] < 2:
        failures.append("minimum-games")
    if shape["largest_team_block"] > 8:
        failures.append("maximum-team")
    if shape["qb_stack_size"] < 2:
        failures.append("qb-stack")
    if shape["bring_back_count"] < 1:
        failures.append("bring-back")
    if (chosen[chosen.pos.eq("RB")].team.value_counts() > 1).any():
        failures.append("same-team-rb")
    dst = chosen[chosen.pos.eq("DST")].iloc[0]
    if (chosen.pos.eq("RB") & chosen.team.eq(str(dst.opp))).any():
        failures.append("rb-vs-dst")
    return {"passes": not failures, "failures": failures, "shape": shape}


def reconstruct_cbwu(
    seed_books: dict[str, list[tuple[str, tuple[str, ...]]]],
) -> list[tuple[str, str]]:
    """Reproduce first-seed dedupe plus fixed quota/fill without scores."""
    if tuple(seed_books) != SEED_ORDER:
        raise ValueError("generator census seed order differs")
    budget = len(seed_books[SEED_ORDER[0]])
    if budget <= 0:
        raise ValueError("generator census base candidate budget is empty")
    buckets: dict[str, list[str]] = {seed: [] for seed in SEED_ORDER}
    seen: set[str] = set()
    for seed in SEED_ORDER:
        for roster_key, _families in seed_books[seed]:
            if roster_key not in seen:
                seen.add(roster_key)
                buckets[seed].append(roster_key)
    base, remainder = divmod(budget, len(SEED_ORDER))
    chosen: list[tuple[str, str]] = []
    used: dict[str, int] = {}
    for index, seed in enumerate(SEED_ORDER):
        take = min(base + int(index < remainder), len(buckets[seed]))
        chosen.extend((seed, roster) for roster in buckets[seed][:take])
        used[seed] = take
    while len(chosen) < budget:
        advanced = False
        for seed in SEED_ORDER:
            if used[seed] < len(buckets[seed]):
                chosen.append((seed, buckets[seed][used[seed]]))
                used[seed] += 1
                advanced = True
                if len(chosen) == budget:
                    break
        if not advanced:
            raise ValueError("generator census CBWU cannot fill fixed budget")
    return chosen


def _family_diagnostic(
    family_rosters: list[tuple[str, ...]],
    exact_p: tuple[str, ...],
    players: pd.DataFrame,
    p_shape: dict[str, float],
) -> dict[str, Any]:
    if not family_rosters:
        return {
            "candidate_count": 0,
            "exact_p_present": False,
            "minimum_swaps_to_p": None,
            "closest_candidate_count": 0,
            "p_player_slot_coverage": 0.0,
            "structure": {},
        }
    distances = [_distance(exact_p, roster) for roster in family_rosters]
    minimum = min(distances)
    represented = set().union(*(set(roster) for roster in family_rosters))
    structures = [_shape(players, roster) for roster in family_rosters]
    contrasts = {}
    for field in STRUCTURE_FIELDS:
        values = np.asarray([row[field] for row in structures], dtype=float)
        point = float(p_shape[field])
        contrasts[field] = {
            "exact_p": point,
            "candidate_median": float(np.median(values)),
            "exact_p_minus_candidate_median": float(point - np.median(values)),
            "exact_p_within_family_percentile": float(np.mean(values <= point)),
        }
    return {
        "candidate_count": len(family_rosters),
        "exact_p_present": exact_p in family_rosters,
        "minimum_swaps_to_p": int(minimum),
        "closest_candidate_count": int(sum(value == minimum for value in distances)),
        "p_player_slot_coverage": float(
            len(set(exact_p) & represented) / len(exact_p)
        ),
        "p_player_appearance_counts": [
            int(sum(player in roster for roster in family_rosters))
            for player in exact_p
        ],
        "structure": contrasts,
    }


def analyze_exact_p_generator_census(
    players: pd.DataFrame,
    native_candidates: pd.DataFrame,
    retained_candidates: pd.DataFrame,
    exact_p_rosters: pd.DataFrame,
    *,
    expected_slates: int = 54,
) -> dict[str, Any]:
    """Run the frozen score-free census over immutable exact-P identities."""
    for frame, label in (
        (players, "players"),
        (native_candidates, "native candidates"),
        (retained_candidates, "retained candidates"),
        (exact_p_rosters, "exact P"),
    ):
        _reject_outcomes(frame, label)
    key = {"season", "week"}
    _require(
        players,
        key | {"id", "pos", "team", "opp", "game_id", "salary"},
        "players",
    )
    _require(
        native_candidates,
        key | {"panel_run_id", "cand_ix", "players", "tag", "all_tags"},
        "native candidates",
    )
    _require(
        retained_candidates,
        key | {"candidate_index", "players", "tag"},
        "retained candidates",
    )
    _require(exact_p_rosters, key | {"players"}, "exact P")
    slate_keys = {
        tuple(map(int, row))
        for row in exact_p_rosters[["season", "week"]].to_numpy()
    }
    if len(exact_p_rosters) != len(slate_keys) or len(slate_keys) != expected_slates:
        raise ValueError("generator census exact-P slate population differs")
    for frame, label in (
        (players, "players"),
        (native_candidates, "native candidates"),
        (retained_candidates, "retained candidates"),
    ):
        observed = {
            tuple(map(int, row))
            for row in frame[["season", "week"]].drop_duplicates().to_numpy()
        }
        if observed != slate_keys:
            raise ValueError(f"generator census {label} slate population differs")
    if set(native_candidates.panel_run_id.astype(str)) != set(SEED_ORDER):
        raise ValueError("generator census native seed set differs")

    records: list[dict[str, Any]] = []
    family_primary_counts = Counter()
    total_native_candidates = 0
    family_incapable_slates = Counter()
    for season, week in sorted(slate_keys):
        pframe = players[
            players.season.eq(season) & players.week.eq(week)
        ].copy()
        pframe["id"] = pframe.id.astype(str)
        pframe["pos"] = pframe.pos.astype(str).str.upper().replace({"DEF": "DST"})
        pframe["team"] = pframe.team.astype(str)
        pframe["opp"] = pframe.opp.astype(str)
        pframe["salary"] = pd.to_numeric(pframe.salary, errors="raise").astype(int)
        exact_p = canonical_roster(exact_p_rosters.loc[
            exact_p_rosters.season.eq(season)
            & exact_p_rosters.week.eq(week), "players"
        ].iloc[0])
        audit = _audit_exact_p(pframe, exact_p)
        if not audit["passes"]:
            raise ValueError(f"generator census exact P is illegal: {audit['failures']}")
        p_shape = audit["shape"]

        seed_books: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
        seed_rosters: dict[str, list[tuple[str, ...]]] = {}
        family_rows: dict[str, dict[str, list[tuple[str, ...]]]] = {}
        for seed in SEED_ORDER:
            group = native_candidates[
                native_candidates.season.eq(season)
                & native_candidates.week.eq(week)
                & native_candidates.panel_run_id.astype(str).eq(seed)
            ].sort_values("cand_ix", kind="stable")
            if group.empty or group.cand_ix.duplicated().any():
                raise ValueError("generator census native book is empty or duplicated")
            book: list[tuple[str, tuple[str, ...]]] = []
            per_family = {family: [] for family in BASE_FAMILIES}
            primary_seen = Counter()
            for row in group.itertuples(index=False):
                roster = canonical_roster(row.players)
                families = _base_tags(row.all_tags, row.tag)
                book.append((",".join(roster), families))
                for family in families:
                    per_family[family].append(roster)
                primary = str(row.tag).split(":", 1)[0]
                if primary not in BASE_FAMILIES:
                    raise ValueError("generator census primary family differs")
                primary_seen[primary] += 1
            if len({roster for roster, _tags in book}) != len(book):
                raise ValueError("generator census native book repeats a roster")
            seed_books[seed] = book
            seed_rosters[seed] = [tuple(key.split(",")) for key, _ in book]
            family_rows[seed] = per_family
            family_primary_counts.update(primary_seen)
            total_native_candidates += len(book)

        reconstructed = reconstruct_cbwu(seed_books)
        retained = retained_candidates[
            retained_candidates.season.eq(season)
            & retained_candidates.week.eq(week)
        ].sort_values("candidate_index", kind="stable")
        retained_keys = [",".join(canonical_roster(value)) for value in retained.players]
        reconstructed_keys = [roster for _seed, roster in reconstructed]
        if retained_keys != reconstructed_keys:
            raise ValueError("generator census retained CBWU does not reproduce")
        expected_tags = [
            f"CBWU_R{SEED_ORDER.index(seed)}" for seed, _roster in reconstructed
        ]
        if retained.tag.astype(str).tolist() != expected_tags:
            raise ValueError("generator census retained CBWU seed attribution differs")

        native_union = {
            roster for rosters in seed_rosters.values() for roster in rosters
        }
        retained_rosters = [tuple(key.split(",")) for key in retained_keys]
        per_seed: dict[str, Any] = {}
        slate_eligibility = {family: False for family in BASE_FAMILIES}
        p_chosen = pframe.set_index("id", drop=False).loc[list(exact_p)]
        qb_id = str(p_chosen[p_chosen.pos.eq("QB")].iloc[0].id)
        for seed in SEED_ORDER:
            families = {}
            for family in BASE_FAMILIES:
                rows = family_rows[seed][family]
                diagnostic = _family_diagnostic(rows, exact_p, pframe, p_shape)
                if family in {"lev", "boom", "epi"}:
                    eligible = True
                elif family == "qbvar":
                    eligible = any(qb_id in roster for roster in rows)
                else:
                    eligible = bool(rows) and p_shape["maximum_game_count"] >= 5
                diagnostic["static_family_eligible"] = eligible
                families[family] = diagnostic
                slate_eligibility[family] |= eligible
            per_seed[seed] = {
                "candidate_count": len(seed_rosters[seed]),
                "exact_p_present": exact_p in seed_rosters[seed],
                "families": families,
            }
        for family, eligible in slate_eligibility.items():
            if not eligible:
                family_incapable_slates[family] += 1
        native_appearances = [
            int(sum(player in roster for roster in native_union))
            for player in exact_p
        ]
        records.append({
            "season": int(season),
            "week": int(week),
            "exact_p": list(exact_p),
            "exact_p_shape": p_shape,
            "native_union_candidate_count": len(native_union),
            "retained_candidate_count": len(retained_rosters),
            "exact_p_in_native_union": exact_p in native_union,
            "exact_p_in_retained_cbwu": exact_p in retained_rosters,
            "loss_stage": (
                "invalid-retained" if exact_p in retained_rosters
                else "fixed-budget-admission" if exact_p in native_union
                else "native-generation-search"
            ),
            "p_player_representation": {
                "appearance_counts": native_appearances,
                "absent_player_slots": int(sum(
                    value == 0 for value in native_appearances
                )),
                "thin_player_slots_under_five": int(sum(
                    0 < value < 5 for value in native_appearances
                )),
                "combination_absent": exact_p not in native_union,
                "combination_removed_by_cbwu_admission": bool(
                    exact_p in native_union and exact_p not in retained_rosters
                ),
            },
            "per_seed": per_seed,
            "static_family_eligibility": slate_eligibility,
        })

    invalid = sum(row["loss_stage"] == "invalid-retained" for row in records)
    native_absent = sum(
        row["loss_stage"] == "native-generation-search" for row in records
    )
    admission = sum(
        row["loss_stage"] == "fixed-budget-admission" for row in records
    )
    family_budget_share = {
        family: float(family_primary_counts[family] / total_native_candidates)
        for family in BASE_FAMILIES
    }
    structurally_material = [
        family for family in BASE_FAMILIES
        if family_budget_share[family] >= 0.10
        and family_incapable_slates[family] >= 36
    ]
    if invalid:
        disposition = "invalid-or-inconclusive"
    elif native_absent >= 36:
        disposition = "native-generation-search-dominant"
    elif admission >= 6:
        disposition = "fixed-budget-admission-material"
    elif structurally_material:
        disposition = "specific-family-structural-exclusion-material"
    else:
        disposition = "mixed"
    return {
        "protocol_id": PROTOCOL_ID,
        "scope": SCOPE,
        "uses_candidate_or_lineup_scores": False,
        "production_change_licensed": False,
        "historical_arm_licensed": False,
        "slates": len(records),
        "disposition": disposition,
        "loss_stage_counts": {
            "native_generation_search": native_absent,
            "fixed_budget_admission": admission,
            "invalid_retained": invalid,
        },
        "family_primary_candidate_counts": {
            family: int(family_primary_counts[family])
            for family in BASE_FAMILIES
        },
        "family_primary_budget_share": family_budget_share,
        "family_statically_incapable_slates": {
            family: int(family_incapable_slates[family])
            for family in BASE_FAMILIES
        },
        "structurally_material_families": structurally_material,
        "records": records,
    }


__all__ = [
    "BASE_FAMILIES", "PROTOCOL_ID", "SCOPE", "SEED_ORDER",
    "analyze_exact_p_generator_census", "canonical_roster", "reconstruct_cbwu",
]
