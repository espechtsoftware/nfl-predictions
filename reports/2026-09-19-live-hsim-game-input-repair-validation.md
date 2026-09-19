# Live game-input repair: tests and full CLI rehearsal pass

As of September 19, 01:24 UTC, lab branch `fix/live-hsim-game-inputs-20260919` at **2dc116c** holds the isolated repair and evidence. No live deployment, timer change or production `main` push has occurred. Independent code review and the operational release plan remain pending.

The live CLI validates current game inputs against its frame before training or candidate generation. Missing or inconsistent lines, duplicate games/teams, foreign game identities, incomplete coverage and invalid totals refuse early. The same explicit inputs reach all five hsim pilot calibrations and its final draw. Actual game values, ordering, spread convention and hash are recorded in the receipt.

Historical callers that omit the new API parameter retain the old benchmark path exactly. **The patched live CLI supplies the parameter, so releasing it changes live behavior.** This is not a passive, default-off live deployment. Game order is explicitly canonical by game id, rather than inherited from a warehouse query. The earlier schedule-only sensitivity held benchmark order fixed; its exact book is not claimed to be this patch's book.

Completed checks:

- **16 offline tests pass**, covering invalid/missing inputs, sign consistency, unchanged callers and propagation through every pilot/final pass.
- On the authenticated archived frame, the unchanged default reproduces **all 4.35 million scores exactly**.
- Explicit live inputs match an independently assembled canonical live-game reference **exactly**, also across all 4.35 million scores. Both numerical comparisons completed in 8.443 seconds.
- A clean-source **full CLI rehearsal passed in 72.2 seconds**: 20 candidates, five written legal lineups, 13 current games explicitly recorded. It exercised current input queries, status gates, component fitting, simulation, generation, selection and output. Identity, salary, roster and low-level gates remained enabled.

The rehearsal used source `9363bfec05249e8fa83c85d45d67b0d152a34165`, group 153428, K5, lev4/boom16, 1,000 worlds and seed2026, with production centering. Its run directory is isolated under the repair worktree. A first invocation refused at the dirty-tree gate because an ignored evidence path had prevented a commit; evidence was moved and committed before retry. No gate was bypassed. Python's CPU-count override kept LightGBM to one thread; this is a mechanics rehearsal, not a production performance comparison.

Evidence: [numerical parity](reviews/evidence/2026-09-19-live-hsim-game-input-parity.json), [CLI receipt](reviews/evidence/2026-09-19-live-hsim-cli-rehearsal.json), [artifact identities](reviews/evidence/2026-09-19-live-hsim-cli-rehearsal-artifacts.json).

These checks establish correct integration of explicit game inputs and preservation of the historical default. They do not establish real-world 220+ improvement or authorize release. Next: independent source review, exact identity/timer rehearsal and rollback plan, and combined usage/game-input sensitivity under a separately fixed design.
