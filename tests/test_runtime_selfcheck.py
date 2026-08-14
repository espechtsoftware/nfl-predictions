from __future__ import annotations

import numpy as np
import pytest

from nfl_dfs.ops.runtime_selfcheck import verify_numeric_stack


def test_numeric_stack_selfcheck_passes():
    verify_numeric_stack()


def test_numeric_stack_selfcheck_fails_closed(monkeypatch):
    monkeypatch.setattr(np, "allclose", lambda *args, **kwargs: False)
    with pytest.raises(RuntimeError, match="numeric stack self-check failed"):
        verify_numeric_stack()
