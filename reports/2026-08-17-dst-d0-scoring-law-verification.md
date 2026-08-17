# DST Phase D0 scoring-law verification

Date: 2026-08-17
Status: current-law prerequisite complete; no historical population, lineup
outcome, cloud execution or production-policy change

## Scope

This is the narrow first prerequisite from Phase D0 in
`2026-08-17-dst-shadow-and-rare-event-feasibility-audit.md`. It verifies the
current DraftKings NFL Classic defense/special-teams scoring law, resolves the
reciprocal points-allowed treatment of a defensive conversion return, and
binds both repository scoring paths to one date-versioned executable contract.

It does **not** create the canonical historical event frame, query a warehouse,
inspect an outcome, simulate a world, select a lineup or license DST Phase D1.

## Official primary-source receipts

The authoritative source is DraftKings' own live rules API, not an independent
rules summary:

1. [DraftKings RulesAndScoring API](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json)
   - selector: top-level group `1`, rule named `NFL Classic`, whose
     `gameTypes` contains `1`;
   - retrieved: `2026-08-17T19:59:59Z`;
   - HTTP `Last-Modified`: `2026-08-13T14:08:31Z`;
   - selected NFL Classic rule-HTML SHA-256:
     `fb0ac704f9bbc5d8fd96727280ad8ef7760b1a9d2456474dd760904543d7bbe5`.
2. [DraftKings game-type 1 API](https://api.draftkings.com/lineups/v1/gametypes/1/rules?format=json)
   - identifies game type `1` as `Classic` and points to
     `/help/rules/1/1`;
   - retrieved: `2026-08-17T19:59:58Z`;
   - complete response SHA-256:
     `0a46969690423d45a93388ff6402ac0335604003deda70e1d525081f6047fb35`.

The API's current NFL Classic rule enumerates the complete DST scoring table
and then separately enumerates which scoring plays count as points allowed.
That latter list explicitly includes defensive two-point/extra-point returns.
Therefore the reciprocal treatment is resolved: the returning DST earns two
fantasy points, and the two scoreboard points also count against the opposing
DST's points-allowed tier because its special teams was on the field.

The same complete scoring table contains no passing-, rushing-, total- or
other yards-allowed fantasy component. Yards allowed can be a predictive
covariate, but it contributes **zero** direct DraftKings NFL Classic DST points
under this rule version.

## Frozen law

Contract ID: `draftkings-nfl-classic-dst-2026-08-17-v1`

| Component | DK points |
|---|---:|
| Sack | 1 |
| Interception | 2 |
| Fumble recovery | 2 |
| Safety | 2 |
| Blocked kick | 2 |
| Defensive/special-teams return touchdown | 6 |
| Defensive two-point/extra-point return | 2 |

Points-allowed tiers are `0 -> +10`, `1-6 -> +7`, `7-13 -> +4`,
`14-20 -> +1`, `21-27 -> 0`, `28-34 -> -1`, and `35+ -> -4`.

Points given up while the subject team's offense is on the field are excluded
from PA. The current rules explicitly count ordinary conversions, conversion
returns, extra points and field goals when the subject DST/special teams is on
the field. Thus:

- an offensive pick-six/fumble-return touchdown is excluded from the affected
  offense's reciprocal DST PA;
- the ensuing extra point is charged while that DST is on the field; and
- a defensive conversion return is also charged to the reciprocal DST PA.

## Repository comparison and implementation

Before this change, both implementations already agreed on component weights,
PA tiers and the requested reciprocal behavior:

- `sql/features/024_team_defense_week.sql` credits
  `defensive_two_point_conv * 2` and subtracts only offensive defensive-return
  touchdowns and offensive safeties from the opponent's final score. It does
  not subtract a defensive conversion return, so those two points remain in
  reciprocal PA.
- `research/recourse_scoring.py` used the same event weights and PA tiers and
  likewise left a defensive conversion return in reciprocal PA.

The duplication was nevertheless fragile. The new
`models/dst_scoring.py` is the single versioned, executable contract. The
point-in-time recourse scorer now calls it directly. The warehouse SQL names
the exact contract ID, and offline parity tests pin its literal weights, tier
boundaries, conversion treatment and absence of yards-allowed scoring. This is
a behavior-preserving refactor; it does not change a production projection or
historical score.

## Validation

```text
.venv/bin/python -m pytest -q \
  tests/test_dst_scoring_law.py tests/test_recourse_scoring.py
28 passed

git diff --check
passed
```

The focused conversion-return fixture proves both sides of one play:

- returning DST: `+2` conversion plus `+10` zero-PA tier = `12`;
- reciprocal DST: `2` PA and therefore the `1-6` tier = `7`.

## Remaining boundaries

- No requested current-rule detail remains unresolved.
- This is a current rules snapshot, not proof that every historical season
  used the same law. A claim about season-specific historical rule changes
  still requires an archived DraftKings rule or authoritative exact labels.
- Phase D0's historical event-vector work remains separate. In particular,
  `team_defense_week` still uses `defensive_conversions` in its scalar score
  but does not expose that count in the final selected schema. That source
  frame must be repaired and support-censused before D1.
- The official source hashes should be checked again before Week 1. Any drift
  requires review and a new contract version; it must not silently mutate this
  frozen law.
