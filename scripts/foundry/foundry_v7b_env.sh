# Foundry v7 LANE B environment — source tasks 28..53 on the second
# reused job. All identities are copied from durable receipts, never
# retyped. Lane A (tasks 0..27) is foundry_v7a_env.sh on the incumbent
# reused job; both lanes share the image, worktree, and service account.

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-2aba4ae
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260823-foundry-production-v7b/transport-live-v7b
export CORPUS_PARAMETRIC_JOB=atlas-cbc-32g-full-2023-w8-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_BUILD_ID=b75297ee-f161-4c10-ba2d-5333efb0bde4
export CORPUS_PARAMETRIC_CODE_SHA=2aba4aefdc98b71e874195c85944c72f4b707c58
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v7b/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

# Appended by append_foundry_lane_identities.py --lane b after the
# foundation execute, and the contract block after configure.
