# PREREG-L10 result: five per game (QB+3 buildable) against the live cap of 4

Laptop agent, read once on 2026-09-28 (05:41 CDT). Frozen lab `laptop/l10-maxgame5-20260927` @ `8b867f8`; every result line
carries identity `8b867f8`, not dirty. 72 of 72 slate-banks (banks 1170–1171), 0 errors, run on the laptop. The
primary selector is MEAN, as designated by the L09 read. Result files: lab `laptop/l10-results-20260928`
(`results/l10/`).

## Reader output (verbatim)

```
slate-banks read: 72 (expected 72); satellite selector from L09: MEAN

K144
             tickets89  tickets95  t89_2023  t89_2024    mean    best  share_above_best    qb3    mg5
CAP4 EMAX        871.0      412.0     370.0     501.0  118.98  188.75           0.01638  0.000  0.000
CAP4 MEAN       1052.0      507.0     495.0     557.0  122.66  187.02           0.02313  0.000  0.000
CAP4 PL160      1078.0      530.0     486.0     592.0  122.37  187.12           0.02350  0.000  0.000
CAP4 PL170      1063.0      527.0     489.0     574.0  122.04  186.65           0.02445  0.000  0.000
CAP4 PLF89      1071.0      521.0     497.0     574.0  122.61  187.26           0.02211  0.000  0.000
CAP4 COVF89      824.0      395.0     349.0     475.0  117.05  188.79           0.01576  0.000  0.000
CAP5 EMAX        858.0      391.0     356.0     502.0  119.05  187.80           0.01643  0.055  0.630
CAP5 MEAN       1035.0      499.0     475.0     560.0  123.08  185.15           0.02406  0.021  0.356
CAP5 PL160       976.0      478.0     444.0     532.0  122.21  183.01           0.02790  0.041  0.540
CAP5 PL170       954.0      469.0     429.0     525.0  122.00  182.76           0.02768  0.048  0.590
CAP5 PLF89      1026.0      490.0     458.0     568.0  122.82  183.25           0.02734  0.032  0.458
CAP5 COVF89      828.0      396.0     354.0     474.0  117.76  186.63           0.01882  0.030  0.513

K40
             tickets89  tickets95  t89_2023  t89_2024    mean    best  share_above_best    qb3    mg5
CAP4 EMAX        264.0      145.0     119.0     145.0  120.69  178.94           0.04281  0.000  0.000
CAP4 MEAN        343.0      171.0     175.0     168.0  124.92  174.45           0.05420  0.000  0.000
CAP4 PL160       329.0      162.0     161.0     168.0  124.18  173.02           0.06631  0.000  0.000
CAP4 PL170       312.0      151.0     154.0     158.0  123.87  172.08           0.06829  0.000  0.000
CAP4 PLF89       336.0      172.0     169.0     167.0  124.57  173.63           0.06077  0.000  0.000
CAP4 COVF89      244.0      126.0     100.0     144.0  118.85  177.62           0.05001  0.000  0.000
CAP5 EMAX        258.0      138.0     114.0     144.0  120.75  178.80           0.04226  0.070  0.732
CAP5 MEAN        323.0      159.0     153.0     170.0  124.95  172.42           0.06410  0.027  0.391
CAP5 PL160       301.0      142.0     142.0     159.0  124.20  171.06           0.06917  0.056  0.603
CAP5 PL170       284.0      137.0     129.0     155.0  123.87  170.29           0.07451  0.066  0.670
CAP5 PLF89       317.0      160.0     147.0     170.0  124.58  171.91           0.06772  0.042  0.514
CAP5 COVF89      236.0      115.0      93.0     143.0  118.79  175.37           0.04900  0.040  0.662

pool oracle mean CAP4 203.15 vs CAP5 203.08; pool >= F89 share 0.0506 vs 0.0509

DECISION (satellite line, K144, selector MEAN): CAP5 1035 vs CAP4 1052 (-1.6%); seasons (CAP4, CAP5) {2023: (495, 475), 2024: (557, 560)}; paired 28-33
  -> CAP5 NOT FLIP-ELIGIBLE (live cap 4 stands)
REPORTED (Millionaire line, K40 EMAX share of field above book best; lower is better): CAP4 0.04281 vs CAP5 0.04226; CAP5 better on 30 of 72 slate-banks
```

## What it means

1. **CAP5 NOT FLIP-ELIGIBLE: the live `MAX_PER_GAME=4` stands.**
   - The cap-5 pools do build the shapes: 36% of the MEAN book has 5 from one game, and QB+3 appears (2–6% of rows).
   - They do not win more tickets: 1,035 vs 1,052 (−1.6%), paired 28–33.
   - The field-lift pattern (`reports/2026-09-27-laptop-critique-of-the-week4-plan.md` §3d) does **not** carry into
     our pipeline. Critique point 5 is not borne out.
   - The Millionaire line is a wash (K40 EMAX share above best 0.0428 vs 0.0423).
2. **MEAN beats EMAX again on independent banks.** At CAP4, K144: 1,052 vs 871 tickets (+20.8%); 2023 495 vs 370,
   2024 557 vs 501.
   - Paired 37–28–7. This is descriptive; L10's frozen rule is about the cap.
   - L09's banks gave +13.3% and 30–32. Pooled over the two panels, MEAN wins 67 slate-banks and loses 60.
   - The direction of the Week-4 mean track is supported twice. It is lumpy week to week.
3. **P(≥line) arms against MEAN at CAP4:** PL160 +2.5% and PLF89 +1.8%. That is still under L09's 5% bar and
   consistent with L09. MEAN stays.
