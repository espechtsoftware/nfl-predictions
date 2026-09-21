"""No money-path tool may have a DEFAULT for the data slice it operates on.

This is the class guard for the defect found 2026-09-21. `player_score.py` had
`--week` defaulting to 1 and the Sunday driver omitted the flag, so every Week-2
composite ordering silently scored Week-2 lineups against the last Week-1
projection batch. The sweep that followed found the same shape in three sibling
tools, two of them defaulting to week 2, which would have been silently wrong on
the very next Sunday.

The rule: an argument that selects WHICH DATA a run operates on -- season, week,
slate, draft group -- must be required, or derived from the artifact being
operated on. Never both optional and defaulted. A per-player or per-id join will
not notice the difference, and a coverage count will look healthy either way.

Adding a new money-path tool with a defaulted slice argument fails this test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Tools on the Sunday money path: they read warehouse slices and their output
# reaches, or orders, an entered book.
MONEY_PATH_TOOLS = (
    "player_score.py",
    "vet_book.py",
    "vet_replace_v4.py",
    "qb_flags.py",
    "market_move.py",
    "ordering_shadows.py",
    "book_sheet.py",
    "qb_classify.py",
)

# Arguments that choose a slice of data rather than how to process it.
SLICE_ARGS = ("--season", "--week", "--slate", "--group", "--draft-group", "--target-week")

_ADD_ARG = re.compile(r'add_argument\(\s*"(--[a-z-]+)"(.*?)\)', re.S)


def _slice_args_with_defaults(path: Path):
    """Return [(flag, fragment)] for slice args that carry a usable default."""
    found = []
    for m in _ADD_ARG.finditer(path.read_text()):
        flag, rest = m.group(1), m.group(2)
        if flag not in SLICE_ARGS:
            continue
        if "required=True" in rest:
            continue
        if "default=" in rest and "default=None" not in rest:
            found.append((flag, m.group(0)))
    return found


@pytest.mark.parametrize("tool", MONEY_PATH_TOOLS)
def test_no_money_path_tool_defaults_its_data_slice(tool):
    path = ROOT / "scripts" / tool
    if not path.is_file():
        pytest.skip(f"{tool} is not in this tree")
    offenders = _slice_args_with_defaults(path)
    assert not offenders, (
        f"{tool} defaults a data-slice argument: {[f for f, _ in offenders]}. "
        f"A defaulted slice silently scored Week 2 against Week 1 on 2026-09-20. "
        f"Make it required=True, or derive it from the run's own receipt.")


class TestTheGuardItselfWorks:
    """A guard that cannot fail is not a guard."""

    def test_it_catches_a_defaulted_week(self, tmp_path):
        f = tmp_path / "t.py"
        f.write_text('ap.add_argument("--week", type=int, default=2)')
        assert [x[0] for x in _slice_args_with_defaults(f)] == ["--week"]

    def test_it_catches_a_defaulted_draft_group(self, tmp_path):
        f = tmp_path / "t.py"
        f.write_text('ap.add_argument("--group", type=int, default=153428)')
        assert [x[0] for x in _slice_args_with_defaults(f)] == ["--group"]

    def test_it_accepts_required(self, tmp_path):
        f = tmp_path / "t.py"
        f.write_text('ap.add_argument("--week", type=int, required=True)')
        assert _slice_args_with_defaults(f) == []

    def test_it_accepts_default_none(self, tmp_path):
        """default=None is the derive-from-artifact pattern player_score.py uses."""
        f = tmp_path / "t.py"
        f.write_text('ap.add_argument("--week", type=int, default=None)')
        assert _slice_args_with_defaults(f) == []

    def test_it_ignores_processing_arguments(self, tmp_path):
        """--k chooses how much work to do, not which data. It may default."""
        f = tmp_path / "t.py"
        f.write_text('ap.add_argument("--k", type=int, default=30)')
        assert _slice_args_with_defaults(f) == []


class TestTheSundayCallersPassTheSlate:
    """The other half of the defect was a caller that omitted the flag.

    Only the CURRENT Sunday chain is covered. `week1_sunday_build_host.sh` and
    `week1_learned_after_build.sh` also call these tools without a slate, and
    that is deliberate: they invoke HOST COPIES
    (`/home/erich/week1-sunday/tools/player_score.py`, `$OUT/tools/vet_book.py`),
    not the files in this repository, and they carry no SEASON/WEEK variables at
    all because they are Week-1 archives. Making the repository tools require the
    flags therefore cannot affect them. Do not "fix" those call sites by inventing
    variables; they are superseded by sunday_build_host.sh and sunday_after_build.sh.
    """

    @pytest.mark.parametrize("tool", ("player_score.py", "vet_book.py"))
    def test_sunday_build_host_passes_the_slate(self, tool):
        script = ROOT / "scripts" / "sunday_build_host.sh"
        lines = [l for l in script.read_text().splitlines() if tool in l and "$TOOLS/" in l]
        assert lines, f"no call to {tool} found in sunday_build_host.sh"
        for line in lines:
            assert '--season "$SEASON"' in line and '--week "$WEEK"' in line, line
