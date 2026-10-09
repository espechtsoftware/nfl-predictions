# His live Week-5 version, replayed on this season's real contests (10-09)

**His request** (relayed): "can we run that version against this season using real info?"

**This is IN-SAMPLE, not a test.** Weeks 1–4 are the weeks whose real-field winners prompted the rule (the TE and
low-ownership findings came from them). A lift on them is the expected direction, not evidence that the rule works. It is
descriptive; nothing decides on it.

**What was built** (`replay.py`, the money gate's machinery; summary `replay_summary.json`; dollars private):
- Each week's archived Saturday + T-70 runs, union_reselect at integration with the Week-5 lab pin and PYTHONHASHSEED=0.
- The week's real contests (Week 4 as entered), laid out with enter_layout's head layout.
- Every lineup placed in the real field with our real entries removed, DraftKings' tie split and the real payout ladders.
- **The arms:**
  - **T50:** his package of 10-06 at a 50% player cap (the money gate's PKG4-rr; the mix, overlap 4, round-robin, the QB cap by
    share), without the cheap +2 block (not built for these weeks; it is the same in all three live variants);
  - **PKG:** + the 35% cap + the ownership cap (+15 points);
  - **PKGRR:** + at most one TE and one sub-3% player per lineup (what is armed for Week 5);
  - **Entered:** what he entered.
- **Weeks:**
  - **Week 4** is the faithful week: Fantasy Points' projections and projected ownership.
  - **Week 3** is approximate: our own T-70 model and our own Saturday ownership model. That model rates 262 of 316 pool
    players under 3%, so the low-ownership limit binds much harder there than on Fantasy Points' numbers.
  - **Weeks 1–2** cannot be built: there is no point-in-time ownership file.

## Week 4 (the faithful week), his limited-entry contests (151 entries)

| | Mean finish percentile | Top-1% | Top-10% | Cashes | Big wins | Return (× fees) |
|---|---|---|---|---|---|---|
| Entered | 45.0 | 0 | 6 | 2 | 0 | 0.19 |
| T50 | 53.7 | 1 | 8 | 2 | 0 | 0.19 |
| PKG | 55.4 | 1 | 13 | 3 | 0 | 0.29 |
| **PKGRR (armed)** | **58.7** | **3** | **20** | **6** | 0 | **0.57** |

## Week 3 (approximate), his limited-entry contests (203 entries)

| | Mean finish percentile | Top-10% | Cashes | Return (× fees) |
|---|---|---|---|---|
| Entered | 36.5 | 7 | 1 | 0.09 |
| T50 | 43.7 | 7 | 0 | 0.00 |
| PKG | 40.8 | 5 | 1 | 0.09 |
| PKGRR | 41.4 | 7 | 0 | 0.00 |

The Millionaire (one or two entries a week): no cash in any rebuilt arm. The entered Week-4 book cashed once there, which
is why the entered book's pooled return (0.27) is above the rebuilt arms'.

## Reading

- **Week 3 and Week 4 are not the same rule in practice.** On Week 4's Fantasy Points ownership the low-ownership limit
  barely binds (the rule acts as "no tight end in the flex"). On Week 3's own-model ownership it binds hard (262 of 316 pool
  players under 3%). Read them apart.
- **The counts are small and there are no big wins**, so the finish percentile and the top-10% counts are the readable
  measures. The returns rest on a handful of cashes (6, 3 and 2 in Week 4).

- **On the faithful week, the armed version finished best by every measure:** higher finishes, more than twice the top-10%
  finishes of the 50% book, three times the cashes, and three times the return. The package alone sat in between.
- **Week 3 is a wash** (all three within 3 percentile points), on approximate inputs.
- **No big win in any version.** Two weeks, partly in-sample: this is a consistency check, not proof.
