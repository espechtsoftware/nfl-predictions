#!/usr/bin/env bash
# Outcome-blind W4 check of an option ON TOP OF the armed W5 version (package + te1_low1), on his W5-style FP book (W4
# inputs, the tracked reports/2026-10-08-s71-flag/w4_union_run.sh). Two known-answer gates: OFF reproduces a4ab2839 and
# ARMED (the package + the row rules, the option off) reproduces the 10-09 13:36 armed check's book e1c8f9f7; then ON.
# Reads book composition and FP projections only: no points, ranks or results.
#   bash flag_w4_check_armed.sh <production worktree> <tag> <option args...>
set -uo pipefail
C=${1:?worktree}; TAG=${2:?tag}; shift 2
O=$HOME/rehearsals/flagcheck-$TAG-$(date -u +%Y%m%dT%H%M%SZ)
R=$C/reports/2026-10-08-s71-flag/w4_union_run.sh
OWN=$HOME/week4-sunday/ownership_fp-20261004t1550z-d800-32cdb61.csv
ARMED=(--main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source "$OWN" --main-own-cap-fallback-share 0.5
       --mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3)
[[ -f "$R" && -z "$(git -C "$C" status --porcelain)" ]] || { echo "STOP: $C lacks the runner or is dirty"; exit 1; }
[[ "$(sha256sum "$OWN" | cut -c1-8)" == 0ec90a6b ]] || { echo "STOP: the W4 FP ownership file changed"; exit 1; }
mkdir -p "$O"
echo "== $TAG W4 check at $(git -C "$C" rev-parse --short HEAD) $(date +%H:%M:%S); option: $*"
bash "$R" "$C" "$O/off" > "$O/off.log" 2>&1; echo "off rc $? $(sha256sum "$O/off/book.csv" | cut -c1-16) (known answer a4ab283949254d12)"
[[ "$(sha256sum "$O/off/book.csv" | cut -c1-16)" == "a4ab283949254d12" ]] || { echo "STOP: OFF does not reproduce the known book"; exit 1; }
bash "$R" "$C" "$O/armed" "${ARMED[@]}" > "$O/armed.log" 2>&1; echo "armed rc $? $(sha256sum "$O/armed/book.csv" | cut -c1-16) (known answer e1c8f9f7f1d15249)"
[[ "$(sha256sum "$O/armed/book.csv" | cut -c1-16)" == "e1c8f9f7f1d15249" ]] || { echo "STOP: ARMED does not reproduce the 13:36 armed book"; exit 1; }
bash "$R" "$C" "$O/on" "${ARMED[@]}" "$@" > "$O/on.log" 2>&1; echo "on rc $?"; grep -h -E "ONE CATCHER|ROW RULES|OWN CAP|REFUSED|NOT APPLIED|Traceback" "$O/on.log" | head -5 | cut -c1-240
/home/erich/projects/nfl-predictions/.venv/bin/python - "$O" <<'PYEOF'
import csv, json, sys
from collections import Counter
from pathlib import Path
import pandas as pd
O = Path(sys.argv[1])
fr = pd.read_parquet(O / "off" / "frame.parquet").drop_duplicates("id")
dk = lambda x: str(x).removesuffix(".0")
pos = {dk(k): str(p) for k, p in zip(fr["dk_player_id"], fr["pos"])}
team = {dk(k): str(t) for k, t in zip(fr["dk_player_id"], fr["team"])}
fid = {dk(k): str(i) for k, i in zip(fr["dk_player_id"], fr["id"])}
def proj(d):
    p = dict(zip(fr["id"].astype(str), pd.to_numeric(fr["mean_projection"], errors="coerce")))
    s = pd.read_csv(d / "proj_source.csv", dtype={"id": str}); p.update({i: float(v) for i, v in zip(s["id"], s["fp"]) if i in p})
    return p
def book(d):
    hdr, *rows = list(csv.reader(open(d / "book.csv")))
    assert hdr == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"], hdr
    return [[x.strip() for x in r] for r in rows]
def tags(d):
    return [e["tag"] for e in json.loads((d / "book.json").read_text())["entries"]]
def stats(d):
    rows, p, tg = book(d), proj(d), tags(d)
    def pair(r):
        q = next(i for i in r if pos[i] == "QB")
        c = Counter(team[i] for i in r if pos[i] in ("WR", "TE") and team[i] != team[q]); return any(v >= 2 for v in c.values())
    fx = Counter(pos[r[7]] for r in rows)
    bc = [k for k, t in enumerate(tg) if t in ("mix_B", "mix_C")]
    return {"rows": len(rows), "cells": dict(Counter(tg)), "pair_rows": sum(pair(r) for r in rows),
            "pair_rows_bc": sum(pair(rows[k]) for k in bc), "pair_at": [k for k, r in enumerate(rows) if pair(r)],
            "tes_per_row": round(sum(sum(pos[i] == "TE" for i in r) for r in rows) / len(rows), 2),
            "flex": f"{fx['WR']}/{fx['TE']}/{fx['RB']}", "distinct": len({i for r in rows for i in r}),
            "fp_proj_per_row": round(sum(sum(p[fid[i]] for i in r) for r in rows) / len(rows), 2)}
a, b = stats(O / "armed"), stats(O / "on")
print("ARMED:", json.dumps(a)); print("ON:   ", json.dumps(b))
ra = set(map(frozenset, book(O / "armed"))); on_rows = book(O / "on"); tg = tags(O / "on")
changed = [k for k, r in enumerate(on_rows) if frozenset(r) not in ra]
print(f"rows of ON not in ARMED: {len(changed)} of {len(on_rows)}; their cells: {dict(Counter(tg[k] for k in changed))}")
sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
import importlib.util
from nfl_dfs.inference.enter_layout import assign_ranks
spec = importlib.util.spec_from_file_location("p3s", "/home/erich/projects/nfl-predictions/scripts/p3_score.py")
P3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(P3)
plan = Path.home() / "week5-sunday/contests.json"
pj = json.loads(plan.read_text()); contests = pj if isinstance(pj, list) else pj["contests"]
big = P3.plan_big(Path.home() / "s24-panel/plan-week5-rev6-s24.json")
assert {str(c["contest_id"]) for c in contests} == set(big)
ranks = assign_ranks(contests, "head")
def seats(k):
    cs = [str(c["contest_id"]) for c, rr in zip(contests, ranks) if k in rr]
    return f"{k}:{len(cs)}c/{sum(1 for c in cs if big[c][0])}big"
print("changed positions under his W5 plan (contests / big):", " ".join(seats(k) for k in changed) or "none")
mix = json.loads((O / "on" / "receipt.json").read_text())["config"]["union"]["mix"]["mix"]
for k in ("one_catcher", "one_catcher_source", "row_rules", "row_rules_source"):
    if k in mix:
        v = mix[k]; v = {x: v[x] for x in v if x not in ("ruled_rows",)} if isinstance(v, dict) else v
        print(f"receipt {k}:", json.dumps(v)[:500])
PYEOF
echo "== done $(date +%H:%M:%S) $O"
