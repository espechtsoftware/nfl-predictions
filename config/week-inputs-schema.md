# Weekly operator inputs — schema and example

The Sunday build refuses to start without two files. This document is the public
record of their **shape**. The **values** are private and live in the project's
private bucket, never in this repository.

## Why they are not committed here

**This repository is public.** `contests.json` carries per-contest entry counts,
keep counts and fees — the week's stake plan and bankroll allocation. Committing
it would publish that permanently, and before lock it is live information about
which contests are being entered and how deep. The contest ids themselves are
public DraftKings identifiers; the entry and fee columns are not.

Neither file has ever been committed on any branch. Keep it that way.

## Where the values live

    gs://nfl-predictions-503414-raw/week-inputs/<season>/w<WW>/contests.json
    gs://nfl-predictions-503414-raw/week-inputs/<season>/w<WW>/chosen-dose.env

That bucket has no `allUsers` or `allAuthenticatedUsers` binding. Object
generations give versioning, so a replaced file does not erase the one a build
actually used.

Managed with `scripts/week_inputs.py`:

    python scripts/week_inputs.py validate --contests c.json --dose dose.env
    python scripts/week_inputs.py push --season 2026 --week 3 --contests c.json --dose dose.env
    python scripts/week_inputs.py pull  --season 2026 --week 3 --out /home/erich/week3-sunday

`pull` writes `week-inputs-receipt.json` beside the files, pinning each object by
uri, generation, sha256 and byte count. **That receipt is safe to commit**: it
carries no contest ids and no per-contest figures, only aggregates that already
appear in the evidence record.

## `chosen-dose.env`

Two keys, both positive integers. Week 2 used:

    CHOSEN_LEV=2560
    CHOSEN_BOOM=10240

## `contests.json`

A JSON list of contest objects. Entries must total **at least 90** across the
file, which is the build gate's own minimum.

| field | type | notes |
|---|---|---|
| `name` | string | short label used in filenames and the operator page |
| `contest_id` | string | the DraftKings contest id; must be unique in the file |
| `entries` | integer | at least 1; the total across the file must reach 90 |
| `keep` | integer | how many of those rows are kept; must not exceed `entries` |
| `fee` | **number** | entry fee in dollars. **Fractional values are real** — the quarter satellites carry `0.25` |
| `note` | string | free text, not validated |

**`fee` is money, not an integer.** An earlier version of the validator cast it
with `int()`, which silently truncated the two `0.25` satellite contests to zero
and made Week 2 total $238 instead of the $246 actually settled. It would also
have rejected a fee written as the string `"0.25"`. Keep it numeric.

### Example — shape only, invented values

    [
      {"name": "milly",      "contest_id": "100000001", "entries":  1, "keep":  1, "fee": 20,   "note": "first entry"},
      {"name": "flea",       "contest_id": "100000002", "entries": 23, "keep": 23, "fee": 5,    "note": ""},
      {"name": "supersat25", "contest_id": "100000003", "entries": 66, "keep": 66, "fee": 0.25, "note": "quarter satellites"}
    ]

That example totals 90 entries, the minimum the gate accepts.
