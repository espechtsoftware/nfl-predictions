"""Every adopted lever must have a reviewed cross-repo consumption status.

WHY. `config_manifest.py` guards the adopted stack and inspects six `nfl_dfs`
modules; it contains the string "nfl2" zero times. The money path IS nfl2. That
is how OWN_MODEL -- the twice-proven chalk fade -- sat at zero for every live week
of 2026 while the manifest correctly reported no discrepancies: the disagreement
is across a repository boundary the guard does not cross.

This test closes that boundary. It does NOT re-prove consumption on every run
(that needs nfl2 checked out); it asserts that every adopted lever with a
non-zero declared value has a HAND-REVIEWED entry in
`tests/adopted_lever_consumers.json`. A new lever added to the policy without a
status fails here, which is the failure mode that was missing.

When nfl2 IS reachable (NFL2_SRC, or the conventional clone path), the second
test additionally checks the recorded statuses against the live nfl2 source.

Statuses: consumed (nfl2 money path uses it) / production_side (used in
nfl-predictions before nfl2 runs) / dead (declared here, not consumed there).
"dead" is not a bug on its own -- several are inert because a sibling count is 0
-- but it must be a DECLARED state, not a discovery.
"""
import json
import os
import re
from pathlib import Path

import pytest

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY

MANIFEST = Path(__file__).parent / "adopted_lever_consumers.json"
VALID = {"consumed", "production_side", "shadowed", "dead", "off", "needs_production_confirmation"}


def _declared() -> dict[str, str]:
    """EVERY adopted lever. Value-based filtering is unsafe.

    An earlier version of this test skipped levers declared "" or "0" on the
    reasoning that an inert lever cannot change a lineup. Mutation M1 (2026-09-22)
    showed that excludes OWN_MODEL, which is declared "" -- and "" SELECTS the
    naive chalk fade rather than disabling it. The guard would have skipped the
    exact defect it was written for. So every lever needs a reviewed status, and
    "off" is a claim someone made, not an inference from the literal.
    """
    return dict(ADOPTED_CLASSIC_POLICY.engine_environment({}))


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text())["levers"]


def test_every_nonzero_adopted_lever_has_a_reviewed_status():
    declared = _declared()
    recorded = _manifest()
    missing = sorted(set(declared) - set(recorded))
    assert not missing, (
        "adopted lever(s) with no cross-repo consumption status: "
        f"{missing}. Trace each to its point of use in the nfl2 money path and add "
        "an entry to tests/adopted_lever_consumers.json. A zero grep is a hypothesis, "
        "not a finding -- OWN_MODEL needed the call path, MAX_OVERLAP is a parameter.")


def test_statuses_are_wellformed_and_carry_proof():
    for key, entry in _manifest().items():
        assert entry.get("status") in VALID, f"{key}: bad status {entry.get('status')!r}"
        assert entry.get("proof", "").strip(), f"{key}: a status without proof is folklore"


def _nfl2_src() -> Path | None:
    env = os.environ.get("NFL2_SRC")
    cands = [Path(env)] if env else []
    cands.append(Path.home() / "projects" / "nfl2" / "src")
    for c in cands:
        if c.is_dir() and (c / "nfl2").is_dir():
            return c
    return None


@pytest.mark.skipif(_nfl2_src() is None, reason="nfl2 source not available on this host")
def test_recorded_consumption_matches_the_live_nfl2_source():
    """Verify the recorded statuses against nfl2 when it is checked out.

    A 'consumed' lever must appear in nfl2 source. A 'dead' one must not -- if it
    does, someone wired it up and the manifest is stale, which is good news that
    still has to be recorded.
    """
    src = _nfl2_src()
    files = [f for f in list(src.rglob("*.py")) + list((src.parent / "scripts").glob("*.py")) if f.is_file()]
    # Strip comments before matching. A bare substring search is the same mistake
    # in reverse: N_DARKGAME appears only inside a comment, and N_LEV/N_BOOM only
    # as local constants in a research script, neither of which is consumption.
    code = []
    for f in files:
        for line in f.read_text(errors="ignore").splitlines():
            s = line.split("#", 1)[0]
            if s.strip():
                code.append(s)
    blob = "\n".join(code)
    wrong = []
    for key, entry in _manifest().items():
        # consumption means READ AS AN ENV KEY, not merely named
        read = re.search(rf'(environ|env)(\.get\(|\[)\s*["\']{re.escape(key)}["\']', blob) is not None
        if entry["status"] == "consumed" and not read:
            wrong.append(f"{key}: recorded consumed, but nfl2 never reads it as an env key")
        if entry["status"] == "dead" and read:
            wrong.append(f"{key}: recorded dead, but nfl2 now reads it -- re-trace and update")
    assert not wrong, "cross-repo lever status is stale:\n  " + "\n  ".join(wrong)
