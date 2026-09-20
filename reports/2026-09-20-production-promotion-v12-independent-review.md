# Production promotion v1.2 / runner v2.1 review — 2026-09-20

Production's corrected consumer addresses all four findings from the v1.1 review, and the new ENTER re-layout closes the delivery path that would otherwise leave the promoted CSV out of the entries file.

## Independent result

I copied the exact v1.2 bytes from shared handoff `0cac952` and reran six boundaries on private copies of the v4.2 rehearsal fixtures. The reader SHA is `2026-09-20-promotion-v12-independent-review.py`; result SHA is recorded in the adjacent result JSON. No provider or outcome calls were made, and the parquet wrapper observed no unrestricted reads.

| Case | Expected / observed | Result |
|---|---:|---|
| baseline | 0 / 0 | rank 5 → 1; mean 143.5388748758316; exact CSV permutation |
| altered same-shape bank | 2 / 2 | source input hash refused before scoring |
| missing source receipt | 2 / 2 | refused |
| final-vetter OUT in a book row | 3 / 3 | publication STOP; no output |
| non-publishable receipt | 2 / 2 | refused |
| synthetic OUT through the unchanged actual vetter | 3 / 3 | publication STOP; no output |

The packet check also passes with zero difference: rank 5, candidate 782, mean 143.5388748758316. The unavailable flag classifier stops all intended membership-unavailable spellings (`DK/report/features` OUT class, healthy-primary backup QB, gated QB, placeholder salary) while leaving ambiguous/unknown QB, D/Q, market silence, and practice-only signals as non-stop risk tiers. Current-week outcome values remained unread.

## ENTER delivery review

`run_promotion.sh` v2.1 stages the upload and keepers sheet outside the page glob, validates the permutation and sheet, then calls `relayout_enter.sh` before moving the promoted upload and sheet into discoverable locations. `relayout_enter.sh` uses the chain's exact layout code and verifier, checks per-contest rows against the promoted upload, and performs a versioned `ENTER` symlink swap. The supplied tests cover success, corrupt-upload refusal, and unavailable-player refusal; the successful path verifies the promoted Millionaire row reaches the ENTER bundle.

The operational branch used for the host installation is reported as commit `e45798ba`, but that commit is not present in the GitHub remote branch `production/week1-audit-adjust-20260912` visible from this checkout (remote currently ends at `78d9616b`). The operator should preserve or push that operational commit before relying on it as a reproducibility identity. This does not invalidate the host installation receipt; it leaves the source identity unavailable to a fresh clone.

The v1.2 `SHA256SUMS` file includes a self-entry whose listed digest does not equal the final checksum file (self-hashing is inherently unstable). Treat the individual file lines as authoritative and either remove the self-entry or label it explicitly as a generation-time digest. Do not use the current self-entry as a package-integrity check.

## D12800 status and next work

The shared receipt reports D12800 complete at `20260919T153008787414Z-2dc116c`, with 12,555 candidates, K97, clean stderr, and archive `gs://nfl-2-506823-lab/research/week2-input-release-20260919/archives/20260919T153008787414Z-2dc116c-d12800/`. Its pre-replacement raw-book pooled mean is 203.45 and P220 22.3%; these are conditional simulator metrics, not NFL efficacy or post-vetter contest results. The preview final book's v1.2 promotion moves rank 7 to first at mean 144.3088699419, but that preview used scratch outputs; Sunday’s fresh status/replacement and receipts remain authoritative.

The next experiment should use the archived D12800 input and a frozen final delivered book to compare first-entry mean, tail proxy, and P220 order rules on the same two selection banks, then report contest-block cost. It can start outcome-blind immediately after the Sunday receipts are frozen. Keep the exposure-cap work as a Week-3 insurance shadow; it did not show a nominal scoring gain.
