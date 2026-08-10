"""Walk-forward fixed-pool reranker for the accepted true-80 K=1 CE panel.

The only adoptable arm is the preregistered structure/provenance ridge model.
It predicts candidate residuals from strictly earlier seasons, applies a
bounded additive shift to every simulated world, and reruns the unchanged
194-point coverage selector. Candidate generation and the pool oracle remain
fixed. A within-slate shuffled-shift book is a negative control.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.optimizer.lineup import select_from_support  # noqa: E402
from nfl_dfs.research.panel_compare import metrics, tail_first_gate  # noqa: E402


PANEL = "20260809-e80-k1-ce12-c616390"
N_ENTRIES = 80
LINE = 194.0
RIDGE_ALPHA = 10.0
SHIFT_CAP = 15.0
SHUFFLE_SEED = 314159
TAGS = (
    "boom", "ce", "dark", "game", "lev", "qbvar", "hyper", "gumbel",
    "thesis", "wild", "qd", "midqb", "nostk", "lowsal",
)
FEATURES = (
    "sim_mean", "sim_sd", "sim_q50", "sim_q90", "sim_q99", "p_line",
    "salary", "n_tags", "stack_mates", "bring_back", "max_from_game",
    "n_games", "salary_left", *(f"tag_{tag}" for tag in TAGS),
)


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def load_panel(panel: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = _panel_id(panel)
    candidates = query_df(f"""
      SELECT season, week, cand_ix, players, selected, selected_rank,
             sim_mean, sim_sd, sim_q50, sim_q90, sim_q99, p_line, salary,
             actual_score, all_tags, score_artifact_uri
      FROM `{settings.predictions}.replay_candidates`
      WHERE panel_run_id = '{panel}' AND research_eligible
    """)
    player_features = query_df(f"""
      SELECT season, week, id, pos, team, opp, game_id
      FROM `{settings.predictions}.slate_player_features`
      WHERE panel_run_id = '{panel}' AND research_eligible
    """)
    return candidates, player_features


def _tag_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, str) or not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("all_tags must decode to a list")
    return [str(item) for item in parsed]


def build_structure_features(candidates: pd.DataFrame,
                             player_features: pd.DataFrame) -> pd.DataFrame:
    """Derive the frozen A1 feature set from immutable panel rows."""
    rows: list[dict] = []
    feature_slates = {
        (int(season), int(week)): group.set_index("id")
        for (season, week), group in player_features.groupby(["season", "week"])
    }
    for candidate in candidates.itertuples(index=False):
        key = (int(candidate.season), int(candidate.week))
        players = feature_slates.get(key)
        if players is None:
            raise ValueError(f"missing player snapshot for {key}")
        ids = [item for item in str(candidate.players).split(",") if item]
        missing = [player_id for player_id in ids if player_id not in players.index]
        if missing:
            raise ValueError(f"missing roster players for {key}: {missing[:4]}")
        roster = players.loc[ids]
        qb = roster[roster.pos.eq("QB")]
        qb_team = qb.team.iloc[0] if len(qb) else None
        qb_opp = qb.opp.iloc[0] if len(qb) else None
        stack_mates = int((
            roster.team.eq(qb_team)
            & roster.pos.isin(("RB", "WR", "TE"))).sum()) if qb_team else 0
        bring_back = int(roster.team.eq(qb_opp).sum()) if qb_opp else 0
        game_counts = roster.game_id.dropna().value_counts()
        tags = _tag_list(candidate.all_tags)
        row = {
            "season": int(candidate.season),
            "week": int(candidate.week),
            "cand_ix": int(candidate.cand_ix),
            "actual_score": float(candidate.actual_score),
            "sim_mean": float(candidate.sim_mean),
            "sim_sd": float(candidate.sim_sd),
            "sim_q50": float(candidate.sim_q50),
            "sim_q90": float(candidate.sim_q90),
            "sim_q99": float(candidate.sim_q99),
            "p_line": float(candidate.p_line),
            "salary": float(candidate.salary),
            "salary_left": 50_000.0 - float(candidate.salary),
            "n_tags": len(tags),
            "stack_mates": stack_mates,
            "bring_back": bring_back,
            "max_from_game": int(game_counts.max()) if len(game_counts) else 0,
            "n_games": int(len(game_counts)),
        }
        row.update({f"tag_{tag}": int(tag in tags) for tag in TAGS})
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.duplicated(["season", "week", "cand_ix"]).any():
        raise ValueError("duplicate candidate feature keys")
    return frame


def walk_forward_shifts(frame: pd.DataFrame) -> tuple[pd.Series, list[dict]]:
    """Fit the frozen ridge on seasons strictly before each served season."""
    shifts = pd.Series(0.0, index=frame.index, dtype=float)
    manifest: list[dict] = []
    for season in sorted(frame.season.unique()):
        train = frame[frame.season.lt(season)]
        test = frame[frame.season.eq(season)]
        train_seasons = sorted(int(value) for value in train.season.unique())
        if train.empty:
            manifest.append({
                "season": int(season), "train_seasons": [],
                "train_rows": 0, "served_rows": int(len(test)),
                "mode": "baseline_fallback",
            })
            continue
        x_train = train.loc[:, list(FEATURES)].astype(float)
        x_test = test.loc[:, list(FEATURES)].astype(float)
        residual = train.actual_score - train.sim_mean
        # Equal total weight per slate while preserving mean sample weight 1,
        # so alpha retains the scale of the original preregistration.
        counts = train.groupby(["season", "week"]).cand_ix.transform("size")
        weights = 1.0 / counts.astype(float)
        weights *= len(weights) / weights.sum()
        scaler = StandardScaler().fit(x_train, sample_weight=weights)
        model = Ridge(alpha=RIDGE_ALPHA).fit(
            scaler.transform(x_train), residual, sample_weight=weights)
        predicted = np.clip(
            model.predict(scaler.transform(x_test)), -SHIFT_CAP, SHIFT_CAP)
        shifts.loc[test.index] = predicted
        manifest.append({
            "season": int(season), "train_seasons": train_seasons,
            "train_rows": int(len(train)), "served_rows": int(len(test)),
            "mode": "ridge",
        })
    return shifts, manifest


def select_shifted(totals: np.ndarray, shifts: np.ndarray,
                   n_entries: int = N_ENTRIES) -> list[int]:
    adjusted = np.asarray(totals, dtype=float) + np.asarray(
        shifts, dtype=float)[:, None]
    clears = adjusted >= LINE
    return select_from_support(
        clears, clears.mean(axis=1), adjusted.mean(axis=1), n_entries)


def _download_totals(uri: str, client) -> np.ndarray:
    bucket, _, path = str(uri).replace("gs://", "").partition("/")
    if not bucket or not path:
        raise ValueError(f"invalid artifact URI {uri!r}")
    payload = client.bucket(bucket).blob(path).download_as_bytes()
    with np.load(io.BytesIO(payload)) as artifact:
        return np.asarray(artifact["totals"])


def source_book(candidates: pd.DataFrame) -> pd.DataFrame:
    return candidates.groupby(["season", "week"]).apply(
        lambda group: pd.Series({
            "selected_best": float(
                group.loc[group.selected, "actual_score"].max()),
            "oracle": float(group.actual_score.max()),
            "n_candidates": int(len(group)),
            "n_selected": int(group.selected.sum()),
        }), include_groups=False).reset_index()


def reranked_books(candidates: pd.DataFrame, frame: pd.DataFrame,
                   shifts: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, dict,
                                               list[str]]:
    from google.cloud import storage

    client = storage.Client()
    primary_rows: list[dict] = []
    shuffled_rows: list[dict] = []
    failures: list[str] = []
    moved_primary = 0
    moved_shuffled = 0
    artifacts_checked = 0
    lookup = frame.assign(shift=shifts).set_index(
        ["season", "week", "cand_ix"])
    for (season, week), unsorted in candidates.groupby(["season", "week"]):
        group = unsorted.sort_values("cand_ix").reset_index(drop=True)
        expected_ix = np.arange(len(group))
        if not np.array_equal(group.cand_ix.to_numpy(dtype=int), expected_ix):
            failures.append(f"non-contiguous cand_ix {season}w{week}")
            continue
        baseline = set(group.index[group.selected].tolist())
        if int(season) == min(candidates.season):
            primary = sorted(baseline)
            shuffled = sorted(baseline)
        else:
            try:
                totals = _download_totals(group.score_artifact_uri.iloc[0], client)
            except Exception as exc:  # pragma: no cover - cloud I/O failure
                failures.append(f"artifact download {season}w{week}: {exc}")
                continue
            if totals.shape[0] != len(group):
                failures.append(f"artifact row mismatch {season}w{week}")
                continue
            artifacts_checked += 1
            slate_shifts = np.array([
                lookup.loc[(season, week, int(cand_ix)), "shift"]
                for cand_ix in group.cand_ix
            ], dtype=float)
            primary = select_shifted(totals, slate_shifts)
            rng = np.random.default_rng(
                SHUFFLE_SEED + int(season) * 100 + int(week))
            shuffled = select_shifted(totals, rng.permutation(slate_shifts))
        moved_primary += len(baseline.symmetric_difference(set(primary))) // 2
        moved_shuffled += len(baseline.symmetric_difference(set(shuffled))) // 2
        common = {
            "season": int(season), "week": int(week),
            "oracle": float(group.actual_score.max()),
            "n_candidates": int(len(group)), "n_selected": N_ENTRIES,
        }
        primary_rows.append({
            **common,
            "selected_best": float(group.iloc[primary].actual_score.max()),
        })
        shuffled_rows.append({
            **common,
            "selected_best": float(group.iloc[shuffled].actual_score.max()),
        })
    mechanism = {
        "artifacts_checked": artifacts_checked,
        "primary_selected_slots_changed": moved_primary,
        "shuffled_selected_slots_changed": moved_shuffled,
        "served_shift_rows": int((shifts.abs() > 1e-12).sum()),
        "max_abs_shift": float(shifts.abs().max()),
        "cold_start_shift_rows": int(
            (shifts[frame.season.eq(frame.season.min())].abs() > 1e-12).sum()),
    }
    return (pd.DataFrame(primary_rows), pd.DataFrame(shuffled_rows),
            mechanism, failures)


def _rank(book: pd.DataFrame) -> tuple:
    report = metrics(book)
    return (
        report["clear_200"], report["clear_210"], report["clear_220"],
        report["clear_194"], report["mean_best"],
    )


def reranker_gate(source: pd.DataFrame, primary: pd.DataFrame,
                  shuffled: pd.DataFrame, failures: list[str]) -> dict:
    gate = tail_first_gate(source, primary)
    gate["beats_shuffled_control"] = _rank(primary) > _rank(shuffled)
    gate["mechanism_valid"] = not failures
    gate["passes"] = all(value for key, value in gate.items()
                         if key != "passes")
    return gate


def _season_metrics(source: pd.DataFrame, primary: pd.DataFrame,
                    shuffled: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for season in sorted(source.season.unique()):
        row: dict[str, int] = {"season": int(season)}
        for name, book in (("source", source), ("primary", primary),
                           ("shuffled", shuffled)):
            season_book = book[book.season.eq(season)]
            for threshold in (187, 194, 200, 210, 220, 230, 240):
                row[f"{name}_{threshold}"] = int(
                    season_book.selected_best.ge(threshold).sum())
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", default=PANEL)
    args = parser.parse_args()
    candidates, player_features = load_panel(args.panel)
    failures: list[str] = []
    if candidates.groupby(["season", "week"]).ngroups != 107:
        failures.append("source does not contain 107 slates")
    if not candidates.groupby(["season", "week"]).selected.sum().eq(
            N_ENTRIES).all():
        failures.append("source does not select 80 entries every slate")
    frame = build_structure_features(candidates, player_features)
    shifts, training = walk_forward_shifts(frame)
    for item in training:
        if any(season >= item["season"] for season in item["train_seasons"]):
            failures.append("training manifest includes held-out/future season")
    source = source_book(candidates)
    primary, shuffled, mechanism, book_failures = reranked_books(
        candidates, frame, shifts)
    failures.extend(book_failures)
    if len(primary) != 107 or len(shuffled) != 107:
        failures.append("reranked books do not contain 107 slates")
    if mechanism["artifacts_checked"] != 90:
        failures.append("did not verify all 90 served-season artifacts")
    if mechanism["cold_start_shift_rows"]:
        failures.append("cold-start season received reranker shifts")
    if mechanism["max_abs_shift"] > SHIFT_CAP + 1e-12:
        failures.append("reranker shift exceeded frozen cap")
    if not mechanism["primary_selected_slots_changed"]:
        failures.append("reranker did not change the submitted book")
    gate = (reranker_gate(source, primary, shuffled, failures)
            if len(primary) == 107 and len(shuffled) == 107 else {})
    report = {
        "panel": args.panel,
        "arm": "A1_structure_walk_forward",
        "settings": {
            "entries": N_ENTRIES, "line": LINE,
            "ridge_alpha": RIDGE_ALPHA, "shift_cap": SHIFT_CAP,
            "shuffle_seed": SHUFFLE_SEED, "features": list(FEATURES),
        },
        "training_manifest": training,
        "mechanism": mechanism,
        "source_metrics": metrics(source),
        "primary_metrics": metrics(primary) if len(primary) else {},
        "shuffled_metrics": metrics(shuffled) if len(shuffled) else {},
        "season_metrics": (_season_metrics(source, primary, shuffled)
                           if len(primary) == 107 else []),
        "gate": gate,
        "disposition": ("pass" if gate.get("passes") else
                        "invalid" if failures else "reject"),
        "failures": failures,
    }
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
