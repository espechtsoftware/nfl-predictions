# Foundry v6 production environment — source this (bash, non-TTY) before
# configure / driver steps. All identities are copied from durable receipts,
# never retyped. Pending identities are filled in AFTER the publication
# steps produce their receipts; sourcing this file fails closed (set -u in
# the consumers) until they are appended.
#
# ORDER:
#   1. Build metadata capture (after build b0bfb7b6 SUCCESS):
#      gcloud builds describe b0bfb7b6-cfb4-4016-8e20-9ebee67b5857 \
#        --project nfl-predictions-503414 --format=json \
#        > reports/corpus-parametric-runs/20260822-foundry-production-v6/governance-live-v6/build-metadata.json
#      (Build 588a2b97 FAILED and is superseded: it was submitted with the
#      MAIN cloudbuild.yaml full suite, whose python:3.11-slim step lacks
#      jq, so two operator-shell tests fail there. The corpus chain builds
#      with the dedicated cloudbuild.corpus-research-expansion.yaml — the
#      config the preplan's build_definition_sha256 pins — which installs
#      jq and runs the complete corpus workstream suites.)
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
export CORPUS_PARAMETRIC_BUILD_ID=b0bfb7b6-cfb4-4016-8e20-9ebee67b5857
export CORPUS_PARAMETRIC_CODE_SHA=bcf31a75087a48d7207389fe6a69bf9244f73aeb
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v6/runtime-iam-policy-capture.json"
# Configure CREATES this evidence file itself (create-once); it must not
# collide with the pre-captured governance-live-v6/build-metadata.json
# that fed the preplan builder.
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

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

# Appended from execute-result.json + build-metadata.json by
# append_foundry_v6_identities.py — never edit by hand.
export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:0b69704a88a8c757ec742e063e4b45ffd61984ba14ccee3747aee579738084c2
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260822-corpus-parametric-production-foundation-v6/governance/publication-completion.json'
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION=1787443651199879
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256=c60aad15ace851119f3021bd5a14c636edacc00c2810634beb23c01a18f48809
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7560
export CORPUS_PARAMETRIC_MANIFEST_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-production-batch-v6/governance/batch-manifest.json'
export CORPUS_PARAMETRIC_MANIFEST_GENERATION=1787443650334040
export CORPUS_PARAMETRIC_MANIFEST_SHA256=3bdcf2eed9a8d2b3198c4209f464f252cf5692600ebd6a1c49423ad2bde15eb9
export CORPUS_PARAMETRIC_MANIFEST_BYTES=122970
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-production-batch-v6/governance/pre-run-evidence-contract.json'
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION=1787443650866249
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256=f96798997038de1fc86d072a04ab4fbfea2f180306a38a3c6bc9ae27e38fd996
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=51640
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260822-corpus-parametric-production-foundation-v6/governance/retrieval-task0-accepted-prerequisite.json'
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION=1787443645268611
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256=68c3b92a335f68de6aa8fed7e351279744bafa178960ec3986b3c6cb4d9e086b
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925

# Transport contract identity — copied from configured.json by the operator.
export CORPUS_PARAMETRIC_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-production-batch-v6/governance/parametric-transport-contract.json'
export CORPUS_PARAMETRIC_CONTRACT_GENERATION=1787444784745289
export CORPUS_PARAMETRIC_CONTRACT_SHA256=92347761cf7c1062807f205285676e571cc18b72be506282b358a5702dd82541
export CORPUS_PARAMETRIC_CONTRACT_BYTES=185386
