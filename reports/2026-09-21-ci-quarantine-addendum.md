# Addendum to the CI triage: quarantine is the wrong frame, and one cached file is at risk

This corrects the open question I left at the end of
`reports/2026-09-21-ci-failure-triage.md`. I asked whether the frozen chains
should move into the test quarantine. Having read the mechanism and the
contracts, that is the wrong question.

## 1. The mechanism already exists, and CI does not use it

`scripts/test_lanes.sh` provides four lanes (`money`, `changed`, `full`,
`quarantine`) and its `full` lane is exactly what a red CI needs: it runs
everything, then classifies each failure as **KNOWN** (quarantined) or
**NEW**, exits non-zero only when `NEW > 0`, and prints
`RELEASE CANDIDATE (no longer failing)` for any quarantine entry that has
started passing. It uses `-rfE` rather than `-rf` specifically so that errors
are not invisible to a lane that only greps failures. The design is sound and
it never hides anything.

**`.github/workflows/ci.yml` line 24 runs bare `pytest`.** The classifier is
never invoked. That is the immediate gap.

The quarantine currently holds **3 modules of the 38** that fail.

## 2. But most of these tests cannot pass in GitHub CI, by construction

`src/nfl_dfs/research/corpus_retrieval_v2_implementation_contract.py` pins a
**numerical runtime identity**, not just source hashes:

- `_PYTHON_VERSION = "3.14.4"`, plus the interpreter binary's exact
  `_PYTHON_EXECUTABLE_SHA256` and `_PYTHON_EXECUTABLE_BYTES = 7_481_192`
- `_NUMPY_VERSION = "2.5.1"`, plus the numpy core binary's sha256 and byte count
- `numpy_cpu_features_true` — the **host CPU feature flags** (AVX, AVX2, BMI,
  BMI2, CX16, F16C, FMA3, LAHF, …)
- byteorder and every dtype spelling, plus the numpy error policy

The GitHub runner cannot satisfy any of this. `ci.yml` installs
**Python 3.11** via `setup-python`, `pyproject.toml` asks only for
`numpy>=1.26` so the numpy build is whatever resolves that day, and runner CPU
models vary between jobs.

Four failing modules pin this directly; the rest reach it transitively — the
observed error `CorpusR6CurrentBankSelectorSuccessorV1Error: frozen upstream
selector contract drifted: roadmap retrieval numerical runtime differs` is a
successor validating an upstream contract that carries the pin.

**This is the design working, and the design is right.** Bit-identical
numerical replay genuinely does require an identical numerical runtime; CPU
feature flags change floating-point results. These are **workstation-local
reproducibility gates**, not CI tests.

So the disposition is not "quarantine them." It is: **they should not execute
on a GitHub runner at all**, and they should keep running in
`scripts/test_lanes.sh full` on the pinned workstation, where the assertion is
meaningful. Quarantining them in CI would record a permanent "known failure"
for a test that was never capable of passing there — which is how a real
regression gets lost, exactly as the quarantine file's own header warns.

Two things follow, both of which are decisions rather than edits, so I have
made neither:

1. CI should run the money/changed lanes, or `test_lanes.sh full`, rather than
   bare `pytest`.
2. The runtime-pinned chains need a marker (e.g. `requires_pinned_runtime`)
   deselected on any host that does not match the pinned identity — fail-closed
   by *skipping with a stated reason*, never by relaxing the pin.

## 3. Time-sensitive: the recovery artifact is still present but unprotected

The existing quarantine entry records the workstation's own drift and the
pending decision:

> 2026-09-12 … pins `/usr/bin/python3.14` as of 3.14.4-1ubuntu0.1
> (sha `b8d8288f…`); apt moved it to 1ubuntu0.2 on 2026-09-09. … Operator
> decision: hold the package or re-freeze the contract.

Verified today:

- installed: `python3.14` and `python3.14-minimal` are **3.14.4-1ubuntu0.2**
- **the 1ubuntu0.1 debs are still in `/var/cache/apt/archives/`**, so the
  documented recovery (`dpkg-deb -x` that deb and run that interpreter) still
  works

That second point is luck, not policy. **An `apt clean`, an autoclean, or a
routine disk sweep destroys the only local copy of the pinned interpreter**,
and with it the ability to reproduce every frozen numerical chain at its
contracted runtime. The operator decision has been open for nine days.

The cheap, reversible protective step — which does not decide anything — is to
copy the two cached debs somewhere durable:

```
cp /var/cache/apt/archives/python3.14{,-minimal}_3.14.4-1ubuntu0.1_amd64.deb \
   ~/pinned-runtime/
```

I would recommend doing that before the decision, not after.

## 4. Done, and verified: the pinned interpreter is preserved and reproducible

Because losing the cached debs is irreversible while copying them is not, I
took the protective step rather than waiting on the decision:

```
/home/erich/pinned-runtime/python3.14_3.14.4-1ubuntu0.1_amd64.deb
/home/erich/pinned-runtime/python3.14-minimal_3.14.4-1ubuntu0.1_amd64.deb
```

The apt cache copies are untouched; these are additional copies, and deleting
the directory undoes it completely.

I then verified the documented recovery end-to-end rather than assuming it.
Extracting the preserved `-minimal` deb yields an interpreter that matches the
contract literals exactly:

| | extracted | contract pin |
|---|---|---|
| bytes | 7,481,192 | `_PYTHON_EXECUTABLE_BYTES = 7_481_192` |
| sha256 | `b8d8288faefdd300201f43fcf00f6f539a27218eeed3a3dff5ab10b9c4c99700` | `_PYTHON_EXECUTABLE_SHA256` |

So the "hold the package" option remains genuinely available, and the frozen
chains can still be run at their contracted runtime on this workstation. That
was true by luck an hour ago; it is now true by arrangement.

This does not settle the operator decision — re-freezing the contract against
1ubuntu0.2 is still the other option, and may be the better one, since holding
a superseded system interpreter indefinitely has its own cost. It only means
the decision can no longer be lost to a disk sweep.
