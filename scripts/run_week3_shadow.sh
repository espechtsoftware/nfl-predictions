#!/usr/bin/env bash
# Run the Week-3 selection-only shadow once against an approved, completed live run.
# This wrapper is deliberately explicit and fail-closed: it does not choose a dose, read outcomes, or commit files.
# The Saturday D12800 entrypoint may enable it with RUN_WEEK3_SHADOW=1 after the shadow runner has been merged.
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROD=${PROD:-$(cd -- "$SCRIPT_DIR/.." && pwd)}
LAB_PY=${LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
CLONE=${CLONE:?CLONE must be exported to the pinned lab release}
EXPECT_SHA=${EXPECT_SHA:?EXPECT_SHA must be exported as the full pinned lab SHA}
CONTESTS_JSON=${CONTESTS_JSON:?CONTESTS_JSON must name the filled contest file}
SHADOW_RUNNER=${SHADOW_RUNNER:-$PROD/scripts/week3_shadow_runner.py}

usage() { echo "usage: $0 [--check] RUN_DIR SHADOW_OUT [live|rehearsal]"; }
CHECK=0
if [[ "${1:-}" == "--check" ]]; then CHECK=1; shift; fi
[[ $# -ge 2 && $# -le 3 ]] || { usage >&2; exit 2; }
RUN_DIR=$1; OUT_DIR=$2; LABEL=${3:-live}
[[ "$LABEL" == live || "$LABEL" == rehearsal ]] || { echo "invalid label: $LABEL" >&2; exit 2; }

fail() { echo "week3 shadow: $*" >&2; exit 2; }
[[ -x "$LAB_PY" ]] || fail "LAB_PY is not executable: $LAB_PY"
[[ -f "$SHADOW_RUNNER" ]] || fail "shadow runner missing: $SHADOW_RUNNER"
[[ -d "$CLONE" ]] || fail "lab clone missing: $CLONE"
[[ -f "$CONTESTS_JSON" ]] || fail "contests file missing: $CONTESTS_JSON"
[[ -d "$RUN_DIR" ]] || fail "run directory missing: $RUN_DIR"
[[ "$EXPECT_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "EXPECT_SHA must be a full 40-character SHA"
for f in frame.parquet candidates.parquet receipt.json book.json incumbent_player_scores.npy corrected_hsim_player_scores.npy; do
  [[ -f "$RUN_DIR/$f" ]] || fail "run is missing $f"
done
if grep -q 'REPLACE' "$CONTESTS_JSON"; then fail "contests file still contains a template marker"; fi
actual_sha=$(git -C "$CLONE" rev-parse HEAD 2>/dev/null) || fail "cannot read lab clone identity"
[[ "$actual_sha" == "$EXPECT_SHA" ]] || fail "lab clone $actual_sha != EXPECT_SHA $EXPECT_SHA"
[[ -z "$(git -C "$CLONE" status --porcelain)" ]] || fail "lab clone is dirty: $CLONE"

if ((CHECK)); then
  printf 'week3 shadow check ok: runner=%s clone=%s run=%s out=%s label=%s\n' \
    "$SHADOW_RUNNER" "$actual_sha" "$RUN_DIR" "$OUT_DIR" "$LABEL"
  exit 0
fi
[[ ! -e "$OUT_DIR" ]] || fail "shadow output already exists (refusing to overwrite): $OUT_DIR"
mkdir -p "$OUT_DIR"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$CLONE/src" "$LAB_PY" "$SHADOW_RUNNER" \
  --run "$RUN_DIR" --contests "$CONTESTS_JSON" --clone "$CLONE" --out "$OUT_DIR" --label "$LABEL"

hashes=$(
  "$LAB_PY" - "$OUT_DIR" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
def digest(name):
    return hashlib.sha256((root / name).read_bytes()).hexdigest()
receipt = {
    "schema": "week3-shadow-wrapper/v1",
    "label": json.loads((root / "manifest.json").read_text()).get("label"),
    "manifest_sha256": digest("manifest.json"),
    "books_sha256": digest("books.json"),
    "diagnostics_sha256": digest("diagnostics.json"),
}
(root / "wrapper-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, sort_keys=True))
PY
)
echo "week3 shadow complete: $hashes"
