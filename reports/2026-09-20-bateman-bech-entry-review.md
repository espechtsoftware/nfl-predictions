# Bateman versus Bech review for the uploaded entry

## Entry reviewed

The Windows Downloads file `DKEntries.csv` contains one Rashod Bateman entry
at physical line 97: the $40K Nickel entry `5256608624`. Its relevant stack is
Lamar Jackson, Derrick Henry, Rashod Bateman, Mark Andrews, and opposing
receiver Devaughn Vele.

## Current status and role

The Baltimore Ravens' Sunday inactive report rules out Zay Flowers and
Ja'Kobi Lane and says that Rashod Bateman steps into the lead wide receiver
spot. This is a stronger Bateman case than the pre-inactives frame used by the
build. The earlier frame had Bateman at depth rank 2, 78% recent snap share,
and a stale 4.2% recent target share before Flowers' inactive status was known.

Jack Bech is active, but the Raiders' unofficial depth chart lists Tre Tucker
ahead of him and Dareke Young behind him. The archived frame has Bech at depth
rank 3 and 40% recent snap share. Bech is a reasonable cheap tournament dart,
not a safer replacement.

Sources: [Ravens final inactive report](https://www.baltimoreravens.com/news/ravens-inactives-saints-ronnie-stanley-carson-vinson),
[Raiders depth chart](https://www.raiders.com/news/raiders-unofficial-depth-chart-nfl-week-2-at-los-angeles-chargers-092026).

## Book comparison

| | Bateman | Bech |
|---|---:|---:|
| Salary | $4,400 | $3,600 |
| Team / opponent | BAL / NO | LV / LAC |
| Implied team total | 27.5 | 18.5 |
| Archived mean projection | 8.20 | 9.41 |
| Archived tournament proxy | 8.20 | 18.35 |
| Archived market projection | 8.40 | none |
| Recent target share | 4.2% (pre-Flowers inactive) | 13.8% |
| Recent snap share | 78% | 40% |

The Bech mean/tournament numbers are pre-inactives model values and do not
include the official Flowers/Lane news. The apparent Bech edge is therefore
not a clean forward comparison. Bech's tournament proxy identifies a cheap,
high-variance dart; it does not outweigh Bateman's newly elevated role and
Lamar correlation in this particular lineup.

## Same-world tail check

Using the archived outcome-blind player-score banks and the same 10,000 worlds
per component, the exact lineup has a lower simulated mean than the swap but a
better high tail in the equal two-bank mixture:

| metric | Bateman | Bech swap |
|---|---:|---:|
| Mean | 130.02 | 131.81 |
| P(220+) | 0.150% | 0.090% |
| P(230+) | 0.055% | 0.035% |
| P(240+) | 0.020% | 0.010% |
| Maximum simulated score | 257.79 | 241.90 |

The incumbent component shows positive Lamar/Bateman world covariance and
almost no Lamar/Bech covariance. The corrected component slightly favors Bech
on P220, so this is not a universal proof; it is a useful tie-break for the
user's 220+ objective. No realized outcomes were read.

## Recommendation

Keep Bateman in this uploaded entry. The official inactive report changes him
from a questionable-looking prebuild value into Baltimore's lead receiver,
while Bech remains a depth-three, low-snap, low-total dart. A Bateman→Bech
swap would also leave $800 unused and remove the Lamar stack. Revisit Bech only
if a different replacement can use the salary savings or if new official news
changes Bateman's availability or role.
