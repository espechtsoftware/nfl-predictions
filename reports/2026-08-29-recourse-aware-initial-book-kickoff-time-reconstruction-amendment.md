# Recourse-aware kickoff-time reconstruction amendment

Date frozen: 2026-08-29, before any kickoff-v3 canary or shard exists.

Production `kickoff_time` is an Eastern wall-clock string in strict `HH:MM`
form. Treating it as a complete timestamp caused pandas to attach the host date
2026-08-29, so the kickoff-v2 canary cannot authorize a result.

Kickoff-v3 reconstructs every time on a fixed Sunday-main date derived only
from the requested season and week: 2023 Week 1 is 2023-09-10, 2024 Week 1 is
2024-09-08, and 2025 Week 1 is 2025-09-07, with exactly seven days added for
each later week. The reconstructed timestamp is localized with
`America/New_York`, preserving the applicable daylight-saving offset. Empty,
malformed, non-`HH:MM`, date-bearing, offset-bearing, or multi-date-ambiguous
inputs fail closed. The exact queried R0 player population and the requirement
for both early and late games remain unchanged.

Fresh execution ID:
`20260829-recourse-aware-initial-book-scorefree-kickoff-v3`.

This amendment changes no slate, player, candidate, world, fold, score-free
metric, outcome boundary, compute allowance, retry law, or production decision.
Kickoff-v1 and kickoff-v2 remain terminal/non-authoritative and must not be
resumed or written beneath. Cloud transport and canary identities must bind
kickoff-v3 separately before any launch.
