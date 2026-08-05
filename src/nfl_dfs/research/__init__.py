"""Research workstreams from reports/emerging-technologies-plan.md.

Shared infrastructure (plan §4, 2026-08-05): canonical run identity,
normalized candidate data model, shipping-defaults manifest, and the
dependence scorecard every workstream is judged against before touching
a panel. Workstream modules (gfn_*, sbi_*, online_conformal, ...) live
alongside it.

Nothing in this package is wired into the production scoring or lineup
path. Modules graduate out of here only through the plan's shadow ->
adoption gates (plan §2, §4.5).
"""
