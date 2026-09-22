# Scripts behind `reports/2026-09-22-production-ceiling-and-eligibility.md`

Run order and what each one settles:

| script | settles |
|---|---|
| `base_rate.py` | hypergeometric expectation for a random K-row book — the correction to "generated N at 170+, entered none". Self-contained, no artifacts needed. |
| `winning_lines.py` | real Week-1/2 contest winning lines vs our pool ceiling. Warehouse read only. |
| `status_predicts.py` | does served DK status predict realized-minus-projection. Needs the archived run dirs. |
| `doubtful_ab.py` | isolated A/B: exclude DK-Doubtful from the selectable universe, both weeks. |
| `doubtful_null.py` | the null for the above — 120 random comparably-used triples. ~4 min. |

**Artifact dependency.** The last three read archived run directories (`frame.parquet`,
`cands.parquet`, `T_inc.npy`, `T_hs.npy`, roster index) for Weeks 1 and 2. Those are
**not in this repository and must not be committed**: `frame.parquet` carries
Fantasy Points derived columns (`fp_route_*`), which are licensed vendor data. They live
on the workstation under the session scratchpad; ask production for a direct copy.

The scripts hard-code `w1/` and `item3/` as those two run dirs and expect to be run from
the directory holding them. `reports/lab-handoffs/supply_vs_retrieval.py` (the laptop's)
is the one with a proper `--run-dir`; it only needs `frame.parquet` + `candidates.parquet`.
