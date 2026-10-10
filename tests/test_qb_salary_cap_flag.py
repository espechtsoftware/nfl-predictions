"""The QB salary cap by cell (the operator 10-10: "in cells B and C, QB salary <= 6400"): union_reselect's CLI refusals, the
per-cell layer in mix_rows, and the wiring (the host, the house fallback, the timers, the runtime check and the arm). The rule
itself is one more member bound (the pool QBs above the cap, 0, 0) appended to the row-rule tier on the named cells' book
solves, so it rides and drops with te1 / low1 / band; checked live by the W4 ON build."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402

BASE = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
OWN = ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
ROWS = ["--mix-portfolio", "mix", "--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1"]


@pytest.mark.parametrize("extra", [
    ROWS + ["--mix-qb-max-salary", "6400"],                                             # no cells
    ROWS + ["--mix-qb-max-salary", "6400", "--mix-qb-max-salary-cells", "B,D"],         # not a MIX cell
    ROWS + ["--mix-qb-max-salary", "6400", "--mix-qb-max-salary-cells", "B,B"],         # not distinct
    ROWS + ["--mix-qb-max-salary", "640", "--mix-qb-max-salary-cells", "B,C"],          # not a salary
    ["--mix-qb-max-salary", "6400", "--mix-qb-max-salary-cells", "B,C"],                # no row rules
])
def test_the_cli_refuses_the_cap_without_its_cells_or_the_row_rules(extra):
    with pytest.raises(SystemExit, match="--mix-qb-max-salary S"):
        ur.main(BASE + OWN + extra)


def test_the_cells_alone_are_refused():
    with pytest.raises(SystemExit, match="--mix-qb-max-salary-cells is read only"):
        ur.main(BASE + OWN + ROWS + ["--mix-qb-max-salary-cells", "B,C"])


def test_the_layer_rides_in_the_row_rule_tier_on_its_cells_only():
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert 'raise ValueError("cell_bounds ride in the row-rule tier: they need row_bounds")' in src
    assert "rbx = rb + cb.get(name, [])" in src                                    # the named cell's book solves only (j < k)
    assert src.count("_solve(name, extra_bans, use_term, rbx") == 3                 # RB mate, ONECATCH and the plain tier
    assert src.count("rb_mate_qb_teams=rm_teams, cell_bounds=qbs_cells)") == 2       # the live book and the term book
    assert "qbs_cells = {c: [(dear, 0, 0)] for c in qb_sal_cells} if dear else {}" in src   # empty set: no layer
    assert '> a.mix_qb_max_salary).to_numpy()' in src                                # strictly above the cap
    assert "!!! QB SALARY CAP NOT APPLIED" in src and 'mix_meta["qb_salary_cap_source"] = dict(qbs_meta)' in src


def test_a_house_fallback_drops_both_qb_salary_flags_and_their_values():
    lib = ROOT / "scripts" / "union_fallbacks.sh"
    args = ("--main mix --main-cap-share 0.35 --mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 "
            "--mix-qb-max-salary 6400 --mix-qb-max-salary-cells B,C --y")
    script = f'source "{lib}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.35|--y|"


def test_the_host_the_timers_the_runtime_check_and_the_arm_carry_it():
    root = ROOT / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert ('UNION_ARGS+=(--mix-qb-max-salary "$UNION_MIX_QB_MAX_SALARY" --mix-qb-max-salary-cells '
            '"$UNION_MIX_QB_MAX_SALARY_CELLS"); QBSAL_ON=1') in host
    assert "grep -q 'QB SALARY CAP NOT APPLIED'" in host and '"$UNION_DIR/qb_salary_cap_not_applied.txt"' in host
    assert (host.index("ROW_RULES_ON=1") < host.index("UNION_ARGS+=(--mix-qb-max-salary")
            < host.index('UNION_RC=0; run_union "${UNION_ARGS[@]}"'))
    timers = (root / "arm_week_timers.sh").read_text()
    assert " UNION_MIX_QB_MAX_SALARY UNION_MIX_QB_MAX_SALARY_CELLS " in timers
    check = (root / "check_week_runtime.py").read_text()
    assert 'os.environ.get("UNION_MIX_QB_MAX_SALARY", "")' in check and 'os.environ.get("UNION_MIX_QB_MAX_SALARY_CELLS", "")' in check
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert ('if [[ -n "$QB_MAX_SALARY" ]]; then e+=(UNION_MIX_QB_MAX_SALARY=$QB_MAX_SALARY '
            'UNION_MIX_QB_MAX_SALARY_CELLS=$QB_MAX_SALARY_CELLS); else u+=(-u UNION_MIX_QB_MAX_SALARY -u UNION_MIX_QB_MAX_SALARY_CELLS); fi') in arm
    assert '"$QB_MAX_SALARY_CELLS" =~ ^(A1|A2|B|C)(,(A1|A2|B|C))*$ && "$ROW_RULES" == te1_low1' in arm



def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


RMT = _load("rb_mate_helpers_qbsal", ROOT / "tests" / "test_rb_mate_c_flag.py")   # the ONECATCH / RB-mate fixture and stand-in solver


def _book(monkeypatch, fr, caps, bounds, cell_bounds=None):
    RMT.install_production(monkeypatch)
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 9, None, 0, RMT.W, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                                        term_rows=8, term_bonus=RMT.TERM, own_cap=caps, row_bounds=bounds, one_catcher=True,
                                        rb_mate_c=4, cell_bounds=cell_bounds)
    return [list(r) for r in rows], list(cells), meta, [list(r) for r, _ in sp]


def test_the_banned_qbs_leave_the_named_cells_and_an_empty_layer_is_off(monkeypatch, tmp_path):
    fr, caps, bounds, _ = RMT.OCT.inputs(tmp_path)
    pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    off = _book(monkeypatch, fr, caps, bounds)
    assert _book(monkeypatch, fr, caps, bounds, {}) == off and "cell_bounds" not in off[2]          # vacuous: byte for byte off
    qb_of = lambda r: next(i for i in r if pos[str(i)] == "QB")                                    # noqa: E731
    used = [qb_of(r) for r, c in zip(off[0], off[1]) if c in ("B", "C")]
    dear = {max(set(used), key=used.count)}                                                       # the B / C rows' most used QB
    on = _book(monkeypatch, fr, caps, bounds, {"B": [(dear, 0, 0)], "C": [(dear, 0, 0)]})
    bc = [r for r, c in zip(on[0], on[1]) if c in ("B", "C")]
    assert bc and not any(qb_of(r) in dear for r in bc)                                           # no banned QB on a B / C book row
    assert on[2]["cell_bounds"] == {"cells": ["B", "C"], "ruled_solves": len(bc), "resolved_without": []}
    assert on[0] != off[0]


def test_the_layer_needs_the_row_rules(monkeypatch, tmp_path):
    fr, caps, bounds, _ = RMT.OCT.inputs(tmp_path)
    RMT.install_production(monkeypatch)
    with pytest.raises(ValueError, match="cell_bounds ride in the row-rule tier"):
        ur.mix_rows(fr, set(), 26, 9, None, 0, RMT.W, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                    own_cap=caps, cell_bounds={"B": [({"x"}, 0, 0)]})
