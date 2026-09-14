# What the manual swaps and the cheap slots taught us (Week 1, scored on official points)

## 1. Every manual removal, versus what replaced it

| step | removed (official pts) → replacement (pts) | swaps | net over the book |
|---|---|---:|---:|
| Bateman out | 0.0 → Vele 19.9 ×3, Tucker 4.7, Hollywood Brown 0.0 | 5 | **+64.4** |
| Downs out | 5.7 → McConkey 19.2, Godwin 8.3, Metcalf 8.0 | 3 | **+18.4** |
| Warren out | 11.3 → Irving 21.3 ×2, Hubbard 23.7, Etienne 14.8 ×3, Jones 10.0 | 7 | **+41.6** |
| Wicks out | **15.3** → Tucker 4.7 ×2, Johnston 3.7, Harrison 4.3 | 4 | **−43.8** |
| McCaffrey out (late window, OUT) | 0.0 → Caleb Douglas | 1 | + |
| proven-scorer rule | Coker 36.8 → Johnston/Godwin/Tucker/Robinson/Burden, and 39 others | 46 | **−129.6** |

Reading. Bateman was inactive, Downs and Warren were diminished, and the projection-based replacement rule (best
projected active same-position player fitting the lineup's salary, stack-preserving) found Vele, Irving, Hubbard and
McConkey: those three calls were worth +124 points across the book. Wicks was not inactive: DraftKings never flagged
him, he played and scored 15.3, and the four replacements were low-frequency boomers that scored 4. The proven-scorer
rule removed the day's best cheap player and cost 130 points across the book, 28 on the best lineup.

Rule for the scratch protocol from here: **a player is removed only when DraftKings marks him OUT/IR or the official
inactives list names him; a "replace X" request is answered first with his live status, and if he is active the
answer is "he is playing" unless the operator overrides knowingly.** The replacement rule itself is sound and stays.

## 2. The cheap slots (skill players at ≤ $5,000)

Week 1: 287 such players; **three** scored 20+: Coker 36.8 (7.5% owned), Goedert 23.7 (10.1%), Kincaid 21.0 (1.8%).
The plain book held all three; the entered book held Goedert and Kincaid and had lost Coker to the filter. Our cheap
picks (37 players, 153 slots) averaged 9.6 points with a 5% hit rate; the field's cheap picks, ownership-weighted,
averaged 10.3 with a 10% hit rate — the difference is Coker. Vele (19.9, 9% owned) was in 11–14 of our lineups.

History, 27,550 cheap player-weeks on the 72 development slates: the big-game rate is 1.5%, and it is strongly
predictable from exactly the signals the optimizer already uses, and from nothing else:

| pre-lock feature (quartiles within the cheap pool) | Q1 | Q2 | Q3 | Q4 |
|---|---:|---:|---:|---:|
| projection | 0.1% | 0.2% | 0.7% | **5.0%** |
| market-implied points | 0.3% | 0.2% | 1.2% | **8.7%** |
| projected ownership | 0.5% | 1.0% | 1.5% | 3.0% |
| game total | 1.4% | 1.8% | 1.4% | 1.5% |
| implied team total | 1.4% | 1.6% | 1.4% | 1.5% |
| depth rank | 1: 7.5% | 2: 2.6% | 3+: 1.3% | |

A leave-one-season-out logistic on these features scores AUC 0.84–0.87; its top decile hits 12.8% against a 2.7% base.
Coker sat in that decile on Sunday (projection 10.1, market 8.7, ownership 7.5%). Game environment (total, implied team
total) carries no lift for cheap players at all — the Chicago–Carolina shootout was not visible in the totals (47.5).

Conclusions. (1) The optimizer's cheap picks are drawn from the predictable decile; the filter that removed Coker cut
against that signal, which is why it tested at −10 to −15 on history. (2) Cheap booms are not "unproven" players
getting lucky; they are the projection/market top decile hitting at 13%, and no history-of-big-games rule improves on
that. (3) There is no exploitable game-environment signal for cheap players. (4) The right control is exposure
(no single cheap player above ~15% of the book) rather than removal; Sunday's book had Vele at 14 of 80.
