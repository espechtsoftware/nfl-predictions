"""Canonical Millionaire-winner registry (roadmap P0.2, v1).

Reconciles the tracked winner CSVs into ONE self-hashed 68-contest
registry with explicit integrity flags, so every analysis names exactly
one winner population instead of silently mixing sources.

Canonical authority (unchanged from `real_winner_overlap`): the
user-supplied `milly-winners-2019-2023-2024.csv` (with the duplicated
2024 week-9 block EXCLUDED as a recorded exclusion, not a silent drop)
plus `2025-milly-rosters.csv`. The article-derived
`milly_rosters_2023_2024.csv` and the 2025 summary file are
CROSS-CHECK sources only: their agreements/disagreements are recorded
per contest and never override the canonical rosters.

Known, deliberately recorded defects (README Data deficiency log
2026-08-22): the 2024 W9 duplicate; raw salary totals above $50,000;
one missing salary; article-source score disagreements; missing
`salary_used` in three 2025 summary weeks; and absent contest IDs /
source URLs / capture times, which cannot be invented and are flagged
as `provenance_gaps` until upstream receipts exist.
"""

from __future__ import annotations

from collections.abc import Mapping
import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Final


REGISTRY_SCHEMA: Final = "milly-winner-registry/v1"
CANONICAL_OLD_FILE: Final = "milly-winners-2019-2023-2024.csv"
CANONICAL_2025_FILE: Final = "2025-milly-rosters.csv"
CROSSCHECK_ARTICLE_FILE: Final = "milly_rosters_2023_2024.csv"
CROSSCHECK_2025_SUMMARY_FILE: Final = "2025-milly-winners.csv"
EXPECTED_CONTESTS: Final = 68
GOVERNED_SEASONS: Final = (2023, 2024, 2025)
ROSTER_SIZE: Final = 9
SALARY_CAP: Final = 50_000
EXCLUDED_DUPLICATE: Final = {"season": 2024, "week": 9}
PROVENANCE_GAPS: Final = (
    "contest-id-absent",
    "source-url-absent",
    "capture-time-absent",
)


class WinnerRegistryError(ValueError):
    """Raised when winner sources differ from their recorded shape."""


def _fail(message: str) -> None:
    raise WinnerRegistryError(message)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _read_rows(path: Path) -> tuple[list[dict[str, str]], dict[str, object]]:
    raw = path.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    identity = {
        "file": path.name,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "rows": len(rows),
    }
    return rows, identity


def _number(value: object) -> float | None:
    text = str(value).strip().replace("%", "")
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_winner_registry(report_root: str | Path) -> dict[str, object]:
    """Build the canonical self-hashed 68-contest winner registry."""
    root = Path(report_root)
    old_rows, old_identity = _read_rows(root / CANONICAL_OLD_FILE)
    recent_rows, recent_identity = _read_rows(root / CANONICAL_2025_FILE)
    article_rows, article_identity = _read_rows(
        root / CROSSCHECK_ARTICLE_FILE
    )
    summary_rows, summary_identity = _read_rows(
        root / CROSSCHECK_2025_SUMMARY_FILE
    )

    contests: dict[tuple[int, int], dict[str, object]] = {}
    excluded_rows = 0
    for row in old_rows:
        season = int(row["season"])
        week = int(row["week"])
        if (
            season == EXCLUDED_DUPLICATE["season"]
            and week == EXCLUDED_DUPLICATE["week"]
        ):
            excluded_rows += 1
            continue
        contest = contests.setdefault((season, week), {
            "season": season,
            "week": week,
            "slate_key": f"{season}-w{week:02d}",
            "players": [],
        })
        contest["players"].append({
            "name": str(row["player"]).strip(),
            "position": str(row["position"]).strip().upper(),
            "salary": (
                int(value) if (value := _number(row["salary"])) is not None
                else None
            ),
            "ownership_pct": _number(row["ownership_pct"]),
            "listed_points": _number(row["fantasy_points"]),
        })
    for row in recent_rows:
        season = 2025
        week = int(row["week"])
        contest = contests.setdefault((season, week), {
            "season": season,
            "week": week,
            "slate_key": f"{season}-w{week:02d}",
            "players": [],
        })
        contest["players"].append({
            "name": str(row["player"]).strip(),
            "position": str(row["position"]).strip().upper(),
            "salary": (
                int(value) if (value := _number(row["salary"])) is not None
                else None
            ),
            "ownership_pct": _number(row["own_pct"]),
            "listed_points": _number(row["pts"]),
        })

    article_scores: dict[tuple[int, int], float] = {}
    for row in article_rows:
        key = (int(row["season"]), int(row["week"]))
        score = _number(row["winning_score"])
        if score is not None:
            article_scores[key] = score
    summary_by_week: dict[int, dict[str, str]] = {
        int(row["week"]): row for row in summary_rows
    }

    registry_contests = []
    for key in sorted(contests):
        contest = contests[key]
        players = sorted(
            contest["players"],
            key=lambda row: (str(row["position"]), str(row["name"])),
        )
        if len(players) != ROSTER_SIZE:
            _fail(
                f"contest {contest['slate_key']} has {len(players)} players"
            )
        salaries = [row["salary"] for row in players]
        points = [row["listed_points"] for row in players]
        roster_points_total = (
            round(sum(points), 2) if all(
                value is not None for value in points
            ) else None
        )
        salary_total = (
            sum(salaries) if all(
                value is not None for value in salaries
            ) else None
        )
        flags: list[str] = []
        if any(value is None for value in salaries):
            flags.append("missing-salary")
        if salary_total is not None and salary_total > SALARY_CAP:
            flags.append("raw-salary-total-above-cap")
        if any(value is None for value in points):
            flags.append("missing-listed-points")
        crosscheck: dict[str, object] = {}
        article = article_scores.get(key)
        if article is not None and roster_points_total is not None:
            crosscheck["article_winning_score"] = article
            crosscheck["article_score_agrees"] = (
                abs(article - roster_points_total) < 0.005
            )
            if not crosscheck["article_score_agrees"]:
                flags.append("article-score-disagrees")
        if contest["season"] == 2025:
            summary = summary_by_week.get(contest["week"])
            if summary is not None:
                summary_score = _number(summary["score"])
                summary_salary = _number(summary["salary_used"])
                crosscheck["summary_score"] = summary_score
                if (
                    summary_score is not None
                    and roster_points_total is not None
                ):
                    crosscheck["summary_score_agrees"] = (
                        abs(summary_score - roster_points_total) < 0.005
                    )
                    if not crosscheck["summary_score_agrees"]:
                        flags.append("summary-score-disagrees")
                if summary_salary is None:
                    flags.append("summary-salary-used-missing")
                elif (
                    salary_total is not None
                    and int(summary_salary) != salary_total
                ):
                    flags.append("summary-salary-disagrees")
        registry_contests.append({
            "season": contest["season"],
            "week": contest["week"],
            "slate_key": contest["slate_key"],
            "governed_cohort": contest["season"] in GOVERNED_SEASONS,
            "players": players,
            "salary_total": salary_total,
            "roster_points_total": roster_points_total,
            "integrity_flags": sorted(set(flags)),
            "crosscheck": crosscheck,
        })

    if len(registry_contests) != EXPECTED_CONTESTS:
        _fail(
            f"registry has {len(registry_contests)} contests, expected "
            f"{EXPECTED_CONTESTS}"
        )
    if excluded_rows != ROSTER_SIZE:
        _fail("2024 week-9 duplicate exclusion did not remove one roster")
    governed = [
        row for row in registry_contests if row["governed_cohort"]
    ]
    per_season: dict[str, int] = {}
    for row in registry_contests:
        per_season[str(row["season"])] = (
            per_season.get(str(row["season"]), 0) + 1
        )
    if sorted(per_season.values()) != [17, 17, 17, 17]:
        _fail(f"per-season contest counts differ: {per_season}")

    body: dict[str, object] = {
        "schema_version": REGISTRY_SCHEMA,
        "canonical_sources": [old_identity, recent_identity],
        "crosscheck_sources": [article_identity, summary_identity],
        "excluded_duplicates": [{
            **EXCLUDED_DUPLICATE,
            "reason": "2024 week 9 duplicates week 7 in the canonical file",
            "rows_excluded": excluded_rows,
        }],
        "contest_count": len(registry_contests),
        "governed_cohort_count": len(governed),
        "governed_cohort_seasons": list(GOVERNED_SEASONS),
        "per_season_contest_counts": per_season,
        "provenance_gaps": list(PROVENANCE_GAPS),
        "contests": registry_contests,
        "uses_realized_outcomes": True,
        "outcome_scope": (
            "historical winner rosters and listed points only; NEVER a "
            "live feature input; analysis joins occur after features and "
            "books are frozen"
        ),
        "promotion_authority": False,
    }
    body["winner_registry_sha256"] = canonical_sha256(body)
    return body


def registry_contest(
    registry: Mapping[str, object], season: int, week: int
) -> dict[str, object]:
    for contest in registry["contests"]:
        if contest["season"] == season and contest["week"] == week:
            return contest
    _fail(f"registry has no contest {season} week {week}")
    raise AssertionError  # unreachable


__all__ = [
    "EXPECTED_CONTESTS",
    "GOVERNED_SEASONS",
    "REGISTRY_SCHEMA",
    "WinnerRegistryError",
    "build_winner_registry",
    "canonical_json_bytes",
    "canonical_sha256",
    "registry_contest",
]
