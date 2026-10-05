"""``nfl_predictions.own_shadow``: who wrote each pre-lock ownership vector.

Until 2026-10-05 the table had no writer column. Every reader took a week's
LATEST generation (``MAX(generated_at)``), so whichever job wrote last -- a
Sunday shadow, a Thursday generation suite, the money path -- silently became
"the" pre-lock ownership prediction. Rows now carry ``writer`` (who built the
vector) and ``run_type`` (the candidate run type of that build, when it has
one). Both columns are NULLABLE: rows written before the change, and rows from
images built before it, read as NULL = legacy.

Readers select ONE writer: use :func:`latest_generation_sql` (or copy its
WHERE/QUALIFY clause) rather than taking the latest row of a week.
"""

from __future__ import annotations

import pandas as pd

OWN_SHADOW_TABLE = "own_shadow"
# app/main.py::_build_classic -- POST /lineups and the book endpoints of the
# nfl-dfs-app service. NOT the Saturday/Sunday money path: that build is the
# lab's live_week.py (sunday_build_host.sh), which never calls live_lineups and
# has written no own_shadow row in 2026 (W2-W4: zero rows of any writer).
WRITER_APP = "app_build_classic"
# prospective_generation_shadow_suite: its incumbent arm logs the build vector.
WRITER_GENERATION_SUITE = "generation_shadow_suite"
_DEFAULT_PREFIX = "build_sim_lineups"


def default_writer(candidate_run_type: str | None) -> str:
    """The writer recorded when a caller does not name itself."""
    return f"{_DEFAULT_PREFIX}:{candidate_run_type or 'unlabelled'}"


def _validated_writer(writer: object) -> str:
    if not isinstance(writer, str) or not writer.strip():
        raise ValueError("own_shadow rows need a non-empty writer")
    return writer.strip()


def ownership_shadow_frame(
    frame: pd.DataFrame,
    own,
    own_source: str,
    season: int,
    week: int,
    *,
    booster_own,
    writer: str,
    run_type: str | None,
    generated_at,
) -> pd.DataFrame:
    """One generation's rows, in the table's column order.

    ``writer``/``run_type`` use pandas' string dtype so the load maps them to
    STRING even when every ``run_type`` is missing.
    """
    writer = _validated_writer(writer)
    rows = pd.DataFrame({
        "generated_at": generated_at,
        "season": int(season), "week": int(week),
        "gsis_id": frame.get("gsis_id"),
        "name": frame.get("name"),
        "pos": frame.pos, "salary": frame.salary,
        "n_pool": len(frame),
        "pred_own": own, "source": own_source,
        "booster_own": booster_own,
    })
    rows["writer"] = pd.Series([writer] * len(rows), index=rows.index,
                               dtype="string")
    rows["run_type"] = pd.Series([run_type] * len(rows), index=rows.index,
                                 dtype="string")
    return rows


def latest_generation_sql(table: str, *, writer: str | None) -> tuple[str, dict]:
    """SQL + params for one writer's latest generation of one week.

    ``writer=None`` reads only the legacy rows (written before the column
    existed). There is deliberately no "any writer" form.
    """
    if writer is None:
        who, params = "writer IS NULL", {}
    else:
        who, params = "writer = @writer", {"writer": _validated_writer(writer)}
    sql = (
        f"SELECT * FROM `{table}`\n"
        f"WHERE season = @season AND week = @week AND {who}\n"
        "QUALIFY generated_at = MAX(generated_at) OVER ()"
    )
    return sql, params


__all__ = [
    "OWN_SHADOW_TABLE",
    "WRITER_GENERATION_SUITE",
    "WRITER_APP",
    "default_writer",
    "latest_generation_sql",
    "ownership_shadow_frame",
]
