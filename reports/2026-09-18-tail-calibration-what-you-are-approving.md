# Tail calibration: what you would be approving

Companion to `reports/2026-09-16-prereg-tail-calibration-DRAFT.md`, written in plain language for the operator.
Prepared 2026-09-18 at his request; **nothing has been signed, frozen or run.** The draft becomes PREREG-101 only after
he answers the three questions in the last section.

## The problem, in one paragraph

The simulator plays each slate out tens of thousands of times to guess how lineups will score. Checked against 65 real
slates, it is roughly right about ordinary outcomes and badly wrong about big ones. It claims the best lineup in your
entered book breaks 220 points about 9 % of the time; the true rate is about 3 %. The pool it selects from is only
1.6 times too optimistic, while the selected book is 2.8 times too optimistic. Selection is amplifying the error,
because the lineups that look best are the ones leaning hardest on the scenarios the simulator handles worst.

## Why this and not another selector

Nine different ways of ranking lineups have already been tested and closed: expected-max variants, tail-seeking
objectives, ownership tilts, vendor data, learned scores, a decision-focused reranker. They either failed or made
things worse. The measured conclusion was that there is no ordering signal left to extract from the information we
have. So this proposal does not change how lineups are ranked. It changes how much weight the simulator's extreme
imagined scenarios carry in the first place.

## How the fix works, and why it cannot cheat

Each simulated scenario gets a weight. Scenarios of a kind that historically produced more real top scores than the
simulator predicted get weighted up; kinds that produced fewer get weighted down. The weights are fitted only on
seasons strictly earlier than the season being tested, and they are capped so no scenario can be weighted up more than
fivefold or down more than fivefold. Everything else is held identical: same lineup pool, same scenarios, same seeds.
Only the weights differ between the arms.

Three arms run side by side. The current money path as the control. The reweighted version. And a third that simply
deletes the most extreme 10 % of scenarios, which exists to answer an awkward question honestly: if the reweighted
version wins, is it really calibration, or is it just "pay less attention to the tail"? If the crude version wins
equally, we adopt the crude version and drop the clever one.

## What happens on each outcome, decided in advance

- **It works, and the diagnostics agree it is calibration.** It goes into a *shadow* book in a later week, scored
  against reality without ever touching an entry of yours, before anyone proposes adopting it.
- **It works, but the crude tail-deletion works just as well.** The crude rule is the candidate instead, same shadow
  path. We do not get to claim the sophisticated explanation.
- **It does not work.** We record that the simulator's tail cannot be repaired this way and stop selector and
  simulator-law work on this engine entirely. The remaining levers for the points program become supply and contest
  choice, which is a real and useful answer even though it is a negative one.

That third branch is the reason for the whole exercise being frozen up front. A failure has to be allowed to close the
line of work, and it only can if nobody may move the goalposts after seeing the result.

## Cost and timing

About $230 of lab compute, roughly eight hours across two lanes, plus about a day of my work to build the reader and
runner. It runs on the lab project, not production. It cannot start until PREREG-099 finishes, because that bank owns
the workstation cores and is currently the critical path. Nothing here touches Week 2 or any entered book.

## The three things you would be deciding

1. **The gates, as written.** The scenario bins, the fivefold weight cap, and the primary success test: the reweighted
   arm must beat the control on the weekly best-lineup score, with a bootstrap lower bound above zero, every bank
   non-negative, and at most one season going the wrong way. Approve as-is or amend before any code runs.
2. **Whether 2019 may be used as training-only data.** The method needs earlier seasons to fit weights from, so 2021
   has nothing to learn from unless 2019 is added. Nothing would ever be evaluated on 2019; it only feeds the fit.
   This is a lab-rules question because 2019 is a development season.
3. **Whether it waits for PREREG-099 or pre-empts it.** My recommendation is to wait. PREREG-099 is already behind and
   pre-empting it would cost more than this gains.

## My recommendation

Approve all three as written, after Week 2 settles. The gates are conservative, the cost is small, and the branch where
it fails is worth as much as the branch where it works, because it would close a line of work we have already spent
months on.
