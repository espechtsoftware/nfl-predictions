"""The adopted classic-tournament lineup policy.

Historical research can continue to expose environment-controlled arms, but
the money-lineup path must not inherit whichever research variables happen to
be present in a process.  This module is the single, code-reviewed production
decision that the projection job, app, simulator, optimizer and CSV routes
consume explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ClassicProductionPolicy:
    policy_id: str = "classic-k1-ce12-boom28-v1"
    source_panel: str = "20260809-e80-k1-ce12-c616390"
    model_variant: str = "tail_k1"
    model_ensemble: int = 1
    default_entries: int = 80
    selector: str = "greedy-tail-coverage"
    tail_line: float = 194.0
    min_lineup_salary: int = 49_000
    blend_model_weight: float = 0.45
    candidate_multiple: int = 2
    n_ce: int = 12
    n_boom: int = 28
    ce_seed: int = 1701

    def engine_environment(
        self, base: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return the complete effective env for one production build.

        Infrastructure settings from ``base`` survive (BQ/GCS identity,
        candidate logging and code SHA), while every research lever that can
        change a classic roster is overwritten with the adopted value.  The
        returned mapping is passed as data; it never mutates ``os.environ``
        and is therefore safe under concurrent FastAPI requests.
        """
        env = dict(base or {})
        env.update({
            # Model, simulator and marginal shape.
            "MODEL_REGISTRY_VARIANT": self.model_variant,
            "MODEL_ENSEMBLE": str(self.model_ensemble),
            "BLEND_MODEL_WEIGHT": str(self.blend_model_weight),
            "LIVE_SIMS": "30000",
            "GAME_SIM_MODE": "possession",
            "GAME_SIM_PACE": "",
            "GAME_SIM_TEAM_FACTORS": "1",
            "GAME_SIM_USAGE": "",
            "TD_LEDGER": "",
            "SIM_WIDEN_DRAWS": "fitted",
            "ROOKIE_WIDEN": "",
            "TABPFN_MARGINALS": "1",
            "EMP_MARGINALS": "1",
            "EMP_POS": "",
            "SHAPE_MIX": "1",
            "DST_CORR_DRAWS": "",
            # Optimizer construction.
            "MIN_LINEUP_SALARY": str(self.min_lineup_salary),
            "PUNT_MIN": "0",
            "PUNT_MAX": "4000",
            "PUNT_STRICT": "",
            "VALUE2_MIN": "0",
            "OWN_BARBELL": "",
            "MAX_PER_GAME": "0",
            "OWN_MODEL": "",
            "PUNT_BOOM": "0",
            "PUNT_BOOM_WR": "",
            "WR_BOOM": "0",
            # Fixed 12-for-12 CE replacement and incumbent generators.
            "GEN_TOTAL_BUDGET": "40",
            "N_CE": str(self.n_ce),
            "N_EPISTEMIC": "0",
            "N_BOOM": str(self.n_boom),
            "CE_SEED": str(self.ce_seed),
            "CE_GAMES": "4",
            "REPLACEMENT_SLOTS": str(self.n_ce),
            "N_GUMBEL": "0",
            "N_NOSTACK": "0",
            "N_LOWSAL": "0",
            "Q99_WILD": "0",
            "QD_CELLS": "0",
            "HYPER_BOOM": "0",
            "N_QB_VARIANTS": "4",
            "N_MIDQB": "0",
            "N_GAMESTACK": "4",
            "N_DARKGAME": "10",
            "CAND_MULT": str(self.candidate_multiple),
            # Fixed coverage selector; rejected selector arms stay off.
            "SELECT_OBJ": "",
            "SELECT_LSE": "0",
            "M4_QBLOCK": "0",
            "MAX_QBS": "0",
            "PEAK_SLICE": "0",
            # Paired-panel controls must never trim a live candidate pool.
            "GEN_POOL_CAP": "0",
            "GEN_POOL_CAP_MAP": "",
            "EPISTEMIC_FAMILY": "standard",
        })
        return env

    def public_identity(
        self, *, model_version: str | None = None,
        entries: int | None = None, tail_line: float | None = None,
    ) -> dict:
        """Stable JSON/header-friendly identity for a generated book."""
        effective_entries = self.default_entries if entries is None else entries
        effective_line = self.tail_line if tail_line is None else tail_line
        return {
            "policy_id": self.policy_id,
            "source_panel": self.source_panel,
            "model_variant": self.model_variant,
            "model_ensemble": self.model_ensemble,
            "model_version": model_version,
            "selector": self.selector,
            "tail_line": float(effective_line),
            "default_entries": self.default_entries,
            "entries": int(effective_entries),
            "salary_floor": self.min_lineup_salary,
            "blend": {
                "model": self.blend_model_weight,
                "market": 1.0 - self.blend_model_weight,
            },
            "portfolio_allocation": {
                "ce": self.n_ce,
                "boom": self.n_boom,
                "total_replacement_slots": self.n_ce + self.n_boom,
            },
        }


ADOPTED_CLASSIC_POLICY = ClassicProductionPolicy()
