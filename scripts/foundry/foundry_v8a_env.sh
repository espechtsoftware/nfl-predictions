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
export CORPUS_PARAMETRIC_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:c6692f0b28e8ad9bcab4da47906148c248e098899efc9b0bc3f153dca0050ed0
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v8a/governance/publication-completion.json'
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION=1787459934224000
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256=5f71c0c7ecf479d09052757890e7654ed52d77f00be050c56453d365c7f3611e
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7578
export CORPUS_PARAMETRIC_MANIFEST_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v8a/governance/batch-manifest.json'
export CORPUS_PARAMETRIC_MANIFEST_GENERATION=1787459933502940
export CORPUS_PARAMETRIC_MANIFEST_SHA256=58f881c142e9ae9109cbe96beba2aa4cdf2207808817a472ef484d470e858db8
export CORPUS_PARAMETRIC_MANIFEST_BYTES=68886
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v8a/governance/pre-run-evidence-contract.json'
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION=1787459933926544
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256=d1aef6b17d2cbaa629031cd08c7c1902aa10117a4fe1644e15807061009feecb
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=45200
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v8a/governance/retrieval-task0-accepted-prerequisite.json'
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION=1787459929253260
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256=630cad7b327969829bebd026af8c170d4335eb72777e5fdfae34093bd52b7778
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925
