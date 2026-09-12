"""Week tail ledger v1: the per-week, post-settlement tail record.

The 2026-09-12 state audit (§5.1) asks for one row per slate, written after
settlement: for every published book and every candidate pool, the realized
maximum, how many lineups cleared each tail threshold, where the pool's best
lineup sits in the book, and the margin to the contest winning score when it
is known.  With ~17 slates a season no arm reaches significance at 220, so
the row reports 200+/210+ supply and the pool oracle as the honest KPIs and
counts 220+/230+ without gating on them.

A row is an observation.  It uses the target week's outcomes by construction
and therefore licenses nothing: no adoption, no allocation change, no
promotion.  Rosters are scored by exact internal player id (gsis id, or
``<TEAM>_DST``) and the scorer fails closed on any id without an actual.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Final

SCHEMA_VERSION: Final = "week-tail-ledger-row/v1"
THRESHOLDS_DK: Final = (194, 200, 210, 220, 230, 240)
ROSTER_SIZE: Final = 9
_BOOK_ENTRY_FIELDS: Final = frozenset({
    "lineup_id", "lineup_rank", "internal_player_ids",
})
_FALSE_AUTHORITY_FIELDS: Final = (
    "adoption_authority",
    "allocation_change_licensed",
    "promotion_authority",
    "selector_tuning_licensed",
)
_ROW_FIELDS: Final = frozenset({
    "schema_version", "season", "week", "slate_id", "lock_utc", "captured_at",
    "thresholds_dk", "uses_target_week_outcomes", "actual_count",
    "input_identities", "pools", "books", "winner", "row_sha256",
    *_FALSE_AUTHORITY_FIELDS,
})


class WeekTailLedgerError(ValueError):
    """The ledger inputs or a ledger row are not what the contract requires."""


def _fail(message: str) -> None:
    raise WeekTailLedgerError(message)


def canonical_sha256(value: object) -> str:
    """SHA-256 of the canonical JSON form (sorted keys, no NaN, no spaces)."""
    try:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WeekTailLedgerError(f"value is not finite canonical JSON: {exc}")
    return sha256(raw).hexdigest()


def _timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{label} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        _fail(f"{label} is not ISO-8601: {value!r}")
    if parsed.tzinfo is None:
        _fail(f"{label} must carry a timezone")
    return parsed.astimezone(timezone.utc)


def roster_key(internal_ids: object) -> tuple[str, ...]:
    """Sorted tuple of exactly nine distinct non-empty internal ids."""
    if isinstance(internal_ids, (str, bytes)) or not isinstance(
        internal_ids, Sequence
    ):
        _fail("roster must be a sequence of internal player ids")
    ids = [str(item).strip() for item in internal_ids]
    if len(ids) != ROSTER_SIZE or any(not item for item in ids):
        _fail(f"roster must hold exactly {ROSTER_SIZE} non-empty ids")
    if len(set(ids)) != ROSTER_SIZE:
        _fail("roster repeats a player id")
    return tuple(sorted(ids))


def roster_sha256(internal_ids: object) -> str:
    return sha256(",".join(roster_key(internal_ids)).encode("utf-8")).hexdigest()


def score_roster(
    internal_ids: object, actual_by_internal_id: Mapping[str, object]
) -> float:
    """Sum realized DK points over the roster; fail closed on any gap."""
    total = 0.0
    for item in roster_key(internal_ids):
        if item not in actual_by_internal_id:
            _fail(f"no realized actual for internal id {item!r}")
        value = actual_by_internal_id[item]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(f"realized actual for {item!r} is not numeric")
        if not math.isfinite(float(value)):
            _fail(f"realized actual for {item!r} is not finite")
        total += float(value)
    return round(total, 4)


def _validated_thresholds(thresholds: object) -> tuple[int, ...]:
    if not isinstance(thresholds, Sequence) or isinstance(thresholds, str):
        _fail("thresholds must be a sequence")
    values = tuple(thresholds)
    if not values or any(
        isinstance(item, bool) or type(item) is not int or item <= 0
        for item in values
    ):
        _fail("thresholds must be positive integers")
    if any(b <= a for a, b in zip(values, values[1:])):
        _fail("thresholds must be strictly increasing")
    return values


def _tail_counts(scores: Sequence[float], thresholds: Sequence[int]) -> dict:
    return {
        f"ge_{threshold}": sum(1 for score in scores if score >= threshold)
        for threshold in thresholds
    }


def _validated_actuals(actual_by_internal_id: object) -> dict[str, float]:
    if not isinstance(actual_by_internal_id, Mapping):
        _fail("actuals must map internal id to realized DK points")
    validated: dict[str, float] = {}
    for key, value in actual_by_internal_id.items():
        if type(key) is not str or not key.strip():
            _fail("actual keys must be non-empty internal id strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(f"realized actual for {key!r} is not numeric")
        if not math.isfinite(float(value)):
            _fail(f"realized actual for {key!r} is not finite")
        validated[key] = float(value)
    if not validated:
        _fail("actuals are empty")
    return validated


def _validated_identities(input_identities: object) -> dict[str, dict]:
    if not isinstance(input_identities, Mapping) or not input_identities:
        _fail("input identities must be a non-empty mapping")
    out: dict[str, dict] = {}
    for label, identity in input_identities.items():
        if type(label) is not str or not label:
            _fail("input identity labels must be non-empty strings")
        if not isinstance(identity, Mapping) or set(identity) != {
            "uri", "generation", "sha256", "bytes",
        }:
            _fail(f"input identity {label!r} must carry uri/generation/sha256/bytes")
        digest = str(identity["sha256"])
        if len(digest) != 64 or set(digest) - set("0123456789abcdef"):
            _fail(f"input identity {label!r} sha256 is not lowercase hex")
        if not str(identity["generation"]).isdigit():
            _fail(f"input identity {label!r} generation is not numeric")
        if type(identity["bytes"]) is not int or identity["bytes"] <= 0:
            _fail(f"input identity {label!r} bytes must be a positive integer")
        out[label] = {
            "uri": str(identity["uri"]),
            "generation": str(identity["generation"]),
            "sha256": digest,
            "bytes": int(identity["bytes"]),
        }
    return out


def _pool_summary(
    pool_id: str,
    rosters: object,
    actuals: Mapping[str, float],
    thresholds: Sequence[int],
) -> tuple[dict, dict[tuple[str, ...], float]]:
    if isinstance(rosters, (str, bytes)) or not isinstance(rosters, Sequence):
        _fail(f"pool {pool_id!r} must be a sequence of rosters")
    if not rosters:
        _fail(f"pool {pool_id!r} is empty")
    scored: dict[tuple[str, ...], float] = {}
    for roster in rosters:
        key = roster_key(roster)
        if key in scored:
            _fail(f"pool {pool_id!r} repeats a roster")
        scored[key] = score_roster(key, actuals)
    scores = sorted(scored.values(), reverse=True)
    best_key = max(scored, key=lambda key: (scored[key], key))
    summary = {
        "pool_id": pool_id,
        "n": len(scores),
        "max": scores[0],
        "max_roster_sha256": roster_sha256(best_key),
        "mean": round(sum(scores) / len(scores), 4),
        "tail_counts": _tail_counts(scores, thresholds),
    }
    return summary, scored


def _book_summary(
    book_id: str,
    entries: object,
    actuals: Mapping[str, float],
    thresholds: Sequence[int],
    pools: Mapping[str, dict[tuple[str, ...], float]],
) -> dict:
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        _fail(f"book {book_id!r} must be a sequence of entries")
    if not entries:
        _fail(f"book {book_id!r} is empty")
    seen_ids: set[str] = set()
    scored: list[tuple[int, str, tuple[str, ...], float]] = []
    for ordinal, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or not _BOOK_ENTRY_FIELDS <= set(entry):
            _fail(f"book {book_id!r} entry[{ordinal}] lacks required fields")
        lineup_id = str(entry["lineup_id"]).strip()
        rank = entry["lineup_rank"]
        if not lineup_id or lineup_id in seen_ids:
            _fail(f"book {book_id!r} lineup ids are empty or repeated")
        if isinstance(rank, bool) or type(rank) is not int:
            _fail(f"book {book_id!r} lineup ranks must be integers")
        seen_ids.add(lineup_id)
        key = roster_key(entry["internal_player_ids"])
        scored.append((rank, lineup_id, key, score_roster(key, actuals)))
    ranks = sorted(rank for rank, _, _, _ in scored)
    if ranks != list(range(1, len(scored) + 1)):
        _fail(f"book {book_id!r} ranks are not exactly 1..n")
    keys = [key for _, _, key, _ in scored]
    if len(set(keys)) != len(keys):
        _fail(f"book {book_id!r} repeats a roster")
    rank_by_key = {key: rank for rank, _, key, _ in scored}
    scores = [score for _, _, _, score in scored]
    best = max(scored, key=lambda row: (row[3], -row[0]))
    against_pools = {}
    for pool_id, pool_scores in pools.items():
        pool_best_key = max(pool_scores, key=lambda key: (pool_scores[key], key))
        pool_max = pool_scores[pool_best_key]
        strictly_better = sum(1 for value in pool_scores.values() if value > best[3])
        against_pools[pool_id] = {
            "pool_max": pool_max,
            "retrieval_gap": round(pool_max - best[3], 4),
            "pool_max_in_book": pool_best_key in rank_by_key,
            "pool_max_book_rank": rank_by_key.get(pool_best_key),
            "book_max_rank_in_pool": strictly_better + 1,
            "book_rosters_in_pool": sum(1 for key in keys if key in pool_scores),
        }
    return {
        "book_id": book_id,
        "n": len(scores),
        "max": best[3],
        "max_lineup_id": best[1],
        "max_lineup_rank": best[0],
        "mean": round(sum(scores) / len(scores), 4),
        "tail_counts": _tail_counts(scores, thresholds),
        "against_pools": against_pools,
    }


def _validated_winner(winner: object) -> dict | None:
    if winner is None:
        return None
    if not isinstance(winner, Mapping) or set(winner) != {
        "score", "source", "contest_id",
    }:
        _fail("winner must carry exactly score/source/contest_id")
    score = winner["score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        _fail("winner score must be numeric")
    if not math.isfinite(float(score)) or float(score) <= 0:
        _fail("winner score must be finite and positive")
    source = str(winner["source"]).strip()
    contest_id = str(winner["contest_id"]).strip()
    if not source or not contest_id:
        _fail("winner source and contest_id must be non-empty")
    return {"score": float(score), "source": source, "contest_id": contest_id}


def build_week_tail_ledger_row_v1(
    *,
    season: int,
    week: int,
    slate_id: str,
    lock_utc: str,
    captured_at: str,
    books: Mapping[str, object],
    pools: Mapping[str, object],
    actual_by_internal_id: Mapping[str, object],
    input_identities: Mapping[str, object],
    winner: Mapping[str, object] | None = None,
    thresholds: Sequence[int] = THRESHOLDS_DK,
) -> dict:
    """Build one self-hashed ledger row from exact inputs; fail closed."""
    if isinstance(season, bool) or type(season) is not int or season < 2026:
        _fail("season must be an integer >= 2026")
    if isinstance(week, bool) or type(week) is not int or not 1 <= week <= 22:
        _fail("week must be an integer in 1..22")
    if not isinstance(slate_id, str) or not slate_id.strip():
        _fail("slate_id must be a non-empty string")
    lock = _timestamp(lock_utc, label="slate lock")
    captured = _timestamp(captured_at, label="captured-at")
    if captured <= lock:
        _fail("captured_at must be after slate lock: the row is post-settlement")
    thresholds = _validated_thresholds(thresholds)
    actuals = _validated_actuals(actual_by_internal_id)
    identities = _validated_identities(input_identities)
    if not isinstance(pools, Mapping) or not pools:
        _fail("at least one candidate pool is required")
    if not isinstance(books, Mapping) or not books:
        _fail("at least one book is required")
    pool_rows: list[dict] = []
    pool_scores: dict[str, dict[tuple[str, ...], float]] = {}
    for pool_id in sorted(pools):
        if type(pool_id) is not str or not pool_id:
            _fail("pool ids must be non-empty strings")
        summary, scored = _pool_summary(pool_id, pools[pool_id], actuals, thresholds)
        pool_rows.append(summary)
        pool_scores[pool_id] = scored
    book_rows = [
        _book_summary(book_id, books[book_id], actuals, thresholds, pool_scores)
        for book_id in sorted(books)
        if type(book_id) is str and book_id or _fail("book ids must be strings")
    ]
    winner_row = _validated_winner(winner)
    if winner_row is not None:
        winner_row["margins"] = {
            "books": {
                row["book_id"]: round(row["max"] - winner_row["score"], 4)
                for row in book_rows
            },
            "pools": {
                row["pool_id"]: round(row["max"] - winner_row["score"], 4)
                for row in pool_rows
            },
        }
        winner_row["beaten_by_any_book"] = any(
            row["max"] >= winner_row["score"] for row in book_rows
        )
        winner_row["beaten_by_any_pool"] = any(
            row["max"] >= winner_row["score"] for row in pool_rows
        )
    body = {
        "schema_version": SCHEMA_VERSION,
        "season": season,
        "week": week,
        "slate_id": slate_id.strip(),
        "lock_utc": lock.isoformat(),
        "captured_at": captured.isoformat(),
        "thresholds_dk": list(thresholds),
        "uses_target_week_outcomes": True,
        "actual_count": len(actuals),
        "input_identities": identities,
        "pools": pool_rows,
        "books": book_rows,
        "winner": winner_row,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return {**body, "row_sha256": canonical_sha256(body)}


def validate_week_tail_ledger_row_v1(row: object) -> dict:
    """Re-derive the self-hash and check the row's internal consistency."""
    if not isinstance(row, Mapping) or set(row) != _ROW_FIELDS:
        _fail("ledger row fields differ from the v1 contract")
    if row["schema_version"] != SCHEMA_VERSION:
        _fail("ledger row schema version differs")
    body = {key: row[key] for key in row if key != "row_sha256"}
    if canonical_sha256(body) != row["row_sha256"]:
        _fail("ledger row self-hash differs")
    if row["uses_target_week_outcomes"] is not True:
        _fail("ledger rows use target-week outcomes by construction")
    if any(row[field] is not False for field in _FALSE_AUTHORITY_FIELDS):
        _fail("ledger row claims an authority it cannot hold")
    thresholds = _validated_thresholds(tuple(row["thresholds_dk"]))
    _validated_identities(row["input_identities"])
    if _timestamp(row["captured_at"], label="captured-at") <= _timestamp(
        row["lock_utc"], label="slate lock"
    ):
        _fail("ledger row captured before lock")
    pool_max = {}
    for kind in ("pools", "books"):
        rows = row[kind]
        if not isinstance(rows, Sequence) or not rows:
            _fail(f"ledger row has no {kind}")
        for item in rows:
            counts = [item["tail_counts"][f"ge_{t}"] for t in thresholds]
            if set(item["tail_counts"]) != {f"ge_{t}" for t in thresholds}:
                _fail(f"{kind} tail counts do not match the thresholds")
            if any(b > a for a, b in zip(counts, counts[1:])):
                _fail(f"{kind} tail counts are not monotone")
            if any(count > item["n"] or count < 0 for count in counts):
                _fail(f"{kind} tail counts exceed n")
            for threshold, count in zip(thresholds, counts):
                if (item["max"] >= threshold) != (count >= 1):
                    _fail(f"{kind} maximum disagrees with its tail counts")
            if kind == "pools":
                pool_max[item["pool_id"]] = item["max"]
    for book in row["books"]:
        for pool_id, against in book["against_pools"].items():
            if pool_id not in pool_max or against["pool_max"] != pool_max[pool_id]:
                _fail("book comparison names a pool the row does not hold")
            if round(against["pool_max"] - book["max"], 4) != against["retrieval_gap"]:
                _fail("book retrieval gap does not re-derive")
            if against["pool_max_in_book"] != (
                against["pool_max_book_rank"] is not None
            ):
                _fail("pool-max-in-book flag disagrees with its rank")
    winner = row["winner"]
    if winner is not None:
        if set(winner) != {
            "score", "source", "contest_id", "margins",
            "beaten_by_any_book", "beaten_by_any_pool",
        }:
            _fail("winner block fields differ")
        for kind, id_field in (("books", "book_id"), ("pools", "pool_id")):
            expected = {
                item[id_field]: round(item["max"] - winner["score"], 4)
                for item in row[kind]
            }
            if winner["margins"][kind] != expected:
                _fail(f"winner margins for {kind} do not re-derive")
        if winner["beaten_by_any_book"] != any(
            item["max"] >= winner["score"] for item in row["books"]
        ) or winner["beaten_by_any_pool"] != any(
            item["max"] >= winner["score"] for item in row["pools"]
        ):
            _fail("winner beaten flags do not re-derive")
    return dict(row)
