# Class selector and class sleeve: the Week-3 and Week-1 gates, for the reviewer

Laptop agent, 2026-09-28 (10:21 CDT). The operator asked: "Please share your evidence so I can have the review check it."

Everything below reproduces from committed code and private-bucket inputs.
- Numbers are paid entries at each contest's **exact payout ladder**, ranking every book row against the contest's
  real field.
- No dollar figures appear here; `--show-value` prints them locally.

## Code and inputs

**Code:**
- Lab: branch `laptop/two-track-selector-20260927` @ `dd0ce98` (`nfl2.class_selector`, `nfl2.two_track`, the generator's
  `boom_sleeve` hook).
- nfl-predictions (this branch): `reports/lab-handoffs/rehearsal_two_track.py` (selectors, layout, exact-ladder
  scoring) and `reports/lab-handoffs/class_sleeve_gate.py` (sleeve generation and scoring).
- Class model: `scripts/fit_field_class_model.py`.

**Private bucket** (`gs://nfl-predictions-503414-raw/private/rehearsal/`):

| Object | Contents |
|---|---|
| `2026-w03/20260926T153408285093Z-65305f5/` | the Week-3 entered D12800 run dir |
| `2026-w03/contest-details-20260927.json` | the Week-3 ladders |
| `2026-w01/20260913T160405364118Z-e7255e9/` | the Week-1 K90 paid build: 800-row pool, both sidecar banks |
| `2026-w01/contest-details-2026-w01.json` | the Week-1 ladders |
| `class-gates-20260928/class_model_w1w2.json` | sha256 `932b5c4f…`: fitted on the Week-1 and Week-2 Millionaire fields, pre-lock map from Week 1; **used for Week 3** |
| `class-gates-20260928/class_model_w2w3.json` | sha256 `b495c85a…`: fitted on Weeks 2–3, map from Week 3; **used for Week 1** |
| `class-gates-20260928/ownership_sets.csv` | sha256 `10175b0e…`: the Week-3 sets file. Only `--sets` needs it; the tilt is 0, so it changes nothing |

The model files come from:
```
python scripts/fit_field_class_model.py --weeks 1:193028206:151307:2026-09-13T17:00:00Z,2:195648007:153427:2026-09-20T17:00:00Z --map-weeks 1 --out class_model_w1w2.json
python scripts/fit_field_class_model.py --weeks 2:195648007:153427:2026-09-20T17:00:00Z,3:195905122:153769:2026-09-27T17:00:00Z --map-weeks 3 --out class_model_w2w3.json
```

Environment for every command below: `PYTHONPATH=<lab checkout>/src:<this repo>/src`, the nfl-predictions venv, and
BigQuery read access. The scripts write nothing.

## Gate 1: class selector vs mean selector, whole book

Configuration A (production 2690e13e): every contest on the main track, head layout, class-score or mean order, overlap
≤ 7, DST cap 0.25, `--min-proj` 1.0 applied after the fact, tilt 0.

**Week 3** (out of sample for the model: fitted on Weeks 1–2):
```
rehearsal_two_track.py --run-dir <w03 run dir> --season 2026 --week 3 --sets ownership_sets.csv --details contest-details-20260927.json \
  --tilt 0 --class-model class_model_w1w2.json --tail "" \
  --sizes "wildcat:2x2,sat20:1x19,ffwc:4,supersat2:5x12,supersat25hi:17x3,supersat25lo:20x3,milly20:1,sat13:1x3,ffwc18:2" \
  --main-selector mean|class
```
mean:
```
pool 12559 candidates (438 hold a skill player projected < 1.0); ownership slot coverage 1.000; layout: 45 contests, 150 rows = 150 mean + 0 sleeve (tail: [], sleeve by pline; main rows by mean); EXACT payout ladders
PLAN without tilt: paid entries 20; mean points per entry 152.22; Millionaire best 163.5 (finish 14032), rows >= min-cash 1
  by contest type: ffwc 0, ffwc18 0, milly20 1, sat13 0, sat20 6, supersat2 2, supersat25hi 11, supersat25lo 0, wildcat 0
```
class:
```
pool 12559 candidates (438 hold a skill player projected < 1.0); ownership slot coverage 1.000; layout: 45 contests, 150 rows = 150 mean + 0 sleeve (tail: [], sleeve by class (model sha 932b5c4ffcc7, map weeks [1], this frame's optimum 138.9); main rows by class); EXACT payout ladders
PLAN without tilt: paid entries 30; mean points per entry 161.88; Millionaire best 165.44 (finish 12212), rows >= min-cash 1
  by contest type: ffwc 0, ffwc18 0, milly20 1, sat13 0, sat20 12, supersat2 3, supersat25hi 9, supersat25lo 5, wildcat 0
```

**Week 1** (out of sample: fitted on Weeks 2–3; the contests actually entered):
```
rehearsal_two_track.py --run-dir <w01 run dir> --season 2026 --week 1 --sets ownership_sets.csv --details contest-details-2026-w01.json \
  --tilt 0 --class-model class_model_w2w3.json --tail "" --allow-unidentified --sizes "milly:57,playaction:20,ffwcq:3" \
  --names-map 'milly=NFL $3.5M Fantasy Football Millionaire [$1M to 1st],playaction=NFL $400K Play-Action [20 Entry Max],ffwcq=$14M 2026 Fantasy Football World Championship Qualifier #7' \
  --main-selector mean|class
```
mean:
```
NOTE: our entries were not identified; the fields include them and the ENTERED line is skipped
pool 800 candidates (13 hold a skill player projected < 1.0); ownership slot coverage 0.851; layout: 3 contests, 74 rows = 74 mean + 0 sleeve (tail: [], sleeve by pline; main rows by mean); EXACT payout ladders
PLAN without tilt: paid entries 31; mean points per entry 159.94
  by contest type: ffwcq 0, milly 17, playaction 14
```
class:
```
NOTE: our entries were not identified; the fields include them and the ENTERED line is skipped
pool 800 candidates (13 hold a skill player projected < 1.0); ownership slot coverage 0.851; layout: 3 contests, 74 rows = 74 mean + 0 sleeve (tail: [], sleeve by class (model sha b495c85af1df, map weeks [3], this frame's optimum 139.0); main rows by class); EXACT payout ladders
PLAN without tilt: paid entries 8; mean points per entry 142.66
  by contest type: ffwcq 0, milly 6, playaction 2
```

## Gate 2: the class sleeve (lineup-shape constraints on half the boom visits)

```
class_sleeve_gate.py --run-dir <run dir> --class-model <model> --season 2026 --week 3|1 --milly-contest 195905122|193028206
```
Week 3 (model `w1w2`):
```
week 3: frame optimum 138.87; projection band 122.7-129.8; QBs banned 11; map weeks [1]
boom        rows  200; realized mean  116.0; >= Milly p90 (161)   1.5%; >= p99 (188)  0.50%; >= 193  0.50%; >= 175   0.5%; best 201.3
boom:class  rows  200; realized mean  138.4; >= Milly p90 (161)  19.5%; >= p99 (188)  1.50%; >= 193  1.50%; >= 175   9.0%; best 196.0
```
Week 1 (model `w2w3`):
```
week 1: frame optimum 138.99; projection band 122.9-130.6; QBs banned 12; map weeks [3]
boom        rows  200; realized mean  133.0; >= Milly p90 (179)   3.5%; >= p99 (209)  0.00%; >= 193  1.00%; >= 175   4.0%; best 205.5
boom:class  rows  198; realized mean  138.0; >= Milly p90 (179)   7.6%; >= p99 (209)  0.00%; >= 193  3.54%; >= 175   9.1%; best 201.2
```

## Reading, and what the reviewer should check

1. **Class selector: Week 3 favours class** (30 vs 20 paid; 161.9 vs 152.2 per entry). **Week 1 reverses it
   hard** (8 vs 31; 142.7 vs 159.9).
   - The Weeks 2–3 model's coefficients carry Week 3's winning shape (QB salary −0.82, TE salary −0.80, a second TE
     +0.62 as standardized top-1% coefficients), and Week 1 did not reward it.
   - Two weeks, one each way. The mean selector is the one with independent historical support (L09 and L10:
     +13% and +21% tickets over EMAX on 72 slate-banks each).
2. **Class sleeve: better lineups in both weeks** (Week 3 mean 138.4 vs 116.0 and 1.5% vs 0.5% at 193; Week 1 138.0
   vs 133.0 and 3.5% vs 1.0% at 193).
   - The Week-3 figure is circular, because the shape was read off Week 3's top finishers. Week 1 is the
     out-of-sample one.
3. **Caveats to check:**
   - (a) The Week-1 pool is small (800 rows, lev 160 / boom 640) and was built at the e7255e9 lab pin, before the
     availability repair.
   - (b) Our Week-1 entries could not be matched in the fields: they came through a vetting path. So Week 1's fields
     include our own 80 entries, which is negligible against 832k, 159k and 5k, and the same for both arms.
   - (c) The Week-3 class model is trained partly on Week 2, the backup-QB defect week.
   - (d) The class model's `proj_pct` map uses prior clean weeks' field ratio distributions (`fit_field_class_model.py`
     docstring).
   - (e) Week-3 tickets use the head layout exactly as configuration A enters them. The earlier 33 vs 22 used class
     seats on a tail track; the direction is the same.

**Laptop's recommendation (the operator decides):** the mean selector for every contest, over a pool whose boom
visits are half class-sleeve. The class selector stays off.
