#!/usr/bin/env python
"""Mechanical audit and frozen five-replicate incumbent seed report."""

from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402


REFERENCE = "20260812-pitclean-e80-selected-tabpfn-active-v2"
PANELS = {
    "R0": (REFERENCE, 0, 7331, True),
    "R1": ("20260813-incumbent-mcseed-r1-v1", 1137260708, 2690847602, False),
    "R2": ("20260813-incumbent-mcseed-r2-v1", 2875959182, 1630284992, False),
    "R3": ("20260813-incumbent-mcseed-r3-v1", 253722715, 3374646876, False),
    "R4": ("20260813-incumbent-mcseed-r4-v1", 1643280042, 3977633467, False),
}
POSITION_SPECS = {
    2023: "QB:0.965,RB:0.99,TE:0.945,WR:1.03",
    2024: "QB:0.905,RB:0.97,TE:0.95,WR:1.06",
    2025: "QB:0.925,RB:0.96,TE:0.94,WR:1.04",
}
TAILS = (240, 230, 220, 210, 200, 194, 187)
MASKS = (187, 194, 200, 210, 220)
STABLE_FEATURE_FIELDS = (
    "gsis_id", "name", "pos", "team", "opp", "game_id", "salary",
    "market_points", "target_share_last", "carry_share_last",
    "snap_share_last", "target_share_jump", "carry_share_jump",
    "snap_share_jump", "target_share_l4", "carry_share_l4",
    "snap_share_l4", "dk_points_l4", "implied_team_total", "spread",
    "game_total", "is_cold_start", "depth_rank", "depth_rank_delta",
    "team_vacated_target_share", "team_vacated_carry_share",
    "salary_delta_wow", "games_played_prior", "actual", "feature_missing",
    "component_mean_carries", "component_mean_catch_rate",
    "component_mean_interceptions", "component_mean_pass_attempts",
    "component_mean_pass_tds", "component_mean_rec_tds",
    "component_mean_rush_tds", "component_mean_targets",
    "component_mean_ypa", "component_mean_ypc", "component_mean_ypr",
    "model_ensemble_size", "model_member_spec", "ensemble_point_0",
    "ensemble_point_1", "ensemble_point_2",
    "fp_cov_receiver_source_season", "fp_cov_defense_source_season",
    "coverage_control_p30", "coverage_treatment_p30", "coverage_delta_30",
    "fp_route_source_season", "fp_route_source_week", "route_control_p30",
    "route_treatment_p30", "route_delta_30",
)


def _parse_pairs(value: str, separator: str) -> dict[str, str]:
    out = {}
    for item in str(value or "").split(separator):
        if not item:
            continue
        key, marker, val = item.partition("=")
        if marker:
            out[key] = val
    return out


def _load_candidates() -> pd.DataFrame:
    frames = []
    fields = (
        "panel_run_id, code_sha, lever_env, seeds, labels_complete, season, "
        "week, cand_ix, selected, selected_rank, players, actual_score, "
        "n_entries, n_sims, n_worlds, clear_bits_187, clear_bits_194, "
        "clear_bits_200, clear_bits_210, clear_bits_220"
    )
    for label, (panel, _, _, promoted) in PANELS.items():
        table = "replay_candidates" if promoted else "replay_candidates_staging"
        eligibility = "AND research_eligible" if promoted else ""
        frame = query_df(f"""
            SELECT {fields}
            FROM `{settings.predictions}.{table}`
            WHERE panel_run_id = '{panel}' {eligibility}
              AND season IN (2023, 2024, 2025)
            """)
        frame["replicate"] = label
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _load_features() -> pd.DataFrame:
    frames = []
    fields = ", ".join(("panel_run_id", "season", "week", "id",
                        *STABLE_FEATURE_FIELDS))
    for label, (panel, _, _, promoted) in PANELS.items():
        eligibility = "AND research_eligible" if promoted else ""
        frame = query_df(f"""
            SELECT {fields}
            FROM `{settings.predictions}.slate_player_features`
            WHERE panel_run_id = '{panel}' {eligibility}
              AND season IN (2023, 2024, 2025)
            """)
        frame["replicate"] = label
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _equal_series(left: pd.Series, right: pd.Series,
                  tolerance: float = 1e-10) -> pd.Series:
    both_null = left.isna() & right.isna()
    ln = pd.to_numeric(left, errors="coerce")
    rn = pd.to_numeric(right, errors="coerce")
    numeric = left.notna() & right.notna() & ln.notna() & rn.notna()
    close = numeric & (ln - rn).abs().le(tolerance)
    text = (~numeric) & left.astype(str).eq(right.astype(str))
    return both_null | close | text


def mechanical_failures(candidates: pd.DataFrame, features: pd.DataFrame,
                        expected_code_sha: str) -> list[str]:
    failures = []
    by_rep = {r: f.copy() for r, f in candidates.groupby("replicate")}
    if set(by_rep) != set(PANELS):
        return ["candidate replicate set is incomplete"]
    reference_levers = {}
    for label, (panel, base_seed, role_seed, _) in PANELS.items():
        frame = by_rep[label]
        if frame.empty:
            failures.append(f"{label} candidate panel is empty")
            continue
        if label != "R0" and not frame.code_sha.astype(str).eq(
                expected_code_sha).all():
            failures.append(f"{label} code SHA differs")
        if set(frame.season.astype(int)) != set(POSITION_SPECS):
            failures.append(f"{label} season set differs")
        groups = frame.groupby(["season", "week"])
        if len(groups) != 54:
            failures.append(f"{label} has {len(groups)} slates, want 54")
        if not frame.labels_complete.fillna(False).astype(bool).all() or \
                frame.actual_score.isna().any():
            failures.append(f"{label} labels are incomplete")
        if not frame.n_entries.eq(80).all() or not frame.n_sims.eq(10000).all() \
                or not frame.n_worlds.eq(10000).all():
            failures.append(f"{label} entries/world counts differ")
        selected = groups.selected.sum()
        if len(selected) and not selected.eq(80).all():
            failures.append(f"{label} does not select exactly 80 per slate")
        if frame[frame.selected].duplicated(["season", "week", "players"]).any():
            failures.append(f"{label} selected rosters are not distinct")
        if frame.duplicated(["season", "week", "cand_ix"]).any():
            failures.append(f"{label} candidate indices are duplicated")
        seed_values = frame.seeds.fillna("").astype(str).unique()
        if len(seed_values) != 1:
            failures.append(f"{label} has multiple seed identities")
        else:
            seeds = _parse_pairs(seed_values[0], ";")
            observed_base = int(seeds.get("REPLAY_PROJECTION_SEED", "0"))
            observed_role = int(seeds.get("ROLE_BELIEF_SEED", "7331"))
            if (observed_base, observed_role) != (base_seed, role_seed):
                failures.append(f"{label} seed pair differs")
        for season, spec in POSITION_SPECS.items():
            values = frame.loc[frame.season.eq(season), "lever_env"].unique()
            if len(values) != 1:
                failures.append(f"{label} {season} lever identity is not unique")
                continue
            lever = _parse_pairs(values[0], ",")
            if lever.get("ROLE_BELIEF_SEED", "7331") != str(role_seed):
                failures.append(f"{label} {season} role seed lever differs")
            if int(lever.get("REPLAY_PROJECTION_SEED", "0")) != base_seed:
                failures.append(f"{label} {season} baseline seed lever differs")
            if lever.get("SERVED_POSITION_SCALES") != spec:
                failures.append(f"{label} {season} position scales differ")
            common = {k: v for k, v in lever.items()
                      if k not in {"REPLAY_PROJECTION_SEED",
                                   "ROLE_BELIEF_SEED"}}
            if label == "R0":
                reference_levers[season] = common
            elif reference_levers.get(season) != common:
                failures.append(f"{label} {season} nonseed levers differ")

    ref = by_rep["R0"][["season", "week", "players", "actual_score"]]
    for label in ("R1", "R2", "R3", "R4"):
        joined = ref.merge(
            by_rep[label][["season", "week", "players", "actual_score"]],
            on=["season", "week", "players"], suffixes=("_r0", "_rx"))
        if joined.empty or not _equal_series(
                joined.actual_score_r0, joined.actual_score_rx).all():
            failures.append(f"{label} shared-roster actual scores differ")
        changed = (set(map(tuple, by_rep[label][["season", "week", "players"]]
                           .itertuples(index=False, name=None))) !=
                   set(map(tuple, ref[["season", "week", "players"]]
                           .itertuples(index=False, name=None))))
        if not changed:
            failures.append(f"{label} candidate membership did not change")

    by_feat = {r: f.copy() for r, f in features.groupby("replicate")}
    if set(by_feat) != set(PANELS):
        failures.append("feature replicate set is incomplete")
        return failures
    keys = ["season", "week", "id"]
    for label, frame in by_feat.items():
        if frame.duplicated(keys).any():
            failures.append(f"{label} feature keys are duplicated")
    left = by_feat["R0"].set_index(keys).sort_index()
    for label in ("R1", "R2", "R3", "R4"):
        right = by_feat[label].set_index(keys).sort_index()
        if not left.index.equals(right.index):
            failures.append(f"{label} feature keys differ")
            continue
        for field in STABLE_FEATURE_FIELDS:
            if not _equal_series(left[field], right[field]).all():
                failures.append(f"{label} stable feature {field} differs")
    return failures


def _support_count(value: str) -> int:
    return int.from_bytes(bytes.fromhex(value), "big").bit_count()


def _canonical_roster(value: str) -> str:
    players = [player for player in str(value).split(",") if player]
    return ",".join(sorted(players))


def replicate_metrics(frame: pd.DataFrame) -> tuple[dict, pd.Series, dict, dict]:
    weekly_selected = frame[frame.selected].groupby(
        ["season", "week"]).actual_score.max().sort_index()
    weekly_oracle = frame.groupby(["season", "week"]).actual_score.max().sort_index()
    selected = frame[frame.selected]
    result = {
        "candidate_rows": int(len(frame)),
        "selected_tail": {str(t): int((weekly_selected >= t).sum()) for t in TAILS},
        "oracle_tail": {str(t): int((weekly_oracle >= t).sum()) for t in TAILS},
        "selected_best": {
            "mean": float(weekly_selected.mean()),
            "median": float(weekly_selected.median()),
            "std": float(weekly_selected.std(ddof=1)),
            "min": float(weekly_selected.min()),
            "max": float(weekly_selected.max()),
        },
        "selected_support": {},
    }
    for threshold in MASKS:
        values = selected[f"clear_bits_{threshold}"].map(_support_count)
        result["selected_support"][str(threshold)] = {
            "mean": float(values.mean()), "median": float(values.median()),
            "zero_fraction": float(values.eq(0).mean()),
            "q10": float(values.quantile(.10)),
            "q25": float(values.quantile(.25)),
            "q75": float(values.quantile(.75)),
            "q90": float(values.quantile(.90)),
            "maximum": int(values.max()),
        }
    result["weekly_selected_best"] = [
        {"season": int(season), "week": int(week), "score": float(score)}
        for (season, week), score in weekly_selected.items()
    ]
    rosters = {
        (int(season), int(week)): set(
            group.players.astype(str).map(_canonical_roster))
        for (season, week), group in selected.groupby(["season", "week"])
    }
    pools = {
        (int(season), int(week)): set(
            group.players.astype(str).map(_canonical_roster))
        for (season, week), group in frame.groupby(["season", "week"])
    }
    return result, weekly_selected, rosters, pools


def seed_report(candidates: pd.DataFrame) -> dict:
    metrics, weekly, rosters, pools = {}, {}, {}, {}
    for label, frame in candidates.groupby("replicate"):
        (metrics[label], weekly[label], rosters[label], pools[label]) = (
            replicate_metrics(frame))
    pairwise = []
    for left, right in combinations(sorted(metrics), 2):
        deltas = (weekly[left] - weekly[right]).abs()
        slate_keys = sorted(set(rosters[left]) & set(rosters[right]))
        selected_overlap = np.array([
            len(rosters[left][key] & rosters[right][key])
            for key in slate_keys], dtype=float)
        candidate_jaccard = np.array([
            len(pools[left][key] & pools[right][key]) /
            len(pools[left][key] | pools[right][key])
            for key in slate_keys], dtype=float)
        pairwise.append({
            "left": left, "right": right,
            "weeks_abs_delta_gt_5": int((deltas > 5).sum()),
            "slates": len(slate_keys),
            "mean_selected_roster_overlap_of_80": float(
                selected_overlap.mean()),
            "median_selected_roster_overlap_of_80": float(
                np.median(selected_overlap)),
            "mean_candidate_jaccard": float(candidate_jaccard.mean()),
        })
    aligned = pd.concat(weekly, axis=1)
    slate_range = aligned.max(axis=1) - aligned.min(axis=1)
    envelope = {"selected_tail": {}, "oracle_tail": {}}
    for kind in envelope:
        for threshold in TAILS:
            vals = np.array([metrics[r][kind][str(threshold)]
                             for r in sorted(metrics)], dtype=float)
            envelope[kind][str(threshold)] = {
                "min": int(vals.min()), "max": int(vals.max()),
                "range": int(vals.max() - vals.min()),
                "mean": float(vals.mean()), "sample_std": float(vals.std(ddof=1)),
            }
    extreme_range = max(envelope["selected_tail"][str(t)]["range"]
                        for t in (210, 220, 230, 240))
    interpretation = ("stable" if extreme_range == 0 else
                      "borderline" if extreme_range == 1 else
                      "materially-monte-carlo-sensitive")
    overlap_means = np.array([
        row["mean_selected_roster_overlap_of_80"] for row in pairwise])
    overlap_medians = np.array([
        row["median_selected_roster_overlap_of_80"] for row in pairwise])
    return {
        "replicates": metrics,
        "envelope": envelope,
        "pairwise": pairwise,
        "pairwise_summary": {
            "mean_of_pairwise_mean_selected_overlap": float(
                overlap_means.mean()),
            "median_of_pairwise_median_selected_overlap": float(
                np.median(overlap_medians)),
        },
        "slate_score_range": {
            "mean": float(slate_range.mean()),
            "median": float(slate_range.median()),
            "maximum": float(slate_range.max()),
            "weeks_gt_5": int((slate_range > 5).sum()),
            "weeks_gt_10": int((slate_range > 10).sum()),
            "weeks_gt_20": int((slate_range > 20).sum()),
        },
        "interpretation": interpretation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()
    candidates = _load_candidates()
    features = _load_features()
    failures = mechanical_failures(candidates, features, args.expected_code_sha)
    report = {
        "protocol": "2026-08-13-incumbent-seed-variance-protocol",
        "reference": REFERENCE,
        "panel_ids": {key: value[0] for key, value in PANELS.items()},
        "mechanical_passes": not failures,
        "failures": failures,
    }
    if not failures:
        report["result"] = seed_report(candidates)
    print("INCUMBENT_SEED_VARIANCE_JSON=" + json.dumps(
        report, separators=(",", ":"), sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
