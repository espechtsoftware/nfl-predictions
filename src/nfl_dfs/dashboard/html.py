"""Server-rendered HTML pieces: layout, tables, notes and small SVG charts.

No JavaScript framework: every page is complete HTML from the server, with
native SVG ``<title>`` tooltips. Colours are role tokens with a selected
dark mode (the dataviz reference palette: categorical slots 1-3 for at most
three highlighted series, everything else recessive grey).
"""
from __future__ import annotations

import math
from html import escape
from typing import Callable, Iterable, Sequence

import pandas as pd

NAV = (
    ("/", "Overview"), ("/games", "Games"), ("/players", "Players"),
    ("/offense", "Offense"), ("/defense", "Defense"), ("/accuracy", "Accuracy"),
    ("/arms", "Arms"), ("/milly", "Milly"), ("/insights", "Insights"),
)

CSS = """
:root{color-scheme:light;--bg:#fcfcfb;--panel:#ffffff;--ink:#0b0b0b;--ink2:#52514e;
--muted:#8a8984;--rule:#e4e3df;--grid:#efeeea;--accent:#2a78d6;--s1:#2a78d6;--s2:#eb6834;
--s3:#1baf7a;--other:#c9c8c3;--good:#0ca30c;--bad:#d03b3b;--warnbg:#fff6e0;--errbg:#fdeceb}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#1a1a19;--panel:#222220;--ink:#ffffff;--ink2:#c3c2b7;--muted:#8f8e86;--rule:#383835;
--grid:#2b2b29;--accent:#3987e5;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--other:#4a4a46;
--warnbg:#3a3220;--errbg:#3d2322}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#1a1a19;--panel:#222220;--ink:#ffffff;
--ink2:#c3c2b7;--muted:#8f8e86;--rule:#383835;--grid:#2b2b29;--accent:#3987e5;--s1:#3987e5;
--s2:#d95926;--s3:#199e70;--other:#4a4a46;--warnbg:#3a3220;--errbg:#3d2322}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,
"Segoe UI",Roboto,sans-serif}
nav{display:flex;flex-wrap:wrap;gap:.25rem .9rem;padding:.7rem 1rem;border-bottom:1px solid var(--rule);
background:var(--panel);position:sticky;top:0;z-index:2}
nav a{color:var(--ink2);text-decoration:none;font-weight:500}
nav a.on{color:var(--ink);border-bottom:2px solid var(--accent)}
nav .brand{font-weight:700;color:var(--ink);margin-right:.6rem}
main{max-width:1240px;margin:0 auto;padding:1rem}
h1{font-size:1.35rem;margin:.4rem 0 .2rem}h2{font-size:1.05rem;margin:1.4rem 0 .4rem}
.sub{color:var(--ink2);margin:0 0 .8rem}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:.8rem 1rem;margin:.6rem 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.7rem}
.stat .v{font-size:1.5rem;font-weight:650}.stat .k{color:var(--ink2);font-size:.85rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:.32rem .55rem;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
th{color:var(--ink2);font-weight:600;font-size:.82rem;position:sticky;top:0;background:var(--panel)}
td.l,th.l{text-align:left}
tr:hover td{background:var(--grid)}
.note{border-radius:8px;padding:.6rem .8rem;margin:.6rem 0;background:var(--warnbg);color:var(--ink)}
.note.err{background:var(--errbg)}
.pos{color:var(--good)}.neg{color:var(--bad)}
.muted{color:var(--muted)}
form.filters{display:flex;flex-wrap:wrap;gap:.6rem;align-items:end;margin:.4rem 0 .8rem}
form.filters label{display:flex;flex-direction:column;font-size:.8rem;color:var(--ink2)}
form.filters select,form.filters input{font:inherit;padding:.25rem .4rem;background:var(--panel);
color:var(--ink);border:1px solid var(--rule);border-radius:6px}
form.filters button{font:inherit;padding:.3rem .8rem;border-radius:6px;border:1px solid var(--accent);
background:var(--accent);color:#fff;cursor:pointer}
.bar{display:inline-block;height:.6rem;border-radius:0 3px 3px 0;background:var(--s1);vertical-align:middle}
svg text{fill:var(--ink2);font-size:11px}
svg .gridline{stroke:var(--grid)}svg .axis{stroke:var(--rule)}
svg .other{stroke:var(--other);fill:none;stroke-width:1.2}
svg .hl{fill:none;stroke-width:2.2}
.legend{display:flex;gap:1rem;flex-wrap:wrap;font-size:.85rem;color:var(--ink2);margin:.2rem 0}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:.35rem;vertical-align:middle}
@media (max-width:640px){main{padding:.6rem 16px}th,td{padding:.28rem .4rem}}
"""

SERIES = ("var(--s1)", "var(--s2)", "var(--s3)")


def page(title: str, body: str, active: str = "/") -> str:
    links = "".join(f"<a href='{h}' class='{'on' if h == active else ''}'>{escape(t)}</a>"
                    for h, t in NAV)
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)} · DFS dashboard</title><style>{CSS}</style></head><body>"
            f"<nav><span class='brand'>DFS dashboard</span>{links}</nav>"
            f"<main>{body}</main></body></html>")


def note(msg: str, error: bool = False) -> str:
    return f"<div class='note{' err' if error else ''}'>{escape(msg)}</div>"


def esc(v: object) -> str:
    return escape("" if v is None else str(v))


def fmt_num(nd: int = 1, signed: bool = False, pct: bool = False) -> Callable[[object], str]:
    def f(v: object) -> str:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return esc(v)
        if math.isnan(x):
            return "<span class='muted'>–</span>"
        if abs(x) < 0.5 * 10 ** -nd:
            x = 0.0
        s = f"{x:+.{nd}f}" if signed else f"{x:,.{nd}f}"
        if pct:
            s += "%"
        if signed and abs(x) >= 10 ** -nd:
            return f"<span class='{'pos' if x > 0 else 'neg'}'>{s}</span>"
        return s
    return f


def table(df: pd.DataFrame, cols: Sequence[tuple], max_rows: int | None = None) -> str:
    """cols: (column, label[, formatter[, 'l' for left-aligned]])."""
    if df is None or df.empty:
        return note("No rows.")
    d = df.head(max_rows) if max_rows else df
    head = "".join(f"<th class='{c[3] if len(c) > 3 else ''}'>{esc(c[1])}</th>" for c in cols)
    body = []
    for r in d.to_dict("records"):
        tds = []
        for c in cols:
            v = r.get(c[0])
            f = c[2] if len(c) > 2 and c[2] else None
            if f is None:
                s = "<span class='muted'>–</span>" if v is None or (isinstance(v, float) and math.isnan(v)) else esc(v)
            else:
                s = f(v)
            tds.append(f"<td class='{c[3] if len(c) > 3 else ''}'>{s}</td>")
        body.append(f"<tr>{''.join(tds)}</tr>")
    return f"<div class='scroll'><table><tr>{head}</tr>{''.join(body)}</table></div>"


def filters(fields: Iterable[str], action: str) -> str:
    return f"<form class='filters' method='get' action='{action}'>{''.join(fields)}<button>Show</button></form>"


def select(name: str, label: str, options: Sequence[tuple[object, str]], value: object) -> str:
    opts = "".join(f"<option value='{esc(v)}'{' selected' if str(v) == str(value) else ''}>{esc(t)}</option>"
                   for v, t in options)
    return f"<label>{esc(label)}<select name='{esc(name)}'>{opts}</select></label>"


def text_input(name: str, label: str, value: object, size: int = 10) -> str:
    return (f"<label>{esc(label)}<input name='{esc(name)}' value='{esc(value or '')}' "
            f"size='{size}'></label>")


def line_chart(series: list[dict], *, width: int = 900, height: int = 320,
               invert_y: bool = False, y_label: str = "", x_label: str = "week",
               y_min: float | None = None, y_max: float | None = None,
               diagonal: bool = False) -> str:
    """series: [{label, points: [(x, y)], highlight: bool}]; at most three
    highlighted series get colour, a legend and an end label; the rest are
    recessive grey context. Each point carries a native tooltip."""
    pts = [(x, y) for s in series for x, y in s["points"] if y is not None and not pd.isna(y)]
    if not pts:
        return note("Nothing to chart yet.")
    xs = sorted({x for x, _ in pts})
    lo = min(y for _, y in pts) if y_min is None else y_min
    hi = max(y for _, y in pts) if y_max is None else y_max
    if hi == lo:
        hi = lo + 1
    ml, mr, mt, mb = 46, 70, 26, 32
    W, H = width - ml - mr, height - mt - mb
    x0, x1 = min(xs), max(xs)

    def sx(x: float) -> float:
        return ml + (W * (x - x0) / (x1 - x0) if x1 != x0 else W / 2)

    def sy(y: float) -> float:
        f = (y - lo) / (hi - lo)
        return mt + (f * H if invert_y else (1 - f) * H)

    out = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' "
           f"aria-label='{esc(y_label)} by {esc(x_label)}'>"]
    for i in range(5):
        y = lo + (hi - lo) * i / 4
        out.append(f"<line class='gridline' x1='{ml}' x2='{ml + W}' y1='{sy(y):.1f}' y2='{sy(y):.1f}'/>"
                   f"<text x='{ml - 6}' y='{sy(y) + 4:.1f}' text-anchor='end'>{y:.0f}</text>")
    step = max(1, math.ceil(len(xs) / 18))
    for x in xs[::step]:
        out.append(f"<text x='{sx(x):.1f}' y='{mt + H + 18}' text-anchor='middle'>{esc(x)}</text>")
    out.append(f"<line class='axis' x1='{ml}' x2='{ml + W}' y1='{mt + H}' y2='{mt + H}'/>")
    out.append(f"<text x='{ml}' y='{height - 2}'>{esc(x_label)}</text>"
               f"<text x='4' y='12'>{esc(y_label)}</text>")
    if diagonal:
        out.append(f"<line class='axis' stroke-dasharray='4 4' x1='{sx(lo):.1f}' y1='{sy(lo):.1f}' "
                   f"x2='{sx(min(hi, x1)):.1f}' y2='{sy(min(hi, x1)):.1f}'/>")
    hl = [s for s in series if s.get("highlight")][:3]
    others = [s for s in series if not s.get("highlight")]
    for s in others:
        p = [(x, y) for x, y in s["points"] if y is not None and not pd.isna(y)]
        if len(p) > 1:
            d = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in p)
            out.append(f"<polyline class='other' points='{d}'><title>{esc(s['label'])}</title></polyline>")
    legend = []
    for i, s in enumerate(hl):
        color = SERIES[i]
        p = [(x, y) for x, y in s["points"] if y is not None and not pd.isna(y)]
        if not p:
            continue
        d = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in p)
        out.append(f"<polyline class='hl' stroke='{color}' points='{d}'/>")
        for x, y in p:
            out.append(f"<circle cx='{sx(x):.1f}' cy='{sy(y):.1f}' r='4' fill='{color}' "
                       f"stroke='var(--panel)' stroke-width='2'><title>{esc(s['label'])} · "
                       f"{esc(x_label)} {esc(x)}: {y:.1f}</title></circle>")
        lx, ly = p[-1]
        out.append(f"<text x='{sx(lx) + 8:.1f}' y='{sy(ly) + 4:.1f}' style='fill:var(--ink)'>"
                   f"{esc(s['label'])}</text>")
        legend.append(f"<span><i style='background:{color}'></i>{esc(s['label'])}</span>")
    out.append("</svg>")
    leg = f"<div class='legend'>{''.join(legend)}</div>" if len(legend) >= 2 else ""
    return f"<div class='card'>{leg}{''.join(out)}</div>"
