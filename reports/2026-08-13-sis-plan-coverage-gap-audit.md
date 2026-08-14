# SIS plan coverage: what was purchased, what was retrieved, what was tested

Date: 2026-08-13. **No code was changed.** Warehouse schema audit plus the
account's own authenticated surface inventory. No outcome was queried.

## Answer

**No.** A substantial part of the promising surface is untested, and some of it
is already paid for and sitting in BigQuery unused. One family in the
account's *own* acquisition priority 1 was never retrieved at all.

---

## 1. What the subscription exposes

From the authenticated navigation audit: Player Leaderboards, Player Lookup,
Team Leaderboards, Team Lookup — each with Totals / Rates / Value views across
these families, at **both player and team grain**:

Passing · Rushing · **Receiving** · Pass defense · Pass rush · Run defense ·
Blocking (+ Runs to Gap, + Adjusted Blown Blocks) · Returning · Punting ·
Kicking

Seasons 2015–2025, with week ranges, Split by Game, and filters for coverage
shell, alignment, route, motion, pressure, box count, personnel and formation.

Separately advertised and **not** in this entitlement (correctly flagged in the
inventory, and worth restating since the question was about the plan): injury
data, **weekly projections**, tendency reports, on/off splits,
participation/frame-timer feeds, player/snap projections. SIS NFL Weekly
Projections is a distinct subscription. Note that an independent projection
source is Priority 2 in the standing acquisition doc — so that product is worth
a price check on its own merits, not as part of this plan.

## 2. What is actually in BigQuery

Two tables, **team grain only**, 79 columns each:

| family | in warehouse | columns |
|---|---|---:|
| Passing offense | ✅ | 13 |
| Rushing offense | ✅ | 24 |
| Pass defense | ✅ | 24 |
| Pass rush | ✅ | 18 |
| Run defense | ✅ | 22 |
| Blocking (broad) | ✅ | 20 |
| **Receiving** | ❌ **absent entirely** | 0 |
| Runs to Gap / Adjusted Blown Blocks | ❌ | 0 |
| Returning / punting / kicking | ❌ (deliberate, priority 3) | 0 |
| **Any player grain** | ❌ **nothing** | 0 |

## 3. What has been tested

| arm | fields used | result |
|---|---|---|
| QB line bundle | blocking blown-block rate, blocking PE/play | failed |
| RB run defense | `rdef_points_saved_per_play` | failed |
| Team pass-defense Wide/Slot × Man/Zone | schema screen only | failed at schema gate |
| SIS ASOE | `pdef` attempts composition | in flight |

Three fields tested out of roughly 120 acquired.

---

## 4. Gaps that are already paid for and in the warehouse

These need no new requests. They are sitting in BigQuery.

### 4.1 Boom% / Bust% — the tail-shape fields, entirely untested

`rush_boom_rate`, `rush_bust_rate`, `rdef_boom_rate`, `rdef_bust_rate`,
`pdef_boom_rate`, `pdef_bust_rate`.

Every SIS arm so far tested a **central-tendency** metric: blocking Points
Earned per play, blown-block rate, run-defense Points Saved per play. The
objective is a tail. The RB arm used `rdef_points_saved_per_play` while
`rdef_boom_rate` sat unused **in the same table**, and boom/bust is exactly the
vendor-charted tail quantity that has no free equivalent.

This is the single clearest mismatch between what has been tested and what the
system is optimising for.

### 4.2 Pass rush — 18 columns, never used, despite being the audit's own top pick

The outcome-blind redundancy screen found SIS pressure rate is **the most
distinct team column** (`r = 0.4573` against existing `opp_pressure_rate_l6`),
versus pass-defense EPA at `r = 0.8803` which was correctly refused as
redundant.

The audit identified the least-redundant field, and the tranche-1 arm then used
different fields (blocking). Pressure, hurries, knockdowns and unblocked sacks
remain untested.

### 4.3 Pass-defense value fields beyond EPA

Only `pdef_epa_per_play` was screened for redundancy. `pdef_points_saved_per_play`,
`pdef_paa_per_play` and `pdef_positive_rate` were never screened, so their
redundancy is unknown rather than established.

### 4.4 Passing-offense charting fields

`pass_catchable`, `pass_on_target`, `pass_intended_air_yards`, `pass_pressures`
have never entered any arm. `on_target` and `catchable` are charting judgments
with **no nflverse equivalent** — they separate quarterback accuracy from
receiver drops, which PBP cannot.

---

## 5. Gaps in the plan that were never retrieved

### 5.1 Receiving — the largest gap, and it is in the account's own priority 1

The inventory's acquisition priority 1 reads: *"Pull team passing, **receiving**,
pass defense, pass rush and blocking Value views plus the Totals denominators
at game grain."*

**Receiving was never pulled.** This is an execution gap, not a decision — the
other four families in that sentence are all present.

Why it matters most: **WR and TE account for 23 of the 36 omitted
Millionaire-winner slots.** The single position group where the misses
concentrate has zero SIS coverage. The family carries routes, target quality,
air yards, YAC/contact, yards per route, ADoT and **ADoC**, receiver rating,
Points Earned/PAA/EPA, and **Boom%/Bust%**, with filters for receiver alignment,
coverage shell, route, motion, QB pressure and end-zone targets.

ADoC (average depth of coverage) in particular has no free equivalent and is a
genuinely novel construct.

### 5.2 Player grain — nothing acquired, and it holds the field a screen just closed on

Acquisition priority 2 was *"player passing, receiving and pass-defense Value
plus Totals at game grain."* None was pulled.

This matters beyond volume: **coverage snaps and yards-per-coverage-snap live at
player grain.** The team pass-defense schema screen closed a path because those
fields were absent from the team Totals export — from a grain that was never
retrieved. The conclusion "SIS cannot support a denominator-controlled model" is
not supported by a screen of the one grain that was tried.

### 5.3 The four priority-1 filtered views — one attempted, three not

The inventory's own table lists four priority-1 filtered views. Only the third
was attempted (and failed on schema):

1. QB passing split by clean pocket / pressure × man/zone — **not attempted**
2. Receiver value/volume by man/zone, alignment, coarse route family — **not attempted**
3. Team defensive coverage-shell deployment — attempted, schema gate failed
4. *(Runs to Gap / ABB are priority 2 by design)*

The inventory states the distinct content is in the splits, not the broad
totals. Only broad totals have been tested, and every one of them failed.

---

## 6. What is correctly deprioritised

To be clear about what is *not* a gap: returning, punting and kicking are
priority 3 by design and NFL Classic has no kicker slot. Runs to Gap and
Adjusted Blown Blocks are priority 2, explicitly gated behind the broad
blocking audit. Not bulk-testing every column is correct discipline — the
multiple-testing cost is real.

The distinction that matters is between **deliberately deferred** and **never
noticed**. Items 4.1–4.4 and 5.1–5.2 are the second kind.

---

## 7. Recommended order

1. **Test boom/bust from the existing tables.** Zero acquisition cost, and it
   is the tail-shape field for a tail objective. Pair it with pass-rush
   pressure (4.2), which the audit already flagged as most distinct. One
   compact predeclared bundle, gated score-free on q95/q99 pinball rather than
   MAE — per the standing metric discipline.
2. **Retrieve team Receiving.** It is in the account's own priority 1, it is
   32 rows per week, and it covers the position group carrying most of the
   misses. Do this before any further filtered view.
3. **Cost one player-grain filtered query** — a single team-season for pass
   defense filtered to one alignment — to replace the player-grain budget
   *assumption* with a *number*, and to establish whether coverage snaps are
   retrievable. This directly determines whether the schema-gate closure was
   about SIS or about one export view.
4. **Then the receiver split view** (priority-1 item 2), which is where the
   inventory says the distinct content lives.
5. Leave Runs to Gap, ABB and special teams where they are.

One process note: the acquisition plan, the warehouse contents and the tested
fields have drifted apart. A short standing table — family × grain × acquired ×
tested — kept current in the intake report would have made this gap visible
without an audit.
