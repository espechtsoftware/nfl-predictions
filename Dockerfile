FROM python:3.11-slim

WORKDIR /app

# libgomp is needed by LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md CLAUDE.md ./
# The final forensic image verifies the byte-level inventory of every tracked
# report before any outcome query.  This remains a private Artifact Registry
# image; the vendor-derived corpus is not published by the application.
COPY reports ./reports
COPY src ./src
COPY sql ./sql
COPY scripts/harvest_accept.py ./scripts/harvest_accept.py
COPY scripts/compare_adoption_panel.py ./scripts/compare_adoption_panel.py
COPY scripts/compare_k1_ce_panel.py ./scripts/compare_k1_ce_panel.py
COPY scripts/compare_k1_role_belief_panel.py ./scripts/compare_k1_role_belief_panel.py
COPY scripts/compare_corrected_k1_direct_role.py ./scripts/compare_corrected_k1_direct_role.py
COPY scripts/compare_pit_tier1.py ./scripts/compare_pit_tier1.py
COPY scripts/compare_served_tail_lineup.py ./scripts/compare_served_tail_lineup.py
COPY scripts/compare_served_position_lineup.py ./scripts/compare_served_position_lineup.py
COPY scripts/compare_served_position_lineup_v2.py ./scripts/compare_served_position_lineup_v2.py
COPY scripts/compare_usage_dirichlet_lineup.py ./scripts/compare_usage_dirichlet_lineup.py
COPY scripts/compare_usage_dirichlet_lineup_v2.py ./scripts/compare_usage_dirichlet_lineup_v2.py
COPY scripts/compare_tabpfn_active_label_lineup.py ./scripts/compare_tabpfn_active_label_lineup.py
COPY scripts/compare_tabpfn_active_label_lineup_v2.py ./scripts/compare_tabpfn_active_label_lineup_v2.py
COPY scripts/compare_tabpfn_sched_lineup_v1.py ./scripts/compare_tabpfn_sched_lineup_v1.py
COPY scripts/compare_tabpfn_team_qb_lineup_v1.py ./scripts/compare_tabpfn_team_qb_lineup_v1.py
COPY scripts/compare_active_label_usage_revalidation.py ./scripts/compare_active_label_usage_revalidation.py
COPY scripts/compare_k1_milly_ownership_panel.py ./scripts/compare_k1_milly_ownership_panel.py
COPY scripts/compare_exact_replay.py ./scripts/compare_exact_replay.py
COPY scripts/compare_role_belief_panel.py ./scripts/compare_role_belief_panel.py
COPY scripts/evaluate_milly_ownership.py ./scripts/evaluate_milly_ownership.py
COPY scripts/evaluate_k1_ce_reranker.py ./scripts/evaluate_k1_ce_reranker.py
COPY scripts/run_conditional_schaake_smoke.py ./scripts/run_conditional_schaake_smoke.py
COPY scripts/analyze_portfolio_effective_rank.py ./scripts/analyze_portfolio_effective_rank.py
COPY scripts/analyze_incumbent_seed_variance.py ./scripts/analyze_incumbent_seed_variance.py
COPY scripts/analyze_game_team_usage_phase_r.py ./scripts/analyze_game_team_usage_phase_r.py
COPY scripts/analyze_sis_asoe_phase_s.py ./scripts/analyze_sis_asoe_phase_s.py
COPY scripts/analyze_multiseed_candidate_world.py ./scripts/analyze_multiseed_candidate_world.py
COPY scripts/analyze_tabpfn_sis_pass_tail_exact80_v1.py ./scripts/analyze_tabpfn_sis_pass_tail_exact80_v1.py
COPY scripts/analyze_selector_resampling.py ./scripts/analyze_selector_resampling.py
COPY scripts/capture_final_forensic_prelock.py ./scripts/capture_final_forensic_prelock.py
COPY scripts/prepare_final_forensic_freeze.py ./scripts/prepare_final_forensic_freeze.py
COPY scripts/run_final_forensic_hpcs.py ./scripts/run_final_forensic_hpcs.py

RUN pip install --no-cache-dir ".[gcp,app]"

# Cloud Run Jobs override the command per job; the default serves the UI.
CMD ["uvicorn", "nfl_dfs.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
