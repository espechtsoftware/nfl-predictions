# Paid-source artifact recovery and next experiment boundary

Checked 2026-09-20 against the shared GCS corpus-retrieval bucket and the local paid-source experiment worktree.

## What was recovered

The frozen Experiment 5 discovery artifacts are present for all 54 historical slates (2023–2025, Weeks 1–18):

- discovery matrix run `exp5-discovery-matrix-20260911d` (and reopened successor `exp5-discovery-matrix-20260911e`);
- candidate authority release `20260830-fixed-g0-candidate-authority-v2`;
- four discovery world blocks (R0–R3), 40,000 worlds per slate;
- an R4 held-out world block that is explicitly marked unread by the discovery run;
- per-slate candidate manifests, matrix identities, lineage hashes, and terminal/reopen receipts.

The root manifest states that no outcome columns were read, graph or production mutation was not licensed, and the matrix representation is candidate-by-simulated-world DK points. The candidate authority contains roster IDs and roster hashes, but no source-specific alternative candidate population.

## What this means for the paid-source work

These files are sufficient to reproduce the already completed direct paid-source ladder and admission-cap study. They are not a missing SIS/Fantasy Points shadow schedule, nor do they provide a new source-conditioned candidate set. Reusing them with a different label would be the same experiment.

The completed results therefore remain the operative evidence:

1. The direct 54-slate ladder found no points gain at K20/K40/K80. SIS-conditioned K20 finish had a positive mean but failed its sign-test rule and went null at larger K.
2. The admission-cap study lifted the admitted ceiling from about 181 to 202 points, but did not improve K20 realized maxima. The source-free tail-aware admission was at least as good as the paid-source gate.
3. At the uncapped admission, Fantasy Points plus SIS versus both off was null at every K. This closes the historical retrieval/admission route for vendor value.

## Next valid experiment

The remaining measurable gap is selector calibration: the simulator exposes realized 194–202 point lineups, but coverage-194 selection does not consistently place them first. The next experiment should keep the candidate authorities and source manifests fixed, use only pre-outcome features, and compare tail-calibrated selectors (for example, a shrinkage-calibrated upper-tail probability or a simple tail-count blend) against coverage-194 on the same held-out weeks. It should report K20/K40/K80 realized maxima, 220+ capture, and finish, with a frozen selector before outcomes are read.

No production change follows from this recovery. The paid-source evidence is complete enough to avoid launching another historical SIS/Fantasy Points ablation; a renewal case would require a genuinely prospective shadow with a new live source capture and a predeclared selector use.

