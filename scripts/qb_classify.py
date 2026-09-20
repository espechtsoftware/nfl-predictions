"""One QB availability classifier for the whole Sunday chain (2026-09-19, lab review of Rung 1c/2 finding 3).

Used by qb_flags.py (the flag table), vet_book.py (demotion), vet_replace_v4.py (exclusion / admission) and — the
same rule, ported verbatim — by production cascade_adjust.find_backup_qbs (Rung 2). ID-keyed; every QB retained.

Per team (blank team excluded):
  * `primary`   = the depth-1 QB when a depth-1 row exists and he is not OUT; when the depth-1 QB is OUT, the
                  shallowest non-OUT QB is promoted to primary (promotion is the only case without a depth-1 primary)
  * team class  = 'healthy'      primary present, not Doubtful/Questionable   -> deeper QBs are GATED
                  'questionable' primary is Questionable                       -> ambiguous, nothing gated
                  'doubtful'     primary is Doubtful                           -> ambiguous, nothing gated
                  'no-depth-1'   no depth-1 row on file (even with other QBs)  -> unknown, nothing gated
                  'all-out'      every QB with depth is OUT                    -> nothing gated
  * per QB role = 'primary' | 'gated' (backup behind a healthy primary) | 'ambiguous' (backup, team not healthy)
                  | 'out' (OUT/IR himself) | 'unknown' (no depth rank, or team unknown)

OUT means the DK feed status O/IR/OUT or a report status of Out. Doubtful/Questionable never make a player 'out':
they are risk information (finding 1). Deterministic gating is a declared practical approximation of the
unconditional expectation (2022-25 depth-2 QBs: 1.8 pts unconditionally), not a proved correction.
"""
from __future__ import annotations

import pandas as pd

OUT_STATUSES = {"O", "OUT", "IR", "INJURED RESERVE", "PUP", "NFI", "SUS", "SUSPENDED"}
DOUBTFUL = {"D", "DOUBTFUL"}
QUESTIONABLE = {"Q", "QUESTIONABLE"}


def _norm(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.upper()


def classify_qbs(qbs: pd.DataFrame) -> pd.DataFrame:
    """qbs columns: an id column (gsis_id or dk_player_id, any name kept), team, depth_rank, and any of
    dk_status / injury_status (report). Returns the same rows plus: is_out, is_doubtful, is_questionable,
    team_class, role."""
    q = qbs.copy()
    team = _norm(q["team"])
    dk = _norm(q["dk_status"]) if "dk_status" in q.columns else pd.Series([""] * len(q), index=q.index)
    rep = _norm(q["injury_status"]) if "injury_status" in q.columns else pd.Series([""] * len(q), index=q.index)
    q["is_out"] = dk.isin(OUT_STATUSES) | rep.eq("OUT")
    q["is_doubtful"] = (~q["is_out"]) & (dk.isin(DOUBTFUL) | rep.isin(DOUBTFUL))
    q["is_questionable"] = (~q["is_out"]) & (~q["is_doubtful"]) & (dk.isin(QUESTIONABLE) | rep.isin(QUESTIONABLE))
    q["depth"] = pd.to_numeric(q["depth_rank"], errors="coerce")
    q["team_class"] = "unknown"
    q["role"] = "unknown"
    q.loc[q["is_out"], "role"] = "out"
    for t, g in q[team.ne("") & q["depth"].notna()].groupby(team[team.ne("") & q["depth"].notna()]):
        g = g.sort_values("depth", kind="stable")
        has_depth1 = bool((g["depth"] == 1).any())
        alive = g[~g["is_out"]]
        if not has_depth1:
            cls, primary = "no-depth-1", None
        elif alive.empty:
            cls, primary = "all-out", None
        else:
            # Ties at the shallowest non-out depth (e.g. two depth-1 rows) are resolved order-independently:
            # if ANY tied row is Doubtful/Questionable the team is ambiguous; otherwise the tie is healthy and the
            # first row is the nominal primary (lab v4 boundary: permuting tied rows must not change the gating).
            top = alive[alive["depth"] == alive["depth"].iloc[0]]
            primary = top.index[0]
            if bool(top["is_doubtful"].any()):
                cls = "doubtful"
            elif bool(top["is_questionable"].any()):
                cls = "questionable"
            else:
                cls = "healthy"
        q.loc[g.index, "team_class"] = cls
        if primary is not None:
            q.loc[top.index, "role"] = "primary"      # every tied shallowest non-out row is a nominal primary
            deeper = g.index[(g["depth"] > g.loc[primary, "depth"]) & (~g["is_out"])]
            q.loc[deeper, "role"] = "gated" if cls == "healthy" else "ambiguous"
    return q


def gated_ids(qbs: pd.DataFrame, id_col: str) -> list:
    c = classify_qbs(qbs)
    return sorted(c.loc[c["role"] == "gated", id_col].astype(str).tolist())
