"""The Monday tools' logic (2026-09-29 sweep A1, A4, B6): the cash scorer's Millionaire lookup, the ownership-sets contest
name pattern, the proof-lines digest resolver."""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports" / "lab-handoffs")); sys.path.insert(0, str(ROOT / "scripts"))
import cash_shadow_paper as csp  # noqa: E402
import week3_proof_lines as wpl  # noqa: E402
from ownership_sets import MILLIONAIRE_NAME_RE  # noqa: E402


def test_find_millionaire_prefers_the_id_then_a_dk_name_or_label_and_refuses_nothing():
    calls = []
    def q(sql):
        calls.append(sql)
        if "COUNT(*) n FROM" in sql and "contest_id='196151357'" in sql:
            return pd.DataFrame({"n": [4161]})
        if "LIKE 'milly%'" in sql:
            return pd.DataFrame({"contest_id": ["195905122"], "n": [161764]})
        return pd.DataFrame({"n": [0]})
    assert csp.find_millionaire(q, 2026, 4, "196151357") == "196151357"
    assert csp.find_millionaire(q, 2026, 3) == "195905122"                 # the label-imported week
    def none(sql):
        return pd.DataFrame({"contest_id": [], "n": []}) if "LIKE" in sql else pd.DataFrame({"n": [0]})
    with pytest.raises(SystemExit, match="no Millionaire"):
        csp.find_millionaire(none, 2026, 4)
    with pytest.raises(SystemExit, match="has no rows"):
        csp.find_millionaire(none, 2026, 4, "1")


def test_millionaire_name_pattern_matches_dk_names_and_import_labels():
    rx = re.compile(MILLIONAIRE_NAME_RE)
    assert rx.search("NFL $2.75M Fantasy Football Millionaire [$1M to 1st]") and rx.search("milly20") and rx.search("milly")
    assert not rx.search("supersat4") and not rx.search("sat13mega") and not rx.search("NFL $555 Satellite")


def test_image_digest_from_job_finds_the_pinned_image_in_either_describe_shape():
    v1 = {"spec": {"template": {"spec": {"template": {"spec": {"containers": [{"image": "us-central1-docker.pkg.dev/p/r/project-slate@sha256:" + "a" * 64}]}}}}}}
    v2 = {"template": {"template": {"containers": [{"image": "gcr.io/p/project-slate@sha256:" + "b" * 64}]}}}
    assert wpl.image_digest_from_job(v1) == "sha256:" + "a" * 64
    assert wpl.image_digest_from_job(v2) == "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="pinned by digest"):
        wpl.image_digest_from_job({"template": {"containers": [{"image": "gcr.io/p/project-slate:latest"}]}})


def test_rehearsal_tail_millionaire_and_min_cash_helpers(tmp_path):
    import numpy as np
    import rehearsal_two_track as rt
    cj = tmp_path / "contests.json"
    cj.write_text(json.dumps([{"name": "supersat8", "track": "mean"}, {"name": "milly", "track": "tail"}, {"name": "sat", "track": "tail"}]))
    assert rt.tail_names(None, cj) == {"milly", "sat"}
    assert rt.tail_names("a,b", cj) == {"a", "b"} and rt.tail_names(None, None) == {"milly20", "ffwc", "ffwc18"}
    contests = [{"name": "supersat8", "track": "mean"}, {"name": "milly", "track": "tail"}, {"name": "sat", "track": "tail"}]
    assert rt.millionaire_label(contests, None) == "milly"
    assert rt.millionaire_label([{"name": "x", "track": "mean"}], None) == "milly20"
    with pytest.raises(SystemExit, match="no tail track"):
        rt.millionaire_label([{"name": "x", "track": "mean"}], "196151357")
    pay = {1: 1_000_000.0, 2: 500.0, 3: 30.0, 4: 30.0, 5: 0.0}          # 4 paid places
    others = np.array([100.0, 180.0, 150.0, 120.0, 170.0, 160.0])
    assert rt.milly_cash_from_ladder(pay, others) == 150.0               # the 4th-best other entrant
    with pytest.raises(SystemExit, match="cannot derive"):
        rt.milly_cash_from_ladder({1: 0.0}, others)
