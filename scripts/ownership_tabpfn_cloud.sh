#!/usr/bin/env bash
# The Week-5 cloud path of the TabPFN ownership fit: the laptop-built features go to the private bucket, the existing
# tabpfn-gen job runs its `ownership` mode (scripts/tabpfn_gen/own_cloud.py; per-execution --args, no new job), and the
# pred_own csv comes back with its receipt. Drop-in for the local `ownership_tabpfn.py fit` step:
#
#   scripts/ownership_tabpfn_cloud.sh <features.parquet> <out.csv> <run tag>
#
# Content identity end to end: the features' sha256 is passed to the job and must come back in the receipt; the csv's
# sha256 must equal the receipt's; the ownership_tabpfn.py baked into the image must equal this checkout's (a code skew
# refuses unless OWN_TABPFN_IMAGE_SKEW_OK=<the image's sha256>, conscious and exact). Outputs are create-only under a
# per-run prefix. Any failure prints "OWNERSHIP TABPFN REFUSED: ..." and exits 2 -- the chain then keeps the blend,
# loudly. A nonzero or ambiguous `gcloud run jobs execute` is reported with the execution name if one exists and is
# NEVER retried here (CLAUDE.md rule 6: reconcile against the provider first). When armed from a host queue, run this
# under `scripts/launcher_registry.sh run --lane tabpfn-gen`.
set -uo pipefail
refuse() { echo "OWNERSHIP TABPFN REFUSED: $*" >&2; exit 2; }
FEATS=${1:?features.parquet}; OUT=${2:?out.csv}; TAG=${3:?run tag}
[[ "$TAG" =~ ^[A-Za-z0-9._-]+$ ]] || refuse "run tag '$TAG' must be [A-Za-z0-9._-]+"
[[ -s "$FEATS" ]] || refuse "features file $FEATS is missing or empty"
[[ "$OUT" == *.csv ]] || refuse "out $OUT must be a .csv"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT=${GCP_PROJECT:-nfl-predictions-503414}; REGION=${OWN_TABPFN_REGION:-us-central1}; JOB=${OWN_TABPFN_JOB:-tabpfn-gen}
PRIV=${OWN_TABPFN_PRIVATE:-gs://nfl-predictions-503414-raw/private}
ROWS=${OWN_TABPFN_ROWS_URI:-$PRIV/l23/rows.parquet}
ROWS26=${OWN_TABPFN_ROWS_2026_URI:-$PRIV/l23/rows_2026_w1w3.parquet}
DEST=$PRIV/own-tabpfn/$TAG
GCLOUD=${GCLOUD:-gcloud}
FSHA=$(sha256sum "$FEATS" | cut -d' ' -f1)
"$GCLOUD" storage cp --no-clobber "$FEATS" "$DEST/features.parquet" >&2 || refuse "cannot upload the features to $DEST"
GOT=$("$GCLOUD" storage cat "$DEST/features.parquet" | sha256sum | cut -d' ' -f1)
[[ "$GOT" == "$FSHA" ]] || refuse "$DEST/features.parquet holds other bytes ($GOT != $FSHA): a stale run tag?"
ARGS="python,/app/own_cloud.py,--rows,$ROWS,--rows-2026,$ROWS26,--features,$DEST/features.parquet,--features-sha256,$FSHA,--out,$DEST/ownership_tabpfn.csv"
EXEC=$(timeout "${OWN_TABPFN_CLOUD_TIMEOUT:-1200}" "$GCLOUD" run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
        --update-env-vars TABPFN_DISABLE_TELEMETRY=1 --args="$ARGS" --wait --format='value(metadata.name)')
RC=$?
(( RC == 0 )) || refuse "gcloud run jobs execute $JOB returned $RC (execution: ${EXEC:-unknown}); not retried -- reconcile with 'gcloud run jobs executions describe'"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
"$GCLOUD" storage cp "$DEST/ownership_tabpfn.csv" "$TMP/o.csv" >&2 || refuse "no csv at $DEST (execution $EXEC)"
"$GCLOUD" storage cp "$DEST/ownership_tabpfn.csv.receipt.json" "$TMP/o.csv.receipt.json" >&2 || refuse "no receipt at $DEST (execution $EXEC)"
python3 - "$TMP/o.csv" "$TMP/o.csv.receipt.json" "$FSHA" "$HERE/ownership_tabpfn.py" "${OWN_TABPFN_IMAGE_SKEW_OK:-}" "$EXEC" <<'PY' || exit 2
import hashlib, json, sys
csv, rec, fsha, local_ot, skew_ok, execution = sys.argv[1:7]
r = json.load(open(rec)); c = r.get("cloud") or {}
def refuse(why):
    print(f"OWNERSHIP TABPFN REFUSED: {why}", file=sys.stderr); sys.exit(2)
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
if (c.get("inputs", {}).get("features") or {}).get("sha256") != fsha:
    refuse("the receipt's features sha256 is not the one uploaded")
if (c.get("csv") or {}).get("sha256") != h(csv):
    refuse("the downloaded csv's sha256 differs from the receipt's")
img, loc = c.get("image_ownership_tabpfn_sha256"), h(local_ot)
if img != loc and skew_ok != img:
    refuse(f"the image's ownership_tabpfn.py ({str(img)[:12]}…) differs from this checkout's ({loc[:12]}…); rebuild the image "
           f"or set OWN_TABPFN_IMAGE_SKEW_OK={img}")
if execution and c.get("execution") and c["execution"] != execution:
    refuse(f"the receipt names execution {c['execution']}, gcloud returned {execution}")
print(f"cloud ownership fit ok: execution {execution}, {r.get('secs')} s on {r.get('gpu')}, pred_own sum {(r.get('predictions') or {}).get('sum')}")
PY
mkdir -p "$(dirname "$OUT")"
cp "$TMP/o.csv" "$OUT" && cp "$TMP/o.csv.receipt.json" "$OUT.receipt.json" || refuse "cannot write $OUT"
echo "wrote $OUT (+ receipt) from $DEST"
