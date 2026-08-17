# ATLAS repair6 accepted-retry wait repair

Date frozen: 2026-08-17, while 44 of the 54 repair5 primary executions were
still nonterminal and before the repair5 attempt resolver, terminal census,
repair6 classification, repair6 canary, repair6 grid, hybrid population or
historical-v4 score existed.

This is a queue-control repair only. The repair6 watcher correctly waited for
all 54 repair5 primary executions before invoking the already-frozen repair5
attempt resolver, but it proceeded directly to the terminal census after the
resolver returned. If the resolver had created any allowed unchanged external
platform replacement, the census could therefore have run while that accepted
execution was still nonterminal.

The watcher must now, after attempt resolution and before terminal census,
check whether the frozen resolver produced `accepted-executions.txt`. When it
did, it must status-poll every accepted execution until none has
`Completed=Unknown`. It records counts of running, succeeded and failed
accepted executions but does not inspect any object, shard, candidate,
score-free effect or realized outcome. A failed accepted execution is left for
the already-frozen terminal census and downstream classification; the watcher
does not retry it or alter any scientific disposition.

This changes no job, execution, object, seed, optimizer law, tolerance,
resource, retry eligibility, candidate identity, historical gate or production
setting. For the live population, the already-known ineligible repair5
identity-tiebreak failure means the resolver is expected to close repair5
without launching a platform replacement, but the queue must remain correct
for every outcome allowed by its preregistered attempt law.

