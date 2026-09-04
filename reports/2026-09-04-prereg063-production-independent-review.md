# PREREG-063 / experiment 093 production independent review

Date: 2026-09-04 UTC

Disposition: **sealed result accepted; PG_AWARE accepted as a prospective
shadow; no paid-policy adoption; PREREG-065 design approved to proceed through
the normal freeze and mechanics gates.**

## Independent replay

Production ran the exact bound reader from lab release commit `2696da5`:

```text
scripts/prereg063_report.py
  093b670r1-20260904T064155Z
  093b671r1-20260904T064407Z
  093b672r1-20260904T074531Z
```

The reader SHA-256 was
`cab4f86fd35be6a573a4d6228ae7a24b0203ad65c0337f4bec418a5f33dd8ef3`.
It exited zero and reproduced the lab's committed first-read transcript and
ledger values:

- registered K80 winner-CDF proxy: `PG_AWARE - PG_CTRL = +0.00242`, family
  interval `[+0.00007, +0.00477]`, verdict `PASS`;
- bank estimates `+0.004094`, `+0.003944`, and `-0.000772`; bank 672's
  interval spans zero and does not trigger the frozen veto;
- all four leave-one-season-out estimates are positive;
- raw K80 weekly-max change `+0.864 [+0.244, +1.397]`;
- mean corpus oracle `194.398 -> 195.417`, with candidate counts at 200+
  `240 -> 265`, 220+ `20 -> 26`, and 230+ `6 -> 10` at unchanged unique
  delivery;
- selected-lineup inactive contamination `16.44% -> 15.94%`;
- A5 raw prefix effects remain mixed: K3 `+0.240`, K10 `-0.168`, K20
  `-0.497`, K57 `+0.142`.

The result is correctly described as a thin preregistered pass. It supports a
prospective shadow and the next mechanism crossing; it does not justify
silently replacing the entered Week-1 `D800_DEMAX + P_MIX` policy. The
production ledger row and lab transcript agree with the independent output.

## Routing decision

Production accepts `PG_AWARE + P_MIX` as a separate outcome-blind prospective
Week-1 shadow. It must be frozen beside the entered book and `P_CTRL`, use the
same timestamped participation inputs, and remain unentered unless a later
explicit operator decision changes the paid policy.

The draft PREREG-065 / experiment 094 mechanism crossing is the direct test
earned by PREREG-063's frozen routing. Production approves the lab to freeze
and implement the bounded three-arm design as written:

- `PG_CTRL`;
- exact-replication `PG_AWARE`;
- mass-conserving `PG_REDIST`;
- identical P_MIX judge and fixed 800-solve budget;
- primary `PG_REDIST - PG_AWARE` and co-primary replication
  `PG_AWARE - PG_CTRL`;
- fresh banks 680--682 and a real engaged mechanics gate before efficacy.

This approval does not waive the clean-source build, immutable image, engaged
mechanics receipt, pinned reader, registered single-writer launch, or the
lab-first-read boundary. Experiment 091 remains held.

## Live D800 rehearsal finding

While the independent reader was running, production executed an outcome-blind
local rehearsal from exact clean lab commit
`c51c150e277d23d97666c976890cd6e245d9b6ec`:

```text
scripts/live_week.py --season 2026 --week 1 --group 151307
  --entries 80 --sims 10000 --lev 160 --boom 640 --k 1
  --seed 2026 --selector dual_emax
```

It completed in 264.6 seconds with 800 candidates, exact K80, zero selected
DraftKings or named-strategy violations, and no outcome access. This is a
diagnostic artifact only and is not accepted as the live candidate authority.

The frame retained 109 skill rows with roster status `DEV` and one with status
`W04`; ten of the 800 candidate lineups contained at least one non-`ACT` skill
player. None of those ten reached the selected K80, but candidate-corpus
eligibility is still wrong and wastes fixed admission budget. The final live
generator must use the same complete target-week active-roster boundary as the
certified production projection pool: active fantasy-role skills only, with
DST handled separately, and an explicit fail-closed source receipt. Do not
publish the current rehearsal or use it as P_MIX candidate authority.

The rehearsal also had zero current injury-report rows, which is expected this
early in the week but means it cannot demonstrate an engaged live P_MIX or
PG_AWARE treatment. Its projection receipt explicitly used the degraded
no-ownership path. These are disclosed rehearsal limitations; the final
pre-lock run must be refreshed once the designated/practice and ownership
inputs exist.

The live-input correction is independent of historical experiment 094 and
should not delay its freeze or implementation.
