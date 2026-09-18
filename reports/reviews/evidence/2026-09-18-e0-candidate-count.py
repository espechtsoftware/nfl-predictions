"""E0b standalone synthetic candidate-count study; no NFL inputs."""
import hashlib
import itertools
import json
import os
import platform
import subprocess
import time
from pathlib import Path
import numpy as np

START = time.monotonic()
COUNTS = (12, 100, 1000, 3200, 12560)
OUT = Path('reports/reviews/evidence/2026-09-18-e0-candidate-count-results.json')
assert not OUT.exists(), 'Refuse to overwrite an existing run'
generator = np.random.Generator(np.random.PCG64(2026091801))
coeff = generator.standard_normal((12560, 6))
offsets = generator.uniform(-5., 5., 12560)
states = np.array(list(itertools.product((0, 1), repeat=6)), dtype=float)
rows = []
for law, p in enumerate((.5, .1)):
    weights = np.prod(np.where(states == 1, p, 1-p), axis=1)
    assert abs(weights.sum()-1) < 1e-12
    x = (states-p)/np.sqrt(p*(1-p))
    random_part = (18/np.sqrt(6))*coeff @ x.T
    random_part -= (random_part @ weights)[:, None]
    base_scores = 160+random_part
    assert np.allclose(base_scores @ weights, 160, atol=1e-10, rtol=0)
    decision_weights, audit_weights = [], []
    for replicate in range(100):
        streams = []
        for stream in (0, 1):
            seed = np.random.SeedSequence([2026091802, law, replicate, stream])
            rng = np.random.Generator(np.random.PCG64(seed))
            streams.append(rng.multinomial(10000, weights)/10000)
        decision_weights.append(streams[0]); audit_weights.append(streams[1])
    decision_weights = np.array(decision_weights)
    audit_weights = np.array(audit_weights)
    decision_base = base_scores @ decision_weights.T
    audit_base = base_scores @ audit_weights.T
    for arm in ('FLAT', 'GAPS'):
        shift = np.zeros(12560) if arm == 'FLAT' else offsets
        truth = 160+shift
        previous = np.full(100, -np.inf)
        for count in COUNTS:
            best_truth = float(np.max(truth[:count]))
            empirical = decision_base[:count]+shift[:count, None]
            selected = np.argmax(empirical >= empirical.max(axis=0)[None, :]-1e-12, axis=0)
            for rep, selected_id in enumerate(selected):
                if time.monotonic()-START > 300:
                    raise TimeoutError('Five-minute cap exceeded; incomplete run')
                i = int(selected_id)
                dec = float(decision_base[i, rep]+shift[i])
                aud = float(audit_base[i, rep]+shift[i])
                exact = float(truth[i])
                regret = best_truth-exact
                assert regret >= -1e-10 and dec+1e-10 >= previous[rep]
                previous[rep] = dec
                if arm == 'FLAT':
                    assert abs(regret) < 1e-10
                # Separate scalar sum check for all reported selections, using original score rows.
                direct_dec = sum(float(v)*float(w) for v, w in zip(base_scores[i]+shift[i], decision_weights[rep]))
                direct_aud = sum(float(v)*float(w) for v, w in zip(base_scores[i]+shift[i], audit_weights[rep]))
                assert abs(dec-direct_dec) < 1e-9 and abs(aud-direct_aud) < 1e-9
                rows.append(dict(law=law, arm=arm, candidates=count, replicate=rep, selected=i,
                    true_mean=exact, prefix_best_true=best_truth, regret=regret,
                    decision=dec, audit=aud, optimism=dec-exact, audit_error=aud-exact,
                    fixed_candidate_decision_error=float(decision_base[0,rep]-160),
                    fixed_candidate_audit_error=float(audit_base[0,rep]-160)))

def describe(values):
    a = np.array(values)
    return dict(n=len(a), mean=float(a.mean()), median=float(np.median(a)),
                q05=float(np.quantile(a,.05)), q95=float(np.quantile(a,.95)),
                mcse=float(a.std(ddof=1)/np.sqrt(len(a))))

summaries, paired = [], []
for law in (0, 1):
    for arm in ('FLAT', 'GAPS'):
        for count in COUNTS:
            group=[r for r in rows if (r['law'],r['arm'],r['candidates'])==(law,arm,count)]
            summaries.append(dict(law=law,arm=arm,candidates=count,
                metrics={key:describe([r[key] for r in group]) for key in
                         ('regret','optimism','audit_error','fixed_candidate_decision_error','fixed_candidate_audit_error')}))
        low=[r for r in rows if (r['law'],r['arm'],r['candidates'])==(law,arm,12)]
        high=[r for r in rows if (r['law'],r['arm'],r['candidates'])==(law,arm,12560)]
        paired.append(dict(law=law,arm=arm,high_minus_low={key:describe([h[key]-l[key] for h,l in zip(high,low)])
                                                       for key in ('regret','optimism','audit_error')}))
assert len(rows)==2000
assert len({(r['law'],r['arm'],r['candidates'],r['replicate']) for r in rows})==2000
result=dict(rows=rows, summaries=summaries,paired=paired,elapsed_seconds=time.monotonic()-START,
    coefficient_sha256=hashlib.sha256(coeff.tobytes()).hexdigest(),
    offset_sha256=hashlib.sha256(offsets.tobytes()).hexdigest(),
    provenance=dict(python=platform.python_version(),numpy=np.__version__,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        git_status=subprocess.check_output(['git','status','--porcelain'],text=True),
        threads={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}),
    checks='2000 unique cells; exact centering; nonnegative regret; flat zero regret; nested decision maxima; all selected decision/audit values scalar-recomputed')
with OUT.open('x') as f:
    json.dump(result,f,indent=2,allow_nan=False)
for s in summaries:
    print(s['law'],s['arm'],s['candidates'],{key:round(value['mean'],6) for key,value in s['metrics'].items()})
print('Elapsed seconds:',result['elapsed_seconds'])
