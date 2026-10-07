# Preregistration: study 38, the FP paper co-run (the regulars' structure beside the yes-book, under the projections we play with) (FROZEN 2026-10-06; AMENDED 2026-10-06 and 10-07, amendments 1, 1b, 2, 3, 4, 5, 6 and 6b, before Week 5's lock)

**Status: FROZEN 2026-10-06** by the reviewer, BEFORE any week of the decision arm (MIXT_RS0) or of the exploratory arms
QBB0 / NQC0 / QAL / RBC0 was read on any slate. Disclosed: before the freeze, the reference MIXT_QA0 was scored on
Weeks 1–4 (his rehearsal of the current process, 10-06), and MIXT_QA against MIXT_QA0 on Week 4 (the ownership-tilt
test). Those reads cannot move a prospective rule on Weeks 5–9 whose decision arm was never read. The live-mode census
on the Week-5 rehearsal snapshot is a post-freeze INTEGRITY GATE (§7), not a design step. The laptop acks and re-runs every
score. Nothing here enters a contest: the money path, its checkout and its files are never touched.

## Amendment 1 (2026-10-06, before Week 5's lock; no Week-5 outcome exists)

- **Why.** The operator adopted the union overlap limit 5 for Week 5 (10-06, through the laptop: "Enter it in Week 5";
  `UNION_MEAN_MAX_SHARED=5`: every union row shares at most 5 of 9 players with every earlier row; the outside review's
  fixed-book screen of Weeks 2–4, reproduced by the laptop). The frozen parity (§3) required the overlap 7, so every
  week with a live 5 would have been INVALID (PARITY REFUSED), and the decision pair would no longer have been "the
  regulars' structure vs his live book".
- **What changes:**
  1. Every paper arm is built at THE LIVE UNION'S `--mean-max-shared`, read from its own arguments (study 18's
     `MAX_SHARED`, which the cap builder reads at every solve, set for each arm's build and restored). The parity
     accepts 5, 6 or 7; any other value, or none, is a mismatch, and the week is invalid. The other parity items are
     unchanged.
  2. A new exploratory arm, **MIXT_QA0_MS7**: his live book at the pre-Week-5 limit, 7. Against MIXT_QA0 it tracks the
     switch to 5 on the real field each week. It is descriptive, never decision-bearing, and identical to MIXT_QA0 in a
     week whose live limit is 7.
  3. Every built book (book rows and spares) is checked against its limit; a breach stops the build.
  4. The scorer scores the new arm and carries the week's live limit into its record; the reader prints both on its
     descriptive line.
- **What does not change:** the rule (§5: the decision pair MIXT_RS0 − MIXT_QA0, the weeks, validity, the guards, the
  verdicts), the decision arm's definition (study 37's frozen tiers), the objective (FP's mean, no ownership term), the
  inputs and provenance (§3), the scoring (§4), and the integrity gate (§7: Wednesday's live-mode build on the A3
  snapshot, which now runs at 5).
- **Disclosed:** the early look on Weeks 1–4 (after the original freeze; in-sample, never decision-bearing) was built at
  7. The limit's own evidence is study 40 (the 36-slate harness: NO DIFFERENCE, leaning positive, +0.028 [−0.012,
  +0.067] on P(≥ 1 big seat), both guards held; read after this amendment's code was committed, and it cannot move this
  study's rule) and the outside screen (Weeks 2–4).
- **The smoke (dry run, Week 4's frozen copies: the same frame, FP projections and ownership, and the rehearsal union
  arguments as the original smoke):**
  - **Regression at 7** (the arguments unchanged): every one of the seven original arms is byte-identical to the
    pre-amendment build (`smoke-w4g`, rows and ranks); MIXT_QA0_MS7 equals MIXT_QA0; parity mismatches none.
  - **At 5** (`--mean-max-shared 5`): the build exited 0; parity mismatches none; every arm was built at 5 and
    MIXT_QA0_MS7 at 7, each book's largest pairwise overlap equal to its limit; no fallback rows; no short books (row
    counts as at 7: the tiered arms' short spare tails are the tiers', not the limit's). His book at 5 against 7:
    10 QBs against 8, 31 distinct non-QB players against 27, 0.14 fewer FP points per dealt lineup (144.34 against
    144.48). Construction only: no outcome was read.
- **Code (amended; supersedes the shas in §7 for the files listed):** nfl2 `production/s38-paper-corun-20261006` @
  `acda6ab`:
  - `experiments/s38_paper_corun.py`, sha256 `cc99885aa2d18394beee0952afe07f3747c25f2121eafe6484f66f2d5b2c3c91`;
  - `scripts/s38_build.py`, `8841d841b8c1757d0f1932323caf6e3d5fc4791f8227b36eac7fe6c6edf35ae3`;
  - `scripts/s38_score.py`, `7cf99ffcade5fb0886b08c114bf78ed3b3080d8964ff07d164565fd3805771d2`;
  - **`scripts/s38_report.py` (the reader), sha256 `b4b7d7b76f32e07a5eb2492549746913655c1cc85b3935f3952a7e7dc09e25d3`**;
  - `tests/test_s38_paper_corun.py`, `1d9778485fb078285271402a3596c51233daf292cf85573017f4115e9e038bb3` (13 tests);
  - Unchanged: `scripts/s38_plan.py` `9af5f805…`; study 37's `experiments/s37_regulars_structure.py` `29a2c2c7…`; the
    production pin (§7).
- **Order:** this amendment → the laptop's ack (it re-runs the tests and the smoke) → Wednesday's integrity gate → the
  snapshot before Week 5's lock.
- **Amendment 1b (same day, before Week 5's lock; the laptop's finding at its ack of amendment 1).** The laptop
  reproduced the smoke (all eight arms' rows and ranks identical at both limits) but found `books.json` not
  byte-identical across builds: it carried the build's runtime ("secs"). The record now carries no runtime (printed
  only) and a CONTENT identity, `books_identity` (the plan, the inputs' shas -- never their names or paths -- the
  overlap limits, every arm's rows and ranks), per the frozen-chain rule (compare by content, never representation).
  Two builds of Week 4's copies at 5 gave byte-identical `books.json` (`7ce3d5a4`), identity `3c43ceb8…`, rows and ranks
  equal to amendment 1's smoke. Code: lab `d36d07d`; `scripts/s38_build.py` `64fe91c6c9e361788a17644549de28a3e7afbf224a7db177cc8b3bc00618bfcf`;
  `tests/test_s38_paper_corun.py` `a177af0bffc253b29e284ace41ced8d414376d3b283d1074230680334c13bbec` (14 tests). Every other sha of amendment 1 stands (the
  reader `b4b7d7b7…` unchanged).

- **Amendment 2 (same day, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The union now takes a fill order (`--mix-fill group | value | rr`, production `99fdd285`; study 42) and the
    overlap limit 4 is a candidate (study 41's PASS, Addendum 145). Amendment 1's parity did not look at the fill, so a
    live `value` or `rr` would have passed parity while the paper arms were still built with the group fill: a silent
    break of "his live book". And a live 4 would have been refused.
  - **What changes:** every paper arm is built with THE LIVE UNION'S `--mix-fill` (absent = group, production's default)
    through study 42's frozen `experiments/mix_fill.py` (copied byte-identical, `dcf6a299…`; its "group" IS study 28's
    `mix_book`); an unknown fill is a parity mismatch (an invalid week). The limits accepted are 4 / 5 / 6 / 7. A new
    exploratory arm, **MIXT_QA0_GROUP**: his live book with the group fill (identical to MIXT_QA0 while the live fill is
    group), tracking a fill switch on the real field. The build's content identity carries the fill. Under the value
    fill a peek that was not committed can record a tier fallback, so fallbacks are now counted by row.
  - **What does not change:** the rule (§5), the decision arm, the objective, the provenance, the scoring.
  - **The smoke (dry run, Week 4's frozen copies):**
    - **Regression at 5 with the group fill** (the rehearsal arguments at 5): every one of the eight amendment-1 arms is
      byte-identical to amendment 1b's build (rows and ranks); MIXT_QA0_GROUP equals MIXT_QA0; parity mismatches none.
    - **At 4 with the round-robin** (the operator's Week-5 settings, 10-06: "Use 4", "Use round-robin"): exit 0; parity
      none; every arm builds its 26-row book (the tiered arms' spare tails as at 5: RS0 28 rows, NQC0 28, RBC0 37), each
      book's largest overlap equal to its limit (4; MS7 at 7), no fallback rows; MIXT_QA0_GROUP built with the group
      fill. His book at 4 + rr: 9 QBs, 33 distinct non-QB players, 144.61 FP points per dealt lineup (MS7: 144.94; group
      fill at 4: 144.04).
    - **At 4 with the value fill:** exit 0, parity none, every arm's book full, no fallback rows.
    - Construction only; no outcome was read. `~/private/paper-corun/smoke-w4-amend2/`: books.json `ms4-rr` `47b701ee`,
      `ms4-value` `d1348d29`, `ms5-group` `79b69c17` (corrected 10-06: the laptop's ack found the first message's labels
      rotated; reproduced byte-identically by the laptop).
  - **Code:** lab `d15fb97`:
    - `experiments/s38_paper_corun.py`, sha256 `aa152647aab7bf5c8e89e5e35aa606341e422cda9d2648fb3fd09b9387926823`;
    - `scripts/s38_build.py`, `848d5a806e6efdbdb07281bd66e9e316e9b3d7d8525f2c5dee95c014bc51e437`;
    - `scripts/s38_score.py`, `38445723df3391d0d1a234863592a23ada6426df6e9c74d399be526ec3b93dfd`;
    - **`scripts/s38_report.py` (the reader), sha256 `33d350b53a917109cb33b00c4bb4b29d38eb3304c6292784fdb718dbc2dfde28`**;
    - `tests/test_s38_paper_corun.py`, `57dcb8815b1cd89f2a4fdf4529a943a310089d46dd9e77ad6a4c74d436d23119` (15 tests);
    - `experiments/mix_fill.py` (study 42's, byte-identical), `dcf6a29997d97369f467377ceb5a69a0ba3bc0edc51fe0c8ec495610a8436fd7`.
    - Every other amendment-1 / 1b sha stands; `scripts/s38_plan.py` `9af5f805…` unchanged.

- **Amendment 3 (same day, before Week 5's lock).** The union now takes `--mix-cover-games N` (study 43's coverage rows,
  production `909c306b`, default 0). Study 43 read NO DIFFERENCE, leaning worse (Addendum 147), and the switch is not
  armed. The paper arms build no coverage rows, so a live nonzero cover is a parity mismatch (an invalid week), never
  silently mirrored without it; 0 or absent passes. Smoke: Week 4's copies at 4 + rr give `books.json` byte-identical to
  amendment 2's (`ms4-rr` `47b701ee`); with `--mix-cover-games 4` the build records the mismatch. Code: lab `7a50650`;
  `experiments/s38_paper_corun.py` `f7b73a9c1f902b434f1ae43faf662ca52203bce069a0d6a526a5cc27820027a2`;
  `tests/test_s38_paper_corun.py` `dbcd08c94438679c22af7136c74eb4bf6390893adaa8b0353b9385080f5887cd` (16 tests). Every other
  amendment-2 sha stands (the reader `33d350b5…` unchanged).

- **Amendment 4 (same day, before Week 5's lock; amendment 3's defect class swept over every union argument).**
  - **Why.** The union now takes `--mix-rs-rows N` (study 46's half-and-half book; production `8a9a5a34`, merged at
    integration `f70ce138`, off). Amendment 3's parity named the cover only. A sweep of all 46 union arguments found
    three more that change the book and were not compared:
    - `--mix-rs-rows`;
    - `--mix-portfolio` (`ws` would be a different book);
    - `--tail-sleeve`.
  - **What changes.** A live nonzero `--mix-rs-rows`, a `--mix-portfolio` other than `mix`, or a nonzero
    `--tail-sleeve` is a parity mismatch (an invalid week).
  - **Why the other construction arguments need nothing:**
    - they are in the parity table;
    - or the union itself refuses them with `--main mix` (`--main-game-cap`, `--pmo`, a QB-cap K other than
      `--entries`);
    - or they are part of each paper arm's own definition (the tilt, the projection and ownership inputs).
  - The live Week-5 arguments pass: `sunday_build_host` always passes `--tail-sleeve 0` and `--mix-portfolio mix`.
  - Code: lab `eb84e85`; `experiments/s38_paper_corun.py` `df9829920c1ac533eac0951540e23f8aa779109b691ed7b2094d340192905441`;
    `tests/test_s38_paper_corun.py` `a0bbe301a19e0473cc0728db57ecf9ecd48b486d0c94b02587f93711df477890` (17 tests).

- **Amendment 5 (same day, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The operator's yes on study 46's half-and-half book for Week 5 (10-06, through the laptop): "Yes, pending
    2022 check". The 2022 check is study 46c, with its go / no-go frozen before its read. With a live regulars' block,
    "his live book" is the half book, so the decision reference must follow it.
  - **What changes.**
    - MIXT_QA0 follows the live union's `--mix-rs-rows N` (0 / 9 / 13 / 17; N > 0 needs the round-robin fill, as
      production). It is built through study 46's frozen `half_book`:
      - `experiments/s46_half_half.py`, copied byte-identical (`30647fef…`), with its `l02b_field_sampler.py`
        (`fadf9cfe…`);
      - every module they import is byte-identical to study 46's branch.
    - A new exploratory arm, **MIXT_QA0_FULL**: his live construction without the regulars' block. It tracks the switch
      on the real field (identical to MIXT_QA0 while N is 0).
    - Every other arm is unchanged. The regulars' arms already are the regulars' structure; QA / QAL / MS7 / GROUP stay
      full books.
    - Amendment 4's refusal of a nonzero N becomes: an N outside 0 / 9 / 13 / 17, or N > 0 with another fill, is a
      parity mismatch.
    - The build's content identity, the scorer (QA0_FULL scored; the build's `mix_rs_rows` recorded) and the reader (a
      descriptive "QA0 without the regulars' block − QA0" line) carry it.
  - **What does not change:** the rule (§5), the decision pair "the regulars' structure vs his live book" (MIXT_RS0 vs
    MIXT_QA0), the objective, the provenance, the scoring.
  - **If study 46c contradicts,** `MIX_RS` stays 0: MIXT_QA0 is the full book and MIXT_QA0_FULL is identical to it.
  - **The smoke** (dry run, Week 4's frozen copies, at 4 + rr with `--mix-portfolio mix --tail-sleeve 0`):
    - **(i)** The ms4-rr arguments plus `--mix-portfolio mix --tail-sleeve 0`, as `sunday_build_host` passes them:
      - exit 0, parity none;
      - all nine amendment-2 arms are identical, rows and ranks, to amendment 2's `ms4-rr` build;
      - MIXT_QA0_FULL equals MIXT_QA0;
      - `books.json` `402f365e`, identity `90c18e3c`.
    - **(ii)** The same plus `--mix-rs-rows 13`:
      - exit 0, parity none;
      - MIXT_QA0 is the half book: 13 regulars' rows at the odd positions (blocks L R L R …), 40 rows, the largest
        overlap 4;
      - MIXT_QA0_FULL equals (i)'s MIXT_QA0;
      - every other arm is identical to (i);
      - `books.json` `4dccc845`, identity `c7524101`.
    - Construction only; no outcome was read. `~/private/paper-corun/smoke-w4-amend45/`, script `run.sh`.
  - **Code:** lab `897f880`:
    - `experiments/s38_paper_corun.py`, sha256 `2ac7e02f3bbb79c28f586d279cc9e96ad9260a402d1925746b829a03705e9d15`;
    - `scripts/s38_build.py`, `2a4b8fdd00892315616eac255e59561f83a391002daf7991ffd101552d847411`;
    - `scripts/s38_score.py`, `b222949c0b4b90c897c18832dec685c7411b3a94b7dc67c1767fe88d433f2f9e`;
    - **`scripts/s38_report.py` (the reader), sha256 `17fda3ac62c77ae172af49b5dccf08726fbf88a83f920ed8c73f4bddbf44c4e3`**;
    - `tests/test_s38_paper_corun.py`, `19de3592d6983daf0d45a9f5c5bd00a409011ec1b21a4f78cfa975d634a174a9` (18 tests);
    - `experiments/s46_half_half.py` (study 46's, byte-identical), `30647fef4175770e8f809cb704f282788f8b4d079319ba282768ad907433ec7a`;
    - `experiments/l02b_field_sampler.py` (item 40's, byte-identical), `fadf9cfe3269ed746e8bd82d109b2cd35797ff934c93861cac56c5893f1241b5`.
    - Every other amendment-3 sha stands (`mix_fill.py` `dcf6a299…`, `s38_plan.py` `9af5f805…`).

- **Amendment 6 (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The operator's Week-5 decision (10-07, through the laptop): the prior-top term goes into the live book,
    capped, on part of it ("Live, capped, part of book").
    - The form: 8 of the 26 rows are built after the live block, on the projection + min(0.20 × pred_own, 2.0).
    - pred_own: 5 × z within position of each player's mean share of the prior weeks' real Millionaire top-1% lineups,
      clipped at 0. The file is `reports/2026-10-07-prior-top-term/priortop-w5.csv`, sha256 `694a6622…`.
    - Production: `union_reselect --term-block-rows 8 --term-block-source <file>` (`production/term-block-20261007` @
      `26fb8d40`).
    - With the block live, "his live book" includes it, so the decision reference must follow it.
  - **What changes.**
    - **MIXT_QA0 follows the live union's `--term-block-rows N`.** N is 0 (off), or 1–25 with `--term-block-source`, a
      tilt in (0, 0.5], a cap in (0, 5] and its coverage gate. The block needs the round-robin fill, no regulars' block
      and no whole-book ownership term, as production.
      - **The term:** production's `own_bonus` (imported from the pin, as for MIXT_QA) on the snapshot's copy of the
        union's term file, then min(term, cap). The copy must be content-identical to the file the union read.
      - **The book:** `experiments/term_book.py`, copied byte-identical from study 49's branch (`62c2306e…`):
        - one state;
        - the live block (26 − N rows) first, on FP's mean;
        - then the N-row block on FP's mean + the term;
        - at study 46's block_positions(26, N);
        - each block interleaved on its own positions' head weights;
        - the spares on FP's mean.
      - If `own_bonus` refuses the file, MIXT_QA0 is built without the block, as the union falls back. This is recorded;
        the host stops the entry until he decides.
    - **A new exploratory arm, MIXT_QA0_NOTERM:** his live construction without the block. It is identical to MIXT_QA0
      while N is 0 and no regulars' block is live (production refuses the two blocks together). Each week it measures
      the block itself on the real field, the only prospective evidence the term will get.
    - **Every other arm is unchanged.**
    - **Parity:** a term-block argument outside its definition, or the block with another fill, a regulars' block or a
      whole-book term, is a parity mismatch (an invalid week).
    - **The snapshot:** the build resolves the term file by the union's own `--term-block-source`. Its copy must be in
      the MANIFEST and identical to the union's file. The laptop's snapshot tool copies it.
    - **The records:** the build's content identity, the scorer (MIXT_QA0_NOTERM scored; the build's `term_block`
      recorded) and the reader (a descriptive "QA0 without the term block − QA0" line) carry it.
  - **What does not change:** the rule (§5), the decision pair "the regulars' structure vs his live book" (MIXT_RS0 vs
    MIXT_QA0), the objective, the provenance, the scoring.
  - **The smoke** (dry run, Week 4's frozen copies, at 4 + rr with `--mix-portfolio mix --tail-sleeve 0`; on the
    committed code):
    - **(i) No block:**
      - exit 0, parity none;
      - all ten amendment-5 arms are identical, rows and ranks, to amendment 5's (i);
      - MIXT_QA0_NOTERM equals MIXT_QA0;
      - `books.json` `2cd95e9b`.
    - **(ii) `--term-block-rows 8 --term-block-source priortop-w4.csv`** (`1f38c8cb`, the replay's Week-4 file):
      - exit 0, parity none;
      - the block applied: 64 players carry a term, 13 at the cap, coverage 0.954;
      - MIXT_QA0's block sits at ranks 2, 5, 9, 12, 15, 18, 22 and 25, and 17 of its 26 rows are shared with (i)'s
        MIXT_QA0;
      - MIXT_QA0_NOTERM equals (i)'s MIXT_QA0, and every other arm is identical to (i);
      - `books.json` `c276bf08` (identical from the union's own frame).
    - **(iii) Production parity:** (ii)'s MIXT_QA0 equals the laptop's Week-4 term8 union book (production `26fb8d40`,
      the exact-form replay) position by position, 26 of 26. This holds from the entered frame and from the union's own
      frame alike.
    - Construction only; no outcome was read. `~/private/paper-corun/smoke-w4-amend6/`, script `run.sh`.
  - **The integrity gate (§7) for Week 5** must pass on a snapshot whose union carries the block. That is Friday's
    rehearsal with the block armed, since the A3 snapshot predates his decision.
  - **Code:** lab `bffa16f`:
    - `experiments/s38_paper_corun.py`, sha256 `358bb71638b2a2886d29331cbb43392715caa7ba6f52480cbdd2e3cec714a440`;
    - `experiments/term_book.py` (study 49's, byte-identical), `62c2306eff1135713d599b788bcbd29be9db308c2eb8537183f3d291b996b887`;
    - `scripts/s38_build.py`, `b194f8e0d3663fe9375dca000615add208cc6f599257d1f3f735db5e6fd82dff`;
    - `scripts/s38_score.py`, `d807a65d708aae9e591b70ad40c3feff30efea3c7398556cffab0fc4152147d7`;
    - **`scripts/s38_report.py` (the reader), sha256 `3f27d123e67bc24c14f7a4e6354ba96d7f4b95cce9ab5a09d61d208b7506fefc`**;
    - `tests/test_s38_paper_corun.py`, `cade05db7caef6baff4ef984266d5a00abe930c0026dfa1b59d5a5f12f00f418` (19 tests).
    - Every other amendment-5 sha stands (`s46_half_half.py` `30647fef…`, `mix_fill.py` `dcf6a299…`, `s38_plan.py`
      `9af5f805…`).
  - **Order:**
    1. this amendment;
    2. the laptop's ack (it re-runs the tests and the smoke);
    3. the snapshot tool copies the term file;
    4. the integrity gate on Friday's rehearsal snapshot;
    5. the snapshot before Week 5's lock.

- **Amendment 6b (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** Study 49 (Addendum 156) read NO DIFFERENCE, leaning negative, for the capped block. The laptop is taking him
    three options for Friday's arming: live 8 capped rows, paper only, or off. "Paper only" needs a study-38 arm that
    carries the block while the live book does not.
  - **What changes.**
    - **A new exploratory arm, MIXT_QA0_TERM8:** his live construction plus the prior-top block from a PAPER term file in
      the snapshot (`paper-term-*.csv`, the week's file made by `make_priortop_files.py`'s rule). The block's parameters
      are frozen here: 8 rows, tilt 0.20, cap 2.0 points, coverage gate 0.5. They do not depend on the live union's term
      arguments. It is built through the same `term_book` and `own_bonus` as amendment 6.
    - **Each of his three options:**
      - **live 8 rows from the same file:** MIXT_QA0_TERM8 equals MIXT_QA0, and MIXT_QA0_NOTERM measures the block;
      - **paper only:** MIXT_QA0 is the live book without the block, and MIXT_QA0_TERM8 is the block's real-field test,
        with no money at risk;
      - **off:** no paper file is in the snapshot, so MIXT_QA0_TERM8 is missing that week (recorded).
    - **When the arm cannot be built** (a live fill other than rr, or a live regulars' block), it is missing that week,
      recorded.
    - **The snapshot:** the build reads the one `paper-term-*.csv` (or none) and records its sha in the MANIFEST check.
      The laptop's snapshot tool copies the week's file when `S38_PAPER_TERM_FILE` is set.
    - **The records:** the content identity, the scorer and the reader (a descriptive "QA0 + the paper 8-row block − QA0"
      line) carry it.
  - **What does not change:** the rule (§5), the decision pair (MIXT_RS0 vs MIXT_QA0), every other arm, the objective,
    the provenance, the scoring. Amendment 6's behavior is unchanged: its term points pass to `term_book` as `arm_pts`,
    which equals `term_pts` for every arm but the paper one.
  - **The smoke** (dry run, Week 4's frozen copies, at 4 + rr; on the committed code `9389216`, clean; the paper file is
    the replay's `priortop-w4.csv`, `1f38c8cb`):
    - **(i) The paper file, no live block:**
      - exit 0, parity none;
      - MIXT_QA0_TERM8 equals amendment 6's (ii) MIXT_QA0 (the live-block book), rows and ranks, with its block at ranks
        2, 5, 9, 12, 15, 18, 22 and 25;
      - every amendment-6 arm is identical to amendment 6's (i);
      - `books.json` `cb0e9401`.
    - **(ii) The live block and the paper file:**
      - parity none;
      - MIXT_QA0_TERM8 equals MIXT_QA0;
      - every amendment-6 arm is identical to amendment 6's (ii);
      - `books.json` `9f5ecb87`.
    - **(iii) No paper file:**
      - parity none;
      - MIXT_QA0_TERM8 is missing ("no paper term file");
      - every amendment-6 arm is identical to amendment 6's (i);
      - `books.json` `e5f886b2`.
    - Construction only; no outcome was read. `~/private/paper-corun/smoke-w4-amend6b/`, script `run.sh`.
  - **Code:** lab `9389216`:
    - `experiments/s38_paper_corun.py`, sha256 `97cc15b324541f094667d034cc659082c3c9cf899d76e6d6c3367da61c8e37d5`;
    - `scripts/s38_build.py`, `64756adeea259d4afe98d89160310e099ea98ba8f1ba870116d82dace01497a2`;
    - `scripts/s38_score.py`, `3d6e7bc34bc53943fd52c50ea1d51f9a641ad17342a164f6071808ba60f7e550`;
    - **`scripts/s38_report.py` (the reader), sha256 `5c979d1c75ecd404fce1ca1d3f012cebb93353c1517ed00e1e32b438c3455214`**;
    - `tests/test_s38_paper_corun.py`, `9eccc91073d64428e8c1a1505eebda3d1e1fe07fc11b252b14212dafc9064f12` (20 tests);
    - every other amendment-6 sha stands (`term_book.py` `62c2306e…`).
  - **Order:** this amendment → the laptop's ack (tests and smoke) → the snapshot tool's `S38_PAPER_TERM_FILE` → his
    Friday choice decides whether the file is set.
  - **His decision (10-07, after study 49's read, through the laptop): "Paper only".**
    - The live union runs no term block (`TERM_ROWS = 0`).
    - The snapshot carries the paper file: `S38_PAPER_TERM_FILE`, Week 5's `priortop-w5.csv` (`694a6622…`). From Week
      6, a new file each week by `make_priortop_files.py`'s rule on the prior weeks' real fields after settlement, each
      sha recorded in HANDOFF.
    - So from Week 5 MIXT_QA0 is his live book without the block, MIXT_QA0_NOTERM equals it, and MIXT_QA0_TERM8 is the
      block's paper test (its weekly "QA0 + the paper 8-row block − QA0" line).
    - **The integrity gate (§7) for Week 5** therefore runs on Friday's rehearsal snapshot with the live block OFF and
      the paper file SET (superseding amendment 6's "with the block armed"). It must show the paper file in the
      MANIFEST, MIXT_QA0_TERM8 built with its block at ranks 2, 5, 9, 12, 15, 18, 22 and 25, MIXT_QA0_NOTERM equal to
      MIXT_QA0, and every live-mode check passing.

## 1. Why
- **The operator (10-06), on the proposal:** "yes, please try it, I want to exhaust all reasonable options."
- **Study 37** (Addendum 142): the regulars' structure (about 11 QB stacks and a steep player curve, their own tier
  profile at 26 lineups) did not raise P(≥ 1 big) under our projections, and breached both guards. QB breadth alone was
  neutral; the player curve carried the cost, because each spread-in player is one our model rates lower.
- **But the regulars beat the field by +6.1 points per lineup WITH their spread**, while ours runs −3.8 (the weekly
  picks-vs-field line). Their alternatives are better than our model says (study 34: their edge is pre-lock knowledge).
  Study 37's harness prices every alternative with our projections and could not credit that.
- **Since Week 5 the live book uses Fantasy Points' projections**, the closest thing we have to that knowledge. The
  fair test of the spread is therefore under FP's projections, on the 2026 slates we actually play (his ruling: test on
  2026 full-data weeks).

## 2. Arms (built each week; never entered)
- **His decision (10-06), which sets the reference:** "yes, remove the tilt as you suggested and proceed as planned". From
  Week 5 the live book runs NO ownership term. The evidence: beyond a market-quality projection, ownership carried no
  information in Weeks 1–4 (props-implied base −0.03 points per ownership point [−0.24, +0.17]; served +0.01; our old
  model +0.44, which is why the term helped before); beyond FP in Week 4 it was negative; production's own Week-4
  replay under FP gave P(≥ 1 big) 0.0094 with the 0.20 term and 0.0336 without. A verdict does not transfer across a
  changed objective, so the decision pair is on FP's mean alone, like his live book.
- **MIXT_QA0** (reference): his live yes-book (the winners' mix, the per-QB cap of 5 rows, production's player / DST
  caps 13 / 6, FP's mean, no ownership term), rebuilt in the lab harness like-for-like.
- **MIXT_RS0** (DECISION): study 37's regulars' structure on the same objective, its frozen tiers unchanged (QB: a 6-row
  cap, at most 1 / 1 / 2 / 4 / 7 QBs reach 6 / 5 / 4 / 3 / 2 rows; non-QB: at most 1 / 1 / 2 / 3 / 4 / 5 / 7 / 10 / 13 /
  18 / 25 / 36 players reach 13 … 2 rows; the loud fallback).
- **Exploratory, never decision-bearing:**
  - MIXT_QBB0 / MIXT_NQC0: each tier set alone.
  - MIXT_QA: the yes-book WITH the dropped +0.20 term (tracks his decision on the real field).
  - MIXT_QAL: the yes-book leaning AGAINST ownership, −0.10 per ownership point (his question 10-06: can ownership find
    players who project well but will be under-owned, for an edge?).
  - MIXT_RBC0: an RB-led floating core plus QB-stack breadth (the laptop's Neo4j finding 10-06: the regulars' heavy core
    is about 5 players, RB-led, carried across many QB stacks; their pass-catchers spread through the stacks). Study 37's
    QB tiers plus a WR / TE-only curve at the regulars' WR / TE medians at 26 rows, rounded half up (no WR / TE reaches 12
    rows; at most 1 / 1 / 2 / 3 / 4 / 6 / 8 / 12 / 17 / 25 reach 11 … 2 rows); RBs at production's 13-row cap; FP's mean.
  - The ownership weights are multiples of the frozen 0.20 (0, +1, −0.5); production's `own_bonus` does the matching and
    the refusals. Without an FP ownership file, only MIXT_QA and MIXT_QAL go missing (recorded), never the week.
- **His ENTERED book**: a context column, scored the same way, never an arm. The lab's MIXT_QA0 and the production union
  will differ (the union's own solver path, pins and spares); that difference is itself reported.

## 3. Inputs and provenance (the laptop's pre-lock snapshot; the build runs after lock)
- **The snapshot** (the laptop, Sunday right after the T-70 union and before 12:00 CT): copies of the union run's
  `frame.parquet`, the union's arguments, and the model inputs AS THE UNION'S OWN ARGUMENTS NAME THEM: FP's
  projections (`--proj-source`, with its `.json` sidecar; a union without one fell back from FP, and that week is not
  an FP week), the ownership file (`--main-own-source`, whatever its name), and a DK status file only when the union read
  one (`--dk-status`; production passes none while O-16 stands, so the union calls `unavailable_ids(fr, None)` and so
  does the build). Also the installed `contests.json`, the week's contest details, `plan-overrides.json` (his
  per-contest decisions that week; `{}` if none), and `MANIFEST.txt` (each file's sha256, bytes, name, source path and
  mtime; the header carries the union's built_utc and lock_utc and the snapshot time), and the union's receipt
  (`union-receipt.json`). The laptop's tool (`scripts/s38_snapshot.sh`) is create-once, never writes under a week's
  money-path directory, makes every copy fatal on failure, and marks a partial copy `SNAPSHOT-FAILED.txt` (the build
  refuses such a folder).
- **The MANIFEST is the build's only input list.** Every file the build reads must have its sha256 in it, or the build
  REFUSES. The copies of FP's projections, FP's ownership and the DK status must be byte-identical to the files the
  union's arguments name, where those originals are still on disk. **Pre-lock is proved by content:** the build refuses
  unless the MANIFEST's snapshot time is before the union receipt's `lock_utc` (and the tool refuses to snapshot at or
  after it).
- **The build** uses production's own functions, imported from a pinned production checkout: `apply_proj_source`
  (FP's projections replace `mean_projection`; it refuses a file made for another frame), `unavailable_ids` plus the
  skill `--min-proj` filter (the exclusions), and `own_bonus` at the frozen 0.20, scaled per arm. Then study 28's
  `mix_book` with study 37's builders, at the plan's K 26 head layout.
- **The union's arguments must match the lab builder's mechanics** (mix, K 26, overlap 7 [amendment 1: the live 5 / 6 / 7], per-game 4, salary floor
  49,000, min-proj 1.0, caps 0.5 / 0.25, the QB cap of 5 rows, head layout), or the build refuses. **The ownership tilt is
  each paper arm's own**, not part of that parity. With the live tilt at 0, Sunday's build captures no FP ownership
  (the capture and export run only with a non-zero tilt), so the laptop's snapshot tool runs that same capture and
  export itself: after the T-70 union, under the same FP profile lock, with the export's `--now` set to the snapshot
  time (before lock). If the vendor collect fails, the export falls back exactly as production's does (the newest
  capture within its 30-hour limit; the age is recorded in the MANIFEST). If the export refuses (stale or low coverage),
  there is no ownership file, and only MIXT_QA and MIXT_QAL go missing that week.
- **Disclosed: the objective differs from studies 28–37.** It is FP's `mean_projection` (plus the arm's ownership
  weight), as the money path ranks, not the simulated `player_mean` of the harness.
- **The plan** in the harness's form is derived inside the build from the snapshot's `contests.json`, details and
  overrides by the tracked converter (`scripts/s38_plan.py`): single-prize contests count every paid seat as big except
  a $20 ticket; multi-tier contests count the places paying $500 or more; his decisions ride in the overrides (Week 5:
  the $125 WFFC qualifier is not a big win). From the installed Rev3 (`8625de0e`) it reproduces the Week-5 harness plan
  `3dd19d6c` byte for byte.
- **No outcome is read by the build:** the frame's `actual` column is dropped on read.

## 4. Scoring (Monday, after settlement)
- Each dealt entry's real DraftKings points (the week's points table, canonical names, hundredths; a missing name
  scores 0 and is counted), and its share of the REAL Millionaire field it beats: every real entry of ours removed,
  ties counted as losses, as the harness's `contest_p`.
- Then the harness's own `big_seat_stats` per plan contest: **P(≥ 1 big seat), expected big seats, P(≥ 2)**, and the
  mean entry pct. That is studies 31–37's endpoint, with the real field in place of a sampled one.
- **Descriptive only:** realized results per contest (`moneygate_score.place` against that contest's real entrants,
  DraftKings' tie split: payouts, cashes, big seats realized), his entered book, the picks-vs-field and monkey lines.

## 5. The rule (the reader `scripts/s38_report.py`, frozen with this document)
- **The weeks:** the first FOUR VALID weeks from Week 5; Week 9 may replace an invalid one, and no later week.
- **A valid week:** its books were built LIVE (the manifest checked, union-args parity, the copies identical to the
  union's files), and every dealt entry was scored with under 1% of player names missing. A week that fails any of
  these is reported as invalid with its reason, never counted.
- **PRIMARY:** per week, d = P(≥ 1 big seat) of MIXT_RS0 − MIXT_QA0.
- **Guards** (pooled over the four weeks): guard 1, the mean of the weekly mean-entry-pct differences > −0.015;
  guard 2, expected big seats summed, MIXT_RS0 / MIXT_QA0 ≥ 0.80 (his tolerance; it holds when both sums are 0).
- **Verdicts:** PASS (d > 0 in ALL FOUR weeks and both guards hold) / FAIL (guard) (d > 0 in all four, a guard fails) /
  WORSE (d < 0 in all four) / NO PASS (anything else) / NOT ENOUGH VALID WEEKS. The guards gate a PASS only.
- **Said plainly: four weeks are four draws.** With one slate a week, four weeks are four independent outcomes. Under a
  coin-flip null, MIXT_RS0 ahead in all four happens 1 time in 16, so a PASS is a strong but not certain signal, and a
  real but modest gain will usually read NO PASS. His goal itself (one big win a week) cannot be measured in four
  weeks; the smooth P(≥ 1 big) on the real field is the closest measurable stand-in. Every weekly number is
  descriptive.

## 6. What a verdict can do
- **PASS:** licenses building production tier code (the QB and non-QB tiers with the loud fallback in
  `union_reselect`) for the following week. It is reviewed, parity-tested against the harness and rehearsed, and
  armed only on his yes.
- **FAIL, NO PASS, WORSE or NOT ENOUGH VALID WEEKS:** the yes-book stays, and the structure remains a paper option.

## 7. Smoke, census and integrity
- **Parity with the money path, confirmed:** the laptop ran production's own fixed-book replay of Week 4 (union_reselect,
  FP source, the QB cap, Rev3 head; the ownership term at 0.20 against none) and reproduced this harness's numbers to
  four decimals: P(≥ 1 big) 0.0094 against 0.0336; expected big seats 0.0094 against 0.0339; mean entry pct .4960
  against .5014. So the paper books are the books production would build. (This one week is a confirmation of the
  machinery and of the 10-06 tilt evidence, not a sample of this study.)
- **The Week-4 smoke** (the laptop's frozen copies; dry run): the build exited 0, all four books built (the parity check
  named Week 4's different union arguments, as it should). The scorer exited 0 with its 2 headers and 4 book lines; no
  outcome line was read. The reader marked the dry-run week INVALID.
- **INTEGRITY GATE (post-freeze):** before Week 5's lock, the LIVE-mode build must pass on the laptop's Week-5 rehearsal
  snapshot (`~/private/paper-corun/rehearsal-w05/`, from A3): the manifest, provenance, union-args parity and pre-lock
  checks, all arms built. If it fails, Week 5 is INVALID (the reader then takes Week 9). The same live-mode checks gate
  every week.
- **Code (frozen; amendment 1 supersedes the shas of the files it changed):** nfl2 `production/s38-paper-corun-20261006` @ `4429fd8`:
  - `experiments/s38_paper_corun.py`, sha256 `e2d593a5d4c9f161763b74c2a4b2247830717196b23372215739083855fcbcdf`;
  - `scripts/s38_build.py`, `fe51ac2e6f528b7ee9d6de27406779e3cbd4dfc4adc6eb85e6b9539587f74174`;
  - `scripts/s38_score.py`, `ca4e74d3468c0cd2f2459e80a59b97f810e0f6a04b94f41b96f5665111d331c3`;
  - **`scripts/s38_report.py` (the reader), sha256 `7865303af4b48b1c1365feb4a9098af817d9b176f5d2559bc02c92a34399da44`**;
  - `scripts/s38_plan.py`, `9af5f8053a0369cc2f787aef332ed3d5f96b506a352a518c763b8773ceb5d924`;
  - `tests/test_s38_paper_corun.py`, `d43597cc6ac0baa5b0bcbce5c509e36f44f701b435b734c6105fafd2bbdb8029` (10 tests);
  - study 37's frozen `experiments/s37_regulars_structure.py`, `29a2c2c72b86f1b5eec6072119482cafa462218272c6c90f2e9aa2c95778acbf`.
- **The production pin** (imported, never copied), identical at integration `5a1ac062` and at the pin `1478dcfb`:
  `scripts/union_reselect.py` `ffd59b721ba6236e…`, `scripts/r1c_sunday_reselect.py` `3c3b9480fc0f5516…`,
  `scripts/moneygate_score.py` `48342ae163e20738…`, `src/nfl_dfs/inference/enter_layout.py` `3cb051ac6a2b40a1…`. If
  the head armed for a week changes these files, the pin follows the armed head and the change is disclosed in that week's
  record.
- **An early look on Weeks 1–4 (after this freeze; never decision-bearing):** every arm replayed on the four completed
  weeks (W4 on FP, W1–3 on our projections), on each week's real Millionaire field. The tiers of RS0 and RBC0 were DERIVED
  from Weeks 1–4, so it is in-sample: it can warn, not confirm.
- **Order:**
  1. this freeze;
  2. the laptop's ack;
  3. each Sunday, the snapshot before lock;
  4. the build after lock;
  5. Monday, `fetch_week` (the laptop), then the score (the reviewer);
  6. the laptop's byte-identical re-run;
  7. the weekly record;
  8. after the fourth valid week, the frozen read, the LEDGER row and an Addendum.
