"""Install authorized read-only five-minute Git inbox monitors on this laptop.

Uses existing tested monitor code from an immutable private snapshot and private
bare repositories. Never fetches into, checks out, or merges an active worktree.
It records updates; an active agent still has to read, review and answer them.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[3]
BASE = Path('/home/erich/.local/state/nfl-dfs/review-inboxes-20260919')
UNITS = Path('/home/erich/.config/systemd/user')
PYTHON = '/usr/bin/python3'
CONFIGS = [
    ('shared-handoff', '/home/erich/projects/nfl2', 'https://github.com/espechtsoftware/nfl2.git',
     'lab/workstation-reply-bank991-20260918', False),
    ('production-review', '/home/erich/projects/nfl-predictions',
     'https://github.com/espechtsoftware/nfl-predictions.git', 'main', True),
]


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=55, **kwargs).stdout.strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    BASE.mkdir(parents=True, exist_ok=False)
    runtime = BASE / 'runtime'
    runtime.mkdir()
    shutil.copytree(REPO / 'scripts', runtime / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
    source_sha = run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'])
    sources = {str(p.relative_to(runtime)): sha(p) for p in sorted((runtime / 'scripts').rglob('*.py'))}
    (runtime / 'SOURCE.json').write_text(json.dumps(dict(commit=source_sha, files=sources), indent=2) + '\n')
    UNITS.mkdir(parents=True, exist_ok=True)
    results = []
    for name, source, url, branch, all_branches in CONFIGS:
        state = BASE / name
        state.mkdir()
        repo = state / 'inbox.git'
        # Share existing objects, but keep refs/FETCH_HEAD/index completely private.
        run(['git', 'clone', '--bare', '--shared', source, str(repo)])
        run(['git', '-C', str(repo), 'remote', 'set-url', 'origin', url])
        run(['git', '-C', str(repo), 'config', 'remote.origin.fetch', '+refs/heads/*:refs/remotes/origin/*'])
        args = [PYTHON, '-m', 'scripts.lab_repo_transition_monitor', '--repo', str(repo),
                '--branch', branch, '--state-file', str(state / 'status.json'),
                '--events-file', str(state / 'events.jsonl'), '--poll-seconds', '300',
                '--command-timeout-seconds', '45', '--git', '/usr/bin/git']
        if all_branches:
            args.append('--all-branches')
        run([*args, '--once'], cwd=runtime)
        status = json.loads((state / 'status.json').read_text())
        assert status['poll']['ok'], status
        unit_name = 'nfl-' + name + '-inbox.service'
        unit_path = UNITS / unit_name
        assert not unit_path.exists(), 'never replace another monitor unit'
        unit = '\n'.join([
            '[Unit]', f'Description=Five-minute read-only {name} Git inbox',
            'After=network-online.target', 'Wants=network-online.target', 'StartLimitIntervalSec=0', '',
            '[Service]', 'Type=simple', f'WorkingDirectory={runtime}',
            'Environment=PYTHONDONTWRITEBYTECODE=1', 'ExecStart=' + ' '.join(args),
            'Restart=always', 'RestartSec=15s', 'StandardOutput=journal', 'StandardError=journal', '',
            '[Install]', 'WantedBy=default.target', '',
        ])
        with unit_path.open('x') as f:
            f.write(unit)
        results.append(dict(name=name, service=unit_name, unit_file=str(unit_path), unit_sha256=sha(unit_path),
            repo=str(repo), state_file=str(state / 'status.json'), events_file=str(state / 'events.jsonl'),
            first_verified_poll=status, poll_seconds=300, automatic_review=False))
    run(['systemctl', '--user', 'daemon-reload'])
    for r in results:
        run(['systemctl', '--user', 'enable', '--now', r['service']])
        assert run(['systemctl', '--user', 'is-active', r['service']]) == 'active'
        r['active'] = True
        r['enabled'] = run(['systemctl', '--user', 'is-enabled', r['service']])
    record = dict(source_commit=source_sha, installer_sha256=sha(__file__), immutable_runtime=str(runtime),
        runtime_manifest_sha256=sha(runtime / 'SOURCE.json'), monitors=results,
        scope='Read-only fetch/change log; no automatic code review, reply, merge, cloud or live-book action.')
    (BASE / 'installation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2), flush=True)


if __name__ == '__main__':
    main()
