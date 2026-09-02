# PREREG-053 / experiment 084 production cross-verification

**Date:** 2026-09-02
**Disposition:** **Cross-verification PASS.** Production independently reproduces the lab's first formal proxy PASS for `T_NOBB_TAIL`. The scientific trigger for the frozen PREREG-055 / experiment 086 D800 compatibility crossing is satisfied. This is historical proxy evidence, not prospective-settlement adoption authority.

## Frozen identity reproduced

- Efficacy runs, in frozen order:
  - `084b590r2-20260902T054328Z`
  - `084b591r2-20260902T054604Z`
  - `084b592r2-20260902T072634Z`
- Frozen source: `798b869e3992f4ff7e8f6c4527619ca546f2279c`
- Immutable image: `sha256:2d352f5de1353fde6c6e41d3d3da2dd17dc3a5b384060b9b12fba38fe6170abe`
- Bound reader SHA-256: `e5ce5d9ff91a61b02409ab4031e054533af544a61e9031a820f4733ce089abb5`
- Mechanics run: `084m590r2-20260902T041825Z`
- Mechanics receipt SHA-256: `4dc31e4ceab099a638911acfac136bf411efc9c4e08e6af34571dcdc016bea23`
- Winner-score registry: `winner_cdf_v1`, 48 records, 2023-2025 era, SHA-256 `4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f`, authority `lab-48-score/pre-adjudication`.

Production ran the frozen reader from worktree commit `e3318847530317eaaf4461873c515e865eaa8f2f` with an isolated import bootstrap that inserted that worktree's own `src` first. This avoids the worktree `.venv` editable-install symlink importing the mutable lab main tree. The reader itself exited `0` after emitting all 90 report lines and all final sleeve-engagement/vacuity checks.

The complete immutable transcript is:

- `reports/2026-09-02-prereg053-production-cross-verification-transcript.txt`
- 13,173 bytes, 90 lines
- SHA-256 `4ef603d0a9e3a9718caa1abdb2ed6430a859ab5f10b13a5b96eee687ca0c4c6f`

## Independent result check

`T_NOBB_TAIL` is the only primary arm with `VERDICT=PASS`:

| Measure | `T_NOBB_TAIL` versus `T_BASE` |
|---|---:|
| Primary winner-range proxy | `+0.00271` |
| Multiplicity-adjusted family interval | `[+0.00147, +0.00355]` |
| Bank deltas 590 / 591 / 592 | `+0.003015 / +0.003254 / +0.001853` |
| Leave-one-season-out estimates | all four positive |
| Weekly W/L/T | `36 / 28 / 8` |
| Weekly sign-flip p-value | `0.2858` |
| Raw weekly K80 maximum | `+1.009 [+0.325, +1.694]` |
| Raw bank deltas 590 / 591 / 592 | `+0.712 / +1.638 / +0.678` |
| Fixed-delivered-count proxy | `+0.00370`, every bank positive |
| Weeks at least 194 | `20` versus `17` |
| Weeks at least 200 | `9` versus `8` |
| Roster hits at least 187 | `160` versus `152` |

The result is specific: removing the bring-back requirement for the final 160 boom worlds while preserving world coverage helps. The concentrated same-world version fails because bank 590 vetoes it. Tail relaxations of the QB-catcher requirement do not help: `T_NOQS_TAIL` fails with a bank-592 veto and `T_FREE_TAIL` has a family interval entirely below zero. This supports the no-bring-back tail sleeve, not wholesale removal of every construction law.

The full mechanics census also proves the treatment was engaged rather than vacuous. Across the natural `T_NOBB_TAIL/boom:nobb` sleeve, 34,526 rosters were delivered and 26,016 had no bring-back.

## Lab-prefix reconciliation

The lab's visible first-read output came from a command ending in `grep ... | head -45`. Its 45 scientific lines are byte-identical to the first 45 production lines:

- Lab 45-line prefix SHA-256: `3bf5368cd083622aca191ca95a7e23188937b09f850ba4d024799093bc5e203a`
- Production 45-line prefix SHA-256: `3bf5368cd083622aca191ca95a7e23188937b09f850ba4d024799093bc5e203a`

That lab command did not use `pipefail`; therefore its displayed exit zero was the pipeline's terminal status and did not prove that Python reached the final engagement checks. It also omitted the last 45 lines. Production's unfiltered run closes both gaps: the Python reader itself exited zero, the prefix matches exactly, and the omitted thresholds, portfolio diagnostics, and all 13 final mixture lines are now durably captured.

## Decision and next action

1. Preserve `T_NOBB_TAIL` as the first formal historical proxy PASS, with the explicit caveat that the 48-score registry is pre-adjudication and prospective 2026 settlement remains the adoption authority.
2. Proceed with PREREG-055 / experiment 086 as the already-frozen compatibility crossing: plain D800 versus D800 with the final 160 boom solves assigned to the no-bring-back tail sleeve.
3. Do not launch 086 efficacy from its initial files. The prelaunch audit found that its reader incorrectly pinned the old 084 mechanics receipt, no 086 gate/registered launcher existed, and the single-treatment reader had a strict-zip crash. A clean-source launch-contract repair and a new outcome-disabled `086m600r1` gate are required first.
4. If the new mechanics gate passes and its source/image/receipt are bound into the reader, release banks 600-602 through the shared registered coordinator. Do not reinterpret the 084 PASS as proof that the sleeve stacks with D800; that interaction is exactly what 086 measures.
