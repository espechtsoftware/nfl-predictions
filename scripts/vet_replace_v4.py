#!/usr/bin/env python3
"""Rung 1c v4 — replace UNAVAILABLE lineups in a vetted book with the best live candidates from the build's own pool.

  PYTHONPATH=<prod>/src:<tools> python vet_replace_v4.py VETTED_DIR SOURCE_RUN_DIR OUT_DIR --qb-flags FLAGS_CSV
      [--season 2026 --week 2] [--lab-src /home/erich/projects/.nfl2-worktrees/week2-release-2dc116c/src]
      [--min-replacements 0] [--test-exclude-dk ID,ID]   (rehearsal only: force extra exclusions)

Lab review of v3 (2026-09-19) applied:
 1. ELIGIBILITY IS NOT THE DEMOTION WEIGHT. The exclusion set E is confirmed-unavailable only: DK feed O/IR/OUT
    (frame.status), report Out (whole slate, nfl_raw.injuries latest row per player), placeholder salary, and QBs the
    shared classifier marks `gated` (backup behind a healthy primary). market:VANISHED, Doubtful, Questionable and
    practice signals are risk information and never remove a row nor zero a player in the worlds.
 2. ONE WHOLE-SLATE, ID-KEYED SET drives removal (any id of E in a final-book row) and candidate admission; the
    no-removal path runs the same checks and honours --min-replacements.
 3. The QB rule is qb_classify.py, shared with qb_flags.py, vet_book.py and Rung 2.
 4. The FINAL book is validated BEFORE anything is written: 97 rows, nine distinct ids, salary <= 50,000, DK slot
    legality, uniqueness, the lab's own validate_roster (salary floor 49,000, QB stack >= 2, bring-back >= 1) on
    every row, replacement count == removal count. Failure -> exit 2, replace.json {status: FAILED}, no book.csv.
 5. The receipt is built from the FINAL book: vetting_final.json carries per-row, per-player flags (DK status, report
    status, QB role/team class) for the rows actually delivered, replacement rows included.
Replacements are chosen greedily to maximize the book's expected maximum under the equal-mass concatenation of the
two saved banks with E's rows zeroed; they take the removed row's vetted position. Outcome-blind.
"""
import argparse, csv, json, pathlib, shutil, sys
import numpy as np, pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from qb_classify import OUT_STATUSES, DOUBTFUL, QUESTIONABLE  # noqa: E402

SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
CAP = 50000
LINE = 220.0


def lineup_totals(bank, idx, chunk=400):
    out = np.empty((idx.shape[0], bank.shape[1]), dtype=np.float32)
    for s in range(0, idx.shape[0], chunk):
        out[s:s + chunk] = bank[idx[s:s + chunk]].sum(axis=1)
    return out


def reslot(dks, pos_of):
    by = {"QB": [], "RB": [], "WR": [], "TE": [], "DST": []}
    for d in dks:
        by.setdefault(pos_of.get(d, "?"), []).append(d)
    need = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "DST": 1}
    extra = [p for p in ("RB", "WR", "TE") if len(by[p]) == need[p] + 1]
    if any(len(by[p]) < need[p] for p in need) or len(extra) != 1 or len(by["QB"]) != 1 or len(by["DST"]) != 1 or "?" in by:
        raise ValueError(f"cannot slot lineup {dks}: { {k: len(v) for k, v in by.items()} }")
    flex = by[extra[0]].pop()
    return by["QB"] + by["RB"][:2] + by["WR"][:3] + by["TE"][:1] + [flex] + by["DST"]


def slot_legal(row, pos_of):
    return all((s is None and pos_of[d] in ("RB", "WR", "TE")) or pos_of[d] == s
               for d, s in zip(row, ("QB", "RB", "RB", "WR", "WR", "WR", "TE", None, "DST")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vetted"); ap.add_argument("run"); ap.add_argument("out")
    ap.add_argument("--qb-flags", required=True); ap.add_argument("--season", type=int, default=2026); ap.add_argument("--week", type=int, default=2)
    ap.add_argument("--lab-src", default="/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c/src")
    ap.add_argument("--min-replacements", type=int, default=0); ap.add_argument("--test-exclude-dk", default="")
    ap.add_argument("--no-fresh-dk", action="store_true", help="archive replays only: do not consult the live DK feed for statuses (the frame's build-time status is used)")
    ap.add_argument("--admit-risky", action="store_true",
                    help="allow replacement candidates that carry a Doubtful/Questionable player. Default OFF: a stated "
                         "operator-side choice, not a lab requirement -- cost on the D6400 rehearsal: eligible pool "
                         "4,376 -> 2,252; benefit: the greedy objective cannot see D/Q risk, so admitting such rows "
                         "imports optimistic-by-injury lineups")
    a = ap.parse_args()
    vetted, run, out = pathlib.Path(a.vetted), pathlib.Path(a.run), pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, a.lab_src)
    from nfl2.validator import validate_roster  # the build's own legality rules, read-only import of the pinned source

    vet = json.loads((vetted / "vetting.json").read_text())
    with (vetted / "book.csv").open(newline="") as h:
        rows = list(csv.reader(h))
    assert tuple(rows[0]) == SLOTS, rows[0]
    book = [[int(x) for x in r] for r in rows[1:]]
    n_book = len(book)
    # required K comes from the operating contract in the source receipt, not from the input's row count (lab v4 boundary)
    src = json.loads((vetted / "source_receipt.json").read_text())
    k_required = int(src.get("written") or src.get("config", {}).get("operational_k") or 0)
    if k_required and n_book != k_required:
        (out / "replace.json").write_text(json.dumps({"version": "vet-replace-v4.1", "status": "FAILED",
                                                       "problems": [f"input book has {n_book} rows but the source receipt requires {k_required}"]}, indent=1) + "\n")
        print(f"REPLACEMENT FAILED: input book rows {n_book} != receipt written {k_required}", file=sys.stderr); sys.exit(2)
    order = vet["order_source_ranks"]
    by_rank = {lu["rank"]: lu for lu in vet["lineups"]}

    f = pd.read_parquet(run / "frame.parquet"); f["dk"] = f.dk_player_id.astype(int)
    row_of = {d: i for i, d in enumerate(f.dk.tolist())}
    id_to_dk = {str(i): d for i, d in zip(f["id"].astype(str), f.dk)}; dk_to_id = {d: i for i, d in id_to_dk.items()}
    name_of = dict(zip(f.dk, f.display_name.astype(str))); pos_of = dict(zip(f.dk, f.pos.astype(str)))
    sal_of = dict(zip(f.dk, pd.to_numeric(f.salary, errors="coerce").fillna(0).astype(int)))
    dk_status = dict(zip(f.dk, f.status.astype(str).str.upper().str.strip())) if "status" in f.columns else {}
    gsis_of = dict(zip(f.dk, f.gsis_id.astype(str)))
    vr_args = [f.set_index("id")[k].to_dict() for k in ("pos", "team", "opp", "salary")]
    game_arg = f.set_index("id")["game_id"].to_dict() if "game_id" in f.columns else None

    # ---- whole-slate statuses: report status (latest row per player) + QB classes ----
    from google.cloud import bigquery
    c = bigquery.Client(project="nfl-predictions-503414")
    ids = sorted({g for g in gsis_of.values() if g and g not in ("None", "nan", "0.0")})
    inj = c.query("""SELECT gsis_id, report_status, date_modified FROM `nfl-predictions-503414.nfl_raw.injuries`
                     WHERE CAST(season AS INT64)=@s AND CAST(week AS INT64)=@w AND gsis_id IN UNNEST(@ids)""",
                  job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week), bigquery.ArrayQueryParameter("ids", "STRING", ids)])).result().to_dataframe()
    report = {}
    if len(inj):
        inj = inj.sort_values("date_modified").groupby("gsis_id").tail(1)
        report = {g: str(s).strip().upper() for g, s in zip(inj.gsis_id, inj.report_status)
                  if s is not None and str(s).strip().upper() not in ("", "NAN", "NONE")}
    report_of = {d: report.get(g, "") for d, g in gsis_of.items()}
    # Fresh DK feed status for the whole slate, ID-keyed by dk_player_id (lab v4 boundary: a status that changed
    # after the build's frame was captured must still exclude). The frame's status is the fallback.
    group = int(src.get("draft_group") or (f["draft_group_id"].iloc[0] if "draft_group_id" in f.columns else 0) or 0)
    fresh = c.query("""SELECT dk_player_id, status, pulled_at FROM `nfl-predictions-503414.nfl_raw.dk_salaries`
                       WHERE draft_group_id=@g QUALIFY ROW_NUMBER() OVER (PARTITION BY dk_player_id ORDER BY pulled_at DESC)=1""",
                    job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("g", "INT64", group)])).result().to_dataframe() if (group and not a.no_fresh_dk) else pd.DataFrame(columns=["dk_player_id", "status", "pulled_at"])
    # Row presence and normalized status are tracked separately (lab v4.1 boundary): a player PRESENT in the fresh
    # capture with a blank status is currently clear, and that clears an old frame Q/OUT; the frame's status is
    # used only for players absent from the fresh capture.
    fresh_present = {int(d) for d in fresh.dk_player_id}
    fresh_status = {int(d): (str(s).upper().strip() if s is not None and str(s).strip().upper() not in ("", "NAN", "NONE") else "")
                    for d, s in zip(fresh.dk_player_id, fresh.status)}
    fresh_pulled_at = str(fresh.pulled_at.max()) if len(fresh) else ""
    dkst = {d: (fresh_status[d] if d in fresh_present else (s if s not in ("", "NAN", "NONE") else "")) for d, s in dk_status.items()}
    # Admission is stricter than removal (lab review, finding 2): a replacement must not bring in a player with
    # material risk -- DK D/Q or report Doubtful/Questionable -- even though such players are never REMOVED.
    risky = {d for d in f.dk if dkst.get(d, "") in DOUBTFUL | QUESTIONABLE or report_of.get(d, "") in ("DOUBTFUL", "QUESTIONABLE")}
    flags = pd.read_csv(a.qb_flags, dtype={"dk_player_id": "Int64"})
    # The flag table must be for THIS season/week/draft group (lab v4.1/v4.2 boundaries): all three provenance
    # columns are required, the table must be non-empty, and every row must carry one consistent tuple equal to the
    # source contract. A legacy or mixed table refuses -- never warn-and-continue.
    def refuse(msg):
        (out / "replace.json").write_text(json.dumps({"version": "vet-replace-v4.3", "status": "FAILED", "problems": [msg]}, indent=1) + "\n")
        print(f"REPLACEMENT FAILED: {msg}", file=sys.stderr); sys.exit(2)
    if not {"season", "week", "draft_group"} <= set(flags.columns):
        refuse("flag table lacks season/week/draft_group provenance columns")
    if len(flags) == 0:
        refuse("flag table is empty")
    tuples = set(zip(pd.to_numeric(flags.season, errors="coerce"), pd.to_numeric(flags.week, errors="coerce"), pd.to_numeric(flags.draft_group, errors="coerce")))
    if len(tuples) != 1 or any(pd.isna(x) for t in tuples for x in t):
        refuse(f"flag table carries {len(tuples)} distinct season/week/draft_group tuples (or nulls): {sorted(map(str, tuples))[:4]}")
    prov = tuple(int(x) for x in next(iter(tuples)))
    want = (int(src.get("season") or a.season), int(src.get("week") or a.week), group)
    if prov != want:
        refuse(f"flag table provenance {prov} != receipt/args {want}")
    qb_role = {int(d): r for d, r in zip(flags.dk_player_id.dropna().astype(int), flags.role[flags.dk_player_id.notna()])}
    qb_class = {int(d): r for d, r in zip(flags.dk_player_id.dropna().astype(int), flags.team_class[flags.dk_player_id.notna()])}

    # ---- the exclusion set E (confirmed unavailable only) ----
    reasons = {}
    for d in f.dk:
        if dkst.get(d, "") in OUT_STATUSES: reasons[d] = f"dk:{dkst[d]}" + ("" if d in fresh_status else "(frame)")
        elif report_of.get(d, "") == "OUT": reasons[d] = "report:Out"
        elif qb_role.get(d) == "out": reasons[d] = "flags:out"
        elif sal_of[d] and sal_of[d] < 2500 and pos_of[d] != "DST": reasons[d] = "placeholder_salary"
        elif qb_role.get(d) == "gated": reasons[d] = f"backup_qb:behind-healthy-primary"
    for tok in [t for t in a.test_exclude_dk.split(",") if t.strip()]:
        reasons[int(tok)] = "TEST-EXCLUDE"
    E = set(reasons)

    # ---- removal from the final (vetted) book, by ids, on every path ----
    remove_positions = [p for p, r in enumerate(book) if any(d in E for d in r)]
    replaced_info = []
    if remove_positions:
        inc = np.load(run / "incumbent_player_scores.npy"); hs = np.load(run / "corrected_hsim_player_scores.npy")
        bank_problems = []
        if not (inc.shape[0] == len(f) == hs.shape[0]): bank_problems.append(f"bank rows {inc.shape[0]}/{hs.shape[0]} != frame rows {len(f)}")
        if inc.ndim != 2 or hs.ndim != 2 or inc.shape[1] != hs.shape[1] or inc.shape[1] < 2: bank_problems.append(f"bank widths {inc.shape} vs {hs.shape}: equal-mass concatenation needs equal, non-trivial world counts")
        if not (np.isfinite(inc).all() and np.isfinite(hs).all()): bank_problems.append("non-finite values in a saved bank")
        if bank_problems:
            (out / "replace.json").write_text(json.dumps({"version": "vet-replace-v4.1", "status": "FAILED", "problems": bank_problems}, indent=1) + "\n")
            print("REPLACEMENT FAILED: " + "; ".join(bank_problems), file=sys.stderr); sys.exit(2)
        inc_g, hs_g = inc.copy(), hs.copy(); zr = [row_of[d] for d in E if d in row_of]
        inc_g[zr, :] = 0.0; hs_g[zr, :] = 0.0; mix = np.concatenate([inc_g, hs_g], axis=1)
        cands = pd.read_parquet(run / "candidates.parquet")
        book_sets = {frozenset(r) for r in book}
        pool_idx, pool_meta, rejected = [], [], {"unmapped": 0, "in_book": 0, "excluded": 0, "risky": 0, "illegal": 0}
        for ci, players in enumerate(cands["players"].astype(str)):
            toks = [t.strip() for t in players.split(",")]
            dks = [id_to_dk.get(t) for t in toks]
            if any(d is None for d in dks) or len(dks) != 9: rejected["unmapped"] += 1; continue
            if frozenset(dks) in book_sets: rejected["in_book"] += 1; continue
            if any(d in E for d in dks): rejected["excluded"] += 1; continue
            if not a.admit_risky and any(d in risky for d in dks): rejected["risky"] += 1; continue
            if validate_roster(toks, *vr_args, salary_floor=49000, qb_stack_min=2, bring_back_min=1, forbid_rb_vs_dst=True, forbid_two_rb_same_team=True): rejected["illegal"] += 1; continue
            pool_idx.append([row_of[d] for d in dks]); pool_meta.append((ci, dks))
        if not pool_idx:
            raise SystemExit("no eligible replacement candidates")
        pool_idx = np.asarray(pool_idx, dtype=np.int64); T = lineup_totals(mix, pool_idx)
        keep = [p for p in range(n_book) if p not in set(remove_positions)]
        M = lineup_totals(mix, np.asarray([[row_of[d] for d in book[p]] for p in keep], dtype=np.int64)).max(axis=0) if keep else np.zeros(mix.shape[1], np.float32)
        used = set()
        for p in remove_positions:
            gain = np.maximum(M[None, :], T).mean(axis=1) - M.mean()
            if used: gain[list(used)] = -np.inf
            j = int(np.argmax(gain)); used.add(j); ci, dks = pool_meta[j]
            if not np.isfinite(gain[j]):
                (out / "replace.json").write_text(json.dumps({"version": "vet-replace-v4.1", "status": "FAILED", "problems": ["non-finite replacement gain"]}, indent=1) + "\n")
                print("REPLACEMENT FAILED: non-finite replacement gain", file=sys.stderr); sys.exit(2)
            new = reslot(dks, pos_of)
            replaced_info.append({"vetted_position": p + 1, "source_rank": order[p], "removed": [name_of[d] for d in book[p]],
                                  "removed_because": {name_of[d]: reasons[d] for d in book[p] if d in E},
                                  "replacement": [name_of[d] for d in new], "candidate_index": int(ci), "gain_corrected_mix": float(gain[j])})
            M = np.maximum(M, T[j]); book[p] = new
        pool_summary = {"eligible": int(len(pool_idx)), "rejected": rejected}
    else:
        pool_summary = {"eligible": None, "rejected": None}

    # ---- final-book validation BEFORE writing ----
    problems = []
    if len(book) != n_book: problems.append(f"row count {len(book)} != {n_book}")
    if len({frozenset(r) for r in book}) != len(book): problems.append("duplicate lineup")
    for p, r in enumerate(book):
        if len(set(r)) != 9: problems.append(f"row {p+1}: ids not distinct")
        if sum(sal_of[d] for d in r) > CAP: problems.append(f"row {p+1}: salary {sum(sal_of[d] for d in r)} > {CAP}")
        if not slot_legal(r, pos_of): problems.append(f"row {p+1}: slot order illegal")
        v = validate_roster([dk_to_id[d] for d in r], *vr_args, salary_floor=49000, qb_stack_min=2, bring_back_min=1, forbid_rb_vs_dst=True, forbid_two_rb_same_team=True)
        if v: problems.append(f"row {p+1}: {v}")
        still = [name_of[d] for d in r if d in E]
        if still: problems.append(f"row {p+1}: still contains excluded {still}")
    if len(replaced_info) != len(remove_positions): problems.append("replacement count != removal count")
    if len(replaced_info) < a.min_replacements: problems.append(f"replaced {len(replaced_info)} < required {a.min_replacements}")
    status = "OK" if not problems else "FAILED"
    import hashlib
    def sha(p):
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""): h.update(chunk)
        return h.hexdigest()
    inputs = {str(p): sha(p) for p in (vetted / "book.csv", vetted / "vetting.json", vetted / "source_receipt.json", run / "frame.parquet",
                                        run / "candidates.parquet", run / "incumbent_player_scores.npy", run / "corrected_hsim_player_scores.npy", pathlib.Path(a.qb_flags)) if p.exists()}
    test_mode = bool(a.test_exclude_dk) or bool(a.no_fresh_dk)
    receipt = {"version": "vet-replace-v4.3", "status": status, "problems": problems, "source_run": str(run), "vetted_dir": str(vetted),
               "publishable": (status == "OK") and not test_mode,
               "rehearsal_flags": {"test_exclude_dk": a.test_exclude_dk, "no_fresh_dk": bool(a.no_fresh_dk)},
               "input_sha256": inputs, "qb_flags": str(a.qb_flags), "required_k": k_required, "admit_risky": bool(a.admit_risky),
               "freshness": {"frame_status": "build-time DK feed", "fresh_dk_pulled_at": fresh_pulled_at, "fresh_dk_players": len(fresh_status), "injury_report_rows": int(len(inj))},
               "exclusion_set": {name_of[d]: reasons[d] for d in sorted(E, key=lambda x: name_of[x]) if d in name_of},
               "removed_positions": [p + 1 for p in remove_positions], "replacements": replaced_info, "pool": pool_summary}
    (out / "replace.json").write_text(json.dumps(receipt, indent=1) + "\n")
    if status != "OK":
        print("REPLACEMENT FAILED:", "; ".join(problems[:6]), file=sys.stderr); sys.exit(2)

    # ---- receipt from the FINAL book ----
    final = []
    for p, r in enumerate(book):
        pf = {}
        for d in r:
            fl = []
            s = dkst.get(d, "")
            if s: fl.append(f"DK:{s}")
            rp = report_of.get(d, "")
            if rp: fl.append(f"report:{rp.title()}")
            if pos_of[d] == "QB" and d in qb_role and not (qb_role[d] == "primary" and qb_class[d] == "healthy"):
                fl.append(f"qb:{qb_role[d]}/{qb_class[d]}")
            if fl: pf[name_of[d]] = fl
        final.append({"position": p + 1, "source": ("replacement" if (p in set(remove_positions)) else f"book-rank-{order[p]}"),
                      "salary": int(sum(sal_of[d] for d in r)), "flags": pf})
    (out / "vetting_final.json").write_text(json.dumps({"version": "vet-replace-v4.3", "publishable": not test_mode, "lineups": final}, indent=1) + "\n")
    with (out / "book.csv").open("w", newline="") as h:
        w = csv.writer(h); w.writerow(SLOTS); [w.writerow(r) for r in book]
    shutil.copy(run / "frame.parquet", out / "frame.parquet"); shutil.copy(vetted / "source_receipt.json", out / "source_receipt.json")
    receipt["output_sha256"] = {"book.csv": sha(out / "book.csv"), "vetting_final.json": sha(out / "vetting_final.json")}
    (out / "replace.json").write_text(json.dumps(receipt, indent=1) + "\n")
    if test_mode:
        (out / "NOT-PUBLISHABLE-REHEARSAL").write_text("rehearsal flags were used; this book must not be emitted\n")
    print(f"replaced {len(replaced_info)} unavailable lineup(s) (exclusion set {len(E)} players); final book validated: {n_book} rows OK")
    for r in replaced_info:
        print(f"  pos {r['vetted_position']:>3} (source rank {r['source_rank']}): removed because {r['removed_because']}\n      -> {', '.join(r['replacement'])}  (gain {r['gain_corrected_mix']:+.3f})")


if __name__ == "__main__":
    main()
