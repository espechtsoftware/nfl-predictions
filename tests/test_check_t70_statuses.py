"""O-59 (the operator 10-08: "Add a 10:47 pull" + a loud warning): the T-70 build's DK pull is checked by CONTENT -- did
it carry DraftKings' inactive update (the out count rose or the Questionable count fell) -- and a pre-inactives pull
prints one banner naming the ~11:00 pre-upload check as the only safety net. It never fails the build."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_t70_statuses as C  # noqa: E402


def test_the_rule_on_the_real_w2_to_w4_counts():
    assert C.decide((90, 13), (90, 13))[0] == "PRE"           # W4: 10:33 = the morning
    assert C.decide((86, 16), (86, 16))[0] == "PRE"           # W3
    assert C.decide((83, 9), (101, 5))[0] == "POST"           # W2: the 10:49 pull
    assert C.decide((90, 13), (90, 5))[0] == "POST"           # Questionable cleared, out unchanged: still an update
    assert "THE ~11:00 PRE-UPLOAD STATUS CHECK IS THE ONLY SAFETY NET TODAY" in C.decide((90, 13), (90, 13))[1]


def _run(tmp_path, pull):
    d = tmp_path / "run"; d.mkdir(parents=True)
    (d / "receipt.json").write_text(json.dumps({"salary_pull": pull}))
    return d


def _t(h, m):
    return datetime(2026, 10, 11, h, m, tzinfo=timezone.utc)


def test_check_takes_the_morning_pull_and_the_builds_pull(tmp_path):
    rows = [(_t(14, 59), 90, 13), (_t(15, 33), 90, 13), (_t(15, 47), 109, 5), (_t(16, 59), 110, 5)]
    v, line = C.check(_run(tmp_path, "2026-10-11 15:47:10.5+00:00"), "154468", "2026-10-11T15:30:00+00:00", counts=lambda g: rows)
    assert v == "POST" and "out 90 -> 109" in line and "15:47" in line          # the 10:47 pull, never the later 11:59
    v, _ = C.check(_run(tmp_path / "b", "2026-10-11 15:33:13+00:00"), "154468", "2026-10-11T15:30:00+00:00", counts=lambda g: rows)
    assert v == "PRE"                                                              # the 10:33 pull alone


def test_unavailable_never_fails(tmp_path, capsys):
    v, line = C.check(tmp_path / "missing", "154468", "2026-10-11T15:30:00+00:00", counts=lambda g: [])
    assert v == "UNAVAILABLE" and "no readable receipt" in line
    v, _ = C.check(_run(tmp_path, "2026-10-11 15:47:00+00:00"), "154468", "2026-10-11T15:30:00+00:00", counts=lambda g: [])
    assert v == "UNAVAILABLE"
    assert C.main([str(tmp_path / "missing"), "--group", "154468", "--inactives-utc", "2026-10-11T15:30:00+00:00"]) == 0
    assert "DK STATUS CHECK UNAVAILABLE" in capsys.readouterr().out


def test_the_host_runs_it_after_m4_and_writes_an_alert_only():
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    block = host[host.index('if [[ -n "${MIN_PROJ_GENERATED_AT:-}" ]]; then\n  if ! SP_WHY'):]
    block = block[:block.index("\nfi\n") + 4]
    assert '"$PROD/scripts/check_t70_statuses.py" "$K90_DIR" --group "$GROUP"' in block
    assert '--inactives-utc "$MIN_PROJ_GENERATED_AT"' in block
    assert '> "$OUT/ALERT-dk-statuses-pre-inactives-$RUN_TAG.txt"' in block
    assert "exit" not in block.split("check_t70_statuses.py")[1]                    # a warning: never a stop
