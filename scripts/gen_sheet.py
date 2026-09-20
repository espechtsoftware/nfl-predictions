"""Generate the Late-Swap Sheet page from a lineup-sheet CSV, an upload CSV and TODAY-30-LATEST.md.
Usage: gen_sheet.py SHEET_CSV UPLOAD_CSV TODAY_MD OUT_HTML STATUS_LABEL [QB_FLAGS_CSV]
QB_FLAGS_CSV (optional, from qb_flags.sh): backup QBs with starter-sized projections; kept lineups whose
QB is on it are marked, with the team's depth-1 QB and his status. Information only -- the swap is the operator's call.
"""
import csv, html, re, sys
sheet, upload, today, out, status = sys.argv[1:6]
qb_flags = {}
if len(sys.argv) > 6 and sys.argv[6]:
    raw = list(csv.DictReader(open(sys.argv[6])))
    if raw and "role" in raw[0]:
        # qb_flags.py format (shared classifier): synthesize the page's fields; flag backups and unavailable/risky QBs only
        primary = {r["team"]: r for r in raw if r.get("role") == "primary"}
        VERD = {"gated": "BEHIND-HEALTHY-STARTER", "out": "OUT"}
        AMB = {"doubtful": "STARTER-DOUBTFUL", "questionable": "STARTER-QUESTIONABLE", "no-depth-1": "NO-DEPTH-1", "all-out": "NO-DEPTH-1"}
        for r in raw:
            own = (r.get("injury_status") or "").strip() or ({"D": "Doubtful", "Q": "Questionable", "O": "Out"}.get((r.get("dk_status") or "").strip().upper(), ""))
            role = r.get("role", "")
            if role == "gated": verdict = VERD["gated"]
            elif role == "out": verdict = VERD["out"]
            elif role == "ambiguous": verdict = AMB.get(r.get("team_class", ""), "NO-DEPTH-1")
            elif role == "primary" and own.upper() in ("DOUBTFUL", "QUESTIONABLE"): verdict = "STARTER-" + own.upper()
            else: continue
            p = primary.get(r["team"])
            qb_flags[r["qb_name"].strip()] = {"qb_name": r["qb_name"].strip(), "team": r["team"], "salary": r.get("salary", ""), "proj": r.get("proj", ""),
                                              "depth_rank": str(r.get("depth_rank", "")).replace(".0", ""), "injury_status": own,
                                              "starter_name": (p["qb_name"] if p and p["qb_name"] != r["qb_name"] else ""),
                                              "starter_injury_status": ((p.get("injury_status") or "").strip() if p else ""), "verdict": verdict, "role": role}
    else:
        for f in raw:
            qb_flags[f["qb_name"].strip()] = f
swaps = {}   # optional 7th arg: swap_suggest.py output, keyed by book row (= keepers rank)
if len(sys.argv) > 7 and sys.argv[7]:
    for s in csv.DictReader(open(sys.argv[7])):
        swaps[str(s["row"])] = s
rows = list(csv.DictReader(open(sheet)))
ids = list(csv.reader(open(upload)))
id_hdr, id_rows = ids[0], ids[1:]
md = open(today).read().splitlines()
first = md[0] if md else ""
repl_fail = next((l.strip() for l in md if "REPLACEMENT FAILED" in l), "")
repl_line = next((l.strip() for l in md if l.strip().startswith("REPLACEMENT STEP:")), "")
m = re.search(r"Source run (\S+), (K\d+), built (\S+)", first)
run, k, built = (m.group(1), m.group(2), m.group(3)) if m else ("?", "?", "?")
import json, os
ids_by_label = {}
cj = os.path.join(os.path.dirname(os.path.abspath(today)), "contests.json")
if os.path.exists(cj):
    for c in json.load(open(cj)):
        ids_by_label[str(c.get("label") or c.get("name") or "")] = str(c.get("id") or c.get("contest_id") or "")
contests = []   # (label, contest_id, entries, keep_lo, keep_hi, fill_lo, fill_hi)
for line in md:
    w2 = re.match(r"\s*(.+?): (\d+) entries, keep rows (\d+)-(\d+)(?: \(vetted ranks \d+-\d+\))?, fill rows (\d+)-(\d+)", line)
    w1 = re.match(r"\s*(.+?) (\d{9}) \((\d+) entries, keep rows (\d+)-(\d+), withdraw (\d+)-(\d+)\)", line)
    if w2:
        lab, n, klo, khi, flo, fhi = w2.groups()
        ml = re.match(r"(.+)-(\d{9})$", lab)            # the writer prints "{name}-{contest_id}"
        name, cid = (ml.group(1), ml.group(2)) if ml else (lab, ids_by_label.get(lab, ""))
        contests.append((name, cid, n, klo, khi, flo, fhi))
    elif w1:
        lab, cid, n, klo, khi, flo, fhi = w1.groups(); contests.append((lab, cid, n, klo, khi, flo, fhi))
POS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
def qb_of(s):
    return s.split("|")[0].strip()
def lineup_html(s):
    names = [n.strip() for n in s.split("|")]
    cells = []
    for i, n in enumerate(names):
        chip = ' <em class="chip">backup QB</em>' if i == 0 and n in qb_flags else ""
        cells.append(f'<span class="p"><b>{POS[i] if i < 9 else ""}</b>{html.escape(n)}{chip}</span>')
    return "".join(cells)
tr = "\n".join(
    f'<tr{" class=flag" if qb_of(r["lineup"]) in qb_flags else ""}><td class="rk">{r["rank"]}</td><td class="lu">{lineup_html(r["lineup"])}</td>'
    f'<td class="num">{int(r["salary"]):,}</td><td class="num">{float(r["inc_p220"])*100:.2f}</td><td class="num">{float(r["hsim_p220"])*100:.2f}</td></tr>'
    for r in rows)
flagged = [r for r in rows if qb_of(r["lineup"]) in qb_flags]
VERDICT = {"BEHIND-HEALTHY-STARTER": "not expected to start — scores zero unless the starter is hurt",
           "STARTER-OUT": "the listed starter is OUT — this QB may be the real starter; confirm who starts",
           "STARTER-DOUBTFUL": "the listed starter is Doubtful — may start; confirm",
           "STARTER-QUESTIONABLE": "the listed starter is Questionable — probably does not start; confirm",
           "NO-DEPTH-1": "no depth-chart starter on file — confirm"}
def st(x):
    return html.escape(x) if x else "healthy"
def is_bad(q):
    f = qb_flags[q]
    return f.get("verdict") == "BEHIND-HEALTHY-STARTER" or f.get("injury_status", "").strip().upper() in ("OUT", "DOUBTFUL", "IR", "QUESTIONABLE")
def swap_html(r):
    """Cap-feasible swap for rows that need action (from swap_suggest.py); nothing for fill-in starters."""
    q = qb_of(r["lineup"]); s = swaps.get(str(r["rank"]))
    if not s or not is_bad(q):
        return ""
    if s.get("single_swaps") and s["single_swaps"] != "NONE":
        return f'<div class="swap">Fits under the cap one-for-one: {html.escape(s["single_swaps"])}</div>'
    if s.get("pair_swap"):
        return f'<div class="swap">No starter fits one-for-one (slack ${int(s["slack"]):,}). Two-player swap: {html.escape(s["pair_swap"])}</div>'
    return '<div class="swap">No cap-feasible swap found.</div>'
fl = "\n".join(
    f'<tr><td class="rk">{r["rank"]}</td><td>{html.escape(qb_of(r["lineup"]))} <span class="eyebrow">depth {html.escape(qb_flags[qb_of(r["lineup"])]["depth_rank"])} · proj {html.escape(qb_flags[qb_of(r["lineup"])]["proj"])}</span></td>'
    f'<td>{html.escape(qb_flags[qb_of(r["lineup"])]["starter_name"] or "?")} <span class="eyebrow">{st(qb_flags[qb_of(r["lineup"])]["starter_injury_status"])}</span></td>'
    f'<td>{html.escape(VERDICT.get(qb_flags[qb_of(r["lineup"])].get("verdict", ""), qb_flags[qb_of(r["lineup"])].get("verdict", "")))}'
    f'{(" — <b>and he is himself " + html.escape(qb_flags[qb_of(r["lineup"])].get("injury_status", "")) + "</b>") if qb_flags[qb_of(r["lineup"])].get("injury_status", "").strip() else ""}'
    f'{swap_html(r)}</td></tr>'
    for r in flagged)
n_bad = sum(1 for r in flagged if is_bad(qb_of(r["lineup"])))
beyond = [s for k, s in sorted(swaps.items(), key=lambda kv: int(kv[0])) if int(k) > len(rows)]
beyond_html = ("" if not beyond else
               '<p class="eyebrow" style="margin:8px 0 0">Flagged rows beyond the keepers (auto-filled rows; swap only if you want): ' +
               "; ".join(f'row {html.escape(s["row"])} {html.escape(s["qb"])} ({html.escape(s.get("verdict", ""))}{(" — himself " + html.escape(s["own_status"])) if s.get("own_status") else ""})' for s in beyond) + '</p>')
qb_section = (f'<section><div class="warn">Backup-QB check: {len(flagged)} kept lineup{"s" if len(flagged) != 1 else ""} start a QB listed as a backup — '
              f'{n_bad} behind a healthy starter or themselves Out/Doubtful (those score zero if he does not play), {len(flagged) - n_bad} where the starter is hurt and this backup may start. '
              f'Your call — confirm who starts before lock.</div>'
              f'<div class="tw"><table><thead><tr><th class="rk">#</th><th>Lineup QB</th><th>Listed starter · status</th><th>What it means</th></tr></thead><tbody>\n{fl}\n</tbody></table></div>{beyond_html}</section>'
              if flagged else (f'<section><div class="ok">Backup-QB check: none of the kept lineups starts a backup QB.</div>{beyond_html}</section>' if qb_flags else ""))
ctr = "\n".join(f'<tr><td>{html.escape(c[0])}</td><td class="num">{c[1]}</td><td class="num">{c[2]}</td><td class="num keep">{c[3]}–{c[4]}</td><td class="num">{c[5]}–{c[6]}</td></tr>' for c in contests)
idr = "\n".join(f'<tr><td class="rk">{i+1}</td>' + "".join(f"<td>{html.escape(v)}</td>" for v in r) + "</tr>" for i, r in enumerate(id_rows))
page = f"""<title>Week 2 Late-Swap Sheet</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@500;700&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#F7F5EF;--ink:#1B1F24;--mute:#5B6360;--rule:#C9CFC7;--band:#2F6B4F;--band-ink:#F7F5EF;--warn:#B7791F;--warn-bg:#FBF1DC;--tile:#EFECE3}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161A1F;--ink:#E8E6E1;--mute:#A3AAA6;--rule:#343B39;--band:#6FB98F;--band-ink:#161A1F;--warn:#E0A83A;--warn-bg:#2A2416;--tile:#1E2429}}}}
:root[data-theme="dark"]{{--bg:#161A1F;--ink:#E8E6E1;--mute:#A3AAA6;--rule:#343B39;--band:#6FB98F;--band-ink:#161A1F;--warn:#E0A83A;--warn-bg:#2A2416;--tile:#1E2429}}
body{{background:var(--bg);color:var(--ink);font-family:"Source Sans 3",system-ui,sans-serif;font-size:16px;line-height:1.45;padding-inline:16px;padding-block:20px 48px;margin:0}}
.wrap{{max-width:720px;margin:0 auto;display:grid;gap:28px}}
h1,h2{{font-family:"Archivo Narrow","Arial Narrow",sans-serif;text-wrap:balance;margin:0;letter-spacing:.01em}}
h1{{font-size:2rem;font-weight:700;line-height:1.05}} h2{{font-size:1.15rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--mute)}}
.eyebrow{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.8rem;color:var(--mute);letter-spacing:.04em}}
.status{{display:flex;flex-wrap:wrap;gap:8px 20px;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.82rem;color:var(--mute)}} .status b{{color:var(--ink);font-weight:500}}
.warn{{background:var(--warn-bg);color:var(--warn);border-left:4px solid var(--warn);padding:10px 14px;font-weight:600}}
table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}} th{{text-align:left;font-family:"Archivo Narrow","Arial Narrow",sans-serif;font-size:.85rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);border-bottom:2px solid var(--rule);padding:6px 8px}}
td{{padding:9px 8px;border-bottom:1px solid var(--rule);vertical-align:top}} .num{{text-align:right;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.9rem;white-space:nowrap}}
.rk{{font-family:"Archivo Narrow","Arial Narrow",sans-serif;font-weight:700;font-size:1.05rem;width:2.2em;text-align:right;color:var(--band)}}
.lu{{display:flex;flex-wrap:wrap;gap:4px 10px}} .p{{white-space:nowrap}} .p b{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.62rem;font-weight:500;color:var(--mute);letter-spacing:.06em;margin-right:4px;vertical-align:.1em}}
.keep{{color:var(--band);font-weight:600}}
.chip{{font-style:normal;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.62rem;font-weight:500;letter-spacing:.06em;text-transform:uppercase;color:var(--warn);background:var(--warn-bg);border:1px solid var(--warn);border-radius:3px;padding:1px 5px;margin-left:6px;vertical-align:.1em}}
tr.flag td{{background:var(--warn-bg)}}
.ok{{background:var(--tile);color:var(--mute);border-left:4px solid var(--band);padding:10px 14px;font-weight:600}}
.swap{{margin-top:6px;font-size:.9rem;color:var(--ink);background:var(--tile);border-radius:4px;padding:6px 8px}}
.fail{{background:#FBE3E0;color:#8A1F11;border-left:4px solid #B3261E;padding:10px 14px;font-weight:700}}
.tw{{overflow-x:auto}} details{{background:var(--tile);border-radius:6px;padding:10px 14px}} summary{{cursor:pointer;font-family:"Archivo Narrow","Arial Narrow",sans-serif;font-weight:700;text-transform:uppercase;letter-spacing:.06em;font-size:.9rem}} details table{{margin-top:10px;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.8rem}} details td{{padding:5px 6px;white-space:nowrap}}
footer{{color:var(--mute);font-size:.85rem;border-top:1px solid var(--rule);padding-top:12px}}
@media (max-width:480px){{h1{{font-size:1.6rem}} td{{padding:8px 5px}} .status{{gap:6px 14px}}}}
</style>
<div class="wrap">
<header>
<div class="eyebrow">DraftKings · Sunday main slate · lock 12:00 CT</div>
<h1>Week 2 Late-Swap Sheet</h1>
<div class="status" style="margin-top:10px"><span>book <b>{k}</b></span><span>run <b>{html.escape(run)}</b></span><span>built <b>{html.escape(built)}</b></span></div>
</header>
<div class="warn">{html.escape(status)}</div>
{('<div class="fail">' + html.escape(repl_fail) + '</div>') if repl_fail else (('<div class="ok">' + html.escape(repl_line) + '</div>') if repl_line else '')}
{qb_section}
<section><h2>Where the keepers go</h2><div class="tw"><table><thead><tr><th>Contest</th><th class="num">ID</th><th class="num">Entries</th><th class="num">Keep rows</th><th class="num">Fill / withdraw</th></tr></thead><tbody>
{ctr}
</tbody></table></div><p class="eyebrow" style="margin:8px 0 0">Keep = the first rows of that contest's ENTER file. The fill rows are placeholders — withdraw them before lock.</p></section>
<section><h2>The keepers, in delivery order</h2><div class="tw"><table><thead><tr><th class="rk">#</th><th>Lineup</th><th class="num">Salary</th><th class="num">P220 inc %</th><th class="num">P220 hsim %</th></tr></thead><tbody>
{tr}
</tbody></table></div></section>
<details><summary>DK upload IDs · {len(id_rows)} rows · {" · ".join(id_hdr)}</summary><div class="tw"><table><tbody>
{idr}
</tbody></table></div></details>
<footer>P220 = modeled chance the lineup scores 220+, per simulator. IDs are DraftKings draftable IDs in slot order. This page is regenerated from the build's own files; nothing here is edited by hand.</footer>
</div>
"""
open(out, "w").write(page); print(out, len(rows), "keepers,", len(id_rows), "id rows,", len(contests), "contests")
