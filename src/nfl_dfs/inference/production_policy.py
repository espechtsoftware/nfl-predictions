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


def contest_entry_policy(
    max_entries_per_user: int,
    requested_entries: int,
    requested_leverage_scale: float,
) -> dict:
    """Resolve the fail-closed portfolio profile for a contest entry cap.

    The adopted selector remains unchanged: smaller books take the first N
    entries from the same candidate/world evidence whose 1--150 entry curve
    was measured.  Low-max contests also cap the soft-field chalk fade so each
    scarce entry is less dependent on a fragile contrarian stand.
    """
    limit = int(max_entries_per_user)
    entries = int(requested_entries)
    if not 1 <= limit <= 150:
        raise ValueError("contest max entries per user must be in 1..150")
    if not 1 <= entries <= min(limit, 80):
        raise ValueError(
            f"requested entries must be in 1..{min(limit, 80)} for this "
            "contest and the adopted 80-entry policy"
        )
    if limit == 1:
        profile = "single-entry-individual-tail"
        leverage_cap = 0.70
        description = (
            "one strongest individual tail lineup; moderated chalk fade"
        )
    elif limit <= 3:
        profile = "three-max-self-sufficient-tail"
        leverage_cap = 0.80
        description = (
            "small self-sufficient book with limited complementary coverage"
        )
    elif limit <= 20:
        profile = "compact-max-tail-coverage"
        leverage_cap = 0.90
        description = (
            "compact tail-coverage book; less diversification than the "
            "80-entry portfolio"
        )
    else:
        profile = "large-max-tail-coverage"
        leverage_cap = 1.00
        description = "adopted large-field tail-coverage portfolio"
    effective_leverage = min(float(requested_leverage_scale), leverage_cap)
    return {
        "profile": profile,
        "max_entries_per_user": limit,
        "entries": entries,
        "selection": "first-N-adopted-CBWU-tail-coverage-order",
        "candidate_entry_basis": 80,
        "requested_leverage_scale": float(requested_leverage_scale),
        "leverage_scale_cap": leverage_cap,
        "effective_leverage_scale": effective_leverage,
        "description": description,
        "tail_line_changed": False,
        "evidence": (
            "historical first-N entry curve; leverage cap is a conservative "
            "contest-format rule pending separate low-max validation"
        ),
    }


@dataclass(frozen=True)
class ClassicProductionPolicy:
    policy_id: str = "classic-k1-role12-boom40-poscal-cbwu-v4"
    source_panel: str = (
        "20260813-multiseed-candidate-world-v1")
    model_variant: str = "tail_k1"
    role_model_variant: str = "tail_k1_role"
    model_ensemble: int = 1
    default_entries: int = 80
    selector: str = "greedy-tail-coverage"
    tail_line: float = 194.0
    min_lineup_salary: int = 49_000
    blend_model_weight: float = 0.45
    candidate_multiple: int = 2
    n_ce: int = 0
    n_role: int = 12
    n_boom: int = 40
    served_position_scales: str = (
        "QB:0.970,RB:1.005,TE:0.940,WR:1.070")
    ce_seed: int = 1701
    role_seed: int = 7331
    role_features: str = (
        "target_share_last,carry_share_last,snap_share_last,"
        "target_share_jump,carry_share_jump,snap_share_jump"
    )
    multiseed_portfolio: str = "CBWU"
    multiseed_seed_pairs: tuple[tuple[int, int], ...] = (
        (0, 7331),
        (1137260708, 2690847602),
        (2875959182, 1630284992),
        (253722715, 3374646876),
        (1643280042, 3977633467),
    )
    multiseed_worlds_per_block: int = 10_000
    multiseed_candidate_entry_basis: int = 80
    prospective_archetype_allocation_version: str = (
        "prospective-archetype-allocation-v1"
    )
    prospective_latent_role_version: str = "prospective-latent-role-state-v1"

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
            # Research caches are explicit and must never leak into money
            # lineups through a process-level environment variable.
            "TABPFN_MARGINAL_TABLE": "",
            "EMP_MARGINALS": "1",
            "EMP_POS": "",
            "SHAPE_MIX": "1",
            # The final-served position calibration passed its frozen
            # exact-80 comparison. Pin the four adopted factors so a research
            # shell variable cannot leak into the money-lineup path.
            "SERVED_TAIL_SCALE": "1",
            "SERVED_POSITION_SCALES": self.served_position_scales,
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
            # Frozen incumbent generation book: direct-role 12 + boom 40.
            "GEN_TOTAL_BUDGET": "52",
            "N_CE": str(self.n_ce),
            "N_EPISTEMIC": str(self.n_role),
            "N_BOOM": str(self.n_boom),
            "CE_SEED": str(self.ce_seed),
            "CE_GAMES": "4",
            "REPLACEMENT_SLOTS": str(self.n_role),
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
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": self.role_features,
            "ROLE_BELIEF_SEED": str(self.role_seed),
            # Frozen multi-seed production mechanism.  Every search retains
            # the K=1 marginals and direct-role/boom candidate mix above;
            # only the registered random streams, fixed candidate allocation
            # and equal selection-world evidence change.
            "MULTISEED_PORTFOLIO": self.multiseed_portfolio,
            "MULTISEED_SEED_PAIRS": ";".join(
                f"R{index}={projection}:{role}"
                for index, (projection, role) in enumerate(
                    self.multiseed_seed_pairs)
            ),
            "MULTISEED_WORLDS_PER_BLOCK": str(
                self.multiseed_worlds_per_block),
            "MULTISEED_CANDIDATE_ENTRY_BASIS": str(
                self.multiseed_candidate_entry_basis),
        })
        return env

    def fallback_environment(
        self, base: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """The prior accepted CE12/boom28 policy for role-model outages.

        Position calibration was validated only with the direct-role/boom40
        candidate book, so the fallback deliberately restores the complete
        older identity-scale policy rather than mixing untested mechanisms.
        """
        env = self.engine_environment(base)
        env.update({
            "GEN_TOTAL_BUDGET": "40",
            "N_CE": "12",
            "N_EPISTEMIC": "0",
            "N_BOOM": "28",
            "EPISTEMIC_FAMILY": "standard",
            "ROLE_BELIEF_FEATURES": "",
            "ROLE_BELIEF_SEED": str(self.role_seed),
            "REPLACEMENT_SLOTS": "12",
            "SERVED_POSITION_SCALES": "",
            # The historical CE12/boom28 outage fallback was not part of the
            # CBWU confirmation. Keep that complete older path single-seed.
            "MULTISEED_PORTFOLIO": "",
            "MULTISEED_SEED_PAIRS": "",
            "MULTISEED_WORLDS_PER_BLOCK": "",
            "MULTISEED_CANDIDATE_ENTRY_BASIS": "",
        })
        return env

    def archetype_shadow_environment(
        self, base: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Outcome-unseen fixed-budget archetype shadow configuration.

        This derives from the complete adopted money environment and changes
        only the CBWU trimming law.  Production never calls this method
        implicitly; a separately labeled shadow job must opt in.
        """
        env = self.engine_environment(base)
        env.update({
            "MULTISEED_PORTFOLIO": "CBWU_ARCHETYPE_SHADOW",
            "ARCHETYPE_ALLOCATION_VERSION": (
                self.prospective_archetype_allocation_version
            ),
            "ARCHETYPE_TAIL_LINE": str(self.tail_line),
            "PROSPECTIVE_SHADOW_ID": "2026-archetype-cbwu-v1",
        })
        return env

    def latent_role_shadow_environment(
        self, base: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Outcome-unseen latent-role candidate replacement shadow.

        This retains the complete adopted five-seed, 40-boom and exact-80
        policy while replacing only its 12 direct-role candidate slots. It is
        never returned by ``engine_environment`` and cannot affect money
        lineups without a separate post-2026 prospective promotion.
        """
        env = self.engine_environment(base)
        env.update({
            "EPISTEMIC_FAMILY": "latent_role_states",
            "ROLE_BELIEF_FEATURES": "",
            "MULTISEED_PORTFOLIO": "CBWU_LATENT_ROLE_SHADOW",
            "PROSPECTIVE_LATENT_ROLE_VERSION": (
                self.prospective_latent_role_version
            ),
            "PROSPECTIVE_SHADOW_ID": "2026-latent-role-cbwu-v1",
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
            "role_model_variant": self.role_model_variant,
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
                "role": self.n_role,
                "boom": self.n_boom,
                "total_generation_solves": (
                    self.n_ce + self.n_role + self.n_boom),
            },
            "served_position_scales": self.served_position_scales,
            "candidate_world_portfolio": {
                "arm": self.multiseed_portfolio,
                "candidate_searches": len(self.multiseed_seed_pairs),
                "fixed_candidate_budget": True,
                "candidate_entry_basis": self.multiseed_candidate_entry_basis,
                "world_blocks": len(self.multiseed_seed_pairs),
                "worlds_per_block": self.multiseed_worlds_per_block,
                "selection_worlds": (
                    len(self.multiseed_seed_pairs)
                    * self.multiseed_worlds_per_block),
                "fail_closed": True,
            },
            "simulation_law": {
                "game_mode": "possession",
                "team_factors": True,
                "usage_allocation": "production-multinomial",
                "game_sim_usage_env": "",
                "dirichlet_k": None,
                "td_ledger": False,
            },
        }


ADOPTED_CLASSIC_POLICY = ClassicProductionPolicy()
