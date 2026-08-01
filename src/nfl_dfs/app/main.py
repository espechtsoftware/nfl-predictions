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
from fastapi.staticfiles import StaticFiles
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

app = FastAPI(title="Fingerblasters' Brain", version="0.1.0")

from pathlib import Path as _Path

app.mount("/static", StaticFiles(directory=_Path(__file__).parent / "static"),
          name="static")
log = logging.getLogger(__name__)


@lru_cache
def default_store() -> ProjectionStore:
    return BigQueryStore()


def get_store() -> ProjectionStore:
    return app.dependency_overrides.get(default_store, default_store)()


class LineupRequest(BaseModel):
    season: int
    week: int
    draft_group_id: int | None = None  # classic slate; None = whole week pool
    n_lineups: int = Field(40, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    locks: list[int] = []
    bans: list[int] = []
    qb_stack_min: int = Field(2, ge=0, le=3)
    bring_back_min: int = Field(1, ge=0, le=2)
    forbid_rb_vs_dst: bool = True
    max_overlap: int = Field(7, ge=1, le=8)
    # Contest sizing: field_size scales the confidence target line via
    # tail_line_for_field (a 20k qualifier's winning line sits below the
    # Milly's); an explicit tail_line overrides. Both None = Milly 194.
    field_size: int | None = Field(None, ge=100)
    tail_line: float | None = Field(None, ge=100, le=300)

    def line(self) -> float:
        if self.tail_line is not None:
            return self.tail_line
        if self.field_size is not None:
            return tail_line_for_field(self.field_size)
        return MIN_MILLY_LINE


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
.topbar .logo{height:32px;width:32px;border-radius:8px;object-fit:cover;
  box-shadow:0 0 0 2px rgba(255,255,255,.25)}
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
<div class='topbar'><img src='/static/logo.png' class='logo' alt=''><div class='brand'>Fingerblasters&#39; <span>Brain</span></div>
<a href='/'>Season</a><a href='/lineups/view'>Lineups</a>
<a href='/defense'>Defense</a><a href='/market'>Market</a><a href='/docs'>API</a>
<button class='guide' onclick="document.getElementById('modal').style.display=
'block';document.getElementById('modalbg').style.display='block'">
&#128197; Weekly guide</button>
<button class='guide' style='margin-left:.6rem' onclick="openStatus()">
&#129658; System status</button></div>
<div id='modalbg' onclick="this.style.display='none';
document.getElementById('modal').style.display='none';
document.getElementById('statusmodal').style.display='none'"></div>
<div id='statusmodal' style='display:none;position:fixed;z-index:100;top:8vh;
left:50%;transform:translateX(-50%);width:min(760px,94vw);background:#fff;
border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.35);
padding:1.4rem 1.6rem;max-height:80vh;overflow-y:auto'>
<button class='x' onclick="document.getElementById('statusmodal')
.style.display='none';document.getElementById('modalbg').style.display=
'none'">&times;</button><h2>System status</h2>
<div id='statusbody'><small>Loading&hellip;</small></div></div>
<div id='modal'><button class='x' onclick="document.getElementById('modal')
.style.display='none';document.getElementById('modalbg').style.display=
'none'">&times;</button><h2>Your weekly schedule</h2>
<table><tr><th>When</th><th>What you do</th></tr>
<tr><td>Tue&ndash;Sat</td><td style='text-align:left'>Optional: tell the
chat about credible news (usage notes); ban/boost players as opinions
form. Automation handles stats, retrain, salaries, odds, props,
weather.</td></tr>
<tr><td>Sun before noon CT</td><td style='text-align:left'>Lineups
&rarr; Build (pick slate + entry count; the Sunday main slate is
preselected) &rarr; review cards, ban/boost +
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
      a.classList.add('active');});});
const _stColor={ok:'#0a7a3d',stale:'#b3261e',missing:'#b3261e',
                empty:'#b26a00',idle:'#667'};
const _stGloss={ok:'fresh',stale:'STALE',missing:'MISSING',
                empty:'no data yet',idle:'idle (off-season)'};
function _stAge(h){if(h==null)return '&mdash;';
  if(h<1)return Math.round(h*60)+'m';
  if(h<48)return h.toFixed(h<10?1:0)+'h';
  return (h/24).toFixed(1)+'d';}
async function openStatus(){
  const m=document.getElementById('statusmodal'),
        b=document.getElementById('statusbody');
  m.style.display='block';
  document.getElementById('modalbg').style.display='block';
  b.innerHTML='<small>Loading&hellip;</small>';
  try{
    const r=await fetch('/api/system-status'); const j=await r.json();
    let h="<table><tr><th>Feed</th><th>State</th><th>Last update</th>"+
          "<th>Rows</th></tr>";
    for(const c of j.components){
      const col=_stColor[c.state]||'#667';
      h+="<tr><td style='text-align:left'>"+c.label+
         (c.note?"<br><small>"+c.note+"</small>":"")+"</td>"+
         "<td style='text-align:left'><span style='color:"+col+
         ";font-weight:700'>&#9679; "+(_stGloss[c.state]||c.state)+"</span>"+
         (c.state==='stale'?"<br><small>max "+c.max_age_hours+"h</small>":"")+
         "</td><td>"+_stAge(c.age_hours)+" ago</td>"+
         "<td>"+(c.rows==null?'&mdash;':c.rows.toLocaleString())+"</td></tr>";
    }
    h+="</table><small>Feeds marked idle are out of season. Generated "+
       new Date(j.generated_at).toLocaleTimeString()+
       ". A daily check emails on any red state.</small>";
    b.innerHTML=h;
  }catch(e){b.innerHTML="<small>Failed to load status: "+e+"</small>";}
}</script>
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
async function loadClassicSlates(){
  const sel=document.getElementById('slate');
  try{const r=await fetch('/classic/slates'); if(!r.ok)return;
    const grp=document.createElement('optgroup'); grp.label='Classic slates';
    for(const g of await r.json()){
      const o=document.createElement('option');
      o.value=g.draft_group_id;
      o.textContent=(g.main?'Main: ':'')+g.label;
      if(g.main)o.selected=true;
      grp.appendChild(o);}
    if(grp.children.length)sel.appendChild(grp);
  }catch(e){}}
async function loadShowdownSlates(){
  const sel=document.getElementById('slate');
  try{const r=await fetch('/showdown/slates?days='); if(!r.ok)return;
    const grp=document.createElement('optgroup');
    grp.label='Showdown (Captain Mode)';
    for(const g of await r.json()){
      const o=document.createElement('option');
      o.value='sd:'+g.draft_group_id;
      o.textContent=g.game+' · '+g.day;
      grp.appendChild(o);}
    if(grp.children.length)sel.appendChild(grp);
  }catch(e){}}
async function loadContests(){
  const sel=document.getElementById('contest');
  try{const r=await fetch('/contests'); if(!r.ok)return;
    const j=await r.json();
    const add=(list,label)=>{
      if(!list.length)return;
      const grp=document.createElement('optgroup'); grp.label=label;
      for(const c of list){
        const o=document.createElement('option');
        o.value=c.field_size;
        o.textContent=`${c.name} · $${c.entry_fee} · `+
          `${(+c.field_size).toLocaleString()} entries (line ${c.tail_line})`;
        grp.appendChild(o);}
      sel.appendChild(grp);};
    add(j.live,'Live DK contests'); add(j.presets,'Presets');
    if(sel.options.length)
      document.getElementById('fsize').value=sel.options[0].value;
    sel.onchange=()=>{
      document.getElementById('fsize').value=sel.value;};
  }catch(e){}}
function slateSel(){
  const v=document.getElementById('slate').value;
  if(v.startsWith('sd:'))return{sd:true,gid:+v.slice(3)};
  return{sd:false,gid:v?+v:null};}
function reqBody(){
  return{season:+document.getElementById('season').value,
    week:+document.getElementById('week').value,
    draft_group_id:slateSel().gid,
    n_lineups:+document.getElementById('n').value,
    field_size:+document.getElementById('fsize').value||null,
    objective:document.getElementById('obj').value};}
function slotNames(players){
  const slots=['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'];
  return players.map((p,i)=>({slot:slots[i]||p.pos,p}));}
async function build(){
  const st=document.getElementById('status'),
        cards=document.getElementById('cards'),
        sd=slateSel().sd;
  st.textContent='Building lineups (CBC solves, ~10-60s)...';
  cards.innerHTML=''; document.getElementById('go').disabled=true;
  try{
    const r=await fetch(sd?'/showdown/lineups':'/lineups',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(reqBody())});
    const j=await r.json();
    if(!r.ok){st.textContent='Error: '+(j.detail||r.status);return;}
    st.textContent=sd
      ? j.lineups.length+' Captain Mode lineups · '+j.game.game+' ('+
        j.game.day+'). Captain scores 1.5x and costs 1.5x.'
      : j.lineups.length+' lineups, strongest first. Confidence = '+
        'P(score >= '+(j.tail_line||194)+'), ordering signal scaled to '+
        'the chosen contest field.';
    j.lineups.forEach((lu,i)=>{
      const named=sd
        ? lu.players.map((p,k)=>({slot:k?'FLEX':'CPT',p,cpt:!k}))
        : slotNames(lu.players);
      const rows=named.map(({slot,p,cpt})=>{
        const sal=cpt?Math.round(p.salary*1.5):p.salary,
              pr=cpt?1.5*p.proj:+p.proj;
        return `<tr><td><span class='slot'>${slot}</span></td>`+
        `<td style='text-align:left'>${p.name}</td>`+
        `<td>${p.team}${p.opp?' @ '+p.opp:''}</td>`+
        `<td>$${sal.toLocaleString()}</td>`+
        `<td>${pr.toFixed(1)}</td></tr>`;}).join('');
      const head=sd
        ? `<header><span>#${i+1}</span>`+
          `<span class='conf'>CPT ${lu.captain.name}</span>`+
          `<span>${lu.proj.toFixed(1)} pts proj</span></header>`
        : `<header><span>#${lu.rank}</span>`+
          `<span class='conf'>${lu.confidence}%</span>`+
          `<span>${lu.proj_mean} pts proj</span></header>`;
      const el=document.createElement('div'); el.className='card';
      el.innerHTML=head+
        `<table><tr><th></th><th style='text-align:left'>Player</th>`+
        `<th>Game</th><th>Salary</th><th>Proj</th></tr>${rows}`+
        `<tfoot><tr><td colspan='3'>Total</td>`+
        `<td>$${lu.salary.toLocaleString()}</td>`+
        `<td>${lu.proj.toFixed(1)}</td></tr></tfoot></table>`;
      cards.appendChild(el);});
  }catch(e){st.textContent='Error: '+e;}
  document.getElementById('go').disabled=false;}
document.getElementById('go').onclick=build;
document.getElementById('csv').onclick=()=>{
  const sd=slateSel().sd;
  fetch(sd?'/showdown/lineups.csv':'/lineups.csv',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(reqBody())})
   .then(r=>r.blob()).then(b=>{const a=document.createElement('a');
    a.href=URL.createObjectURL(b);
    a.download=sd?'dk_showdown_lineups.csv':'dk_lineups.csv';a.click();});};
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
loadSlates().then?loadSlates():loadSlates;
loadClassicSlates(); loadShowdownSlates(); loadPrefs(); loadContests();
"""


@app.get("/lineups/view", response_class=HTMLResponse)
def lineups_page() -> str:
    """DK-style lineup card viewer: build entries and eyeball them without
    touching the CSV. Cards are confidence-ordered, strongest first."""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Fingerblasters' Brain — Lineups</title><link rel='icon' href='/static/logo.png'>"
        f"<style>{_PAGE_CSS}{_LINEUPS_CSS}</style></head><body>"
        f"{_NAV_HTML}<main><h1>Lineup builder</h1>"
        f"<div id='controls'>"
        f"<label>Season<input id='season' type='number'></label>"
        f"<label>Week<input id='week' type='number'></label>"
        f"<label>Slate<select id='slate' style='width:15rem'>"
        f"<option value=''>Whole week pool (no slate filter)</option>"
        f"</select></label>"
        f"<label>Contest<select id='contest' style='width:16rem'></select>"
        f"</label>"
        f"<label>Field size<input id='fsize' type='number' value='20000'>"
        f"</label>"
        f"<label>Entries<input id='n' type='number' value='40'></label>"
        f"<label>Objective<select id='obj'>"
        f"<option value='proj_points'>Mean (GPP default — replay-validated; ceiling logic is built in via punts/boom stacks)</option>"
        f"<option value='proj_p90'>Ceiling p90 (tested: underperforms for GPP)</option>"
        f"<option value='proj_p50'>Median</option></select></label>"
        f"<button id='go' style='padding:.5rem 1.2rem;background:#1a1a2e;"
        f"color:#fff;border:0;border-radius:6px;cursor:pointer'>Build</button>"
        f"<button id='csv' style='padding:.5rem 1.2rem;background:#fff;"
        f"border:1px solid #1a1a2e;border-radius:6px;cursor:pointer'>"
        f"DK CSV</button>"
        f"<label>Ban player<input id='banin' placeholder='name'></label>"
        f"<label>Boost player<input id='boostin' placeholder='name'></label>"
        f"</div><div id='prefs' style='margin:.5rem 0;font-size:.85rem'></div>"
        f"<div id='status'>Pick season/week/slate and Build (the Sunday "
        f"main slate preselects itself when DK lists one; single games under "
        f"Showdown build Captain Mode entries). Classic tournament defaults "
        f"apply: QB+2 stack, bring-back, punt slot, chalk fade — showdown "
        f"leverages captain diversity instead.</div>"
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
        f"<title>Fingerblasters' Brain — Defense</title><link rel='icon' href='/static/logo.png'>"
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
  const [r,xr]=await Promise.all([
    fetch(`/results/lineups?season=${se}&week=${wk}`),
    fetch(`/results/exports?season=${se}`)]);
  const lus=await r.json();
  const info=(await xr.json()).find(s=>s.week===wk);
  if(!lus.length){box.innerHTML='<small>No recorded lineups for week '+
    wk+' (lineups are recorded when the DK CSV is downloaded).</small>';
    return;}
  box.innerHTML='<h2>Week '+wk+' entries by score</h2>'+
    (info?`<small>Export set: <b>${info.lineups}</b> lineups, recorded `+
      `${info.recorded_at} (latest DK CSV download for the week &mdash; `+
      `each download replaces the last). </small>`:'')+
    `<button id='delwk' style='margin-left:.5rem;padding:.2rem .7rem;`+
    `background:#fff;border:1px solid #b00;color:#b00;border-radius:6px;`+
    `cursor:pointer'>Delete recorded slate</button><br>`+
    '<small>Click a player to swap him for whoever you used on DK.</small>'+
    "<div id='cards'>"+lus.map((lu,i)=>
    `<div class='card'><header><span>#${i+1}</span>`+
    `<span class='conf'>${lu.score}</span></header><table>`+
    lu.players.map(p=>`<tr><td><span class='slot'>${p.pos}</span></td>`+
      `<td style='text-align:left'><a href='#' class='swp' data-ix='${lu.ix}'`+
      ` data-out='${p.name}'>${p.name}</a></td><td>${p.team}</td>`+
      `<td>${p.pts}</td></tr>`).join('')+
    `</table></div>`).join('')+'</div>';
  document.getElementById('delwk').onclick=async()=>{
    if(!confirm('Delete week '+wk+"'s recorded lineups? Do this for "+
      'what-if slates you never entered on DK, so Tuesday scoring '+
      "skips the week. (An already-scored best_score isn't reset; "+
      're-score after recording the real slate, or edit via the API.)'))
      return;
    const dr=await fetch(`/results/lineups?season=${se}&week=${wk}`,
      {method:'DELETE'});
    if(dr.ok){box.innerHTML='<small>Week '+wk+
      ' recorded lineups deleted.</small>';}
    else alert('Delete failed: '+(await dr.json()).detail);
  };
  document.querySelectorAll('a.swp').forEach(a=>a.onclick=async e=>{
    e.preventDefault();
    const q=prompt('Swap OUT '+a.dataset.out+'.\nSearch replacement name:');
    if(!q)return;
    const se=+document.getElementById('rseason').value;
    const cs=await (await fetch(`/players/search?season=${se}&week=${wk}`+
      `&q=${encodeURIComponent(q)}`)).json();
    if(!cs.length){alert('No match for "'+q+'"');return;}
    let pick=cs[0];
    if(cs.length>1){
      const c=prompt(cs.map((p,i)=>`${i+1}. ${p.name} ${p.pos} ${p.team} `+
        `$${p.salary}`).join('\n')+'\n\nEnter number:');
      pick=cs[+c-1]; if(!pick)return;}
    const r=await fetch('/entries/swap',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({season:se,week:wk,lineup_ix:+a.dataset.ix,
        out_name:a.dataset.out,in_name:pick.name})});
    if(!r.ok){alert('Swap failed: '+(await r.json()).detail);return;}
    showWeek(wk);
  });
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
        f"<title>Fingerblasters' Brain — Season</title><link rel='icon' href='/static/logo.png'>"
        f"<style>{_PAGE_CSS}{_LINEUPS_CSS}</style></head><body>"
        f"{_NAV_HTML}<main>"
        f"<div style='display:flex;align-items:center;gap:1.1rem;"
        f"margin-top:1.2rem'>"
        f"<img src='/static/logo.png' alt='' style='height:110px;"
        f"width:110px;border-radius:18px;object-fit:cover;"
        f"box-shadow:0 8px 24px rgba(13,27,42,.25)'>"
        f"<div><h1 style='margin:.2rem 0'>Season tracker</h1>"
        f"<div id='totals' style='font-size:1.05rem;margin:.3rem 0'></div>"
        f"</div></div>"
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


@app.get("/market", response_class=HTMLResponse)
def market_page() -> str:
    """Market intelligence: line movement since open, and where our model
    disagrees most with the prop market (2026-08-01 audit item)."""
    body = """
<main><h1>Market</h1>
<h2>Line movement (since first snapshot)</h2>
<div id='moves'><small>Loading&hellip;</small></div>
<h2 style='margin-top:2rem'>Model vs prop market</h2>
<div style='margin:.4rem 0'><small>Season/week with projections:</small>
<input id='ms' size='5' placeholder='season'> <input id='mw' size='3'
placeholder='wk'> <button id='mgo'>Load</button></div>
<div id='dis'><small>Enter a projected week (in-season) and Load.</small></div>
</main>
<script>
function tbl(rows, cols){if(!rows.length)return '<small>No data yet.</small>';
  let h='<table><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>';
  for(const r of rows){h+='<tr>'+cols.map(c=>'<td>'+(r[c]??'')+'</td>').join('')+'</tr>';}
  return h+'</table>';}
fetch('/api/line-movement').then(r=>r.json()).then(j=>{
  document.getElementById('moves').innerHTML=tbl(j,
    ['event_name','market_type','selection','open_line','latest_line',
     'line_move','latest_odds','last_seen']);});
document.getElementById('mgo').onclick=async()=>{
  const s=document.getElementById('ms').value,w=document.getElementById('mw').value;
  if(!s||!w)return;
  const j=await (await fetch(`/api/market-disagreement?season=${s}&week=${w}`)).json();
  document.getElementById('dis').innerHTML=tbl(j,
    ['display_name','position','team','salary','proj_points','market_points','edge']);
};
</script>"""
    return f"<html><head><title>Market</title><style>{_PAGE_CSS}</style></head><body>{_NAV_HTML}{body}</body></html>"


@app.get("/api/line-movement")
def api_line_movement(limit: int = 40) -> list[dict]:
    """Biggest spread/total moves since first snapshot (odds_movement
    view; collecting 2x/day Wed-Sun since the 2026-07-31 odds fix)."""
    from ..bq import query_df
    from ..config import settings

    df = query_df(f"""
        SELECT event_name, market_type, selection, open_line, latest_line,
               line_move, open_odds, latest_odds,
               FORMAT_TIMESTAMP('%m-%d %H:%M', last_seen) AS last_seen
        FROM `{settings.raw}.odds_movement`
        WHERE line_move IS NOT NULL AND market_type IN ('Spread', 'Total')
        ORDER BY ABS(line_move) DESC
        LIMIT {int(limit)}
    """)
    return df.to_dict("records")


@app.get("/api/market-disagreement")
def api_market_disagreement(season: int, week: int, limit: int = 40) -> list[dict]:
    """Model projections vs prop-market-implied points: the rows where we
    disagree most with the betting market, both directions. Divergence is
    either alpha or a bug -- worth eyes each week either way."""
    from ..models.prop_market import market_points

    store = get_store()
    proj = store.projections(season, week)
    if proj.empty:
        return []
    mkt = market_points(seasons=(season,))
    mkt = mkt[mkt.week == week]
    if mkt.empty:
        return []
    j = proj.merge(mkt[["gsis_id", "market_points"]], on="gsis_id", how="inner")
    j["edge"] = j.proj_points - j.market_points
    j = j.reindex(j.edge.abs().sort_values(ascending=False).index).head(int(limit))
    cols = ["display_name", "position", "team", "salary",
            "proj_points", "market_points", "edge"]
    return j[[c for c in cols if c in j.columns]].round(2).to_dict("records")


@app.get("/api/system-status")
def api_system_status() -> dict:
    """Freshness of every data feed, for the System status popup. See
    nfl_dfs/status.py for the feed specs and state rules."""
    from datetime import datetime, timezone

    from .. import status as _status

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": _status.system_status(),
    }


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
            "ix": int(ix),
            "score": round(float(grp.pts.sum()), 1),
            "players": [{"name": r.name, "pos": r.pos, "team": r.team,
                         "pts": round(float(r.pts), 1)}
                        for r in players.itertuples()]})
    return sorted(out, key=lambda x: -x["score"])


@app.get("/results/exports")
def list_exports(season: int) -> list[dict]:
    """Recorded export sets by week: lineup/player counts and when the DK
    CSV was downloaded (only the latest download per week is kept)."""
    from .. import notes as _n

    return _n.list_entered_sets(season).to_dict("records")


@app.delete("/results/lineups")
def delete_week_lineups(season: int, week: int) -> dict:
    """Forget the week's recorded export set — for what-if slates that
    were downloaded but never entered on DK, so scoring skips the week."""
    from .. import notes as _n

    try:
        return {"deleted": _n.delete_entered_lineups(season, week)}
    except Exception as exc:
        raise HTTPException(422, f"delete failed: {exc}")


@app.get("/players/search")
def player_search(season: int, week: int, q: str,
                  store: ProjectionStore = Depends(get_store)) -> list[dict]:
    """Name search over the week's projectable pool (swap candidates)."""
    df = store.projections(season, week)
    if df.empty:
        return []
    hit = df[df.display_name.str.contains(q, case=False, na=False)]
    return [{"name": r.display_name, "pos": r.position, "team": r.team,
             "salary": int(r.salary), "dk_player_id": int(r.dk_player_id),
             "proj": round(float(r.proj_points), 1)}
            for r in hit.head(10).itertuples()]


class SwapRequest(BaseModel):
    season: int
    week: int
    lineup_ix: int
    out_name: str
    in_name: str


@app.post("/entries/swap")
def swap_entry_player(req: SwapRequest,
                      store: ProjectionStore = Depends(get_store)) -> dict:
    """Replace a player in a recorded lineup (mirrors a DK edit)."""
    from .. import notes as _n

    df = store.projections(req.season, req.week)
    hit = df[df.display_name.str.contains(req.in_name, case=False, na=False)]
    if hit.empty:
        raise HTTPException(404, f"no player matching '{req.in_name}'")
    if len(hit) > 1 and not (hit.display_name.str.lower()
                             == req.in_name.lower()).any():
        raise HTTPException(409, "ambiguous: "
                            + ", ".join(hit.display_name.head(5)))
    r = (hit[hit.display_name.str.lower() == req.in_name.lower()].iloc[0]
         if len(hit) > 1 else hit.iloc[0])
    # Duplicate guards: the swap must not clone another entered lineup,
    # and the incoming player must not already be in this one.
    rosters = _n.entered_rosters(req.season, req.week)
    cur = rosters.get(req.lineup_ix)
    if cur is not None:
        incoming = _n.norm_name(str(r.display_name))
        if incoming in cur:
            raise HTTPException(409, f"{r.display_name} is already in "
                                     f"this lineup")
        proposed = (cur - {_n.norm_name(req.out_name)}) | {incoming}
        for ix, roster in rosters.items():
            if ix != req.lineup_ix and roster == proposed:
                raise HTTPException(
                    409, f"blocked: that swap would make this lineup "
                         f"identical to entry #{ix + 1} — DK rejects "
                         f"duplicate lineups, pick a different player")
    _n.swap_entered_player(req.season, req.week, req.lineup_ix,
                           req.out_name,
                           {"name": r.display_name, "pos": r.position,
                            "team": r.team,
                            "dk_player_id": int(r.dk_player_id)})
    return {"swapped": req.out_name, "for": str(r.display_name)}


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


def _slate_label(kickoffs: pd.Series, games: int) -> str:
    """Human label for a classic draft group from its kickoff times:
    'Sun 1:00 PM–4:25 PM · 12 games' or 'Thu–Mon · 16 games' (US/Eastern)."""
    et = pd.to_datetime(kickoffs, utc=True).dt.tz_convert(
        "America/New_York").sort_values()
    days = list(dict.fromkeys(et.dt.strftime("%a")))

    def clock(ts) -> str:
        return ts.strftime("%I:%M %p").lstrip("0")

    if len(days) == 1:
        first, last = clock(et.iloc[0]), clock(et.iloc[-1])
        when = f"{days[0]} {first}" + (f"–{last}" if last != first else "")
    else:
        when = f"{days[0]}–{days[-1]}"
    return f"{when} · {games} game{'s' if games != 1 else ''}"


@app.get("/classic/slates")
def classic_slates(store: ProjectionStore = Depends(get_store)) -> list[dict]:
    """Upcoming classic slates (draft groups) to build lineups against.
    `main` flags the Sunday main slate: the all-Sunday group with the most
    games (DK's 1:00+4:25 slate — the user's usual tournament target)."""
    df = store.classic_slates()
    if df.empty:
        raise HTTPException(404, "No upcoming classic slates; run ingest-dk")
    out = []
    for gid, grp in df.groupby("draft_group_id", sort=False):
        starts = pd.to_datetime(grp.game_start, utc=True)
        games = int(grp.teams.sum()) // 2
        et_days = list(dict.fromkeys(
            starts.dt.tz_convert("America/New_York").dt.strftime("%a")))
        out.append({
            "draft_group_id": int(gid),
            "label": _slate_label(grp.game_start, games),
            "days": et_days,
            "games": games,
            "players": int(grp.players.sum()),
            "first_game": str(starts.min()),
            "last_game": str(starts.max()),
            "main": False,
        })
    sunday_only = [s for s in out if s["days"] == ["Sun"]]
    if sunday_only:
        max(sunday_only, key=lambda s: (s["games"], s["players"]))["main"] = True
    return sorted(out, key=lambda s: (s["first_game"], -s["games"]))


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
        kickoff = getattr(r, "kickoff", None)
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
                "kickoff": kickoff if pd.notna(kickoff) else None,
            }
        )
    own = naive_ownership(pd.DataFrame(pool))
    for p, w in zip(pool, own):
        p["proj"] = p["proj"] - LEVERAGE_PENALTY * float(w)
    return pool


MIN_MILLY_LINE = 194.0  # lowest 2025 Milly-winning score; confidence target
MILLY_FIELD = 150_000   # field the 194 anchor was measured in
_FIELD_MU = 120.0       # contending-entry mean the Gumbel term scales from


def tail_line_for_field(field_size: int) -> float:
    """Winning-line estimate for a GPP of `field_size` entries.

    Extreme-value scaling: the max of N entry scores grows like
    mu + sigma*sqrt(2 ln N), so the line moves with sqrt(ln N) around a
    contending-field mean. Anchored at the one point we measured (2025
    Milly, 150k entries, min winning line 194). PROVISIONAL until real
    qualifier standings recalibrate it (in-season queue item 7) — treat
    it as "a 20k field wins ~6-7 points lower", not gospel.
    """
    import math

    n = max(int(field_size), 100)
    scale = math.sqrt(math.log(n) / math.log(MILLY_FIELD))
    return round(_FIELD_MU + (MIN_MILLY_LINE - _FIELD_MU) * scale, 1)


# Static picker fallbacks; live DK contests (real names, fees and field
# sizes from the overlay scaffold's fill polls) take over when
# INGEST_CONTESTS_ENABLED has landed data. $5 qualifier first: it's the
# primary contest this shop enters.
CONTEST_PRESETS = [
    {"name": "$5 Qualifier (typical)", "entry_fee": 5.0, "field_size": 20_000},
    {"name": "Millionaire Maker", "entry_fee": 20.0, "field_size": MILLY_FIELD},
    {"name": "Small qualifier / single-entry", "entry_fee": 5.0,
     "field_size": 5_000},
]


@app.get("/contests")
def contest_options() -> dict:
    """Contest picker: live upcoming DK contests when the fill-poll table
    has them, else just the presets. Every option carries the field size
    and the tail line the confidence ordering will target."""
    live: list[dict] = []
    try:
        from ..bq import query_df
        from ..config import settings

        df = query_df(f"""
            SELECT name, entry_fee, field_size, prize_pool FROM (
              SELECT name, entry_fee, max_entries AS field_size, prize_pool,
                     ROW_NUMBER() OVER (PARTITION BY contest_id
                                        ORDER BY pulled_at DESC) rn
              FROM `{settings.raw}.dk_contest_fills`
              WHERE start_time > CURRENT_TIMESTAMP()
                AND is_guaranteed AND max_entries >= 1000)
            WHERE rn = 1 ORDER BY prize_pool DESC LIMIT 25""")
        live = df.to_dict("records")
    except Exception as exc:  # table absent until the scaffold is enabled
        log.info("live contest list unavailable (%s); presets only", exc)
    for c in live + CONTEST_PRESETS:
        c["tail_line"] = tail_line_for_field(int(c["field_size"]))
    return {"live": live, "presets": CONTEST_PRESETS}


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


def _classic_projections(
    req: LineupRequest, store: ProjectionStore
) -> tuple[pd.DataFrame, dict[int, int]]:
    """The week's projections plus draftable IDs, restricted to the chosen
    classic slate when the request names one. Slate salaries and draftable
    IDs override the projection row's — both are slate-specific, and a CSV
    with another slate's draftable IDs is a CSV DK rejects."""
    df = store.projections(req.season, req.week)
    if df.empty:
        raise HTTPException(404, f"No projections for {req.season} week {req.week}")
    if req.draft_group_id is None:
        return df, _classic_dk_ids(store)
    sal = store.classic_salaries(req.draft_group_id)
    if sal.empty:
        raise HTTPException(
            404, f"No classic slate {req.draft_group_id}; "
                 f"see GET /classic/slates for what's upcoming")
    sal = sal.drop_duplicates(subset=["dk_player_id"]).set_index("dk_player_id")
    df = df[df.dk_player_id.isin(sal.index)].copy()
    if df.empty:
        raise HTTPException(
            404, f"No projections overlap slate {req.draft_group_id}; "
                 f"run project after ingest-dk")
    df["salary"] = (df.dk_player_id.map(sal.salary)
                    .fillna(df.salary).astype(int))
    if "game_start" in sal.columns:
        # Feeds slot_order()'s late-swap FLEX preference (roadmap #13.2);
        # absent for callers with no chosen slate, which is the existing
        # proj-based behavior.
        df["kickoff"] = df.dk_player_id.map(sal.game_start)
    unprojected = len(sal) - df.dk_player_id.nunique()
    if unprojected:
        log.info("slate %s: %d salary rows have no projection and are "
                 "left out of the pool", req.draft_group_id, unprojected)
    dk_ids = {int(pid): int(d)
              for pid, d in sal.dk_draftable_id.dropna().items()}
    return df, dk_ids


def _build_classic(req: LineupRequest, store: ProjectionStore) -> tuple:
    df, dk_ids = _classic_projections(req, store)
    from .. import notes as _notes

    pool = _notes.apply_prefs(_player_pool(df, req.objective, dk_ids),
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
    ranked = _rank_by_confidence(lineups, df, line=req.line())
    return [r["lineup"] for r in ranked], ranked


@app.post("/lineups")
def build_lineups(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    lineups, ranked = _build_classic(req, store)
    return {
        "tail_line": req.line(),  # what "confidence" is P(score >= X) of
        "lineups": [
            {
                "rank": i + 1,
                "confidence": r["confidence"],  # P(total >= tail_line), %
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
    df, dk_ids = _classic_projections(req, store)
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
    ranked = _rank_by_confidence(lineups, df, line=req.line())
    return {
        "tail_line": req.line(),
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


def _showdown_pool(game: pd.DataFrame, proj: pd.DataFrame, objective: str,
                   trailing: pd.DataFrame | None = None) -> list[dict]:
    """Player pool for one showdown game: classic projections joined by DK
    player id; K/DST fall back to trailing-mean DK actuals (issue #10's
    last item, store.trailing_kdst) and only then to DK's dk_ppg figure."""
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    opp = {t: next((o for o in teams if o != t), None) for t in teams}
    by_id = {}
    if not proj.empty:
        cols = ["proj_points", "proj_p50", "proj_p90"]
        if "proj_std" in proj.columns:
            cols.append("proj_std")
        by_id = proj.set_index("dk_player_id")[cols].to_dict("index")
    trail_map = {}
    if trailing is not None and len(trailing):
        trail_map = {(t.kind, t.key): float(t.trailing_pts)
                     for t in trailing.itertuples()}
    pool = []
    for r in game.itertuples():
        row = by_id.get(r.dk_player_id)
        tkey = (("DST", r.team_abbr) if r.position == "DST"
                else ("K", str(r.display_name).upper()))
        if row is not None and pd.notna(row[objective]):
            value, source = float(row[objective]), "model"
        elif tkey in trail_map:
            value, source = trail_map[tkey], "trailing"
        elif pd.notna(r.dk_ppg):
            value, source = float(r.dk_ppg), "dk_ppg"
        else:
            continue  # no projection at all — can't rank the player
        draftable = getattr(r, "dk_draftable_id", None)
        cpt = getattr(r, "dk_cpt_draftable_id", None)
        sd = None
        if row is not None and pd.notna(row.get("proj_std")):
            sd = float(row["proj_std"])
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
                "proj_sd": sd,  # None -> sim-mode's FALLBACK_SD_RATIO
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
    # Correlated-draw construction, adopted 2026-08-01 (2025 replay:
    # capture 85.0% vs 80.7% MILP, >=90%-capture slates 16/41 vs 8/41).
    # sim=False restores the plain MILP-on-means path.
    sim: bool = True
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
    trailing = None
    trail_fn = getattr(store, "trailing_kdst", None)
    if trail_fn is not None:
        try:
            trailing = trail_fn(req.season, req.week)
        except Exception:  # trailing is a fallback nicety, never a blocker
            log.warning("trailing_kdst unavailable", exc_info=True)
    pool = _showdown_pool(game, proj, req.objective, trailing=trailing)
    if len(pool) < 6 or len({p["team"] for p in pool}) < 2:
        raise HTTPException(422, "Showdown pool too thin to build a lineup")
    pool_ids = {p["id"] for p in pool}
    wanted = set(req.locks) | ({req.captain} if req.captain is not None else set())
    if wanted - pool_ids:
        raise HTTPException(
            422, f"Players not in this game's projectable pool: {sorted(wanted - pool_ids)}"
        )

    if req.sim:
        from ..optimizer.showdown import sim_mode_entries

        lineups = sim_mode_entries(
            pool, req.n_lineups, seed=req.week, locks=set(req.locks),
            bans=set(req.bans) & pool_ids, captain_lock=req.captain,
        )
    else:
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
