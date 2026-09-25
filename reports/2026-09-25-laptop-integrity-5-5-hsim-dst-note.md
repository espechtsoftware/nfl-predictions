# Integrity 5.5: hsim's DST points allowed are reduced by the DST's own touchdowns: confirmed in code, likely small

**Laptop lab note, 2026-09-25.** Outside-the-box plan §0 item 5.5 ("second critic only; Week-4+ fix if confirmed"). Read-only.

**The code, at the live lab pin `9b341d7`** (`src/nfl2/hsim/world.py`, the DST block after the recenter):
```python
fum = rng.poisson(0.47, n_worlds); dtd = rng.poisson(0.115, n_worlds)
pts[i] = dst_points(flat["sacks"][oi], flat["ints"][oi], fum, dtd, flat["points"][oi] - 6.0 * dtd)
```
The last argument is points allowed: the **opponent's** simulated points minus six for every defensive or return touchdown
the **DST itself** scores.
- **Why it is incoherent:** a DST touchdown adds to the DST's own team's score, not to the opponent's.
  - The subtraction is defensible only under an unstated model: the pick-six *replaces* an opponent scoring drive worth
    exactly six. That is at best approximate, and it ties points allowed to a draw that is independent of the opponent's
    path.
  - In the ~11% of worlds with `dtd ≥ 1` (Poisson 0.115), points allowed falls by 6 per TD. That can lift the DST one or
    two points-allowed tiers, **on top of** the TD's own 6 points: a double reward that concentrates in exactly the DST's
    best worlds.
- **Where it matters:** the live selection banks are the incumbent law **plus** corrected hsim (dual-law
  `select_expected_max`). So hsim's DST tail feeds book selection. It does not feed projections (served means come from
  production), and `recenter` does not touch the DST rows, which are computed after it.
- **Size:** not measured yet; expected small (a fraction of a point on the DST mean, more in its upper tail). DSTs are one
  slot per lineup, and selection is sensitive to tail shape.

**Proposed Week-4+ check (lab, outcome-free first):**
1. On a few 2024 slates, draw hsim worlds twice with the same seed, once as today and once with points allowed =
   `flat["points"][oi]`. Report the DST mean, p90 and the share of worlds in each points-allowed tier.
2. If the upper tail moves materially, the default-off fix is to drop the subtraction. A replay panel would then be
   needed before the pin moves, because it changes the selection law (the post-selection law applies).

No change is proposed for Week 3.
