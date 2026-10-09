#!/usr/bin/env bash
# Outcome-blind W4 check of an unmerged production option on his W5-style FP book (W4 inputs, the W5 arming via the tracked
# reports/2026-10-08-s71-flag/w4_union_run.sh). OFF must reproduce the s73 ack's off book a4ab2839... byte for byte (the
# known-answer gate); then the flag. Reads book composition and FP projections only: no points, ranks or results.
#   bash flag_w4_check.sh <production worktree at the option's commit> <tag> <flag args...>
set -uo pipefail
C=${1:?worktree}; TAG=${2:?tag}; shift 2
O=$HOME/rehearsals/flagcheck-$TAG-$(date -u +%Y%m%dT%H%M%SZ)
R=$C/reports/2026-10-08-s71-flag/w4_union_run.sh
[[ -f "$R" && -z "$(git -C "$C" status --porcelain)" ]] || { echo "STOP: $C lacks the runner or is dirty"; exit 1; }
mkdir -p "$O"
echo "== $TAG W4 check at $(git -C "$C" rev-parse --short HEAD) $(date +%H:%M:%S); flag: $*"
bash "$R" "$C" "$O/off" > "$O/off.log" 2>&1; echo "off rc $? $(sha256sum "$O/off/book.csv" | cut -c1-16) (known answer a4ab283949254d12)"
[[ "$(sha256sum "$O/off/book.csv" | cut -c1-16)" == "a4ab283949254d12" ]] || { echo "STOP: OFF does not reproduce the known book"; exit 1; }
bash "$R" "$C" "$O/on" "$@" > "$O/on.log" 2>&1; echo "on rc $?"; grep -h -E "QB ALONE|ONE CATCHER|FLEX WR|REFUSED|Traceback" "$O/on.log" | head -3
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
    ps = d / "proj_source.csv"
    if ps.is_file():
        s = pd.read_csv(ps, dtype={"id": str}); p.update({i: float(v) for i, v in zip(s["id"], s["fp"]) if i in p})
    return p
def book(d):
    hdr, *rows = list(csv.reader(open(d / "book.csv")))
    assert hdr == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"], hdr
    return [[x.strip() for x in r] for r in rows]
def stats(d):
    rows, p = book(d), proj(d)
    def mates(r):
        q = next(i for i in r if pos[i] == "QB"); return sum(1 for i in r if pos[i] in ("WR", "TE") and team[i] == team[q])
    def nonqb_pair(r):
        q = next(i for i in r if pos[i] == "QB")
        c = Counter(team[i] for i in r if pos[i] in ("WR", "TE") and team[i] != team[q]); return any(v >= 2 for v in c.values())
    fx = Counter(pos[r[7]] for r in rows)
    return {"rows": len(rows), "qb_alone": sum(mates(r) == 0 for r in rows), "qb2": sum(mates(r) >= 2 for r in rows),
            "nonqb_pair": sum(nonqb_pair(r) for r in rows), "flex": f"{fx['WR']}/{fx['TE']}/{fx['RB']}",
            "fp_proj_per_row": round(sum(sum(p[fid[i]] for i in r) for r in rows) / len(rows), 2),
            "qb_alone_at": [k for k, r in enumerate(rows) if mates(r) == 0],
            "nonqb_pair_at": [k for k, r in enumerate(rows) if nonqb_pair(r)]}
a, b = stats(O / "off"), stats(O / "on")
print("OFF:", json.dumps(a)); print("ON: ", json.dumps(b))
ra, rb = set(map(frozenset, book(O / "off"))), set(map(frozenset, book(O / "on")))
print(f"rows of ON not in OFF: {len(rb - ra)} of {len(rb)}")
# his real W5 plan (Rev6, the runner's --mix-plan): each changed / ruled position -> how many contests it is dealt into under
# the head layout (enter_layout.assign_ranks, before the small-contest overlap limit) and how many of them are big
# (p3_score.plan_big). Counts only: no contest names, no stakes.
import importlib.util
sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
from nfl_dfs.inference.enter_layout import assign_ranks
spec = importlib.util.spec_from_file_location("p3s", "/home/erich/projects/nfl-predictions/scripts/p3_score.py")
P3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(P3)
plan = Path.home() / "week5-sunday/contests.json"
pj = json.loads(plan.read_text()); contests = pj if isinstance(pj, list) else pj["contests"]
s24 = Path.home() / "s24-panel/plan-week5-rev6-s24.json"          # the converted Rev6 plan carries the big flags (s38_plan)
big = P3.plan_big(s24)
assert {str(c["contest_id"]) for c in contests} == set(big), "the s24 plan's contests differ from the W5 plan's"
ranks = assign_ranks(contests, "head")
def seats(k):
    cs = [str(c["contest_id"]) for c, rr in zip(contests, ranks) if k in rr]
    return f"pos {k}: {len(cs)} contests, {sum(1 for c in cs if big[c][0])} big"
on_rows = book(O / "on")
changed = [k for k, r in enumerate(on_rows) if frozenset(r) not in ra]
print("plan sha", __import__("hashlib").sha256(plan.read_bytes()).hexdigest()[:8], "; big contests", sum(1 for v in big.values() if v[0]), "of", len(big))
print("QB-alone rows in ON:", "; ".join(seats(k) for k in b["qb_alone_at"]) or "none")
def rb_mate(r):
    q = next(i for i in r if pos[i] == "QB"); return any(pos[i] == "RB" and team[i] == team[q] for i in r)
print("QB-alone rows with an RB teammate:", sum(rb_mate(on_rows[k]) for k in b["qb_alone_at"]), "of", len(b["qb_alone_at"]))
print("non-QB-pair rows: OFF at", a["nonqb_pair_at"], "| ON at", b["nonqb_pair_at"])
print("first 8 positions under the plan:", "; ".join(seats(k) for k in range(8)))
mix = json.loads((O / "on" / "receipt.json").read_text())["config"]["union"]["mix"]["mix"]
for k in ("qb_alone", "one_catcher", "flex_wr"):
    if mix.get(k):
        blk = {x: mix[k][x] for x in mix[k] if x not in ("ruled_rows", "rules")}
        print(f"receipt {k}:", json.dumps(blk)[:400])
PYEOF
echo "== done $(date +%H:%M:%S) $O"
