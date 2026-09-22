# Laptop review item 5: injured-player concentration — the rule was aimed at the wrong player

Answering item 5 of `handoffs/2026-09-21-laptop-postmortem-review-round1.md`:

> Keep all proposed numerical caps/rules exploratory until compared fairly. Honor
> Erich's request to limit injured-player concentration; provide a concrete
> constrained-selection option, per-contest exposures, feasibility and score
> tradeoffs. Do not infer missing props equals medical unavailability; distinguish
> feed gaps and observation times.

Method and reproduction gate as in
[item 3](2026-09-21-laptop-item3-isolated-cap-effect.md) §1 — the delivered book
is reproduced exactly before any arm is run.

## 1. The finding that reframes this item

The post-mortem built its injured-player proposal around **Ladd McConkey**
(Questionable, 26 of 97 rows, played, scored 6.5). That was the wrong headline.

**Zay Flowers was listed Doubtful at build time, was placed in 48 of our 97 rows
including the Millionaire entry, and DraftKings recorded him at 0.0 points.**

| | rows | build-time status | DK points |
|---|---:|---|---:|
| Zay Flowers | **48 / 97** | **Doubtful** | **0.0** (recorded, 11 standings rows) |
| Ladd McConkey | 26 / 97 | Questionable | 6.5 |
| Tua Tagovailoa | 5 / 97 | Doubtful | 0.0 (*imputed* — see §5) |
| Brock Bowers | 0 / 97 | Doubtful | 0.0 (recorded) |

51 of 97 delivered rows carried a player who was Doubtful at build time. All three
Doubtful players scored zero; none played. Those 51 rows averaged **91.6** realized
against **105.9** for the 46 clean rows (descriptive — the two groups are not
otherwise matched).

**The single most valuable row we entered, the Millionaire entry, carried a
Doubtful player who did not play.** The designation was already in the frame at
build time. Nothing had to be predicted.

## 2. Erich's request, isolated from the general cap

His ask was to limit injured-player concentration. The post-mortem bundled that
with a general 30% cap and a DST cap, so here it is on its own — same pool, same
statuses, same K, same objective, same contest assignment:

| arm | sim E[max] | cost | realized mean | best | >=150 | McConkey rows | max exposure |
|---|---:|---:|---:|---:|---:|---:|---:|
| delivered (no cap) | 203.45 | — | 98.40 | 157.96 | 3 | 26 | 51 |
| **injury rule only** | 199.77 | **-1.8%** | 108.38 | 170.22 | 4 | 4 | **57** |
| injury rule + general 30% / DST 20% | 198.73 | -2.3% | **114.68** | **184.54** | **9** | 4 | 29 |

Injury rule = Doubtful 0%, Questionable-with-a-posted-prop 10%, Questionable-without 5%.

**The injury rule alone makes general concentration worse.** Capping the injured
players pushes their book share onto whoever the greedy likes next: peak exposure
*rises* from 51 to 57 (Jefferson). The injury rule needs the general cap beside
it or it relocates the problem rather than removing it. That is a design finding,
not a tuning result, and it holds regardless of who scored what.

## 3. Per-contest exposures, and a hazard a book-share cap cannot see

McConkey's rows under the delivered contest assignment:

| contest | rows | delivered | injury rule | injury + general |
|---|---:|---:|---:|---:|
| **milly** | 1 | **0** | **1** | **1** |
| flea | 23 | 7 | 3 | 3 |
| nickel | 5 | 2 | 0 | 0 |
| satellite | 2 | 1 | 0 | 0 |
| supersat1b | 10 | 4 | 0 | 0 |
| supersat25b | 16 | 5 | 0 | 0 |
| *all others* | | 7 | 0 | 0 |
| **total** | 97 | **26** | **4** | **4** |

The rule cuts him 26 -> 4 and **puts one of the four in the Millionaire**, which
the delivered book had kept him out of. A cap expressed as a share of the book
constrains *how many* rows, never *which* rows, and the greedy reshuffles freely
underneath it.

This is why the "<= 20% of the majors' rows" sub-rule — which I excluded from item 3
as not implementable at book level — **is load-bearing rather than optional**. Without
per-contest counting inside the selection loop, an exposure rule can quietly move an
injured player into the highest-value seat while reporting that it reduced his exposure.

## 4. Your criticism of the no-prop rule: right in general, immaterial here

You said not to treat a missing prop as medical unavailability. Checking it:

**Population-wide you are right.** Only 177 of 429 players (41.3%) carry a prop, so
absence is the norm and carries almost no information by itself.

**But coverage is almost entirely a salary effect**, and at the top of the board
absence is anomalous:

| salary band (skill) | n | prop coverage |
|---|---:|---:|
| <= $3,500 | 154 | 17% |
| $3,500–4,500 | 138 | 33% |
| **$4,500–5,500** | 57 | **95%** |
| **$5,500–6,500** | 32 | **97%** |
| **$6,500–8,000** | 20 | **90%** |

All **16** healthy WRs within $800 of McConkey's $6,200 have a posted prop. He is
the only one without. At that price point absence is a signal, not a gap.

So the rule should be conditional on peer coverage, not on raw absence:

> A flagged player counts as having *no market* only if his position-and-salary
> peer group (healthy, +/- $800, >= 6 peers) has **>= 80%** prop coverage and he has
> none. Below that threshold, absence is a feed gap and carries no information.

Applied to the eleven flagged players, that separates them cleanly:

| verdict | players | DK points (mean) |
|---|---|---:|
| feed gap | Bowers (1 peer), Tua (24% peer cov), O'Connell (9%) | 0.0 |
| **real absence** | **Flowers, McConkey, Harvey** (88–100% peer cov) | 2.2 |
| has prop | Olave, Burrow, Pittman, Black, McMillan | 8.3 |

The ordering is consistent with the rule but n=11 establishes nothing; the value here
is that the distinction you asked for is now *computable* rather than asserted.

**Materially it changed nothing on this slate**: the peer-aware and raw-absence arms
produce the **identical 97-row book** (§2 shows one row, because they tie). The only
player reclassified, O'Connell, was never selected. Your objection is methodologically
correct and had zero effect on Week 2 — both halves of that are worth saying.

## 5. Observation times: not answerable from the artifacts, and that is a gap

You also asked to distinguish observation times. **The run receipt records a props
content hash (`07609a6731553cb0`) and a row count (8,589) but no props observation
timestamp.** The build ran 2026-09-19 15:30 UTC against a 2026-09-20 17:00 UTC lock —
about 25.5 hours pre-lock, and props for questionable players routinely post later
than that. So "absent at build time" cannot currently be distinguished from "never
offered", and the post-mortem's "no prop posted **by Saturday morning**" clause was
never verifiable from what we keep.

**Concrete request:** add `props_pulled_at`, and a per-player first-seen timestamp, to
the run receipt. Until then any rule keyed to prop absence is keyed to an unobservable.

**One imputation disclosed:** Tua Tagovailoa has no row in any of the twelve standings
exports, so his 0.0 is my default for an unrostered player, not a DK-recorded score.
Flowers' and Bowers' zeros are recorded. Tua appears in 5 of 97 rows, so the §1
conclusion does not rest on him.

## 6. Feasibility

Covered in item 3 §5: at a 15% general cap the constrained greedy cannot fill the book
(91 of 97). The injury rule alone is feasible at K=97, as is the combined arm. No arm
in this report is infeasible except the 15% general cap.

## 7. Status of the proposals

Per your instruction they stay **exploratory**. Specifically:

- **Doubtful -> 0%** is the part I would actually argue for, and I did not propose it
  prominently enough the first time. It requires no forecast, no threshold chosen from
  outcomes, and no ownership input — only a designation already sitting in the frame.
  It is the nearest thing here to a free correction.
- **Questionable tiering** is not supported by this slate: Questionable-carrying rows
  averaged 98.3 against 98.4 for the rest, and the two Questionable players with posted
  props were among the better outcomes (Olave 22.6, Burrow 16.2). The post-mortem's
  framing around McConkey overweighted one visible case.
- **Numerical levels** are not identified by one slate and I am not proposing any.
- **The majors sub-rule** needs a design decision (§3), not a threshold.

Reproduce: `reports/item3-cap-isolation/injury_arms.py` and the two CSVs beside it.
