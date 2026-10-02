"""Capture Fantasy Points' projection tables (operator 2026-10-02: the account was upgraded to the DFS tier; "be sure
we're grabbing the other data that is useful from that site this week").

Three tables, each served through the site's /api/proxy as a JSON payload on its page:

  dfs      /tables/nfl/projections/dfs      every DraftKings/FanDuel slate (Classic and Showdown) with its players:
                                            salary, DK/FD fantasy-point projection, points per dollar, projected
                                            ownership, roster slots; keyed by the operator's draft-group id
  weekly   /tables/nfl/projections/weekly   every player's weekly projection under every scoring system (DK included)
                                            and the stat projections behind it
  betting  /tables/nfl/projections/betting  the betting projections (kept whole; shape recorded on first capture)

Capture only: nothing in the build reads these tables until a paper test is adopted by the operator.

READ RULE (reviewer 10-02): every capture is APPENDED, so a table holds one copy per capture. A reader takes only the
newest `retrieved_at` per (season, week) -- and for dfs per (season, week, operator, slate_id) -- never the union. Each capture is
archived create-once and hash-addressed under licensed/fantasy-points/projections/<table>/ (licensed data: never in
git), then appended to BigQuery with its retrieval time. Fails closed on an anonymous session, an offseason table,
locked values (`CtaLockValue`), an empty table or another week's rows.

    python -m nfl_dfs.ops.fantasy_points_projections collect --week 4 [--tables dfs,weekly,betting]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from .fantasy_points_downloads import default_profile_dir
from .fantasy_points_ownership import PROXY_URL, _redacted

COLLECTOR_VERSION = "fantasy-points-projections-collector-v1"
ARCHIVE_PREFIX = "licensed/fantasy-points/projections"
TABLES = {
    "dfs": ("https://www.fantasypoints.com/nfl/projections/dfs", "/tables/nfl/projections/dfs", "fantasy_points_dfs_projections"),
    "weekly": ("https://www.fantasypoints.com/nfl/projections/weekly", "/tables/nfl/projections/weekly", "fantasy_points_weekly_projections"),
    "betting": ("https://www.fantasypoints.com/nfl/projections/betting", "/tables/nfl/projections/betting", "fantasy_points_betting_projections"),
}
MIN_ROWS = {"dfs": 1, "weekly": 100, "betting": 10}
WEEK_EVIDENCE_MIN = 0.95          # share of whole-table rows that must carry season AND week (reviewer 10-02, item 1)
COERCE_FAIL_SHARE = 0.03          # DraftKings dfs rows losing salary or points to a parse failure (item 3)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")


def assert_no_secrets(text: str) -> None:
    """The archived JSON must carry no email address and no JWT-like token (the session is redacted to roles)."""
    if _EMAIL.search(text) or _JWT.search(text):
        raise RuntimeError("the redacted payload still contains an email-like or token-like string; not archived")


def _table(payload: dict[str, Any], what: str) -> dict[str, Any]:
    session = payload.get("session") if isinstance(payload, dict) else None
    roles = [r for r in ((session or {}).get("roles") or []) if isinstance(r, str)]
    if not isinstance(session, dict) or not session.get("uid") or all(r in ("role_anonymous", "anonymous") for r in roles):
        raise RuntimeError(f"{what}: the API session is anonymous; run `fantasy-points-ownership login --terminal-credentials`")
    table = (payload.get("content") or {}).get("table")
    if not isinstance(table, dict):
        raise RuntimeError(f"{what}: payload carries no table")
    if table.get("isOffseason"):
        raise RuntimeError(f"{what}: table reports offseason")
    values = table.get("values")
    if not isinstance(values, list) or not values:
        raise RuntimeError(f"{what}: table has no values")
    if "CtaLockValue" in json.dumps(values):
        raise RuntimeError(f"{what}: values are locked (CtaLockValue); the plan does not include this table")
    return table


def normalize_dfs(payload: dict[str, Any], *, season: int, week: int) -> list[dict[str, Any]]:
    """One row per slate x player."""
    rows = []
    for slate in _table(payload, "dfs")["values"]:
        if int(slate.get("season") or 0) != season or int(slate.get("week") or 0) != week:
            raise RuntimeError(f"dfs: a slate is for {slate.get('season')}/{slate.get('week')}, expected {season}/{week}")
        for p in slate.get("dfsSlatePlayers") or []:
            rows.append({
                "season": season, "week": week, "operator": slate.get("operator"), "slate_id": str(slate.get("operatorSlateId")),
                "slate_name": slate.get("operatorName"), "game_type": slate.get("operatorGameType"),
                "slate_start": slate.get("operatorStartTime"), "n_games": slate.get("numberOfGames"),
                "last_updated": slate.get("lastUpdated"), "player_id": p.get("playerId"),
                "slate_player_id": str(p.get("operatorSlatePlayerId")), "name": p.get("name"),
                "position": p.get("fantasyPosition"), "operator_position": p.get("operatorPosition"), "team": p.get("team"),
                "opponent": p.get("opponent"), "salary": p.get("operatorSalary"), "fantasy_points": p.get("fantasyPoints"),
                "points_per_dollar": p.get("fantasyPointsPerDollar"),
                "projected_ownership_pct": p.get("projectedOwnershipPercentage"),
                "roster_slots": ",".join(p.get("operatorRosterSlots") or []),
            })
    if not rows:
        raise RuntimeError("dfs: no slate players")
    return rows


def normalize_whole(payload: dict[str, Any], what: str, *, season: int, week: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Weekly / betting: key fields plus the whole row as JSON (no column is dropped). The table has no table-level week,
    so the rows are the only evidence: at least WEEK_EVIDENCE_MIN of them must carry season and week, all of those must
    match, and the rows without them are counted (reviewer 10-02, item 1)."""
    rows = []
    values = _table(payload, what)["values"]
    with_week = sum(1 for v in values if isinstance(v, dict) and v.get("season") is not None and v.get("week") is not None)
    if with_week < WEEK_EVIDENCE_MIN * len(values):
        raise RuntimeError(f"{what}: only {with_week} of {len(values)} rows carry season and week; the week cannot be verified")
    for v in values:
        if not isinstance(v, dict):
            raise RuntimeError(f"{what}: a value is not an object")
        if v.get("season") is not None and int(v["season"]) != season:
            raise RuntimeError(f"{what}: a row is for season {v['season']}, expected {season}")
        if v.get("week") is not None and int(v["week"]) != week:
            raise RuntimeError(f"{what}: a row is for week {v['week']}, expected {week}")
        rows.append({"season": season, "week": week, "player_id": v.get("playerId"), "name": v.get("name"),
                     "position": v.get("fantasyPosition") or v.get("position"), "team": v.get("team"),
                     "opponent": v.get("opponent"), "fantasy_points_draftkings": v.get("fantasyPointsDraftKings"),
                     "last_updated": v.get("lastUpdated"), "row_json": json.dumps(v, sort_keys=True)})
    return rows, {"rows_without_week": len(values) - with_week}


def coerced_nulls(rows: list[dict[str, Any]], frame: Any) -> dict[str, int]:
    """Per numeric column: values present in the payload that became NULL on parsing (reviewer 10-02, item 3)."""
    out = {}
    for c in ("salary", "fantasy_points", "points_per_dollar", "projected_ownership_pct"):
        if c in frame:
            present = [r.get(c) is not None for r in rows]
            out[c] = int(sum(1 for p, isna in zip(present, frame[c].isna()) if p and isna))
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _archive(path: Path, table: str, season: int, week: int) -> str:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    from ..config import settings

    digest = _sha(path)
    name = f"{ARCHIVE_PREFIX}/{table}/season={season}/week={week:02d}/sha256={digest}/{path.name}"
    blob = storage.Client().bucket(settings.gcs_bucket).blob(name)
    try:
        blob.upload_from_filename(str(path), content_type="application/json", if_generation_match=0)
    except PreconditionFailed:
        if hashlib.sha256(blob.download_as_bytes()).hexdigest() != digest:
            raise RuntimeError(f"hash-addressed archive {name} is non-identical")
    return f"gs://{settings.gcs_bucket}/{name}"


def capture_payloads(profile_dir: Path, timeout_s: float, which: list[str]) -> dict[str, list[dict[str, Any]]]:
    from playwright.sync_api import sync_playwright

    if not profile_dir.is_dir():
        raise RuntimeError("Fantasy Points browser profile is missing; run `fantasy-points-ownership login --terminal-credentials`")
    got: dict[str, list[dict[str, Any]]] = {k: [] for k in which}
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(profile_dir), headless=True, viewport={"width": 1800, "height": 1200})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(int(timeout_s * 1000))

        def cap(resp: Any) -> None:
            if resp.url != PROXY_URL:
                return
            try:
                post = resp.request.post_data or ""; body = resp.json()
            except Exception:
                return
            for k in which:
                if f'"url":"{TABLES[k][1]}"' in post and isinstance(body, dict):
                    got[k].append(body)
        page.on("response", cap)
        try:
            for k in which:
                page.goto(TABLES[k][0], wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=30_000)
                except Exception:
                    pass
                page.wait_for_timeout(3_000)
        finally:
            ctx.close()
    return got


def collect(profile_dir: Path, timeout_s: float, *, season: int, week: int, which: list[str], output_root: Path,
            archive: bool = True, load: bool = True) -> dict[str, Any]:
    retrieved_at = datetime.now(UTC)
    stamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    payloads = capture_payloads(profile_dir, timeout_s, which)
    manifest: dict[str, Any] = {"version": COLLECTOR_VERSION, "season": season, "week": week,
                                "retrieved_at_utc": retrieved_at.isoformat(), "tables": {}}
    failures = {}
    for k in which:
        try:
            if not payloads[k]:
                raise RuntimeError(f"{k}: no table payload was observed at {TABLES[k][0]}")
            body = payloads[k][-1]
            evidence: dict[str, int] = {}
            if k == "dfs":
                rows = normalize_dfs(body, season=season, week=week)
            else:
                rows, evidence = normalize_whole(body, k, season=season, week=week)
            if len(rows) < MIN_ROWS[k]:
                raise RuntimeError(f"{k}: only {len(rows)} rows")
            out = output_root / k / f"season={season}" / f"week={week:02d}" / stamp
            out.mkdir(parents=True, exist_ok=True)
            raw = out / f"{k}-raw.json"
            text = json.dumps(_redacted(body), indent=1, sort_keys=True) + "\n"
            assert_no_secrets(text)
            raw.write_text(text, encoding="utf-8")
            entry: dict[str, Any] = {"rows": len(rows), "raw_sha256": _sha(raw), "archive": None, "bigquery": None, **evidence}
            if k == "dfs":
                slates = {}
                for r in rows:
                    slates.setdefault((r["operator"], r["slate_id"], r["slate_name"], r["game_type"]), 0)
                    slates[(r["operator"], r["slate_id"], r["slate_name"], r["game_type"])] += 1
                entry["slates"] = [{"operator": o, "slate_id": s, "name": n, "type": t, "players": c} for (o, s, n, t), c in sorted(slates.items())]
                entry["players_with_ownership"] = sum(1 for r in rows if r["projected_ownership_pct"] is not None)
            if archive:
                entry["archive"] = _archive(raw, k, season, week)
            if load:
                import pandas as pd

                from ..bq import load_dataframe
                from ..config import settings

                frame = pd.DataFrame(rows)
                frame["last_updated"] = pd.to_datetime(frame["last_updated"], utc=True, errors="coerce")
                frame["player_id"] = frame["player_id"].astype("string")      # item 3: the first load fixes the schema
                if k == "dfs":
                    frame["slate_start"] = frame["slate_start"].astype(str)
                    frame["salary"] = pd.to_numeric(frame["salary"], errors="coerce").astype("Int64")
                    for c in ("fantasy_points", "points_per_dollar", "projected_ownership_pct"):
                        frame[c] = pd.to_numeric(frame[c], errors="coerce").astype(float)
                    entry["coerced_nulls"] = coerced_nulls(rows, frame)
                    dk = frame["operator"] == "DraftKings"
                    for c in ("salary", "fantasy_points"):
                        lost = int((frame.loc[dk, c].isna() & pd.Series([r[c] is not None for r in rows], index=frame.index)[dk]).sum())
                        if dk.any() and lost > COERCE_FAIL_SHARE * int(dk.sum()):
                            raise RuntimeError(f"dfs: {lost} DraftKings rows lost {c} to a parse failure (format change?)")
                    frame["n_games"] = pd.to_numeric(frame["n_games"], errors="coerce").astype("Int64")
                else:
                    frame["fantasy_points_draftkings"] = pd.to_numeric(frame["fantasy_points_draftkings"], errors="coerce").astype(float)
                frame["retrieved_at"] = retrieved_at
                frame["source_sha256"] = entry["raw_sha256"]
                frame["collector_version"] = COLLECTOR_VERSION
                ref = f"{settings.raw}.{TABLES[k][2]}"
                load_dataframe(frame, ref, write_disposition="WRITE_APPEND")
                entry["bigquery"] = {"table": ref, "rows": int(len(frame))}
            manifest["tables"][k] = entry
        except RuntimeError as exc:
            failures[k] = str(exc)
    manifest["failures"] = failures
    print(json.dumps(manifest, indent=2, sort_keys=True, default=str))
    if failures:
        raise RuntimeError("; ".join(f"{k}: {v}" for k, v in failures.items()))
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fantasy-points-projections")
    ap.add_argument("--profile-dir", type=Path, default=default_profile_dir())
    ap.add_argument("--timeout", type=float, default=120.0); ap.add_argument("--season", type=int, default=2026)
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect"); c.add_argument("--week", type=int, required=True)
    c.add_argument("--tables", default="dfs,weekly")   # betting: a 3-row preview on the 10-02 plan (In-Season Betting add-on)
    c.add_argument("--output-root", type=Path, default=default_profile_dir().parent / "fantasy-points-projections")
    c.add_argument("--no-archive", action="store_true"); c.add_argument("--no-load", action="store_true")
    a = ap.parse_args(argv)
    which = [t.strip() for t in a.tables.split(",") if t.strip()]
    bad = [t for t in which if t not in TABLES]
    if bad:
        print(f"ERROR: unknown table(s) {bad}; choose from {sorted(TABLES)}", file=sys.stderr); return 2
    try:
        collect(a.profile_dir, a.timeout, season=a.season, week=a.week, which=which, output_root=a.output_root,
                archive=not a.no_archive, load=not a.no_load)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
