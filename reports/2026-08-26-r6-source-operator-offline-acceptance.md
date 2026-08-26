# R6 matchup-source operator offline acceptance

Date: 2026-08-26

Final disposition: **APPROVED for an offline validate-only commit only**

## Exact reviewed artifacts

This acceptance binds exactly these three candidate artifacts:

| Artifact | SHA-256 |
| --- | --- |
| `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py` | `3a1ebd4fab2b4fecffecba1785c6f4a237718f173a64c779e79ea18ca1b95cc3` |
| `scripts/run_corpus_r6_matchup_source_operator_v1.py` | `cc1ea47d311d4c8e769fa927c7a43b452bfc42691c0035f46daf40f0d39e9f00` |
| `tests/test_corpus_r6_matchup_source_operator_v1.py` | `7840d16c0c6d82fb24d5469f7812fde73518d01d75dfab4a4bae3e14647f5bfb` |

Any byte change to any of these files falls outside this acceptance and requires
fresh validation and review.

## Validation and review evidence

- The author reported exactly one focused pytest invocation with 28/28 passing.
- The independent final review was static only and found **P0 none, P1 none,
  and P2 none**.
- Independent static compilation of the three exact artifacts passed 3/3
  without creating bytecode.
- The test file contains 20 test functions; its one nine-case parametrization
  statically accounts for the reported total of 28 cases.
- The independent reviewer did not rerun pytest.

Before this report was added, targeted status showed exactly the three reviewed
candidate files as untracked and no change to the tracked repository
instructions or existing matchup-source contract.

## Accepted validate-only behavior

The accepted public boundary has these properties:

1. `run_matchup_source_operator_v1` accepts only the input bytes and the exact
   `validate_only` boolean. It accepts no store, carrier, project, or catalog
   input. Every `validate_only=False` request fails with `frozen 54-entry
   authority catalog unavailable` after bounded bundle parsing
   (`corpus_r6_matchup_source_operator_v1.py:1683-1696`).
2. The public result-receipt validator independently rejects every
   `mode="execute"` receipt before any execute-authority shape can be accepted
   (`corpus_r6_matchup_source_operator_v1.py:1528-1544`).
3. Validate-only performs the full semantic source replay in an ephemeral
   memory exact-object store. It publishes no external result identity and
   returns `capture_mechanics_authority=false`, `published=false`, null trusted
   artifact identities, false external exact-reopen flags, no outcome columns,
   and every unrelated authority false
   (`corpus_r6_matchup_source_operator_v1.py:1625-1637` and `:1697-1725`).
4. The former public capture-authority schema, builder, and validator names are
   absent from the module and from `__all__`. The remaining fixture builder and
   validator are underscore-private and cannot enter the public run path
   (`corpus_r6_matchup_source_operator_v1.py:38`, `:901`, `:961`, and
   `:1728-1747`).
5. The CLI exposes no project, carrier, storage-client, or catalog-authority
   option. Its reserved `--execute` flag truthfully reports that execute is
   unavailable, while `--validate-only` constructs no cloud client
   (`run_corpus_r6_matchup_source_operator_v1.py:1-53` and `:147-175`).

Focused adversarial coverage binds these claims:

- validate-only has no trusted mechanics or external publication authority
  (`test_corpus_r6_matchup_source_operator_v1.py:191-217`);
- the former public minting names remain absent
  (`test_corpus_r6_matchup_source_operator_v1.py:220-227`);
- ordinary and fully coherent caller-selected execute chains remain blocked
  (`test_corpus_r6_matchup_source_operator_v1.py:230-256`);
- a canonically rehashed execute-mode result receipt is rejected by the frozen
  catalog gate (`test_corpus_r6_matchup_source_operator_v1.py:259-276`);
- coherent catalog, source-authority, accepted-reconstruction, ordinal, query,
  relation, code, and output substitutions cannot enable execute
  (`test_corpus_r6_matchup_source_operator_v1.py:415-439`); and
- CLI execute produces no result and returns the frozen-catalog error
  (`test_corpus_r6_matchup_source_operator_v1.py:623-638`).

The previously reported P2 parser and storage defects are also closed:

- huge JSON integers are converted to the controlled operator exception;
- unhashable result modes are type-checked before set membership; and
- generation-pinned GCS metadata size is checked before a bounded range
  download.

## Explicit non-approval boundary

This acceptance does **not** approve or authorize:

- execute mode;
- a 54-entry catalog implementation, catalog root, or catalog integration;
- caller-supplied carrier authority;
- GCS or other cloud execution or publication;
- BigQuery or any live source query;
- capture-mechanics authority;
- scoring, fill, retrieval, graph, promotion, decision, production, or
  production-policy authority;
- reading realized outcomes or any outcome-bearing artifact; or
- integration with or modification of T230.

A future execute implementation must introduce the separately reviewed,
non-caller-selectable pinned 54-member catalog root and undergo a new independent
review. This offline acceptance cannot be cited as evidence for that future
execution boundary.

## Review boundary

The independent review and this preservation step performed no pytest, cloud,
BigQuery, GCS, IAM, outcome, scoring, promotion, or T230 action. No candidate or
tracked project file was edited, staged, or committed as part of the review.
This report is the only file added by the preservation step.
