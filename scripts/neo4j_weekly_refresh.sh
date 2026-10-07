#!/usr/bin/env bash
# The weekly Milly-graph refresh (the operator 10-07: "let's make sure each week we keep the enhanced neo4j data populated
# and learn from it"). Run on MONDAY after settlement, once week N is in ~/moneygate/weeks.json (its T-70 run archived):
#   1. start the local Neo4j (never during a build window: the Saturday arm refuses while it runs);
#   2. load the week's Millionaire lineups -- the top set plus every lineup of the users in the PRIVATE users file -- with
#      FP projection / ownership (--include-fp; the graph is local only);
#   3. load the week's pre-lock player / team / game / lineup facts (--with-facts --facts-only; needs the T-70 frame);
#   4. run the standing learning queries (scripts/graph_weekly/: the outside reviewer's within-portfolio facts, the
#      sub-$4k count check, the cheap-tier boom check and the by-tier picks-vs-field edges), writing their AGGREGATE outputs under ~/private/neo4j/weekly/<season>-w<NN>/ for the weekly record;
#   5. stop Neo4j if THIS refresh started it, on every exit (unless --keep-running); an instance already running (another
#      session's) is left as found and must be stopped before Saturday's arming. Refuses to run under xtrace.
# Credentials come from ~/.config/neo4j-local-milly.txt (sourced, never printed). Nothing is written to the repository.
#   bash scripts/neo4j_weekly_refresh.sh <week> <private users file> [--keep-running]
set -uo pipefail
WEEK=${1:?week}; USERS=${2:?private users file (one DraftKings name per line)}; KEEP=${3:-}
SEASON=${SEASON:-2026}; P=$(cd "$(dirname "$0")/.." && pwd); PY=${MILLY_PY:-$HOME/.local/share/milly-analytics/.venv/bin/python}
OUTD=$HOME/private/neo4j/weekly/$SEASON-w$(printf %02d "$WEEK"); mkdir -p "$OUTD"
say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*"; }
stop() { say "NEO4J WEEKLY STOPPED: $*"; exit 1; }
[[ -s "$USERS" ]] || stop "the users file $USERS is missing"
python3 - "$WEEK" <<'EOF' || stop "week $WEEK has no t70_run in ~/moneygate/weeks.json (add it at settlement first: the facts need the T-70 frame)"
import json, sys
from pathlib import Path
w = json.loads((Path.home() / "moneygate/weeks.json").read_text())["weeks"].get(sys.argv[1], {})
sys.exit(0 if w.get("t70_run") and (Path(w["t70_run"]) / "frame.parquet").is_file() else 1)
EOF
case $- in *x*) stop "refusing xtrace: the credentials would print";; esac
set -a; . "$HOME/.config/neo4j-local-milly.txt"; set +a
export MILLY_NEO4J_URI=$NEO4J_URI MILLY_NEO4J_USERNAME=$NEO4J_USER MILLY_NEO4J_PASSWORD=$NEO4J_PASSWORD MILLY_NEO4J_DATABASE=neo4j GCP_PROJECT=${GCP_PROJECT:-nfl-predictions-503414}
# stop only an instance THIS script started (the outside reviewer queries the same local graph), on every exit -- a failed
# load must not leave it running into Saturday's arming (the reviewer 10-07)
STARTED=0
if ! neo4j-milly status >/dev/null 2>&1; then
  say "starting Neo4j"; neo4j-milly start > "$OUTD/neo4j-start.txt" 2>&1 || stop "neo4j-milly start failed"; STARTED=1
  [[ "$KEEP" != --keep-running ]] && trap 'neo4j-milly stop > "$OUTD/neo4j-stop.txt" 2>&1; say "Neo4j stopped (this refresh started it)"' EXIT
fi
HP=${NEO4J_URI#*://}; HP=${HP%%/*}; BOLT_HOST=${HP%:*}; BOLT_PORT=${HP##*:}   # the bolt address from the credentials file (never printed)
for i in $(seq 1 30); do (echo > "/dev/tcp/$BOLT_HOST/$BOLT_PORT") 2>/dev/null && break; sleep 2; done
LOAD=(--season "$SEASON" --week "$WEEK" --users-file "$USERS" --include-fp --node-limit 5000000 --rel-limit 20000000)
say "pass 1: the week's lineups"
( cd "$P" && PYTHONPATH="$P/src" timeout 3000 "$PY" scripts/load_milly_neo4j.py "${LOAD[@]}" --apply ) > "$OUTD/load-lineups.txt" 2>&1 || stop "the lineup load failed (see $OUTD/load-lineups.txt)"
grep -v -i warn "$OUTD/load-lineups.txt" | tail -3
say "pass 2: the week's pre-lock facts"
( cd "$P" && PYTHONPATH="$P/src" timeout 3000 "$PY" scripts/load_milly_neo4j.py "${LOAD[@]}" --with-facts --facts-only --apply ) > "$OUTD/load-facts.txt" 2>&1 || stop "the facts load failed (see $OUTD/load-facts.txt)"
grep -E "FACTS|facts loaded" "$OUTD/load-facts.txt" | tail -4
G=$P/scripts/graph_weekly                   # the outside reviewer's standing queries (copied 10-07 from abb4db74; aggregates only)
# every query runs FROM the private output dir (cheap_tier.py writes to its working directory; each finds gconn.py through
# its own folder on sys.path), so nothing lands in the repository
say "learning 1: within-portfolio pre-lock facts (the regulars' top-1% lineups vs their other lineups, every loaded week)"
( cd "$OUTD" && timeout 1800 "$PY" "$G/within_portfolio.py" "$OUTD" ) > "$OUTD/within_portfolio.txt" 2>&1 || say "WARN: within_portfolio.py failed (see $OUTD)"
tail -15 "$OUTD/within_portfolio.txt"
say "learning 2: sub-\$4,000 players in the field, our pool and our books (study list 51)"
( cd "$OUTD" && timeout 1800 "$PY" "$G/cheap_count_check.py" "$OUTD" ) > "$OUTD/cheap_count.txt" 2>&1 || say "WARN: cheap_count_check.py failed (see $OUTD)"
tail -12 "$OUTD/cheap_count.txt"
say "learning 3: which sub-\$4,000 players boom, and do the regulars pick better ones"
( cd "$OUTD" && timeout 1800 "$PY" "$G/cheap_tier.py" ) > "$OUTD/cheap_tier.txt" 2>&1 || say "WARN: cheap_tier.py failed (see $OUTD)"
tail -12 "$OUTD/cheap_tier.txt"
say "learning 4: where our picks gained or lost, by salary tier (the Monday picks-vs-field line; the outside reviewer's tier_edges)"
( cd "$OUTD" && timeout 1800 "$PY" "$G/tier_edges.py" "$P/scripts/weekly_picks_vs_field.py" "$OUTD/tier_edges.csv" ) > "$OUTD/tier_edges.txt" 2>&1 || say "WARN: tier_edges.py failed (see $OUTD)"
tail -20 "$OUTD/tier_edges.txt"
if [[ $STARTED == 0 ]]; then say "Neo4j was already running before this refresh (left as found): it must be stopped before Saturday's arming"
elif [[ "$KEEP" == --keep-running ]]; then say "Neo4j LEFT RUNNING (--keep-running): stop it before Saturday's arming (neo4j-milly stop)"; fi
say "done: $OUTD"
