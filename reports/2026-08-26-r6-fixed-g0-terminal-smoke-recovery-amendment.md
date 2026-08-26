# R6 fixed-G0 terminal-smoke recovery amendment

Date: 2026-08-26

## Purpose

This amendment closes the two consumed fixed-G0 adapter task-0 attempts
truthfully and permits the already-designed 54-slate player-catalog projection
to proceed without a third smoke. It does not license realized outcomes,
historical scoring, lineup selection, corpus mutation, graph mutation,
promotion, or production strategy changes.

## Frozen facts

The v1 attempt stopped before GCS client construction because its temporary
virtual environment could not import `google.cloud.storage`. Its marker is:

- `reports/2026-08-26-r6-player-catalog-fixed-g0-task0-real-artifact-smoke-attempt.json`
- SHA-256 `35d2a32334f7b06074a8f37245042881f4dd100796e3093b1e09639a6d81ae48`
- 3,278 bytes
- internal self-hash
  `2e3adc38313f2811cf7d245e77d7838915cb9602cc416e3c581e20d029d57eff`

The v2 attempt stopped after GCS client construction but before its first
generation-pinned GCS object read. Its marker is:

- `reports/2026-08-26-r6-player-catalog-fixed-g0-task0-real-artifact-smoke-attempt-v2.json`
- SHA-256 `36e28956944cf3d9ed68152d773f381838c3385965d0bb47bfca0f068deaa6c5`
- 3,904 bytes
- internal self-hash
  `8a2d364c711c047a6704c9e441cea7b9275671bad224428575c62b1ccbfa1115`

The v2 failure is a single representation defect: the immutable receipt uses
the producer's canonical schema
`foundry-v12-panel-index-publication/v1`, while the adapter and its synthetic
fixture expected the nonexistent
`foundry-v12-panel-publication-receipt/v1`. The complete defect-class sweep is
recorded in
`reports/2026-08-26-r6-fixed-g0-v2-smoke-publication-schema-failure.md`.
Only the adapter and its fixture carry the wrong literal; every producer and
other consumer carries the canonical schema.

No success receipt exists for either adapter attempt. The lifetime adapter
attempt count is two. A third adapter smoke, a renamed smoke, or an equivalent
manual GCS replay is prohibited.

## Existing real-artifact proof

The same accepted G0 panel already passed the stronger outcome-blind
production one-slate smoke for `2023-w01`. That execution read and verified
the exact fixed panel, task-0 acceptance, carrier, later-source identity, five
world artifacts, seven arm result bindings, reconstruction, and support
census. It exited zero and wrote:

- result path:
  `reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index/panel-index-live/extreme-tail-smoke-2023-w01/result.json`
- result SHA-256:
  `73464ee66c358dbedf30d34b6348e049e5e218a28f542428053a0d6e6674ac99`
- result bytes: 386,371
- result internal self-hash:
  `ceddab226e3ff66e5668e227d144c1431cb889da95e90570d9b7619d35fd346e`
- execution-time evidence path:
  `reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index/panel-index-live/extreme-tail-smoke-2023-w01/time-v.txt`
- execution-time evidence SHA-256:
  `89261ccb4fe08d7ae137c07f45979e49e1fd48a136e7042840f496b61da0e3cc`
- execution-time evidence bytes: 1,251

The result binds panel generation `1787663639938214`, panel content SHA
`4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9`,
task-0 acceptance generation `1787524357272657` and SHA
`800e673713602035daed571c0d11dea9f2cc841ca4e33145b8763a162096d0a4`,
and carrier generation `1787521590972723` and SHA
`8149de8f5ca66c89d1137b92328f0add7f76c46aeff281d9323ca6ac5ce20548`.
All verification flags are true; all authority fields and
`uses_realized_outcomes` are false.

## Bounded implementation correction

The correction may do only the following:

1. Replace the adapter and fixture's nonexistent publication schema literal
   with exact `foundry-v12-panel-index-publication/v1`.
2. Add an offline regression that reads the immutable receipt and G0 lock from
   evidence commit `168bc70a9793dce729d7e7e0a5d809b046a7a254` and exercises the same
   adapter validator.
3. Add a terminal-recovery controller that exact-binds both failed attempt
   markers, the v2 failure report, the recovery lock, the successful prior
   smoke result and exit record, the immutable G0 lock/publication receipt,
   and the corrected implementation/test bytes.
4. Build a two-phase local review lock and final release lock. The review lock
   grants no cloud action. The final lock may license only the fixed 54-slate
   catalog projection command after independent static review and one focused
   offline test invocation pass.
5. The final lock must state that both adapter attempts failed, no adapter
   success receipt exists, the prior production real-artifact smoke passed,
   lifetime adapter attempts equal two, and a third attempt is forbidden. It
   must never reinterpret either failed marker as a pass.

The base adapter-review binding may remain the earlier reviewed binding used
to define the replay contract, but the terminal-recovery locks must separately
bind the corrected code and test bytes that actually execute the projection.
The resulting replay receipt therefore retains its base-contract review
lineage while the final recovery lock supplies the corrected-execution
lineage.

## Projection execution boundary

The licensed projection command must derive all 54 inputs and exact-reopen all
54 small task-acceptance bodies and all 54 small carrier bodies before it
creates any output. It may then create only the fixed namespace's 54 catalog
pairs, catalog release, and replay receipt using generation-match-zero and
exact generation reopen. Existing byte-identical objects may be resumed;
unequal collisions fail closed. It may not read world-matrix or arm-result
bodies and may not access realized outcomes.

Any additional schema failure before output creation is an implementation
defect in the materializer, not authority for another smoke. Correct it
offline against the exact immutable identities and resume only after a new
tracked review lock. No score or strategy decision may be inferred from this
source-only operation.
