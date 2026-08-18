# Residual-world retained-MPS proof parser review

Date: 2026-08-17

Status: score-free, read-only implementation review. This review licenses no
cloud execution, historical scoring or production change.

## Reviewed identities

- Exact-solver amendment before any parser-driven output:
  `reports/2026-08-17-residual-world-exact-solver-and-selector-amendment.md`,
  SHA-256
  `84474ad0cbfafffb503f21cf5bf1c91e4e83a40564c3c1c40ac585fc9dcdfcab`.
- Installed PuLP: `3.3.2`.
- Installed `pulp/mps_lp.py` SHA-256:
  `e6ec5badbfb1ecd389a94c4e4c67db267cab492a7c69c011a2490fa0a5e8fd78`.
- Installed `pulp/apis/coin_api.py` SHA-256:
  `c412dbbc9c871b31137972071ed31837a29f1ecdd1ca8b705b1e14d14ffda26d`.
- Solver boundary: CBC `2.10.3`, including its official solution-writer and
  COIN MPS-reader behavior.

No real-slate residual column, selected treatment book, historical treatment
score or 2026 outcome was inspected or produced during this review.

## Verdict

Calling PuLP's own `fromMPS` reader is not a sufficiently independent proof of
the MPS emitted by PuLP. It also round-trips coefficients and bounds through
binary floating point. The retained proof boundary must instead parse the
exact pinned PuLP writer profile, retain base-10 values exactly, and
reconstruct the integral assignment, every row, every bound and the objective
with exact integer arithmetic.

CBC's `printingOptions all` solution body is not a high-precision numerical
artifact. Its row activities and column values use `%15.8g`, and its header
objective uses `%.8f`. Consequently a blanket `1e-9` comparison to printed row
activities is invalid: at magnitude `1e8`, the display can round by several
whole units. Scientific feasibility must come from exact reconstruction. The
printed activities remain redundant display evidence only.

## Required fail-closed parser contract

1. Hash the raw MPS and solution bytes before parsing. Decode strict ASCII and
   reject NUL bytes, malformed sections, unexpected sections and trailing
   content.
2. Accept exactly the pinned PuLP writer order:
   `*SENSE`, `NAME MODEL`, `ROWS`, `COLUMNS`, `RHS`, `BOUNDS`, `ENDATA`.
   Reject `RANGES`, SOS/quadratic extensions, duplicate sections, inline `$`
   comments, multiple RHS/bound vectors and `OBJSENSE`.
3. Require exactly one `N OBJ` row, then uniquely named `E`, `L` or `G` rows.
   Require contiguous normalized `C0000000...` and `X0000000...` names.
4. Columns must be contiguous in first-occurrence order. Require exactly one
   row/value pair per PuLP writer line. Reject paired standard-MPS records,
   duplicate `(column,row)` or `(column,OBJ)` coefficients, explicit zero or
   tiny nonzero coefficients, and BOUNDS references before a real COLUMNS
   declaration.
5. Parse numeric tokens as finite `Decimal`, but use Python integers or exact
   rational arithmetic for reconstruction. Do not rely on the default Decimal
   context for unchecked multiplication or summation.
6. Under this integer/radix formulation, require every scientific coefficient,
   RHS, bound and objective coefficient to be mathematically integral. Every
   column must be registered in a complete, hashed renamed-to-scientific domain
   manifest as binary, integer or mathematically implied integer. This includes
   the deliberately continuous PuLP auxiliaries whose Boolean/radix constraints
   force integral values; it does not permit an arbitrary continuous column.
   Parse each raw solution token as finite `Decimal`, map it to its unique
   nearest integer only when the exact residual is inclusively
   `<= Decimal("1e-11")`, and then use only that Python integer in scientific
   reconstruction. Never widen this boundary. It is 100 times tighter than the
   frozen CBC integer tolerance and roughly five times the largest score-free
   residue observed before output. Do not canonicalize `0.9999999995` or
   `2.0000000001`.
7. Parse `INTORG`/`INTEND` as a strict state machine. Reject nesting, reversed
   or unmatched markers, empty blocks, marker-only variables and a column that
   crosses a marker boundary. Under the exact PuLP profile, require each
   integer column's dedicated marker pair.
8. A marker integer with no explicit bound uses COIN's `[0,1]` default. Once
   an explicit bound exists, apply that explicit side and ordinary defaults;
   notably `LO 0` means `[0,+infinity]`, not binary.
9. Apply exact bound semantics:

   | record | effect |
   |---|---|
   | `BV` | integer, lower `0`, upper `1` |
   | `LI n` | integer lower `n`; other side unchanged/default |
   | `UI n` | integer upper `n`; other side unchanged/default |
   | `LO n` | lower `n`; category unchanged |
   | `UP n` | upper `n`; category unchanged |
   | `FX n` | both sides `n`; integral inside integer markers |
   | `FR` | lower `-infinity`, upper `+infinity` |
   | `MI` | lower `-infinity`; upper unchanged/default |
   | `PL` | upper `+infinity`; lower unchanged/default |

   A generic parser may understand every record, but the pinned PuLP writer
   profile must reject `LI`, `UI` and `PL`, which that writer does not emit.
   Reject a repeated specification of the same side or an incompatible
   combination. Accept the valid PuLP `MI` followed by `UP` pair. Reject lower
   greater than upper.
10. The semantic MPS default for omitted RHS is zero, but the pinned PuLP
    writer emits every constraint RHS, including zero. Require exactly one RHS
    per constraint. Reject duplicates, extra vectors, unknown rows and any RHS
    on `OBJ`; the latter is an unregistered objective offset.
11. `writeMPS(rename=1)` records sense only in the `*SENSE` comment; CBC gets
    maximization from the separate `-max` command. Require exact agreement
    among the sense comment, registered in-memory sense and exactly one
    appropriate `-max` command token. Reject a nonzero in-memory objective
    constant because PuLP does not serialize it. A missing objective
    coefficient for a declared column means zero.
12. Parse the CBC solution body in physical order: every constraint row first
    in MPS order, then every column in MPS order. Row indices must be exactly
    `0..R-1`; column indices restart at `0..C-1`. Require exactly `R+C` lines,
    exact names, no duplicates/omissions/extras/interleaving, no blank early
    termination and no trailing text. Reject every `**` prefix and every
    nonfinite token. Duals and reduced costs are retained but do not license a
    scientific claim. Never initialize an omitted column to zero.
13. After the single token-decoding step, reconstruct every column bound,
    binary/integer domain, row activity/sense and objective with tolerance zero
    from the canonical Python-integer assignment and MPS coefficients. Require
    exact equality for `E`, exact `<=` for `L` and exact `>=` for `G`. Require
    exact equality among reconstructed objective, exact integral solution
    header and registered scientific objective.
14. Bind the renamed-to-scientific variable mapping and every registered
    integral/implied-integral domain as a separate bijective hashed manifest. A
    structurally valid renamed model cannot be accepted for different
    scientific player/auxiliary meanings.
15. Require every integer coefficient, bound, assignment and worst-case
    row/objective activity to remain strictly within the frozen safe range
    below `2^53`. Otherwise the exact base-10 MPS and CBC's executed binary
    double model need not represent the same integer relation.

This proves exact feasibility and objective reconstruction for the retained
assignment. It does not independently prove global optimality; that claim
still requires the separate exact terminal CBC log/solution/command contract.

## Mandatory poison matrix

- Missing/extra/duplicate column; wrong or non-restarting column index.
- Missing/extra row; row/column interleaving; wrong row index.
- Blank solution-body line or trailing body text.
- Any `**` row or column.
- Accept decoding examples `-2.220446e-15 -> 0`,
  `1.9999306e-13 -> 0`, `0.999999999998 -> 1`,
  `-1.000000000002 -> -1`, and the exact inclusive `n +/- 1e-11`
  boundary. Retain raw token, canonical integer, exact residual, maximum
  residual, affected-column count and raw-solution SHA in operational evidence.
- Reject `n +/- 1.00000001e-11`, fractional binary `0.9999999995`,
  fractional integer `2.0000000001`, a binary canonicalizing to `-1` or `2`,
  any column missing from the domain manifest, and any post-canonicalization
  exact row/objective defect.
- Exact bound or equality violation of `5e-10`.
- Reversed `L`/`G` sense.
- Objective coefficient, sign or sense mutation; maximize registration without
  the exact `-max` command; one-unit header/reconstruction mismatch.
- Stopped or gap-tolerance header masquerading as Optimal.
- `nan`, `inf`, `infinity`, exponent overflow or locale comma.
- Nested, missing, reversed or empty `INTORG`/`INTEND`; column crossing marker
  blocks.
- Marker integer with no bound versus marker integer with `LO 0`.
- `BV` plus conflicting `UP`; nonintegral `FX` inside integer markers.
- Valid `MI+UP`; incorrect `MI` upper-zero and `PL` lower-zero semantics.
- `LI`/`UI` category creation and pinned-writer-profile rejection.
- Duplicate coefficient/objective/RHS/bound side; multiple RHS/bound vectors.
- Missing RHS (semantically zero but invalid under the pinned writer profile),
  RHS on `OBJ`, and undeclared row/column references.
- Nonzero objective constant lost during serialization.
- An integer above eight significant digits, such as `123456789` displayed as
  `1.2345679e+08`: display rounding must not become scientific rounding.
- A coefficient beyond PuLP writer precision, an arithmetic case beyond the
  default 28-digit Decimal context, and any worst-case activity at or above
  `2^53`.

The `1e-11` boundary is an evidence-decoding law, not a claim that CBC's hidden
internal double was within that distance: `%15.8g` may itself round a residue
away. The accepted scientific claim is narrower and auditable--the retained
token decodes under the frozen rule to one exact integer point, and that point
independently satisfies every retained model relation and the proven objective.
Two raw files with different accepted residues therefore have distinct
operational solution hashes but the same canonical scientific-assignment hash.

## Remaining gate

After implementation, freeze the source/test hashes and repeat an independent
line-by-line audit. The parser, model-hash binding, scientific receipt return,
final payload self-recomputation and final amendment hash must all be green
before the score-free core can be committed. A green parser still licenses no
real-slate run; the source-lock, endpoint/stability, runner/harvester, image,
IAM, shared-lease and dual-canary blockers remain.
