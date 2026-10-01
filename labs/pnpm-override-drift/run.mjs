// Run candidate lockfile checks against three fixed lockfiles for one manifest.
// Offline: packages come from the store populated at image build time.
// Writes one JSON evidence record to stdout.
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cpSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const HERE = new URL('.', import.meta.url).pathname;
const FIXTURES = join(HERE, 'fixtures');
const PNPM = join(HERE, 'tool/node_modules/pnpm/bin/pnpm.cjs');
// pnpm writes project registrations into its store, so run against a writable copy of
// the read-only store baked into the image. Contents are unchanged; nothing is fetched.
const BAKED_STORE = process.env.LAB_PNPM_STORE ?? '/opt/pnpm-store';
const BAKED_CACHE = process.env.LAB_PNPM_CACHE ?? '/opt/pnpm-cache';
let STORE = BAKED_STORE;
let CACHE = BAKED_CACHE;
export const LOCKFILES = ['faithful', 'no-header', 'header-only'];

const sha256 = (text) => createHash('sha256').update(text).digest('hex');

function pnpm(cwd, args) {
  const r = spawnSync(process.execPath, [PNPM, ...args, '--offline', '--ignore-scripts', `--store-dir=${STORE}`, `--cache-dir=${CACHE}`], {
    cwd, encoding: 'utf8', timeout: 120_000,
    env: { ...process.env, CI: 'true', npm_config_update_notifier: 'false', COREPACK_ENABLE_STRICT: '0' },
  });
  const out = `${r.stdout ?? ''}${r.stderr ?? ''}`;
  return { exit: r.status, signal: r.signal, error: (out.match(/ERR_PNPM_[A-Z_]+/) ?? [null])[0], output: out.slice(-4000) };
}

// The resolved edge parent -> child as recorded in the lockfile's snapshots section.
export function lockfileEdge(lock, parent, child) {
  const snapshots = lock.slice(lock.indexOf('\nsnapshots:'));
  let inParent = false;
  for (const line of snapshots.split('\n')) {
    if (/^ {2}\S/.test(line)) inParent = line.trim().replace(/^'/, '').startsWith(`${parent}@`);
    else if (inParent) {
      const m = line.match(new RegExp(`^ {6}${child}: (\\S+)$`));
      if (m) return m[1];
    }
  }
  return null;
}

export const checks = {
  headerPresent: (lock) => /^overrides:\n {2}satori>fflate: 0\.7\.5$/m.test(lock),
  patchedVersionPresent: (lock) => /^ {2}fflate@0\.7\.5:/m.test(lock),
  edgeMatchesOverride: (lock) => lockfileEdge(lock, 'satori', 'fflate') === '0.7.5',
};

function installedEdge(dir) {
  const link = join(dir, 'node_modules/.pnpm/satori@0.33.4/node_modules/fflate');
  if (!existsSync(link)) return null;
  return JSON.parse(readFileSync(join(realpathSync(link), 'package.json'), 'utf8')).version;
}

function observe(name) {
  const dir = mkdtempSync(join(tmpdir(), `lab-${name}-`));
  try {
    cpSync(join(FIXTURES, 'package.json'), join(dir, 'package.json'));
    const lock = readFileSync(join(FIXTURES, `${name}.pnpm-lock.yaml`), 'utf8');
    writeFileSync(join(dir, 'pnpm-lock.yaml'), lock);
    const result = {
      lockfile: name, lockfileSha256: sha256(lock),
      static: Object.fromEntries(Object.entries(checks).map(([k, f]) => [k, f(lock)])),
      lockfileSatoriFflate: lockfileEdge(lock, 'satori', 'fflate'),
      lockfileOpentypeFflate: lockfileEdge(lock, '@shuding/opentype.js', 'fflate'),
    };
    const frozen = pnpm(dir, ['install', '--frozen-lockfile']);
    result.frozenInstall = { exit: frozen.exit, error: frozen.error, ...(frozen.exit ? { tail: frozen.output.slice(-600) } : {}) };
    result.installedSatoriFflate = frozen.exit === 0 ? installedEdge(dir) : null;
    const why = pnpm(dir, ['why', 'fflate', '--json']);
    result.whyFflateExit = why.exit;
    rmSync(join(dir, 'node_modules'), { recursive: true, force: true });
    const dedupe = pnpm(dir, ['dedupe', '--check']);
    result.dedupeCheck = { exit: dedupe.exit, error: dedupe.error };
    writeFileSync(join(dir, 'pnpm-lock.yaml'), lock);
    const regen = pnpm(dir, ['install', '--lockfile-only']);
    const after = readFileSync(join(dir, 'pnpm-lock.yaml'), 'utf8');
    result.lockfileOnlyRegeneration = {
      exit: regen.exit, error: regen.error, changed: after !== lock,
      satoriFflateAfter: lockfileEdge(after, 'satori', 'fflate'), headerAfter: checks.headerPresent(after),
    };
    return result;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const work = mkdtempSync(join(tmpdir(), 'lab-pnpm-'));
  STORE = join(work, 'store');
  CACHE = join(work, 'cache');
  cpSync(BAKED_STORE, STORE, { recursive: true });
  cpSync(BAKED_CACHE, CACHE, { recursive: true });
  const pnpmVersion = spawnSync(process.execPath, [PNPM, '--version'], { encoding: 'utf8' }).stdout.trim();
  const record = {
    lab: 'pnpm-override-drift',
    environment: {
      node: process.version, pnpm: pnpmVersion, platform: `${process.platform}/${process.arch}`,
      imageId: process.env.LAB_IMAGE_ID ?? null, revision: process.env.LAB_REVISION ?? null,
      dirty: process.env.LAB_DIRTY ?? null, startedAt: new Date().toISOString(),
    },
    registryMetadata: ['fflate', 'satori', '@shuding/opentype.js'].map((name) => {
      const j = JSON.parse(readFileSync(join(CACHE, 'metadata-v1.3/registry.npmjs.org', `${name}.json`), 'utf8'));
      return { name, modified: j.modified, cachedAt: j.cachedAt, latest: j['dist-tags']?.latest };
    }),
    manifestSha256:sha256(readFileSync(join(FIXTURES, 'package.json'), 'utf8')),
    observations: LOCKFILES.map(observe),
  };
  process.stdout.write(`${JSON.stringify(record, null, 2)}\n`);
  if (pnpmVersion !== '10.33.0') process.exitCode = 1;
}
