# Constraint-lattice real-path canary amendment

Date frozen: 2026-08-16, before either constraint-lattice 54-cell population
was launched and before any shard from either population existed.

Applies to:

- `20260816-constraint-lattice-control-support-census-v1`; and
- `20260816-constraint-lattice-scorefree-v1`.

This is a mechanical launch-contract amendment. It changes no image, code,
resource envelope, command, output prefix, cell computation, support rule or
scientific gate.

## Frozen canary law

Each launcher first deploys and executes only the population's actual 2023
Week 1 job. This is not a separate smoke job: it uses the real job name, real
immutable run prefix, real output URI, real image, command, environment,
service account, CPU, memory, timeout and task `maxRetries=0`, and its
execution becomes the 2023 Week 1 primary row in the final 54-cell ledger.

The remaining 53 jobs may be deployed or executed only after a strict canary
validator establishes all of the following without downloading the object:

1. the only execution of the canary job is the receipted execution;
2. its exact Cloud Run specification matches the population manifest;
3. it is terminal with `Completed=True`, `succeededCount=1`,
   `failedCount=0` and a completion time;
4. its exact create-only URI exists with a positive byte size and immutable
   generation; and
5. the execution and object metadata are durably retained and hash-bound by a
   `canary-completion.txt` receipt.

No support count, effect, exception, lineup or realized score may be read to
make the release decision. The object is not downloaded. A canary failure of
any class stops that immutable population before the other 53 executions. It
is not eligible for the later 54-primary bounded platform-attempt resolver;
a new population version and explicit disposition are required instead.

After canary success, the launcher appends the other 53 primary identities to
the same ledger. The existing bounded platform-attempt amendment applies only
after all 54 primaries are terminal. The strict finisher must bind the canary
receipt and metadata in addition to the primary/retry/accepted attempt ledgers.

## Consequence boundary

The canary validates the exact launch path and immutable namespace that the
resource preflight cannot cover. It cannot validate the other 53 workloads,
alter the resource finding, expose a scientific result, weaken the all-cell
requirement, authorize a retry, or license production.
