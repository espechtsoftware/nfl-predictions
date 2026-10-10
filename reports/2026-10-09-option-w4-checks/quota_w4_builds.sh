#!/usr/bin/env bash
# Outcome-blind W4 known-answer builds of study 95's shape arms on the ARMED version (package + te1_low1 + ONECATCH), so a
# morning choice of shape percentages has been built once on his real book before arming. Gates: ARMED (no quotas) and LIVE
# (the default quotas spelled out) both reproduce the 18:33 ONECATCH book 293d9465. Then NO_x / ONLY_x.
#   bash quota_w4_builds.sh <production worktree carrying the zero-quota parser>
set -uo pipefail
C=${1:?worktree}
O=$HOME/rehearsals/quotacheck-$(date -u +%Y%m%dT%H%M%SZ)
R=$C/reports/2026-10-08-s71-flag/w4_union_run.sh
OWN=$HOME/week4-sunday/ownership_fp-20261004t1550z-d800-32cdb61.csv
ARMED=(--main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source "$OWN" --main-own-cap-fallback-share 0.5
       --mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-one-catcher-all)
[[ -f "$R" && -z "$(git -C "$C" status --porcelain)" ]] || { echo "STOP: $C lacks the runner or is dirty"; exit 1; }
[[ "$(sha256sum "$OWN" | cut -c1-8)" == 0ec90a6b ]] || { echo "STOP: the W4 FP ownership file changed"; exit 1; }
mkdir -p "$O"; echo "== quota W4 builds at $(git -C "$C" rev-parse --short HEAD) $(date +%H:%M:%S) -> $O"
declare -A Q=(
  [LIVE]="A1=0.3,A2=0.14,B=0.28,C=0.28"
  [NO_A1]="A1=0,A2=0.20000000000000004,B=0.4000000000000001,C=0.4000000000000001"
  [NO_A2]="A1=0.3488372093023256,A2=0,B=0.32558139534883723,C=0.32558139534883723"
  [NO_B]="A1=0.4166666666666667,A2=0.19444444444444448,B=0,C=0.38888888888888895"
  [NO_C]="A1=0.4166666666666667,A2=0.19444444444444448,B=0.38888888888888895,C=0"
  [ONLY_A1]="A1=1,A2=0,B=0,C=0" [ONLY_A2]="A1=0,A2=1,B=0,C=0" [ONLY_B]="A1=0,A2=0,B=1,C=0" [ONLY_C]="A1=0,A2=0,B=0,C=1")
bash "$R" "$C" "$O/ARMED" "${ARMED[@]}" > "$O/ARMED.log" 2>&1; echo "ARMED rc $? $(sha256sum "$O/ARMED/book.csv" | cut -c1-16) (known answer 293d9465eec54e4f)"
[[ "$(sha256sum "$O/ARMED/book.csv" | cut -c1-16)" == "293d9465eec54e4f" ]] || { echo "STOP: ARMED does not reproduce the 18:33 ONECATCH book"; exit 1; }
for a in LIVE NO_A1 NO_A2 NO_B NO_C ONLY_A1 ONLY_A2 ONLY_B ONLY_C; do
  bash "$R" "$C" "$O/$a" "${ARMED[@]}" --mix-cell-quotas "${Q[$a]}" > "$O/$a.log" 2>&1; rc=$?
  echo "$a rc $rc $( [[ -f "$O/$a/book.csv" ]] && sha256sum "$O/$a/book.csv" | cut -c1-16) quotas ${Q[$a]}"
  [[ $a != LIVE || "$(sha256sum "$O/LIVE/book.csv" | cut -c1-16)" == "293d9465eec54e4f" ]] || { echo "STOP: the spelled-out LIVE quotas do not reproduce ARMED"; exit 1; }
done
/home/erich/projects/nfl-predictions/.venv/bin/python - "$O" <<'PYEOF'
import csv, json, sys
from collections import Counter
from pathlib import Path
import pandas as pd
O = Path(sys.argv[1])
fr = pd.read_parquet(O / "ARMED" / "frame.parquet").drop_duplicates("id")
dk = lambda x: str(x).removesuffix(".0")
pos = {dk(k): str(p) for k, p in zip(fr["dk_player_id"], fr["pos"])}
team = {dk(k): str(t) for k, t in zip(fr["dk_player_id"], fr["team"])}
fid = {dk(k): str(i) for k, i in zip(fr["dk_player_id"], fr["id"])}
def book(d):
    hdr, *rows = list(csv.reader(open(d / "book.csv"))); return [[x.strip() for x in r] for r in rows]
def proj(d):
    p = dict(zip(fr["id"].astype(str), pd.to_numeric(fr["mean_projection"], errors="coerce")))
    s = pd.read_csv(d / "proj_source.csv", dtype={"id": str}); p.update({i: float(v) for i, v in zip(s["id"], s["fp"]) if i in p})
    return p
ref = set(map(frozenset, book(O / "ARMED")))
print(f"{'arm':8} {'cells A1/A2/B/C':16} {'FP/row':>7} {'distinct':>8} {'changed':>7} {'QBs':>4} {'oc ruled':>8} {'passes':>6}")
for a in ("ARMED", "LIVE", "NO_A1", "NO_A2", "NO_B", "NO_C", "ONLY_A1", "ONLY_A2", "ONLY_B", "ONLY_C"):
    d = O / a
    if not (d / "book.csv").is_file():
        print(f"{a:8} (no book)"); continue
    rows, p = book(d), proj(d)
    tags = Counter(e["tag"].removeprefix("mix_") for e in json.loads((d / "book.json").read_text())["entries"])
    mix = json.loads((d / "receipt.json").read_text())["config"]["union"]["mix"]["mix"]
    oc = mix.get("one_catcher") or {}
    qbs = len({next(i for i in r if pos[i] == "QB") for r in rows})
    print(f"{a:8} {'/'.join(str(tags.get(c, 0)) for c in ('A1','A2','B','C')):16} "
          f"{sum(sum(p[fid[i]] for i in r) for r in rows) / len(rows):7.2f} {len({i for r in rows for i in r}):8d} "
          f"{sum(frozenset(r) not in ref for r in rows):7d} {qbs:4d} {oc.get('ruled_solves', '-')!s:>8} {mix.get('passes_to_A1', '-')!s:>6}")
PYEOF
echo "== done $(date +%H:%M:%S) $O"
