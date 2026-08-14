# docs/explainer

Non-technical explanations of the system, for readers outside the project.

This is **not** research output. Nothing here is a protocol, a result, or
evidence for a decision — `reports/` and `HANDOFF.md` remain the authoritative
record. These files exist only to explain the work to someone who does not read
the ledger.

| file | purpose |
|---|---|
| `what-we-built.html` | One-page explainer, designed for sharing. Source of the product page and published artifact. |
| `what-we-built.md` | Plain-text companion with the same content, for terminal reading and diffs. |

## Product page

The FastAPI product serves `what-we-built.html` at `/explainer` and links it as
**About** in the main navigation. The application image copies this directory,
so update the HTML and Markdown companions together and deploy the normal app
image; do not duplicate the prose inside the application module.

## Published artifact

`what-we-built.html` is published as a private page:

    https://claude.ai/code/artifact/444acd5a-4087-43d9-915b-bfedc45a37bc

**To update it, republish this exact file and pass that URL** — publishing
without the URL creates a second, separate artifact instead of updating the
existing one. The page is private until shared from its own share menu.

## Keeping the numbers honest

The explainer quotes figures from the research record. If those change, update
both files. Current sources:

| claim in the explainer | source |
|---|---|
| simulated QB→WR lift `1.053` vs realized `3.3228` | G0 execution `g0-final-served-dependence-v2-7fsx6` |
| 0 of 68 weeks beat the top prize; ~57-point gap | `reports/2026-08-08-80-entry-tail-audit.md` |
| ~7 in 10 weeks clear a representative min-cash line | `reports/2026-08-08-true80-weekly-max.csv`, at the 169.34 line |
| ~120 ledger entries, 20+ closed failures | `reports/2026-07-25-system-study.md` addenda |

The honest scoreboard is deliberately included. It is what makes the rest of the
document credible, and it should not be trimmed for an audience.
