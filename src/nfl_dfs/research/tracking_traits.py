"""Tracking-derived v0 trait aggregates (Workstream C, plan §7.3, §7.6).

BDB 2026 pre-throw tracking frames (2023 regular season, pass plays
only — see the selection-bias note in the data catalog) reduced to
slowly-changing TRAIT priors per (nfl_id, position, season). v0 is
deterministic aggregation only; the §7.4-7.5 graph encoder is a later
phase and explicitly out of scope here.

Canonical coordinates (§7.3): every play is oriented offense
left-to-right. ``play_direction == "left"`` plays are rotated 180°
about the field center (x -> 120-x, y -> 53.3-y, angles += 180°), so a
play and its mirror produce byte-identical canonical frames — the
invariant the tests pin. ``absolute_yardline_number`` is flipped the
same way and kept as goal-line distance (110 - canonical LOS x).

Traits (v0):
- receiver rows (role Targeted Receiver / Other Route Runner):
  mean + p90 speed, acceleration burst (p90 of ``a``), route-depth
  proxy (canonical downfield x displacement, first -> last pre-throw
  frame, per play), and for the targeted receiver a separation proxy
  (distance to the nearest Defensive Coverage player at the final
  pre-throw frame);
- defender rows (role Defensive Coverage): closing-speed proxy
  (p90 of ``s``);
- §7.6 coverage metadata: frames, plays by role, weeks seen, recency.

The accumulator streams one week-file at a time (the box crashes under
load): ``update()`` takes a single canonicalized week frame — whole
plays only, plays never span files — and holds per-player float32
value arrays (~tens of MB across a season), so peak memory stays a
single week's frame. Quantiles are computed once at ``finalize`` over
the concatenated arrays, which is what makes streaming exactly
equivalent to processing the concatenated season in one call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = ["INPUT_USECOLS", "INPUT_DTYPES", "FIELD_LENGTH", "FIELD_WIDTH",
           "read_week_file", "canonicalize", "TraitAccumulator"]

FIELD_LENGTH = 120.0   # yards, end line to end line
FIELD_WIDTH = 53.3     # yards (53 1/3)

RECEIVER_ROLES = ("Targeted Receiver", "Other Route Runner")
TARGET_ROLE = "Targeted Receiver"
DEFENDER_ROLE = "Defensive Coverage"

# Explicit dtypes + usecols: one 2023 week file is ~285k rows x 23 cols;
# trimmed and typed it stays well under the ~2GB budget.
INPUT_USECOLS = [
    "game_id", "play_id", "nfl_id", "frame_id", "play_direction",
    "absolute_yardline_number", "player_name", "player_birth_date",
    "player_position", "player_role", "x", "y", "s", "a", "dir", "o",
]
INPUT_DTYPES = {
    "game_id": "int64", "play_id": "int32", "nfl_id": "int32",
    "frame_id": "int32", "play_direction": "category",
    "absolute_yardline_number": "float32", "player_name": "category",
    "player_birth_date": "category", "player_position": "category",
    "player_role": "category",
    "x": "float32", "y": "float32", "s": "float32", "a": "float32",
    "dir": "float32", "o": "float32",
}


def read_week_file(path) -> pd.DataFrame:
    """One input_2023_wNN.csv, typed and trimmed. Never call this on
    more than one file at a time — process, accumulate, discard."""
    return pd.read_csv(path, usecols=INPUT_USECOLS, dtype=INPUT_DTYPES)


def canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    """Orient every play offense left-to-right (§7.3).

    Left-direction plays are rotated 180° about field center; angular
    columns get +180° mod 360. Adds ``dist_to_goal`` (yards from the
    canonical LOS to the offense's goal line) and drops
    ``play_direction`` (spent). Returns a new frame; input untouched.
    """
    out = df.copy()
    left = (df["play_direction"] == "left").to_numpy()
    for col, span in (("x", FIELD_LENGTH), ("y", FIELD_WIDTH)):
        v = out[col].to_numpy(dtype="float32", copy=True)
        v[left] = np.float32(span) - v[left]
        out[col] = v
    for col in ("dir", "o"):
        if col in out.columns:
            v = out[col].to_numpy(dtype="float32", copy=True)
            v[left] = np.mod(v[left] + np.float32(180.0), np.float32(360.0))
            out[col] = v
    los = out["absolute_yardline_number"].to_numpy(dtype="float32", copy=True)
    los[left] = np.float32(FIELD_LENGTH) - los[left]
    out["absolute_yardline_number"] = los
    out["dist_to_goal"] = np.float32(FIELD_LENGTH - 10.0) - los
    return out.drop(columns=["play_direction"])


@dataclass
class _PlayerAcc:
    name: str = ""
    birth_date: str | None = None
    position: str = ""
    frames: int = 0
    recv_plays: int = 0
    targeted_plays: int = 0
    def_plays: int = 0
    weeks: set = field(default_factory=set)
    recv_speed: list = field(default_factory=list)   # float32 arrays
    recv_accel: list = field(default_factory=list)
    def_speed: list = field(default_factory=list)
    separations: list = field(default_factory=list)  # float scalars
    route_depths: list = field(default_factory=list)


class TraitAccumulator:
    """Streaming per-player trait accumulator; §7.6 metadata included."""

    def __init__(self) -> None:
        self._players: dict[int, _PlayerAcc] = {}

    def _acc(self, nfl_id: int) -> _PlayerAcc:
        return self._players.setdefault(int(nfl_id), _PlayerAcc())

    def update(self, canon: pd.DataFrame, week: int) -> dict:
        """Fold one CANONICALIZED week frame in (whole plays only).
        Returns per-call coverage stats for the driver's report."""
        role = canon["player_role"].astype(str)
        is_recv = role.isin(RECEIVER_ROLES).to_numpy()
        is_def = (role == DEFENDER_ROLE).to_numpy()

        # identity + frame counts, all rows
        meta = canon.groupby("nfl_id", observed=True).agg(
            name=("player_name", "first"),
            birth_date=("player_birth_date", "first"),
            position=("player_position", "first"),
            frames=("frame_id", "size"))
        for nfl_id, m in meta.iterrows():
            a = self._acc(nfl_id)
            a.name = a.name or str(m["name"])
            a.birth_date = a.birth_date or (
                None if pd.isna(m["birth_date"]) else str(m["birth_date"]))
            a.position = a.position or str(m["position"])
            a.frames += int(m["frames"])
            a.weeks.add(int(week))

        # per-role speed/accel samples + play counts
        for mask, speed_attr, accel_attr, plays_attr in (
                (is_recv, "recv_speed", "recv_accel", "recv_plays"),
                (is_def, "def_speed", None, "def_plays")):
            sub = canon.loc[mask]
            for nfl_id, g in sub.groupby("nfl_id", observed=True):
                a = self._acc(nfl_id)
                getattr(a, speed_attr).append(
                    g["s"].to_numpy(dtype="float32"))
                if accel_attr:
                    getattr(a, accel_attr).append(
                        g["a"].to_numpy(dtype="float32"))
                n_plays = g.groupby(["game_id", "play_id"],
                                    observed=True).ngroups
                setattr(a, plays_attr, getattr(a, plays_attr) + n_plays)

        # route-depth proxy: canonical downfield displacement per play
        recv = canon.loc[is_recv].sort_values("frame_id")
        depth = recv.groupby(["game_id", "play_id", "nfl_id"],
                             observed=True)["x"].agg(["first", "last"])
        for (_, _, nfl_id), row in depth.iterrows():
            self._acc(nfl_id).route_depths.append(
                float(row["last"] - row["first"]))

        # separation proxy at the final pre-throw frame
        last_frame = canon.groupby(["game_id", "play_id"],
                                   observed=True)["frame_id"].transform("max")
        final = canon.loc[canon["frame_id"] == last_frame]
        final_role = role.loc[final.index]
        tgt = final.loc[final_role == TARGET_ROLE,
                        ["game_id", "play_id", "nfl_id", "x", "y"]]
        dfd = final.loc[final_role == DEFENDER_ROLE,
                        ["game_id", "play_id", "x", "y"]]
        pair = tgt.merge(dfd, on=["game_id", "play_id"],
                         suffixes=("", "_d"))
        if len(pair):
            d = np.hypot(pair["x"] - pair["x_d"], pair["y"] - pair["y_d"])
            sep = d.groupby(
                [pair["game_id"], pair["play_id"], pair["nfl_id"]]).min()
            for (_, _, nfl_id), val in sep.items():
                a = self._acc(nfl_id)
                a.separations.append(float(val))
                a.targeted_plays += 1

        return {"week": int(week), "rows": int(len(canon)),
                "plays": int(canon.groupby(["game_id", "play_id"],
                                           observed=True).ngroups),
                "players": int(canon["nfl_id"].nunique())}

    @staticmethod
    def _stats(chunks: list) -> tuple[float, float, int]:
        """(mean, p90, n) over concatenated float32 chunks — order-free,
        so streaming == concatenated."""
        if not chunks:
            return float("nan"), float("nan"), 0
        v = np.concatenate(chunks)
        return float(v.mean()), float(np.quantile(v, 0.9)), int(v.size)

    def finalize(self, season: int) -> pd.DataFrame:
        """Tidy traits per (nfl_id, position, season)."""
        rows = []
        for nfl_id in sorted(self._players):
            a = self._players[nfl_id]
            rs_mean, rs_p90, rs_n = self._stats(a.recv_speed)
            _, ra_p90, _ = self._stats(a.recv_accel)
            _, ds_p90, ds_n = self._stats(a.def_speed)
            sep = np.asarray(a.separations, dtype="float64")
            dep = np.asarray(a.route_depths, dtype="float64")
            rows.append({
                "nfl_id": nfl_id, "player_name": a.name,
                "birth_date": a.birth_date, "position": a.position,
                "season": season,
                "play_type_coverage": "pass_pre_throw",
                "weeks_seen": len(a.weeks),
                "last_week": max(a.weeks) if a.weeks else 0,
                "frames": a.frames,
                "recv_plays": a.recv_plays,
                "targeted_plays": a.targeted_plays,
                "def_plays": a.def_plays,
                "recv_speed_mean": rs_mean,
                "recv_speed_p90": rs_p90,
                "recv_accel_p90": ra_p90,
                "recv_speed_n": rs_n,
                "separation_mean": float(sep.mean()) if sep.size else float("nan"),
                "separation_n": int(sep.size),
                "route_depth_mean": float(dep.mean()) if dep.size else float("nan"),
                "route_depth_p90": float(np.quantile(dep, 0.9)) if dep.size else float("nan"),
                "def_close_speed_p90": ds_p90,
                "def_speed_n": ds_n,
            })
        return pd.DataFrame(rows)
