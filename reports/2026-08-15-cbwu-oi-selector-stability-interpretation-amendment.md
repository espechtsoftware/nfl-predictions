# Pre-result interpretation amendment: CBWU-OI selector stability

**Frozen:** 2026-08-15 CDT, before the paired selector-stability result was
available. This amendment changes no source, seed, sample, selector, output or
mechanical gate in the frozen protocol.

The source protocol remains
`reports/2026-08-15-cbwu-oi-selector-stability-protocol.md` with SHA-256
`81c8d0ff7750c7781e9c9181699b3bdf397d6161c8bf6e7a91025d233236cb01`.

## Primary comparator

The primary comparison is CBWU-OI versus the canonical pool reconstructed in
the same execution from the same five 10,000-world blocks and measured with
the same stratified split/bootstrap indices. The older canonical R0
disjoint-half overlap of `54.28/80` is historical context only because it used
a different source width and sampling design.

## Required joint presentation

The result report must place these already-observed, fixed-budget construction
facts beside the new score-free stability results:

- mean C: `181.07 -> 186.73` (`+5.66`);
- C weeks >=187/194/200/210: `22/11/8/6 -> 25/18/14/10`;
- C weeks >=220/230/240: `3/1/0 -> 3/1/0`; and
- canonical and OI absolute stability plus paired OI-minus-canonical deltas.

## Interpretation firewall

- Use continuous absolute and paired stability measurements plus the frozen
  descriptive bands. Do not invent a post-result threshold for "materially
  worse."
- Worse stability is evidence of membership/order reproducibility risk. It is
  not a quantitative estimate of C-to-S conversion and cannot explain away an
  absent realized S gain.
- Comparable or better stability strengthens the operational case for a later
  frozen OI shadow; it does not prove that the candidate C gain reaches S.
- No stability outcome promotes/rejects the arm, changes the selector, changes
  the tail-first law or licenses an outcome query.

Any candidate-to-selected-score or expected-dollar claim remains a separate,
prospectively frozen evaluation.
