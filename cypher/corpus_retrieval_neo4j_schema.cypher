// Dedicated analytical projection only. Canonical GCS evidence stays authoritative.
CREATE CONSTRAINT corpus_retrieval_entity_id IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) REQUIRE n.id IS UNIQUE;

CREATE INDEX corpus_retrieval_entity_kind IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.kind);

CREATE INDEX corpus_retrieval_entity_logical_id IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.logical_id);

CREATE INDEX corpus_retrieval_entity_run_id IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.run_id);

CREATE INDEX corpus_retrieval_entity_task_id IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.task_id);

CREATE INDEX corpus_retrieval_entity_task_index IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.task_index);

CREATE INDEX corpus_retrieval_entity_slate_id IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.slate_id);

CREATE INDEX corpus_retrieval_entity_payload_sha256 IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.payload_sha256);

CREATE INDEX corpus_retrieval_entity_namespace IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.workstream_namespace);

CREATE INDEX corpus_retrieval_entity_parameter_set IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.parameter_set_id);

CREATE INDEX corpus_retrieval_entity_strategy IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.strategy_id);

CREATE INDEX corpus_retrieval_entity_metric IF NOT EXISTS
FOR (n:CorpusRetrievalEntity) ON (n.metric_name);

CREATE INDEX corpus_retrieval_relation_key IF NOT EXISTS
FOR ()-[r:CORPUS_RELATION]-() ON (r.edge_key);

CREATE INDEX corpus_retrieval_relation_type IF NOT EXISTS
FOR ()-[r:CORPUS_RELATION]-() ON (r.relationship_type);
