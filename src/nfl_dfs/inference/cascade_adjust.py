"""Late-breaking inactive adjustment: the injury cascade (guide §8.4) wired
into the hourly inference pass.

Injuries reach projections through two complementary layers:

* ``team_week_vacated`` features (018/021/023) carry Wednesday-Friday "Out"
  designations into the feature matrix, so the models learn next-man-up
  bumps from history.
* This module handles what the feature build can't: status flips after
  features were built — the starter ruled out Sunday morning. Players the
  DK slate marks O/IR (or the report lists as Out) get their projections
  zeroed, and their opportunity is redistributed to slate teammates via
  ``graph.cascade.project_vacated_usage`` — measured with/without splits
  when the player has absence history, depth-chart-style weighting when
  history is thin.

The redistribution normalizes over slate teammates, so opportunity that
would really leak to unrosterable players is credited to rosterable ones —
a mild, deliberate overestimate: for DFS the cost of missing the next man
up exceeds the cost of slightly overpricing him.

Runs after the cold-start fill so bumps land on top of role priors instead
of vanishing into NaNs.
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from ..graph.build import build_graph
from ..graph.cascade import project_vacated_usage, vacated_usage

log = logging.getLogger(__name__)

# DK draftable statuses that mean the player will not play. Doubtful ("D")
# is deliberately not here: most doubtful players sit, but zeroing them
# would erase real late-swap decisions; their depressed practice features
# already carry the signal.
OUT_STATUSES = {"O", "OUT", "IR"}

# The carry-side cascade reuses the target-centric machinery by renaming:
# total carries ~ total targets, goal-line carries ~ red zone targets,
# carry share ~ target share.
_RUSH_AS_TARGETS = {
    "total_carries": "total_targets",
    "gl3_carries": "rz20_targets",
    "carry_share": "target_share",
}

_PROJ_ZERO_COLS = ["proj_points", "proj_p10", "proj_p50", "proj_p90",
                   "proj_std", "p_20_plus", "value"]


def find_out_players(feats: pd.DataFrame) -> list[str]:
    """GSIS ids of slate players who won't play: DK status O/IR or an
    injury-report Out designation -- and, when CASCADE_DOUBTFUL=1, Doubtful
    NON-QB skill players too.

    Doubtful as absent (2026-09-22). Both next-man-up layers counted only "Out":
    the vacated-share features and this cascade. Walk-forward 2022-24, model fit
    on active rows as production fits it: a backup promoted past an OUT starter
    has model residual -0.02 (already handled), past a DOUBTFUL starter +1.04
    (n=270; per season -0.07, +1.49, +1.53). Doubtful starters sit ~97% of the
    time (176 panel player-weeks, 2.8% played), yet nothing redistributed their
    opportunity -- e.g. Week-2 Zay Flowers (D, 0 pts) while Rashod Bateman ran
    8.2 -> 21.8. QBs are excluded: QB availability goes through find_backup_qbs.
    DEFAULT OFF: CASCADE_DOUBTFUL unset or "0" leaves behaviour unchanged.
    """
    status = feats.get("status", pd.Series(index=feats.index, dtype=object))
    st = status.fillna("").astype(str).str.upper().str.strip()
    dk_out = st.isin(OUT_STATUSES)
    report = feats.get("injury_status", pd.Series(index=feats.index, dtype=object))
    rep = report.fillna("").astype(str).str.upper().str.strip()
    report_out = rep.eq("OUT")
    absent = dk_out | report_out
    if os.environ.get("CASCADE_DOUBTFUL", "0") == "1":
        pos = _col(feats, "position", "dk_position").fillna("").astype(str).str.upper()
        doubtful = st.isin(DOUBTFUL_STATUSES) | rep.eq("DOUBTFUL")
        absent = absent | (doubtful & pos.ne("QB"))
    ids = feats.loc[absent & feats.gsis_id.notna(), "gsis_id"]
    return sorted(set(ids))


def slate_graph(feats: pd.DataFrame):
    """Minimal player/team graph over the slate: enough for team_of /
    teammates (same team + position group) traversal in the cascade."""
    rosters = pd.DataFrame(
        {
            "gsis_id": feats.get("gsis_id"),
            "name": feats.get("display_name", feats.get("gsis_id")),
            "position": feats.get("position", feats.get("dk_position")),
            "team": feats.get("team", feats.get("team_abbr")),
        }
    ).dropna(subset=["gsis_id", "team"]).drop_duplicates("gsis_id")
    qb_connections = pd.DataFrame(
        columns=["qb", "wr", "team", "targets", "rz_targets", "air_yards", "tds"]
    )
    return build_graph(rosters, qb_connections)


def _bump(feats: pd.DataFrame, rows, col: str, delta: float,
          lo: float = 0.0, hi: float | None = None) -> None:
    if col not in feats.columns:
        return
    base = pd.to_numeric(feats.loc[rows, col], errors="coerce").fillna(0.0) + delta
    feats.loc[rows, col] = base.clip(lower=lo, upper=hi)


def _redistribute(
    feats: pd.DataFrame,
    G,
    usage: pd.DataFrame,
    injuries: pd.DataFrame,
    out_id: str,
    skip: set[str],
    share_col: str,
    wopr_col: str | None,
    smoothed_col: str,
    share_cap: float,
) -> None:
    if usage.empty or out_id not in set(usage.gsis_id):
        return
    plan = project_vacated_usage(G, usage, injuries, out_id)
    if plan.empty:
        return
    vac = vacated_usage(usage, out_id)
    # vacated_usage's `mean() or 0` doesn't catch NaN — guard here so a
    # historyless share can't smear NaN over teammates' features.
    if not np.isfinite(vac.avg_target_share) or vac.avg_target_share <= 0:
        return
    rz_pool = vac.avg_rz20_targets if np.isfinite(vac.avg_rz20_targets) else 0.0
    for row in plan.itertuples():
        if row.gsis_id in skip or pd.isna(row.delta):
            continue
        rows = feats.index[feats.gsis_id == row.gsis_id]
        if rows.empty:
            continue
        frac = row.delta / vac.avg_target_share  # share of the vacated role
        _bump(feats, rows, share_col, row.delta, hi=share_cap)
        if wopr_col:
            _bump(feats, rows, wopr_col, 1.5 * row.delta, hi=1.2)
        _bump(feats, rows, smoothed_col, frac * rz_pool)
        log.info("cascade: %s inherits %+.3f %s from %s (%s)",
                 row.gsis_id, row.delta, share_col, out_id, row.method)


def _report_out_ids(feats: pd.DataFrame) -> set[str]:
    """Players the injury report already lists Out: the feature build prices
    their vacated carries through team_vacated_carry_share (sql/features/023),
    so redistributing carry share again at inference counts them twice.

    Double-count audit (2026-09-22, walk-forward 2022-24, model fit on prior
    active rows, the real cascade fed report-Out sources with usage strictly
    before the week): bumped RBs' mean residual was -0.14 without the cascade,
    -0.68 [-1.10, -0.26] with it, and -0.19 with the carry side skipped; the
    effect had the same sign every season (-0.61, -0.68, -0.39). The target
    side is left alone (WR+TE +0.18 -> -0.15, a wash). DK-only late flips and
    Doubtful sources are not in team_vacated_* and keep the full cascade.
    DEFAULT OFF: CASCADE_SKIP_PRICED_CARRIES unset or "0" leaves behaviour
    unchanged."""
    rep = feats.get("injury_status", pd.Series(index=feats.index, dtype=object))
    rep = rep.fillna("").astype(str).str.upper().str.strip()
    return set(feats.loc[rep.eq("OUT") & feats.gsis_id.notna(), "gsis_id"])


def adjust_for_inactives(
    feats: pd.DataFrame,
    usage_rec: pd.DataFrame,
    usage_rush: pd.DataFrame,
    injuries: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Redistribute out players' opportunity to slate teammates.

    usage_rec:  per-game [gsis_id, season, week, total_targets, rz20_targets,
                target_share] (features.rz_receiving grain)
    usage_rush: per-game [gsis_id, season, week, total_carries, gl3_carries,
                carry_share] (features.rz_rushing grain)
    injuries:   [gsis_id, season, week, game_status]

    Returns the adjusted copy and the out players' gsis ids (their
    projections should be zeroed — see zero_out_projections).
    """
    out_ids = find_out_players(feats)
    if not out_ids:
        return feats, []
    feats = feats.copy()
    G = slate_graph(feats)
    skip = set(out_ids)
    rush = usage_rush.rename(columns=_RUSH_AS_TARGETS)
    priced = _report_out_ids(feats) if os.environ.get(
        "CASCADE_SKIP_PRICED_CARRIES", "0") == "1" else set()
    for out_id in out_ids:
        _redistribute(feats, G, usage_rec, injuries, out_id, skip,
                      share_col="target_share_l4", wopr_col="wopr_l4",
                      smoothed_col="rz20_targets_smoothed", share_cap=0.5)
        if out_id in priced:
            log.info("cascade: %s carries already priced by team_vacated_carry_share; "
                     "carry side skipped", out_id)
            continue
        _redistribute(feats, G, rush, injuries, out_id, skip,
                      share_col="carry_share_l4", wopr_col=None,
                      smoothed_col="gl3_carries_smoothed", share_cap=0.85)
    log.info("cascade: adjusted slate for %d inactive(s): %s",
             len(out_ids), ", ".join(out_ids))
    return feats, out_ids


def zero_out_projections(out: pd.DataFrame, out_ids: list[str]) -> pd.DataFrame:
    """A player who won't play projects to zero — after the market blend,
    which knows nothing about a Sunday-morning scratch."""
    if not out_ids:
        return out
    out = out.copy()
    mask = out.gsis_id.isin(out_ids)
    for col in _PROJ_ZERO_COLS:
        if col in out.columns:
            out.loc[mask, col] = 0.0
    return out


# Backup-QB availability gate (2026-09-19). The component models fit on
# active rows only, so a backup QB's served projection is E[points | he
# played] — and a backup who plays usually plays most of a game. History
# (2022-25, by depth_rank): depth-2 QBs appear 30% of weeks, 6.0 pts when
# they do, 1.8 pts unconditionally; depth-3 0.8. Week 2 of 2026 served
# depth-2 QBs 9.8 pts on average at the minimum salary, and 29% of a 6,400
# candidate pool carried one behind a healthy starter. Nothing downstream
# converts the conditional number: find_out_players sees only O/IR/Out.
# Status-only gate: the team's primary QB is the shallowest depth-chart QB
# who is not out; every deeper QB projects to zero. A Doubtful primary
# leaves the team untouched (a split rule is a later, measured refinement),
# and a team with no depth-chart QB on file is untouched. QB_BACKUP_GATE=0
# disables it without a redeploy.
DOUBTFUL_STATUSES = {"D", "DOUBTFUL"}
QUESTIONABLE_STATUSES = {"Q", "QUESTIONABLE"}


def _col(feats: pd.DataFrame, *names: str) -> pd.Series:
    for n in names:
        if n in feats.columns:
            return feats[n]
    return pd.Series([None] * len(feats), index=feats.index, dtype=object)


def find_backup_qbs(feats: pd.DataFrame) -> list[str]:
    """GSIS ids of QBs listed behind a primary QB who is expected to play."""
    if os.environ.get("QB_BACKUP_GATE", "1") == "0" or "depth_rank" not in feats.columns:
        return []
    pos = _col(feats, "position", "dk_position").fillna("").astype(str).str.upper()
    team = _col(feats, "team", "team_abbr").fillna("").astype(str)
    depth = pd.to_numeric(feats["depth_rank"], errors="coerce")
    status = _col(feats, "status").fillna("").astype(str).str.upper().str.strip()
    report = _col(feats, "injury_status").fillna("").astype(str).str.upper().str.strip()
    is_out = status.isin(OUT_STATUSES) | report.eq("OUT")
    is_doubtful = status.isin(DOUBTFUL_STATUSES) | report.eq("DOUBTFUL")
    is_questionable = status.isin(QUESTIONABLE_STATUSES) | report.eq("QUESTIONABLE")
    qbs = feats.loc[pos.eq("QB") & depth.notna() & feats.gsis_id.notna() & team.ne(""),
                    ["gsis_id"]].assign(team=team, depth=depth, out=is_out,
                                        doubtful=is_doubtful, questionable=is_questionable)
    # Shared rule (tools/qb_classify.py, lab review 2026-09-19): a team needs a
    # depth-1 row on file; the primary is that QB unless he is unavailable, in
    # which case the shallowest available QB is promoted. Blank teams are never
    # grouped. Deterministic zeroing is a declared practical approximation of the
    # unconditional expectation, not a proved correction.
    #
    # Doubtful counts as UNAVAILABLE, not as ambiguous (refinement 2026-09-22,
    # laptop review). The original rule treated Doubtful and Questionable as one
    # ambiguous class and so skipped the whole team. Measured: 13 of 13 Doubtful
    # player-weeks took zero offensive snaps and scored zero, while Questionable
    # played 77.4% of the time. The rule is right for Q and was wrong for D. Its
    # cost was concrete -- a Doubtful QB promoted to primary kept a 17.47
    # projection, scored zero, and left his backups ungated. A Doubtful QB is
    # therefore zeroed himself and never blocks the promotion.
    # QB_DOUBTFUL_ABSENT=0 restores the previous ambiguous-on-Doubtful behaviour.
    # No depth-1 row on file (2026-09-22): previously the whole team was left alone,
    # which is the ACTUAL cause of the Week-2 Atlanta miss -- not the ambiguity rule.
    # Three of twenty-six teams in Week 2 (ATL, MIN, SEA) had no depth-1 QB on the DK
    # slate and were ungated entirely, covering 8.5% of the candidate pool. A QB absent
    # from the slate cannot be rostered, so the shallowest QB present is the best
    # available read on the starter. Measured on both released weeks: the promotion is
    # correct in 4 of 4 team-weeks, and 38.22 of the 40.78 projection points it removes
    # came from QBs who scored exactly zero (93.7% precision, against 89.6% for the
    # depth-1 path). QB_NO_DEPTH1_PROMOTE=0 restores the leave-the-team-alone behaviour.
    doubtful_absent = os.environ.get("QB_DOUBTFUL_ABSENT", "1") != "0"
    promote_no_depth1 = os.environ.get("QB_NO_DEPTH1_PROMOTE", "1") != "0"
    ids: list[str] = []
    for _, g in qbs.groupby("team"):
        g = g.sort_values(["depth", "gsis_id"])
        if not (g.depth == 1).any() and not promote_no_depth1:
            continue
        unavailable = g.out | (g.doubtful if doubtful_absent else False)
        primary = g[~unavailable]
        if primary.empty:
            continue
        # Ties at the shallowest available depth (two depth-1 rows) resolve
        # order-independently: any tied row Questionable -> ambiguous team,
        # nothing gated (lab v4 boundary). Doubtful ties are already excluded
        # above when doubtful_absent.
        top = primary[primary.depth == primary.iloc[0]["depth"]]
        if top.questionable.any() or (not doubtful_absent and top.doubtful.any()):
            continue
        cut = top.iloc[0]["depth"]
        ids.extend(g.loc[(g.depth > cut) & ~g.out, "gsis_id"].astype(str))
        if doubtful_absent:
            # the Doubtful QB himself, at any depth, including above the cut
            ids.extend(g.loc[g.doubtful & ~g.out, "gsis_id"].astype(str))
    return sorted(set(ids))


def q_primary_backup_scale() -> float:
    """QB_Q_PRIMARY_BACKUP_SCALE: multiplier for QBs listed behind a Questionable primary (default 1.0, a
    no-op). A value outside [0, 1] fails closed."""
    v = float(os.environ.get("QB_Q_PRIMARY_BACKUP_SCALE", "1.0"))
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"QB_Q_PRIMARY_BACKUP_SCALE must be in [0, 1], got {v}")
    return v


def find_q_primary_backups(feats: pd.DataFrame) -> list[str]:
    """GSIS ids of QBs listed behind a QUESTIONABLE primary (2026-09-23, operator decision).

    find_backup_qbs leaves such a team alone (lab v4 boundary: the starter may sit), so its backups keep a
    full as-if-starting projection. A Questionable QB plays ~80-84% of the time, so his backup starts ~16-20%
    of the time; run_projections scales these rows by QB_Q_PRIMARY_BACKUP_SCALE (the complement of
    Q_HAIRCUT). Same primary and promotion rules as find_backup_qbs; the Questionable primary himself is not
    returned (Q_HAIRCUT prices him), nor is a Doubtful QB (unavailable, handled elsewhere). Week 3 dry run:
    SEA (Darnold Q -> Lock, Milroe) and CHI (Williams D, Bagent Q -> Keenum)."""
    if os.environ.get("QB_BACKUP_GATE", "1") == "0" or "depth_rank" not in feats.columns:
        return []
    pos = _col(feats, "position", "dk_position").fillna("").astype(str).str.upper()
    team = _col(feats, "team", "team_abbr").fillna("").astype(str)
    depth = pd.to_numeric(feats["depth_rank"], errors="coerce")
    status = _col(feats, "status").fillna("").astype(str).str.upper().str.strip()
    report = _col(feats, "injury_status").fillna("").astype(str).str.upper().str.strip()
    is_out = status.isin(OUT_STATUSES) | report.eq("OUT")
    is_doubtful = status.isin(DOUBTFUL_STATUSES) | report.eq("DOUBTFUL")
    is_questionable = status.isin(QUESTIONABLE_STATUSES) | report.eq("QUESTIONABLE")
    qbs = feats.loc[pos.eq("QB") & depth.notna() & feats.gsis_id.notna() & team.ne(""),
                    ["gsis_id"]].assign(team=team, depth=depth, out=is_out,
                                        doubtful=is_doubtful, questionable=is_questionable)
    doubtful_absent = os.environ.get("QB_DOUBTFUL_ABSENT", "1") != "0"
    promote_no_depth1 = os.environ.get("QB_NO_DEPTH1_PROMOTE", "1") != "0"
    ids: list[str] = []
    for _, g in qbs.groupby("team"):
        g = g.sort_values(["depth", "gsis_id"])
        if not (g.depth == 1).any() and not promote_no_depth1:
            continue
        unavailable = g.out | (g.doubtful if doubtful_absent else False)
        primary = g[~unavailable]
        if primary.empty:
            continue
        top = primary[primary.depth == primary.iloc[0]["depth"]]
        if not top.questionable.any():
            continue                                  # healthy primary: find_backup_qbs zeroes the backups
        cut = top.iloc[0]["depth"]
        ids.extend(g.loc[(g.depth > cut) & ~unavailable, "gsis_id"].astype(str))
    return sorted(set(ids))


def apply_scale(out: pd.DataFrame, ids: list[str], scale: float) -> pd.DataFrame:
    """Scale proj_points and value of `ids` by `scale` (1.0 or no ids: unchanged)."""
    if scale == 1.0 or not ids:
        return out
    out = out.copy()
    mask = out.gsis_id.astype(str).isin(ids)
    for col in ("proj_points", "value"):
        if col in out.columns:
            out.loc[mask, col] = out.loc[mask, col] * scale
    return out


# Returning-teammate adjustment (2026-09-23, operator decision). When a top receiver who missed last week is
# back, his teammates' recent-usage features still carry the week he was out, and the model over-projects
# them. Walk-forward 2018-2024 on the training panel (E[pts|played] fit on active rows, as production fits
# it; returner = WR/TE/RB with target_share_l4 >= 0.18, inactive at W-1, active at W-2 or W-3; teammates
# = WR/TE/RB who played W-1): residual in the return week vs all other teammate-weeks -0.41 (se 0.18) for
# all teammates and -1.20 (se 0.40) for teammates whose target share spiked >= 5 points (target_share_jump),
# negative in 6 of 7 seasons each; spiked WRs -1.51 (se 0.54). The market absorbs part of it: on the
# 2023-24 rows with >= 2 prop markets the served-blend gap for spiked teammates is about -1.0 (se 1.4).
# The deltas below are applied to the MODEL component before the market blend, so the blend dilutes them
# exactly where the market carries information. A Questionable returner scales them by 0.8.
RETURN_MIN_TARGET_SHARE = 0.18
RETURN_SPIKE_JUMP = 0.05
RETURN_DELTA_SPIKED = 1.20
RETURN_DELTA_OTHER = 0.41
RETURN_Q_FACTOR = 0.80
# Carry side (2026-09-23): when a lead RB (carry_share_l4 >= 0.40) returns, the model over-projects the RBs who
# played while he was out by 2.40 (se 0.36) and those whose carry share spiked (carry_share_jump >= 0.10) by
# 4.35 (se 0.66), negative in 7 of 7 seasons each (same walk-forward panel and definitions as above). Backup RBs
# rarely carry two prop markets, so the served projection is mostly the model's and keeps the whole bias.
# RETURNING_RB_ADJ=1 enables it (default off); it runs only inside the RETURNING_TEAMMATE_ADJ path.
RETURN_RB_MIN_CARRY_SHARE = 0.40
RETURN_RB_SPIKE_JUMP = 0.10
RETURN_RB_DELTA_SPIKED = 4.35
RETURN_RB_DELTA_OTHER = 2.40


def returning_rb_enabled() -> bool:
    """RETURNING_RB_ADJ=1 enables the carry-side adjustment (default off); not 0/1 fails closed."""
    v = os.environ.get("RETURNING_RB_ADJ", "0").strip()
    if v not in ("0", "1"):
        raise ValueError(f"RETURNING_RB_ADJ must be 0 or 1, got {v!r}")
    return v == "1"


def returning_teammate_enabled() -> bool:
    """RETURNING_TEAMMATE_ADJ=1 enables the adjustment (default off). Any other non-empty value but 0/1
    fails closed."""
    v = os.environ.get("RETURNING_TEAMMATE_ADJ", "0").strip()
    if v not in ("0", "1"):
        raise ValueError(f"RETURNING_TEAMMATE_ADJ must be 0 or 1, got {v!r}")
    return v == "1"


def returning_teammate_deltas(feats: pd.DataFrame, prev_played: set[str],
                              prev_teams: set[str]) -> tuple[np.ndarray, list[str]]:
    """Per-row points to SUBTRACT from the model component (aligned with feats), and the returners' ids.

    prev_played: gsis ids with a box-score line in week W-1; prev_teams: teams that played in W-1 (a bye
    week is never an absence). Returners are WR/TE/RB with target_share_l4 >= 0.18 who did not play W-1,
    whose team did, and who are not Out/Doubtful now. Each WR/TE/RB teammate who played W-1 loses 1.20
    (target_share_jump >= 0.05) or 0.41, times 0.8 if every returner on his team is Questionable. A player
    with several returning teammates takes the largest single delta, never a sum."""
    n = len(feats)
    delta = np.zeros(n)
    if n == 0 or not prev_played:
        return delta, []
    pos = _col(feats, "position", "dk_position").fillna("").astype(str).str.upper()
    team = _col(feats, "team", "team_abbr").fillna("").astype(str)
    gid = feats.gsis_id.astype(str)
    status = _col(feats, "status").fillna("").astype(str).str.upper().str.strip()
    report = _col(feats, "injury_status").fillna("").astype(str).str.upper().str.strip()
    ts = pd.to_numeric(_col(feats, "target_share_l4"), errors="coerce").fillna(0.0)
    jump = pd.to_numeric(_col(feats, "target_share_jump"), errors="coerce").fillna(0.0)
    skill = pos.isin(["WR", "TE", "RB"])
    unavailable = status.isin(OUT_STATUSES | DOUBTFUL_STATUSES) | report.isin({"OUT", "DOUBTFUL"})
    questionable = status.isin(QUESTIONABLE_STATUSES) | report.eq("QUESTIONABLE")
    played_prev = gid.isin(prev_played)
    returner = (skill & (ts >= RETURN_MIN_TARGET_SHARE) & ~played_prev & team.isin(prev_teams)
                & ~unavailable & team.ne(""))
    def _team_factor(mask: pd.Series) -> dict[str, float]:
        out: dict[str, float] = {}
        for t, q in zip(team[mask], questionable[mask]):
            out[t] = max(out.get(t, 0.0), RETURN_Q_FACTOR if q else 1.0)
        return out

    returner_ids: set[str] = set()
    fac = _team_factor(returner)
    if fac:
        base = np.where(jump >= RETURN_SPIKE_JUMP, RETURN_DELTA_SPIKED, RETURN_DELTA_OTHER)
        f_row = team.map(fac).fillna(0.0).to_numpy()
        benef = (skill & played_prev & ~returner).to_numpy()
        delta = np.maximum(delta, np.where(benef, base * f_row, 0.0))
        returner_ids |= set(gid[returner])
    if returning_rb_enabled():
        cs = pd.to_numeric(_col(feats, "carry_share_l4"), errors="coerce").fillna(0.0)
        cjump = pd.to_numeric(_col(feats, "carry_share_jump"), errors="coerce").fillna(0.0)
        rb = pos.eq("RB")
        rb_ret = (rb & (cs >= RETURN_RB_MIN_CARRY_SHARE) & ~played_prev & team.isin(prev_teams)
                  & ~unavailable & team.ne(""))
        rfac = _team_factor(rb_ret)
        if rfac:
            rbase = np.where(cjump >= RETURN_RB_SPIKE_JUMP, RETURN_RB_DELTA_SPIKED, RETURN_RB_DELTA_OTHER)
            rf_row = team.map(rfac).fillna(0.0).to_numpy()
            rbenef = (rb & played_prev & ~rb_ret).to_numpy()
            delta = np.maximum(delta, np.where(rbenef, rbase * rf_row, 0.0))
            returner_ids |= set(gid[rb_ret])
    return delta, sorted(returner_ids)


# Questionable availability haircut (2026-09-22). The featureset carries no
# injury or practice feature, so a Questionable player is served E[points | he
# plays at full strength]. Walk-forward 2018-2024 on the training panel, model fit
# on active rows exactly as production fits it: Questionable players under-ran
# healthy players in 7 of 7 seasons (mean gap -1.33, sd 0.56); their
# realized/projected ratio relative to healthy players is 0.77-0.91 (0.86 pooled,
# 0.77-0.83 in 2022-24). The market blend does not price it away: on the served
# 2026 projections Q players ran 0.45x (W1) and 0.63x (W2) of healthy.
#
# Q_HAIRCUT is the multiplier; the DEFAULT 1.0 IS A NO-OP. Only proj_points and
# value are scaled -- the money path reads proj_points alone, and scaling the
# quantiles or proj_std of a play/no-play mixture by a constant would be wrong.
# A value outside (0, 1] fails closed rather than being ignored.
QUESTIONABLE_STATUSES_Q = {"Q", "QUESTIONABLE"}


def questionable_haircut(feats: pd.DataFrame) -> float:
    raw = os.environ.get("Q_HAIRCUT", "1.0")
    try:
        h = float(raw)
    except ValueError as exc:
        raise ValueError(f"Q_HAIRCUT must be a number in (0, 1], got {raw!r}") from exc
    if not (0.0 < h <= 1.0):
        raise ValueError(f"Q_HAIRCUT must be in (0, 1], got {h}")
    return h


def find_questionable_players(feats: pd.DataFrame) -> list[str]:
    """GSIS ids of skill players designated Questionable (DK status or report)."""
    status = _col(feats, "status").fillna("").astype(str).str.upper().str.strip()
    report = _col(feats, "injury_status").fillna("").astype(str).str.upper().str.strip()
    q = status.isin(QUESTIONABLE_STATUSES_Q) | report.eq("QUESTIONABLE")
    return sorted(set(feats.loc[q & feats.gsis_id.notna(), "gsis_id"].astype(str)))


def apply_questionable_haircut(out: pd.DataFrame, q_ids: list[str], h: float) -> pd.DataFrame:
    if h == 1.0 or not q_ids:
        return out
    out = out.copy()
    mask = out.gsis_id.astype(str).isin(q_ids)
    for col in ("proj_points", "value"):
        if col in out.columns:
            out.loc[mask, col] = out.loc[mask, col] * h
    return out
