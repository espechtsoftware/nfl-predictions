# Review: TD competitive WR allocation protocol

Date: 2026-08-14. Review of
`reports/2026-08-14-td-competitive-wr-allocation-protocol.md`.
**No code was changed. No outcome was queried.**

---

## Verdict

The protocol is well built and already contains almost everything I would have
raised. One gap worth closing, one thing to confirm rather than change, and one
scope statement to add.

---

## 1. What it gets right

**It is motivated by the current-path shape error, not the stale diagnosis.**

The stated premise — that supported three-player multiplicity is *already too
high*, and that the closed global ledger "moved QB-WR in the desired direction
but worsened every competing" cell — is the correct reading of the repaired
path. This was the failure mode I was most concerned about: a design still
chasing the pre-`26e73c5` story ("the simulator is near teammate-independent")
would have added coupling indiscriminately and made the worst cell worse.

Current-path position, for reference:

| cell | current control | realized | error direction |
|---|---:|---:|---|
| QB→WR | 2.418 | 3.323 | **under**-produced |
| multiplicity ≥3 | 2.377 | 1.835 | **over**-produced |
| multiplicity ≥4 | 6.175 | 2.333 | **over**-produced, ~2.6× |

**The gates are absolute-log error, not directional.** Items 3–7 require
*absolute* error to improve. This is the single most important design decision
in the protocol and it is correct: because QB-WR errs low while multiplicity
errs high, a directional "increase coupling" gate would have passed a treatment
that overshoots multiplicity further. Two-sided error is the only formulation
that works on the repaired path.

**WR-WR is explicitly gated at both levels** (items 4 and 6) rather than left to
average out inside an aggregate sum. That is the cell whose near-independence
mathematically constrained G2, and since WR ranks are precisely what this
treatment moves, it is the most likely casualty. I had this as my main expected
gap; it is not one.

**Item 11 is a proper mechanical negative control.** Requiring QB, RB and TE
scorecard values and simulated estimates to remain unchanged within `1e-12`
*proves* the treatment is WR-only rather than asserting it. Combined with the
`>=3` and `>=2` guards, the design cannot pass by quietly moving something it
claims not to touch.

**No free parameter.** TD-ledger values supply ranks only; there is no
winner-count choice, no binning, no season tuning, no added randomness, and no
post-result repair. That closes the tuning surface that would otherwise sit in
"how do the QB rank and the within-team relative rank combine."

**Stage R precedes Stage T.** Re-measuring the repaired control before the
treatment is exactly what the stale-reference finding requires, and it is what
prevents a third invalidation on the same cause.

---

## 2. Gap: multiplicity ≥4 is unmeasured by the gate

Items 7 and 8 cover `>=3` and `>=2`. `>=4` appears nowhere, presumably because
G0 declared it **unsupported** at seven realized events against 3.00
independence-expected. That exclusion is defensible on its own terms and I am
not proposing it become a gate.

But `>=4` carries the **largest error on the current path** — `6.175` against a
realized `2.333` — and it is the cell that produces the biggest lineups. A
treatment that concentrates WR outcomes onto high-QB worlds is plausibly the
kind of change that worsens it, and under the gate as written that would be
invisible.

**Recommendation:** add `>=4` as a **mandatory reported diagnostic**, with its
realized and simulated values and its event count shown alongside. It cannot
gate on seven events, and it should not try to. But if it moves sharply against
realized, that belongs in the disposition even when every gated item passes —
and if it moves *toward* realized, that is meaningful supporting evidence the
gate would otherwise discard.

The precedent already exists: G0 reported its `>=4` point estimate while
correctly declaring it unsupported. Do the same here.

---

## 3. Confirm, do not change: Stage R must supply Stage T's references

Every `1e-12` comparison in items 3–11 must resolve against the **Stage R
repaired-control values**, not against any pre-`26e73c5` frozen reference.

The design clearly intends this — Stage R exists for exactly this reason, and
the population is specified as "the exact 2023–2025 Stage R population." The
recommendation is only that the runner **assert** it rather than inherit it:
a single check that the reference artifact Stage T loads carries the Stage R
run identity and code SHA.

This is worth an explicit assertion because the failure it prevents has now
happened twice. The v2 arm died on a `1e-12` variogram reproduction failure, and
the v3 arm died on a 48-value control reproduction failure against stale
references. A third invalidation on the same cause would be avoidable and
expensive.

---

## 4. Scope statement to add: QB→TE is deliberately out of scope

Restricting the mechanism to WR is correct. Competition among same-position
teammates is specifically the WR problem — a team has one relevant tight end, so
a competitive allocation construction has nothing to act on there, and the
mechanical negative control in item 11 depends on TE draws being untouched.

But QB→TE has a realized lift of `2.371` and is not addressed by this arm. As
written, a passing Stage T could reasonably be read as having repaired "the QB
hub," when in fact half of it is untouched by construction.

**Recommendation:** state in the protocol that QB→TE is out of scope, why (one
relevant TE per team; no competitive structure to exploit), and what — if
anything — is designated to address it. G2's factor mechanism did materially
repair QB-TE (`1.0788 → 1.7438` against realized `2.3709`) before failing its
overall gate on the WR channel, so a WR-ledger-plus-TE-factor composition is the
obvious candidate. Naming it now prevents it from becoming a post-result choice
if Stage T passes.

---

## Summary

No changes required to the mechanism, the gate structure or the sequencing. The
absolute-error gating, the explicit WR-WR guards, the mechanical negative
control and the Stage R precedence are all correct, and together they address
the shape error the repaired path revealed.

Three additions, none of which alters the science:

1. report multiplicity `>=4` as a mandatory diagnostic, ungated;
2. assert that Stage T's references carry the Stage R run identity;
3. state QB→TE as deliberately out of scope, with its designated follow-up
   named in advance.
