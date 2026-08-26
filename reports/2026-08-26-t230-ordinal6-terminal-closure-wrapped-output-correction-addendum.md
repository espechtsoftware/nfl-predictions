# T230 ordinal-6 terminal-closure wrapped-output correction addendum

Date frozen: 2026-08-26, after the independently licensed corrected focused
terminal-closure test completed successfully and before any terminal-closure
preflight attempt marker, preflight receipt, cloud publication, result or
acceptance body read, realized-outcome read, or score.

This addendum is subordinate to both
`2026-08-26-t230-ordinal6-replacement-terminal-closure-amendment.md` and
`2026-08-26-t230-ordinal6-terminal-closure-focused-output-correction-addendum.md`.
It corrects only the retained-output parser's treatment of ordinary pytest
line wrapping. It grants no preflight, publication, execution, result read,
outcome read, scoring, or analytical authority.

## Preserved second successful invocation

The prior correction candidate and its exact output are durably replayable
from commit `25ea2a372590d69ad5cb3e84e39358ec23080d6a`. Independent exact-byte
review licensed exactly one invocation of:

```text
.venv/bin/python -m pytest -q tests/test_corpus_extreme_tail_panel_platform_replacement_terminal_v1.py tests/test_run_corpus_extreme_tail_panel_platform_replacement_terminal_v1.py
```

That invocation exited 0. Its exact retained output is SHA-256
`d5909c51985bd5db202843a4382250d792189dd73767b52e1fa90d69193bf46c`,
160 bytes, and two newline-terminated progress lines. The first line contains
72 period pass markers, one separator space, and `[ 79%]`. The second contains
19 period pass markers, 54 separator spaces, and `[100%]`. The total is 91
passing progress markers. It contains no failure, skip, warning, error, xfail,
xpass, deselection, or diagnostic marker.

The invocation made no cloud call, created no preflight attempt marker or
preflight receipt, published no GCS object, submitted no Cloud Run execution,
and read no result, acceptance, effect, realized outcome, or score.

## Bounded wrapped-progress correction

`focused_test_pass_count_v1` may accept one or more newline-terminated pytest
progress-only lines. Every line must contain one or more `.` bytes, one or
more ASCII separator spaces, a bracketed right-aligned three-character
decimal percentage field, `%]`, and `\n`. Percentages must be canonical
integers from 1 through 100, strictly increase across lines, occur at 100 only
on the final line, and end exactly at 100. The parser returns the total number
of period bytes across all lines.

The grammar must reject any non-period test marker; diagnostic or extra text;
missing terminal newline; tabs; malformed spacing or percentage padding;
zero, leading-zero, over-100, repeated, or decreasing percentages; an early
100-percent line; no test marker; or a final percentage below 100. The clean
summary grammar remains separately valid.

Focused regression tests must bind the exact 160-byte retained output and the
listed adversaries. This addendum must be measured in the terminal-closure
contract, preflight-attempt marker, preflight receipt, final review lock,
implementation-source commit replay, and later clean lock-containing HEAD
replay.

## Authority consequence

The first and second successful invocations remain consumed. After a fresh
exact-byte independent review reports P0/P1/P2 counts of zero, this addendum
licenses exactly one final corrective invocation of the same focused command.
The terminal-closure lifetime focused-test count is then exactly three. A
failed final invocation consumes that allowance; no fourth invocation is
authorized without another truthful pre-publication amendment.

The v3 review lock must record all three invocations separately: the original
51-marker output at commit `c7556b4a1282f1252a6298baaaa3d47c9513ef14`,
the wrapped 91-marker output at commit
`25ea2a372590d69ad5cb3e84e39358ec23080d6a`, and the final corrected output at
its later implementation commit. It may not relabel either earlier pass,
reuse either earlier output as the final output, or erase the two parser
defects. Reusing the fixed output path for the final bytes is allowed only
because both historical versions remain replayable and separately bound.

All execution, publication, historical scoring, R6 freeze, promotion,
production-change, and decision authorities remain false.
