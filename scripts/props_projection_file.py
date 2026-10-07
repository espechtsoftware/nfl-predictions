#!/usr/bin/env python3
"""P3's PROPS_MILP projection file (the frozen prereg reports/2026-10-07-prereg-p3-simple-baseline.md §2): the market's
props-implied DK points -- the T-70 frame's market_points -- for every player with a REAL prop number (market_points that
is not the dk_ppg fallback: |market_points - dk_ppg| >= 0.01), and the live projection for everyone else: with --base (the
week's projection override file the union read, e.g. its proj_source.csv) every other player the base file holds keeps
the base's value; without --base they keep the frame's own projection (they are simply not listed).

Written in the format union_reselect's --proj-source reads (apply_proj_source): a CSV (id, fp, source, name, pos) and the
<csv>.json sidecar naming the frame's sha256 and the CSV's sha256 (any other frame is refused there). The file can hold
licensed vendor values (the base): write it under a private run directory, never into the repository.

    python scripts/props_projection_file.py --frame <T-70 frame.parquet> [--base <proj_source.csv>] --out <proj_props.csv>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def props_rows(frame: pd.DataFrame, base: pd.DataFrame | None = None) -> pd.DataFrame:
    """The override rows: props where real, else the base's value for players the base holds."""
    fr = frame.drop_duplicates("id").copy()
    fr["id"] = fr["id"].astype(str)
    mp = pd.to_numeric(fr.get("market_points"), errors="coerce"); dk = pd.to_numeric(fr.get("dk_ppg"), errors="coerce")
    real = mp.notna() & ((mp - dk).abs() >= 0.01)
    out = pd.DataFrame({"id": fr.loc[real, "id"], "fp": mp[real].astype(float), "source": "props",
                        "name": fr.loc[real, "display_name"].astype(str), "pos": fr.loc[real, "pos"].astype(str)})
    if base is not None:
        b = base.assign(id=base["id"].astype(str))
        b = b[~b["id"].isin(set(out["id"]))]
        bfp = pd.to_numeric(b["fp"], errors="coerce")
        if bfp.isna().any():
            raise ValueError("the base file holds a non-number")
        info = fr.set_index("id")
        out = pd.concat([out, pd.DataFrame({"id": b["id"], "fp": bfp.astype(float), "source": "base",
                                            "name": b["id"].map(info["display_name"]).astype(str),
                                            "pos": b["id"].map(info["pos"]).astype(str)})], ignore_index=True)
    if out.empty:
        raise ValueError("no player carries a real prop number (and no base)")
    if not np.isfinite(out["fp"].to_numpy(float)).all():
        raise ValueError("a non-finite projection")
    return out.reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--base", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"PROPS FILE REFUSED: {a.out} exists", file=sys.stderr)
        return 3
    try:
        rows = props_rows(pd.read_parquet(a.frame), pd.read_csv(a.base, dtype={"id": str}) if a.base else None)
    except (ValueError, KeyError) as e:
        print(f"PROPS FILE REFUSED: {e}", file=sys.stderr)
        return 3
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(a.out, index=False)
    meta = {"capture": {"source": "the T-70 frame's market_points (real props only)" + (f"; else the base {a.base.name}" if a.base else "; else the frame's own projection")},
            "frame": str(a.frame), "frame_sha256": sha256_file(a.frame), "csv_sha256": sha256_file(a.out),
            "base": str(a.base) if a.base else None, "base_sha256": sha256_file(a.base) if a.base else None,
            "before_inactives": None, "gates": {}, "props": int((rows.source == "props").sum()), "base_rows": int((rows.source == "base").sum())}
    Path(str(a.out) + ".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"props file {a.out.name}: {meta['props']} players on props, {meta['base_rows']} on the base; frame {meta['frame_sha256'][:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
