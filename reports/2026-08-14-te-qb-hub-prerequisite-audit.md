# TE-only QB-hub prerequisite audit

Date: 2026-08-14 CDT. This audit uses only the already-harvested repaired-path
Stage R reference. It launches no simulator, joins no new outcome, and scores
no lineup.

## Question

The competitive-WR protocol named a separate TE-only QB-hub rank evaluation
before the WR treatment was observed. Naming the mechanism preserved it from
being invented after the WR result, but did not itself license an experiment.
This audit asks whether the repaired path contains the stable QB-to-TE miss
needed to justify freezing that separate historical arm.

## Existing repaired-path evidence

The canonical Stage R report is
`reports/td-competitive-wr-runs/20260814-td-competitive-wr-v1/reference/report.json`
with report SHA-256
`748822294c90f3178ca79989bac17f065662589230bf0fab24897d2c59898e2b`
and canonical score SHA-256
`2584120b13fa99da99a6f916015c70eb985cb1f06396750de829593d7fd8979e`.

Its supported broad QB-to-TE relationship is already close to realized:

| scope | simulated lift | realized lift | log(simulated/realized) |
|---|---:|---:|---:|
| aggregate | 2.313707 | 2.370873 | -0.024408 |
| 2023 | 2.346178 | 2.152663 | +0.086082 |
| 2024 | 2.339104 | 1.948254 | +0.182834 |
| 2025 | 2.362120 | 3.190173 | -0.300516 |

The analogous supported G0 QB-to-TE cell is 2.294844 simulated versus 2.358795
realized, absolute log error 0.027486. Both aggregate cells are classified
inconclusive, not material misses. The season directions are mixed: increasing
positive QB-to-TE coupling would worsen 2023 and 2024 while moving 2025 in the
desired direction. The TE-to-TE relationship is unsupported at only 37
realized source booms, so it cannot supply a stable competitive-allocation
target or guard.

The original review also identified the structural limitation: most supported
teams have one relevant tight end, leaving no same-position competition for a
centered allocation law. Its suggested composition was a passing WR mechanism
plus a separately passing TE mechanism. The WR treatment is now terminally
invalid/unadjudicated, exact-80 is unlicensed, and its disclosed movement was
adverse on every frozen improvement gate. Composition is therefore prohibited
independently of this prerequisite audit.

## Disposition

The historical TE-only prerequisite does not pass. There is no stable
repaired-path QB-to-TE deficiency to target, no supported TE-to-TE structure
on which to freeze a competitive law, and no passed WR mechanism with which a
TE factor could be composed. Selecting a weak factor or season-specific
strength after observing these values would create a new tuning surface rather
than test the pre-named mechanism.

Do not launch a historical TE-only score-free or exact-80 arm on this panel.
This closes the current-stack historical TE follow-up as not licensed; it does
not claim that every future TE dependence model is impossible. Retain TE/QB
dependence as a prospective 2026 shadow diagnostic if new pre-lock evidence
establishes a stable miss. With the already terminal SIS marginal,
Route/dependence, pass-tail, selector, multi-seed, G-series and TD mechanisms,
the preregistered historical mechanism queue is exhausted and the final
forensic program may proceed.

