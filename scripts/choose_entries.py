#!/usr/bin/env python3
"""Choose the operator's m entries for ONE big contest from the week's entered book (study 32's R4; Addendum 137).

    python scripts/choose_entries.py --run <union run dir> --book <the entered book.csv> --ownership <ownership_fp-*.csv>
        --contests <the week's contests.json> --contest-details <contest-details-*.json> --contest-id <id> --m 3
        [--win-line 500] [--out choice.json]
    (or --N / --S instead of the contest details; --all-rows instead of --contests to choose from every book row)

Prints R4's rows (joint coverage: the set most likely to have at least one entry in the contest's top S, S = the places
paying at least --win-line, the operator's "$500 or more", 10-06) beside book order (R0) and the random baseline, all
SIMULATED (in-sample; study 32: the simulator over-sells about 3x). With m = 1 it says plainly that no rule beat a random
pick. Writes the choice and the R0 pair to --out (the weekly R0-vs-R4 paired shadow; scored on Monday by
scripts/score_entry_choice.py).

The candidates are the week's ENTERED mean rows, the first rows_needed - sleeve rows of the book under the week's layout
(K 26 under Rev3): the pool study 32 measured. --all-rows chooses from every book row and says it is outside the
studied pool (a larger pool gives the in-sample optimum more subsets to over-fit). m 4 is allowed and flagged: the
study measured m <= 3.

The field is PRE-LOCK by construction: the T-70 Fantasy Points ownership export the build used (pred_own %), skill
players only, DSTs uniform, sampled with the vendored field sampler (study 32's settings and its fallback). Never contest
results. Outcome-free; it reads no scores.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nfl_dfs.inference import entry_choice as EC  # noqa: E402

BANKS = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")
STUDIED_K = 26                                                # study 32's pool: Rev3's entered mean rows
SEED = 20261006


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True); ap.add_argument("--book", type=Path, required=True)
    ap.add_argument("--ownership", type=Path, required=True)
    ap.add_argument("--contest-details", type=Path); ap.add_argument("--contest-id")
    ap.add_argument("--N", type=int); ap.add_argument("--S", type=int)
    ap.add_argument("--win-line", type=float, default=500.0, help="S = the places paying at least this (operator 10-06: $500)")
    ap.add_argument("--contests", type=Path, help="the week's contests.json: the candidates are its entered mean rows (K)")
    ap.add_argument("--layout", default=os.environ.get("ENTER_LAYOUT", "head"))
    ap.add_argument("--all-rows", action="store_true", help="choose from every book row (outside the studied pool)")
    ap.add_argument("--m", type=int, required=True); ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    from field_sampler import sample_field                   # vendored verbatim from the lab (sha in its header)

    if a.contest_details:
        det = json.loads(a.contest_details.read_text()).get(str(a.contest_id))
        if det is None:
            raise SystemExit(f"contest {a.contest_id} is not in {a.contest_details}")
        N, S, cname = int(det.get("maximumEntries") or det.get("max")), EC.seats_at_or_above(det.get("payoutSummary"), a.win_line), det.get("name")
    elif a.N and a.S:
        N, S, cname = a.N, a.S, None
    else:
        raise SystemExit("give --contest-details with --contest-id, or --N and --S")
    if not 0 < S < N:
        raise SystemExit(f"S {S} must be in 1..N-1 (N {N}; places paying >= {a.win_line})")

    fr = pd.read_parquet(a.run / "frame.parquet").reset_index(drop=True)
    banks = [np.load(a.run / b).astype(np.float32) for b in BANKS]
    if any(b.shape[0] != len(fr) for b in banks):
        raise SystemExit("the banks do not match the frame's rows")
    W = EC.worlds(*banks)
    dk2id = dict(zip(pd.to_numeric(fr.dk_player_id, errors="coerce").astype("Int64").astype(str), fr.id.astype(str)))
    idx = {str(i): n for n, i in enumerate(fr.id.astype(str))}
    with a.book.open(newline="") as h:
        body = list(csv.reader(h))[1:]
    try:
        rows = [[dk2id[d] for d in r] for r in body]
    except KeyError as e:
        raise SystemExit(f"book player {e} is not in the run's frame")
    if a.all_rows:
        k, pool_note = len(rows), f"ALL {len(rows)} book rows -- OUTSIDE the studied pool (study 32: the K {STUDIED_K} entered rows)"
    elif a.contests:
        from nfl_dfs.inference import enter_layout as EL
        cs = EL._contests(a.contests)
        k = EL.rows_needed(cs, a.layout) - EL.sleeve_size(cs, a.layout)
        pool_note = f"the week's {k} entered mean rows ({a.layout}; study 32 measured K {STUDIED_K})"
        if len(rows) < k:
            raise SystemExit(f"the book holds {len(rows)} rows < the {k} entered mean rows of {a.contests}")
    else:
        raise SystemExit("give --contests (the week's contests.json; the candidates are its entered mean rows) or --all-rows")
    rows = rows[:k]
    book_ix = [[idx[i] for i in r] for r in rows]

    own = pd.read_csv(a.ownership, dtype={"id": str})
    if "pred_own" not in own.columns or "id" not in own.columns:
        raise SystemExit(f"{a.ownership}: needs id and pred_own (the T-70 FP ownership export)")
    if float(pd.to_numeric(own.pred_own, errors="coerce").max()) <= 1.0:     # the reviewer 10-06: as s29's pred_own guard
        raise SystemExit(f"{a.ownership}: pred_own looks like FRACTIONS, not % (max <= 1.0): the field targets would be 100x too small")
    own_of = dict(zip(own.id.astype(str), pd.to_numeric(own.pred_own, errors="coerce").fillna(0.0)))
    pos = fr.pos.astype(str).to_numpy(); n_dst = int((pos == "DST").sum())
    tgt = {str(i): (1.0 / n_dst if p == "DST" else float(own_of.get(str(i), 0.0)) / 100.0) for i, p in zip(fr.id.astype(str), pos)}
    try:
        field, _ = sample_field(fr, tgt, EC.FIELD_SIM, seed=a.seed); fld = {"n": EC.FIELD_SIM, "ipf_rounds": 6, "fallback": False}
    except RuntimeError as e:                                  # study 32's deviation note 1
        field, _ = sample_field(fr, tgt, EC.SEL_FALLBACK_N, seed=a.seed, ipf_rounds=1)
        fld = {"n": EC.SEL_FALLBACK_N, "ipf_rounds": 1, "fallback": True, "why": str(e)[:200]}
    F = EC.field_cdf(W, field, book_ix)
    r4, v4, vr = EC.joint_coverage(F, N, S, a.m)
    r0 = list(range(a.m)); v0 = EC.value_of(F, r0, N, S, a.m)
    name = dict(zip(fr.id.astype(str), fr.display_name.astype(str)))
    qb = {str(i) for i, p in zip(fr.id.astype(str), pos) if p == "QB"}

    def show(rr):
        return [f"row {r + 1}: QB {next((name[i] for i in rows[r] if i in qb), '?')} | " + ", ".join(name[i] for i in rows[r] if i not in qb) for r in rr]

    print(f"CONTEST {cname or ''} N {N}, S {S} (places paying >= {a.win_line:g}); {a.m} entr{'y' if a.m == 1 else 'ies'}; "
          f"K {k}: {pool_note}; field {fld['n']}{' (FALLBACK)' if fld['fallback'] else ''}; SIMULATED (in-sample) values")
    if a.m > 3:
        print(f"  NOTE: m {a.m} is OUTSIDE the study (m <= 3).")
    if a.m == 1:
        print("  NOTE: with ONE entry no rule beat a random pick in study 32 (Addendum 137): any row is as good. R4 is shown "
              "for the record only.")
    print(f"  R4 (choose together)  P(>= 1 in top S) {v4:.3f}"); [print("    " + s) for s in show(r4)]
    print(f"  R0 (book order)       P(>= 1 in top S) {v0:.3f}"); [print("    " + s) for s in show(r0)]
    print(f"  random pick (mean)    P(>= 1 in top S) {vr:.3f}")
    print("  (study 32: simulated gains over-state realized ones about 3x; realized R4 - random was +0.030 pooled, +0.069 at m 3)")
    if a.out:
        a.out.write_text(json.dumps({
            "rule": "R4 joint coverage (study 32, Addendum 137)", "contest_id": a.contest_id, "contest": cname, "N": N, "S": S,
            "win_line": a.win_line, "m": a.m, "K": k, "pool": pool_note, "R4_rows": [r + 1 for r in r4], "R0_rows": [r + 1 for r in r0],
            "R4_book_rows": [rows[r] for r in r4], "R0_book_rows": [rows[r] for r in r0],
            "R4_names": [[name[i] for i in rows[r]] for r in r4], "R0_names": [[name[i] for i in rows[r]] for r in r0],
            "simulated": {"R4": v4, "R0": v0, "RND": vr}, "field": fld, "seed": a.seed,
            "inputs_sha256": {"book": sha(a.book), "ownership": sha(a.ownership), "frame": sha(a.run / "frame.parquet"),
                              **{b: sha(a.run / b) for b in BANKS}},
            "written_utc": datetime.now(timezone.utc).isoformat()}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
