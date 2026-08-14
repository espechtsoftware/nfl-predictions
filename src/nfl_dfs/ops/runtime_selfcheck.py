"""Fast deterministic runtime checks for compute-heavy replay workers."""

from __future__ import annotations


def verify_numeric_stack() -> None:
    """Fail before replay work if NumPy/SciPy cannot reproduce fixed values.

    Immutable image identity proves which bytes were published, but this
    assertion also checks that the worker can load and execute its numeric
    libraries after the container layers have materialized.
    """
    try:
        import numpy as np
        from scipy import linalg, special

        matrix = np.array([
            [3.0, 1.0, -1.0],
            [2.0, 4.0, 1.0],
            [-1.0, 2.0, 5.0],
        ], dtype=np.float64)
        vector = np.array([4.0, 1.0, 1.0], dtype=np.float64)
        solved = linalg.solve(matrix, vector)
        expected_solved = np.array([2.0, -1.0, 1.0], dtype=np.float64)
        cdf = special.ndtr(np.array([-1.0, 0.0, 1.0], dtype=np.float64))
        expected_cdf = np.array([
            0.15865525393145707,
            0.5,
            0.8413447460685429,
        ], dtype=np.float64)
        if not np.allclose(solved, expected_solved, rtol=0.0, atol=1e-12):
            raise ValueError(f"linear solve mismatch: {solved!r}")
        if not np.allclose(cdf, expected_cdf, rtol=0.0, atol=1e-12):
            raise ValueError(f"normal CDF mismatch: {cdf!r}")
        checksum = float(np.dot(solved, np.array([1.0, 2.0, 3.0])))
        if not np.isfinite(checksum) or abs(checksum - 3.0) > 1e-12:
            raise ValueError(f"numeric checksum mismatch: {checksum!r}")
    except Exception as exc:
        raise RuntimeError(f"numeric stack self-check failed: {exc}") from exc
