"""PREREG-O1's target, population and metric, shared by every ownership reader (O1 itself, A3) so they cannot drift
(reviewer 10-02: "use O1's population and matching, not a new one").

Target: realized Millionaire ownership counted from the contest's own lineups (book_vs_field_scoreboard.field_ownership_sql).
Population (O1 §Population): every main-slate player PRICED BY THE SOURCE and IN THE REALIZED TABLE. A player is matched to
the slate by DraftKings id when the source carries one, else by normalised name + team; to the realized table by
normalised name. Reported for all players and for skill players only. Name collisions (two slate players with one
normalised name) are printed and dropped, never silently merged.
Metric: Spearman rank correlation (average ranks for ties).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ownership_blend import norm  # noqa: E402

PROJECT = "nfl-predictions-503414"


def _key(v: object) -> str:
    """An id as the frame spells it: '1164402.0' and 1164402 are both '1164402'; a missing value is ''."""
    s = str(v).strip()
    if s.lower() in ("", "nan", "none", "<na>"):
        return ""
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s
SKILL = ("QB", "RB", "WR", "TE")


def realized(client, season: int, week: int, contest: str) -> pd.Series:
    from book_vs_field_scoreboard import field_ownership_sql
    d = client.query(field_ownership_sql(f"{PROJECT}.nfl_raw", season, week, contest)).to_dataframe()
    if d.empty:
        raise SystemExit(f"no lineups for contest {contest} in {season} week {week} (import the Millionaire standings first)")
    return pd.Series(d.own.to_numpy(float), index=d.display_name.map(norm)).groupby(level=0).max()


def slate(client, group: int, lock_utc: str) -> pd.DataFrame:
    d = client.query(f"""SELECT dk_player_id, display_name, position, team_abbr FROM `{PROJECT}.nfl_raw.dk_salaries`
        WHERE draft_group_id={int(group)} AND pulled_at < TIMESTAMP('{lock_utc}') QUALIFY pulled_at = MAX(pulled_at) OVER ()""").to_dataframe()
    d["key"] = d.display_name.map(norm); d["dk"] = d.dk_player_id.map(_key); d["pos"] = d.position.str.split("/").str[0]
    dup = d[d.duplicated("key", keep=False)]
    if len(dup):
        print(f"name collisions on the slate (dropped): {sorted(set(dup.display_name))}")
    return d[~d.key.isin(set(dup.key))].drop_duplicates("dk")


def attach(source: pd.DataFrame, sl: pd.DataFrame, value: str) -> pd.DataFrame:
    """The source's rows matched to the slate (DK id first, then name + team): key, pos, value."""
    s = source.copy(); s["key_src"] = s.get("display_name", s.get("name")).map(norm)
    out = []
    if "dk_player_id" in s:
        s["dk"] = s.dk_player_id.map(_key)
        m = sl.merge(s[["dk", value]], on="dk", how="inner"); out.append(m)
        rest = s[~s.dk.isin(set(m.dk))]
    else:
        rest = s
    team = "team" if "team" in rest else None
    if team:
        m2 = sl.merge(rest[["key_src", team, value]].rename(columns={"key_src": "key", team: "team_abbr"}), on=["key", "team_abbr"], how="inner")
    else:
        m2 = sl.merge(rest[["key_src", value]].rename(columns={"key_src": "key"}), on="key", how="inner")
    out.append(m2)
    return pd.concat(out, ignore_index=True).drop_duplicates("key")[["key", "pos", value]]


def population(src: pd.DataFrame, real: pd.Series) -> pd.DataFrame:
    """Players priced by the source and in the realized table (O1)."""
    return src[src.key.isin(set(real.index))]


def spearman(pred: pd.Series, real: pd.Series) -> float:
    return float(pred.rank().corr(real.reindex(pred.index).rank()))


def score_both(df: pd.DataFrame, value: str, real: pd.Series) -> dict:
    """Spearman over all and over skill players."""
    s = df.set_index("key")[value].astype(float); sk = df[df.pos.isin(SKILL)].set_index("key")[value].astype(float)
    return {"n": len(s), "spearman": round(spearman(s, real), 4), "n_skill": len(sk), "spearman_skill": round(spearman(sk, real), 4)}
