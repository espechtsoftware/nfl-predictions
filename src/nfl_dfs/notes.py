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
