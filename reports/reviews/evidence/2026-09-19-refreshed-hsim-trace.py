"""Observe the unchanged morning hsim path; require exact archived-bank parity."""
from __future__ import annotations

import hashlib
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def write(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def main():
    started = time.monotonic()
    signal.alarm(600)
    here = Path(__file__).resolve().parent
    manifest_path = here / '2026-09-19-refreshed-hsim-trace-inputs.json'
    spec = json.loads(manifest_path.read_text())
    root = Path(__file__).resolve().parents[3]
    assert not git(root, 'status', '--porcelain'), 'freeze diagnostic source first'
    lab, run = Path(spec['lab']), Path(spec['run'])
    assert git(lab, 'rev-parse', 'HEAD') == spec['source_sha']
    assert not git(lab, 'status', '--porcelain'), 'pinned source must be clean'
    for name, expected in spec['source_files'].items():
        assert digest(lab / name) == expected, name
    for name, rec in spec['files'].items():
        assert (run / name).stat().st_size == rec['bytes']
        assert digest(run / name) == rec['sha256'], name
    out = Path(spec['output'])
    assert not out.exists()
    receipt = json.loads((run / 'receipt.json').read_text())
    assert receipt['identity']['sha'] == spec['source_sha'] and not receipt['identity']['dirty']
    assert receipt['config']['production_generated_at'] == '2026-09-19 15:09:52.915006+00:00'
    assert receipt['config']['hsim_seed'] == spec['seed']
    assert receipt['config']['hsim_worlds'] == spec['worlds']
    assert 'actual' not in spec['frame_columns']
    frame = pq.read_table(run / 'frame.parquet', columns=spec['frame_columns']).to_pandas()
    assert len(frame) == frame.id.nunique() == spec['n_players']
    assert frame.dk_player_id.astype(str).is_unique
    candidates = pq.read_table(run / 'candidates.parquet', columns=['players', 'book_rank']).to_pandas()
    assert len(candidates) == spec['n_candidates']
    index = {str(v): i for i, v in enumerate(frame.id)}
    rosters = np.asarray([[index[v] for v in text.split(',')] for text in candidates.players])
    assert rosters.shape == (spec['n_candidates'], 9)
    assert all(len(set(row)) == 9 for row in rosters)
    assert len({tuple(sorted(row)) for row in rosters}) == len(rosters)
    selected = candidates[candidates.book_rank.notna()].sort_values('book_rank').index.to_numpy()
    assert len(selected) == len(set(selected)) == spec['book_size']
    dk_index = {str(v): i for i, v in enumerate(frame.dk_player_id)}
    csv_book = pd.read_csv(run / 'book.csv', dtype=str)
    csv_rosters = np.asarray([[dk_index[v] for v in row] for row in csv_book.to_numpy()])
    assert np.array_equal(np.sort(csv_rosters, axis=1), np.sort(rosters[selected], axis=1))
    saved = {}
    for law, name in [('I', 'incumbent_player_scores.npy'), ('H', 'corrected_hsim_player_scores.npy')]:
        saved[law] = np.load(run / name, mmap_mode='r', allow_pickle=False)
        assert saved[law].shape == (len(frame), spec['worlds'])
        assert saved[law].dtype == np.float32 and np.isfinite(saved[law]).all()

    # Only the already-authenticated historical inputs are accessible to the simulator.
    files = {}
    for rec in spec['benchmark']:
        rel = rec['uri'].split('/benchmark/v0/', 1)[1]
        path = Path(spec['benchmark_cache']) / rel
        assert digest(path) == rec['sha256'], rel
        files[rel] = path
    sys.path.insert(0, str(lab / 'src'))
    import nfl2.data as data
    from nfl2.hsim import world
    from nfl2.hsim.live_games import validate_game_inputs
    from nfl2.hsim.shares import active_mask, _prior_weights, TARGET_POS, CARRY_POS
    assert Path(world.__file__).resolve() == lab / 'src/nfl2/hsim/world.py'

    def allowed_list(prefix):
        assert prefix in {'warehouse/' + n + '/' for n in
                          ('player_week_training', 'raw_weekly_stats', 'raw_schedules')}
        return sorted(k for k in files if k.startswith(prefix))

    def allowed_fetch(key):
        assert key in files, key
        return files[key]

    data._list, data._fetch = allowed_list, allowed_fetch
    games = pd.DataFrame(receipt['config']['hsim_game_inputs']['games'])
    games = validate_game_inputs(frame, games, spec['season'], spec['week'])
    pilot = []
    original = world._sample

    def observed(fr, season, week, n_worlds, seed, wt, wc, *args, **kwargs):
        result = original(fr, season, week, n_worlds, seed, wt, wc, *args, **kwargs)
        if n_worlds == 400:
            assert seed == spec['seed'] + 1000 + len(pilot)
            pilot.append(dict(seed=seed, means=result.mean(axis=1).tolist(),
                              target_weights=wt.tolist(), carry_weights=wc.tolist(),
                              team_eff=dict(kwargs['team_eff'])))
        return result

    world._sample = observed
    capture = {}
    try:
        with data.outcome_firewall(spec['season']):
            reproduced = world.simulate_hsim(frame, spec['season'], spec['week'],
                                            spec['worlds'], spec['seed'],
                                            calibrate=spec['calibrate'], capture=capture,
                                            game_inputs=games).astype(np.float32)
    finally:
        world._sample = original
    assert len(pilot) == spec['calibrate']
    equal = bool(np.array_equal(reproduced, saved['H']))
    provenance = dict(source_commit=git(root, 'rev-parse', 'HEAD'),
                      script_sha256=digest(__file__), manifest_sha256=digest(manifest_path),
                      lab_sha=spec['source_sha'], current_outcomes_read=False,
                      elapsed_seconds=time.monotonic() - started)
    if not equal:
        write(out, dict(exact_parity=False, max_absolute_difference=float(
            np.abs(reproduced.astype(float) - saved['H']).max()), provenance=provenance))
        raise RuntimeError('Replay mismatch: no substantive attribution emitted')

    tm = frame.team.astype(str).to_numpy()
    pos = frame.pos.astype(str).to_numpy()
    skill = np.isin(pos, ['RB', 'WR', 'TE'])
    target = frame.mean_projection.to_numpy(float)
    initial_t = _prior_weights(frame, 'target_share_l4', TARGET_POS, world.POS_FALLBACK_T)
    initial_c = _prior_weights(frame, 'carry_share_l4', CARRY_POS, world.POS_FALLBACK_C)
    primary = np.zeros(len(frame), dtype=bool)
    for team in sorted(set(tm)):
        idx = np.flatnonzero((tm == team) & (pos == 'QB'))
        if len(idx):
            primary[idx[np.argmax(frame.proj.to_numpy(float)[idx])]] = True
    players = frame.copy()
    players['selected_exposure'] = np.bincount(rosters[selected].ravel(), minlength=len(frame))
    players['pool_exposure'] = np.bincount(rosters.ravel(), minlength=len(frame))
    players['active_proxy'] = active_mask(frame)
    players['primary_qb'] = primary
    players['initial_target_weight'] = initial_t
    players['initial_carry_weight'] = initial_c
    players['final_target_weight'] = capture['w_t']
    players['final_carry_weight'] = capture['w_c']
    for law, bank in saved.items():
        players[law + '_mean'] = bank.mean(axis=1, dtype=np.float64)
    players['H_minus_served'] = players.H_mean - target
    players['H_minus_I'] = players.H_mean - players.I_mean
    for name in ('targets', 'carries', 'rec', 'rec_yds', 'rush_yds', 'rec_tds', 'rush_tds', 'pass_yds', 'pass_tds'):
        players[name + '_mean'] = capture[name].mean(axis=1, dtype=np.float64)
    summaries = []
    for population, mask in [('all', np.ones(len(frame), dtype=bool)),
                             ('selected', players.selected_exposure.to_numpy() > 0)]:
        for p in sorted(set(pos)):
            ix = mask & (pos == p)
            if not ix.any():
                continue
            delta = players.loc[ix, 'H_minus_served'].to_numpy()
            summaries.append(dict(population=population, pos=p, n=int(ix.sum()),
                                  mean_offset=float(delta.mean()),
                                  mean_absolute_offset=float(np.abs(delta).mean())))
    team_rows = []
    for ti, team in enumerate(capture['teams']):
        mask = tm == team
        s = mask & skill
        expected_t = capture['flat']['dropbacks'][ti] - capture['flat']['sacks'][ti]
        expected_c = capture['flat']['carries'][ti]
        allocated_t = capture['targets'][mask].sum(axis=0)
        allocated_c = capture['carries'][mask].sum(axis=0)
        assert np.array_equal(allocated_t, expected_t), ('target conservation', team)
        assert np.array_equal(allocated_c, expected_c), ('carry conservation', team)
        # Passing production is assigned exactly once to the primary QB.
        q = mask & primary
        if q.any():
            assert np.array_equal(capture['pass_yds'][q].sum(axis=0),
                                  capture['rec_yds'][mask].sum(axis=0))
            assert np.array_equal(capture['pass_tds'][q].sum(axis=0),
                                  capture['rec_tds'][mask].sum(axis=0))
        team_rows.append(dict(team=team, served_skill_total=float(target[s].sum()),
                              simulated_skill_total=float(players.loc[s, 'H_mean'].sum()),
                              mean_targets=float(allocated_t.mean()), mean_carries=float(allocated_c.mean()),
                              team_eff=float(capture['team_eff'][team]),
                              pilot_skill_totals=[float(np.asarray(p['means'])[s].sum()) for p in pilot],
                              target_weight_sums=[float(np.asarray(p['target_weights'])[mask].sum()) for p in pilot],
                              carry_weight_sums=[float(np.asarray(p['carry_weights'])[mask].sum()) for p in pilot]))
    steps = []
    for it, p in enumerate(pilot):
        cur = np.asarray(p['means'])
        eligible = np.isfinite(target) & skill & (cur > .3) & (target > .3)
        ratios = target[eligible] / cur[eligible]
        steps.append(dict(iteration=it, skill_mean_absolute_residual=float(np.abs(cur[skill] - target[skill]).mean()),
                          clipped_low=int((ratios < .5).sum()), clipped_high=int((ratios > 2).sum()),
                          team_eff_floor=sum(v == .5 for v in p['team_eff'].values()),
                          team_eff_ceiling=sum(v == 1.8 for v in p['team_eff'].values())))
    book_metrics = {}
    for law, bank in saved.items():
        totals = np.stack([bank[row].sum(axis=0, dtype=np.float32) for row in rosters[selected]])
        mx = totals.max(axis=0).astype(float)
        book_metrics[law] = dict(expected_max=float(mx.mean()), p220=float((mx >= 220).mean()))
    zero = skill & (initial_t == 0) & (initial_c == 0) & (target > 0)
    result = dict(exact_parity=True, conservation_passed=True, n_verified_scores=int(reproduced.size),
                  groups=summaries, team_rows=team_rows, calibration_steps=steps, pilots=pilot,
                  players=json.loads(players.to_json(orient='records', double_precision=12)),
                  zero_support_ids=frame.loc[zero, 'id'].astype(str).tolist(),
                  selected_zero_support_ids=frame.loc[zero & (players.selected_exposure > 0), 'id'].astype(str).tolist(),
                  fixed_book=book_metrics, provenance=provenance,
                  scope='Same saved D160/K97 input trace; no model intervention or outcome evaluation.')
    write(out, result)
    print(json.dumps({k: result[k] for k in ('exact_parity', 'conservation_passed', 'groups',
                                           'calibration_steps', 'selected_zero_support_ids', 'fixed_book')}, indent=2))


if __name__ == '__main__':
    main()
