"""Render the study's JSON (week{w}.json, cross.json) as markdown tables for the document. Usage: summarize.py RUN_DIR"""
import json, sys
from pathlib import Path
R = Path(sys.argv[1]); weeks = sorted(int(p.stem[4:]) for p in R.glob("week*.json"))
def fmt(v): return "—" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))
for w in weeks:
    r = json.loads((R / f"week{w}.json").read_text()); d = r["describe"]; L = r["lines"]
    print(f"\n### Week {w}: winner {r['winner']:.2f}; field {r['field']:,}; within 10 points: {d['n']['cluster']} lineups"
          f"{' (' + str(d['unresolved_cluster']) + ' not buildable from the T-70 frame)' if d['unresolved_cluster'] else ''}; "
          f"top 100 at {L['top100']:.1f}; top 1% at {L['top1pct']:.1f}; projection {r['proj_source']}\n")
    print("| attribute | cluster value | cluster share | field share | lift | rule |\n|---|---|---|---|---|---|")
    for k, c in sorted(d["chosen"].items(), key=lambda kv: -kv[1]["lift"]):
        print(f"| {k} | {c['value']} | {c['share']:.2f} | {c['field']:.2f} | {c['lift']:.2f} | {'yes' if c['use'] else ''} |")
    print("\n| layer | rules added | oracle | first within 10 | first top 100 | first top 1% | best in budget | built |\n|---|---|---|---|---|---|---|---|")
    prev = {}
    for e in r["layers"]:
        add = {k: v for k, v in e["rules"].items() if prev.get(k) != v}; prev = e["rules"]; en = e.get("enum")
        f = en["first"] if en else {}
        print(f"| {e['layer']} | {', '.join(f'{k}={v}' for k, v in add.items()) or '(none)'} | {fmt(e['oracle'])} | {fmt(f.get('hit')) if en else 'cannot reach'} | {fmt(f.get('top100'))} | {fmt(f.get('top1pct'))} | {fmt(en['best_actual']) if en else '—'} | {en['n_built'] if en else '—'} |")
    hit = next((e for e in r["layers"] if e.get("enum") and e["enum"]["first"]["hit"]), None)
    if hit:
        print(f"\nThe lineup that landed within 10 (built #{hit['enum']['first']['hit']} under `{hit['layer']}`, {hit['enum']['hit_lineup'] and sum(float(s.split()[-1]) for s in hit['enum']['hit_lineup']):.1f} points):")
        for s in hit["enum"]["hit_lineup"]: print(f"- {s}")
    else:
        last = [e for e in r["layers"] if e.get("enum")]
        if last:
            b = max(last, key=lambda e: e["enum"]["best_actual"]); print(f"\nNo lineup within 10 in the budget; the best built was {b['enum']['best_actual']:.1f} under `{b['layer']}`:")
            for s in b["enum"]["best_lineup"]: print(f"- {s}")
cp = R / "cross.json"
if cp.exists():
    c = json.loads(cp.read_text()); print("\n### Cross-week\n\n| rules from | applied to | oracle | winner | first within 10 | first top 100 | first top 1% | best in budget |\n|---|---|---|---|---|---|---|---|")
    for k, e in c.items():
        a, b = k.split("->"); en = e.get("enum"); f = en["first"] if en else {}
        print(f"| W{a} | W{b} | {fmt(e['oracle'])} | {e['winner']:.1f} | {fmt(f.get('hit')) if en else '—'} | {fmt(f.get('top100'))} | {fmt(f.get('top1pct'))} | {fmt(en['best_actual']) if en else '—'} |")
