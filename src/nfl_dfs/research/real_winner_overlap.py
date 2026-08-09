"""Diagnostics against known real Millionaire Maker winning rosters.

This module deliberately separates two questions:

* Did the candidate/selected books expose the individual players who later
  appeared in the winning roster?
* Given those exact marginal player exposures, did the generator assemble
  winning-player pairs and larger subsets less often than an independent
  exposure-preserving null would?

The null is diagnostic rather than a legal-lineup generator: it preserves
each winner player's observed marginal exposure but not salary, position, or
stack constraints.  It can falsify a broad assembly-defect story; it cannot
identify a lineup that was knowable before lock.
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
_TEAM_NICKNAMES = {
    "cardinals": "ARI", "falcons": "ATL", "ravens": "BAL",
    "bills": "BUF", "panthers": "CAR", "bears": "CHI",
    "bengals": "CIN", "browns": "CLE", "cowboys": "DAL",
    "broncos": "DEN", "lions": "DET", "packers": "GB",
    "texans": "HOU", "colts": "IND", "jaguars": "JAX",
    "chiefs": "KC", "raiders": "LV", "chargers": "LAC",
    "rams": "LA", "dolphins": "MIA", "vikings": "MIN",
    "patriots": "NE", "saints": "NO", "giants": "NYG",
    "jets": "NYJ", "eagles": "PHI", "steelers": "PIT",
    "49ers": "SF", "seahawks": "SEA", "buccaneers": "TB",
    "titans": "TEN", "commanders": "WAS", "redskins": "WAS",
}


def _name_tokens(value: object) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", str(value).lower().replace("'", ""))
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return tokens


def load_known_winner_rows(report_root: str | Path) -> pd.DataFrame:
    """Load the two tracked winner-roster sources into one stable schema."""
    root = Path(report_root)
    old = pd.read_csv(root / "milly-winners-2019-2023-2024.csv").rename(
        columns={
            "player": "winner_name", "position": "winner_pos",
            "fantasy_points": "winner_actual",
        })
    # The supplied 2024 week-9 block duplicates week 7 and is not evidence.
    old = old[~(old.season.eq(2024) & old.week.eq(9))]
    recent = pd.read_csv(root / "2025-milly-rosters.csv").rename(
        columns={
            "player": "winner_name", "position": "winner_pos",
            "pts": "winner_actual",
        })
    recent["season"] = 2025
    columns = [
        "season", "week", "winner_name", "winner_pos", "salary",
        "winner_actual",
    ]
    rows = pd.concat([old[columns], recent[columns]], ignore_index=True)
    rows["season"] = rows.season.astype(int)
    rows["week"] = rows.week.astype(int)
    return rows


def _name_matches(winner_name: object, feature_name: object) -> bool:
    winner = _name_tokens(winner_name)
    feature = _name_tokens(feature_name)
    if len(winner) < 2 or len(feature) < 2:
        return False
    if len(winner[0]) == 1:
        return winner[0][0] == feature[0][0] and winner[-1] == feature[-1]
    return "".join(winner) == "".join(feature)


def match_known_winner_players(
    winner_rows: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    """Resolve tracked winner names to immutable slate-player snapshot IDs.

    Older sources abbreviate names and label the ninth skill slot ``FLEX``.
    Name is the primary key; salary and source score are deterministic
    tiebreakers.  A few tracked rows contain a nickname or mistaken first
    name (for example 2023 week 11's ``Bijan`` at Brian Robinson's salary),
    so an otherwise unique salary/score match is retained and made auditable
    through the returned source/canonical columns.
    """
    needed_winner = {
        "season", "week", "winner_name", "winner_pos", "salary",
        "winner_actual",
    }
    needed_features = {
        "season", "week", "id", "name", "pos", "team", "salary",
        "actual", "proj", "mean_projection",
    }
    if missing := needed_winner - set(winner_rows.columns):
        raise ValueError(f"winner rows missing {sorted(missing)}")
    if missing := needed_features - set(features.columns):
        raise ValueError(f"feature rows missing {sorted(missing)}")

    resolved: list[dict] = []
    for source in winner_rows.itertuples(index=False):
        group = features[
            features.season.eq(int(source.season))
            & features.week.eq(int(source.week))
        ].drop_duplicates("id")
        if source.winner_pos == "DST":
            group = group[group.pos.eq("DST")]
            nickname = "".join(_name_tokens(source.winner_name))
            team = _TEAM_NICKNAMES.get(nickname)
            if team is not None and not group[group.team.eq(team)].empty:
                group = group[group.team.eq(team)]
        else:
            allowed = ("RB", "WR", "TE") if source.winner_pos == "FLEX" \
                else (source.winner_pos,)
            group = group[group.pos.isin(allowed)]
            by_name = group[group.name.map(
                lambda value: _name_matches(source.winner_name, value))]
            if not by_name.empty:
                group = by_name

        if len(group) > 1:
            salary = pd.to_numeric(group.salary, errors="coerce")
            actual = pd.to_numeric(group.actual, errors="coerce")
            salary_delta = (
                (salary - float(source.salary)).abs()
                if pd.notna(source.salary)
                else pd.Series(0.0, index=group.index))
            ranked = group.assign(
                _salary_delta=salary_delta,
                _actual_delta=(actual - float(source.winner_actual)).abs(),
            ).sort_values(
                ["_salary_delta", "_actual_delta", "id"], kind="mergesort")
            group = ranked.head(1)
        if len(group) != 1:
            raise ValueError(
                f"winner resolution for {int(source.season)} week "
                f"{int(source.week)} {source.winner_name!r} returned "
                f"{len(group)} rows")

        player = group.iloc[0]
        projection = (
            player.proj if str(player.pos).upper() == "DST"
            else player.mean_projection)
        resolved.append({
            "season": int(source.season),
            "week": int(source.week),
            "winner_name": str(source.winner_name),
            "winner_pos": str(source.winner_pos),
            "winner_salary": (
                np.nan if pd.isna(source.salary) else float(source.salary)),
            "winner_actual": float(source.winner_actual),
            "id": str(player.id),
            "name": str(player["name"]),
            "pos": str(player.pos),
            "team": str(player.team),
            "snapshot_salary": float(player.salary),
            "snapshot_actual": float(player.actual),
            "projection": float(projection),
        })
    result = pd.DataFrame(resolved)
    counts = result.groupby(["season", "week"]).id.nunique()
    if not counts.eq(9).all():
        bad = counts[~counts.eq(9)].to_dict()
        raise ValueError(f"known winner rosters are not nine unique IDs: {bad}")
    return result


def _candidate_player_sets(rows: pd.DataFrame) -> list[set[str]]:
    return [set(str(value).split(",")) for value in rows.players]


def _book_overlap(
    rows: pd.DataFrame,
    winner_ids: list[str],
    rng: np.random.Generator,
    null_reps: int,
) -> dict:
    if rows.empty:
        raise ValueError("winner-overlap book is empty")
    player_sets = _candidate_player_sets(rows)
    membership = np.asarray([
        [player_id in lineup for player_id in winner_ids]
        for lineup in player_sets
    ], dtype=bool)
    exposures = membership.mean(axis=0)
    overlaps = membership.sum(axis=1)
    null_max = (
        rng.random((null_reps, len(rows), len(winner_ids))) < exposures
    ).sum(axis=2).max(axis=1)

    pair_hits: list[bool] = []
    pair_expectations: list[float] = []
    for first in range(len(winner_ids)):
        for second in range(first + 1, len(winner_ids)):
            pair_hits.append(bool(np.any(
                membership[:, first] & membership[:, second])))
            independent_pair = exposures[first] * exposures[second]
            pair_expectations.append(
                float(1.0 - (1.0 - independent_pair) ** len(rows)))
    return {
        "n_entries": int(len(rows)),
        "winner_player_coverage": int(np.count_nonzero(exposures)),
        "max_overlap": int(overlaps.max()),
        "null_max_mean": float(null_max.mean()),
        "null_max_q05": float(np.quantile(null_max, 0.05)),
        "null_max_q95": float(np.quantile(null_max, 0.95)),
        "max_minus_null": float(overlaps.max() - null_max.mean()),
        "pair_any_rate": float(np.mean(pair_hits)),
        "pair_independent_rate": float(np.mean(pair_expectations)),
    }


def evaluate_known_winner_overlap(
    candidates: pd.DataFrame,
    winners: pd.DataFrame,
    *,
    seed: int = 8163,
    null_reps: int = 2_000,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate pool/selected assembly and omitted individual winner slots."""
    if null_reps <= 0:
        raise ValueError("null_reps must be positive")
    needed_candidates = {
        "season", "week", "players", "selected", "actual_score",
    }
    needed_winners = {
        "season", "week", "id", "name", "pos", "snapshot_actual",
        "projection",
    }
    if missing := needed_candidates - set(candidates.columns):
        raise ValueError(f"candidate rows missing {sorted(missing)}")
    if missing := needed_winners - set(winners.columns):
        raise ValueError(f"winner rows missing {sorted(missing)}")

    rng = np.random.default_rng(seed)
    reports: list[dict] = []
    omitted: list[dict] = []
    grouped_candidates = {
        (int(season), int(week)): group.sort_values("cand_ix")
        if "cand_ix" in group else group
        for (season, week), group in candidates.groupby(
            ["season", "week"], sort=True)
    }
    for (season, week), winner_group in winners.groupby(
            ["season", "week"], sort=True):
        key = (int(season), int(week))
        if key not in grouped_candidates:
            raise ValueError(f"winner week {key} absent from candidate panel")
        slate = grouped_candidates[key]
        selected = slate[slate.selected.astype(bool)]
        if selected.empty:
            raise ValueError(f"winner week {key} has no selected candidates")
        winner_ids = winner_group.id.astype(str).tolist()
        pool_sets = _candidate_player_sets(slate)
        pool_union = set().union(*pool_sets)
        selected_sets = _candidate_player_sets(selected)
        selected_union = set().union(*selected_sets)

        actual = pd.to_numeric(slate.actual_score, errors="coerce")
        if actual.isna().any():
            raise ValueError(f"winner week {key} has missing candidate scores")
        oracle_pos = int(actual.to_numpy().argmax())
        selected_actual = pd.to_numeric(
            selected.actual_score, errors="coerce")
        selected_best_label = selected_actual.idxmax()
        oracle_players = pool_sets[oracle_pos]
        selected_best_players = set(
            str(slate.loc[selected_best_label, "players"]).split(","))

        exact_in_pool = any(set(winner_ids) == lineup for lineup in pool_sets)
        common = {
            "season": key[0], "week": key[1],
            "exact_winner_in_pool": bool(exact_in_pool),
            "oracle_overlap": int(len(set(winner_ids) & oracle_players)),
            "selected_best_overlap": int(
                len(set(winner_ids) & selected_best_players)),
        }
        for label, book, union in (
                ("pool", slate, pool_union),
                ("selected", selected, selected_union)):
            reports.append({
                **common, "book": label,
                **_book_overlap(book, winner_ids, rng, null_reps),
            })
            if label == "pool":
                for player in winner_group.itertuples(index=False):
                    if str(player.id) not in union:
                        omitted.append({
                            "season": key[0], "week": key[1],
                            "id": str(player.id), "name": str(player.name),
                            "pos": str(player.pos),
                            "actual": float(player.snapshot_actual),
                            "projection": float(player.projection),
                            "surprise": float(
                                player.snapshot_actual - player.projection),
                        })
    return pd.DataFrame(reports), pd.DataFrame(omitted)
