# Paid Route Share contains prior participation for five zero-support receivers

The outcome-free join found positive Fantasy Points 2026-Week1 Route Share observations for **five of the six** receivers who receive zero opportunity in the archived Week2 hsim bank. This establishes useful prior participation information exists. It does not establish a better predictive model or justify substituting route share for target share.

| Archived zero-support receiver | Prior-week Route Share |
|---|---:|
| Chris Moore | 23.3% |
| Kalif Raymond | 57.9% |
| Kendrick Bourne | 74.4% |
| Jack Bech | 38.7% |
| Denzel Boston | 90.0% |
| Devontez Walker | No matched observation; not inferred zero |

Across all archived players, 125/147 WRs and 79/100 TEs match the feed. Among the 95 WRs outside hsim's archived activity mask, 73 match and 63 have positive routes. All 46 selected activity-supported WRs and all 32 selected TEs have positive routes too. The feed contains no matching RB/QB observations in this census, so it cannot supply a complete replacement for missing opportunity history.

All 265 queried source rows pass the declared identity/week/value checks and resolved player IDs are unique. They share source SHA-256 `07642ab6138be27f62b425376d2c084d9db9dc2d0eb4a63f2f4ba11b3d775e3e`, retrieved September17 17:29 UTC and ingested at 17:30. This is after the Thursday diagnostic build, before Sunday's lock. The source record includes the archive URI. Query job `85a57517-263a-40e4-b0d8-d60c8c75f452` processed 5,419,346 bytes; no vendor requests or warehouse writes.

Source frozen **7ef91992**; [protocol](2026-09-19-route-role-support-protocol.md), [script](reviews/evidence/2026-09-19-route-role-support.py), [evidence](reviews/evidence/2026-09-19-route-role-support.json). Only prior-week participation fields were queried. Neither outcome associations nor changed lineups were evaluated.

**New priority after this census:** the workstation independently traced missing usage history to a concrete salary-week contract defect (`d0b3e4c` on the lab handoff branch). Ingestion writes a null week expecting downstream schedule resolution; the feature salary source filters null weeks out. Week1 stats/snaps exist, but no 2026 salary-week rows reach rolling usage. An isolated correction is now being tested on production branch `fix/2026-09-salary-week-resolution`.

Repair that missing-history path before measuring Route Share's incremental value. A vendor feature can appear unusually informative when the free-data baseline is broken. A subsequent route/participation experiment should compare against the repaired baseline, preserve point-in-time source dates, and evaluate its effect on the final law and selected book. This finding strengthens a specific research question, not an unconditional renewal recommendation. No live changes were made.
