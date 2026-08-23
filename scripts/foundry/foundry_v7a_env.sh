# Foundry v7 LANE A environment — source tasks 0..27 on the incumbent
# reused job. All identities are copied from durable receipts, never
# retyped. Lane B (tasks 28..53) is foundry_v7b_env.sh on the second
# reused job; both lanes share the image, worktree, and service account.

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-2aba4ae
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260823-foundry-production-v7a/transport-live-v7a
export CORPUS_PARAMETRIC_JOB=atlas-minimal-c-s2023-w1-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=d6e4b8c1-5950-46b7-8869-7e34dbf29ad2
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_BUILD_ID=b75297ee-f161-4c10-ba2d-5333efb0bde4
export CORPUS_PARAMETRIC_CODE_SHA=2aba4aefdc98b71e874195c85944c72f4b707c58
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v7a/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

# Appended by append_foundry_lane_identities.py --lane a after the
# foundation execute, and the contract block after configure.
