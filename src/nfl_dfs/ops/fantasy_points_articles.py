"""Capture the week's Fantasy Points NFL articles (operator 2026-10-02: "capture as much of it as possible" -- Barfield's
DFS Slate Breakdown, Heath's Advanced Matchups, the DFS early looks, Showdown analyses, best bets, the injury tracker).

The site lists articles through /api/proxy `/content/nfl/articles` (title, slug, path, season, published date,
categories, author) and serves each one through `/content/nfl/articles/<season>/<slug>`. For the requested week this
collects every article of the season whose title or slug names that week, plus the season-long injury tracker; for
each it keeps the article record (author reduced to the name) and the page's readable text.

Licensed content: archived create-once and hash-addressed under licensed/fantasy-points/articles/season=/week=/ (never
in git) and appended to nfl_raw.fantasy_points_articles with the retrieval time. Capture only. READ RULE: take the newest
`retrieved_at` per (season, week, slug).

    python -m nfl_dfs.ops.fantasy_points_articles collect --week 4
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
from .fantasy_points_ownership import PROXY_URL
from .fantasy_points_projections import assert_no_secrets

COLLECTOR_VERSION = "fantasy-points-articles-collector-v1"
ARCHIVE_PREFIX = "licensed/fantasy-points/articles"
BQ_TABLE = "fantasy_points_articles"
LIST_PAGES = ("https://www.fantasypoints.com/nfl/articles", "https://www.fantasypoints.com/nfl/dfs")
ALWAYS = re.compile(r"injury-tracker", re.I)
MIN_TEXT_CHARS = 300


def week_pattern(week: int) -> re.Pattern:
    return re.compile(rf"\bweek[- ]?{week}\b|-week-{week}(?:-|$)", re.I)


def select_articles(listing: list[dict[str, Any]], *, season: int, week: int) -> list[dict[str, Any]]:
    """The season's articles naming the week (title or slug), plus the always-kept ones; unique by path."""
    pat = week_pattern(week); out, seen = [], set()
    for a in listing:
        if not isinstance(a, dict) or not a.get("path"):
            continue
        if a.get("season") is not None and int(a["season"]) != season:
            continue
        text = f"{a.get('title', '')} {a.get('slug', '')}"
        if (pat.search(text) or ALWAYS.search(a.get("slug", ""))) and a["path"] not in seen:
            seen.add(a["path"]); out.append(a)
    return out


def article_record(article: dict[str, Any], text: str, *, season: int, week: int) -> dict[str, Any]:
    """One row: the article's identity, its author's NAME only, and the readable text."""
    author = article.get("author")                     # a list of {name, authorId, title, ...} (10-02), a dict, or a string
    authors = author if isinstance(author, list) else [author]
    names = [x.get("name") if isinstance(x, dict) else x for x in authors if isinstance(x, (dict, str))]
    name = ", ".join(n for n in names if n) or None
    access = article.get("access")
    if isinstance(access, dict) and any(str(v).lower() in ("locked", "true") and "lock" in str(k).lower() for k, v in access.items()):
        raise RuntimeError(f"article {article.get('slug')} is locked")
    if len(text or "") < MIN_TEXT_CHARS:
        raise RuntimeError(f"article {article.get('slug')}: only {len(text or '')} characters of text (a paywall preview?)")
    cats = article.get("categories")
    return {"season": season, "week": week, "article_id": str(article.get("articleId")), "slug": article.get("slug"),
            "path": article.get("path"), "title": article.get("title"), "author": name, "topic": str(article.get("topic")),
            "categories": json.dumps(cats, sort_keys=True) if cats is not None else None,
            "published_date": article.get("publishedDate"), "text": text, "text_chars": len(text)}


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _archive(path: Path, season: int, week: int) -> str:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    from ..config import settings

    digest = _sha_bytes(path.read_bytes())
    name = f"{ARCHIVE_PREFIX}/season={season}/week={week:02d}/sha256={digest}/{path.name}"
    blob = storage.Client().bucket(settings.gcs_bucket).blob(name)
    try:
        blob.upload_from_filename(str(path), content_type="application/json", if_generation_match=0)
    except PreconditionFailed:
        if _sha_bytes(blob.download_as_bytes()) != digest:
            raise RuntimeError(f"hash-addressed archive {name} is non-identical")
    return f"gs://{settings.gcs_bucket}/{name}"


def collect(profile_dir: Path, timeout_s: float, *, season: int, week: int, output_root: Path,
            archive: bool = True, load: bool = True) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    if not profile_dir.is_dir():
        raise RuntimeError("Fantasy Points browser profile is missing; run `fantasy-points-ownership login --terminal-credentials`")
    retrieved_at = datetime.now(UTC); stamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    listing: list[dict[str, Any]] = []; bodies: dict[str, dict[str, Any]] = {}
    rows, failures = [], {}
    out = output_root / f"season={season}" / f"week={week:02d}" / stamp
    out.mkdir(parents=True, exist_ok=True)
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
            m = re.search(r'"url":"(/content/nfl/articles[^"]*)"', post)
            if not m or not isinstance(body, dict):
                return
            content = body.get("content") or {}
            if m.group(1) == "/content/nfl/articles":
                vals = ((content.get("articles") or {}).get("values")) or []
                listing.extend(v for v in vals if isinstance(v, dict))
            elif isinstance(content.get("article"), dict):
                bodies[m.group(1)] = content["article"]
        page.on("response", cap)
        try:
            for u in LIST_PAGES:
                page.goto(u, wait_until="domcontentloaded"); page.wait_for_timeout(5_000)
            chosen = select_articles(listing, season=season, week=week)
            for a in chosen:
                try:
                    page.goto(f"https://www.fantasypoints.com{a['path']}", wait_until="domcontentloaded"); page.wait_for_timeout(5_000)
                    text = page.inner_text("article") if page.locator("article").count() else page.inner_text("main")
                    art = next((v for k, v in bodies.items() if k.endswith(a["slug"])), None)
                    if art is None:
                        raise RuntimeError("no article payload observed")
                    rec = article_record(art, text, season=season, week=week)
                    blob = json.dumps({"article": {k: v for k, v in art.items() if k != "author"}, "author": rec["author"],
                                       "text": text}, indent=1, sort_keys=True) + "\n"
                    assert_no_secrets(blob)
                    path = out / f"{a['slug']}.json"; path.write_text(blob, encoding="utf-8")
                    rec["source_sha256"] = _sha_bytes(blob.encode())
                    rec["archive"] = _archive(path, season, week) if archive else None
                    rows.append(rec)
                except Exception as exc:       # noqa: BLE001 -- one bad article must not lose the others
                    failures[a.get("slug", "?")] = f"{type(exc).__name__}: {exc}"
        finally:
            ctx.close()
    manifest = {"version": COLLECTOR_VERSION, "season": season, "week": week, "retrieved_at_utc": retrieved_at.isoformat(),
                "listed": len(listing), "selected": len(rows) + len(failures), "captured": len(rows), "failures": failures,
                "articles": [{"slug": r["slug"], "title": r["title"], "author": r["author"], "chars": r["text_chars"]} for r in rows],
                "bigquery": None}
    if load and rows:
        import pandas as pd

        from ..bq import load_dataframe
        from ..config import settings

        frame = pd.DataFrame(rows).drop(columns=["archive"])
        frame["published_date"] = pd.to_datetime(frame["published_date"], utc=True, errors="coerce")
        frame["retrieved_at"] = retrieved_at; frame["collector_version"] = COLLECTOR_VERSION
        ref = f"{settings.raw}.{BQ_TABLE}"
        load_dataframe(frame, ref, write_disposition="WRITE_APPEND")
        manifest["bigquery"] = {"table": ref, "rows": int(len(frame))}
    print(json.dumps(manifest, indent=2, sort_keys=True, default=str))
    if not rows:
        raise RuntimeError(f"no article captured for {season} week {week}: {failures or 'none listed'}")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fantasy-points-articles")
    ap.add_argument("--profile-dir", type=Path, default=default_profile_dir())
    ap.add_argument("--timeout", type=float, default=120.0); ap.add_argument("--season", type=int, default=2026)
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect"); c.add_argument("--week", type=int, required=True)
    c.add_argument("--output-root", type=Path, default=default_profile_dir().parent / "fantasy-points-articles")
    c.add_argument("--no-archive", action="store_true"); c.add_argument("--no-load", action="store_true")
    a = ap.parse_args(argv)
    try:
        collect(a.profile_dir, a.timeout, season=a.season, week=a.week, output_root=a.output_root,
                archive=not a.no_archive, load=not a.no_load)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
