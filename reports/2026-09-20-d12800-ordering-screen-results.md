# D12800 ordering screen: pooled mean points to preview rank 7; P220 does not

This is an outcome-blind screen of the completed D12800 archive. It reads only allowlisted identity columns (`id`, `dk_player_id`, `salary`, `name`), candidates’ `players`, the two selection banks, and DK-id books. No current outcome, audit, provider, or actual-value columns were decoded. The result is pre-vetter research and cannot replace Sunday’s fresh status/replacement receipts.

The archived run is `20260919T153008787414Z-2dc116c`, D12800 (lev 2,560 / boom 10,240), 12,555 candidates, K97, 10,000 worlds per bank. Archive manifest and all downloaded object hashes match. Selection banks are the same D6400 banks: incumbent SHA `1d711ff9…`, corrected hsim SHA `c9f97729…`.

On the **scratch post-replacement preview book** supplied in the installation receipt, the current first row has pooled selection mean 139.8872, P220 0.785%, and P230 0.295%. The highest pooled mean among delivered ranks 1–30 is current rank **7**, candidate 2123, at 144.3089 (**+4.4217**). The highest P220 remains current rank 1 (no change); P230 also selects rank 7 (+0.045 percentage points). The pooled mean and P220 objectives therefore disagree on this book. The handoff’s preview value 144.3088699419 differs only in displayed floating-point rounding from the independently recomputed 144.3088699442.

Bank-specific mean choices disagree strongly on the preview: incumbent rank 28, corrected hsim rank 14, pooled rank 7. Bank-specific P220 choices are ranks 20 and 21, while the pooled P220 choice is rank 1. This supports keeping the equal-mass two-bank rule and reporting component disagreement rather than choosing a single bank’s head.

The same screen on the **raw archived K97 book** finds the existing first row already highest by pooled mean, P220, and P230 (mean 150.3344, P220 1.280%, P230 0.610%). The raw `book_wemax.csv` has the same first row and gives the same three head choices, though its later top-30 order differs. This confirms the post-replacement ordering question is a delivery/vetting effect, not a raw-generation head change.

For the preview book, replacing the first row with the pooled-mean rank 7 reduces the simulated max of the unchanged rows 2–24 block by 0.4771 points and 0.290 percentage points of P220. Replacing it with the P220-selected rank 1 reduces that block mean-max by only 0.0581 and P220 by 0.010 pp. These are conditional simulator diagnostics, not a contest efficacy estimate; they quantify the tradeoff behind putting a candidate into the Millionaire slot.

The next experiment is ready: repeat this objective comparison on the **fresh Sunday final book** after status/replacement, preserving mean, P220, P230, both bank components, and block 2–24 costs. Do not carry the preview rank 7 into the live book automatically. If the fresh book again has a mean/P220 disagreement, use the operator’s selected objective and record the displaced-block cost explicitly.

Evidence: [reader](reviews/evidence/2026-09-20-d12800-ordering-screen.py), [result](reviews/evidence/2026-09-20-d12800-ordering-screen-result.json). Private downloaded archive and preview inputs are under `/home/erich/projects/review-evidence/overnight-20260918/d12800-archive-20260920/`.
