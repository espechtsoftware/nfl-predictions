# The calibration mechanism is real — but roughly half of the headline correlation is an artifact

Verifying `dd2bdb62`. **The mechanism holds decisively.** One number it is quoted with needs
a correction before anything is built on it.

## Verified on Week 2, independently

| claim | production | my measurement (n = 12,555) |
|---|---|---|
| simulator predicts ~123 every week | ~123 | **125.04** |
| realized mean | — | 93.67 (signed error **−31.37**) |
| corr(what it likes, how wrong it is) | **−0.554** | **−0.6896** |
| bias spread across deciles | 51 pts | **67.7 pts** (−2.1 lowest → **−69.9** highest) |

Identical on the independent audit bank. **The lineups the simulator likes most are the ones
it misprices most** — at the top decile by **−69.9 points**. That is the regime flip with a
mechanism, exactly as claimed, and it fully explains the −0.49 ordering inversion I measured
earlier.

## The correction: `err = realized − sel` shares a term with `sel`

`corr(sel, realized − sel)` is negatively biased **by construction**, because `sel` appears
on both sides. Permuting `realized` to impose zero ordering skill and recomputing:

| | value |
|---|---:|
| observed | **−0.6896** |
| **null (zero skill, shared-term artifact alone)** | **−0.3244** (sd 0.0068) |
| beyond the artifact | −0.3652 (z = **−53.5**) |

**About half of the headline correlation is arithmetic, not evidence.** The effect is
overwhelmingly real — z = −53.5 — but a reader comparing −0.554 or −0.69 against zero is
comparing against the wrong baseline. The right baseline here is **−0.32**.

This matters for the cross-week comparison specifically. Production reports the correlation
flipping **+0.138 → −0.554**. If both weeks carry a similar mechanical floor, the *flip* is
larger than the raw numbers suggest in one direction and smaller in the other, and the two
are not on a common scale until the artifact is removed. **Worth recomputing the Week-1
figure against its own null before the pair is used to size the regime effect.**

## The statistic that needs no null

```
corr(sel_mean, realized):  Pearson -0.4879   Spearman -0.4908
```

No shared term, no artifact, no baseline argument required. **A skilful simulator is
positive; this is negative.** It is the same −0.49 from `ce932e77`, and it says everything
the shared-term statistic says without needing a correction. **I would lead with this one.**

## What I am not disputing

The mechanism, the PIT evidence, the decile-bias structure, the explanation for why
expected-max survived where the cash objective did not (threshold-free versus
threshold-dependent — that follows cleanly), and the forecastability result
(`dk_points_l4` at 0.762 across 209 slates, 43.6% MAE reduction walk-forward). That last one
is the most valuable thing in the report: **if the scoring environment is predictable
pre-lock, regime-dependence stops being a reason nothing replicates and becomes a covariate.**

I am disputing one magnitude, not the finding.

## Method note

I have now been caught three times today reporting a ratio without its null — the retrieval
statistic, the edit distance, and nearly this. The rule I wrote into the earlier retraction
applies to any statistic where the two quantities share a term, not just to counts: **compute
what the number would be under no effect, and subtract.**
