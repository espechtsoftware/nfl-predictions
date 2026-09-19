"""Reconstruct both archived laws exactly, then draw the declared fresh audits.

No current outcome reads or provider queries. Proposal identities precede audits.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from google.cloud import bigquery

HERE = Path(__file__).parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
MORNING = ROOT.parent / 'morning-refresh-20260919'
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
SOURCE = '2dc116ce95647a776ba9c36cf194f44d022d03a4'
FROZEN_BOOKS = '87262e06f43a6352f7b92df1a4aacd5d6913fb9c0abb759e630b69b86cd38ecd'
OUT = ROOT / 'reselection-fresh-audit'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    signal.alarm(600)
    started = time.monotonic()
    assert sha(ROOT / 'reselection-proposals/frozen-books.json') == FROZEN_BOOKS
    assert subprocess.check_output(['git', '-C', str(LAB), 'rev-parse', 'HEAD'], text=True).strip() == SOURCE
    assert not subprocess.check_output(['git', '-C', str(LAB), 'status', '--porcelain'], text=True).strip()
    assert not any(os.environ.get(k) for k in ('EXTRA_FEATURES', 'DROP_FEATURES', 'DRAFT_PRIORS'))
    os.environ['MODEL_ENSEMBLE'] = '1'
    def forbidden(*args, **kwargs):
        raise AssertionError('provider query forbidden in frozen audit')
    bigquery.Client.query = forbidden
    sys.path.insert(0, str(LAB / 'src'))
    from nfl2.core import components, coldstart, simulate, featureset
    from nfl2.core.draw_shape import apply_draw_shape, apply_served_position_scales
    from nfl2.core.blend import shift_draws_to_means
    from nfl2.pipeline import PRODUCTION_ENV
    from nfl2 import data
    from nfl2.hsim import world
    from nfl2.hsim.live_games import from_live_schedule, game_input_receipt
    trace = json.loads((HERE / '2026-09-19-refreshed-hsim-trace-inputs-v2.json').read_text())
    for name, digest in trace['source_files'].items():
        assert sha(LAB / name) == digest
    for name, r in trace['files'].items():
        if name in ('frame.parquet', 'incumbent_player_scores.npy', 'corrected_hsim_player_scores.npy'):
            assert sha(ROOT / 'source' / name) == r['sha256']
    cols = sorted(set(trace['frame_columns'] + featureset.FEATURES +
        ['name', 'gsis_id', 'season', 'week', 'has_features', 'is_rookie', 'draft_round', 'dk_ppg']))
    assert 'actual' not in cols
    fr = pd.read_parquet(ROOT / 'source/frame.parquet', columns=cols)
    rec = json.loads((ROOT / 'source/receipt.json').read_text())
    train_path = MORNING / 'host-training.parquet'
    cache_path = MORNING / 'refreshed-cache.parquet'
    assert sha(train_path) == '8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7'
    assert sha(cache_path) == '834e5176f7b12a30f0ead08edfe389b774207bd3c7d2fdb5547c8f2787c79f45'
    training = pd.read_parquet(train_path)
    assert training.season.max() <= 2025
    OUT.mkdir(exist_ok=False)
    model = components.train(training, target_season=2026)
    skill = fr.position.isin(['QB', 'RB', 'WR', 'TE']).to_numpy()
    modeled = skill & fr.has_features.to_numpy()
    rows = coldstart.fill_cold_start_features(fr[modeled].copy())
    comps = model.predict_components(rows)
    comps.to_parquet(OUT / 'components.parquet', index=False)
    keys = rows[['gsis_id', 'season', 'week']].reset_index(drop=True)
    tabcols = ['gsis_id', 'season', 'week', 'mean'] + ['q' + str(q).zfill(2) for q in [1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]]
    tab = pd.read_parquet(cache_path, columns=tabcols)
    tab = tab[tab.season.eq(2026) & tab.week.eq(2)].copy()
    assert len(tab) == 877
    target = fr.mean_projection.to_numpy(float)

    def incumbent(seed):
        d = np.zeros((len(fr), 10000))
        sim = simulate.simulate(comps, n_sims=10000, seed=seed, keep_draws=True,
            game_ids=rows.game_id.reset_index(drop=True), team_ids=rows.team.reset_index(drop=True),
            game_totals=rows.game_total.reset_index(drop=True), env=PRODUCTION_ENV)
        shaped = apply_draw_shape(sim.draws, rows.position.reset_index(drop=True), seed, keys=keys,
                                  env=PRODUCTION_ENV, tabpfn_cache_rows=tab)
        d[modeled] = apply_served_position_scales(shaped, rows.position.reset_index(drop=True), env=PRODUCTION_ENV)
        rng = np.random.default_rng(seed)
        for i in np.flatnonzero(skill & ~modeled):
            mu = float(fr.dk_ppg.iloc[i]) if pd.notna(fr.dk_ppg.iloc[i]) and fr.dk_ppg.iloc[i] > 0 else 2.
            d[i] = rng.gamma(2., mu / 2., 10000)
        d[skill] = shift_draws_to_means(d[skill], target[skill])
        d[~skill] = target[~skill, None]
        return d.astype(np.float32)

    local = {}
    for r in trace['benchmark']:
        key = r['uri'].split('/benchmark/v0/', 1)[1]
        p = Path(trace['benchmark_cache']) / key
        assert sha(p) == r['sha256']
        local[key] = p
    def listing(prefix):
        assert prefix in {'warehouse/' + x + '/' for x in ('player_week_training', 'raw_weekly_stats', 'raw_schedules')}
        return sorted(k for k in local if k.startswith(prefix))
    def fetching(key):
        assert key in local
        return local[key]
    data._list, data._fetch = listing, fetching
    recorded = rec['config']['hsim_game_inputs']
    schedule = pd.DataFrame(recorded['games']).rename(columns={'home': 'home_team', 'away': 'away_team', 'spread_home': 'spread_line'})
    games = from_live_schedule(fr, schedule, 2026, 2)
    assert game_input_receipt(games) == recorded
    with data.outcome_firewall(2026):
        assert np.array_equal(incumbent(2076), np.load(ROOT / 'source/incumbent_player_scores.npy', allow_pickle=False)), 'incumbent selection parity failed'
        wt, wc, eff = world.calibrate_weights(fr, 2026, 2, 2326, game_inputs=games)
        def hsim(seed):
            return world._sample(fr, 2026, 2, 10000, seed, wt, wc, recenter=False,
                                 team_eff=eff, game_inputs=games).astype(np.float32)
        assert np.array_equal(hsim(2326), np.load(ROOT / 'source/corrected_hsim_player_scores.npy', allow_pickle=False)), 'hsim selection parity failed'
        print('BOTH_D6400_SELECTION_BANKS_EXACT', flush=True)
        banks = {'I': incumbent(20260919), 'H': hsim(21260919)}
    identities = {}
    for name, bank in banks.items():
        assert bank.shape == (429, 10000) and bank.dtype == np.float32 and np.isfinite(bank).all()
        p = OUT / (name + '_audit.npy')
        with p.open('xb') as f:
            np.save(f, bank, allow_pickle=False)
        identities[name] = dict(path=str(p), sha256=sha(p), seed={'I': 20260919, 'H': 21260919}[name])
    result = dict(source_sha256=sha(__file__), frozen_books_sha256=FROZEN_BOOKS,
        model_source=SOURCE, historical_training_sha256=sha(train_path), cache_sha256=sha(cache_path),
        frame_columns=cols, components_sha256=sha(OUT / 'components.parquet'), banks=identities,
        both_selection_banks_exact=True, current_outcomes_read=False, seconds=time.monotonic() - started)
    (OUT / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
