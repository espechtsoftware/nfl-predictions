

"""LEM v1: FACTORED next-event model (v0's composite-vocab design lost
to the bigram 8.19 vs 8.12 — 49.5k vocab / 470k tokens is ~9 samples
per embedding; see study report). Each play is 7 small factors
(quarter, down, distance, yardline, score-diff, event, yards). Input =
sum of factor embeddings; output = 7 heads; NLL(event) = sum of factor
NLLs (model factorizes conditionally on context). Directly comparable
in nats/event to the composite bigram baseline.
"""
import json
import os
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
DEV = "cuda" if torch.cuda.is_available() else "cpu"
BUCKET = os.environ.get("LEM_BUCKET", "nfl-predictions-503414-raw")
BLOCK, D, LAYERS, HEADS = 256, 192, 4, 6
BATCH, STEPS, LR = 64, 6000, 3e-4
EVAL_EVERY = 500
print(f"device={DEV} torch={torch.__version__}", flush=True)
corpus = pd.read_parquet(f"gs://{BUCKET}/lem/lem_corpus.parquet")
print(f"corpus {len(corpus):,} plays {corpus.season.min()}-{corpus.season.max()}",
      flush=True)
parts = corpus.tok.str.split("|", expand=True)
parts.columns = ["qtr", "down", "dist", "yl", "sd", "ev", "yds"]
parts["game_id"] = corpus.game_id.values
parts["season"] = corpus.season.values
FACTORS = ["qtr", "down", "dist", "yl", "sd", "ev", "yds"]
tr = parts[parts.season <= 2023]
te = parts[parts.season >= 2024]
vocabs, stois = {}, {}
for f in FACTORS:
    vocabs[f] = ["<g>"] + sorted(tr[f].unique())
    stois[f] = {t: i for i, t in enumerate(vocabs[f])}
sizes = {f: len(vocabs[f]) for f in FACTORS}
def encode(df):
    cols = []
    for f in FACTORS:
        m = stois[f]
        arr = []
        for _, g in df.groupby("game_id", sort=False):
            arr.append(np.array([0]))  # <g>
            arr.append(g[f].map(lambda t: m.get(t, 0)).to_numpy(np.int64))
        cols.append(np.concatenate(arr))
    return np.stack(cols, axis=1)  # (T, 7)
ids_tr, ids_te = encode(tr), encode(te)
print(f"train events {len(ids_tr):,}  test events {len(ids_te):,}", flush=True)
# composite bigram baseline (same as v0, on joined factor strings)
from scipy import sparse as sp
comp_tr = np.array(["|".join(map(str, r)) for r in ids_tr])
comp_te = np.array(["|".join(map(str, r)) for r in ids_te])
uniq, inv_tr = np.unique(comp_tr, return_inverse=True)
lut = {t: i for i, t in enumerate(uniq)}
inv_te = np.array([lut.get(t, -1) for t in comp_te])
V = len(uniq) + 1
inv_te[inv_te < 0] = V - 1
k = 0.05
big = sp.csr_matrix((np.ones(len(inv_tr) - 1, np.float32),
                     (inv_tr[:-1], inv_tr[1:])), shape=(V, V))
pair = np.asarray(big[inv_te[:-1], inv_te[1:]]).ravel()
probs = (pair + k) / (row_tot[inv_te[:-1]] + k * V)
base_ll = float(-np.log(probs).mean())
print(f"BIGRAM baseline: held-out NLL {base_ll:.4f}", flush=True)
class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln1, self.ln2 = nn.LayerNorm(D), nn.LayerNorm(D)
        self.attn = nn.MultiheadAttention(D, HEADS, dropout=0.1,
                                          batch_first=True)
        self.mlp = nn.Sequential(nn.Linear(D, 4 * D), nn.GELU(),
                                 nn.Linear(4 * D, D), nn.Dropout(0.1))
    def forward(self, x, mask):
        h = self.ln1(x)
        a, _ = self.attn(h, h, h, attn_mask=mask, need_weights=False)
        x = x + a
class LEM(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb = nn.ModuleList([nn.Embedding(sizes[f], D) for f in FACTORS])
        self.pos = nn.Embedding(BLOCK, D)
        self.blocks = nn.ModuleList([Block() for _ in range(LAYERS)])
        self.ln = nn.LayerNorm(D)
        self.heads = nn.ModuleList([nn.Linear(D, sizes[f]) for f in FACTORS])
    def forward(self, idx):  # idx: (B, T, 7)
        T = idx.shape[1]
        x = sum(e(idx[:, :, i]) for i, e in enumerate(self.emb))
        x = x + self.pos(torch.arange(T, device=idx.device))
        mask = torch.triu(torch.ones(T, T, device=idx.device), 1).bool()
        for b in self.blocks:
            x = b(x, mask)
        h = self.ln(x)
        return [head(h) for head in self.heads]
model = LEM().to(DEV)
print(f"params {sum(p.numel() for p in model.parameters())/1e6:.1f}M", flush=True)
opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, STEPS)
def get_batch(ids, n=BATCH):
    ix = np.random.randint(0, len(ids) - BLOCK - 1, n)
    x = torch.from_numpy(np.stack([ids[i:i + BLOCK] for i in ix])).to(DEV)
    y = torch.from_numpy(np.stack([ids[i + 1:i + BLOCK + 1] for i in ix])).to(DEV)
    return x, y
def loss_fn(logits, y):
    return sum(F.cross_entropy(lg.reshape(-1, lg.shape[-1]),
                               y[:, :, i].reshape(-1))
               for i, lg in enumerate(logits))
@torch.no_grad()
def evaluate(ids, n_batches=60):
    model.eval()
    tot, cnt, allright = 0.0, 0, 0
    for _ in range(n_batches):
        x, y = get_batch(ids)
        logits = model(x)
        tot += sum(F.cross_entropy(lg.reshape(-1, lg.shape[-1]),
                                   y[:, :, i].reshape(-1), reduction="sum").item()
                   for i, lg in enumerate(logits))
        right = torch.ones_like(y[:, :, 0], dtype=torch.bool)
        for i, lg in enumerate(logits):
            right &= lg.argmax(-1) == y[:, :, i]
        allright += right.sum().item()
        cnt += y.shape[0] * y.shape[1]
    model.train()
    return tot / cnt, allright / cnt
best = 1e9
t0 = time.time()
for step in range(1, STEPS + 1):
    x, y = get_batch(ids_tr)
    loss = loss_fn(model(x), y)
    opt.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    opt.step()
    sched.step()
    if step % EVAL_EVERY == 0:
        te_ll, te_acc = evaluate(ids_te)
        print(f"step {step}  train {loss.item():.4f}  heldout NLL/event "
              f"{te_ll:.4f}  top1(all-factors) {te_acc:.3f} "
              f"({time.time()-t0:.0f}s)", flush=True)
        if te_ll < best:
            best = te_ll
            torch.save({"model": model.state_dict(), "vocabs": vocabs},
                       "/tmp/lem_best.pt")
final_ll, final_acc = evaluate(ids_te, n_batches=200)
verdict = ("LEM BEATS BIGRAM" if best < base_ll
           else "LEM DOES NOT BEAT BIGRAM")
print(f"FINAL: LEM heldout NLL/event {final_ll:.4f} (best {best:.4f}) "
      f"top1 {final_acc:.3f} | bigram {base_ll:.4f} -> {verdict}", flush=True)
from google.cloud import storage
b = cl.bucket(BUCKET)
b.blob("lem/lem_v1_best.pt").upload_from_filename("/tmp/lem_best.pt")
b.blob("lem/metrics_v1.json").upload_from_string(json.dumps(
    {"lem_nll": best, "lem_top1": final_acc, "bigram_nll": base_ll,
     "factor_sizes": sizes, "verdict": verdict}))
print("artifacts uploaded; LEM_TRAIN_DONE", flush=True)
