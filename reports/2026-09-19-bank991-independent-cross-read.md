# Bank 991: independent cross-read matches exactly

The laptop independently ran the frozen amendment-5 reader from lab commit `51d91444b38444c6a9e94366405f2ae6a43a3663`, following the explicit bank991 read authorization. The combined 990+991 transcript is **byte-identical** to production's saved transcript: SHA-256 `cca5d7664358f65e7a87b3391167163cca8f572f08f6059d1cd4ab2f3b48a7d9`. The reader's SHA-256 is `37a08337ffb6bae8883219fa23cff8d31633b9c218d9feb1083d1bdfaf5afd56`.

- Primary candidate supply at 200+: **716/365 = 1.962**, reported 95% interval **[1.846, 2.135]**. The frozen verdict remains **DOUBLING**. Bank991 alone has ratio **1.91579**, clearing the specified 1.5 replication floor.
- Descriptive 220+ supply ratio: **57/34 = 1.676**, interval **[1.167, 2.286]**; bank991 ratio **1.5**. The primary was 200+, so do not relabel this as a confirmed doubling of 220+ supply.
- K80 retrieval, D12800 versus D6400: proxy delta **−0.01384**, negative in both banks (**−0.00201 / −0.02568**). The slate interval **[−0.03772, +0.00628]** is descriptive; season-clustered inference is not estimable from this single-season cohort.
- D6400 versus D3200: combined proxy **+0.00101**, with signs **+0.01418 / −0.01217**. The earlier positive first-bank result did not replicate in bank991.

The larger pool contains more strong realized lineups, but this selector does not reliably recover that additional supply. This supports the priority on better forecasts and retrieval; it does not establish a scoring benefit from increasing dose alone. These are historical 2021 results, not current-week NFL outcomes, and do not identify the best Week2 dose under today's changed inputs.

[Full transcript](reviews/evidence/2026-09-19-bank991-independent-read.txt) and [execution / exact-match receipt](reviews/evidence/2026-09-19-bank991-independent-read.json). The frozen reader was executed once interactively and once to save and compare the exact transcript; no reader, inputs or evaluation rules changed between those invocations.
