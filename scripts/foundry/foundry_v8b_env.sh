# Foundry v7 LANE B environment — source tasks 28..53 on the second
# reused job. All identities are copied from durable receipts, never
# retyped. Lane A (tasks 0..27) is foundry_v8a_env.sh on the incumbent
# reused job; both lanes share the image, worktree, and service account.

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-9be4a07
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260823-foundry-production-v8b/transport-live-v8b
export CORPUS_PARAMETRIC_JOB=atlas-cbc-32g-full-2023-w8-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research-b@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_BUILD_ID=6af6927f-88dd-4c96-92dd-8a59a7d09fa0
export CORPUS_PARAMETRIC_CODE_SHA=9be4a07f9f3b9640f7d35a60fb2903c5dfc18ce3
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v8b/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

# Appended by append_foundry_lane_identities.py --lane b after the
# foundation execute, and the contract block after configure.

# Appended from execute-result.json + build-metadata.json by
# append_foundry_lane_identities.py --lane b — never edit by hand.
export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:c6692f0b28e8ad9bcab4da47906148c248e098899efc9b0bc3f153dca0050ed0
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v8b/governance/publication-completion.json'
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION=1787461243872040
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256=75f3508e5b5fbedef379a1b18ee0290545fbb1f979dda12a64019bf3e7fa5db6
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7578
export CORPUS_PARAMETRIC_MANIFEST_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v8b/governance/batch-manifest.json'
export CORPUS_PARAMETRIC_MANIFEST_GENERATION=1787461243027405
export CORPUS_PARAMETRIC_MANIFEST_SHA256=0666d564dff1151888128b0fface9efa3a77511113859563bc5ca5e33a63f092
export CORPUS_PARAMETRIC_MANIFEST_BYTES=64766
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v8b/governance/pre-run-evidence-contract.json'
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION=1787461243465629
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256=a5b1f10c23168a25637b8b50e1d164ff995dd170a2f18b5249bf0648bb2ef63c
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=44713
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v8b/governance/retrieval-task0-accepted-prerequisite.json'
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION=1787461238443010
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256=d8a4710523a57e08f359adacbd1e8ee77e60eafe36f96dda70878316417d7d2e
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925
