# Foundry v6 production environment — source this (bash, non-TTY) before
# configure / driver steps. All identities are copied from durable receipts,
# never retyped. Pending identities are filled in AFTER the publication
# steps produce their receipts; sourcing this file fails closed (set -u in
# the consumers) until they are appended.
#
# ORDER:
#   1. Build metadata capture (after build 588a2b97 SUCCESS):
#      gcloud builds describe 588a2b97-5e2b-4663-a1c1-65b5039a4588 \
#        --project nfl-predictions-503414 --format=json \
#        > reports/corpus-parametric-runs/20260822-foundry-production-v6/governance-live-v6/build-metadata.json
#   2. python scripts/foundry/build_foundry_v6_preplan.py   (py311 worktree)
#      then validate + dry-run + execute --execute via
#      scripts/prepare_corpus_parametric_batch_v1.py from the worktree.
#      Append CORPUS_PARAMETRIC_{FOUNDATION_PUBLICATION,MANIFEST,
#      EVIDENCE_CONTRACT,RETRIEVAL_PREREQUISITE}_* from execute-result.json.
#   3. bash scripts/foundry/foundry_v6_iam_move.sh            # inspect diff
#      bash scripts/foundry/foundry_v6_iam_move.sh --execute  # apply
#   4. Capture fresh runtime IAM policy to $CORPUS_PARAMETRIC_RUNTIME_IAM_FILE
#      (canonicalize via the transport's canonicalize-external-json +
#      build-runtime-iam-evidence flow, against the v6 prefixes).
#   5. cd "$CORPUS_PARAMETRIC_SOURCE" && \
#      bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute configure
#   6. Export CORPUS_PARAMETRIC_CONTRACT_{URI,GENERATION,SHA256,BYTES} from
#      the configure output, then:
#      bash scripts/foundry/foundry_batch_driver.sh 0 0   # task-0
#      python scripts/foundry/accept_foundry_task0.py ... # independent gate
#      bash scripts/foundry/foundry_batch_driver.sh 1 53  # fan-out

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-bcf31a7
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260822-foundry-production-v6/transport-live-v6
export CORPUS_PARAMETRIC_JOB=atlas-minimal-c-s2023-w1-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=d6e4b8c1-5950-46b7-8869-7e34dbf29ad2
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_BUILD_ID=588a2b97-5e2b-4663-a1c1-65b5039a4588
export CORPUS_PARAMETRIC_CODE_SHA=bcf31a75087a48d7207389fe6a69bf9244f73aeb
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v6/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v6/build-metadata.json"

# CORPUS_PARAMETRIC_IMAGE — append after build SUCCESS, copied from
# build-metadata.json results.images[0].digest:
#   export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:<digest>

# Publication identities — append from
# reports/corpus-parametric-runs/20260822-foundry-production-v6/foundation-live/execute-result.json
# after the execute step (uri/generation/sha256/bytes for each):
#   CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_*
#   CORPUS_PARAMETRIC_MANIFEST_*
#   CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_*
#   CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_*
