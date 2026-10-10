#!/usr/bin/env python3
"""Fail-closed preflight for the tracked Sunday money path.

This check is intentionally outcome-blind. It verifies identities, paths, tools, contest metadata and the chosen-dose
contract before a timer can launch a build or watcher. It does not query BigQuery or DraftKings; the build's own
provider checks remain responsible for fresh data.

O-20 (2026-10-03): the preflight used to stop at its FIRST failure, so every check after it stayed unexercised until
the morning it mattered (the 10-02 dry run stopped on the missing sets file and never reached the stale UNION_SAT_DOSE
check, which then stopped Saturday's arm 14 minutes before the D12800). It now runs every check whose prerequisites
hold, prints each failure as it is found ("WEEK RUNTIME PREFLIGHT FAILED: ..."), and exits 2 ONCE at the end. A check
that needs an input which itself failed (a missing variable, directory or contest file) is skipped, not crashed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


HELPERS = (
    "ordering_shadows.py", "hybrid30.py", "vet_book.py", "player_score.py", "book_sheet.py",
    "fill_dk_entries.py", "qb_classify.py", "qb_flags.py", "vet_replace_v4.py", "verify_enter_bundle.py",
)

FAILURES = []
DOC_ONLY = re.compile(r"^(HANDOFF\.md|README\.md|reports/|briefings/)")   # changes that never reach a build (M3)


def fail(message):
    """Record a failure and keep checking; main() exits 2 once, after every check has run."""
    FAILURES.append(message)
    print(f"WEEK RUNTIME PREFLIGHT FAILED: {message}", file=sys.stderr)


def git(root, *args):
    """stdout of a git command, or None (recorded as a failure) when git fails."""
    p = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
    if p.returncode:
        fail(f"git {' '.join(args)} failed in {root}: {p.stderr.strip()}")
        return None
    return p.stdout.strip()


def _int_env(name, default=None):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        fail(f"{name} must be an integer: {raw!r}")
        return None


def check_contests(contests_path):
    """The parsed contest list when it is valid, else None (each problem recorded)."""
    if not contests_path.is_file():
        fail(f"contest file missing: {contests_path}")
        return None
    try:
        contests = json.loads(contests_path.read_text())
    except Exception as exc:
        fail(f"contest file is not JSON: {exc}")
        return None
    if not isinstance(contests, list) or not contests:
        fail("contests.json must be a non-empty list")
        return None
    ok = True
    for contest in contests:
        if not isinstance(contest, dict) or not {"name", "contest_id", "entries", "keep"}.issubset(contest):
            fail(f"contest entry lacks name/id/entries/keep: {contest!r}"); ok = False; continue
        if "REPLACE" in json.dumps(contest): fail(f"contest template marker remains: {contest!r}"); ok = False
        if not str(contest["contest_id"]).isdigit(): fail(f"contest id is not numeric: {contest!r}"); ok = False
        try:
            if int(contest["entries"]) < int(contest["keep"]): fail(f"keep exceeds entries: {contest!r}"); ok = False
        except (TypeError, ValueError):
            fail(f"contest entries/keep are not integers: {contest!r}"); ok = False
    return contests if ok else None


def check_clone_levers(clone, tail_sleeve):
    """Every lever the chain will send as a flag must be one the pinned lab clone accepts (operator 2026-09-27: fail
    here, at arming, never at Saturday's argument parsing). The clone's live_week.py is the authority."""
    live_week = clone / "scripts" / "live_week.py"
    if not live_week.is_file():
        return
    text = live_week.read_text()
    wanted = []
    if os.environ.get("LIVE_MIN_PROJ"): wanted.append("--min-proj")
    if tail_sleeve:
        wanted += ["--tail-sleeve", "--tail-line", "--tail-sleeve-selector"]
        if os.environ.get("TAIL_SLEEVE_SELECTOR", "emax") == "mean":
            if not re.search(r'"--tail-sleeve-selector"[^\n]*\n?[^\n]*"mean"', text):
                fail(f"the pinned lab clone {clone} has no --tail-sleeve-selector mean (lab 54dd512+); move the pin or declare no tail contests")
        if os.environ.get("TAIL_SLEEVE_SELECTOR", "emax") == "class":
            wanted.append("--class-model")
            cm = os.environ.get("CLASS_MODEL", "")
            if not (cm and Path(cm).is_file() and Path(cm + ".sha256").is_file()):
                fail(f"TAIL_SLEEVE_SELECTOR=class needs CLASS_MODEL (json + .sha256); got {cm!r}")
    if os.environ.get("LIVE_SELECTOR", "dual_emax") == "class":
        wanted += ['"class"', "--class-model"]
        cm = os.environ.get("CLASS_MODEL", "")
        if not (cm and Path(cm).is_file() and Path(cm + ".sha256").is_file()):
            fail(f"LIVE_SELECTOR=class needs CLASS_MODEL (json + .sha256); got {cm!r}")
    if os.environ.get("UNION_SATURDAY_RUN"):
        if os.environ.get("LIVE_SELECTOR", "dual_emax") != "mean":
            fail(f"UNION_SATURDAY_RUN needs LIVE_SELECTOR=mean; got {os.environ.get('LIVE_SELECTOR')!r}")
        if not (clone / "src" / "nfl2" / "two_track.py").is_file() or "dst_of" not in (clone / "src" / "nfl2" / "two_track.py").read_text():
            fail(f"the pinned lab clone {clone} has no DST-capped select_top_mean (union_reselect.py needs it)")
        u = os.environ["UNION_SATURDAY_RUN"]
        if u != "auto" and not Path(u, "receipt.json").is_file():
            fail(f"UNION_SATURDAY_RUN={u!r} is neither 'auto' nor a run dir with a receipt")
        if os.environ.get("UNION_MAIN", "mean") not in ("mean", "pmo_x50", "mix"):
            fail(f"UNION_MAIN={os.environ.get('UNION_MAIN')!r} must be mean, pmo_x50 or mix")
        if os.environ.get("UNION_MAIN") == "mix":
            # study 18's shape portfolio solves with optimize(second_game_pair=, qb_game_max=): a clone without them would
            # raise TypeError at the Sunday solve. Checked by CAPABILITY in the clone's own optimize() (frozen-chain rule 7:
            # content, not a commit constant), as the levers above are; the Week-5 re-pin f69598b is the first such clone.
            lineup = clone / "src" / "nfl2" / "core" / "lineup.py"
            ltext = lineup.read_text() if lineup.is_file() else ""
            if not ("second_game_pair" in ltext and "qb_game_max" in ltext and "def _apply_game_shape" in ltext):
                fail(f"UNION_MAIN=mix needs the pinned lab clone's optimize() to take second_game_pair and qb_game_max "
                     f"(lab production/live-pin-w5-20261006 @ f69598b or later); {clone} lacks them")
            if not Path(os.environ.get("CONTESTS_JSON", "")).is_file():
                fail(f"UNION_MAIN=mix needs CONTESTS_JSON (the interleave's plan weights); got {os.environ.get('CONTESTS_JSON')!r}")
        dose = os.environ.get("UNION_SAT_DOSE", "2560/10240")
        if not re.fullmatch(r"\d+/\d+(,\d+/\d+)*", dose):     # an ordered list since 10-01 (week_env; cracks audit B)
            fail(f"UNION_SAT_DOSE={dose!r} must be lev/boom[,lev/boom...]")
    if os.environ.get("UNION_MIX_PORTFOLIO", "") not in ("", "mix", "ws"):
        fail(f"UNION_MIX_PORTFOLIO={os.environ.get('UNION_MIX_PORTFOLIO')!r} must be mix or ws")
    elif os.environ.get("UNION_MAIN") == "mix" and not os.environ.get("UNION_MIX_PORTFOLIO"):
        fail("UNION_MAIN=mix needs UNION_MIX_PORTFOLIO=mix|ws (no default: the operator's chosen arm, stated)")
    _spares = os.environ.get("UNION_MIX_SPARES", "")
    if _spares and not (_spares.isdigit() and 0 <= int(_spares) <= 50):
        fail(f"UNION_MIX_SPARES={_spares!r} must be an integer 0..50")
    elif os.environ.get("UNION_MAIN") == "mix" and _spares == "0":
        fail("UNION_MIX_SPARES=0 with UNION_MAIN=mix leaves a WS row with no in-shape replacement on Sunday (reviewer 10-06)")
    if os.environ.get("UNION_PROJ_SOURCE", "") not in ("", "fp"):
        fail(f"UNION_PROJ_SOURCE={os.environ.get('UNION_PROJ_SOURCE')!r} must be empty (ours) or fp")
    elif os.environ.get("UNION_PROJ_SOURCE") == "fp" and not os.environ.get("UNION_SATURDAY_RUN"):
        fail("UNION_PROJ_SOURCE=fp acts in the T-70 union: set UNION_SATURDAY_RUN (auto)")
    if os.environ.get("CLASS_SLEEVE_EVERY", "0") not in ("", "0"):
        wanted += ["--class-sleeve-every", "--class-model"]
        cm = os.environ.get("CLASS_MODEL", "")
        if not (cm and Path(cm).is_file() and Path(cm + ".sha256").is_file()):
            fail(f"CLASS_SLEEVE_EVERY={os.environ['CLASS_SLEEVE_EVERY']} needs CLASS_MODEL (json + .sha256); got {cm!r}")
    if os.environ.get("LIVE_SELECTOR", "dual_emax") in ("mean", "class"):
        wanted.append('"mean"')
        if os.environ.get("MEAN_OWN_TILT"): wanted += ["--mean-own-tilt", "--mean-own-source"]
        if os.environ.get("MEAN_DST_CAP"): wanted.append("--mean-dst-cap")
        if os.environ.get("MEAN_OWN_TILT") and not Path(os.environ.get("MEAN_OWN_SOURCE", "")).is_file():
            fail(f"MEAN_OWN_TILT={os.environ['MEAN_OWN_TILT']} needs MEAN_OWN_SOURCE (the ownership sets file); got {os.environ.get('MEAN_OWN_SOURCE')!r}")
    missing = [w for w in wanted if w not in text]
    if missing:
        fail(f"the pinned lab clone {clone} does not accept {missing}; move EXPECT_SHA to a commit that does, or unset the lever")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=("build", "watchers"), required=True)
    args = ap.parse_args()
    required = ("SEASON", "WEEK", "WEEKDIR", "SUNDAY", "GROUP", "OUT", "CLONE", "PROD", "PROD_PY", "LAB_PY",
                "TOOLS", "CONTESTS_JSON", "LIVE_DIR", "EXPECT_SHA", "BOOK_ENTRIES")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        fail("missing environment: " + ", ".join(missing))
    env = os.environ.get

    # Paths and interpreters. A directory that is missing (or unset) disables the checks that read inside it.
    prod = Path(env("PROD")) if env("PROD") else None
    clone = Path(env("CLONE")) if env("CLONE") else None
    tools = Path(env("TOOLS")) if env("TOOLS") else None
    if prod is not None and not prod.is_dir(): fail(f"production checkout missing: {prod}"); prod = None
    if clone is not None and not clone.is_dir(): fail(f"live clone missing: {clone}"); clone = None
    if tools is not None and not tools.is_dir(): fail(f"tools directory missing: {tools}"); tools = None
    for name in ("PROD_PY", "LAB_PY"):
        if env(name):
            p = Path(env(name))
            if not p.is_file() or not os.access(p, os.X_OK): fail(f"{name} is not executable: {p}")

    # Identities.
    sha = env("EXPECT_SHA")
    if sha:
        if not re.fullmatch(r"[0-9a-f]{40}", sha): fail(f"EXPECT_SHA must be a full 40-character commit: {sha!r}")
        fixture_sha = "e7255e98bf87297452befb61fb508ad4b368b59f"
        if sha == fixture_sha and env("ALLOW_FIXTURE_PIN") != "1":
            fail("EXPECT_SHA is the compatibility fixture e7255e98...; export the approved Week-3 pin (or set ALLOW_FIXTURE_PIN=1 only for a deliberate rehearsal)")
    actual = None
    if clone is not None:
        actual = git(clone, "rev-parse", "HEAD")
        if actual is not None and sha and actual != sha: fail(f"live clone identity {actual} != EXPECT_SHA {sha}")
        if git(clone, "status", "--porcelain"): fail(f"live clone is dirty: {clone}")
        if not (clone / "scripts/live_week.py").is_file(): fail("live clone has no scripts/live_week.py")
    if prod is not None:
        if git(prod, "status", "--porcelain"): fail(f"production checkout is dirty: {prod}")
        armed = env("PROD_ARMED_HEAD")      # M3 (the outside review 10-07): Sunday runs the code armed on Saturday
        if armed:
            if not re.fullmatch(r"[0-9a-f]{40}", armed):
                fail(f"PROD_ARMED_HEAD must be a full 40-character commit: {armed!r}")
            else:
                head = git(prod, "rev-parse", "HEAD")
                if head is not None and head != armed:
                    changed = git(prod, "diff", "--name-only", armed, "HEAD")
                    if changed is not None:
                        code = [f for f in changed.splitlines() if f and not DOC_ONLY.match(f)]
                        if code:
                            fail(f"production code moved since arming ({armed[:12]} -> {head[:12]}): {code[:8]}")
        if not (prod / "scripts/sunday_build_host.sh").is_file(): fail("production checkout has no sunday_build_host.sh")
    if tools is not None:
        missing_tools = [name for name in HELPERS if not (tools / name).is_file()]
        if missing_tools: fail("missing tracked/helper tools: " + ", ".join(missing_tools))

    # Contests and the layout they need.
    contests = check_contests(Path(env("CONTESTS_JSON"))) if env("CONTESTS_JSON") else None
    book_entries = _int_env("BOOK_ENTRIES")
    tail_sleeve = _int_env("TAIL_SLEEVE", 0)
    layout = env("ENTER_LAYOUT") or "sequential"
    enter_layout = None
    if prod is not None:
        sys.path.insert(0, str(prod / "src"))
        try:
            from nfl_dfs.inference import enter_layout   # the one layout rule (2026-09-24)
        except Exception as exc:
            fail(f"cannot import nfl_dfs.inference.enter_layout from {prod / 'src'}: {exc}")
    required_entries = None
    if enter_layout is not None and contests is not None:
        try:
            required_entries = enter_layout.rows_needed(contests, layout)
        except enter_layout.LayoutError as exc:
            fail(str(exc))
        if required_entries is not None and tail_sleeve is not None:
            declared_sleeve = enter_layout.sleeve_size(contests, layout)
            if tail_sleeve != declared_sleeve:
                fail(f"TAIL_SLEEVE={tail_sleeve} but the contests declare {declared_sleeve} tail-track rows")
            if book_entries is not None and book_entries + tail_sleeve < required_entries:
                fail(f"BOOK_ENTRIES={book_entries} + TAIL_SLEEVE={tail_sleeve} cannot satisfy {layout} contest layout (needs {required_entries})")
    # study 35's per-QB cap is in ROWS calibrated at one K (the reviewer 10-06; the K-dependence lesson): it is armed only
    # with the K it was calibrated at, and only when that K is this week's book
    # the union overlap limit (the outside review 10-06: 5 instead of 7 read ahead on the W2-4 replay); default 7
    # his 10-09 package (study 89, Addendum 186): the ownership cap is armed only as the package -- the player cap 0.35 WITH
    # the ownership cap at +15 points, on the mix -- and the flat 35% never runs alone
    _ocd = os.environ.get("UNION_MAIN_OWN_CAP_DELTA", "")
    _mcap = os.environ.get("UNION_MAIN_CAP", "")
    if _ocd not in ("", "0") and (_ocd != "15" or os.environ.get("UNION_MAIN") != "mix" or _mcap != "0.35"):
        fail(f"UNION_MAIN_OWN_CAP_DELTA={_ocd!r} is his package only: 15 with UNION_MAIN=mix and UNION_MAIN_CAP=0.35 "
             f"(got UNION_MAIN={os.environ.get('UNION_MAIN')!r}, UNION_MAIN_CAP={_mcap!r})")
    if _mcap == "0.35" and _ocd in ("", "0"):
        fail("UNION_MAIN_CAP=0.35 without the ownership cap: the flat 35% never runs alone (his rule; Addendum 186)")
    # his 10-09 test 2 (study 91): the row rules ride only on his package (they read its ownership file)
    _rr = os.environ.get("UNION_MIX_ROW_RULES", "")
    if _rr not in ("", "0") and (_rr != "te1_low1" or os.environ.get("UNION_MAIN") != "mix" or _ocd != "15"):
        fail(f"UNION_MIX_ROW_RULES={_rr!r} must be te1_low1, with UNION_MAIN=mix and his package (UNION_MAIN_OWN_CAP_DELTA=15)")
    # his 10-09 decision (study 93's ONECATCH): one WR / TE per team on the QB + 1 rows, only on top of the row rules
    _oc = os.environ.get("UNION_MIX_ONE_CATCHER_ALL", "")
    if _oc not in ("", "0") and (_oc != "1" or _rr != "te1_low1" or os.environ.get("UNION_MAIN") != "mix" or _ocd != "15"):
        fail(f"UNION_MIX_ONE_CATCHER_ALL={_oc!r} must be 1, with UNION_MIX_ROW_RULES=te1_low1, UNION_MAIN=mix and his package "
             "(UNION_MAIN_OWN_CAP_DELTA=15)")
    # the union refuses the whole run (SystemExit) on these, so they must fail here, on Saturday, not in Sunday's union
    _oc_bad = [f"{k}={os.environ.get(k)!r}" for k, ok in (("UNION_MIX_PORTFOLIO", ("mix",)), ("UNION_MIX_FILL", ("rr",)),
               ("UNION_MIX_COVER_GAMES", ("", "0")), ("UNION_MIX_RS_ROWS", ("", "0")), ("UNION_MIX_BRING_BACK_TOP_WR", ("",)),
               ("UNION_WINNER_SELECT", ("", "0"))) if os.environ.get(k, "") not in ok]
    if _oc == "1" and _oc_bad:
        fail(f"UNION_MIX_ONE_CATCHER_ALL=1 is refused by the union with {', '.join(_oc_bad)} (it needs portfolio mix, fill rr, "
             "no cover / half rows, no bring-back top WR, no winner select)")
    # his 10-09 decision (study 94's RBMATE4): the QB's own RB in the first 4 C rows, only on top of ONECATCH (study 96)
    _rm = os.environ.get("UNION_MIX_RB_MATE_C", "")
    if _rm not in ("", "0") and (_rm != "4" or _oc != "1"):
        fail(f"UNION_MIX_RB_MATE_C={_rm!r} must be 4 (study 94's tested value), with UNION_MIX_ONE_CATCHER_ALL=1 (study 96 read the two "
             "together)")
    # study 97's game-script scopes (default all / off): the RB-mate scope only with the RB mate; the QB2 scope only on ONECATCH
    _rs = os.environ.get("UNION_MIX_RB_MATE_SCOPE", "")
    if _rs not in ("", "all") and (_rs not in ("fav", "favhi", "naked", "oppqb") or _rm != "4"):
        fail(f"UNION_MIX_RB_MATE_SCOPE={_rs!r} must be all / fav / favhi / naked / oppqb, and a scope only with UNION_MIX_RB_MATE_C=4")
    _q2 = os.environ.get("UNION_MIX_QB2_SCOPE", "")
    if _q2 not in ("", "off") and (_q2 not in ("high", "doghi") or _oc != "1"):
        fail(f"UNION_MIX_QB2_SCOPE={_q2!r} must be off / high / doghi, and a scope only with UNION_MIX_ONE_CATCHER_ALL=1")
    if _q2 not in ("", "off") and _rm not in ("", "0"):
        fail(f"UNION_MIX_QB2_SCOPE={_q2!r} with UNION_MIX_RB_MATE_C={_rm!r}: untested together (study 97 read them apart)")
    _fill = os.environ.get("UNION_MIX_FILL", "")
    if _fill and (_fill not in ("group", "value", "rr") or os.environ.get("UNION_MAIN") != "mix"):
        fail(f"UNION_MIX_FILL={_fill!r} must be group, value or rr, with UNION_MAIN=mix (got UNION_MAIN={os.environ.get('UNION_MAIN')!r})")
    _ws = os.environ.get("UNION_WINNER_SELECT", "")
    if _ws and _ws != "0" and (_ws != "1" or os.environ.get("UNION_MAIN") != "mix" or os.environ.get("UNION_WINNER_ORDER", "0") not in ("", "0")
                               or os.environ.get("UNION_MIX_SPARES", "15") == "0"):
        fail(f"UNION_WINNER_SELECT={_ws!r} must be 0 or 1; 1 needs UNION_MAIN=mix with spares and UNION_WINNER_ORDER off (study 48d)")
    _tb = os.environ.get("UNION_TERM_BLOCK_ROWS", "")
    if _tb and _tb != "0":                                   # the live term block (the operator 10-07; its source is the armed file)
        _src = Path(os.environ.get("UNION_TERM_BLOCK_SOURCE", "") or "/nonexistent")
        _sha = os.environ.get("UNION_TERM_BLOCK_SHA256", "")
        _bad = []
        if not _tb.isdigit() or not 0 < int(_tb) < int(os.environ.get("BOOK_ENTRIES", "0") or 0):
            _bad.append(f"rows {_tb!r} not in 1..BOOK_ENTRIES-1")
        if os.environ.get("UNION_MAIN") != "mix" or os.environ.get("UNION_MIX_FILL") != "rr":
            _bad.append("needs UNION_MAIN=mix and UNION_MIX_FILL=rr")
        if any(os.environ.get(v, "0") not in ("", "0") for v in ("UNION_MIX_RS_ROWS", "UNION_MIX_COVER_GAMES", "UNION_WINNER_ORDER", "UNION_WINNER_SELECT", "UNION_MAIN_OWN_TILT")):
            _bad.append("no half / cover / winner order or select / whole-book ownership term with it")
        if not _src.is_file():
            _bad.append(f"the term file {_src} does not exist")
        elif _sha:
            import hashlib
            if hashlib.sha256(_src.read_bytes()).hexdigest() != _sha:
                _bad.append(f"the term file's sha is not the pinned UNION_TERM_BLOCK_SHA256 {_sha[:12]}")
        else:
            _bad.append("no UNION_TERM_BLOCK_SHA256 pin for the term file")
        try:
            _cap = float(os.environ.get("UNION_TERM_BLOCK_CAP", "2.0") or 2.0)
            if not 0 < _cap <= 5.0:
                _bad.append(f"cap {_cap} outside (0, 5]")
        except ValueError:
            _bad.append("UNION_TERM_BLOCK_CAP is not a number")
        if _bad:
            fail(f"UNION_TERM_BLOCK_ROWS={_tb!r}: " + "; ".join(_bad) + " (the live term block)")
    _po = os.environ.get("UNION_PRIORITY_ORDER", "")         # priority-first dealing (the operator 10-07)
    if _po and _po != "0" and (_po != "1" or os.environ.get("UNION_MAIN") != "mix" or os.environ.get("UNION_MIX_PORTFOLIO") != "mix"
                               or any(os.environ.get(v, "0") not in ("", "0") for v in ("UNION_MIX_RS_ROWS", "UNION_MIX_COVER_GAMES", "UNION_WINNER_ORDER", "UNION_WINNER_SELECT", "UNION_MAIN_OWN_TILT"))):
        fail(f"UNION_PRIORITY_ORDER={_po!r} must be 0 or 1; 1 needs UNION_MAIN=mix with UNION_MIX_PORTFOLIO=mix and no half / cover / "
             f"winner order or select / whole-book ownership term (the priority-first deal)")
    _wo = os.environ.get("UNION_WINNER_ORDER", "")
    if _wo and _wo != "0" and (_wo != "1" or os.environ.get("UNION_MAIN") != "mix"):
        fail(f"UNION_WINNER_ORDER={_wo!r} must be 0 or 1, and 1 needs UNION_MAIN=mix (study 48b)")
    _rs = os.environ.get("UNION_MIX_RS_ROWS", "")
    if _rs and _rs != "0" and (_rs not in ("9", "13", "17") or os.environ.get("UNION_MAIN") != "mix"
                               or os.environ.get("UNION_MIX_PORTFOLIO") != "mix" or os.environ.get("UNION_MIX_FILL") != "rr"
                               or os.environ.get("UNION_MIX_COVER_GAMES", "0") not in ("", "0")):
        fail(f"UNION_MIX_RS_ROWS={_rs!r} must be 0, 9, 13 or 17, with UNION_MAIN=mix, UNION_MIX_PORTFOLIO=mix, "
             f"UNION_MIX_FILL=rr and no cover (study 46)")
    _cov = os.environ.get("UNION_MIX_COVER_GAMES", "")
    if _cov and _cov != "0" and (not (_cov.isdigit() and 1 <= int(_cov) <= 8) or os.environ.get("UNION_MAIN") != "mix"
                                 or os.environ.get("UNION_MIX_PORTFOLIO") != "mix"):
        fail(f"UNION_MIX_COVER_GAMES={_cov!r} must be 0..8, with UNION_MAIN=mix and UNION_MIX_PORTFOLIO=mix (study 43)")
    _bb = os.environ.get("UNION_MIX_BRING_BACK_TOP_WR", "")       # study 71: the tested arm only (TOPBB_AB on LIVE_CB)
    if _bb and (_bb != "A1,B" or os.environ.get("UNION_MAIN") != "mix" or os.environ.get("UNION_MIX_PORTFOLIO") != "mix"
                or os.environ.get("UNION_MIX_FILL") != "rr"
                or any(os.environ.get(v, "0") not in ("", "0") for v in ("UNION_MIX_RS_ROWS", "UNION_MIX_COVER_GAMES", "UNION_WINNER_ORDER",
                                                                         "UNION_WINNER_SELECT", "UNION_PRIORITY_ORDER", "UNION_MAIN_OWN_TILT"))):
        fail(f"UNION_MIX_BRING_BACK_TOP_WR={_bb!r} must be empty or A1,B (study 71's tested arm), with UNION_MAIN=mix, "
             f"UNION_MIX_PORTFOLIO=mix, UNION_MIX_FILL=rr and no half / cover / winner order or select / priority order / "
             f"whole-book ownership term")
    _bbr = os.environ.get("UNION_MIX_BRING_BACK_TOP_WR_ROWS", "")   # study 71b: the small-share dose, the tested decision arm only (N4)
    if _bbr and (_bbr != "4" or os.environ.get("UNION_MIX_BRING_BACK_TOP_WR") != "A1,B"):
        fail(f"UNION_MIX_BRING_BACK_TOP_WR_ROWS={_bbr!r} must be empty (every A1/B row) or 4 (study 71b's TOPBB_N4), with "
             f"UNION_MIX_BRING_BACK_TOP_WR=A1,B")
    _ms = os.environ.get("UNION_MEAN_MAX_SHARED", "")
    if _ms and not (_ms.isdigit() and 3 <= int(_ms) <= 8):
        fail(f"UNION_MEAN_MAX_SHARED={_ms!r} must be an integer 3..8 (players a union row may share with every earlier row)")
    _qcap, _qk = os.environ.get("UNION_MAIN_QB_CAP_ROWS", ""), os.environ.get("UNION_MAIN_QB_CAP_K", "")
    if _qcap:
        if not (_qcap.isdigit() and int(_qcap) >= 1):
            fail(f"UNION_MAIN_QB_CAP_ROWS={_qcap!r} must be a positive integer (rows)")
        elif os.environ.get("UNION_MAIN") not in ("pmo_x50", "mix"):
            fail(f"UNION_MAIN_QB_CAP_ROWS needs UNION_MAIN=pmo_x50 or mix; got {os.environ.get('UNION_MAIN')!r}")
        elif not _qk.isdigit():
            fail("UNION_MAIN_QB_CAP_ROWS needs UNION_MAIN_QB_CAP_K (the book size the cap was calibrated at, study 35: 26)")
        elif book_entries is None:                     # never skip the K check (the reviewer 10-06)
            fail("UNION_MAIN_QB_CAP_ROWS needs BOOK_ENTRIES (the week's book size) to check its calibration K")
        elif int(_qk) != book_entries:
            fail(f"UNION_MAIN_QB_CAP_ROWS={_qcap} was calibrated at K {_qk}, but BOOK_ENTRIES={book_entries}: "
                 f"{_qcap} rows is not the studied share at this K; re-calibrate before arming it")
    elif _qk:
        fail("UNION_MAIN_QB_CAP_K is set without UNION_MAIN_QB_CAP_ROWS")
    if enter_layout is not None and book_entries is not None and book_entries < enter_layout.MEAN_ROWS_FLOOR:
        fail(f"BOOK_ENTRIES={book_entries} is below the mean-track floor {enter_layout.MEAN_ROWS_FLOOR}")
    if tail_sleeve and env("LIVE_SELECTOR", "dual_emax") not in ("mean", "class"):
        fail(f"tail-track contests need LIVE_SELECTOR=mean or class (the two-track builder); got {env('LIVE_SELECTOR')!r}")
    if clone is not None:
        check_clone_levers(clone, tail_sleeve)
    if layout != "sequential" and required_entries is not None:   # laptop review F2: show every contest's ranks at arming
        print(f"{layout} layout, {required_entries} distinct lineups:")
        for line in enter_layout.rank_summary(contests, layout):
            print("  " + line)
    order = env("ENTER_ORDER") or "greedy"
    if enter_layout is not None and order not in enter_layout.ORDERS:
        fail(f"unknown ENTER_ORDER {order!r}; expected one of {enter_layout.ORDERS}")
    if order == "fewest-low":
        sets = Path(env("OWNERSHIP_SETS", ""))
        if not sets.is_file():
            fail(f"ENTER_ORDER=fewest-low needs the Saturday sets file OWNERSHIP_SETS={sets} (scripts/ownership_sets.py sets "
                 f"--week {env('WEEK')} --group {env('GROUP')} --out {sets}); write it before arming")
    if args.role == "watchers":
        chosen = Path(env("CHOSEN_FILE", ""))
        if not chosen.is_file():
            fail(f"chosen dose file missing: {chosen}; write CHOSEN_LEV/CHOSEN_BOOM before arming watchers")
        else:
            text = chosen.read_text()
            for name in ("CHOSEN_LEV", "CHOSEN_BOOM"):
                if not re.search(rf"^\s*{name}\s*=\s*[0-9]+\s*$", text, re.MULTILINE):
                    fail(f"chosen dose file lacks {name}=integer: {chosen}")
    if FAILURES:
        print(f"WEEK RUNTIME PREFLIGHT FAILED: {len(FAILURES)} check(s) failed (each listed above)",
              file=sys.stderr)
        raise SystemExit(2)
    print(f"week runtime preflight ok: role={args.role} season={env('SEASON')} week={env('WEEK')} "
          f"group={env('GROUP')} book_entries={book_entries} layout={layout} order={order} clone={actual} tools={tools}")


if __name__ == "__main__":
    main()
