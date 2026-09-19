# Complementary retrieval tradeoff measurement: whole book only

This is a separately frozen, adaptive diagnostic after the strict [fixed-K screen](2026-09-19-fixed-k-retrieval-results.md), also suggested independently in the workstation's `35acf79` before it reviewed that result. It measures why some coverage-improving replacements fail the stricter nomination guard. It never nominates an entered-policy change.

Use precisely the same archive, original K97 book, identity checks, float32 summation, Milly preservation and pair-ordering as source `d0a41807`. Change only the guard to six metrics for the WHOLE book: incumbent and hsim Emax, GLOBAL proxy and P220 all nondecreasing, with positive combined covered-world gain. Evaluate replacements in descending combined coverage gain, then row, then candidate index; accept at most ONE. Retain the same 300-second and 10,000-proposal caps and honest partial-result handling.

Report the best passing single replacement under this order and every prefix/block delta, including every negative delta and threshold-world loss. If none passes, report that without expanding the search. This is a one-swap headroom measure under the remaining whole-book guards, not a global upper bound or the unrestricted maximum coverage book. The stricter study's original rejection counts are not treated as causal attribution.

Implementation is a count-asserted transformation of the exact frozen previous script. Pin its SHA-256, record both wrapper and transformed hashes, and retain a separate create-once result. The executable/protocol are committed before the comparison. No outcome access, actual-score selection, live entries, policy, dose or schedule edits.
