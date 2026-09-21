"""Row-level lineage of the Sunday regeneration (audit VET-001, 2026-09-21).

The Sunday chain writes three books: the vetted book, the replaced book (every
row holding a player in the whole-slate exclusion set is swapped, receipt
``replace.json``) and the promoted book (a permutation, receipt
``promotion.json``).  Week 2 changed 44 upload rows this way.  This module
proves, fail-closed, that every changed row has a recorded reason, that the
receipts' hashes bind the books they describe, that the promotion is exactly
the recorded permutation, and (optionally) that the upload CSV and the filled
DraftKings entries export carry exactly the promoted book.  It writes one
immutable manifest per run (create-once) with the lineage of every changed row.
Nothing here modifies a book.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = "regeneration-lineage/v1"


class LineageError(RuntimeError):
    """A lineage check failed; the message names the row and the rule."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_book(path: Path) -> list[tuple[str, ...]]:
    rows = [tuple(c.strip() for c in r) for r in csv.reader(open(path)) if r]
    if not rows or rows[0][0].upper() != "QB":
        raise LineageError(f"{path}: not a book.csv (header must start with QB)")
    body = rows[1:]
    if any(len(r) != 9 for r in body):
        raise LineageError(f"{path}: every book row must hold nine ids")
    return body


def name_map(frame_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(dk_player_id -> display name, dk_draftable_id -> dk_player_id) from a run frame."""
    fr = pd.read_parquet(frame_path)
    pid = fr["dk_player_id"].astype("Int64").astype(str)
    names = dict(zip(pid, fr["name"].astype(str) if "name" in fr.columns else fr["display_name"].astype(str)))
    draft = {}
    if "dk_draftable_id" in fr.columns:
        d = fr["dk_draftable_id"]
        draft = {str(int(x)): p for x, p in zip(d, pid) if pd.notna(x)}
    return names, draft


def roster_sha(row: tuple[str, ...]) -> str:
    """Canonical nine-id roster hash (sorted ids, comma-joined)."""
    return hashlib.sha256(",".join(sorted(row)).encode("utf-8")).hexdigest()


def contest_of_position(contests: list[dict] | None, position: int) -> str | None:
    """Sequential layout: contests.json order gives each contest a row block; None when no contests are given."""
    if not contests:
        return None
    p0 = 0
    for c in contests:
        e = int(c["entries"])
        if p0 < position <= p0 + e:
            return str(c.get("name"))
        p0 += e
    return None


def _names(row: tuple[str, ...], names: dict[str, str]) -> set[str]:
    missing = [p for p in row if p not in names]
    if missing:
        raise LineageError(f"book ids not in the frame: {missing[:5]}")
    return {names[p] for p in row}


def verify_replacement(vetted: list, replaced: list, receipt: dict, names: dict[str, str]) -> list[dict]:
    """Every row that differs between the vetted and replaced books must be a receipted replacement with a reason."""
    if len(vetted) != len(replaced):
        raise LineageError(f"vetted book has {len(vetted)} rows, replaced book {len(replaced)}")
    changed = {i + 1 for i, (a, b) in enumerate(zip(vetted, replaced)) if a != b}
    receipted = {int(r["vetted_position"]) for r in receipt.get("replacements", [])}
    removed_positions = {int(x) for x in receipt.get("removed_positions", [])}
    if changed != receipted or changed != removed_positions:
        raise LineageError(
            "changed rows do not match the receipt: changed=%s receipted=%s removed_positions=%s"
            % (sorted(changed - receipted - removed_positions or changed)[:10], sorted(receipted - changed)[:10], sorted(removed_positions - changed)[:10])
        )
    exclusion = {str(k): str(v) for k, v in (receipt.get("exclusion_set") or {}).items()}
    if not exclusion:
        raise LineageError("receipt carries no exclusion_set")
    lineage = []
    for r in sorted(receipt["replacements"], key=lambda r: int(r["vetted_position"])):
        pos = int(r["vetted_position"])
        before, after = _names(vetted[pos - 1], names), _names(replaced[pos - 1], names)
        if before != set(r["removed"]):
            raise LineageError(f"row {pos}: receipt 'removed' roster differs from the vetted book row")
        if after != set(r["replacement"]):
            raise LineageError(f"row {pos}: receipt 'replacement' roster differs from the replaced book row")
        reasons = {str(k): str(v) for k, v in (r.get("removed_because") or {}).items()}
        if not reasons:
            raise LineageError(f"row {pos}: changed without a recorded reason")
        for player, reason in reasons.items():
            if player not in before:
                raise LineageError(f"row {pos}: reason names {player!r} who is not in the removed roster")
            if exclusion.get(player) != reason:
                raise LineageError(f"row {pos}: reason for {player!r} ({reason}) is not the exclusion set's ({exclusion.get(player)})")
        unexplained = sorted(p for p in before if p in exclusion and p not in reasons)
        if unexplained:
            raise LineageError(f"row {pos}: excluded players present but not named in the reason: {unexplained}")
        if any(p in exclusion for p in after):
            raise LineageError(f"row {pos}: replacement still holds an excluded player")
        lineage.append({"upload_row": pos, "removed": sorted(before), "replacement": sorted(after), "reasons": reasons,
                        "removed_roster_sha256": roster_sha(vetted[pos - 1]), "replacement_roster_sha256": roster_sha(replaced[pos - 1]),
                        "source_rank": r.get("source_rank"), "candidate_index": r.get("candidate_index")})
    return lineage


def verify_promotion(replaced: list, promoted: list, receipt: dict) -> dict:
    """The promoted book must be exactly the receipt's permutation of the replaced book."""
    if Counter(replaced) != Counter(promoted):
        raise LineageError("promoted book is not a permutation of the replaced book (row multisets differ)")
    perm = [int(x) for x in receipt.get("permutation") or []]
    if sorted(perm) != list(range(1, len(replaced) + 1)):
        raise LineageError("promotion receipt permutation is not a permutation of 1..K")
    for i, src in enumerate(perm):
        if promoted[i] != replaced[src - 1]:
            raise LineageError(f"promoted row {i + 1} is not replaced row {src} as the receipt states")
    final_of = {src: i + 1 for i, src in enumerate(perm)}          # replaced position -> promoted position
    moved = {(int(m["position_before"]), int(m["position_after"])) for m in receipt.get("moved_rows", [])}
    actual = {(src, dst) for src, dst in final_of.items() if src != dst}
    if moved != actual:
        raise LineageError(f"promotion moved_rows differ from the permutation: receipt {sorted(moved)[:6]} vs actual {sorted(actual)[:6]}")
    return {"final_position_of_replaced_row": final_of, "moved": sorted(actual)}


def parse_cell_ids(cells: list[str]) -> list[str]:
    """'Name (44132580)' or '44132580' -> '44132580'."""
    out = []
    for c in cells:
        c = c.strip()
        if c.endswith(")") and "(" in c:
            c = c[c.rindex("(") + 1:-1].strip()
        if not c.isdigit():
            raise LineageError(f"cannot read a draftable id from cell {c!r}")
        out.append(c)
    return out


def verify_upload(promoted: list, path: Path, draft_to_player: dict[str, str], *, ordered: bool) -> dict:
    """The upload CSV (nine draftable ids per row, in layout order) or the filled DK entries export (Entry ID,
    Contest Name, Contest ID, Entry Fee, then nine 'Name (id)' cells; contest-grouped) must carry the promoted book."""
    rows = [r for r in csv.reader(open(path, encoding="utf-8-sig")) if r and any(x.strip() for x in r)]
    header = [h.strip() for h in rows[0]]
    if header[0].upper() == "QB":
        body = [parse_cell_ids(r[:9]) for r in rows[1:]]
    elif header[:4] == ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]:
        body = [parse_cell_ids(r[4:13]) for r in rows[1:] if len(r) >= 13 and r[0].strip()]
    else:
        raise LineageError(f"{path}: unrecognised upload/export header {header[:5]}")
    mapped = []
    for i, ids in enumerate(body):
        missing = [d for d in ids if d not in draft_to_player]
        if missing:
            raise LineageError(f"{path} row {i + 1}: draftable ids not in the frame: {missing[:3]}")
        mapped.append(tuple(sorted(draft_to_player[d] for d in ids)))
    canon = [tuple(sorted(r)) for r in promoted]
    if len(mapped) != len(canon):
        raise LineageError(f"{path}: {len(mapped)} rows against {len(canon)} promoted rows")
    if ordered:
        bad = [i + 1 for i, (a, b) in enumerate(zip(mapped, canon)) if a != b]
        if bad:
            raise LineageError(f"{path}: rows differ from the promoted book in order at {bad[:10]}")
    elif Counter(mapped) != Counter(canon):
        raise LineageError(f"{path}: row multiset differs from the promoted book")
    return {"path": str(path), "sha256": sha256_of(path), "rows": len(mapped), "check": "ordered" if ordered else "multiset"}


def _recorded_sha(receipt_shas: dict | None, endswith: str) -> str | None:
    for k, v in (receipt_shas or {}).items():
        if str(k).replace("\\", "/").endswith(endswith):
            return str(v)
    return None


def build_manifest(vetted_dir: Path, replaced_dir: Path | None, promoted_dir: Path, *, upload_csv: Path | None = None,
                   entries_csv: Path | None = None, contests: list[dict] | None = None) -> dict:
    """``replaced_dir`` may be None when no replacement step ran: the promotion is then checked against the vetted
    book and the manifest records ``replacement: none`` (recorded, not assumed)."""
    vetted_dir, promoted_dir = Path(vetted_dir), Path(promoted_dir)
    replaced_dir = Path(replaced_dir) if replaced_dir is not None else None
    vetted, promoted = read_book(vetted_dir / "book.csv"), read_book(promoted_dir / "book.csv")
    replaced = read_book(replaced_dir / "book.csv") if replaced_dir is not None else vetted
    names, draft = name_map(promoted_dir / "frame.parquet")
    replace_receipt = json.loads((replaced_dir / "replace.json").read_text()) if replaced_dir is not None else None
    promotion_receipt = json.loads((promoted_dir / "promotion.json").read_text())
    shas = {"vetted_book": sha256_of(vetted_dir / "book.csv"),
            "replaced_book": (sha256_of(replaced_dir / "book.csv") if replaced_dir is not None else None),
            "promoted_book": sha256_of(promoted_dir / "book.csv"),
            "replace_receipt": (sha256_of(replaced_dir / "replace.json") if replaced_dir is not None else None),
            "promotion_receipt": sha256_of(promoted_dir / "promotion.json")}
    problems: list[str] = []
    if replace_receipt is not None:
        rec_in = _recorded_sha(replace_receipt.get("input_sha256"), "/paid-vetted/book.csv") or _recorded_sha(replace_receipt.get("input_sha256"), "book.csv")
        if rec_in != shas["vetted_book"]:
            problems.append("replace.json input sha does not bind the vetted book")
        rec_out = (replace_receipt.get("output_sha256") or {}).get("book.csv")
        if rec_out != shas["replaced_book"]:
            problems.append("replace.json output sha does not bind the replaced book")
    base_sha = shas["replaced_book"] if replaced_dir is not None else shas["vetted_book"]
    prom_out = (promotion_receipt.get("output_sha256") or {}).get("book.csv")
    if prom_out != shas["promoted_book"]:
        problems.append("promotion.json output sha does not bind the promoted book")
    prom_in = json.dumps(promotion_receipt.get("input_sha256") or promotion_receipt.get("inputs") or {})
    if base_sha not in prom_in:
        problems.append("promotion.json inputs do not bind the book it promoted")
    lineage: list[dict] = []
    promotion: dict = {}
    if replace_receipt is not None:
        try:
            lineage = verify_replacement(vetted, replaced, replace_receipt, names)
        except LineageError as exc:
            problems.append(f"replacement: {exc}")
    try:
        promotion = verify_promotion(replaced, promoted, promotion_receipt)
    except LineageError as exc:
        problems.append(f"promotion: {exc}")
    if promotion:
        for row in lineage:
            row["final_position"] = promotion["final_position_of_replaced_row"].get(row["upload_row"])
            row["contest_before"] = contest_of_position(contests, row["upload_row"])
            row["contest_after"] = contest_of_position(contests, row["final_position"]) if row["final_position"] else None
    checks = {}
    for label, path, ordered in (("upload_csv", upload_csv, True), ("entries_export", entries_csv, False)):
        if path is None:
            continue
        try:
            checks[label] = verify_upload(promoted, Path(path), draft, ordered=ordered)
        except LineageError as exc:
            problems.append(f"{label}: {exc}")
    return {"schema": SCHEMA, "built_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "OK" if not problems else "FAILED", "problems": problems,
            "inputs": {"vetted_dir": str(vetted_dir), "replaced_dir": (str(replaced_dir) if replaced_dir is not None else None), "promoted_dir": str(promoted_dir), "sha256": shas},
            "replacement": ("receipted" if replace_receipt is not None else "none"),
            "rows": len(promoted), "changed_rows": len(lineage), "lineage": lineage,
            "promoted_rows_sha256": [roster_sha(r) for r in promoted],
            "contest_blocks": ([{"name": str(c.get("name")), "contest_id": str(c.get("contest_id", "")), "entries": int(c["entries"])} for c in contests] if contests else None),
            "promotion": {"moved": promotion.get("moved", [])}, "upload_checks": checks}


def write_manifest_create_once(manifest: dict, out: Path) -> None:
    out = Path(out)
    if out.exists():
        raise LineageError(f"manifest already exists (create-once): {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
