# Incumbent portfolio effective-rank protocol

Date frozen: 2026-08-13, before running the diagnostic.

## Purpose and scope

Describe the simulator-implied conditional diversity and tail overlap of the
accepted 80-entry incumbent after the G2 dependence gate closed without a
production change. This is outcome-blind descriptive evidence. It cannot
promote, reject, retune or reopen an arm and it is not an estimate of realized
ROI or a claim that the real portfolio contains the reported number of
independent bets.

## Immutable input

- Panel: `20260812-pitclean-e80-selected-tabpfn-active-v2`
- Warehouse source: promoted `replay_candidates`
- Expected slates: 107 across 2019, 2021, 2022, 2023, 2024 and 2025
- Entries per selected book: 80
- Worlds per slate: 10,000
- Dependence law: unchanged accepted incumbent after valid G2 disposition
  `g2-dependence-gate-fails`

Every slate must provide one checksummed candidate-by-world artifact. The
analyzer must verify its SHA-256, canonical `cand_ix` universe, exact selected
rank identity, world count, tail line and simulated means. No realized score
or lineup outcome column may be queried.

## Frozen outputs

For each slate and selected book, report:

- raw covariance and correlation participation/entropy ranks and spectra;
- covariance-leading-PC-deflated spectra, with deflated correlation
  participation ratio as the conditional-diversity headline;
- leading entry and player loadings;
- exact event, pair-support, joint-rate/lift and Jaccard disclosures at
  `187, 194, 200, 210, 220, 230, 240`;
- nested selected-prefix books of 20, 40 and 80 entries; and
- the same-pool top-80-by-simulated-mean control plus 20 deterministic random
  80-entry controls seeded by `20260812, season, week`.

The controls use the same worlds and therefore remain in-sample. The report
must retain the caveat that effective rank is likely optimistic while the
measured QB-receiver upper-tail miss remains unresolved, but is not a formal
upper bound.

## Transport and validation

Run only on an immutable full-test Cloud image. Emit deterministic gzip/base64
chunks with JSON/gzip byte counts and SHA-256 checksums. The terminal harvester
must require a clean execution, complete unique chunks, checksum-valid JSON,
the exact panel/source, 107 complete slates, the frozen seasons/lines/books,
80 entries, 10,000 worlds, controls and explicit no-outcome flags before
writing a durable machine report.

## Next action

Summarize the cross-slate conditional-diversity and marginal 20/40/80 tail
coverage results, then proceed to the separately motivated G3 participation-
conditioned allocation hierarchy. This diagnostic does not choose that arm's
parameters or gate.
