FROM python:3.11-slim

WORKDIR /app

# libgomp is needed by LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md CLAUDE.md cloudbuild.yaml ./
# The final forensic image verifies the byte-level inventory of every tracked
# report before any outcome query.  This remains a private Artifact Registry
# image; the vendor-derived corpus is not published by the application.
COPY reports ./reports
COPY src ./src
COPY sql ./sql
COPY scripts/harvest_accept.py ./scripts/harvest_accept.py
COPY scripts/run_atlas_minimal_world_selection_c.py ./scripts/run_atlas_minimal_world_selection_c.py
COPY scripts/run_all_boom_reallocation_c.py ./scripts/run_all_boom_reallocation_c.py
COPY scripts/run_all_boom_selection_s.py ./scripts/run_all_boom_selection_s.py
COPY scripts/run_stack_relaxation_carve.py ./scripts/run_stack_relaxation_carve.py
COPY scripts/run_a7_select_ladder.py ./scripts/run_a7_select_ladder.py
COPY scripts/freeze_a7_select_ladder.py ./scripts/freeze_a7_select_ladder.py
COPY scripts/cloud_a7_select_ladder.sh ./scripts/cloud_a7_select_ladder.sh
COPY scripts/watch_a7_select_ladder_queue.sh ./scripts/watch_a7_select_ladder_queue.sh
COPY scripts/finish_a7_select_ladder.py ./scripts/finish_a7_select_ladder.py
COPY scripts/close_a7_select_ladder_failed_preflight_v1.py ./scripts/close_a7_select_ladder_failed_preflight_v1.py
COPY scripts/run_lr8_training_source.py ./scripts/run_lr8_training_source.py
COPY scripts/finish_lr8_training_source_smoke.py ./scripts/finish_lr8_training_source_smoke.py
COPY scripts/cloud_lr8_training_source_smoke.sh ./scripts/cloud_lr8_training_source_smoke.sh
COPY scripts/watch_lr8_training_source_smoke_queue.sh ./scripts/watch_lr8_training_source_smoke_queue.sh
COPY scripts/historical_outcome_lease.py ./scripts/historical_outcome_lease.py
COPY scripts/run_b1_union_c_census.py ./scripts/run_b1_union_c_census.py
COPY scripts/run_b2prime_volume_oi_admission.py ./scripts/run_b2prime_volume_oi_admission.py
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
COPY scripts/run_post_forensic_construction_addendum.py ./scripts/run_post_forensic_construction_addendum.py
COPY scripts/run_exact_p_generator_constraint_census.py ./scripts/run_exact_p_generator_constraint_census.py
COPY scripts/run_exact_p_corrected_identity_source.py ./scripts/run_exact_p_corrected_identity_source.py
COPY scripts/run_atlas_world_ranking.py ./scripts/run_atlas_world_ranking.py
COPY scripts/run_atlas_money_transfer.py ./scripts/run_atlas_money_transfer.py
COPY scripts/run_atlas_matched_diversity_mvp.py ./scripts/run_atlas_matched_diversity_mvp.py
COPY scripts/render_atlas_matched_diversity_repair4_command.py ./scripts/render_atlas_matched_diversity_repair4_command.py
COPY scripts/run_atlas_historical_score_diagnostic.py ./scripts/run_atlas_historical_score_diagnostic.py
COPY scripts/run_atlas_historical_score_diagnostic_v3.py ./scripts/run_atlas_historical_score_diagnostic_v3.py
COPY scripts/run_atlas_historical_score_diagnostic_v4.py ./scripts/run_atlas_historical_score_diagnostic_v4.py
COPY scripts/run_constraint_lattice_scorefree.py ./scripts/run_constraint_lattice_scorefree.py
COPY scripts/aggregate_constraint_lattice_scorefree.py ./scripts/aggregate_constraint_lattice_scorefree.py
COPY scripts/run_constraint_lattice_support_census.py ./scripts/run_constraint_lattice_support_census.py
COPY scripts/aggregate_constraint_lattice_support_census.py ./scripts/aggregate_constraint_lattice_support_census.py
COPY scripts/run_constraint_lattice_resource_preflight.py ./scripts/run_constraint_lattice_resource_preflight.py
COPY scripts/run_recourse_aware_initial_scorefree.py ./scripts/run_recourse_aware_initial_scorefree.py
COPY scripts/aggregate_recourse_aware_initial_scorefree.py ./scripts/aggregate_recourse_aware_initial_scorefree.py
COPY scripts/coherent_market_state_sources.py ./scripts/coherent_market_state_sources.py
COPY scripts/run_coherent_market_state_scorefree.py ./scripts/run_coherent_market_state_scorefree.py
COPY scripts/aggregate_coherent_market_state_scorefree.py ./scripts/aggregate_coherent_market_state_scorefree.py
COPY scripts/run_coherent_market_state_historical_score.py ./scripts/run_coherent_market_state_historical_score.py
COPY scripts/run_production_law_dependence_source_lock.py ./scripts/run_production_law_dependence_source_lock.py
COPY scripts/run_production_law_dependence_remeasurement.py ./scripts/run_production_law_dependence_remeasurement.py
COPY scripts/run_a2a_rank_factor_split_census.py ./scripts/run_a2a_rank_factor_split_census.py
COPY scripts/run_a2a_production_law_dependence_remeasurement.py ./scripts/run_a2a_production_law_dependence_remeasurement.py
COPY scripts/finish_a2a_production_law_dependence_remeasurement.py ./scripts/finish_a2a_production_law_dependence_remeasurement.py
COPY scripts/cloud_a2a_production_law_dependence_remeasurement.sh ./scripts/cloud_a2a_production_law_dependence_remeasurement.sh
COPY scripts/watch_a2a_production_law_dependence_queue.sh ./scripts/watch_a2a_production_law_dependence_queue.sh
COPY scripts/run_b1_corpus_tail_model.py ./scripts/run_b1_corpus_tail_model.py
COPY scripts/finish_b1_corpus_tail_model.py ./scripts/finish_b1_corpus_tail_model.py
COPY scripts/cloud_b1_corpus_tail_model.sh ./scripts/cloud_b1_corpus_tail_model.sh
COPY scripts/watch_b1_corpus_tail_queue.sh ./scripts/watch_b1_corpus_tail_queue.sh
COPY scripts/run_b1_corpus_tail_panel_producer.py ./scripts/run_b1_corpus_tail_panel_producer.py
COPY scripts/run_b1_corpus_tail_shadow_transport.py ./scripts/run_b1_corpus_tail_shadow_transport.py
COPY scripts/run_b1_authoritative_settlement.py ./scripts/run_b1_authoritative_settlement.py
COPY scripts/cloud_b1_corpus_tail_shadow.sh ./scripts/cloud_b1_corpus_tail_shadow.sh
COPY scripts/run_cbwu_seed_order_audit.py ./scripts/run_cbwu_seed_order_audit.py
COPY scripts/run_cbwu_oi_construction_diagnostic.py ./scripts/run_cbwu_oi_construction_diagnostic.py
COPY scripts/run_cbwu_oi_selector_stability.py ./scripts/run_cbwu_oi_selector_stability.py
COPY scripts/run_exact_n_scorefree.py ./scripts/run_exact_n_scorefree.py
COPY scripts/run_realistic_recourse_sizing.py ./scripts/run_realistic_recourse_sizing.py
COPY scripts/audit_recourse_scoring_reconciliation.py ./scripts/audit_recourse_scoring_reconciliation.py
COPY scripts/cleanup_final_forensic_warehouse.py ./scripts/cleanup_final_forensic_warehouse.py

RUN pip install --no-cache-dir ".[gcp,app]"

# Cloud Run Jobs override the command per job; the default serves the UI.
CMD ["uvicorn", "nfl_dfs.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
