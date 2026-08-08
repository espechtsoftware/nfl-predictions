"""Mechanically evaluate the frozen fixed-budget role-belief panel.

This reads staging because a failed treatment must never be promoted merely
to score it. It exits nonzero on any mechanical mismatch or adoption-gate
failure and emits a JSON record suitable for the panel run directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402


def _validate_panel_id(panel: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", panel):
        raise ValueError(f"invalid panel id {panel!r}")


def _load(panel: str) -> pd.DataFrame:
    _validate_panel_id(panel)
    return query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, players, selected,
               actual_score, code_sha, config_hash, lever_env, seeds
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id = '{panel}'""")


def _load_source(panel: str) -> pd.DataFrame:
    _validate_panel_id(panel)
    return query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, players, selected,
               actual_score, code_sha, config_hash, lever_env, seeds
        FROM `{settings.predictions}.replay_candidates`
        WHERE panel_run_id = '{panel}' AND research_eligible""")


def _control_reproduces_source(source: pd.DataFrame,
                               control: pd.DataFrame) -> tuple[bool, str]:
    """Require the paired control to be the accepted baseline, not a proxy."""
    keys = ["season", "week", "cand_ix"]
    cols = keys + ["tag", "all_tags", "players", "selected", "actual_score"]
    if source.duplicated(keys).any() or control.duplicated(keys).any():
        return False, "duplicate source/control candidate keys"
    check = source[cols].merge(
        control[cols], on=keys, how="outer", suffixes=("_source", "_control"),
        indicator=True, validate="one_to_one")
    missing = int(check._merge.ne("both").sum())
    mismatches = 0
    both = check[check._merge.eq("both")]
    for col in ("tag", "all_tags", "players", "selected"):
        mismatches += int(both[f"{col}_source"].ne(
            both[f"{col}_control"]).sum())
    mismatches += int((both.actual_score_source -
                       both.actual_score_control).abs().gt(1e-9).sum())
    same_sha = (source.code_sha.nunique(dropna=False) == 1
                and control.code_sha.nunique(dropna=False) == 1
                and source.code_sha.iloc[0] == control.code_sha.iloc[0])
    ok = missing == 0 and mismatches == 0 and same_sha
    return ok, (f"missing={missing} field_mismatches={mismatches} "
                f"same_code_sha={same_sha}")


def _slates(d: pd.DataFrame) -> pd.DataFrame:
    return d.groupby(["season", "week"]).apply(
        lambda g: pd.Series({
            "n": len(g),
            "selected_best": float(g.loc[g.selected, "actual_score"].max()),
            "oracle": float(g.actual_score.max()),
        }), include_groups=False).reset_index()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("control")
    ap.add_argument("treatment")
    ap.add_argument("--source", required=True,
                    help="accepted same-image baseline panel")
    ap.add_argument("--output")
    a = ap.parse_args()
    source = _load_source(a.source)
    control, treatment = _load(a.control), _load(a.treatment)
    failures: list[str] = []
    if source.empty or control.empty or treatment.empty:
        print("missing panel rows", file=sys.stderr)
        return 2
    for name, frame in (("source", source), ("control", control),
                        ("treatment", treatment)):
        if frame.groupby(["season", "week"]).ngroups != 107:
            failures.append(f"{name} does not contain 107 slates")
        for col in ("code_sha", "config_hash", "lever_env", "seeds"):
            if frame[col].nunique(dropna=False) != 1:
                failures.append(f"{name} has mixed {col}")

    source_reproduced, source_detail = _control_reproduces_source(
        source, control)
    if not source_reproduced:
        failures.append(
            "control does not exactly reproduce accepted source baseline: "
            + source_detail)

    c, t = _slates(control), _slates(treatment)
    pair = c.merge(t, on=["season", "week"], suffixes=("_control", "_treatment"),
                   validate="one_to_one")
    unequal = pair[pair.n_control != pair.n_treatment]
    if len(pair) != 107 or not unequal.empty:
        failures.append(
            f"realized pools are not exactly paired: slates={len(pair)} "
            f"unequal={len(unequal)}")

    epi_count = treatment[treatment.tag.eq("epi")].groupby(
        ["season", "week"]).size().reindex(
            pd.MultiIndex.from_frame(pair[["season", "week"]]), fill_value=0)
    if len(epi_count) != 107 or not epi_count.eq(12).all():
        failures.append(
            f"role replacement quota not realized on all slates: "
            f"range={int(epi_count.min())}-{int(epi_count.max())}")

    # A role candidate must create a genuinely new actual frontier, not just
    # rearrange selection among incumbent-equivalent rosters.
    control_rosters = {
        (int(s), int(w)): set(g.players.astype(str))
        for (s, w), g in control.groupby(["season", "week"])
    }
    role = treatment[treatment.tag.eq("epi")].copy()
    role["novel"] = role.apply(
        lambda r: str(r.players) not in control_rosters[(int(r.season), int(r.week))],
        axis=1)
    novel = role[role.novel]
    novel_best = novel.groupby(["season", "week"]).actual_score.max().rename(
        "novel_role_best")
    pair = pair.merge(novel_best, on=["season", "week"], how="left")
    frontier = pair[
        pair.novel_role_best.fillna(float("-inf")) > pair.oracle_control + 1e-9]
    if frontier.empty:
        failures.append("no novel role candidate improved a control slate frontier")

    def totals(frame: pd.DataFrame) -> dict:
        return {
            "clear_187": int((frame.selected_best >= 187).sum()),
            "clear_194": int((frame.selected_best >= 194).sum()),
            "clear_200": int((frame.selected_best >= 200).sum()),
            "oracle_194": int((frame.oracle >= 194).sum()),
            "mean": float(frame.selected_best.mean()),
            "median": float(frame.selected_best.median()),
        }

    cm = totals(pair.rename(columns={
        "selected_best_control": "selected_best",
        "oracle_control": "oracle"}))
    tm = totals(pair.rename(columns={
        "selected_best_treatment": "selected_best",
        "oracle_treatment": "oracle"}))
    by_season = pair.groupby("season").apply(
        lambda g: pd.Series({
            "control_194": int((g.selected_best_control >= 194).sum()),
            "treatment_194": int((g.selected_best_treatment >= 194).sum()),
        }), include_groups=False)
    by_season["lift"] = by_season.treatment_194 - by_season.control_194

    gate = {
        "clear_lift_at_least_2": tm["clear_194"] >= cm["clear_194"] + 2,
        "four_seasons_nonnegative": int((by_season.lift >= 0).sum()) >= 4,
        "at_most_one_negative_season": int((by_season.lift < 0).sum()) <= 1,
        "mean_not_worse_by_more_than_0_5": tm["mean"] >= cm["mean"] - 0.5,
        "oracle_not_worse": tm["oracle_194"] >= cm["oracle_194"],
        "novel_role_frontier": len(frontier) >= 1,
        "exact_pool_pairing": len(pair) == 107 and unequal.empty,
        "exact_role_quota": (len(epi_count) == 107
                             and bool(epi_count.eq(12).all())),
        "control_reproduces_source": source_reproduced,
    }
    if not all(gate.values()):
        failures.append("one or more frozen adoption gates failed")
    report = {
        "source": a.source,
        "control": a.control,
        "treatment": a.treatment,
        "control_metrics": cm,
        "treatment_metrics": tm,
        "season_metrics": by_season.reset_index().to_dict("records"),
        "novel_role_candidates": int(len(novel)),
        "novel_role_frontier_weeks": frontier[
            ["season", "week"]].to_dict("records"),
        "gate": gate,
        "verdict": "ADOPT" if not failures else "REJECT",
        "failures": failures,
        "source_reproduction_detail": source_detail,
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    print(payload)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
