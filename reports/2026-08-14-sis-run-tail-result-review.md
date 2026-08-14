# Review: SIS run-tail (Boom%/Bust%) result

Date: 2026-08-14. **No code was changed. No new outcome was queried.**

---

## 1. The characterisation is accurate, and the failure is decisive

Verified against the result document:

| metric | control | treatment | ratio |
|---|---:|---:|---:|
| q95 pinball | 0.748047 | 0.750678 | 1.003517 |
| q99 pinball | 0.230791 | 0.232606 | 1.007866 |
| **equal q95/q99 mean** | — | — | **1.005691** |

The registered gate required the equal mean ratio strictly below 1.0. It is
1.005691. Marginal preservation passed at `7.1054e-15` against a `1e-10`
ceiling, so this is mechanically valid — a scientific failure, not an
infrastructure one, exactly as described.

**It is also stronger than a marginal null**, which is worth recording:

- CRPS `+0.004768`, whole-slate 95% CI `[+0.001388, +0.008147]` — wholly
  unfavourable;
- q99 pinball `+0.001815`, CI `[+0.000016, +0.003615]` — wholly unfavourable;
- point absolute error `−0.005170`, CI `[−0.010159, −0.000182]` — a real but
  small mean improvement.

Both tail intervals exclude zero. This is not a coin flip that fell the wrong
way; the tail genuinely worsened. Several past closures rested on far weaker
evidence than this one.

The disposition and the decision to move capacity to the TD repaired-reference
stage are both correct.

---

## 2. The result updates one of my own recommendations, and I would now reverse it

I recommended this arm specifically, and the reasoning was:

> every SIS arm tested a central-tendency metric — blocking Points Earned per
> play, blown-block rate, run-defense Points Saved per play — while the
> objective is a tail. Boom/bust is the only tail-shape family acquired.

The implied hypothesis was that the **field class** was the problem: that a
vendor-charted *tail frequency* might behave differently from a *mean*
quantity when the gate is a tail metric.

It did not. Boom/bust produced **exactly the same signature** as every
mean-shaped field before it — point MAE improves, tail proper scores worsen.
And it did so despite being the best-screened candidate available: the
outcome-blind redundancy screen put `rdef_boom_rate` at `r = 0.1922` and
`rdef_bust_rate` at `−0.0827` against the nearest existing features,
substantially more distinct than the `0.4573` pressure column the project had
identified as its most distinct, and far from the `0.8803` that got
pass-defense EPA rejected as redundant.

So the most distinct, most tail-appropriate marginal input available failed the
tail gate with confidence intervals excluding zero.

**That is evidence about the channel, not the field.** A marginal-channel
feature improves the centre and does not reach the served upper tail —
regardless of whether the input itself is a tail statistic. It removes the last
"we have not tested the right *kind* of field" objection to closing the SIS
marginal channel.

**Consequence, and this reverses my pre-forensic exhaustion review:** I would
now close SIS marginal work rather than proceed to the remaining items.

- **Pass rush** (18 columns, `r = 0.4573`) is *less* distinct than boom/bust and
  is a mean-shaped quantity. If the more distinct tail-shaped field failed
  decisively, a less distinct mean-shaped one is a poor bet.
- `pass_on_target` / `pass_catchable` are also mean-shaped.
- **Receiving** and **player grain** remain unretrieved, but as marginal-channel
  inputs they inherit the same prior. Their remaining value is
  **copula-channel** — allocation modulation in the ASOE style — and ASOE
  already occupies that role and was adopted.

The honest position: **SIS's marginal channel is closed on this panel.** What
survives is its copula-channel use, which is already in production.

---

## 3. What this does and does not close

**Closed.** SIS marginal features on the historical panel. Boom/bust was the
strongest remaining candidate by every available pre-outcome measure and it
failed with intervals excluding zero.

**Not closed.** The features themselves — the result correctly says "its source
features remain available for future genuinely distinct mechanisms." A boom-rate
column used to *modulate allocation concentration* is a different mechanism in
a different channel from a boom-rate column added as a player marginal, and the
closure should be scoped to the latter.

**Unaffected.** The TD competitive WR allocation arm. It is copula-channel, it
does not use SIS features, and the capacity reallocation to its Stage R
repaired-reference stage is the correct next use of compute.

---

## Summary

The description is accurate in every particular, the failure is decisive rather
than marginal, and the sequencing decision is right.

The finding worth carrying forward is not the rejection itself but what it rules
out: a tail-shaped input in the marginal channel behaves exactly like a
mean-shaped one. That closes the last open question about SIS's marginal
channel, and it reverses my own earlier recommendation to continue to pass rush.
