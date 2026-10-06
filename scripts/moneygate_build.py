#!/usr/bin/env python3
"""Week-5 money gate, BUILD half (reports/2026-10-04-week5-money-gate-design.md §2-§3, §6; Addendum 1 point 5).

OUTCOME-BLIND. Builds every arm's book for each week from that week's archived, sha256-pinned pools, lays it into the
week's real contests with today's layout code, and runs the §6 integrity checks. It never reads a field, a standings
file, a realized-points table or a payout; the scorer (scripts/moneygate_score.py) is a separate program.

Arms (§3, frozen; flags are the Week-4 entered union_args.txt minus its paths):
  A1 CURRENT  --main pmo_x50 --main-cap-share 0.5 --main-own-tilt 0.20 (+ the week's point-in-time ownership file);
              field sleeve on the Millionaire row (--sleeve-source field --sleeve-field-rows 1)
  A2 MEAN     --main mean (top-K by T-70 mean, <= 7 shared, DST cap 0.25); same sleeve and layout
  A3 CAP30    A1 with --main-cap-share 0.30
  A4 NO-TILT  A1 with --main-own-tilt 0 (the field sleeve keeps the ownership file)
A week WITHOUT a point-in-time ownership file (W1, W2) runs with no term and the projection sleeve
(--sleeve-source mean), so A1 = A4 there by construction (disclosed; Addendum 1 point 1).

Contest routing (today's rule, applied identically to every week): the week's real contest list and entry counts,
operator pins and old track fields stripped; the Millionaire contest `track_override: tail`; field-size holds as in
Week 4 (`--hold-on-main 2378` where such a contest exists); then scripts/set_contest_tracks.py --rule line (deep-line
contests to the mean-selected tail sleeve). K and T come from enter_layout (head layout), exactly as week_env.sh
computes BOOK_ENTRIES / TAIL_SLEEVE. Week 4 uses its entered contests.json unchanged, and the routing rule is checked
against it (it must reproduce Week 4's tracks and order).

Layout: enter_layout.write (head layout, greedy order, ENTER_SMALL_MAX_SHARED=5, ENTER_SMALL_OVERLAP_MAX_ENTRIES=10).

Every union_reselect.py run uses the SAME code: this checkout's scripts + the lab src pinned in the private config
(32cdb61, the code that entered Week 4). The older weeks' own lab pins lack nfl2.two_track (select_top_mean), which
union_reselect.py imports, so they cannot run it (recorded in the build receipt by `pins` below).

    python scripts/moneygate_build.py contests  [--weeks 1,2,3,4]
    python scripts/moneygate_build.py build     [--weeks ...] [--arms A1,A2,A3,A4] [--runs 2]
    python scripts/moneygate_build.py layout    [--weeks ...] [--arms ...]
    python scripts/moneygate_build.py integrity [--weeks ...]
    python scripts/moneygate_build.py all       [--weeks ...]
    python scripts/moneygate_build.py a1-paper --week-config <week.json> --out <dir>   # the weekly A1 paper book (rollback trigger)
    python scripts/moneygate_build.py build --weeks 2,3,4 --arms PKG5-group,PKG4-rr --runs 1   # DESCRIPTIVE package arms

PKG<ms>-<fill> (DESCRIPTIVE, never a money-gate arm; the operator's 10-06 expedited plan, the reviewer's terms): the
Week-5 package translated to each week's REAL contests -- --main mix (the winners' mix, the week's routed contests as
the mix plan, head), overlap limit <ms>, --mix-fill <fill>, no ownership term, FP projections where the week's config
pins an fp_proj_source (W4 only), the week's own T with A1's sleeve flags, and study 35's QB cap TRANSLATED by share:
rows = round(5 x K / 26) at --main-qb-cap-k K (the cap was studied at K 26 only). The week's contest mix is not Rev3.

Config: ~/moneygate/weeks.json (private: paths and sha256 pins; MONEYGATE_CONFIG overrides). Outputs: ~/moneygate/books
(MONEYGATE_BOOKS overrides). Nothing is written inside git.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROD / "src"))
sys.path.insert(0, str(PROD / "scripts"))

from nfl_dfs.inference import enter_layout as EL  # noqa: E402

CONFIG = Path(os.environ.get("MONEYGATE_CONFIG", Path.home() / "moneygate" / "weeks.json"))
BOOKS = Path(os.environ.get("MONEYGATE_BOOKS", Path.home() / "moneygate" / "books"))
LAYOUT = "head"
SMALL_MAX_SHARED = 5
OVERLAP_CEILING = 10
SAT_DOSE = "2560/10240,1280/5120"
ARMS = ("A1", "A2", "A3", "A4", "AG")   # AG: study-1 TRANSFER CHECK (descriptive; not a money-gate arm)
PKG_RE = re.compile(r"^PKG([3-8])-(group|value|rr)$")   # DESCRIPTIVE package arms (see the module docstring)
QB_CAP_AT_K26 = (5, 26)                                  # study 35's cap A: 5 rows at K 26 (studied there only)
SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
SALARY_CAP = 50_000


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict:
    return json.loads(Path(path).read_text())


# ----------------------------------------------------------------------------------------------------------- arms
def arm_flags(arm: str, own_file: str | None) -> list[str]:
    """The flags of §3 beyond the inputs (Week 4's union_args.txt minus --saturday-run/--t70-run/--live-dir/--group/
    --saturday-after/--out/--entries/--tail-sleeve). own_file None = the week has no point-in-time ownership input."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm}")
    main = "mean" if arm == "A2" else "pmo_x50"
    cap = "0.30" if arm == "A3" else "0.5"
    f = ["--saturday-dose", SAT_DOSE, "--mean-max-shared", "7", "--min-proj", "1.0", "--max-per-game", "4",
         "--min-salary", "49000", "--pmo", "0", "--pmo-cap-share", "0.5", "--main", main, "--main-cap-share", cap,
         "--sleeve-cap-share", "0.5", "--main-dst-cap", "0.25", "--sleeve-includes-main", "--mean-dst-cap", "0.25"]
    if own_file and arm in ("A1", "A3", "AG"):
        f += ["--main-own-tilt", "0.20", "--main-own-source", own_file]
    if arm == "AG":                       # A1 + study 1's per-game cap (production union_reselect --main-game-cap p3)
        f += ["--main-game-cap", "p3"]
    if own_file:
        f += ["--sleeve-source", "field", "--sleeve-field-mode", "top", "--sleeve-max-per-game", "5",
              "--sleeve-field-rows", "1", "--sleeve-own-source", own_file]
    else:
        f += ["--sleeve-source", "mean"]
    return f


def pkg_qb_cap_rows(K: int) -> int:
    """The QB cap translated by share from study 35's K 26 (a translation, not a studied setting)."""
    return max(1, int(round(QB_CAP_AT_K26[0] * K / QB_CAP_AT_K26[1])))


def pkg_flags(arm: str, e: dict, K: int, contests: Path) -> list[str]:
    m = PKG_RE.match(arm)
    if not m:
        raise ValueError(f"not a package arm: {arm}")
    ms, fill = m.group(1), m.group(2)
    f = ["--saturday-dose", SAT_DOSE, "--mean-max-shared", ms, "--min-proj", "1.0", "--max-per-game", "4",
         "--min-salary", "49000", "--pmo", "0", "--pmo-cap-share", "0.5", "--main", "mix", "--mix-portfolio", "mix",
         "--mix-plan", str(contests), "--mix-layout", LAYOUT, "--mix-fill", fill, "--main-cap-share", "0.5",
         "--sleeve-cap-share", "0.5", "--main-dst-cap", "0.25", "--sleeve-includes-main", "--mean-dst-cap", "0.25",
         "--main-qb-cap-rows", str(pkg_qb_cap_rows(K)), "--main-qb-cap-k", str(K)]
    own = e.get("own_file")
    if own:
        f += ["--sleeve-source", "field", "--sleeve-field-mode", "top", "--sleeve-max-per-game", "5",
              "--sleeve-field-rows", "1", "--sleeve-own-source", own]
    else:
        f += ["--sleeve-source", "mean"]
    if e.get("fp_proj_source"):
        f += ["--proj-source", e["fp_proj_source"]]
    return f


def known_arm(arm: str) -> bool:
    return arm in ARMS or bool(PKG_RE.match(arm))


# ------------------------------------------------------------------------------------------------------ contests
STRIP = ("ranks", "note", "track", "track_override", "priority", "line_percentile", "deep_line")


def route_contests(raw: list[dict], details: dict, millionaire: str, hold_fields: list[int]) -> tuple[list[dict], list[str]]:
    """Today's routing applied to a week's real contest list (see module docstring). Returns (contests, printout)."""
    import set_contest_tracks as SCT
    base = []
    for c in raw:
        n = {k: v for k, v in c.items() if k not in STRIP}
        n["contest_id"] = str(c["contest_id"])
        if n["contest_id"] == str(millionaire):
            n["track_override"] = "tail"
        base.append(n)
    if str(millionaire) not in {c["contest_id"] for c in base}:
        raise SystemExit(f"the Millionaire contest {millionaire} is not in the week's contest list")
    lines: list[str] = []
    sizes = {int(s) for s in hold_fields}
    present = {int(details[c["contest_id"]].get("max") or 0) for c in base if c["contest_id"] in details}
    sizes &= present                                     # set_contest_tracks refuses a size no contest has
    if sizes:
        base, bad = SCT.hold_on_main(base, details, sizes)
        if bad:
            raise SystemExit("hold-on-main refused: " + "; ".join(bad))
        lines.append(f"hold on main: field sizes {sorted(sizes)}")
    out, more, problems = SCT.decide_by_line(base, details, 0.02, deep_as_tail=True)
    if problems:
        raise SystemExit("TRACKS NOT SET: " + "; ".join(problems))
    return out, lines + more


def book_size(contests: list[dict]) -> tuple[int, int]:
    """(K, T) exactly as week_env.sh: K = max(1, rows_needed - sleeve), T = sleeve_size, head layout."""
    t = EL.sleeve_size(contests, LAYOUT)
    return max(1, EL.rows_needed(contests, LAYOUT) - t), t


def cmd_contests(cfg: dict, weeks: list[str]) -> dict:
    out = {}
    for w in weeks:
        e = cfg["weeks"][w]
        for key, f in (("contests_src_sha256", e["contests_src"]), ("details_sha256", e["details"])):
            if sha256(Path(f)) != e[key]:
                raise SystemExit(f"W{w}: {f} sha256 != the pinned {key}")
        raw = json.loads(Path(e["contests_src"]).read_text())
        raw = raw if isinstance(raw, list) else raw["contests"]
        details = json.loads(Path(e["details"]).read_text())
        routed, lines = route_contests(raw, details, e["millionaire_contest"], e.get("hold_on_main_fields", []))
        rec = {"week": int(w), "routing": lines}
        if e.get("contests_as_entered"):
            # Week 4: the entered file is used unchanged; the rule above must reproduce its tracks and order
            same = [(c["contest_id"], c["track"]) for c in routed] == [(str(c["contest_id"]), c["track"]) for c in raw]
            rec["rule_reproduces_entered_routing"] = same
            if not same:
                raise SystemExit(f"W{w}: the routing rule does not reproduce the entered contests.json")
            routed = raw
        K, T = book_size(routed)
        d = BOOKS / f"w{w}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "contests.json").write_text(json.dumps(routed, indent=1) + "\n")
        rec.update({"contests": len(routed), "entries": sum(int(c["entries"]) for c in routed), "K": K, "T": T,
                    "tail_contests": [c["contest_id"] for c in routed if c.get("track") == "tail"],
                    "rank_summary": EL.rank_summary(routed, LAYOUT), "contests_sha256": sha256(d / "contests.json")})
        (d / "contests_receipt.json").write_text(json.dumps(rec, indent=1) + "\n")
        print(f"W{w}: {rec['contests']} contests, {rec['entries']} entries, K {K} + T {T}; tail {rec['tail_contests']}")
        out[w] = rec
    return out


# --------------------------------------------------------------------------------------------------------- build
def check_inputs(e: dict) -> dict:
    sat, t70 = Path(e["saturday_run"]), Path(e["t70_run"])
    got = {"saturday_candidates": sha256(sat / "candidates.parquet"), "t70_candidates": sha256(t70 / "candidates.parquet"),
           "t70_frame": sha256(t70 / "frame.parquet"),
           "incumbent_player_scores.npy": sha256(t70 / "incumbent_player_scores.npy"),
           "corrected_hsim_player_scores.npy": sha256(t70 / "corrected_hsim_player_scores.npy")}
    bad = {k: (got[k][:12], e["sha256"][k][:12]) for k in got if got[k] != e["sha256"][k]}
    if bad:
        raise SystemExit(f"INPUTS REFUSED (content != pin): {bad}")
    if e.get("own_file") and sha256(Path(e["own_file"])) != e["own_sha256"]:
        raise SystemExit(f"INPUTS REFUSED: {e['own_file']} sha256 != pin")
    if e.get("fp_proj_source") and sha256(Path(e["fp_proj_source"])) != e.get("fp_proj_sha256"):
        raise SystemExit(f"INPUTS REFUSED: {e['fp_proj_source']} sha256 != the pinned fp_proj_sha256")
    return got


def union_cmd(cfg: dict, e: dict, arm: str, K: int, T: int, out: Path, contests: Path | None = None) -> tuple[list[str], dict]:
    flags = pkg_flags(arm, e, K, contests) if PKG_RE.match(arm) else arm_flags(arm, e.get("own_file"))
    args = ["--saturday-run", e["saturday_run"], "--t70-run", e["t70_run"], "--live-dir", str(Path(e["t70_run"]).parent),
            "--entries", str(K), "--tail-sleeve", str(T), *flags, "--out", str(out), "--rehearsal"]
    env = dict(os.environ, LIVE_FLEX_LATEST="1", PYTHONPATH=f"{cfg['lab_src']}:{PROD / 'src'}")
    return [cfg["lab_py"], str(PROD / "scripts" / "union_reselect.py"), *args], env


def lab_head(cfg: dict) -> str:
    src = Path(cfg["lab_src"]).parent
    r = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True)
    d = subprocess.run(["git", "-C", str(src), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True)
    if r.stdout.strip() != cfg["lab_sha"] or d.stdout.strip():
        raise SystemExit(f"lab src {src} is at {r.stdout.strip()[:12]} (dirty={bool(d.stdout.strip())}); the config pins {cfg['lab_sha'][:12]}")
    return r.stdout.strip()


def cmd_build(cfg: dict, weeks: list[str], arms: list[str], runs: int) -> None:
    lab = lab_head(cfg)
    for w in weeks:
        e = cfg["weeks"][w]
        check_inputs(e)
        rec = json.loads((BOOKS / f"w{w}" / "contests_receipt.json").read_text())
        K, T = rec["K"], rec["T"]
        for arm in arms:
            for r in range(1, runs + 1):
                out = BOOKS / f"w{w}" / arm / f"run{r}"
                if (out / "book.csv").is_file():
                    print(f"W{w} {arm} run{r}: exists, kept")
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                if not known_arm(arm):
                    raise SystemExit(f"unknown arm {arm}")
                cmd, env = union_cmd(cfg, e, arm, K, T, out, BOOKS / f"w{w}" / "contests.json")
                (out.parent / f"run{r}.cmd.json").write_text(json.dumps({"argv": cmd, "PYTHONPATH": env["PYTHONPATH"],
                                                                         "LIVE_FLEX_LATEST": "1", "lab_sha": lab}, indent=1) + "\n")
                print(f"W{w} {arm} run{r}: union_reselect K {K} T {T}", flush=True)
                p = subprocess.run(cmd, env=env, cwd=PROD, capture_output=True, text=True)
                (out.parent / f"run{r}.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
                if p.returncode != 0:
                    tail = (p.stdout + p.stderr).strip().splitlines()[-5:]
                    raise SystemExit(f"W{w} {arm} run{r}: union_reselect exit {p.returncode}:\n  " + "\n  ".join(tail))


# -------------------------------------------------------------------------------------------------------- layout
def read_book(path: Path) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(open(path, newline="")))
    return rows[0], rows[1:]


def layout_book(contests: list[dict], book: Path, stage: Path) -> dict:
    """enter_layout.write + check on the arm's book.csv; returns {contest_id: {rows, lineups, ...}}."""
    os.environ[EL.SMALL_OVERLAP_CEILING_ENV] = str(OVERLAP_CEILING)
    hdr, body = read_book(book)
    perm = (list(range(len(body))), {"order": "greedy"})
    stage.mkdir(parents=True, exist_ok=True)
    lines = EL.write(contests, book, stage, LAYOUT, perm, max_shared=SMALL_MAX_SHARED)
    bad = EL.check(contests, book, stage, LAYOUT, perm, max_shared=SMALL_MAX_SHARED)
    if bad:
        raise SystemExit(f"layout check failed for {book}: {bad}")
    rowmap = json.loads((stage / EL.ROWMAP_NAME).read_text())
    per = {}
    for c in contests:
        rows = rowmap[EL.label(c)]
        if len(rows) != int(c["entries"]):
            raise SystemExit(f"{EL.label(c)}: {len(rows)} rows for {c['entries']} entries")
        per[str(c["contest_id"])] = {"name": c["name"], "entries": int(c["entries"]), "track": c.get("track", "mean"),
                                     "rows": rows, "lineups": [body[i] for i in rows]}
    (stage / "layout.txt").write_text("\n".join(lines) + "\n")
    return per


def cmd_layout(weeks: list[str], arms: list[str]) -> None:
    for w in weeks:
        contests = json.loads((BOOKS / f"w{w}" / "contests.json").read_text())
        for arm in arms:
            d = BOOKS / f"w{w}" / arm
            per = layout_book(contests, d / "run1" / "book.csv", d / "enter")
            (d / "layout.json").write_text(json.dumps({"week": int(w), "arm": arm, "book_sha256": sha256(d / "run1" / "book.csv"),
                                                       "contests": per}, indent=1) + "\n")
            print(f"W{w} {arm}: {sum(len(v['rows']) for v in per.values())} entries in {len(per)} contests")


# ----------------------------------------------------------------------------------------------------- integrity
def dk_valid(row: list[str], frame) -> list[str]:
    """Independent DK classic check of one upload row (dk_player_id per slot) against the T-70 frame."""
    f = frame.assign(_k=frame.dk_player_id.astype(str).str.replace(r"\.0$", "", regex=True)).drop_duplicates("_k").set_index("_k")
    errs = []
    if len(row) != 9 or len(set(row)) != 9:
        return [f"{len(row)} cells / {len(set(row))} distinct"]
    miss = [x for x in row if x not in f.index]
    if miss:
        return [f"ids not in the frame: {miss}"]
    pos = [str(f.loc[x, "pos"]) for x in row]
    want = {"QB": ("QB",), "RB": ("RB",), "WR": ("WR",), "TE": ("TE",), "FLEX": ("RB", "WR", "TE"), "DST": ("DST",)}
    for s, p, x in zip(SLOTS, pos, row):
        if p not in want[s]:
            errs.append(f"{x} ({p}) in {s}")
    sal = sum(int(f.loc[x, "salary"]) for x in row)
    if sal > SALARY_CAP:
        errs.append(f"salary {sal} > {SALARY_CAP}")
    if len({str(f.loc[x, "game_id"]) for x in row}) < 2:
        errs.append("one game")
    return errs


def cmd_integrity(cfg: dict, weeks: list[str]) -> dict:
    import pandas as pd
    report = {}
    for w in weeks:
        e = cfg["weeks"][w]
        frame = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet")
        wk = {"inputs_sha256": check_inputs(e), "own_file_sha256": e.get("own_sha256"), "arms": {}}
        a1 = BOOKS / f"w{w}" / "A1" / "run1" / "book.csv"
        for arm in list(ARMS) + sorted(p.name for p in (BOOKS / f"w{w}").glob("PKG*") if PKG_RE.match(p.name)):
            d = BOOKS / f"w{w}" / arm
            if not (d / "run1" / "book.csv").is_file():
                continue
            shas = {r.name: sha256(r / "book.csv") for r in sorted(d.glob("run*")) if (r / "book.csv").is_file()}
            ctrl = {r.name: sha256(r / "book_main_control.csv") for r in sorted(d.glob("run*")) if (r / "book_main_control.csv").is_file()}
            _, body = read_book(d / "run1" / "book.csv")
            bad = {i + 1: v for i, row in enumerate(body) if (v := dk_valid(row, frame))}
            rec = json.loads((d / "run1" / "receipt.json").read_text())
            u = rec["config"]["union"]
            wk["arms"][arm] = {
                "book_sha256": shas, "deterministic": len(shas) >= 2 and len(set(shas.values())) == 1,
                "control_sha256": ctrl, "rows": len(body), "dk_invalid_rows": bad,
                "union_contract": rec.get("inputs", {}).get("book_contract"),
                "identical_to_A1": arm != "A1" and sha256(d / "run1" / "book.csv") == sha256(a1),
                "receipt_input_sha256_match": all(u["input_sha256"][k] == e["sha256"][k] for k in e["sha256"]),
                "main": u.get("main"), "own_term": (u.get("pmo_x50") or {}).get("own_term"),
                "field_sleeve": {k: (rec["config"].get("tail_sleeve") or {}).get("field", {}).get(k) for k in ("requested", "used", "failed", "split")},
                "sleeve_selector_used": (rec["config"].get("tail_sleeve") or {}).get("selector_used"),
                "sleeve_cap": (rec["config"].get("tail_sleeve") or {}).get("player_cap"),
                "layout_book_sha256": json.loads((d / "layout.json").read_text())["book_sha256"] if (d / "layout.json").is_file() else None}
        # A4 = A1's plain-mean control main (the union's own book_main_control): the term is the only difference
        a4 = BOOKS / f"w{w}" / "A4" / "run1" / "book.csv"
        a1c = BOOKS / f"w{w}" / "A1" / "run1" / "book_main_control.csv"
        if a4.is_file() and a1c.is_file():
            _, b4 = read_book(a4); _, bc = read_book(a1c)
            wk["A4_main_equals_A1_control"] = b4[:len(bc)] == bc
        if e.get("entered_union"):
            ent = Path(e["entered_union"]) / "book.csv"
            wk["A1_equals_entered_book"] = {"entered_sha256": sha256(ent), "A1_sha256": sha256(a1) if a1.is_file() else None,
                                            "equal": a1.is_file() and sha256(ent) == sha256(a1)}
        report[w] = wk
        print(f"W{w}: " + "; ".join(f"{a} det={v['deterministic']} sha={list(v['book_sha256'].values())[0][:12]} "
                                    f"dkbad={len(v['dk_invalid_rows'])} =A1:{v['identical_to_A1']}" for a, v in wk["arms"].items()))
    (BOOKS / "integrity.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    return report


# ------------------------------------------------------------------------------------------------ weekly A1 paper
def cmd_a1_paper(week_cfg: Path, out: Path) -> None:
    """Addendum 1 point 5: the A1 paper book for a live week (the rollback trigger's comparison). week_cfg is one
    week's entry of the config format (saturday_run, t70_run, sha256 pins, contests file already routed, own_file),
    plus lab_src / lab_sha / lab_py. Builds A1 into out/run1, lays it out into out/enter, writes out/layout.json."""
    e = json.loads(Path(week_cfg).read_text())
    cfg = {k: e[k] for k in ("lab_src", "lab_sha", "lab_py")}
    lab_head(cfg)
    check_inputs(e)
    contests = json.loads(Path(e["contests"]).read_text())
    contests = contests if isinstance(contests, list) else contests["contests"]
    K, T = book_size(contests)
    run = out / "run1"
    if run.exists():
        raise SystemExit(f"{run} exists")
    cmd, env = union_cmd(cfg, e, "A1", K, T, run)
    p = subprocess.run(cmd, env=env, cwd=PROD, capture_output=True, text=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run1.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
    if p.returncode:
        raise SystemExit(f"A1 paper: union_reselect exit {p.returncode}; see {out / 'run1.log'}")
    per = layout_book(contests, run / "book.csv", out / "enter")
    (out / "layout.json").write_text(json.dumps({"arm": "A1", "book_sha256": sha256(run / "book.csv"), "contests": per}, indent=1) + "\n")
    print(f"A1 paper book: {run / 'book.csv'} ({sha256(run / 'book.csv')[:12]}), K {K} T {T}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["contests", "build", "layout", "integrity", "all", "a1-paper"])
    ap.add_argument("--weeks", default="1,2,3,4")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--runs", type=int, default=2, help="builds per arm (2 = the §6 determinism check)")
    ap.add_argument("--week-config", type=Path); ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "a1-paper":
        if not (a.week_config and a.out):
            raise SystemExit("a1-paper needs --week-config and --out")
        cmd_a1_paper(a.week_config, a.out)
        return 0
    cfg = load_config()
    weeks = [w.strip() for w in a.weeks.split(",") if w.strip()]
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    if a.cmd in ("contests", "all"):
        cmd_contests(cfg, weeks)
    if a.cmd in ("build", "all"):
        cmd_build(cfg, weeks, arms, a.runs)
    if a.cmd in ("layout", "all"):
        cmd_layout(weeks, arms)
    if a.cmd in ("integrity", "all"):
        cmd_integrity(cfg, weeks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
