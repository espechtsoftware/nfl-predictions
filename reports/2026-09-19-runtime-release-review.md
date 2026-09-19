# Weekend runtime option: independent checks accepted

Reviewed lab `d7abe2c` on September19. All **42 behavioral tests pass** on the
laptop, using fake systemctl/Git/arm commands and temporary checkout fixtures.
No real timer or service was changed. This closes the reproduced command-failure,
checkout-validation, inactive-timer and pre-stop state-check defects. It also fixes
the earlier test that incorrectly allowed success in a rollback-refusal case.

The runner SHA256 is
`655561f86e9579eb87e2e1deee743071dfc07e685ea83c244211e4741e3a04c9`.
The complete patched arm script independently reconstructed from operational
production `2c088027` has SHA256
`c1cf827099bfe4b8d73b5a7d55a8533ce45f7c16a52f9c456b6d4bc10bd94424`.
Its patch SHA256 is
`1575ad8c2fd67d03592ddb30a1cf12fc37b4166eb26d5adabf9c53e46f17b32e`.

Calling the actual tracked `week_env 2 153428` with pins unset resolves the old
`week1-live-center-e7255e9` checkout and full old SHA. Explicit candidate pins
resolve `week2-release-2dc116c` and its corresponding `results/live/2026-w02`
directory. Both branches were checked in separate shell processes without
provider reads; no build was launched. The workstation separately reports both
actual checkouts clean at their expected commits. The reviewed timer patch
carries matching pins into all five builds and the watcher.

Activation remains a coordinated, quiet-window operation. A service can start
between the final status check and stop; the runner does not make this atomic.
On arm failure, **some units may already be armed**: use its per-unit report,
preserve possibly running work, and reconcile before another attempt. Nonzero
does not mean that nothing changed.

The existing manual refresh commands do not automatically acquire registry lanes.
The [release plan](2026-09-19-weekend-input-repair-release-plan.md) explicitly
requires registered ownership of each job's update/execute/reconciliation chain,
fresh provider census, all 36 verified backups, complete refresh and the actual
live CLI proof before changing runtime pins. Registry ownership alone does not
stop Cloud Scheduler; relevant writers must be coordinated independently. Pause
only schedules whose actual targets/writes conflict with the release, retaining
their previous state; a contemporaneous unrelated schedule is not itself evidence
of a conflicting writer.

No live adoption, scheduler change, backup creation, image update or timer arm
has occurred. This review accepts the prepared host implementation, not an
unexecuted release. The three input repairs remain the recommended engineering
option; ordinary DUAL_EMAX, candidate doses, contests and the disabled target
prior remain the proposed configuration.
