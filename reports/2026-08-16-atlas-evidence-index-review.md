# Review: ATLAS deployment-set evidence index

Date: 2026-08-16. **No code was changed. No outcome was queried.**

The index is well built — findings, boundaries, immutable hashes and a reviewer
firewall in one place. One correction to my own prior recommendation, one
housekeeping item that follows from it, and three observations on how the
results should be described.

---

## 0. Two corrections to my own reviews

**0.1 Law separation.** Section B is right and my premise was wrong: Phase S
ATLAS and CBWU-OI used the **same five Phase S panels**, not different
simulation laws. My conclusion — that they cannot be ranked against each other —
survives, but for the reason the index gives rather than mine: they measure
**different endpoints**. §2 below develops that, and it is the more useful
distinction.

**0.2 The 54.28 comparator.** In
[2026-08-16-post-cbwu-oi-suggestions.md](reports/2026-08-16-post-cbwu-oi-suggestions.md#L39)
I wrote that "the comparison point is the canonical **54.28/80** disjoint-half
overlap." **That was wrong, and the frozen interpretation amendment correctly
overrode it before the result landed.**

I nearly compounded the error. The index reports canonical disjoint-half
overlap at `65.6852` against bootstrap `61.1252` — the opposite ordering to the
earlier diagnostic's `54.2778` versus `61.6362` — and my first reading of that
was a probable implementation defect, on the argument that bootstrap resamples
share ~63% of their draws and should therefore agree *more* than genuinely
disjoint halves.

That argument holds width constant. **The two designs do not.**

| | old (R0 only) | new (five blocks) |
|---|---|---|
| disjoint half width | 5,000 worlds | **25,000 worlds** |
| bootstrap resample width | ~10,000 worlds | **10,000 worlds** |
| relative half/bootstrap information | 0.5× | **2.5×** |

In the old design each half carried half the information of a bootstrap
resample, so halves agreed less. In the new design each half carries **2.5× the
information** of a bootstrap resample, which more than offsets the independence
penalty. The ordering flip is a designed consequence of sample width, not a
defect. No reconciliation is needed.

## 1. Housekeeping: 54.28 is now stale and load-bearing in at least five documents

The amendment's ruling — that the older figure "is historical context only
because it used a different source width and sampling design" — is correct, but
that number has already propagated:

- [2026-08-14-pre-forensic-exhaustion-review.md:27](reports/2026-08-14-pre-forensic-exhaustion-review.md#L27)
- [2026-08-11-final-preseason-forensic-closure-protocol.md:376](reports/2026-08-11-final-preseason-forensic-closure-protocol.md#L376)
- [2026-08-16-cbwu-oi-correction-and-construction-reframe.md:33](reports/2026-08-16-cbwu-oi-correction-and-construction-reframe.md#L33)
- [2026-08-16-cbwu-book-instability-and-tie-break-opportunity.md:22](reports/2026-08-16-cbwu-book-instability-and-tie-break-opportunity.md#L22)
- [2026-08-16-cbwu-oi-construction-result-review.md:114](reports/2026-08-16-cbwu-oi-construction-result-review.md#L114) — mine
- [2026-08-16-post-cbwu-oi-suggestions.md:39](reports/2026-08-16-post-cbwu-oi-suggestions.md#L39) — mine

Several of those use it as a *standing* characterisation of selector
instability ("about 26 of 80 slots differ under independent evidence"), not as
historical context. Under the new measurement the canonical figure at 25,000-world
half width is `65.6852` — roughly **14 slots differing, not 26.**

**Suggestion:** sweep the citations, or add one line to the simulation-law
ledger recording that any overlap figure is meaningless without its sample
width. This is the same failure mode as the `26e73c5` allocation-unit repair —
a superseded constant still being quoted downstream — and it is cheap to close
now.

The **paired deltas are unaffected** and remain the usable result: both arms in
the new diagnostic share width, indices and seeds, so `−6.5466` bootstrap and
`−4.8148` disjoint-half are valid. **CBWU-OI does select less reproducibly.**

## 2. ATLAS's headline is not a `C` measurement, and should not be read as one

The transfer result is `271.5607 → 282.4947` on **mean exact attainable legal
world quality**, improving in all 270 cells. Strong and clean on its own terms.

But the endpoint is **world quality**, not candidate quality. The exact-P census
review and the CBWU-OI result both established that construction successors
should be scored on **`C`** — and CBWU-OI demonstrated why empirically, gaining
`+5.66` of `C` while moving only `0.30` swaps toward P.

**Nothing yet measures ATLAS's `C`.** The `+10.93` is not comparable to CBWU-OI's
`+5.66`. The index is careful in prose, but the findings-at-a-glance section
places the two close enough that a reader will pair them.

**Suggestion:** carry the endpoint on every construction result in the summary
table itself — *attainable world quality*, *candidate `C`*, *selected `S`*. The
register needs that column more than it needs the law column I previously
argued for.

## 3. ATLAS reduces combination breadth — the opposite sign to CBWU-OI's mechanism

Under the production law:

| reach metric | ratio |
|---|---:|
| exact-roster | 0.9999 |
| stack-core | 0.9997 |
| **player-pair** | **0.9520** (q10 `0.8948`, min `0.7952`) |
| **dominant-game** | **0.9080** |

Against what CBWU-OI established: its `C` gain came with pair reach **+41%** and
stack-core reach **+52%**, achieved *despite* worse player coverage. On that
evidence **combination breadth is the mechanism** for candidate-layer gains.

So ATLAS improves its own endpoint while moving breadth in the **opposite
direction** on the metric shown to drive `C`.

The index draws the right conclusion — pair/game concentration is "the principal
adjustment clue," and the matched-diversity MVP is the licensed response. Two
additions:

1. **Predeclare the prior in the MVP protocol.** On current evidence an ATLAS
   variant that reduces pair reach is *expected* to underperform on `C` relative
   to one that preserves it, even while attaining better worlds. That makes a
   disappointing `C` result confirmatory rather than surprising.
2. **Add a pair-reach floor to the MVP gate.** The frozen gate requires a strict
   pair-*weight* gain, which does not prevent the aggregate reach *ratio* from
   falling further. Reach is the quantity with the demonstrated link to `C`.

## 4. Exact-N decays with book size and fails before production scale

| N | relative primary-coverage change | treatment/control identity overlap | disposition |
|---:|---:|---:|---|
| 1 | +3.53% | 0.44/1 | shadow |
| 3 | **+7.23%** | 1.37/3 | shadow |
| 20 | +1.62% | 14.26/20 | shadow |
| **40** | **−0.05%** | 32.46/40 | **failed/closed** |

Monotone decay after N=3, crossing zero by N=40. **Production submits 80.**

The overlap column explains the decay: at N=40 the treatment already retains 81%
of the control's identities, so there is little room left to differ. Linear
extrapolation is not warranted, but the honest prior for N=80 is negative.

**Suggestion:** predeclare that exact-N is **not expected to transfer to the
80-entry book**, and state what it *is* for — small-field qualifiers and
multi-entry contests at low N, which is a real use case given the weekly mix
includes qualifier entries well below 80. Framing it as a small-book mechanism
from the outset prevents a later N=80 null from reading as a failure of
something never claimed.

---

## 5. Summary

| # | item | priority |
|---|---|---|
| 1 | **Sweep the stale 54.28 citations** (six documents, two of them mine); record that overlap figures are meaningless without sample width | high — cheap |
| 2 | Label every construction result with its **endpoint**; `+10.93` world quality ≠ `+5.66` candidate `C` | high |
| 3 | Add a **pair-reach floor** to the MVP gate; predeclare the breadth-versus-`C` prior | high |
| 4 | Predeclare exact-N as a **small-book mechanism** not expected to reach N=80 | medium |

No blocking issue. The evidence firewall at the end of the index is the right
model and should be kept verbatim in any successor document.
