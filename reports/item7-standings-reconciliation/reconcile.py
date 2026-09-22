"""Item 7: is the ownership-mass shortfall rounding, or a real defect?

DK's summary block is keyed by (player, roster position) -- a player used at RB
and at FLEX gets two rows -- so the ground truth from the lineup column must be
keyed the same way. Reads the raw exports read-only and prints aggregates only.
"""
import re
import pandas as pd, numpy as np
from pathlib import Path

D = Path("/home/erich/week2-sunday/ENTERED/standings")
SLOT = re.compile(r"\b(QB|RB|WR|TE|FLEX|DST)\b")

def parse_lineup(s):
    if not isinstance(s, str) or not s.strip():
        return []
    parts = SLOT.split(s)
    return [(parts[i], parts[i + 1].strip())
            for i in range(1, len(parts) - 1, 2) if parts[i + 1].strip()]

rows, worst = [], []
for f in sorted(D.glob("contest-standings-*.csv")):
    raw = pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
    ent = raw[raw.EntryId.notna()]
    is_blank = ent.Lineup.isna() | ent.Lineup.astype(str).str.strip().eq("")
    filled, blank = ent[~is_blank], int(is_blank.sum())
    field = len(filled) + blank

    cnt, slots = {}, 0
    for s in filled.Lineup:
        pl = parse_lineup(s)
        slots += len(pl)
        for slot, nm in pl:
            cnt[(nm, slot)] = cnt.get((nm, slot), 0) + 1
    truth = {k: 100.0 * v / field for k, v in cnt.items()}

    own = raw[raw.Player.notna()][["Player", "Roster Position", "%Drafted"]].copy()
    own["pct"] = own["%Drafted"].astype(str).str.rstrip("%").astype(float)
    # DK writes DST team names with a trailing space ("49ers "); strip before keying.
    own["k"] = list(zip(own.Player.astype(str).str.strip(),
                        own["Roster Position"].astype(str).str.strip()))
    if own.k.duplicated().any():
        print(f"  !! {f.stem}: duplicate (player, slot) rows in summary")
    m = own.set_index("k").pct

    dk_mass = float(own.pct.sum())
    exp_mass = 900.0 * len(filled) / field
    both = sorted(set(m.index) & set(truth))
    diff = np.array([m[p] - truth[p] for p in both], dtype=float)
    rounding_bound = 0.005 * len(own)          # DK prints 2dp
    only_dk = set(m.index) - set(truth)
    only_lu = set(truth) - set(m.index)
    for p in sorted(only_lu | only_dk):
        worst.append(dict(contest=f.stem.split("-")[-1], key=str(p),
                          dk=float(m.get(p, np.nan)) if p in m.index else None,
                          lineups=round(truth.get(p, 0.0), 4)))
    rows.append(dict(
        contest=f.stem.split("-")[-1], field=field, blank=blank,
        slots=slots, exp_slots=9 * len(filled), slot_gap=9 * len(filled) - slots,
        dk_mass=round(dk_mass, 2), exp_mass=round(exp_mass, 2),
        shortfall=round(exp_mass - dk_mass, 2),
        rounding_bound=round(rounding_bound, 2),
        explained_by_rounding=bool(abs(exp_mass - dk_mass) <= rounding_bound),
        max_perplayer_abs=round(float(np.abs(diff).max()) if len(diff) else 0.0, 4),
        only_in_summary=len(only_dk), only_in_lineups=len(only_lu),
        omitted_mass=round(sum(truth[p] for p in only_lu), 3),
        residual=round(exp_mass - dk_mass - sum(truth[p] for p in only_lu), 3)))
    print(rows[-1], flush=True)

df = pd.DataFrame(rows)
out = Path(__file__).parent
df.to_csv(out / "ownership_reconciliation.csv", index=False)
pd.DataFrame(worst).to_csv(out / "unmatched_keys.csv", index=False)
print("\n", df.to_string(index=False))
