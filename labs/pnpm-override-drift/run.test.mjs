// Static tests for the fixtures and checks, plus the end-to-end offline observations.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { checks, lockfileEdge, LOCKFILES } from './run.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const read = (name) => readFileSync(join(HERE, 'fixtures', `${name}.pnpm-lock.yaml`), 'utf8');

test('fixtures differ only where intended', () => {
  const [faithful, noHeader, headerOnly] = LOCKFILES.map(read);
  assert.equal(lockfileEdge(faithful, 'satori', 'fflate'), '0.7.5');
  assert.equal(lockfileEdge(noHeader, 'satori', 'fflate'), '0.7.3');
  assert.equal(lockfileEdge(headerOnly, 'satori', 'fflate'), '0.7.3');
  for (const lock of [faithful, noHeader, headerOnly]) {
    assert.equal(lockfileEdge(lock, '@shuding/opentype.js', 'fflate'), '0.7.5');
  }
  // header-only is exactly no-header plus the three-line overrides block.
  assert.equal(headerOnly.replace('overrides:\n  satori>fflate: 0.7.5\n\n', ''), noHeader);
});

test('negative control: edge parser returns null for an absent edge', () => {
  assert.equal(lockfileEdge(read('faithful'), 'satori', 'no-such-dep'), null);
  assert.equal(lockfileEdge('lockfileVersion: 9.0\n', 'satori', 'fflate'), null);
});

test('static checks: only the edge check rejects every degraded lockfile', () => {
  const verdicts = Object.fromEntries(LOCKFILES.map((n) => [n, Object.fromEntries(
    Object.entries(checks).map(([k, f]) => [k, f(read(n))]))]));
  assert.deepEqual(verdicts.faithful, { headerPresent: true, patchedVersionPresent: true, edgeMatchesOverride: true });
  assert.deepEqual(verdicts['no-header'], { headerPresent: false, patchedVersionPresent: true, edgeMatchesOverride: false });
  assert.deepEqual(verdicts['header-only'], { headerPresent: true, patchedVersionPresent: true, edgeMatchesOverride: false });
});

test('pnpm behaviour, offline, pinned 10.33.0', () => {
  const record = JSON.parse(execFileSync(process.execPath, [join(HERE, 'run.mjs')], { encoding: 'utf8', maxBuffer: 1 << 24 }));
  assert.equal(record.environment.pnpm, '10.33.0');
  const by = Object.fromEntries(record.observations.map((o) => [o.lockfile, o]));
  // Positive control.
  assert.equal(by.faithful.frozenInstall.exit, 0);
  assert.equal(by.faithful.installedSatoriFflate, '0.7.5');
  assert.equal(by.faithful.dedupeCheck.exit, 0);
  assert.equal(by.faithful.lockfileOnlyRegeneration.changed, false);
  // Loud half: frozen install refuses; regeneration restores header and edge.
  assert.equal(by['no-header'].frozenInstall.error, 'ERR_PNPM_LOCKFILE_CONFIG_MISMATCH');
  assert.equal(by['no-header'].lockfileOnlyRegeneration.satoriFflateAfter, '0.7.5');
  assert.equal(by['no-header'].lockfileOnlyRegeneration.headerAfter, true);
  // Header-only repair: frozen install succeeds and installs the overridden-away version.
  assert.equal(by['header-only'].frozenInstall.exit, 0);
  assert.equal(by['header-only'].installedSatoriFflate, '0.7.3');
  assert.equal(by['header-only'].lockfileOnlyRegeneration.changed, false);
  assert.notEqual(by['header-only'].dedupeCheck.exit, 0);
});
