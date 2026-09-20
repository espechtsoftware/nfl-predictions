# Week-2 Sunday live receipt review

The workstation published the K97 receipt package at shared handoff commit
`e35df552`. I independently read only the receipt package and the archived
outcome-blind ordering result. I did not open current scores, standings,
settlement, or entry keys.

Every one of the 12 files listed in the package `SHA256SUMS` matched its
Git-transported bytes. The replacement receipt is `OK` and publishable, with
49 replacements against a 42-player exclusion set. The final book hash is
`529d4f2a50bfdc40ddd5d844d8fb66844121bc8438ec8ce56e62c08364b7b3b3`.
The final vetter reports hard flags 0, material flags 39, clean/soft rows 58,
zero rows raised by fresh status, and zero unavailable-by-membership players.
Its 97-lineup reconstruction and source/bank bindings all pass.

The final-book ordering screen is explicitly pre-vetter and outcome-blind
(`current_outcomes_read=false`, `provider_calls=0`). It independently confirms
the operator-authorized MEAN promotion: source rank 7 (candidate 2123) has
pooled selection mean **144.3089** versus the delivered first row's **139.8872**,
so rank 7 was moved into the Millionaire slot. P230 also selects rank 7; P220
keeps the delivered rank 1 (candidate 12413). This is an objective choice,
not evidence that the tail objective is universally better. Moving rank 7 into
the first row costs the unchanged ranks 2–24 block 0.4771 simulated mean-max
points, 0.290 percentage points of P220, and 0.150 percentage points of P230.
The promotion was authorized under the frozen MEAN rule and the receipt binds
the rule hash, final vetting, input hashes, and the promoted-book hash.

The final promoted CSV has 97 lineups and is the final-book permutation with
source rank 7 first; the receipt states that the Millionaire row equals the
promoted row 1 and that all 97 upload rows match the promoted book. This
completes today's contest ordering decision while preserving the displaced
flea-block cost for Monday's evidence record.

## Operational issue to repair next week

The 09:12 CT watcher timer started a transient service that launched detached
children. Systemd's default control-group cleanup killed all three watchers,
leaving empty logs and no ENTER bundle. The operator relaunched the exact
command manually at 14:35:00Z; the chain watcher completed at 14:35:46Z and
the entries and late-inactives watchers were then alive. The book was not
changed, but late-status coverage began late. The receipt's next step is the
15:30Z inactives sweep, followed by the 16:15Z upload deadline and 17:00Z
lock. Week 3 should use a persistent watcher unit (or an explicitly verified
interactive launch), with a one-minute liveness and non-empty-log check.

Evidence is in `handoffs/receipts/2026-09-20-sunday-live-k97/` on the shared
handoff branch, including `sunday-watchers-timer-defect.md` and the complete
promotion/replacement/vetting receipts. No production code or current-week
outcome data was changed or opened by this review.
