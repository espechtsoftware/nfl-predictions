"""Player watch notes: qualitative "keep an eye on this guy" intel.

Deliberately DISTINCT from manual usage notes (notes.py): a watch note is
one free-text field attached to a player and it affects NOTHING — no
projection, no lineup math. It is the first stage of a pipeline the user
runs by hand: watch -> (maybe) convert into a usage-note adjustment once
the hunch firms up. Conversion creates the manual note via notes.add_note
and stamps this row converted, preserving the paper trail.

Surfaced in three places: chat tools (add/list/delete/convert), the
/watchlist page (lifecycle view + convert/delete), and inline on any
generated lineup containing a watched player.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

import pandas as pd

from .bq import load_dataframe, query_df
from .config import settings

log = logging.getLogger(__name__)

TABLE = "player_watch_notes"


def _table() -> str:
    return f"{settings.features}.{TABLE}"


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z ]", "", str(name).upper()).strip()


def list_watch(include_converted: bool = True) -> pd.DataFrame:
    cols = ["note_id", "gsis_id", "display_name", "note", "status",
            "created_at", "converted_at", "converted_note_id", "converted_mult"]
    try:
        df = query_df(
            f"SELECT {', '.join(cols)} FROM `{_table()}` ORDER BY created_at DESC"
        )
    except Exception:  # table may not exist until the first note
        log.info("player_watch_notes absent; returning empty")
        return pd.DataFrame(columns=cols)
    if not include_converted:
        df = df[df.status == "active"]
    return df


def add_watch(display_name: str, note: str, gsis_id: str = "") -> str:
    note_id = uuid.uuid4().hex[:12]
    row = pd.DataFrame([{
        "note_id": note_id, "gsis_id": gsis_id or "",
        "display_name": display_name, "note": note, "status": "active",
        "created_at": datetime.now(timezone.utc),
        "converted_at": pd.NaT, "converted_note_id": "",
        "converted_mult": float("nan"),
    }])
    load_dataframe(row, _table(), write_disposition="WRITE_APPEND")
    return note_id


def delete_watch(note_id: str) -> int:
    from google.cloud import bigquery

    from .bq import client

    job = client().query(
        f"DELETE FROM `{_table()}` WHERE note_id = @id",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", note_id)]),
    )
    job.result()
    return job.num_dml_affected_rows or 0


def convert_watch(note_id: str, mult: float, season: int) -> str:
    """Promote a watch note into a real usage-note adjustment (notes.py),
    stamping this row converted. Returns the manual note's id."""
    from . import notes

    df = list_watch()
    row = df[df.note_id == note_id]
    if row.empty:
        raise ValueError(f"no watch note {note_id}")
    r = row.iloc[0]
    if r.status == "converted":
        raise ValueError(f"watch note {note_id} already converted "
                         f"(manual note {r.converted_note_id})")
    manual_id = notes.add_note(
        gsis_id=str(r.gsis_id or ""), display_name=str(r.display_name),
        season=int(season), mult=float(mult),
        note=f"[from watchlist] {r.note}", source="watchlist")

    from google.cloud import bigquery

    from .bq import client

    job = client().query(
        f"""UPDATE `{_table()}`
            SET status = 'converted',
                converted_at = CURRENT_TIMESTAMP(),
                converted_note_id = @mid,
                converted_mult = @mult
            WHERE note_id = @id""",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("mid", "STRING", manual_id),
            bigquery.ScalarQueryParameter("mult", "FLOAT64", float(mult)),
            bigquery.ScalarQueryParameter("id", "STRING", note_id)]),
    )
    job.result()
    return manual_id


def annotate_players(players: list[dict]) -> None:
    """Attach 'watch_note' in place to any player dict whose name matches
    an ACTIVE watch note. Failure-safe: lineups without notes beat no
    lineups."""
    try:
        active = list_watch(include_converted=False)
    except Exception:
        log.exception("watchlist unavailable; lineups un-annotated")
        return
    if active.empty:
        return
    by_name = {_norm(r.display_name): str(r.note) for r in active.itertuples()}
    seen: set[int] = set()  # pool dicts recur across lineups; annotate once
    for p in players:
        if id(p) in seen:
            continue
        seen.add(id(p))
        note = by_name.get(_norm(p.get("name", "")))
        if note:
            p["watch_note"] = note
