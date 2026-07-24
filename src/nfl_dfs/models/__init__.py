"""Modeling layer: DK scoring, baseline + component models, Monte Carlo
composition, market blending, cold starts, registry, and drift monitoring.

Guide map (see README):
  §6.1  scoring.py     — DK Classic scoring incl. yardage bonuses
  §6.3  validation.py  — walk-forward folds, market comparison, calibration
  §7.3  baseline.py    — direct DK-points model with quantile ceilings
  §6.2  components.py  — per-component LightGBM models
  §6.2  simulate.py    — Monte Carlo composition of components
  §7.4  weights.py     — recency sample weights
  §7.5  tuning.py      — walk-forward Optuna tuning (optional extra)
  §7.6  coldstart.py   — role priors + widened uncertainty
  §7.7  blend.py       — market blending, prop-line conversions
  §7.8  registry.py    — versioned model store (local or GCS)
  §7.8  monitoring.py  — MAE/coverage/PSI/null-rate drift alarms
  §7.8  train_job.py   — weekly retrain entry point
"""
