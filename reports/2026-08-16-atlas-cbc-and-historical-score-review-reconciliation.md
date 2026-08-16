# Reconciliation: ATLAS CBC and historical-score review

Date: 2026-08-16
Reviewed document: `reports/2026-08-16-atlas-cbc-and-historical-score-review.md`
Outcome access: none

The review identified one material resource-diagnosis defect, one historical
decision-rule asymmetry and several implementation checks. Its substantive
recommendations were accepted and resolved prospectively before any valid
ATLAS matched-diversity effect or historical score was opened.

## CBC diagnosis

The original interpretation of one-minute Cloud Monitoring p99 memory was
withdrawn. Memory pressure became the leading hypothesis rather than a ruled-
out explanation.

An independent diagnostic was frozen and run on 2024 Weeks 7, 15 and 16. It
captured the exact CBC child return code and terminating signal plus the
available cgroup memory counters, current usage, limit and true peak. Week 7
was included as requested. The strict harvest found:

| cell | result | child result | peak / 4 GiB |
|---|---|---:|---:|
| 2024 Week 7 | failed | `-9` / `SIGKILL` | 84.24% |
| 2024 Week 15 | completed R0 | `0` | 82.11% |
| 2024 Week 16 | failed | `-9` / `SIGKILL` | 84.38% |

Cloud Run exposed the cgroup-v1 compatibility interface and `failcnt`, not a
cgroup-v2 `oom_kill` counter. The frozen interpretation therefore correctly
records `SIGKILL` and resource pressure without overstating those two deaths
as directly proven OOM kills. The native Week 16 MPS parsed without error and
entered branch-and-bound before its retained log ended abruptly.

The prospectively frozen 80% pressure rule licensed a resource repair. A
single R0 enumeration then completed at 4 CPU/16 GiB, but the later exact
five-seed 2023 Week 8 full cell failed at that envelope with Cloud Run's
explicit terminal reason: `The configured memory limit was reached.` This is
direct evidence that 16 GiB is insufficient for at least one unchanged full
binary-interaction cell.

The current go/no-go experiment is therefore the exact same full 2023 Week 8
cell at 8 CPU/32 GiB. It remains score-free. Only strict terminal success and
valid shard mechanics can license the prospectively frozen all-54 resource-
only repair5 grid.

## Historical-score decision rule

The asymmetry was accepted. The original protocol file remains immutable, but
the controlling prospective amendment
`reports/2026-08-16-atlas-historical-high-tail-guard-amendment.md` now requires:

- at least two additional selected-book weeks at 200;
- no selected-book decline at 210, 220, 230 or 240;
- no candidate-pool decline at 200; and
- complete mechanical validity.

It also discloses that the 200 anchor was informed by earlier CBWU-OI results
on the same historical panel. A regression test proves that a treatment with
two additional 200 weeks but one lost 230 week cannot receive the positive
label. The later repair4 upstream amendment and the conditional repair5
protocol both retain these guards.

Historical scoring remains unlicensed because repair4 is mechanically invalid
and produced no output objects. If repair5 becomes a complete valid upstream,
the scorer must receive a separately frozen repair5 binding before any effect
is inspected.

## Integrality and pair-reach findings

The review's proof confirmation is accepted. Continuous interaction
auxiliaries preserve the exact integer roster problem, and focused parity tests
cover the old-binary versus continuous formulation where the old solver
completes. That optimization is deliberately excluded from the current 32-GiB
preflight and conditional repair5: those experiments isolate the resource
envelope while retaining binary auxiliaries. If the 32-GiB binary preflight
fails, the proved continuous formulation remains the next separately frozen
solver-mechanism option.

The pair-reach amendment and source-parity correction remain accepted and
binding. Neither licenses an outcome conclusion by itself.

## Disposition

No further correction is required before the live 32-GiB preflight completes.
Do not inspect its ATLAS effect fields. On strict success, run the entirely new
54-cell repair5 population at 8 CPU/32 GiB; on failure, do not launch repair5
and return to the separately frozen continuous-interaction path.
