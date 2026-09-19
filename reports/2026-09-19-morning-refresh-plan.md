# Saturday morning refresh: laptop owner, same deployed release

Prepared September 19 after the completed overnight release. This is the normal fresh-input feature → TabPFN → projection refresh for the **10:30 CDT / 15:30 UTC** build, under the existing three-fix authorization. It adds no model, image, selector, dose, contest or historical-cache change. Laptop ownership was accepted in lab handoff `38be625`; workstation `8df3fe8` commits to starting none of these jobs.

## Start and consumer coordination

Target start **09:45 CDT / 14:45 UTC**, after the 09:30 props pull. Before any warehouse mutation, require the refreshed raw inputs, unchanged approved job templates/images, clear provider execution census and all three local registry lanes. A host-local lock alone cannot exclude Cloud Scheduler, another host or a manual operator. The workstation must mark its manual refresh instructions laptop-owned and confirm no competing launch.

This planned candidate-source proof is conditional on **verified host activation to `2dc116c`**. It cannot certify a build that still runs `e7255e9`. If the pin remains unapplied, the automatic plan stays unlaunched; a proof of the old-source/refreshed-data combination would be a separately documented fallback, not completion of the authorized three-fix release. The overnight cloud changes are already shared by both source versions.

Because a partial refresh must not feed the 10:30 build, coordinate an explicit temporary hold of that Saturday consumer with the workstation. Require a fresh acknowledgment that its relevant build service is inactive, its Saturday timer is held, and no alternate/manual Saturday launch will occur until release. This is a proposed operational safeguard, not a claim that the timer has been stopped. Do not delay the other Sunday timers or stop a running build. If a suitable existing consumer gate supplies the same guarantee, review its exact behavior before substituting it.

The laptop must not start the refresh without that consumer coordination. If ready before 10:30, the workstation restores the unchanged Saturday schedule. If delayed, it reports the missed deadline and starts the same build only after validated completion and its ordinary preflight, without overlapping another build. Failure or ambiguous execution leaves the consumer held until reconciled; it is not an instruction to retry cloud jobs automatically.

## Fixed sequence and evidence

1. Verify the three deployed templates against the successful overnight release, and the existing rollback snapshots. Capture raw source timestamps/support. In particular, Week 2 props must include today's 09:30 capture; game odds, weather and injury snapshots must reflect their scheduled morning arrivals. A table modification time alone does not prove relevant slate rows arrived.
2. Acquire the `build-features`, `tabpfn-gen` and `project-slate` registry lanes for the complete sequence. Repeat the provider census immediately before each execution. Record the exact command and provider identity before proceeding; no image update, template patch or automatic mutation retry.
3. Execute `build-features`. Require its normal leakage checks, valid unique feature keys, restored Week 2 prior-game/snap support, no Week 1 future support, and expected schemas. Inspect source-driven historical changes separately; do not compare against the old broken usage snapshot and silently treat every expected correction as a new release.
4. Execute `tabpfn-gen` with only the per-execution target `TABPFN_UPCOMING=2026:2`. Require the exact logged strictly-prior-week context receipt, full-refresh mode, unique finite ordered quantiles, complete current inference keys and no missing historical keys. Use the fixed deployed strict-prior image.
5. Execute the unchanged `project-slate` image. Bind one exact new batch to that execution's timestamps, verify player/DST identity contracts, finite ordered values, unchanged registered model and real-prop coverage/branch evidence. Do not report the fallback-inclusive log count as pure Odds coverage.
6. Run the same small complete D160 CLI proof on clean lab `2dc116c`, with the authenticated existing workstation historical cache, ordinary DUAL_EMAX and normal guards. Require the exact new projection batch, 97 legal unique rows and current game inputs. This is an engineering proof, not a production-dose timing or efficacy experiment.
7. Retain all commands, logs, validation/source hashes and completion receipts. Release the writer lanes; send the exact successful execution IDs, projection batch and proof to the workstation for independent verification and consumer release.

The existing overnight snapshots and image/source rollback plan remain retained. A new refresh does not make an old source pin alone a complete rollback. No current football outcome read is needed for these checks.

## State

**Prepared plan; not scheduled or launched.** The consumer-hold mechanism and exact morning supervisor still need review. An unfinished supervisor draft is preserved only in local working evidence as `morning-refresh-draft-unreviewed.py`; it is not a launcher and must not be executed. The successful overnight release remains complete.

Workstation `d8ee83f` now records an actual activation mutation rejected by its automatic approval review (`Modify Shared Resources`), followed by rejection of the read-only verification (`Auto-Mode Bypass`). Further host attempts are not requested. It also surfaces the operator's standing expectation that he runs the three 09:45 commands. That expectation and the agent ownership agreement must be reconciled so only one producer runs. No automatic refresh or timer hold is scheduled while this coordination is unresolved. The operator's already reviewed package and ordinary commands remain available; this plan does not itself change them.

Follow-up `796cebf` correctly notes that a denied restore could leave the one-shot build timer stopped. No host write, hold or restoration is assigned to the restricted agent while that dependency remains unresolved. A future coordinated hold requires a responsible actor able to restore or launch the same service; merely writing a plan is insufficient. Unconditionally releasing a build during an unfinished refresh would abandon this plan's input-consistency guarantee and must not be described as validated completion.

This document must be updated with actual scheduling, launch, completion or stop evidence; a future start time is not a completion receipt.
