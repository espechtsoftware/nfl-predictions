# ATLAS continuous-image validation build-path repair

Date frozen: 2026-08-16, after candidate build
`85aace06-7f36-4307-acfa-194c4648ef6d` failed but while the binary 32-GiB
preflight remained nonterminal and before any continuous-interaction cloud
calculation.

Applies to:
`reports/2026-08-16-atlas-continuous-interaction-parity-protocol.md`.

## Mechanical failure

The candidate build failed during pytest collection. Two tracked tests import
renderer helpers through the repository-level `scripts` namespace, while the
generic `cloudbuild.yaml` invoked bare `pytest` without the repository root on
`PYTHONPATH`. Both failures were `ModuleNotFoundError: No module named
'scripts'`. No test body ran, no Docker image was built or pushed and no ATLAS
source, data, solver or effect was executed.

This does not test or invalidate the continuous formulation.

## Sole repair

Resubmit the exact Git archive of source commit
`06797314a0ed423b9f5783fc926b269c1fb24371`. Use the dedicated build
configuration `cloudbuild-atlas-continuous.yaml`, SHA-256
`950db566469aa645efda634370e1f6fe7554db6317537e3a820e9161bec8f93e`.
It is identical in validation/image/smoke intent to the first configuration
except that the test command is `PYTHONPATH=. pytest`.

Use the create-only tag `atlas-continuous-0679731-r1`. Record the unique build
ID before observing its status. Only a complete successful test step, image
build, both container smokes and immutable resolved digest license the parity
launcher. A second failure does not license another unregistered repair.

The candidate image source, optimizer, runner, diagnostic source, parity cell,
resources and every scientific gate remain unchanged. This repair licenses no
Cloud Run calculation, historical score or production change.
