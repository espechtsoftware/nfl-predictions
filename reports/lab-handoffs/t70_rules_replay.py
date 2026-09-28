#!/usr/bin/env python3
"""Replay the T-70 rules (operator decision 2, 5435c539; production D1) on a settled week's T-70 state. WRITES NOTHING.

Runs production's own `project()` twice on the week's slate features, once with the rules off and once with
T70_ACTIVE_Q=1 T70_VACATED_BUMP=1, with each player's DK status taken from the last dk_salaries pull before the cutoff
and the rules' clock fixed there (T70_NOW). `run_projections.load_dataframe` is replaced by a guard that refuses, so the
monitor logs `project()` normally appends are never written. Prints the four receipt columns and the projection change
for the named players and for every row the rules touched.

    python reports/lab-handoffs/t70_rules_replay.py --season 2026 --week 3 --group 153769 --cutoff 2026-09-27T15:50:00Z \
        --players "Kenyon Sadiq,Isaiah Williams,Jaylen Warren,Brock Bowers,Zay Flowers,Mike Evans,Jalen Coker"
"""
from __future__ import annotations

import argparse
import logging
import os

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--group", type=int, required=True); ap.add_argument("--cutoff", required=True)
    ap.add_argument("--players", default=""); ap.add_argument("--sims", type=int, default=None)
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    from nfl_dfs.inference import run_projections as rp
    from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
    from nfl_dfs.models.train_job import load_latest_component_models

    def _refuse(*_a, **_k):
        raise RuntimeError("t70_rules_replay writes nothing")
    rp.load_dataframe = _refuse          # the monitor-log writes inside project() are caught and logged there

    feats = rp.upcoming_slate_features(a.season, a.week, as_of=a.cutoff)   # the slate as it stood at the cutoff
    st = query_df(f"""SELECT dk_player_id, status FROM `{settings.raw}.dk_salaries`
                      WHERE draft_group_id = {a.group} AND pulled_at <= TIMESTAMP('{a.cutoff.replace('Z', '')}')
                      QUALIFY ROW_NUMBER() OVER (PARTITION BY dk_player_id ORDER BY pulled_at DESC) = 1""")
    smap = dict(zip(st.dk_player_id.astype("Int64").astype(str), st.status))
    key = feats.dk_player_id.astype("Int64").astype(str)
    feats["status"] = key.map(smap).where(key.isin(smap), feats.get("status"))
    print(f"slate rows {len(feats)}; statuses from the last pull before {a.cutoff}: {int(key.isin(smap).sum())} matched")
    skill = feats[feats.dk_position.isin(["QB", "RB", "WR", "TE"])].reset_index(drop=True)
    policy = ADOPTED_CLASSIC_POLICY
    model, version = load_latest_component_models(policy.model_variant)
    runs = {}
    for label, env in (("off", {"T70_ACTIVE_Q": "0", "T70_VACATED_BUMP": "0"}),
                       ("on", {"T70_ACTIVE_Q": "1", "T70_VACATED_BUMP": "1", "T70_NOW": a.cutoff})):
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            penv = policy.engine_environment(os.environ)
            n = a.sims or int(penv["LIVE_SIMS"])
            runs[label] = rp.project(skill.copy(), model, version, a.season, a.week, n_sims=n,
                                     adjust=rp._cascade_adjuster(a.season), policy_env=penv)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    off, on = runs["off"], runs["on"]
    cols = [c for c in ("t70_active_q", "t70_vacated_gross", "t70_cascade_effect", "t70_vacated_net") if c in on.columns]
    m = on[["gsis_id", "display_name", "team", "position", "proj_points"] + cols].merge(
        off[["gsis_id", "proj_points"]].rename(columns={"proj_points": "proj_off"}), on="gsis_id", how="left")
    m["delta"] = (m.proj_points - m.proj_off).round(2)
    names = [s.strip() for s in a.players.split(",") if s.strip()]
    pd.set_option("display.width", 220)
    print(f"model {version}; rules ON clock {a.cutoff}")
    if names:
        print("\nnamed players:"); print(m[m.display_name.isin(names)].round(2).to_string(index=False))
    ruled = m[(m.get("t70_active_q", False) == True) | (m.get("t70_vacated_gross", 0) > 0)]  # noqa: E712
    print(f"\nevery row a rule applied to ({len(ruled)}; other deltas are simulation noise between the two passes):")
    print(ruled.sort_values("delta").round(2).to_string(index=False))
    q = feats.loc[feats.get("status", pd.Series(dtype=object)).astype(str).str.upper().isin(["Q", "QUESTIONABLE"]),
                  [c for c in ("display_name", "status", "injury_status", "game_start") if c in feats.columns]]
    print(f"\nQuestionable at the cutoff pull ({len(q)}), for checking the activation rule's inputs:")
    print(q.to_string(index=False))


if __name__ == "__main__":
    main()
