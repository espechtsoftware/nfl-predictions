#!/usr/bin/env python3
"""Fail-loud audit of a completed live build (operator, 2026-09-27: "I'm getting sick of being told after the week that
wrong code paths existed ... implement safeguards and fail loudly when something isn't working as it should. I don't
want fallbacks").

Reads ONE run dir (frame.parquet, candidates.parquet, receipt.json, book.csv) and the week's contests.json, and checks
that every lever the build claims to use left a measurable trace, that no lever left an undeclared trace, that every
candidate is legal, that the declared data sources reached the frame, and that the selector and book match the
contests' tracks. Any failed check exits 2 with the check named; the Sunday chain refuses the run dir. Nothing here
reads outcomes. A JSON receipt of every check and its numbers is written next to the run's own receipt.

  python scripts/audit_build_levers.py RUN_DIR --contests contests.json [--layout head] [--expect-selector dual_emax]
      [--expect-max-per-game 4] [--min-salary 49000] [--punt-max 4000] [--market-floor 0.30]
      [--sources market_points:0.30,dk_ppg:0.90,report_status:0.0] [--fade on|off] [--out audit.json]

The checks (each named in the output):
  candidates_no_nonplayers   no candidate holds a player projected under 1 point or listed OUT/IR/D at build time
  punt_valuation_availability the tournament objective exceeds the projection only for playable players at or under the
                             punt price (a non-player valued at his "upside" is exactly the Week-3 Winston defect)
  fade_effect                --fade on: the objective must sit BELOW the projection for the most-owned players (a fade
                             that leaves them untouched is the 2026 no-op); --fade off: no player above the punt price
                             may differ (an undeclared lever)
  max_per_game               every candidate respects the declared cap (QB and DST count), or the receipt declares none
  stack_rules                every candidate holds QB + >=2 same-team WR/TE + >=1 opponent skill player
  salary_bounds              every candidate's salary in [min-salary, 50000]
  market_sources             the share of projected skill players carrying a market number meets the floor
  declared_sources_present   each declared frame column meets its non-null coverage floor
  selector_and_tracks        receipt selector == expected; tail contests => the receipt's sleeve size and the book's row
                             count equal the layout's mean rows + sleeve rows
  t70_rules_effect           --t70 on: an absent depth-1 starter must have produced a bumped backup and an early-game
                             Questionable an activation (the t70_* receipt columns); --t70 off: no trace at all
  union_main                 a union receipt's declared main form (mean | pmo_x50) matches the book's rows and the exposure cap held
  main_own_term              a declared ownership term (union.pmo_x50.own_term.tilt > 0) has its source file, sha256 and coverage,
                             and a control main (book_main_control.csv) that differs from the entered main; no term -> no control book
  book_rows_legal            mean rows distinct, sleeve rows distinct (a sleeve row may repeat a mean row), complete, ids in the frame
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

OUT_STATUSES = {"OUT", "IR", "D", "O", "DOUBTFUL", "INJURED RESERVE", "SUSPENDED", "NA", "PUP"}
SKILL = ("QB", "RB", "WR", "TE")


class AuditFailure(Exception):
    pass


def _players_of(cell: str) -> list[str]:
    return [x.strip() for x in str(cell).split(",") if x.strip()]


def t70_trace_from_bq(receipt: dict, reader=None) -> "pd.DataFrame | None":
    """The t70_* columns of the build's own projection batch from nfl_predictions.player_projections (season, week,
    generated_at = the receipt's config.production_generated_at). Returns None, with the reason printed, when the batch
    is not identifiable or the table lacks the columns; the caller then fails the check."""
    cfg = receipt.get("config", {}) or {}
    gen = cfg.get("production_generated_at"); season = receipt.get("season"); week = receipt.get("week")
    if not gen or season is None or week is None:
        print("t70 trace: the receipt names no projection batch (config.production_generated_at)", file=sys.stderr); return None
    if reader is None:
        def reader(sql):
            from nfl_dfs.bq import client
            return client().query(sql).result().to_dataframe()
    import os
    project = os.environ.get("GCP_PROJECT", "")
    table = f"`{project + '.' if project else ''}nfl_predictions.player_projections`"
    try:
        df = reader(f"SELECT gsis_id, t70_active_q, t70_vacated_net FROM {table} WHERE season = {int(season)} AND week = {int(week)} "
                    f"AND generated_at = TIMESTAMP('{gen}')")
    except Exception as exc:                                   # noqa: BLE001 -- named, then the check fails
        print(f"t70 trace: player_projections query failed ({type(exc).__name__}: {str(exc)[:200]}); the batch carries no t70 columns "
              "or the table lacks them (the deployed projection image predates the T-70 rules)", file=sys.stderr); return None
    if df is None or len(df) == 0:
        print(f"t70 trace: no player_projections rows for season {season} week {week} generated_at {gen}", file=sys.stderr); return None
    return df


def audit(run: Path, contests: list[dict], *, layout: str, expect_selector: str | None, expect_max_per_game: int | None,
          min_salary: int, punt_max: int, market_floor: float, sources: dict[str, float], fade: str,
          top_owned: int = 20, t70: str = "off", t70_reader=None) -> dict:
    fr = pd.read_parquet(run / "frame.parquet")
    cands = pd.read_parquet(run / "candidates.parquet")
    receipt = json.loads((run / "receipt.json").read_text())
    book = [r for r in csv.reader((run / "book.csv").open())][1:]
    by_id = fr.set_index(fr["id"].astype(str))
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str, **numbers):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, **numbers})

    # ---- candidates_no_nonplayers
    proj = by_id["proj"].fillna(0.0).to_dict()
    status = by_id["status"].astype(str).str.upper().to_dict() if "status" in by_id else {}
    bad_rows = 0; examples: list[str] = []
    for cell in cands["players"]:
        offenders = [p for p in _players_of(cell)
                     if (p in proj and proj[p] < 1.0) or status.get(p, "") in OUT_STATUSES]
        if offenders:
            bad_rows += 1
            if len(examples) < 5:
                examples.append(",".join(by_id["name"].get(p, p) for p in offenders))
    record("candidates_no_nonplayers", bad_rows == 0,
           f"{bad_rows} of {len(cands)} candidates hold a non-player (proj < 1 or OUT/IR/D); e.g. {examples[:3]}",
           offending_candidates=bad_rows, candidates=int(len(cands)))

    # ---- punt_valuation_availability
    if "proj_tourney" in fr:
        lifted = fr[(fr["proj_tourney"] - fr["proj"]) > 0.01]
        illegal = lifted[(lifted["salary"] > punt_max) | (lifted["proj"] < 1.0)]
        record("punt_valuation_availability", len(illegal) == 0,
               f"{len(illegal)} players valued above projection while over ${punt_max} or projected under 1 point; "
               f"e.g. {illegal['name'].head(5).tolist()}", lifted=int(len(lifted)), illegal=int(len(illegal)))
    else:
        record("punt_valuation_availability", False, "frame has no proj_tourney column", lifted=0, illegal=0)

    # ---- fade_effect
    if "proj_tourney" in fr:
        above = fr[fr["salary"] > punt_max]
        moved = above[(above["proj_tourney"] - above["proj"]).abs() > 0.01]
        if fade == "on":
            own_col = next((c for c in ("own_est", "field_own", "ownership") if c in fr), None)
            if own_col is None:
                record("fade_effect", False, "--fade on but the frame carries no ownership column to fade on", moved=int(len(moved)))
            else:
                top = fr.sort_values(own_col, ascending=False).head(top_owned)
                faded = int(((top["proj_tourney"] - top["proj"]) < -0.01).sum())
                record("fade_effect", faded >= max(1, top_owned // 2),
                       f"fade declared ON: {faded} of the {top_owned} most-owned players sit below projection", faded=faded)
        else:
            record("fade_effect", len(moved) == 0,
                   f"fade declared OFF: {len(moved)} players above ${punt_max} differ from projection (undeclared lever); "
                   f"e.g. {moved['name'].head(5).tolist()}", moved=int(len(moved)))

    # ---- max_per_game, stack_rules, salary_bounds
    game = by_id["game_id"].astype(str).to_dict(); pos = by_id["pos"].astype(str).to_dict()
    team = by_id["team"].astype(str).to_dict(); opp = by_id["opp"].astype(str).to_dict() if "opp" in by_id else {}
    sal = by_id["salary"].to_dict()
    cap = expect_max_per_game if expect_max_per_game is not None else (receipt.get("config", {}).get("arm", {}) or {}).get("max_per_game")
    over_cap = 0; max_seen = 0; bad_stack = 0; bad_salary = 0; stack_examples: list[str] = []
    # The field sleeve's rows (operator 2026-10-02, union_reselect --sleeve-source field) are held to the limits the receipt
    # declares FOR THEM: their own per-game limit (5), the house stack only when the field ran with the house rules, and
    # the sampler's salary band in `free` mode. Every other candidate keeps the build's cap and rules, as before.
    fmeta = ((receipt.get("config", {}).get("tail_sleeve") or {}).get("field") or {})
    src_col = cands["source_run"].astype(str).tolist() if "source_run" in cands else [""] * len(cands)
    tag_col = cands["tag"].astype(str).tolist() if "tag" in cands else [""] * len(cands)
    # --main mix (study 18's shape portfolio): a row tagged mix_<cell> is held to ITS cell's shape
    # (nfl_dfs.inference.mix_shapes.shape_violations, counting as the pinned optimize constrains); a row from the mix main
    # (source mix / mix_control) without a known cell tag FAILS. Every other row keeps the house check below, unchanged.
    mix_rows_seen = 0
    field_rows = 0
    from nfl_dfs.inference.mix_shapes import bring_back_top_wr_rule, rule_applies      # study 71 (off: {}, (), set(), None)
    from nfl_dfs.inference.mix_shapes import top_game_qb1_rows, top_game_stack_rows, top_game_violations  # study 73 / 74 (off: {})
    bb_top, bb_cells, bb_exempt, bb_required = bring_back_top_wr_rule(receipt)
    tg_forced = {**top_game_qb1_rows(receipt), **top_game_stack_rows(receipt)}
    bb_top = {t: i for t, i in bb_top.items() if not ((i in proj and proj[i] < 1.0) or status.get(i, "") in OUT_STATUSES)}
    for cell, src, tag in zip(cands["players"], src_col, tag_col):
        ps = _players_of(cell)
        is_field = src == "field" and bool(fmeta)
        field_rows += is_field
        row_cap = fmeta.get("max_game", cap) if is_field else cap
        house = (fmeta.get("house_rules_applied", True) is not False) if is_field else True
        row_min_salary = min_salary if house else 48_500
        counts: dict[str, int] = {}
        for p in ps:
            counts[game.get(p, "?")] = counts.get(game.get(p, "?"), 0) + 1
        m = max(counts.values()) if counts else 0
        max_seen = max(max_seen, m)
        if row_cap is not None and m > int(row_cap):
            over_cap += 1
        qbs = [p for p in ps if pos.get(p) == "QB"]
        if tag.startswith("mix_") or src in ("mix", "mix_control"):
            from nfl_dfs.inference.mix_shapes import cell_of_tag, shape_violations
            mix_rows_seen += 1
            try:
                mcell = cell_of_tag(tag)
            except ValueError:
                mcell = None
            v = [f"no mix cell in tag {tag!r}"] if mcell is None else shape_violations(
                ps, mcell, pos, team, opp, game, top_wr=bb_top,
                top_wr_cells=bb_cells if rule_applies(ps, bb_exempt, bb_required) else ())
            v = v + top_game_violations(ps, tg_forced)
            if v:
                bad_stack += 1
                if len(stack_examples) < 3:
                    stack_examples.append(f"{tag}: {v}")
        elif len(qbs) != 1:
            bad_stack += 1
        elif not house:
            pass
        else:
            q = qbs[0]
            mates = sum(1 for p in ps if p != q and team.get(p) == team.get(q) and pos.get(p) in ("WR", "TE"))
            bring = sum(1 for p in ps if p != q and pos.get(p) in SKILL and team.get(p) == opp.get(q))
            if mates < 2 or bring < 1:
                bad_stack += 1
                if len(stack_examples) < 3:
                    stack_examples.append(f"{by_id['name'].get(q, q)}: {mates} mates, {bring} bring-back")
        s = sum(sal.get(p, 0) for p in ps)
        if not (row_min_salary <= s <= 50000):
            bad_salary += 1
    fnote = (f"; {field_rows} field-sleeve rows held to their declared limit {fmeta.get('max_game')} per game"
             f"{'' if fmeta.get('house_rules_applied', True) is not False else ' without the house stack'}") if field_rows else ""
    record("max_per_game", (cap is None) or over_cap == 0,
           f"cap {cap}: {over_cap} candidates over it; max players from one game seen {max_seen}{fnote}",
           cap=cap, over_cap=over_cap, max_seen=max_seen, field_rows=int(field_rows))
    mnote = f" ({mix_rows_seen} mix rows held to their own cell's shape)" if mix_rows_seen else ""
    record("stack_rules", bad_stack == 0, f"{bad_stack} candidates without QB + 2 same-team WR/TE + 1 bring-back{mnote}; e.g. {stack_examples}",
           bad_stack=bad_stack, **({"mix_rows": mix_rows_seen} if mix_rows_seen else {}))
    record("salary_bounds", bad_salary == 0, f"{bad_salary} candidates outside [{min_salary}, 50000]", bad_salary=bad_salary)

    # ---- market_sources
    skill = fr[(fr["pos"].isin(SKILL)) & (fr["proj"] >= 5)]
    share = float(skill["market_points"].notna().mean()) if "market_points" in fr and len(skill) else 0.0
    record("market_sources", share >= market_floor,
           f"{share:.1%} of projected skill players carry a market number (floor {market_floor:.0%})", market_share=round(share, 4))

    # ---- declared_sources_present
    missing = []
    coverage = {}
    for col, floor in sources.items():
        if col not in fr:
            missing.append(f"{col}: column absent"); coverage[col] = None; continue
        cov = float(fr[col].notna().mean())
        coverage[col] = round(cov, 4)
        if cov < floor:
            missing.append(f"{col}: {cov:.1%} < {floor:.0%}")
    record("declared_sources_present", not missing, f"absent or thin declared sources: {missing}" if missing else
           f"all {len(sources)} declared sources present", coverage=coverage)

    # ---- selector_and_tracks
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from nfl_dfs.inference.enter_layout import rows_needed, sleeve_size  # noqa: E402
    t = sleeve_size(contests, layout); need = rows_needed(contests, layout); k_mean = need - t
    cfg = receipt.get("config", {})
    sel_ok = expect_selector is None or cfg.get("selector") == expect_selector
    sleeve_cfg = cfg.get("tail_sleeve") or {}
    sleeve_rows = int(sleeve_cfg.get("rows", 0)) if isinstance(sleeve_cfg, dict) else int(sleeve_cfg or 0)
    written = int(receipt.get("written", 0)); opk = int(cfg.get("operational_k", 0) or 0)
    if t:
        # k_mean already carries the chain's mean-row floor (enter_layout.MEAN_ROWS_FLOOR), so the equality is exact
        tracks_ok = sleeve_rows == t and opk == k_mean and written == k_mean + t and len(book) == written
    else:
        tracks_ok = sleeve_rows == 0 and written == len(book) and written >= k_mean
    record("selector_and_tracks", sel_ok and tracks_ok,
           f"selector {cfg.get('selector')!r} (expected {expect_selector!r}); layout needs {k_mean} mean + {t} sleeve rows; "
           f"receipt written {written}, operational_k {opk}, sleeve {sleeve_rows}; book rows {len(book)}",
           selector=cfg.get("selector"), mean_rows=k_mean, sleeve=t, written=written, operational_k=opk, book_rows=len(book))

    # ---- t70_rules_effect (operator 2026-09-28): declared ON must leave a trace when there was something to act on;
    # declared OFF must leave none. The trace is the t70_* columns the projection step writes. The lab's frame does not
    # carry them (sweep 2026-09-29 item 1), so with --t70 on they are read from player_projections for the build's own
    # batch (the receipt's config.production_generated_at); a batch without the columns FAILS the check by name (the
    # deployed projection image predates the rules), never silently.
    trace = fr[["t70_active_q", "t70_vacated_net"]] if {"t70_active_q", "t70_vacated_net"} <= set(fr.columns) else None
    trace_src = "frame"
    if trace is None and t70 == "on":
        trace, trace_src = t70_trace_from_bq(receipt, t70_reader), "player_projections"
    has_cols = trace is not None
    n_active = int(trace["t70_active_q"].fillna(False).astype(bool).sum()) if has_cols else 0
    n_bumped = int((pd.to_numeric(trace["t70_vacated_net"], errors="coerce").fillna(0) > 0).sum()) if has_cols else 0
    st_up = fr["status"].astype(str).str.upper() if "status" in fr else pd.Series("", index=fr.index)
    absent_starters = int(((pd.to_numeric(fr.get("depth_rank"), errors="coerce") == 1) & st_up.isin(OUT_STATUSES)).sum()) if "depth_rank" in fr else 0
    early_q = 0
    if "game_start" in fr and "status" in fr:
        starts = pd.to_datetime(fr["game_start"], errors="coerce", utc=True)
        first = starts.min()
        early_q = int((st_up.isin({"Q", "QUESTIONABLE"}) & (starts == first)).sum())
    if t70 == "on":
        ok = has_cols and ((absent_starters == 0 or n_bumped > 0) and (early_q == 0 or n_active > 0))
        record("t70_rules_effect", ok,
               f"T-70 rules declared ON: trace {'present (' + trace_src + ')' if has_cols else 'ABSENT'}; {absent_starters} absent depth-1 "
               f"starter(s) -> {n_bumped} bumped backup(s); {early_q} early-game Questionable(s) -> {n_active} activated",
               absent_starters=absent_starters, bumped=n_bumped, early_q=early_q, activated=n_active, trace_source=trace_src if has_cols else None)
    else:
        record("t70_rules_effect", n_active == 0 and n_bumped == 0,
               f"T-70 rules declared OFF: {n_active} activated, {n_bumped} bumped (undeclared lever if nonzero)",
               activated=n_active, bumped=n_bumped)

    # ---- union_main: a union receipt's declared main form must be what the book holds (lever check)
    uni = cfg.get("union") or {}
    if uni:
        main = uni.get("main", "mean")
        if "source_run" in cands.columns and "book_rank" in cands.columns:
            top = cands[cands["book_rank"].notna() & (cands["book_rank"] <= k_mean)]
            n_pmo = int((top["source_run"] == "pmo_x50").sum())
            if main == "pmo_x50":
                px = uni.get("pmo_x50") or {}
                dcap = px.get("dst_cap")
                dst_ok = True if not isinstance(dcap, int) else int(px.get("max_dst_rows_used", 10**9)) <= dcap
                ok = n_pmo == len(top) == k_mean and int(px.get("max_exposure_used", 10**9)) <= int(px.get("exposure_cap", 0)) and dst_ok
                record("union_main", ok, f"union main declared pmo_x50: {n_pmo} of {len(top)} main rows are pmo_x50 rows (need {k_mean}); "
                       f"max exposure used {px.get('max_exposure_used')} <= cap {px.get('exposure_cap')}; DST rows used {px.get('max_dst_rows_used')} "
                       f"<= DST cap {dcap}", main=main, pmo_rows_in_main=n_pmo, dst_cap_ok=dst_ok)
            elif main == "mix":
                # study 18's shape portfolio: every main row is a mix row tagged with a known cell, under the declared caps
                px = uni.get("mix") or {}
                n_mix = int((top["source_run"] == "mix").sum())
                tags = top["tag"].astype(str) if "tag" in top.columns else pd.Series([""] * len(top))
                cells = tags.str.replace("mix_", "", n=1)
                tagged = int(tags.str.startswith("mix_").sum())
                dcap = px.get("dst_cap")
                dst_ok = True if not isinstance(dcap, int) else int(px.get("max_dst_rows_used", 10**9)) <= dcap
                ok = (n_mix == tagged == len(top) == k_mean and int(px.get("max_exposure_used", 10**9)) <= int(px.get("exposure_cap", 0))
                      and dst_ok and bool(px.get("mix")))
                record("union_main", ok, f"union main declared mix: {n_mix} of {len(top)} main rows are mix rows, {tagged} tagged with a cell "
                       f"(need {k_mean}); cells {dict(cells.value_counts())}; max exposure used {px.get('max_exposure_used')} <= cap "
                       f"{px.get('exposure_cap')}; DST rows used {px.get('max_dst_rows_used')} <= DST cap {dcap}",
                       main=main, mix_rows_in_main=n_mix, dst_cap_ok=dst_ok)
            else:
                n_mix = int((top["source_run"] == "mix").sum())
                record("union_main", n_pmo == 0 and n_mix == 0, f"union main declared {main}: {n_pmo} pmo_x50 rows in the main book (must be 0)"
                       + (f"; {n_mix} mix rows (must be 0)" if n_mix else ""), main=main, pmo_rows_in_main=n_pmo)
        else:
            record("union_main", False, "union receipt without source_run/book_rank columns in candidates.parquet", main=main)

    # ---- main_own_term: a declared ownership term must leave its trace (source file, sha256, coverage, a control main that
    # differs); an undeclared one must leave none (reviewer 2026-09-29 gate 3; laptop W-A)
    if uni:
        px = (uni.get("mix") if uni.get("main") == "mix" else uni.get("pmo_x50")) or {}      # the term sits under its main's key
        term = px.get("own_term") or {}
        tilt = float(term.get("tilt") or 0.0)
        control = run / "book_main_control.csv"
        if tilt > 0:
            problems: list[str] = []
            if uni.get("main", "mean") not in ("pmo_x50", "mix"):
                problems.append(f"own_term declared on main={uni.get('main')}")
            src = term.get("source"); want = term.get("source_sha256")
            if not src or not want:
                problems.append("receipt own_term lacks source/source_sha256")
            elif not Path(src).is_file():
                problems.append(f"ownership source {src} is not on disk")
            else:
                got = hashlib.sha256(Path(src).read_bytes()).hexdigest()
                if got != want:
                    problems.append(f"ownership source sha256 {got[:12]} != receipt {str(want)[:12]}")
            cov = term.get("coverage_projected_5"); min_cov = term.get("min_coverage")
            if cov is None or min_cov is None:
                problems.append("receipt own_term lacks coverage_projected_5/min_coverage")
            elif float(cov) < float(min_cov):
                problems.append(f"coverage {float(cov):.3f} below min_coverage {float(min_cov):.2f}")
            if not control.is_file():
                problems.append("book_main_control.csv missing")
            else:
                ctrl = [r for r in csv.reader(control.open())][1:]
                ctrl_set = {tuple(sorted(r)) for r in ctrl}
                main_set = {tuple(sorted(r)) for r in book[:k_mean]}
                if len(ctrl) != k_mean:
                    problems.append(f"book_main_control.csv holds {len(ctrl)} rows, not {k_mean}")
                if main_set == ctrl_set:
                    problems.append("the entered main is identical to the control main (the term changed nothing)")
                shared = len(main_set & ctrl_set)
            record("main_own_term", not problems,
                   f"ownership term declared (tilt {tilt}): " + ("; ".join(problems) if problems else
                   f"source sha256 matches, coverage {term.get('coverage_projected_5')} >= {term.get('min_coverage')}, control main present, "
                   f"{shared} of {k_mean} main rows shared with it"), tilt=tilt, problems=len(problems))
        else:
            record("main_own_term", not control.is_file(),
                   "no ownership term declared: " + ("book_main_control.csv is present (an undeclared term?)" if control.is_file() else "no control book, as expected"),
                   tilt=0.0)

    # ---- proj_source (operator 2026-10-05, FP projections): a declared projection override must travel with the book
    # (proj_source.csv in the run dir, its sha256 as the receipt says) and its gates must hold. No check when undeclared.
    ps = (cfg.get("union") or {}).get("proj_source") or {}
    if ps:
        problems = []
        f = run / "proj_source.csv"
        if not f.is_file():
            problems.append("proj_source.csv missing from the run dir")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != ps.get("sha256"):
            problems.append("proj_source.csv sha256 differs from the receipt")
        g = ps.get("gates") or {}
        if float(g.get("coverage_skill_ge5", 0)) < 0.95:
            problems.append(f"coverage {g.get('coverage_skill_ge5')} < 0.95")
        if not float(g.get("pearson_r", 0)) >= 0.7:
            problems.append(f"r(FP, ours) {g.get('pearson_r')} < 0.7")
        # before_inactives is FP's own update time since 4a860839 (H2), not our capture time: name both (the reviewer, 10-07)
        cap = ps.get("capture") or {}
        record("proj_source", not problems, f"FP projections for {ps.get('replaced')} players (ours for {ps.get('kept_ours')}); captured "
               f"{cap.get('retrieved_at')}, FP last updated {cap.get('fp_last_updated') or 'UNKNOWN'}"
               f"{'; FP UPDATED BEFORE THE INACTIVES' if ps.get('before_inactives') else ''}"
               + (f"; problems: {problems}" if problems else ""), replaced=ps.get("replaced"))

    # ---- book_rows_legal
    frame_ids = set(fr["id"].astype(str)) | set(fr["dk_player_id"].astype(str)) if "dk_player_id" in fr else set(fr["id"].astype(str))
    # The mean rows (the first k_mean) must be distinct and so must the sleeve rows among themselves; a sleeve row MAY repeat
    # a mean row (the adopted mean sleeve is the top-T by the same score, so the deep contests take the top mean rows again;
    # reviewer 2026-09-28). No contest ever holds one lineup twice: a deep contest reads sleeve rows only.
    main_rows, sleeve_rows = book[:k_mean], book[k_mean:]
    dup = (len(main_rows) - len({tuple(sorted(r)) for r in main_rows})) + (len(sleeve_rows) - len({tuple(sorted(r)) for r in sleeve_rows}))
    repeats = len({tuple(sorted(r)) for r in sleeve_rows} & {tuple(sorted(r)) for r in main_rows})
    unknown = sum(1 for r in book for x in r if x.strip() not in frame_ids)
    short = sum(1 for r in book if len(r) != 9)
    record("book_rows_legal", dup == 0 and unknown == 0 and short == 0,
           f"{dup} duplicate rows (within the mean rows or within the sleeve; {repeats} sleeve rows repeat a mean row, allowed), "
           f"{unknown} ids not in the frame, {short} rows without 9 slots", duplicates=dup, sleeve_repeats_of_main=repeats,
           unknown_ids=unknown, short_rows=short)

    failed = [c["check"] for c in checks if not c["ok"]]
    return {"run": str(run), "layout": layout, "checks": checks, "failed": failed, "ok": not failed}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path)
    ap.add_argument("--contests", type=Path, required=True)
    ap.add_argument("--layout", default="head")
    ap.add_argument("--expect-selector", default=None)
    ap.add_argument("--expect-max-per-game", type=int, default=None)
    ap.add_argument("--min-salary", type=int, default=49000)
    ap.add_argument("--punt-max", type=int, default=4000)
    ap.add_argument("--market-floor", type=float, default=0.30)
    ap.add_argument("--sources", default="market_points:0.30,dk_ppg:0.80",
                    help="comma list of frame_column:min_nonnull_share that must be present")
    ap.add_argument("--fade", choices=["on", "off"], default="off",
                    help="whether an ownership fade is declared ON for this build (the audit checks its trace either way)")
    ap.add_argument("--t70", choices=["on", "off"], default="off",
                    help="whether the T-70 rules (T70_ACTIVE_Q / T70_VACATED_BUMP) are declared ON for this build")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    contests = json.loads(a.contests.read_text()); contests = contests if isinstance(contests, list) else contests["contests"]
    sources = {}
    for item in [x for x in a.sources.split(",") if x.strip()]:
        col, floor = item.split(":"); sources[col.strip()] = float(floor)
    result = audit(a.run, contests, layout=a.layout, expect_selector=a.expect_selector, expect_max_per_game=a.expect_max_per_game,
                   min_salary=a.min_salary, punt_max=a.punt_max, market_floor=a.market_floor, sources=sources, fade=a.fade,
                   t70=a.t70)
    out = a.out or (a.run / "lever_audit.json")
    out.write_text(json.dumps(result, indent=2) + "\n")
    for c in result["checks"]:
        print(f"{'PASS' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}")
    if result["failed"]:
        print(f"BUILD AUDIT FAILED: {result['failed']} (receipt {out})", file=sys.stderr)
        return 2
    print(f"build audit OK: {len(result['checks'])} checks (receipt {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
