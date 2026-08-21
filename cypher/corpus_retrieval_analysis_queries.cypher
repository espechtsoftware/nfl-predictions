// Read-only catalog for the dedicated corpus research database.
// Canonical GCS objects remain authoritative; properties_json is returned for
// detailed client-side analysis without requiring APOC.

// query: high_tail_lineups
MATCH (lineup:CorpusRetrievalEntity)
WHERE lineup.workstream_namespace = 'corpus-retrieval-research'
  AND lineup.run_id = $run_id
  AND lineup.task_id = $task_id
  AND lineup.task_index = 0
  AND lineup.slate_id = $task_id
  AND lineup.kind = 'LineupCandidate'
  AND lineup.metric_name = 'strict_gt_200_event_count_all_r0_r4_descriptive'
  AND lineup.metric_value >= $minimum_event_count
RETURN lineup.logical_id AS lineup_id,
       lineup.metric_value AS strict_gt_200_event_count,
       lineup.analysis_scope AS analysis_scope,
       lineup.properties_json AS lineup_properties_json,
       lineup.source_uri AS graph_uri,
       lineup.source_generation AS graph_generation,
       lineup.source_sha256 AS graph_sha256,
       lineup.source_bytes AS graph_bytes
ORDER BY strict_gt_200_event_count DESC, lineup_id
LIMIT $limit;

// query: high_tail_world_event_pointer
MATCH (artifact:CorpusRetrievalEntity)
WHERE artifact.workstream_namespace = 'corpus-retrieval-research'
  AND artifact.run_id = $run_id
  AND artifact.task_id = $task_id
  AND artifact.task_index = 0
  AND artifact.slate_id = $task_id
  AND artifact.kind = 'CorpusArtifactPointer'
  AND artifact.logical_id = 'artifact:strict-gt-200-events:task'
RETURN artifact.source_uri AS event_npz_uri,
       artifact.source_generation AS event_npz_generation,
       artifact.source_sha256 AS event_npz_sha256,
       artifact.source_bytes AS event_npz_bytes,
       artifact.properties_json AS semantic_receipt_json;

// query: player_pair_team_game_enrichment
MATCH (measurement:CorpusRetrievalEntity)
WHERE measurement.workstream_namespace = 'corpus-retrieval-research'
  AND measurement.run_id = $run_id
  AND measurement.task_id = $task_id
  AND measurement.task_index = 0
  AND measurement.slate_id = $task_id
  AND measurement.kind = 'CorpusAssociationMeasurement'
  AND measurement.logical_id CONTAINS (':' + $association_kind + ':')
  AND measurement.analysis_scope = $analysis_scope
  AND measurement.metric_value >= $minimum_enrichment
RETURN measurement.logical_id AS association_id,
       measurement.metric_value AS enrichment_vs_all_lineups,
       measurement.properties_json AS support_and_event_counts_json,
       measurement.source_uri AS authority_uri,
       measurement.source_generation AS authority_generation,
       measurement.source_sha256 AS authority_sha256,
       measurement.source_bytes AS authority_bytes
ORDER BY enrichment_vs_all_lineups DESC, association_id
LIMIT $limit;

// query: lineup_pair_correlations
MATCH (measurement:CorpusRetrievalEntity)
WHERE measurement.workstream_namespace = 'corpus-retrieval-research'
  AND measurement.run_id = $run_id
  AND measurement.task_id = $task_id
  AND measurement.task_index = 0
  AND measurement.slate_id = $task_id
  AND measurement.kind = 'CorpusCorrelationMeasurement'
  AND abs(measurement.metric_value) >= $minimum_absolute_correlation
RETURN measurement.logical_id AS lineup_pair_id,
       measurement.metric_value AS pearson_score_correlation,
       measurement.properties_json AS overlap_event_jaccard_json,
       measurement.source_uri AS authority_uri,
       measurement.source_generation AS authority_generation,
       measurement.source_sha256 AS authority_sha256,
       measurement.source_bytes AS authority_bytes
ORDER BY abs(pearson_score_correlation) DESC, lineup_pair_id
LIMIT $limit;

// query: parameter_rule_arm_effects
MATCH (arm:CorpusRetrievalEntity)-[state:CORPUS_RELATION]->(rule:CorpusRetrievalEntity)
WHERE arm.workstream_namespace = 'corpus-parametric-research'
  AND arm.run_id = $batch_id
  AND arm.task_index = $task_index
  AND arm.slate_id = $slate_id
  AND arm.kind = 'CorpusParametricArm'
  AND state.relationship_type = 'RULE_STATE'
  AND state.task_index = $task_index
  AND state.slate_id = $slate_id
  AND rule.kind = 'CorpusParametricRule'
OPTIONAL MATCH (arm)-[has_measurement:CORPUS_RELATION]->(effect:CorpusRetrievalEntity)
WHERE has_measurement.relationship_type = 'HAS_MEASUREMENT'
  AND has_measurement.task_index = $task_index
  AND has_measurement.slate_id = $slate_id
  AND effect.task_index = $task_index
  AND effect.slate_id = $slate_id
  AND effect.analysis_scope = $effect_scope
RETURN arm.task_index AS task_index,
       arm.slate_id AS slate_id,
       arm.parameter_set_id AS parameter_set_id,
       arm.properties_json AS parameter_set_json,
       rule.logical_id AS rule_id,
       state.properties_json AS rule_state_json,
       effect.metric_name AS effect_metric,
       effect.metric_value AS effect_value,
       effect.properties_json AS effect_evidence_json
ORDER BY parameter_set_id, rule_id, effect_metric;

// query: discovery_vs_heldout_strategy_comparison
MATCH (discovery:CorpusRetrievalEntity), (heldout:CorpusRetrievalEntity)
WHERE discovery.workstream_namespace = 'corpus-retrieval-research'
  AND discovery.run_id = $run_id
  AND discovery.task_id = $task_id
  AND discovery.task_index = 0
  AND discovery.slate_id = $task_id
  AND discovery.kind = 'CorpusStrategySplitMeasurement'
  AND discovery.analysis_scope = 'discovery_r0_r3'
  AND discovery.metric_name = $metric_name
  AND heldout.workstream_namespace = discovery.workstream_namespace
  AND heldout.run_id = discovery.run_id
  AND heldout.task_id = discovery.task_id
  AND heldout.task_index = discovery.task_index
  AND heldout.slate_id = discovery.slate_id
  AND heldout.kind = discovery.kind
  AND heldout.strategy_id = discovery.strategy_id
  AND heldout.analysis_scope = 'heldout_r4'
  AND heldout.metric_name = discovery.metric_name
RETURN discovery.strategy_id AS strategy_id,
       discovery.metric_value AS discovery_value,
       heldout.metric_value AS heldout_value,
       heldout.metric_value - discovery.metric_value AS heldout_minus_discovery,
       discovery.source_uri AS selection_authority_uri,
       discovery.source_generation AS selection_authority_generation
ORDER BY heldout_minus_discovery DESC, strategy_id;

// query: uncertainty_and_support_inputs
MATCH (measurement:CorpusRetrievalEntity)
WHERE measurement.workstream_namespace = $workstream_namespace
  AND measurement.run_id = $evidence_run_id
  AND measurement.task_index = $task_index
  AND measurement.slate_id = $slate_id
  AND measurement.kind IN [
    'CorpusAssociationMeasurement',
    'CorpusCoverageMeasurement',
    'CorpusRuleEffectMeasurement'
  ]
  AND measurement.metric_value_present = true
RETURN measurement.run_id AS evidence_run_id,
       measurement.task_index AS task_index,
       measurement.slate_id AS slate_id,
       measurement.parameter_set_id AS parameter_set_id,
       measurement.analysis_scope AS analysis_scope,
       measurement.metric_name AS metric_name,
       measurement.metric_value AS metric_value,
       measurement.properties_json AS denominators_counts_and_hashes_json,
       measurement.source_uri AS authority_uri,
       measurement.source_generation AS authority_generation,
       measurement.source_sha256 AS authority_sha256,
       measurement.source_bytes AS authority_bytes
ORDER BY task_index, parameter_set_id, analysis_scope, metric_name;

// query: parametric_workstream_parent_and_firewall
MATCH (workstream:CorpusRetrievalEntity)-[parent:CORPUS_RELATION]->(retrieval:CorpusRetrievalEntity)
WHERE workstream.workstream_namespace = 'corpus-parametric-research'
  AND workstream.run_id = $batch_id
  AND workstream.kind = 'CorpusParametricWorkstream'
  AND workstream.task_index_present = false
  AND parent.relationship_type = 'DERIVED_FROM_RETRIEVAL_TASK0'
  AND parent.task_index_present = false
  AND retrieval.kind = 'CorpusGraphProjection'
RETURN workstream.logical_id AS parametric_workstream_id,
       workstream.properties_json AS no_feedback_firewall_json,
       retrieval.logical_id AS parent_retrieval_projection,
       retrieval.source_uri AS parent_authority_uri,
       retrieval.source_generation AS parent_authority_generation,
       retrieval.source_sha256 AS parent_authority_sha256,
       retrieval.source_bytes AS parent_authority_bytes;

// query: parametric_suite_task_and_arm_coverage
MATCH (task:CorpusRetrievalEntity)
WHERE task.workstream_namespace = 'corpus-parametric-research'
  AND task.run_id = $batch_id
  AND task.kind = 'CorpusParametricTask'
OPTIONAL MATCH (task)-[has_arm:CORPUS_RELATION]->(arm:CorpusRetrievalEntity)
WHERE has_arm.relationship_type = 'HAS_PARAMETER_ARM'
  AND has_arm.task_index = task.task_index
  AND has_arm.slate_id = task.slate_id
  AND arm.kind = 'CorpusParametricArm'
  AND arm.task_index = task.task_index
  AND arm.slate_id = task.slate_id
RETURN count(DISTINCT task) AS loaded_task_count,
       count(DISTINCT arm) AS loaded_arm_count,
       collect(DISTINCT task.task_index) AS loaded_task_indexes,
       collect(DISTINCT task.slate_id) AS loaded_slate_ids;

// query: cross_slate_parameter_arm_effects
// Paired within slate against the incumbent; callers should require all 54
// task indexes before treating the aggregate as the complete suite.
MATCH (challenger:CorpusRetrievalEntity),
      (incumbent:CorpusRetrievalEntity)
WHERE challenger.workstream_namespace = 'corpus-parametric-research'
  AND challenger.run_id = $batch_id
  AND challenger.kind = 'CorpusScoreFreeMeasurement'
  AND challenger.analysis_scope = 'score-free-endpoint'
  AND challenger.metric_name = $metric_name
  AND challenger.parameter_set_id <> 'incumbent'
  AND incumbent.workstream_namespace = challenger.workstream_namespace
  AND incumbent.run_id = challenger.run_id
  AND incumbent.kind = challenger.kind
  AND incumbent.analysis_scope = challenger.analysis_scope
  AND incumbent.metric_name = challenger.metric_name
  AND incumbent.parameter_set_id = 'incumbent'
  AND incumbent.task_index = challenger.task_index
  AND incumbent.slate_id = challenger.slate_id
WITH challenger.parameter_set_id AS parameter_set_id,
     challenger.metric_value - incumbent.metric_value AS paired_delta,
     challenger.task_index AS task_index,
     challenger.slate_id AS slate_id
RETURN parameter_set_id,
       count(*) AS paired_slate_count,
       count(DISTINCT task_index) AS distinct_task_count,
       avg(paired_delta) AS mean_paired_delta,
       stDevP(paired_delta) AS population_sd_paired_delta,
       min(paired_delta) AS minimum_paired_delta,
       max(paired_delta) AS maximum_paired_delta,
       sum(CASE WHEN paired_delta > 0 THEN 1 ELSE 0 END) AS improved_slate_count,
       sum(CASE WHEN paired_delta = 0 THEN 1 ELSE 0 END) AS tied_slate_count,
       collect(CASE WHEN paired_delta < 0 THEN {
         task_index: task_index, slate_id: slate_id, delta: paired_delta
       } END) AS regressed_slates
ORDER BY mean_paired_delta DESC, parameter_set_id;

// query: cross_slate_arm_score_and_population_ranking
MATCH (measurement:CorpusRetrievalEntity)
WHERE measurement.workstream_namespace = 'corpus-parametric-research'
  AND measurement.run_id = $batch_id
  AND measurement.task_index_present = true
  AND measurement.kind IN [
    'CorpusScoreFreeMeasurement',
    'CorpusCoverageMeasurement',
    'CorpusRuleEffectMeasurement'
  ]
  AND measurement.metric_name IN $metric_names
  AND measurement.metric_value_present = true
RETURN measurement.parameter_set_id AS parameter_set_id,
       measurement.metric_name AS metric_name,
       count(*) AS slate_count,
       avg(measurement.metric_value) AS mean_value,
       stDevP(measurement.metric_value) AS population_sd,
       min(measurement.metric_value) AS minimum_value,
       max(measurement.metric_value) AS maximum_value,
       collect(DISTINCT measurement.task_index) AS task_indexes
ORDER BY metric_name, mean_value DESC, parameter_set_id;

// query: reserved_population_namespace_audit
MATCH (entity:CorpusRetrievalEntity)
WHERE entity.workstream_namespace = 'corpus-population-research'
RETURN count(entity) AS population_research_entity_count;
