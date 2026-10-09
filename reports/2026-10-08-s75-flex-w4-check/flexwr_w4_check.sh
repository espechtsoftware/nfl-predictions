#!/usr/bin/env bash
# Outcome-blind: what does study 75's forced WR flex displace in a W5-style FP book? W4 inputs with the W5 arming
# (reports/2026-10-08-s71-flag/w4_union_run.sh), the flag branch 09e93be1: OFF (must reproduce the s73 ack's off book
# a4ab2839... byte for byte = a known-answer gate) and --mix-flex-wr-rows 8. Reads book composition only; no scores.
set -uo pipefail
C=/home/erich/projects/.nfl-predictions-worktrees/flexwr-w4-check-20261008
O=$HOME/rehearsals/flexwr-w4-check-20261008
R=$C/reports/2026-10-08-s71-flag/w4_union_run.sh
[[ -e "$O" ]] && { echo "STOP: $O exists"; exit 1; }
mkdir -p "$O"
echo "== flex WR W4 check at $(git -C "$C" rev-parse --short HEAD) $(date +%H:%M:%S)"
bash "$R" "$C" "$O/off" > "$O/off.log" 2>&1; echo "off rc $? $(sha256sum "$O/off/book.csv" | cut -c1-16) (known answer a4ab283949254d12)"
[[ "$(sha256sum "$O/off/book.csv" | cut -c1-16)" == "a4ab283949254d12" ]] || { echo "STOP: OFF does not reproduce the s73 ack's off book"; exit 1; }
bash "$R" "$C" "$O/fx8" --mix-flex-wr-rows 8 > "$O/fx8.log" 2>&1; echo "fx8 rc $?"; grep -h "FLEX WR" "$O/fx8.log" | head -2
/home/erich/projects/nfl-predictions/.venv/bin/python - "$O" <<'PYEOF'
import csv, json, sys
from collections import Counter
from pathlib import Path
import pandas as pd
O = Path(sys.argv[1])
fr = pd.read_parquet(O / "off" / "frame.parquet").drop_duplicates("id")
pos = {str(k).removesuffix(".0"): str(p) for k, p in zip(fr["dk_player_id"], fr["pos"])}
def flex(row):                                     # the FLEX slot (column 8 of QB,RB,RB,WR,WR,WR,TE,FLEX,DST)
    return pos[row[7]]
def book(d):
    hdr, *rows = list(csv.reader(open(d / "book.csv")))
    assert hdr == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"], hdr
    return [[x.strip() for x in r] for r in rows]
a, b = book(O / "off"), book(O / "fx8")
fa, fb = Counter(flex(r) for r in a), Counter(flex(r) for r in b)
print(f"book rows: off {len(a)}, fx8 {len(b)}; rows of fx8 not in off: {len(set(map(frozenset, b)) - set(map(frozenset, a)))}")
print("flex of the 26 book rows (WR / TE / RB):", f"off {fa['WR']} / {fa['TE']} / {fa['RB']}", f"| fx8 {fb['WR']} / {fb['TE']} / {fb['RB']}")
fx = json.loads((O / "fx8" / "receipt.json").read_text())["config"]["union"]["mix"]["mix"].get("flex_wr")
print("receipt flex_wr:", json.dumps(fx)[:300])
PYEOF
echo "== done $(date +%H:%M:%S)"
