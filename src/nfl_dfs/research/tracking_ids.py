"""Tracking-ID crosswalk: BDB nfl_id -> nflverse gsis_id (plan §7.2).

The Big Data Bowl tracking releases key players by ``nfl_id``; the rest
of this system is keyed by gsis_id. §7.2 requires a DETERMINISTIC
mapping with confidence flags and human resolution for ambiguity —
never a guess. Matching is name + birth_date against nflverse rosters:

- ``high``    exactly one roster candidate whose birth_date equals the
              tracking birth_date (dob is the primary disambiguator);
- ``medium``  exactly one name candidate but no dob confirmation
              (missing on either side) — name-only unambiguous;
- ``review``  everything else: no candidate, several candidates dob
              cannot separate, or a dob CONFLICT on a unique name
              match (conflicts are suspicious, not tie-broken).

Name normalization reuses ``nfl_dfs.names``: ``norm_name`` (suffix
stripping) for the exact tier, ``initial_key`` for the diminutive
fallback ("Cam"/"Cameron") — the fallback is only consulted when the
exact tier finds nothing, mirroring ``names.resolve``.

``match_tracking_players`` is pure (frames in, frame out) so the test
suite runs offline; ``build_id_map`` is the thin BQ-backed wrapper for
real runs and is deliberately untested.
"""

from __future__ import annotations

import pandas as pd

from ..names import initial_key, norm_name

__all__ = ["match_tracking_players", "build_id_map",
           "CONF_HIGH", "CONF_MEDIUM", "CONF_REVIEW"]

CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_REVIEW = "review"

_OUT_COLS = ["nfl_id", "player_name", "birth_date", "position", "gsis_id",
             "confidence", "method", "n_candidates", "roster_name",
             "roster_birth_date", "roster_position"]


def _roster_index(rosters: pd.DataFrame) -> tuple[dict, dict]:
    """{norm_name: [row, ...]} and {initial_key: [row, ...]} over roster
    rows deduped by gsis_id (rosters_weekly repeats players per week)."""
    r = rosters.dropna(subset=["gsis_id"]).copy()
    # date-only normalization (2026-08-05 first real run: nflverse
    # birth_date strings carry " 00:00:00" while tracking has bare
    # dates — every dob compared as unequal and 1384/1384 landed in
    # review as dob_conflict)
    r["birth_date"] = r["birth_date"].astype("string").str[:10]
    # keep, per gsis_id, the row with a birth_date when one exists
    r = (r.sort_values("birth_date", na_position="last")
          .drop_duplicates("gsis_id", keep="first"))
    by_norm: dict[str, list] = {}
    by_init: dict[str, list] = {}
    for row in r.itertuples(index=False):
        rec = {"gsis_id": row.gsis_id, "name": row.display_name,
               "dob": None if pd.isna(row.birth_date) else str(row.birth_date),
               "position": getattr(row, "position", None)}
        by_norm.setdefault(norm_name(row.display_name), []).append(rec)
        by_init.setdefault(initial_key(row.display_name), []).append(rec)
    return by_norm, by_init


def _match_one(name: str, dob: str | None, by_norm: dict, by_init: dict):
    """-> (gsis_id, confidence, method, n_candidates, roster_rec)."""
    cands = by_norm.get(norm_name(name))
    method = "norm_name"
    if not cands:
        cands = by_init.get(initial_key(name))
        method = "initial_key"
    if not cands:
        return None, CONF_REVIEW, "unmatched", 0, None
    n = len(cands)
    if dob is not None:
        dob_hits = [c for c in cands if c["dob"] == dob]
        if len(dob_hits) == 1:
            return dob_hits[0]["gsis_id"], CONF_HIGH, method + "+dob", n, dob_hits[0]
        if len(dob_hits) > 1:
            # duplicate roster identities — a human decides, we don't
            return None, CONF_REVIEW, method + "+dob_dup", n, None
        if n == 1 and cands[0]["dob"] is None:
            # name unambiguous, roster dob absent: unconfirmable
            return cands[0]["gsis_id"], CONF_MEDIUM, method, n, cands[0]
        # unique name but CONFLICTING dob, or several non-matching dobs
        return None, CONF_REVIEW, method + "+dob_conflict", n, None
    if n == 1:
        return cands[0]["gsis_id"], CONF_MEDIUM, method, n, cands[0]
    return None, CONF_REVIEW, method + "+ambiguous", n, None


def match_tracking_players(players: pd.DataFrame,
                           rosters: pd.DataFrame) -> pd.DataFrame:
    """Deterministic nfl_id -> gsis_id match with confidence tiers.

    ``players``: one row per tracking player — nfl_id, player_name,
    player_birth_date (YYYY-MM-DD or null), player_position.
    ``rosters``: gsis_id, display_name, birth_date, position.
    Returns one row per nfl_id (gsis_id null wherever confidence is
    ``review`` — flagged for a human, never guessed).
    """
    by_norm, by_init = _roster_index(rosters)
    p = players.drop_duplicates("nfl_id")
    rows = []
    for t in p.itertuples(index=False):
        dob = t.player_birth_date
        dob = None if pd.isna(dob) else str(dob)
        gsis, conf, method, n, rec = _match_one(
            str(t.player_name), dob, by_norm, by_init)
        rows.append({
            "nfl_id": t.nfl_id, "player_name": t.player_name,
            "birth_date": dob, "position": t.player_position,
            "gsis_id": gsis, "confidence": conf, "method": method,
            "n_candidates": n,
            "roster_name": rec["name"] if rec else None,
            "roster_birth_date": rec["dob"] if rec else None,
            "roster_position": rec["position"] if rec else None,
        })
    return pd.DataFrame(rows, columns=_OUT_COLS)


def build_id_map(players: pd.DataFrame, seasons: tuple[int, ...] = (2023,)
                 ) -> pd.DataFrame:  # pragma: no cover - needs BigQuery
    """Real-run wrapper: pull rosters from `${raw}.rosters_weekly` for
    ``seasons`` and run the pure matcher."""
    from ..bq import query_df
    from ..config import settings

    season_list = ",".join(str(int(s)) for s in seasons)
    rosters = query_df(f"""
        SELECT gsis_id,
               ANY_VALUE(full_name)  AS display_name,
               ANY_VALUE(CAST(birth_date AS STRING)) AS birth_date,
               ANY_VALUE(position)   AS position
        FROM `{settings.raw}.rosters_weekly`
        WHERE season IN ({season_list}) AND gsis_id IS NOT NULL
        GROUP BY gsis_id
    """)
    return match_tracking_players(players, rosters)
