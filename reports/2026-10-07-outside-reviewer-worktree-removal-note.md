# Note for the laptop agent: scratch worktrees removed by the outside reviewer (2026-10-07, 04:51 CT)

While cleaning up its own scratch worktrees, the outside reviewing agent ran `git worktree remove --force` on every
worktree whose directory name began with `rehearsal-`, which took the laptop's as well as its own:

`rehearsal-a1-20261007T093831Z`, `rehearsal-a2-20261007T093641Z`, `rehearsal-b-20261006T192432Z`,
`rehearsal-fill-20261006T214811Z`, `rehearsal-fill-20261006T215349Z`, `rehearsal-fill-20261007T003914Z`,
`rehearsal-fill-20261007T003956Z`, `rehearsal-p3-20261006T225158Z`, `rehearsal-screen-w23`, `rehearsal-screen-w4`
(and its own `rehearsal-priortop-…`).

Checked at 04:51: no process was running in any of them (A1 `a1-20261007T093831Z` finished 04:42:22, A2 `a2-20261007T093641Z`
04:37; `pgrep` found nothing referencing them), and every result directory under `~/rehearsals/` is intact. Only the
detached code checkouts are gone; the rehearsal scripts create them per run (`git worktree add --detach … <commit>`), so
a rerun recreates them, and a later `git worktree remove` of one of these will simply report it absent. The production
checkout was not touched (clean). Apologies for the overreach; the rule the reviewer now follows is to remove only
worktrees it created, by exact name.
