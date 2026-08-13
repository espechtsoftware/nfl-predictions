# SIS alignment sample operational scope repair

Date: 2026-08-13. Frozen before observing any accepted sample artifact or row.
This repairs the acquisition scope after two fail-closed attempts spent six of
the immutable 12-query ceiling. It does not change the game, teams, players,
volume fields, mapping, thresholds or outcome-blind decision.

The original protocol requested Left Slot (`2`) and Right Slot (`5`) as two
separate Receiving Totals submissions, then explicitly summed both into one
receiver `Slot` bucket before normalization. To remain within the original
ceiling without resetting the durable counter, submit values `2` and `5`
together in one normal UI request and label that artifact `slot`. This produces
the same additive Routes denominator used by the frozen calculation. The
remaining scope is exactly six Submit requests:

1. receiver Left (`1`);
2. receiver Slot (`2`,`5`);
3. receiver Right (`6`);
4. defender LCB (`1`);
5. defender RCB (`2`); and
6. defender SCB (`3`).

No other scope or decision changes. The route must block automatic page/tab
refresh queries and increment the durable provider counter only for these
visible Submit requests. All six artifacts and exact submitted filter arrays
must validate before the concentration calculation runs.

