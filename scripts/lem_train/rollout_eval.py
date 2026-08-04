"""LEM rollout-realism gate (the pre-registered next hurdle after v1
beat the bigram — study report Addendum 46/50 road map).

Loads the v1 checkpoint from GCS, autoregressively generates full games,
and compares against held-out 2024-25 actuals on the statistics a game
engine must reproduce before it can feed the sim:
  - plays per game
  - offensive TDs per game (ev == touchdown tokens)
  - FG attempts per game (field_goal tokens)
  - turnovers per game
  - punt share of drives
Pass bar (pre-registered): every statistic's generated mean within 10%
of held-out actual AND generated std within 25%. Prints PASS/FAIL per
stat; the gate result decides whether GAME_SIM_MODE=lem integration
work begins (September).

Runs on the lem-train GPU job image:
  gcloud run jobs deploy lem-rollout --image .../lem-train:latest \
    --command python --args /app/rollout_eval.py ... (see README)
"""
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

DEV = "cuda" if torch.cuda.is_available() else "cpu"
BUCKET = os.environ.get("LEM_BUCKET", "nfl-predictions-503414-raw")
BLOCK, D, LAYERS, HEADS = 256, 192, 4, 6
N_GAMES = int(os.environ.get("LEM_ROLLOUT_GAMES", "400"))
FACTORS = ["qtr", "down", "dist", "yl", "sd", "ev", "yds"]

corpus = pd.read_parquet(f"gs://{BUCKET}/lem/lem_corpus.parquet")
parts = corpus.tok.str.split("|", expand=True)
parts.columns = FACTORS
parts["game_id"] = corpus.game_id.values
parts["season"] = corpus.season.values
held = parts[parts.season >= 2024]

from google.cloud import storage

cl = storage.Client()
cl.bucket(BUCKET).blob("lem/lem_v1_best.pt").download_to_filename("/tmp/lem.pt")
ckpt = torch.load("/tmp/lem.pt", map_location=DEV, weights_only=False)
vocabs = ckpt["vocabs"]
sizes = {f: len(vocabs[f]) for f in FACTORS}
stois = {f: {t: i for i, t in enumerate(vocabs[f])} for f in FACTORS}


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
        return x + self.mlp(self.ln2(x))


class LEM(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb = nn.ModuleList([nn.Embedding(sizes[f], D) for f in FACTORS])
        self.pos = nn.Embedding(BLOCK, D)
        self.blocks = nn.ModuleList([Block() for _ in range(LAYERS)])
        self.ln = nn.LayerNorm(D)
        self.heads = nn.ModuleList([nn.Linear(D, sizes[f]) for f in FACTORS])

    def forward(self, idx):
        T = idx.shape[1]
        x = sum(e(idx[:, :, i]) for i, e in enumerate(self.emb))
        x = x + self.pos(torch.arange(T, device=idx.device))
        mask = torch.triu(torch.ones(T, T, device=idx.device), 1).bool()
        for b in self.blocks:
            x = b(x, mask)
        h = self.ln(x)
        return [head(h) for head in self.heads]


model = LEM().to(DEV)
model.load_state_dict(ckpt["model"])
model.eval()
print(f"checkpoint loaded on {DEV}; rolling out {N_GAMES} games", flush=True)


@torch.no_grad()
def rollout(n_games, max_plays=180, temp=1.0, batch=50):
    games = []
    for start in range(0, n_games, batch):
        b = min(batch, n_games - start)
        seq = torch.zeros((b, 1, len(FACTORS)), dtype=torch.long, device=DEV)
        done = np.zeros(b, dtype=bool)
        plays = [[] for _ in range(b)]
        for _ in range(max_plays):
            ctx = seq[:, -BLOCK:, :]
            logits = model(ctx)
            nxt = []
            for i, lg in enumerate(logits):
                probs = torch.softmax(lg[:, -1, :] / temp, dim=-1)
                nxt.append(torch.multinomial(probs, 1).squeeze(1))
            step = torch.stack(nxt, dim=1)  # (b, 7)
            seq = torch.cat([seq, step.unsqueeze(1)], dim=1)
            qtr = step[:, 0].cpu().numpy()
            for i in range(b):
                if not done[i]:
                    # qtr factor index 0 is <g>; a sampled <g> = game end
                    if qtr[i] == 0 and len(plays[i]) > 40:
                        done[i] = True
                    else:
                        plays[i].append([int(x) for x in step[i].cpu()])
            if done.all():
                break
        games.extend(plays)
    return games


def stats(frames_or_games, from_tokens):
    out = {}
    if from_tokens:
        ev_vocab = vocabs["ev"]
        per_game = []
        for g in frames_or_games:
            evs = [ev_vocab[p[FACTORS.index("ev")]] for p in g]
            per_game.append({
                "plays": len(g),
                "tds": sum(e == "touchdown" for e in evs),
                "fgs": sum(e == "field_goal" for e in evs),
                "tos": sum(e == "turnover" for e in evs),
                "punts": sum(e == "punt" for e in evs),
            })
        d = pd.DataFrame(per_game)
    else:
        g = frames_or_games.groupby("game_id")
        d = pd.DataFrame({
            "plays": g.size(),
            "tds": g.ev.apply(lambda s: (s == "touchdown").sum()),
            "fgs": g.ev.apply(lambda s: (s == "field_goal").sum()),
            "tos": g.ev.apply(lambda s: (s == "turnover").sum()),
            "punts": g.ev.apply(lambda s: (s == "punt").sum()),
        })
    for c in ("plays", "tds", "fgs", "tos", "punts"):
        out[c] = (float(d[c].mean()), float(d[c].std()))
    return out


gen = rollout(N_GAMES)
gs, hs = stats(gen, True), stats(held, False)
print(f"\n{'stat':7s} {'gen mean':>9s} {'act mean':>9s} {'gen sd':>7s} "
      f"{'act sd':>7s}  verdict")
n_pass = 0
for c in gs:
    gm, gsd = gs[c]
    am, asd = hs[c]
    ok = abs(gm - am) / max(am, 1e-6) < 0.10 and \
         abs(gsd - asd) / max(asd, 1e-6) < 0.25
    n_pass += ok
    print(f"{c:7s} {gm:9.2f} {am:9.2f} {gsd:7.2f} {asd:7.2f}  "
          f"{'PASS' if ok else 'FAIL'}", flush=True)
print(f"\nROLLOUT GATE: {n_pass}/5 stats pass -> "
      f"{'GATE PASSED' if n_pass == 5 else 'GATE FAILED'}; LEM_ROLLOUT_DONE",
      flush=True)
