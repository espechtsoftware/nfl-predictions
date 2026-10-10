# New lineup-rule ideas from your real Weeks 1–4 fields (2026-10-10)

**For:** Erich. Your request this morning: "Use the tools you have available (neo4j, bigquery, etc) and suggest any other lineup
selection ideas." Written by the outside reviewer. The numbers come from BigQuery: every main-slate entry of your Weeks 1–4
contests, 1.66 million lineups across 86 contests. An agent tabulated them, and I re-computed two of the headline rows
independently with my own query; they match exactly. Neo4j was not reachable from this session. **Aggregates only**: no
usernames, no stakes.

## Read this first

- **These describe winners after the fact.** They show what the top 1% / top 0.1% of real lineups looked like, not that building
  that way before lock wins more. Each idea needs the usual test (the harness, a fresh draw) before you use it.
- **Only patterns that point the same way in all four weeks are listed as ideas.** About 33 features were screened. Chance alone
  makes a feature 4-for-4 about one time in eight, so roughly 4 of these could be luck. W1 was a high-scoring week that
  dominates the top tail; every number is shown per week.
- **Already tested and closed** (not repeated here): the shapes, the stacking variants, the QB and player caps, overlap, the
  ownership term and caps, price rules, stars-and-scrubs, the full game stack, upside objectives, and the regulars' habits.
  The floor (106) and the recency fade (109) are running today.

## The ideas, strongest first

Each row reads W1 / W2 / W3 / W4. The top 1% is set against the whole field; "ours" means your 535 real entries.

### 1. No low-owned players at all (instead of "at most one")
| | Field | Top 1% | Top 0.1% | Ours |
|---|---|---|---|---|
| No skill player at ≤ 5% ownership | 17.7 / 14.4 / 19.3 / 24.1% | 34.0 / 26.9 / 31.0 / 32.7% | 33.1 / 23.4 / 30.6 / 39.4% | 10.0 / 1.0 / 7.4 / 90.3% |

- Top lineups were about **2× as likely** to have no player at 5% or below, in every week (odds ratio 2.4 / 2.2 / 1.9 / 1.5).
- **The same holds on Fantasy Points' pre-lock numbers** (Week 4, the only week with FP ownership stored): zero players under 3%
  in 45% of the field, 56% of the top 1% and 64% of the top 0.1%.
- **The gap sits in low-owned $5,000–6,900 players**, not in the expensive ones.
- **Your live rule** allows one player under 3%. The idea: allow **none**. Never tested (study 91 tested "at most one").
- **Cost to test:** a harness study (about 40 minutes). In production it is a small change: today the setting only takes 1.

### 2. The cheap block only on *popular* punts
| | Field | Top 1% |
|---|---|---|
| At least one sub-$4,000 player at > 5% ownership | 48.3 / 43.1 / 33.8 / 47.3% | 66.5 / 90.0 / 78.5 / 77.0% |
| At least one sub-$4,000 player at ≤ 5% ownership | 28.2 / 39.8 / 29.7 / 23.2% | 16.3 / 24.7 / 22.5 / 20.7% |

- **Cheap players helped when they were the popular value plays,** not the obscure ones. Your book leaned the other way in
  Weeks 1–3: fewer popular punts than the field and more low-owned ones.
- **Caution:** each week one heavily played punt drives most of it. With that player removed, it survives only in W1 (and
  weakly in W3).
- **The idea:** the cheap +2 block counts only punts projected at 5%+ ownership. A variant of your cheap-block trial, not a new
  rule.

### 3. The QB from the slate's top-3 game totals (not just the top game)
| | Field | Top 1% | Top 0.1% | Ours |
|---|---|---|---|---|
| QB from a top-3-total game (ties included) | 62.3 / 58.9 / 45.4 / 49.3% | 77.5 / 65.4 / 72.6 / 75.8% | 84.9 / 63.8 / 77.8 / 85.1% | 55.0 / 48.5 / 45.1 / 61.0% |

- Top lineups' QBs came from the highest-total games in every week (odds ratio 2.1 / 1.3 / 3.2 / 3.3).
- **Your QBs were at or below the field** in Weeks 1–3.
- **It is not "chase the top game":** a QB from the top **2** games reversed in W3 and W4.
- **Earlier related tests:**
  - forcing full stacks into the top games was worse (studies 43 and 102);
  - a QB-only restriction to the top 3 is softer, and untested.

### 4. Never a QB with his own defense
| | Field | Top 1% | Top 0.1% |
|---|---|---|---|
| QB + his own team's DST | 5.5 / 5.4 / 3.8 / 5.1% | 2.2 / 3.4 / 1.0 / 2.1% | 1.0 / 1.6 / 0.6 / 1.1% |

- About half as common at the top, in every week.
- **Your book barely builds it** (5% of W1 entries, 0% in W3–W4), so a hard ban costs almost nothing. It is a hygiene rule with a
  small effect.

### 5. Use at least $49,500 of salary
| | Field | Top 1% | Ours |
|---|---|---|---|
| Lineup salary under $49,500 | 5.3 / 4.6 / 3.5 / 3.7% | 3.7 / 3.8 / 1.8 / 3.0% | 11.3 / 8.2 / 2.5 / 5.2% |

- **Top lineups left money unspent less often in every week.** Your entries left it more often than the field in Weeks 1–2.
- **Today's floor is $49,000.** The only earlier test (August, an old build) removed the floor and read neutral. Raising it is
  untested.

## Two signals that cut against live rules (for your awareness)

- **The one-TE limit.** A second TE in the FLEX was **more** common among top lineups in 3 of 4 weeks:
  - field 21.6 / 17.3 / 39.0 / 35.2%;
  - top 1% 16.2 / 41.3 / 54.8 / 39.5%;
  - W1 went the other way.
  - The remove-one-rule study you asked for (last today) tests dropping the TE limit, so this gets its proper test there.
- **The RB version you adopted this morning.** In the real fields, a favored QB's lineup with his own RB was more common at the top
  only in W1:
  - W4's top 1% rarely had it (4% vs 21% of the field);
  - the samples are small and after the fact;
  - you adopted it on two harness reads, so nothing changes. Sunday's results will show it live.

## Not suggested

- **A cap on total ownership per lineup.** The top lineups were chalkier than the field in W1–W3 and much less chalky in W4. That
  argues for a mix of chalky and contrarian lineups, which your shape mix already is.
- **Five from one game, or two bring-backs.** These helped only in W1 and W3; the 200+ profile and study 102 already showed it.

## What I'd suggest testing, in order

1. **No low-owned players (idea 1).** The most consistent signal, and a one-setting change once the setting allows 0.
2. **QB from the top-3 totals (idea 3).**
3. **The popular-punt cheap block (idea 2).**

Ideas 4 and 5 are cheap enough to fold into one "hygiene" arm (no QB with his own DST, at least $49,500).

Today's machine time is booked through about 17:30: the floor, its re-check, the recency fade, the per-position floors and the
rule-removal study. So these are **Week 6 candidates** unless you want one of them moved ahead today.
