"""Shared player-name normalization (2026-08-04 readiness check).

Name joins live only at the system's EDGES (typed prefs, prop-market
vendor names, external imports) — the core pipeline is ID-keyed. But
those edges silently dropped players on suffix ("Odell Beckham Jr.")
and diminutive ("Cameron Ward" vs "Cam Ward") variants. Measured on
2025 props: suffix-stripping +1.4% match rate; the initial fallback
catches diminutives when unambiguous.
"""
from __future__ import annotations

import re

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def norm_name(s: str) -> str:
    """Lowercase, alpha-only, generational suffixes stripped."""
    s = re.sub(r"[^a-z ]", "", str(s).lower())
    toks = s.split()
    while len(toks) > 2 and toks[-1] in _SUFFIXES:
        toks = toks[:-1]
    return " ".join(toks)


def initial_key(s: str) -> str:
    """'cam ward' / 'cameron ward' -> 'c ward' — diminutive-proof, but
    ambiguous (two J. Joneses collide); use only via match_map."""
    n = norm_name(s)
    toks = n.split()
    return (toks[0][0] + " " + toks[-1]) if len(toks) >= 2 else n


def match_map(reference: dict[str, object]) -> dict[str, object]:
    """Expand {display_name: value} into a lookup keyed by norm_name
    plus UNAMBIGUOUS initial keys (colliding initial keys are dropped —
    never guess between two J. Joneses)."""
    out: dict[str, object] = {}
    for name, val in reference.items():
        out[norm_name(name)] = val
    ik: dict[str, list] = {}
    for name, val in reference.items():
        ik.setdefault(initial_key(name), []).append(val)
    for k, vals in ik.items():
        if k not in out and len(set(map(str, vals))) == 1:
            out[k] = vals[0]
    return out


def resolve(name: str, lookup: dict[str, object]):
    """Two-stage: exact normalized match, then initial-key fallback."""
    n = norm_name(name)
    if n in lookup:
        return lookup[n]
    return lookup.get(initial_key(name))
