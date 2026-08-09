"""Contest-aware Sunday-main Millionaire ownership evaluation helpers.

This module deliberately models one large-field Classic Milly per week rather
than averaging ownership across incompatible cash, Showdown, and alternate
slates.  Every fold is trained only on earlier seasons.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd


TARGET = "pct_drafted"
POSITIONS = ("QB", "RB", "WR", "TE", "DST")
SCOPE_EXCLUSIONS = {
    # Christmas fell on Sunday. The accepted replay's Sunday slate contains
    # only DEN-LAR and GB-MIA, while DK's named Week-16 Milly was the large
    # Saturday main slate. It is not ownership truth for the replay universe.
    (2022, 16): "Christmas Saturday Milly does not match Sunday replay slate",
}
FEATURES = (
    "salary", "proj_points", "value", "salary_rank_pos", "value_rank_pos",
    "salary_pct_pos", "value_pct_pos", "slate_size", "implied_team_total",
    "spread", "game_total", "is_cold_start", "depth_rank",
    "depth_rank_delta", "target_share_last", "carry_share_last",
    "snap_share_last", "target_share_jump", "carry_share_jump",
    "snap_share_jump", "target_share_l4", "carry_share_l4", "snap_share_l4",
    "dk_points_l4", "team_vacated_target_share", "team_vacated_carry_share",
    "salary_delta_wow", "games_played_prior", "pos_QB", "pos_RB", "pos_WR",
    "pos_TE", "pos_DST",
)

_DST_NICKNAME_TO_TEAM = {
    "49ERS": "SF", "BEARS": "CHI", "BENGALS": "CIN", "BILLS": "BUF",
    "BRONCOS": "DEN", "BROWNS": "CLE", "BUCCANEERS": "TB",
    "CARDINALS": "ARI", "CHARGERS": "LAC", "CHIEFS": "KC",
    "COLTS": "IND", "COMMANDERS": "WAS", "COWBOYS": "DAL",
    "DOLPHINS": "MIA", "EAGLES": "PHI", "FALCONS": "ATL",
    "GIANTS": "NYG", "JAGUARS": "JAX", "JETS": "NYJ", "LIONS": "DET",
    "PACKERS": "GB", "PANTHERS": "CAR", "PATRIOTS": "NE",
    "RAIDERS": "LV", "RAMS": "LAR", "RAVENS": "BAL", "REDSKINS": "WAS",
    "SAINTS": "NO", "SEAHAWKS": "SEA", "STEELERS": "PIT",
    "TEXANS": "HOU", "TITANS": "TEN", "VIKINGS": "MIN",
    "WASHINGTONFOOTBALLTEAM": "WAS",
}


def normalize_name(value: object) -> str:
    """Stable player-name key with punctuation and generational suffixes out."""
    if value is None or pd.isna(value):
        return ""
    text = re.sub(r"[^A-Z0-9 ]+", " ", str(value or "").upper())
    parts = text.split()
    while parts and parts[-1] in {"JR", "SR", "II", "III", "IV", "V"}:
        parts.pop()
    return "".join(parts)


def ownership_join_key(name: object, position: object,
                       team: object | None = None) -> str:
    pos = str(position or "").upper().replace("D/ST", "DST")
    if pos == "DST":
        if team is not None and not pd.isna(team) and str(team).strip():
            return "DST_" + str(team).upper().strip()
        normalized = normalize_name(name)
        normalized = re.sub(r"(?:DST|DEFENSE)$", "", normalized)
        code = _DST_NICKNAME_TO_TEAM.get(normalized, normalized)
        return "DST_" + code
    return f"PLAYER_{pos}_" + normalize_name(name)


def parse_field_size(contest_name: object) -> int:
    matches = re.findall(r"\[(\d+)\s+entries\b", str(contest_name), re.I)
    return max((int(value) for value in matches), default=0)


def select_main_milly_contests(ownership: pd.DataFrame) -> pd.DataFrame:
    """Return exactly one mass-valid, largest-field Classic Milly per week."""
    needed = {"season", "week", "contest_id", "contest_name",
              "roster_position", TARGET}
    missing = needed - set(ownership.columns)
    if missing:
        raise ValueError(f"ownership rows missing {sorted(missing)}")
    rows = ownership.copy()
    rows["position"] = (rows.roster_position.astype(str).str.upper()
                        .replace({"D/ST": "DST"}))
    summary = rows.groupby(
        ["season", "week", "contest_id", "contest_name"], dropna=False
    ).agg(
        own_sum=(TARGET, "sum"),
        qb_sum=(TARGET, lambda s: float(s[rows.loc[s.index, "position"].eq("QB")].sum())),
        dst_sum=(TARGET, lambda s: float(s[rows.loc[s.index, "position"].eq("DST")].sum())),
        n_players=(TARGET, "size"),
    ).reset_index()
    summary["field_size"] = summary.contest_name.map(parse_field_size)
    name = summary.contest_name.fillna("").astype(str)
    valid = summary[
        name.str.contains("Fantasy Football Millionaire", case=False)
        & ~name.str.contains(r"\([^)]*\)", regex=True)
        & summary.own_sum.between(800.0, 930.0)
        & summary.qb_sum.between(75.0, 105.0)
        & summary.dst_sum.between(90.0, 105.0)
        & summary.n_players.ge(100)
        & summary.field_size.gt(0)
    ].copy()
    chosen: list[pd.Series] = []
    for key, group in valid.groupby(["season", "week"]):
        best = group[group.field_size.eq(group.field_size.max())]
        if len(best) != 1:
            ids = best.contest_id.astype(str).tolist()
            raise ValueError(f"ambiguous main Milly contest for {key}: {ids}")
        chosen.append(best.iloc[0])
    if not chosen:
        raise ValueError("no mass-valid main Milly contests")
    return pd.DataFrame(chosen).sort_values(["season", "week"]).reset_index(drop=True)


def join_milly_truth(features: pd.DataFrame, ownership: pd.DataFrame,
                     contests: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join actual Milly ownership to exact snapshots without zero filling."""
    ids = contests[["season", "week", "contest_id"]]
    truth = ownership.merge(ids, on=["season", "week", "contest_id"],
                            how="inner", validate="many_to_one").copy()
    truth["position"] = (truth.roster_position.astype(str).str.upper()
                         .replace({"D/ST": "DST"}))
    truth["join_key"] = [
        ownership_join_key(name, pos)
        for name, pos in zip(truth.display_name, truth.position)
    ]
    if truth.join_key.str.endswith("_").any():
        raise ValueError("ownership truth contains an empty player name")
    feat = features.copy()
    feat["position"] = feat.pos.astype(str).str.upper().replace({"D/ST": "DST"})
    feat["join_key"] = [
        ownership_join_key(name, pos, team if pos == "DST" else None)
        for name, pos, team in zip(feat.name, feat.position, feat.team)
    ]
    # The accepted snapshot legitimately includes a few rows whose upstream
    # display-name lookup is null. They remain in the full slate for naive
    # normalization but cannot be joined to settled ownership. Give each an
    # explicit nonmatching key instead of collapsing all nulls to PLAYER_NAN.
    empty_feature_key = feat.join_key.str.endswith("_")
    feat.loc[empty_feature_key, "join_key"] = (
        "UNMATCHED_ID_" + feat.loc[empty_feature_key, "id"].astype(str))
    keys = ["season", "week", "join_key"]
    for label, frame in (("ownership", truth), ("feature", feat)):
        if frame.duplicated(keys).any():
            sample = frame.loc[frame.duplicated(keys, keep=False), keys].head()
            raise ValueError(f"duplicate {label} join keys: {sample.to_dict('records')}")
    joined = truth.merge(
        feat, on=keys, how="inner", suffixes=("_truth", ""),
        validate="one_to_one")
    coverage = contests[["season", "week", "contest_id", "contest_name",
                         "field_size", "own_sum"]].copy()
    matched = joined.groupby(["season", "week"])[TARGET].agg(
        matched_mass="sum", matched_rows="size").reset_index()
    coverage = coverage.merge(matched, on=["season", "week"], how="left")
    coverage[["matched_mass", "matched_rows"]] = coverage[
        ["matched_mass", "matched_rows"]].fillna(0)
    coverage["mass_coverage"] = coverage.matched_mass / coverage.own_sum
    return joined, coverage


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "position" not in out:
        if "pos" not in out:
            raise ValueError("snapshot needs pos or position")
        out["position"] = (out.pos.astype(str).str.upper()
                           .replace({"D/ST": "DST"}))
    out["proj_points"] = pd.to_numeric(out.proj, errors="coerce")
    out["value"] = out.proj_points / (
        pd.to_numeric(out.salary, errors="coerce") / 1000.0).clip(lower=0.1)
    groups = [out.season, out.week, out.position]
    out["salary_rank_pos"] = out.groupby(
        ["season", "week", "position"])["salary"].rank(
            ascending=False, method="average")
    out["value_rank_pos"] = out.groupby(
        ["season", "week", "position"])["value"].rank(
            ascending=False, method="average")
    out["salary_pct_pos"] = out.groupby(
        ["season", "week", "position"])["salary"].rank(
            ascending=False, pct=True)
    out["value_pct_pos"] = out.groupby(
        ["season", "week", "position"])["value"].rank(
            ascending=False, pct=True)
    out["slate_size"] = out.groupby(["season", "week"])["id"].transform("size")
    for pos in POSITIONS:
        out[f"pos_{pos}"] = out.position.eq(pos).astype(float)
    # Make the contract explicit and fail early if a future snapshot drops a
    # preregistered field. LightGBM itself handles nullable point-in-time data.
    missing = set(FEATURES) - set(out.columns)
    if missing:
        raise ValueError(f"snapshot missing ownership features {sorted(missing)}")
    return out


def train_contest_model(frame: pd.DataFrame, num_boost_round: int = 180):
    import lightgbm as lgb

    y = frame[TARGET].clip(1e-3, 100 - 1e-3) / 100.0
    y = np.log(y / (1.0 - y))
    dataset = lgb.Dataset(frame[list(FEATURES)], label=y)
    params = {
        "objective": "regression", "metric": "l2", "verbosity": -1,
        "learning_rate": 0.035, "num_leaves": 7, "min_data_in_leaf": 45,
        "feature_fraction": 0.85, "feature_fraction_seed": 2701,
        "deterministic": True, "force_col_wise": True, "num_threads": 2,
    }
    return lgb.train(params, dataset, num_boost_round=num_boost_round)


def predict_contest_model(booster, frame: pd.DataFrame) -> np.ndarray:
    logit = booster.predict(frame[list(FEATURES)])
    return 100.0 / (1.0 + np.exp(-np.asarray(logit, dtype=float)))


def prediction_metrics(frame: pd.DataFrame, prediction: object) -> dict:
    actual = pd.to_numeric(frame[TARGET], errors="raise")
    pred = pd.Series(np.asarray(prediction, dtype=float), index=frame.index)
    top = actual.groupby([frame.season, frame.week]).rank(
        ascending=False, pct=True, method="average").le(0.25)
    return {
        "rows": int(len(frame)),
        "pearson": float(actual.corr(pred, method="pearson")),
        "spearman": float(actual.corr(pred, method="spearman")),
        "mae": float((actual - pred).abs().mean()),
        "top_quartile_mae": float((actual[top] - pred[top]).abs().mean()),
    }


def diagnostic_gate(metric_rows: pd.DataFrame,
                    aggregate_mass_coverage: float) -> dict:
    """Frozen held-out gate from the preregistration report."""
    aggregate = metric_rows[metric_rows.season.eq("aggregate")].set_index("method")
    model = aggregate.loc["contest_aware"]
    comparators = aggregate.loc[["all_contest", "naive"]]
    aggregate_better = bool(
        model.mae < comparators.mae.min()
        and model.spearman > comparators.spearman.max())
    season_passes = 0
    no_large_spearman_loss = True
    for season in (2023, 2024, 2025):
        fold = metric_rows[metric_rows.season.eq(season)].set_index("method")
        candidate = fold.loc["contest_aware"]
        bases = fold.loc[["all_contest", "naive"]]
        season_passes += int(
            candidate.mae <= bases.mae.min()
            and candidate.spearman >= bases.spearman.max())
        no_large_spearman_loss &= bool(
            candidate.spearman >= bases.spearman.max() - 0.02)
    checks = {
        "aggregate_mae_and_spearman_better_than_both": aggregate_better,
        "both_metrics_improve_or_tie_in_two_seasons": season_passes >= 2,
        "no_season_spearman_loss_worse_than_0_02": no_large_spearman_loss,
        "ownership_mass_coverage_at_least_90pct":
            aggregate_mass_coverage >= 0.90,
    }
    checks["season_pass_count"] = season_passes
    checks["passes"] = all(
        value for key, value in checks.items()
        if key not in {"season_pass_count", "passes"})
    return checks


def mark_scope_eligibility(coverage: pd.DataFrame) -> pd.DataFrame:
    """Apply calendar-proven slate exclusions and fail on any new mismatch."""
    out = coverage.copy()
    out["scope_eligible"] = True
    out["scope_exclusion_reason"] = ""
    observed = set(zip(out.season.astype(int), out.week.astype(int)))
    missing_declared = set(SCOPE_EXCLUSIONS) - observed
    if missing_declared:
        raise ValueError(f"declared scope exclusions absent: {missing_declared}")
    for key, reason in SCOPE_EXCLUSIONS.items():
        mask = out.season.eq(key[0]) & out.week.eq(key[1])
        if not out.loc[mask, "mass_coverage"].lt(0.05).all():
            raise ValueError(f"declared scope exclusion unexpectedly matches: {key}")
        out.loc[mask, "scope_eligible"] = False
        out.loc[mask, "scope_exclusion_reason"] = reason
    unexpected = out[out.scope_eligible & out.mass_coverage.lt(0.90)]
    if not unexpected.empty:
        keys = list(zip(unexpected.season.astype(int),
                        unexpected.week.astype(int)))
        raise ValueError(f"unexpected Milly/snapshot scope or join mismatch: {keys}")
    return out
