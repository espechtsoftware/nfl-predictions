"""Allowlist companion to test_week3_blocker_watch_is_read_only.

The sibling test denylists mutating verbs. A denylist over shell leaks. Measured
2026-09-22 against the adopted script, the sibling catches `bq load` but passes
all of: `rm -rf`, `> file`, `bq extract`, `curl -X POST`, and -- the one that
matters most on a money-path host -- `gcloud scheduler jobs run`, which
force-fires a scheduler. The sibling pins jobs execute/deploy/update/delete, not
run.

This pins the complementary property, which does not leak the same way: the watch
may invoke only allowlisted binaries, every `bq` call must be a query, and it may
not redirect into a file. Keep both -- the denylist names intent, the allowlist
bounds capability.
"""
import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "week3_blocker_watch.sh"

# Everything the reporter legitimately needs. Adding to this list is a deliberate
# act that should be argued for in review -- that is the point of an allowlist.
ALLOWED = {
    "bash", "date", "timeout", "bq", "echo", "tail", "set", "case", "esac",
    "if", "then", "else", "elif", "fi", "for", "while", "do", "done", "in",
    "local", "return", "exit", "printf", "q", "true", "false",
}

# Command position: line start, or after a pipe / semicolon / && / || / $( / backtick.
# Deliberately NOT after "{", which would split ${VAR} into fragments.
# Backticks here quote BigQuery table names, not command substitution, so they are
# stripped as data rather than treated as a command boundary.
_SPLIT = re.compile(r"(?:^|\||;|&&|\|\||\$\()\s*")
_STRING = re.compile(r"'[^']*'|\"[^\"]*\"")
_BACKTICK = re.compile(r"`[^`]*`")
_EXPANSION = re.compile(r"\$\{[^}]*\}|\$\w+|\$\(")
_CASE_PATTERN = re.compile(r"^[^\s]*\)")


def _strip_data(line):
    """Quoted text and variable expansions are data, not commands."""
    return _EXPANSION.sub(" ", _BACKTICK.sub(" ", _STRING.sub(" ", line)))


def _code_lines():
    return [s for s in (l.strip() for l in SCRIPT.read_text().splitlines())
            if s and not s.startswith("#")]


def test_only_allowlisted_binaries_are_invoked():
    bad = set()
    for raw in _code_lines():
        line = _strip_data(raw)
        if _CASE_PATTERN.match(line):
            continue
        for seg in _SPLIT.split(line):
            seg = seg.strip()
            if not seg:
                continue
            tok = seg.split()[0].strip("\"'")
            if not tok or tok.endswith(")") or tok.endswith("()"):
                continue
            if "=" in tok or tok.startswith(("$", "-", "[", "]", "{", "}")):
                continue
            if tok not in ALLOWED:
                bad.add(tok)
    assert not bad, f"watch invokes non-allowlisted command(s): {sorted(bad)}"


def test_every_bq_invocation_is_a_query():
    """bq query reads. bq load/rm/mk/cp/extract/insert do not."""
    for raw in _code_lines():
        line = _strip_data(raw)
        if re.search(r"\bbq\b", line):
            assert re.search(r"\bquery\b", line), f"non-query bq invocation: {raw}"


def test_the_watch_never_redirects_into_a_file():
    """`2>/dev/null` and `>&` are fine; `> path` and `>> path` are not."""
    for raw in _code_lines():
        line = _strip_data(raw)
        line = re.sub(r"\d?>&\d?|\d?>\s*/dev/null", "", line)
        assert not re.search(r">>?\s*\S", line), f"writes to a file: {raw}"
