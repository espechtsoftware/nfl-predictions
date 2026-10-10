# Preregistration: study 38, the FP paper co-run (the regulars' structure beside the yes-book, under the projections we play with) (FROZEN 2026-10-06; AMENDED 2026-10-06, 10-07, 10-08 and 10-09, amendments 1, 1b, 2, 3, 4, 5, 6, 6b, 6c, 6d, 6e, 6f, 6i, 6j, 6k, 6l, 6n, 6n's follow-up, 6o, 6p, 6q, 6r, 6s, 6t, 6u, 6v and 6w before Week 5's lock; repair 6g and the big-win rule 6h before its first score)

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

- **Amendment 6c (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** O-40 (Addendum 157): the projection model never carried a defense-vs-position input. Our model's screen
    shows almost no projection gain from it, but Week 4's FP residual correlated +0.12 with in-season DvP (one week).
    The book's means are FP's. The operator chose (10-07): "Yes, paper arm".
  - **What changes.** A new exploratory arm, **MIXT_QA0_DVP**: his live construction, following every live setting as
    MIXT_QA0 does (limit, fill, regulars' block, term block), on FP's means plus a defense-vs-position correction from a
    PAPER file in the snapshot (`paper-dvp-*.csv`).
    - **The file** is written by production's `scripts/paper_dvp_file.py` (integration `e07675ab`, sha256 `592799cc…`;
      the writer and its format are FROZEN). **Repaired before first use** (integration `f4a1d2d6`, sha256 `a4651e61…`, the
      reviewer's decision): a frame row without a dk_player_id is now refused (exit 3). Under pandas 3 the old string cast
      kept a missing id as "nan", so the refusal never fired. The format, the recipe and the output for any valid frame
      are unchanged. It holds a `#` JSON metadata line (slope, n_slope, weeks, prior_weeks
      with their frame and FP shas, the target's frame and FP shas, rows, the script's sha), then dk_player_id,
      gsis_id, pos, opp, z, slope, fp and adj_points. adj_points is FP's ADJUSTED mean, fp + slope × z; a player FP
      projects at 0 stays 0. There is one row per skill player of the frame with an FP value and a z.
    - **The recipe**, verbatim in the writer's docstring:
      - **z:** the opponent's mean DK points allowed to the player's position over the PRIOR 2026 weeks, as a z-score
        within position across the slate's skill players. QB / RB / WR / TE only.
      - **slope:** the OLS slope of FP's residual (actual DK points − FP's T-70 mean) on that z, pooled over every prior
        2026 week with an archived T-70 FP capture, using players with FP ≥ 5.
      - Week 5's slope rests on Week 4 alone (disclosed); it learns as weeks accrue. There is no cap and no shrinkage.
      - The writer refuses (the arm is then missing that week) with fewer than 30 regression rows, a duplicated or
        missing id, a non-finite slope, or a prior week given twice or not before the target. The floor only refuses;
        it never changes a slope.
    - **The arm validates the file:** its metadata line; one slope, equal to the metadata's; adj_points on its rule;
      skill positions; finite values; unique ids. It adds the correction (adj_points − fp) by DK id; a player absent
      from the file gets 0. Players FP projects under the pool's `--min-proj` (1.0) are already out of the pool before
      any correction. It records the file's fp against the build's FP means (`fp_disagreements`) as a diagnostic.
      Without a valid file it is missing that week (recorded).
    - **The records:** the snapshot finds the one `paper-dvp-*.csv` (or none). The content identity, the scorer and the
      reader (a descriptive "QA0 on FP + DvP − QA0" line) carry it. The identical-book share every arm already prints
      is the vacuity check: a slope near 0 changes nothing.
    - **Disclosed:** the reviewer and the laptop crossed twice on the file's format. Lab `0b8c9f9` read a
      slope × z format; `05acfee` adopted production's format; `e08b05f` reverted it; `cbca4dd` re-applied it. The
      code is `05acfee`'s, byte for byte. No outcome was involved at any step.
  - **What does not change:** the rule (§5), the decision pair, every other arm. The older amendments' code paths are
    unchanged: their `arm_rs` / `arm_term` calls now go through `like`, which equals the arm for every arm but the DvP
    one, and their tests pin it.
  - **The smoke** (dry run, Week 4's frozen copies, at 4 + rr, with amendment 6b's paper term file; on the committed
    code `cbca4dd`, clean). The DvP files are written by PRODUCTION's own `build()` (`e07675ab`) on Week 4's frame and
    FP capture, with main()'s metadata keys and a SYNTHETIC points-allowed table: mechanics only, never the recipe's
    data.
    - **(i) Zero slope:** MIXT_QA0_DVP equals MIXT_QA0 (rows and ranks), and every amendment-6b arm is identical to 6b's
      (i). `books.json` `1adbd2e7`.
    - **(ii) Slope 1:** 235 pool players corrected; MIXT_QA0_DVP differs from MIXT_QA0, and every other arm is identical
      to 6b's (i). `books.json` `2e114268`.
    - **(iii) No file:** MIXT_QA0_DVP is missing, and every other arm is identical to 6b's (i). `books.json` `4fa7e4a3`.
    - **(iv) A live 8-row term block with slope 1:** MIXT_QA0_DVP follows the block (ranks 2, 5, …, 25), and every
      other arm is identical to 6b's (ii). `books.json` `fff6fa8a`.
    - Parity none in all four. Construction only; no outcome was read. `~/private/paper-corun/smoke-w4-amend6c/`,
      script `run.sh`.
  - **Code:** lab `cbca4dd`:
    - `experiments/s38_paper_corun.py`, sha256 `a018218ea0a11bb2ff99e5a2615e0026f9c2e65496c25b47f62d2b43ed050936`;
    - `scripts/s38_build.py`, `5d5dd74b24ddd67bf45556e0c63098ce55a449e0cc738f99167af33a9d3aa834`;
    - `scripts/s38_score.py`, `a902b7a90c52a09010091af275642706755ea60056b529dfb370334488f3eccf`;
    - **`scripts/s38_report.py` (the reader), sha256 `0bea39a63ab1097dd85b539cd2f90a1d556759117217c2c7096fa35abf88a591`**;
    - `tests/test_s38_paper_corun.py`, `0f8b70ae9a7eff51b091b1c51a5b58d23f24a63025bc89c077aa87cbf26a39d2` (21 tests);
    - every other sha stands (`term_book.py` `62c2306e…`).
  - **Order:**
    1. this amendment;
    2. the laptop's ack (tests and smoke);
    3. the snapshot tool's `S38_PAPER_DVP_FILE` (`d72b91d4`, done);
    4. Sunday's checklist step writes the week's file after the T-70 union.
    5. Friday's rehearsal snapshot carries both paper files for the integrity gate.

    If Week 5's file cannot be made, the arm starts at Week 6, never with an improvised slope.
- **Amendment 6d (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The operator (10-07) asked to "schedule any necessary experiments this week" on the outside reviewer's "why
    we missed the winners' players". The harness test is study 50 (`reports/2026-10-08-prereg-study50-factor-bonuses.md`).
    These paper arms are the same bonuses on the real field, with no money at risk. With 6c's walk-forward DvP arm, two
    matchup doses are tested side by side (the operator's rule: when the agents disagree, test both).
  - **What changes.** Two new exploratory arms, each his live construction (every live setting as MIXT_QA0 does;
    `FOLLOW_QA0` is now the DvP arm and these two) on FP's means plus a bonus from a PAPER file in the snapshot
    (`paper-factor-*.csv`):
    - **MIXT_QA0_MATCHUPX** adds b_matchup.
    - **MIXT_QA0_COMBINED** adds b_combined = clip(b_matchup + b_vacated + b_market, 0, 3), the full live form, with the
      market term computed against FP's means.
  - **The file** is written by production's `scripts/paper_factor_file.py` (integration `fb837d58`, sha256 `de4f4cb3…`).
    Its format was named by the reviewer before the build:
    - a `#` JSON metadata line (weights, clips, prior season, prior games, input and script shas, rows, unmatched_opp);
    - then dk_player_id, gsis_id, pos, team, opp, b_matchup, b_vacated, b_market, b_combined and fp.
    - The formulas are `make_factor_files.py`'s exactly. The writer reproduces the outside reviewer's own Week-4 bonus
      files (all four bonuses, 270 rows, max difference 0).
  - **The arm validates the file:** its metadata line; every b finite and inside its clip ([0, 2], [0, 3], [0, 2],
    [0, 3]); b_combined on its rule; a player FP projects at 0 with no bonus; skill positions; unique ids. A player
    absent gets 0. Without a valid file both arms are missing that week (recorded).
  - **The records:** the content identity, the scorer and the reader (descriptive "QA0 + matchup bonus − QA0" and "QA0 +
    combined bonus − QA0" lines) carry it.
  - **What does not change:** the rule (§5), the decision pair, every other arm. The older amendments' `like` pins now
    read `FOLLOW_QA0`, unchanged for every other arm.
  - **The smoke** (dry run, Week 4's frozen copies, at 4 + rr, with 6b's paper term file; on the committed code
    `f01611c`, clean). The factor files are written by PRODUCTION's own `build()` (`fb837d58`) with main()'s metadata
    keys and a SYNTHETIC points-allowed table: mechanics only.
    - **(i) Every bonus zero:** MIXT_QA0_MATCHUPX and MIXT_QA0_COMBINED equal MIXT_QA0, and every amendment-6b arm is
      identical to 6b's (i). `books.json` `38ff01ef`.
    - **(ii) The real formulas:** 127 / 162 pool players carry a matchup / combined bonus. Both arms differ from
      MIXT_QA0, and every other arm is identical to 6b's (i). `books.json` `ea81475a`.
    - **(iii) No file:** both arms are missing, and every other arm is identical. `books.json` `25b5f067`.
    - Parity none in all three. Construction only; no outcome was read. `~/private/paper-corun/smoke-w4-amend6d/`,
      script `run.sh`.
  - **Code:** lab `f01611c`:
    - `experiments/s38_paper_corun.py`, sha256 `913652c35113da4a23f66459132da1cdbc745b61de1dcb449a1b089968bb80d5`;
    - `scripts/s38_build.py`, `f756705dfd11621a7ced7310f7bf82234f7ccf24de89c41ac6dc6939c7b660a2`;
    - `scripts/s38_score.py`, `131fc323b4bf823077dc52e0dac48826d27244fa18cec0f368bfec031ca4f6d8`;
    - **`scripts/s38_report.py` (the reader), sha256 `865d691bc21c4beb4b8d322812911844c5e7325dfbbd30ecf63eed3f4a0869ac`**;
    - `tests/test_s38_paper_corun.py`, `b71fa7e0235e27acc72d7f8276547518c262c1c12a6a50886637299419aa0c08` (22 tests).
  - **Order:**
    1. this amendment;
    2. the laptop's ack (tests and smoke);
    3. the snapshot tool's `S38_PAPER_FACTOR_FILE` (`8b3d63ae`, done);
    4. Sunday's checklist writes the week's file after the T-70 union, beside the DvP file;
    5. Friday's rehearsal carries all three paper files.

    If Week 5's file cannot be made, both arms start at Week 6.
- **Amendment 6e (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The operator (10-07): "Please try to tackle the 'matchup bonus' one this week". The matchup bonus may go
    LIVE in the Week-5 book as the 8-row term block. The file is production's `scripts/matchup_block_file.py`
    (`57d80375`, reviewed): every skill player, with pred_own = b_matchup / 0.20, tilt 0.20 and cap 2.0. His decision is
    at Saturday's arming, after study 51 (`reports/2026-10-08-prereg-study51-matchup-block.md`) and the laptop's replay.
    Amendment 6 assumed the live block's file was the prior-top file, so a live block from another source needs a rule.
  - **What changes.**
    - **MIXT_QA0** carries whatever block is armed (TERM_FOLLOW, unchanged). **MIXT_QA0_NOTERM** is his live
      construction with no block (unchanged).
    - **MIXT_QA0_MATCHUPX and MIXT_QA0_COMBINED never carry the live block** (`NO_LIVE_TERM`). They keep every other live
      setting of MIXT_QA0 and add their whole-book bonus. With a live matchup block, their block rows would otherwise
      carry the bonus twice.
    - **References.** MIXT_QA0_TERM8, MIXT_QA0_MATCHUPX and MIXT_QA0_COMBINED are read against MIXT_QA0_NOTERM.
      TERM8's paper block already replaces the live one: its rows come from the paper file and its frozen parameters,
      not from the live N.
    - **MIXT_QA0_DVP** follows the live book, including its block (reference MIXT_QA0): his live book on DvP-corrected
      means. Its overlap with a live matchup block is confined to the block's 8 rows (disclosed).
    - **The reader's descriptive lines:**
      - "the paper 8-row block − NOTERM", "matchup bonus − NOTERM" and "combined bonus − NOTERM";
      - the live block's line ("QA0 without the term block − QA0 with N term rows") names the live file. It is the
        weekly real-field record of the live matchup block.
    - **With no live block, MIXT_QA0_NOTERM equals MIXT_QA0**, so every arm, record and line is 6b's and 6d's.
  - **What does not change:** the rule (§5), the decision pair (RS0 vs QA0, where QA0 stays the book he plays), and
    every other arm.
  - **The smoke** (dry run, Week 4's frozen copies, at 4 + rr, with 6b's paper term file, 6d's factor files and 6c's
    DvP file):
    - **OFF:** 6d's three runs with the 6e code reproduce 6d's `books.json` byte-for-byte (zero `38ff01ef`, real
      `ea81475a`, none `25b5f067`).
    - **ON:** a live matchup block built by PRODUCTION's own writer (`matchup_block_file.py` at integration
      `9d6818a9`, on Week 4's frame with 6d's SYNTHETIC points-allowed table; 292 rows, 158 with a bonus; mechanics
      only).
      - MIXT_QA0 and MIXT_QA0_DVP carry it at ranks 2, 5, 9, 12, 15, 18, 22 and 25.
      - MIXT_QA0_NOTERM equals the OFF run's MIXT_QA0.
      - TERM8, MATCHUPX and COMBINED equal the OFF run's, and so do the 13 other arms.
      - Parity none; no arm missing. `books.json` `5cfd22f8`.
    - Construction only; no outcome was read. `~/private/paper-corun/smoke-w4-amend6e/`, script `run.sh`.
  - **The integrity gate (§7) for Week 5** follows the arming on Friday's rehearsal snapshot.
    - **Block armed:** the live file is in MANIFEST; MIXT_QA0 and MIXT_QA0_DVP carry it at ranks 2–25; NOTERM,
      MATCHUPX and COMBINED do not; TERM8 carries the paper block; every arm is built.
    - **Block off:** NOTERM == QA0, as in 6b.
  - **Code:** lab `ef46bc6`:
    - `experiments/s38_paper_corun.py`, sha256 `df3e5d5d6fb0bd1f644f148eff07c31f5678f829c3151aa994115e548609f3d2`;
    - `scripts/s38_build.py`, `f756705d…` (unchanged);
    - `scripts/s38_score.py`, `131fc323…` (unchanged);
    - **`scripts/s38_report.py` (the reader), sha256 `f177fea3e9c4b69f53a1e28bdae9c381cd33a1b5622e575fb64b58d8bf03d72d`**;
    - `tests/test_s38_paper_corun.py`, `64e53a54adeda6e02ac4b85708182e2fdc5f3335dd528b6eb47e6aedb339e43d` (23 tests).
  - **Order:**
    1. this amendment;
    2. the laptop's ack (tests and smoke);
    3. Friday's rehearsal, with the block armed as the laptop plans, and the integrity gate;
    4. Saturday, his decision. If he says no, Sunday's snapshot takes the OFF path.
- **Amendment 6f (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The outside reviewer's graph finding, relayed at the operator's request
    (`review/outside-fill-order-20261006` @ `0c727116`): within the regulars' own portfolios, the top-1% lineups carried
    more sub-$4,000 non-DST players (+0.43 sd). The harness test is study 53
    (`reports/2026-10-08-prereg-study53-cheap-pref.md`). These paper arms are its real-field record, from Week 5, with no
    money at risk.
  - **What changes.** Two exploratory arms, **MIXT_QA0_CHEAP2** and **MIXT_QA0_CHEAP4**, built as the factor arms are:
    - every live setting as MIXT_QA0, but never a live block (`FOLLOW_QA0`, `NO_LIVE_TERM`); reference MIXT_QA0_NOTERM;
    - on FP's means plus 2.0 / 4.0 points per non-DST player with a DK salary under 4,000;
    - the salaries are the snapshot frame's own, so no new file is needed (a missing salary never counts);
    - the record carries `paper_cheap` (the pool's count, by position);
    - the scorer scores them, and the reader's descriptive lines read "sub-$4k +2 / +4 − NOTERM".
  - **What does not change:** the rule (§5), the decision pair, and every other arm.
  - **The smoke** (dry run, Week 4's frozen copies; 6e's OFF+DvP and ON+DvP runs repeated with the 6f code):
    - every one of the 15 amendment-6e arms is identical, OFF and ON;
    - the two cheap arms are built (Week 4's pool: 91 such players, WR 48 / TE 43) and differ from NOTERM (2 / 0 of 26
      rows shared; FP projection per dealt lineup 143.86 / 141.43 vs 144.61);
    - they carry no live block and are equal between OFF and ON;
    - parity none. `books.json` OFF `65a43969`, ON `91fdfa42`. `~/private/paper-corun/smoke-w4-amend6f/`, script
      `run.sh`.
  - **The integrity gate (§7)** also checks both cheap arms: built, no live block, and the pool holds such players.
  - **Code:** lab `3279ab8`:
    - `experiments/s38_paper_corun.py`, sha256 `16c1bd8c613643eb7ccfd9571945055f64376819e9cd79c14f3485cbe8c2e870`;
    - `scripts/s38_build.py`, `f756705d…` (unchanged);
    - `scripts/s38_score.py`, `ec8ad8f192e2f636f3c0a22359828ab20e2925a3479799f3b6fd202f109c17a7`;
    - **`scripts/s38_report.py` (the reader), sha256 `c283a20bc08ba9c9ed7249a7232bdb12acd75e4f5b72787c49d6d27aa0464708`**;
    - `tests/test_s38_paper_corun.py`, `37db54ce351306c19748b78f53b566643d351c08e0ff64cade9301d8f7fe87f2` (24 tests).
  - **Order:**
    1. this amendment;
    2. the laptop's ack (tests and smoke);
    3. Friday's rehearsal and the integrity gate.
- **Amendment 6g (2026-10-07, a REPAIR before Week 5's first score; no Week-5 outcome exists).**
  - **Why.** The laptop's P3 Week 2–4 replay (10-07) found that `scripts/s38_plan.py` crashes on a multi-tier contest whose
    tier pays a TICKET. Week 3's $14M FFWC qualifier #42 pays first place "NFL 2026 $12.5M FFWC Contest Ticket,…", and
    the text parse raised ValueError.
    - Study 38's plan step would fail the same way in any week holding such a qualifier, and P3's scorer uses the same
      converter.
  - **What changes.** A multi-tier contest's tier is counted in dollars by its description when that is a cash amount (the
    rule as frozen). Otherwise it takes DK's numeric `value`: 70,000 for that ticket. A tier with neither raises; the
    converter never guesses.
  - **What does not change:** the plan rule ($500+ seats in a multi-tier contest, BIG; single-prize contests as before),
    the overrides, and every other file.
  - **The check:** the old and new converters were run over every contest in the Week 1–4 details files (86):
    - 83 convert identically;
    - 0 change;
    - the 3 that crashed now convert: Week 1's FFWC qualifiers #6 and #7 and Week 3's #42, each 2 seats, big, at lines
      99.9888 / 99.96 / 99.96.
  - **Code:** lab `91359fc`:
    - `scripts/s38_plan.py`, sha256 `19ad35a09cbf9a63c52c2f8ad9ac06f9f35f649d229fbe027e03d03279d2d199` (was `9af5f805…`);
    - `tests/test_s38_paper_corun.py`, `2a328926185d677a42a07c75968d7d3f615da7aa987a343ec4e79e740f43a72c` (25 tests;
      one added);
    - every other amendment-6f sha stands, including the four files the Friday integrity gate pins.
- **Amendment 6h (2026-10-07, before Week 5's first score; no Week-5 outcome exists).**
  - **Why.** The operator, 10-07, relayed verbatim by the laptop: "A $125 qualifier ticket is not considered a big win. A
    $490 qualifier ticket is."
    - The converter's single-prize rule ("BIG unless the prize is a $20 ticket") makes a $125 FFWC qualifier ticket big.
      Only Week 5's hand override (`{"196421726": {"big": false}}`) caught it.
    - The rule now encodes his definition, so no later week depends on remembering the override.
  - **What changes.** A single-prize contest is BIG unless its prize contains "$20 " (as frozen) or "FFWC $125
    Qualifier" (`NOT_BIG`). The override mechanism stays; Week 5's override is now redundant and still applied.
  - **What does not change:** multi-tier contests (6g), the overrides, the reader, and every other file.
  - **The check:** against 6g, over every contest in the Week 1–4 details files (86):
    - 85 convert identically;
    - 1 changes: Week 3's "NFL $125 2026 FFWC Qualifier Satellite", big → not big, as he defines it;
    - the Week-5 plan's big flags (`plan-week5-rev3-s24.json`) are unchanged, because its override already said so.
  - **Code:** lab `35a1c4f`:
    - `scripts/s38_plan.py`, sha256 `6c4cc53accdce8e1a8f8977e01eae8e70801558261221b0e25db609a9780cf1b` (was `19ad35a0…`);
    - `tests/test_s38_paper_corun.py`, `3c1b8a212346e20e7cc695f0734d76365e73fe81beb26e5c94d671aa1c259844` (26 tests; one
      added: $125 not big, $490 big, $20 not big, $333 / $555 / $4,444 big);
    - every other sha stands, including the four the Friday integrity gate pins.
- **Amendment 6i (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The operator chose the cheap +2 block as Week 5's live block (about 13:10, confirmed directly to the laptop),
    "matchup kept on paper". MIXT_QA0_MATCHUPX (6d) is the whole-book matchup bonus, not the 8-row block, so no paper arm
    built the matchup block in its 8-row form.
  - **What changes.** A new exploratory arm, **MIXT_QA0_MBLOCK8**: his live construction plus the 8-row MATCHUP block.
    - The block comes from a PAPER file in the snapshot, `paper-mblock-*.csv`: the week's production
      `matchup_block_file.py` file, copied by `s38_snapshot.sh`'s `S38_PAPER_MBLOCK_FILE` (integration `7c7f11ce`).
    - It uses 6b's frozen parameters (8 rows, tilt 0.20, cap 2.0, gate 0.5), through the same own_bonus and term_book.
    - It never carries the live block; its paper block replaces it, as TERM8's does. Reference MIXT_QA0_NOTERM.
    - With the matchup block live from the same file it equals MIXT_QA0. Without a paper file, with a live fill other than
      rr, or with a live regulars' block, it is missing that week (recorded).
    - It is built after every earlier arm. The build CLI, the content identity, the scorer and the reader carry it (the
      reader's descriptive line "the paper matchup block − NOTERM").
  - **What does not change:** the rule (§5), the decision pair, and every other arm.
  - **The smoke** (dry run, Week 4's frozen copies; 6f's inputs plus 6e's W4 matchup file as the paper matchup block;
    `~/private/paper-corun/smoke-w4-amend6i/`, script `run.sh`):
    - **OFF** (no live block): every one of the 17 amendment-6f arms is identical to 6f's smoke. MIXT_QA0_MBLOCK8 is built
      with 8 term rows at ranks 2, 5, 9, 12, 15, 18, 22, 25, differs from NOTERM (17 of 26 rows shared), and the paper file
      applied (127 players, none capped).
    - **ON, the matchup block live from the same file:** every 6f arm is identical to 6f's ON smoke, and MBLOCK8 = MIXT_QA0.
    - **ON, the cheap +2 block live** (production's `cheap_block_file.py` on W4's frame, cap 2.0; 134 of 292 skill
      players): MIXT_QA0 carries the cheap block (8 rows, applied) and differs from MBLOCK8. MBLOCK8, NOTERM, TERM8 and the
      factor and cheap paper arms equal OFF's.
    - Parity none in all three. `books.json` OFF `60ea49d4`, ON-matchup `5e171463`, ON-cheap `1944e3ca`.
  - **The integrity gate (§7)** adds: the MANIFEST names `paper-mblock-*`; the paper matchup block is applied;
    MIXT_QA0_MBLOCK8 has 8 term rows at ranks 2–25. The gate now pins 6i's four shas.
  - **Code:** lab `beea499`:
    - `experiments/s38_paper_corun.py`, sha256 `1f5d43e230edd634b5b0466d6e4cf37beb3221bc1491896b66ed20aad6e6cac0`;
    - `scripts/s38_build.py`, `42ce1de6526fabd0ed9621a1ec86c635c9288195565b07bb50d6f24e1f86aa4a`;
    - `scripts/s38_score.py`, `fffe2dde259a8a04344cfe3513034aa27be90d46652f2dc39d78824362dd9deb`;
    - **`scripts/s38_report.py` (the reader), sha256 `e5120fe3048b67f2c8f873d1efe199af571afbf46561258c7387eb9b40a5444a`**;
    - `tests/test_s38_paper_corun.py`, `1853acd92d61cd0e5046f59e73296599183cd18692381db47202f6f5f2d30ccc` (27 tests);
    - `scripts/s38_plan.py` `6c4cc53a…` (6h), unchanged.
  - **Order:**
    1. this amendment;
    2. the laptop's ack (tests and its own smoke copy);
    3. Friday's cheap-armed A3 and the integrity gate.
- **Amendment 6j (2026-10-07, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** Production's `--mix-cell-quotas` (study 56's switch, integration `48946cd0`, default off) changes the MIX
    cells' entry quotas. If the operator arms it on a study 56 PASS, his live book changes, and QA0 must follow it or the
    week is invalid.
    - Study 38's parity did not know the argument. A live switch would have passed silently while every paper arm kept
      the old quotas: an invalid week that looks complete.
    - The same sweep of the union's arguments (55 now; 45 at amendment 4) found three more unchecked: `--winner-select`
      and `--winner-order` (study 48d / 48b's steps, default off) and `--priority-order` (study 59's switch, default off).
  - **What changes.**
    - Every arm is built at the LIVE union's quotas, through `s28_winners_mix.QUOTAS` (the one list the fill, the blocks
      and the spares read), set for each arm's build. With the argument absent the quotas are the cells' own, so every
      arm is 6i's byte for byte.
    - A new exploratory arm, **MIXT_QA0_QB2HALF**: his live construction (every live setting as QA0, the live block
      included) at study 56's QB2HALF quotas, A1 0.44 / A2 0.28 / B 0.14 / C 0.14. It is read against MIXT_QA0, and
      equals it when those quotas are live. This is the operator's "worth a test to find out" on the real fields: study 56
      read NO DIFFERENCE (Addendum 163), so QB2HALF stays on paper in Week 5 through this arm.
    - **Parity:** a `--mix-cell-quotas` outside its definition (the four MIX cells, every value > 0, the sum 1), a live
      `--winner-select`, a live `--winner-order`, or a live `--priority-order` (production `f19222e0`, default off;
      followed only by a later amendment) is a mismatch (an invalid week).
  - **What does not change:** the rule (§5), the decision pair, and every other arm's definition.
  - **The smoke:** (dry run, Week 4's frozen copies with 6i's inputs; `~/private/paper-corun/smoke-w4-amend6j/`, script `run.sh`)
    - **OFF** (no quotas argument): every one of the 18 amendment-6i arms is identical to 6i's smoke. MIXT_QA0_QB2HALF is
      built at book cells 11 / 7 / 4 / 4 (QA0: 8 / 4 / 7 / 7) and shares 3 of 26 rows with QA0.
    - **ON**, `--mix-cell-quotas A1=0.44,A2=0.28,B=0.14,C=0.14`: parity none; MIXT_QA0 = MIXT_QA0_QB2HALF, and equals the
      OFF build's QB2HALF arm; NOTERM and the other arms follow the live quotas.
    - **ON with the cheap +2 block live:** MIXT_QA0 = MIXT_QA0_QB2HALF, both with 8 term rows.
    - `books.json` OFF `906c6861`, ON `a4112f83`, ON + block `41545383`.
    - The parity tests also cover an undefined quotas spec (five forms) and live `--winner-select`, `--winner-order` and
      `--priority-order`.
  - **The integrity gate (§7)** adds: MIXT_QA0_QB2HALF is built; with the QB2HALF quotas live, QB2HALF = MIXT_QA0. The gate
    pins 6j's four shas.
  - **Code:** lab `44becda`:
    - `experiments/s38_paper_corun.py`, sha256 `801381ab7540b3f08072e1270a8603cf1d3429c2cddad18a536cefee55aebcc0`;
    - `scripts/s38_build.py`, `bb52c6f18ca02f92fe7596ec70aaef604f0cecc50f1d245cae4b036f2619ef8c`;
    - `scripts/s38_score.py`, `564ce2c60b22b33ffb1d44af8d6c844cebe291e9ca6256dcfe1226516763932a`;
    - **`scripts/s38_report.py` (the reader), sha256 `de63c136fe4442c1077fd4cb60a20b95fd6dd9b9de1c2cd989bf6888b959a74a`**;
    - `tests/test_s38_paper_corun.py`, `b00f9b5ec92ea830ca0345f6d1cb6a5c96ffea6f6b8167c4775bcf43a49dad62` (28 tests; one added, three earlier pinned
      strings updated);
    - `scripts/s38_plan.py` `6c4cc53a…` (6h), unchanged.
  - **Order:**
    1. this amendment;
    2. the laptop's ack;
    3. Friday's A3 and the integrity gate (pinned to 6j).
- **Amendment 6k (2026-10-08, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The operator asked on 10-07 night, relayed by the outside reviewer (study list 63): "I would like to do more
    testing on the QB tight end stacks right away" … "and also to include a bonus to the tight end in these types of
    situations."
    - The harness test is study 63.
    - These arms add a real-field read from Week 5, at no risk.
  - **What changes.** Three new exploratory arms. Each is his live construction with an 8-row PAPER tight-end block
    INSTEAD of any live block, with 6b's frozen parameters (8 rows, tilt 0.20, cap 2.0, coverage gate 0.5):
    - **MIXT_QA0_TE2B8:** +2.0 to pass-catching TEs, those whose frame `target_share_l4` is ≥ 0.15.
    - **MIXT_QA0_TETOUGH2B8:** those TEs only when they face the slate's toughest third of pass defences, by
      `epa_per_dropback_allowed_l6`. This is the operator's form.
    - **MIXT_QA0_CHEAPTE2B8:** one block giving +2.0 to a pass-catching TE OR to any non-DST player under $4,000.
  - **How the blocks are built.**
    - Each block file is written by PRODUCTION's `scripts/te_block_file.py`, imported from the pinned checkout (never
      copied), with its sha256 asserted: `196ae64eaf795c4dd9a802d2659cdf8747c4a16ace60431f9a5d676290ff2bf1`. Integration
      `266da256` holds it, and the laptop's test `d35e1542…` passes 8.
    - The writer runs on the snapshot's own frame, so there is no new snapshot file. Its output goes into the build's
      out dir and is read through the same `own_bonus` and `term_book` as every paper block.
  - **How they are read:** against **MIXT_QA0**, his live book with the live cheap block. The Week-6 question is "this
    block INSTEAD of the cheap block".
  - **When an arm is missing that week** (recorded):
    - the writer is absent or is not the pinned one;
    - the writer refuses the frame (for the tough form, a frame without `epa_per_dropback_allowed_l6`; the laptop checks
      A3's W5 frame on Thursday);
    - `own_bonus` refuses the file;
    - the live fill is not rr, or a regulars' block is live.
  - **Disclosed (production O-55, `1004155c`):** the served frame's defence columns are one game staler than training's,
    because Week W's frame holds the defence's week W−1 row. The tough third reads the SERVED value, which is exactly
    what a live block would read.
  - **What does not change:** the rule (§5), the decision pair, every other arm and the snapshot.
  - **The smoke** (dry run on Week 4's frozen copies with 6i's onc-6i inputs, the cheap +2 block live;
    `~/private/paper-corun/smoke-w4-amend6k/`, script `run.sh`):
    - **Against `s38-prod-pin`** (no writer): every 6i arm is identical to onc-6i's (rows and ranks), and the three TE
      arms are missing, "production's te_block_file.py is not in the pinned checkout". `books.json` is `6e4f8353`.
    - **Against production `266da256`:**
      - Every arm is identical to the pin's build. The union_reselect sha differs, ffd59b72 vs 8b325960, and moves no arm.
      - The three TE arms are built, each with 8 term rows at ranks 2, 5, 9, 12, 15, 18, 22, 25.
      - The TE2 and CHEAPTE2 files are byte-identical to the outside reviewer's W4 replay files (`80a3b039…`,
        `53208c3f…`).
      - TETOUGH2 gives the bonus to 4 TEs (file `c90de0c7…`).
      - Each TE arm shares 18–19 of 26 rows with QA0.
      - `books.json` is `9c7d9046`.
  - **The integrity gate (§7)** adds four checks:
    - the TE blocks used the pinned writer;
    - TE2B8 and CHEAPTE2B8 carry 8 term rows at those ranks;
    - TETOUGH2B8 does too, or is missing only for a frame without the pass-defence column;
    - every other arm is still required.
    - The gate pins 6k's four shas, and its default production checkout must contain `266da256`. That is Friday's move
      of `s38-prod-pin` to FRIDAY_HEAD.
  - **Code:** lab `82a5bf4`:
    - `experiments/s38_paper_corun.py`, sha256 `770aa5c6d94ea38833d916e89e345da1c26a673dcdb9358456094ad6b8af37ce`;
    - `scripts/s38_build.py`, `412f92a222b572c1356599051ed9438471b4c3838cefaac7002962d4ac208790`;
    - `scripts/s38_score.py`, `fb8781fb298ca9d89d56762244f98a5738c7750f661d7548299663f79f2bf938`;
    - **`scripts/s38_report.py` (the reader), sha256 `afd56ba1e317774c99dd268df45fc395b6924b47a34719080ee2341e72a90a1d`**;
    - `tests/test_s38_paper_corun.py`, `f757a1b10d092fb5f0e345b296fbf97a5354911435fd0bca607f4f04ddba1c63` (29 tests; one
      added, one order assertion updated);
    - `scripts/s38_plan.py` `6c4cc53a…` (6h), unchanged.
  - **Order:**
    1. this amendment;
    2. the laptop's ack;
    3. Thursday's frame-column check on A3;
    4. Friday's A3, `s38-prod-pin` moved to FRIDAY_HEAD, and the integrity gate (pinned to 6k).

- **Amendment 6l (2026-10-09, before Week 5's lock; no Week-5 outcome exists).**
  - **Why (the outside reviewer's finding, verified by the laptop and the reviewer, 10-08 night).** `parity()` was an
    ALLOW-LIST of named checks.
    - Amendment 4 classified the 46 union arguments of 10-06. Nothing classified the arguments added since: 57 at
      integration `bf45a29a`, plus four flags on unmerged branches.
    - So a construction argument the paper arms do not build passed unseen. The merged `--mix-bring-back-top-wr` /
      `--mix-bring-back-top-wr-rows` (studies 71 / 71b) is an example, as are the flex-WR (study 75), top-game (73 / 74)
      and QB-alone (77) flags.
    - Armed live, MIXT_QA0 would silently not be his live book, and the week would look valid. That is the failure
      CLAUDE.md names: "an invalid week that looks complete is worse than a missing week."
  - **What changes: DEFAULT-DENY.**
    - Every union argument (its argparse dest) is classified in `UNION_ARGS` as one of:
      - checked by parity;
      - not built (`NOT_BUILT`);
      - a snapshot input or run control;
      - inert for the 26-row MIX book under the checked settings, with the reason written beside it (e.g. the sleeve's
        arguments with `--tail-sleeve 0`, the mean selector's `--mean-dst-cap`, the spares built after the book).
    - A live argument outside the classification is a parity MISMATCH.
    - So is a NOT_BUILT argument at anything but absent or its off value: `--mix-bring-back-top-wr` (off ""), and
      `--mix-bring-back-top-wr-rows`, `--mix-flex-wr-rows`, `--mix-top-game-qb1`, `--mix-top-game-stack`,
      `--mix-qb-alone-rows` (off 0).
    - So is `--pmo` above 0, or `--main-game-cap` other than off. Amendment 4 left these two to the union's own refusal
      under `--main mix`; they are now checked here too.
  - **The pinned production checkout is read as well** (`union_classification`). The build parses the `--prod` checkout's
    `scripts/union_reselect.py`: the checkout it is given, never a hard-coded commit (frozen-chain rule 7). It records as
    a mismatch:
    - any argument there that is not classified;
    - any argument whose default differs from the one these checks assume when the argument is absent from
      `union_args.txt` (`ASSUMED_DEFAULTS`: e.g. `--mix-fill group`, `--term-block-rows 0`, every not-built flag off).
    - So a lever merged into production before the table classifies it fails the integrity gate instead of passing it.
  - **One classification kept by the frozen design (the laptop's observation at its ack):** `--main-own-tilt` stays
    "inert". Each paper arm owns its tilt (the frozen table: none for MIXT_QA0, 0.20 for QA / RS / QBB / NQC), and the
    live union may run any tilt.
    - So a live whole-book tilt without a term block would make MIXT_QA (0.20), not MIXT_QA0, the closer match to his
      live book, and parity does not say so.
    - Week 5's live tilt is 0 (the term block is the live lever, and it refuses a whole-book tilt), so this is moot for
      Week 5. A future week that arms a whole-book tilt names QA beside QA0 in its record.
  - **What a mismatch does:** an invalid week, as before. Live mode refuses ("PARITY REFUSED"), and the reader marks the
    week INVALID.
  - **What does not change:** every arm, the rule (§5), the decision pair, the snapshot and the scorer. The smoke shows
    every book unchanged.
  - **Also recorded here (the earlier 6l item): the scorer's pin.**
    - Production's `scripts/moneygate_score.py` is now `dd8ff1f7…`. §7 names `48342ae1…`.
    - The new version equals the old table for Weeks 1–4 and adds the schedule for Weeks 5–18. The laptop reconciled it
      on W1–4 (PASS, receipts identical), and the live receipt names it.
    - `s38_score.py` records the scorer's sha in each week's record (it does not assert it). Week 5's record should name
      `dd8ff1f7…`.
  - **If he takes study 77's trial** (`--mix-qb-alone-rows 3`), 6l refuses that week as written. Amendment 6m, drafted
    only on his yes, would make MIXT_QA0 follow it through study 77's frozen wrapper. Without 6m, a week with the trial
    armed is INVALID for study 38: fail-closed, never silent.
  - **Disclosed (machine):** while study 78's scored run held the machine, the reviewer ran study 38's test module once
    (1.4 s; one new test failed on its own fixture, a whole-book tilt with a term block, which parity correctly refuses)
    and a few one-second `python -c` parity checks. Everything else ran in a gap.
  - **The smoke:** dry run on Week 4's frozen copies with 6k's inputs (the W5-shaped args `union-args-ms4-rr-cheap8.txt`: mix,
    rr, overlap 4, QB cap 5, the 8-row cheap block); `~/private/paper-corun/smoke-w4-amend6l/`, script `run.sh` `7f475b00`;
    lab `bf53dccd`, clean; 00:32–00:37 CDT, in the gap after study 78's run.
    - The tests: 31 pass (6k's 29 and 6l's two).
    - **pin-6l** (production `s38-prod-pin` `1478dcfb`): every one of the 19 arms is identical to 6k's pin build (rows and
      ranks), and `books.json` is byte-identical (`6e4f8353`). The three TE arms are missing, as at 6k (no writer in the
      pin). Union mismatches: none.
    - **head-6l** (production integration `bf45a29a`, 57 union arguments): every one of the 22 arms is identical to 6k's
      head build (`266da256`). `books.json` is `a63927ed`; it differs only by the production identities it records.
      Union mismatches: none.
    - **deny-6l** (the head with the same args plus `--mix-bring-back-top-wr B`): the dry run records exactly one
      mismatch, "--mix-bring-back-top-wr 'B' (the paper arms build no such rows; amendment 6l)" (live mode would refuse).
      `books.json` is `fe860af1`.
    - **The classification against every production state FRIDAY_HEAD could be:** the pin, the integration head
      `bf45a29a` and the unmerged branches (flex-WR `09e93be1`, s73 `60cc9cfe`, s74 `e25fb520`; QB-alone `3a9327e1`,
      dest `mix_qb_alone_rows`, off 0) all give no unclassified argument and no
      changed default.
    - **Parity on real argument files:** the W5 arming (the laptop's `w4_union_run.sh`) gives none. A1's 10-07 args give
      only their expected W4-era mismatches (tail sleeve 5, entries 105, no QB cap).
  - **Code:** lab `bf53dccd` (on `82a5bf4a`):
    - `experiments/s38_paper_corun.py`, sha256 `3e891ffdf6473d53aae4e2e5f5ba424b8f1956f8db1fe4f8607f8b3b7f34332c`;
    - `tests/test_s38_paper_corun.py`, `6e6a3e815620133aa7be3e5ae3662cb3b8c66944b7bf00cb7588c901d5bf913d` (31 tests; two
      added);
    - unchanged: `scripts/s38_build.py` `412f92a2…`, `scripts/s38_score.py` `fb8781fb…`, **the reader
      `scripts/s38_report.py` `afd56ba1…`**, `scripts/s38_plan.py` `6c4cc53a…`.
    - The integrity gate pins 6l's module sha in place of 6k's; the other three gate shas stand.
  - **Follow-up (10-09 01:17, after the laptop's ack of `bf53dccd`):** `--mix-one-catcher-rows` (study 79's option,
    production `review/one-catcher-flag-20261009`, unmerged) is classified NOT_BUILT, off 0 (`ASSUMED_DEFAULTS` 0). So a
    default-off merge into FRIDAY_HEAD cannot fail the gate, and a live nonzero value is a mismatch until a 6m-style follow
    (only on his yes).
    - Lab `a430d8b1`: `experiments/s38_paper_corun.py` `0930eb63beaf…`, `tests/test_s38_paper_corun.py` `2ccb2cf4744f…`
      (31 tests pass, rc 0).
    - `union_classification` gives no unclassified argument and no changed default on the pin, `bf45a29a` and every
      unmerged flag branch, including the one-catcher head `8a907f6e`.
    - The integrity gate pins this module sha in place of `bf53dccd`'s. The smoke's books are unaffected: one table entry,
      read only by parity.
  - **Second follow-up (10-09, after studies 83 / 84's production options appeared):** `--mix-no-te-above` (studies 81 /
    84's TE ban, production `review/combo-te-flag-20261009`, unmerged) is classified NOT_BUILT, off 0 (`ASSUMED_DEFAULTS` 0).
    - Lab `9058617a`: `experiments/s38_paper_corun.py` `a03051ce7abd…`, `tests/test_s38_paper_corun.py` `45c97287e6bb…`
      (31 tests pass, rc 0).
    - `union_classification` gives no unclassified argument and no changed default on the pin, `bf45a29a` and every
      unmerged option branch, including the combined option (`review/combo-flag-20261009`) and the TE option
      (`review/combo-te-flag-20261009`).
    - The integrity gate pins this module sha. One table entry, read only by parity; no book can move.
    - A live nonzero value, or the three-flag combination, stays a mismatch (an invalid week) until amendment 6m makes the
      MIXT_QA0 arms follow whichever version he enters (only if study 84's entry order enters one).
  - **Order:**
    1. this amendment;
    2. the laptop's ack (shas, tests, the smoke);
    3. Friday's A3 with `s38-prod-pin` moved to FRIDAY_HEAD (whatever head he ends up with: the classification reads it);
    4. the integrity gate pinned to 6l.

- **Amendment 6n (2026-10-09, before Week 5's lock; no Week-5 outcome exists).**
  - **Why.** The operator, 10-09 (relayed by the outside reviewer; recorded by the laptop): the Week-5 per-player exposure
    cap moves from 50% to 35%, a reversible trial ("Yes, W5 trial"). Study 38's paper arms follow every live construction
    setting. Today's parity pins `--main-cap-share 0.5`, so a live 0.35 would make Week 5 INVALID.
  - **What changes.** Every paper arm is built at THE LIVE UNION'S `--main-cap-share`, exactly as amendment 1 made every
    arm follow the live overlap limit. The decision pair keeps comparing structures at the live caps.
    - The cap is production's own form, `main_exposure_cap`: a player in max(1, int(share × K)) rows is banned from later
      solves. That is 13 rows at 0.5 and 9 at 0.35 (K 26).
    - Accepted shares (`CAP_SHARE_OK`): 0.5, the old setting, and 0.35, the trial. Anything else is a parity mismatch: an
      invalid week. The DST cap is unchanged (0.25).
    - `main_cap_share` leaves the fixed parity table and is checked by `live_cap_share` instead (6l's classification:
      "checked").
  - **His real book** (the laptop's outcome-blind W4 check, 35% cap): FP projection −2.31 per row; 17 of 26 rows change; the
    most-used player 13 → 9 rows; players in ≥ 40% of entries 7 → 0.
  - **The smoke** (dry run on Week 4's frozen copies with 6l's inputs; `~/private/paper-corun/smoke-w4-amend6n/`, script
    `run.sh` `ce227c99`; lab `28bf0eba`):
    - 32 tests pass (rc 0).
    - **pin-6n** (0.5): every one of the 19 arms is identical to 6l's pin build (rows and ranks); mismatches none.
    - **cap35** (0.35): mismatches none; the player cap is 9 rows, and every arm's most-used player sits at exactly 9 of the
      26 book rows.
    - **bad04** (0.4): the dry run records exactly the one mismatch "--main-cap-share '0.4' (the paper arms are defined at
      0.35 / 0.5; amendment 6n)".
  - **Code:** lab `28bf0eba` (on `9058617a`): `experiments/s38_paper_corun.py` sha256
    `5e4306835dfe3d3b3e4de8fd8f203bafbff7835985e02abf20b870d6e9b0e2ab`; `tests/test_s38_paper_corun.py`
    `283fc8ac0c758a30953c5da154609497474c3c6e9876e8977acb0e05ef2b7969` (32 tests). The reader, scorer, build and plan files
    are unchanged.
  - **The integrity gate** pins this module sha in place of 6l's `a03051ce…`. Friday's A3 rehearsal was cancelled by the
    operator, so the gate runs on the live snapshot: Saturday's arming or Sunday's T-70.
  - **Order:**
    1. this amendment;
    2. the laptop's ack (shas, tests, the smoke);
    3. the live arming with `UNION_MAIN_CAP=0.35` (his decision);
    4. the integrity gate on the live snapshot.
- **Amendment 6n, follow-up (2026-10-09, before Week 5's lock; no Week-5 outcome exists): the 50% book on paper.**
  - **Why.** The laptop's check of 6n: under a live 0.35 every paper arm moves to 0.35, so nothing measured the 50% book
    that his trial keeps "on paper" (HANDOFF `a391f2e5`: ARM 0.35 "with the 50% book scored on paper beside it").
  - **What changes.** One exploratory arm, **MIXT_QA0_CAP50**:
    - his live construction at the FIXED player cap 0.5 (13 of 26 rows);
    - it follows every other live setting as MIXT_QA0 does (`FOLLOW_QA0`: overlap limit, fill, regulars' block, cell
      quotas, the live term block);
    - read against MIXT_QA0 (`REF`).
    - It is built only when the live cap is not 0.5. Otherwise it is MIXT_QA0's book and is recorded in `arms_missing`
      ("the live player cap is 0.5: the same book as MIXT_QA0").
    - The arm gets its own caps (`arm_caps`; the DST cap unchanged). Every other arm's `arm_caps` is the shared caps, so
      no other book moves. Each arm's record carries `player_cap_rows`.
    - The scorer records `build.main_cap_share`. The reader's descriptive line adds "QA0 at the 50% player cap - QA0 at
      the live {cap}" with both books' expected big seats. A test runs that line on synthetic scores (no outcome).
    - Descriptive only, never decision-bearing. The decision pair (MIXT_RS0 against MIXT_QA0) is unchanged.
  - **The smoke** (dry run on Week 4's frozen copies with 6n's inputs; `~/private/paper-corun/smoke-w4-amend6n2/`, script
    `run.sh` `5ecf2ba9`, log `55b7d303`; lab `dc6df978`):
    - 34 tests pass (rc 0); the cap35 union args are 6n's file byte for byte.
    - **pin** (0.5): the 19 built arms are identical to 6n's pin build (rows and ranks); mismatches none; MIXT_QA0_CAP50
      recorded missing ("the live player cap is 0.5: the same book as MIXT_QA0").
    - **cap35** (0.35): the 19 other arms are identical to 6n's cap35 build; mismatches none. **MIXT_QA0_CAP50 is identical,
      rows and ranks, to 6n's pin MIXT_QA0** (the same union arguments but the cap): it is the 50% book exactly. Its most-used
      player sits at 13 rows (MIXT_QA0's at 9).
    - **bad04** (0.4): exactly the one mismatch, as in 6n; MIXT_QA0_CAP50 not built (the paper share falls back to 0.5).
  - **Code:** lab `dc6df978` (`7ca9bb38` the arm, then `dc6df978` the reader test; on 6n's `28bf0eba`):
    - `experiments/s38_paper_corun.py` sha256 `de77764112f9beed838f8e73350680df945d519f606a2be69efedb21d6244409`;
    - `scripts/s38_score.py` `ee0ca6b9c6134149d4b178cbca72a5b9bd2ffbb133202e11c10caea12aba1e96`;
    - `scripts/s38_report.py` `9942d38eab1ba706285b5a58bc1ca093b959b337ee659f89bca8efb6a4e395aa`;
    - `tests/test_s38_paper_corun.py` `023b4eec736314a5b4f0e04e4004fd49dd2a8eb5b01c7976c962f03e18a4c107` (34 tests).
    - The build and plan files are unchanged.
  - **The integrity gate** pins this module sha in place of 6n's `5e430683…`, on the live snapshot (Saturday's arming or
    Sunday's T-70).
  - **Order:**
    1. this follow-up;
    2. the laptop's ack (shas, tests, the smoke);
    3. the integrity gate on the live snapshot.
  - **Week 5 (10-09, after study 89's READ):** his rule kept the live cap at 0.5 (Addendum 186), so MIXT_QA0_CAP50 is not
    built in Week 5 and every other book is 6n's. The follow-up is kept for any week whose live cap is 0.35.

- **Amendment 6o (2026-10-09, before Week 5's lock; no Week-5 outcome exists): his W5 package on paper.**
  - **Why.** His decision (10-09, in the outside reviewer's session; HANDOFF `5380e0e7`): "Use the tested package (35% max +
    each player capped at FantasyPros' projected ownership + 15 points) live in Week 5?" → "Live W5 trial if built in time
    (Recommended)". The option: production builds it (default off), proves parity with the lab and checks his W4 book; armed
    Saturday only if all of that passes, "with today's book scored on paper beside it". Under 6l's default-deny the new
    flag would make the week INVALID.
  - **What changes.**
    - **Parity.** The four new union arguments (`--main-own-cap-delta`, `--main-own-cap-source`,
      `--main-own-cap-min-coverage`, `--main-own-cap-fallback-share`) are "checked". Two live states are accepted:
      - (0.5, off): today's book, also the host's fallback week;
      - (0.35, delta 15 with a source, coverage 0.9, an EXPLICIT fallback share 0.5).
      Everything else is a mismatch, an invalid week:
      - the flat 35% alone (his rule: it never runs alone);
      - 0.5 with the ownership cap;
      - another delta, coverage or fallback;
      - a package without the fallback share (production's default is none, and a refused cap would then build at 35%).
    - **The caps.** Computed by PRODUCTION's `own_cap_rows` (the pinned checkout) on the snapshot's copy of the union's
      own-cap file, with s38's own exclusions (the union's form). They are applied in the lab builder by study 89's
      `own_caps` (`s89_own_cap.py` `92b09345`), pasted byte for byte; a test pins its text (`aec94b8b…`). It runs inside the
      tiers' builder, on book solves only (spares never). An infeasible solve is re-solved without the ownership bans and
      recorded per arm.
    - **The live state comes from the union receipt,** not from the arguments alone: `own_cap_source.applied` and
      `cap_share_used`.
      - The paper build must agree on applied or refused, on the share used, and on the cap's identity (`source_sha256`,
        `factor`, `matched_skill_players`, the coverage, `min_cap_rows` and the other meta keys present in both). If not,
        the week is invalid.
      - A cap refused by both means the live union built today's book (the fallback share 0.5, no cap), so the paper arms
        do too.
    - **Every paper arm follows the live ownership cap,** as 6n made them follow the player cap.
    - **MIXT_QA0_TODAY** (exploratory; his named comparison, "today's book"): his live construction at 0.5 with NO ownership
      cap. It is built only when the live book is not that, and read against MIXT_QA0 with both books' expected big seats.
    - **MIXT_QA0_CAP50** keeps 6n's definition: 0.5 with the live ownership cap. In a package week it isolates the flat cap
      inside the package. This supersedes the 6n follow-up's Week-5 line: if the package arms in Week 5, CAP50 and TODAY are
      both built; if it does not, neither is.
    - **The snapshot.** Production's `s38_snapshot.sh` copies the union's `--main-own-cap-source` as named (review
      `bbc6581c`, merged with the flag and the host wiring), and s38_build resolves it as `own_cap_src`.
  - **The smoke** (dry run on Week 4's frozen copies with 6n2's inputs; production at the flag `c948944d`;
    `~/private/paper-corun/smoke-w4-amend6o/`, script `run.sh` `a5f9ce3a`, log `97c5a837`; lab `0cfc51c3`, production `680533c8`, union_reselect `3ff8f0d5`, the W4 file
    `0ec90a6b`, PYTHONHASHSEED=0):
    - 40 tests pass (rc 0).
    - **pinN** (0.5, no own-cap flags): the 19 arms of 6n2's pin build are identical (rows and ranks); mismatches none;
      CAP50 and TODAY recorded missing. (This checkout also builds the three TE-block arms, which the older pin lacked: 22.)
    - **pkg** (0.35 + delta 15 + the W4 FP ownership file + coverage 0.9 + fallback 0.5): mismatches none; the cap applied
      (factor 1.012781, 292 of 292 skill players matched, coverage 1.0, the minimum cap 3 rows).
      - **MIXT_QA0_TODAY is identical, rows and ranks, to pinN's MIXT_QA0**: today's book exactly.
      - Every capped arm: the most-used player at 9 rows, **0 skill players over their ownership cap**, 26 ruled solves,
        0 re-solved without the ownership bans; 1.5–5.3 players banned per solve on average (max 16).
      - MIXT_QA0_CAP50 (13 + the ownership cap): the most-used player at 11 rows, 0 over the cap.
    - **pkgrec** (pkg + the laptop's W4 package-check receipt, `~/rehearsals/flagcheck-pkg035own15-20261009T173906Z/on/`,
      applied, cap_share_used 0.35): mismatches none (the receipt and the paper build agree); the books equal pkg's.
    - **refused** (a non-number fp_own_raw on one skill row; a receipt "applied false, 0.5"): both refused; mismatches none;
      the paper arms at 0.5 with no cap; **all 22 books identical to pinN's**; CAP50 and TODAY missing.
    - **disagree** (the refusing file; a receipt "applied true"): the mismatch "the union applied the ownership cap and the
      paper build refused it" recorded.
    - Parity only: the flat 35% alone and 0.5 with the package are each the expected mismatch.
  - **Code:** lab `0cfc51c3` (`e050c730` the code, `e9a44d5b` and `0cfc51c3` the receipt keys; on 6n2's `dc6df978`):
    - `experiments/s38_paper_corun.py` sha256 `238d7c1ea48fa67cee0b990022277d3b412e9c535583ace6a6d8b39b490360f1`;
    - `scripts/s38_build.py` `15373e149d6e742a1ae83b7c3ab70ea9bc1f9be6f1037a0c367a1cb02c70e3c9`;
    - `scripts/s38_score.py` `491ee2e3f210903172786677a2d7fe82c26a40af5615dc786146c887540ea603`;
    - `scripts/s38_report.py` `b5449db4f23056d2ee48827ff5dffe0ee3ef34fa2c60e0d28b3d48c59c03f595`;
    - `tests/test_s38_paper_corun.py` `e4743350d1da5e1ac3ec3c09818212329f40300fc35a47560462ba9459538c3c` (40 tests).
    - Strict receipt keys: the exclusion-free meta (source_sha256, column, delta_pts, k, skill_sum_raw, rescale_to, factor,
      matched / skill players, unnamed, rows_without_fp_own_raw, min_coverage) plus applied and cap_share_used; the coverage
      and the pool's minimum cap depend on the T-70 exclusions and are recorded only (`info_differs`).
  - **The integrity gate** pins this module sha in place of 6n2's `de777641…`, on the live snapshot.
  - **Order:**
    1. this amendment;
    2. the laptop's ack (shas, tests, the smoke);
    3. one merge batch before FRIDAY_HEAD (the flag, the host wiring, the snapshot change);
    4. Saturday's arming, his package only if production's parity and the W4 check pass, else today's book (his option text);
    5. the integrity gate on the live snapshot.

- **Amendment 6p (2026-10-09, before Week 5's lock; no Week-5 outcome exists): his limited-entry row rules on paper.**
  - **Why.** His request (HANDOFF `f8b1dc30`): the limited-entry contests' winners against ours, and two tests, "Yes do that".
    - The outside reviewer's real-field scan of his W1–4 limited-entry contests (aggregates; hindsight, NOT evidence): a TE in
      our flex in 54–100% of entries against the top 3's 11–50%; about 1.0 player under 3% REALIZED contest ownership per
      lineup against the top 3's 0.4–0.5.
      The report: `reports/lab-handoffs/2026-10-09-limited-entry-winners/README.md` (sha256 `cadc6ae2cec18358…`; with
      `analyze.py` and `select_by_p1.py`, which write only under `~/private/`), committed at `9e4c39da` with study 91's prereg.
      Its second finding: selecting by the model's P(1st) against each real field did not beat selecting by projection in 4 of 5
      groups, and the T-70 pool held a would-be winner in most contests (pre-lock selection, not generation, is the bottleneck).
    - His follow-up (HANDOFF `2ab54e30`): the harness test (study 91) decides whether the rule goes LIVE in Week 5. This paper
      test is the real-field measurement either way.
  - **The prior.** The TE half was read twice in the harness, flat both times: study 85's no-TE-in-flex rule +0.2 (2022 +3.4;
    Addendum 183) and study 88's TE-in-flex-allowed against BOOK87 +0.2 (2022 +0.1; Addendum 187). The low-ownership cap is new.
  - **What changes.** Two exploratory paper arms on his live construction (every live setting as MIXT_QA0 follows it,
    `FOLLOW_QA0`, the package included), read against MIXT_QA0, overall AND per contest group:
    - **MIXT_QA0_TE1:** at most one TE per book row (= no TE in the flex);
    - **MIXT_QA0_TE1_LOW1:** that, and at most one skill player whose FP projected ownership is below 3%.
      - The ownership is the snapshot ownership file's `fp_own_raw` (FP's raw %): the union's own-cap file in a package
        week, else the week's `ownership_fp` copy.
      - Players are matched by the frame id, then the DK id; a blank value (lag-filled) or an unnamed player counts as 0%;
        DSTs are never counted; a non-number refuses the arm (recorded missing).
    - **The mechanics:** every BOOK solve (j < 26, build order, any cell, the live and the term block; spares never) carries
      the rules as `set_constraints`, one solve; infeasible → the same solve without them, recorded (`row_rules`; study 87's
      pattern). It sits INSIDE the ownership cap, so the rules are dropped first and the ownership cap is kept. Its records go
      to its own class (a subclass-attribute collision with `own_caps` that the new test caught before any build).
    - **The contest groups:** the Millionaire, and every other plan contest (his limited-entry satellites). The scorer adds
      `by_group` per arm; the reader prints one 6p line per week (each rule − QA0, overall / limited entry / Millionaire).
    - Every arm's record adds TEs per row, low-owned players per row and the rows it shares with its reference.
  - **The smoke** (dry run on Week 4's frozen copies; 6o's package and fallback states; production at FRIDAY_HEAD `22bf64f1`;
    `~/private/paper-corun/smoke-w4-amend6p/`, script `run.sh` `4958672478cf`, log `e0e614581b35`; lab `b03ddaac`; PYTHONHASHSEED=0):
    - 43 tests pass (rc 0).
    - **Package week:** mismatches none; the 24 pre-6p arms are identical to 6o's build; the low set holds 163 of 235 pool
      skill players (all named), with 55 pool TEs.
      - MIXT_QA0: 1.654 TEs and 0.115 low-owned players per row; FP projection per dealt lineup 141.40.
      - **TE1:** 1.00 TE per row; 0.269 low-owned; 5 of 26 rows shared with QA0 (21 change); 26 ruled solves, 0 re-solved;
        the ownership cap kept (0 plain); FP 140.80 (−0.61).
      - **TE1_LOW1:** 1.00 TE; 0.231 low-owned; 5 rows shared; FP 140.79 (−0.61).
    - **Fallback week** (0.5, no cap; the low set from the week's ownership file): the pre-6p arms identical to 6o's;
      **TE1 and TE1_LOW1 identical** (0.115 low-owned per row each; FP −0.26).
    - **Plainly:** on his real Week-4 book the TE rule changes 21 of 26 lineups. The low-ownership half barely binds, because
      by FP's PROJECTIONS his book holds only 0.1–0.3 players under 3% per lineup. The real-field excess is in REALIZED
      ownership, which no pre-lock rule can see.
  - **Code:** lab `b03ddaac` (on 6o's `0cfc51c3`):
    - `experiments/s38_paper_corun.py` sha256 `ecc55fa0f934fd20ad7e0dc5e7125d3c8d4ea31325dbc50ae64da9ba552d0afd`;
    - `scripts/s38_score.py` `9d99c0a969f155de61cf9f41c388a86ee29463c1173e40c76b2aadd113a59df9`;
    - `scripts/s38_report.py` `3f9b6d8ca85d57e64f04460850dcaefd14d1ac446eb697da2a407a6242ee037b`;
    - `tests/test_s38_paper_corun.py` `595ca69b05bf6e2866b3edc7ad689a5306046622b28a958dfaa237448cc15932` (43 tests);
    - `scripts/s38_build.py` unchanged (`15373e14…`).
  - **The integrity gate** pins this module sha in place of 6o's `238d7c1e…`, on the live snapshot.
  - **If study 91 puts the rule LIVE in Week 5** (his rule: better than the package on both draws, seats ≥ 0.80): a
    follow-up (6q) classifies the live row-rule flag as checked, makes MIXT_QA0 follow it, adds the package without the rule as
    the paired paper book, and records TE1_LOW1 as missing (then the same book as MIXT_QA0). Its format is agreed with the
    outside reviewer first.
  - **Order:**
    1. this amendment;
    2. the laptop's ack;
    3. the gate pin moved;
    4. the integrity gate on the live snapshot.

- **Amendment 6q (2026-10-09, before Week 5's lock; no Week-5 outcome exists): his row rules LIVE, the package without them on paper.**
  - **Why.** Study 91's frozen rule said GO LIVE (Addendum 188). Stated the transfer caveat (the gain was the low-ownership half,
    which barely binds on his FP book), he chose to go live in three sessions. Production's row-rules flag (`e8c63263`;
    `--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3`, on the ownership cap) enters Week 5. Under 6l's default-deny the
    three arguments would make the week INVALID.
  - **What changes.**
    - **Parity:** the three arguments are "checked". Accepted live states: the rules off, or 1 / 1 / 3% on his package. Any
      other value, or the rules without the ownership cap, is a mismatch.
    - **The live sets** come from PRODUCTION's `row_rule_sets` (the pinned checkout) on the snapshot's copy of the own-cap file,
      with s38's own exclusions, and are applied by 6p's `row_rules` inside `own_caps`. Production applies the rules only on an
      applied ownership cap; so does 6q.
    - **The receipt** (`config.union.mix.mix.row_rules_source`) must agree with the paper build: applied, `source_sha256`,
      `low_pct`, `te_max`, `low_own_max` strictly; the exclusion-dependent counts (`pool_skill_players`, `named`, `low_owned`,
      `pool_tes`) are recorded only. Else the week is invalid.
    - **Every paper arm follows the live rules** (as 6o made them follow the ownership cap), except:
      - **MIXT_QA0_NORR** (new, exploratory): his live package WITHOUT the row rules, the paired paper book, built only when the
        rules are live, read against MIXT_QA0 overall and per contest group with both books' expected big seats;
      - **MIXT_QA0_TODAY**: unchanged (0.5, no ownership cap, no rules: the pre-package book);
      - **MIXT_QA0_TE1** keeps its own rule (the TE half alone, in place of the live rules);
      - **MIXT_QA0_TE1_LOW1** is then the live book itself and is recorded missing.
  - **The smoke** (dry run on Week 4's frozen copies; production at the flag `e8c63263` (union_reselect `869a112b`);
    `~/private/paper-corun/smoke-w4-amend6q/`, script `run.sh` `0300f52dd475`, log `678825f929a6`; lab `16d7b8fc`; PYTHONHASHSEED=0):
    - 44 tests pass (rc 0).
    - **The rules live** (the package + the three flags + the laptop's W4 receipt `flagcheck-pkgTE1LOW1-…/on/receipt.json`):
      mismatches none; the rules applied; the receipt agrees (no strict or informational key differs).
      - **MIXT_QA0 is identical, rows and ranks, to 6p's MIXT_QA0_TE1_LOW1** (production's sets = 6p's `low_owned` sets);
      - **MIXT_QA0_NORR is identical to 6p's MIXT_QA0** (the package book);
      - MIXT_QA0_TE1 and MIXT_QA0_TODAY are identical to 6p's;
      - MIXT_QA0_TE1_LOW1 recorded missing; every rule-following arm has exactly 1.00 TE per row.
    - **The rules off** (the package): all 26 books identical to 6p's package build; MIXT_QA0_NORR recorded missing.
  - **Code:** lab `16d7b8fc` (on 6p's `b03ddaac`):
    - `experiments/s38_paper_corun.py` sha256 `5ad07e994c2c105c6b646838b83fa4b13d6f275a8b8425cc0e4f45ae29e95609`;
    - `scripts/s38_score.py` `9f0feeb3a88789094886d0f3d1876ab817be536777f48a4b19457ae847d7e55d`;
    - `scripts/s38_report.py` `543de78117f688e134cedd9dc2f785f06d63ecfa143294357e4049d0d4d46386`;
    - `tests/test_s38_paper_corun.py` `4fb28242da70a2081c948542d9b04068cc3ee5f79af2a53b101b7f6612e1b601` (44 tests);
    - `scripts/s38_build.py` unchanged (`15373e14…`).
  - **The integrity gate** pins this module sha in place of 6p's `ecc55fa0…`, on the live snapshot; `s38-prod-pin` moves to the new
    FRIDAY_HEAD (the classification is re-checked there).
  - **Order:** this amendment; the laptop's ack; the pin and the gate.

- **Amendment 6r (2026-10-09, before Week 5's lock; no Week-5 outcome exists): his S1 and S2 on paper.**
  - **Why.** His request (HANDOFF `2be97397`): "Test both tonight for live". S2 (one $8,000+ RB / WR / TE per row) FAILED its gate on
    the laptop's W3 / W4 replay; S1 (shrink the projection toward the salary curve, k 0.7) failed his rule in study 92 (Addendum
    190: −4.4, worse on both draws). **Neither is live in Week 5**; both are measured on its real fields here.
  - **What changes.**
    - **Classification:** production's `--proj-shrink-k`, `--proj-shrink-window`, `--mix-min-star` and `--mix-star-salary`
      (the unmerged flag branch `b4934067`) are "checked", so a merge cannot make a week invalid. Accepted live states: the
      shrink off, or k 0.7 / window 500 on his armed version (the receipt's `shrink` record must agree on k and window); S2
      never live (any `--mix-min-star` is a mismatch; `--mix-star-salary` alone only at $8,000).
    - **MIXT_QA0_STAR1** (exploratory, S2 on paper): his live construction plus at least one RB / WR / TE priced $8,000+ per book
      row, added to the live row rules as ONE `set_constraints` list (an infeasible solve drops all of them, recorded).
    - **MIXT_QA0_SHRINK07** (exploratory, S1 on paper; built only while the live book is not shrunk): his live construction on
      the shrunk objective base (per skill position the median FP mean of the pool's same-position players within ± $500,
      himself included; proj' = typical + 0.7 × (proj − typical); DSTs unchanged).
    - **If S1 is ever live** (not in Week 5): every paper arm but TODAY and **MIXT_QA0_NOSHRINK** (the live book without the
      shrink, then the paired book) is built on the shrunk base.
    - The shrink and the star set are **study 92's frozen functions** (`s92_shrink_star.py` `7913aefc`), pasted byte for byte
      (tests pin the text: `shrink` `95ac8553…`, `star_set` `5fb6e7b2…`).
    - All read against MIXT_QA0, overall and per contest group (the reader's third 6r line per week).
  - **The smoke** (dry run on Week 4's frozen copies; the armed state = 6q's (the package + the row rules) with the laptop's
    receipts; production at FRIDAY_HEAD `f5f96468`; `~/private/paper-corun/smoke-w4-amend6r/`, script `run.sh` `bcb03a9e5ef2`, log `e8a25e6e63cb`;
    lab `90a3053c`; PYTHONHASHSEED=0):
    - 45 tests pass (rc 0).
    - **The armed state (the shrink off), Week 5's form:** mismatches none; **all 26 pre-6r arms identical to 6q's armed build**;
      MIXT_QA0_STAR1 built with a star in every row (1.038 per row against QA0's 0.769; 26 ruled, 0 re-solved; four stars in the
      W4 pool); MIXT_QA0_SHRINK07 built (the shrink moves a skill projection by 0.395 on average); MIXT_QA0_NOSHRINK missing.
    - **The shrink live** (the laptop's W4 armed + S1 receipt): mismatches none (the receipt agrees); **MIXT_QA0 is identical,
      rows and ranks, to the armed state's MIXT_QA0_SHRINK07**; **MIXT_QA0_NOSHRINK is identical to the armed state's MIXT_QA0**;
      TODAY identical; every arm shrunk except TODAY and NOSHRINK; SHRINK07 missing.
    - S2 live (`--mix-min-star 1`): the mismatch "S2 failed its gate: never live".
  - **Code:** lab `90a3053c` (on 6q's `16d7b8fc`):
    - `experiments/s38_paper_corun.py` sha256 `8ac576307b4d91a1892ddbe3d0508cbf2e55fb42764d41efd2e726bb2f56c11d`;
    - `scripts/s38_score.py` `f6e8585391ba0685c6c278a744f5be84c111b5d455e3081d89521f2840c77a9d`;
    - `scripts/s38_report.py` `87e45c9d27e34e9884dd79b55bacbc86e45b9e2401c8d9d1324567c14db043ef`;
    - `tests/test_s38_paper_corun.py` `c816a7fad3b56b4c7df2ef3c0835763a4ffe7910e91c2561565a05373be1b960` (45 tests);
    - `scripts/s38_build.py` unchanged (`15373e14…`).
  - **The integrity gate** pins this module sha in place of 6q's `5ad07e99…`, on the live snapshot (`s38-prod-pin` at FRIDAY_HEAD
    `f5f96468`; the classification there is clean).
  - **Order:** this amendment; the laptop's ack; the gate pin.

- **Amendment 6s (2026-10-09, before Week 5's lock; no Week-5 outcome exists): a low-ownership limit that can bind, on paper.**
  - **Why.** His question (in the outside reviewer's session; HANDOFF `7a47ecc3`): "is there anything in your log for things that
    seemed promising that we should still try?", and on the list "let's try each that you suggested". Item 1: study 91's LOW1 alone
    passed in the harness (+2.8, Addendum 188), but at 3% of FP's projections it barely binds on his real book (0.1–0.2 such
    players per row). Thresholds at which it binds are 5% and 8%. There is no FP ownership history, so no harness read exists:
    real weeks only.
  - **What changes.** Two exploratory paper arms on his live construction (every live setting as MIXT_QA0 follows it):
    - **MIXT_QA0_LOW5 / MIXT_QA0_LOW8:** at most one TE and at most one skill player under 5% / 8% FP projected ownership
      (6p's `low_owned` at that threshold; `fp_own_raw`; blank or unnamed = 0%) per book row, in place of the live 3% rule.
    - **The fallback:** a solve infeasible under the 5% / 8% rule is re-solved under the LIVE rules (te1 + the 3% rule), and only
      then with none, each recorded (`row_rules_or`, a new two-tier wrapper inside `own_caps`; `row_rules`' pinned text is
      unchanged). The first smoke showed why: at 8% four of 26 W4 solves were infeasible, and the one-list fallback had dropped
      the TE rule too.
    - Every arm records its low-owned players per row at 5% and 8%. Read against MIXT_QA0, overall and per contest group.
  - **The smoke** (dry run on Week 4's frozen copies, the armed state (the package + the row rules, the laptop's receipt);
    production at FRIDAY_HEAD `f5f96468`; `~/private/paper-corun/smoke-w4-amend6s/`, script `run.sh` `12cb4e15f7df`, log `5187960002fb`; lab
    `64d330d5`; PYTHONHASHSEED=0):
    - 47 tests pass (rc 0); mismatches none; **all 28 pre-6s arms identical to 6r's armed build**; the low sets hold 177 (5%)
      and 201 (8%) of 235 pool skill players (3%: 163).
    - **MIXT_QA0** (the live 3% rule): low-owned per row 0.23 (3%), 0.73 (5%), 1.69 (8%); FP per dealt lineup 140.79.
    - **MIXT_QA0_LOW5:** 0.42 under 5% per row; **8 of 26 rows change**; 26 ruled solves, 0 fallbacks; FP 140.82.
    - **MIXT_QA0_LOW8:** 1.23 under 8% per row (the limit is infeasible on 4 of 26 solves, which fall back to the live rules,
      keeping one TE per row); **17 of 26 rows change**; FP 140.71.
    - The first smoke (before the fallback tier; run.log kept as run-first.log) had LOW8's 4 infeasible solves drop the TE rule
      too (1.15 TEs per row); that is why the second tier exists.
  - **Code:** lab `64d330d5` (6s `4a00ffda` and the fallback `64d330d5`, on 6r's `90a3053c`):
    - `experiments/s38_paper_corun.py` sha256 `29f8c095d4704538162d160d8d514d8c9ac4d0e7528c6148b9edae5ea81ace5a`;
    - `scripts/s38_score.py` `d268f8f7b58a2950666c46d4ad7853bffa3dbf7ec6f3dcb4d3071304be396435`;
    - `scripts/s38_report.py` `c9353c16994c89b759e0eeb2238209a7ac1ca0e7c73ee13f67ee686cd1063b6e`;
    - `tests/test_s38_paper_corun.py` `312915abfa8806b8cd934f3c6545db0a069a6f906fc9515e672a2f50d03098e2` (47 tests);
    - `scripts/s38_build.py` unchanged (`15373e14…`).
  - **The integrity gate** pins this module sha in place of 6r's `8ac57630…`, on the live snapshot.
  - **Order:** this amendment; the laptop's ack; the gate pin.

- **Amendment 6t (2026-10-09, before Week 5's lock; no Week-5 outcome exists): study 93's ONECATCH, if it goes live, followed on paper.**
  - **Why.** His answer on study 93's lead (relayed by the laptop; HANDOFF `90e8470c`): "Live W5 if built in time
    (Recommended)". The rule allows at most one WR / TE of any team on the B / C book rows. The paper arms follow every live
    construction setting (6o, 6q, 6r), so this one must be classified, followed and paired too.
  - **What changes.**
    - **Classification:** the union argument `--mix-one-catcher-all` (production `c391fbd0`, the outside reviewer's flag,
      reviewed by the laptop and by 84) is classified checked. It is accepted only on the armed version, and is otherwise a
      parity mismatch (6l's default-deny is unchanged).
    - **The receipt must agree:** when the flag is declared, `config.union.mix.mix.one_catcher_source.applied` must equal the
      paper build's own state (applied iff the live row rules apply). When applied, the rule's identity must match: cells
      `["B", "C"]`, `max_per_team` 1. Anything else stops the build.
    - **When live and applied,** every rule-following arm carries the rule through `oc_tiers`. On a B / C book solve (spares
      never), one constraint per team (its WR / TE ids, at most 1) joins the constraint list. The tiers are one call each:
      [primary + oc] → [primary] → none. The low arms (6s) run [low-N + te1 + oc] → [live + oc] → [live] → none. These are
      study 93's `lead_rules` calls; a test executes 93's pinned text (`c5bcac30…`) and asserts identical optimize calls.
    - **Never:** MIXT_QA0_TODAY and MIXT_QA0_NORR, which stay off the live rules by design.
    - **MIXT_QA0_NOONECATCH** (exploratory): the armed live book without the rule, the paired paper book. It is built only
      while the rule is live. It is read against MIXT_QA0, overall and per contest group.
    - When the rule is not live, nothing changes. NOONECATCH is missing and every arm is identical to 6s's.
  - **The smoke** (dry run on Week 4's frozen copies; `~/private/paper-corun/smoke-w4-amend6t/`, script `run.sh` `5dfe08e05760`,
    log `f5caf81a6456`; lab `3de36327`; PYTHONHASHSEED=0). Production was the laptop's merge check `93d58464` (integration
    `90e8470c` + the flag `c391fbd0` + the wiring `f483644c`), and FRIDAY_HEAD `f5f96468` (no flag) for the first build. The
    rule-on build used the laptop's W4 ONECATCH check receipt
    (`~/rehearsals/flagcheck-onecatchALL-20261009T233318Z/on/receipt.json`, sha256 `e2b66fb94894…`).
    - 48 tests pass (rc 0); union-argument mismatches none in every build.
    - **The rule off:** all 30 arms are identical to 6s's armed build (rows + ranks), on `f5f96468` and on `93d58464` alike.
      NOONECATCH is missing.
    - **The rule on:** the receipt agrees (one_catcher_source applied; cells B / C, at most 1 per team; 14 ruled solves, 0
      re-solved without it, 0 B / C rows with a same-team pair); the paper build applies it.
      - **MIXT_QA0_NOONECATCH equals the rule-off MIXT_QA0** (rows + ranks). TODAY and NORR are unchanged.
      - Every other arm carries it on every B / C book solve (14; QB2HALF 7, its B / C rows). No B / C row holds two WR / TE of
        one team (MIXT_QA0: 5 such rows → 0). LOW8's 4 solves infeasible under its own rule fall to [live + oc], none further.
      - 27 arms change. MATCHUPX is unchanged: it had no such pair on W4, so the rule was slack there.
      - MIXT_QA0 keeps 7 of 26 rows; FP per dealt lineup 140.79 → 140.70. Production's own W4 check (the laptop's) changed 19
        of 26 rows, 5 pair rows → 0. The two come from different builders, so their rows are not compared.
    - **A missing receipt record:** with the flag declared and a receipt that carries no one-catcher record, a dry run builds
      (as 6o–6r's records do); the gate (not a dry run) refuses it ("the union receipt carries no one-catcher record"). This
      is from reading the code; the smoke ran this case dry only.
  - **Code:** lab `3de36327` (on 6s's `64d330d5`):
    - `experiments/s38_paper_corun.py` sha256 `b34b5468b184f0b913ddd8e44f86d1613f8da6b0a45adbe0f0cc0ea91a90bc6a`;
    - `scripts/s38_score.py` `d8c242956c5bf46837f362014f6de05d3d096cbe105ab8d5de11c0700b9b04a0`;
    - `scripts/s38_report.py` `2f3237eaccddea7d0ba2ac88f3830ad59c270039fbbc8267c61c2c99452c2d68`;
    - `tests/test_s38_paper_corun.py` `8628551a8ab8db01d3da0373c5ba9bf9d06897298fac4c0f666aef82fa600bb8` (48 tests);
    - `scripts/s38_build.py` unchanged (`15373e14…`).
  - **The integrity gate** pins this module sha in place of 6s's `29f8c095…`, on the live snapshot.
  - **Order:** this amendment; the laptop's ack; the gate pin. If the rule goes live, `s38-prod-pin` moves to the FRIDAY_HEAD that
    carries the flag: 6l's classification reads the union arguments of the `--prod` checkout, and `f5f96468`'s has no such argument.

- **Amendment 6u (2026-10-09, before Week 5's lock; no Week-5 outcome exists): study 94's RBMATE4, followed on paper whether or not it goes live.**
  - **Why.** His answer on study 94's lead (in the laptop's session; HANDOFF `ad00da5c`): "Try live W5 if built". The option
    text: "New code tonight, plus a test of it together with one receiver per team and the same checks as before. It goes
    live at Saturday's 10:28 arming only if all pass, otherwise paper." The paper arms follow every live construction setting
    (6o, 6q, 6r, 6t). So this rule must be classified, followed and paired if it goes live, and scored on paper if it does not.
  - **The rule.** On the first 4 C-cell book solves (QB + 1, no bring-back; by identity), the lineup must hold the QB and an
    RB of the QB's team: an interaction floor of 1 over study 94's (QB, own-team RB) pairs. A slot is used whether the floor
    holds or is dropped, and an ownership-cap re-solve takes another, as in studies 94 and 96. Study 94's `rb_pairs` is
    pasted byte for byte (text sha256 `5e961923…`, a test).
  - **What changes.**
    - **Classification:** the union argument `--mix-rb-mate-c` (production, the outside reviewer's flag) is classified
      checked. It is accepted only at 4 and only with `--mix-one-catcher-all` (production refuses it alone). Any other value
      is a parity mismatch.
    - **The receipt must agree:** when the flag is declared, `config.union.mix.mix.rb_mate_source.applied` must equal the paper
      build's own state (applied iff the one-catcher rule applies). When applied, the rule's identity must match: cell `C`,
      `rows_cap` 4. Anything else stops the build.
    - **The tiers** (`oc_tiers` with the floor; one call each): on an RBMATE4 slot, [rules + one-catcher] with the floor FIRST,
      then 6t's tiers ([rules + one-catcher] → [rules] → none; the low arms [low-N + te1 + one-catcher] → [live + one-catcher]
      → [live] → none). This is study 96's combined order (the floor dropped first, then the one-catcher rule, then the
      rules). The floor tier is recorded as tier −1, so 6t's tier numbers are unchanged. Without the floor, `oc_tiers` makes
      6t's calls exactly (a test).
    - **When live and applied:** every arm that carries the live one-catcher rule carries RBMATE4 too.
      **MIXT_QA0_NORBMATE** (exploratory) is the armed live book without RBMATE4 (the one-catcher rule kept), the paired
      paper book, built only while RBMATE4 is live.
    - **When not live** (and the one-catcher rule is live): **MIXT_QA0_RBMATE** (exploratory) is RBMATE4 on paper on top of
      the live book. Every other arm is unchanged.
    - **Never:** NOONECATCH (production refuses RBMATE4 without the one-catcher rule), TODAY and NORR.
    - Every arm records its book rows holding a (QB, own-team RB) pair. NORBMATE / RBMATE are read against MIXT_QA0, overall
      and per contest group.
  - **The first smoke** (dry run on Week 4's frozen copies; `~/private/paper-corun/smoke-w4-amend6u/`, script `run.sh`
    `7328adf1bf73`, log `27b709fa4e22`; lab `f798548a`; production FRIDAY_HEAD `462ba341` (no RBMATE4 flag); PYTHONHASHSEED=0;
    the laptop's W4 ONECATCH receipt `e2b66fb94894…`):
    - 49 tests pass (rc 0); union-argument mismatches none in both builds.
    - **RBMATE4 not live (the armed state today):** all 31 arms identical to 6t's armed build (rows + ranks).
      **MIXT_QA0_RBMATE**: 4 slots, 4 floors held, 0 dropped; QB + own-RB rows 4 → 6 of 26; 6 of 26 rows shared with MIXT_QA0;
      0 B / C rows with a same-team receiver pair; FP per dealt lineup 140.70 → 140.69. NORBMATE missing (as designed).
    - **RBMATE4 live** (`--mix-rb-mate-c 4` added; a dry run, so the ONECATCH receipt without an RBMATE4 record is tolerated):
      **MIXT_QA0 equals the not-live build's MIXT_QA0_RBMATE, and MIXT_QA0_NORBMATE equals its MIXT_QA0** (rows + ranks);
      TODAY, NORR and NOONECATCH are unchanged; 28 arms carry it (4 slots each; QB2HALF 3, its C rows); RBMATE missing.
  - **The parity with study 96** (lab `3b74eaa5`): `oc_tiers` takes study 96's slot rule exactly, so an empty pair set still
    takes the slots and makes the first call without the floor, as `combo_rules` does. A test executes study 96's
    `combo_rules` text (`66ed0eff…`, nfl2 `3cf3e8eb`) against `oc_tiers` and asserts identical optimize calls and slot records
    in five cases: the floor holding; the floor dropped; a whole-tier re-solve of the same row (a second slot); no pair; and a
    dropped floor before a fifth C solve. Three mutations are caught. 50 tests pass.
  - **The final smoke** (dry run on Week 4's frozen copies; `~/private/paper-corun/smoke-w4-amend6uv/`, script `run.sh`
    `69a121cc4cc5`, log `76ce1a6c068b`; lab `6e67ea55` (6u with 6v); production = the laptop's merge check `5c66f156`, which carries
    the flag; PYTHONHASHSEED=0; the laptop's W4 RBMATE4 check receipt
    `~/rehearsals/flagcheck-rbmateC4-20261010T010937Z/on/receipt.json`, sha256 `9cd0e39cb77d…`):
    - 51 tests pass (rc 0); union-argument mismatches none in all three builds.
    - **RBMATE4 not live:** all 32 arms identical to the first smoke's (31 identical to 6t's armed build).
    - **RBMATE4 live, with the real receipt:** the receipt agrees (rb_mate_source applied; cell C, rows_cap 4; 59 pairs; 4 slots,
      4 ruled, 0 re-solved without it). **MIXT_QA0 equals the not-live MIXT_QA0_RBMATE, and MIXT_QA0_NORBMATE equals the not-live
      MIXT_QA0** (rows + ranks). TODAY, NORR and NOONECATCH are unchanged; 28 arms carry it.
  - **Week 5:** study 96 read PAPER ONLY (Addendum 193), and his night rules (HANDOFF `543f2695`) keep RB_MATE_C at 0 until his
    morning word. So in Week 5 MIXT_QA0_RBMATE is the expected arm: RBMATE4 on paper beside his book.
  - **Code:** lab `3b74eaa5` (`f798548a` and `3b74eaa5`, on 6t's `3de36327`):
    - `experiments/s38_paper_corun.py` sha256 `183f7dcf227f9b1b9531489318a63174130c95d6e37225f5cb4931429fbc72f7`;
    - `scripts/s38_score.py` `4f3bdaa3972a08cdcb8d742f912a611ad1005b9cd6e179501c74dd2cc470a981`;
    - `scripts/s38_report.py` `2aa06f4f40156119564b09557910a8e8a0d22e0d0fe6457fbb9d8931f0ddc7fc`;
    - `tests/test_s38_paper_corun.py` `b2313f06dce3085f1a3bf864ccc0378cf1b1967fb82a68fa5e56704eaabbc71c` (50 tests);
    - `scripts/s38_build.py` unchanged (`15373e14…`).
  - **The integrity gate** pins the module of amendment 6v below (6u and 6v ship together). If RBMATE4 goes live,
    `s38-prod-pin` moves to the FRIDAY_HEAD that carries its flag.
- **Amendment 6v (2026-10-09, before Week 5's lock; no Week-5 outcome exists): the paper arms follow live cell quotas with a shape at 0.**
  - **Why.** His night rules (HANDOFF `543f2695`): he decides the shape percentages in the morning from study 95, whose rule
    (`92108ea0`) can suggest dropping a shape. Production's `--mix-cell-quotas` now takes a cell at 0 (the laptop's
    production/cell-quotas-zero-20261009 @ `21fa9d29`, parser only; reviewed by 84). 6j's `live_quotas` refused any value ≤ 0,
    so a dropped shape would have been a parity mismatch and stopped the paper build.
  - **What changes.** `live_quotas` takes production's rule: exactly the four MIX cells, every value ≥ 0, at least one > 0, the
    sum 1 within 1e-9. A cell at 0 gets no rows in either block and stays a cell; a failed cell's quota still passes to A1, as
    the live book and study 95's NO_x arms do. Every fill path (mix_fill, term_book, the half book) takes its targets from
    study 18's `allocate` / `interleave` over `S28.QUOTAS`. These are the functions production's `mix_shapes` uses: the bodies
    are identical, only the docstrings differ. Nothing else changes. MIXT_QA0_QB2HALF keeps its own fixed quotas.
  - **Tests:** 6j's test moves the zero spec to valid and adds all-zero, negative and NaN specs as invalid. A new test follows
    zero and one-cell specs and reproduces study 95's census counts per cell from `allocate` per block (live 18 + cheap 8):
    NO_A1 0 / 6 / 10 / 10, NO_A2 9 / 0 / 9 / 8, NO_B 10 / 6 / 0 / 10, NO_C 10 / 6 / 10 / 0. The laptop's production W4 builds at
    those quotas gave the same counts (~/rehearsals/quotacheck-20261010T011001Z).
  - **The smoke** (the same run as 6u's final smoke, its third build: `--mix-cell-quotas` at study 95's NO_A2 floats
    `A1=0.3488372093023256,A2=0.0,B=0.32558139534883723,C=0.32558139534883723`): mismatches none; **no quota-following arm holds
    an A2 row**; MIXT_QA0's cells A1 9 / B 9 / C 8 (the known answer 9 / 0 / 9 / 8); MIXT_QA0_QB2HALF (its own quotas) identical
    to the armed build.
  - **Code:** lab `6e67ea55` (on 6u's `3b74eaa5`): `experiments/s38_paper_corun.py` sha256 `0656a38e6cf3556c09c4f50ee9ba37f814b3132de33431ff44a41ce7b6845ada`;
    `tests/test_s38_paper_corun.py` `6ade15bd9304273996c43caf60a1f7e2cef27b61b2400417616040b019a5e529` (51 tests); `scripts/s38_score.py`, `scripts/s38_report.py` and
    `scripts/s38_build.py` unchanged.
  - **The integrity gate** pins this module sha (`0656a38e…`) in place of 6t's `b34b5468…`, on the live snapshot. **Order:**
    6u and 6v; the laptop's ack; the gate pin.

- **Amendment 6w (2026-10-10, before Week 5's lock; no Week-5 outcome exists): the RB mate's game-script scope (FAVHI), and the
  A1 full-stack switch classified.**
  - **Why.** Study 97's pre-fixed situation rule picked RBMATE4_FAVHI -- the RB mate only for the expected winner of a high-total
    game (Addendum 195) -- and study 99 confirmed it on a fresh draw (Addendum 197). Production built `--mix-rb-mate-scope favhi`
    (review/game-script-scopes @ `60f6dbe9`, default all; the laptop's wiring and Week-4 check), off until his morning word (his
    night rules, HANDOFF `543f2695`). The paper arms follow every live construction setting, so the scope must be classified and
    followed; and production's prepared `--mix-a1-full-stack` (study 102's TAIL_STACK8, review/a1-full-stack @ `6d4c0457`,
    store_true, default off) must be classified before any default-off merge, or 6l's default-deny would stop the build.
  - **What changes.**
    - `--mix-rb-mate-scope` is classified checked: all or favhi, favhi only with `--mix-rb-mate-c 4`; anything else is a parity
      mismatch.
    - Study 97's `scenarios` and `rm_pairs_for` are pasted byte for byte (texts `938032a8…` / `fb2142c7…`, the ones production's
      test pins; a test). The FAVHI pairs are `rm_pairs_for("RBMATE4_FAVHI", …)` on the paper pool.
    - **A live favhi scope:** every arm that carries the live RB mate uses the FAVHI pairs. The scope is refused -- the RB mate
      OFF -- exactly when production refuses it (the frame lacks the lines, or no FAVHI team has both a QB and an RB in the pool).
      The receipt must agree: `rb_mate.scope` and `rb_mate.qb_teams` (== the paper's FAVHI teams).
    - **MIXT_QA0_RBMATE_FAVHI** (exploratory): the FAVHI RB mate on paper, built while the live scope is not favhi (with the
      one-catcher rule live). MIXT_QA0_RBMATE (every pair) stays on paper unless the live scope is all. NORBMATE pairs with the
      live RB mate of either scope.
    - `--mix-a1-full-stack` is classified NOT_BUILT (off = absent; ASSUMED_DEFAULTS False). The paper arms follow it only by a
      later amendment, if study 102 picks it and study 103 holds.
  - **The smoke** (dry run on Week 4's frozen copies; `~/private/paper-corun/smoke-w4-amend6w/`, script `run.sh` `2d276265b59e`, log
    `a28741038fd3`; lab `2f102325`; production = the laptop's merge check `de1a7700`, which carries the scope flag; PYTHONHASHSEED=0;
    the laptop's three Week-4 receipts: ONECATCH `e2b66fb9…`, RB mate (all) `9cd0e39c…`, RB mate (favhi) `80cf84f1…`):
    - 52 tests pass (rc 0); union-argument mismatches none in all three builds.
    - **RB mate not live:** all 32 earlier arms identical to 6u / 6v's smoke; MIXT_QA0_RBMATE_FAVHI built: the FAVHI teams BUF /
      HOU / SF (8 pairs, the same teams as production's receipt), 4 of 4 slots ruled; QB + own-RB rows 4 → 7.
    - **Live favhi, with the real receipt:** the receipt agrees (applied; scope favhi; qb_teams BUF / HOU / SF). **MIXT_QA0 equals
      the not-live MIXT_QA0_RBMATE_FAVHI; MIXT_QA0_NORBMATE equals the not-live MIXT_QA0; MIXT_QA0_RBMATE (every pair) equals the
      not-live one** (rows + ranks); TODAY, NORR and NOONECATCH are unchanged; RBMATE_FAVHI missing as designed.
    - **Live all:** all 32 arms identical to 6u / 6v's live build; MIXT_QA0_RBMATE_FAVHI on paper equals the not-live one.
  - **Code:** lab `2f102325` (`3ac7febf` and `2f102325`, on 6v's `6e67ea55`):
    - `experiments/s38_paper_corun.py` sha256 `e7038cbaa01e91778c2dbbf18e215d99ec5e7bbd70b09118f84dd5527b8b7865`;
    - `scripts/s38_score.py` `165185033d8e39d8f4df36da30b9e669708f6a314631954c5ec2d367a1c3c3bf`;
    - `scripts/s38_report.py` `afa55d5a1e578d375da78a8115525e6d2fd74c8a561aa132c3aa34ad9268daec`;
    - `tests/test_s38_paper_corun.py` `79176ac4935c6823e8241e2e916f223b68bf2f977413314c1d39fe67d370a008` (52 tests);
    - `scripts/s38_build.py` unchanged (`15373e14…`).
  - **The integrity gate** pins this module sha (`e7038cba…`) in place of 6v's `0656a38e…`, on the live snapshot. If the scope
    flag merges into FRIDAY_HEAD, `s38-prod-pin` moves there and the gate is re-run.
  - **Order:** this amendment; the laptop's ack; the gate pin; then the flags' default-off merge.

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
