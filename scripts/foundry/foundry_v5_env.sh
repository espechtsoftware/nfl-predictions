# Foundry v5 production environment — source this (bash, non-TTY) before
# configure / driver steps. All identities are copied from durable receipts,
# never retyped.
#
# ORDER (after the v4 chain is FULLY closed — producer closed, verifier
# accepted, batch finished):
#   1. bash ~/nfl-panels/foundry_v5_iam_move.sh            # inspect diff
#      bash ~/nfl-panels/foundry_v5_iam_move.sh --execute  # apply
#   2. Capture fresh runtime IAM policy to $CORPUS_PARAMETRIC_RUNTIME_IAM_FILE
#      (canonicalize via the transport's canonicalize-external-json +
#      build-runtime-iam-evidence flow used for v4, against the v5 prefixes).
#   3. cd "$CORPUS_PARAMETRIC_SOURCE" && \
#      bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute configure
#   4. Export CORPUS_PARAMETRIC_CONTRACT_{URI,GENERATION,SHA256,BYTES} from
#      the configure output (transport contract identity), then run
#      ~/nfl-panels/foundry_batch_driver.sh 0 0     # task-0 equivalence gate
#      -> compare accepted task-0 science vs accepted v4 (comparator TBD
#         against the real v4 artifact) ->
#      ~/nfl-panels/foundry_batch_driver.sh 1 53

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-04d6579
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260822-foundry-production-v5/transport-live-v5
export CORPUS_PARAMETRIC_JOB=atlas-minimal-c-s2023-w1-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=d6e4b8c1-5950-46b7-8869-7e34dbf29ad2
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:232c1087471f91a62e1f3a7d7036e7a344dab1c826eedc004cb027d86a2cdadd
export CORPUS_PARAMETRIC_BUILD_ID=b2832a18-666d-4260-9d4b-619ad94aa5ae
export CORPUS_PARAMETRIC_CODE_SHA=04d6579394af70df7120e81c0196837d29b5ffcf
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v5/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260822-corpus-parametric-production-foundation-v5/governance/publication-completion.json'
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION=1787418113444767
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256=c4314f30316ef62e7e7ec8822b11c7c4c000652ba2d76aabc78acf751420ece2
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7560

export CORPUS_PARAMETRIC_MANIFEST_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-production-batch-v5/governance/batch-manifest.json'
export CORPUS_PARAMETRIC_MANIFEST_GENERATION=1787418112515448
export CORPUS_PARAMETRIC_MANIFEST_SHA256=7f0a21674df18d238e815e293f89d7c88b94a953895e22353139d8f5f53b2b31
export CORPUS_PARAMETRIC_MANIFEST_BYTES=122970

export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-production-batch-v5/governance/pre-run-evidence-contract.json'
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION=1787418113085346
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256=67cbbba555576c695f211ab1c0d5c45e653eb1a6187749622706c142a0273e35
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=51640

export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260822-corpus-parametric-production-foundation-v5/governance/retrieval-task0-accepted-prerequisite.json'
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION=1787418106867770
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256=5f5a8214d1c243343905ff5695728d41555e8fe2de1c5b0737f50f8cf5c1b03f
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925
