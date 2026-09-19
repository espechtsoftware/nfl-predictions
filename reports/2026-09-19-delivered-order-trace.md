# Which lineup actually reaches the Millionaire slot?

The current delivery chain sends the **first vetted lineup** to the Millionaire.
That can differ substantially from the raw model's first lineup. Replaying the
exact installed vetting helper on the two retained D1600 research books with
fresh, identical live vetting inputs gives:

| Identity trace | Control book | Repaired-input book |
|---|---:|---:|
| Original rank of first delivered lineup | 5 | 10 |
| Delivered position of original first lineup | 35 | 37 |
| Lineups marked material risk | 63/97 | 61/97 |
| Lineups marked hard risk | 0 | 0 |
| Raw top30 replaced within delivered top30 | 21 | 19 |

The original first lineup in both books contains Zay Flowers with DK `Doubtful`,
a DNP/hamstring report and no current matched props. Its risk is6.5/control and
6.0/repaired. The first promoted lineup has risk0 in each. Rest-related DNP flags
are displayed but contribute zero risk. This is an explanation of current code,
not a new claim about the player's eventual status or score.

The helper sums player risk and stably sorts by `(hard, material, original rank)`.
Material means total risk≥1. It retains all97 lineups. Thus this changes contest
allocation and spreadsheet priority, not the selected set. Under the verified
keep97/withdraw0 contest layout, these first promoted lineups would occupy the
Millionaire slot; all12 block mappings are recorded in the evidence. No operator
entries export, entry key, upload file or live lineup was read or changed.

Earlier D1600 comparisons of first lineups, raw prefixes and raw contest blocks
were **before vetting**. They do not establish a gain for the final Millionaire
entry. A pure permutation preserves whole-book Emax/P220, but not prefix or
contest-specific metrics. The result report now carries that explicit qualification.

## Reproduction and limits

Capture cutoff: **2026-09-19 05:32:31.918633 UTC**. All three BigQuery inputs
(raw injuries, inference features, prop lines) use the same time-travel cutoff.
Each source query is read-only, capped, receipted and captured to hashed parquet.
The props dates used are September17/18. Both arms deliberately use the same
fresh live vetting tables, not a refreshed repaired warehouse; this is not an
exact release-effect comparison or a replay of a retained Sunday's input state.
Later refreshes and Sunday reports can change the ordering.

The installed workstation helper was independently reported byte-identical to
tracked `scripts/week1_vet_book.py` in lab handoff `181592b`; this replay asserts
SHA256 `aa7d35f808d2a5db4faea6471b95c0c89b765ad1bc3c1e0c310ff5a428d6e89e`.
Both saved source receipts are hash-verified. The replay reads an explicit safe
frame-column allowlist excluding `actual`, runs the unchanged helper in isolated
folders and asserts that output rows are an exact permutation of the97 source
rows. It performs no NFL outcome or simulation-bank score read.

[Replay source](reviews/evidence/2026-09-19-vetting-order-trace.py) and
[identity results](reviews/evidence/2026-09-19-vetting-order-trace.json) retain the
original run/book hashes, full rank permutations, first-lineup flags, contest
maps and query artifact identities. Query parameters remain in the complete local
receipt; the tracked copy omits the long player-ID arrays only.

No vetting-policy change is nominated by this identity trace. Any proposal to
remove/reweight its soft flags needs a distinct historical test of this exact
sum-of-player-risk implementation, followed by a prospective delivered-book
comparison. Describing the raw model's first choice as the final entry would
skip an active downstream decision stage.
