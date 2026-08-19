"""Content-identity receipts: representation differences never mismatch;
content differences always do; malformed receipts fail closed."""
from hashlib import sha256

import pytest

from nfl_dfs.research.object_identity import (
    content_identity,
    live_object_receipt,
    same_object,
)


def _receipt(**overrides):
    base = {
        "uri": "gs://bucket/run/slate-2023-1.json",
        "generation": "1787074515655534",
        "sha256": "a" * 64,
        "bytes": 481335,
        "updated": "2026-08-18T17:35:15+0000",
    }
    base.update(overrides)
    return base


def test_timestamp_format_never_causes_mismatch():
    # The exact failure that killed execution coherent-market-historical-
    # v1-bg74m: same object, different `updated` representation.
    a = _receipt(updated="2026-08-18T17:35:15+0000")
    b = _receipt(updated="2026-08-18T17:35:15.743000+00:00")
    assert same_object(a, b)


def test_extra_and_missing_representation_keys_are_ignored():
    a = _receipt()
    b = _receipt()
    del b["updated"]
    b["season"] = 2023
    assert same_object(a, b)


def test_content_differences_always_mismatch():
    assert not same_object(_receipt(), _receipt(generation="9"))
    assert not same_object(_receipt(), _receipt(sha256="b" * 64))
    assert not same_object(_receipt(), _receipt(bytes=1))
    assert not same_object(
        _receipt(), _receipt(uri="gs://bucket/run/slate-2023-2.json"))


def test_malformed_receipts_fail_closed():
    with pytest.raises(ValueError, match="identity fields"):
        content_identity({"uri": "gs://x/y"})
    with pytest.raises(ValueError, match="not numeric"):
        content_identity(_receipt(generation="17e5"))
    with pytest.raises(ValueError, match="hex digest"):
        content_identity(_receipt(sha256="Z" * 64))


class _FakeUpdated:
    def isoformat(self):
        return "2026-08-18T17:35:15.743000+00:00"


class _FakeBlob:
    def __init__(self, raw):
        self._raw = raw
        self.generation = 1787074515655534
        self.updated = _FakeUpdated()

    def download_as_bytes(self):
        return self._raw

    def reload(self):
        pass


class _FakeBucket:
    def __init__(self, raw):
        self._raw = raw

    def blob(self, name):
        assert name == "run/slate-2023-1.json"
        return _FakeBlob(self._raw)


class _FakeClient:
    def __init__(self, raw):
        self._raw = raw

    def bucket(self, name):
        assert name == "bucket"
        return _FakeBucket(self._raw)


def test_live_receipt_uses_the_scorer_primitive():
    raw = b'{"x": 1}'
    receipt, downloaded = live_object_receipt(
        _FakeClient(raw), "gs://bucket/run/slate-2023-1.json")
    assert downloaded == raw
    assert receipt["sha256"] == sha256(raw).hexdigest()
    assert receipt["generation"] == "1787074515655534"
    assert receipt["updated"] == "2026-08-18T17:35:15.743000+00:00"
    assert receipt["bytes"] == len(raw)
    with pytest.raises(ValueError, match="not a GCS uri"):
        live_object_receipt(_FakeClient(raw), "s3://bucket/x")
    with pytest.raises(ValueError, match="lacks an object path"):
        live_object_receipt(_FakeClient(raw), "gs://bucket")
