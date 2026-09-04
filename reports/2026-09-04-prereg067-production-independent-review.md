# PREREG-067 / experiment 096 production independent review

Date: 2026-09-04 UTC

Disposition: **the sealed result is reproduced exactly and is non-passing; the
compact linked-beneficiary rescue closes with no dose, priority-law, or
sleeve-size search.**

## Independent replay

Production ran the exact bound reader over the three registered efficacy runs:

```text
scripts/prereg067_report.py
  096b700r1-20260904T210529Z
  096b701r1-20260904T210811Z
  096b702r1-20260904T214843Z
```

The clean binding checkout was commit
`89822dea8976695ff8d1c40bf034650bb9a6339c`. Runtime imports were forced to
that checkout's `src` tree rather than the canonical virtual environment's
editable lab-main path. The reader SHA-256 was
`3a12322b22929fb1ef7a04eaf53007bdd234019085bd72f64327b84e694cb160`.
Its four pins were the frozen source
`b71dbbcb8da62ef7ae50226c9035ed333f7a3ce1`, image
`sha256:486dce554eb64a3e99a3662474b4a7780e920d81a5e96175f517e7af5b0b14da`,
gate run `096m700r1-20260904T204546Z`, and gate-receipt SHA-256
`19101084bf6ef1d4d4872521971fddbc35319851a9a1d4897a0c4302b178f570`.

The reader exited zero with empty stderr. Production stdout is exactly 58
lines / 6,575 bytes and has SHA-256
`3053346f42e0d1c986665036fbf6b2885f58710c35dbe07bb7e1a40a3abe9b80`.
It is byte-identical to the lab's sealed transcript committed at
`bd55ebe57e580f1e9c3742203d2dc41fcf7c8a22`.

## Reproduced result

- Primary K80 winner-CDF proxy, `REDIST_BEN_RESCUE - REDIST_DEMAX`:
  `+0.00109`, family interval `[-0.00034, +0.00286]`, sign-flip `p=0.2703`;
  bank effects `-0.00038`, `+0.00091`, and `+0.00275`.
- The frozen reader's literal result label is **`VERDICT=FAIL`**. Bank 700's
  interval is entirely negative, so this is not merely a positive estimate
  whose pooled interval happens to cross zero.
- Raw K80 weekly maximum is descriptively `+0.221 [+0.007, +0.609]`, but this
  is not the preregistered decision value. Its W/L/T census is 8/10/54.
- Nested raw prefixes are all negative: K3 `-0.491`, K10 `-0.193`, K20
  `-0.204`, and K57 `-0.190`.
- Treatment changes 162/216 slate-bank books. It produces 10 versus 9 weeks
  at 200+, but 14 versus 16 at 194+, and no improvement at 220+.
- Rescued candidates beat displaced incumbents in 80/162 engaged slates. At
  200+ the added/displaced census is 6/3, but at 220+ it is 0/1.
- The held-out proxy is slightly lower for treatment (`0.07637` versus
  `0.07664`), and all reported held-out tail probabilities are also slightly
  lower. This does not support prospective rescue quality.
- Selected-roster inactive-player contamination improves slightly from
  `0.1603` to `0.1584`, so the safety veto does not trigger.

## Terminology cross-check

The lab action note and ledger describe the result as `PRIMARY NULL`, while
the frozen reader says `VERDICT=FAIL`. The numeric evidence and required
routing are otherwise identical. Production accepts the non-passing result
and closure, but recommends a terminology-only ledger/action-note correction
to preserve the reader's literal label, for example:

> **PRIMARY FAIL (pooled interval crosses zero; bank 700 vetoes)**

This correction requires no reread, rerun, or scientific amendment.

## Frozen routing and scope

The compact beneficiary-rescue sleeve closes. Do not search another dose,
priority law, or sleeve size on this panel. The D4 spike/N2 sidecar remains
post-read, non-decision-bearing work and was not mixed into this independent
verification. Experiment 091 remains held. SD-B continues as an independent
diagnostic and no result from this review changes live policy, production
scoring, paid-entry state, graph state, or any cloud execution.
