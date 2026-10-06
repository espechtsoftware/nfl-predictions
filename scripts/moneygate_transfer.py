"""Study-1 TRANSFER CHECK (descriptive; production prereg reports/2026-10-05-prereg-study1-deconcentration.md): A1 (the
current system) vs AG (A1 + union_reselect --main-game-cap p3) on the REAL 2026 W1-4 pools, contests, fields and ladders,
scored by moneygate_score's validated path (the A0 known-answer gate passed exactly; this script only imports it).
Direction: finish pct = share of the contest field an entry beats (higher = better); every difference is AG - A1.
Week 4 motivated the study and is flagged. Not decision-bearing: it is checked only for DIRECTION agreement with the
panel (panel G vs C: NO DIFFERENCE; zero-ticket slates fell, the ceiling dipped)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402


def main() -> int:
    MS.require_reconcile([1, 2, 3, 4])
    cfg = MS.load_config()
    weeks = [1, 2, 3, 4]
    data = {w: MS.load_week(cfg, w) for w in weeks}
    lay = {a: {w: json.loads((MS.BOOKS / f"w{w}" / a / "layout.json").read_text()) for w in weeks} for a in ("A1", "AG")}
    res = {a: {w: MS.score_book(data[w], lay[a][w])[0] for w in weeks} for a in ("A1", "AG")}
    print("STUDY-1 TRANSFER CHECK (descriptive): AG - A1 on the real 2026 W1-4 contests; higher pct = better; W4 motivated the study")
    print("book sha:", {a: {w: lay[a][w]["book_sha256"][:8] for w in weeks} for a in ("A1", "AG")})
    tot = {"up": 0, "down": 0}
    for w in weeks:
        A, G = res["A1"][w], res["AG"][w]
        zero = {a: sum(1 for r in res[a][w].values() if r.cashes == 0) for a in ("A1", "AG")}
        up = sum(G[c].pct.mean() > A[c].pct.mean() for c in A); dn = sum(G[c].pct.mean() < A[c].pct.mean() for c in A)
        tot["up"] += up; tot["down"] += dn
        print(f"W{w}{' (motivating)' if w == 4 else ''}: multiple A1 {MS.multiple([A]):.3f} AG {MS.multiple([G]):.3f} | "
              f"ex-largest A1 {MS.multiple([A], True):.3f} AG {MS.multiple([G], True):.3f} | cashes {sum(r.cashes for r in A.values())} vs "
              f"{sum(r.cashes for r in G.values())} | mean entry pct {MS.mean_pct(A):.4f} vs {MS.mean_pct(G):.4f} | contests with no cash "
              f"{zero['A1']} vs {zero['AG']} of {len(A)} | contests AG above/below A1 {up}/{dn} | identical book "
              f"{lay['A1'][w]['book_sha256'] == lay['AG'][w]['book_sha256']}")
    for ws, lab in (((1, 2, 3, 4), "W1-4"), ((1, 2, 3), "W1-3 (excl. motivating W4)")):
        A = [res["A1"][w] for w in ws]; G = [res["AG"][w] for w in ws]
        print(f"{lab}: multiple A1 {MS.multiple(A):.3f} AG {MS.multiple(G):.3f}; ex-largest {MS.multiple(A, True):.3f} vs {MS.multiple(G, True):.3f}; "
              f"mean entry pct {sum(MS.mean_pct(x) * sum(r.n for r in x.values()) for x in A) / sum(r.n for x in A for r in x.values()):.4f} vs "
              f"{sum(MS.mean_pct(x) * sum(r.n for r in x.values()) for x in G) / sum(r.n for x in G for r in x.values()):.4f}")
    print(f"contests AG above / below A1 (W1-4, contest-level, anti-conservative): {tot['up']} / {tot['down']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
