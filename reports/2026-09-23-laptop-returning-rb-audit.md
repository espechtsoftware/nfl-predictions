# Audit: the returning-lead-RB study (`RETURNING_RB_ADJ`, shipping `2301dd86`): real and return-specific, but half-size in 2022–24

Requested by production in HANDOFF `69f99753` ("an audit like this morning's… before it is ever switched on"). Same
independently rebuilt panel and walk-forward residuals as `reports/2026-09-23-laptop-returning-teammate-audit.md`.
Scripts: `reports/lab-handoffs/2026-09-23-returning-rb-audit{,-a}.py`.

## Output (verbatim)
```

RETURN (study definition): 139 lead-weeks
  all RB teammates 2018-24                     n_ret  218  diff -2.49 (se 0.36)  negative 6/7 seasons
  all RB teammates 2022-24                     n_ret   59  diff -1.22 (se 0.71)  negative 2/3 seasons
  all RB teammates 2018-21                     n_ret  159  diff -2.98 (se 0.41)  negative 4/4 seasons
  spiked RB teammates 2018-24                  n_ret   90  diff -4.47 (se 0.68)  negative 7/7 seasons
  spiked RB teammates 2022-24                  n_ret   31  diff -3.34 (se 0.98)  negative 3/3 seasons
  spiked RB teammates 2018-21                  n_ret   59  diff -5.09 (se 0.90)  negative 4/4 seasons

LIVE definition (no W-2/W-3 requirement): 200 lead-weeks
  all RB teammates 2018-24                     n_ret  295  diff -2.55 (se 0.33)  negative 7/7 seasons
  all RB teammates 2022-24                     n_ret   80  diff -1.57 (se 0.68)  negative 3/3 seasons
  all RB teammates 2018-21                     n_ret  215  diff -2.94 (se 0.37)  negative 4/4 seasons
  spiked RB teammates 2018-24                  n_ret  112  diff -4.06 (se 0.66)  negative 7/7 seasons
  spiked RB teammates 2022-24                  n_ret   41  diff -2.97 (se 1.08)  negative 3/3 seasons
  spiked RB teammates 2018-21                  n_ret   71  diff -4.72 (se 0.83)  negative 4/4 seasons

PLACEBO: lead STAYS OUT at W (no return): 334 lead-weeks
  all RB teammates 2018-24                     n_ret  588  diff +0.29 (se 0.25)  negative 2/7 seasons
  all RB teammates 2022-24                     n_ret  222  diff +0.41 (se 0.41)  negative 1/3 seasons
  all RB teammates 2018-21                     n_ret  366  diff +0.22 (se 0.31)  negative 1/4 seasons
  spiked RB teammates 2018-24                  n_ret  208  diff +0.44 (se 0.53)  negative 3/7 seasons
  spiked RB teammates 2022-24                  n_ret   77  diff +0.55 (se 0.85)  negative 1/3 seasons
  spiked RB teammates 2018-21                  n_ret  131  diff +0.37 (se 0.69)  negative 2/4 seasons

RB returners 139: played W-1 per box/snaps 2; positive control at W 1.000
           n  false
season             
2014-21  103      2
2022-24   36      0
```

## Reading
- **Reproduced:** −2.49 (0.36) for all RB teammates and −4.47 (0.68) for spiked ones, against production's −2.40 and −4.35.
- **Definition is sound:** 2 of 139 returners had played at W−1 per box scores or snap counts (both pre-2022). The positive
  control is 100%.
- **The effect is return-specific.** New placebo: the lead RB (carry share ≥ 0.40) was out at W−1 and **stays out** at W. The
  backups who played W−1 are then **not** over-projected: +0.29 (0.25) all, +0.44 (0.53) spiked, with mixed signs. So this is not
  generic regression after a spike week; it appears only when the lead comes back. Production's own placebo (the week after
  the return, −1.36) fits a lingering effect while the l4 window still holds the absence.
- **But the size halves in the modern era.** 2022–24 alone (the era with inactive rows, closest to live): **−1.22 (0.71)** all
  (2/3 seasons negative), **−3.34 (0.98)** spiked (3/3). 2018–21 alone: −2.98 and −5.09. The shipped deltas (2.40 / 4.35) are
  pooled, and 2018–21 is 159 of 218 return cases, so they carry the older, larger effect.
- **Why the size matters here:** the subtraction is applied to the model component and floored at zero. A backup projected at
  3–5 points loses 2.4–4.35, which is most of his projection. Over-subtracting a cheap RB who inherits real work is the
  expensive error, so the asymmetry argues for the smaller number.
- **Live definition** (no "active W−2/W−3"): 200 returns, −2.55 all and −4.06 spiked, 7/7. The same picture.

## Recommendation (production's decision)
Before `RETURNING_RB_ADJ` is ever switched on, use the **2022–24 deltas (≈ 1.2 all / 3.3 spiked)** or a recency-weighted
value, not the pooled 2.40 / 4.35. The direction and mechanism are verified; the pooled magnitude is dominated by 2018–21. No
effect this week (no returning lead RB).
