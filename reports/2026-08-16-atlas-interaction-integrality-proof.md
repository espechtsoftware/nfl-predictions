# ATLAS interaction-variable integrality proof

Date: 2026-08-16
Status: outcome-free repair3 candidate; implemented but not licensed for launch
until the native-CBC diagnostic is strictly harvested.

## Finding

The shared lineup optimizer created a binary auxiliary `y_T` for every priced
pair or triple `T`, with binary roster-membership variables `x_i` and the
standard product constraints:

```text
0 <= y_T <= 1
y_T <= x_i                         for every i in T
y_T >= sum(i in T, x_i) - (|T|-1)
```

`y_T` does not need to be declared integer. If every member is selected, the
last inequality forces `y_T >= 1` and the upper bound forces `y_T = 1`. If any
member is absent, one upper inequality forces `y_T <= 0` and the lower bound
forces `y_T = 0`. Thus `y_T` is exactly binary at every feasible integer
roster even when its solver category is continuous.

This proof holds both when interaction weight is the maximized stage-two
objective and when the interaction optimum is retained as the stage-three
floor. It uses the existing requirement that all interaction weights are
finite/nonnegative but does not rely on their magnitudes. It changes neither
the feasible roster set nor any exact integer objective value.

## Candidate repair

Declare each `interaction_*` auxiliary continuous with explicit bounds
`[0,1]`. All roster variables remain binary. This removes a large family of
redundant branch-and-bound integers from the difficult ATLAS MILPs while
preserving the frozen construction law exactly. The default non-interaction
optimizer path is untouched.

The change is implemented in `src/nfl_dfs/optimizer/lineup.py`. A focused test
inspects the constructed model and confirms the continuous category/bounds;
the existing stage-two and stage-three tests continue to require the priced
pair. The focused optimizer, ATLAS and CBC-diagnostic suites pass 39 tests.

## Boundary

This is not yet repair3 and is not deployed. The two native-CBC diagnostics
retain the original binary auxiliaries and immutable repair2 image, so this
implementation cannot influence their evidence. Once both diagnostics are
strictly harvested, repair3 may adopt this exact reformulation alone or in
combination with a separately justified CBC transport update. Repair3 still
requires new full-grid identities, full tests, immutable image validation and
score-free parity checks before any 54-slate launch.
