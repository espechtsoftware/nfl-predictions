"""The reviewed weekly inputs must validate identically to the build gate.

`contests.json` and `chosen-dose.env` are the two files the Sunday build refuses
to start without, and they used to exist only on one host. This tool moves them
to the project's private bucket. It must NOT be possible for this tool to accept
a pair that `check_build_inputs.py` would then reject at arming time, so the
rules are asserted against that module's own behaviour where they overlap.

The tool must also never leak per-contest detail into the receipt: the repository
is public, and the entry/keep/fee columns are the week's stake plan.

Each test breaks the property it claims.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "scripts" / "week_inputs.py"
_spec = importlib.util.spec_from_file_location("week_inputs", _SRC)
wi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wi)

GOOD_DOSE = "CHOSEN_LEV=2560\nCHOSEN_BOOM=10240\n"


def contests(n=12, entries=8, fee=20, start=1000):
    return json.dumps([
        {"name": f"contest {i}", "contest_id": str(start + i), "entries": entries,
         "keep": entries, "fee": fee, "note": ""} for i in range(n)])


class TestDose:
    def test_a_good_pair_passes(self):
        assert wi.validate_dose(GOOD_DOSE) == []

    @pytest.mark.parametrize("key", wi.DOSE_KEYS)
    def test_a_missing_key_is_caught(self, key):
        text = "\n".join(l for l in GOOD_DOSE.splitlines() if not l.startswith(key))
        assert any(key in p for p in wi.validate_dose(text))

    def test_zero_and_negative_are_refused(self):
        assert wi.validate_dose("CHOSEN_LEV=0\nCHOSEN_BOOM=10240") != []
        assert wi.validate_dose("CHOSEN_LEV=-1\nCHOSEN_BOOM=10240") != []

    def test_a_non_integer_is_refused(self):
        assert any("not an integer" in p for p in wi.validate_dose("CHOSEN_LEV=lots\nCHOSEN_BOOM=1"))

    def test_comments_and_blank_lines_are_ignored(self):
        assert wi.validate_dose("# note\n\nCHOSEN_LEV=2560\nCHOSEN_BOOM=10240\n") == []


class TestContests:
    def test_a_good_file_passes(self):
        assert wi.validate_contests(contests()) == []

    def test_a_dict_wrapper_is_accepted(self):
        wrapped = json.dumps({"contests": json.loads(contests())})
        assert wi.validate_contests(wrapped) == []

    def test_too_few_entries_is_refused(self):
        """The minimum mechanism, at an explicit floor (the default floor is 1 since
        2026-09-22, matching build_inputs; a volume floor is not a quality check)."""
        assert any("minimum" in p for p in wi.validate_contests(contests(n=2, entries=8), min_entries=90))
        assert wi.validate_contests(contests(n=2, entries=8)) == []

    def test_a_duplicate_contest_id_is_refused(self):
        rows = json.loads(contests())
        rows[1]["contest_id"] = rows[0]["contest_id"]
        assert any("more than once" in p for p in wi.validate_contests(json.dumps(rows)))

    def test_an_empty_contest_id_is_refused(self):
        rows = json.loads(contests())
        rows[0]["contest_id"] = "  "
        assert any("empty contest_id" in p for p in wi.validate_contests(json.dumps(rows)))

    @pytest.mark.parametrize("field", wi.CONTEST_FIELDS)
    def test_a_missing_field_is_caught(self, field):
        rows = json.loads(contests())
        rows[3].pop(field)
        assert any(field in p for p in wi.validate_contests(json.dumps(rows)))

    def test_keeping_more_than_entered_is_refused(self):
        rows = json.loads(contests())
        rows[0]["keep"] = rows[0]["entries"] + 1
        assert any("keeps more rows" in p for p in wi.validate_contests(json.dumps(rows)))

    def test_bad_json_is_reported_not_raised(self):
        assert any("not valid JSON" in p for p in wi.validate_contests("{oops"))

    def test_an_empty_list_is_refused(self):
        assert wi.validate_contests("[]") != []

    def test_a_non_integer_entry_count_is_refused(self):
        rows = json.loads(contests())
        rows[0]["entries"] = "eight"
        assert any("not an integer" in p for p in wi.validate_contests(json.dumps(rows)))


class TestTheReceiptLeaksNothing:
    """The repository is public; the stake plan must not become committable."""

    def test_the_summary_carries_no_contest_ids(self):
        s = wi.summarise(contests(), GOOD_DOSE)
        blob = json.dumps(s)
        for row in json.loads(contests()):
            assert row["contest_id"] not in blob
            assert row["name"] not in blob

    def test_the_summary_is_aggregates_only(self):
        s = wi.summarise(contests(n=12, entries=8, fee=20), GOOD_DOSE)
        assert s == {"contests": 12, "total_entries": 96, "total_fee": float(96 * 20),
                     "chosen_lev": 2560, "chosen_boom": 10240}

    def test_per_contest_fees_are_not_itemised(self):
        s = wi.summarise(contests(), GOOD_DOSE)
        assert not any(isinstance(v, (list, dict)) for v in s.values())


class TestObjectLayout:
    def test_the_uri_is_week_padded_and_private(self):
        uri = wi.object_uri(wi.DEFAULT_BUCKET, 2026, 3, "contests.json")
        assert uri == f"gs://{wi.DEFAULT_BUCKET}/week-inputs/2026/w03/contests.json"

    def test_weeks_do_not_collide(self):
        a = wi.object_uri(wi.DEFAULT_BUCKET, 2026, 3, "contests.json")
        b = wi.object_uri(wi.DEFAULT_BUCKET, 2026, 13, "contests.json")
        assert a != b and "w03" in a and "w13" in b

    def test_the_default_bucket_is_the_private_one(self):
        assert wi.DEFAULT_BUCKET == "nfl-predictions-503414-raw"


class TestTheGateAgrees:
    """This tool must not accept what the build gate would reject."""

    def test_the_minimum_matches_the_gate(self):
        # Imported as a package module, not by file path: build_inputs uses a
        # relative import and a path load breaks it.
        from nfl_dfs.inference import build_inputs as bi
        import inspect
        sig = inspect.signature(bi.assess_files)
        assert sig.parameters["min_book_entries"].default == wi.MIN_BOOK_ENTRIES

    def test_the_gate_accepts_what_this_tool_accepts(self):
        from nfl_dfs.inference import build_inputs as bi
        text, dose_text = contests(), GOOD_DOSE
        assert wi.validate_contests(text) == [] and wi.validate_dose(dose_text) == []
        verdict = bi.assess_files(wi.parse_dose(dose_text), json.loads(text))
        assert verdict["ok"], verdict


class TestFeeIsMoneyNotAnInteger:
    """Caught by validating the real Week-2 file rather than a fixture.

    Two of the twelve Week-2 contests carry a $0.25 fee. Validating fee as an
    int truncated those to zero, so the summary read $238 against the $246
    actually settled, and a fee written as the string "0.25" would have been
    rejected outright as "not an integer" — refusing a perfectly valid file.
    """

    def test_a_fractional_fee_is_accepted(self):
        rows = json.loads(contests())
        rows[0]["fee"] = 0.25
        assert wi.validate_contests(json.dumps(rows)) == []

    def test_a_fractional_fee_written_as_a_string_is_accepted(self):
        rows = json.loads(contests())
        rows[0]["fee"] = "0.25"
        assert wi.validate_contests(json.dumps(rows)) == []

    def test_a_fractional_fee_is_not_truncated_in_the_total(self):
        rows = json.loads(contests(n=1, entries=16, fee=20))
        rows[0]["fee"] = 0.25
        rows.extend(json.loads(contests(n=11, entries=8, fee=1, start=5000)))
        s = wi.summarise(json.dumps(rows), GOOD_DOSE)
        assert s["total_fee"] == pytest.approx(16 * 0.25 + 88 * 1)

    def test_the_real_week2_file_totals_what_was_settled(self):
        """The cross-check that found the bug: $246.00, per the evidence record."""
        real = Path("/home/erich/week2-sunday/contests.json")
        if not real.is_file():
            pytest.skip("the Week-2 contests file is not on this host")
        s = wi.summarise(real.read_text(), GOOD_DOSE)
        assert s["contests"] == 12 and s["total_entries"] == 97
        assert s["total_fee"] == pytest.approx(246.00)

    def test_a_negative_fee_is_still_refused(self):
        rows = json.loads(contests())
        rows[0]["fee"] = -1
        assert any("must not be negative" in p for p in wi.validate_contests(json.dumps(rows)))

    def test_a_non_numeric_fee_is_refused(self):
        rows = json.loads(contests())
        rows[0]["fee"] = "free"
        assert any("not a number" in p for p in wi.validate_contests(json.dumps(rows)))


# --- The torn-pair boundary the laptop identified (2026-09-21) ----------------
# push writes two separate objects, so a pull overlapping an operator update
# could install one push's contests beside another push's dose. push now writes
# a manifest LAST as the single commit point, and pull resolves the pair through
# it BY GENERATION. These tests drive that with a fake GCS client.

import types
from datetime import UTC, datetime


class _FakeBlob:
    def __init__(self, store, name, generation=None):
        self._store, self.name = store, name
        self._want = generation
        self.updated = datetime(2026, 9, 21, tzinfo=UTC)

    @property
    def _versions(self):
        return self._store.get(self.name, [])

    @property
    def _chosen(self):
        if not self._versions:
            return None
        if self._want is None:
            return self._versions[-1]
        for gen, raw in self._versions:
            if gen == self._want:
                return (gen, raw)
        return None

    @property
    def generation(self):
        return self._chosen[0] if self._chosen else None

    def exists(self):
        return self._chosen is not None

    def download_as_bytes(self):
        if not self._chosen:
            raise FileNotFoundError(f"no such generation for {self.name}")
        return self._chosen[1]

    def upload_from_string(self, raw):
        raw = raw if isinstance(raw, bytes) else raw.encode()
        nxt = (self._versions[-1][0] + 1) if self._versions else 1000
        self._store.setdefault(self.name, []).append((nxt, raw))

    def reload(self):
        return None


class _FakeBucket:
    def __init__(self, store): self._store = store
    def blob(self, name, generation=None): return _FakeBlob(self._store, name, generation)


class _FakeClient:
    def __init__(self): self.store = {}
    def bucket(self, _name): return _FakeBucket(self.store)


def _args(**kw):
    base = {"bucket": wi.DEFAULT_BUCKET, "min_entries": wi.MIN_BOOK_ENTRIES,
            "season": 2026, "week": 3}
    base.update(kw)
    return types.SimpleNamespace(**base)


@pytest.fixture
def fake(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(wi, "_client", lambda: client)
    return client


def _push(fake, tmp_path, contests_text, dose_text):
    c = tmp_path / "c.json"; c.write_text(contests_text)
    d = tmp_path / "d.env"; d.write_text(dose_text)
    return wi.cmd_push(_args(contests=str(c), dose=str(d)))


class TestTheManifestPinsThePair:
    def test_push_then_pull_round_trips(self, fake, tmp_path):
        assert _push(fake, tmp_path, contests(), GOOD_DOSE) == 0
        out = tmp_path / "out"
        assert wi.cmd_pull(_args(out=str(out))) == 0
        assert json.loads((out / "contests.json").read_text())
        assert "CHOSEN_LEV" in (out / "chosen-dose.env").read_text()

    def test_push_writes_the_manifest(self, fake, tmp_path):
        _push(fake, tmp_path, contests(), GOOD_DOSE)
        keys = [k for k in fake.store if k.endswith(wi.MANIFEST)]
        assert keys, "no manifest object was written"

    def test_a_pull_gets_the_pinned_pair_not_the_newest_objects(self, fake, tmp_path):
        """The torn-read case: a file is replaced WITHOUT a new manifest."""
        _push(fake, tmp_path, contests(n=12, entries=8), GOOD_DOSE)
        contests_key = next(k for k in fake.store if k.endswith("contests.json"))
        newer = contests(n=12, entries=9, start=7000).encode()
        fake.store[contests_key].append((9999, newer))

        out = tmp_path / "out"
        assert wi.cmd_pull(_args(out=str(out))) == 0
        installed = json.loads((out / "contests.json").read_text())
        assert sum(c["entries"] for c in installed) == 96, \
            "pull took the newest object instead of the generation the manifest pins"

    def test_a_second_push_moves_the_pair_together(self, fake, tmp_path):
        _push(fake, tmp_path, contests(n=12, entries=8), GOOD_DOSE)
        _push(fake, tmp_path, contests(n=12, entries=9, start=7000),
              "CHOSEN_LEV=1280\nCHOSEN_BOOM=5120\n")
        out = tmp_path / "out"
        assert wi.cmd_pull(_args(out=str(out))) == 0
        installed = json.loads((out / "contests.json").read_text())
        assert sum(c["entries"] for c in installed) == 108
        assert "CHOSEN_LEV=1280" in (out / "chosen-dose.env").read_text()


class TestPullFailsClosed:
    def test_no_manifest_means_no_install(self, fake, tmp_path):
        out = tmp_path / "out"
        assert wi.cmd_pull(_args(out=str(out))) == 1
        assert not (out / "contests.json").exists()

    def test_a_missing_pinned_generation_is_refused(self, fake, tmp_path):
        _push(fake, tmp_path, contests(), GOOD_DOSE)
        key = next(k for k in fake.store if k.endswith("chosen-dose.env"))
        fake.store[key] = []                      # the pinned version is gone
        out = tmp_path / "out"
        assert wi.cmd_pull(_args(out=str(out))) == 1
        assert not (out / "contests.json").exists(), "a partial pair was installed"

    def test_a_hash_mismatch_is_refused(self, fake, tmp_path):
        _push(fake, tmp_path, contests(), GOOD_DOSE)
        key = next(k for k in fake.store if k.endswith("contests.json"))
        gen, _ = fake.store[key][-1]
        fake.store[key][-1] = (gen, b'[{"name":"x","contest_id":"1","entries":999,'
                                    b'"keep":1,"fee":1}]')
        out = tmp_path / "out"
        assert wi.cmd_pull(_args(out=str(out))) == 1

    def test_invalid_inputs_are_never_installed(self, fake, tmp_path):
        """Validation runs after fetch and before any file is written."""
        _push(fake, tmp_path, contests(), GOOD_DOSE)
        key = next(k for k in fake.store if k.endswith("chosen-dose.env"))
        gen, raw = fake.store[key][-1]
        bad = b"CHOSEN_LEV=0\nCHOSEN_BOOM=10240\n"
        fake.store[key][-1] = (gen, bad)
        m_key = next(k for k in fake.store if k.endswith(wi.MANIFEST))
        m_gen, m_raw = fake.store[m_key][-1]
        m = json.loads(m_raw)
        import hashlib
        m["objects"]["chosen-dose.env"]["sha256"] = hashlib.sha256(bad).hexdigest()
        m["objects"]["chosen-dose.env"]["bytes"] = len(bad)
        fake.store[m_key][-1] = (m_gen, json.dumps(m).encode())
        out = tmp_path / "out"
        assert wi.cmd_pull(_args(out=str(out))) == 1
        assert not (out / "chosen-dose.env").exists()

    def test_push_refuses_to_publish_an_invalid_pair(self, fake, tmp_path):
        bad = json.loads(contests(n=2)); bad[1]["contest_id"] = bad[0]["contest_id"]   # duplicate id
        assert _push(fake, tmp_path, json.dumps(bad), GOOD_DOSE) == 1
        assert not fake.store, "an invalid pair reached the bucket"
