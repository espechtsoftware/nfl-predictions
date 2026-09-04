# Production independent review of PREREG-064C / experiment 092

Date: 2026-09-04  
Production review basis: frozen lab source `a08da15e44a82bb301963d99c5df289b4315e10b`  
Disposition: **the lab result is reproduced byte-for-byte; M2 closes in its tested form**

## Production finding

Production independently reran the frozen PREREG-064C reader against the exact
registered efficacy runs:

- bank 660: `092b660r1-20260904T015211Z`, execution `lab-run-m5w7b`;
- bank 661: `092b661r1-20260904T015426Z`, execution
  `lab-run-slow-qf6qs`;
- bank 662: `092b662r1-20260904T023545Z`, execution `lab-run-skvgt`.

Provider state independently confirms 18/18 successful tasks for each
execution with zero failures, cancellations, and observed retries. All three
used immutable image digest
`sha256:cd642db9c943bb4b8a42e11f82c131ee1ae24778ed835a1c26fdee8b7dc53a24`.
The bound reader bytes have SHA-256
`ee2aa80a9713cedff5898196040b772e8d69bd7c11c6e204ad218e44647ab72c`.
The reader exited zero, and production stdout has SHA-256
`df54444f637ea971b0311864e7bb564a294a5e5ff8400ec38c7e73ac105dfe01`,
exactly matching the lab's committed first-read transcript.

The reproduced registered results are:

- `M2 - M0`: `+0.00137`, family interval `[-0.00022, +0.00389]`,
  `p = 0.4473`, verdict `UNPASSED_NEAR_MISS`;
- M2 bank effects: `-0.00037`, `-0.00215`, and `+0.00662`;
- M2 raw realized K80 weekly-maximum change: `+0.128` points, interval
  `[-0.256, +0.625]`;
- `NP - M0`: `-0.00240`, family interval `[-0.00496, -0.00053]`, verdict
  `FAIL` rather than a positive false signal;
- NP raw realized K80 change: `-0.391` points, interval
  `[-0.602, -0.141]`;
- selected-roster contamination: M0 `21.80%`, M2 `19.76%`, NP `21.88%`;
- M2 book Jaccard versus M0: `0.790`, with an average `2.64` players added;
- mean realized K80 maximum: M0 `181.228`, M2 `181.356`, NP `180.836`;
- A5 M2 raw prefixes: K3 `+0.737`, K10 `-0.404`, K20 `-0.335`, K57
  `+0.164`.

The frozen NP void rule does not fire: NP was significantly negative, not
significantly positive. The experiment is therefore mechanically informative
and the M2 estimate may be interpreted.

## Interpretation

M2 changes the selected book, reduces inactive-player contamination, and
produces some favorable descriptive tail counts. Those facts establish that
the treatment engaged. They do not clear the preregistered efficacy gate:
the family interval includes zero, two banks are negative, and the A5 prefixes
are mixed. The large positive bank-662 result is not sufficient to adopt the
treatment.

The most plausible mechanism is overlap with the P_MIX participation judge:
M2's compact residual contains availability-related information, while P_MIX
already prices participation directly. That interpretation is a hypothesis,
not authority to refit or retest M2 on this panel.

## Production disposition

1. Accept the lab's 092 seal and require no rerun.
2. Do not adopt M2 or NP into the Week-1 generator or selector.
3. Close M2 at its frozen artifact, feature set, and dose; do not reweight it
   or produce a second same-panel artifact.
4. Preserve P_MIX certification and prospective participation work as separate
   paths; this result does not close participation-aware generation.
5. Continue D6 and the real-artifact 093 smoke/freeze path. Keep 091 held.

No scoring code, production policy, graph state, paid-entry state, or cloud
experiment was changed by this independent review.
