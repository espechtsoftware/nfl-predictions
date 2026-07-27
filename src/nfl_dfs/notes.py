"""Manual usage notes: qualitative intel (coach usage statements, role
changes) entered by hand and applied as opportunity-prior adjustments.

Why this exists: the model's cold-start priors are generic role averages
(coldstart.py). Credible offseason/camp news ("he's moving to the slot",
"he gets the two-minute snaps") is real signal in weeks 1-4, before stats
exist to prove it. A note scales the affected player's opportunity
components (targets/carries/pass attempts) by `mult`, decaying linearly to
nothing by DECAY_FULL_WEEK — by then actual snaps speak for themselves.

Applied at inference only (run_projections), never in replays: notes are
forward-looking by construction, and injecting them into historical
backtests would be leakage in spirit if not in letter.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import pandas as pd

from .bq import load_dataframe, query_df
from .config import settings

log = logging.getLogger(__name__)

TABLE = "manual_notes"
DECAY_FULL_WEEK = 6  # full effect week 1, linearly to zero here
OPP_COLS = ("targets", "carries", "pass_attempts")


def _table() -> str:
    return f"{settings.features}.{TABLE}"


def decay(week: int) -> float:
    """Fraction of a note's effect remaining in `week` (1.0 -> 0.0)."""
    return max(0.0, min(1.0, (DECAY_FULL_WEEK - week) / (DECAY_FULL_WEEK - 1)))


def list_notes(season: int | None = None) -> pd.DataFrame:
    where = f"WHERE season = {int(season)}" if season else ""
    try:
        return query_df(
            f"SELECT note_id, gsis_id, display_name, season, mult, note, "
            f"source, created_at FROM `{_table()}` {where} ORDER BY created_at"
        )
    except Exception:  # table may not exist until the first note
        log.info("manual_notes table absent or unreadable; returning empty")
        return pd.DataFrame(columns=["note_id", "gsis_id", "display_name",
                                     "season", "mult", "note", "source",
                                     "created_at"])


def add_note(gsis_id: str, display_name: str, season: int, mult: float,
             note: str, source: str = "") -> str:
    """mult is the opportunity multiplier at full effect (e.g. 1.15 = +15%
    targets/carries; 0.85 = reduced role). Clamped to a sane band —
    qualitative news never justifies more than +/-40%."""
    mult = max(0.6, min(1.4, float(mult)))
    note_id = uuid.uuid4().hex[:12]
    row = pd.DataFrame([{
        "note_id": note_id, "gsis_id": gsis_id, "display_name": display_name,
        "season": int(season), "mult": mult, "note": note, "source": source,
        "created_at": datetime.now(timezone.utc),
    }])
    load_dataframe(row, _table(), write_disposition="WRITE_APPEND")
    return note_id


def delete_note(note_id: str) -> int:
    from .bq import client

    job = client().query(
        f"DELETE FROM `{_table()}` WHERE note_id = @id",
        job_config=_param_config(note_id),
    )
    job.result()
    return job.num_dml_affected_rows or 0


def _param_config(note_id: str):
    from google.cloud import bigquery

    return bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("id", "STRING", note_id)])


def apply_notes(comps: pd.DataFrame, feats: pd.DataFrame, season: int,
                week: int) -> pd.DataFrame:
    """Scale opportunity components for players with active notes. Mean
    projections move by design — this is the user overriding the prior.
    Failure-safe: projections without notes beat no projections."""
    try:
        notes = list_notes(season)
    except Exception:
        log.exception("manual notes unavailable; projecting without them")
        return comps
    if notes.empty:
        return comps
    d = decay(week)
    if d <= 0:
        return comps
    comps = comps.copy()
    gsis = feats.get("gsis_id")
    if gsis is None:
        return comps
    # Multiple notes on one player multiply together (each is independent
    # intel); each note's effect is interpolated toward 1.0 by the decay.
    eff = notes.assign(m=1 + (notes.mult - 1) * d).groupby("gsis_id").m.prod()
    m = gsis.map(eff).fillna(1.0).to_numpy()
    applied = int((m != 1.0).sum())
    for c in OPP_COLS:
        if c in comps.columns:
            comps[c] = comps[c] * m
    if applied:
        log.info("manual notes: scaled opportunity for %d players "
                 "(week %d decay %.0f%%)", applied, week, 100 * d)
    return comps


# Weekly lineup preferences: bans (never roster) and boosts (tilt into
# more lineups). Stored by normalized display name and matched against
# the pool at build time — robust to dk_player_id churn across slates.

PREFS_TABLE = "lineup_prefs"
BOOST_BONUS = 2.5  # proj_tourney points added to boosted players


def _prefs_table() -> str:
    return f"{settings.features}.{PREFS_TABLE}"


def norm_name(s: str) -> str:
    import re

    return re.sub(r"[^a-z ]", "", str(s).lower()).strip()


def list_prefs(season: int, week: int) -> pd.DataFrame:
    try:
        return query_df(
            f"SELECT pref_id, display_name, kind, created_at FROM "
            f"`{_prefs_table()}` WHERE season={int(season)} AND "
            f"week={int(week)} ORDER BY created_at")
    except Exception:
        return pd.DataFrame(columns=["pref_id", "display_name", "kind",
                                     "created_at"])


def add_pref(season: int, week: int, display_name: str, kind: str) -> str:
    assert kind in ("ban", "boost")
    pref_id = uuid.uuid4().hex[:12]
    load_dataframe(pd.DataFrame([{
        "pref_id": pref_id, "season": int(season), "week": int(week),
        "display_name": display_name, "norm": norm_name(display_name),
        "kind": kind, "created_at": datetime.now(timezone.utc)}]),
        _prefs_table(), write_disposition="WRITE_APPEND")
    return pref_id


def delete_pref(pref_id: str) -> int:
    from .bq import client

    job = client().query(f"DELETE FROM `{_prefs_table()}` WHERE pref_id=@id",
                         job_config=_param_config(pref_id))
    job.result()
    return job.num_dml_affected_rows or 0


def apply_prefs(pool: list[dict], season: int, week: int) -> list[dict]:
    """Drop banned players; add BOOST_BONUS to boosted players' objective.
    Failure-safe: no prefs table -> pool unchanged."""
    try:
        p = query_df(f"SELECT norm, kind FROM `{_prefs_table()}` WHERE "
                     f"season={int(season)} AND week={int(week)}")
    except Exception:
        return pool
    if p.empty:
        return pool
    bans = set(p[p.kind == "ban"].norm)
    boosts = set(p[p.kind == "boost"].norm)
    out = []
    for pl in pool:
        n = norm_name(pl.get("name", ""))
        if n in bans:
            continue
        if n in boosts:
            pl = {**pl, "proj": pl["proj"] + BOOST_BONUS}
        out.append(pl)
    log.info("prefs: %d banned, %d boosted (wk %s)", len(bans), len(boosts),
             week)
    return out


# Season bankroll tracking: weekly contests/spent/won + best-lineup notes.

RESULTS_TABLE = "season_results"


def _results_table() -> str:
    return f"{settings.features}.{RESULTS_TABLE}"


def list_results(season: int) -> pd.DataFrame:
    try:
        return query_df(
            f"SELECT result_id, week, contests, spent, won, best_score, "
            f"best_rank, note FROM `{_results_table()}` "
            f"WHERE season={int(season)} ORDER BY week")
    except Exception:
        return pd.DataFrame(columns=["result_id", "week", "contests",
                                     "spent", "won", "best_score",
                                     "best_rank", "note"])


def upsert_result(season: int, week: int, contests: int, spent: float,
                  won: float, best_score: float | None = None,
                  best_rank: int | None = None, note: str = "") -> str:
    """One row per (season, week): replace any existing row for the week."""
    from .bq import client

    try:
        client().query(
            f"DELETE FROM `{_results_table()}` WHERE season={int(season)} "
            f"AND week={int(week)}").result()
    except Exception:
        pass  # table may not exist yet
    rid = uuid.uuid4().hex[:12]
    load_dataframe(pd.DataFrame([{
        "result_id": rid, "season": int(season), "week": int(week),
        "contests": int(contests), "spent": float(spent),
        "won": float(won),
        "best_score": float(best_score) if best_score is not None else None,
        "best_rank": int(best_rank) if best_rank is not None else None,
        "note": note, "created_at": datetime.now(timezone.utc)}]),
        _results_table(), write_disposition="WRITE_APPEND")
    return rid


def import_entry_history(csv_text: str, season: int) -> dict:
    """Aggregate a DraftKings Entry History CSV into weekly rows.
    Tolerant of column naming: finds fee/winnings/date columns by
    substring. Only rows whose date falls inside an NFL week count."""
    import io

    df = pd.read_csv(io.StringIO(csv_text))
    cols = {c.lower(): c for c in df.columns}

    def find(*subs):
        for lc, c in cols.items():
            if any(s in lc for s in subs):
                return c
        return None

    fee, won, date = (find("fee"), find("winning", "won"),
                      find("date", "time"))
    if not (fee and won and date):
        raise ValueError(f"unrecognized CSV columns: {list(df.columns)}")
    df["_d"] = pd.to_datetime(df[date], errors="coerce").dt.date
    weeks = query_df(
        f"SELECT week, MIN(gameday) AS d0, MAX(gameday) AS d1 "
        f"FROM `{settings.raw}.schedules` WHERE season={int(season)} "
        f"GROUP BY week")
    money = lambda s: pd.to_numeric(
        s.astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    df[fee], df[won] = money(df[fee]), money(df[won])
    out = {}
    for w in weeks.itertuples():
        d0 = pd.Timestamp(w.d0).date()
        d1 = pd.Timestamp(w.d1).date() + pd.Timedelta(days=1)
        rows = df[(df._d >= d0) & (df._d <= d1)]
        if len(rows):
            upsert_result(season, int(w.week), len(rows),
                          float(rows[fee].sum()), float(rows[won].sum()),
                          note="imported from DK entry history")
            out[int(w.week)] = {"contests": len(rows),
                                "spent": float(rows[fee].sum()),
                                "won": float(rows[won].sum())}
    return out
