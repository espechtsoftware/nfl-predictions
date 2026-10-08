"""The build host's REFERENCE emits (vetted-all30 / all90, composite-all30, hybrid15-all30) are skipped, with a line
saying so, when their ranks exceed the book (2026-10-08: at K 26 they always printed EMIT FAILED, "rank range 1-30
exceeds the 26 available lineups", breaking the rule that an EMIT FAILED line on Sunday means a real failure)."""
import re
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh"


def _emit_ref_source() -> str:
    text = SCRIPT.read_text()
    m = re.search(r"^emit_ref\(\) \{.*?^\}\n", text, re.S | re.M)
    assert m, "emit_ref() not found"
    return m.group(0)


def _run(book: int, sleeve: int, n: int) -> str:
    prog = ('emit() { echo "EMIT $2 $3"; }\n' + _emit_ref_source()
            + f'BOOK_ENTRIES={book}; TAIL_SLEEVE={sleeve}; emit_ref /run vetted-all{n} {n}\n')
    return subprocess.run(["bash", "-c", prog], capture_output=True, text=True, check=True).stdout.strip()


def test_k26_skips_and_says_so():
    assert _run(26, 0, 30) == "skip reference emit vetted-all30 (ranks 1-30 exceed the 26-lineup book)"
    assert _run(26, 0, 90).startswith("skip reference emit vetted-all90")


def test_a_big_book_still_emits():
    assert _run(105, 0, 30) == "EMIT vetted-all30 1-30"
    assert _run(105, 0, 90) == "EMIT vetted-all90 1-90"
    assert _run(26, 4, 30) == "EMIT vetted-all30 1-30"          # the tail sleeve counts toward the book


def test_no_unguarded_all_n_emit_remains():
    text = SCRIPT.read_text()
    assert not re.search(r'\bemit "\$\w+_DIR" \S+-all\d+ ', text)
    assert len(re.findall(r'emit_ref "\$\w+_DIR" \S+-all\d+ \d+', text)) == 4
