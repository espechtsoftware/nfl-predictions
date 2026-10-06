"""Which book rows each contest's entries receive -- the one layout rule every ENTER writer and checker uses.

Before 2026-09-24 the rule was vendored inline in `sunday_after_build.sh`, `relayout_enter.sh` and its check, and
assumed (sequential only) in `exposure_cap_book.py`, `promote_first.py`, the lineage report and the exposure sheet.
A layout added in one place and not the others fails late or, worse, silently falls into another branch. Every
consumer now asks this module.

Layouts (ENTER_LAYOUT):
  sequential  each contest takes its own consecutive block (keepers first, fills from the tail); unique lineups.
  top         every contest takes ranks 1..n; a contest marked "block": true takes its own consecutive block.
  head        (operator, 2026-09-24, Week 3) every contest opens with the book's best rows and fills the rest with
              lineups used nowhere else:
                - head size h = 2 for contests of <= 5 entries, 4 for larger ones (never more than n);
                - contests whose entries are all head (n <= 2) take rows 1-4 in blocks of n, per group of contests of
                  the same SIZE (whatever their names), and NEVER repeat a lineup inside the group (operator, 2026-09-24:
                  the nineteen $2 single-entry satellites must not share entries): two 2-entry contests take rows 1-2
                  and 3-4; of nineteen 1-entry contests four take rows 1-4 and the other fifteen take the next unique
                  rows (5-19), which are dealt before any other contest's unique rows;
                - the other contests take rows 1..h, then unique rows, dealt snake-fashion (one per contest per
                  round, in contests.json order, reversing each round);
                - a contest may pin its rows explicitly with "ranks": [1-based ranks] (operator, 2026-09-25: the $20
                  Millionaire takes row 1, three $13 satellites rows 1, 2, 3). Pinned ranks may name any row the
                  unpinned layout already reads (2026-09-27), and the contest takes no part in the rotation, the
                  overflow or the deal;
                - TWO TRACKS (operator, 2026-09-27, after Week 3): a contest marked "track": "tail" (default "mean")
                  draws from a SLEEVE of rows placed after every mean-track row: the mean rows 1..K are the
                  highest-projected-mean lineups for the satellites, the sleeve rows K+1..K+T are the tail-selected
                  lineups for the Millionaire seats. Tail contests take consecutive unique sleeve rows in file order, or
                  pin "ranks" 1-based INSIDE the sleeve (rank 1 = book row K+1). The order (below) permutes the mean
                  rows only; sleeve rows keep their book position. "tail" under any other layout is an error.

  spread      (winners study 2026-09-29 §4.2; laptop W-C) the head layout's TWO TRACKS and book size, but every mean-track
              contest takes its rows SPREAD EVENLY over the mean rows 1..K (K = the head layout's row count for the same
              contests, so the builder's BOOK_ENTRIES is unchanged) instead of the shared head plus consecutive unique rows:
                - the g-th of G contests with n entries takes ranks floor((i + (g + 0.5) / G) * K / n) + 1, i = 0..n-1
                  (n <= K), in the book's order, so its rows sit K/n apart along the optimizer's sequence and hit or
                  miss less together, and equal-size contests are OFFSET from one another (reviewer 2026-09-29
                  addendum: without the offset equal-size contests took identical rows, 37 distinct lineups of 100);
                - all-head contests (n <= 2), grouped by SIZE as the head does, take the group's G*n spread ranks in blocks
                  of n, so no two single-entry satellites share a lineup;
                - contests of DIFFERENT sizes may still hold the same lineup (as the head rows already do); one contest never
                  repeats a row;
                - pins ("ranks") and tail-track contests behave exactly as under head; protected ranks cover every rank an
                  all-head contest takes, which now reach across the whole mean block.

Order (ENTER_ORDER): the ranks above index an ORDER over the upload's rows.
  greedy      the book's own order (vetted, replaced and promoted), rank r = upload row r.
  fewest-low  (external review 2026-09-24 §5.3) rows sorted by their count of predicted LOW-owned players, fewest
              first, ties in the book's order; a promoted row 1 stays row 1, and flagged rows are kept out of the
              PROTECTED ranks only -- the head rows and every rank an all-head (1-2 entry) contest takes, so the
              wildcats and the nineteen single-entry satellites hold clean lineups (operator, 2026-09-24) -- elsewhere they take their fewest-LOW place, so they spread across the
              contests instead of piling into the last-dealt ones (operator, 2026-09-24, after the external
              reviewer showed that "flagged behind every clean row" put all 50 flagged rows into the six supersat25s). "Flagged" (operator, 2026-09-24: "any injury flag") is any player tag from INJURY_TAGS --
              a DK status, an injury-report status or a QB-availability note -- read the same way from
              vetting_final.json and vetting.json, so one book always gets one order. LOW comes from the ownership sets file, matched on the book's dk_player_id.

Command line (the chain's writer and the relayout check call these):
  python -m nfl_dfs.inference.enter_layout write CONTESTS UPLOAD_CSV STAGE_DIR [order options]
  python -m nfl_dfs.inference.enter_layout check CONTESTS UPLOAD_CSV STAGE_DIR [order options]
  python -m nfl_dfs.inference.enter_layout rows-needed CONTESTS [--layout L]
order options: --layout L (default $ENTER_LAYOUT, else sequential) --order O (default $ENTER_ORDER, else greedy)
               --book BOOK_CSV --vetting VETTING_FINAL_JSON --sets SETS_CSV --pin-first
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

LAYOUTS = ("sequential", "top", "head", "spread")
TWO_TRACK = ("head", "spread")   # layouts with a tail sleeve after the mean rows
TRACKS = ("mean", "tail")     # per-contest selection track (2026-09-27): satellites by mean, Millionaire seats by tail
ROWMAP_NAME = "ENTER-rowmap.json"   # published beside the per-contest files: {label: [0-based rows of the bundle's upload]}
MEAN_ROWS_FLOOR = 1           # the mean track's floor (laptop 2026-09-28: the 90-row floor served the retired K80/K90 contract; it built
                              # 71 rows no contest read once the class track owned the book). week_env / sunday_build_host /
                              # check_week_runtime floor BOOK_ENTRIES at the same value; the sleeve starts after the mean rows.
ORDERS = ("greedy", "fewest-low")
HEAD_TOP = 4             # the head rows every contest draws from
HEAD_SMALL, HEAD_LARGE = 2, 4
SMALL_MAX_ENTRIES = 5
# Week-5 candidate (operator 2026-09-30, Q11 649d9c65; panel pending): ENTER_SMALL_MAX_SHARED=M limits how many players
# two rows of the SAME 2..SMALL_MAX_ENTRIES-entry mean-track contest may share. Unset = off (the head/spread rows as
# before). Not for Week 4: this branch merges only after Week 4's Sunday.
SMALL_OVERLAP_ENV = "ENTER_SMALL_MAX_SHARED"
# The largest contest the overlap limit governs (reviewer 2026-09-30 §2: the 10-entry contests gain as the 2-5s did).
# Deliberately NOT SMALL_MAX_ENTRIES, which also sets the head layout's own split (head_size): raising that would re-deal
# every 6..10-entry contest even with the limit off. Unset = 5 (L25's cells).
SMALL_OVERLAP_CEILING_ENV = "ENTER_SMALL_OVERLAP_MAX_ENTRIES"
SMALL_OVERLAP_MAX_ENTRIES = SMALL_MAX_ENTRIES
PLAYER_SLOTS = ("QB", "RB", "WR", "TE", "FLEX", "DST")
MIN_SETS_COVERAGE = 0.90  # share of the book's distinct skill ids the sets file must know
INJURY_TAGS = ("DK", "report", "qb", "backup_qb")   # flag-tag prefixes that bar a row from the head (not practice/market)
# Deliberately NOT "features:" (vet_book.py's designation read from player_week_inference, which can be Wednesday's and
# stale; vet_replace_v4.py never emits it). Only the live DK status, the injury report and QB-availability notes count.


class LayoutError(ValueError):
    pass


def head_size(n: int) -> int:
    return min(n, HEAD_SMALL if n <= SMALL_MAX_ENTRIES else HEAD_LARGE)


def assign_ranks(contests: list[dict], layout: str) -> list[list[int]]:
    """Per contest (contests.json order), the 0-based RANKS its entries take, in file order."""
    if layout not in LAYOUTS:
        raise LayoutError(f"unknown ENTER_LAYOUT {layout!r}; expected one of {LAYOUTS}")
    sizes = []
    for c in contests:
        n = c.get("entries")
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise LayoutError(f"contests.json: entries for {c.get('name')!r} must be a positive integer (got {n!r})")
        sizes.append(n)
    if layout not in TWO_TRACK and any(str(c.get("track", "mean")) == "tail" for c in contests):
        raise LayoutError(f"contests.json: a \"track\": \"tail\" contest needs ENTER_LAYOUT=head or spread (got {layout!r})")
    # 2026-10-06 (the operator's Rev2: his Milly super-satellites pinned to his top rows): sequential and top have no pin
    # handling, so a pinned contest would silently get its own new rows -- against his explicit instruction. Fail closed.
    pinned = [c.get("name") for c in contests if "ranks" in c]
    if pinned and layout not in TWO_TRACK:
        raise LayoutError(f"contests.json: pinned contests {pinned} (\"ranks\") are honored only under ENTER_LAYOUT=head or "
                          f"spread; {layout!r} would ignore the pins")
    if layout == "sequential":
        keep_total = sum(int(c["keep"]) for c in contests)
        keep_next, fill_next, out = 0, keep_total, []
        for c, n in zip(contests, sizes):
            k = int(c["keep"])
            out.append(list(range(keep_next, keep_next + k)) + list(range(fill_next, fill_next + n - k)))
            keep_next += k
            fill_next += n - k
        return out
    if layout == "top":
        cursor, out = 0, []
        for c, n in zip(contests, sizes):
            if c.get("block"):
                out.append(list(range(cursor, cursor + n)))
                cursor += n
            else:
                out.append(list(range(n)))
        return out
    # head / spread: two tracks. The mean-track contests get the head or spread algorithm below; tail-track contests get
    # the sleeve after it.
    mean_algo = _head_ranks if layout == "head" else _spread_ranks
    tracks = [str(c.get("track", "mean")) for c in contests]
    if any(t not in TRACKS for t in tracks):
        raise LayoutError(f"contests.json: track must be one of {TRACKS} (got {sorted(set(tracks) - set(TRACKS))})")
    mean_idx = [i for i, t in enumerate(tracks) if t == "mean"]
    tail_idx = [i for i, t in enumerate(tracks) if t == "tail"]
    if tail_idx:
        mean_out = mean_algo([contests[i] for i in mean_idx], [sizes[i] for i in mean_idx]) if mean_idx else []
        # The sleeve starts after the mean rows the BUILDER writes, which the chain floors at MEAN_ROWS_FLOOR (1 since
        # 2026-09-28; it was 90 while the K90 paid contract lived).
        k = max(MEAN_ROWS_FLOOR, max((max(r) + 1 for r in mean_out if r), default=0))
        t_total = sum(sizes[i] for i in tail_idx)
        out: list[list[int]] = [[] for _ in contests]
        for j, i in enumerate(mean_idx):
            out[i] = mean_out[j]
        cursor = 0
        for i in tail_idx:
            c, n = contests[i], sizes[i]
            if "ranks" in c:
                r = c["ranks"]
                if (not isinstance(r, list) or len(r) != n or len(set(r)) != n
                        or any(not isinstance(x, int) or isinstance(x, bool) or not 1 <= x <= t_total for x in r)):
                    raise LayoutError(f"contests.json: tail contest {c.get('name')!r} ranks {r!r} must be {n} distinct "
                                      f"integers in 1..{t_total} (sleeve ranks, 1 = the first row after the mean rows)")
                out[i] = [k + x - 1 for x in r]
            else:
                out[i] = list(range(k + cursor, k + cursor + n))
                cursor += n
        return out
    return mean_algo(contests, sizes)


def sleeve_size(contests: list[dict], layout: str) -> int:
    """How many book rows the tail track holds (0 unless a two-track layout with tail contests)."""
    if layout not in TWO_TRACK:
        return 0
    return sum(int(c["entries"]) for c in contests if str(c.get("track", "mean")) == "tail")


def _head_ranks(contests: list[dict], sizes: list[int]) -> list[list[int]]:
    """The head algorithm over one track's contests (0-based ranks)."""
    out = [[] for _ in contests]
    seen: dict[tuple, int] = {}
    unique_slots = [0] * len(contests)
    overflow: list[int] = []                   # all-head contests past their group's head blocks
    pinned: list[int] = []
    for i, (c, n) in enumerate(zip(contests, sizes)):
        h = head_size(n)
        if "ranks" in c:                          # explicit pin (operator)
            r = c["ranks"]
            if (not isinstance(r, list) or len(r) != n or len(set(r)) != n
                    or any(not isinstance(x, int) or isinstance(x, bool) or x < 1 for x in r)):
                raise LayoutError(f"contests.json: {c.get('name')!r} ranks {r!r} must be {n} distinct positive integers")
            out[i] = [x - 1 for x in r]
            pinned.append(i)
            continue
        if n <= HEAD_SMALL:                       # the whole contest is head: one head block per group member
            key = n                               # by size, not name: renamed twins must not share rows
            b = seen.get(key, 0)
            seen[key] = b + 1
            if b < HEAD_TOP // n:
                out[i] = list(range(b * n, b * n + n))
            else:
                overflow.append(i)
        else:
            out[i] = list(range(h))
            unique_slots[i] = n - h
    nxt, rnd = HEAD_TOP, 0
    for i in overflow:                            # their own unique rows, the best of the unique pool
        out[i] = list(range(nxt, nxt + sizes[i]))
        nxt += sizes[i]
    order = [i for i in range(len(contests)) if unique_slots[i] > 0]
    while any(unique_slots[i] > 0 for i in order):
        for i in (order if rnd % 2 == 0 else list(reversed(order))):
            if unique_slots[i] > 0:
                out[i].append(nxt)
                nxt += 1
                unique_slots[i] -= 1
        rnd += 1
    # 2026-09-27 (operator: a 2-entry $18 qualifier on rows 1 and 5): a pin may name any row the unpinned layout already
    # reads (at least the head), never a new one -- so a pin cannot grow the book, and rows_needed is unchanged by pins.
    limit = max([HEAD_TOP] + [max(r) + 1 for j, r in enumerate(out) if j not in pinned and r])
    for i in pinned:
        if max(out[i]) + 1 > limit:
            raise LayoutError(f"contests.json: {contests[i].get('name')!r} ranks {contests[i]['ranks']!r} must be "
                              f"{sizes[i]} distinct integers in 1..{limit} (a pin may not add rows to the book)")
    return out


def _spread_ranks(contests: list[dict], sizes: list[int]) -> list[list[int]]:
    """The spread algorithm over one track's contests (0-based ranks): the head layout's row count K for the same
    contests, each contest's rows spread evenly over 0..K-1 (all-head groups spread as one block), pins as under head."""
    K = max((max(r) + 1 for r in _head_ranks(contests, sizes) if r), default=0)
    out = [[] for _ in contests]
    pinned: list[int] = []
    groups: dict[int, list[int]] = {}
    multi: dict[int, list[int]] = {}                        # n -> the multi-entry contests of that size, in file order
    for i, (c, n) in enumerate(zip(contests, sizes)):
        if "ranks" in c:
            r = c["ranks"]
            if (not isinstance(r, list) or len(r) != n or len(set(r)) != n
                    or any(not isinstance(x, int) or isinstance(x, bool) or not 1 <= x <= K for x in r)):
                raise LayoutError(f"contests.json: {c.get('name')!r} ranks {r!r} must be {n} distinct integers in 1..{K} "
                                  f"(a pin may not add rows to the book)")
            out[i] = [x - 1 for x in r]
            pinned.append(i)
        elif n <= HEAD_SMALL:
            groups.setdefault(n, []).append(i)
        else:
            if n > K:
                raise LayoutError(f"contests.json: {c.get('name')!r} has {n} entries but the layout holds {K} mean rows")
            multi.setdefault(n, []).append(i)
    for n, members in multi.items():                        # the g-th of G equal-size contests is offset by (g + 0.5) / G of a step
        G = len(members)
        for g, i in enumerate(members):
            out[i] = [int((j + (g + 0.5) / G) * K / n) for j in range(n)]
    for n, members in groups.items():                       # G contests of n entries: G*n spread ranks, dealt in blocks of n
        total = n * len(members)
        if total > K:
            raise LayoutError(f"contests.json: {len(members)} contests of {n} entries need {total} distinct rows; the layout holds {K}")
        spots = [int((j + 0.5) * K / total) for j in range(total)]
        for g, i in enumerate(members):
            out[i] = spots[g * n:(g + 1) * n]
    for i, r in enumerate(out):
        if len(set(r)) != len(r):
            raise LayoutError(f"contests.json: {contests[i].get('name')!r} would repeat a row under the spread layout")
    return out


def rank_summary(contests: list[dict], layout: str) -> list[str]:
    """One line per contest (preflight print): its entries and the 1-based ranks it takes."""
    return [f"{c.get('name')} [{c.get('contest_id')}] x{int(c['entries'])}: ranks {_ranges(r)}"
            for c, r in zip(contests, assign_ranks(contests, layout))]


def protected_ranks(contests: list[dict], layout: str) -> int:
    """How many leading ranks must hold clean (unflagged) rows: the head, plus under `head` every rank an all-head
    contest takes (its whole entry list is shared or single, with no second lineup to cover a late scratch)."""
    if layout not in TWO_TRACK:
        return HEAD_TOP
    ranks = assign_ranks(contests, layout)
    small = [max(r) + 1 for c, r in zip(contests, ranks)
             if int(c["entries"]) <= HEAD_SMALL and r and str(c.get("track", "mean")) == "mean"]
    return max([HEAD_TOP] + small)


def rows_needed(contests: list[dict], layout: str) -> int:
    """Distinct book rows the layout reads (the book must hold at least this many)."""
    ranks = assign_ranks(contests, layout)
    return max((max(r) + 1 for r in ranks if r), default=0)


def _read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(open(path, newline="")))
    if not rows:
        raise LayoutError(f"{path} is empty")
    return rows[0], rows[1:]


def fewest_low_order(book_rows: list[list[str]], low_ids: set[str], flagged: set[int], pin_first: bool,
                     protect: int = HEAD_TOP, fixed_tail: int = 0) -> list[int]:
    """Row order by (LOW count, book rank), a promoted row 1 first; the first `protect` ranks take clean rows only,
    and the flagged rows they skip keep their fewest-LOW place right after them. The last `fixed_tail` rows (the
    tail-track sleeve) are never moved."""
    n_all = len(book_rows)
    if not 0 <= fixed_tail <= n_all:
        raise LayoutError(f"fixed_tail {fixed_tail} outside 0..{n_all}")
    if fixed_tail:
        head_perm = fewest_low_order(book_rows[:n_all - fixed_tail], low_ids, flagged, pin_first, protect=protect)
        return head_perm + list(range(n_all - fixed_tail, n_all))
    def key(i: int):
        return (0 if (pin_first and i == 0) else 1, sum(1 for pid in book_rows[i] if pid in low_ids), i)
    ordered = sorted(range(len(book_rows)), key=key)
    head: list[int] = []
    for i in ordered:
        if len(head) >= protect:
            break
        if i not in flagged or (pin_first and i == 0):
            head.append(i)
    taken = set(head)
    return head + [i for i in ordered if i not in taken]


def _injury_flagged(flags: dict | None) -> bool:
    return any(str(t).split(":", 1)[0] in INJURY_TAGS for tags in (flags or {}).values() for t in tags)


def flagged_positions(vetting: Path, n_rows: int) -> set[int]:
    """0-based book positions holding a player with an injury flag (INJURY_TAGS); they stay behind every clean row.

    vetting_final.json (the replacement's final vetting, and the promoted book's) lists flags by book position;
    vetting.json (the plain vetter, when no replacement ran) lists them by source rank, mapped to book position
    through order_source_ranks. Both are read with the SAME tag rule."""
    v = json.loads(Path(vetting).read_text())
    lineups = v.get("lineups")
    if not isinstance(lineups, list) or not lineups:
        raise LayoutError(f"vetting file {vetting} holds no lineups")
    if "position" in lineups[0]:
        if len(lineups) != n_rows:
            raise LayoutError(f"vetting file {vetting} describes {len(lineups)} rows, the book has {n_rows}")
        return {int(x["position"]) - 1 for x in lineups if _injury_flagged(x.get("flags"))}
    order = v.get("order_source_ranks")
    if not isinstance(order, list) or len(order) != n_rows:
        raise LayoutError(f"vetting file {vetting} has no order_source_ranks for the {n_rows}-row book")
    by_rank = {int(x["rank"]): x for x in lineups}
    out = set()
    for pos, src in enumerate(order):
        lu = by_rank.get(int(src))
        if lu is None:
            raise LayoutError(f"vetting file {vetting}: source rank {src} has no lineup record")
        if _injury_flagged(lu.get("flags")):
            out.add(pos)
    return out


LIVE_FLAG_STATUSES = {"Q", "D", "O", "OUT", "IR", "QUESTIONABLE", "DOUBTFUL", "PUP", "NFI", "SUS"}
QB_NOTE_TAGS = ("qb", "backup_qb")


def live_flagged_positions(vetting: Path, n_rows: int, book_rows: list[list[str]], live_status: Path) -> set[int]:
    """Refinement 1 (operator, 2026-09-24; run after the Sunday inactives): a row is flagged when any player's CURRENT
    DraftKings status is Q/D/O/IR, or the vetting gave it a QB-availability note (DK does not carry those). The Friday
    injury-report tag is not used: DK drops Q when a player is declared active, the report never clears.
    `live_status` is a CSV snapshot (id = dk_player_id, status) taken at run time, kept for the audit trail."""
    v = json.loads(Path(vetting).read_text())
    lineups = v.get("lineups")
    if not isinstance(lineups, list) or not lineups or "position" not in lineups[0] or len(lineups) != n_rows:
        raise LayoutError(f"the live flag rule needs the final vetting by position for the {n_rows}-row book")
    with open(live_status, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or not {"id", "status"} <= set(rows[0]):
        raise LayoutError(f"live status snapshot {live_status} lacks id/status")
    status = {str(r["id"]): str(r.get("status") or "").upper() for r in rows}
    missing = {p for row in book_rows for p in row} - set(status)
    if missing:
        raise LayoutError(f"the live status snapshot lacks {len(missing)} of the book's players (wrong draft group?)")
    # T-70 rule (iii) (operator 2026-09-28, review §5.2): with ENTER_FLAG_LATE_Q_ONLY=1 a Questionable player is a flag
    # only if his game starts after the lock -- an early-game Questionable still listed at the T-70 pull is active (his
    # inactives are public). Needs `game_start` in the snapshot and LOCK_UTC in the environment; fails closed otherwise.
    late_only = os.environ.get("ENTER_FLAG_LATE_Q_ONLY", "0") == "1"
    q_only = {"Q", "QUESTIONABLE"}
    if late_only:
        lock_raw = os.environ.get("LOCK_UTC", "")
        if not lock_raw or "game_start" not in rows[0]:
            raise LayoutError("ENTER_FLAG_LATE_Q_ONLY=1 needs LOCK_UTC and a live snapshot with game_start")
        from datetime import datetime, timezone
        lock = datetime.fromisoformat(lock_raw.replace("Z", "+00:00"))
        if lock.tzinfo is None:
            lock = lock.replace(tzinfo=timezone.utc)
        start = {}
        for r in rows:
            g = str(r.get("game_start") or "").replace("Z", "+00:00")
            if g:
                try:
                    t = datetime.fromisoformat(g[:26] + g[26:] if "." not in g else g.split(".")[0] + "+00:00")
                except ValueError:
                    t = None
                start[str(r["id"])] = t.replace(tzinfo=timezone.utc) if t is not None and t.tzinfo is None else t
        def is_flag(p: str) -> bool:
            st = status[p]
            if st in q_only:
                t = start.get(p)
                return t is None or t > lock
            return st in LIVE_FLAG_STATUSES
    else:
        def is_flag(p: str) -> bool:
            return status[p] in LIVE_FLAG_STATUSES
    qb = {int(x["position"]) - 1 for x in lineups
          if any(str(t).split(":", 1)[0] in QB_NOTE_TAGS for tags in (x.get("flags") or {}).values() for t in tags)}
    return qb | {i for i, row in enumerate(book_rows) if any(is_flag(p) for p in row)}


def check_aligned(book_rows: list[list[str]], upload_rows: list[list[str]]) -> None:
    """The book (dk_player_id) and the upload (draftable ids) must be the same lineups in the same order: every
    player id maps to exactly one draftable id and back, slot for slot. A shifted or foreign upload breaks that."""
    if len(book_rows) != len(upload_rows):
        raise LayoutError(f"book has {len(book_rows)} rows, upload has {len(upload_rows)}")
    fwd: dict[str, str] = {}
    back: dict[str, str] = {}
    for r, (b, u) in enumerate(zip(book_rows, upload_rows)):
        if len(b) != len(u):
            raise LayoutError(f"row {r + 1}: book and upload hold different slot counts")
        for pid, did in zip(b, u):
            if fwd.setdefault(pid, did) != did or back.setdefault(did, pid) != pid:
                raise LayoutError(f"row {r + 1}: book and upload disagree (player {pid} / draftable {did}); "
                                  "they are not the same book in the same order")


def load_order(order: str, n_rows: int, *, book: Path | None, vetting: Path | None, sets: Path | None,
               pin_first: bool, upload_rows: list[list[str]] | None = None,
               protect: int = HEAD_TOP, live_status: Path | None = None, fixed_tail: int = 0) -> tuple[list[int], dict]:
    """The order over upload rows, and a record of how it was made. Fails closed on any missing input."""
    if order not in ORDERS:
        raise LayoutError(f"unknown ENTER_ORDER {order!r}; expected one of {ORDERS}")
    if order == "greedy":
        return list(range(n_rows)), {"order": "greedy"}
    for name, p in (("--book", book), ("--vetting", vetting), ("--sets", sets)):
        if p is None or not Path(p).is_file():
            raise LayoutError(f"ENTER_ORDER=fewest-low needs {name} (got {p!r}); set ENTER_ORDER=greedy to enter in "
                              "the book's own order")
    _, brows = _read_rows(Path(book))
    if len(brows) != n_rows:
        raise LayoutError(f"book {book} has {len(brows)} rows but the upload has {n_rows}; they must be the same book")
    if upload_rows is not None:
        check_aligned(brows, upload_rows)
    _, _brows = _read_rows(Path(book))
    flagged = (live_flagged_positions(Path(vetting), n_rows, _brows, Path(live_status)) if live_status
               else flagged_positions(Path(vetting), n_rows))
    with open(sets, newline="") as f:
        srows = list(csv.DictReader(f))
    if not srows or not {"dk_player_id", "set", "pos"} <= set(srows[0]):
        raise LayoutError(f"sets file {sets} lacks dk_player_id / set / pos")
    known = {str(r["dk_player_id"]) for r in srows}
    low_ids = {str(r["dk_player_id"]) for r in srows if r["set"] == "LOW"}
    skill_known = {str(r["dk_player_id"]) for r in srows if r["pos"] in ("QB", "RB", "WR", "TE")}
    book_ids = {pid for row in brows for pid in row[:8]}            # the eight skill/flex slots; DST is never LOW
    coverage = len(book_ids & known) / max(len(book_ids), 1)
    if coverage < MIN_SETS_COVERAGE:
        raise LayoutError(f"the sets file knows only {coverage:.0%} of the book's players (need "
                          f"{MIN_SETS_COVERAGE:.0%}): wrong week, wrong slate or wrong id form")
    n_mean = n_rows - fixed_tail
    clean = n_mean - len({i for i in flagged if i < n_mean} - ({0} if pin_first else set()))
    if clean < min(protect, n_mean):
        raise LayoutError(f"only {clean} clean rows for {protect} protected ranks; widen the book or relax the layout")
    perm = fewest_low_order(brows, low_ids, flagged, pin_first, protect=protect, fixed_tail=fixed_tail)
    counts = [sum(1 for pid in brows[i] if pid in low_ids) for i in range(n_rows)]
    return perm, {"order": "fewest-low", "sets": str(sets), "book": str(book), "vetting": str(vetting),
                  "pin_first": pin_first, "flagged_rows": len(flagged), "protected_ranks": protect, "fixed_tail": fixed_tail,
                  "flag_rule": f"live DK status ({live_status})" if live_status else "vetting tags (INJURY_TAGS)", "sets_coverage": round(coverage, 4),
                  "low_players": len(low_ids), "skill_players_known": len(skill_known),
                  "low_count_first_10": [counts[i] for i in perm[:10]]}


def parse_max_shared(value: str | int | None) -> int | None:
    """ENTER_SMALL_MAX_SHARED: unset/empty = off; otherwise an integer 0..8 (players two rows may share)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        m = int(str(value).strip())
    except ValueError:
        raise LayoutError(f"{SMALL_OVERLAP_ENV}={value!r} must be an integer 0..8 (players two rows may share) or unset") from None
    if not 0 <= m <= 8:
        raise LayoutError(f"{SMALL_OVERLAP_ENV}={m} must be 0..8 (players two rows may share) or unset")
    return m


def overlap_ceiling(value: str | int | None = None) -> int:
    """The largest contest (entries) the overlap limit governs: ENTER_SMALL_OVERLAP_MAX_ENTRIES, default 5; 2..20."""
    v = os.environ.get(SMALL_OVERLAP_CEILING_ENV) if value is None else value
    if v is None or (isinstance(v, str) and not v.strip()):
        return SMALL_OVERLAP_MAX_ENTRIES
    try:
        n = int(str(v).strip())
    except ValueError:
        raise LayoutError(f"{SMALL_OVERLAP_CEILING_ENV}={v!r} must be an integer 2..20 or unset") from None
    if not 2 <= n <= 20:
        raise LayoutError(f"{SMALL_OVERLAP_CEILING_ENV}={n} must be 2..20 or unset")
    return n


def row_players(hdr: list[str], row: list[str]) -> frozenset:
    """The player cells of one upload row (the QB/RB/WR/TE/FLEX/DST columns)."""
    cols = [j for j, h in enumerate(hdr) if str(h).strip().upper() in PLAYER_SLOTS]
    if len(cols) != 9:
        raise LayoutError(f"upload header has {len(cols)} player columns (expected 9): {hdr!r}")
    return frozenset(str(row[j]).strip() for j in cols)


def _deal_small(first_ranks: list[int], rank_players: list[frozenset], K: int, m: int):
    """One contest at limit m: (chosen ranks, rank changes), or (None, None) when some entry has no fitting mean row."""
    chosen = [first_ranks[0]]
    changes = []

    def fits(q: int) -> bool:
        return q not in chosen and all(len(rank_players[q] & rank_players[x]) <= m for x in chosen)

    for r in first_ranks[1:]:
        if fits(r):
            chosen.append(r)
            continue
        for step in range(1, K):
            q = (r + step) % K
            if fits(q):
                chosen.append(q)
                changes.append({"from_rank": r, "to_rank": q})
                break
        else:
            return None, None
    return chosen, changes


def limit_small_overlap(contests: list[dict], ranks: list[list[int]], rank_players: list[frozenset],
                        max_shared: int) -> tuple[list[list[int]], list[dict]]:
    """The small-contest overlap limit over layout RANKS. For each mean-track contest of 2..overlap_ceiling() entries
    without an explicit pin: its first rank is kept; each later rank is kept if that row shares <= M players with every
    row already chosen for the contest, otherwise it is replaced by the first rank after it in solve order (wrapping
    within the mean ranks 0..K-1) that does and is not already chosen. Rows may repeat across contests, as under head.
    Other contests are untouched.
    NEVER REFUSES for want of a fitting row (operator 2026-09-30: a loud fallback, not a blocked upload): that contest
    is re-dealt at M + 1, ..., 7, and if nothing fits even at 7 it keeps its head rows. Deterministic (check recomputes
    the same result). rank_players[r] = the player set of the row at rank r. Returns (ranks, changes): rank swaps are
    {"contest", "label", "from_rank", "to_rank"}; every relaxation is {"contest", "label", "relaxed_from", "relaxed_to"}
    with relaxed_to an int M or "head"."""
    if not isinstance(max_shared, int) or isinstance(max_shared, bool) or not 0 <= max_shared <= 8:
        raise LayoutError(f"max_shared must be an integer 0..8 (got {max_shared!r})")
    ceiling = overlap_ceiling()
    mean = [str(c.get("track", "mean")) == "mean" for c in contests]
    K = max((max(r) + 1 for r, m in zip(ranks, mean) if m and r), default=0)
    if len(rank_players) < K:
        raise LayoutError(f"the overlap limit needs the players of all {K} mean ranks; got {len(rank_players)}")
    out = [list(r) for r in ranks]
    changes: list[dict] = []
    for i, c in enumerate(contests):
        n = len(ranks[i])
        if not mean[i] or "ranks" in c or not 2 <= n <= ceiling:
            continue
        tag = {"contest": c.get("name"), "label": label(c)}
        for m in range(max_shared, 8):
            got, ch = _deal_small(ranks[i], rank_players, K, m)
            if got is not None:
                out[i] = got
                changes.extend({**tag, **x} for x in ch)
                if m != max_shared:
                    changes.append({**tag, "relaxed_from": max_shared, "relaxed_to": m})
                break
        else:
            changes.append({**tag, "relaxed_from": max_shared, "relaxed_to": "head"})   # out[i] keeps the head ranks
    return out, changes


def small_overlap_record(contests: list[dict], max_shared: int, changes: list[dict]) -> dict:
    """{contest label: the M it was dealt at (an int) or "head"} for every contest the limit governs."""
    rec = {}
    relaxed = {x["label"]: x["relaxed_to"] for x in changes if "relaxed_to" in x}
    for c in contests:
        if str(c.get("track", "mean")) == "mean" and "ranks" not in c and 2 <= int(c.get("entries", 0)) <= overlap_ceiling():
            rec[label(c)] = relaxed.get(label(c), max_shared)
    return rec


def relaxation_banners(changes: list[dict]) -> list[str]:
    return [f"!!! SMALL-CONTEST OVERLAP LIMIT RELAXED for {x['label']}: M={x['relaxed_from']} -> "
            f"{'head rows' if x['relaxed_to'] == 'head' else x['relaxed_to']}" for x in changes if "relaxed_to" in x]


def final_ranks(contests: list[dict], layout: str, rank_players: list[frozenset] | None = None,
                max_shared: int | None = None) -> tuple[list[list[int]], list[dict]]:
    """assign_ranks, then the small-contest overlap limit when max_shared is set."""
    ranks = assign_ranks(contests, layout)
    if max_shared is None:
        return ranks, []
    if rank_players is None:
        raise LayoutError(f"{SMALL_OVERLAP_ENV} is set but the book rows' players were not supplied")
    return limit_small_overlap(contests, ranks, rank_players, max_shared)


def contest_rows(contests: list[dict], n_rows: int, layout: str, perm: list[int],
                 rank_players: list[frozenset] | None = None, max_shared: int | None = None) -> list[list[int]]:
    """Per contest, the UPLOAD row indices its entries take (ranks mapped through the order; with max_shared set, after
    the small-contest overlap limit -- rank_players[r] is the player set of upload row perm[r])."""
    ranks, _ = final_ranks(contests, layout, rank_players, max_shared)
    need = max((max(r) + 1 for r in ranks if r), default=0)
    if need > n_rows:
        raise LayoutError(f"the {layout} layout needs {need} distinct lineups but the book holds {n_rows}")
    # Two tracks: the sleeve starts right after the mean rows the layout counted, so the book must hold EXACTLY
    # mean rows + sleeve rows; a longer book would put the sleeve on mean-track lineups without anyone noticing.
    t = sleeve_size(contests, layout)
    if t and n_rows != need:
        raise LayoutError(f"two-track book must hold exactly {need} rows ({need - t} mean rows, floored at {MEAN_ROWS_FLOOR}, "
                          f"+ {t} sleeve); it holds {n_rows}")
    return [[perm[r] for r in rs] for rs in ranks]


def contest_rows_from_book(contests: list[dict], book_rows: list[list[str]], layout: str, perm: list[int],
                           max_shared: int | None = None) -> list[list[int]]:
    """contest_rows for a book given as rows of nine player cells (no header): the exposure sheet's view of the same
    dealing the ENTER bundle publishes, the small-contest overlap limit included when max_shared is set (the book's player
    ids and the upload's draftable ids are one-to-one within a slate, so the overlaps and the decisions are the same)."""
    rp = [frozenset(str(x).strip() for x in book_rows[i]) for i in perm] if max_shared is not None else None
    return contest_rows(contests, len(book_rows), layout, perm, rp, max_shared)


def frozen_contest_rows(contests: list[dict], bundle: Path, new_rows: list[list[str]],
                        receipt: Path | None = None) -> tuple[list[list[int]], dict]:
    """Swap re-publication (laptop review 2026-09-24, HIGH): a swap changes CELLS, never which book row a contest holds.

    The published bundle records its own upload (ENTER-all-rows-*-KEEPERS.csv, copied at publication); every contest's
    rows are located in it, and the new bundle takes the SAME row indices from the swapped upload. Nothing is re-ordered,
    so no lineup moves between contests (after a lock DraftKings cannot re-assign an entry). The swapped upload may differ
    from the bundle's only in the cells a swap receipt names (apply_swaps.py's <OUT_CSV>.swap.json) -- or, without a
    receipt, in at most one cell per changed row."""
    base_files = sorted(Path(bundle).glob("ENTER-all-rows-*-KEEPERS.csv"))
    if len(base_files) != 1:
        raise LayoutError(f"{bundle} holds {len(base_files)} ENTER-all-rows-*-KEEPERS.csv files; expected exactly one")
    base = _read_rows(base_files[0])[1]
    if len(base) != len(new_rows):
        raise LayoutError(f"the swapped upload has {len(new_rows)} rows, the published bundle's upload {len(base)}")
    rowmap_file = Path(bundle) / ROWMAP_NAME
    rowmap = json.loads(rowmap_file.read_text()) if rowmap_file.is_file() else None
    index: dict[tuple, int] = {}
    if rowmap is None:                                   # a bundle published before the row map: the reverse lookup
        for i, r in enumerate(base):
            if tuple(r) in index:
                raise LayoutError(f"the published upload repeats a lineup (rows {index[tuple(r)] + 1} and {i + 1}); "
                                  "this bundle has no row map, so its contests cannot be re-published")
            index[tuple(r)] = i
    per = []
    for c in contests:
        f = Path(bundle) / enter_filename(c)
        if not f.is_file():
            raise LayoutError(f"the published bundle lacks {f.name}")
        rows = _read_rows(f)[1]
        if rowmap is not None:
            got = rowmap.get(label(c))
            if not isinstance(got, list) or len(got) != len(rows) or any(not isinstance(i, int) or not 0 <= i < len(base) for i in got):
                raise LayoutError(f"the bundle's row map does not cover {label(c)} ({len(rows)} rows)")
            if any(base[i] != r for i, r in zip(got, rows)):
                raise LayoutError(f"{f.name} does not match the row map's rows of the bundle's own upload")
            per.append(list(got))
        else:
            try:
                per.append([index[tuple(r)] for r in rows])
            except KeyError:
                raise LayoutError(f"{f.name} holds a lineup that is not in the bundle's own upload") from None
        if len(rows) != int(c["entries"]):
            raise LayoutError(f"{f.name} holds {len(rows)} entries, contests.json says {c['entries']}")
    changed = {(i, j) for i, (a, b) in enumerate(zip(base, new_rows)) for j, (x, y) in enumerate(zip(a, b)) if x != y}
    if any(len(a) != len(b) for a, b in zip(base, new_rows)):
        raise LayoutError("the swapped upload changes a row's slot count")
    if receipt is not None and Path(receipt).is_file():
        rec = json.loads(Path(receipt).read_text())
        allowed = set()
        for sw in rec.get("swaps", []):                  # apply_swaps.py v1.1: row (1-based), slot_index, out.dd
            row, j = int(sw["row"]) - 1, int(sw["slot_index"])
            if base[row][j] != str(sw["out"]["dd"]):
                raise LayoutError(f"swap receipt row {row + 1} slot {j}: the published upload does not hold {sw['out']['dd']} there")
            allowed.add((row, j))
        if not changed <= allowed:
            raise LayoutError(f"the swapped upload changes cells the swap receipt does not name: {sorted(changed - allowed)[:5]}")
    else:
        per_row: dict[int, int] = {}
        for i, _ in changed:
            per_row[i] = per_row.get(i, 0) + 1
        if any(v > 1 for v in per_row.values()):
            raise LayoutError("without a swap receipt, a row may change in at most one cell")
    return per, {"order": "frozen (swap re-publication)", "bundle": str(bundle), "changed_cells": len(changed),
                 "rows_changed": sorted({i + 1 for i, _ in changed}), "receipt": str(receipt) if receipt else None}


def label(c: dict) -> str:
    return f"{c['name']}-{c['contest_id']}"


def enter_filename(c: dict) -> str:
    return f"ENTER-{label(c)}-{int(c['entries'])}-entries-KEEP-first-{int(c['keep'])}.csv"


def _ranges(xs: list[int]) -> str:
    xs = [x + 1 for x in xs]
    if not xs:
        return "-"
    out, a, b = [], xs[0], xs[0]
    for x in xs[1:]:
        if x == b + 1:
            b = x
        else:
            out.append(f"{a}" if a == b else f"{a}-{b}"); a = b = x
    out.append(f"{a}" if a == b else f"{a}-{b}")
    return ",".join(out)


def _rank_players(hdr: list[str], body: list[list[str]], perm: list[int]) -> list[frozenset]:
    return [row_players(hdr, body[i]) for i in perm]


def write(contests: list[dict], upload: Path, stage: Path, layout: str, perm_info: tuple[list[int], dict],
          frozen: list[list[int]] | None = None, max_shared: int | None = None) -> list[str]:
    hdr, body = _read_rows(upload)
    perm, info = perm_info
    rp = _rank_players(hdr, body, perm) if max_shared is not None and frozen is None else None
    per = frozen if frozen is not None else contest_rows(contests, len(body), layout, perm, rp, max_shared)
    stage.mkdir(parents=True, exist_ok=True)
    lines = [f"layout {layout}; order {info['order']}; {sum(len(r) for r in per)} entries from "
             f"{len(set(x for r in per for x in r))} distinct book rows of {len(body)}"]
    if info["order"] != "greedy":
        lines.append("order record: " + json.dumps(info, sort_keys=True))
    if frozen is None:
        ranks, changes = final_ranks(contests, layout, rp, max_shared)
        if max_shared is not None:
            swaps = [x for x in changes if "from_rank" in x]
            lines.append(f"{SMALL_OVERLAP_ENV}={max_shared}: {len(swaps)} small-contest rank(s) replaced"
                         + (": " + "; ".join(f"{x['contest']} {x['from_rank'] + 1}->{x['to_rank'] + 1}" for x in swaps) if swaps else ""))
            for banner in relaxation_banners(changes):
                lines.append(banner)
                print(banner, file=sys.stderr)
            lines.append("small_overlap: " + json.dumps(small_overlap_record(contests, max_shared, changes), sort_keys=True))
    else:
        ranks = [[] for _ in contests]
    for c, rows, rk in zip(contests, per, ranks):
        with open(stage / enter_filename(c), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            w.writerows(body[i] for i in rows)
        lines.append(f"{label(c)}: {len(rows)} entries = ranks {_ranges(rk) if rk else 'frozen'} (book rows {_ranges(sorted(rows))}; "
                     f"keep {int(c['keep'])}) -> {enter_filename(c)}")
    # The row map (2026-09-29): which 0-based rows of the bundle's own upload each contest holds. A swap re-publication
    # reads it instead of reverse-looking rows up by roster, which breaks once the sleeve repeats a mean row.
    (stage / ROWMAP_NAME).write_text(json.dumps({label(c): list(rows) for c, rows in zip(contests, per)}, indent=1) + "\n")
    return lines


def check(contests: list[dict], upload: Path, stage: Path, layout: str, perm_info: tuple[list[int], dict],
          frozen: list[list[int]] | None = None, max_shared: int | None = None) -> list[str]:
    hdr, body = _read_rows(upload)
    rp = _rank_players(hdr, body, perm_info[0]) if max_shared is not None and frozen is None else None
    per = frozen if frozen is not None else contest_rows(contests, len(body), layout, perm_info[0], rp, max_shared)
    bad = []
    for c, rows in zip(contests, per):
        f = stage / enter_filename(c)
        if not f.is_file():
            bad.append(f"MISSING {f.name}")
            continue
        got = _read_rows(f)[1]
        if got != [body[i] for i in rows]:
            bad.append(f"MISMATCH {label(c)}: staged rows != layout-mapped upload rows ({layout}, {perm_info[1]['order']})")
    return bad


def _contests(path: Path) -> list[dict]:
    c = json.loads(Path(path).read_text())
    c = c if isinstance(c, list) else c.get("contests")
    if not isinstance(c, list) or not c:
        raise LayoutError("contests.json must be a non-empty list")
    return c


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["write", "check", "rows-needed"])
    ap.add_argument("contests", type=Path)
    ap.add_argument("upload", type=Path, nargs="?")
    ap.add_argument("stage", type=Path, nargs="?")
    ap.add_argument("--layout", default=os.environ.get("ENTER_LAYOUT") or "sequential")
    ap.add_argument("--order", default=os.environ.get("ENTER_ORDER") or "greedy")
    ap.add_argument("--book", type=Path)
    ap.add_argument("--vetting", type=Path)
    ap.add_argument("--sets", type=Path, default=Path(os.environ["OWNERSHIP_SETS"]) if os.environ.get("OWNERSHIP_SETS") else None)
    ap.add_argument("--pin-first", action="store_true")
    ap.add_argument("--frozen-bundle", type=Path,
                    default=Path(os.environ["ENTER_FROZEN_BUNDLE"]) if os.environ.get("ENTER_FROZEN_BUNDLE") else None,
                    help="swap re-publication: keep this published bundle's row->contest map, change cells only")
    ap.add_argument("--swap-receipt", type=Path, default=None, help="apply_swaps.py receipt (default: UPLOAD.swap.json)")
    ap.add_argument("--live-status", type=Path,
                    default=Path(os.environ["ENTER_LIVE_STATUS"]) if os.environ.get("ENTER_LIVE_STATUS") else None,
                    help="refinement 1: a DK status snapshot (id,status); flags come from it instead of the report")
    ap.add_argument("--small-max-shared", default=os.environ.get(SMALL_OVERLAP_ENV),
                    help="the small-contest overlap limit (players two rows of one 2-5-entry contest may share); unset = off")
    a = ap.parse_args(argv)
    max_shared = parse_max_shared(a.small_max_shared)
    overlap_ceiling()                                # validated up front: a bad value refuses before anything is written
    contests = _contests(a.contests)
    if a.cmd == "rows-needed":
        print(rows_needed(contests, a.layout))
        return 0
    if a.upload is None or a.stage is None:
        raise LayoutError(f"{a.cmd} needs UPLOAD_CSV and STAGE_DIR")
    body = _read_rows(a.upload)[1]
    if a.frozen_bundle is not None:
        receipt = a.swap_receipt or Path(str(a.upload) + ".swap.json")
        frozen, info = frozen_contest_rows(contests, a.frozen_bundle, body, receipt if receipt.is_file() else None)
        fz = (list(range(len(body))), info)
        if a.cmd == "write":
            print("\n".join(write(contests, a.upload, a.stage, a.layout, fz, frozen=frozen)))
            return 0
        bad = check(contests, a.upload, a.stage, a.layout, fz, frozen=frozen)
        for b in bad:
            print(b)
        print("staged bundle == the published bundle's row map with the swapped cells:", not bad)
        return 1 if bad else 0
    perm_info = load_order(a.order, len(body), book=a.book, vetting=a.vetting, sets=a.sets, pin_first=a.pin_first,
                           upload_rows=body, protect=protected_ranks(contests, a.layout), live_status=a.live_status,
                           fixed_tail=sleeve_size(contests, a.layout))
    if a.cmd == "write":
        print("\n".join(write(contests, a.upload, a.stage, a.layout, perm_info, max_shared=max_shared)))
        return 0
    bad = check(contests, a.upload, a.stage, a.layout, perm_info, max_shared=max_shared)
    for b in bad:
        print(b)
    print(f"staged bundle == upload rows under the {a.layout} layout and {perm_info[1]['order']} order:", not bad)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LayoutError as exc:
        print(f"enter_layout: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
