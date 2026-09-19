# D6400 selection tradeoff: a small tail gain survives, weakened by availability risk

The new search finds a **small modeled 220+ improvement**, not the large retrieval breakthrough we want. Allowing a visible expected-score cost produces one replacement whose benefit survives fresh worlds under both simulator components. Its whole-book P220 gain is **0.085 percentage points** under the all-active assumption, falling to **0.035 points** when the fixed participation probabilities are applied. The latter interval includes zero. The first 40 entries, including the Millionaire lineup, are unchanged.

This is an executed comparison on the completed **6,399-candidate D6400 corpus**, with the fresh, legal **97-lineup v4.3 replacement book** as control. No live book, upload, selector configuration or current NFL outcome was changed/read. The projection release and host-tool review remain complete independently of this experiment.

## Frozen comparison and evidence

The [protocol](2026-09-19-selection-loss-frontier-protocol.md) permits one exchange, searches 128 unused candidates against all 97 outgoing positions, and measures gains at fixed expected-maximum loss allowances of 0, 0.25, 0.5, 1 and 2 points. It imposes no universal component/prefix improvement rule. Current role/status and house-legality checks admit **3,366 candidates**. Both proposed alternatives preserve legal unique K97 books and the other delivered positions.

All original source files are authenticated; original selection order and stored candidate means reproduce exactly. Source frame and two selection banks match the morning D160 archive byte for byte. The actual v4.3 rehearsal replaced 46 rows using the newer OUT statuses; this controls the present comparison. The saved forecasts still come from the **15:09:52.915006Z** projection batch, not tonight's newer means.

Proposal consumer `cacab6f0` froze before effects. The complete packet, including all 12,416 evaluated exchanges, was frozen at SHA `cd604b8fc0c90c27043bd04d2f324acfbe124987d467a480acde36210a657143` before fresh audit construction. The [summary](reviews/evidence/2026-09-19-d6400-frontier-proposal-summary.json) retains every selected budget and book; complete costs remain in the bound packet. The 0.25–2 point allowances all choose the same proposal: relaxing these budgets further does not change this bounded search's answer.

The [audit constructor](reviews/evidence/2026-09-19-d6400-fresh-audit-banks.py), frozen at `10a8c03d`, reconstructs **both** original 429×10,000 selection banks exactly before generating new incumbent/hsim seeds **18260919 / 19260919**. It retains the original historical training/cache identities and blocks provider queries/current-season outcome access. Reconstruction and new audits completed in 23 seconds; the known hsim divide warning did not produce nonfinite scores. The [reader](reviews/evidence/2026-09-19-d6400-frontier-read.py), frozen at `8bcf8b10`, reports every proposal, both components, both availability assumptions and all 20 predeclared regions. It uses independent availability seed **20260919061** and the previously fixed map. [Full results](reviews/evidence/2026-09-19-d6400-frontier-result.json), [audit identities](reviews/evidence/2026-09-19-d6400-fresh-audit-receipt.json).

## Whole-book results

Differences below are alternative minus the fresh v4.3 control. Intervals measure Monte Carlo error under fixed simulation laws; they do not describe uncertainty about actual NFL efficacy, and are not a multiple-comparison-adjusted winning claim.

| Proposed exchange | Selection P220 gain | Fresh all-active P220 change | Fresh participation P220 change | Participation expected-max change |
|---|---:|---:|---:|---:|
| Rank 57 → candidate 4056; zero-loss budget | +0.045 pp | −0.040 pp | −0.040 pp | −0.00368 points |
| Rank 94 → candidate 3623; budgets 0.25–2 | +0.095 pp | **+0.085 pp** | **+0.035 pp** | −0.02113 points |

For the rank-94 proposal, the all-active P220 interval is **[+0.034, +0.136] pp**. Both component point estimates are positive: incumbent **+0.070 pp**, hsim **+0.100 pp**. Mean expected maximum changes by only +0.00160 points, with an interval spanning zero. The labelled winner-score proxy increases by +0.000256 in the equal mixture.

Under participation, the P220 interval becomes **[−0.005, +0.075] pp**, with component changes +0.020/+0.050 pp. Expected maximum changes by **−0.02113 [−0.04382, +0.00156]** points; the proxy is +0.000052 with an interval spanning zero. The incoming lineup includes **Questionable Chris Olave**, whose frozen map probability is 0.6556. That uncertainty explains why assuming everyone plays overstates this particular candidate's modeled appeal. This is a reason to quantify its cost, not a new blanket Q/D exclusion rule.

The zero-loss proposal does not carry its selection-bank P220 gain into either fresh component; both all-active component differences are −0.040 pp. This is an example of why a tiny optimization gain on the same worlds is insufficient evidence by itself.

## Allocation and recommendation

The rank-94 exchange affects the **80–95 contest block**. Under the participation mixture, that block gains +0.291 expected-max points and +0.180 pp P220, while the whole book gains much less because stronger entries elsewhere already cover many favorable worlds. The first 40 entries are exactly unchanged in every audited law and metric. This experiment therefore does not improve the top spreadsheet rows or the Millionaire allocation.

Keep the rank-94 proposal as a small research/shadow candidate, with its Questionable-player risk visible. It is not a material system-wide gain or a reason to interrupt the cleared host release. This result also does **not** justify saying every scoring tradeoff fails: a small fresh-world tail benefit exists, and its size and sensitivity are now measured.

The next higher-value comparisons are the already prepared **full eligible-pool reselection under participation** and **first-delivered promotion** on this actual corpus. They address availability and delivery directly. This one-exchange result does not test coordinated multi-row changes, a larger incoming search, a different forecast law or a newly generated pool; it closes none of those questions. Production's independent numerical replay is requested before any ledger conclusion or adoption claim.

## Portable independent replay

Reader `905503e9` adds configurable data/output paths and bundled winner references, with the numerical calculations unchanged. Every result field except reader SHA and elapsed seconds reproduces exactly. The create-once [publication receipt](reviews/evidence/2026-09-19-d6400-frontier-publication.json) identifies the 19,139,205-byte archive at `gs://nfl-2-506823-lab/research/d6400-frontier-20260919/portable-v1.tar.gz`, generation `1789853952290833`, SHA `cf00b1fa101bac0771fde8594fe7532fa1efe5bb426680aefddb68545ea2d7e9`; download round-trip is exact. It contains authenticated frozen books, audit banks, status evidence, unchanged source frame and expected output; no entry exports. The reader explicitly decodes allowlisted input columns only.

From this research checkout, after verifying and unpacking the archive into a new directory:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/erich/projects/nfl-predictions/.venv/bin/python -X cpu_count=1 reports/reviews/evidence/2026-09-19-d6400-frontier-replay-v2.py --root /path/to/d6400-frontier-portable-v1 --output /path/to/new-replay-result.json
```

Compare the new result to `expected-result.json`, excluding only `reader_sha256` and `seconds`. This is a numerical cross-read; reconstructing the audit laws from training remains the separately frozen stronger check.
