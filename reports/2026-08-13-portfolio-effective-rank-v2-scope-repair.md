# Incumbent effective-rank composite-scope repair

Date frozen: 2026-08-13, after the v1 harvester rejected its report and before
any effective-rank metric was decoded, summarized, or used.

## Invalid v1 execution

Execution `portfolio-effective-rank-v1-jbgtr` completed successfully, but the
fail-closed harvester rejected its output before writing `report.json`. The
terminal transport contains 54 slates rather than the registered 107. The
cause is an input-contract error, not a scientific result: panel
`20260812-pitclean-e80-selected-tabpfn-active-v2` is the selected evaluation
book for 2023--2025 only. The terminal policy uses historical source panel
`20260811-pitclean-e80-k1-role12union-a12ab31` for 2019, 2021 and 2022.

The v1 manifest incorrectly described the 54-slate evaluation panel as a
107-slate single-panel source. Its raw checksummed output is retained only as
invalid operational evidence. No partial or aggregate v1 diagnostic is
accepted.

## Sole v2 repair

Preserve every scientific output, score artifact, book size, tail line,
control, seed and no-outcome rule in the original protocol. Change only the
warehouse identity to the terminal composite it intended to describe:

- 2019, 2021 and 2022 must come from promoted panel
  `20260811-pitclean-e80-k1-role12union-a12ab31`;
- 2023, 2024 and 2025 must come from promoted panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`;
- each slate must name exactly one expected source panel in the report; and
- the harvester must require exactly 107 unique slates and the exact
  season-to-panel mapping before it writes the report.

The replacement uses a new v2 run/job identity and an immutable full-test
image. It may not accept or summarize the invalid v1 payload. Because the
diagnostic remains outcome-blind and non-gating, this repair cannot select,
promote, reject, or retune an arm.
