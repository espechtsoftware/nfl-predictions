from collections.abc import Sequence

import numpy as np
import pytest

from nfl_dfs.optimizer.lineup import (
    CoverageSelectorEvent,
    select_from_support,
    select_tail_entries,
)


def _legacy_select_from_support(
    clears: np.ndarray,
    p_line: np.ndarray,
    mean_total: np.ndarray,
    n_entries: int,
) -> list[int]:
    """The selector body from before optional lineage instrumentation."""
    selected: list[int] = []
    covered = np.zeros(clears.shape[1], dtype=bool)
    remaining = set(range(len(clears)))
    while len(selected) < n_entries and remaining:
        best = max(
            remaining,
            key=lambda i: (
                int(np.count_nonzero(clears[i] & ~covered)),
                p_line[i],
                mean_total[i],
            ),
        )
        if not np.count_nonzero(clears[best] & ~covered):
            break
        selected.append(best)
        covered |= clears[best]
        remaining.discard(best)
    fill = sorted(
        remaining,
        key=lambda i: (p_line[i], mean_total[i]),
        reverse=True,
    )
    selected += fill[: n_entries - len(selected)]
    return selected


def _index_bytes(indices: Sequence[int]) -> bytes:
    return np.asarray(indices, dtype="<i8").tobytes()


def _support_fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    clears = np.asarray(
        [
            [True, True, False, False],
            [True, True, False, False],
            [False, False, True, False],
            [False, False, False, False],
            [False, False, False, False],
        ],
        dtype=bool,
    )
    p_line = clears.mean(axis=1)
    mean_total = np.asarray([100.0, 110.0, 90.0, 80.0, 70.0])
    return clears, p_line, mean_total


@pytest.mark.parametrize("seed", range(10))
def test_optional_trace_preserves_legacy_selection_bytes(seed: int) -> None:
    rng = np.random.default_rng(seed)
    clears = rng.random((17, 31)) < rng.uniform(0.05, 0.65, size=(17, 1))
    p_line = clears.mean(axis=1)
    mean_total = rng.normal(145.0, 20.0, size=17)
    n_entries = int(rng.integers(1, 20))

    legacy = _legacy_select_from_support(clears, p_line, mean_total, n_entries)
    without_trace = select_from_support(clears, p_line, mean_total, n_entries)
    events: list[CoverageSelectorEvent] = []
    with_trace = select_from_support(
        clears,
        p_line,
        mean_total,
        n_entries,
        event_sink=events.append,
    )

    assert without_trace == legacy
    assert with_trace == legacy
    assert _index_bytes(without_trace) == _index_bytes(with_trace)
    assert [event.candidate_index for event in events if event.selected] == legacy


def test_trace_records_actual_coverage_and_saturation_fill_steps() -> None:
    clears, p_line, mean_total = _support_fixture()
    events: list[CoverageSelectorEvent] = []

    selected = select_from_support(
        clears,
        p_line,
        mean_total,
        4,
        event_sink=events.append,
    )

    assert selected == [1, 2, 0, 3]
    selected_events = [event for event in events if event.selected]
    assert [event.candidate_index for event in selected_events] == selected
    assert [event.selection_rank for event in selected_events] == [0, 1, 2, 3]
    assert [event.phase for event in selected_events] == [
        "coverage",
        "coverage",
        "saturation-fill",
        "saturation-fill",
    ]
    assert [event.fresh_world_count for event in selected_events] == [2, 1, 0, 0]
    assert [event.individual_clear_count for event in selected_events] == [
        2,
        1,
        2,
        0,
    ]
    assert [event.mean_simulated_total for event in selected_events] == [
        110.0,
        90.0,
        100.0,
        80.0,
    ]
    assert [event.tiebreak for event in selected_events] == [
        (0.5, 110.0),
        (0.25, 90.0),
        (0.5, 100.0),
        (0.0, 80.0),
    ]

    assert events[-1] == CoverageSelectorEvent(
        candidate_index=4,
        selected=False,
        selection_rank=None,
        fresh_world_count=0,
        individual_clear_count=0,
        p_line=0.0,
        mean_simulated_total=70.0,
        phase="terminal",
        tiebreak=(0.0, 70.0),
        eligible_for_selection=True,
        terminal_reason="fill-order",
    )


def test_nonselected_after_coverage_book_full_has_no_fabricated_rank() -> None:
    clears = np.asarray(
        [
            [True, False, False],
            [False, True, False],
            [False, False, True],
        ],
        dtype=bool,
    )
    p_line = clears.mean(axis=1)
    mean_total = np.asarray([120.0, 110.0, 100.0])
    events: list[CoverageSelectorEvent] = []

    assert select_from_support(
        clears,
        p_line,
        mean_total,
        1,
        event_sink=events.append,
    ) == [0]

    assert [(event.candidate_index, event.selection_rank) for event in events] == [
        (0, 0),
        (1, None),
        (2, None),
    ]
    for event in events[1:]:
        assert event.phase == "terminal"
        assert event.fresh_world_count == 1
        assert event.eligible_for_selection is True
        assert event.terminal_reason == "book-full"


def test_tail_selector_trace_preserves_indices_and_uses_simulated_means() -> None:
    totals = np.asarray(
        [
            [120.0, 115.0, 0.0, 0.0],
            [125.0, 118.0, 0.0, 50.0],
            [0.0, 0.0, 110.0, 0.0],
            [90.0, 90.0, 90.0, 90.0],
        ]
    )
    without_trace = select_tail_entries(totals, 3, 100.0)
    events: list[CoverageSelectorEvent] = []
    with_trace = select_tail_entries(totals, 3, 100.0, event_sink=events.append)

    assert without_trace == with_trace
    assert _index_bytes(without_trace) == _index_bytes(with_trace)
    for event in events:
        assert event.mean_simulated_total == pytest.approx(
            totals[event.candidate_index].mean()
        )


def test_sink_side_effects_run_only_after_selector_decisions() -> None:
    clears, p_line, mean_total = _support_fixture()
    expected = select_from_support(clears, p_line, mean_total, 4)
    observed: list[CoverageSelectorEvent] = []

    def mutating_sink(event: CoverageSelectorEvent) -> None:
        observed.append(event)
        clears[:] = False
        p_line[:] = -1.0
        mean_total[:] = -1.0

    actual = select_from_support(
        clears,
        p_line,
        mean_total,
        4,
        event_sink=mutating_sink,
    )

    assert actual == expected
    assert _index_bytes(actual) == _index_bytes(expected)
    assert [event.candidate_index for event in observed if event.selected] == expected


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"SELECT_LSE": "0.5"}, "SELECT_LSE"),
        ({"SELECT_LADDER": "194:1"}, "SELECT_LADDER"),
    ],
)
def test_trace_request_rejects_noncoverage_selector(
    env: dict[str, str], message: str
) -> None:
    totals = np.asarray([[120.0, 0.0], [0.0, 120.0]])

    with pytest.raises(ValueError, match=message):
        select_tail_entries(
            totals,
            1,
            100.0,
            env,
            event_sink=lambda _event: None,
        )
