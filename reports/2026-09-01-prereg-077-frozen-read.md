# PREREG-077 frozen read and independent reproduction

**Date:** 2026-09-01
**Disposition:** `PASS` under the frozen PREREG-047 contract; no successor
experiment released

## Exact cohort and reader

The complete three-bank cohort was read with the frozen reader invocation:

```bash
.venv/bin/python scripts/prereg047_report.py \
  077b490r1-20260901T134449Z \
  077b491r1-20260901T134715Z \
  077b492r1-20260901T143944Z
```

The run prefixes correspond to banks 490, 491, and 492 and executions
`lab-run-lfmw7`, `lab-run-vwnnk`, and `lab-run-wnd8r`. All 54 expected result
objects were present. The final execution, `lab-run-wnd8r` (UID
`4d898fda-ef61-4da6-b16e-e644a4db156e`), completed 18/18 tasks at
`2026-09-01T15:35:42.213382Z` with no failed, cancelled, or retried task.

The frozen identities were:

- reader SHA-256:
  `473bd70526dfee54e7e05a9ff61566ae30f5095c04fb3a9025052547dad107c4`;
- loader SHA-256:
  `e6c293e1d83edd11e666bab6b03091a62e9e0100b89e21cff1e59fcb7b60461e`;
- runtime source commit: `231582afb10720992437f1925518106c1c9f24ed`;
- immutable image:
  `sha256:a1bbcae3d89b18c4199d118a8b067af8b71382ddff5147435c17d3aa53003006`;
- benchmark identity: version `v1`, hash `04710846d67fb6c6`.

## Frozen result

The primary D800_DEMAX minus D400_DEMAX contrast at K=80 was **+1.216
points**, with 95% interval **[+0.467, +1.965]**. The three bank estimates
were +1.857, +0.510, and +1.281; W/L/T was 39/30/3 and every leave-one-slate-
out estimate was positive. Mean weekly maximum moved from **180.241 to
181.456** and median weekly maximum from 180.507 to 182.463.

The threshold counts averaged over banks were:

| Threshold | D400_DEMAX | D800_DEMAX |
|---:|---:|---:|
| >=187 | 25 | 27 |
| >=194 | 16 | 16 |
| >=200 | 9 | 13 |
| >=210 | 2 | 3 |
| >=220 | 1 | 1 |
| >=230 | 1 | 0 |
| >=240 | 0 | 0 |

This is therefore evidence of a positive average-max and 200+ retention gain,
not a monotone improvement at every tail threshold and not evidence of a
230+ improvement.

The fixed-delivered-unique count-matched reference was null versus D400_DEMAX:
**+0.064 [-0.576, +0.704]**, with bank disagreement. Natural unique-pool size
rose from approximately 399.8 to 799.2 and every D400 pool was nested in its
D800 counterpart. The pool oracle rose from **188.71 to 194.50**, while a
random 400-of-800 reference reached 189.38. This leaves material retrieval
headroom, but it does not authorize post-read selector tuning on these worlds.

The D800 minus D400 prefix deltas at K=10/20/30/40 were
-0.360/+0.439/-0.094/+1.190. Approximate per-slate-bank runtime rose from 160
seconds to 386 seconds.

## Independent reproduction

Production independently reproduced the read from a Git archive of the exact
reader-introduction commit
`79fbb52f613d41e8aa72b9aa09778eda40bd1fd3`. The isolated loader bytes and
reader hash were asserted before reading. The lab repeat and isolated
production transcript were byte-identical: each was 2,194 bytes with SHA-256
`89cfb2bcc64645c734b726303f7d2ea3ad04a0d0cf651505d21ebfebdf35e40a`.

A read-only identity census covered all 54 generation-pinned result objects.
Its canonical manifest was 22,473 bytes with SHA-256
`0eb65af58a1a34d479e261aaa064f0159798147096e82215598a0fe9b964220c`.
The bank object counts, total bytes, and identity-list hashes were:

- bank 490: 18 objects, 5,644,431 bytes,
  `494a708b6cab57faea45c141cae8f467dab8e15c4d26f66db0e956541570c5ae`;
- bank 491: 18 objects, 5,646,103 bytes,
  `223ade2628f11c9f57cb3779e530579369401f314382deb34dfa4c3e0fb01c44`;
- bank 492: 18 objects, 5,644,038 bytes,
  `6c2a12a87b9ce9bdcee9e17b910344595af19585ba619a3e0c9ccc6c2c3b6a7b`.

No tracked code or frozen artifact changed during either read. No cloud job was
launched. PREREG-080, PREREG-081, and PREREG-082 remain held on winner-registry
v2 adjudication, and this result does not release them.
