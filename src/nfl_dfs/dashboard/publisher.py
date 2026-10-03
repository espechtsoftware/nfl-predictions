"""Publish a week's laptop artifacts to the dashboard tables.

The laptop holds our candidate pool, books and shadow arms only as files:
the lab live run directory (candidates.parquet, book.csv, frame.parquet,
receipt.json) and ``~/weekN-sunday`` (vetted/composite/hybrid/cash/paper
books, exposure-cap books, ordering shadows, DraftKings upload files).

Safety (reviewer, 2026-10-03):
* The live week directories are never parsed in place. ``make_snapshot``
  copies an allow-listed set of files into
  ``~/.cache/laptop-agent/dashboard-snapshots/<season>-wNN/<utc>/`` (into a
  temporary directory first, renamed when complete; a source file that
  changes while it is copied aborts the snapshot), and only the copy is
  parsed.
* A week is not touched before its Sunday window closes (15:30 Central)
  unless the caller points ``--inputs`` at an existing snapshot.
* Private files are never read: contests.json (stake plan), contest
  details, DraftKings entry exports and bundles (entry keys), the private/
  folder, env files and logs are outside the allow-list.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .teams import canon_team

SNAPSHOT_ROOT = Path.home() / ".cache" / "laptop-agent" / "dashboard-snapshots"
LAB_LIVE = Path.home() / "projects" / ".nfl2-worktrees" / "week4-live-center" / "results" / "live"
MANIFEST = "SNAPSHOT.json"

RUN_FILES = ("candidates.parquet", "book.csv", "frame.parquet", "receipt.json")

# Week-directory allow-list, relative to ~/weekN-sunday; {tag} is the build
# tag (e.g. 20261003t1535z-d6400sat-32cdb61).
WEEK_PATTERNS = (
    "vetted-{tag}/book.csv",
    "composite-{tag}/book.csv",
    "hybrid15-{tag}/book.csv",
    "cash-shadow-w??-?-{tag}/book.csv",
    "exposure-caps-{tag}/capped_book.csv",
    "exposure-caps-r2-{tag}/capped_book.csv",
    "paper-r2-{tag}/book/book.csv",
    "ordering_shadows-{tag}-k*.json",
    "upload-{tag}-*.csv",
)
# Never copied even if a pattern above would match.
DENY = ("contests.json*", "contest-details*", "*ENTER*", "*entries*", "private/*",
        "*bundle/*", "*.env", "*.log", "*DKEntries*")

ID_COLUMNS = ("id", "dk_player_id", "dk_draftable_id", "display_name")


class PublishError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def week_key(season: int, week: int) -> str:
    return f"{int(season)}-w{int(week):02d}"


# ------------------------------------------------------------- discovery --

def run_tag_prefix(run_id: str) -> str:
    """Lab run '20261003T153519693080Z-32cdb61' -> week-dir tag prefix
    '20261003t1535z' and the code sha '32cdb61'."""
    m = re.match(r"^(\d{8})T(\d{4})\d*Z-([0-9a-f]+)$", run_id)
    if not m:
        raise PublishError(f"unrecognised lab run id {run_id!r}")
    return f"{m.group(1)}t{m.group(2)}z"


def tags_for_run(week_dir: Path, run_id: str) -> list[str]:
    prefix = run_tag_prefix(run_id)
    sha = run_id.rsplit("-", 1)[-1]
    tags = set()
    for p in week_dir.glob(f"vetted-{prefix}-*"):
        tag = p.name.removeprefix("vetted-")
        if tag.endswith(sha):
            tags.add(tag)
    return sorted(tags)


def find_run(lab_week_dir: Path, run_id: str | None) -> Path:
    if run_id:
        p = lab_week_dir / run_id
    else:
        latest = lab_week_dir / "LATEST"
        if not latest.is_file():
            raise PublishError(f"no LATEST in {lab_week_dir}; pass --run-id")
        p = lab_week_dir / latest.read_text().strip()
    if not p.is_dir():
        raise PublishError(f"lab run dir {p} not found")
    return p


def _denied(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, d) or fnmatch.fnmatch(Path(rel).name, d) for d in DENY)


def week_files(week_dir: Path, tag: str) -> list[Path]:
    out = []
    for pat in WEEK_PATTERNS:
        for p in sorted(week_dir.glob(pat.format(tag=tag))):
            rel = str(p.relative_to(week_dir))
            if p.is_file() and not _denied(rel):
                out.append(p)
    return out


# -------------------------------------------------------------- snapshot --

def _copy_stable(src: Path, dst: Path) -> dict:
    before = src.stat()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    after = src.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise PublishError(f"{src} changed while it was copied; retry when the build is idle")
    return {"bytes": dst.stat().st_size, "sha256": _sha256(dst)}


def make_snapshot(season: int, week: int, run_dir: Path, week_dir: Path, tag: str,
                  root: Path = SNAPSHOT_ROOT, now: datetime | None = None) -> Path:
    """Copy the allow-listed inputs into a fresh snapshot directory
    (temporary name, renamed when complete) and return it."""
    now = now or datetime.now(timezone.utc)
    parent = root / week_key(season, week)
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".tmp-{uuid.uuid4().hex}"
    final = parent / now.strftime("%Y%m%dT%H%M%SZ")
    files = []
    try:
        for name in RUN_FILES:
            src = run_dir / name
            if src.is_file():
                files.append({"rel": f"run/{name}", "source": str(src),
                              **_copy_stable(src, tmp / "run" / name)})
        for src in week_files(week_dir, tag):
            rel = str(src.relative_to(week_dir))
            files.append({"rel": f"week/{rel}", "source": str(src),
                          **_copy_stable(src, tmp / "week" / rel)})
        if not any(f["rel"] == "run/frame.parquet" for f in files):
            raise PublishError(f"{run_dir} has no frame.parquet; nothing can be resolved")
        manifest = {"season": int(season), "week": int(week), "tag": tag,
                    "run_id": run_dir.name, "created_utc": now.isoformat(), "files": files}
        (tmp / MANIFEST).write_text(json.dumps(manifest, indent=1))
        if final.exists():
            raise PublishError(f"{final} already exists")
        os.rename(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


def read_manifest(snap: Path) -> dict:
    p = snap / MANIFEST
    if not p.is_file():
        raise PublishError(f"{snap} is not a dashboard snapshot (no {MANIFEST})")
    return json.loads(p.read_text())


# --------------------------------------------------------------- parsing --

def _key(v: object) -> str:
    """'1164402.0' and 1164402 are both '1164402'; missing -> ''."""
    s = str(v).strip()
    if s.lower() in ("", "nan", "none", "<na>"):
        return ""
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


@dataclass
class Resolver:
    """Maps any roster token (gsis id / TEAM_DST, dk_player_id,
    dk_draftable_id or display name) to a frame row."""
    frame: pd.DataFrame
    maps: dict[str, dict[str, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.frame = self.frame.reset_index(drop=True)
        for col in ID_COLUMNS:
            if col in self.frame:
                m: dict[str, int] = {}
                for i, v in enumerate(self.frame[col]):
                    k = _key(v)
                    if k and k not in m:
                        m[k] = i
                self.maps[col] = m

    def resolve(self, rosters: list[list[str]]) -> tuple[np.ndarray, int]:
        """(n_ok x 9 frame rows, n_skipped); the id column is detected by
        overlap, never assumed."""
        rosters = [[_key(t) for t in r] for r in rosters if r]
        if not rosters:
            return np.zeros((0, 9), int), 0
        tokens = {t for r in rosters for t in r}
        col = max(self.maps, key=lambda c: len(tokens & set(self.maps[c])))
        m = self.maps[col]
        ok = [[m[t] for t in r] for r in rosters if len(r) == 9 and all(t in m for t in r)]
        return np.array(ok, int).reshape(-1, 9), len(rosters) - len(ok)


def read_rosters(path: Path) -> list[list[str]]:
    """Rosters from every book format found on the laptop:
    DraftKings-header CSVs (QB,RB,...,DST: ids per slot), candidate-style CSV
    or parquet ('players' = comma-separated ids)."""
    if path.suffix == ".parquet":
        df = pd.read_parquet(path, columns=["players"])
        return [str(p).split(",") for p in df.players]
    df = pd.read_csv(path, dtype=str)
    if "players" in df.columns and "names" in df.columns:
        return [str(p).split(",") for p in df.players]
    slots = [c for c in df.columns if re.match(r"^(QB|RB|WR|TE|FLEX|DST)(\.\d+)?$", c)]
    if len(slots) == 9:
        return df[slots].astype(str).values.tolist()
    if "ids" in df.columns:  # cash_shadow.csv: '|'-joined ids
        return [str(p).split("|") for p in df.ids]
    raise PublishError(f"{path.name}: no roster columns recognised ({list(df.columns)[:6]})")


def read_orderings(path: Path) -> dict[str, list[list[str]]]:
    d = json.loads(path.read_text())
    out = {}
    for name, o in (d.get("orderings") or {}).items():
        rosters = o.get("rosters") if isinstance(o, dict) else None
        if rosters:
            out[name] = [[str(x) for x in r] for r in rosters]
    return out


@dataclass
class ArmSource:
    arm: str
    kind: str
    rel: str
    contest_id: str | None = None
    ordering: str | None = None


def classify(rel: str, tag: str) -> ArmSource | None:
    """Arm identity from a snapshot-relative path."""
    name = rel.removeprefix("week/")
    if rel == "run/book.csv":
        return ArmSource("lab_book", "book", rel)
    if rel == "run/candidates.parquet":
        return ArmSource("pool", "pool", rel)
    if name == f"vetted-{tag}/book.csv":
        return ArmSource("vetted", "entered", rel)
    for prefix, arm, kind in (("composite", "composite", "shadow"),
                              ("hybrid15", "hybrid15", "shadow"),
                              ("exposure-caps-r2", "exposure_caps_r2", "shadow"),
                              ("exposure-caps", "exposure_caps", "shadow"),
                              ("paper-r2", "paper_r2", "paper")):
        if name.startswith(f"{prefix}-{tag}/"):
            return ArmSource(arm, kind, rel)
    m = re.match(rf"^cash-shadow-w\d\d-([A-Z])-{re.escape(tag)}/book\.csv$", name)
    if m:
        return ArmSource(f"cash_{m.group(1)}", "cash_shadow", rel)
    m = re.match(rf"^upload-{re.escape(tag)}-(.+)\.csv$", name)
    if m:
        label = m.group(1)
        cid = re.search(r"-(\d{6,})-ranks-", label)
        return ArmSource(f"upload:{label}", "upload", rel, contest_id=cid.group(1) if cid else None)
    m = re.match(rf"^ordering_shadows-{re.escape(tag)}-(k\d+)\.json$", name)
    if m:
        return ArmSource(f"ordering:{m.group(1)}", "ordering", rel)
    return None


@dataclass
class Parsed:
    manifest: dict
    frame: pd.DataFrame
    pool: np.ndarray
    book: np.ndarray
    book_source: str
    arms: list[tuple[ArmSource, np.ndarray]]
    skipped: list[str]
    built_utc: str | None


def parse_snapshot(snap: Path) -> Parsed:
    man = read_manifest(snap)
    tag = man["tag"]
    frame = pd.read_parquet(snap / "run" / "frame.parquet")
    res = Resolver(frame)
    sha = {f["rel"]: f["sha256"] for f in man["files"]}
    arms: list[tuple[ArmSource, np.ndarray]] = []
    skipped: list[str] = []
    for rel in sorted(sha):
        src = classify(rel, tag)
        if src is None:
            continue
        path = snap / rel
        try:
            if src.kind == "ordering":
                for oname, rosters in read_orderings(path).items():
                    idx, bad = res.resolve(rosters)
                    if bad:
                        skipped.append(f"{rel}#{oname}: {bad} roster(s) unresolved")
                    if len(idx):
                        arms.append((ArmSource(f"ordering:{oname}", "ordering", rel,
                                               ordering=oname), idx))
                continue
            idx, bad = res.resolve(read_rosters(path))
        except Exception as exc:  # report and continue: one bad file never sinks the week
            skipped.append(f"{rel}: {type(exc).__name__}: {exc}")
            continue
        if bad:
            skipped.append(f"{rel}: {bad} roster(s) unresolved")
        if len(idx):
            arms.append((src, idx))
        else:
            skipped.append(f"{rel}: no resolvable rosters")
    by_arm = {a.arm: idx for a, idx in arms}
    if "pool" not in by_arm:
        raise PublishError("the snapshot has no resolvable candidates.parquet")
    book_arm = "vetted" if "vetted" in by_arm else "lab_book"
    if book_arm not in by_arm:
        raise PublishError("the snapshot has neither a vetted nor a lab book")
    built = None
    if (snap / "run" / "receipt.json").is_file():
        built = json.loads((snap / "run" / "receipt.json").read_text()).get("built_utc")
    return Parsed(man, res.frame, by_arm["pool"], by_arm[book_arm],
                  next(a.rel for a, _ in arms if a.arm == book_arm), arms, skipped, built)


# ------------------------------------------------------------------ rows --

def pool_exposure_rows(p: Parsed) -> pd.DataFrame:
    fr = p.frame
    n_rows = len(fr)
    pool_n = np.bincount(p.pool.ravel(), minlength=n_rows)
    book_n = np.bincount(p.book.ravel(), minlength=n_rows)
    keep = np.flatnonzero((pool_n > 0) | (book_n > 0))
    pos = fr.get("pos", fr.get("position"))
    out = pd.DataFrame({
        "season": int(p.manifest["season"]), "week": int(p.manifest["week"]),
        "run_id": p.manifest["run_id"],
        "built_utc": pd.to_datetime(p.built_utc, utc=True) if p.built_utc else pd.NaT,
        "player": fr.display_name.iloc[keep].astype(str).to_numpy(),
        "dk_player_id": pd.to_numeric(fr.dk_player_id.iloc[keep], errors="coerce").astype("Int64").to_numpy(),
        "position": (pos.iloc[keep].astype(str).str.split("/").str[0].to_numpy()
                     if pos is not None else None),
        "team": [canon_team(t) for t in fr.get("team", fr.get("team_abbr")).iloc[keep]],
        "pool_share": pool_n[keep] / max(len(p.pool), 1),
        "book_share": book_n[keep] / max(len(p.book), 1),
        "n_pool": pool_n[keep].astype(int), "n_book": book_n[keep].astype(int),
    })
    return out.sort_values("pool_share", ascending=False).reset_index(drop=True)


@dataclass
class Outcomes:
    """Realized inputs: per-frame-row DK points, the Millionaire field's
    points, and its cash line when payouts are known."""
    player_points: np.ndarray | None
    field_points: np.ndarray | None
    cash_line: float | None


def arm_metrics(idx: np.ndarray, out: Outcomes) -> dict:
    m = {"n_lineups": int(len(idx)), "mean_points": None, "best_points": None,
         "best_rank": None, "cash_rate": None}
    if out.player_points is None or not len(idx):
        return m
    pts = out.player_points[idx].sum(axis=1)
    m["mean_points"] = float(pts.mean())
    m["best_points"] = float(pts.max())
    if out.field_points is not None and len(out.field_points):
        m["best_rank"] = int(1 + (out.field_points > pts.max() + 1e-9).sum())
    if out.cash_line is not None and np.isfinite(out.cash_line):
        m["cash_rate"] = float((pts >= out.cash_line - 1e-9).mean())
    return m


def arms_rows(p: Parsed, out: Outcomes, published: datetime | None = None) -> pd.DataFrame:
    published = published or datetime.now(timezone.utc)
    sha = {f["rel"]: f["sha256"] for f in p.manifest["files"]}
    rows = []
    for src, idx in p.arms:
        rows.append({"season": int(p.manifest["season"]), "week": int(p.manifest["week"]),
                     "arm": src.arm, "kind": src.kind, "contest_id": src.contest_id,
                     **arm_metrics(idx, out), "source_file": src.rel,
                     "source_sha256": sha.get(src.rel), "published_utc": published})
    return pd.DataFrame(rows)


def player_points(frame: pd.DataFrame, by_name: dict[str, float],
                  by_gsis: dict[str, float]) -> np.ndarray | None:
    """DK points per frame row: the standings' printed fpts by display name
    first, then player_week_actuals by gsis id; None when neither has rows
    (the week is not scored yet)."""
    if not by_name and not by_gsis:
        return None
    pts = []
    for name, gid in zip(frame.display_name.astype(str), frame.get("id", frame.get("gsis_id"))):
        v = by_name.get(name)
        if v is None:
            v = by_gsis.get(_key(gid))
        pts.append(0.0 if v is None else float(v))
    return np.array(pts, float)


def fetch_outcomes(query: Callable[[str], pd.DataFrame], season: int, week: int,
                   frame: pd.DataFrame) -> Outcomes:
    """Read-only BigQuery reads for scoring (see sql/dashboard/milly_points.sql)."""
    from .data import render

    names = query(render("week_player_points", season=int(season), week=int(week)))
    by_name = {str(r.display_name): float(r.fpts) for r in names.itertuples(index=False)
               if pd.notna(r.fpts)}
    acts = query(render("week_actuals", season=int(season), week=int(week)))
    by_gsis = {str(r.gsis_id): float(r.dk_points) for r in acts.itertuples(index=False)
               if pd.notna(r.dk_points)}
    field = query(render("milly_points", season=int(season), week=int(week)))
    fp = field.points.to_numpy(float) if len(field) else None
    cash = None
    if len(field) and "payout" in field and field.payout.notna().any():
        paid = field[pd.to_numeric(field.payout, errors="coerce") > 0]
        cash = float(paid.points.min()) if len(paid) else None
    return Outcomes(player_points(frame, by_name, by_gsis), fp, cash)
