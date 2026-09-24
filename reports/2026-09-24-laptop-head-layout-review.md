# Adversarial review: the Week-3 head layout (`production/week3-head-layout-20260924` @ `726bc27c`)

**2026-09-24, laptop agent, answering HANDOFF `97defaf9` item 3(b).** Read-only. Nothing was run against a live book, and
`contests.json` was not read. The operator's contest list is rebuilt from the HANDOFF text (2 + 2 wildcats, 19 × sat20,
FFWC 4, 12 × supersat2 5, 3 × supersat25hi 17, 3 × supersat25lo 20; 198 entries).

**Verdict: clears for Week 3 with one operator question (F3) and one cheap guard (F2).** The rule does what the operator
asked for, all 74 tests pass, and production's rehearsal (`74360dff`) agrees with every structural check below.
- F1 is resolved (the sat20 rule is recorded in `1df6469b`).
- F2 cannot bite this week: the rehearsal's independent bundle check shows the real names group correctly. It is latent.
- **F3 changes which lineups sit in every contest, and the rehearsal shows it at scale: 50 of 144 rows barred from the
  head.** The operator should confirm that rule, or it should become the vetter's rule on both paths.
- F4 and F5 are hardening, not blockers.

## What holds (checked)
- **Legal entries and counts.** Every contest gets exactly `entries` ranks, with no rank twice inside a contest. The 198
  entries read **144 distinct rows**, so `BOOK_ENTRIES` becomes 144 under `head`. Only rows 1–4 are shared between
  contests, and no unique row repeats. Each row is a book row, so each is a legal roster (the bundle verifier still
  checks nine non-empty cells per row).
- **The operator's spec, contest by contest** (with the wildcats sharing one name; see F2):
  - wildcats: rows 1–2 and 3–4;
  - FFWC: 1, 2 + 2 unique;
  - supersat2: 1, 2 + 3 unique each;
  - supersat25hi/lo: 1–4 + unique rest;
  - unique rows dealt snake-fashion in `contests.json` order. Example: FFWC takes rows 20 and 57; supersat25hi #1 takes
    33 and 44.
- **Fail-closed paths.** An unknown layout, a missing order input, a sets file covering < 90% of the book's players or a
  short book all stop the ENTER publish and keep the previous `ENTER/`. A launcher that loses `ENTER_LAYOUT` falls back
  to `sequential`, which needs 198 rows against a 144-row book, so it fails loudly instead of publishing a wrong layout.
- **Promotion.** `run_promotion.sh` re-lays out from `$PROMOTED`, which holds `book.csv` and a renumbered
  `vetting_final.json`, with `--pin-first`, so the promoted row 1 stays row 1 in every contest. Dropping `--contests`
  from `promote_first.py` and the lineage report under `head` removes labels only (`contest_map` feeds report blocks),
  not a guard.
- **Keep semantics.** `fill_dk_entries.py` keeps each contest's first `keep` entries. Under `head` those are the head rows
  and then the earliest unique rows, the right ones to keep.
- **Tests:** `tests/test_enter_layout.py` + `tests/test_exposure_cap_book.py`: 74 passed.

## Findings
**F1 — sat20 rule (resolved).** HANDOFF `97defaf9` said "rows 1,2,3,4,1,2,… rotating". The code gives four sat20s rows
1–4 and fifteen unique rows 5–19, dealt before every other unique row. That is the operator's follow-up recorded in
`1df6469b` ("make sure we're not doing the same entries for all of those"). One consequence: the other contests' unique
rows start at row 20, not row 5.

**F2 — grouping by `name` is silent (medium: latent; Week 3's names are correct per the rehearsal).** All-head contests (≤ 2 entries) share head blocks only with contests of the
**same `name` and size**. With the reconstructed list:
- wildcats named alike: rows 1–2 and 3–4, as specified;
- **wildcats named differently** (e.g. `wildcat-a`, `wildcat-b`): **both take rows 1–2**, and nothing fails;
- likewise, if the nineteen sat20 contests do not share one name, **each takes row 1**, the opposite of "must not share
  entries".

No test or preflight can see this, because it depends on the names in `contests.json`. Suggested guard (fails closed):
under `head`, refuse when two all-head contests of the same size carry different names, or group on an explicit field.
Also print every contest's rank list in the preflight, so the operator reads the map before arming.

**F3 — "flagged" means two different things (medium-high; changes the head).** Under `fewest-low`, flagged rows go behind
every clean row:
- **from `vetting_final.json`** (whenever the replacement ran): a row with **any** flag. `vet_replace_v4.py` flags every
  DK Q/D status, **every** injury-report status and QB role/class notes;
- **from `vetting.json`** (no replacement): only rows the vetter itself demotes (hard or material).

So the same book gets a different head depending on whether replacement ran. On the replacement path, every row holding a
Questionable player leaves rows 1–4, which sit in every contest. Production's rehearsal (`74360dff`) shows it: the
replacement ran, **50 of 144 rows were flagged** on a slate with 49 Questionable players, and none reached the head. In Week 2,
48 of 97 rows held one Q player (Flowers). That is a
demotion rule the operator did not choose, stronger than "fewest LOW first, then greedy". Suggest one definition for both
paths, the vetter's demotion, plus a test that one book gets one order from either file.

**F4 — book-to-upload alignment is checked by row count only (medium).** `load_order` computes LOW counts on `--book`
(DK **player** ids) and applies the permutation to the upload's rows (slate **draftable** ids), requiring only equal
row counts. Today's callers are consistent by construction (`emit_dk_upload_csv_v1.py --source run-dir` on the same
directory). A manual relayout pointed at the wrong book would still order silently by another book's counts. Suggest
mapping each upload row to player ids through the run frame and requiring equality with the book row, or checking that
the emitter's recorded input sha equals sha256(`--book`).

**F5 — the exposure-cap report uses greedy positions (low).** `exposure_cap_book.py` places its per-contest caps on greedy
ranks, while the ENTER writer uses `fewest-low`. Its per-contest sheet then describes a contest map that is not the
entered one. It is report-only; label that in its output, or pass it the same order. The entry-weighted
`exposure_sheet.py` does use the real order.

## Rehearsal suggestion (money-path rule: test on historical books first)
Run `enter_layout write` and `check` on the Week-2 entered book directories, both paths (`paid-vetted` with `vetting.json`,
and `paid-vetted-replaced` with `vetting_final.json`), with a Week-2 `contests.json` rewritten to the head spec. Then diff
the head rows the two paths choose (F3), and print each contest's rank list (F2).
