"""Checkout- and representation-independent GCS object identity.

2026-08-18 produced four serialized chain failures whose content was
byte-identical while a REPRESENTATION differed: a receipt key spelling,
absolute checkout paths, a validator's own pinned hash, and a timestamp
string format (`+0000` vs `isoformat()`'s `+00:00` with microseconds).
Each cost a full build+launch cycle. This module is the single place new
protocols should get object receipts and compare them, so the class
cannot recur: receipts are produced with one primitive, and equality is
defined on content identity only.

Frozen chains already in flight keep their own pinned code; this helper
is for every protocol written after it (see the frozen-chain lessons in
CLAUDE.md, rule 2).
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

RECEIPT_FIELDS = ("uri", "generation", "sha256", "bytes", "updated")
# The fields that define WHICH object this is. `updated` is retained in
# receipts for human audit but is a representation, not an identity:
# generation already pins the exact GCS object version.
IDENTITY_FIELDS = ("uri", "generation", "sha256", "bytes")


def live_object_receipt(
    client: Any, uri: str, raw: bytes | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Download (unless ``raw`` is supplied) and receipt one GCS object.

    The receipt shape matches the de facto chain standard (the historical
    scorer's `_download_json`): `updated` is always
    ``blob.updated.isoformat()`` so any consumer using this module never
    reintroduces a format mismatch. Returns ``(receipt, raw_bytes)``.
    """
    if not uri.startswith("gs://"):
        raise ValueError(f"not a GCS uri: {uri!r}")
    bucket_name, _, blob_name = uri[5:].partition("/")
    if not blob_name:
        raise ValueError(f"uri lacks an object path: {uri!r}")
    blob = client.bucket(bucket_name).blob(blob_name)
    if raw is None:
        raw = blob.download_as_bytes()
    blob.reload()
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }, raw


def content_identity(receipt: Mapping[str, Any]) -> tuple:
    """The representation-free comparison key for one object receipt."""
    missing = [f for f in IDENTITY_FIELDS if f not in receipt]
    if missing:
        raise ValueError(f"receipt lacks identity fields: {missing}")
    generation = str(receipt["generation"])
    digest = str(receipt["sha256"])
    if not generation.isdigit():
        raise ValueError(f"receipt generation is not numeric: {generation!r}")
    if len(digest) != 64 or set(digest) - set("0123456789abcdef"):
        raise ValueError("receipt sha256 is not a lowercase hex digest")
    return (str(receipt["uri"]), generation, digest, int(receipt["bytes"]))


def same_object(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """Content-identity equality; representations (`updated`, extra keys,
    path spellings inside unrelated fields) can never cause a mismatch."""
    return content_identity(a) == content_identity(b)
