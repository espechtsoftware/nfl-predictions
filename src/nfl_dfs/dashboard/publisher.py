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
* Private files are never read: contests.json (stake plan), DraftKings entry
  exports (entry keys), paper-r2 bundles, the private/ folder, env files and
  logs are outside the allow-list. The published enter bundle (player ids per
  slot) is copied whole, from where ENTER points. DraftKings' public contest details
  (contest-details*.json: payout ladders) are snapshotted for the cash line.

Two book arms, never substituted for each other (reviewer 2026-10-03):
  book    the lab run's book.csv, the pre-R4 union book;
  played  the published enter bundle that ``<week dir>/ENTER`` resolves to at
          snapshot time (scripts/sunday_swap.sh re-points it at
          enter-bundles/<tag>-swapN after each R4/swap and never edits the
          upload files): per contest, the first N rows of
          ENTER-<key>-<contest_id>-<N>-entries-KEEP-first-<N>.csv. The whole
          resolved bundle is snapshotted; a missing or dangling ENTER leaves
          the played arm absent, never substituted.
The pool_exposure book share uses the one named by --exposure-book.
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
    "contest-details*.json",
)
# Never copied even if a pattern above would match.
DENY = ("contests.json*", "*ENTER*", "*entries*", "private/*",
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


def resolve_enter(week_dir: Path) -> tuple[Path | None, str]:
    """The bundle directory ``week_dir/ENTER`` points at, and a status:
    ok | missing | dangling | not-a-directory."""
    link = week_dir / "ENTER"
    if not link.is_symlink() and not link.exists():
        return None, "missing"
    target = Path(os.path.realpath(link))
    if not target.exists():
        return None, "dangling"
    if not target.is_dir():
        return None, "not-a-directory"
    return target, "ok"


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
        bundle, enter_status = resolve_enter(week_dir)
        if bundle is not None:
            for src in sorted(p for p in bundle.iterdir() if p.is_file()):
                files.append({"rel": f"enter/{bundle.name}/{src.name}", "source": str(src),
                              **_copy_stable(src, tmp / "enter" / bundle.name / src.name)})
            again, _ = resolve_enter(week_dir)
            if again != bundle:   # a swap re-pointed ENTER mid-copy
                raise PublishError(f"{week_dir / 'ENTER'} changed from {bundle.name} while it was copied; "
                                   f"retry when the swap is done")
        if not any(f["rel"] == "run/frame.parquet" for f in files):
            raise PublishError(f"{run_dir} has no frame.parquet; nothing can be resolved")
        manifest = {"season": int(season), "week": int(week), "tag": tag,
                    "run_id": run_dir.name, "created_utc": now.isoformat(),
                    "enter_bundle": bundle.name if bundle is not None else None,
                    "enter_status": enter_status, "files": files}
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
        return ArmSource("book", "book", f"{rel} [book: pre-R4 union book.csv]")
    if rel == "run/candidates.parquet":
        return ArmSource("pool", "pool", rel)
    if name == f"vetted-{tag}/book.csv":
        return ArmSource("vetted", "vetted", rel)
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


def _rel_path(rel: str) -> str:
    """The file part of an arm's source label ("run/book.csv [book: ...]")."""
    return rel.split(" [", 1)[0]


def paid_places(details: dict) -> int | None:
    """Last paid rank in a DraftKings contest-details payout ladder (tiers
    with a positive value; scripts/sat_late_swap_live.paid_places)."""
    paid = 0
    for t in details.get("payoutSummary") or []:
        if any(float(x.get("value", 0) or 0) > 0 for x in t.get("payoutDescriptions") or []):
            paid = max(paid, int(t["maxPosition"]))
    return paid or None


def read_details(snap: Path, rels: list[str]) -> dict[str, dict]:
    """{contest_id: details} merged over the snapshotted contest-details
    files in name order (a later file wins for a contest it repeats)."""
    out: dict[str, dict] = {}
    for rel in sorted(r for r in rels if Path(r).name.startswith("contest-details")):
        d = json.loads((snap / rel).read_text())
        for cid, v in (d.items() if isinstance(d, dict) else []):
            if isinstance(v, dict):
                out[str(cid)] = {**v, "_source": rel}
    return out


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
    details: dict = field(default_factory=dict)


ENTER_RE = re.compile(r"^ENTER-(.+)-(\d{6,})-(\d+)-entries-KEEP-first-(\d+)\.csv$")


def read_enter_bundle(snap: Path, bundle: str, res: "Resolver") -> tuple[list, list[str]]:
    """Per-contest played rosters from a snapshotted bundle: the first N rows
    of each ENTER-<key>-<contest_id>-<N>-entries-KEEP-first-<N>.csv."""
    out, problems = [], []
    for path in sorted((snap / "enter" / bundle).glob("ENTER-*-entries-KEEP-first-*.csv")):
        m = ENTER_RE.match(path.name)
        if not m:
            problems.append(f"enter/{bundle}/{path.name}: name not recognised")
            continue
        key, cid, keep = m.group(1), m.group(2), int(m.group(4))
        rosters = read_rosters(path)[:keep]
        if len(rosters) < keep:
            problems.append(f"enter/{bundle}/{path.name}: {len(rosters)} rows, expected {keep}")
        idx, bad = res.resolve(rosters)
        if bad:
            problems.append(f"enter/{bundle}/{path.name}: {bad} roster(s) unresolved")
        out.append((key, cid, f"enter/{bundle}/{path.name}", idx))
    return out, problems


def parse_snapshot(snap: Path, exposure_book: str = "played") -> Parsed:
    """Every arm in the snapshot, plus the ``played`` union and the book
    named by ``exposure_book`` ("played" or "book") for pool_exposure; a
    missing choice is an error, never a silent substitution."""
    man = read_manifest(snap)
    tag = man["tag"]
    frame = pd.read_parquet(snap / "run" / "frame.parquet")
    res = Resolver(frame)
    sha = {f["rel"]: f["sha256"] for f in man["files"]}
    arms: list[tuple[ArmSource, np.ndarray]] = []
    skipped: list[str] = []
    try:
        details = read_details(snap, list(sha))
    except Exception as exc:  # noqa: BLE001 -- reported; cash lines then stay NULL
        skipped.append(f"contest-details: {type(exc).__name__}: {exc}")
        details = {}
    for rel in sorted(sha):
        src = classify(rel, tag)
        if src is None:
            continue
        path = snap / _rel_path(src.rel)
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
    bundle = man.get("enter_bundle")
    contests = []
    if bundle:
        contests, problems = read_enter_bundle(snap, bundle, res)
        skipped += problems
    contests = [c for c in contests if len(c[3])]
    if contests:
        for key, cid, rel, idx in contests:
            arms.append((ArmSource(f"played:{key}-{cid}", "played_contest", rel, contest_id=cid), idx))
        rels = sorted(rel for _, _, rel, _ in contests)
        src = ArmSource("played", "played",
                        f"enter/{bundle}/ [played: ENTER bundle {bundle} as published after R4/swap; "
                        f"{len(contests)} contests]")
        arms.append((src, np.vstack([idx for _, _, _, idx in contests])))
        sha[src.rel] = hashlib.sha256("".join(sha[r] for r in rels).encode()).hexdigest()
    else:
        skipped.append(f"played: ENTER {man.get('enter_status', 'missing')}"
                       + (f" (bundle {bundle} has no KEEP-first files)" if bundle else "")
                       + "; no played arm published")
    by_arm = {a.arm: (a, idx) for a, idx in arms}
    if "pool" not in by_arm:
        raise PublishError("the snapshot has no resolvable candidates.parquet")
    if exposure_book not in ("played", "book"):
        raise PublishError(f"--exposure-book must be played or book, not {exposure_book!r}")
    if exposure_book not in by_arm:
        raise PublishError(f"the {exposure_book!r} book is not in this snapshot; pass "
                           f"--exposure-book {'book' if exposure_book == 'played' else 'played'} explicitly "
                           f"if that is the book you mean")
    built = None
    if (snap / "run" / "receipt.json").is_file():
        built = json.loads((snap / "run" / "receipt.json").read_text()).get("built_utc")
    man = {**man, "files": [*man["files"], *({"rel": r, "sha256": h} for r, h in sha.items()
                                              if r not in {f["rel"] for f in man["files"]})]}
    src, book = by_arm[exposure_book]
    return Parsed(man, res.frame, by_arm["pool"][1], book, src.rel, arms, skipped, built, details)


# ------------------------------------------------------------------ rows --

def pool_exposure_rows(p: Parsed, published: datetime | None = None) -> pd.DataFrame:
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
        "book_source": p.book_source,
        "published_utc": published or datetime.now(timezone.utc),
    })
    return out.sort_values("pool_share", ascending=False).reset_index(drop=True)


@dataclass
class Outcomes:
    """Realized inputs: per-frame-row DK points, the Millionaire field's
    points, and cash lines per contest (the points of the last paid rank,
    paid places from the snapshotted contest details)."""
    player_points: np.ndarray | None
    field_points: np.ndarray | None
    cash_line: float | None                       # the Millionaire's
    cash_lines: dict = field(default_factory=dict)  # contest_id -> cash line
    milly_contest: str | None = None


def cash_line_at(points: np.ndarray, paid: int | None) -> float | None:
    """The score at the last paid rank (None without a ladder or standings)."""
    if not paid or points is None or not len(points):
        return None
    srt = np.sort(np.asarray(points, float))[::-1]
    return float(srt[min(paid, len(srt)) - 1])


def arm_metrics(idx: np.ndarray, out: Outcomes, contest_id: str | None = None) -> dict:
    m = {"n_lineups": int(len(idx)), "mean_points": None, "best_points": None,
         "best_rank": None, "cash_rate": None}
    if out.player_points is None or not len(idx):
        return m
    pts = out.player_points[idx].sum(axis=1)
    m["mean_points"] = float(pts.mean())
    m["best_points"] = float(pts.max())
    if out.field_points is not None and len(out.field_points):
        m["best_rank"] = int(1 + (out.field_points > pts.max() + 1e-9).sum())
    line = out.cash_lines.get(str(contest_id)) if contest_id else out.cash_line
    if line is not None and np.isfinite(line):
        m["cash_rate"] = float((pts >= line - 1e-9).mean())
    return m


def arms_rows(p: Parsed, out: Outcomes, published: datetime | None = None) -> pd.DataFrame:
    published = published or datetime.now(timezone.utc)
    sha = {f["rel"]: f["sha256"] for f in p.manifest["files"]}
    rows = []
    for src, idx in p.arms:
        rows.append({"season": int(p.manifest["season"]), "week": int(p.manifest["week"]),
                     "arm": src.arm, "kind": src.kind, "contest_id": src.contest_id,
                     **arm_metrics(idx, out, src.contest_id), "source_file": src.rel,
                     "source_sha256": sha.get(src.rel) or sha.get(_rel_path(src.rel)),
                     "published_utc": published})
    return pd.DataFrame(rows)


def contest_lines_rows(p: Parsed, points: dict[str, np.ndarray],
                       published: datetime | None = None) -> pd.DataFrame:
    """One row per contest in the snapshotted details: paid places, field
    size, and the cash line (NULL when the standings are not imported)."""
    published = published or datetime.now(timezone.utc)
    sha = {f["rel"]: f["sha256"] for f in p.manifest["files"]}
    rows = []
    for cid, d in sorted(p.details.items()):
        paid = paid_places(d)
        pts = points.get(cid)
        rows.append({"season": int(p.manifest["season"]), "week": int(p.manifest["week"]),
                     "contest_id": cid, "contest_name": d.get("name"),
                     "draft_group_id": d.get("draftGroupId"),
                     "field_size": int(len(pts)) if pts is not None and len(pts) else
                     (d.get("entries") or d.get("maximumEntries") or d.get("max")),
                     "paid_places": paid, "cash_line": cash_line_at(pts, paid),
                     "source_file": d.get("_source"), "source_sha256": sha.get(d.get("_source")),
                     "published_utc": published})
    return pd.DataFrame(rows, columns=["season", "week", "contest_id", "contest_name", "draft_group_id",
                                       "field_size", "paid_places", "cash_line", "source_file",
                                       "source_sha256", "published_utc"])


def player_points(frame: pd.DataFrame, by_name: dict[str, float],
                  by_gsis: dict[str, float]) -> np.ndarray | None:
    """DK points per frame row: the standings' printed fpts by display name
    first, then player_week_actuals by gsis id; None when neither has rows
    (the week is not scored yet)."""
    if not by_name and not by_gsis:
        return None
    names = frame.display_name.astype(str)
    shared = set(names[names.duplicated(keep=False)])   # two frame players, one name
    pts = []
    for name, gid in zip(names, frame.get("id", frame.get("gsis_id"))):
        v = None if name in shared else by_name.get(name)
        if v is None:
            v = by_gsis.get(_key(gid))
        pts.append(0.0 if v is None else float(v))
    return np.array(pts, float)


def fetch_outcomes(query: Callable[[str], pd.DataFrame], season: int, week: int,
                   frame: pd.DataFrame, details: dict | None = None
                   ) -> tuple[Outcomes, dict[str, np.ndarray]]:
    """Read-only BigQuery reads for scoring: player points, the Millionaire
    field, and every detailed contest's standings points (for cash lines)."""
    from .data import fetch_milly_contests, render

    names = query(render("week_player_points", season=int(season), week=int(week)))
    by_name = {str(r.display_name): float(r.fpts) for r in names.itertuples(index=False)
               if pd.notna(r.fpts)}
    acts = query(render("week_actuals", season=int(season), week=int(week)))
    by_gsis = {str(r.gsis_id): float(r.dk_points) for r in acts.itertuples(index=False)
               if pd.notna(r.dk_points)}
    field = query(render("milly_points", season=int(season), week=int(week)))
    if field.empty:
        # Before the standings land, player_week_actuals already holds zeros:
        # scoring now would publish zeros as results.
        raise PublishError(f"no Millionaire standings imported for {season} week {week}; refusing to "
                           f"score (import them first, or --no-bq for an unscored dry run)")
    fp = field.points.to_numpy(float)
    mc = fetch_milly_contests(query, season)
    mc = mc[mc.week == int(week)] if not mc.empty else mc
    milly = str(mc.contest_id.iloc[0]) if len(mc) else None
    if len(mc) and "lobby_contest_id" in mc and pd.notna(mc.lobby_contest_id.iloc[0]) \
            and str(mc.lobby_contest_id.iloc[0]) != milly:
        print(f"MISMATCH: the lobby's Millionaire is {mc.lobby_contest_id.iloc[0]} but the imported "
              f"standings are {milly}; using the standings")
    details = details or {}
    ids = sorted(c for c in details if c.isdigit())
    points: dict[str, np.ndarray] = {}
    if ids:
        cp = query(render("contest_points", season=int(season), week=int(week),
                          contest_ids=", ".join(f"'{c}'" for c in ids)))
        for cid, g in cp.groupby(cp.contest_id.astype(str)) if len(cp) else []:
            points[cid] = g.points.to_numpy(float)
    if milly and fp is not None:
        points.setdefault(milly, fp)
    lines = {cid: cash_line_at(points.get(cid), paid_places(d)) for cid, d in details.items()}
    lines = {k: v for k, v in lines.items() if v is not None}
    return (Outcomes(player_points(frame, by_name, by_gsis), fp, lines.get(milly) if milly else None,
                     lines, milly), points)
