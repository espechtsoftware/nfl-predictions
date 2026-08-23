# Foundry v7 LANE A environment — source tasks 0..27 on the incumbent
# reused job. All identities are copied from durable receipts, never
# retyped. Lane B (tasks 28..53) is foundry_v8b_env.sh on the second
# reused job; both lanes share the image, worktree, and service account.

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_SOURCE=/tmp/nfl-predictions-corpus-9be4a07
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_PARAMETRIC_SOURCE/src"
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260823-foundry-production-v8a/transport-live-v8a
export CORPUS_PARAMETRIC_JOB=atlas-minimal-c-s2023-w1-v1
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID=d6e4b8c1-5950-46b7-8869-7e34dbf29ad2
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT=corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com
export CORPUS_PARAMETRIC_BUILD_ID=6af6927f-88dd-4c96-92dd-8a59a7d09fa0
export CORPUS_PARAMETRIC_CODE_SHA=9be4a07f9f3b9640f7d35a60fb2903c5dfc18ce3
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$CORPUS_PARAMETRIC_RUN_DIR/../governance-live-v8a/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$CORPUS_PARAMETRIC_RUN_DIR/build-metadata.json"

# Appended by append_foundry_lane_identities.py --lane a after the
# foundation execute, and the contract block after configure.


# Appended from execute-result.json + build-metadata.json by
# append_foundry_lane_identities.py --lane a — never edit by hand.
export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:0bb76bf06473214cdc8496e707892548680ed5313f6fab945778a51fe856917d
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v8a/governance/publication-completion.json'
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION=1787471596823375
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256=a056590540bbf290926c3d01b06fdbe40ab04939909042eba98f199b4208d0d5
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7578
export CORPUS_PARAMETRIC_MANIFEST_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v8a/governance/batch-manifest.json'
export CORPUS_PARAMETRIC_MANIFEST_GENERATION=1787471596071104
export CORPUS_PARAMETRIC_MANIFEST_SHA256=90f19ae25a9ae172ccc50ed469ef0b34d4e6cf1de2474b6c02d7c3f80a179839
export CORPUS_PARAMETRIC_MANIFEST_BYTES=68886
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v8a/governance/pre-run-evidence-contract.json'
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION=1787471596514688
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256=6bba808f7d6ab89e98a5435700a9947b7ea3159412cdbb3575a56d65fe3a8086
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=45200
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v8a/governance/retrieval-task0-accepted-prerequisite.json'
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION=1787471591863254
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256=5025c258bf211c832d59d9ca1d0dd504a6e885c3e8ee1aebd55ac800198d1810
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925
