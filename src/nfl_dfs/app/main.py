"""FastAPI service (guide Phase 7): slate view, projections table, lineup
builder with stacking options, exposure summary, DK-format CSV export.

Run locally:  uvicorn nfl_dfs.app.main:app --reload
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from functools import lru_cache

import pandas as pd
from fastapi import (Depends, FastAPI, File, HTTPException, Query, Response,
                     UploadFile)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from ..optimizer.export import (
    entry_count,
    exposure_summary,
    fill_entries_csv,
    showdown_exposure_summary,
    to_dk_csv,
    to_dk_showdown_csv,
)
from ..optimizer.lineup import core_and_variations, optimize_many
from ..optimizer.construction_presets import (
    INCUMBENT_GPP_PRESET_ID,
    LEGALITY_ONLY_PRESET_ID,
)
from ..optimizer.showdown import optimize_many_showdown
from ..inference.production_policy import (
    ADOPTED_CLASSIC_POLICY,
    contest_entry_policy,
)
from .corpus_research import router as corpus_research_router
from .store import BigQueryStore, ProjectionStore
from .week1_operating_book_api import (
    Week1OperatingBookAPIError,
    load_week1_operating_book_export,
)

app = FastAPI(title="Fingerblasters' Brain", version="0.1.0")

from pathlib import Path as _Path

app.mount("/static", StaticFiles(directory=_Path(__file__).parent / "static"),
          name="static")
app.include_router(corpus_research_router)
log = logging.getLogger(__name__)
_EXPLAINER_PATH = _Path(__file__).parent / "static" / "explainer.html"


@lru_cache
def default_store() -> ProjectionStore:
    return BigQueryStore()


def get_store() -> ProjectionStore:
    return app.dependency_overrides.get(default_store, default_store)()


class LineupRequest(BaseModel):
    season: int
    week: int
    draft_group_id: int | None = None  # classic slate; None = whole week pool
    n_lineups: int = Field(
        ADOPTED_CLASSIC_POLICY.default_entries, ge=1, le=150)
    contest_max_entries: int = Field(150, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    locks: list[int] = []
    bans: list[int] = []
    construction_preset_id: str = Field(
        INCUMBENT_GPP_PRESET_ID,
        pattern=(
            f"^({INCUMBENT_GPP_PRESET_ID}|{LEGALITY_ONLY_PRESET_ID})$"
        ),
    )
    # Optional means inherit the selected named preset; explicit zero/false
    # is a real deletion and is retained in the construction receipt.
    qb_stack_min: int | None = Field(None, ge=0, le=3)
    bring_back_min: int | None = Field(None, ge=0, le=2)
    forbid_rb_vs_dst: bool | None = None
    forbid_two_rb_same_team: bool | None = None
    min_lineup_salary: int | None = Field(None, ge=0, le=50_000)
    min_games: int | None = Field(None, ge=1, le=9)
    max_per_game: int | None = Field(None, ge=0, le=9)
    max_overlap: int | None = Field(None, ge=1, le=8)
    # Sim-mode (2026-08-03, fidelity fix): run the VALIDATED replay
    # engine on the live slate — correlated draws with the adopted EW
    # shaping, boom-draw candidates, tail-coverage selection. Falls back
    # to the plain MILP path on any failure. sim=False forces the old path.
    sim: bool = True
    # Apply converted watch-notes (boost/ban prefs) to the build
    # (2026-08-04, user request): False = pure algorithm, no manual
    # tilts — for comparing "my ideas" vs the untouched system.
    apply_notes: bool = True
    # Thesis constraints (2026-08-03): [{players: [dk_ids], min: k}] —
    # ">=k of my entries must contain this combo". Builds toward
    # correlated convictions; pairs with watchlist conversions.
    theses: list[dict] = []
    # Chalk-fade scaling (contest presets, 2026-08-03): 1.0 = validated
    # large-field fade; sharp/high-stakes fields use 0.5-0.7 — our fade
    # is soft-field-calibrated and sharp chalk busts less.
    lev_scale: float = Field(1.0, ge=0.0, le=2.0)
    # Field size is retained for contest comparison/metadata. The production
    # selector stays on its validated fixed 194 line; only an explicit
    # advanced tail_line request overrides it.
    field_size: int | None = Field(None, ge=100)
    tail_line: float | None = Field(None, ge=100, le=300)

    @model_validator(mode="after")
    def validate_contest_entry_limit(self):
        # FillEntriesRequest deliberately leaves this unset until its DK CSV
        # has been counted.  The copied build request is validated below.
        if self.n_lineups is not None:
            contest_entry_policy(
                self.contest_max_entries, self.n_lineups, self.lev_scale,
            )
        return self

    def entry_policy(self) -> dict:
        if self.n_lineups is None:
            raise ValueError("lineup count is unresolved")
        return contest_entry_policy(
            self.contest_max_entries, self.n_lineups, self.lev_scale,
        )

    def line(self) -> float:
        if self.tail_line is not None:
            return self.tail_line
        return ADOPTED_CLASSIC_POLICY.tail_line


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
      border-radius:8px;padding:1rem;display:flex;flex-direction:column;
      height:calc(100vh - 220px);min-height:340px}
#chatlog{flex:1;overflow-y:auto;font-size:.9rem;margin-bottom:.6rem;
         scroll-behavior:smooth}
#typing{display:inline-block;margin:.2rem 0 .2rem .8rem;color:#888}
#typing span{display:inline-block;width:6px;height:6px;margin:0 2px;
  background:#999;border-radius:50%;animation:blink 1.2s infinite}
#typing span:nth-child(2){animation-delay:.2s}
#typing span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,80%,100%{opacity:.25}40%{opacity:1}}
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
<select id='chatmodel' title='Model for this chat'>
<option value='claude-opus-5'>Opus</option>
<option value='claude-fable-5'>Fable</option></select>
<button id='chatbtn'>Send</button></div></div>
<script>
let hist=[];
const log=document.getElementById('chatlog'),inp=document.getElementById('chatin'),
      btn=document.getElementById('chatbtn');
function show(cls,text){const d=document.createElement('div');d.className=cls;
  d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;}
function showTyping(){
  const d=document.createElement('div');d.id='typing';
  d.innerHTML='<span></span><span></span><span></span>';
  log.appendChild(d);log.scrollTop=log.scrollHeight;}
function hideTyping(){const d=document.getElementById('typing');if(d)d.remove();}
async function send(){
  const q=inp.value.trim(); if(!q)return;
  inp.value=''; btn.disabled=true; show('u','You: '+q);
  hist.push({role:'user',content:q});
  showTyping();
  try{
    const r=await fetch('/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:hist,
        model:document.getElementById('chatmodel').value})});
    const j=await r.json();
    hideTyping();
    if(!r.ok){show('a','Error: '+(j.detail||r.status));}
    else{hist=j.messages; show('a',j.reply||'(no reply)');}
  }catch(e){hideTyping();show('a','Error: '+e);}
  btn.disabled=false; inp.focus();
}
btn.onclick=send;
inp.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script>
"""


_NAV_HTML = """
<div class='topbar'><img src='/static/logo.png' class='logo' alt=''><div class='brand'>Fingerblasters&#39; <span>Brain</span></div>
<a href='/'>Season</a><a href='/lineups/view'>Lineups</a>
<a href='/defense'>Defense</a><a href='/market'>Market</a>
<a href='/corpus-research'>Corpus research</a>
<a href='/watchlist'>Watchlist</a><a href='/explainer'>About</a>
<a href='/docs'>API</a>
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
<tr><td>Wed 10:00am CT<br>(every target week)</td><td style='text-align:left'>
<b>Combined weekly data run.</b> From the repository environment run
<code>nfl-weekly-data run --week W</code>. It verifies both saved vendor
sessions first and prompts for either expired login before starting the
unattended work. It triggers a secret-backed Odds API game-lines snapshot,
downloads only Fantasy Points source Week W&minus;1 Route Share, performs the
guarded archive/import, and captures the three pre-lock matchup reports. If
the prior-week report is not posted yet, retry Wednesday evening; finish
before Thursday 6:30am CT. The existing Wed&ndash;Sun game-odds and Thursday
props cloud schedules still run independently. SIS is preflighted every week,
but makes no paid queries until an evidence-approved recurring plan is passed
with <code>--sis-plan</code>. Never select or import Week W data for a Week W
prediction. Week 1 automatically skips Route Share because there is no prior
2026 week.</td></tr>
<tr><td>Wed/Sat/Sun ownership<br>(every main slate)</td><td
style='text-align:left'><b>Fantasy Points projected ownership.</b> The tracked
collector will archive DraftKings Classic Sunday Main when first posted,
Saturday evening, and before both Sunday book freezes. Use it to simulate the
opposing field, estimate duplicates and compare payout-aware portfolios&mdash;
not as a generic penalty to player scoring. After settlement, the exact
pre-lock snapshots are graded against imported contest ownership. Until the
collector is implemented and the Premium-page entitlement is confirmed, this
row is a preseason setup item rather than a manual copy/paste task.</td></tr>
<tr><td>Tue/Wed matchup snapshot<br>(every week)</td><td
style='text-align:left'><b>Fantasy Points QB Coverage, WR Coverage and OL/DL
Matchups.</b> Before the target week&#39;s first kickoff, run
<code>fantasy-points-matchups --season 2026 --week W --archive</code>. The
collector presses Apply, verifies Schedule Week W and every opponent against
the project schedule, then archives a fail-closed manifest. These snapshots
are research-only until a separately frozen prospective gate passes; do not
substitute the stale offseason samples.</td></tr>
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
Season page (fills contests/spent/won). For one target GPP per slate,
<b>download the full contest standings CSV while it is still available</b>
and save it in the project for import. That preserves ranks, lineups and
ownership for exact placement and ROI analysis.</td></tr>
<tr><td>Tue 8:00 (auto)</td><td style='text-align:left'>Lineups scored
vs actuals; best score fills itself. Click week numbers to review
entries by score.</td></tr></table></div>
<script>
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}document.addEventListener('DOMContentLoaded',()=>{
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

_EXPLAINER_APPBAR = """
<style>
.explainer-appbar{margin:0 -6vw 2rem;padding:.7rem 6vw;display:flex;
  align-items:center;gap:1rem;background:#0d1b2a;color:#fff;
  box-shadow:0 2px 12px rgba(13,27,42,.35);
  font-family:system-ui,-apple-system,'Segoe UI',sans-serif}
.explainer-appbar img{height:32px;width:32px;border-radius:8px;object-fit:cover;
  box-shadow:0 0 0 2px rgba(255,255,255,.25)}
.explainer-appbar .explainer-brand{font-weight:800;letter-spacing:.03em;
  white-space:nowrap}
.explainer-appbar .explainer-brand span{color:#53d337}
.explainer-appbar a{color:#c8cede;text-decoration:none;font-size:.88rem;
  padding:.35rem .75rem;border-radius:999px}
.explainer-appbar a:hover{color:#fff;background:rgba(255,255,255,.1)}
.explainer-appbar .current{color:#0d1b2a;background:#53d337;font-weight:700}
@media(max-width:42rem){.explainer-appbar{gap:.35rem;flex-wrap:wrap}
  .explainer-appbar a{padding:.25rem .45rem}
  .explainer-brand{width:calc(100% - 42px)}}
</style>
<nav class="explainer-appbar" aria-label="Product navigation">
  <img src="/static/logo.png" alt="">
  <div class="explainer-brand">Fingerblasters&#39; <span>Brain</span></div>
  <a href="/">Season</a>
  <a href="/lineups/view">Lineups</a>
  <a href="/explainer" class="current" aria-current="page">About</a>
</nav>
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
#week1book{margin:0 0 1rem;background:#fff;border:1px solid #cbd9d5;
  border-radius:10px;padding:1rem;box-shadow:0 1px 4px rgba(0,0,0,.05)}
#week1book h2{margin:0;font-size:1.15rem}
.week1-actions{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:.55rem 0}
.week1-actions button,.week1-actions a{padding:.42rem .75rem;border-radius:6px;
  border:1px solid #164a41;background:#fff;color:#164a41;text-decoration:none;
  cursor:pointer;font-size:.82rem}
.week1-viz{display:grid;grid-template-columns:minmax(250px,.8fr) minmax(320px,1.2fr);
  gap:.8rem;margin-top:.7rem}
.week1-chart{border:1px solid #e1e9e6;border-radius:8px;padding:.7rem}
.week1-chart h3{font-size:.9rem;margin:0 0 .5rem}
.week1-bar-row{display:grid;grid-template-columns:minmax(105px,1fr) 2fr 42px;
  gap:.45rem;align-items:center;font-size:.76rem;margin:.35rem 0}
.week1-bar{height:.72rem;background:#edf2f0;border-radius:999px;overflow:hidden}
.week1-bar i{display:block;height:100%;border-radius:999px;background:#2b8a78}
.week1-book-note{font-size:.8rem;color:#58635f;margin:.25rem 0}
@media(max-width:720px){.week1-viz{grid-template-columns:1fr}}
#portfolio{margin:1rem 0;background:#fff;border:1px solid #e5e5ef;
  border-radius:10px;padding:1rem;box-shadow:0 1px 3px rgba(0,0,0,.04)}
#portfolio h2{margin:0 0 .25rem;font-size:1.15rem}
.portfolio-note{margin:0 0 .8rem;color:#666;font-size:.82rem}
#portfolio-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));
  gap:.55rem;margin-bottom:.8rem}
.portfolio-metric{background:#f7f8fb;border:1px solid #e5e5ef;border-radius:8px;
  padding:.55rem .65rem}
.portfolio-metric b{display:block;font-size:1.15rem;color:#1a1a2e}
.portfolio-metric small{color:#666}
.portfolio-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));
  gap:.8rem}
.portfolio-chart{border:1px solid #e5e5ef;border-radius:8px;padding:.6rem;
  min-width:0}
.portfolio-chart h3{margin:0;font-size:.95rem}
.portfolio-chart p{margin:.2rem 0 .45rem;color:#666;font-size:.76rem}
.portfolio-chart svg{display:block;width:100%;height:auto;background:#fbfbfd;
  border-radius:6px}
.portfolio-legend{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:.4rem;
  font-size:.72rem;color:#555}
.portfolio-legend span{white-space:nowrap}
.portfolio-dot{display:inline-block;width:.65rem;height:.65rem;border-radius:50%;
  margin-right:.2rem;vertical-align:-.05rem}
.portfolio-clear{border:1px solid #aaa;background:#fff;border-radius:5px;
  padding:.25rem .5rem;cursor:pointer;font-size:.75rem;float:right}
.card.portfolio-match{outline:3px solid #7b61ff;box-shadow:0 2px 12px rgba(91,65,220,.28)}
.card.portfolio-dim{opacity:.28}
@media(max-width:520px){.portfolio-grid{grid-template-columns:1fr}}
"""

_LINEUPS_JS = """
let lastBuild=null;
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
const SVG_NS='http://www.w3.org/2000/svg';
const PORTFOLIO_COLORS=['#6544d9','#008f8c','#e76f51','#2d6a9f','#d69e00',
  '#8f4f9f','#3b8d4c','#d1495b','#557a95','#9c6644','#5c677d','#bc6c25'];
const POS_COLORS={QB:'#6f42c1',RB:'#198754',WR:'#0d6efd',TE:'#fd7e14',DST:'#6c757d'};
function svgEl(tag,attrs={}){
  const e=document.createElementNS(SVG_NS,tag);
  for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);
  return e;
}
function playerKey(p){return String(p.id??p.dk_id??p.name);}
function lineupIds(lu){return new Set(lu.players.map(playerKey));}
function sharedPlayers(a,b){let n=0;for(const x of a)if(b.has(x))n++;return n;}
function clearPortfolioSelection(){
  document.querySelectorAll('#cards .card[data-lineup-index]').forEach(c=>
    c.classList.remove('portfolio-match','portfolio-dim'));
}
function highlightPortfolio(test){
  document.querySelectorAll('#cards .card[data-lineup-index]').forEach(c=>{
    const yes=test(c);
    c.classList.toggle('portfolio-match',yes);
    c.classList.toggle('portfolio-dim',!yes);});
  const first=document.querySelector('#cards .card.portfolio-match');
  if(first)first.scrollIntoView({behavior:'smooth',block:'center'});
}
function lineupFamilies(lineups,sets){
  const groups=[];
  lineups.forEach((lu,i)=>{
    let best=-1,bestShared=-1;
    groups.forEach((g,gi)=>{
      const n=sharedPlayers(sets[i],sets[g.seed]);
      if(n>bestShared){best=gi;bestShared=n;}});
    const need=Math.ceil(Math.min(sets[i].size,
      best<0?sets[i].size:sets[groups[best].seed].size)*.55);
    if(best>=0&&bestShared>=need)groups[best].members.push(i);
    else groups.push({seed:i,members:[i]});
  });
  return groups;
}
function renderLineupMap(lineups,sets,groups){
  const box=document.getElementById('lineup-map');box.innerHTML='';
  const shown=lineups.length<=120
    ?lineups.map((_,i)=>i)
    :Array.from({length:120},(_,i)=>Math.floor(i*(lineups.length-1)/119));
  const visible=new Set(shown),w=620,h=360;
  const svg=svgEl('svg',{viewBox:`0 0 ${w} ${h}`,
    role:'img','aria-label':'Lineup families grouped by shared players'});
  const cols=Math.max(1,Math.ceil(Math.sqrt(groups.length*w/h))),
        rows=Math.ceil(groups.length/cols),cw=w/cols,ch=h/rows;
  groups.forEach((g,gi)=>{
    const members=g.members.filter(i=>visible.has(i));if(!members.length)return;
    const cx=(gi%cols+.5)*cw,cy=(Math.floor(gi/cols)+.54)*ch,
          ring=Math.min(cw,ch)*.31;
    const label=svgEl('text',{x:cx,y:Math.max(13,cy-ring-10),
      'text-anchor':'middle','font-size':'11',fill:'#555'});
    label.textContent=`Family ${gi+1} · ${g.members.length}`;svg.appendChild(label);
    members.forEach((idx,j)=>{
      const angle=2*Math.PI*j/Math.max(1,members.length),
            radius=members.length===1?0:ring*(.4+.6*((j%3)+1)/3),
            x=cx+Math.cos(angle)*radius,y=cy+Math.sin(angle)*radius,
            c=svgEl('circle',{cx:x,cy:y,r:members.length>35?5:7,
              fill:PORTFOLIO_COLORS[gi%PORTFOLIO_COLORS.length],
              stroke:'#fff','stroke-width':'1.5',tabindex:'0',
              style:'cursor:pointer'}),
            near=Math.max(...sets.map((s,k)=>k===idx?0:sharedPlayers(sets[idx],s)));
      const title=svgEl('title');
      title.textContent=`Lineup #${lineups[idx].rank??idx+1}; family ${gi+1}; closest lineup shares ${near} players`;
      c.appendChild(title);
      c.addEventListener('click',()=>highlightPortfolio(card=>+card.dataset.lineupIndex===idx));
      c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();c.click();}});
      svg.appendChild(c);
    });
  });
  box.appendChild(svg);
  const note=document.getElementById('lineup-map-note');
  note.textContent=(lineups.length>120?'Showing an even sample of 120 entries. ':'')+
    'A family shares at least 55% of its roster with the family seed. Click a dot to find that entry.';
}
function renderPlayerNetwork(lineups){
  const box=document.getElementById('player-map');box.innerHTML='';
  const counts=new Map(),meta=new Map(),pairCounts=new Map();
  for(const lu of lineups){
    const ps=lu.players.map(p=>{const id=playerKey(p);meta.set(id,p);
      counts.set(id,(counts.get(id)||0)+1);return id;});
    for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++){
      const key=[ps[i],ps[j]].sort().join('\u001f');
      pairCounts.set(key,(pairCounts.get(key)||0)+1);}}
  const ids=[...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))
    .slice(0,50).map(x=>x[0]),keep=new Set(ids),w=620,h=360;
  const nodes=ids.map((id,i)=>({id,p:meta.get(id),count:counts.get(id),
    x:w/2+135*Math.cos(2*Math.PI*i/ids.length),
    y:h/2+135*Math.sin(2*Math.PI*i/ids.length),vx:0,vy:0}));
  const byId=new Map(nodes.map(n=>[n.id,n])),minPair=Math.max(2,Math.ceil(lineups.length*.04));
  let edges=[...pairCounts].map(([key,count])=>{const [a,b]=key.split('\u001f');
      return{a,b,count};}).filter(e=>keep.has(e.a)&&keep.has(e.b)&&e.count>=minPair)
    .sort((a,b)=>b.count-a.count).slice(0,140);
  for(let it=0;it<90;it++){
    for(const n of nodes){n.vx+=(w/2-n.x)*.006;n.vy+=(h/2-n.y)*.006;}
    for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
      const a=nodes[i],b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,
            d2=Math.max(36,dx*dx+dy*dy),f=35/d2;
      a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f;}
    for(const e of edges){const a=byId.get(e.a),b=byId.get(e.b),
      dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),
      target=105-45*Math.min(1,e.count/Math.max(1,Math.min(a.count,b.count))),
      f=(d-target)*.007,fx=dx/d*f,fy=dy/d*f;
      a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}
    for(const n of nodes){n.vx*=.74;n.vy*=.74;n.x=Math.max(28,Math.min(w-75,n.x+n.vx));
      n.y=Math.max(24,Math.min(h-24,n.y+n.vy));}}
  const svg=svgEl('svg',{viewBox:`0 0 ${w} ${h}`,
    role:'img','aria-label':'Player co-occurrence network'});
  for(const e of edges){const a=byId.get(e.a),b=byId.get(e.b),
    line=svgEl('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:'#aab0bf',
      'stroke-opacity':Math.min(.7,.12+e.count/lineups.length),
      'stroke-width':Math.min(4,.5+4*e.count/lineups.length)});
    const title=svgEl('title');title.textContent=`Together in ${e.count} lineups`;
    line.appendChild(title);svg.appendChild(line);}
  nodes.forEach((n,i)=>{
    const r=5+12*Math.sqrt(n.count/lineups.length),
          c=svgEl('circle',{cx:n.x,cy:n.y,r,
            fill:POS_COLORS[n.p.pos]||'#555',stroke:'#fff','stroke-width':'1.5',
            tabindex:'0',style:'cursor:pointer'}),title=svgEl('title');
    title.textContent=`${n.p.name} · ${n.p.team} ${n.p.pos} · ${n.count}/${lineups.length} lineups (${(100*n.count/lineups.length).toFixed(1)}%)`;
    c.appendChild(title);
    c.addEventListener('click',()=>highlightPortfolio(card=>
      (card.dataset.playerIds||'').split(',').includes(n.id)));
    c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();c.click();}});
    svg.appendChild(c);
    if(i<15){const t=svgEl('text',{x:n.x+r+2,y:n.y+3,'font-size':'9',fill:'#333'});
      t.textContent=n.p.name.split(' ').slice(-1)[0];svg.appendChild(t);}
  });
  box.appendChild(svg);
  document.getElementById('player-map-note').textContent=
    `${ids.length} highest-exposure players shown; a line connects players used together in at least ${minPair} entries. Click a player to find every lineup containing them.`;
}
function renderPortfolio(lineups){
  const panel=document.getElementById('portfolio');
  if(!lineups||!lineups.length){panel.hidden=true;return;}
  panel.hidden=false;clearPortfolioSelection();
  const sets=lineups.map(lineupIds),groups=lineupFamilies(lineups,sets);
  let pairs=0,totalShared=0,maxShared=0;
  for(let i=0;i<sets.length;i++)for(let j=i+1;j<sets.length;j++){
    const n=sharedPlayers(sets[i],sets[j]);pairs++;totalShared+=n;maxShared=Math.max(maxShared,n);}
  const counts=new Map();for(const lu of lineups)for(const p of lu.players){
    const id=playerKey(p);counts.set(id,(counts.get(id)||0)+1);}
  const top5=[...counts.values()].sort((a,b)=>b-a).slice(0,5)
    .reduce((a,b)=>a+b,0)/(lineups.length*(lineups[0].players.length||1));
  const uniqueRosters=new Set(sets.map(s=>[...s].sort().join('|'))).size;
  const metrics=[['Lineups',lineups.length],['Unique players',counts.size],
    ['Lineup families',groups.length],['Avg. shared players',pairs?(totalShared/pairs).toFixed(2):'—'],
    ['Maximum overlap',pairs?maxShared:'—'],['Top-5 concentration',(100*top5).toFixed(1)+'%'],
    ['Exact duplicates',lineups.length-uniqueRosters]];
  document.getElementById('portfolio-metrics').innerHTML=metrics.map(([k,v])=>
    `<div class='portfolio-metric'><b>${esc(v)}</b><small>${esc(k)}</small></div>`).join('');
  renderLineupMap(lineups,sets,groups);renderPlayerNetwork(lineups);
}
async function loadWeek1OperatingBook(){
  const status=document.getElementById('week1status'),viz=document.getElementById('week1viz'),
        csv=document.getElementById('week1csv');
  status.textContent='Exact-reading the immutable Week-1 book...';viz.hidden=true;csv.hidden=true;
  try{
    const r=await fetch('/week1/operating-book'),j=await r.json();
    if(!r.ok){status.textContent='Canonical book not available yet: '+(j.detail||r.status);return;}
    status.textContent=`K${j.k} · exact artifact ${j.materialization_sha256.slice(0,12)}… · `+
      `cap-4 off · Tier 3 ${j.tier3_used?'on':'empty'} · no tuning controls accepted.`;
    const labels={'boom-first-40-160':'Tier 1 boom-first',
      'ceiling-all-boom-0-200':'Tier 2 all-boom','cross-law-40-100-60':'Tier 2 BX60'},
      colors={'boom-first-40-160':'#216869','ceiling-all-boom-0-200':'#f2a541',
        'cross-law-40-100-60':'#7b61ff'};
    document.getElementById('week1sources').innerHTML=Object.entries(j.source_counts).map(([id,n])=>
      `<div class='week1-bar-row'><span>${esc(labels[id]||id)}</span>`+
      `<span class='week1-bar'><i style='width:${100*n/j.k}%;background:${colors[id]||'#2b8a78'}'></i></span>`+
      `<b>${n}</b></div>`).join('');
    const players=new Map();
    for(const lu of j.lineups)for(const p of lu.players){const id=String(p.dk_draftable_id),
      row=players.get(id)||{p,n:0};row.n++;players.set(id,row);}
    const top=[...players.values()].sort((a,b)=>b.n-a.n||a.p.display_name.localeCompare(b.p.display_name)).slice(0,16),
      max=Math.max(1,...top.map(x=>x.n));
    document.getElementById('week1exposure').innerHTML=top.map(x=>
      `<div class='week1-bar-row'><span>${esc(x.p.display_name)} <small>${esc(x.p.position)} ${esc(x.p.team)}</small></span>`+
      `<span class='week1-bar'><i style='width:${100*x.n/max}%'></i></span>`+
      `<b>${x.n}</b></div>`).join('');
    viz.hidden=false;csv.hidden=false;
  }catch(e){status.textContent='Canonical book could not be loaded: '+e;}
}
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
        o.dataset.cfg=JSON.stringify(c);
        o.textContent=`${c.name} · $${c.entry_fee} · `+
          `${(+c.field_size).toLocaleString()} entries · `+
          `${c.entry_limit||150}-max (line ${c.tail_line})`;
        grp.appendChild(o);}
      sel.appendChild(grp);};
    add(j.live,'Live DK contests'); add(j.presets,'Presets');
    const applyCfg=()=>{
      const o=sel.options[sel.selectedIndex]; if(!o)return;
      const c=JSON.parse(o.dataset.cfg||'{}');
      document.getElementById('fsize').value=c.field_size||sel.value;
      document.getElementById('entrylimit').value=c.entry_limit||150;
      if(c.entries)document.getElementById('n').value=c.entries;
      applyEntryPolicy(false,c.lev_scale??1,c.note||'');};
    if(sel.options.length)applyCfg();
    sel.onchange=applyCfg;
  }catch(e){}}
function slateSel(){
  const v=document.getElementById('slate').value;
  if(v.startsWith('sd:'))return{sd:true,gid:+v.slice(3)};
  return{sd:false,gid:v?+v:null};}
function entryProfile(limit){
  if(limit===1)return{name:'single-entry individual-tail',cap:.7};
  if(limit<=3)return{name:'3-max self-sufficient tail',cap:.8};
  if(limit<=20)return{name:'compact-max tail coverage',cap:.9};
  return{name:'large-max tail coverage',cap:1};}
function applyEntryPolicy(fillEntries=false,requestedLev=null,note=''){
  const limitEl=document.getElementById('entrylimit'),
        nEl=document.getElementById('n'),levEl=document.getElementById('lev');
  let limit=Math.max(1,Math.min(150,+limitEl.value||150));
  limitEl.value=limit;
  const maxBook=Math.min(limit,80),p=entryProfile(limit);
  nEl.min=1;nEl.max=maxBook;
  if(fillEntries||+nEl.value>maxBook||+nEl.value<1)nEl.value=maxBook;
  const asked=requestedLev==null?p.cap:+requestedLev;
  levEl.value=Math.min(asked,p.cap);
  document.getElementById('chint').textContent=
    `auto: ${nEl.value} entries · ${limit}-max · ${p.name} · `+
    `chalk-fade cap x${p.cap} · fixed 194 tail line`+(note?` — ${note}`:'');}
function reqBody(){
  const sd=slateSel().sd;
  const base={season:+document.getElementById('season').value,
    week:+document.getElementById('week').value,
    draft_group_id:slateSel().gid,
    n_lineups:+document.getElementById('n').value,
    objective:document.getElementById('obj').value};
  if(sd)return base;
  return{...base,
    field_size:+document.getElementById('fsize').value||null,
    contest_max_entries:+document.getElementById('entrylimit').value||150,
    lev_scale:+document.getElementById('lev').value||1,
    apply_notes:document.getElementById('usenotes').checked};}
function buildKey(body){return JSON.stringify(body);}
function setModeControls(){
  const sd=slateSel().sd;
  for(const id of ['contestctl','entrylimitctl','fieldctl','notesctl']){
    const e=document.getElementById(id); if(e)e.style.display=sd?'none':'';}
  const obj=document.getElementById('obj');
  if(!sd)obj.value='proj_points';
  obj.disabled=!sd;
  document.getElementById('objhint').textContent=sd
    ? 'Choose the Showdown projection objective.'
    : 'Classic simulation uses the validated tournament objective; Mean is fixed.';
}
function slotNames(players){
  const slots=['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'];
  return players.map((p,i)=>({slot:slots[i]||p.pos,p}));}
async function build(){
  const st=document.getElementById('status'),
        cards=document.getElementById('cards'),
        sd=slateSel().sd;
  st.textContent='Building lineups (simulating 30k worlds + candidate solves; ~1-4 min, first build of the day slowest)...';
  cards.innerHTML=''; document.getElementById('portfolio').hidden=true;
  document.getElementById('go').disabled=true;
  try{
    const body=reqBody();
    const r=await fetch(sd?'/showdown/lineups':'/lineups',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)});
    const j=await r.json();
    if(!r.ok){st.textContent='Error: '+(j.detail||r.status);return;}
    lastBuild={key:buildKey(body),payload:j,showdown:sd};
    st.textContent=sd
      ? j.lineups.length+' Captain Mode lineups · '+j.game.game+' ('+
        j.game.day+'). Captain scores 1.5x and costs 1.5x.'
      : j.lineups.length+' lineups · '+(j.policy?.policy_id||'policy unknown')+
        ' · '+(j.policy?.contest_entry_policy?.profile||'entry profile unknown')+
        ' · '+(j.policy?.simulation_law?.usage_allocation||
               'simulation law unreported')+' usage'+
        ' · model '+(j.policy?.model_version||'unreported')+
        '. Confidence = P(score >= '+
        (j.tail_line||194)+') per the sim — PORTFOLIO-level validated; '+
        'the within-set ordering is approximate (measured ~coin-flip on '+
        'realized outcomes), so treat all entries as co-equal shots.';
    if(j.model_health&&j.model_health.warning){
      const w=document.createElement('div');
      w.style.cssText='color:#b00;font-weight:600;margin:.3rem 0';
      w.textContent='\u26a0 '+j.model_health.warning;
      st.after(w);}
    j.lineups.forEach((lu,i)=>{
      const named=sd
        ? lu.players.map((p,k)=>({slot:k?'FLEX':'CPT',p,cpt:!k}))
        : slotNames(lu.players);
      const rows=named.map(({slot,p,cpt})=>{
        const sal=cpt?Math.round(p.salary*1.5):p.salary,
              pr=cpt?1.5*p.proj:+p.proj;
        const wn=p.watch_note?` <span title="${String(p.watch_note)
          .replace(/"/g,'&quot;')}" style='cursor:help'>&#128221;</span>`:'';
        const lev=(p.lev_pct!=null&&Math.abs(p.lev_pct)>=8)
          ?` <small title='Lev%: our exposure minus expected field ownership'`+
           ` style='color:${p.lev_pct>0?"#0a7":"#c60"}'>${p.lev_pct>0?"+":""}${p.lev_pct}%</small>`:'';
        return `<tr${p.watch_note?` title="${String(p.watch_note)
          .replace(/"/g,'&quot;')}"`:''}><td><span class='slot'>${slot}</span></td>`+
        `<td style='text-align:left'>${esc(p.name)}${wn}${lev}</td>`+
        `<td>${p.team}${p.opp?' @ '+p.opp:''}</td>`+
        `<td>$${sal.toLocaleString()}</td>`+
        `<td>${pr.toFixed(1)}</td></tr>`;}).join('');
      const head=sd
        ? `<header><span>#${i+1}</span>`+
          `<span class='conf'>CPT ${esc(lu.captain.name)}</span>`+
          `<span>${lu.proj.toFixed(1)} pts proj</span></header>`
        : `<header><span>#${lu.rank}</span>`+
          `<span class='conf'>${lu.confidence}%</span>`+
          `<span>${lu.proj_mean} pts proj</span></header>`;
      const el=document.createElement('div'); el.className='card';
      el.dataset.lineupIndex=i;
      el.dataset.playerIds=lu.players.map(playerKey).join(',');
      el.innerHTML=head+
        `<table><tr><th></th><th style='text-align:left'>Player</th>`+
        `<th>Game</th><th>Salary</th><th>Proj</th></tr>${rows}`+
        `<tfoot><tr><td colspan='3'>Total</td>`+
        `<td>$${lu.salary.toLocaleString()}</td>`+
        `<td>${lu.proj.toFixed(1)}</td></tr></tfoot></table>`;
      cards.appendChild(el);});
    renderPortfolio(j.lineups);
    if(sd&&j.captain_board&&j.captain_board.length){
      const cb=j.captain_board.slice(0,12),
            pc=v=>v==null?'&mdash;':(100*v).toFixed(1)+'%';
      const rows=cb.map(m=>`<tr><td style='text-align:left'>${esc(m.name)}`+
        ` <small>${m.team||''} ${m.position||''}</small></td>`+
        `<td>${pc(m.cpt_opt)}</td><td>${pc(m.flex_opt)}</td>`+
        `<td>${pc(m.p_top)}</td><td>${pc(m.p_top6)}</td></tr>`).join('');
      const el=document.createElement('div'); el.className='card';
      el.style.gridColumn='1/-1';
      el.innerHTML=`<header><span>Captain board</span>`+
        `<span title='CPT-opt / FLEX-opt: share of simulated worlds whose`+
        ` salary-aware optimal lineup used the player at captain / flex.`+
        ` Top scorer: outscores the whole slate (best captain ignoring`+
        ` salary). Top 6: lands in the perfect lineup ignoring salary.'`+
        ` style='cursor:help'>computed from this build&#39;s sims &#9432;</span></header>`+
        `<table><tr><th style='text-align:left'>Player</th><th>CPT-opt</th>`+
        `<th>FLEX-opt</th><th>Top scorer</th><th>Top 6</th></tr>${rows}</table>`;
      cards.appendChild(el);}
  }catch(e){st.textContent='Error: '+e;}
  document.getElementById('go').disabled=false;}
document.getElementById('go').onclick=build;
document.getElementById('week1load').onclick=loadWeek1OperatingBook;
document.getElementById('cmpgo').onclick=async()=>{
  const cs=[];
  for(const i of [0,1]){
    const f=+document.getElementById('cf'+i).value,
          s=+document.getElementById('cs'+i).value,
          p=+document.getElementById('cp'+i).value,
          e=+document.getElementById('ce'+i).value;
    if(f&&s&&p&&e)cs.push({name:document.getElementById('cn'+i).value||('Contest '+(i+1)),
      entry_fee:f,field_size:s,top_prize:p,n_entries:e});}
  if(cs.length<2){document.getElementById('cmpout').textContent=
    'Fill both contests.';return;}
  const r=await fetch('/api/contest-compare',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({contests:cs})});
  const j=await r.json();
  if(!r.ok){document.getElementById('cmpout').textContent='Error: '+
    JSON.stringify(j.detail).slice(0,120);return;}
  document.getElementById('cmpout').innerHTML=
    j.contests.map(c=>`<div><b>${c.name}</b>: est line ${c.est_line}, `+
      `P(reach) ${(100*c.p_reach).toFixed(1)}%, top-prize EV `+
      `$${c.ev_top.toLocaleString()} on $${c.cost} `+
      `(<b>${c.ev_per_dollar}</b>/$)</div>`).join('')+
    `<div style='margin-top:.3rem'><b>Better call: ${j.verdict}</b> `+
    `<small>${j.note}</small></div>`;};
function downloadCsv(text,name){
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([text],{type:'text/csv'}));
  a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
document.getElementById('csv').onclick=async()=>{
  const st=document.getElementById('status'), body=reqBody(), sd=slateSel().sd;
  if(!lastBuild||lastBuild.showdown!==sd||lastBuild.key!==buildKey(body)){
    st.textContent='Build lineups first; CSV always downloads that exact preview.';
    return;
  }
  downloadCsv(lastBuild.payload.dk_csv,sd?'dk_showdown_lineups.csv':'dk_lineups.csv');
  if(!sd){
    const r=await fetch('/lineups/record',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({season:body.season,week:body.week,
        lineups:lastBuild.payload.lineups.map(x=>({players:x.players}))})});
    if(!r.ok)st.textContent='CSV downloaded, but recording it for scoring failed: '+
      ((await r.json()).detail||r.status);
  }
};
document.getElementById('recgo').onclick=async()=>{
  const out=document.getElementById('recout'),file=document.getElementById('recentry').files[0],
        uri=document.getElementById('recuri').value.trim(),
        sha=document.getElementById('recsha').value.trim(),slate=slateSel();
  if(slate.sd||!slate.gid){out.textContent='Choose an explicit Classic slate.';return;}
  if(!file||!uri||!sha){out.textContent='Choose DKEntries.csv and provide the pinned artifact URI/checksum.';return;}
  let status=[];
  try{status=JSON.parse(document.getElementById('recstatus').value||'[]');}
  catch(e){out.textContent='Game status must be a JSON array.';return;}
  out.textContent='Checking timestamped game state and simulated remaining worlds...';
  const r=await fetch('/lineups/entries/recourse/preview',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({
      entries_csv:await file.text(),draft_group_id:slate.gid,
      artifact_uri:uri,artifact_sha256:sha,status_information:status})});
  const j=await r.json();
  if(!r.ok){out.textContent='Recourse blocked: '+(j.detail||r.status);return;}
  const counts=j.world_adapter_receipt?.status_counts||{},changes=j.changes||[];
  out.innerHTML=`<b>Shadow preview only — upload remains blocked.</b> `+
    `Artifact arm ${esc(j.artifact_arm)}. `+
    `${j.changed_entries} of ${j.entries} entries proposed to change. `+
    `As of ${esc(j.as_of)}; next upload deadline ${esc(j.next_upload_deadline||'none')}. `+
    `Game states: ${counts.final||0} final, ${counts.in_progress||0} in progress, `+
    `${counts.not_started||0} not started.`+
    (changes.length?`<ol>${changes.map(c=>`<li>Entry ${esc(c.entry_id)}: `+
      `out ${esc(c.players_out.join(', ')||'none')}; `+
      `in ${esc(c.players_in.join(', ')||'none')} (${esc(c.reach_class)})</li>`
      ).join('')}</ol>`:'');
};
document.getElementById('recrehearse').onclick=async()=>{
  const out=document.getElementById('recout'),file=document.getElementById('recentry').files[0],
        uri=document.getElementById('recuri').value.trim(),
        sha=document.getElementById('recsha').value.trim(),slate=slateSel();
  if(slate.sd||!slate.gid){out.textContent='Choose an explicit Classic slate.';return;}
  if(!file||!uri||!sha){out.textContent='Choose DKEntries.csv and provide the pinned artifact URI/checksum.';return;}
  let status=[];
  try{status=JSON.parse(document.getElementById('recstatus').value||'[]');}
  catch(e){out.textContent='Game status must be a JSON array.';return;}
  out.textContent='Generating the entry-bound file internally and validating it...';
  const r=await fetch('/lineups/entries/recourse/rehearsal',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({
      entries_csv:await file.text(),draft_group_id:slate.gid,
      artifact_uri:uri,artifact_sha256:sha,status_information:status})});
  const j=await r.json();
  if(!r.ok){out.textContent='Rehearsal blocked: '+(j.detail||r.status);return;}
  const v=j.validation_receipt||{};
  out.innerHTML=`<b>Rehearsal passed; no CSV was returned.</b> `+
    `${v.entries} entries, ${v.changed_slots} changed slots, ${v.locked_slots} locked slots. `+
    `Generated bytes ${j.generated_csv_bytes}; SHA-256 ${esc(j.generated_csv_sha256)}. `+
    `Upload licensed: ${j.upload_licensed}.`;
};
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
  const r=await fetch('/prefs',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({season:+document.getElementById('season').value,
      week:+document.getElementById('week').value,display_name:v,kind})});
  if(!r.ok){document.getElementById('status').textContent='Preference not added: '+
    ((await r.json()).detail||r.status); return;}
  document.getElementById(inputId).value=''; loadPrefs(); noteConflicts();
}
async function noteConflicts(){
  try{
    const se=+document.getElementById('season').value,
          wk=+document.getElementById('week').value;
    if(!se||!wk)return;
    const r=await fetch(`/api/note-conflicts?season=${se}&week=${wk}`);
    if(!r.ok)return;
    const j=await r.json();
    let el=document.getElementById('noteconf');
    if(!el){el=document.createElement('div');el.id='noteconf';
      el.style.cssText='color:#b60;font-size:.85rem;margin:.2rem 0';
      document.getElementById('prefs').after(el);}
    el.innerHTML=j.length?('\u26a0 possible double-counts: '+
      j.map(c=>`<b>${c.player}</b> (${c.kind}: we ${c.our_proj} vs market `+
        `${c.market_proj})`).join(' · ')):'';
  }catch(e){}}
document.getElementById('banin').addEventListener('keydown',
  e=>{if(e.key==='Enter')addPref('ban','banin');});
document.getElementById('boostin').addEventListener('keydown',
  e=>{if(e.key==='Enter')addPref('boost','boostin');});
document.getElementById('season').addEventListener('change',()=>{loadPrefs();noteConflicts();});
document.getElementById('week').addEventListener('change',()=>{loadPrefs();noteConflicts();});
document.getElementById('slate').addEventListener('change',setModeControls);
document.getElementById('entrylimit').addEventListener('change',
  ()=>applyEntryPolicy(true));
(async()=>{
  await loadSlates();
  await Promise.all([loadClassicSlates(),loadShowdownSlates(),loadContests()]);
  setModeControls(); loadPrefs(); noteConflicts(); loadWeek1OperatingBook();
})();
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
        f"<section id='week1book'><h2>Week 1 canonical operating book</h2>"
        f"<p class='week1-book-note'>This panel reads only the generation-pinned "
        f"boom-first / coverage-194 artifact. It cannot accept locks, bans, "
        f"tail lines, construction changes, cap-4, or other build controls.</p>"
        f"<div class='week1-actions'><button id='week1load' type='button'>"
        f"Refresh exact book</button><a id='week1csv' hidden "
        f"href='/week1/operating-book.csv'>Download exact DK CSV</a>"
        f"<span id='week1status'>Waiting for the pre-lock artifact.</span></div>"
        f"<div id='week1viz' class='week1-viz' hidden>"
        f"<section class='week1-chart'><h3>Book composition</h3>"
        f"<div id='week1sources'></div></section>"
        f"<section class='week1-chart'><h3>Highest player exposure</h3>"
        f"<div id='week1exposure'></div></section></div></section>"
        f"<div id='controls'>"
        f"<label>Season<input id='season' type='number'></label>"
        f"<label>Week<input id='week' type='number'></label>"
        f"<label>Slate<select id='slate' style='width:15rem'>"
        f"<option value=''>Whole week pool (no slate filter)</option>"
        f"</select></label>"
        f"<label id='contestctl'>Contest<select id='contest' style='width:16rem'></select>"
        f"</label>"
        f"<label id='entrylimitctl' title='DraftKings maximum entries per player for this contest'>"
        f"Contest max / player<input id='entrylimit' type='number' min='1' max='150' value='150'>"
        f"</label>"
        f"<label id='fieldctl'>Field size<input id='fsize' type='number' value='20000'>"
        f"</label>"
        f"<label>Entries<input id='n' type='number' min='1' max='80' value='"
        f"{ADOPTED_CLASSIC_POLICY.default_entries}'></label>"
        f"<input id='lev' type='hidden' value='1'>"
        f"<div id='chint' style='font-size:.8em;color:#888'></div>"
        f"<label>Objective<select id='obj'>"
        f"<option value='proj_points'>Mean (GPP default — replay-validated; sim mode always uses this + validated tilts)</option>"
        f"<option value='proj_p90'>Ceiling p90</option>"
        f"<option value='proj_p50'>Median</option></select>"
        f"<small id='objhint'></small></label>"
        f"<label id='notesctl' style='display:flex;align-items:center;gap:.35rem' "
        f"title='On: your converted notes tilt the build — boost/ban prefs AND multiplier notes from chat conversions. "
        f"Off: the pure validated algorithm, no manual adjustments — "
        f"build both ways to compare.'>"
        f"<input id='usenotes' type='checkbox' checked> My notes</label>"
        f"<button id='go' style='padding:.5rem 1.2rem;background:#1a1a2e;"
        f"color:#fff;border:0;border-radius:6px;cursor:pointer'>Build</button>"
        f"<button id='csv' style='padding:.5rem 1.2rem;background:#fff;"
        f"border:1px solid #1a1a2e;border-radius:6px;cursor:pointer'>"
        f"DK CSV</button>"
        f"<label>Ban player<input id='banin' placeholder='name'></label>"
        f"<label>Boost player<input id='boostin' placeholder='name'></label>"
        f"</div><div id='prefs' style='margin:.5rem 0;font-size:.85rem'></div>"
        f"<details style='margin:.4rem 0'><summary style='cursor:pointer;"
        f"font-size:.9rem'>Contest comparator (which contest is the better "
        f"call?)</summary><div id='cmp' style='display:flex;gap:1rem;"
        f"flex-wrap:wrap;margin:.4rem 0'>"
        + "".join(
            f"<div style='border:1px solid #ccc;border-radius:8px;"
            f"padding:.5rem'><b>Contest {i+1}</b><br>"
            f"<label>Name<input id='cn{i}' placeholder='e.g. \u00245 Milly'"
            f" style='width:9rem'></label><br>"
            f"<label>Entry fee $<input id='cf{i}' type='number' value='{v[0]}'"
            f" style='width:5rem'></label><br>"
            f"<label>Field size<input id='cs{i}' type='number' value='{v[1]}'"
            f" style='width:7rem'></label><br>"
            f"<label>Top prize $<input id='cp{i}' type='number' value='{v[2]}'"
            f" style='width:7rem'></label><br>"
            f"<label>My entries<input id='ce{i}' type='number' value='{v[3]}'"
            f" style='width:4rem'></label></div>"
            for i, v in enumerate([(5, 832000, 1000000, 4),
                                   (20, 100000, 200000, 4)]))
        + f"<div><button id='cmpgo' style='padding:.4rem 1rem'>Compare"
        f"</button><div id='cmpout' style='font-size:.85rem;max-width:22rem'>"
        f"</div></div></div></details>"
        f"<details id='recourse-panel' style='margin:.4rem 0'><summary "
        f"style='cursor:pointer;font-size:.9rem'>Prospective late-swap "
        f"preview (shadow only)</summary><div style='display:grid;gap:.4rem;"
        f"max-width:52rem;margin:.5rem 0'>"
        f"<label>Current filled DKEntries.csv<input id='recentry' type='file' "
        f"accept='.csv,text/csv'></label>"
        f"<label>Retained-world artifact URI<input id='recuri' "
        f"placeholder='gs://.../recourse_worlds/...npz'></label>"
        f"<label>Artifact SHA-256<input id='recsha' maxlength='64'></label>"
        f"<label>Timestamped game status JSON<textarea id='recstatus' rows='4' "
        f"placeholder='[&#123;&quot;dk_id&quot;:&quot;...&quot;,&quot;points_to_date&quot;:12.5,"
        f"&quot;game_status&quot;:&quot;final&quot;,&quot;available_at&quot;:&quot;...Z&quot;&#125;]'"
        f"></textarea></label><div><button id='recgo' type='button'>Preview proposed "
        f"changes</button> <button id='recrehearse' type='button'>Rehearse fill + "
        f"validation</button></div><div id='recout' style='font-size:.85rem'>No preview "
        f"run. This cannot produce an upload file.</div></div></details>"
        f"<div id='status'>Pick season/week/slate and Build (the Sunday "
        f"main slate preselects itself when DK lists one; single games under "
        f"Showdown build Captain Mode entries). Classic tournament defaults "
        f"apply automatically: {ADOPTED_CLASSIC_POLICY.policy_id}, 80 entries, "
        f"fixed 194 coverage, QB+2 stack, bring-back and chalk fade — showdown "
        f"leverages captain diversity instead.</div>"
        f"<section id='portfolio' hidden><button class='portfolio-clear' "
        f"onclick='clearPortfolioSelection()'>Clear highlight</button>"
        f"<h2>Portfolio map</h2>"
        f"<p class='portfolio-note'>These views describe diversification and "
        f"co-occurrence inside the entries you just built; they do not use "
        f"future results or imply that a visual cluster is stronger.</p>"
        f"<div id='portfolio-metrics'></div><div class='portfolio-grid'>"
        f"<section class='portfolio-chart'><h3>Lineup families</h3>"
        f"<p id='lineup-map-note'></p><div id='lineup-map'></div></section>"
        f"<section class='portfolio-chart'><h3>Player co-occurrence</h3>"
        f"<p id='player-map-note'></p><div id='player-map'></div>"
        f"<div class='portfolio-legend'>"
        + "".join(
            f"<span><i class='portfolio-dot' style='background:{color}'></i>{pos}</span>"
            for pos, color in (("QB", "#6f42c1"), ("RB", "#198754"),
                               ("WR", "#0d6efd"), ("TE", "#fd7e14"),
                               ("DST", "#6c757d"))
        )
        + f"</div></section></div></section>"
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
    lu.players.map(p=>`<tr><td><span class='slot'>${esc(p.pos)}</span></td>`+
      `<td style='text-align:left'><a href='#' class='swp' data-ix='${lu.ix}'`+
      ` data-out='${esc(p.name)}'>${esc(p.name)}</a></td><td>${esc(p.team)}</td>`+
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
    const q=prompt('Swap OUT '+a.dataset.out+'.\\nSearch replacement name:');
    if(!q)return;
    const se=+document.getElementById('rseason').value;
    const cs=await (await fetch(`/players/search?season=${se}&week=${wk}`+
      `&q=${encodeURIComponent(q)}`)).json();
    if(!cs.length){alert('No match for "'+q+'"');return;}
    let pick=cs[0];
    if(cs.length>1){
      const c=prompt(cs.map((p,i)=>`${i+1}. ${p.name} ${p.pos} ${p.team} `+
        `$${p.salary}`).join('\\n')+'\\n\\nEnter number:');
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


@app.get("/explainer", response_class=HTMLResponse)
def explainer() -> str:
    """Render the evolving, non-technical repository explainer in the UI."""
    try:
        source = _EXPLAINER_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        log.exception("Unable to read project explainer")
        raise HTTPException(
            status_code=503, detail="Project explainer unavailable") from exc
    marker = "</style>"
    if marker not in source:
        raise HTTPException(
            status_code=503, detail="Project explainer is malformed")
    return source.replace(marker, marker + _EXPLAINER_APPBAR, 1)


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
<h2 style='margin-top:2rem'>Projection accuracy (last completed week)</h2>
<div style='margin:.4rem 0'>
<input id='as' size='5' placeholder='season'> <input id='aw' size='3' placeholder='wk'>
<button id='ago'>Grade</button></div>
<div id='acc'><small>Grade any completed week: our MAE / rank corr vs the
naive trailing-average baseline.</small></div>
<h2 style='margin-top:2rem'>Consensus diff (external projections)</h2>
<div style='margin:.4rem 0'><small>Upload an outside CSV (ETR, Stokastic,
free ownership sites — needs name + projection columns; ownership/ceiling
optional). A disagreement flag, never a model input: big divergence on a
player we're heavy on belongs in the watchlist.</small></div>
<div style='margin:.4rem 0'>
<input id='xsrc' size='10' placeholder='source'>
<input id='xs' size='5' placeholder='season'> <input id='xw' size='3' placeholder='wk'>
<input id='xfile' type='file' accept='.csv'>
<button id='xup'>Upload</button> <button id='xgo'>Show diff</button></div>
<div id='xdiff'><small>No external projections loaded.</small></div>
</main>
<script>
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function tbl(rows, cols){if(!rows.length)return '<small>No data yet.</small>';
  let h='<table><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr>';
  for(const r of rows){h+='<tr>'+cols.map(c=>'<td>'+esc(r[c]??'')+'</td>').join('')+'</tr>';}
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
document.getElementById('ago').onclick=async()=>{
  const s=document.getElementById('as').value,w=document.getElementById('aw').value;
  if(!s||!w)return;
  const j=await (await fetch(`/api/accuracy?season=${s}&week=${w}`)).json();
  if(j.status){document.getElementById('acc').innerHTML=`<small>${esc(j.status)}</small>`;return;}
  let h=`<p><b>MAE ${j.mae}</b>${j.naive_mae?` vs naive ${j.naive_mae}`:''} · rank corr ${j.rank_corr} · n=${j.rows}</p>`;
  document.getElementById('acc').innerHTML=h+tbl(j.by_position||[],['position','n','mae','rank_corr']);
};
document.getElementById('xup').onclick=async()=>{
  const src=document.getElementById('xsrc').value||'external',
        s=document.getElementById('xs').value,w=document.getElementById('xw').value,
        f=document.getElementById('xfile').files[0];
  if(!s||!w||!f){alert('source, season, week and a CSV file required');return;}
  const fd=new FormData();fd.append('file',f);
  const r=await fetch(`/api/external-projections?source=${encodeURIComponent(src)}&season=${s}&week=${w}`,
    {method:'POST',body:fd});
  const j=await r.json();
  document.getElementById('xdiff').innerHTML = r.ok ?
    `<small>Imported ${esc(j.imported)} rows from ${esc(j.source)}.</small>` :
    `<small>Import failed: ${esc(j.detail||r.status)}</small>`;
};
document.getElementById('xgo').onclick=async()=>{
  const s=document.getElementById('xs').value,w=document.getElementById('xw').value;
  if(!s||!w)return;
  const j=await (await fetch(`/api/external-diff?season=${s}&week=${w}`)).json();
  document.getElementById('xdiff').innerHTML=tbl(j,
    ['display_name','position','team','salary','proj_points','ext_proj','diff',
     'ext_own','ext_ceiling','source']);
};
</script>"""
    return f"<html><head><title>Market</title><style>{_PAGE_CSS}</style></head><body>{_NAV_HTML}{body}</body></html>"


def _with_watch_notes(players: list[dict]) -> list[dict]:
    """Attach active watch notes to lineup players (fail-safe passthrough)."""
    from .. import watchlist

    watchlist.annotate_players(players)
    return players


@app.get("/api/watchlist")
def api_watchlist() -> list[dict]:
    from .. import watchlist

    df = watchlist.list_watch()
    if df.empty:
        return []
    df = df.copy()
    for c in ("created_at", "converted_at"):
        df[c] = df[c].astype(str).replace("NaT", "")
    return df.fillna("").to_dict("records")


@app.post("/api/watchlist/{note_id}/convert")
def api_watchlist_convert(note_id: str, mult: float, season: int | None = None) -> dict:
    from .. import watchlist
    from ..config import current_season

    try:
        mid = watchlist.convert_watch(note_id, mult, season or current_season())
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"converted": note_id, "manual_note_id": mid}


@app.delete("/api/watchlist/{note_id}")
def api_watchlist_delete(note_id: str) -> dict:
    from .. import watchlist

    return {"deleted": watchlist.delete_watch(note_id)}


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page() -> str:
    """Player watch notes: free-text intel, lifecycle view, convert/delete.
    Notes change nothing until converted into a usage-note adjustment."""
    body = """
<main><h1>Watchlist</h1>
<small>Free-text player notes from the chat ("add a note: ..."). A note
changes <b>nothing</b> until you convert it into a usage-note adjustment
(opportunity multiplier, decays by week 6). Notes also appear as &#128221;
on any generated lineup containing the player.</small>
<div id='wl' style='margin-top:1rem'><small>Loading&hellip;</small></div>
</main>
<script>
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function load(){
  const j=await (await fetch('/api/watchlist')).json();
  const el=document.getElementById('wl');
  if(!j.length){el.innerHTML='<small>No notes yet. Add one in the chat on the Season page.</small>';return;}
  let h='<table><tr><th>Player</th><th>Note</th><th>Added</th><th>Status</th><th></th></tr>';
  for(const n of j){
    const st=n.status==='converted'
      ?`<span style="color:#0a7a3d;font-weight:700">converted</span><br><small>mult ${n.converted_mult} &middot; ${String(n.converted_at).slice(0,10)}</small>`
      :`<span style="color:#b26a00;font-weight:700">active</span>`;
    const act=n.status==='converted'?''
      :`<input id='m_${n.note_id}' size='4' placeholder='1.10'>
        <button onclick="conv('${n.note_id}')">Convert</button>
        <button onclick="del('${n.note_id}')" style='color:#b3261e'>Delete</button>`;
    h+=`<tr><td style='text-align:left'><b>${esc(n.display_name)}</b></td>
      <td style='text-align:left;max-width:28rem'>${esc(n.note)}</td>
      <td>${String(n.created_at).slice(0,10)}</td><td>${st}</td>
      <td style='text-align:left'>${act}</td></tr>`;
  }
  el.innerHTML=h+'</table>';
}
async function conv(id){
  const m=document.getElementById('m_'+id).value;
  if(!m){alert('Enter a multiplier, e.g. 1.10');return;}
  const r=await fetch(`/api/watchlist/${id}/convert?mult=${m}`,{method:'POST'});
  if(!r.ok){alert((await r.json()).detail||r.status);return;}
  load();
}
async function del(id){
  if(!confirm('Delete this note?'))return;
  await fetch(`/api/watchlist/${id}`,{method:'DELETE'});
  load();
}
load();
</script>"""
    return f"<html><head><title>Watchlist</title><style>{_PAGE_CSS}</style></head><body>{_NAV_HTML}{body}</body></html>"


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


class ContestSpec(BaseModel):
    name: str = ""
    entry_fee: float = Field(gt=0)
    field_size: int = Field(gt=99)
    top_prize: float = Field(gt=0)
    n_entries: int = Field(gt=0, le=150)


class ContestCompareRequest(BaseModel):
    contests: list[ContestSpec] = Field(min_length=2, max_length=4)


@app.get("/api/note-conflicts")
def api_note_conflicts(season: int, week: int) -> list[dict]:
    """Double-count guard (2026-08-04): for every active multiplier note
    and boost/ban pref, compare OUR projection to the prop-market's for
    that player. If the market already leans the note's direction, the
    note likely re-prices information the blend already carries — a
    warning, never a block (notes are deliberate overrides)."""
    from .. import notes as _notes
    from ..models.prop_market import market_points
    from ..names import match_map, resolve

    store = get_store()
    proj = store.projections(season, week)
    if proj.empty:
        return []
    try:
        mkt = market_points((season,))
        mkt = mkt[mkt.week == week]
    except Exception:
        mkt = pd.DataFrame(columns=["gsis_id", "market_points"])
    j = proj.merge(mkt[["gsis_id", "market_points"]] if len(mkt) else
                   pd.DataFrame(columns=["gsis_id", "market_points"]),
                   on="gsis_id", how="left")
    out = []
    # multiplier notes (by gsis)
    try:
        nts = _notes.list_notes(season)
        eff = {}
        if len(nts):
            d = _notes.decay(week)
            for r in nts.itertuples():
                eff[r.gsis_id] = eff.get(r.gsis_id, 1.0) * (1 + (r.mult - 1) * d)
        for gid, m in eff.items():
            row = j[j.gsis_id == gid]
            if row.empty or abs(m - 1.0) < 0.02:
                continue
            r = row.iloc[0]
            mk = r.get("market_points")
            if pd.isna(mk):
                continue
            gap = float(r.proj_points) - float(mk)
            same_dir = (m > 1 and gap > 1.0) or (m < 1 and gap < -1.0)
            if same_dir:
                out.append({
                    "player": r.display_name, "kind": "multiplier",
                    "note_effect": round(m, 2),
                    "our_proj": round(float(r.proj_points), 1),
                    "market_proj": round(float(mk), 1),
                    "warning": "market already leans this way — note may "
                               "double-count priced-in information"})
    except Exception:
        log.exception("note-conflict multiplier scan failed")
    # boost/ban prefs (by name)
    try:
        prefs = _notes.list_prefs(season, week)
        lookup = match_map(dict(zip(j.display_name, j.index)))
        for r in prefs.itertuples():
            ix = resolve(r.display_name, lookup)
            if ix is None:
                continue
            pr = j.loc[ix]
            mk = pr.get("market_points")
            if pd.isna(mk):
                continue
            gap = float(pr.proj_points) - float(mk)
            same_dir = (r.kind == "boost" and gap > 1.0) or                        (r.kind == "ban" and gap < -1.0)
            if same_dir:
                out.append({
                    "player": pr.display_name, "kind": r.kind,
                    "our_proj": round(float(pr.proj_points), 1),
                    "market_proj": round(float(mk), 1),
                    "warning": f"model already {'above' if gap > 0 else 'below'} "
                               f"market by {abs(gap):.1f} — {r.kind} may "
                               f"double-count"})
    except Exception:
        log.exception("note-conflict pref scan failed")
    return out


@app.post("/api/contest-compare")
def api_contest_compare(req: ContestCompareRequest) -> dict:
    """Contest picker math (2026-08-04, the '$5 Milly vs smaller pool'
    rule): per contest, estimate the winning line from field size
    (tail_line_for_field — PROVISIONAL until real standings recalibrate
    it), read P(best-of-N reaches it) off the measured 3-season entries
    curve, and score by top-prize EV per dollar of fees. Top-prize-only
    EV: min-cash ladders and field sharpness are NOT modeled — this
    ranks lottery tails, it does not price tickets."""
    from ..models.entries_curve import p_reach

    rows = []
    for c in req.contests:
        line = tail_line_for_field(c.field_size)
        p = p_reach(c.n_entries, line)
        cost = c.entry_fee * c.n_entries
        ev = p * c.top_prize
        rows.append({
            "name": c.name or f"{c.field_size:,} @ ${c.entry_fee:g}",
            "est_line": round(line, 1), "p_reach": round(p, 4),
            "cost": round(cost, 2), "ev_top": round(ev, 2),
            "ev_per_dollar": round(ev / cost, 3) if cost else 0.0})
    best = max(rows, key=lambda r: r["ev_per_dollar"])
    return {"contests": rows, "verdict": best["name"],
            "note": "top-prize EV per fee dollar; lines provisional until "
                    "real standings recalibrate tail_line_for_field"}


@app.get("/api/market-tails")
def api_market_tails(season: int, week: int, limit: int = 40) -> list[dict]:
    """Model q90 vs the market's de-vigged implied q90 from alternate
    prop ladders (Addendum 45): disagreement predicted the direction of
    market error BOTH ways on 2025 holdout, so the biggest gaps in each
    direction are the week's leverage watchlist."""
    from ..bq import query_df
    from ..config import settings
    from ..inference.market_implied import ALT_MARKETS, market_quantiles

    props = query_df(
        f"""WITH latest AS (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY market, player, CAST(point AS STRING),
                             outcome_name
                ORDER BY snapshot_ts DESC) rn
              FROM `{settings.raw}.prop_lines`
              WHERE season={int(season)} AND week={int(week)}
                AND bookmaker='draftkings'
                AND market IN ({", ".join("'" + m + "'" for m in ALT_MARKETS)})
            ) SELECT season, week, market, player, point, outcome_name,
                     price FROM latest WHERE rn=1""")
    if props.empty:
        return []
    mq = market_quantiles(props)
    if mq.empty:
        return []
    store = get_store()
    proj = store.projections(season, week)
    if proj.empty or "proj_p90" not in proj.columns:
        return []
    norm = lambda s: (s.astype(str).str.lower()  # noqa: E731
                      .str.replace(r"[^a-z ]", "", regex=True).str.strip())
    mq["norm"], proj = mq.player.pipe(norm), proj.assign(
        norm=norm(proj.display_name))
    # spread vs spread, both in DK pts: our (p90 - mean) vs the market's
    # (q90 - q50) at the correct DK rate per market (0.1/yd rush+rec,
    # 0.04/yd pass — the first cut priced QBs 2.5x hot). Known bias,
    # displayed not modeled: summed independent per-market spreads
    # overstate a dual-threat player's combined spread, and our side
    # includes reception/TD variance the yardage markets don't — treat
    # tail_edge as a WATCHLIST ranking, not a calibrated quantity.
    pts_per_yd = {"player_pass_yds_alternate": 0.04}
    tails = (mq.assign(mkt_spread_pts=(mq.q90 - mq.q50)
                       * mq.market.map(pts_per_yd).fillna(0.1))
             .groupby("norm").mkt_spread_pts.sum().reset_index())
    j = proj.merge(tails, on="norm", how="inner")
    j["tail_edge"] = (j.proj_p90 - j.proj_points) - j.mkt_spread_pts
    j = j.reindex(j.tail_edge.abs().sort_values(ascending=False).index)
    cols = ["display_name", "position", "team", "salary", "proj_points",
            "proj_p90", "mkt_spread_pts", "tail_edge"]
    return j[[c for c in cols if c in j.columns]].head(int(limit)).round(
        2).to_dict("records")


@app.post("/api/external-projections")
async def api_external_import(source: str, season: int, week: int,
                              file: UploadFile = File(...)) -> dict:
    """Upload an outside source's projections CSV (ETR/Stokastic/free
    ownership sites). Loose schema; replaces the same (source, season,
    week). Feeds the consensus-diff view — a disagreement flag, never a
    model input."""
    from .. import external_proj

    text = (await file.read()).decode("utf-8", errors="replace")
    try:
        n = external_proj.import_csv(text, source, season, week)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"imported": n, "source": source, "season": season, "week": week}


@app.get("/api/accuracy")
def api_accuracy(season: int, week: int) -> dict:
    """Walk-forward self-grading (4for4 discipline, vendor audit 10/11f):
    last completed week's projections vs actuals — MAE, rank correlation,
    and the naive trailing-average baseline that any real model must
    beat. Empty until the week's actuals land (Tue after the slate)."""
    from ..bq import query_df
    from ..config import settings

    store = get_store()
    proj = store.projections(season, week)
    if proj.empty:
        return {"status": f"no projections for {season} wk {week}"}
    act = query_df(
        f"""SELECT gsis_id, MAX(dk_points) actual
            FROM `{settings.features}.player_week_actuals`
            WHERE season={int(season)} AND week={int(week)} GROUP BY gsis_id""")
    if act.empty:
        return {"status": "actuals not loaded yet (Tuesday ingest)"}
    j = proj.merge(act, on="gsis_id", how="inner")
    if len(j) < 20:
        return {"status": f"only {len(j)} matched rows"}
    out = {"season": season, "week": week, "rows": int(len(j)),
           "mae": round(float((j.proj_points - j.actual).abs().mean()), 2),
           "rank_corr": round(float(
               j.proj_points.corr(j.actual, method="spearman")), 3)}
    if "dk_points_l4" in j.columns:
        n = j.dropna(subset=["dk_points_l4"])
        if len(n) > 20:
            out["naive_mae"] = round(float(
                (n.dk_points_l4 - n.actual).abs().mean()), 2)
    per = []
    for pos, g in j.groupby("position"):
        if len(g) >= 8:
            per.append({"position": pos, "n": int(len(g)),
                        "mae": round(float((g.proj_points - g.actual).abs().mean()), 2),
                        "rank_corr": round(float(
                            g.proj_points.corr(g.actual, method="spearman")), 3)})
    out["by_position"] = per
    return out


@app.get("/api/external-diff")
def api_external_diff(season: int, week: int, limit: int = 40) -> list[dict]:
    from .. import external_proj

    store = get_store()
    proj = store.projections(season, week)
    if proj.empty:
        return []
    d = external_proj.diff(proj, season, week, limit=limit)
    return d.to_dict("records")


@app.get("/api/cfb-export-links")
def cfb_export_links(days: int = 3, limit: int = 5) -> list[dict]:
    """Saturday-night helper (2026-08-03): the biggest recently-completed
    CFB contests with ready-made standings-export URLs — click each while
    logged into DK, then import-ownership the downloads. No entry
    required; contest IDs come from the automated fills poll. Empty until
    the CFB scaffold lands data (late Aug)."""
    from ..bq import query_df
    from ..config import settings

    try:
        df = query_df(f"""
            SELECT contest_id, name, entry_fee, prize_pool, start_time
            FROM (SELECT contest_id, name, entry_fee, prize_pool, start_time,
                         ROW_NUMBER() OVER (PARTITION BY contest_id
                                            ORDER BY pulled_at DESC) rn
                  FROM `{settings.raw}.dk_contest_fills`
                  WHERE sport = 'CFB'
                    AND start_time < CURRENT_TIMESTAMP()
                    AND start_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(),
                                                   INTERVAL {int(days)} DAY))
            WHERE rn = 1 ORDER BY prize_pool DESC LIMIT {int(limit)}""")
    except Exception:
        return []
    out = df.to_dict("records")
    for c in out:
        c["export_url"] = ("https://www.draftkings.com/contest/"
                           f"exportfullstandingscsv/{c['contest_id']}")
        c["start_time"] = str(c["start_time"])
    return out


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
    # Per-conversation model choice (UI selector): Opus default —
    # tool-driven, well-scoped work; Fable for hard reasoning turns.
    model: str | None = Field(None, pattern="^claude-(opus-5|fable-5)$")


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
        messages = chat_mod.chat_turn(list(req.messages), model=req.model)
    except Exception as exc:
        log.exception("chat turn failed")
        log.exception("chat turn failed")
        raise HTTPException(500, "chat failed — see server logs")
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
def post_pref(req: PrefRequest,
              store: ProjectionStore = Depends(get_store)) -> dict:
    from .. import notes as _notes

    # A preference that matches nobody is indistinguishable from a working
    # preference in the old UI.  Resolve it at entry time and store the
    # canonical display name; suffix-insensitive matching keeps common
    # shorthand (e.g. "Odell Beckham") usable.
    df = store.projections(req.season, req.week)
    matches = (df[df.display_name.map(_notes.norm_name)
                  == _notes.norm_name(req.display_name)]
               if not df.empty else df)
    if matches.empty:
        raise HTTPException(422,
                            f"No projectable player matches '{req.display_name}'")
    if len(matches) > 1:
        raise HTTPException(409, "Ambiguous player preference: " + ", ".join(
            matches.display_name.head(5)))
    name = str(matches.display_name.iloc[0])
    return {"pref_id": _notes.add_pref(req.season, req.week, name, req.kind),
            "display_name": name}


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
    hit = df[df.display_name.str.contains(q, case=False, na=False,
                                           regex=False)]
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
    hit = df[df.display_name.str.contains(req.in_name, case=False,
                                           na=False, regex=False)]
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


@lru_cache(maxsize=8)
def _punt_boom_keys(season: int, week: int) -> frozenset:
    from ..backtest.replay import punt_boom_flags_live

    return frozenset(punt_boom_flags_live(season, week))


def _player_pool(
    df: pd.DataFrame, objective: str, dk_ids: dict[int, int] | None = None,
    lev_scale: float = 1.0,
) -> list[dict]:
    """Tournament-tilted pool: sub-$4k players are valued at their ceiling
    (p90 — a punt's only job is to boom) and every projection carries a
    chalk-fade penalty proportional to naive ownership, so entries lean
    into the leverage that wins large fields. dk_id carries the slate's
    draftable ID, which DK's upload parser requires.

    Punt-boom tilt (adopted, Addendum 37): punt-priced skill players
    matching a winning-punt archetype (cheap starting TE, rank 2->1
    promotion, top-decile vacated share) get +PUNT_BOOM objective points
    — replays measured 16 vs 15 tail weeks with every other metric up."""
    from ..backtest.field import naive_ownership
    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY

    # default 0 ADOPTED 2026-08-05 (Addendum 77/79b) — caught drifting
    # at "2" by the config manifest's first run (§3.5 reconciliation).
    punt_boom = float(os.environ.get("PUNT_BOOM", "0") or 0)
    boom_keys: set = set()
    if punt_boom and {"gsis_id", "season", "week"} <= set(df.columns) \
            and len(df):
        try:
            boom_keys = _punt_boom_keys(int(df.season.iloc[0]),
                                        int(df.week.iloc[0]))
        except Exception:
            log.exception("punt-boom flags unavailable; pool untilted")

    pool = []
    for r in df.itertuples():
        pid = int(r.dk_player_id)
        proj = float(getattr(r, objective))
        if int(r.salary) <= PUNT_MAX_SALARY and hasattr(r, "proj_p90") \
                and pd.notna(r.proj_p90):
            proj = max(proj, float(r.proj_p90))
        if boom_keys and int(r.salary) <= PUNT_MAX_SALARY \
                and r.position != "DST" \
                and (getattr(r, "gsis_id", None), int(r.season),
                     int(r.week)) in boom_keys:
            proj += punt_boom
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
        p["proj"] = p["proj"] - LEVERAGE_PENALTY * lev_scale * float(w)
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
    {"name": "$5 Qualifier (typical)", "entry_fee": 5.0,
     "field_size": 20_000, "entries": 80, "entry_limit": 150,
     "lev_scale": 1.0,
     "note": "adopted 80-entry coverage portfolio, full leverage"},
    {"name": "$3 Large GPP", "entry_fee": 3.0,
     "field_size": 100_000, "entries": 80, "entry_limit": 150,
     "lev_scale": 1.0,
     "note": "adopted 80-entry coverage portfolio, full leverage"},
    {"name": "Millionaire Maker", "entry_fee": 20.0,
     "field_size": MILLY_FIELD, "entries": 4, "entry_limit": 150,
     "lev_scale": 1.0,
     "note": "4 lottery tickets at the 194+ line"},
    {"name": "Small qualifier / single-entry", "entry_fee": 5.0,
     "field_size": 5_000, "entries": 1, "entry_limit": 1,
     "lev_scale": 0.7,
     "note": "one strongest individual-tail lineup; moderated chalk fade"},
    # High-stakes: sharp field — our chalk fade is soft-field-calibrated,
    # so halve it; 3-max entries must each stand alone (memory:
    # contest-mix-qualifiers, 2026-08-03).
    {"name": "$333 High-Stakes (3-max)", "entry_fee": 333.0,
     "field_size": 3_000, "entries": 3, "entry_limit": 3,
     "lev_scale": 0.5,
     "note": "sharp field: halved chalk fade, self-sufficient entries"},
]


def _entry_limit_from_name(name: str) -> int:
    """Best-effort DK contest-name parser; the UI always allows correction."""
    text = str(name or "").lower()
    if "single entry" in text or "single-entry" in text:
        return 1
    match = re.search(r"\b(\d{1,3})\s*[- ]?max\b", text)
    if match:
        return max(1, min(int(match.group(1)), 150))
    return 150


def _strategy_for(
    field_size: float,
    entry_fee: float,
    entry_limit: int = 150,
) -> dict:
    """Auto-strategy for LIVE contests (no hand-tuned preset): sharp
    small/high-stakes fields get moderated leverage and few entries."""
    if entry_fee >= 100 or field_size <= 3_500:
        entries, lev_scale = 3, 0.5
        note = "sharp field: halved chalk fade"
    elif field_size <= 10_000:
        entries, lev_scale = 3, 0.7
        note = "small field: moderated chalk fade"
    else:
        entries, lev_scale = ADOPTED_CLASSIC_POLICY.default_entries, 1.0
        note = "large field: adopted tail-coverage portfolio"
    entries = min(entries, int(entry_limit), 80)
    profile = contest_entry_policy(entry_limit, entries, lev_scale)
    return {
        "entries": entries,
        "entry_limit": int(entry_limit),
        "lev_scale": profile["effective_leverage_scale"],
        "note": f"{profile['description']}; {note}",
    }


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
    for c in live:
        entry_limit = _entry_limit_from_name(str(c.get("name") or ""))
        c.update(_strategy_for(
            float(c["field_size"]),
            float(c.get("entry_fee") or 0),
            entry_limit,
        ))
    for c in live + CONTEST_PRESETS:
        c["estimated_winning_line"] = tail_line_for_field(
            int(c["field_size"]))
        c["tail_line"] = ADOPTED_CLASSIC_POLICY.tail_line
    return {"live": live, "presets": CONTEST_PRESETS}


def _rank_by_confidence(lineups: list, df: pd.DataFrame,
                        line: float = MIN_MILLY_LINE,
                        season: int | None = None,
                        week: int | None = None,
                        prefer_lineup_means: bool = False) -> list[dict]:
    """Sort lineups by tournament confidence — P(lineup total >= line)
    under a normal approximation from each player's projection mean and
    std. Independence understates stacked lineups' true tail, so treat
    the number as an ordering signal, not a literal probability; the
    untilted means are used (confidence is about scoring, not leverage)."""
    from statistics import NormalDist

    # CQR sigma scale (external review 3.1): rolling in-season
    # calibration makes confidence% converge to a real probability as
    # accuracy data accrues; neutral 1.0 until then.
    _scale = 1.0
    if season is not None and week is not None:
        from ..models.conformal import sigma_scale

        _scale = sigma_scale(season, week)
    mu_map = df.set_index("dk_player_id").proj_points.to_dict()
    sd_map = (df.set_index("dk_player_id").proj_std.to_dict()
              if "proj_std" in df.columns else {})
    ranked = []
    for lu in lineups:
        mu = sum(float(p["proj"] if prefer_lineup_means
                       else mu_map.get(p["id"], p["proj"]))
                 for p in lu.players)
        var = sum(float(sd_map.get(p["id"], 0) or 0) ** 2 for p in lu.players)
        sigma = max(var ** 0.5, 1e-6) * _scale
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


def _request_construction_preset(req: LineupRequest):
    return ADOPTED_CLASSIC_POLICY.construction_preset(
        preset_id=req.construction_preset_id,
        qb_stack_min=req.qb_stack_min,
        bring_back_min=req.bring_back_min,
        forbid_rb_vs_dst=req.forbid_rb_vs_dst,
        forbid_two_rb_same_team=req.forbid_two_rb_same_team,
        min_salary=req.min_lineup_salary,
        min_games=req.min_games,
        max_per_game=req.max_per_game,
        max_overlap=req.max_overlap,
    )


def _build_classic(req: LineupRequest, store: ProjectionStore) -> tuple:
    df, dk_ids = _classic_projections(req, store)
    from .. import notes as _notes

    entry_policy = req.entry_policy()
    effective_lev_scale = entry_policy["effective_leverage_scale"]

    policy = ADOPTED_CLASSIC_POLICY
    construction = _request_construction_preset(req)
    stack = construction.stack
    # Sim-mode is THE path (validated replay engine on the live slate,
    # locks/bans/slate-restriction included). No silent fallback — the
    # user chose the validated system always (2026-08-03): a sim failure
    # returns a clear error naming the cause; sim=false is the explicit
    # escape hatch to the plain MILP path.
    if req.sim:
        policy_env = policy.engine_environment(
            os.environ, construction_preset=construction,
        )
        allowed = None
        if req.draft_group_id is not None:
            allowed = set(int(p) for p in df.dk_player_id.dropna())
        salaries = ({int(r.dk_player_id): int(r.salary)
                     for r in df[["dk_player_id", "salary"]].itertuples()
                     if pd.notna(r.dk_player_id) and pd.notna(r.salary)}
                    if req.draft_group_id is not None else None)
        from ..inference.live_lineups import (
            RoleBeliefUnavailable, build_sim_lineups)
        try:
            lineups = build_sim_lineups(
                req.season, req.week, n_entries=req.n_lineups,
                stack=stack, tail_line=req.line(),
                lev_scale=effective_lev_scale,
                locks=set(req.locks), bans=set(req.bans),
                allowed_ids=allowed, theses=req.theses or None,
                salary_overrides=salaries,
                apply_notes=req.apply_notes,
                model_variant=policy.model_variant,
                belief_model_variant=policy.role_model_variant,
                expected_model_k=policy.model_ensemble,
                policy_env=policy_env,
                construction_preset_receipt=construction.receipt())
        except RoleBeliefUnavailable as exc:
            if not policy.role_outage_fallback_allowed:
                log.exception(
                    "exact Week-1 role policy unavailable; fallback forbidden"
                )
                raise HTTPException(
                    503,
                    "The exact Week-1 boom-first generator is unavailable "
                    "because its role model could not be loaded. This policy "
                    "forbids silently substituting the CE12/boom28 generator."
                ) from exc
            log.error("promoted role policy unavailable; using CE fallback: %s",
                      exc)
            fallback_env = policy.fallback_environment(
                os.environ, construction_preset=construction,
            )
            try:
                lineups = build_sim_lineups(
                    req.season, req.week, n_entries=req.n_lineups,
                    stack=stack, tail_line=req.line(),
                    lev_scale=effective_lev_scale, locks=set(req.locks),
                    bans=set(req.bans), allowed_ids=allowed,
                    theses=req.theses or None, salary_overrides=salaries,
                    apply_notes=req.apply_notes,
                    model_variant=policy.model_variant,
                    expected_model_k=policy.model_ensemble,
                    policy_env=fallback_env,
                    construction_preset_receipt=construction.receipt())
            except Exception as fallback_exc:
                log.exception("CE fallback lineup build also failed")
                raise HTTPException(
                    503, "Role-union and CE fallback builds failed "
                    f"({type(fallback_exc).__name__}: "
                    f"{str(fallback_exc)[:180]}).") from fallback_exc
            for lineup in lineups:
                lineup.policy_fallback = "classic-k1-ce12-boom28-v1"
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("sim-mode lineup build failed")
            raise HTTPException(
                503, "Sim-mode build failed "
                f"({type(exc).__name__}: {str(exc)[:200]}). Fix the cause "
                "or pass sim=false to explicitly use the MILP path.")
        if not lineups:
            raise HTTPException(
                422, "Sim-mode found no feasible lineups under the given "
                     "constraints")
        # dk_id + kickoff onto sim-built players: kickoff drives the
        # latest-kickoff FLEX preference (late-swap flexibility) and was
        # silently absent from the sim path (2026-08-04 audit).
        kick = {}
        if "kickoff" in df.columns:
            kick = {int(k): (v if pd.notna(v) else None)
                    for k, v in zip(df.dk_player_id, df.kickoff)
                    if pd.notna(k)}
        for lu in lineups:
            lu.construction_preset_receipt = construction.receipt()
            for p in lu.players:
                p.setdefault("dk_id", (dk_ids or {}).get(int(p["id"])))
                p.setdefault("kickoff", kick.get(int(p["id"])))
        ranked = _rank_by_confidence(lineups, df, line=req.line(),
                                 season=req.season, week=req.week,
                                 prefer_lineup_means=True)
        _annotate_leverage([r["lineup"] for r in ranked], slate=df)
        return [r["lineup"] for r in ranked], ranked

    pool = _player_pool(
        df, req.objective, dk_ids, lev_scale=effective_lev_scale,
    )
    if req.apply_notes:
        pool = _notes.apply_prefs(pool, req.season, req.week)
    lineups = optimize_many(
        pool, n_lineups=req.n_lineups, stack=stack,
        locks=set(req.locks), bans=set(req.bans),
        max_overlap=construction.max_overlap,
        env=construction.optimizer_environment(),
    )
    for lu in lineups:
        lu.construction_preset_receipt = construction.receipt()
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    # Confidence order everywhere (JSON + CSVs): first lineup = strongest
    # entry, so "enter the top N in the bigger contest" is just slicing.
    ranked = _rank_by_confidence(lineups, df, line=req.line(),
                                 season=req.season, week=req.week)
    _annotate_leverage([r["lineup"] for r in ranked], slate=df)
    return [r["lineup"] for r in ranked], ranked


def _annotate_leverage(lineups: list, slate: pd.DataFrame | None = None) -> None:
    """Stokastic-style Lev% (2026-08-03 vendor-methodology audit): a
    player's exposure across OUR chosen entries minus his expected field
    ownership — 'how much more are we on him than the field will be'.
    Display-only; positive = our stand, negative = underweight vs field.
    Fail-safe: lineups without the metric beat no lineups.

    Field ownership normalizes over the FULL slate when provided
    (2026-08-04 audit): normalizing over only the ~30 rostered players
    overstated every field percentage ~10x and biased Lev% hard
    negative."""
    try:
        import pandas as _pd

        from ..backtest.field import naive_ownership

        players: dict[int, dict] = {}
        counts: dict[int, int] = {}
        for lu in lineups:
            for p in lu.players:
                players[p["id"]] = p
                counts[p["id"]] = counts.get(p["id"], 0) + 1
        pool = list(players.values())
        if slate is not None and {"dk_player_id", "position", "salary",
                                  "proj_points"} <= set(slate.columns):
            full = _pd.DataFrame({
                "pos": slate.position, "salary": slate.salary,
                "proj": slate.proj_points})
            own_map = dict(zip(slate.dk_player_id.astype(int),
                               naive_ownership(full)))
            own = [own_map.get(int(p["id"]), 0.0) for p in pool]
        else:
            own = naive_ownership(_pd.DataFrame(pool))
        slots = {"QB": 1.0, "RB": 2.5, "WR": 3.5, "TE": 1.2, "DST": 1.0}
        n = max(len(lineups), 1)
        for p, w in zip(pool, own):
            field_pct = 100.0 * float(w) * slots.get(str(p.get("pos")), 1.0)
            expo = 100.0 * counts[p["id"]] / n
            p["lev_pct"] = round(expo - field_pct, 1)
    except Exception:
        log.exception("leverage annotation failed; lineups unannotated")


def _marginals_health(season: int, week: int) -> dict:
    """Which marginal model will the sim actually use (external review
    1.2, 2026-08-04): the TabPFN cache fallback is graceful but must
    never be SILENT — a missing cache on a Sunday means building with
    the older EW marginals (-6 validated tail weeks) without knowing."""
    try:
        from ..bq import query_df
        from ..config import settings

        n = query_df(
            f"SELECT COUNT(*) n FROM `{settings.features}.tabpfn_projections`"
            f" WHERE season={int(season)} AND week={int(week)}").n.iloc[0]
        unmatched = 0
        try:
            unmatched = int(query_df(
                f"SELECT COUNT(*) n FROM "
                f"`{settings.features}.unmatched_dk_players`").n.iloc[0])
        except Exception:
            pass
        warn = None
        if unmatched:
            warn = (f"{unmatched} slate players have NO gsis mapping "
                    f"(likely rookies/call-ups) — they are EXCLUDED from "
                    f"the pool. Review features.unmatched_dk_players and "
                    f"drain into player_id_overrides.")
        if int(n) > 0:
            return {"marginals": "tabpfn", "unmatched_players": unmatched,
                    "warning": warn}
        return {"marginals": "empirical-fallback",
                "unmatched_players": unmatched,
                "warning": f"TabPFN cache has NO rows for {season} wk {week}"
                           " — sim used the older empirical marginals. Run"
                           " the tabpfn-gen job before building for money."}
    except Exception:
        return {"marginals": "unknown",
                "warning": "TabPFN cache probe failed — marginal source "
                           "unverified."}


def _classic_policy_identity(req: LineupRequest, lineups: list) -> dict:
    """Identity attached to every classic JSON/CSV build response."""
    if not req.sim:
        construction = _request_construction_preset(req)
        return {
            "policy_id": "manual-milp-escape-hatch",
            "adopted": False,
            "model_version": None,
            "entries": len(lineups),
            "contest_entry_policy": req.entry_policy(),
            "construction_preset": construction.receipt(),
        }
    model_version = (getattr(lineups[0], "model_version", None)
                     if lineups else None)
    fallback = (getattr(lineups[0], "policy_fallback", None)
                if lineups else None)
    role_model_version = (getattr(lineups[0], "role_model_version", None)
                          if lineups else None)
    return {
        **ADOPTED_CLASSIC_POLICY.public_identity(
            model_version=model_version, entries=len(lineups),
            tail_line=req.line(),
            construction_preset=_request_construction_preset(req)),
        "role_model_version": role_model_version,
        "effective_policy_id": (
            fallback or ADOPTED_CLASSIC_POLICY.policy_id),
        "fallback_used": bool(fallback),
        "adopted": True,
        "contest_entry_policy": req.entry_policy(),
    }


def _classic_policy_headers(req: LineupRequest, lineups: list) -> dict[str, str]:
    identity = _classic_policy_identity(req, lineups)
    simulation_law = identity.get("simulation_law", {})
    environment_receipt = identity.get("engine_environment_receipt", {})
    return {
        "X-Lineup-Policy": str(
            identity.get("effective_policy_id") or identity["policy_id"]),
        "X-Model-Version": str(identity.get("model_version") or "n/a"),
        "X-Simulation-Usage": str(
            simulation_law.get("usage_allocation") or "n/a"),
        "X-Policy-Environment-SHA256": str(
            environment_receipt.get("sha256") or "n/a"),
    }



@app.post("/lineups")
def build_lineups(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    lineups, ranked = _build_classic(req, store)
    return {
        "policy": _classic_policy_identity(req, lineups),
        "model_health": (_marginals_health(req.season, req.week)
                         if req.sim else {"marginals": "n/a (MILP path)",
                                          "warning": None}),
        "tail_line": req.line(),  # what "confidence" is P(score >= X) of
        "lineups": [
            {
                "rank": i + 1,
                "confidence": r["confidence"],  # P(total >= tail_line), %
                "proj_mean": r["proj_mean"],
                "players": _with_watch_notes(r["lineup"].slot_order()),
                "salary": r["lineup"].salary,
                "proj": round(r["lineup"].proj, 2),
            }
            for i, r in enumerate(ranked)
        ],
        "exposure": exposure_summary(lineups),
        "dk_csv": to_dk_csv(lineups),
    }


@app.get("/week1/operating-book")
def week1_operating_book(
    store: ProjectionStore = Depends(get_store),
) -> dict[str, object]:
    """Canonical immutable money book; accepts no construction controls."""

    try:
        return load_week1_operating_book_export(projection_store=store)
    except Week1OperatingBookAPIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/week1/operating-book.csv")
def week1_operating_book_csv(
    store: ProjectionStore = Depends(get_store),
) -> Response:
    """Download the same exact canonical book as a DraftKings upload CSV."""

    try:
        payload = load_week1_operating_book_export(projection_store=store)
    except Week1OperatingBookAPIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=str(payload["dk_csv"]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=dk_week1_operating_book.csv"
            ),
            "X-Week1-Book-SHA256": str(payload["materialization_sha256"]),
            "X-Week1-Export-SHA256": str(payload["export_sha256"]),
        },
    )


class CoreLineupRequest(LineupRequest):
    """Core-and-variations mode: a consensus core (picked on the stable
    median objective) locked into every entry, with the remaining spots
    varied on `objective` (defaults to ceiling — variation is for upside).
    core_size omitted = the system decides how many players it feels
    strongly about (conviction + positional value, with a budget guard so
    the core can't hoard the salary cap)."""

    objective: str = Field("proj_p90", pattern="^proj_(points|p50|p90)$")
    core_size: int | None = Field(None, ge=2, le=8)


class RecordPreviewLineupsRequest(BaseModel):
    """The exact classic preview the browser downloaded.

    The UI receives the finished DK CSV from `/lineups`; rebuilding on
    download can diverge when live inputs change.  Keep scoring history tied
    to that exact reviewed response instead of asking the server to solve a
    second time.
    """
    season: int
    week: int
    lineups: list[dict] = Field(min_length=1, max_length=150)


@app.post("/lineups/record")
def record_preview_lineups(req: RecordPreviewLineupsRequest,
                           store: ProjectionStore = Depends(get_store)) -> dict:
    from .. import notes as _notes
    from ..optimizer.lineup import Lineup

    valid = store.projections(req.season, req.week)
    valid_ids = (set(valid.dk_player_id.dropna().astype(int))
                 if not valid.empty else set())
    recorded = []
    for ix, item in enumerate(req.lineups):
        players = item.get("players")
        if not isinstance(players, list) or len(players) != 9:
            raise HTTPException(422, f"preview lineup {ix + 1} is not a 9-player roster")
        ids = [p.get("id") for p in players if isinstance(p, dict)]
        if len(ids) != 9 or len(set(ids)) != 9 or not all(isinstance(i, int) for i in ids):
            raise HTTPException(422, f"preview lineup {ix + 1} has invalid player IDs")
        if valid_ids and not set(ids) <= valid_ids:
            raise HTTPException(422, f"preview lineup {ix + 1} has players outside this week")
        recorded.append(Lineup(players=players))
    return {"recorded": _notes.record_entered_lineups(req.season, req.week,
                                                         recorded)}


@app.post("/lineups/core")
def build_core_lineups(
    req: CoreLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    df, dk_ids = _classic_projections(req, store)
    stable_pool = _player_pool(df, "proj_p50", dk_ids)
    upside_pool = _player_pool(df, req.objective, dk_ids)
    construction = _request_construction_preset(req)
    stack = construction.stack
    core, lineups = core_and_variations(
        stable_pool, upside_pool, n_lineups=req.n_lineups,
        core_size=req.core_size, stack=stack,
        locks=set(req.locks), bans=set(req.bans),
        max_overlap=construction.max_overlap,
        env=construction.optimizer_environment(),
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    by_id = {p["id"]: p for p in upside_pool}
    ranked = _rank_by_confidence(lineups, df, line=req.line(),
                                 season=req.season, week=req.week)
    return {
        "tail_line": req.line(),
        "construction_preset": construction.receipt(),
        "core": [
            {"id": c["id"], "conviction": c["conviction"],
             "name": by_id[c["id"]]["name"], "pos": by_id[c["id"]]["pos"],
             "team": by_id[c["id"]]["team"], "salary": by_id[c["id"]]["salary"]}
            for c in core
        ],
        "lineups": [
            {"rank": i + 1, "confidence": r["confidence"],
             "proj_mean": r["proj_mean"],
             "players": _with_watch_notes(r["lineup"].slot_order()),
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
        for c in ("proj_std", "gsis_id", "season", "week"):
            if c in proj.columns:
                cols.append(c)
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
                # keys for the TabPFN showdown marginal map (opt-in)
                "gsis_id": (row or {}).get("gsis_id"),
                "season": (row or {}).get("season"),
                "week": (row or {}).get("week"),
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
) -> tuple[pd.DataFrame, list, list | None]:
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

    captain_board = None
    if req.sim:
        from ..optimizer.showdown import sim_mode_entries

        lineups, captain_board = sim_mode_entries(
            pool, req.n_lineups, seed=req.week, locks=set(req.locks),
            bans=set(req.bans) & pool_ids, captain_lock=req.captain,
            with_metrics=True,
        )
    else:
        lineups = optimize_many_showdown(
            pool, n_lineups=req.n_lineups, locks=set(req.locks),
            bans=set(req.bans) & pool_ids,
            captain_lock=req.captain, max_overlap=req.max_overlap,
        )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    return game, lineups, captain_board


@app.post("/showdown/lineups")
def build_showdown_lineups(
    req: ShowdownLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    game, lineups, captain_board = _build_showdown(req, store)
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    return {
        "game": {
            "draft_group_id": int(game.draft_group_id.iloc[0]),
            "game": " vs ".join(teams),
            "day": game["_day"].iloc[0],
            "game_start": str(game["_start"].iloc[0]),
        },
        "captain_board": captain_board,
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
    # ONE build (2026-08-04 audit): this used to run the full sim build
    # twice — 2x latency, and worse, the recorded set could diverge from
    # the uploaded CSV (the ownership booster retrains from BQ per call
    # and BQ tie-breaking is not deterministic — the rebuild law).
    lineups, ranked = _build_classic(req, store)
    try:
        from .. import notes as _n

        _n.record_entered_lineups(req.season, req.week, lineups)
    except Exception:
        log.exception("could not record entered lineups")
    return Response(
        content=to_dk_csv(lineups),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=dk_lineups.csv",
            **_classic_policy_headers(req, lineups),
        },
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
    # Fill only this contest's rows (multi-contest DKEntries downloads:
    # one download, one fill per contest with that contest's preset;
    # untouched rows pass through for the next pass). None = all rows.
    contest_id: str | None = None
    # The prospective validated late-swap route rejects duplicate rosters by
    # default.  This escape hatch is explicit and is echoed in its receipt.
    allow_duplicate_lineups: bool = False


class RecoursePreviewRequest(BaseModel):
    entries_csv: str
    draft_group_id: int
    artifact_uri: str
    artifact_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    status_information: list[dict] = Field(default_factory=list)


class ShowdownFillEntriesRequest(ShowdownLineupRequest):
    entries_csv: str
    n_lineups: int | None = None  # ignored — one lineup per entry row


def _entries_n(entries_csv: str, contest_id: str | None = None) -> int:
    try:
        n = entry_count(entries_csv, contest_id=contest_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if n == 0:
        raise HTTPException(422, "Entries file contains no entry rows")
    if n > MAX_ENTRIES:
        raise HTTPException(422, f"{n} entries exceeds DK's {MAX_ENTRIES}-row limit")
    return n


def _entries_response(entries_csv: str, lineups: list,
                      contest_id: str | None = None,
                      policy_headers: dict[str, str] | None = None) -> Response:
    try:
        filled = fill_entries_csv(entries_csv, lineups, contest_id=contest_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return Response(
        content=filled,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=DKEntries.csv",
                 **(policy_headers or {})},
    )


def _late_swap_now() -> datetime:
    """Server-controlled decision time; clients cannot backdate validation."""
    return datetime.now(timezone.utc)


def _late_swap_catalog(
    store: ProjectionStore, draft_group_id: int
) -> pd.DataFrame:
    """Create the validator's slate-local catalog from the DK salary pull."""
    salaries = store.classic_salaries(draft_group_id)
    if salaries.empty:
        raise HTTPException(
            404, f"No classic slate {draft_group_id}; "
                 "see GET /classic/slates for what's upcoming")
    required = {
        "dk_draftable_id", "display_name", "position", "salary", "game_start",
    }
    missing = required - set(salaries.columns)
    if missing:
        raise HTTPException(
            422, "Slate salary snapshot cannot validate late swap; missing "
                 + ", ".join(sorted(missing)))
    return salaries.rename(columns={
        "dk_draftable_id": "dk_id",
        "display_name": "name",
        "position": "pos",
        "game_start": "kickoff",
    })[["dk_id", "name", "pos", "salary", "kickoff"]].copy()


@app.post("/lineups/entries.csv")
def fill_classic_entries(
    req: FillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv, getattr(req, "contest_id", None))})
    lineups = _build_classic(build_req, store)[0]
    return _entries_response(
        req.entries_csv, lineups, contest_id=req.contest_id,
        policy_headers=_classic_policy_headers(build_req, lineups))


@app.post("/lineups/entries/validated.csv")
def fill_validated_late_swap_entries(
    req: FillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    """Build and fail-closed validate a prospective classic late-swap file.

    This is deliberately separate from the established entries route until
    the prospective recourse policy is evaluated.  It requires a slate-local
    DK salary snapshot and an already-filled DKEntries file, uses the server's
    current time to enforce kickoff locks, and emits an auditable receipt in
    response headers.  It does not use realized player outcomes.
    """
    if req.draft_group_id is None:
        raise HTTPException(
            422, "Validated late swap requires draft_group_id")
    if req.contest_id is not None:
        raise HTTPException(
            422, "Validated late swap currently requires a single-contest "
                 "DKEntries file (omit contest_id)")
    build_req = req.model_copy(update={
        "n_lineups": _entries_n(req.entries_csv),
    })
    lineups = _build_classic(build_req, store)[0]
    try:
        filled = fill_entries_csv(req.entries_csv, lineups)
        from ..optimizer.late_swap import validate_swap_upload

        receipt = validate_swap_upload(
            req.entries_csv,
            filled,
            _late_swap_catalog(store, req.draft_group_id),
            as_of=_late_swap_now(),
            allow_duplicate_lineups=req.allow_duplicate_lineups,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        content=filled,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=DKEntries.csv",
            **_classic_policy_headers(build_req, lineups),
            "X-Late-Swap-Validated": "true",
            "X-Late-Swap-State-Version": str(receipt["state_version"]),
            "X-Late-Swap-As-Of": str(receipt["as_of"]),
            "X-Late-Swap-Entries": str(receipt["entries"]),
            "X-Late-Swap-Changed-Slots": str(receipt["changed_slots"]),
            "X-Late-Swap-Locked-Slots": str(receipt["locked_slots"]),
            "X-Late-Swap-Uses-Outcomes": "false",
        },
    )


@app.post("/lineups/entries/recourse/preview")
def preview_prospective_recourse(
    req: RecoursePreviewRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    """Preview the frozen recourse proposal; never emit an upload file.

    Only checksum-pinned artifacts under this project's dedicated GCS prefix
    are accepted. The proposal remains non-money shadow output until a later
    DK fill also passes the validated export gate.
    """
    from ..config import settings
    from ..inference.recourse_worlds import (
        load_recourse_world_artifact,
        propose_recourse_from_artifact,
    )
    from ..optimizer.late_swap import entry_rosters_from_csv

    prefix = f"gs://{settings.gcs_bucket}/recourse_worlds/"
    if not req.artifact_uri.startswith(prefix):
        raise HTTPException(
            422, f"Recourse artifact must be under {prefix}")
    try:
        artifact = load_recourse_world_artifact(
            req.artifact_uri, req.artifact_sha256
        )
        context = artifact["metadata"].get("context") or {}
        if int(context.get("draft_group_id", -1)) != req.draft_group_id:
            raise ValueError("recourse artifact draft group differs")
        artifact_arm = str(context.get("arm", ""))
        if artifact_arm not in {"control", "treatment"}:
            raise ValueError("recourse artifact arm is not control/treatment")
        catalog = _late_swap_catalog(store, req.draft_group_id)
        entries = entry_rosters_from_csv(req.entries_csv, catalog)
        status = pd.DataFrame(req.status_information)
        if status.empty:
            status = pd.DataFrame(columns=(
                "dk_id", "points_to_date", "game_status", "available_at",
            ))
        result = propose_recourse_from_artifact(
            artifact,
            entries,
            catalog,
            status,
            as_of=_late_swap_now(),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    kickoff = pd.to_datetime(catalog.kickoff, errors="coerce", utc=True)
    as_of = pd.Timestamp(result["as_of"]).tz_convert("UTC")
    future = kickoff[kickoff.gt(as_of)]
    return {
        **result,
        "artifact_uri": req.artifact_uri,
        "artifact_arm": artifact_arm,
        "draft_group_id": req.draft_group_id,
        "next_upload_deadline": (
            None if future.empty else future.min().isoformat()
        ),
        "upload_licensed": False,
        "upload_blocker": (
            "Prospective preview only; fill and validate the proposed book "
            "before any DK upload."
        ),
    }


@app.post("/lineups/entries/recourse/rehearsal")
def rehearse_prospective_recourse(
    req: RecoursePreviewRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    """Generate and validate the exact proposed CSV without returning it."""
    from ..optimizer.late_swap import fill_entry_assignments_csv

    result = preview_prospective_recourse(req, store)
    catalog = _late_swap_catalog(store, req.draft_group_id)
    try:
        generated_csv, validation = fill_entry_assignments_csv(
            req.entries_csv,
            result["assignments"],
            catalog,
            as_of=result["as_of"],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    payload = generated_csv.encode("utf-8")
    return {
        **result,
        "validation_receipt": validation,
        "source_csv_sha256": hashlib.sha256(
            req.entries_csv.encode("utf-8")
        ).hexdigest(),
        "source_csv_bytes": len(req.entries_csv.encode("utf-8")),
        "generated_csv_sha256": hashlib.sha256(payload).hexdigest(),
        "generated_csv_bytes": len(payload),
        "generated_csv_returned": False,
        "upload_licensed": False,
        "upload_blocker": (
            "Rehearsal only; the validated CSV bytes are deliberately not "
            "returned by this endpoint."
        ),
    }


@app.post("/lineups/entries/diff")
def preview_classic_entries(
    req: FillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    """Sunday late-swap preview (2026-08-03): what the entries.csv fill
    WOULD change, per entry — churn-minimizing assignment, locked-player
    rows flagged. Review here, then POST /lineups/entries.csv for the
    upload file (same assignment, deterministic)."""
    from ..optimizer.export import fill_entries_csv

    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv, getattr(req, "contest_id", None))})
    lineups = _build_classic(build_req, store)[0]
    diff: list = []
    fill_entries_csv(req.entries_csv, lineups, diff_out=diff,
                     contest_id=req.contest_id)
    changed = [d for d in diff if d["out"] or d["in"]]
    return {"entries": diff,
            "summary": {"total": len(diff), "changed": len(changed),
                        "untouched_locked": sum(d["untouched"] for d in diff),
                        "avg_swaps": round(sum(len(d["out"]) for d in diff)
                                           / len(diff), 2) if diff else 0}}


@app.post("/showdown/lineups/entries.csv")
def fill_showdown_entries(
    req: ShowdownFillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv, getattr(req, "contest_id", None))})
    _, lineups, _ = _build_showdown(build_req, store)
    return _entries_response(req.entries_csv, lineups)
