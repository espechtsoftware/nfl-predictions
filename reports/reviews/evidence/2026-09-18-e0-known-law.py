"""Bounded synthetic E0; no NFL inputs or cloud access."""
import argparse
import hashlib
import itertools
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np

TOL = 1e-12
COUNTS = (32, 128, 512, 2048)


def choose(values):
    return int(np.flatnonzero(values >= values.max() - TOL)[0])


def greedy(scores, weights, k):
    selected = []
    current = None
    for _ in range(k):
        values = (scores if current is None else np.maximum(scores, current)) @ weights
        values[selected] = -np.inf
        pick = choose(values)
        selected.append(pick)
        current = scores[pick].copy() if current is None else np.maximum(current, scores[pick])
    return selected


def problem(prob):
    states = np.array(list(itertools.product((0, 1), repeat=6)), dtype=np.int64)
    weights = np.prod(np.where(states == 1, prob, 1 - prob), axis=1)
    scores = []
    for i in range(12):
        a, b, c = i % 6, (i % 6 + 1) % 6, (i % 6 + 3) % 6
        scores.append(120 + 2*i + 55*states[:, a] + 35*states[:, b] + 20*states[:, c]
                      + 15*(i >= 6)*states[:, a]*states[:, b])
    return states, np.array(scores, dtype=float), weights


def mechanics():
    # Highest two standalone means duplicate each other; marginal gain picks complement.
    fixture = np.array([[10., 0.], [9., 0.], [0., 8.]])
    weights = np.array([.5, .5])
    assert greedy(fixture, weights, 2) == [0, 2]
    for subset in itertools.combinations(range(3), 2):
        direct = sum(weights[s]*max(fixture[i, s] for i in subset) for s in range(2))
        assert abs(direct - np.max(fixture[list(subset)], axis=0) @ weights) < TOL
    assert choose(np.array([1., 1.])) == 0
    for prob in (.5, .1):
        _, scores, p = problem(prob)
        assert np.isclose(p.sum(), 1.) and np.all(p > 0) and np.isfinite(scores).all()
        for k in (1, 3):
            subsets = list(itertools.combinations(range(12), k))
            maxima = np.array([scores[list(s)].max(axis=0) for s in subsets])
            best = choose(maxima @ p)
            g = greedy(scores, p, k)
            assert (maxima @ p)[best] + TOL >= scores[g].max(axis=0) @ p
            if k == 1:
                assert list(subsets[best]) == g
    return {'passed': True, 'checks': ['complementary marginal gain', 'direct objective parity',
            'deterministic ties', 'probability mass', 'population exact dominance', 'K1 parity']}


def summary(values):
    a = np.array(values, dtype=float)
    return dict(n=len(a), mean=float(a.mean()), median=float(np.median(a)),
                q05=float(np.quantile(a, .05)), q95=float(np.quantile(a, .95)),
                mcse=float(a.std(ddof=1)/np.sqrt(len(a))))


def run():
    started = time.monotonic()
    checks = mechanics()
    rows, populations = [], []
    for law_index, prob in enumerate((.5, .1)):
        states, scores, p = problem(prob)
        for k in (1, 3):
            subsets = list(itertools.combinations(range(12), k))
            maxima = np.array([scores[list(s)].max(axis=0) for s in subsets])
            true_values = maxima @ p
            optimal_index = choose(true_values)
            optimum = float(true_values[optimal_index])
            true_greedy = greedy(scores, p, k)
            populations.append(dict(law=law_index, k=k, probability=prob, states=states.tolist(),
                scores=scores.tolist(), weights=p.tolist(),
                array_sha256=hashlib.sha256(scores.tobytes()+p.tobytes()).hexdigest(),
                optimum=optimum, optimum_book=list(subsets[optimal_index]),
                true_greedy=true_greedy,
                population_greedy_gap=optimum-float(scores[true_greedy].max(axis=0) @ p)))
            for replicate in range(100):
                if time.monotonic()-started > 300:
                    raise TimeoutError('Five-minute bound exceeded; run incomplete')
                decision_seed = np.random.SeedSequence([20260918, law_index, replicate, 0])
                audit_seed = np.random.SeedSequence([20260918, law_index, replicate, 1])
                assert decision_seed.entropy != audit_seed.entropy
                decision = np.random.Generator(np.random.PCG64(decision_seed)).choice(64, 2048, p=p)
                audit = np.random.Generator(np.random.PCG64(audit_seed)).choice(64, 8192, p=p)
                audit_weights = np.bincount(audit, minlength=64)/8192
                for count in COUNTS:
                    empirical = np.bincount(decision[:count], minlength=64)/count
                    exact_index = choose(maxima @ empirical)
                    exact_book = list(subsets[exact_index])
                    g = greedy(scores, empirical, k)
                    assert len(set(g)) == k
                    if k == 1:
                        assert exact_book == g
                    g_max = scores[g].max(axis=0)
                    e_max = maxima[exact_index]
                    g_true = float(g_max @ p)
                    e_true = float(e_max @ p)
                    g_est = float(g_max @ empirical)
                    e_est = float(e_max @ empirical)
                    assert e_est + 1e-10 >= g_est
                    selection_loss = optimum-e_true
                    signed_gap = e_true-g_true
                    regret = optimum-g_true
                    assert selection_loss >= -1e-10
                    assert abs(regret-selection_loss-signed_gap) < 1e-10
                    rows.append(dict(law=law_index, k=k, replicate=replicate, worlds=count,
                        greedy_order=g, exact_book=exact_book, greedy_true=g_true, exact_true=e_true,
                        greedy_decision=g_est, exact_decision=e_est,
                        greedy_audit=float(g_max @ audit_weights), exact_audit=float(e_max @ audit_weights),
                        regret=regret,
                        exact_selection_loss=selection_loss, signed_search_effect=signed_gap,
                        optimism=g_est-g_true, audit_error=float(g_max @ audit_weights)-g_true,
                        greedy_p220_true=float((g_max >= 220) @ p),
                        greedy_p220_decision=float((g_max >= 220) @ empirical),
                        greedy_p220_audit=float((g_max >= 220) @ audit_weights),
                        exact_p220_true=float((e_max >= 220) @ p),
                        exact_p220_decision=float((e_max >= 220) @ empirical),
                        exact_p220_audit=float((e_max >= 220) @ audit_weights)))
    summaries, paired = [], []
    for law in (0, 1):
        for k in (1, 3):
            for n in COUNTS:
                group = [r for r in rows if (r['law'], r['k'], r['worlds']) == (law, k, n)]
                summaries.append(dict(law=law, k=k, worlds=n, metrics={key:summary([r[key] for r in group])
                    for key in ('regret', 'exact_selection_loss', 'signed_search_effect', 'optimism', 'audit_error')}))
            low = [r['regret'] for r in rows if (r['law'], r['k'], r['worlds']) == (law, k, 32)]
            high = [r['regret'] for r in rows if (r['law'], r['k'], r['worlds']) == (law, k, 2048)]
            paired.append(dict(law=law, k=k, high_minus_low_regret=summary(np.array(high)-low)))
    return dict(mechanics=checks, populations=populations, rows=rows, summaries=summaries,
                paired=paired, elapsed_seconds=time.monotonic()-started)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mechanics-only', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mechanics_only:
        print(json.dumps(mechanics(), indent=2))
    else:
        if args.output is None or args.output.exists():
            raise SystemExit('A new output path is required; overwrites refused')
        result = run()
        result['provenance'] = dict(python=platform.python_version(), numpy=np.__version__,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            git_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            git_status=subprocess.check_output(['git', 'status', '--porcelain'], text=True),
            thread_env={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')})
        with args.output.open('x') as f:
            json.dump(result, f, indent=2, allow_nan=False)
        print(json.dumps({'elapsed_seconds': result['elapsed_seconds'], 'rows':len(result['rows']),
                          'paired':result['paired']}, indent=2))
