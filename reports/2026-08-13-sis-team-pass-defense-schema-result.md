# SIS team pass-defense filtered-view schema result

Frozen disposition: **fails the outcome-blind schema gate; this exact
consumer-UI path is closed.**

The guarded sample completed all eight preregistered 2025 Week 1 Team Pass
Defense views—Wide/Slot crossed with Man/Zone in Totals and Value—using 9 of
the hard 10-request ceiling. Raw licensed CSVs remain gitignored under
`sis/team-pass-defense-schema-v1/`. The immutable local manifest SHA-256 is
`1516b5b92df642329cce9163110ceaf43424ebf94f2e3011fe31549df320204a`;
the machine result SHA-256 is
`4a6d6b1a80f96e723dc5582095c3ea77c6c61d559c8f17e47e82638e3908511a`.

## Mechanical result

Scope, cap and identity mechanics were usable:

- all eight exact artifacts exist and hash to the manifest;
- every slice remained below the 200-row cap;
- Totals and Value returned matching team IDs within each slice;
- the four slices covered all 32 team IDs in union; and
- the Value schema exposed `Points Saved` and `PS Per Play`.

The required volume-denominator condition failed in every Totals slice. The
team Pass Defense Totals CSV exposes `Att`, but neither a coverage-snap field
(`Cov. Snaps`/`Coverage Snaps`) nor targets (`Tgts`/`Targets`). Those fields are
available at player/defender grain, not in this filtered team export.

The frozen test required both coverage snaps and targets because a receiver
allocation law must distinguish opportunity volume from conditional outcomes.
Substituting `Att` after observing the schema would change the estimand and
the preregistered rule. Therefore no historical bulk plan is licensed and no
performance value, correlation, dependence score or lineup score was read.

## Queue consequence

Do not retry this exact Team Pass Defense Wide/Slot × Man/Zone consumer-UI
path, mine narrower shells/routes, or relax the denominator rule. The completed
historical team pass-defense marginal data remains valid for its already-closed
uses. Future receiver joint-allocation work needs a distinct source/grain with
auditable point-in-time opportunities—such as a vendor matchup export captured
prospectively, a separately justified player-level route/coverage source, or a
new non-SIS mechanism—under its own frozen protocol.

