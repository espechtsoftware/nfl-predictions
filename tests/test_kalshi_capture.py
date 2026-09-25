"""R5 Kalshi collector: pagination, 429 backoff, one bad series recorded not fatal, create-once snapshot files."""
import gzip
import importlib.util
import io
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pytest

_P = Path(__file__).resolve().parents[1] / "scripts" / "kalshi_capture.py"
_spec = importlib.util.spec_from_file_location("kalshi_capture", _P)
kc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kc)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(pages, fail_first_429=False, broken=()):
    calls = {"n": 0}

    def open_(url, timeout=30):
        calls["n"] += 1
        if fail_first_429 and calls["n"] == 1:
            raise urllib.error.HTTPError(url, 429, "rate", {}, None)
        series = url.split("series_ticker=")[1].split("&")[0]
        if series in broken:
            raise urllib.error.HTTPError(url, 404, "nope", {}, None)
        cur = url.split("cursor=")[1].split("&")[0] if "cursor=" in url else ""
        page = pages.get((series, cur), {"markets": [], "cursor": ""})
        return _Resp(json.dumps(page).encode())
    return open_


def test_pagination_and_429_backoff():
    pages = {("KXNFLFFPTS", ""): {"markets": [{"ticker": "a"}], "cursor": "c1"},
             ("KXNFLFFPTS", "c1"): {"markets": [{"ticker": "b"}], "cursor": ""}}
    slept = []
    ms = kc.series_markets("KXNFLFFPTS", _opener(pages, fail_first_429=True), slept.append)
    assert [m["ticker"] for m in ms] == ["a", "b"] and 1 in slept      # backed off once (1 s) after the 429


def test_snapshot_writes_once_and_records_a_failed_series(tmp_path, monkeypatch):
    monkeypatch.setattr(kc, "SERIES", ("KXNFLFFPTS", "KXNFLREC"))
    pages = {("KXNFLFFPTS", ""): {"markets": [{"ticker": "a"}, {"ticker": "b"}], "cursor": ""}}
    now = datetime(2026, 9, 26, 15, 30, tzinfo=timezone.utc)
    data, man, m = kc.snapshot("sat-build", 2026, 3, tmp_path, _opener(pages, broken={"KXNFLREC"}), lambda s: None, now)
    rows = [json.loads(l) for l in gzip.open(data, "rt")]
    assert [r["market"]["ticker"] for r in rows] == ["a", "b"] and m["series_counts"] == {"KXNFLFFPTS": 2}
    assert "KXNFLREC" in m["series_errors"] and json.loads(man.read_text())["sha256"] == m["sha256"]
    with pytest.raises(SystemExit, match="written once"):
        kc.snapshot("sat-build", 2026, 3, tmp_path, _opener(pages), lambda s: None, now)
