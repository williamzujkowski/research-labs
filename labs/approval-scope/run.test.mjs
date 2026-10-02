// Parser tests on fixed strace text, then the controls and one positive arm end to end.
import assert from 'node:assert/strict';
import test from 'node:test';
import { classify, observe, parseTrace, scriptCommands } from './run.mjs';

const SAMPLE = [
  '10 execve("/usr/local/bin/npm", ["npm", "install"], 0x7ffd /* 9 vars */) = 0',
  '11 execve("/usr/local/sbin/sh", ["sh", "-c", "node canary.js app:postinstall"], 0x1 /* 9 vars */) = -1 ENOENT (No such file or directory)',
  '11 execve("/bin/sh", ["sh", "-c", "node canary.js app:postinstall"], 0x1 /* 9 vars */ <unfinished ...>',
  '12 openat(AT_FDCWD, "/w/app/package.json", O_RDONLY|O_CLOEXEC) = 3',
  '11 <... execve resumed>) = 0',
  '13 openat(AT_FDCWD, "/w/app/.git/hooks/pre-commit", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0755) = -1 EROFS (Read-only file system)',
  '13 mkdir("/w/app/.canary", 0777) = -1 EEXIST (File exists)',
  '13 rename("/w/app/node_modules/.tmp", "/w/app/node_modules/canary-dep") = 0',
  '14 openat(AT_FDCWD, "relative/file", O_WRONLY|O_CREAT, 0644) = 4',
  '15 +++ exited with 0 +++',
].join('\n');

test('parser: successful execs only, resumed lines rejoined', () => {
  const { execs } = parseTrace(SAMPLE);
  assert.deepEqual(execs.map((e) => e.argv), [['npm', 'install'], ['sh', '-c', 'node canary.js app:postinstall']]);
  assert.deepEqual(scriptCommands(execs), ['node canary.js app:postinstall']);
});

test('parser: reads are ignored, EEXIST is not a mutation, denials keep their errno', () => {
  const { mutations } = parseTrace(SAMPLE);
  assert.deepEqual(mutations.map((m) => [m.call, m.path, m.ok, m.errno]), [
    ['openat', '/w/app/.git/hooks/pre-commit', false, 'EROFS'],
    ['rename', '/w/app/node_modules/canary-dep', true, null],
    ['openat', 'relative/file', true, null],
  ]);
});

test('classify: hooks, workspace, outside and relative paths are distinct', () => {
  const c = (p) => classify(p, '/w/app', '/w/outside');
  assert.equal(c('/w/app/.git/hooks/pre-commit'), 'workspace-.git/hooks');
  assert.equal(c('/w/app/.git/index'), 'workspace-.git-other');
  assert.equal(c('/w/app/node_modules/x'), 'workspace-node_modules');
  assert.equal(c('/w/app/.canary/x'), 'workspace-.canary');
  assert.equal(c('/w/app/src/x'), 'workspace-other');
  assert.equal(c('/w/outside/x'), 'outside-workspace-marker-dir');
  assert.equal(c('/w/application/x'), 'elsewhere');
  assert.equal(c('/tmp/x'), 'elsewhere');
  assert.equal(c('relative/x'), 'relative-path');
});

// Control first: with --ignore-scripts nothing may run, or no other arm can be read.
for (const arm of ['npm-install-ignore-scripts', 'npm-ci-ignore-scripts', 'pnpm-install-ignore-scripts']) {
  test(`control ${arm}: no lifecycle script, marker or hook`, () => {
    const o = observe(arm);
    assert.equal(o.install.exit, 0);
    assert.equal(o.install.traceCaptured, true);
    assert.deepEqual(o.install.lifecycleScripts, []);
    assert.deepEqual(o.install.markersInside, []);
    assert.deepEqual(o.install.markersOutside, []);
    assert.equal(o.install.preCommitHookPresent, false);
    assert.equal(o.commit.hookRan, false);
  });
}

// Positive control: the same tracer and marker checks must see the canaries when they run.
test('positive npm-install: three scripts, markers on both sides, hook fires at commit', () => {
  const o = observe('npm-install');
  assert.equal(o.install.exit, 0);
  assert.deepEqual(o.install.lifecycleScripts, ['node canary.js dep:postinstall', 'node canary.js app:postinstall', 'node install-hook.js']);
  assert.deepEqual(o.install.markersInside, ['app:postinstall', 'dep:postinstall']);
  assert.deepEqual(o.install.markersOutside, ['app:postinstall', 'dep:postinstall']);
  assert.equal(o.install.preCommitHookPresent, true);
  assert.equal(o.commit.hookRan, true);
  assert.equal(o.commit.canaryExecs, 1);
});

// The test container refuses user namespaces, so sandbox-runtime cannot build its sandbox.
// It must refuse to run the command rather than run it unsandboxed.
test('sandbox-runtime without user namespaces: command does not run', () => {
  const o = observe('npm-install', { sandbox: true });
  assert.notEqual(o.install.exit, 0);
  assert.equal(o.install.processesStarted, 0);
  assert.deepEqual(o.install.markersInside, []);
  assert.deepEqual(o.install.markersOutside, []);
  assert.equal(o.install.preCommitHookPresent, false);
});
