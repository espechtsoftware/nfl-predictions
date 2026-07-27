"""FastAPI service (guide Phase 7): slate view, projections table, lineup
builder with stacking options, exposure summary, DK-format CSV export.

Run locally:  uvicorn nfl_dfs.app.main:app --reload
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..optimizer.export import (
    entry_count,
    exposure_summary,
    fill_entries_csv,
    showdown_exposure_summary,
    to_dk_csv,
    to_dk_showdown_csv,
)
from ..optimizer.lineup import StackRules, core_and_variations, optimize_many
from ..optimizer.showdown import optimize_many_showdown
from .store import BigQueryStore, ProjectionStore

app = FastAPI(title="NFL DFS", version="0.1.0")
log = logging.getLogger(__name__)


@lru_cache
def default_store() -> ProjectionStore:
    return BigQueryStore()


def get_store() -> ProjectionStore:
    return app.dependency_overrides.get(default_store, default_store)()


class LineupRequest(BaseModel):
    season: int
    week: int
    n_lineups: int = Field(40, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    locks: list[int] = []
    bans: list[int] = []
    qb_stack_min: int = Field(2, ge=0, le=3)
    bring_back_min: int = Field(1, ge=0, le=2)
    forbid_rb_vs_dst: bool = True
    max_overlap: int = Field(7, ge=1, le=8)


_PAGE_CSS = """
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;margin:0;
     color:#1a1a2e;background:#f2f4f8;min-height:100vh}
main{max-width:1100px;margin:0 auto;padding:1.2rem 1.2rem 3rem}
.topbar{position:sticky;top:0;z-index:50;display:flex;align-items:center;
  gap:1.2rem;padding:.7rem 1.4rem;color:#fff;
  background:linear-gradient(90deg,#0d1b2a 0%,#1a1a2e 60%,#232946 100%);
  box-shadow:0 2px 12px rgba(13,27,42,.35)}
.topbar .brand{font-weight:800;font-size:1.05rem;letter-spacing:.03em}
.topbar .brand span{color:#53d337}
.topbar a{color:#c8cede;text-decoration:none;font-size:.9rem;
  padding:.38rem .85rem;border-radius:999px;transition:all .15s}
.topbar a:hover{color:#fff;background:rgba(255,255,255,.1)}
.topbar a.active{color:#0d1b2a;background:#53d337;font-weight:700}
.topbar .guide{margin-left:auto;cursor:pointer;border:1px solid
  rgba(255,255,255,.35);background:none;color:#fff;border-radius:999px;
  padding:.38rem .95rem;font-size:.85rem}
.topbar .guide:hover{background:rgba(255,255,255,.12)}
#modalbg{display:none;position:fixed;inset:0;z-index:99;
  background:rgba(13,27,42,.55);backdrop-filter:blur(2px)}
#modal{display:none;position:fixed;z-index:100;top:8vh;left:50%;
  transform:translateX(-50%);width:min(680px,92vw);background:#fff;
  border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.35);
  padding:1.4rem 1.6rem;max-height:80vh;overflow-y:auto}
#modal h2{margin-top:0}
#modal .x{float:right;cursor:pointer;border:0;background:#eef0f6;
  border-radius:8px;padding:.3rem .7rem;font-weight:700}
h1{font-size:1.45rem;margin:1rem 0 .4rem} h2{font-size:1.05rem;margin-top:1.6rem}
table{border-collapse:collapse;width:100%;font-size:.9rem;background:#fff}
th,td{padding:.35rem .6rem;text-align:right;border-bottom:1px solid #e5e5ef}
th:first-child,td:first-child{text-align:left}
th{background:#1a1a2e;color:#fff;position:sticky;top:0}
tr:nth-child(-n+5) td:first-child{font-weight:600}
.up{color:#0a7a3d}.down{color:#b3261e}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
small{color:#666}
#chat{margin:1.5rem 0;background:#fff;border:1px solid #e5e5ef;
      border-radius:8px;padding:1rem}
#chatlog{max-height:320px;overflow-y:auto;font-size:.9rem;margin-bottom:.6rem}
#chatlog .u{font-weight:600;margin-top:.5rem}
#chatlog .a{white-space:pre-wrap;margin:.2rem 0 .2rem .8rem}
#chatrow{display:flex;gap:.5rem}
#chatin{flex:1;padding:.45rem .6rem;border:1px solid #ccc;border-radius:6px}
#chatbtn{padding:.45rem 1rem;background:#1a1a2e;color:#fff;border:0;
         border-radius:6px;cursor:pointer}
#chatbtn:disabled{opacity:.5}
button{transition:filter .15s} button:hover{filter:brightness(1.12)}
.card{transition:transform .12s,box-shadow .12s}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(13,27,42,.14)}
"""

_CHAT_HTML = """
<div id='chat'><h2 style='margin-top:0'>Assistant</h2>
<small>Manage usage notes ("Add a note: coach says Odunze moves to the
slot, +15%"), list/delete them, or ask about projections and player form.</small>
<div id='chatlog'></div>
<div id='chatrow'>
<input id='chatin' placeholder='Ask or instruct...'>
<button id='chatbtn'>Send</button></div></div>
<script>
let hist=[];
const log=document.getElementById('chatlog'),inp=document.getElementById('chatin'),
      btn=document.getElementById('chatbtn');
function show(cls,text){const d=document.createElement('div');d.className=cls;
  d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;}
async function send(){
  const q=inp.value.trim(); if(!q)return;
  inp.value=''; btn.disabled=true; show('u','You: '+q);
  hist.push({role:'user',content:q});
  try{
    const r=await fetch('/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:hist})});
    const j=await r.json();
    if(!r.ok){show('a','Error: '+(j.detail||r.status));}
    else{hist=j.messages; show('a',j.reply||'(no reply)');}
  }catch(e){show('a','Error: '+e);}
  btn.disabled=false; inp.focus();
}
btn.onclick=send;
inp.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script>
"""


_NAV_HTML = """
<div class='topbar'><div class='brand'>&#127944; NFL <span>DFS</span></div>
<a href='/'>Season</a><a href='/lineups/view'>Lineups</a>
<a href='/defense'>Defense</a><a href='/docs'>API</a>
<button class='guide' onclick="document.getElementById('modal').style.display=
'block';document.getElementById('modalbg').style.display='block'">
&#128197; Weekly guide</button></div>
<div id='modalbg' onclick="this.style.display='none';
document.getElementById('modal').style.display='none'"></div>
<div id='modal'><button class='x' onclick="document.getElementById('modal')
.style.display='none';document.getElementById('modalbg').style.display=
'none'">&times;</button><h2>Your weekly schedule</h2>
<table><tr><th>When</th><th>What you do</th></tr>
<tr><td>Tue&ndash;Sat</td><td style='text-align:left'>Optional: tell the
chat about credible news (usage notes); ban/boost players as opinions
form. Automation handles stats, retrain, salaries, odds, props,
weather.</td></tr>
<tr><td>Sun before noon CT</td><td style='text-align:left'>Lineups
&rarr; Build (pick entry count) &rarr; review cards, ban/boost +
rebuild &rarr; <b>download DK CSV</b> (also records entries for
auto-scoring) &rarr; upload at DraftKings before 1pm ET lock.</td></tr>
<tr><td>Sun afternoon</td><td style='text-align:left'>Optional late swap
on DK for 3pm/night games if news breaks.</td></tr>
<tr><td>Mon or Tue</td><td style='text-align:left'>DraftKings &rarr; My
Contests &rarr; <b>download Entry History CSV</b> &rarr; upload on the
Season page (fills contests/spent/won). Optional: contest standings CSV
for rank + real ownership.</td></tr>
<tr><td>Tue 8:00 (auto)</td><td style='text-align:left'>Lineups scored
vs actuals; best score fills itself. Click week numbers to review
entries by score.</td></tr></table></div>
<script>document.addEventListener('DOMContentLoaded',()=>{
  const p=location.pathname;
  document.querySelectorAll('.topbar a').forEach(a=>{
    if(a.getAttribute('href')===p||(p==='/'&&a.getAttribute('href')==='/'))
      a.classList.add('active');});});</script>
"""

_LINEUPS_CSS = """
#controls{display:flex;gap:.6rem;flex-wrap:wrap;align-items:end;
  background:#fff;border:1px solid #e5e5ef;border-radius:8px;padding:1rem}
#controls label{display:flex;flex-direction:column;font-size:.75rem;color:#666}
#controls input,#controls select{padding:.4rem;border:1px solid #ccc;
  border-radius:6px;width:6.5rem}
#cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:1rem;margin-top:1.2rem}
.card{background:#fff;border:1px solid #e5e5ef;border-radius:10px;
  overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card header{background:#1a1a2e;color:#fff;padding:.5rem .8rem;display:flex;
  justify-content:space-between;align-items:baseline;font-size:.85rem}
.card header .conf{color:#53d337;font-weight:700}
.card table{font-size:.8rem;box-shadow:none}
.card td,.card th{padding:.25rem .55rem;border-bottom:1px solid #f0f0f5}
.slot{display:inline-block;min-width:2.6rem;text-align:center;font-weight:700;
  font-size:.68rem;background:#eef0f6;border-radius:4px;padding:.12rem .2rem;
  color:#1a1a2e}
.card tfoot td{font-weight:600;background:#fafafa}
#status{margin:.8rem 0;color:#666}
"""

_LINEUPS_JS = """
async function loadSlates(){
  try{const r=await fetch('/slates');const s=await r.json();
    if(s.length){const last=s[s.length-1];
      document.getElementById('season').value=last.season??'';
      document.getElementById('week').value=last.week??'';}}catch(e){}}
function slotNames(players){
  const slots=['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'];
  return players.map((p,i)=>({slot:slots[i]||p.pos,p}));}
async function build(){
  const st=document.getElementById('status'),
        cards=document.getElementById('cards');
  st.textContent='Building lineups (CBC solves, ~10-60s)...';
  cards.innerHTML=''; document.getElementById('go').disabled=true;
  const body={season:+document.getElementById('season').value,
    week:+document.getElementById('week').value,
    n_lineups:+document.getElementById('n').value,
    objective:document.getElementById('obj').value};
  try{
    const r=await fetch('/lineups',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(!r.ok){st.textContent='Error: '+(j.detail||r.status);return;}
    st.textContent=j.lineups.length+' lineups, strongest first. '+
      'Confidence = P(score >= 194), ordering signal.';
    for(const lu of j.lineups){
      const rows=slotNames(lu.players).map(({slot,p})=>
        `<tr><td><span class='slot'>${slot}</span></td>`+
        `<td style='text-align:left'>${p.name}</td>`+
        `<td>${p.team}${p.opp?' @ '+p.opp:''}</td>`+
        `<td>$${p.salary.toLocaleString()}</td>`+
        `<td>${(+p.proj).toFixed(1)}</td></tr>`).join('');
      const el=document.createElement('div'); el.className='card';
      el.innerHTML=`<header><span>#${lu.rank}</span>`+
        `<span class='conf'>${lu.confidence}%</span>`+
        `<span>${lu.proj_mean} pts proj</span></header>`+
        `<table><tr><th></th><th style='text-align:left'>Player</th>`+
        `<th>Game</th><th>Salary</th><th>Proj</th></tr>${rows}`+
        `<tfoot><tr><td colspan='3'>Total</td>`+
        `<td>$${lu.salary.toLocaleString()}</td>`+
        `<td>${lu.proj.toFixed(1)}</td></tr></tfoot></table>`;
      cards.appendChild(el);}
  }catch(e){st.textContent='Error: '+e;}
  document.getElementById('go').disabled=false;}
document.getElementById('go').onclick=build;
document.getElementById('csv').onclick=()=>{
  const body={season:+document.getElementById('season').value,
    week:+document.getElementById('week').value,
    n_lineups:+document.getElementById('n').value,
    objective:document.getElementById('obj').value};
  fetch('/lineups.csv',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
   .then(r=>r.blob()).then(b=>{const a=document.createElement('a');
    a.href=URL.createObjectURL(b);a.download='dk_lineups.csv';a.click();});};
async function loadPrefs(){
  const se=+document.getElementById('season').value,
        wk=+document.getElementById('week').value;
  if(!se||!wk)return;
  const r=await fetch(`/prefs?season=${se}&week=${wk}`);
  const ps=await r.json();
  document.getElementById('prefs').innerHTML=ps.map(p=>
    `<span style='margin-right:.6rem'>${p.kind==='ban'?'&#128683;':'&#11088;'} `+
    `${p.display_name} <a href='#' data-id='${p.pref_id}'>x</a></span>`).join('');
  document.querySelectorAll('#prefs a').forEach(a=>a.onclick=async e=>{
    e.preventDefault();
    await fetch('/prefs/'+a.dataset.id,{method:'DELETE'}); loadPrefs();});
}
async function addPref(kind,inputId){
  const v=document.getElementById(inputId).value.trim(); if(!v)return;
  await fetch('/prefs',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({season:+document.getElementById('season').value,
      week:+document.getElementById('week').value,display_name:v,kind})});
  document.getElementById(inputId).value=''; loadPrefs();
}
document.getElementById('banin').addEventListener('keydown',
  e=>{if(e.key==='Enter')addPref('ban','banin');});
document.getElementById('boostin').addEventListener('keydown',
  e=>{if(e.key==='Enter')addPref('boost','boostin');});
loadSlates().then?loadSlates():loadSlates; loadPrefs();
"""


@app.get("/lineups/view", response_class=HTMLResponse)
def lineups_page() -> str:
    """DK-style lineup card viewer: build entries and eyeball them without
    touching the CSV. Cards are confidence-ordered, strongest first."""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>NFL DFS — Lineups</title>"
        f"<style>{_PAGE_CSS}{_LINEUPS_CSS}</style></head><body>"
        f"{_NAV_HTML}<main><h1>Lineup builder</h1>"
        f"<div id='controls'>"
        f"<label>Season<input id='season' type='number'></label>"
        f"<label>Week<input id='week' type='number'></label>"
        f"<label>Entries<input id='n' type='number' value='40'></label>"
        f"<label>Objective<select id='obj'>"
        f"<option value='proj_points'>Mean</option>"
        f"<option value='proj_p90'>Ceiling</option>"
        f"<option value='proj_p50'>Median</option></select></label>"
        f"<button id='go' style='padding:.5rem 1.2rem;background:#1a1a2e;"
        f"color:#fff;border:0;border-radius:6px;cursor:pointer'>Build</button>"
        f"<button id='csv' style='padding:.5rem 1.2rem;background:#fff;"
        f"border:1px solid #1a1a2e;border-radius:6px;cursor:pointer'>"
        f"DK CSV</button>"
        f"<label>Ban player<input id='banin' placeholder='name'></label>"
        f"<label>Boost player<input id='boostin' placeholder='name'></label>"
        f"</div><div id='prefs' style='margin:.5rem 0;font-size:.85rem'></div>"
        f"<div id='status'>Pick season/week and Build. Tournament defaults "
        f"apply: QB+2 stack, bring-back, punt slot, chalk fade.</div>"
        f"<div id='cards'></div>"
        f"</main><script>{_LINEUPS_JS}</script></body></html>"
    )


def _defense_page(df, season: int) -> str:
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    sections = []
    for pos in ("QB", "RB", "WR", "TE"):
        grp = latest[latest.position == pos].sort_values("fp_allowed_season")
        if grp.empty:
            continue
        rows = []
        for r in grp.itertuples():
            arrow = ("<span class='down'>&#9660; fading</span>" if r.trend > 1.5
                     else "<span class='up'>&#9650; improving</span>" if r.trend < -1.5
                     else "&mdash;")
            rows.append(
                f"<tr><td>{r.team}</td><td>{r.fp_allowed_season:.1f}</td>"
                f"<td>{r.fp_allowed_l6:.1f}</td><td>{r.fp_allowed_l3:.1f}</td>"
                f"<td>{r.trend:+.1f}</td><td>{arrow}</td></tr>"
            )
        sections.append(
            f"<div><h2>vs {pos}</h2><table>"
            f"<tr><th>Team</th><th>Season</th><th>L6</th><th>L3</th>"
            f"<th>Trend</th><th></th></tr>{''.join(rows)}</table></div>"
        )
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>NFL DFS — Defense vs Position</title>"
        f"<style>{_PAGE_CSS}</style></head><body>"
        f"{_NAV_HTML}<main>"
        f"<h1>DK points allowed per position &middot; {season}</h1>"
        f"<small>Season/L6/L3 = avg DK points allowed per game to the position "
        f"(fewest first = toughest defense). Trend = last 3 vs season norm: "
        f"positive means the defense is giving up more than usual lately. "
        f"API: <a href='/docs'>/docs</a>, "
        f"<a href='/defense/trends?season={season}'>/defense/trends</a></small>"
        f"{_CHAT_HTML}"
        f"<div class='grid'>{''.join(sections)}</div></main></body></html>"
    )




_SEASON_JS = """
const yr=new Date().getFullYear();
document.getElementById('rseason').value=yr;
async function loadResults(){
  const se=+document.getElementById('rseason').value;
  const r=await fetch('/results?season='+se); const rows=await r.json();
  let spent=0,won=0,contests=0,html='';
  for(const x of rows){spent+=x.spent;won+=x.won;contests+=x.contests;
    const pl=x.won-x.spent, cum=won-spent;
    html+=`<tr><td><a href='#' class='wk' data-w='${x.week}'>`+
      `${x.week}</a></td><td>${x.contests}</td>`+
      `<td>$${x.spent.toFixed(2)}</td><td>$${x.won.toFixed(2)}</td>`+
      `<td class='${pl>=0?"up":"down"}'>$${pl.toFixed(2)}</td>`+
      `<td class='${cum>=0?"up":"down"}'>$${cum.toFixed(2)}</td>`+
      `<td>${x.best_score??''}</td><td>${x.best_rank??''}</td>`+
      `<td>${x.note||''}</td></tr>`;}
  document.getElementById('rbody').innerHTML=html;
  document.querySelectorAll('a.wk').forEach(a=>a.onclick=e=>{
    e.preventDefault(); showWeek(+a.dataset.w);});
  const pl=won-spent;
  document.getElementById('totals').innerHTML=
    `Season: <b>${contests}</b> entries &middot; spent <b>$${spent.toFixed(2)}</b>`+
    ` &middot; won <b>$${won.toFixed(2)}</b> &middot; `+
    `<b class='${pl>=0?"up":"down"}'>${pl>=0?"+":""}$${pl.toFixed(2)}`+
    ` (${spent?(100*pl/spent).toFixed(1):0}% ROI)</b>`;
}
async function showWeek(wk){
  const se=+document.getElementById('rseason').value;
  const box=document.getElementById('wklineups');
  box.innerHTML='<small>Scoring week '+wk+'...</small>';
  const r=await fetch(`/results/lineups?season=${se}&week=${wk}`);
  const lus=await r.json();
  if(!lus.length){box.innerHTML='<small>No recorded lineups for week '+
    wk+' (lineups are recorded when the DK CSV is downloaded).</small>';
    return;}
  box.innerHTML='<h2>Week '+wk+' entries by score</h2>'+
    "<div id='cards'>"+lus.map((lu,i)=>
    `<div class='card'><header><span>#${i+1}</span>`+
    `<span class='conf'>${lu.score}</span></header><table>`+
    lu.players.map(p=>`<tr><td><span class='slot'>${p.pos}</span></td>`+
      `<td style='text-align:left'>${p.name}</td><td>${p.team}</td>`+
      `<td>${p.pts}</td></tr>`).join('')+
    `</table></div>`).join('')+'</div>';
}
document.getElementById('rfile').addEventListener('change',async e=>{
  const f=e.target.files[0]; if(!f)return;
  const txt=await f.text();
  const r=await fetch('/results/import',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({season:+document.getElementById('rseason').value,
                         csv_text:txt})});
  const j=await r.json();
  document.getElementById('istatus').textContent=r.ok?
    'Imported '+Object.keys(j.weeks).length+' week(s)':('Error: '+j.detail);
  loadResults();});
loadResults();
"""


@app.get("/", response_class=HTMLResponse)
def season_dashboard() -> str:
    """Home: season bankroll tracker — weekly entries/spent/won with
    running P/L, best-lineup notes, and DK Entry History CSV import."""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>NFL DFS — Season</title>"
        f"<style>{_PAGE_CSS}{_LINEUPS_CSS}</style></head><body>"
        f"{_NAV_HTML}<main><h1>Season tracker</h1>"
        f"<div id='totals' style='font-size:1.05rem;margin:.6rem 0'></div>"
        f"<div id='controls'>"
        f"<label>Season<input id='rseason' type='number'></label>"
        f"<label>DK Entry History CSV<input id='rfile' type='file' "
        f"accept='.csv'></label><span id='istatus'></span></div>"
        f"<small>Upload the cumulative export any time (draftkings.com "
        f"&rarr; My Contests &rarr; Download Entry History) — weeks "
        f"recompute in place; re-uploads are safe. The manual week form "
        f"was removed by request; the /results API still accepts manual "
        f"rows if ever needed.</small>"
        f"<table style='margin-top:1rem'><tr><th>Wk</th><th>Contests</th>"
        f"<th>Spent</th><th>Won</th><th>P/L</th><th>Cumulative</th>"
        f"<th>Best score</th><th>Best rank</th><th>Note</th></tr>"
        f"<tbody id='rbody'></tbody></table>"
        f"<div id='wklineups' style='margin-top:1rem'></div>"
                f"{_CHAT_HTML}"
        f"</main><script>{_SEASON_JS}</script></body></html>"
    )


@app.get("/defense", response_class=HTMLResponse)
def defense_dashboard(
    season: int | None = None,
    store: ProjectionStore = Depends(get_store),
) -> str:
    df = store.defense_points_against(season)
    if df.empty:
        return ("<h1>No defense data yet</h1>"
                "<p>Run <code>nfl-dfs build-features</code> first.</p>")
    season = int(season or df.season.max())
    return _defense_page(df[df.season == season], season)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    messages: list[dict]  # Claude-API-shaped history; last entry is the user turn


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    """Dashboard assistant: manage usage notes, query projections/form.
    Needs ANTHROPIC_API_KEY in the environment."""
    import os

    from . import chat as chat_mod

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set — add it to "
                                 ".env to enable chat")
    try:
        messages = chat_mod.chat_turn(list(req.messages))
    except Exception as exc:
        log.exception("chat turn failed")
        raise HTTPException(500, f"chat failed: {exc}")
    return {"reply": chat_mod.reply_text(messages), "messages": messages}


class PrefRequest(BaseModel):
    season: int
    week: int
    display_name: str
    kind: str = Field(pattern="^(ban|boost)$")


@app.get("/prefs")
def get_prefs(season: int, week: int) -> list[dict]:
    from .. import notes as _notes

    return _notes.list_prefs(season, week).to_dict("records")


@app.post("/prefs")
def post_pref(req: PrefRequest) -> dict:
    from .. import notes as _notes

    return {"pref_id": _notes.add_pref(req.season, req.week,
                                       req.display_name, req.kind)}


@app.delete("/prefs/{pref_id}")
def del_pref(pref_id: str) -> dict:
    from .. import notes as _notes

    return {"deleted": _notes.delete_pref(pref_id)}


class ResultRequest(BaseModel):
    season: int
    week: int
    contests: int
    spent: float
    won: float
    best_score: float | None = None
    best_rank: int | None = None
    note: str = ""


@app.get("/results")
def get_results(season: int) -> list[dict]:
    from .. import notes as _n

    df = _n.list_results(season)
    return df.where(pd.notna(df), None).to_dict("records")


@app.post("/results")
def post_result(req: ResultRequest) -> dict:
    from .. import notes as _n

    return {"result_id": _n.upsert_result(req.season, req.week, req.contests,
                                          req.spent, req.won, req.best_score,
                                          req.best_rank, req.note)}


class HistoryImport(BaseModel):
    season: int
    csv_text: str


@app.get("/results/lineups")
def week_lineups(season: int, week: int) -> list[dict]:
    """The week's entered lineups with actual player points, best first."""
    from .. import notes as _n

    e = _n.scored_lineups(season, week)
    if e.empty:
        return []
    out = []
    for ix, grp in e.groupby("lineup_ix"):
        players = grp.sort_values("pts", ascending=False)
        out.append({
            "score": round(float(grp.pts.sum()), 1),
            "players": [{"name": r.name, "pos": r.pos, "team": r.team,
                         "pts": round(float(r.pts), 1)}
                        for r in players.itertuples()]})
    return sorted(out, key=lambda x: -x["score"])


@app.post("/results/score")
def score_results(season: int, week: int) -> dict:
    """Score the recorded entry set vs actuals; fills best_score."""
    from .. import notes as _n

    try:
        return _n.score_entries(season, week)
    except Exception as exc:
        raise HTTPException(422, f"scoring failed: {exc}")


@app.post("/results/import")
def import_history(req: HistoryImport) -> dict:
    from .. import notes as _n

    try:
        return {"weeks": _n.import_entry_history(req.csv_text, req.season)}
    except Exception as exc:
        raise HTTPException(422, f"could not parse entry history: {exc}")


@app.get("/defense/points-against")
def defense_points_against(
    season: int | None = None,
    position: str | None = None,
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    """Fantasy-style points-against: latest-week snapshot per team/position
    with season average, last-3/6, and trend (positive = fading defense)."""
    df = store.defense_points_against(season)
    if df.empty:
        raise HTTPException(404, "No defense data; run build-features")
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    if position:
        latest = latest[latest.position == position.upper()]
    return (
        latest.sort_values(["position", "fp_allowed_season"])
        .round(2).to_dict("records")
    )


@app.get("/defense/trends")
def defense_trends(
    season: int | None = None,
    top: int = Query(5, ge=1, le=32),
    store: ProjectionStore = Depends(get_store),
) -> dict:
    """Per position: defenses improving (clamping down vs. their season
    norm) and fading (allowing more lately)."""
    df = store.defense_points_against(season)
    if df.empty:
        raise HTTPException(404, "No defense data; run build-features")
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    out: dict = {}
    for pos, grp in latest.groupby("position"):
        g = grp.sort_values("trend").round(2)
        cols = ["team", "trend", "fp_allowed_l3", "fp_allowed_season", "week"]
        out[pos] = {
            "improving": g.head(top)[cols].to_dict("records"),
            "fading": g.tail(top)[cols].iloc[::-1].to_dict("records"),
        }
    return out


@app.get("/slates")
def slates(store: ProjectionStore = Depends(get_store)) -> list[dict]:
    return store.slates().to_dict("records")


@app.get("/projections")
def projections(
    season: int = Query(...),
    week: int = Query(...),
    position: str | None = None,
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    df = store.projections(season, week)
    if df.empty:
        raise HTTPException(404, f"No projections for {season} week {week}")
    if position:
        df = df[df.position == position.upper()]
    return df.sort_values("proj_points", ascending=False).to_dict("records")


def _classic_dk_ids(store: ProjectionStore) -> dict[int, int]:
    """dk_player_id -> draftable ID for the latest classic slate. DK's
    upload parser matches on draftable IDs; without the mapping the CSV
    falls back to player IDs, which DK rejects."""
    try:
        m = store.classic_draftable_ids()
    except Exception:
        log.warning("classic draftable IDs unavailable; upload CSV will "
                    "carry player IDs DK won't accept", exc_info=True)
        return {}
    if m.empty:
        log.warning("no draftable IDs in the latest classic pull; run "
                    "ingest-dk (rows pulled before 2026-07 lack them)")
        return {}
    return {int(r.dk_player_id): int(r.dk_draftable_id) for r in m.itertuples()}


def _player_pool(
    df: pd.DataFrame, objective: str, dk_ids: dict[int, int] | None = None
) -> list[dict]:
    """Tournament-tilted pool: sub-$4k players are valued at their ceiling
    (p90 — a punt's only job is to boom) and every projection carries a
    chalk-fade penalty proportional to naive ownership, so entries lean
    into the leverage that wins large fields. dk_id carries the slate's
    draftable ID, which DK's upload parser requires."""
    from ..backtest.field import naive_ownership
    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY

    pool = []
    for r in df.itertuples():
        pid = int(r.dk_player_id)
        proj = float(getattr(r, objective))
        if int(r.salary) <= PUNT_MAX_SALARY and hasattr(r, "proj_p90") \
                and pd.notna(r.proj_p90):
            proj = max(proj, float(r.proj_p90))
        pool.append(
            {
                "id": pid,
                "dk_id": (dk_ids or {}).get(pid),
                "name": r.display_name,
                "pos": r.position,
                "team": r.team,
                "opp": getattr(r, "opponent", None),
                "game_id": f"{r.team}@{getattr(r, 'opponent', '?')}",
                "salary": int(r.salary),
                "proj": proj,
            }
        )
    own = naive_ownership(pd.DataFrame(pool))
    for p, w in zip(pool, own):
        p["proj"] = p["proj"] - LEVERAGE_PENALTY * float(w)
    return pool


MIN_MILLY_LINE = 194.0  # lowest 2025 Milly-winning score; confidence target


def _rank_by_confidence(lineups: list, df: pd.DataFrame,
                        line: float = MIN_MILLY_LINE) -> list[dict]:
    """Sort lineups by tournament confidence — P(lineup total >= line)
    under a normal approximation from each player's projection mean and
    std. Independence understates stacked lineups' true tail, so treat
    the number as an ordering signal, not a literal probability; the
    untilted means are used (confidence is about scoring, not leverage)."""
    from statistics import NormalDist

    mu_map = df.set_index("dk_player_id").proj_points.to_dict()
    sd_map = (df.set_index("dk_player_id").proj_std.to_dict()
              if "proj_std" in df.columns else {})
    ranked = []
    for lu in lineups:
        mu = sum(float(mu_map.get(p["id"], p["proj"])) for p in lu.players)
        var = sum(float(sd_map.get(p["id"], 0) or 0) ** 2 for p in lu.players)
        sigma = max(var ** 0.5, 1e-6)
        p_line = 1 - NormalDist(mu, sigma).cdf(line)
        ranked.append({"lineup": lu, "proj_mean": round(mu, 1),
                       "confidence": round(100 * p_line, 2)})
    ranked.sort(key=lambda r: (r["confidence"], r["proj_mean"]), reverse=True)
    return ranked


def _build_classic(req: LineupRequest, store: ProjectionStore) -> tuple:
    df = store.projections(req.season, req.week)
    if df.empty:
        raise HTTPException(404, f"No projections for {req.season} week {req.week}")
    from .. import notes as _notes

    pool = _notes.apply_prefs(_player_pool(df, req.objective,
                                           _classic_dk_ids(store)),
                              req.season, req.week)
    stack = StackRules(
        qb_stack_min=req.qb_stack_min,
        bring_back_min=req.bring_back_min,
        forbid_rb_vs_dst=req.forbid_rb_vs_dst,
    )
    lineups = optimize_many(
        pool, n_lineups=req.n_lineups, stack=stack,
        locks=set(req.locks), bans=set(req.bans), max_overlap=req.max_overlap,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    # Confidence order everywhere (JSON + CSVs): first lineup = strongest
    # entry, so "enter the top N in the bigger contest" is just slicing.
    ranked = _rank_by_confidence(lineups, df)
    return [r["lineup"] for r in ranked], ranked


@app.post("/lineups")
def build_lineups(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    lineups, ranked = _build_classic(req, store)
    return {
        "lineups": [
            {
                "rank": i + 1,
                "confidence": r["confidence"],  # P(total >= 194), % (ordering signal)
                "proj_mean": r["proj_mean"],
                "players": r["lineup"].slot_order(),
                "salary": r["lineup"].salary,
                "proj": round(r["lineup"].proj, 2),
            }
            for i, r in enumerate(ranked)
        ],
        "exposure": exposure_summary(lineups),
        "dk_csv": to_dk_csv(lineups),
    }


class CoreLineupRequest(LineupRequest):
    """Core-and-variations mode: a consensus core (picked on the stable
    median objective) locked into every entry, with the remaining spots
    varied on `objective` (defaults to ceiling — variation is for upside).
    core_size omitted = the system decides how many players it feels
    strongly about (conviction + positional value, with a budget guard so
    the core can't hoard the salary cap)."""

    objective: str = Field("proj_p90", pattern="^proj_(points|p50|p90)$")
    core_size: int | None = Field(None, ge=2, le=8)


@app.post("/lineups/core")
def build_core_lineups(
    req: CoreLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    df = store.projections(req.season, req.week)
    if df.empty:
        raise HTTPException(404, f"No projections for {req.season} week {req.week}")
    dk_ids = _classic_dk_ids(store)
    stable_pool = _player_pool(df, "proj_p50", dk_ids)
    upside_pool = _player_pool(df, req.objective, dk_ids)
    stack = StackRules(
        qb_stack_min=req.qb_stack_min,
        bring_back_min=req.bring_back_min,
        forbid_rb_vs_dst=req.forbid_rb_vs_dst,
    )
    core, lineups = core_and_variations(
        stable_pool, upside_pool, n_lineups=req.n_lineups,
        core_size=req.core_size, stack=stack,
        locks=set(req.locks), bans=set(req.bans),
        max_overlap=req.max_overlap if req.max_overlap != 7 else None,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    by_id = {p["id"]: p for p in upside_pool}
    ranked = _rank_by_confidence(lineups, df)
    return {
        "core": [
            {"id": c["id"], "conviction": c["conviction"],
             "name": by_id[c["id"]]["name"], "pos": by_id[c["id"]]["pos"],
             "team": by_id[c["id"]]["team"], "salary": by_id[c["id"]]["salary"]}
            for c in core
        ],
        "lineups": [
            {"rank": i + 1, "confidence": r["confidence"],
             "proj_mean": r["proj_mean"],
             "players": r["lineup"].slot_order(),
             "salary": r["lineup"].salary,
             "proj": round(r["lineup"].proj, 2)}
            for i, r in enumerate(ranked)
        ],
        "exposure": exposure_summary(lineups),
        "dk_csv": to_dk_csv([r["lineup"] for r in ranked]),
    }


# --- Showdown Captain Mode (single-game slates, guide §9.5) ---------------
#
# DK runs a showdown slate for every game, but the interesting ones here are
# the standalone prime-time games — Thursday and Monday night — so that's
# the default filter. Projections are reused from the classic pipeline
# (joined by DK player id); showdown-only positions (K, DST) fall back to
# DK's own points-per-game figure.

SHOWDOWN_DEFAULT_DAYS = "thu,mon"


def _showdown_games(store: ProjectionStore, days: str) -> pd.DataFrame:
    """One row per upcoming showdown draft group, filtered to the requested
    kickoff days (US/Eastern)."""
    sd = store.showdown_salaries()
    if sd.empty:
        return sd
    start = pd.to_datetime(sd.game_start, utc=True, format="ISO8601")
    sd = sd.assign(
        _day=start.dt.tz_convert("America/New_York").dt.day_name(),
        _start=start,
    )
    wanted = {d.strip().lower()[:3] for d in days.split(",") if d.strip()}
    if wanted:
        sd = sd[sd["_day"].str.lower().str[:3].isin(wanted)]
    return sd


def _showdown_pool(game: pd.DataFrame, proj: pd.DataFrame, objective: str) -> list[dict]:
    """Player pool for one showdown game: classic projections joined by DK
    player id, dk_ppg fallback for unprojected players (K, DST)."""
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    opp = {t: next((o for o in teams if o != t), None) for t in teams}
    by_id = {}
    if not proj.empty:
        by_id = proj.set_index("dk_player_id")[
            ["proj_points", "proj_p50", "proj_p90"]
        ].to_dict("index")
    pool = []
    for r in game.itertuples():
        row = by_id.get(r.dk_player_id)
        if row is not None and pd.notna(row[objective]):
            value, source = float(row[objective]), "model"
        elif pd.notna(r.dk_ppg):
            value, source = float(r.dk_ppg), "dk_ppg"
        else:
            continue  # no projection at all — can't rank the player
        draftable = getattr(r, "dk_draftable_id", None)
        cpt = getattr(r, "dk_cpt_draftable_id", None)
        pool.append(
            {
                "id": int(r.dk_player_id),
                "dk_id": int(draftable) if pd.notna(draftable) else None,
                "cpt_dk_id": int(cpt) if pd.notna(cpt) else None,
                "name": r.display_name,
                "pos": r.position,
                "team": r.team_abbr,
                "opp": opp.get(r.team_abbr),
                "game_id": int(r.draft_group_id),
                "salary": int(r.salary),
                "proj": value,
                "proj_source": source,
            }
        )
    return pool


class ShowdownLineupRequest(BaseModel):
    season: int
    week: int
    draft_group_id: int | None = None  # default: next upcoming Thu/Mon game
    days: str = SHOWDOWN_DEFAULT_DAYS
    n_lineups: int = Field(1, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    locks: list[int] = []
    bans: list[int] = []
    captain: int | None = None
    max_overlap: int = Field(5, ge=1, le=5)


@app.get("/showdown/slates")
def showdown_slates(
    days: str = Query(SHOWDOWN_DEFAULT_DAYS),
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    """Upcoming Captain Mode games (default: Thursday/Monday night)."""
    sd = _showdown_games(store, days)
    if sd.empty:
        raise HTTPException(404, "No upcoming showdown slates; run ingest-dk")
    out = []
    for gid, grp in sd.groupby("draft_group_id", sort=False):
        teams = sorted(t for t in grp.team_abbr.dropna().unique())
        out.append(
            {
                "draft_group_id": int(gid),
                "game": " vs ".join(teams),
                "day": grp["_day"].iloc[0],
                "game_start": str(grp["_start"].iloc[0]),
                "players": len(grp),
            }
        )
    return sorted(out, key=lambda g: g["game_start"])


def _build_showdown(
    req: ShowdownLineupRequest, store: ProjectionStore
) -> tuple[pd.DataFrame, list]:
    sd = _showdown_games(store, "" if req.draft_group_id else req.days)
    if sd.empty:
        raise HTTPException(404, "No upcoming showdown slates; run ingest-dk")
    if req.draft_group_id is not None:
        game = sd[sd.draft_group_id == req.draft_group_id]
        if game.empty:
            raise HTTPException(404, f"No showdown slate {req.draft_group_id}")
    else:
        next_gid = sd.sort_values("_start").draft_group_id.iloc[0]
        game = sd[sd.draft_group_id == next_gid]

    proj = store.projections(req.season, req.week)
    pool = _showdown_pool(game, proj, req.objective)
    if len(pool) < 6 or len({p["team"] for p in pool}) < 2:
        raise HTTPException(422, "Showdown pool too thin to build a lineup")
    pool_ids = {p["id"] for p in pool}
    wanted = set(req.locks) | ({req.captain} if req.captain is not None else set())
    if wanted - pool_ids:
        raise HTTPException(
            422, f"Players not in this game's projectable pool: {sorted(wanted - pool_ids)}"
        )

    lineups = optimize_many_showdown(
        pool, n_lineups=req.n_lineups, locks=set(req.locks),
        bans=set(req.bans) & pool_ids,
        captain_lock=req.captain, max_overlap=req.max_overlap,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    return game, lineups


@app.post("/showdown/lineups")
def build_showdown_lineups(
    req: ShowdownLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    game, lineups = _build_showdown(req, store)
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    return {
        "game": {
            "draft_group_id": int(game.draft_group_id.iloc[0]),
            "game": " vs ".join(teams),
            "day": game["_day"].iloc[0],
            "game_start": str(game["_start"].iloc[0]),
        },
        "lineups": [
            {
                "captain": lu.captain,
                "players": lu.slot_order(),
                "salary": lu.salary,
                "proj": round(lu.proj, 2),
            }
            for lu in lineups
        ],
        "exposure": showdown_exposure_summary(lineups),
        "dk_csv": to_dk_showdown_csv(lineups),
    }


@app.post("/showdown/lineups.csv")
def build_showdown_lineups_csv(
    req: ShowdownLineupRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    payload = build_showdown_lineups(req, store)
    return Response(
        content=payload["dk_csv"],
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dk_showdown_lineups.csv"},
    )


@app.post("/lineups.csv")
def build_lineups_csv(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    lineups, ranked = _build_classic(req, store)
    try:
        from .. import notes as _n

        _n.record_entered_lineups(req.season, req.week, lineups)
    except Exception:
        log.exception("could not record entered lineups")
    payload = build_lineups(req, store)
    return Response(
        content=payload["dk_csv"],
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dk_lineups.csv"},
    )


# --- DKEntries filling ----------------------------------------------------
#
# The other DK import path: for contests already entered, download
# DKEntries.csv (Lineups -> Edit Entries on DraftKings), POST it here, and
# re-upload the response on the same screen. One lineup is generated per
# entry row; everything else in the file passes through untouched.

MAX_ENTRIES = 500  # DK's own per-file upload limit


class FillEntriesRequest(LineupRequest):
    entries_csv: str
    n_lineups: int | None = None  # ignored — one lineup per entry row


class ShowdownFillEntriesRequest(ShowdownLineupRequest):
    entries_csv: str
    n_lineups: int | None = None  # ignored — one lineup per entry row


def _entries_n(entries_csv: str) -> int:
    try:
        n = entry_count(entries_csv)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if n == 0:
        raise HTTPException(422, "Entries file contains no entry rows")
    if n > MAX_ENTRIES:
        raise HTTPException(422, f"{n} entries exceeds DK's {MAX_ENTRIES}-row limit")
    return n


def _entries_response(entries_csv: str, lineups: list) -> Response:
    try:
        filled = fill_entries_csv(entries_csv, lineups)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return Response(
        content=filled,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=DKEntries.csv"},
    )


@app.post("/lineups/entries.csv")
def fill_classic_entries(
    req: FillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv)})
    return _entries_response(req.entries_csv, _build_classic(build_req, store)[0])


@app.post("/showdown/lineups/entries.csv")
def fill_showdown_entries(
    req: ShowdownFillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv)})
    _, lineups = _build_showdown(build_req, store)
    return _entries_response(req.entries_csv, lineups)
