# Foundry v7 LANE A environment — source tasks 0..27 on the incumbent
# reused job. All identities are copied from durable receipts, never
# retyped. Lane B (tasks 28..53) is foundry_v12b_env.sh on the second
# reused job; both lanes share the image, worktree, and service account.

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-cd5e64d
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260823-foundry-production-v12a/transport-live-v12a
export CORPUS_PARAMETRIC_JOB=atlas-minimal-c-s2023-w1-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=d6e4b8c1-5950-46b7-8869-7e34dbf29ad2
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_BUILD_ID=27177530-ee69-4bd8-b45d-503e1a61c920
export CORPUS_PARAMETRIC_CODE_SHA=cd5e64d42d35d7b36c61b80896a2a3df8c9ced0b
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v12a/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

# Appended by append_foundry_lane_identities.py --lane a after the
# foundation execute, and the contract block after configure.






# Appended from execute-result.json + build-metadata.json by
# append_foundry_lane_identities.py --lane a — never edit by hand.
export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:b1ca2abcbe9dfcb4d9b403fe1c73ca95728ede29570a64cd5488a0f39efab536
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v12a/governance/publication-completion.json'
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION=1787516652644650
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256=c4133e8590894517834b52d8d111d3ebd7819de4063b35bb026df7128455c5db
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7597
export CORPUS_PARAMETRIC_MANIFEST_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12a/governance/batch-manifest.json'
export CORPUS_PARAMETRIC_MANIFEST_GENERATION=1787516651848534
export CORPUS_PARAMETRIC_MANIFEST_SHA256=cdcdc77b66ad01e77e97419ba596cd87d65eba1f3b3b36313c6af89d388f9aa3
export CORPUS_PARAMETRIC_MANIFEST_BYTES=68958
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12a/governance/pre-run-evidence-contract.json'
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION=1787516652337348
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256=bdc707bf302d648eca209f8e2803b18685bb4f7e7ecd979e408585cc1c667f28
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=45205
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v12a/governance/retrieval-task0-accepted-prerequisite.json'
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION=1787516646691047
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256=21fffef58432017eb25cdad5e08f7a2b6d2bfa8702b5eb6afbe56e01965ad07d
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925

# Transport contract identity — copied from configured.json.
export CORPUS_PARAMETRIC_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12a/governance/parametric-transport-contract.json'
export CORPUS_PARAMETRIC_CONTRACT_GENERATION=1787518866025476
export CORPUS_PARAMETRIC_CONTRACT_SHA256=c3bac0b6a6aab67bfa6074e4271a413db9b4ee76f629dbe22185b259a23b79fa
export CORPUS_PARAMETRIC_CONTRACT_BYTES=98849
