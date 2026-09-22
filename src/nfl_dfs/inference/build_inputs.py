"""Pure assessment of the money-build inputs (laptop plan Phase 0 item 1; the script does the warehouse reads).

A build may proceed only when: production projections for the target week exist, are fresh and cover the slate;
the market-source monitor has a fresh batch that is prop-sourced for most non-DST rows; the TabPFN cache holds rows
for the target week; the chosen-dose file and contests.json are present and well-formed.  Nothing is substituted
when a check fails: the verdict is FAIL and the reasons are named.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .market_monitor import assess_batch


def assess_projections(batch: pd.DataFrame, *, now: datetime, max_age_minutes: float = 120.0, min_skill_rows: int = 300) -> dict:
    if batch is None or len(batch) == 0:
        return {"ok": False, "reason": "no production projection batch for the target week", "rows": 0}
    gen = pd.to_datetime(batch["generated_at"].iloc[0], utc=True)
    age = (now.astimezone(timezone.utc) - gen.to_pydatetime()).total_seconds() / 60.0
    skill = int((batch["position"].astype(str).str.upper() != "DST").sum())
    problems = []
    if age > max_age_minutes: problems.append(f"projection batch is {age:.0f} min old (limit {max_age_minutes:.0f})")
    if skill < min_skill_rows: problems.append(f"projection batch has {skill} skill rows (minimum {min_skill_rows})")
    if batch["proj_points"].isna().all(): problems.append("projection batch has no proj_points")
    return {"ok": not problems, "reason": "; ".join(problems), "rows": int(len(batch)), "skill_rows": skill, "generated_at": gen.isoformat(), "age_minutes": age}


def assess_tabpfn(rows_for_week: int, weeks_present: list[int], *, target_week: int,
                  expected_rows: int | None = None, min_coverage: float = 0.80) -> dict:
    """Presence AND sufficiency.

    2026-09-21: a `tabpfn-gen` run made before `build-features` wrote **51** rows for
    week 3 against a 633-skill-player slate, and this gate went green because it only
    tested `rows_for_week <= 0`. A cache can be present and still be a one-game cache.

    `expected_rows` is the target slate's skill-player count, which is why the threshold
    is derived rather than constant -- a constant here becomes the next `N_BOOM=40`.
    Historic full caches run at roughly one row per skill player (2025 weeks: 637-800),
    so 80% is a floor that a complete cache clears comfortably and a truncated one
    cannot approach.

    Sufficiency that cannot be computed is NOT silently skipped: with no `expected_rows`
    the check reports that it could not be made, and the gate fails closed.
    """
    problems = []
    if rows_for_week <= 0:
        problems.append(f"TabPFN cache has no rows for week {target_week}")
    beyond = sorted(w for w in weeks_present if int(w) > int(target_week))
    if beyond:
        problems.append(f"TabPFN cache carries weeks beyond the target: {beyond[:5]} (target-week discipline)")
    floor = None
    if expected_rows is None or int(expected_rows) <= 0:
        problems.append("TabPFN sufficiency not checkable: no slate skill-player count "
                        "(pass --draft-group so the floor is derived from the slate)")
    elif rows_for_week > 0:
        floor = int(min_coverage * int(expected_rows))
        if rows_for_week < floor:
            problems.append(
                f"TabPFN cache has {rows_for_week} rows for week {target_week} against a "
                f"{int(expected_rows)}-skill-player slate (floor {floor} = "
                f"{min_coverage:.0%}); it looks truncated, re-run tabpfn-gen AFTER build-features")
    return {"ok": not problems, "reason": "; ".join(problems), "rows_for_week": int(rows_for_week),
            "weeks_present": sorted(int(w) for w in weeks_present),
            "expected_rows": None if expected_rows is None else int(expected_rows),
            "sufficiency_floor": floor, "min_coverage": float(min_coverage)}


def assess_files(chosen_dose: dict | None, contests: list | None, *, min_book_entries: int = 90) -> dict:
    problems = []
    if not chosen_dose or not all(k in chosen_dose for k in ("CHOSEN_LEV", "CHOSEN_BOOM")):
        problems.append("chosen-dose file missing or without CHOSEN_LEV/CHOSEN_BOOM")
    else:
        try:
            if int(chosen_dose["CHOSEN_LEV"]) <= 0 or int(chosen_dose["CHOSEN_BOOM"]) <= 0: problems.append("chosen dose must be positive")
        except ValueError:
            problems.append("chosen dose is not numeric")
    if not contests:
        problems.append("contests.json missing or empty")
    else:
        try:
            total = sum(int(c["entries"]) for c in contests)
            if total < min_book_entries: problems.append(f"contests.json totals {total} entries (minimum {min_book_entries})")
            if any(not str(c.get("contest_id", "")).strip() or not str(c.get("name", "")).strip() for c in contests): problems.append("a contest lacks contest_id or name")
        except (KeyError, TypeError, ValueError):
            problems.append("contests.json rows lack integer entries")
    return {"ok": not problems, "reason": "; ".join(problems)}


def verdict(projections: dict, market: dict, tabpfn: dict, files: dict) -> dict:
    parts = {"projections": projections, "market_monitor": market, "tabpfn": tabpfn, "files": files}
    ok = all(p.get("ok") for p in parts.values())
    reasons = [f"{k}: {p.get('reason') or p.get('line')}" for k, p in parts.items() if not p.get("ok")]
    return {"ok": ok, "status": "OK" if ok else "FAIL", "reasons": reasons, "checks": parts}
