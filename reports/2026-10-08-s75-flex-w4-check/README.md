# Study 75's transfer question: what a forced WR flex displaces in his FP book (W4 inputs, outcome-blind, 2026-10-08)

**Why:** study 75 (Addendum 173) found WR_FLEX8 leaning positive in the harness, where the WR displaced mostly TE
flexes (3.6 TE, 1.8 RB of 26). The harness's base flex mix (TE about 60%, RB about 19%) is not his FP book's (TE 54%,
RB 42%, WR about 4%), so what a WR displaces in his real book was unmeasured.

**What ran:** two union runs on the Week-4 inputs with the Week-5 arming (mix, rr, overlap 4, QB cap 5, FP projections,
the cheap +2 block), through the tracked `reports/2026-10-08-s71-flag/w4_union_run.sh`, from the outside reviewer's
flag branch `review/flex-wr-flag-20261008` @ `09e93be1` (UNMERGED; reviewed by the laptop):
- **OFF:** must reproduce the laptop's study-73 flag ack OFF book (`a4ab2839…`) byte for byte, the known-answer gate.
- **FX8:** `--mix-flex-wr-rows 8`.
Only the books' composition is read (the FLEX slot's position): no points, no ranks, no contest results.
Script: `flexwr_w4_check.sh`; verbatim output: `OUTPUT.txt`.

**Result:**

| Book (W4 inputs, W5 arming) | flex WR | flex TE | flex RB |
|---|---|---|---|
| OFF (his W5-style FP book) | 1 | 14 | 11 |
| FX8 (a WR in the flex on the first 8 book solves) | 8 | 9 | 9 |

- The known-answer gate passed. All 8 ruled solves were feasible (one per MIX cell in build order: A1, B, C, A2, twice),
  and 0 were built plain.
- **The forced WRs displaced 5 TE and 2 RB flexes, net.** That is the same TE-first pattern as the harness (3.6 TE /
  1.8 RB), so the transfer concern is smaller than its base mixes suggested.
- 25 of the 26 book rows differ from OFF (path dependence, as in the harness).
- **What this does not say:** anything about points or wins. It is one week's inputs, and it is descriptive only.
