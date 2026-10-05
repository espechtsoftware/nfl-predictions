#!/usr/bin/env bash
# Run the Cloud Build live lane's tests locally in a CLEAN context, the way the build sees them: only the paths
# build_week1_live_image.sh copies, no GCP_PROJECT, an empty HOME, no .env. Twice on 2026-10-04 the lane failed in
# Cloud Build on tests that passed in the checkout (host files, config defaults, reports/ not copied); run this before
# any live image build or after adding a module to cloudbuild.week1-live.yaml.
#   scripts/live_lane_local.sh [python]      # default: the checkout's .venv python
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
py="${1:-$root/.venv/bin/python}"
[[ -x "$py" ]] || { echo "live_lane_local: no python at $py (pass one)" >&2; exit 2; }
paths=$(sed -n '/^for path in \\/,/; do$/p' "$root/scripts/build_week1_live_image.sh" | sed -e 's/^for path in//' -e 's/; do$//' | tr -d '\\' | xargs)
[[ -n "$paths" ]] || { echo "live_lane_local: could not read the copy list from build_week1_live_image.sh" >&2; exit 2; }
ctx="$(mktemp -d)"; trap 'rm -rf -- "$ctx"' EXIT
for p in $paths; do cp -a "$root/$p" "$ctx/$p"; done
mkdir -p "$ctx/.home"
tests=$("$py" -c "
import re,sys,yaml
y=yaml.safe_load(open(sys.argv[1]))
s=' '.join(' '.join(st.get('args',[])) for st in y['steps'][:1])
print(' '.join(sorted(set(re.findall(r'tests/[\w/]+\.py', s)))))" "$root/cloudbuild.week1-live.yaml")
[[ -n "$tests" ]] || { echo "live_lane_local: no lane tests found in cloudbuild.week1-live.yaml" >&2; exit 2; }
echo "live_lane_local: $(wc -w <<<"$tests") modules from cloudbuild.week1-live.yaml; context: $paths"
cd "$ctx" && env -i PATH=/usr/bin:/bin HOME="$ctx/.home" PYTHONPATH=src "$py" -m pytest $tests -p no:cacheprovider
