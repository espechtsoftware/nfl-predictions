# Study 95 → shape percentages: the translation rule, fixed BEFORE study 95 is read (2026-10-09 evening)

**Why:** the operator, 10-09 evening: "we're going to decide the percentages of each of the successful shapes first thing in
the morning … My hope is that by morning you'll have suggestions on which of the tested arms should be used in which situations
and in what percentages." Study 95 (frozen `9332a0b4`) measures each shape removed (NO_x) and each shape alone (ONLY_x) against
his live mix A1 30% / A2 14% / B 28% / C 28%. This note fixes, before the read, how its numbers become a SUGGESTED mix. The
frozen preregistration is not changed; this is a separate file. The operator decides; this is a suggestion rule.

## The rule (per shape x ∈ A1, A2, B, C; "both draws" = the two random opponent sets of the reader; seats = the pooled
## expected big seats ratio)
1. **Removing x helped** — NO_x − LIVE > 0 on BOTH draws AND seats ≥ 0.80 (his rule passes for NO_x):
   - suggest **halving** x's share (not dropping it: one pass happens about one time in three under no true effect);
   - suggest **dropping** x only if, in addition, the pooled two-sided 0.95 interval of NO_x − LIVE lies above 0.
2. **Removing x hurt** — NO_x − LIVE < 0 on BOTH draws, and ONLY_x − LIVE is not < 0 on both draws:
   - suggest **raising** x's share by half (× 1.5).
3. **Otherwise** — keep x at its live share.
4. Apply every change, then re-scale the four shares to 100% in proportion; the 26 book rows follow by the harness's own
   allocation (largest remainder). No share is pushed below half of its live value by the re-scaling of another shape's raise
   (if it would be, the raise is reduced until it is not).
5. **ONLY_x results are information only**: they never by themselves move a share (a 100% book is a different construction).
6. **Reported beside the suggestion:** every arm's pooled point, interval, both draws and the seats ratio, verbatim from the
   reader; the multiplicity (eight comparisons, about two false passes expected under no effect); the transfer caveat (the
   harness builds on simulator means, his book on Fantasy Points' projections); and that his live mix is itself the result of
   studies 18 / 28 / 56 (no mix has beaten another on both draws so far).

## Game situations (study 97)
How the shapes should vary by game situation (expected blowouts, shootouts, trailing teams) is study 97's question; its own
preregistration states its rule before its run. The morning suggestion combines the two only by these rules, never by a
new reading of either study's numbers.
