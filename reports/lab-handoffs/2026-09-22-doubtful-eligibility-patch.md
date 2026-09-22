# Patch: exclude Doubtful players at DK-status eligibility

**Repo:** `nfl2` (lab). **File:** `src/nfl2/live.py` line 211.
**Status: NOT APPLIED. Needs the operator's authorization**, because the money path runs
from the clone `/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c`, which is
required to stay CLEAN at `2dc116c`, and because nothing of ours modifies nfl2.

## The change

```python
-DK_INACTIVE_STATUSES = frozenset({"O", "OUT", "IR"})
+DK_INACTIVE_STATUSES = frozenset({"O", "OUT", "IR", "D"})
```

That is the whole diff.

## Why this is the right place, and why it is not a tuning knob

`apply_dk_status_invariant` already exists to do exactly this job — "remove
DraftKings-inactive rows **before any simulation or candidate solve**" — and it already
receipts what it removed and what it retained. Today its receipt reads
`retained_designations: {"Q": 10, "D": 3}`: Doubtful is retained **deliberately**, treated
identically to a healthy player by every downstream stage.

Excluding at eligibility is not the same as capping exposure. A cap changes the selector's
optimum; eligibility changes the universe, exactly as it already does for OUT and IR. The
objective, the draws and the construction rules are untouched — the pool simply never
contains a player who is not expected to play.

## The Week-2 evidence

| player | DK status at build | rows held | DK points |
|---|---|---:|---:|
| **Zay Flowers** | **Doubtful** | **48 of 97** | **0.0** |
| Tua Tagovailoa | Doubtful | 5 of 97 | 0.0 (imputed — unrostered in all twelve exports) |
| Brock Bowers | Doubtful | 0 of 97 | 0.0 |

51 of 97 rows carried a Doubtful player. All three scored zero; none played. The
Millionaire entry — one row, the most valuable one — was among them.

**Questionable is NOT included in this patch and should not be.** Q-carrying rows averaged
98.3 against 98.4 for the rest, and the two Q players with posted props were among the
better outcomes (Olave 22.6, Burrow 16.2). The asymmetry is specific to D.

## What I am not claiming

Three players is not a sample. The argument is structural, not statistical: OUT and IR are
excluded because those players cannot play, and by NFL convention Doubtful means roughly
75% likely not to play — while DraftKings prices them close to normally, which is the
mispricing. If a Doubtful player does play he is usually limited. The current policy puts
him in the pool at full price with no discount anywhere in the chain.

## Failing test (drop in as `tests/test_dk_status_invariant_excludes_doubtful.py`)

```python
import pandas as pd
from nfl2.live import apply_dk_status_invariant


def test_doubtful_is_removed_before_any_solve():
    """Week 2: a Doubtful player held 48 of 97 entered rows and scored 0.0."""
    fr = pd.DataFrame({
        "name": ["Healthy WR", "Doubtful WR", "Questionable WR", "Out WR"],
        "status": ["", "D", "Q", "OUT"],
        "pos": ["WR"] * 4,
    })
    kept, receipt = apply_dk_status_invariant(fr)
    assert "Doubtful WR" not in set(kept.name)
    assert "Out WR" not in set(kept.name)
    # Questionable is deliberately still eligible
    assert "Questionable WR" in set(kept.name)
    assert receipt["removed_by_status"].get("D") == 1
    assert "D" not in receipt["retained_designations"]
```

Against the current code this test fails on the first assertion, which is the point.

## Decision required

1. **Authorize or decline** the one-line change.
2. If authorized, decide **how it reaches the money path**: a new clone at a new nfl2
   commit (clean, but the arming/`EXPECT_SHA` chain has to move with it), or a disclosed
   patch applied to the existing clone (faster, breaks the clean-at-`2dc116c` rule that
   the verification chain depends on).

I have not touched the clone. `2dc116c` is still clean.
