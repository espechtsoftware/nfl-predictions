# Offline experiment scripts (2026-08-03, research rounds 7-8)

One-shot studies run outside the pipeline; results recorded in
reports/2026-07-25-system-study.md (Addendum 43). Paths reference the
session scratchpad — update the `S` constant to rerun.

- `tabpfn_experiment.py` — TabPFN-v2 vs LightGBM vs trailing baseline on
  the real player-week panel (walk-forward 2019-24 -> 2025).
- `conformal_experiment.py` — CQR / conformal-z calibration of q90
  intervals vs raw quantile and Gaussian shapes.
- `persona_ownership_experiment.py` — LLM persona field ("silicon
  sampling") vs naive_ownership vs real contest ownership
  (raw.contest_ownership). Needs ANTHROPIC_API_KEY.
