"""vet_book.block_order: hard / material rows sink WITHIN their block; nothing crosses the mean/sleeve boundary."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vet_book as vb  # noqa: E402


def test_block_order_sorts_within_the_mean_and_sleeve_blocks_only():
    tiers = [(True, False), (False, False), (False, True), (False, False),   # mean block: row 0 hard, row 2 material
             (False, False), (True, False), (False, False)]                   # sleeve block: row 5 hard
    assert vb.block_order(tiers, 4) == [1, 3, 2, 0, 4, 6, 5]
    assert vb.block_order(tiers, 7) == [1, 3, 4, 6, 2, 0, 5]                  # one block: the old whole-book order
    assert vb.block_order(tiers, 0) == [1, 3, 4, 6, 2, 0, 5] and vb.block_order([], 3) == []
