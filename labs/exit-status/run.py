"""Run each published command shape and its corrected form; record what the shell sees.

Every case runs `bash -c <script>` in a fresh temporary directory and records the exit
status, stdout, stderr, and the size and hash of every file left behind. The lab's
question is narrow: does the command report success when the job it was published to do
did not happen, and does the corrected form (the negative control) report the failure?

Prints one JSON document. Exit status: 0 when every case matched its stated
expectation, 3 when any did not (the JSON still records what was observed),
other nonzero values for harness failure.
"""

import hashlib
import http.server
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading

TIMEOUT_SECONDS = 20
OUTPUT_LIMIT = 4096

GPG = 'gpg --batch --pinentry-mode loopback --passphrase-file pass.txt'
FAILING_FETCH = "sh -c 'echo \"fetch failed: 403\" >&2; exit 1'"
PIHOLE = {
    'v6.0': '/opt/pihole-upstream/pihole-v6.0',
    'v6.4.3': '/opt/pihole-upstream/pihole-v6.4.3',
}

# A synthetic copy of the error body an S3-style origin returns for a denied object.
DENIED_BODY = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>'
)
COMPOSE_BODY = b'services:\n  lab:\n    image: example.invalid/lab:1\n'

CASES = [
    # Harness self-check: the runner must be able to see a failure at all.
    {'id': 'harness-sees-failure', 'group': 'harness', 'role': 'control',
     'script': 'exit 7', 'expect': {'exit': 7}},

    # 1. `set -e` with a pipeline: the status is the last command's, and tee succeeds.
    {'id': 'pipe-set-e', 'group': 'pipeline', 'role': 'published',
     'script': 'set -e; false | tee out.log; echo REACHED',
     'expect': {'exit': 0, 'stdout_contains': 'REACHED'}},
    {'id': 'pipe-set-e-pipefail', 'group': 'pipeline', 'role': 'control',
     'script': 'set -eo pipefail; false | tee out.log; echo REACHED',
     'expect': {'exit': 1, 'stdout_lacks': 'REACHED'}},
    {'id': 'pipe-set-e-failing-fetch', 'group': 'pipeline', 'role': 'published',
     'script': f'set -e; {FAILING_FETCH} 2>&1 | tee update.log; echo RELOADING',
     'expect': {'exit': 0, 'stdout_contains': 'RELOADING',
                'files': {'update.log': 'contains:fetch failed'}}},
    {'id': 'pipe-pipefail-failing-fetch', 'group': 'pipeline', 'role': 'control',
     'script': f'set -eo pipefail; {FAILING_FETCH} 2>&1 | tee update.log; echo RELOADING',
     'expect': {'exit': 1, 'stdout_lacks': 'RELOADING',
                'files': {'update.log': 'contains:fetch failed'}}},

    # 2. gpg with a shell redirect: gpg names its own output file; the redirect target
    #    is created empty by the shell.
    {'id': 'gpg-redirect', 'group': 'gpg', 'role': 'published',
     'script': f'{GPG} --symmetric --cipher-algo AES256 seeds.txt > backup.gpg',
     'expect': {'exit': 0, 'files': {'backup.gpg': 'empty', 'seeds.txt.gpg': 'nonempty',
                                     'seeds.txt': 'nonempty'}}},
    {'id': 'gpg-redirect-roundtrip', 'group': 'gpg', 'role': 'check',
     'script': (f'{GPG} --symmetric --cipher-algo AES256 seeds.txt > backup.gpg; '
                f'{GPG} --decrypt backup.gpg > restored.txt; status=$?; '
                'cmp -s seeds.txt restored.txt && echo RESTORED; exit $status'),
     'expect': {'exit_nonzero': True, 'stdout_lacks': 'RESTORED'}},
    {'id': 'gpg-output', 'group': 'gpg', 'role': 'control',
     'script': f'{GPG} --symmetric --cipher-algo AES256 --output backup.gpg seeds.txt',
     'expect': {'exit': 0, 'files': {'backup.gpg': 'nonempty', 'seeds.txt.gpg': 'absent'}}},
    {'id': 'gpg-output-roundtrip', 'group': 'gpg', 'role': 'check',
     'script': (f'{GPG} --symmetric --cipher-algo AES256 --output backup.gpg seeds.txt && '
                f'{GPG} --decrypt --output restored.txt backup.gpg && '
                'cmp -s seeds.txt restored.txt && echo RESTORED'),
     'expect': {'exit': 0, 'stdout_contains': 'RESTORED'}},

    # 3. curl -O against a 403: without --fail the error body becomes the file.
    {'id': 'curl-O-403', 'group': 'curl', 'role': 'published',
     'script': 'curl -sO {base}/denied/docker-compose.yml',
     'expect': {'exit': 0, 'files': {'docker-compose.yml': 'contains:AccessDenied'}}},
    {'id': 'curl-fail-403', 'group': 'curl', 'role': 'control',
     'script': 'curl -fsSO {base}/denied/docker-compose.yml',
     'expect': {'exit': 22, 'files': {'docker-compose.yml': 'absent'}}},
    {'id': 'curl-fail-with-body-403', 'group': 'curl', 'role': 'control',
     'script': 'curl --fail-with-body -sSO {base}/denied/docker-compose.yml',
     'expect': {'exit': 22, 'files': {'docker-compose.yml': 'contains:AccessDenied'}}},
    {'id': 'curl-fail-200', 'group': 'curl', 'role': 'control',
     'script': 'curl -fsSO {base}/ok/docker-compose.yml',
     'expect': {'exit': 0, 'files': {'docker-compose.yml': 'contains:services:'}}},

    # 4. Pi-hole v6 dispatch: an unknown option (including v5's `-a`) falls to helpFunc.
    *[case for tag, path in PIHOLE.items() for case in (
        {'id': f'pihole-{tag}-adlist-add', 'group': 'pihole', 'role': 'published',
         'script': f'bash {path} -a adlist add https://blocklist.invalid/malware',
         'expect': {'exit': 0, 'stdout_contains': 'Usage: pihole',
                    'stdout_equals_case': f'pihole-{tag}-help'}},
        {'id': f'pihole-{tag}-help', 'group': 'pihole', 'role': 'control',
         'script': f'bash {path} --help',
         'expect': {'exit': 0, 'stdout_contains': 'Usage: pihole'}},
    )],
]


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    """Loopback-only origin: /denied/* answers 403 with an XML body, /ok/* answers 200."""

    def do_GET(self):
        if self.path.startswith('/ok/'):
            status, body, kind = 200, COMPOSE_BODY, 'application/yaml'
        else:
            status, body, kind = 403, DENIED_BODY, 'application/xml'
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start_server():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def describe_files(workdir):
    files = {}
    for name in sorted(os.listdir(workdir)):
        path = os.path.join(workdir, name)
        if not os.path.isfile(path) or name == 'pass.txt':
            continue
        with open(path, 'rb') as handle:
            data = handle.read()
        # Ciphertext is random per run; keep only its size and hash.
        head = None if name.endswith('.gpg') else data[:120].decode('utf-8', 'replace')
        files[name] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'head': head}
    return files


def prepare(workdir):
    with open(os.path.join(workdir, 'seeds.txt'), 'w') as handle:
        handle.write('otpauth://totp/lab:synthetic?secret=JBSWY3DPEHPK3PXP\n')
    with open(os.path.join(workdir, 'pass.txt'), 'w') as handle:
        handle.write('synthetic-lab-passphrase\n')
    gnupg = os.path.join(workdir, '.gnupg')
    os.mkdir(gnupg, 0o700)
    return gnupg


def run_case(case, base):
    workdir = tempfile.mkdtemp(prefix=case['id'] + '-')
    try:
        gnupg = prepare(workdir)
        env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': workdir, 'GNUPGHOME': gnupg,
               'LC_ALL': 'C.UTF-8', 'USER': 'lab'}
        script = case['script'].replace('{base}', base)
        try:
            proc = subprocess.run(['bash', '-c', script], cwd=workdir, env=env,
                                  capture_output=True, timeout=TIMEOUT_SECONDS, check=False)
            exit_status, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
        except subprocess.TimeoutExpired as exc:
            exit_status, out, err, timed_out = None, exc.stdout or b'', exc.stderr or b'', True
        subprocess.run(['gpgconf', '--kill', 'all'], env=env, capture_output=True, check=False)
        files = describe_files(workdir)
        return {
            'id': case['id'], 'group': case['group'], 'role': case['role'],
            'script': script, 'expect': case['expect'],
            'exit': exit_status, 'timed_out': timed_out,
            'stdout': out[:OUTPUT_LIMIT].decode('utf-8', 'replace'),
            'stdout_sha256': hashlib.sha256(out).hexdigest(),
            'stderr': err[:OUTPUT_LIMIT].decode('utf-8', 'replace'),
            'files': files,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def check(observation, by_id):
    """Return a list of human-readable expectation failures (empty when matched)."""
    expect, failures = observation['expect'], []
    if 'exit' in expect and observation['exit'] != expect['exit']:
        failures.append(f"exit {observation['exit']} != {expect['exit']}")
    if expect.get('exit_nonzero') and observation['exit'] in (0, None):
        failures.append(f"exit {observation['exit']} is not a nonzero status")
    if 'stdout_contains' in expect and expect['stdout_contains'] not in observation['stdout']:
        failures.append(f"stdout lacks {expect['stdout_contains']!r}")
    if 'stdout_lacks' in expect and expect['stdout_lacks'] in observation['stdout']:
        failures.append(f"stdout contains {expect['stdout_lacks']!r}")
    other = expect.get('stdout_equals_case')
    if other and (other not in by_id or by_id[other]['stdout_sha256'] != observation['stdout_sha256']):
        failures.append(f'stdout differs from {other}')
    for name, want in expect.get('files', {}).items():
        got = observation['files'].get(name)
        if want == 'absent':
            ok = got is None
        elif want == 'empty':
            ok = got is not None and got['size'] == 0
        elif want == 'nonempty':
            ok = got is not None and got['size'] > 0
        elif want.startswith('contains:'):
            ok = got is not None and want[len('contains:'):] in (got['head'] or '')
        else:
            raise ValueError(f'unknown file expectation {want!r}')
        if not ok:
            failures.append(f'{name}: wanted {want}, observed {got and got["size"]} bytes')
    return failures


def tool_versions():
    def first_line(*argv):
        try:
            return subprocess.run(argv, capture_output=True, text=True, check=False).stdout.splitlines()[0]
        except (OSError, IndexError):
            return None
    return {
        'bash': first_line('bash', '--version'),
        'gpg': first_line('gpg', '--version'),
        'curl': first_line('curl', '--version'),
        'python': sys.version.split()[0],
        'pihole_upstream_sha256': {
            tag: hashlib.sha256(open(path, 'rb').read()).hexdigest() for tag, path in PIHOLE.items()
        },
    }


def main():
    server = start_server()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    observations = []
    try:
        by_id = {}
        for case in CASES:
            observation = run_case(case, base)
            by_id[case['id']] = observation
            observations.append(observation)
        for observation in observations:
            observation['expectation_failures'] = check(observation, by_id)
            observation['matched'] = not observation['expectation_failures']
    finally:
        server.shutdown()
        server.server_close()
    report = {
        'lab': 'exit-status',
        'environment': {
            'image_id': os.environ.get('LAB_IMAGE_ID'), 'revision': os.environ.get('LAB_REVISION'),
            'dirty': os.environ.get('LAB_DIRTY'), 'machine': platform.machine(),
            'kernel': platform.release(), 'uid': os.getuid(), **tool_versions(),
        },
        'all_matched': all(o['matched'] for o in observations),
        'cases': observations,
    }
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write('\n')
    return 0 if report['all_matched'] else 3


if __name__ == '__main__':
    sys.exit(main())
