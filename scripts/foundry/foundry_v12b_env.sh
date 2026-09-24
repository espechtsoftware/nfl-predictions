# Foundry v7 LANE B environment — source tasks 28..53 on the second
# reused job. All identities are copied from durable receipts, never
# retyped. Lane A (tasks 0..27) is foundry_v12a_env.sh on the incumbent
# reused job; both lanes share the image, worktree, and service account.

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-cd5e64d
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260823-foundry-production-v12b/transport-live-v12b
export CORPUS_PARAMETRIC_JOB=atlas-cbc-32g-full-2023-w8-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research-b@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_BUILD_ID=27177530-ee69-4bd8-b45d-503e1a61c920
export CORPUS_PARAMETRIC_CODE_SHA=cd5e64d42d35d7b36c61b80896a2a3df8c9ced0b
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v12b/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

# Appended by append_foundry_lane_identities.py --lane b after the
# foundation execute, and the contract block after configure.





# Appended from execute-result.json + build-metadata.json by
# append_foundry_lane_identities.py --lane b — never edit by hand.
export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:b1ca2abcbe9dfcb4d9b403fe1c73ca95728ede29570a64cd5488a0f39efab536
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v12b/governance/publication-completion.json'
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION=1787517979158001
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256=f56d6dd7bc51c7562036995d13b9d4ee7d55768e66bed84c7a87487abb910bd6
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7597
export CORPUS_PARAMETRIC_MANIFEST_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12b/governance/batch-manifest.json'
export CORPUS_PARAMETRIC_MANIFEST_GENERATION=1787517978301938
export CORPUS_PARAMETRIC_MANIFEST_SHA256=90d60d62e5045c1a5b82486d4ee2bddaa24200f8ee0ce4c26a3dea7a51d17b92
export CORPUS_PARAMETRIC_MANIFEST_BYTES=64834
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12b/governance/pre-run-evidence-contract.json'
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION=1787517978822295
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256=0483a827bff7300cc12a191cc9457cf904ff5aa24ab3539a050420cdef1ab29e
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=44718
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v12b/governance/retrieval-task0-accepted-prerequisite.json'
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION=1787517973643851
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256=d4df252f3ab0cc6d641e570b2b212127f32271b83590884a50116984b3f5c775
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925

# Transport contract identity — copied from configured.json.
export CORPUS_PARAMETRIC_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12b/governance/parametric-transport-contract.json'
export CORPUS_PARAMETRIC_CONTRACT_GENERATION=1787520548956269
export CORPUS_PARAMETRIC_CONTRACT_SHA256=0a8159f7ad4d3aa6e3281861fc7608dc175152e300065e630d8c41c496bb6b66
export CORPUS_PARAMETRIC_CONTRACT_BYTES=92077
